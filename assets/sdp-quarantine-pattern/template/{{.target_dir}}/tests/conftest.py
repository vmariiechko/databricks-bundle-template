"""Shared pytest fixtures for the quarantine-pattern unit tests.

These tests run locally with a real Spark session, no Databricks workspace
required. The fixture and the UTC timestamp fix follow the standard PySpark
unit-testing setup for Lakeflow SDP transform code.
"""

import datetime
import os
import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import TimestampType

# Fix PySpark collect() returning local-timezone timestamps (SPARK-25244).
_original_fromInternal = TimestampType.fromInternal


def _utc_fromInternal(self, ts: int) -> datetime.datetime:
    if ts is not None:
        return datetime.datetime.fromtimestamp(ts // 1000000, tz=datetime.UTC).replace(
            microsecond=ts % 1000000, tzinfo=None
        )


TimestampType.fromInternal = _utc_fromInternal

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# The pipeline modules (expectations.py, expectations.json) live one level up,
# in the pipeline source directory. Put that on sys.path so tests import them
# the same way the pipeline does: `from expectations import ...`.
SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture(scope="session")
def spark():
    """Local Spark session with UTC timestamps for behavior-focused tests."""
    session = (
        SparkSession.builder.master("local[1]")
        .appName("sdp-quarantine-pattern-tests")
        .config("spark.driver.extraJavaOptions", "-Duser.timezone=UTC")
        .config("spark.executor.extraJavaOptions", "-Duser.timezone=UTC")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.default.parallelism", "1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    return session
