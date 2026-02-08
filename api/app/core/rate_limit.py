from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Dict, Tuple

from app.redis.client import get_redis
from app.redis.keys import rate_limit_bucket

_LOCAL_LOCK = Lock()
_LOCAL_BUCKETS: Dict[str, Tuple[int, float]] = {}
_METRICS_LOCK = Lock()
_RATE_LIMIT_METRICS = {
  "allowed_total": 0,
  "blocked_total": 0,
  "blocked_by_action": {},
  "retry_after_seconds_total": 0,
  "retry_after_seconds_samples": 0,
  "retry_after_seconds_max": 0,
}


@dataclass(frozen=True)
class RateLimitResult:
  allowed: bool
  retry_after: int | None


def _action_label(bucket: str) -> str:
  if not bucket:
    return "unknown"
  parts = bucket.split(":")
  return parts[-1] if parts else bucket


def _record_rate_limit(bucket: str, result: RateLimitResult) -> None:
  action = _action_label(bucket)
  with _METRICS_LOCK:
    if result.allowed:
      _RATE_LIMIT_METRICS["allowed_total"] += 1
      return
    _RATE_LIMIT_METRICS["blocked_total"] += 1
    blocked_by_action = _RATE_LIMIT_METRICS["blocked_by_action"]
    blocked_by_action[action] = blocked_by_action.get(action, 0) + 1
    if result.retry_after:
      _RATE_LIMIT_METRICS["retry_after_seconds_total"] += result.retry_after
      _RATE_LIMIT_METRICS["retry_after_seconds_samples"] += 1
      if result.retry_after > _RATE_LIMIT_METRICS["retry_after_seconds_max"]:
        _RATE_LIMIT_METRICS["retry_after_seconds_max"] = result.retry_after


def rate_limit_metrics() -> dict:
  with _METRICS_LOCK:
    samples = _RATE_LIMIT_METRICS["retry_after_seconds_samples"]
    avg = (
      _RATE_LIMIT_METRICS["retry_after_seconds_total"] / samples
      if samples
      else 0
    )
    return {
      "allowed_total": _RATE_LIMIT_METRICS["allowed_total"],
      "blocked_total": _RATE_LIMIT_METRICS["blocked_total"],
      "blocked_by_action": dict(_RATE_LIMIT_METRICS["blocked_by_action"]),
      "retry_after_seconds_avg": avg,
      "retry_after_seconds_max": _RATE_LIMIT_METRICS["retry_after_seconds_max"],
    }


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
      result = RateLimitResult(allowed=False, retry_after=retry_after)
    else:
      result = RateLimitResult(allowed=True, retry_after=None)
  except Exception:
    result = _local_check(key, limit, window_seconds)
  _record_rate_limit(bucket, result)
  return result


def reset_local_rate_limits_for_tests() -> None:
  """Test-only helper to prevent cross-test coupling."""
  with _LOCAL_LOCK:
    _LOCAL_BUCKETS.clear()
  with _METRICS_LOCK:
    _RATE_LIMIT_METRICS["allowed_total"] = 0
    _RATE_LIMIT_METRICS["blocked_total"] = 0
    _RATE_LIMIT_METRICS["blocked_by_action"] = {}
    _RATE_LIMIT_METRICS["retry_after_seconds_total"] = 0
    _RATE_LIMIT_METRICS["retry_after_seconds_samples"] = 0
    _RATE_LIMIT_METRICS["retry_after_seconds_max"] = 0
  try:
    from app.redis.client import scan_keys, delete_key
    from app.redis.keys import KEY_PREFIX
    for key in scan_keys(f"{KEY_PREFIX}:rate:*"):
      delete_key(key)
  except Exception:
    pass
