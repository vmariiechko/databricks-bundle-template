#!/usr/bin/env python3
"""Run guarded read-only Databricks SQL and print agent-friendly output.

Wraps `databricks experimental aitools tools query`. The wrapper enforces a
two-layer safety check before delegating to the CLI:

1. The statement must START with one of the allow-listed read-only prefixes
   (SELECT, WITH, SHOW, DESCRIBE, DESC, EXPLAIN).
2. The statement must NOT contain any block-listed destructive verb anywhere
   after we strip block comments, line comments, and quoted strings.

The strip step is what blocks classic smuggling attempts like
`SELECT '/* DROP TABLE foo */ 1'` or stacked statements behind a comment.
Output is shaped for LLM agents: scalar / lines / tsv / csv / json plus an
`auto` mode that picks based on the row-shape.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from typing import Any

ALLOWED_FORMATS = ("auto", "scalar", "lines", "csv", "tsv", "json")

# Only statements that start with one of these tokens are allowed through.
# The match is anchored at the beginning of the cleaned statement.
ALLOWED_START_PATTERNS = (
    r"SELECT\b",
    r"WITH\b",
    r"SHOW\b",
    r"DESCRIBE\b",
    r"DESC\b",
    r"EXPLAIN\b",
)

# Any of these verbs anywhere in the cleaned statement is rejected. The list
# covers the standard DML/DDL surface plus session-mutating verbs (SET, USE)
# and maintenance commands (OPTIMIZE, VACUUM, ANALYZE, ...).
FORBIDDEN_PATTERNS = (
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bMERGE\b",
    r"\bCREATE\b",
    r"\bALTER\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bOPTIMIZE\b",
    r"\bVACUUM\b",
    r"\bCOPY\s+INTO\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bREPAIR\b",
    r"\bMSCK\b",
    r"\bANALYZE\b",
    r"\bCACHE\b",
    r"\bUNCACHE\b",
    r"\bSET\b",
    r"\bUSE\b",
)


def sql_for_inspection(text: str) -> str:
    """Strip comments and quoted strings so forbidden verbs cannot hide in them.

    Without this step, `SELECT '/* DROP TABLE x */ 1'` would slip past the
    block-list because DROP appears inside a string. Order matters: block
    comments first (they may contain quotes), then line comments, then
    string and identifier quotes. Whitespace is collapsed so the start-of-
    statement match is stable.
    """
    clean = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    clean = re.sub(r"--.*?$", " ", clean, flags=re.MULTILINE)
    clean = re.sub(r"'(?:''|[^'])*'", "''", clean)
    clean = re.sub(r'"(?:""|[^"])*"', '""', clean)
    return re.sub(r"\s+", " ", clean).strip()


def validate_read_only_sql(sql: str) -> None:
    """Raise SystemExit if `sql` is not safe to run as a read-only query."""
    upper = sql_for_inspection(sql).upper()
    if not any(re.match(pattern, upper) for pattern in ALLOWED_START_PATTERNS):
        raise SystemExit(
            "Only read-only SQL is allowed. Use SELECT, WITH, SHOW, DESCRIBE, DESC, or EXPLAIN."
        )

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, upper):
            raise SystemExit(
                f"Rejected non-read-only SQL because it matched forbidden pattern: {pattern}"
            )


def normalize_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [row if isinstance(row, dict) else {"value": row} for row in data]
    if isinstance(data, dict):
        return [data]
    return [{"value": data}]


def first_property_value(row: dict[str, Any]) -> Any:
    if not row:
        return None
    return next(iter(row.values()))


def stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def rows_to_delimited(rows: list[dict[str, Any]], delimiter: str) -> str:
    if not rows:
        return ""

    columns = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([stringify(row.get(column)) for column in columns])
    return output.getvalue().rstrip("\n")


def choose_auto_format(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "json"
    if len(rows) == 1 and len(rows[0]) == 1:
        return "scalar"
    if len(rows[0]) == 1:
        return "lines"
    return "tsv"


def format_rows(rows: list[dict[str, Any]], output_format: str) -> str:
    if output_format == "auto":
        output_format = choose_auto_format(rows)

    if output_format == "scalar":
        if len(rows) != 1 or len(rows[0]) != 1:
            raise SystemExit("Format 'scalar' requires exactly one row and one column.")
        return stringify(first_property_value(rows[0]))
    if output_format == "lines":
        return "\n".join(stringify(first_property_value(row)) for row in rows)
    if output_format == "csv":
        return rows_to_delimited(rows, ",")
    if output_format == "tsv":
        tsv = rows_to_delimited(rows, "\t")
        return tsv if tsv.strip() else json.dumps(rows, separators=(",", ":"))
    if output_format == "json":
        return json.dumps(rows, separators=(",", ":"), default=str)

    raise SystemExit(f"Unsupported format: {output_format}")


def load_json_from_lines(lines: Iterable[str]) -> Any:
    text = "\n".join(lines)
    return json.loads(text) if text.strip() else []


def run_query(sql: str, profile: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        [
            "databricks",
            "experimental",
            "aitools",
            "tools",
            "query",
            sql,
            "--profile",
            profile,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        raise SystemExit(proc.returncode)

    return normalize_rows(load_json_from_lines(proc.stdout.splitlines()))


def configure_text_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    configure_text_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sql")
    parser.add_argument("profile")
    parser.add_argument("format", nargs="?", choices=ALLOWED_FORMATS, default="auto")
    args = parser.parse_args(argv)

    validate_read_only_sql(args.sql)
    rows = run_query(args.sql, args.profile)
    output = format_rows(rows, args.format)
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
