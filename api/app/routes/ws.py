from __future__ import annotations

import json

import anyio
from fastapi import APIRouter, WebSocket

from app.core.jwt import decode_token
from app.data.rooms import (
  RoomState,
  StorageUnavailableError,
  ensure_prompts_assigned,
  get_player,
  get_room,
  record_room_activity,
  reassign_prompts_if_needed,
  room_progress,
)
from app.realtime.events import EVENT_CHANNEL, with_request_id
from app.redis.client import get_redis
from app.routes.rooms import _room_snapshot  # reuse the canonical snapshot shape

router = APIRouter(prefix="/v1", tags=["ws"])


@router.websocket("/ws")
async def ws_handler(ws: WebSocket):
  room_code = (ws.query_params.get("room_code") or "").upper().strip()
  token = (ws.query_params.get("token") or "").strip()
  if not room_code or not token:
    await ws.close(code=4400, reason="room_code and token are required")
    return

  try:
    room = get_room(room_code)
  except StorageUnavailableError:
    await ws.close(code=4503, reason="storage temporarily unavailable")
    return
  if not room:
    await ws.close(code=4404, reason="room not found")
    return
  if room.is_expired():
    await ws.close(code=4410, reason="room expired")
    return

  # Auth: verify JWT claims for host or player role.
  claims = decode_token(token)
  if not claims or claims.get("room_id") != room.id:
    await ws.close(code=4403, reason="unauthorized")
    return
  role = claims.get("role")
  if role == "player":
    player_id = claims.get("player_id")
    if not player_id or not get_player(room, player_id):
      await ws.close(code=4403, reason="unauthorized")
      return
  elif role != "host":
    await ws.close(code=4403, reason="unauthorized")
    return

  await ws.accept()

  client = None
  pubsub = None
  try:
    client = get_redis()
    pubsub = client.pubsub()
    pubsub.subscribe(EVENT_CHANNEL)
  except Exception:
    pubsub = None

  # Send an initial snapshot so clients can render immediately.
  try:
    record_room_activity(room)
    reassign_prompts_if_needed(room)
    # Don't auto-start a lobby just because someone connected.
    if room.state != RoomState.LOBBY_OPEN:
      ensure_prompts_assigned(room)
    await ws.send_text(
      json.dumps(
        with_request_id(
          {
            "type": "room.snapshot",
            "room_code": room.code,
            "round_id": room.round_id,
            "state_version": room.state_version,
            "ts": None,
            "payload": {"room_snapshot": _room_snapshot(room).model_dump(), "progress": room_progress(room)},
          }
        )
      )
    )
  except Exception:
    pass

  async def recv_loop():
    # Keep the connection open; we don't require client messages yet (heartbeat optional).
    while True:
      await ws.receive_text()

  async def send_loop():
    if not pubsub:
      # If Redis is unavailable, degrade to a no-op connection rather than failing outright.
      while True:
        await anyio.sleep(10)

    while True:
      msg = await anyio.to_thread.run_sync(
        lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
      )
      if not msg:
        continue
      raw = msg.get("data")
      if not raw:
        continue
      try:
        payload = json.loads(raw)
      except Exception:
        continue
      if payload.get("room_code") != room_code:
        continue
      await ws.send_text(json.dumps(payload))

  try:
    async with anyio.create_task_group() as tg:
      tg.start_soon(send_loop)
      tg.start_soon(recv_loop)
  except Exception:
    return
  finally:
    try:
      if pubsub:
        await anyio.to_thread.run_sync(pubsub.close)
    except Exception:
      pass
