"""
Silver Layer Transformation Job

Reads raw data from bronze layer, applies basic cleaning and standardization.
Gold layer will contain further aggregations and business logic.
"""

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog_name", type=str, required=True)
    parser.add_argument("--environment", type=str, required=True)
    parser.add_argument("--user_name", type=str, required=True)
    args = parser.parse_args()

    print(f"Starting Silver Transformation in environment: `{args.environment}`")

    spark = SparkSession.builder.appName("SilverTransformation").getOrCreate()

    catalog_name = args.catalog_name
    bronze_schema = "bronze"
    silver_schema = "silver"

    # Read from bronze layer
    bronze_table_fqn = f"`{catalog_name}`.`{bronze_schema}`.`sales_customers_raw`"
    df_bronze = spark.read.table(bronze_table_fqn)
    print(f"Read {df_bronze.count()} records from {bronze_table_fqn}")

    # Apply basic cleaning and standardization
    df_silver = (
        df_bronze
        # Standardize column names: customerID -> customer_id
        .withColumnRenamed("customerID", "customer_id")
        # Remove duplicates
        .dropDuplicates(["customer_id"])
        # Filter out invalid records
        .filter(F.col("customer_id").isNotNull())
        .filter(F.col("email_address").isNotNull())
        # Normalize text fields
        .withColumn("email_address", F.lower(F.trim(F.col("email_address"))))
        .withColumn("first_name", F.trim(F.col("first_name")))
        .withColumn("last_name", F.trim(F.col("last_name")))
        # Add processing metadata
        .withColumn("processed_at", F.current_timestamp())
    )

    print(f"Cleaned to {df_silver.count()} records")

    # Write to silver layer
    silver_table_fqn = f"`{catalog_name}`.`{silver_schema}`.`sales_customers_clean`"
    df_silver.write.mode("overwrite").saveAsTable(silver_table_fqn)

    print(f"Wrote to {silver_table_fqn}")
    print(" Silver transformation completed")


if __name__ == "__main__":
    main()
