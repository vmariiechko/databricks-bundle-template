# sdp-quarantine-pattern

A Lakeflow Spark Declarative Pipeline that demonstrates the inverse-expectations quarantine pattern on the public `samples.nyctaxi.trips` dataset. Critical (drop) expectations route violating rows into a `quarantine_trips` table; valid rows flow to `clean_trips`; advisory (warn) expectations log to the pipeline event log without dropping.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/sdp-quarantine-pattern
```

You will be prompted for `target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `bronze_schema`, `silver_schema`, and `skill_dir` (all with safe defaults). The asset installs the pipeline notebook, a declarative `expectations.json`, a pure helper module, an offline unit-test suite, event-log parsing queries, the DABs pipeline resource, and a companion agent skill.

## Two doors

This is a dual-door asset:

- **Door 1, the reference pipeline.** Copy it, point it at your catalog/schemas, deploy, and watch the quarantine pattern work on `samples.nyctaxi.trips`. This README documents it.
- **Door 2, the companion agent skill** at `<skill_dir>/skills/sdp-quarantine-pattern/SKILL.md`. Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at it and it adapts the pattern to your own dataset: it investigates your data, proposes drop/warn rules for you to confirm, keeps every drop predicate NULL-safe, adapts and runs the offline unit tests, wires the resource into your bundle, and verifies the result (offline unit tests first, then live read-only audits). It applies and verifies a pattern; it is not an auto-rewriter and does not guarantee correctness on arbitrary data. The in-bundle `docs/sdp-quarantine-pattern/README.md` has a ready-to-paste kickoff prompt.

## Architecture

```
samples.nyctaxi.trips
        │
        ▼
  raw_trips               (bronze schema)
        │
        ├─► clean_trips        (silver schema)   @expect_all(warn) + @expect_all_or_drop(drop)
        └─► quarantine_trips   (silver schema)   @expect_all_or_drop(NOT(drop))
```

The schemas are the medallion layers; the table names describe content. `raw_trips` ingests the read-only public sample as a streaming table and lands in the bronze schema (the pipeline default). `clean_trips` and `quarantine_trips` both read `raw_trips` and land in the silver schema, following medallion schema separation. The clean table applies the drop rules; quarantine applies their inverse. They read the same source once each, which is the tradeoff of this pattern: the data is processed twice.

The public sample already contains some invalid rows, so the quarantine table is populated on the first run with no extra setup.

## Expectations

Rules live in `expectations.json`, split into two lists. Drop rules are critical and route failures to quarantine; warn rules are advisory and only annotate the event log.

| Action | Name | Predicate |
|---|---|---|
| drop | `valid_fare` | `fare_amount IS NOT NULL AND fare_amount > 0` |
| drop | `valid_distance` | `trip_distance IS NOT NULL AND trip_distance > 0` |
| drop | `valid_pickup_ts` | `tpep_pickup_datetime IS NOT NULL` |
| drop | `valid_dropoff_after_pickup` | `tpep_dropoff_datetime IS NOT NULL AND tpep_dropoff_datetime > tpep_pickup_datetime` |
| drop | `valid_pickup_zip` | `pickup_zip IS NOT NULL` |
| warn | `fare_within_expected` | `fare_amount < 500` |
| warn | `distance_within_expected` | `trip_distance < 100` |
| warn | `dropoff_zip_present` | `dropoff_zip IS NOT NULL` |

The quarantine predicate is derived automatically as `NOT((p1) AND (p2) AND ...)` over the drop predicates. You do not maintain it by hand.

## The NULL trap

This is the point worth internalizing before you copy the pattern.

`expect_all_or_drop` drops a row only when its predicate evaluates to `false`; a predicate that evaluates to SQL `NULL` (unknown) is not `false`, so the row is kept (see the [`is false` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/isfalse): `NULL is false` is `false`). So if you write a drop rule as `fare_amount > 0` and a row has a NULL fare, the predicate is `NULL` and the row is kept in the clean table. The inverse `NOT(fare_amount > 0)` is also `NULL`, which is likewise not `false`, so the same row is kept in the quarantine table too. The one row lands in both tables, double-counted, and the clean/quarantine split is no longer a clean partition.

