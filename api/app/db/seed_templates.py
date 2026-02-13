from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.data.templates import TEMPLATE_DEFINITIONS
from app.db.models import Template as TemplateRow


def _now():
  return datetime.now(timezone.utc)


def seed_templates(db: Session) -> int:
  """Insert/update built-in templates into the DB. Returns number of templates written."""
  written = 0
  now = _now()
  for template_id, definition in TEMPLATE_DEFINITIONS.items():
    row = db.query(TemplateRow).filter(TemplateRow.id == template_id).one_or_none()
    payload = {
      "slots": [slot.model_dump() for slot in definition.slots],
      "story": definition.story,
      "narration_hints": definition.narration_hints,
    }
    if row is None:
      row = TemplateRow(
        id=definition.id,
        title=definition.title,
        description=definition.description,
        genre=definition.genre,
        content_rating=definition.content_rating,
        definition=payload,
        version=1,
        created_at=now,
        published_at=now,
      )
      db.add(row)
    else:
      row.title = definition.title
      row.description = definition.description
      row.genre = definition.genre
      row.content_rating = definition.content_rating
      row.definition = payload
      row.published_at = row.published_at or now
    written += 1

  db.commit()
  return written


def main() -> None:
  from app.db.session import SessionLocal

  db = SessionLocal()
  try:
    count = seed_templates(db)
    print(f"Seeded {count} templates.")
  finally:
    db.close()


if __name__ == "__main__":
  main()
