# Verifying the wired pattern

Load this when you are ready to prove both notification paths work on the user's pipeline. Substitute the user's real identifiers for the placeholders:

- `<event_log>` = the published event log table, for example `main.dq_notifications.dq_notifications_event_log`
- `<alert_key>` = the backstop alert's DABs resource key
- `<update_id>` = the pipeline update id you are checking (from `databricks pipelines list-updates` or the create_update event)

Checks 1, 2, and 4 are machine-checkable with read-only SQL and the CLI. Check 3 is a workspace UI observation with no CLI or SQL surface; hand it to the user and record their answer. Do not claim a check you could not run.

## 0. Static gate (before any run)

`databricks bundle validate` is clean, and the hook body respects the two SKILL.md rules (only `flow_progress` handling plus print/HTTP; no `spark.sql()` writes, no blocking work). This is a code-reading check, not a runtime one.

## 1. Hooks registered (event log)

```sql
SELECT timestamp, origin.update_id,
       details:hook_progress.hook_name AS hook_name,
       details:hook_progress.state AS state
FROM <event_log>
WHERE event_type = 'hook_progress'
ORDER BY timestamp DESC;
```

PASS when the notifier hook appears with state `ENABLED` for the update you ran. Interpret it honestly: `hook_progress` records ENABLED, FAILED, and DISABLED transitions (observed live), so a FAILED or DISABLED row is a red flag worth reporting, but the absence of failures does not prove the hook processed any particular event; per-invocation output has no event-log surface.

## 2. Expectation results recorded (event log)

```sql
SELECT
  e.dataset, e.name AS expectation,
  SUM(e.passed_records) AS passed, SUM(e.failed_records) AS failed
FROM (
  SELECT explode(from_json(
    details:flow_progress.data_quality.expectations,
    'array<struct<name: string, dataset: string, passed_records: bigint, failed_records: bigint>>'
  )) AS e
  FROM <event_log>
  WHERE event_type = 'flow_progress' AND origin.update_id = '<update_id>'
)
GROUP BY e.dataset, e.name;
```

PASS when every expectation the pipeline declares shows up with counts for the update. If the user expected violations (a test row, a known-bad source), `failed > 0` for the matching rule. This is the durable record both notification paths derive from.

## 3. The hook actually fired (driver log, user observation)

The hook's output (`EXPECTATION VIOLATION | ...` lines, and any `WEBHOOK_DELIVERY_FAILED` lines) exists only in the pipeline compute's driver log. Ask the user to: open the pipeline in the workspace UI, open the update's compute, open Logs, and search for `EXPECTATION VIOLATION`.

PASS when the printed counts match check 2's counts for the same `update_id` (expect ONE `EXPECTATION VIOLATION` line per expectation per throttle window, not one per microbatch: suppressed repeats print nothing). If a webhook is configured, also confirm the message arrived at the endpoint (the user's channel or the endpoint's own log).

## 3b. Throttle state markers (only when `dq_notify.state_dir` is set)

```bash
databricks fs ls dbfs:<state_dir>/dq_notify_state/
databricks fs cat "dbfs:<state_dir>/dq_notify_state/<pipeline folder>/<dataset>__<expectation>.json"
```

PASS when a folder named after the pipeline exists and each notified expectation has one marker whose `last_notified_at` matches the run and whose counts match check 2. A second run inside the throttle window must NOT advance `last_notified_at` (suppression proof); a run after the window must. Marker files are state, not history: one file per expectation, overwritten in place.

If the log shows nothing despite check 2 showing failures: first suspect timing (delivery is best-effort; events emitted just before compute termination can be lost, which is exactly why the backstop exists), then the hook's filter logic. A `mode: development` target keeps compute warm and its log long-lived, which makes this check easier to run and the loss scenario less likely to occur; see the development-mode caveat in `references/adapt-the-pattern.md`.

## 4. The backstop alert evaluates and delivers

1. Preview the value: run the alert's exact `query_text` read-only against the warehouse; note `failed_records`.
2. Evaluate: wait for the cron slot, or have the user click Run now on the alert in the UI (SQL > Alerts). Then check state via CLI:

   ```bash
   databricks alerts-v2 list-alerts   # find the id by display_name
   databricks alerts-v2 get-alert <id>
   ```

   PASS when `state` is `TRIGGERED` (given `failed_records > 0` in step 1) and `last_evaluated_at` is fresh. With no violations in the window, `OK` is the correct passing state; do not manufacture violations in real data to force a trigger. A persistent `ERROR` state means the query itself fails and the alert emails on EVERY evaluation until fixed (observed live); treat it as urgent, not as noise to ignore.
3. Delivery: only the recipient can confirm the email arrived (sender `noreply@databricks.com`, subject containing the alert display name and state). Expected volume, observed live: one email per state transition, plus one recovery email if `notify_on_ok` is true, plus windowed re-sends only if `retrigger_seconds` is set. Ask the user; record their answer as the delivery confirmation.

## Interpreting results honestly

Checks 1, 2, and 4 prove the durable path end to end: results recorded, sweep evaluated, notification state reached. Check 3 proves the fast path fired for the update tested; it does not prove the hook will catch every future event, because the platform explicitly does not guarantee that. Report both paths' results separately and say which checks the user verified by eye (driver log, inbox) versus what you verified by query. If a check failed, report the failure and what you observed; do not average it away.