The fix is to make every drop predicate total (NULL-safe): guard each column test with `IS NOT NULL`, as in `fare_amount IS NOT NULL AND fare_amount > 0`. A total predicate never returns `NULL`, so `expect_all_or_drop(drop_rules)` and `expect_all_or_drop(NOT(drop_rules))` partition the raw input exactly once: every row lands in exactly one of the clean or quarantine table. This asset writes all drop predicates this way.

If you cannot guarantee total predicates (for example, rules loaded from an external system), the robust alternative is to compute an explicit `_quarantined` boolean with NULL-safe SQL once, then branch the clean and quarantine tables on that flag instead of on raw inverse predicates.

## Comparison: the status-column variant

An alternative implementation keeps a single table and adds a validation-status column that marks each row good or bad, partitioning on that column instead of using a separate table. Tradeoff: it avoids reading the source twice, but the per-expectation data-quality metrics do not surface in the pipeline event log the way they do with expectations. This asset builds the separate-quarantine-table approach; the status-column variant is noted here for context.

## Inspecting expectation results

The pipeline publishes its event log to a queryable UC table (`<catalog>.<bronze_schema>.quarantine_pipeline_event_log`). `event_log_queries.sql` parses it into per-expectation passed/failed counts for the latest run, plus a focused query for the warn expectations, which never route to quarantine and so only surface in the event log.

## Tests

The asset ships its own unit tests at `<target_dir>/tests/`: a real local-Spark `pytest` suite that proves the partition invariant (clean + quarantine == raw) and NULL routing on crafted edge rows, with no Databricks workspace. It models `expect_all_or_drop`'s keep-on-NULL semantics with `IS NOT FALSE`, so a drop predicate that is not NULL-safe fails the partition assertion. Run it with `pip install -r <target_dir>/tests/requirements-test.txt && pytest <target_dir>/tests/ -q` (needs Java for PySpark). The companion skill adapts these tests to your dataset as the first verification tier.

Repo-level tests (`tests/assets/test_sdp_quarantine_pattern.py`) verify the asset installs the expected files, the pipeline source parses, `expectations.py` builds the correct clean and inverse predicates, every drop predicate is NULL-safe, the resource YAML is valid (schema split, source parameterization, event log, tags, library path), and the skill and unit-test scaffold install. End-to-end expectation firing on the workspace is verified live (see below).

## Validation results

The pattern was validated live on serverless SDP against `samples.nyctaxi.trips`.

- **Partition invariant holds exactly.** Baseline run: 21,932 raw rows split into 21,847 clean and 85 quarantine (21,847 + 85 = 21,932). The split stayed exact across every test.
- **Quarantine works on real data out of the box.** The 85 baseline quarantine rows are naturally invalid rows in the public sample (74 zero-distance, 9 zero or negative fare, 2 with multiple violations). No injection needed to see the pattern work.
- **The NULL trap is real and the fix works.** A row with a NULL `fare_amount` routed to quarantine only and did not leak into the clean table, because `valid_fare` is NULL-safe. A naive `fare_amount > 0` would have treated the NULL as passing and leaked the row.
- **Multiple violations on one row produce exactly one quarantine row.** No duplication; the event log still attributes each failed expectation separately.
- **Warn rules behave as advisory.** A row that only violated `fare_within_expected` flowed to the clean table and was recorded in the event log; quarantine was unaffected.

Two lived findings worth carrying into your own pipelines:

- `spark.catalog.tableExists()` is not whitelisted inside SDP (it raises `Py4JSecurityException`). Avoid it in pipeline code; this asset does not use it.
- A streaming table's set of input sources is fixed at its first run. Changing it later (for example, adding a union source) is incompatible with the existing checkpoint and requires a full refresh.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

It is a demonstration of one specific pattern with its tradeoffs documented, not a general-purpose data-quality framework. For a fuller framework, look at [DQX](https://databrickslabs.github.io/dqx/) (Databricks Labs).
