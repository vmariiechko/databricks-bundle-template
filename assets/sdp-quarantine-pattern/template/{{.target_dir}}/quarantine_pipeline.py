# Databricks notebook source
# MAGIC %md
# MAGIC # Quarantine pattern: inverse expectations + a separate quarantine table
# MAGIC
# MAGIC Critical (drop) expectations remove violating rows from `silver_trips`. The
# MAGIC `quarantine_trips` table applies the **inverse** of those expectations, so it
# MAGIC captures exactly the rows silver dropped. Advisory (warn) expectations annotate
# MAGIC the pipeline event log without dropping anything.
# MAGIC
# MAGIC Drop predicates are NULL-safe, so silver and quarantine partition the input
# MAGIC exactly once (every bronze row lands in exactly one of them). The README's
# MAGIC "The NULL trap" section explains why that matters.
# MAGIC
# MAGIC Source is the public `samples.nyctaxi.trips`, which already contains some
# MAGIC invalid rows, so `quarantine_trips` is populated on the first run.

# COMMAND ----------

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from expectations import DROP_RULES, WARN_RULES, build_quarantine_expr

spark = SparkSession.getActiveSession()

# Catalog and silver schema come from the pipeline configuration (set by the
# DABs resource). Bronze tables use the pipeline's default schema; silver and
# quarantine are fully qualified into the silver schema.
CATALOG = spark.conf.get("quarantine.catalog", "main")
SILVER_SCHEMA = spark.conf.get("quarantine.silver_schema", "silver")

SOURCE_TABLE = "samples.nyctaxi.trips"
SILVER_TRIPS = f"{CATALOG}.{SILVER_SCHEMA}.silver_trips"
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
# MAGIC ## Bronze: ingest the public sample (default = bronze schema)

# COMMAND ----------


@dp.table(
    name="bronze_trips",
    comment="Raw NYC taxi trips ingested from samples.nyctaxi.trips.",
)
def bronze_trips():
    return (
        spark.readStream.table(SOURCE_TABLE)
        .select(*TRIP_COLUMNS)
        .withColumn("_ingested_at", F.current_timestamp())
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver: valid rows (drop expectations enforced; warn rules logged)

# COMMAND ----------


@dp.table(
    name=SILVER_TRIPS,
    comment="Valid trips: pass every critical (drop) expectation.",
)
@dp.expect_all(WARN_RULES)
@dp.expect_all_or_drop(DROP_RULES)
def silver_trips():
    return spark.readStream.table("bronze_trips")


# COMMAND ----------
# MAGIC %md
# MAGIC ## Quarantine: the inverse of silver (same source, opposite predicate)

# COMMAND ----------


@dp.table(
    name=QUARANTINE_TRIPS,
    comment="Invalid trips: fail at least one critical (drop) expectation.",
)
@dp.expect_all_or_drop({"is_quarantined": QUARANTINE_EXPR})
def quarantine_trips():
    return spark.readStream.table("bronze_trips").withColumn(
        "_quarantined_at", F.current_timestamp()
    )
