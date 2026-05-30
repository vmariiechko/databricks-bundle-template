"""Asset-specific tests for `assets/monitoring-sql-warehouse`.

Framework-level smoke checks (no .tmpl leftovers, schema validity, etc.)
live in `tests/assets/test_framework.py`. This file asserts behavior
unique to this asset: exact files installed at the chosen paths, YAML
parses and matches the proven serverless-PRO configuration, and the
custom `warehouse_resource_key` flows into both the filename and the
DABs resource key.
"""

from pathlib import Path

import pytest
import yaml

ASSET_NAME = "monitoring-sql-warehouse"
DEFAULT_CONFIG = "monitoring_sql_warehouse"
DEFAULT_TARGET_DIR = "resources"
DEFAULT_RESOURCE_KEY = "monitoring_sql_warehouse"
DEFAULT_WAREHOUSE_NAME = "Monitoring SQL Warehouse"
DEFAULT_CLUSTER_SIZE = "2X-Small"
DEFAULT_AUTO_STOP_MINS = 1
DOCS_PATH = "docs/monitoring-sql-warehouse/README.md"


def _resource_path(target_dir: str, resource_key: str) -> str:
    return f"{target_dir}/{resource_key}.sql_warehouse.yml"


@pytest.fixture(scope="module")
def installed(install_asset) -> Path:
    """Install the asset once per module using the default config."""
    return install_asset(ASSET_NAME, config=DEFAULT_CONFIG)


def test_installs_expected_files(installed: Path):
    expected_yaml = installed / _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY)
    expected_doc = installed / DOCS_PATH
    assert expected_yaml.is_file(), f"missing warehouse YAML: {expected_yaml}"
    assert expected_doc.is_file(), f"missing usage doc: {expected_doc}"


def test_no_extra_files_installed(installed: Path):
    """Asset should install exactly two files: the resource YAML and the usage doc."""
    installed_files = sorted(
        p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()
    )
    expected = sorted([
        _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY),
        DOCS_PATH,
    ])
    assert installed_files == expected, (
        f"unexpected files: {set(installed_files) - set(expected)}"
    )


def test_warehouse_yaml_parses(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "resources" in data, "top-level `resources:` key missing"
    assert "sql_warehouses" in data["resources"], "missing sql_warehouses block"
    assert DEFAULT_RESOURCE_KEY in data["resources"]["sql_warehouses"], (
        f"warehouse key {DEFAULT_RESOURCE_KEY!r} missing"
    )


def test_warehouse_matches_proven_config(installed: Path):
    """Assert the YAML matches the values Vadim verified against a live workspace."""
    yaml_path = installed / _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    wh = data["resources"]["sql_warehouses"][DEFAULT_RESOURCE_KEY]

    assert wh["name"] == DEFAULT_WAREHOUSE_NAME
    assert wh["cluster_size"] == DEFAULT_CLUSTER_SIZE
    assert wh["warehouse_type"] == "PRO"
    assert wh["enable_serverless_compute"] is True
    assert wh["auto_stop_mins"] == DEFAULT_AUTO_STOP_MINS
    assert isinstance(wh["auto_stop_mins"], int), (
        "auto_stop_mins must serialize as an integer; the field is integer-only"
    )
    assert wh["min_num_clusters"] == 1
    assert wh["max_num_clusters"] == 1


def test_warehouse_has_cost_attribution_tags(installed: Path):
    """The proven config tags the warehouse so cost reporting can attribute it.

    `workload=monitoring-alerts`     -> cost dashboards group by workload type.
    `created_by=dabs-asset/...`     -> traceability back to the originating asset.
    """
    yaml_path = installed / _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    wh = data["resources"]["sql_warehouses"][DEFAULT_RESOURCE_KEY]

    tags = wh.get("tags", {}).get("custom_tags", [])
    assert {"key": "workload", "value": "monitoring-alerts"} in tags, (
        f"missing workload tag in custom_tags: {tags}"
    )
    assert {"key": "created_by", "value": "dabs-asset/monitoring-sql-warehouse"} in tags, (
        f"missing created_by tag in custom_tags: {tags}"
    )


def test_warehouse_pins_stable_channel(installed: Path):
    """Channel is pinned to CHANNEL_NAME_CURRENT so Preview rollouts don't drift behavior."""
    yaml_path = installed / _resource_path(DEFAULT_TARGET_DIR, DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    wh = data["resources"]["sql_warehouses"][DEFAULT_RESOURCE_KEY]
    assert wh.get("channel", {}).get("name") == "CHANNEL_NAME_CURRENT", (
        f"channel.name should be CHANNEL_NAME_CURRENT, got: {wh.get('channel')}"
    )


def test_custom_resource_key_flows_into_filename_and_yaml(install_asset):
    """A user-supplied warehouse_resource_key must appear in both the
    filename and the DABs resource key inside the YAML."""
    custom_key = "alerts_warehouse_x"
    out = install_asset(
        ASSET_NAME,
        overrides={
            "target_dir": "resources",
            "warehouse_resource_key": custom_key,
            "warehouse_name": "Alerts Warehouse X",
            "cluster_size": "X-Small",
            "auto_stop_mins": "5",
        },
    )

    yaml_path = out / _resource_path("resources", custom_key)
    assert yaml_path.is_file(), f"missing renamed YAML: {yaml_path}"

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert custom_key in data["resources"]["sql_warehouses"], (
        f"resource key {custom_key!r} did not flow into YAML"
    )
    wh = data["resources"]["sql_warehouses"][custom_key]
    assert wh["name"] == "Alerts Warehouse X"
    assert wh["cluster_size"] == "X-Small"
    assert wh["auto_stop_mins"] == 5


def test_custom_target_dir_is_honored(install_asset):
    """A user-supplied target_dir must place the YAML under that subdirectory."""
    out = install_asset(
        ASSET_NAME,
        overrides={
            "target_dir": "resources/sql_warehouses",
            "warehouse_resource_key": DEFAULT_RESOURCE_KEY,
            "warehouse_name": DEFAULT_WAREHOUSE_NAME,
            "cluster_size": DEFAULT_CLUSTER_SIZE,
            "auto_stop_mins": "1",
        },
    )
    yaml_path = out / _resource_path("resources/sql_warehouses", DEFAULT_RESOURCE_KEY)
    assert yaml_path.is_file(), f"missing YAML at custom target_dir: {yaml_path}"


def test_auto_stop_zero_serializes_as_int(install_asset):
    """auto_stop_mins=0 (disable auto-stop) must render as the integer 0, not '0'."""
    out = install_asset(
        ASSET_NAME,
        overrides={
            "target_dir": "resources",
            "warehouse_resource_key": DEFAULT_RESOURCE_KEY,
            "warehouse_name": DEFAULT_WAREHOUSE_NAME,
            "cluster_size": DEFAULT_CLUSTER_SIZE,
            "auto_stop_mins": "0",
        },
    )
    yaml_path = out / _resource_path("resources", DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    wh = data["resources"]["sql_warehouses"][DEFAULT_RESOURCE_KEY]
    assert wh["auto_stop_mins"] == 0
    assert isinstance(wh["auto_stop_mins"], int)
