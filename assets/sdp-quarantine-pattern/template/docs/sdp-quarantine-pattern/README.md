# SDP Quarantine Pattern (in-bundle usage)

This pipeline demonstrates the inverse-expectations quarantine pattern on the public `samples.nyctaxi.trips` dataset. Critical (drop) expectations route violating rows into a separate `quarantine_trips` table; valid rows flow to `clean_trips`; advisory (warn) expectations log to the pipeline event log without dropping.

The full design rationale and the NULL trap live in the asset README in the [databricks-bundle-template repo](https://github.com/vmariiechko/databricks-bundle-template/tree/main/assets/sdp-quarantine-pattern). This file covers what you do after install.

## What this asset installed

| Path | Purpose |
|---|---|
| `<target_dir>/quarantine_pipeline.py` | The SDP pipeline source (Databricks notebook): raw, clean, quarantine. |
| `<target_dir>/expectations.json` | Declarative drop/warn rule lists (source of truth). |
| `<target_dir>/expectations.py` | Pure helper: loads rules, builds the clean and inverse predicates. |
| `<target_dir>/tests/` | Offline unit tests (`pytest` + local Spark) that prove the partition invariant and NULL routing without a workspace. |
| `<target_dir>/event_log_queries.sql` | Queries that parse expectation results from the event log. |
| `resources/<pipeline_resource_key>.pipeline.yml` | The DABs pipeline resource definition. |
| `<skill_dir>/skills/sdp-quarantine-pattern/SKILL.md` | Companion agent skill: adapt the pattern to your own dataset and verify it. |
| `docs/sdp-quarantine-pattern/README.md` | This file. |

## Adapt the pattern to your own dataset (companion skill)

This asset ships a companion agent skill at `<skill_dir>/skills/sdp-quarantine-pattern/SKILL.md`. Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at it and it will adapt the quarantine pattern to your own table: investigate your data, propose drop/warn rules for you to confirm, keep every drop predicate NULL-safe, adapt and run the offline unit tests, wire the resource into your bundle, and verify the result.

To start, paste a prompt like this into your agent and fill the placeholders:

```
Use the sdp-quarantine-pattern skill to add the quarantine pattern to my pipeline.

- Source table: <catalog.schema.table or file path>
- Catalog / schemas: <catalog>, <bronze_schema>, <silver_schema>
- Quality rules I care about: <e.g. amount must be positive; customer_id required;
  event_time must precede ship_time; flag amounts over 10000 as a warning>
- Deploy mode: <I will deploy and run myself | you may deploy and run>

Investigate the source, propose drop/warn rules for me to confirm, adapt the pattern,
run the offline unit tests, and then guide me through (or do) the deploy and live checks.
```

The skill defaults to handing deploy and run steps back to you for review; tell it explicitly if you want it to deploy and run on its own.

The skill delegates the deploy, run, and query mechanics to your agent's runtime rather than hardcoding CLI commands. On Databricks, Genie Code already knows how to drive pipelines. Locally, installing the official Databricks [ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit) agent skills gives the agent CLI authentication, profile selection, and pipeline management, which makes the workflow smoother. Optionally, the `dbx-ro-query` asset from this same repo adds a guarded read-only SQL window for the investigation and audit queries.

## Run the offline unit tests

The asset ships unit tests at `<target_dir>/tests/` that prove the partition invariant (clean + quarantine == raw) and NULL routing on crafted edge rows, with no Databricks workspace. They need Java (for PySpark) and Python 3.10+:

```bash
pip install -r <target_dir>/tests/requirements-test.txt
pytest <target_dir>/tests/ -q
```

A failing partition or NULL-routing test means a drop predicate is not NULL-safe. Fix it in `expectations.json` and rerun.

## Tables the pipeline creates

Following medallion schema separation:

- `<catalog>.<bronze_schema>.raw_trips`: raw trips ingested from the configured source (default `samples.nyctaxi.trips`).
- `<catalog>.<silver_schema>.clean_trips`: rows passing every drop expectation.
- `<catalog>.<silver_schema>.quarantine_trips`: rows failing at least one drop expectation (the inverse).
- `<catalog>.<bronze_schema>.quarantine_pipeline_event_log`: the published pipeline event log.

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

The pipeline reads its catalog, schemas, and source from the DABs resource `configuration` block (`quarantine.catalog`, `quarantine.bronze_schema`, `quarantine.silver_schema`, `quarantine.source`); the bronze schema also matches the pipeline's default `schema`. To change them later, edit the resource YAML and redeploy. Pointing `quarantine.source` at a curated test table (in a separate test target) is how you run a clean end-to-end integration test against known-good and known-bad rows.

## Editing the expectations

Add or change rules in `expectations.json` under `drop` (critical, routed to quarantine) or `warn` (advisory, logged). Keep every `drop` predicate NULL-safe (guard each column with `IS NOT NULL`) so the clean/quarantine split stays a clean partition. The quarantine predicate is derived automatically from the drop list; you do not maintain it by hand. After editing rules, rerun the unit tests in `<target_dir>/tests/` to confirm the partition still holds.

## References

1. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
2. [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectation-patterns)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [DABs pipelines resource reference](https://docs.databricks.com/aws/en/dev-tools/bundles/resources.html#pipelines)
5. [Databricks sample datasets (`samples.nyctaxi.trips`)](https://docs.databricks.com/aws/en/discover/databricks-datasets)
