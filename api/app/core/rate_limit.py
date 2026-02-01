from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Dict, Tuple

from app.redis.client import get_redis
from app.redis.keys import rate_limit_bucket

_LOCAL_LOCK = Lock()
_LOCAL_BUCKETS: Dict[str, Tuple[int, float]] = {}


@dataclass(frozen=True)
class RateLimitResult:
  allowed: bool
  retry_after: int | None


def _local_check(bucket: str, limit: int, window_seconds: int) -> RateLimitResult:
  now = time()
  with _LOCAL_LOCK:
    count, reset_at = _LOCAL_BUCKETS.get(bucket, (0, now + window_seconds))
    if now >= reset_at:
      count = 0
      reset_at = now + window_seconds
    count += 1
    _LOCAL_BUCKETS[bucket] = (count, reset_at)
    if count > limit:
      retry_after = max(int(reset_at - now), 1)
      return RateLimitResult(allowed=False, retry_after=retry_after)
  return RateLimitResult(allowed=True, retry_after=None)


def check_rate_limit(bucket: str, limit: int, window_seconds: int) -> RateLimitResult:
  key = rate_limit_bucket(bucket)
  try:
    client = get_redis()
    count = client.incr(key)
    if count == 1:
      client.expire(key, window_seconds)
      ttl = window_seconds
    else:
      ttl = client.ttl(key)
      if ttl < 0:
        client.expire(key, window_seconds)
        ttl = window_seconds
    if count > limit:
      retry_after = max(int(ttl), 1)
      return RateLimitResult(allowed=False, retry_after=retry_after)
    return RateLimitResult(allowed=True, retry_after=None)
  except Exception:
    return _local_check(key, limit, window_seconds)
