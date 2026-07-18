"""Lakeflow SDP pipeline: per-expectation notification via a throttled event hook.

One streaming table carries a deliberately tight WARN expectation that fails on
the healthy public sample, so the hook has something to notify about on the
first run. The hook filters `flow_progress` events for expectation results with
failures, de-duplicates, and notifies via `print` (always) and an optional
webhook (Slack, Teams, or generic JSON).

Noise control is a two-layer, time-aware throttle (validated live 2026-07-18):

- In-memory layer (always on): a last-notified timestamp per (pipeline,
  dataset, expectation). Without it, one failing expectation notifies once per
  microbatch: a multi-file backlog or a continuous pipeline multiplies every
  violation (measured: 4 notifications for one expectation in one update).
  Time-aware on purpose: continuous pipelines keep one Python process alive
  for days, so a notify-once-per-process set would go silent forever.
- Durable marker layer (optional): JSON marker files under
  `<state_dir>/dq_notify_state/<pipeline>/<dataset>__<expectation>.json` in a
  UC Volume, carrying the throttle across updates and compute restarts. Point
  `dq_notify.state_dir` at a path under an EXISTING volume to enable; leave
  empty for in-memory only. One file per expectation, overwritten on notify,
  never growing. Fail-open: any state error means notify, never stay silent.

The hook is the fast path only. Event hook delivery is best-effort: the
platform waits only seconds after an update completes before terminating
compute (measured: a hook needing 20s per event lost 6 of 6 queued
notifications under normal teardown), and does not guarantee every hook runs
on every event. Keep hook work in single-digit seconds. The companion backstop
alert (see `resources/`) sweeps the published event log on a schedule as the
guaranteed path.

Do not write Delta tables from inside a hook via `spark.sql()`. SDP restricts
`spark.sql()` in pipeline Python to a read allowlist (INSERT fails with
`UNSUPPORTED_SPARK_SQL_COMMAND`; allowed: SELECT, DESCRIBE, SHOW variants,
USE; observed live 2026-07-18). Durable state goes through plain-Python UC
Volume file I/O instead (create/overwrite/read work; append does not).

Webhook URLs are credentials (a Slack incoming webhook grants posting rights).
Resolve them from a secret scope: set `dq_notify.webhook_secret_scope` (and
key) and the module resolves via `dbutils.secrets.get`, which works at module
level in serverless SDP pipeline Python (validated live; `{{secrets/...}}`
interpolation in pipeline configuration does NOT resolve and arrives as the
literal string). The plain `dq_notify.webhook_url` config is the demo-only
fallback. A missing scope is caught and the hook degrades to print-only.
"""

import json
import os
import time

import requests
from pyspark import pipelines as dp
from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()

SOURCE_TABLE = spark.conf.get("dq_notify.source", "samples.nyctaxi.trips")

# Throttle: at most one notification per (pipeline, dataset, expectation) per
# window. 0 disables throttling entirely (v1.11 behavior: one notification per
# failing expectation per microbatch; expect floods on multi-batch pipelines).
THROTTLE_SECONDS = int(spark.conf.get("dq_notify.throttle_seconds", "3600"))
# Durable state root under an EXISTING UC Volume; empty = in-memory only.
STATE_DIR = spark.conf.get("dq_notify.state_dir", "").rstrip("/")

# Webhook payload format: "slack" (validated live), "teams" (documented
# Workflows Adaptive Card envelope, not live-tested), or "generic" (plain JSON
# with the violation fields, for webhook receivers you control).
CHANNEL_FORMAT = spark.conf.get("dq_notify.channel_format", "slack")

# Webhook resolution: secret scope first (real setups), plain config second
# (demo), empty means print-only. Never log the resolved URL.
WEBHOOK_SECRET_SCOPE = spark.conf.get("dq_notify.webhook_secret_scope", "")
WEBHOOK_SECRET_KEY = spark.conf.get("dq_notify.webhook_secret_key", "slack_webhook_url")
WEBHOOK_URL = spark.conf.get("dq_notify.webhook_url", "")
if WEBHOOK_SECRET_SCOPE:
    try:
        WEBHOOK_URL = dbutils.secrets.get(WEBHOOK_SECRET_SCOPE, WEBHOOK_SECRET_KEY)  # noqa: F821
    except Exception as e:
        print(
            f"DQ_NOTIFY_SECRET_UNAVAILABLE: scope={WEBHOOK_SECRET_SCOPE} "
            f"key={WEBHOOK_SECRET_KEY} ({type(e).__name__}); webhook disabled, print-only."
        )
        WEBHOOK_URL = ""

_MEM_LAST = {}  # (pipeline, dataset, expectation) -> epoch of last notification


@dp.table(comment="NYC taxi trips with one deliberately tight warn expectation.")
@dp.expect("demo_short_trip", "trip_distance < 5")
def monitored_trips():
    """Demo table whose WARN expectation fails on the healthy public sample.

    `trip_distance < 5` is a tripwire chosen because plenty of NYC trips exceed
    5 miles, not a sensible quality rule. WARN keeps every row flowing while
    still recording per-expectation counts in the event log, which is what the
    hook and the backstop alert both consume.
    """
    return spark.readStream.table(SOURCE_TABLE).select(
        "tpep_pickup_datetime", "trip_distance", "fare_amount"
    )


