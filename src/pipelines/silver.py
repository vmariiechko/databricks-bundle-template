# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Sample Pipeline
# MAGIC

# COMMAND ----------
import dlt
from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, count, current_timestamp
from pyspark.sql.functions import sum as _sum

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()

CATALOG_NAME = spark.conf.get("catalogName", "default")
ENVIRONMENT = spark.conf.get("pipelineEnvironment", "user")
USER_NAME = spark.conf.get("userName", "user")

# COMMAND ----------


def get_fqn(table_name):
    schema_name = f"{USER_NAME}_silver" if ENVIRONMENT == "user" else "silver"
    return f"`{CATALOG_NAME}`.`{schema_name}`.`{table_name}`"


# COMMAND ----------


@dlt.table(
    name=get_fqn("taxi_trips"),
    comment="Silver layer: Aggregated and enriched data",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
def taxi_trips():
    """
    Example silver table with simple aggregations.
    """
    return (
        dlt.read("taxi_trips_raw")
        .groupBy("pickup_zip")
        .agg(
            count("*").alias("trip_count"),
            _sum("fare_amount").alias("total_fare"),
            avg("fare_amount").alias("avg_fare"),
        )
        .withColumn("processing_timestamp", current_timestamp())
    )
