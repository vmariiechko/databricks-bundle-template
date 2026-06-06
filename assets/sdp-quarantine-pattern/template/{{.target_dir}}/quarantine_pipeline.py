# Databricks notebook source
# MAGIC %md
# MAGIC # Quarantine pattern: inverse expectations + a separate quarantine table
# MAGIC
# MAGIC Critical (drop) expectations remove violating rows from `clean_trips`. The
# MAGIC `quarantine_trips` table applies the **inverse** of those expectations, so it
# MAGIC captures exactly the rows the clean table dropped. Advisory (warn) expectations
# MAGIC annotate the pipeline event log without dropping anything.
# MAGIC
# MAGIC Drop predicates are NULL-safe, so the clean and quarantine tables partition the
# MAGIC input exactly once (every raw row lands in exactly one of them). The README's
# MAGIC "The NULL trap" section explains why that matters.
# MAGIC
# MAGIC The source defaults to the public `samples.nyctaxi.trips`, which already
# MAGIC contains some invalid rows, so `quarantine_trips` is populated on the first
# MAGIC run. The source is read from the `quarantine.source` configuration, so a test
# MAGIC run can point it at a curated dataset (see the skill's self-verify reference).

# COMMAND ----------

from pyspark import pipelines as dp
from pyspark.sql import SparkSession, functions as F

from expectations import DROP_RULES, WARN_RULES, build_quarantine_expr

spark = SparkSession.getActiveSession()

# Catalog, schemas, and source come from the pipeline configuration (set by the
# DABs resource). The raw table lands in the bronze schema (also the pipeline's
# default schema); the clean and quarantine tables land in the silver schema.
# All three tables are named with fully qualified identifiers so the source
# reads consistently and the in-pipeline dependencies resolve unambiguously.
CATALOG = spark.conf.get("quarantine.catalog", "main")
BRONZE_SCHEMA = spark.conf.get("quarantine.bronze_schema", "bronze")
SILVER_SCHEMA = spark.conf.get("quarantine.silver_schema", "silver")
SOURCE_TABLE = spark.conf.get("quarantine.source", "samples.nyctaxi.trips")

RAW_TRIPS = f"{CATALOG}.{BRONZE_SCHEMA}.raw_trips"
CLEAN_TRIPS = f"{CATALOG}.{SILVER_SCHEMA}.clean_trips"
QUARANTINE_TRIPS = f"{CATALOG}.{SILVER_SCHEMA}.quarantine_trips"

# The full samples.nyctaxi.trips schema.
TRIP_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
    "pickup_zip",
    "dropoff_zip",
]

# Inverse of all drop predicates AND-ed together: true for a row that fails at
# least one critical expectation.
QUARANTINE_EXPR = build_quarantine_expr(DROP_RULES)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Raw: ingest the source (bronze schema)

# COMMAND ----------


@dp.table(
    name=RAW_TRIPS,
    comment="Raw NYC taxi trips ingested from the configured source.",
)
def raw_trips():
    return (
        spark.readStream.table(SOURCE_TABLE)
        .select(*TRIP_COLUMNS)
        .withColumn("_ingested_at", F.current_timestamp())
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Clean: valid rows (drop expectations enforced; warn rules logged)

# COMMAND ----------


@dp.table(
    name=CLEAN_TRIPS,
    comment="Valid trips: pass every critical (drop) expectation.",
)
@dp.expect_all(WARN_RULES)
@dp.expect_all_or_drop(DROP_RULES)
def clean_trips():
    return spark.readStream.table(RAW_TRIPS)


# COMMAND ----------
# MAGIC %md
# MAGIC ## Quarantine: the inverse of clean (same source, opposite predicate)

# COMMAND ----------


@dp.table(
    name=QUARANTINE_TRIPS,
    comment="Invalid trips: fail at least one critical (drop) expectation.",
)
@dp.expect_all_or_drop({"is_quarantined": QUARANTINE_EXPR})
def quarantine_trips():
    return spark.readStream.table(RAW_TRIPS).withColumn("_quarantined_at", F.current_timestamp())