def _event_details(event):
    """Return the event's details payload as a dict.

    Inside a hook the runtime hands `event["details"]` over as a native dict
    (the JSON-string form only appears when querying the persisted event log
    table). The string branch is kept as cheap defense in case a future runtime
    changes the delivery shape.
    """
    details = event.get("details") or {}
    if isinstance(details, str):
        details = json.loads(details)
    return details


def _sanitize(name):
    """Make a pipeline/dataset/expectation name safe as a file or folder name."""
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in str(name))


def _should_notify(pipeline, dataset, expectation, failed, passed, now):
    """Two-layer time-aware throttle. Returns True when a notification is due.

    Layer 1 (memory) covers repeats within one Python process: later
    microbatches of the same update, and a continuous pipeline's whole run.
    Layer 2 (marker files, only when STATE_DIR is set) covers repeats across
    updates and compute restarts. Both layers fail open: a state error must
    produce a notification, never silence.
    """
    if THROTTLE_SECONDS <= 0:
        return True
    key = (pipeline, dataset, expectation)
    last = _MEM_LAST.get(key)
    if last is not None and (now - last) < THROTTLE_SECONDS:
        return False
    marker = None
    if STATE_DIR:
        marker = (
            f"{STATE_DIR}/dq_notify_state/{_sanitize(pipeline)}/"
            f"{_sanitize(dataset)}__{_sanitize(expectation)}.json"
        )
        try:
            with open(marker) as f:
                prior = float((json.load(f) or {}).get("last_notified_epoch"))
            if (now - prior) < THROTTLE_SECONDS:
                _MEM_LAST[key] = prior
                return False
        except Exception:
            pass  # no marker or unreadable: fail open and notify
    _MEM_LAST[key] = now
    if marker:
        try:
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w") as f:
                json.dump(
                    {
                        "pipeline": pipeline,
                        "dataset": dataset,
                        "expectation": expectation,
                        "last_notified_at": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)
                        ),
                        "last_notified_epoch": now,
                        "last_failed_records": failed,
                        "last_passed_records": passed,
                        "throttle_seconds": THROTTLE_SECONDS,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"DQ_NOTIFY_MARKER_WRITE_FAILED: {type(e).__name__}: {e}")
    return True


def _payload(msg, pipeline, dataset, expectation, failed, passed):
    """Build the webhook payload for the configured channel format."""
    if CHANNEL_FORMAT == "teams":
        # MS Teams Workflows incoming webhook: Adaptive Card envelope
        # (documented format; not live-tested by this asset, see README).
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [{"type": "TextBlock", "text": msg, "wrap": True}],
                    },
                }
            ],
        }
    if CHANNEL_FORMAT == "generic":
        return {
            "text": msg,
            "pipeline": pipeline,
            "dataset": dataset,
            "expectation": expectation,
            "failed_records": failed,
            "passed_records": passed,
        }
    return {"text": msg}  # slack (default)


@dp.on_event_hook(max_allowable_consecutive_failures=None)
def notify_on_expectation_violation(event):
    """Notify, at most once per throttle window, when an expectation fails.

    Expectation counts arrive in `flow_progress` events under
    `details.flow_progress.data_quality.expectations`, one entry per
    expectation per flow, once per microbatch (so an unthrottled hook repeats
    per batch). The pipeline identity comes from the event's own `origin`
    (observed live: `origin.pipeline_name` and `origin.pipeline_id` are
    present in hook events), so this same code runs unchanged in any number of
    pipelines, each throttling in its own state folder.

    Hooks run serialized and the post-update grace budget is seconds: keep
    this fast (marker I/O ~100ms, webhook timeout 5s, no retries).
    `max_allowable_consecutive_failures=None` means the hook is never disabled
    by its own failures; `hook_progress` records ENABLED, FAILED, and DISABLED
    transitions (observed live), so a finite value here is event-log-visible
    but silently stops notifications until the next restart.
    """
    try:
        if event.get("event_type") != "flow_progress":
            return
        details = _event_details(event)
        data_quality = (details.get("flow_progress") or {}).get("data_quality") or {}
        failing = [
            e
            for e in (data_quality.get("expectations") or [])
            if (e.get("failed_records") or 0) > 0
        ]
        if not failing:
            return
        origin = event.get("origin") or {}
        pipeline = origin.get("pipeline_name") or origin.get("pipeline_id") or "unknown_pipeline"
        for exp in failing:
            now = time.time()
            dataset = exp.get("dataset")
            expectation = exp.get("name")
            failed = exp.get("failed_records") or 0
            passed = exp.get("passed_records") or 0
            if not _should_notify(pipeline, dataset, expectation, failed, passed, now):
                continue
            msg = (
                "EXPECTATION VIOLATION"
                f" | pipeline={pipeline}"
                f" | dataset={dataset}"
                f" | expectation={expectation}"
                f" | failed={failed}"
                f" | passed={passed}"
            )
            print(msg)
            if WEBHOOK_URL:
                try:
                    requests.post(
                        WEBHOOK_URL,
                        json=_payload(msg, pipeline, dataset, expectation, failed, passed),
                        timeout=5,
                    )
                except Exception as e:
                    print(f"WEBHOOK_DELIVERY_FAILED: {type(e).__name__}: {e}")
    except Exception as e:
        # A raising hook risks racking up FAILED states; notification code
        # must never take the hook down.
        print(f"DQ_NOTIFY_HOOK_UNEXPECTED: {type(e).__name__}: {e}")
