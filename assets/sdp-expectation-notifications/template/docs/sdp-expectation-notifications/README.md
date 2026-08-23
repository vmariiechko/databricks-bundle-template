# SDP Expectation Notifications (in-bundle usage)

This asset installs per-expectation data-quality notification for a Lakeflow Spark Declarative Pipeline as a pair: a native event hook fires the moment an expectation result with failed records is logged, whether the expectation's action is `warn` or `drop` (fast, best-effort, throttled to at most one notification per expectation per window), and one DABs-managed Databricks SQL alert sweeps the published pipeline event log on a schedule (guaranteed, one email per state change). The demo pipeline runs on the public `samples.nyctaxi.trips` dataset with a deliberately tight WARN expectation, so both paths fire on the first run.

The full design rationale, the validated facts, and the honest caveats live in the asset README in the [databricks-bundle-template repo](https://github.com/vmariiechko/databricks-bundle-template/tree/main/assets/sdp-expectation-notifications). This file covers what you do after install.

## What this asset installed

| Path | Purpose |
|---|---|
| `<target_dir>/expectation_notifications_pipeline.py` | The SDP pipeline source: demo table, WARN expectation, and the notifier event hook. |
| `<target_dir>/event_log_queries.sql` | Queries for expectation counts, `hook_progress` states, and the backstop's sweep. |
| `resources/<pipeline_resource_key>.pipeline.yml` | The DABs pipeline resource (publishes the event log to a UC table). |
| `resources/<pipeline_resource_key>_backstop.alert.yml` | The backstop alert resource (a Databricks SQL alert; scheduled sweep + email subscription). |
| `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md` | Companion agent skill: wire the pattern into your own pipeline. |
| `docs/sdp-expectation-notifications/README.md` | This file. |

## Before you deploy

1. **Placeholders.** If you kept the defaults for `warehouse_id` or `notification_email` at install, `resources/<pipeline_resource_key>_backstop.alert.yml` contains `WAREHOUSE_ID_PLACEHOLDER` or `EMAIL_PLACEHOLDER`. Replace them: find a warehouse id with `databricks warehouses list`, and use an email that belongs to a workspace user. If you installed the `monitoring-sql-warehouse` asset from the same repo, you can reference its warehouse instead: `${resources.sql_warehouses.monitoring_sql_warehouse.id}`. If you kept the `state_volume_path` placeholder, the hook's throttle runs in-memory only (still removes per-microbatch repeats within an update); to add cross-update throttling, set `dq_notify.state_dir` in the pipeline resource to a path under an existing UC Volume.
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
- **Hook registration state** is the second query (`hook_progress` events). It records ENABLED, FAILED, and DISABLED transitions (so a failing hook is visible here), but not per-invocation execution.
- **Throttle state** (when `dq_notify.state_dir` is set) is browsable: `<state_dir>/dq_notify_state/<pipeline>/`, one human-readable JSON marker per expectation with the last-notified time and counts, overwritten in place. Expect one notification per expectation per `dq_notify.throttle_seconds` window, not one per microbatch; a rerun inside the window notifies nothing, by design.
- **The backstop alert** evaluates daily at 06:00 UTC by default. To see it immediately, open the alert in the workspace UI (SQL > Alerts) and run it manually, or temporarily tighten `quartz_cron_schedule`. On trigger it emails the configured subscription from `noreply@databricks.com`, subject `Databricks SQL Alert: <alert display name> (<STATE>)`, so the state is filterable from the subject line alone; the body carries the evaluated metric against its threshold plus a five-run mini history (which lists evaluations, not notifications, so rows that notified nobody appear in it). The third query in `event_log_queries.sql` is the alert's exact sweep query, so you can preview the evaluated value.

## Optional webhook (Slack, Teams, or generic)

The hook posts each due notification to a webhook when one is configured, in the format selected by `dq_notify.channel_format` (`slack`, `teams`, or `generic`). Route hook posts to chat-style channels; email belongs to the backstop alert.

No endpoint for the hook to post to (a Slack or Teams webhook, a receiver you control, any reachable HTTPS service)? Skip this section and the hook's webhook config entirely: print-only output has no advantage over the event log the backstop already sweeps, so the backstop alone covers you (see the asset README's "Notification channels" section for the full reasoning).

