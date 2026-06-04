# SDP Quarantine Pattern (in-bundle usage)

This pipeline demonstrates the inverse-expectations quarantine pattern on the public `samples.nyctaxi.trips` dataset. Critical (drop) expectations route violating rows into a separate `quarantine_trips` table; valid rows flow to `silver_trips`; advisory (warn) expectations log to the pipeline event log without dropping.

The full design rationale and the NULL trap live in the asset README in the [databricks-bundle-template repo](https://github.com/vmariiechko/databricks-bundle-template/tree/main/assets/sdp-quarantine-pattern). This file covers what you do after install.

## What this asset installed

| Path | Purpose |
|---|---|
| `<target_dir>/quarantine_pipeline.py` | The SDP pipeline source (Databricks notebook): bronze, silver, quarantine. |
| `<target_dir>/expectations.json` | Declarative drop/warn rule lists (source of truth). |
| `<target_dir>/expectations.py` | Pure helper: loads rules, builds the inverse predicate. |
| `<target_dir>/event_log_queries.sql` | Queries that parse expectation results from the event log. |
| `resources/<pipeline_resource_key>.pipeline.yml` | The DABs pipeline resource definition. |
| `docs/sdp-quarantine-pattern/README.md` | This file. |

## Tables the pipeline creates

Following medallion schema separation:

- `<catalog>.<bronze_schema>.bronze_trips`: raw trips ingested from `samples.nyctaxi.trips`.
- `<catalog>.<silver_schema>.silver_trips`: rows passing every drop expectation.
- `<catalog>.<silver_schema>.quarantine_trips`: rows failing at least one drop expectation (the inverse).
- `<catalog>.<bronze_schema>.pipeline_event_log`: the published pipeline event log.

The public sample contains some naturally invalid rows (zero distance, zero or negative fare, and similar), so `quarantine_trips` is populated on the first run with no extra setup.

## Bundle integration

Most bundles already include `resources/*.yml` from `databricks.yml`:

```yaml
include:
  - resources/*.yml
```

If yours does, the pipeline resource is picked up automatically. The resource references the pipeline source with a path relative to the resource file (`../<target_dir>/quarantine_pipeline.py`); DABs translates library paths relative to the resource file's directory, so the default layout works without changes.

## Deploy and run

```bash
databricks bundle validate -t <your-target>
databricks bundle deploy -t <your-target>
```

After deploy, the pipeline appears in the workspace Pipelines list. Run it, then check the three tables and the event log.

## Inspecting expectation results

`event_log_queries.sql` parses the published event log into per-expectation passed/failed counts for the latest update, plus a focused query for the warn expectations (which never route to quarantine, so the event log is the only place they surface). Run those queries against your warehouse or in a notebook after a pipeline run.

## Configuration

The pipeline reads its catalog and silver schema from the DABs resource `configuration` block (`quarantine.catalog`, `quarantine.silver_schema`); the bronze schema is the pipeline's default `schema`. To change them later, edit the resource YAML and redeploy.

## Editing the expectations

Add or change rules in `expectations.json` under `drop` (critical, routed to quarantine) or `warn` (advisory, logged). Keep every `drop` predicate NULL-safe (guard each column with `IS NOT NULL`) so the silver/quarantine split stays a clean partition. The quarantine predicate is derived automatically from the drop list; you do not maintain it by hand.

## References

1. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
2. [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectation-patterns)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [DABs pipelines resource reference](https://docs.databricks.com/aws/en/dev-tools/bundles/resources.html#pipelines)
5. [Databricks sample datasets (`samples.nyctaxi.trips`)](https://docs.databricks.com/aws/en/discover/databricks-datasets)
