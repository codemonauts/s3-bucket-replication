# s3-bucket-replication

Copy every new object from an S3 bucket to one or more other buckets


## Motivation

S3 offers CRR (Cross Region Replication) or SRR (Same Region Replication) to trigger a copy operation on every new file in a bucket, but it has one limitation which got us:
While you can define multiple rules for e.g. different subfolders, all of the rules has to use the same target bucket.

Our usecase is, that we want to copy every new file into two different
buckets (one for backup and one used by our staging system), which is not
possible with out-of-the-box S3 tools so we used
[eleven41/aws-lambda-copy-s3-objects](https://github.com/eleven41/aws-lambda-copy-s3-objects)
for some years. But because it has been unmaintained for quite a while now and we
lack the skillset to move the codebase to be compatible with modern NodeJS
versions, we decidet to rewrite the tool in Python3.

## Installation

  * Create a Lambda function (With the latest Python runtime) and give it proper permissions (See next section)
  * Add a tag with the name 'TargetBucket' to the bucket you want to use as a source with a whitespace seperated list of target buckets as the value
  * Add a event for "All object create events" on the bucket, which executes the lambda function

## Configuration

The function can be tuned with the following optional environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `TAG_CACHE_TTL` | `300` | Seconds the `TargetBucket` tag lookup is cached per source bucket (warm containers only). Tag changes take effect after the TTL expires or on a cold start. |
| `STORAGE_CLASS` | _(unset)_ | Storage class for the copied objects, e.g. `STANDARD_IA` or `GLACIER_IR`. |
| `SSE_KMS_KEY_ID` | _(unset)_ | KMS key id/ARN; if set, copies are written with SSE-KMS using this key. |

## IAM

Lambda functions needs the following additional permissions to work:
  * `s3:GetBucketTagging` and `s3:GetObject` on the source bucket
  * `s3:PutObject` on all target buckets
  * `s3:AbortMultipartUpload` on all target buckets (objects larger than 5 GB are copied via multipart upload, which needs this permission to clean up failed copies)
  * If the source objects are SSE-KMS encrypted: `kms:Decrypt` on the source key
  * If `SSE_KMS_KEY_ID` is set: `kms:GenerateDataKey` and `kms:Decrypt` on that key

## Operational notes

  * A failed copy now fails the whole invocation, so S3's built-in async retries kick in. Configure an [on-failure destination or DLQ](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-retain-records.html) on the function to catch events that still fail after all retries.
  * The function skips a target that equals the source bucket, but it cannot detect loops across multiple buckets. Don't point two buckets at each other via their `TargetBucket` tags while both trigger this function.
