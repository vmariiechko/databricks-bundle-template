"""Asset-specific tests for `assets/sdp-quarantine-pattern`.

Framework-level smoke checks (no .tmpl leftovers, schema validity, etc.) live
in `tests/assets/test_framework.py`. This file asserts behavior unique to this
asset:

- the exact files install at the chosen paths;
- the pipeline source is a Databricks notebook and parses as Python;
- the pure helper `expectations.py` builds the correct inverse predicate and
  every drop predicate is NULL-safe (the partition invariant);
- the pipeline resource YAML is valid: medallion schema split, event-log block,
  cost/trace tags, and the notebook library pointing at the installed source;
- a custom `pipeline_resource_key` / `target_dir` flows into the filename, the
  DABs resource key, and the library path;
- the companion agent skill installs alongside the pipeline with well-formed
  `SKILL.md` frontmatter and honors a custom `skill_dir`;
- the shipped Tier 1 unit-test files install and are structurally sound.

The shipped unit tests themselves need PySpark + Java to execute and are run in
the user's bundle, not in this (pyspark-free) suite. Expectation firing,
quarantine routing, and the schema split are runtime properties verified live
on a workspace, not here.
"""

import ast
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ASSET_NAME = "sdp-quarantine-pattern"
DEFAULT_CONFIG = "sdp_quarantine_pattern"
DEFAULT_TARGET_DIR = "src/sdp_quarantine_pattern"
DEFAULT_RESOURCE_KEY = "sdp_quarantine_pattern"
DEFAULT_PIPELINE_NAME = "SDP Quarantine Pattern Demo"
DEFAULT_CATALOG = "main"
DEFAULT_BRONZE_SCHEMA = "bronze"
DEFAULT_SILVER_SCHEMA = "silver"
DEFAULT_SKILL_DIR = ".agents"
EVENT_LOG_TABLE = "quarantine_pipeline_event_log"

SKILL_BASE = f"{DEFAULT_SKILL_DIR}/skills/sdp-quarantine-pattern"
SKILL_FILES = (
    f"{SKILL_BASE}/SKILL.md",
    f"{SKILL_BASE}/references/adapt-the-pattern.md",
    f"{SKILL_BASE}/references/self-verify.md",
)

UNIT_TEST_FILES = (
    f"{DEFAULT_TARGET_DIR}/tests/conftest.py",
    f"{DEFAULT_TARGET_DIR}/tests/test_expectations.py",
    f"{DEFAULT_TARGET_DIR}/tests/requirements-test.txt",
)

EXPECTED_FILES = (
    f"{DEFAULT_TARGET_DIR}/quarantine_pipeline.py",
    f"{DEFAULT_TARGET_DIR}/expectations.py",
    f"{DEFAULT_TARGET_DIR}/expectations.json",
    f"{DEFAULT_TARGET_DIR}/event_log_queries.sql",
    f"resources/{DEFAULT_RESOURCE_KEY}.pipeline.yml",
    "docs/sdp-quarantine-pattern/README.md",
    *UNIT_TEST_FILES,
    *SKILL_FILES,
)


def _resource_path(resource_key: str) -> str:
    return f"resources/{resource_key}.pipeline.yml"


