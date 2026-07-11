"""Lakeflow SDP pipeline demonstrating per-expectation notification via an event hook.

One streaming table carries a deliberately tight WARN expectation that fails on
the healthy public sample, so the hook has something to notify about on the
first run. The hook filters `flow_progress` events for expectation results with
failures and notifies via `print` (always) and an optional webhook.

The hook is the fast path only. Event hook delivery is best-effort: the
platform waits a fixed, non-configurable period before terminating pipeline
compute and does not guarantee every hook runs on every event. The companion
backstop alert (see the resource in `resources/`) sweeps the published event
log on a schedule as the guaranteed path.

Do not write Delta tables from inside a hook via `spark.sql()`. SDP restricts
`spark.sql()` in pipeline Python to a read-oriented command allowlist (DDL such
as CREATE TABLE fails with `UNSUPPORTED_SPARK_SQL_COMMAND`), and the patched
`spark.sql()` does not accept the parameterized-query `args=` kwarg. The
supported notification surface inside a hook is `print` and HTTP calls such as
`requests` (both used by the official event-hooks docs examples).
"""

import json

import requests
from pyspark import pipelines as dp
from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()

SOURCE_TABLE = spark.conf.get("dq_notify.source", "samples.nyctaxi.trips")
# Optional webhook for real delivery (Slack incoming webhook or similar).
# Empty string disables it and the hook only prints to the driver log.
# For authenticated endpoints, resolve tokens from a Databricks secret scope at
# module level (as the docs' Slack example does), not inside the hook body.
WEBHOOK_URL = spark.conf.get("dq_notify.webhook_url", "")


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


@dp.on_event_hook(max_allowable_consecutive_failures=None)
def notify_on_expectation_violation(event):
    """Notify the moment an expectation result with failures is logged.

    Expectation counts arrive in `flow_progress` events under
    `details.flow_progress.data_quality.expectations`, one entry per
    expectation per flow. Hooks run serialized (one at a time), so anything
    slow in here delays every other hook and widens the window in which
    queued events can be lost at compute termination: keep it fast.

    `max_allowable_consecutive_failures=None` means the hook is never disabled
    by its own failures; a finite value would silently disable it until the
    next pipeline restart. Either way, `hook_progress` events record only
    enable/disable state, not per-invocation execution, so the webhook failure
    branch below prints rather than raises.
    """
    if event.get("event_type") != "flow_progress":
        return
    details = _event_details(event)
    data_quality = (details.get("flow_progress") or {}).get("data_quality") or {}
    for exp in data_quality.get("expectations") or []:
        if (exp.get("failed_records") or 0) > 0:
            msg = (
                "EXPECTATION VIOLATION"
                f" | dataset={exp.get('dataset')}"
                f" | expectation={exp.get('name')}"
                f" | failed={exp.get('failed_records')}"
                f" | passed={exp.get('passed_records')}"
            )
            print(msg)
            if WEBHOOK_URL:
                try:
                    requests.post(WEBHOOK_URL, json={"text": msg}, timeout=10)
                except Exception as e:
                    print(f"WEBHOOK_DELIVERY_FAILED: {e}")
