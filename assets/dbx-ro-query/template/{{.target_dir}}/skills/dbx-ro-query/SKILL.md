---
name: dbx-ro-query
description: Use this skill whenever you need to query a Databricks workspace from the agent shell — schema discovery (DESCRIBE, SHOW), row sampling, aggregations, EXPLAIN, anything that reads but must not mutate. Invoke `scripts/dbx-ro-query.py` instead of calling `databricks experimental aitools tools query` raw, so destructive SQL cannot run by accident. The wrapper allow-lists SELECT / WITH / SHOW / DESCRIBE / DESC / EXPLAIN, blocks every destructive verb after stripping comments and quoted strings, and emits agent-friendly output (auto / scalar / lines / csv / tsv / json) with a shape-aware default that returns 1x1 results as scalars and Nx1 results as lines for token efficiency.
---

# dbx-ro-query

Use this skill to query a Databricks workspace safely. The bundled script enforces a read-only guard before any SQL reaches the warehouse and shapes output for compact agent consumption.

## How to invoke

```bash
python <skill-dir>/scripts/dbx-ro-query.py "<sql>" "<profile>" "<format>"
```

`format` is optional and defaults to `auto`. `profile` is required.

## When to use

- Schema discovery: `DESCRIBE <catalog>.<schema>.<table>`, `SHOW TABLES IN <catalog>.<schema>`, `SHOW CATALOGS`.
- Sample rows for evidence: `SELECT * FROM <catalog>.<schema>.<table> LIMIT 10`.
- Aggregations and counts: `SELECT COUNT(*) FROM ...`.
- Plan inspection: `EXPLAIN SELECT ...`.
- Anything that must not mutate state.

Do not use this skill for migrations, table maintenance, session-mutating commands, or anything destructive. The wrapper will refuse them, but skip the round-trip.

## Allowed SQL starts

The first non-whitespace token of the cleaned statement must be one of:

`SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `DESC`, `EXPLAIN`.

## Rejected verbs anywhere in the statement

`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `OPTIMIZE`, `VACUUM`, `COPY INTO`, `CALL`, `GRANT`, `REVOKE`, `REPAIR`, `MSCK`, `ANALYZE`, `CACHE`, `UNCACHE`, `SET`, `USE`.

The wrapper strips block comments, line comments, and quoted strings before applying the block-list, so `SELECT '/* DROP TABLE x */ 1'` and `SELECT 1; DROP TABLE foo` are rejected.

## Output formats

| Format | Shape it expects | Use when |
|---|---|---|
| `auto` (default) | Any | Quick checks; the wrapper picks scalar / lines / tsv based on result shape |
| `scalar` | 1 row, 1 column | A single count, max, min, etc. |
| `lines` | N rows, 1 column | List of names: tables, columns, distinct values |
| `csv` | N rows, M columns | Pasting into spreadsheets |
| `tsv` | N rows, M columns | **Preferred for evidence captures.** Stable, paste-ready |
| `json` | Any | When downstream tooling needs structured rows |

Prefer `tsv` for evidence captures. Use `auto` for quick interactive checks. Use `json` only when downstream tooling needs structured rows.

## Examples

```bash
# Schema of a sample table (TSV evidence)
python .agents/skills/dbx-ro-query/scripts/dbx-ro-query.py \
  "DESCRIBE samples.nyctaxi.trips" \
  "<your-profile>" "tsv"

# Single-value scalar
python .agents/skills/dbx-ro-query/scripts/dbx-ro-query.py \
  "SELECT COUNT(*) FROM samples.nyctaxi.trips" \
  "<your-profile>" "scalar"

# List of column names, one per line
python .agents/skills/dbx-ro-query/scripts/dbx-ro-query.py \
  "SELECT column_name FROM information_schema.columns WHERE table_schema='nyctaxi' AND table_name='trips'" \
  "<your-profile>" "lines"
```

## Operational notes

- Never call `databricks bundle deploy` or `databricks bundle run` from this skill. The skill's purpose is read-only evidence; deployment is out of scope.
- If your shell runtime has a login/profile option, disable it for invocations of this script. In Codex, set `login: false` on `shell_command`. If output contains valid TSV/results followed by `oh-my-posh`, `Terminal-Icons`, `ResourceUnavailable`, or `Export-Clixml` errors, rerun with the parent shell's no-profile / non-login option.
- If Databricks auth, token cache, or profile access fails because of sandbox restrictions, rerun the same command with the runtime's elevated / outside-sandbox execution mechanism. Do not call raw `databricks experimental aitools tools query` to work around the wrapper.
- Use `python3` on Unix hosts if `python` does not point to Python 3. The script is Python 3.9+, no third-party dependencies.
- Exit code is 0 on success, non-zero on validation failure or upstream CLI error. Stderr carries the upstream error message; stdout carries the formatted result.
- A SQL statement that begins with a line comment (`-- comment\nSELECT 1`) is rejected by the upstream CLI's argv parser, not by this wrapper. Move the comment to the end of the statement, use a block comment, or strip it before invoking.
- The block-list is verb-based, not parser-based. A read-only statement that uses a forbidden verb as a column alias or quoted identifier (`SELECT 1 AS drop`, `SELECT \`drop\` FROM x`) will be rejected. Rename the alias rather than weakening the guard.
