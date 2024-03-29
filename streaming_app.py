# -*- coding: utf-8 -*-
"""streaming_app.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1TWWDxoT9Y2uSA7yUZmGvFgM1xG6Ba-cK
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import sum
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
from pyspark.sql.functions import from_json, col, window , to_timestamp


# Initialize Spark Session
spark = SparkSession.builder.appName("KafkaStreamProcessing").getOrCreate()

# Set LEGACY Time Parser Policy
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")

# Define Kafka parameters
kafka_params = {
    "kafka.bootstrap.servers": "kafka:9092",
    "subscribePattern": "low_quantity,medium_quantity,high_quantity",
}

# Define the schema for the JSON data
json_schema = StructType([
    StructField("InvoiceNo", StringType(), True),
    StructField("StockCode", StringType(), True),
    StructField("Description", StringType(), True),
    StructField("Quantity", IntegerType(), True),
    StructField("InvoiceDate", StringType(), True),
    StructField("UnitPrice", DoubleType(), True),
    StructField("CustomerID", StringType(), True),
    StructField("Country", StringType(), True)
])

# Read data from Kafka, parse JSON, and cast "InvoiceDate" to timestamp
df = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", kafka_params["kafka.bootstrap.servers"]) \
        .option("subscribe", kafka_params["subscribePattern"]) \
        .option("startingOffsets", "earliest") \
        .load()

df.printSchema()

# Perform aggregations on Quantity and total price for each Invoice with watermark
parsed_data = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), json_schema).alias("data")).select("data.*")

# Filter data for "United Kingdom ,France, Spain"
filtered_data = parsed_data.filter(col("Country").isin("United Kingdom", "France", "Spain"))

# Convert "InvoiceDate" to timestamp
filtered_data = filtered_data.withColumn("InvoiceDate", to_timestamp("InvoiceDate", "MM/dd/yyyy H:mm"))


# Perform aggregations on Quantity and total price for each Invoice
# aggregated_data = filtered_data.withWatermark("InvoiceDate", "10 minutes").groupBy("InvoiceNo", window("InvoiceDate", "10 minutes")) \
#     .agg(sum("Quantity").alias("TotalQuantity"), sum(col("Quantity") * col("UnitPrice")).alias("TotalPrice"))

aggregated_data = filtered_data.withWatermark("InvoiceDate", "10 minutes").groupBy("InvoiceNo", "CustomerID", "Country", window("InvoiceDate", "10 minutes")) \
    .agg(sum("Quantity").alias("TotalQuantity"), sum(col("Quantity") * col("UnitPrice")).alias("TotalPrice"))


# Write aggregated data to HDFS
filterQuery = aggregated_data \
    .writeStream \
    .outputMode("append") \
    .format("json") \
    .option("checkpointLocation", "/tmp/checkpoints") \
    .option("path", "hdfs://namenode:9000/project/aggregated_data") \
    .start()

# Start the query
# This will run for 600 seconds (10 minutes)
filterQuery.awaitTermination(timeout=600)


# Stop the Spark session gracefully
spark.stop()