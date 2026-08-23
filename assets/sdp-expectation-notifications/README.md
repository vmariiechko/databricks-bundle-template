# sdp-expectation-notifications

Per-expectation data-quality notification for Lakeflow Spark Declarative Pipelines (SDP), as a pair: a scheduled DABs-managed **Databricks SQL alert** sweeps the published pipeline event log (the guaranteed path, throttled by the platform to one email per state change), and a native **event hook** posts the moment an expectation result with failed records is logged, whether the expectation's action is `warn` or `drop` (the fast path, throttled by this asset to one notification per expectation per window). The pair exists because the platform explicitly does not guarantee hook delivery; each half covers the other's gap.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/sdp-expectation-notifications
```

You will be prompted for `target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `schema`, `warehouse_id`, `notification_email`, `state_volume_path`, and `skill_dir` (all with safe defaults; the warehouse id, email, and volume path default to placeholders you replace before deploying). The asset installs the pipeline source (with the throttled event hook inside), event-log parsing queries, the DABs pipeline resource, the backstop alert resource, an in-bundle usage doc, and a companion agent skill.

## Two doors

This is a dual-door asset:

- **Door 1, the reference pipeline.** A self-contained demo on the public `samples.nyctaxi.trips` dataset: one streaming table with a deliberately tight WARN expectation, the throttled notifier hook, and the backstop alert. Deploy it, run it, and watch both notification paths fire on the first update. This README documents it.
- **Door 2, the companion agent skill** at `<skill_dir>/skills/sdp-expectation-notifications/SKILL.md`. Point a coding agent (Claude Code, Codex, or Genie Code on Databricks) at it and it wires the pattern into your own SDP pipelines: the same hook code runs unchanged in any number of pipelines because it scopes its throttle state by the pipeline identity carried in every event. It proposes and confirms; it is not an auto-rewriter.

## Architecture

```
samples.nyctaxi.trips
        │
        ▼
  monitored_trips  @dp.expect (WARN, fails by design on the healthy sample)
        │
        ├─► event hook (in-pipeline)          fires when the flow_progress event
        │     two-layer time-aware throttle   is logged; best-effort delivery;
        │     print + optional webhook        at most 1 notification per
        │     (Slack / Teams / generic)       expectation per throttle window
        │         │
        │         └─ state markers (optional): <volume>/dq_notify_state/
        │              <pipeline>/<dataset>__<expectation>.json
        │
        └─► published event log (UC table: dq_notifications_event_log)
              ▲
              └── backstop SQL alert          scheduled sweep over a trailing
                    email / destinations      1-day window; guaranteed
                    1 email per state change  evaluation; notify_on_ok closes
                                              the loop on recovery
```

The demo WARN rule `trip_distance < 5` is a tripwire chosen to fail on a healthy public dataset; it is not presented as a sensible quality rule. WARN keeps every row flowing while still recording per-expectation passed/failed counts in the event log, which is exactly the payload both notification paths consume.

## Why the hook is throttled (measured, not assumed)

The v1.11.0 hook notified on every qualifying `flow_progress` event. Measured live (2026-07-17, serverless, non-development-mode target): expectation counts arrive **once per microbatch**, so one failing expectation on a 4-file backlog notified 4 times in a single update (failed counts 708, 682, 636, 686, summing exactly to the single-batch 2,712); a full refresh re-notified everything; a continuous pipeline emitted a fresh event within about 70 seconds of every arriving file. Wire that to a real channel on a failing scheduled pipeline and it floods.

The revised hook throttles at most one notification per (pipeline, dataset, expectation) per `dq_notify.throttle_seconds` (default 3600), in two time-aware layers:

- **In-memory (always on):** kills repeats within one Python process: later microbatches of the same update, and a continuous pipeline's whole run. Time-aware on purpose: continuous compute lives for days, so a notify-once-per-process set would go silent forever. Validated on a continuous pipeline: NOTIFY, SUPPRESS at +89s (inside a 180s test window), NOTIFY again at +239s.
- **Durable markers (optional):** small human-readable JSON files under `<state_dir>/dq_notify_state/<pipeline>/<dataset>__<expectation>.json` in a UC Volume you already own, carrying the throttle across updates and restarts. One file per expectation, overwritten on notify, never growing; reading one answers "when did this last notify and how bad was it". Validated across full refreshes and process restarts: two consecutive full refreshes produced 12 raw events and 2 notifications, and a rerun minutes later produced 0.
- **Multi-pipeline safe by construction:** state is scoped per pipeline (identity read from the event's own `origin`, no configuration), so pipelines cannot cross-suppress; validated with two pipelines sharing one state root.
- **Fail-open:** any state error means notify, never stay silent. Empty `dq_notify.state_dir` (the placeholder default) runs in-memory only. `dq_notify.throttle_seconds: "0"` restores the old per-microbatch behavior.

An update that processes no new rows emits no expectation events at all (measured), so re-running a pipeline on static data does not re-notify even unthrottled; the flood mechanisms are new data, full refreshes, retries, and continuous mode.

## Notification channels

The two lanes get channels in two different ways:

- **Backstop (email and beyond, zero code):** the alert subscribes an email by default. Notification destinations can only be configured for Databricks SQL and jobs, so a destination is how Slack, MS Teams, PagerDuty, or a generic webhook attach to the backstop: create a workspace notification destination (Settings > Notifications; the docs state you must be a workspace admin to manage them) and reference it via the commented `destination_id` line in the alert YAML. A destination is a wrapper around a webhook, not a substitute for one, but for an alert it is a thin one: a Slack destination takes the incoming webhook URL and nothing else, and so does Teams. The OAuth token, channel id, App ID, Auth Secret, Channel URL, and Tenant ID fields exist on the form, are marked `(optional)`, and the form's own section heading scopes them to dashboard subscriptions, a different feature; verified live 2026-08-22 on a Slack destination that delivered five messages while its stored config read `url_set: true, oauth_token_set: false, channel_id_set: false`. EMAIL is the only destination type taking plain addresses with no webhook. Minting the Slack webhook is still a Slack app install (per Slack's own docs: create an app, enable incoming webhooks, authorize it into the workspace), so the credential still has to exist; what a destination buys is centralizing it once at workspace level instead of pasting it into every alert. Also worth knowing (measured live 2026-07-26): a destination and a `user_email` pointing at the same address produce two independent, non-deduplicated sends per trigger, not a merged one.
- **Hook (webhook formats):** `dq_notify.channel_format` selects the payload: `slack` (`{"text": ...}`, validated end to end: secret scope to channel message, HTTP 200), `teams` (Workflows Adaptive Card envelope, documented format, not live-tested by this asset), or `generic` (plain JSON with the violation fields; live-tested 2026-08-22, all six fields arriving verbatim and correctly typed at a third-party collector). Route hook posts to chat-style channels that tolerate an occasional repeat; email belongs to the backstop. There is no Databricks-native email surface inside a hook, which is the accurate form of that limit: the hook does reach arbitrary HTTPS (lived 2026-08-22, shipped code, two unrelated third-party hosts), so an email API is reachable in principle, but the shipped `requests.post` passes no `headers` argument, so an authenticated email API needs the hook modified first. And the egress result was measured on Free Edition serverless SDP with no egress controls configured: in a workspace with an egress firewall, a network policy, or private-link networking, the network policy decides, not the hook.

**No endpoint to deliver to? Deploy the backstop alone.** Without a delivery surface, print-only hook output has no advantage over the published event log the backstop already sweeps; the hook's only edge is latency, and that's worthless with nowhere to deliver it. The test is broader than a chat integration: anything the hook can POST to counts, whether that is a Slack or Teams webhook, a receiver you control, or another reachable HTTPS service, subject to the two limits above (no `headers` on the shipped call, and your network policy). If nothing qualifies, skip the hook and ship just the backstop alert.

**Webhook URLs are credentials** (a Slack incoming webhook grants posting rights). Real setups put the URL in a secret scope and set `dq_notify.webhook_secret_scope`/`dq_notify.webhook_secret_key`; the pipeline resolves it via `dbutils.secrets.get` at startup, which works at module level in serverless SDP Python (validated live), and degrades to print-only if the scope is missing (also validated). Two things that do NOT work, so you do not have to rediscover them: `{{secrets/scope/key}}` in pipeline configuration is not interpolated (the literal string arrives), and the plain `dq_notify.webhook_url` config is a demo-only convenience.

### One violation, three message shapes

Same violation, same moment, three different payloads (measured live 2026-08-22). Choosing a delivery lane, and a destination type inside it, is also choosing how much a responder can triage before clicking through.

