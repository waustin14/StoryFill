from datetime import datetime, timezone

from botocore.exceptions import ClientError
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.db.session import SessionLocal
from app.metrics import collect_metrics
from app.redis.client import get_redis
from app.storage.minio import bucket_name, get_s3_client

router = APIRouter(tags=["health"])


def _now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _check_postgres() -> tuple[bool, str | None]:
  try:
    db = SessionLocal()
  except Exception as exc:
    return False, str(exc)

  try:
    db.execute(text("SELECT 1"))
    return True, None
  except Exception as exc:
    return False, str(exc)
  finally:
    db.close()


def _check_redis() -> tuple[bool, str | None]:
  try:
    client = get_redis()
    client.ping()
    return True, None
  except Exception as exc:
    return False, str(exc)


def _check_minio() -> tuple[bool, str | None]:
  try:
    client = get_s3_client()
    client.head_bucket(Bucket=bucket_name())
    return True, None
  except ClientError as exc:
    return False, str(exc)
  except Exception as exc:
    return False, str(exc)


@router.get("/health")
def health_check(response: Response):
  postgres_ok, postgres_error = _check_postgres()
  redis_ok, redis_error = _check_redis()
  minio_ok, minio_error = _check_minio()

  deps = {
    "postgres": {"status": "ok" if postgres_ok else "error", "error": postgres_error},
    "redis": {"status": "ok" if redis_ok else "error", "error": redis_error},
    "minio": {"status": "ok" if minio_ok else "error", "error": minio_error},
  }

  ok = postgres_ok and redis_ok and minio_ok
  if not ok:
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

  return {
    "status": "ok" if ok else "degraded",
    "ts": _now_iso(),
    "dependencies": deps,
  }


@router.get("/health/ready")
def readiness_check(response: Response):
  postgres_ok, postgres_error = _check_postgres()
  redis_ok, redis_error = _check_redis()
  minio_ok, minio_error = _check_minio()

  deps = {
    "postgres": {"status": "ok" if postgres_ok else "error", "error": postgres_error},
    "redis": {"status": "ok" if redis_ok else "error", "error": redis_error},
    "minio": {"status": "ok" if minio_ok else "error", "error": minio_error},
  }

  ok = postgres_ok and redis_ok and minio_ok
  if not ok:
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

  return {
    "status": "ready" if ok else "degraded",
    "ts": _now_iso(),
    "dependencies": deps,
  }


@router.get("/health/live")
def liveness_check():
  return {"status": "live", "ts": _now_iso()}


@router.get("/metrics")
def metrics_handler():
  return collect_metrics()
