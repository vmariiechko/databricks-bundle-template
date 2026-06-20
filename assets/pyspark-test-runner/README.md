# pyspark-test-runner

A single-file Python wrapper around `pytest` for local PySpark suites that gives an LLM agent a bounded, readable view of a test run. The wrapper runs pytest, writes the full output to a log file, and prints only a compact digest built from the JUnit XML: exit code, counts, runnable failing node ids, and failures deduplicated by signature. When many tests fail with the same error, the digest collapses them into one block instead of flooding the agent's context window.

Packaged as an [agentskills.io](https://agentskills.io)-style skill: `SKILL.md` is the agent contract, `scripts/run-pyspark-tests.py` is the bundled runner. The two ship together and copy together. The wrapper adds no dependencies of its own (Python 3.9+, standard library), but it runs your suite, so pytest and PySpark must be installed in the project interpreter.

## Why

A PySpark pytest suite is verbose: Spark and JVM logging, long Py4J stack traces, and one traceback per failing test. When an agent runs the suite and a shared mistake makes many tests fail with the same error, the raw output can run to thousands of lines and burn the agent's context before it can fix anything. This wrapper turns that flood into a digest the agent can read in one glance, and keeps the full detail in a log file for when it is actually needed.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/pyspark-test-runner
```

You will be prompted for `target_dir` (default `.agents`). Two files are installed:

- `<target_dir>/skills/pyspark-test-runner/SKILL.md`: the agent-facing skill contract
- `<target_dir>/skills/pyspark-test-runner/scripts/run-pyspark-tests.py`: the bundled wrapper script

## Picking a `target_dir`

The default `.agents` is vendor-neutral and matches the convention used by Codex, the Databricks AI Dev Kit, and any multi-agent project. If you only use one agent CLI and want auto-discovery:

| Agent | Override `target_dir` to | Notes |
|---|---|---|
| Claude Code | `.claude` | Auto-discovered via `.claude/skills/`. No further wiring needed. |
| Codex | `.codex` (or keep `.agents`) | Reference the SKILL.md from `AGENTS.md`. |
| Cursor | `.cursor` | Add a rule under `.cursor/rules/` referencing the SKILL.md. |
| Gemini CLI | `.gemini` | Reference from `.gemini/` configuration. |
| Multi-agent / unsure | `.agents` (default) | Wire each agent manually via its config file. |

The post-install message prints the exact one-liner per agent.

## Usage

Run from your project root (the pytest working directory), or pass `--project-root`:

```bash
python <target_dir>/skills/pyspark-test-runner/scripts/run-pyspark-tests.py \
  "tests/test_cleaning_utils.py::TestCleanStr::test_clean_str_logic" -x
```

Start with the narrowest node that covers the change and `-x` (stop on first failure). Widen only after the narrow run passes or clearly needs more context. The failing node ids in the digest are real pytest node ids, so you can copy one back as the next target. See `<target_dir>/skills/pyspark-test-runner/SKILL.md` for the full flag reference and workflow.

The wrapper writes logs to `<project-root>/.pyspark-test-logs/` by default (override with `PYSPARK_TEST_LOG_DIR`). Add that folder to `.gitignore`.

## How the digest stays bounded

- **Driven by JUnit XML, not stdout scraping.** Counts, node ids, and failure messages come from the structured report pytest writes, so heavy interleaved Spark/JVM stderr does not corrupt the digest.
- **Failing-tests list is capped** (`--max-failures-listed`, default 20), with a `... and K more` line beyond the cap.
- **Failures are deduplicated by a normalized signature.** Volatile tokens (numbers, hex addresses, file paths) are stripped, so failures that share a root cause group together. The digest shows the top signatures, each with a count and one representative excerpt.
- **Each excerpt is head+tail trimmed** (`--excerpt-lines`, default 40), so a single enormous Py4J stack keeps both its call site and its final exception line.
- **A hard total-output cap** clips the whole digest as a last resort. Full detail always lives in the log file.

## Example compact output

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
tests/test_flight_transforms.py::TestApplySoftDelete::test_soft_delete_columns  -  AssertionError: ...
... and 3 more (see log)
--- SIGNATURE 1 of 1  (23 tests) ---
AssertionError: ...
Example: tests/test_flight_transforms.py::TestApplySoftDelete::test_soft_delete_columns
<traceback excerpt, head+tail trimmed>
```

23 failures with one root cause render as one signature block, about 70 lines total, whether the count is 23 or 2300.

## Caveats and limits

- **Local pytest only.** No Databricks deploy, run, or workspace auth. Not a CI runner, not a pytest plugin.
- **Dedup depends on JUnit XML.** If a suite disables the JUnit report or pytest crashes before writing it, the wrapper falls back to a bounded tail of the log file (it never crashes on missing or malformed XML), but signature grouping is unavailable in that case.
- **Signature normalization strips numbers.** Two assertions that differ only by an expected value group together. That is intended for collapsing a flood, but it means the digest points you to the shared cause, not to every distinct value. The log has the full per-test detail.
- **Not covered (by design):** parallel runs (`pytest-xdist`) are not aggregated, rerun/flaky-plugin outcomes are not interpreted, and coverage reports are out of scope.
- **Spark must be able to start locally.** If the agent sandbox blocks Spark's loopback networking, rerun the same command outside the sandbox. Do not mock Spark to make tests pass.

## Validation

Validated locally against a real PySpark suite (30 tests, PySpark 4.1.2, OpenJDK 17, Windows), not a mock.

- **All-pass:** clean header digest, correct counts and timing, exit 0.
- **Repetitive-failure flood:** a shared broken `spark` fixture made 19 tests error with one identical Py4J cause. The same run through raw pytest produced **797 lines**; the wrapper digest was about **70 lines**, collapsing all 19 into one `SIGNATURE 1 of 1 (19 tests)` block. The bound holds regardless of how many tests share the cause.
- **Collection/import error (exit 2):** surfaced compactly with the `ModuleNotFoundError` and an actionable hint.
- **No tests collected:** a typo'd node id (exit 4) and an empty test file (exit 5) both map to a readable result.
- **Timeout:** a run past `--timeout-sec` is killed and reported as `TIMEOUT` (exit 124) with no hang and no orphaned JVM workers on Windows.
- **Long Py4J traceback:** head+tail trimmed to `--excerpt-lines`, keeping the call site and the final exception line.

One finding worth stating plainly: the runnable-node-id feature was initially wrong. pytest's default JUnit report omits the `file` attribute, so node ids must be rebuilt from the dotted `classname`. A real run caught it where reading the code did not; the wrapper now reconstructs ids from the classname using pytest's lowercase-module / TitleCase-class convention.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle, or any Python project that runs PySpark tests with pytest. See [ASSETS.md](../../ASSETS.md) for the full catalog.
