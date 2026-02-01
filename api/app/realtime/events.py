from __future__ import annotations

import json
from datetime import datetime, timezone

from app.redis.client import get_redis
from app.redis.keys import KEY_PREFIX

EVENT_CHANNEL = f"{KEY_PREFIX}:events"


def _now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def emit_room_expired(room_code: str, round_id: str) -> None:
  payload = {
    "type": "room.expired",
    "room_code": room_code,
    "round_id": round_id,
    "ts": _now_iso(),
  }
  try:
    client = get_redis()
    client.publish(EVENT_CHANNEL, json.dumps(payload))
  except Exception:
    return
