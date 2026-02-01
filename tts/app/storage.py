from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

MINIO_ENDPOINT = "http://minio:9000"
MINIO_ROOT_USER = "minio"
MINIO_ROOT_PASSWORD = "minio123"
MINIO_BUCKET = "storyfill-audio"
MINIO_REGION = "us-east-1"

_s3_client = None
_bucket_ready = False


def configure_from_env() -> None:
  global MINIO_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, MINIO_BUCKET, MINIO_REGION
  import os

  MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", MINIO_ENDPOINT)
  MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", MINIO_ROOT_USER)
  MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", MINIO_ROOT_PASSWORD)
  MINIO_BUCKET = os.getenv("MINIO_BUCKET", MINIO_BUCKET)
  MINIO_REGION = os.getenv("MINIO_REGION", MINIO_REGION)


def get_s3_client():
  global _s3_client
  if _s3_client is None:
    _s3_client = boto3.client(
      "s3",
      endpoint_url=MINIO_ENDPOINT,
      region_name=MINIO_REGION,
      aws_access_key_id=MINIO_ROOT_USER,
      aws_secret_access_key=MINIO_ROOT_PASSWORD,
      config=Config(signature_version="s3v4"),
    )
  return _s3_client


def ensure_bucket() -> None:
  global _bucket_ready
  if _bucket_ready:
    return
  s3 = get_s3_client()
  try:
    s3.head_bucket(Bucket=MINIO_BUCKET)
  except ClientError:
    s3.create_bucket(Bucket=MINIO_BUCKET)
  _bucket_ready = True


def put_object(key: str, data: bytes, content_type: str) -> None:
  ensure_bucket()
  s3 = get_s3_client()
  s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=data, ContentType=content_type)


def bucket_name() -> str:
  return MINIO_BUCKET
