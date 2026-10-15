"""Lambda entry point: S3 (input bucket) -> analytics -> S3 (output bucket).

Triggered by s3:ObjectCreated events for .csv files. For every new file it
writes one CSV per report to the output bucket, partitioned as:

    <report_name>/ingest_date=YYYY-MM-DD/<input_key without .csv, "/" -> "_">.csv

Environment variables:
    OUTPUT_BUCKET  name of the bucket reports are written to (required)
    LOG_LEVEL      logging level, default INFO
"""
import io
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3
import pandas as pd

import orders_analytics

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3_client = boto3.client("s3")


def get_s3_path_from_event(record: dict) -> str:
    "Returns the S3 path (s3://bucket/key) from a single S3 event record"
    bucket = record["s3"]["bucket"]["name"]
    # Keys in S3 events are URL-encoded (spaces become '+', etc.)
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    return f"s3://{bucket}/{key}"


def split_s3_path(s3_path: str):
    "Split s3://bucket/key into (bucket, key)"
    bucket, _, key = s3_path[len("s3://"):].partition("/")
    return bucket, key


def build_output_key(report_name: str, source_key: str, ingest_date: str) -> str:
    "Output key, partitioned by report and ingest date, named after the input key"
    # Use the whole key (not just the file name) so "a/orders.csv" and "b/orders.csv" don't collide.
    source_name = os.path.splitext(source_key)[0].replace("/", "_")
    return f"{report_name}/ingest_date={ingest_date}/{source_name}.csv"


def lambda_handler(event, context):
    "Lambda function to process S3 events and perform analytics on orders data"
    output_bucket = os.environ["OUTPUT_BUCKET"]
    ingest_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    written = []

    for record in event.get("Records", []):
        input_bucket, input_key = split_s3_path(get_s3_path_from_event(record))

        if not input_key.lower().endswith(".csv"):
            logger.info("Skipping non-CSV object %s", input_key)
            continue

        logger.info("Processing s3://%s/%s", input_bucket, input_key)
        try:
            body = s3_client.get_object(Bucket=input_bucket, Key=input_key)["Body"].read()
            orders_df = pd.read_csv(io.BytesIO(body))
            orders_df.columns = orders_df.columns.str.strip()
            reports = orders_analytics.run_all_reports(orders_df)
        except Exception:
            # Log with traceback, then re-raise so Lambda marks the invocation as failed
            # (S3 invokes asynchronously, so Lambda retries it automatically).
            logger.exception("Failed to process s3://%s/%s", input_bucket, input_key)
            raise

        for report_name, report_df in reports.items():
            output_key = build_output_key(report_name, input_key, ingest_date)
            s3_client.put_object(
                Bucket=output_bucket,
                Key=output_key,
                Body=report_df.to_csv(index=False).encode("utf-8"),
                ContentType="text/csv",
            )
            written.append(f"s3://{output_bucket}/{output_key}")
            logger.info("Wrote s3://%s/%s", output_bucket, output_key)

    return {"statusCode": 200, "reports_written": written}
