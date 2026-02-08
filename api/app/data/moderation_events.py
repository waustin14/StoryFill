from datetime import datetime, timezone
from typing import Optional

from app.db.models import ModerationEvent as ModerationEventRow
from app.db.session import SessionLocal


def _now() -> datetime:
  return datetime.now(timezone.utc)


def record_moderation_event(scope: str, result: str, reason_code: Optional[str]) -> None:
  try:
    db = SessionLocal()
  except Exception:
    return

  try:
    event = ModerationEventRow(
      scope=scope,
      result=result,
      reason_code=reason_code,
      created_at=_now(),
    )
    db.add(event)
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()
