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

PASS when the notifier hook appears with state `ENABLED` for the update you ran. Interpret it honestly: `hook_progress` records enable/disable state at registration only. It proves the hook is alive, not that it processed any particular event.

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

PASS when the printed counts match check 2's counts for the same `update_id` exactly. If a webhook is configured, also confirm the message arrived at the endpoint (the user's channel or the endpoint's own log).

If the log shows nothing despite check 2 showing failures: first suspect timing (delivery is best-effort; events emitted just before compute termination can be lost, which is exactly why the backstop exists), then the hook's filter logic. A `mode: development` target keeps compute warm and its log long-lived, which makes this check easier to run and the loss scenario less likely to occur; see the development-mode caveat in `references/adapt-the-pattern.md`.

## 4. The backstop alert evaluates and delivers

1. Preview the value: run the alert's exact `query_text` read-only against the warehouse; note `failed_records`.
2. Evaluate: wait for the cron slot, or have the user click Run now on the alert in the UI (SQL > Alerts). Then check state via CLI:

   ```bash
   databricks alerts-v2 list-alerts   # find the id by display_name
   databricks alerts-v2 get-alert <id>
   ```

   PASS when `state` is `TRIGGERED` (given `failed_records > 0` in step 1) and `last_evaluated_at` is fresh. With no violations in the window, `OK` is the correct passing state; do not manufacture violations in real data to force a trigger.
3. Delivery: only the recipient can confirm the email arrived (sender `noreply@databricks.com`, subject containing the alert display name and state). Ask the user; record their answer as the delivery confirmation.

## Interpreting results honestly

Checks 1, 2, and 4 prove the durable path end to end: results recorded, sweep evaluated, notification state reached. Check 3 proves the fast path fired for the update tested; it does not prove the hook will catch every future event, because the platform explicitly does not guarantee that. Report both paths' results separately and say which checks the user verified by eye (driver log, inbox) versus what you verified by query. If a check failed, report the failure and what you observed; do not average it away.
