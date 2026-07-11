# sdp-expectation-notifications

Per-expectation data-quality notification for Lakeflow Spark Declarative Pipelines (SDP), as a pair: a native **event hook** fires the moment a WARN expectation result is logged (the fast path), and exactly one DABs-managed **Alert v2** sweeps the published pipeline event log on a schedule (the guaranteed path). The pair exists because the platform explicitly does not guarantee hook delivery; each half covers the other's gap.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/sdp-expectation-notifications
```

You will be prompted for `target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `schema`, `warehouse_id`, `notification_email`, and `skill_dir` (all with safe defaults; the warehouse id and email default to placeholders you replace before deploying). The asset installs the pipeline source (with the event hook inside), event-log parsing queries, the DABs pipeline resource, the backstop alert resource, an in-bundle usage doc, and a companion agent skill.

## Two doors

This is a dual-door asset:

- **Door 1, the reference pipeline.** A self-contained demo on the public `samples.nyctaxi.trips` dataset: one streaming table with a deliberately tight WARN expectation, the notifier hook, and the backstop alert. Deploy it, run it, and watch both notification paths fire on the first update. This README documents it.
- **Door 2, the companion agent skill** at `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md`. Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at it and it wires the hook-plus-backstop pattern into your own SDP pipeline: it reads your pipeline source and expectations, adds the hook and the event-log publication, adapts the backstop alert to your event log and recipients, and verifies the result with read-only queries. It proposes and confirms; it is not an auto-rewriter.

## Architecture

```
samples.nyctaxi.trips
        │
        ▼
  monitored_trips  @dp.expect (WARN, fails by design on the healthy sample)
        │
        ├─► event hook (in-pipeline)      fires at the moment the flow_progress
        │     print + optional webhook    event is logged; best-effort
        │
        └─► published event log (UC table: dq_notifications_event_log)
              ▲
              └── backstop Alert v2       scheduled sweep over a trailing
                    email subscription    1-day window; guaranteed evaluation
```

The demo WARN rule `trip_distance < 5` is a tripwire chosen to fail on a healthy public dataset (plenty of NYC trips exceed 5 miles); it is not presented as a sensible quality rule. WARN keeps every row flowing while still recording per-expectation passed/failed counts in the event log, which is exactly the payload both notification paths consume.

## Why a pair and not just the hook

The event-hooks documentation states the limitation plainly: SDP "attempts" to run each hook on every emitted event, waits "a fixed, non-configurable period" before terminating the pipeline's compute, and "there is no guarantee that all hooks will be triggered on all events before compute termination." The events this pattern cares about (`flow_progress` with expectation counts) are emitted as flows complete, late in the update, adjacent to that termination window. So the hook is the right fast path and the wrong only path.

The backstop is one scheduled Alert v2 over the published event log. A scheduled SQL query either runs or visibly fails, so it provides the delivery guarantee the hook lacks. Its query aggregates over a past-time window (trailing 1 day), not just the latest row: a latest-row read silently misses violations whenever alert cadence differs from pipeline cadence. If you change the alert's cron, change the `INTERVAL` in its query to stay at least as long as the cadence.

This replaces the fleet-of-scheduled-alerts approach (one alert per expectation, plus jobs to trigger them, plus a deployment script) with one hook function and one YAML block.

## The rules of the hook (learned the honest way)

These were established on a live serverless SDP run (validated 2026-07-11, Databricks CLI v0.297.2), not just read from docs:

