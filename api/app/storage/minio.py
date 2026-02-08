from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from opentelemetry import trace

from app.core.config import (
  MINIO_BUCKET,
  MINIO_ENDPOINT,
  MINIO_REGION,
  MINIO_ROOT_PASSWORD,
  MINIO_ROOT_USER,
)

_s3_client = None
_bucket_ready = False
_TRACER = trace.get_tracer(__name__)


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
    with _TRACER.start_as_current_span("minio.head_bucket") as span:
      span.set_attribute("minio.bucket", MINIO_BUCKET)
      s3.head_bucket(Bucket=MINIO_BUCKET)
  except ClientError:
    with _TRACER.start_as_current_span("minio.create_bucket") as span:
      span.set_attribute("minio.bucket", MINIO_BUCKET)
      s3.create_bucket(Bucket=MINIO_BUCKET)
  _bucket_ready = True


def put_object(key: str, data: bytes, content_type: str) -> None:
  ensure_bucket()
  s3 = get_s3_client()
  with _TRACER.start_as_current_span("minio.put_object") as span:
    span.set_attribute("minio.bucket", MINIO_BUCKET)
    span.set_attribute("minio.key", key)
    span.set_attribute("minio.content_type", content_type)
    s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=data, ContentType=content_type)


def get_object(key: str):
  ensure_bucket()
  s3 = get_s3_client()
  with _TRACER.start_as_current_span("minio.get_object") as span:
    span.set_attribute("minio.bucket", MINIO_BUCKET)
    span.set_attribute("minio.key", key)
    return s3.get_object(Bucket=MINIO_BUCKET, Key=key)


def object_exists(key: str) -> bool:
  ensure_bucket()
  s3 = get_s3_client()
  try:
    with _TRACER.start_as_current_span("minio.head_object") as span:
      span.set_attribute("minio.bucket", MINIO_BUCKET)
      span.set_attribute("minio.key", key)
      s3.head_object(Bucket=MINIO_BUCKET, Key=key)
    return True
  except ClientError:
    return False


def delete_object(key: str) -> None:
  ensure_bucket()
  s3 = get_s3_client()
  with _TRACER.start_as_current_span("minio.delete_object") as span:
    span.set_attribute("minio.bucket", MINIO_BUCKET)
    span.set_attribute("minio.key", key)
    s3.delete_object(Bucket=MINIO_BUCKET, Key=key)


def bucket_name() -> str:
  return MINIO_BUCKET
