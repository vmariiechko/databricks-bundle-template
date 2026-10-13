"""Asset-specific tests for `assets/sdp-expectation-notifications`.

Framework-level smoke checks (no .tmpl leftovers, schema validity, etc.) live
in `tests/assets/test_framework.py`. This file asserts behavior unique to this
asset:

- the exact files install at the chosen paths;
- the pipeline source parses as Python, defines the event hook on the
  supported notification surface, and contains no `spark.sql(` call anywhere
  (the anti-pattern the live run proved is rejected inside hooks);
- the pipeline resource YAML is valid: serverless, event-log publication, the
  file library pointing at the installed source, config keys, trace tags;
- the backstop alert YAML is valid: sweep query over the published event log
  with the documented from_json parsing shape and a past-time window,
  GREATER_THAN threshold 0, email subscription, unpaused daily schedule;
- custom prompt values flow into filenames, resource keys, paths, and the
  alert query;
- the companion agent skill installs with well-formed frontmatter and honors
  a custom skill_dir.

Hook firing, event-log publication, and alert delivery are runtime properties
verified live on a workspace, not here.
"""

import ast
import json
import os
import time
from pathlib import Path

import pytest
import yaml

ASSET_NAME = "sdp-expectation-notifications"
DEFAULT_CONFIG = "sdp_expectation_notifications"
DEFAULT_TARGET_DIR = "src/sdp_expectation_notifications"
DEFAULT_RESOURCE_KEY = "sdp_expectation_notifications"
DEFAULT_ALERT_KEY = f"{DEFAULT_RESOURCE_KEY}_backstop"
DEFAULT_PIPELINE_NAME = "SDP Expectation Notifications Demo"
DEFAULT_CATALOG = "main"
DEFAULT_SCHEMA = "dq_notifications"
DEFAULT_SKILL_DIR = ".agents"
EVENT_LOG_TABLE = "dq_notifications_event_log"
PIPELINE_SOURCE = "expectation_notifications_pipeline.py"

SKILL_BASE = f"{DEFAULT_SKILL_DIR}/skills/sdp-expectation-notifications"
SKILL_FILES = (
    f"{SKILL_BASE}/SKILL.md",
    f"{SKILL_BASE}/references/adapt-the-pattern.md",
    f"{SKILL_BASE}/references/self-verify.md",
)

EXPECTED_FILES = (
    f"{DEFAULT_TARGET_DIR}/{PIPELINE_SOURCE}",
    f"{DEFAULT_TARGET_DIR}/event_log_queries.sql",
    f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml",
    f"resources/{DEFAULT_ALERT_KEY}.alert.yml",
    "docs/sdp-expectation-notifications/README.md",
    *SKILL_FILES,
)


