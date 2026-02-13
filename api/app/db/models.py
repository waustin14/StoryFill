from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Template(Base):
  __tablename__ = "templates"

  # Keep IDs stable and human-readable for now (matches existing API ids like "t-forest-mishap").
  id: Mapped[str] = mapped_column(String(64), primary_key=True)
  title: Mapped[str] = mapped_column(String(200), nullable=False)
  description: Mapped[str | None] = mapped_column(String(500), nullable=True)
  genre: Mapped[str] = mapped_column(String(64), nullable=False)
  content_rating: Mapped[str] = mapped_column(String(32), nullable=False)

  # Canonical definition (slots + story, and room for future fields like narration_hints).
  definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

  version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RoomSession(Base):
  __tablename__ = "room_sessions"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
  room_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
  template_id: Mapped[str] = mapped_column(String(64), ForeignKey("templates.id"), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Round(Base):
  __tablename__ = "rounds"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
  room_session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("room_sessions.id"), nullable=False)
  round_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  final_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
  revealed_story_text: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShareArtifact(Base):
  __tablename__ = "share_artifacts"

  share_token: Mapped[str] = mapped_column(String(128), primary_key=True)
  round_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("rounds.id"), nullable=True)
  room_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
  rendered_story_text: Mapped[str] = mapped_column(Text, nullable=False)
  audio_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class TTSJob(Base):
  __tablename__ = "tts_jobs"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
  round_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("rounds.id"), nullable=True)
  provider: Mapped[str] = mapped_column(String(64), nullable=False, default="tts-service")
  voice_id: Mapped[str] = mapped_column(String(64), nullable=False)
  cache_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
  status: Mapped[str] = mapped_column(String(32), nullable=False)
  audio_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
  error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TTSCache(Base):
  __tablename__ = "tts_cache"

  cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
  audio_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ModerationEvent(Base):
  __tablename__ = "moderation_events"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
  scope: Mapped[str] = mapped_column(String(64), nullable=False)
  result: Mapped[str] = mapped_column(String(32), nullable=False)
  reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

