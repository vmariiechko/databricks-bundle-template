# Verifying the adapted quarantine pattern

Load this when you are ready to prove the adapted pattern works. Verification is a ladder of three tiers. Lead with Tier 1: it is deterministic, repeatable, and needs no Databricks workspace, so it proves the core correctness before anyone deploys anything. Tiers 2 and 3 confirm behavior on the live pipeline.

Throughout, substitute the user's real identifiers for the placeholders:

- `<raw>` = the raw/bronze table, for example `main.bronze.raw_orders`
- `<clean>` = the clean/silver table (valid rows)
- `<quarantine>` = the quarantine table
- `<event_log>` = the published event log table (the resource's `event_log` block)

## Tier 1: offline rule unit tests (primary, always do this)

This is the highest-value check and it runs locally with a real Spark session, no workspace. It proves the one property the whole pattern depends on: every raw row lands in exactly one of clean or quarantine, and a NULL in a guarded column routes to quarantine, not clean.

The asset ships a worked example at `<target_dir>/tests/` (`conftest.py`, `test_expectations.py`, `requirements-test.txt`). Adapt it to the user's dataset:

1. Read `<target_dir>/tests/test_expectations.py`. It has two parts: pure-Python config checks (rules load, every drop predicate is NULL-safe, the quarantine predicate is the inverse of the clean predicate) and a real-Spark routing test.
2. Replace the example schema (`_SCHEMA`) and edge rows (`_EDGE_ROWS`) with the user's columns. Craft one row per case: a fully valid row, one row per single drop violation, a multi-violation row, a warn-only row (passes all drop rules), and critically a row with `NULL` in each column that a drop rule guards. Label each row's `expected` bucket (`clean` or `quarantine`).
3. Keep the routing model as-is: the test reproduces `expect_all_or_drop`'s keep-on-NULL semantics with `(<predicate>) IS NOT FALSE`, so a non-NULL-safe rule shows up as a broken partition. Do not weaken it to a plain filter.
4. Run it:

   ```bash
   pip install -r <target_dir>/tests/requirements-test.txt
   pytest <target_dir>/tests/ -q
   ```

PASS when every test is green. If `test_partition_invariant` or a NULL-routing test fails, a drop predicate is not NULL-safe: fix it in `expectations.json` (add the `IS NOT NULL` guard) and rerun. You have now proven the rules partition correctly without touching a workspace.

This tier needs Java (for PySpark) and Python 3.10+. If the runtime cannot run Spark locally, say so and rely on Tier 2 and Tier 3 for the partition proof instead; do not skip verification silently.

## Tier 2: read-only audits on the deployed pipeline (reality check)

After the pipeline runs on the workspace, confirm the same invariants on real data with read-only SQL (use whatever read-only query capability your runtime has). These need no fault injection.

### A. Partition invariant

```sql
SELECT
  (SELECT COUNT(*) FROM <raw>)        AS raw_rows,
  (SELECT COUNT(*) FROM <clean>)      AS clean_rows,
  (SELECT COUNT(*) FROM <quarantine>) AS quarantine_rows,
  (SELECT COUNT(*) FROM <raw>)
    - (SELECT COUNT(*) FROM <clean>)
    - (SELECT COUNT(*) FROM <quarantine>) AS gap;
```

PASS when `gap = 0`.

### B. NULL-in-clean audit

For every column that appears in a drop rule, no clean row may have it NULL:

```sql
SELECT '<col>' AS dropped_column, COUNT(*) AS nulls_in_clean
FROM <clean>
WHERE <col> IS NULL;
```

PASS when `nulls_in_clean = 0` for every dropped column.

### C. Expectation results in the event log

The per-expectation passed/failed counts (and the warn rules, which never route to quarantine) surface in the event log. The reference ships `<target_dir>/event_log_queries.sql`; point it at `<event_log>` to confirm each rule fired as expected.

## Tier 3: integration test via source parameterization (optional E2E)

When the user wants a full end-to-end test on the workspace with known inputs, do not mutate the live source or splice in a faults table. Use the source parameterization the pipeline already supports. The raw layer reads its source from the `quarantine.source` configuration, so a test run can point it at a curated table.

This follows the Databricks guidance to create test datasets that include records which break expectations, and it keeps the run clean and repeatable (no streaming-checkpoint surgery):

1. Create a small curated test table with the same columns the raw layer selects. Populate it with known-good rows and known-bad rows, one per scenario (single violation, multi-violation, warn-only, and a NULL in a guarded column), each with a value you can recognize afterward.
2. Point the pipeline at it: set `quarantine.source` to the test table in a test target (or a copy of the resource), so the live (main-target) config is untouched.
3. Deploy to the test target and run the pipeline.
4. Run the Tier 2 audits, plus assert the exact routing: each known-bad row is in `<quarantine>` and not in `<clean>`, each known-good row is in `<clean>`, the multi-violation row appears in quarantine exactly once, and the NULL row is in quarantine only.
5. Tear down the test target when done.

PASS when the partition holds and every known row lands where you expect.

A full, reusable integration-test harness for SDP pipelines (fixtures, CI wiring, golden outputs) is beyond this skill's scope. If the user wants that, treat it as its own effort.

## Interpreting results honestly

Tier 1 proves the rules partition correctly on the crafted edge cases, deterministically and offline. Tier 2 confirms it on whatever real data flowed. Tier 3 confirms it end-to-end on curated inputs. None of these prove the rules capture every real defect in the user's domain, nor that they hold for data shapes you have not tested. Report what you verified and what you did not. The user owns whether the rules are the right rules.
