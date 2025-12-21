"""
Sample Data Ingestion Job
"""

import argparse

from pyspark.sql import SparkSession


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog_name", type=str, required=True)
    parser.add_argument("--environment", type=str, required=True)
    parser.add_argument("--user_name", type=str, required=True)
    args = parser.parse_args()

    print(
        f"Starting Job for catalog: `{args.catalog_name}` in environment: `{args.environment}` by"
        f" user: {args.user_name}"
    )

    spark = SparkSession.builder.appName("SampleIngestion").getOrCreate()

    df = spark.read.table("samples.bakehouse.sales_customers").limit(1000)

    print(f"\nRead {df.count()} sample records")
    print("\nSample data:")
    df.show(5)

    catalog_name = args.catalog_name
    schema_name = "bronze"
    table_fqn = f"`{catalog_name}`.`{schema_name}`.`sales_customers_raw`"
    df.write.mode("overwrite").saveAsTable(table_fqn)

    print(f"\nWrote {df.count()} sample records to {table_fqn}.")
    print("\n Job completed successfully!")


if __name__ == "__main__":
    main()
