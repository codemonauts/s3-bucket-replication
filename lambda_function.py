"""
AWS Lambda function to copy objects from one bucket to other bucklets.
"""

import logging
from urllib.parse import unquote_plus

import boto3
from boto3.exceptions import S3TransferFailedError
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_targets_from_bucket(client, src_bucket):
    """
    Find the 'TargetBucket' tag on a bucket and return
    a list of all targets
    """

    try:
        bucket_tagging = client.get_bucket_tagging(Bucket=src_bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchTagSet":
            return None
        raise

    tags = bucket_tagging["TagSet"]

    # Look for the 'TargetBucket' string
    for t in tags:
        if t["Key"] == "TargetBucket":
            return t["Value"].split()

    return None


def copy(client, src_bucket, dest_bucket, key):
    """
    Copy one object from the src to the dest bucket.

    Uses the managed 'copy' transfer, which transparently switches to a
    multipart copy for objects larger than the 5 GB single-request limit.
    """

    try:
        client.copy(CopySource={"Bucket": src_bucket, "Key": key}, Bucket=dest_bucket, Key=key)
    except (ClientError, S3TransferFailedError) as exc:
        logger.error("Error while copying '%s' to '%s': %s", key, dest_bucket, exc)


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """
    Entrypoint for AWS Lambda
    """

    client = boto3.client("s3")

    for record in event["Records"]:
        src_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        targets = get_targets_from_bucket(client, src_bucket)
        if targets:
            for dest_bucket in targets:
                logger.info("Will copy '%s' to '%s'", key, dest_bucket)
                copy(client, src_bucket, dest_bucket, key)
        else:
            logger.info("Bucket %s has no targets configured", src_bucket)
