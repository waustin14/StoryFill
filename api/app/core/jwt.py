from datetime import datetime, timezone
from typing import Optional

import jwt

from app.core.config import JWT_SECRET

_ALGORITHM = "HS256"


def create_host_token(room_id: str, room_code: str, ttl_seconds: int, jti: str) -> str:
  now = datetime.now(timezone.utc)
  payload = {
    "role": "host",
    "room_id": room_id,
    "room_code": room_code,
    "iat": now,
    "exp": datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc),
    "jti": jti,
  }
  return jwt.encode(payload, JWT_SECRET, algorithm=_ALGORITHM)


def create_player_token(
  room_id: str, room_code: str, player_id: str, ttl_seconds: int, jti: str
) -> str:
  now = datetime.now(timezone.utc)
  payload = {
    "role": "player",
    "room_id": room_id,
    "room_code": room_code,
    "player_id": player_id,
    "iat": now,
    "exp": datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc),
    "jti": jti,
  }
  return jwt.encode(payload, JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
  try:
    return jwt.decode(token, JWT_SECRET, algorithms=[_ALGORITHM])
  except Exception:
    return None