def _load_expectations_module(installed: Path, target_dir: str):
    """Import the installed (pure) expectations.py by file path."""
    script = installed / target_dir / "expectations.py"
    spec = importlib.util.spec_from_file_location("quarantine_expectations", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_pipeline_source_is_notebook_and_parses(installed: Path):
    """The source is a Databricks notebook (header present) and valid Python.

    It can't be imported offline (no pyspark.pipelines), so we parse it. The
    notebook markers (# Databricks notebook source, # COMMAND, # MAGIC) are all
    comments, so ast.parse succeeds.
    """
    src = (installed / DEFAULT_TARGET_DIR / "quarantine_pipeline.py").read_text(encoding="utf-8")
    assert src.lstrip().startswith("# Databricks notebook source"), (
        "pipeline source must start with the Databricks notebook header"
    )
    ast.parse(src)


def test_clean_and_quarantine_qualified_into_silver_schema(installed: Path):
    """Clean and quarantine outputs must be fully qualified into the silver
    schema (read from config), demonstrating medallion schema separation."""
    src = (installed / DEFAULT_TARGET_DIR / "quarantine_pipeline.py").read_text(encoding="utf-8")
    assert 'spark.conf.get("quarantine.silver_schema"' in src
    assert "CLEAN_TRIPS = f" in src and "clean_trips" in src
    assert "QUARANTINE_TRIPS = f" in src and "quarantine_trips" in src


def test_helper_builds_inverse_expression(installed: Path):
    mod = _load_expectations_module(installed, DEFAULT_TARGET_DIR)
    expr = mod.build_quarantine_expr({"a": "a IS NOT NULL AND a > 0", "b": "b IS NOT NULL"})
    assert expr == "NOT((a IS NOT NULL AND a > 0) AND (b IS NOT NULL))"


def test_helper_builds_clean_expression(installed: Path):
    mod = _load_expectations_module(installed, DEFAULT_TARGET_DIR)
    expr = mod.build_silver_expr({"a": "a IS NOT NULL AND a > 0", "b": "b IS NOT NULL"})
    assert expr == "(a IS NOT NULL AND a > 0) AND (b IS NOT NULL)"
    # quarantine is exactly the inverse of clean
    assert mod.build_quarantine_expr(mod.DROP_RULES) == f"NOT({mod.build_silver_expr(mod.DROP_RULES)})"


def test_helper_rejects_empty_rules(installed: Path):
    mod = _load_expectations_module(installed, DEFAULT_TARGET_DIR)
    with pytest.raises(ValueError):
        mod.build_quarantine_expr({})


def test_drop_and_warn_rules_load(installed: Path):
    mod = _load_expectations_module(installed, DEFAULT_TARGET_DIR)
    assert set(mod.DROP_RULES) == {
        "valid_fare",
        "valid_distance",
        "valid_pickup_ts",
        "valid_dropoff_after_pickup",
        "valid_pickup_zip",
    }
    assert "fare_within_expected" in mod.WARN_RULES


def test_every_drop_predicate_is_null_safe(installed: Path):
    """The partition invariant: each drop predicate must be total (NULL-safe).

    Every drop predicate must be guarded by an `IS NOT NULL` so it never
    evaluates to SQL NULL.
    """
    mod = _load_expectations_module(installed, DEFAULT_TARGET_DIR)
    for name, predicate in mod.DROP_RULES.items():
        assert re.search(r"IS NOT NULL", predicate, re.IGNORECASE), (
            f"drop rule {name!r} is not NULL-safe: {predicate!r}"
        )


def test_resource_yaml_is_valid_pipeline(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    assert pipe["name"] == DEFAULT_PIPELINE_NAME
    assert pipe["catalog"] == DEFAULT_CATALOG
    assert pipe["schema"] == DEFAULT_BRONZE_SCHEMA  # pipeline default = bronze
    assert pipe["serverless"] is True
    assert pipe["channel"] == "CURRENT"


def test_resource_publishes_event_log(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    event_log = pipe["event_log"]
    assert event_log["catalog"] == DEFAULT_CATALOG
    assert event_log["schema"] == DEFAULT_BRONZE_SCHEMA
    assert event_log["name"] == EVENT_LOG_TABLE


def test_resource_has_trace_tags(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    tags = pipe["tags"]
    assert tags["created_by"] == "dabs-asset"
    assert tags["asset"] == "sdp-quarantine-pattern"


def test_resource_library_points_at_installed_notebook(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    nb_paths = [lib["notebook"]["path"] for lib in pipe["libraries"] if "notebook" in lib]
    assert nb_paths == [f"../{DEFAULT_TARGET_DIR}/quarantine_pipeline.py"], (
        f"library path should point at the installed notebook via ../: {nb_paths}"
    )


def test_resource_passes_catalog_and_silver_schema_config(installed: Path):
    yaml_path = installed / _resource_path(DEFAULT_RESOURCE_KEY)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][DEFAULT_RESOURCE_KEY]
    config = pipe["configuration"]
    assert config["quarantine.catalog"] == DEFAULT_CATALOG
    assert config["quarantine.bronze_schema"] == DEFAULT_BRONZE_SCHEMA
    assert config["quarantine.silver_schema"] == DEFAULT_SILVER_SCHEMA
    # Source is parameterized so a test run can point it at a curated table.
    assert config["quarantine.source"] == "samples.nyctaxi.trips"


def test_all_three_tables_fully_qualified(installed: Path):
    """Raw, clean, and quarantine are all named with FQN constants, the raw
    table is read from config, and the source is parameterized (carry-in:
    consistent naming + dependency resolution + Tier 3 testability)."""
    src = (installed / DEFAULT_TARGET_DIR / "quarantine_pipeline.py").read_text(encoding="utf-8")
    assert 'spark.conf.get("quarantine.bronze_schema"' in src
    assert 'spark.conf.get("quarantine.source"' in src
    assert "RAW_TRIPS = f" in src and "raw_trips" in src
    # The raw table is registered and read by its FQN constant, not unqualified.
    assert "name=RAW_TRIPS," in src
    assert "spark.readStream.table(RAW_TRIPS)" in src
    assert 'spark.readStream.table("raw_trips")' not in src


def test_event_log_query_targets_published_table(installed: Path):
    """The parsing query must point at the published event log table FQN."""
    sql = (installed / DEFAULT_TARGET_DIR / "event_log_queries.sql").read_text(encoding="utf-8")
    assert f"{DEFAULT_CATALOG}.{DEFAULT_BRONZE_SCHEMA}.{EVENT_LOG_TABLE}" in sql
    assert "data_quality.expectations" in sql


def test_custom_resource_key_and_schemas_flow_through(install_asset):
    """A user-supplied resource key, target_dir, and schemas must flow into the
    filename, the DABs resource key, the library path, and the config."""
    custom_key = "trips_quarantine_x"
    custom_target = "pipelines/quarantine_demo"
    out = install_asset(
        ASSET_NAME,
        overrides={
            "target_dir": custom_target,
            "pipeline_resource_key": custom_key,
            "pipeline_name": "Trips Quarantine X",
            "catalog": "sandbox",
            "bronze_schema": "raw",
            "silver_schema": "clean",
        },
    )

    yaml_path = out / _resource_path(custom_key)
    assert yaml_path.is_file(), f"missing renamed resource YAML: {yaml_path}"
    assert (out / custom_target / "quarantine_pipeline.py").is_file()

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipe = data["resources"]["pipelines"][custom_key]
    assert pipe["name"] == "Trips Quarantine X"
    assert pipe["catalog"] == "sandbox"
    assert pipe["schema"] == "raw"
    assert pipe["event_log"]["schema"] == "raw"
    assert pipe["event_log"]["name"] == EVENT_LOG_TABLE
    assert pipe["configuration"]["quarantine.bronze_schema"] == "raw"
    assert pipe["configuration"]["quarantine.silver_schema"] == "clean"
    nb_paths = [lib["notebook"]["path"] for lib in pipe["libraries"] if "notebook" in lib]
    assert nb_paths == [f"../{custom_target}/quarantine_pipeline.py"]


# --- Companion agent skill --------------------------------------------------


def test_skill_files_install(installed: Path):
    for rel in SKILL_FILES:
        assert (installed / rel).is_file(), f"missing skill file: {rel}"


def test_skill_frontmatter_well_formed(installed: Path):
    """SKILL.md must open with YAML frontmatter declaring name and description."""
    skill = installed / SKILL_BASE / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md missing opening frontmatter delimiter"
    end = text.find("\n---", 4)
    assert end != -1, "SKILL.md missing closing frontmatter delimiter"
    front = yaml.safe_load(text[4:end])
    assert front["name"] == "sdp-quarantine-pattern"
    assert isinstance(front.get("description"), str) and front["description"].strip()


def test_skill_points_at_reference_pipeline(installed: Path):
    """The templated SKILL.md must reference the worked example at the chosen
    target_dir so the agent can find it."""
    skill = (installed / SKILL_BASE / "SKILL.md").read_text(encoding="utf-8")
    assert f"{DEFAULT_TARGET_DIR}/quarantine_pipeline.py" in skill
    # Read-only access stays runtime-neutral: no mandated tool in the skill body.
    assert "whatever read-only query capability" in skill


def test_custom_skill_dir(install_asset):
    """A user-provided skill_dir is honored for the skill install path."""
    out = install_asset(ASSET_NAME, overrides={"skill_dir": ".claude"})
    base = out / ".claude" / "skills" / "sdp-quarantine-pattern"
    assert (base / "SKILL.md").is_file()
    assert (base / "references" / "adapt-the-pattern.md").is_file()
    assert (base / "references" / "self-verify.md").is_file()


# --- Tier 1 unit-test scaffold ----------------------------------------------


def test_unit_test_files_install(installed: Path):
    for rel in UNIT_TEST_FILES:
        assert (installed / rel).is_file(), f"missing unit-test file: {rel}"


def test_unit_tests_are_structurally_sound(installed: Path):
    """The shipped tests parse, provide a `spark` fixture, and import the rules
    from the sibling pipeline module (so they exercise the real predicates)."""
    tests_dir = installed / DEFAULT_TARGET_DIR / "tests"
    conftest = (tests_dir / "conftest.py").read_text(encoding="utf-8")
    test_mod = (tests_dir / "test_expectations.py").read_text(encoding="utf-8")
    ast.parse(conftest)
    ast.parse(test_mod)
    assert "def spark(" in conftest, "conftest must define a `spark` fixture"
    assert "from expectations import" in test_mod
    # The routing test models expect_all_or_drop keep-on-NULL semantics.
    assert "IS NOT FALSE" in test_mod