| Lane | What the recipient sees without clicking |
|---|---|
| Hook webhook (fast) | dataset, expectation name, exact `failed`/`passed` counts, at violation time |
| Backstop email (guaranteed) | the evaluated metric against its threshold (for example `3003.0 > 0.0`), plus an embedded five-run mini history |
| Backstop Slack destination (guaranteed) | a state-change title and two deep links, no data at all |

The hook's message is the payload; the email is a summary with numbers; the destination message is a pointer that says go look.

## The rules of the hook (learned the honest way)

Established on live serverless SDP runs (2026-07-11, 2026-07-17/18, and 2026-08-22, CLI v0.297.2):

- **Do not write Delta from inside a hook.** `spark.sql()` in SDP pipeline Python is restricted to a read allowlist: `INSERT INTO` fails with `UNSUPPORTED_SPARK_SQL_COMMAND` (the error lists the allowlist: SELECT, DESCRIBE, SHOW variants, USE), `CREATE TABLE` fails the same way, and the SDP-patched `spark.sql()` rejects the parameterized-query `args=` kwarg. All three write paths are closed; this is definitive.
- **Durable state goes through UC Volume file I/O instead.** Plain Python `open()` against `/Volumes/...` works from inside a hook: create, overwrite, read, `os.path.exists`, `os.listdir`, `os.stat`, `os.makedirs` all validated live. The one gap: append to an existing file fails (`OSError [Errno 29] Illegal seek`), which is why the markers are overwrite-only.
- **Reads are fine.** `spark.sql("SELECT ...").collect()` works reliably from a hook (validated across many invocations), so a hook can consult a small gate table if you need a manual mute switch.
- **The hook reaches arbitrary HTTPS, and your network policy is what limits it.** Lived 2026-08-22: the shipped, unmodified hook POSTed to two unrelated third-party collectors (different operators), HTTP 200, the request arriving bare at one of them with no proxy header, no policy header, and no interception signature. That was Free Edition serverless SDP with no egress controls configured; a workspace with an egress firewall, a network policy, or private-link networking may behave differently, and that could not be tested here. Read the two halves together: the hook itself imposes no restriction on outbound HTTPS, and in a governed workspace the network policy is what decides.
- **Keep the hook fast; the grace budget is seconds.** Hooks run serialized, and compute is torn down shortly after an update completes. A hook needing about 1s per event drained 5 queued events with zero loss, all within about 8 seconds of completion. A hook needing 20s per event had its first event start 3 seconds after completion, never finish, and lost **6 of 6** notifications under normal, non-forced teardown. Keep total hook work in single-digit seconds. No retries, tight webhook timeout (5s), marker I/O only (~100ms); the POST itself measured 116 ms on success and 3 ms to fail on an unresolvable name (instrumented, 2026-08-22), so one call per event is comfortably affordable and unbounded fan-out is what is not. The exact platform timer is not documented and we have not established it.
- **`hook_progress` records ENABLED, FAILED, and DISABLED transitions** (correcting v1.11.0, which claimed enable-state only). Hook health is event-log-observable and alertable. It still does not record per-invocation output; the printed notifications exist only in the pipeline compute's driver log, which has no CLI or SQL surface.
- **`max_allowable_consecutive_failures` is a tradeoff.** A finite value disables a flaky hook until the next restart (visible as `DISABLED` in `hook_progress`, but notifications silently stop); `None` (this asset's choice) lets a broken hook fail forever, which is why every failure path in the shipped hook prints instead of raising.
- **`mode: development` masks the teardown behavior.** A DABs development-mode target keeps pipeline compute warm across updates, hiding both the delivery gap and the fresh-process-per-update behavior (in non-dev mode each update gets a new Python process; measured via per-process ids).
- **Inside the hook, `event["details"]` arrives as a native Python dict**, and `event["origin"]` carries `pipeline_name` and `pipeline_id` (the basis for zero-config multi-pipeline state scoping).
- **The hook covers `warn` and `drop` identically, not just `warn`.** It filters purely on `failed_records > 0` inside the expectations array and never inspects the expectation's action type, so `@dp.expect` and `@dp.expect_or_drop` rules notify the same way. The demo ships one `warn` rule because `warn` keeps every row flowing, which makes the demo repeatable; it is not a limit of the hook itself. `details.flow_progress.data_quality.dropped_records` is DROP-only (0 on a WARN row) and is how you tell from the event log alone that rows were discarded rather than merely flagged. Databricks' own docs exclude `fail` from this metrics recording entirely, because a `fail` action stops the update instead of letting it complete.

## The backstop's notification behavior (measured)

- **Default: exactly one email per state transition.** Nine consecutive TRIGGERED evaluations on an every-minute cron produced exactly one email; the state change is what notifies, not the evaluation. The masking consequence: while the alert stays TRIGGERED, new failures inside the sweep window send nothing, which is why `notify_on_ok: true` ships as the default: the single recovery email (also measured: exactly one) closes the loop and re-arms attention. Since 2026-08-22 this is displayed rather than inferred: the alert's History panel carries a `Notified destinations` column, and it is empty on evaluations that did not change state. One reading trap in the email itself: its embedded `Last 5 runs` block lists evaluations, not notifications, so rows that notified nobody appear in it.
- **`retrigger_seconds` is deliberate re-nagging:** re-sends at the first evaluation past each window (measured with 120s: gaps of 120s, 180s, 179s, aligned to evaluation ticks). Off by default; the commented block suggests 86400 as a daily "still broken" escalation for critical pipelines.
- **ERROR does not throttle.** If the sweep query itself fails, the alert flips to ERROR and emails on **every evaluation** until fixed (measured: 5 emails in 4 minutes). The backstop cannot die silently; treat an `(ERROR)` email as a page.
- The sweep query aggregates over a past-time window (trailing 1 day), not just the latest row; keep the window at least as long as the cadence if you change the cron.
- **Do not edit the sweep query into a shape that can return zero rows.** The alert's Advanced panel reads `Empty result state: Error` on an alert deployed from this asset's resource, which sets no such field: no rows means ERROR, and ERROR emails on every evaluation. The shipped query wraps its aggregate in `COALESCE(SUM(...), 0)`, so it always returns exactly one row and cannot hit this. A `GROUP BY`, a `HAVING`, or a filter that can match nothing silently converts the backstop into a per-evaluation ERROR emailer.
- **Cron cadence should match the pipeline's mode.** The shipped daily 06:00 UTC cron, paired with a 1-day window, fits a triggered pipeline on a daily-or-slower cadence. A continuous pipeline is a different shape: Databricks positions continuous mode for freshness requirements between 10 seconds and a few minutes, so a daily sweep adds a full day of latency on top of that. Tighten both the cron and the `INTERVAL` together if the pipeline runs continuously, but tightening costs more warehouse wake-ups; the `monitoring-sql-warehouse` asset in this repo (2X-Small serverless, `auto_stop_mins: 1`) is sized for exactly that tradeoff.

## Validation results

v1.11.0's pattern was validated end to end on 2026-07-11 (hook fires with exact counts matching the event log; backstop delivers email; resources deploy and update in place). The v1.12 revision was validated on 2026-07-17/18 (Free Edition serverless, CLI v0.297.2, non-development-mode target):

- Per-microbatch multiplication measured (4 events for one expectation on a 4-file backlog; sums match single-batch exactly: 708+682+636+686 = 2,712).
- Two-layer throttle: 12 raw events across two consecutive full refreshes reduced to 2 notifications; cross-update suppression through marker files after a process restart; multi-pipeline isolation with two pipelines sharing one state root.
- Continuous mode with Auto Loader: notify, suppress inside the window, re-notify after it, in one long-lived process; continuous pipelines auto-start on `bundle deploy`.
- Slack end to end: secret scope, `dbutils.secrets.get` at module level, throttled hook, two channel messages with HTTP 200 and counts matching the hook records exactly; missing secret scope degraded to print-only with the pipeline unaffected.
- Databricks SQL alerts: one email per state transition (9 TRIGGERED evaluations, 1 email), `retrigger_seconds` re-send alignment, exactly one `notify_on_ok` recovery email, ERROR emailing every evaluation.
- Drop-expectation coverage, live 2026-07-26: a `drop` expectation on the same source and tripwire condition produced the same passed/failed shape as the WARN row (18929 passed / 3003 failed on 21,932 total rows), the hook fired with an exact-matching driver-log line, the update reported `COMPLETED` while discarding 3,003 of 21,932 rows (13.7%), `dropped_records` read 3003 on the DROP row versus 0 on the WARN row, and the backstop's sweep query summed both expectations with no special-casing (6,006 = 3,003 + 3,003).

The 2026-08-22 session (same workspace and CLI, non-development-mode target) added:

- Arbitrary HTTPS egress from the hook: the shipped, unmodified code delivered to two unrelated third-party collectors, HTTP 200, one capture bare (no proxy or policy header). Limit: that workspace had no egress controls configured, so in a governed workspace the network policy is what decides.
- The `generic` payload live-tested: all six fields (`text`, `pipeline`, `dataset`, `expectation`, `failed_records`, `passed_records`) arrived verbatim, the two counts as JSON numbers.
- Per-event webhook cost, instrumented: 116 ms on success, 3 ms to fail on an unresolvable name.
- The delivery-failure line with a real instance rather than a described shape: `WEBHOOK_DELIVERY_FAILED: ConnectionError: HTTPSConnectionPool(...) ... NameResolutionError ... [Errno -2] Name or service not known`. The class is `requests.exceptions.ConnectionError` (`type(e).__name__` renders it bare, which collides with the Python builtin's name). The violation line printed first, the update still reported `COMPLETED`, and the hook was not disabled.
- A Slack notification destination created from the incoming webhook URL alone, delivering five messages, one per state change; its stored config reads `url_set: true, oauth_token_set: false, channel_id_set: false`.
- One notification per state transition shown by the product rather than inferred from counting emails: the History panel's `Notified destinations` column is empty on evaluations that did not change state.

## Honest limits and open questions

- Hook delivery is best-effort by design; the throttle makes the fast lane quiet, not reliable. The backstop remains the guaranteed path.
- The two lanes de-duplicate independently and share no state: one violation can produce one hook message and one backstop email. Different audiences, different guarantees; by design.
- The hook cannot notice "the pipeline has not run at all": no update, no events, no hook. Pair with a freshness check (for example Unity Catalog data quality monitoring's anomaly detection) if that failure mode matters.
- The backstop inherits scheduled-scan limits: latency bounded by its cron cadence, and a SQL warehouse in the loop. The `monitoring-sql-warehouse` asset (2X-Small serverless, `auto_stop_mins: 1`) exists for exactly this workload shape.
- **Still open, and the one that matters most: whether hook egress is restricted in a governed workspace.** The arbitrary-HTTPS result was measured on Free Edition with no egress controls configured; an egress firewall, a network policy, or private-link networking could not be tested from there, and in a workspace that has them the network policy is what decides.
- Also still open on the hook: the Teams payload ships doc-confirmed, not live-tested; concurrent marker writes from two simultaneously running pipelines are untested (the per-pipeline folders give them no shared file to race on, but Free Edition cannot run two updates at once to prove it); and the exact numeric grace period remains unestablished, two runs bounding it loosely (one showed compute still alive at ~8s, one showed it dead before ~23s) without either being designed to measure the timer itself.
- Still open on destinations: whether managing them genuinely requires workspace admin (documented, but the verification account owns that workspace, so no blocked case was exercised), and MS Teams and PagerDuty delivery (their form field lists are lived, their delivery is not).

## Inspecting the results

`<target_dir>/event_log_queries.sql` ships queries against the published event log table (`<catalog>.<schema>.dq_notifications_event_log`): per-expectation passed/failed counts for the latest update (the numbers the hook prints), the `hook_progress` states, and the backstop alert's exact sweep query. The throttle's durable state, when enabled, is directly browsable: `<state_dir>/dq_notify_state/<pipeline>/`, one JSON per expectation with the last-notified time and counts.

## Tests

Repo-level tests (`tests/assets/test_sdp_expectation_notifications.py`) verify the asset installs the expected files, the pipeline source parses and contains the hook wired to the supported surface (and no `spark.sql` write calls anywhere in it), the throttle and payload functions behave (pure-function tests, offline), the resource YAMLs are valid, and custom prompt values flow through to filenames, resource keys, and paths. End-to-end firing is verified live on a workspace (see above).

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

It demonstrates one notification pattern with its tradeoffs documented, not a general alerting framework. For schema-level freshness and completeness anomalies (the failure class expectations structurally cannot see), look at Unity Catalog [data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/); for a broader data-quality framework, look at [DQX](https://databrickslabs.github.io/dqx/) (Databricks Labs).

## References

1. [Lakeflow SDP event hooks](https://docs.databricks.com/aws/en/ldp/event-hooks)
2. [Lakeflow SDP expectations](https://docs.databricks.com/aws/en/ldp/expectations)
3. [Monitor pipelines with the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)
4. [`event_log` table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/event_log)
5. [DABs alert resource](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)
6. [Notification destinations](https://docs.databricks.com/aws/en/admin/workspace-settings/notification-destinations)
