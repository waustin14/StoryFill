from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Optional

from app.db.models import ShareArtifact as ShareArtifactRow
from app.db.session import SessionLocal
from app.redis.client import get_value, set_value
from app.redis.keys import share_artifact

SHARE_TTL = timedelta(days=7)
SHARE_TTL_SECONDS = int(SHARE_TTL.total_seconds())

_SHARE_FALLBACK: dict[str, dict] = {}


def _now() -> datetime:
  return datetime.now(timezone.utc)


@dataclass
class ShareArtifact:
  token: str
  room_code: str
  round_id: str
  rendered_story: str
  created_at: datetime
  expires_at: datetime


def _encode(artifact: ShareArtifact) -> str:
  payload = {
    "token": artifact.token,
    "room_code": artifact.room_code,
    "round_id": artifact.round_id,
    "rendered_story": artifact.rendered_story,
    "created_at": artifact.created_at.isoformat(),
    "expires_at": artifact.expires_at.isoformat(),
  }
  return json.dumps(payload)


def _decode(raw: str) -> Optional[ShareArtifact]:
  try:
    payload = json.loads(raw)
    return ShareArtifact(
      token=payload["token"],
      room_code=payload["room_code"],
      round_id=payload["round_id"],
      rendered_story=payload["rendered_story"],
      created_at=datetime.fromisoformat(payload["created_at"]),
      expires_at=datetime.fromisoformat(payload["expires_at"]),
    )
  except Exception:
    return None


def create_share(room_code: str, round_id: str, rendered_story: str) -> ShareArtifact:
  token = token_urlsafe(16)
  created_at = _now()
  expires_at = created_at + SHARE_TTL
  artifact = ShareArtifact(
    token=token,
    room_code=room_code,
    round_id=round_id,
    rendered_story=rendered_story,
    created_at=created_at,
    expires_at=expires_at,
  )
  raw = _encode(artifact)
  try:
    set_value(share_artifact(token), raw, ttl_seconds=SHARE_TTL_SECONDS)
  except Exception:
    _SHARE_FALLBACK[token] = json.loads(raw)

  # Best-effort persistence (DB is optional in local/test).
  try:
    db = SessionLocal()
    try:
      db.add(
        ShareArtifactRow(
          share_token=artifact.token,
          round_id=None,  # Current app round ids are not DB UUIDs yet.
          room_code=artifact.room_code,
          rendered_story_text=artifact.rendered_story,
          audio_object_key=None,
          created_at=artifact.created_at,
          expires_at=artifact.expires_at,
        )
      )
      db.commit()
    finally:
      db.close()
  except Exception:
    pass

  return artifact


def get_share(token: str) -> Optional[ShareArtifact]:
  try:
    raw = get_value(share_artifact(token))
  except Exception:
    raw = None
  if raw:
    return _decode(raw)

  # Best-effort DB lookup (if available).
  try:
    db = SessionLocal()
    try:
      row = db.query(ShareArtifactRow).filter(ShareArtifactRow.share_token == token).one_or_none()
    finally:
      db.close()
    if row and row.expires_at and row.expires_at > _now():
      artifact = ShareArtifact(
        token=row.share_token,
        room_code=row.room_code,
        round_id="",  # Current app round ids are not persisted yet.
        rendered_story=row.rendered_story_text,
        created_at=row.created_at,
        expires_at=row.expires_at,
      )
      try:
        set_value(share_artifact(token), _encode(artifact), ttl_seconds=SHARE_TTL_SECONDS)
      except Exception:
        pass
      return artifact
  except Exception:
    pass

  payload = _SHARE_FALLBACK.get(token)
  if not payload:
    return None
  try:
    expires_at = datetime.fromisoformat(payload["expires_at"])
  except Exception:
    return None
  if expires_at <= _now():
    _SHARE_FALLBACK.pop(token, None)
    return None
  return ShareArtifact(
    token=payload["token"],
    room_code=payload["room_code"],
    round_id=payload["round_id"],
    rendered_story=payload["rendered_story"],
    created_at=datetime.fromisoformat(payload["created_at"]),
    expires_at=expires_at,
  )