- **Do not write Delta from inside a hook.** SDP restricts `spark.sql()` in pipeline Python to a read-oriented command allowlist: `CREATE TABLE` from a hook fails with `UNSUPPORTED_SPARK_SQL_COMMAND` (the error lists the allowlist: SELECT, DESCRIBE, SHOW variants, USE), and the SDP-patched `spark.sql()` wrapper rejects the standard PySpark parameterized-query `args=` kwarg outright. The supported notification surface inside a hook is `print` and HTTP calls such as `requests`, which is also what the official docs examples use.
- **Keep the hook fast.** Hooks run serialized, one at a time; a slow call delays every other hook and widens the window in which queued events are lost at compute termination. In a probe run with a deliberately slow (2-second) hook, forcing compute teardown mid-queue lost 7 of 18 STABLE events (39%) for that hook. The loss mechanism is real, not just quotable.
- **`hook_progress` tells you less than it sounds like.** It records only enable/disable state (`{"hook_name": ..., "state": "ENABLED"}`), one row per hook per update, at registration time. It does not record which events a hook processed, counts, timings, or failures. Per-invocation output (the printed notifications) exists only in the pipeline compute's driver log, which has no CLI or SQL surface.
- **`max_allowable_consecutive_failures` is a tradeoff, not a setting to forget.** A finite value silently disables a flaky hook until the next pipeline restart; `None` (this asset's choice) lets a permanently broken hook fail forever. That is why the optional webhook call catches and prints its own failures instead of raising.
- **`mode: development` masks the teardown behavior.** A DABs target in development mode propagates `development: true` to the pipeline, which keeps pipeline compute warm across updates instead of tearing it down after the grace period. If you are trying to observe the hook delivery gap, a dev-mode target will hide it.
- **Inside the hook, `event["details"]` arrives as a native Python dict.** The JSON-string form only appears when querying the persisted event log table. The shipped `_event_details` helper keeps a defensive string branch anyway; it costs nothing.

## Validation results

The pattern was validated end to end on a live workspace (serverless SDP, Free Edition, 2026-07-11, CLI v0.297.2) against `samples.nyctaxi.trips`:

- **Hooks run on serverless SDP pipelines.** Confirmed via `hook_progress` rows in the published event log on every update; the docs are silent on this, so it is a lived finding with the date stamped.
- **The hook fires per-expectation with exact counts.** The driver log line `EXPECTATION VIOLATION | dataset=...monitored_trips | expectation=demo_short_trip | failed=3003 | passed=18929` matched the event log's `flow_progress` counts for the same `update_id` exactly (3,003 failed, 18,929 passed of 21,932 sample rows), reproduced across multiple full-refresh updates.
- **The backstop alert delivers end to end.** The sweep query, the scheduled execution (confirmed via query history), the alert state (`TRIGGERED` via `alerts-v2 get-alert`), and the actual email delivery (from `noreply@databricks.com`, evaluated value matching the independently computed sum exactly) all agreed.
- **`comparison_operator: GREATER_THAN` validates and deploys** in the Alerts v2 bundle resource, and **the `event_log` block is accepted** by the DABs pipeline resource as written here.
- **Alerts v2 bundle resources update in place on rename**; changing `display_name` and redeploying kept the same alert id with no orphaned duplicate.

The shipped asset itself (installed via `bundle init --template-dir`, wrapped in a fresh bundle) was then re-validated end to end on the same workspace and date: install produced exactly the expected files, `bundle validate` passed first try, the pipeline update completed on serverless with the hook registered (`hook_progress: ENABLED`), the driver log carried the exact `failed=3003 | passed=18929` notification line, and the backstop alert evaluated on its cron to `TRIGGERED` with the email delivered (evaluated value 3003 matching the sweep query run independently).

## Honest limits and open questions

- Hook delivery is best-effort by design; this asset treats that as an architectural input (hence the backstop), not a problem it solves.
- The backstop inherits scheduled-scan limits at miniature scale: latency bounded by its cron cadence, and a SQL warehouse in the loop. The `monitoring-sql-warehouse` asset (2X-Small serverless, `auto_stop_mins: 1`) exists for exactly this workload shape.
- The hook cannot notice "the pipeline has not run at all": no update, no events, no hook. Pair with a freshness check (for example Unity Catalog data quality monitoring's anomaly detection) if that failure mode matters.
- Still open, not settled by the validation run: whether the fixed grace period drops queued hook events automatically under default (non-development) pipeline teardown (the observed loss was under a forced stop); the exact size of that grace period; whether a literal non-parameterized `INSERT` from a hook would pass the `spark.sql()` allowlist (untested; two other write patterns failed for two different reasons); and the full `comparison_operator` enum beyond the confirmed `EQUAL` and `GREATER_THAN`.

## Inspecting the results

`<target_dir>/event_log_queries.sql` ships three queries against the published event log table (`<catalog>.<schema>.dq_notifications_event_log`): per-expectation passed/failed counts for the latest update (the numbers the hook prints), the `hook_progress` registration states, and the backstop alert's exact sweep query so you can see the value the alert compares against its threshold.

## Tests

Repo-level tests (`tests/assets/test_sdp_expectation_notifications.py`) verify the asset installs the expected files, the pipeline source parses and contains the hook wired to the supported surface (and no `spark.sql` calls anywhere in it), the resource YAMLs are valid (event-log publication, alert query shape, past-time-window aggregation, threshold, subscription, schedule), and custom prompt values flow through to filenames, resource keys, and paths. End-to-end firing is verified live on a workspace (see above).

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

It demonstrates one notification pattern with its tradeoffs documented, not a general alerting framework. For schema-level freshness and completeness anomalies (the failure class expectations structurally cannot see), look at Unity Catalog [data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/); for a broader data-quality framework, look at [DQX](https://databrickslabs.github.io/dqx/) (Databricks Labs).

## References

1. [Lakeflow SDP event hooks](https://docs.databricks.com/aws/en/ldp/event-hooks)
2. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [`event_log` table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/event_log)
5. [DABs alert resource (Alerts v2)](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)