def _load_yaml(installed: Path, rel: str) -> dict:
    return yaml.safe_load((installed / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def installed(install_asset) -> Path:
    """Install the asset once per module using the default config."""
    return install_asset(ASSET_NAME, config=DEFAULT_CONFIG)


def test_installs_expected_files(installed: Path):
    for rel in EXPECTED_FILES:
        assert (installed / rel).is_file(), f"missing expected file: {rel}"


def test_no_extra_files_installed(installed: Path):
    installed_files = sorted(
        p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()
    )
    assert installed_files == sorted(EXPECTED_FILES), (
        f"unexpected files: {set(installed_files) - set(EXPECTED_FILES)}"
    )


# --- Pipeline source ----------------------------------------------------------


def test_pipeline_source_parses(installed: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    ast.parse(src)


def test_hook_defined_and_filters_flow_progress(installed: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    assert "@dp.on_event_hook(max_allowable_consecutive_failures=None)" in src
    assert "def notify_on_expectation_violation(event):" in src
    assert '"flow_progress"' in src
    assert "failed_records" in src


def test_hook_stays_on_supported_surface(installed: Path):
    """The live run proved spark.sql() writes are rejected inside hooks. The
    shipped source must not make a single .sql(...) call (docstrings may
    mention it as the documented anti-pattern); notification goes through
    print and requests only."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    sql_calls = [
        node
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sql"
    ]
    assert not sql_calls, f".sql() calls found at lines: {[c.lineno for c in sql_calls]}"
    assert "print(" in src
    assert "requests.post(" in src


def test_webhook_is_optional_and_guarded(installed: Path):
    """The webhook is off by default (no secret scope, empty URL) and its
    failure is caught and printed, so a broken endpoint never counts as a
    hook failure. There is no plain-config URL: the secret scope is the only
    source."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    assert "dq_notify.webhook_url" not in src
    assert 'WEBHOOK_URL = ""' in src
    assert "if WEBHOOK_URL:" in src
    assert "WEBHOOK_DELIVERY_FAILED" in src
    assert "timeout=5" in src


def test_webhook_secret_resolution_is_guarded(installed: Path):
    """Secret-scope resolution goes through dbutils.secrets.get (config
    interpolation of {{secrets/...}} does not resolve in SDP pipeline
    configuration, observed live) and a missing scope degrades to print-only
    instead of failing the pipeline."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    assert 'spark.conf.get("dq_notify.webhook_secret_scope", "")' in src
    assert "dbutils.secrets.get(WEBHOOK_SECRET_SCOPE, WEBHOOK_SECRET_KEY)" in src
    assert "DQ_NOTIFY_SECRET_UNAVAILABLE" in src


def test_no_installed_file_mentions_plain_webhook_url(installed: Path):
    """The removed plain-config key must not survive anywhere in the install:
    code, resource YAML, docs, or the companion skill."""
    offenders = [
        p.relative_to(installed).as_posix()
        for p in installed.rglob("*")
        if p.is_file() and "dq_notify.webhook_url" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"dq_notify.webhook_url still mentioned in: {offenders}"


class _Conf:
    def __init__(self, values: dict):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _Spark:
    def __init__(self, values: dict):
        self.conf = _Conf(values)


class _SecretsUnavailableError(Exception):
    """Stand-in for the platform's exception on an unreadable scope."""


class _Dbutils:
    def __init__(self, url=None, error=None):
        self.calls = []
        self._url = url
        self._error = error
        self.secrets = self

    def get(self, scope, key):
        self.calls.append((scope, key))
        if self._error is not None:
            raise self._error
        return self._url


def _resolve_webhook(src: str, conf: dict, dbutils: _Dbutils) -> tuple[dict, list[str]]:
    """Exec only the module-level webhook resolution (the WEBHOOK_* assignments
    and the `if WEBHOOK_SECRET_SCOPE:` block) against stubbed spark/dbutils."""
    tree = ast.parse(src)

    def is_webhook_node(node):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            return any(name.startswith("WEBHOOK_") for name in names)
        return (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "WEBHOOK_SECRET_SCOPE"
        )

    subset = ast.Module(body=[n for n in tree.body if is_webhook_node(n)], type_ignores=[])
    printed: list[str] = []
    ns = {
        "spark": _Spark(conf),
        "dbutils": dbutils,
        "print": lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
    }
    exec(compile(subset, "<webhook>", "exec"), ns)  # noqa: S102 (test-only)
    return ns, printed


def test_secret_resolution_fail_open(installed: Path):
    """No scope: print-only and dbutils untouched. Scope readable: URL
    resolved. Scope unreadable: the exact DQ_NOTIFY_SECRET_UNAVAILABLE line,
    then print-only (fail-open, the pipeline is never blocked)."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")

    no_scope = _Dbutils(url="https://hooks.example/never")
    ns, printed = _resolve_webhook(src, {}, no_scope)
    assert ns["WEBHOOK_URL"] == ""
    assert no_scope.calls == [] and printed == []

    ok = _Dbutils(url="https://hooks.example/secret")
    ns, printed = _resolve_webhook(src, {"dq_notify.webhook_secret_scope": "dq-notifications"}, ok)
    assert ns["WEBHOOK_URL"] == "https://hooks.example/secret"
    assert ok.calls == [("dq-notifications", "slack_webhook_url")] and printed == []

    broken = _Dbutils(error=_SecretsUnavailableError("no such scope"))
    ns, printed = _resolve_webhook(
        src,
        {"dq_notify.webhook_secret_scope": "missing-scope", "dq_notify.webhook_secret_key": "k"},
        broken,
    )
    assert ns["WEBHOOK_URL"] == ""
    assert printed == [
        "DQ_NOTIFY_SECRET_UNAVAILABLE: scope=missing-scope key=k (_SecretsUnavailableError); "
        "webhook disabled, print-only."
    ]


def _throttle_ns(src: str, state_dir: str, throttle_seconds: int) -> dict:
    """Exec only the pure throttle helpers from the installed source with
    stubbed module globals, so the decision logic is testable offline."""
    tree = ast.parse(src)
    wanted = {"_sanitize", "_state_scope", "_should_notify"}
    subset = ast.Module(
        body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted],
        type_ignores=[],
    )
    ns = {
        "os": os,
        "json": json,
        "time": time,
        "THROTTLE_SECONDS": throttle_seconds,
        "STATE_DIR": state_dir,
        "_MEM_LAST": {},
        "print": lambda *a, **k: None,
    }
    exec(compile(subset, "<throttle>", "exec"), ns)  # noqa: S102 (test-only)
    return ns


PIPE_ID = "0f1e2d3c-aaaa-bbbb-cccc-000000000001"
OTHER_PIPE_ID = "0f1e2d3c-aaaa-bbbb-cccc-000000000002"
MARKER_FIELDS = {
    "pipeline",
    "pipeline_id",
    "dataset",
    "expectation",
    "last_notified_at",
    "last_notified_epoch",
    "last_failed_records",
    "last_passed_records",
    "throttle_seconds",
}


def test_throttle_suppresses_within_window_in_memory(installed: Path, tmp_path: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    ns = _throttle_ns(src, str(tmp_path), 3600)
    notify = ns["_should_notify"]
    t0 = 1_000_000.0
    assert notify("pipe", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0) is True
    assert notify("pipe", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 10) is False
    assert notify("pipe", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 3601) is True


def test_throttle_is_durable_across_processes_and_scoped_per_pipeline(
    installed: Path, tmp_path: Path
):
    """A fresh namespace simulates the fresh Python process each update gets in
    non-development mode (observed live): the marker file must carry the
    suppression across, and a different pipeline scope must not be suppressed."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    t0 = 1_000_000.0
    first = _throttle_ns(src, str(tmp_path), 3600)["_should_notify"]
    assert first("pipe_a", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0) is True
    fresh = _throttle_ns(src, str(tmp_path), 3600)["_should_notify"]  # same state dir
    assert fresh("pipe_a", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 10) is False
    assert fresh("pipe_b", OTHER_PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 10) is True


def test_same_name_different_ids_never_share_state(installed: Path, tmp_path: Path):
    """Two pipelines with one display name, one dataset, and one expectation
    (for example a pipeline deleted and recreated under the same name) must
    each notify, keep separate marker folders, and throttle independently."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    t0 = 1_000_000.0
    notify = _throttle_ns(src, str(tmp_path), 3600)["_should_notify"]
    assert notify("Same Name", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0) is True
    assert notify("Same Name", OTHER_PIPE_ID, "cat.sch.tbl", "rule", 6, 94, t0 + 5) is True, (
        "same display name with a different id must not be suppressed"
    )
    folders = sorted(p.name for p in (tmp_path / "dq_notify_state").iterdir())
    assert folders == [f"Same_Name__{PIPE_ID}", f"Same_Name__{OTHER_PIPE_ID}"]
    fresh = _throttle_ns(src, str(tmp_path), 3600)["_should_notify"]  # markers decide
    assert fresh("Same Name", PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 60) is False
    assert fresh("Same Name", OTHER_PIPE_ID, "cat.sch.tbl", "rule", 5, 95, t0 + 60) is False


def test_state_scope_fallbacks(installed: Path):
    """Name plus id when both exist; the hook's display fallback chain
    (name, else id, else unknown_pipeline) decides the folder otherwise."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    scope = _throttle_ns(src, "", 3600)["_state_scope"]
    assert scope("My Pipeline", PIPE_ID) == f"My_Pipeline__{PIPE_ID}"
    assert scope("My Pipeline", None) == "My_Pipeline"  # no id: the pre-1.13 layout
    assert scope(PIPE_ID, PIPE_ID) == PIPE_ID  # no name: display already fell back to id
    assert scope("unknown_pipeline", None) == "unknown_pipeline"


def test_throttle_marker_is_human_readable_and_overwritten(installed: Path, tmp_path: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    notify = _throttle_ns(src, str(tmp_path), 3600)["_should_notify"]
    t0 = 1_000_000.0
    notify("My Pipeline", PIPE_ID, "cat.sch.tbl", "rule", 7, 93, t0)
    marker_dir = tmp_path / "dq_notify_state" / f"My_Pipeline__{PIPE_ID}"
    markers = list(marker_dir.glob("*.json"))
    assert [m.name for m in markers] == ["cat.sch.tbl__rule.json"]
    body = json.loads(markers[0].read_text(encoding="utf-8"))
    assert set(body) == MARKER_FIELDS, "marker keeps every pre-1.13 field and adds pipeline_id"
    assert body["pipeline"] == "My Pipeline"
    assert body["pipeline_id"] == PIPE_ID
    assert body["last_failed_records"] == 7
    assert body["last_notified_epoch"] == t0
    assert body["throttle_seconds"] == 3600
    notify("My Pipeline", PIPE_ID, "cat.sch.tbl", "rule", 9, 91, t0 + 4000)
    assert len(list(marker_dir.glob("*.json"))) == 1, "marker must be overwritten, not accumulated"
    assert json.loads(markers[0].read_text(encoding="utf-8"))["last_failed_records"] == 9


def test_throttle_zero_disables_and_empty_state_dir_stays_in_memory(
    installed: Path, tmp_path: Path
):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    unthrottled = _throttle_ns(src, str(tmp_path), 0)["_should_notify"]
    t0 = 1_000_000.0
    assert unthrottled("p", PIPE_ID, "d", "r", 1, 1, t0) is True
    assert unthrottled("p", PIPE_ID, "d", "r", 1, 1, t0 + 1) is True
    in_memory = _throttle_ns(src, "", 3600)["_should_notify"]
    assert in_memory("p", PIPE_ID, "d", "r", 1, 1, t0) is True
    assert in_memory("p", PIPE_ID, "d", "r", 1, 1, t0 + 10) is False
    assert not list(tmp_path.rglob("*.json")), "empty state dir must write no markers"


class _HookStubDp:
    @staticmethod
    def on_event_hook(**_kwargs):
        return lambda fn: fn


class _RecordingRequests:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout})


def _hook_ns(src: str, state_dir: str, webhook_url: str, channel_format: str) -> dict:
    """Exec the hook and every helper it calls, with stubbed module globals."""
    tree = ast.parse(src)
    wanted = {
        "_event_details",
        "_sanitize",
        "_state_scope",
        "_should_notify",
        "_payload",
        "notify_on_expectation_violation",
    }
    subset = ast.Module(
        body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted],
        type_ignores=[],
    )
    printed: list[str] = []
    ns = {
        "os": os,
        "json": json,
        "time": time,
        "dp": _HookStubDp,
        "requests": _RecordingRequests(),
        "THROTTLE_SECONDS": 3600,
        "STATE_DIR": state_dir,
        "CHANNEL_FORMAT": channel_format,
        "WEBHOOK_URL": webhook_url,
        "_MEM_LAST": {},
        "print": lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        "_printed": printed,
    }
    exec(compile(subset, "<hook>", "exec"), ns)  # noqa: S102 (test-only)
    return ns


def _flow_progress_event(origin: dict) -> dict:
    expectation = {
        "name": "demo_short_trip",
        "dataset": "main.dq.monitored_trips",
        "passed_records": 18929,
        "failed_records": 3003,
    }
    return {
        "event_type": "flow_progress",
        "origin": origin,
        "details": {"flow_progress": {"data_quality": {"expectations": [expectation]}}},
    }


def test_hook_message_and_generic_payload_unchanged(installed: Path, tmp_path: Path):
    """The id scopes state only: the printed line and the `generic` payload
    carry the display name and exactly the pre-1.13 shape, byte for byte."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    ns = _hook_ns(src, str(tmp_path), "https://hooks.example/x", "generic")
    event = _flow_progress_event({"pipeline_name": "My Pipeline", "pipeline_id": PIPE_ID})
    ns["notify_on_expectation_violation"](event)
    expected_line = (
        "EXPECTATION VIOLATION | pipeline=My Pipeline | dataset=main.dq.monitored_trips"
        " | expectation=demo_short_trip | failed=3003 | passed=18929"
    )
    assert ns["_printed"] == [expected_line]
    assert ns["requests"].posts == [
        {
            "url": "https://hooks.example/x",
            "json": {
                "text": expected_line,
                "pipeline": "My Pipeline",
                "dataset": "main.dq.monitored_trips",
                "expectation": "demo_short_trip",
                "failed_records": 3003,
                "passed_records": 18929,
            },
            "timeout": 5,
        }
    ]
    marker_dir = tmp_path / "dq_notify_state" / f"My_Pipeline__{PIPE_ID}"
    assert (marker_dir / "main.dq.monitored_trips__demo_short_trip.json").is_file()
    # A second event in the same process is throttled: nothing printed or posted.
    ns["notify_on_expectation_violation"](event)
    assert len(ns["_printed"]) == 1 and len(ns["requests"].posts) == 1


def test_hook_without_name_shows_id_and_without_both_stays_safe(installed: Path, tmp_path: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    ns = _hook_ns(src, str(tmp_path), "", "slack")
    ns["notify_on_expectation_violation"](_flow_progress_event({"pipeline_id": PIPE_ID}))
    ns["notify_on_expectation_violation"](_flow_progress_event({}))
    assert [line.split(" | ")[1] for line in ns["_printed"]] == [
        f"pipeline={PIPE_ID}",
        "pipeline=unknown_pipeline",
    ]
    folders = sorted(p.name for p in (tmp_path / "dq_notify_state").iterdir())
    assert folders == [PIPE_ID, "unknown_pipeline"]
    assert ns["requests"].posts == [], "no secret scope means print-only"


def test_payload_formats_cover_all_channels(installed: Path):
    """One payload function, three formats; Teams is the documented Adaptive
    Card envelope (doc-confirmed, not live-tested; the README says so)."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    tree = ast.parse(src)
    payload_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_payload"]
    assert payload_defs, "_payload function missing"
    assert '"teams"' in src and '"generic"' in src
    assert "application/vnd.microsoft.card.adaptive" in src


def test_demo_expectation_is_warn_tripwire(installed: Path):
    """The demo rule must be a WARN expectation (plain @dp.expect, no drop or
    fail variant) so rows keep flowing while counts land in the event log."""
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    assert '@dp.expect("demo_short_trip", "trip_distance < 5")' in src
    assert "expect_or_drop" not in src
    assert "expect_or_fail" not in src


def test_source_is_parameterized(installed: Path):
    src = (installed / DEFAULT_TARGET_DIR / PIPELINE_SOURCE).read_text(encoding="utf-8")
    assert 'spark.conf.get("dq_notify.source", "samples.nyctaxi.trips")' in src
    assert "spark.readStream.table(SOURCE_TABLE)" in src


# --- Pipeline resource --------------------------------------------------------


def test_resource_yaml_is_valid_pipeline(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml")
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    assert pipe["name"] == DEFAULT_PIPELINE_NAME
    assert pipe["catalog"] == DEFAULT_CATALOG
    assert pipe["schema"] == DEFAULT_SCHEMA
    assert pipe["serverless"] is True
    assert pipe["channel"] == "CURRENT"


def test_resource_publishes_event_log(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml")
    event_log = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]["event_log"]
    assert event_log["catalog"] == DEFAULT_CATALOG
    assert event_log["schema"] == DEFAULT_SCHEMA
    assert event_log["name"] == EVENT_LOG_TABLE


def test_resource_library_points_at_installed_source(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml")
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    file_paths = [lib["file"]["path"] for lib in pipe["libraries"] if "file" in lib]
    assert file_paths == [f"../{DEFAULT_TARGET_DIR}/{PIPELINE_SOURCE}"]


def test_resource_config_and_tags(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml")
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    config = pipe["configuration"]
    assert config["dq_notify.source"] == "samples.nyctaxi.trips"
    assert config["dq_notify.throttle_seconds"] == "3600"
    # The placeholder volume path must template to an empty state_dir
    # (in-memory throttle only), never leak the placeholder into the config.
    assert config["dq_notify.state_dir"] == ""
    assert config["dq_notify.channel_format"] == "slack"
    assert config["dq_notify.webhook_secret_scope"] == ""
    assert config["dq_notify.webhook_secret_key"] == "slack_webhook_url"
    # The secret scope is the only webhook source; the plain-config key is gone.
    assert "dq_notify.webhook_url" not in config
    assert pipe["tags"]["created_by"] == "dabs-asset"
    assert pipe["tags"]["asset"] == "sdp-expectation-notifications"


# --- Backstop alert resource ----------------------------------------------------


def test_alert_yaml_is_valid(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_ALERT_KEY}.alert.yml")
    alert = data["resources"]["alerts"][DEFAULT_ALERT_KEY]
    assert alert["display_name"] == f"{DEFAULT_PIPELINE_NAME} Backstop"
    assert alert["warehouse_id"] == "WAREHOUSE_ID_PLACEHOLDER"


def test_alert_query_sweeps_published_event_log(installed: Path):
    """The sweep must aggregate over a past-time window (not latest-row) from
    the published event log, using the documented from_json parsing shape."""
    data = _load_yaml(installed, f"resources/{DEFAULT_ALERT_KEY}.alert.yml")
    query = data["resources"]["alerts"][DEFAULT_ALERT_KEY]["query_text"]
    assert f"{DEFAULT_CATALOG}.{DEFAULT_SCHEMA}.{EVENT_LOG_TABLE}" in query
    assert "details:flow_progress.data_quality.expectations" in query
    assert "event_type = 'flow_progress'" in query
    assert "INTERVAL 1 DAY" in query
    assert "SUM(CAST(exp.failed_records AS BIGINT))" in query


def test_alert_evaluation_and_schedule(installed: Path):
    data = _load_yaml(installed, f"resources/{DEFAULT_ALERT_KEY}.alert.yml")
    alert = data["resources"]["alerts"][DEFAULT_ALERT_KEY]
    evaluation = alert["evaluation"]
    assert evaluation["comparison_operator"] == "GREATER_THAN"
    assert evaluation["source"]["name"] == "failed_records"
    assert evaluation["threshold"]["value"]["double_value"] == 0
    # notify_on_ok true is the v1.12 default: exactly one recovery email on
    # TRIGGERED -> OK (observed live), closing the loop after the masking
    # window of state-change-only notification.
    assert evaluation["notification"]["notify_on_ok"] is True
    assert "retrigger_seconds" not in evaluation["notification"], (
        "retrigger_seconds must ship commented out, not active"
    )
    assert evaluation["notification"]["subscriptions"] == [{"user_email": "EMAIL_PLACEHOLDER"}]
    schedule = alert["schedule"]
    assert schedule["pause_status"] == "UNPAUSED"
    assert schedule["quartz_cron_schedule"] == "0 0 6 * * ?"
    assert schedule["timezone_id"] == "UTC"


# --- Event-log queries ----------------------------------------------------------


def test_event_log_queries_target_published_table(installed: Path):
    sql = (installed / DEFAULT_TARGET_DIR / "event_log_queries.sql").read_text(encoding="utf-8")
    assert f"{DEFAULT_CATALOG}.{DEFAULT_SCHEMA}.{EVENT_LOG_TABLE}" in sql
    assert "data_quality.expectations" in sql
    assert "hook_progress" in sql


# --- Custom prompt values ---------------------------------------------------------


def test_custom_values_flow_through(install_asset):
    """User-supplied resource key, target_dir, catalog/schema, warehouse, and
    email must flow into filenames, resource keys, paths, and the alert."""
    out = install_asset(
        ASSET_NAME,
        overrides={
            "target_dir": "pipelines/dq_notify_demo",
            "pipeline_resource_key": "trips_dq_notify",
            "pipeline_name": "Trips DQ Notify",
            "catalog": "sandbox",
            "schema": "observability",
            "warehouse_id": "abc123def456",
            "notification_email": "someone@example.com",
            "state_volume_path": "/Volumes/sandbox/observability/state_vol",
        },
    )

    pipe_yaml = out / "resources/trips_dq_notify.pipeline.yml"
    alert_yaml = out / "resources/trips_dq_notify_backstop.alert.yml"
    assert pipe_yaml.is_file()
    assert alert_yaml.is_file()
    assert (out / "pipelines/dq_notify_demo" / PIPELINE_SOURCE).is_file()

    pipe = yaml.safe_load(pipe_yaml.read_text(encoding="utf-8"))["resources"]["pipelines"][
        "trips_dq_notify"
    ]
    assert pipe["name"] == "Trips DQ Notify"
    assert pipe["catalog"] == "sandbox"
    assert pipe["schema"] == "observability"
    assert pipe["event_log"]["schema"] == "observability"
    assert pipe["configuration"]["dq_notify.state_dir"] == "/Volumes/sandbox/observability/state_vol"
    file_paths = [lib["file"]["path"] for lib in pipe["libraries"] if "file" in lib]
    assert file_paths == [f"../pipelines/dq_notify_demo/{PIPELINE_SOURCE}"]

    alert = yaml.safe_load(alert_yaml.read_text(encoding="utf-8"))["resources"]["alerts"][
        "trips_dq_notify_backstop"
    ]
    assert alert["display_name"] == "Trips DQ Notify Backstop"
    assert alert["warehouse_id"] == "abc123def456"
    assert f"sandbox.observability.{EVENT_LOG_TABLE}" in alert["query_text"]
    subs = alert["evaluation"]["notification"]["subscriptions"]
    assert subs == [{"user_email": "someone@example.com"}]


# --- Companion agent skill -----------------------------------------------------


def test_skill_files_install(installed: Path):
    for rel in SKILL_FILES:
        assert (installed / rel).is_file(), f"missing skill file: {rel}"


def test_skill_frontmatter_well_formed(installed: Path):
    """SKILL.md must open with YAML frontmatter declaring name and description."""
    text = (installed / SKILL_BASE / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md missing opening frontmatter delimiter"
    end = text.find("\n---", 4)
    assert end != -1, "SKILL.md missing closing frontmatter delimiter"
    front = yaml.safe_load(text[4:end])
    assert front["name"] == "sdp-expectation-notifications"
    assert isinstance(front.get("description"), str) and front["description"].strip()


def test_skill_points_at_reference_and_states_the_rules(installed: Path):
    """The templated SKILL.md must reference the worked example at the chosen
    target_dir and carry the two non-negotiable rules."""
    skill = (installed / SKILL_BASE / "SKILL.md").read_text(encoding="utf-8")
    assert f"{DEFAULT_TARGET_DIR}/{PIPELINE_SOURCE}" in skill
    assert "never the only notification path" in skill
    assert "Never write Delta from inside a hook" in skill
    # Read-only access stays runtime-neutral: no mandated tool in the skill body.
    assert "whatever read-only query capability" in skill


def test_custom_skill_dir(install_asset):
    """A user-provided skill_dir is honored for the skill install path."""
    out = install_asset(ASSET_NAME, overrides={"skill_dir": ".claude"})
    base = out / ".claude" / "skills" / "sdp-expectation-notifications"
    assert (base / "SKILL.md").is_file()
    assert (base / "references" / "adapt-the-pattern.md").is_file()
    assert (base / "references" / "self-verify.md").is_file()
