#!/usr/bin/env python3
"""Run local PySpark pytest targets and emit a bounded, agent-friendly digest.

Raw pytest output floods an agent's context window when many tests fail with
the same error. This wrapper runs pytest, writes the full stdout/stderr to a
log file, and prints only a compact digest built from the JUnit XML: counts,
runnable failing node ids, and failures deduplicated by a normalized
signature so N identical failures collapse to one block. Total stdout is
capped no matter how many tests fail.

The wrapper script itself adds no third-party dependencies; it runs your
suite, so pytest and PySpark must be installed in the project interpreter.
Local pytest only: no Databricks workspace, deploy, or run.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

# Compaction defaults. --excerpt-lines and --max-failures-listed are exposed
# as CLI flags; the other two are fixed to keep the interface small.
DEFAULT_EXCERPT_LINES = 40
DEFAULT_MAX_FAILURES_LISTED = 20
MAX_SIGNATURES = 3
MAX_OUTPUT_LINES = 120

# How many lines of the log to show when there is no usable JUnit data.
LOG_TAIL_LINES = 60

# How long to wait for a killed process tree to be reaped before giving up,
# so a stuck JVM child cannot make the wrapper hang past its timeout.
REAP_TIMEOUT_SEC = 15

# Bind os.name to a bool. Type checkers narrow os.name to a platform literal
# (e.g. "nt" on Windows), which marks the other branch as unreachable; the
# bool keeps both the Windows and POSIX branches live.
IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------- #
# Environment resolution
# --------------------------------------------------------------------------- #
def resolve_python(project_root: Path, explicit: Path | None) -> Path:
    """Resolve the interpreter for pytest and Spark workers.

    Explicit path wins (and must exist). Otherwise prefer a project-local
    virtual environment, then fall back to the current interpreter.
    """
    if explicit is not None:
        if not explicit.exists():
            raise SystemExit(f"Python executable not found: {explicit}")
        return explicit

    if IS_WINDOWS:
        candidates = [
            project_root / ".venv" / "Scripts" / "python.exe",
            project_root / "venv" / "Scripts" / "python.exe",
        ]
    else:
        candidates = [
            project_root / ".venv" / "bin" / "python",
            project_root / "venv" / "bin" / "python",
        ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return Path(sys.executable)


def writable_log_dir(project_root: Path) -> Path:
    """Return a writable directory for log + JUnit files.

    Anchored to the project under test (not to the skill install location),
    with an env override and a temp fallback.
    """
    candidates: list[Path] = []
    env_dir = os.environ.get("PYSPARK_TEST_LOG_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(project_root / ".pyspark-test-logs")
    candidates.append(Path(tempfile.gettempdir()) / "pyspark-test-runner-logs")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".write-test-{uuid.uuid4().hex}.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue

    raise SystemExit("No writable log directory found. Set PYSPARK_TEST_LOG_DIR and retry.")


# --------------------------------------------------------------------------- #
# JUnit XML parsing
# --------------------------------------------------------------------------- #
def _module_prefix_from_file(file_attr: str) -> str:
    """Convert a JUnit `file` attribute to its dotted module prefix.

    `tests/test_x.py` -> `tests.test_x`. Used to peel the module portion off
    the dotted `classname` so we can recover the test-class chain.
    """
    no_suffix = re.sub(r"\.py$", "", file_attr)
    return no_suffix.replace("\\", "/").replace("/", ".")


def _split_classname(classname: str) -> tuple[list[str], str]:
    """Split a dotted JUnit classname into (module path parts, class chain).

    pytest's default JUnit report omits the `file` attribute and stores only
    a dotted `classname` like `tests.test_x.TestC`. By pytest convention test
    modules and packages are lowercase and test classes are TitleCase, so the
    trailing uppercase-initial segments are the class chain and the rest is
    the module path. Falls back to treating everything as the module when no
    segment looks like a class.
    """
    segments = classname.split(".")
    split_at = len(segments)
    while split_at > 0 and segments[split_at - 1][:1].isupper():
        split_at -= 1
    return segments[:split_at], ".".join(segments[split_at:])


def node_id_from_case(file_attr: str, classname: str, name: str) -> str:
    """Reconstruct a runnable pytest node id from JUnit testcase attributes.

    pytest node ids use the file path plus `::`-separated class/method
    segments (`tests/test_x.py::TestC::test_m`). Prefer the JUnit `file`
    attribute when present; otherwise rebuild the path from the dotted
    `classname` (the default report omits `file`). Falls back gracefully when
    the attributes cannot be aligned.
    """
    file_attr = (file_attr or "").strip()
    classname = (classname or "").strip()
    name = (name or "").strip()

    path = ""
    class_chain = ""

    if file_attr:
        path = file_attr
        prefix = _module_prefix_from_file(file_attr)
        if classname == prefix:
            class_chain = ""
        elif classname.startswith(prefix + "."):
            class_chain = classname[len(prefix) + 1 :]
        elif classname:
            _, class_chain = _split_classname(classname)
    elif classname:
        module_parts, class_chain = _split_classname(classname)
        if module_parts:
            path = "/".join(module_parts) + ".py"

    if not path:
        return f"{classname}::{name}" if classname else name

    parts = [path]
    if class_chain:
        parts.extend(class_chain.split("."))
    parts.append(name)
    return "::".join(parts)


def _int_attr(elem: ET.Element, key: str) -> int:
    try:
        return int(elem.attrib.get(key, "0") or "0")
    except (TypeError, ValueError):
        return 0


def parse_junit(junit_file: Path) -> dict | None:
    """Parse pytest JUnit XML into counts and a list of failures.

    Returns None when the file is absent. Returns a dict with a
    `parse_error` key (and empty counts/failures) when the XML cannot be
    parsed, so callers can fall back to the log tail instead of crashing.
    """
    if not junit_file.exists():
        return None

    empty = {
        "counts": {
            "tests": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "passed": 0,
            "time": 0.0,
        },
        "failures": [],
    }

    try:
        root = ET.parse(junit_file).getroot()
    except ET.ParseError as exc:
        return {**empty, "parse_error": str(exc)}

    # A testsuites wrapper may contain one or more testsuite elements.
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))

    tests = failures = errors = skipped = 0
    total_time = 0.0
    problems: list[dict] = []

    for suite in suites:
        tests += _int_attr(suite, "tests")
        failures += _int_attr(suite, "failures")
        errors += _int_attr(suite, "errors")
        skipped += _int_attr(suite, "skipped")
        try:
            total_time += float(suite.attrib.get("time", "0") or "0")
        except (TypeError, ValueError):
            pass

        for case in suite.iter("testcase"):
            for kind in ("failure", "error"):
                child = case.find(kind)
                if child is None:
                    continue
                node_id = node_id_from_case(
                    case.attrib.get("file", ""),
                    case.attrib.get("classname", ""),
                    case.attrib.get("name", ""),
                )
                body = (child.text or "").strip()
                message = (child.attrib.get("message", "") or "").strip()
                if not message and body:
                    message = body.splitlines()[-1].strip()
                problems.append(
                    {
                        "node_id": node_id,
                        "reason": message,
                        "body": body,
                        "kind": kind,
                    }
                )
                break  # one failure/error entry per case is enough

    passed = max(tests - failures - errors - skipped, 0)
    return {
        "counts": {
            "tests": tests,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "passed": passed,
            "time": round(total_time, 2),
        },
        "failures": problems,
    }


# --------------------------------------------------------------------------- #
# Compaction: signatures, grouping, trimming
# --------------------------------------------------------------------------- #
_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s'\"]+")
_NIX_PATH_RE = re.compile(r"(?<![\w])/[^\s'\"]+")
_NUM_RE = re.compile(r"\d+")
_WS_RE = re.compile(r"\s+")


def normalize_signature(message: str) -> str:
    """Reduce a failure message to a stable signature for grouping.

    Strips volatile tokens (hex addresses, file paths, numbers) and collapses
    whitespace so failures that share a root cause but differ in incidental
    values (row counts, line numbers, addresses) group together.
    """
    if not message:
        return "<no message>"
    text = message.strip()
    text = _HEX_RE.sub("HEXADDR", text)
    text = _WIN_PATH_RE.sub("PATH", text)
    text = _NIX_PATH_RE.sub("PATH", text)
    text = _NUM_RE.sub("N", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def group_failures(failures: list[dict]) -> list[dict]:
    """Group failures by normalized signature, most frequent first.

    Each group: {signature, count, reason (representative), node_ids,
    body (representative)}. Insertion order is preserved for equal counts so
    output is deterministic.
    """
    groups: dict[str, dict] = {}
    for fail in failures:
        sig = normalize_signature(fail.get("reason", ""))
        group = groups.get(sig)
        if group is None:
            group = {
                "signature": sig,
                "count": 0,
                "reason": fail.get("reason", "") or "<no message>",
                "node_ids": [],
                "body": fail.get("body", ""),
            }
            groups[sig] = group
        group["count"] += 1
        group["node_ids"].append(fail.get("node_id", ""))

    return sorted(groups.values(), key=lambda g: g["count"], reverse=True)


def trim_excerpt(text: str, max_lines: int) -> list[str]:
    """Trim a traceback to max_lines, keeping the head and the tail.

    The final lines of a traceback carry the actual exception, so a head-only
    truncation would hide the cause. Keeps both ends with a marker between.
    """
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return lines
    head = max(max_lines // 2, 1)
    tail = max(max_lines - head - 1, 1)
    trimmed = len(lines) - head - tail
    return lines[:head] + [f"... ({trimmed} lines trimmed, see log) ..."] + lines[-tail:]


# --------------------------------------------------------------------------- #
# Exit-code interpretation
# --------------------------------------------------------------------------- #
def result_for_exit_code(code: int) -> tuple[str, str]:
    """Map a pytest exit code to a (result, hint) pair."""
    mapping = {
        0: ("PASSED", ""),
        1: ("FAILED", ""),
        2: (
            "ERROR",
            "pytest was interrupted (often a collection or import error); "
            "fix the import and rerun the narrowest node.",
        ),
        3: ("INTERNAL ERROR", "pytest hit an internal error; see the log."),
        4: ("USAGE ERROR", "pytest usage error; check the target and flags."),
        5: ("NO TESTS", "no tests were collected; check the target path or node id."),
        6: ("WARNINGS", "pytest stopped after too many warnings; see the log."),
    }
    return mapping.get(code, (f"EXIT {code}", ""))


# --------------------------------------------------------------------------- #
# Digest assembly (pure: testable without IO)
# --------------------------------------------------------------------------- #
def build_digest(
    *,
    result: str,
    hint: str,
    exit_code: int | None,
    junit: dict | None,
    project_root: str,
    target: str,
    command: str,
    log_path: str,
    junit_path: str,
    log_tail: list[str] | None,
    excerpt_lines: int,
    max_failures_listed: int,
) -> str:
    """Build the bounded digest string from parsed data.

    Pure function: no file IO, no process state. `log_tail` is used as a
    fallback when JUnit data is missing or unusable.
    """
    out: list[str] = []
    out.append("=== PYSPARK TEST SUMMARY ===")
    out.append(f"Result: {result}")
    if exit_code is not None:
        out.append(f"ExitCode: {exit_code}")

    if junit and "parse_error" not in junit:
        c = junit["counts"]
        out.append(
            f"Collected: {c['tests']}  Passed: {c['passed']}  "
            f"Failed: {c['failures']}  Errors: {c['errors']}  Skipped: {c['skipped']}"
        )
        out.append(f"TimeSec: {c['time']}")

    out.append(f"ProjectRoot: {project_root}")
    out.append(f"Target: {target}")
    out.append(f"Command: {command}")
    out.append(f"Log: {log_path}")
    out.append(f"JUnit: {junit_path}")
    if hint:
        out.append(f"Hint: {hint}")

    failures = junit["failures"] if (junit and "parse_error" not in junit) else []

    if failures:
        # Section A: bounded list of runnable failing node ids + one-line reason.
        shown_count = min(len(failures), max_failures_listed)
        out.append(f"--- FAILING TESTS (showing {shown_count} of {len(failures)}) ---")
        for fail in failures[:max_failures_listed]:
            reason = (fail.get("reason") or "").splitlines()[0] if fail.get("reason") else ""
            line = fail["node_id"]
            if reason:
                line += f"  -  {reason}"
            out.append(line)
        if len(failures) > max_failures_listed:
            out.append(f"... and {len(failures) - max_failures_listed} more (see log)")

        # Section B: deduplicated signatures with one representative excerpt each.
        groups = group_failures(failures)
        shown = groups[:MAX_SIGNATURES]
        for index, group in enumerate(shown, start=1):
            out.append(
                f"--- SIGNATURE {index} of {len(groups)}  ({group['count']} test"
                f"{'s' if group['count'] != 1 else ''}) ---"
            )
            reason = (group["reason"] or "").splitlines()[0]
            out.append(reason)
            out.append(f"Example: {group['node_ids'][0]}")
            if group["body"]:
                out.extend(trim_excerpt(group["body"], excerpt_lines))
        if len(groups) > MAX_SIGNATURES:
            out.append(f"... and {len(groups) - MAX_SIGNATURES} more signatures (see log)")

    elif junit is None or "parse_error" in junit or junit["counts"]["tests"] == 0:
        # No usable structured failure data: fall back to a bounded log tail.
        if junit and "parse_error" in junit:
            out.append(f"(JUnit XML unparseable: {junit['parse_error']})")
        if log_tail:
            out.append(f"--- LOG TAIL (no JUnit failure data, last {len(log_tail)} lines) ---")
            out.extend(log_tail)

    # Hard backstop: clip the whole digest so no pathological input blows the budget.
    if len(out) > MAX_OUTPUT_LINES:
        out = out[: MAX_OUTPUT_LINES - 1]
        out.append("... (digest truncated; full output in log)")

    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Process control + IO
# --------------------------------------------------------------------------- #
def kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill the pytest process and its children (Spark/JVM workers)."""
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def tail_lines(path: Path, count: int) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:]
    except OSError:
        return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="+",
        help="pytest node id(s) or file path(s), relative to --project-root",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Directory to run pytest in (default: current working directory)",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=None,
        help="Python executable for pytest and PySpark workers "
        "(default: project .venv/venv, else current interpreter)",
    )
    parser.add_argument(
        "--timeout-sec", type=int, default=900, help="Kill hung runs after N seconds"
    )
    parser.add_argument("--stop-on-first-fail", "-x", action="store_true")
    parser.add_argument(
        "--verbose-pytest",
        "-v",
        action="store_true",
        help="Run pytest verbosely (escape hatch; digest still printed)",
    )

    parser.add_argument(
        "--excerpt-lines",
        type=int,
        default=DEFAULT_EXCERPT_LINES,
        help=(
            f"Max traceback lines per signature, head+tail trimmed "
            f"(default {DEFAULT_EXCERPT_LINES})"
        ),
    )
    parser.add_argument(
        "--max-failures-listed",
        type=int,
        default=DEFAULT_MAX_FAILURES_LISTED,
        help=(
            f"Max failing node ids listed before collapsing (default {DEFAULT_MAX_FAILURES_LISTED})"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    project_root = (args.project_root or Path.cwd()).resolve()
    if not project_root.is_dir():
        raise SystemExit(f"Project root not found: {project_root}")

    python = resolve_python(project_root, args.python)
    logs_dir = writable_log_dir(project_root)
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    log_file = logs_dir / f"pytest-{stamp}.log"
    junit_file = logs_dir / f"pytest-{stamp}.xml"

    env = os.environ.copy()
    env["PYSPARK_PYTHON"] = str(python)
    env["PYSPARK_DRIVER_PYTHON"] = str(python)
    env["PYTHONUNBUFFERED"] = "1"

    pytest_args = ["-m", "pytest"]
    if args.verbose_pytest:
        pytest_args.append("-v")
    else:
        pytest_args.extend(["-q", "--tb=short", "--color=no", "--disable-warnings"])
    pytest_args.append("-p")
    pytest_args.append("no:cacheprovider")
    if args.stop_on_first_fail:
        pytest_args.append("-x")
    pytest_args.append(f"--junitxml={junit_file}")
    pytest_args.extend(args.target)

    command = [str(python), *pytest_args]
    proc = subprocess.Popen(
        command,
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=not IS_WINDOWS,
    )

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=REAP_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            # Could not reap the child tree; do not block on it.
            stdout, stderr = "", "(process did not exit after kill; see log)"

    log_file.write_text("\n".join([stdout or "", stderr or ""]), encoding="utf-8")

    command_str = f"{python} {' '.join(pytest_args)}"

    if timed_out:
        digest = build_digest(
            result="TIMEOUT",
            hint=(
                f"run exceeded {args.timeout_sec}s and was killed; "
                "narrow the target or raise --timeout-sec."
            ),
            exit_code=None,
            junit=None,
            project_root=str(project_root),
            target=" ".join(args.target),
            command=command_str,
            log_path=str(log_file),
            junit_path=str(junit_file),
            log_tail=tail_lines(log_file, LOG_TAIL_LINES),
            excerpt_lines=args.excerpt_lines,
            max_failures_listed=args.max_failures_listed,
        )
        print(digest)
        return 124

    exit_code = proc.returncode or 0
    result, hint = result_for_exit_code(exit_code)
    junit = parse_junit(junit_file)

    digest = build_digest(
        result=result,
        hint=hint,
        exit_code=exit_code,
        junit=junit,
        project_root=str(project_root),
        target=" ".join(args.target),
        command=command_str,
        log_path=str(log_file),
        junit_path=str(junit_file),
        log_tail=tail_lines(log_file, LOG_TAIL_LINES),
        excerpt_lines=args.excerpt_lines,
        max_failures_listed=args.max_failures_listed,
    )
    print(digest)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
