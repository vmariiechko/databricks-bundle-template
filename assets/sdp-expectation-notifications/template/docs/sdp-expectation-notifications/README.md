# SDP Expectation Notifications (in-bundle usage)

This asset installs per-expectation data-quality notification for a Lakeflow Spark Declarative Pipeline as a pair: a native event hook fires the moment a WARN expectation result is logged (fast, best-effort), and one DABs-managed Alert v2 sweeps the published pipeline event log on a schedule (guaranteed). The demo pipeline runs on the public `samples.nyctaxi.trips` dataset with a deliberately tight WARN expectation, so both paths fire on the first run.

The full design rationale, the validated facts, and the honest caveats live in the asset README in the [databricks-bundle-template repo](https://github.com/vmariiechko/databricks-bundle-template/tree/main/assets/sdp-expectation-notifications). This file covers what you do after install.

## What this asset installed

| Path | Purpose |
|---|---|
| `<target_dir>/expectation_notifications_pipeline.py` | The SDP pipeline source: demo table, WARN expectation, and the notifier event hook. |
| `<target_dir>/event_log_queries.sql` | Queries for expectation counts, `hook_progress` states, and the backstop's sweep. |
| `resources/<pipeline_resource_key>.pipeline.yml` | The DABs pipeline resource (publishes the event log to a UC table). |
| `resources/<pipeline_resource_key>_backstop.alert.yml` | The backstop Alert v2 resource (scheduled sweep + email subscription). |
| `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md` | Companion agent skill: wire the pattern into your own pipeline. |
| `docs/sdp-expectation-notifications/README.md` | This file. |

## Before you deploy

1. **Placeholders.** If you kept the defaults for `warehouse_id` or `notification_email` at install, `resources/<pipeline_resource_key>_backstop.alert.yml` contains `WAREHOUSE_ID_PLACEHOLDER` or `EMAIL_PLACEHOLDER`. Replace them: find a warehouse id with `databricks warehouses list`, and use an email that belongs to a workspace user. If you installed the `monitoring-sql-warehouse` asset from the same repo, you can reference its warehouse instead: `${resources.sql_warehouses.monitoring_sql_warehouse.id}`.
2. **Bundle integration.** Most bundles already include `resources/*.yml` from `databricks.yml`:

   ```yaml
   include:
     - resources/*.yml
   ```

   If yours does, both resources are picked up automatically. The pipeline resource references the source with a path relative to the resource file (`../<target_dir>/expectation_notifications_pipeline.py`), so the default layout works without changes.

## Deploy and run

```bash
databricks bundle validate -t <your-target>
databricks bundle deploy -t <your-target>
databricks bundle run <pipeline_resource_key> -t <your-target>
```

The first update ingests the full sample table, so the demo WARN expectation (`demo_short_trip`, a tripwire chosen to fail on the healthy public sample) records failures immediately.

## What to look at after the first run

- **The hook's notification** is printed to the pipeline compute's driver log: open the pipeline in the workspace UI, go to the update's compute, open Logs, and search for `EXPECTATION VIOLATION`. There is no CLI or SQL surface for driver-log output; this is a UI observation.
- **The durable record** is the published event log table `<catalog>.<schema>.dq_notifications_event_log`. Run the first query in `<target_dir>/event_log_queries.sql` to see per-expectation passed/failed counts for the latest update; they match the numbers in the hook's printed line.
- **Hook registration state** is the second query (`hook_progress` events). Note what it does and does not tell you: one row per hook per update recording enable/disable state only, not per-invocation execution.
- **The backstop alert** evaluates daily at 06:00 UTC by default. To see it immediately, open the alert in the workspace UI (SQL > Alerts) and run it manually, or temporarily tighten `quartz_cron_schedule`. On trigger it emails the configured subscription from `noreply@databricks.com`. The third query in `event_log_queries.sql` is the alert's exact sweep query, so you can preview the evaluated value.

## Optional webhook

Set `dq_notify.webhook_url` in the pipeline resource's `configuration` block to a webhook endpoint (a Slack incoming webhook or similar) and redeploy; the hook then posts each violation message as JSON (`{"text": ...}`) in addition to printing. Keep the endpoint fast: hooks run one at a time, and a slow call delays every other hook. For authenticated endpoints, resolve tokens from a Databricks secret scope at module level, the way the official event-hooks docs example does.

## Wire the pattern into your own pipeline (companion skill)

Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md` and it will adapt the pattern to your pipeline: add the hook to your pipeline source, publish your event log to a UC table, and point one backstop alert at it. It proposes and confirms with you; it does not rewrite your pipeline silently.

To start, paste a prompt like this into your agent and fill the placeholders:

```
Use the sdp-expectation-notifications skill to add per-expectation notifications
to my SDP pipeline.

- Pipeline source file(s): <path(s) in this repo>
- Event log: <already published to a UC table at catalog.schema.table | not published yet>
- Notify via: <driver-log print only | also webhook: <url or secret scope/key>>
- Backstop alert: warehouse <id or resource reference>, recipient <email>,
  cadence <e.g. daily 06:00 UTC>
- Deploy mode: <I will deploy and run myself | you may deploy and run>

Read my pipeline and expectations first, propose the changes for me to confirm,
then apply them and guide me through (or do) the deploy and verification.
```

## Adjusting the backstop

- **Cadence and window are coupled.** The alert query aggregates the trailing `INTERVAL 1 DAY`; the schedule is daily. If you change the cron, change the interval to stay at least as long as the cadence, or violations can fall between sweeps.
- **Recipients** live in `evaluation.notification.subscriptions` (add more `user_email` entries, or a `destination_id` for a workspace notification destination).
- **Threshold** is `failed_records > 0`. Raise the threshold or filter the query to specific expectation names if the demo tripwire pattern is too chatty for your rules.

## References

1. [Lakeflow SDP event hooks](https://docs.databricks.com/aws/en/ldp/event-hooks)
2. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [DABs alert resource (Alerts v2)](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)
5. [Databricks sample datasets (`samples.nyctaxi.trips`)](https://docs.databricks.com/aws/en/discover/databricks-datasets)
