from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.redis.client import get_redis
from app.redis.keys import KEY_PREFIX

EVENT_CHANNEL = f"{KEY_PREFIX}:events"


def _now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _request_id() -> str:
  return uuid4().hex


def with_request_id(payload: dict) -> dict:
  if "request_id" not in payload:
    payload["request_id"] = _request_id()
  return payload


def emit_event(payload: dict) -> None:
  try:
    client = get_redis()
    client.publish(EVENT_CHANNEL, json.dumps(with_request_id(payload)))
  except Exception:
    return


def emit_room_snapshot(*, room_code: str, round_id: str, state_version: int, room_snapshot: dict, progress: dict) -> None:
  emit_event(
    {
      "type": "room.snapshot",
      "room_code": room_code,
      "round_id": round_id,
      "state_version": state_version,
      "ts": _now_iso(),
      "payload": {"room_snapshot": room_snapshot, "progress": progress},
    }
  )


def emit_room_expired(room_code: str, round_id: str) -> None:
  emit_event({"type": "room.expired", "room_code": room_code, "round_id": round_id, "ts": _now_iso()})
