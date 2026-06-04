# sdp-quarantine-pattern

A Lakeflow Spark Declarative Pipeline that demonstrates the inverse-expectations quarantine pattern on the public `samples.nyctaxi.trips` dataset. Critical (drop) expectations route violating rows into a `quarantine_trips` table; valid rows flow to `silver_trips`; advisory (warn) expectations log to the pipeline event log without dropping.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/sdp-quarantine-pattern
```

You will be prompted for `target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `bronze_schema`, and `silver_schema` (all with safe defaults). The asset installs the pipeline notebook, a declarative `expectations.json`, a pure helper module, event-log parsing queries, and the DABs pipeline resource.

## Architecture

```
samples.nyctaxi.trips
        │
        ▼
  bronze_trips            (bronze schema)
        │
        ├─► silver_trips       (silver schema)   @expect_all(warn) + @expect_all_or_drop(drop)
        └─► quarantine_trips   (silver schema)   @expect_all_or_drop(NOT(drop))
```

- `bronze_trips` ingests the read-only public sample as a streaming table and lands in the bronze schema (the pipeline default).
- `silver_trips` and `quarantine_trips` both read `bronze_trips` and land in the silver schema, following medallion schema separation. Silver applies the drop rules; quarantine applies their inverse. They read the same source once each, which is the tradeoff of this pattern: the data is processed twice.

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

`expect_all_or_drop` drops a row only when its predicate evaluates to `false`. A predicate that evaluates to SQL `NULL` (unknown) is treated as passing. So if you write a drop rule as `fare_amount > 0` and a row has a NULL fare, the predicate is `NULL`, the row is kept in silver, and the inverse `NOT(fare_amount > 0)` is also `NULL`, so the quarantine table's behavior on that row is inconsistent. The row can leak into both tables or neither.

The fix is to make every drop predicate total (NULL-safe): guard each column test with `IS NOT NULL`, as in `fare_amount IS NOT NULL AND fare_amount > 0`. A total predicate never returns `NULL`, so `expect_all_or_drop(drop_rules)` and `expect_all_or_drop(NOT(drop_rules))` partition the bronze input exactly once: every row lands in exactly one of silver or quarantine. This asset writes all drop predicates this way.

If you cannot guarantee total predicates (for example, rules loaded from an external system), the robust alternative is to compute an explicit `_quarantined` boolean with NULL-safe SQL once, then branch silver and quarantine on that flag instead of on raw inverse predicates.

## Comparison: the status-column variant

An alternative implementation keeps a single table and adds a validation-status column that marks each row good or bad, partitioning on that column instead of using a separate table. Tradeoff: it avoids reading the source twice, but the per-expectation data-quality metrics do not surface in the pipeline event log the way they do with expectations. This asset builds the separate-quarantine-table approach; the status-column variant is noted here for context.

## Inspecting expectation results

The pipeline publishes its event log to a queryable UC table (`<catalog>.<bronze_schema>.pipeline_event_log`). `event_log_queries.sql` parses it into per-expectation passed/failed counts for the latest run, plus a focused query for the warn expectations, which never route to quarantine and so only surface in the event log.

## Tests

Offline tests (`tests/assets/test_sdp_quarantine_pattern.py`) verify the asset installs the expected files, the pipeline source parses, `expectations.py` builds the correct inverse predicate, every drop predicate is NULL-safe, and the resource YAML is valid (schema split, event log, tags, library path). Expectation-firing and routing are runtime properties, verified live (see below), not offline.

## Validation results

The pattern was validated live on serverless SDP against `samples.nyctaxi.trips`.

- **Partition invariant holds exactly.** Baseline run: 21,932 bronze rows split into 21,847 silver and 85 quarantine (21,847 + 85 = 21,932). The split stayed exact across every test.
- **Quarantine works on real data out of the box.** The 85 baseline quarantine rows are naturally invalid rows in the public sample (74 zero-distance, 9 zero or negative fare, 2 with multiple violations). No injection needed to see the pattern work.
- **The NULL trap is real and the fix works.** A row with a NULL `fare_amount` routed to quarantine only and did not leak into silver, because `valid_fare` is NULL-safe. A naive `fare_amount > 0` would have treated the NULL as passing and leaked the row.
- **Multiple violations on one row produce exactly one quarantine row.** No duplication; the event log still attributes each failed expectation separately.
- **Warn rules behave as advisory.** A row that only violated `fare_within_expected` flowed to silver and was recorded in the event log; quarantine was unaffected.

Two lived findings worth carrying into your own pipelines:

- `spark.catalog.tableExists()` is not whitelisted inside SDP (it raises `Py4JSecurityException`). Avoid it in pipeline code; this asset does not use it.
- A streaming table's set of input sources is fixed at its first run. Changing it later (for example, adding a union source) is incompatible with the existing checkpoint and requires a full refresh.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

It is a demonstration of one specific pattern with its tradeoffs documented, not a general-purpose data-quality framework. For a fuller framework, look at [DQX](https://databrickslabs.github.io/dqx/) (Databricks Labs).
