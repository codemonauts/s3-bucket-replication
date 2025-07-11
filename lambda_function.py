"""
AWS Lambda function to copy objects from one bucket to other bucklets.
"""

from urllib.parse import unquote
import boto3


def get_targets_from_bucket(client, src_bucket):
    """
    Find the 'TargetBucket' tag on a bucket and return
    a list of all targets
    """

    bucket_tagging = client.get_bucket_tagging(Bucket=src_bucket)
    tags = bucket_tagging["TagSet"]

    # Look for the 'TargetBucket' string
    for t in tags:
        if t["Key"] == "TargetBucket":
            return t["Value"].split(" ")

    return None


def copy(client, src_bucket, dest_bucket, key):
    """
    Copy one object from the src to the dest bucket
    """

    response = client.copy_object(Bucket=dest_bucket, Key=key, CopySource={"Bucket": src_bucket, "Key": key})
    if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        print(f"Error while copying {key}: {response}")


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """
    Entrypoint for AWS Lambda
    """

    client = boto3.client("s3")

    for record in event["Records"]:
        src_bucket = record["s3"]["bucket"]["name"]
        key = unquote(record["s3"]["object"]["key"])
        targets = get_targets_from_bucket(client, src_bucket)
        if targets:
            for dest_bucket in targets:
                print(f"Will copy '{key}' to '{dest_bucket}'")
                copy(client, src_bucket, dest_bucket, key)
        else:
            print(f"Bucket {src_bucket} has no targets configured")