A webhook URL is a credential (it grants posting rights), so the real setup goes through a secret scope:

```bash
databricks secrets create-scope dq-notifications
databricks secrets put-secret dq-notifications slack_webhook_url --string-value "<your webhook url>"
```

Then set `dq_notify.webhook_secret_scope: dq-notifications` in the pipeline resource's `configuration` and redeploy; the pipeline resolves the URL at startup and, if the scope is missing, prints a notice and runs print-only (your pipeline is never blocked by notification config). The plain `dq_notify.webhook_url` config exists as a demo-only shortcut. Do not use `{{secrets/scope/key}}` in pipeline configuration; it is not interpolated and the literal string arrives.

## Wire the pattern into your own pipeline (companion skill)

Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md` and it will adapt the pattern to your pipeline: add the hook to your pipeline source, publish your event log to a UC table, and point one backstop alert at it. It proposes and confirms with you; it does not rewrite your pipeline silently.

To start, paste a prompt like this into your agent and fill the placeholders:

```
Use the sdp-expectation-notifications skill to add per-expectation notifications
to my SDP pipeline.

- Pipeline source file(s): <path(s) in this repo; multiple pipelines welcome,
  the hook and state layout support them without per-pipeline config>
- Event log: <already published to a UC table at catalog.schema.table | not published yet>
- Notify via: <driver-log print only | also webhook: secret scope/key, channel format slack|teams|generic>
- Throttle: <window in seconds, default 3600; state path under an existing UC
  Volume for cross-update throttling, or in-memory only>
- Backstop alert: warehouse <id or resource reference>, recipient <email>,
  cadence <e.g. daily 06:00 UTC>
- Deploy mode: <I will deploy and run myself | you may deploy and run>

Read my pipeline and expectations first, propose the changes for me to confirm,
then apply them and guide me through (or do) the deploy and verification.
```

## Adjusting the backstop

- **Cadence and window are coupled, and cadence should match your pipeline's mode.** The alert query aggregates the trailing `INTERVAL 1 DAY`; the schedule is daily. If you change the cron, change the interval to stay at least as long as the cadence, or violations can fall between sweeps. The shipped daily cadence fits a triggered pipeline; a continuous pipeline needs a tighter cron and window (Databricks positions continuous mode for freshness between 10 seconds and a few minutes, so a daily sweep would add a full day of latency on top of that), but a tighter cron means more warehouse wake-ups: the `monitoring-sql-warehouse` asset (2X-Small serverless, `auto_stop_mins: 1`) is sized for that tradeoff.
- **Notification behavior (measured live):** one email per state transition, however many evaluations stay TRIGGERED; `notify_on_ok: true` (the shipped default) adds exactly one recovery email; the commented `retrigger_seconds` re-sends while TRIGGERED at most once per window, a deliberate escalation knob (for example 86400 for a daily reminder on a critical pipeline). While the alert stays TRIGGERED, new failures inside the window send nothing; the recovery email is what re-arms attention.
- **If the sweep query itself breaks** (dropped table, deleted warehouse), the alert flips to ERROR and emails on every evaluation until fixed. It cannot die silently; treat an `(ERROR)` email as a page.
- **Recipients** live in `evaluation.notification.subscriptions` (add more `user_email` entries, or a `destination_id` for a workspace notification destination, which is how Slack, MS Teams, PagerDuty, and generic webhooks attach to the backstop with zero code; managing destinations requires workspace admin, per the docs). Worth knowing before you pick one: a Slack destination's message carries a state-change title and two links and no data, where the email carries the evaluated metric against its threshold, so the destination type also decides how much a responder can triage without clicking.
- **Threshold** is `failed_records > 0`. Raise the threshold or filter the query to specific expectation names if the demo tripwire pattern is too chatty for your rules. If you edit the query, keep it returning exactly one row: the shipped `COALESCE(SUM(...), 0)` guarantees that, and an alert whose query returns no rows flips to ERROR (`Empty result state: Error`), which emails on every evaluation until fixed.

## References

1. [Lakeflow SDP event hooks](https://docs.databricks.com/aws/en/ldp/event-hooks)
2. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [DABs alert resource](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)
5. [Databricks sample datasets (`samples.nyctaxi.trips`)](https://docs.databricks.com/aws/en/discover/databricks-datasets)
