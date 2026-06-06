"""Unit tests for the quarantine-pattern expectation rules.

Two layers, both offline (no Databricks workspace):

1. `TestExpectationsConfig` (pure Python): the rule config is well formed, every
   drop predicate is NULL-safe, and the derived quarantine predicate is the
   inverse of the clean predicate.

2. `TestQuarantineRouting` (real local Spark): feed crafted edge rows through the
   same drop predicates the pipeline uses and assert the partition invariant
   (clean + quarantine == raw, disjoint) and that a NULL in a guarded column
   routes to quarantine only. This is the offline proof of the NULL trap fix.

The pipeline drops rows with `@dp.expect_all_or_drop`, which keeps a row unless a
predicate evaluates to `false` (a `NULL` predicate is treated as passing). The
SDP pipelines runtime is not importable offline, so these tests reproduce that
keep-on-NULL semantics with `<predicate> IS NOT FALSE`. For NULL-safe predicates
this is identical to the pipeline; for a predicate that is NOT NULL-safe it
exposes the leak as a broken partition, which is exactly what we want to catch.
"""

import json
from pathlib import Path

import pytest
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from expectations import (
    DROP_RULES,
    WARN_RULES,
    build_quarantine_expr,
    build_silver_expr,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "expectations.json"


@pytest.fixture(scope="module")
def config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class TestExpectationsConfig:
    """Pure-Python validation of the rule config and derived predicates."""

    def test_has_drop_and_warn_lists(self, config):
        assert config["drop"], "drop rules must not be empty"
        assert "warn" in config

    def test_each_rule_has_name_and_query(self, config):
        for action in ("drop", "warn"):
            for rule in config.get(action, []):
                assert "name" in rule and "query" in rule, f"malformed {action} rule: {rule}"

    def test_every_drop_predicate_is_null_safe(self):
        """The partition invariant depends on every drop predicate being total."""
        for name, predicate in DROP_RULES.items():
            assert "IS NOT NULL" in predicate.upper(), (
                f"drop rule {name!r} is not NULL-safe: {predicate!r}"
            )

    def test_quarantine_is_inverse_of_clean(self):
        assert build_quarantine_expr(DROP_RULES) == f"NOT({build_silver_expr(DROP_RULES)})"

    def test_helper_rejects_empty_rules(self):
        with pytest.raises(ValueError):
            build_quarantine_expr({})


# --- Routing semantics (real local Spark) -----------------------------------

# A row is kept unless a predicate is false; a NULL predicate passes. This
# mirrors @dp.expect_all_or_drop without the SDP runtime.
CLEAN_KEEP_EXPR = f"({build_silver_expr(DROP_RULES)}) IS NOT FALSE"
QUARANTINE_KEEP_EXPR = f"({build_quarantine_expr(DROP_RULES)}) IS NOT FALSE"

_SCHEMA = StructType(
    [
        StructField("tag", StringType(), True),
        StructField("expected", StringType(), True),
        StructField("tpep_pickup_datetime", TimestampType(), True),
        StructField("tpep_dropoff_datetime", TimestampType(), True),
        StructField("trip_distance", DoubleType(), True),
        StructField("fare_amount", DoubleType(), True),
        StructField("pickup_zip", IntegerType(), True),
        StructField("dropoff_zip", IntegerType(), True),
    ]
)


def _ts(text):
    from datetime import datetime

    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


# tag, expected, pickup, dropoff, distance, fare, pickup_zip, dropoff_zip
_EDGE_ROWS = [
    ("valid", "clean", _ts("2016-02-14 10:00:00"), _ts("2016-02-14 10:20:00"), 3.5, 14.0, 10001, 10002),
    ("warn_only", "clean", _ts("2016-02-14 12:00:00"), _ts("2016-02-14 12:40:00"), 8.0, 999.0, 10001, 10002),
    ("neg_fare", "quarantine", _ts("2016-02-14 10:00:00"), _ts("2016-02-14 10:20:00"), 3.5, -14.0, 10001, 10002),
    ("zero_distance", "quarantine", _ts("2016-02-14 10:00:00"), _ts("2016-02-14 10:20:00"), 0.0, 14.0, 10001, 10002),
    ("dropoff_before_pickup", "quarantine", _ts("2016-02-14 11:00:00"), _ts("2016-02-14 10:30:00"), 3.5, 14.0, 10001, 10002),
    ("multi_violation", "quarantine", _ts("2016-02-14 11:00:00"), _ts("2016-02-14 10:30:00"), 0.0, -5.0, 10001, 10002),
    ("null_fare", "quarantine", _ts("2016-02-14 13:00:00"), _ts("2016-02-14 13:25:00"), 4.0, None, 10001, 10002),
    ("null_pickup_ts", "quarantine", None, _ts("2016-02-14 13:25:00"), 4.0, 14.0, 10001, 10002),
    ("null_pickup_zip", "quarantine", _ts("2016-02-14 13:00:00"), _ts("2016-02-14 13:25:00"), 4.0, 14.0, None, 10002),
]


class TestQuarantineRouting:
    """The clean/quarantine split is a clean partition under SDP keep-on-NULL."""

    @pytest.fixture(scope="class")
    def routed(self, spark):
        df = spark.createDataFrame(_EDGE_ROWS, _SCHEMA)
        clean = df.filter(CLEAN_KEEP_EXPR)
        quarantine = df.filter(QUARANTINE_KEEP_EXPR)
        clean_tags = {r["tag"] for r in clean.select("tag").collect()}
        quarantine_tags = {r["tag"] for r in quarantine.select("tag").collect()}
        return df, clean, quarantine, clean_tags, quarantine_tags

    def test_partition_invariant(self, routed):
        df, clean, quarantine, _, _ = routed
        assert clean.count() + quarantine.count() == df.count()

    def test_clean_and_quarantine_disjoint(self, routed):
        _, _, _, clean_tags, quarantine_tags = routed
        assert clean_tags.isdisjoint(quarantine_tags)

    def test_each_row_routes_as_expected(self, routed):
        df, _, _, clean_tags, quarantine_tags = routed
        for row in df.collect():
            bucket = clean_tags if row["expected"] == "clean" else quarantine_tags
            assert row["tag"] in bucket, f"{row['tag']} expected in {row['expected']}"

    def test_null_in_guarded_column_routes_to_quarantine_only(self, routed):
        """The marquee: NULL-safe predicates keep NULLs out of the clean table."""
        _, _, _, clean_tags, quarantine_tags = routed
        for null_tag in ("null_fare", "null_pickup_ts", "null_pickup_zip"):
            assert null_tag in quarantine_tags
            assert null_tag not in clean_tags

    def test_multi_violation_appears_once(self, routed):
        _, _, quarantine, _, _ = routed
        rows = [r for r in quarantine.select("tag").collect() if r["tag"] == "multi_violation"]
        assert len(rows) == 1

    def test_warn_only_row_stays_clean(self, routed):
        """Warn rules do not route; a row that only trips a warn rule is clean."""
        _, _, _, clean_tags, _ = routed
        assert "warn_only" in clean_tags
        assert WARN_RULES, "this asset ships warn rules"
