---
name: pyspark-test-runner
description: Use this skill whenever you run or debug local PySpark pytest suites from the agent shell. Invoke `scripts/run-pyspark-tests.py` instead of calling `pytest` raw, so the full output goes to a log file and only a bounded digest reaches your context. The digest carries the exit code, counts, runnable failing node ids, and failures deduplicated by signature, so a suite where many tests fail with the same error collapses to one short block instead of flooding the window. Run the narrowest node first, stop on the first failure by default, and widen only when needed.
---

# PySpark Test Runner

Run local PySpark-backed pytest through this wrapper. It runs pytest for you, writes the complete stdout and stderr to a log file, and prints a compact digest built from the JUnit XML. The point is to keep your context bounded: raw pytest output from a PySpark suite can be thousands of lines, and when many tests fail with the same error it floods the window before you can act. The digest stays small regardless of how many tests fail.

## How to invoke

```bash
python <skill-dir>/scripts/run-pyspark-tests.py "<pytest-node-id-or-path>" -x
```

Run it from your project root (the pytest working directory), or pass `--project-root`. The wrapper adds no dependencies of its own (Python 3.9+, standard library), but it runs your suite, so pytest and PySpark must be installed in the project interpreter.

## Default test strategy

Start with the narrowest pytest node that covers the changed behavior, and use `-x` (stop on first failure) by default:

```bash
python <skill-dir>/scripts/run-pyspark-tests.py \
  "tests/test_cleaning_utils.py::TestCleanStr::test_clean_str_logic" -x
```

Widen only after the narrow run passes or clearly needs broader context:

1. single test case
2. test class
3. test file
4. full suite (only when explicitly needed)

The failing node ids in the digest are real pytest node ids, so you can copy one straight back as your next narrow target.

## What the wrapper does

- resolves a Python interpreter: project `.venv` / `venv`, else the current interpreter (`--python` to override)
- sets `PYSPARK_PYTHON` / `PYSPARK_DRIVER_PYTHON` to that interpreter so Spark workers match
- runs `python -m pytest` from the project root with a JUnit XML report
- writes full stdout + stderr to a log file under `<project-root>/.pyspark-test-logs/` (override with `PYSPARK_TEST_LOG_DIR`)
- prints the bounded digest and exits with pytest's exit code

## The digest

```
=== PYSPARK TEST SUMMARY ===
Result: FAILED
ExitCode: 1
Collected: 30  Passed: 7  Failed: 23  Errors: 0  Skipped: 0
TimeSec: 41.2
ProjectRoot: /path/to/project
Target: tests/
Command: <python> -m pytest -q --tb=short ...
Log: /path/to/project/.pyspark-test-logs/pytest-<stamp>.log
JUnit: /path/to/project/.pyspark-test-logs/pytest-<stamp>.xml
--- FAILING TESTS (showing 20 of 23) ---
tests/test_x.py::TestA::test_one  -  AssertionError: ...
... and 3 more (see log)
--- SIGNATURE 1 of 1  (23 tests) ---
AssertionError: ...
Example: tests/test_x.py::TestA::test_one
<traceback excerpt, head+tail trimmed to --excerpt-lines>
```

Failures are grouped by a normalized signature. 23 tests failing with one root cause show as a single `SIGNATURE 1 of 1 (23 tests)` block, not 23 tracebacks. Open the log file only when you need the full detail.

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--project-root PATH` | current dir | pytest working directory |
| `--python PATH` | venv or current | interpreter for pytest and Spark workers |
| `--timeout-sec N` | 900 | kill a hung run after N seconds |
| `-x`, `--stop-on-first-fail` | off | stop at the first failure (use by default) |
| `-v`, `--verbose-pytest` | off | verbose pytest output (escape hatch) |
| `--excerpt-lines N` | 40 | traceback lines per signature, head+tail trimmed |
| `--max-failures-listed N` | 20 | failing node ids listed before collapsing |

## Reading the result

- `PASSED` (exit 0): done.
- `FAILED` (exit 1): read the signatures; fix the root cause; rerun the narrowest failing node.
- `ERROR` (exit 2): usually a collection or import error, so no tests ran. Fix the import named in the digest, then rerun.
- `NO TESTS` (exit 5): the target matched nothing. Check the path or node id.
- `TIMEOUT`: the run exceeded `--timeout-sec` and was killed. Narrow the target or raise the timeout.

You own the fix. The wrapper reports; it does not change your code.

## When Spark fails to start locally

If pytest dies with loopback, socket, or child event-loop errors, your agent sandbox is likely blocking Spark's local networking. Rerun the same wrapper command with your runtime's elevated or outside-sandbox execution. Do not switch to mocking Spark transforms to make tests pass, and do not bypass the wrapper unless you are debugging the wrapper itself.

## Scope

Local pytest only. This skill does not deploy or run Databricks bundles, and it is not a CI runner or a pytest plugin. It is a thin wrapper that keeps test output readable for an agent.
