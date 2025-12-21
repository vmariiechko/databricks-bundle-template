# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Sample Pipeline
# MAGIC

# COMMAND ----------

import dlt
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()

CATALOG_NAME = spark.conf.get("catalogName", "default")
ENVIRONMENT = spark.conf.get("pipelineEnvironment", "user")
USER_NAME = spark.conf.get("userName", "user")

# COMMAND ----------


def get_fqn(table_name, schema_name):
    return f"`{CATALOG_NAME}`.`{schema_name}`.`{table_name}`"


# COMMAND ----------


@dlt.table(
    name=get_fqn("taxi_trips_raw", "bronze"),
    comment="Bronze layer: Raw data with minimal processing",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
    },
)
def taxi_trips_raw():
    """
    Example bronze table reading from Databricks sample data.
    """
    return (
        spark.read.table("samples.nyctaxi.trips")
        .limit(1000)
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            col("tpep_pickup_datetime"),
            col("tpep_dropoff_datetime"),
            col("pickup_zip"),
            col("dropoff_zip"),
            col("fare_amount"),
            col("ingestion_timestamp"),
        )
    )
