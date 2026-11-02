"""
AWS Lambda function to copy objects from one bucket to other buckets.
"""

import logging
import os
import time
from urllib.parse import unquote_plus

import boto3
from boto3.exceptions import S3TransferFailedError
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TAG_CACHE_TTL = int(os.environ.get("TAG_CACHE_TTL", "300"))

# {bucket: (targets, fetched_at)}, reused across warm invocations
_target_cache = {}


def get_extra_args():
    """Build optional ExtraArgs for the copy from environment variables."""

    extra_args = {}
    storage_class = os.environ.get("STORAGE_CLASS")
    if storage_class:
        extra_args["StorageClass"] = storage_class
    kms_key_id = os.environ.get("SSE_KMS_KEY_ID")
    if kms_key_id:
        extra_args["ServerSideEncryption"] = "aws:kms"
        extra_args["SSEKMSKeyId"] = kms_key_id
    return extra_args


def get_targets_from_bucket(client, src_bucket):
    """
    Find the 'TargetBucket' tag on a bucket and return a list of all
    targets. Results are cached for TAG_CACHE_TTL seconds.
    """

    cached = _target_cache.get(src_bucket)
    if cached and time.monotonic() - cached[1] < TAG_CACHE_TTL:
        return cached[0]

    targets = None
    try:
        bucket_tagging = client.get_bucket_tagging(Bucket=src_bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchTagSet":
            raise
    else:
        for t in bucket_tagging["TagSet"]:
            if t["Key"] == "TargetBucket":
                targets = t["Value"].split()
                break

    _target_cache[src_bucket] = (targets, time.monotonic())
    return targets


def copy(client, src_bucket, dest_bucket, key, extra_args):
    """
    Copy one object from the src to the dest bucket and return success.

    Uses the managed 'copy' transfer, which transparently switches to a
    multipart copy for objects larger than the 5 GB single-request limit.
    """

    kwargs = {"ExtraArgs": extra_args} if extra_args else {}
    try:
        client.copy(CopySource={"Bucket": src_bucket, "Key": key}, Bucket=dest_bucket, Key=key, **kwargs)
    except (ClientError, S3TransferFailedError) as exc:
        logger.error("Error while copying '%s' to '%s': %s", key, dest_bucket, exc)
        return False
    return True


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """
    Entrypoint for AWS Lambda
    """

    client = boto3.client("s3")
    extra_args = get_extra_args()
    failed = []

    records = event.get("Records", [])
    if not records:
        logger.warning("Event contains no records")
        return

    for record in records:
        if "s3" not in record:
            logger.warning("Skipping record without S3 payload")
            continue
        src_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        targets = get_targets_from_bucket(client, src_bucket)
        if not targets:
            logger.info("Bucket %s has no targets configured", src_bucket)
            continue
        for dest_bucket in targets:
            if dest_bucket == src_bucket:
                logger.warning("Skipping target '%s' because it is the source bucket", dest_bucket)
                continue
            logger.info("Will copy '%s' to '%s'", key, dest_bucket)
            if not copy(client, src_bucket, dest_bucket, key, extra_args):
                failed.append(f"'{key}' -> '{dest_bucket}'")

    # Fail the invocation so S3's async retry and any OnFailure destination kick in
    if failed:
        raise RuntimeError(f"{len(failed)} copies failed: {', '.join(failed)}")
