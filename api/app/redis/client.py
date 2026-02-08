from typing import Generator, Optional

import redis

from app.core.config import REDIS_URL

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
  global _client
  if _client is None:
    _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
  return _client


def refresh_ttl(key: str, ttl_seconds: int) -> bool:
  client = get_redis()
  return bool(client.expire(key, ttl_seconds))


def set_value(key: str, value: str, ttl_seconds: int | None = None) -> bool:
  client = get_redis()
  if ttl_seconds is None:
    return bool(client.set(key, value))
  return bool(client.set(key, value, ex=ttl_seconds))


def get_value(key: str) -> Optional[str]:
  client = get_redis()
  return client.get(key)


def delete_key(key: str) -> int:
  client = get_redis()
  return int(client.delete(key))


def scan_keys(pattern: str) -> Generator[str, None, None]:
  client = get_redis()
  yield from client.scan_iter(match=pattern)
