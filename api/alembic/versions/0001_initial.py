"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-01-31 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "templates",
    sa.Column("id", sa.String(length=64), primary_key=True),
    sa.Column("title", sa.String(length=200), nullable=False),
    sa.Column("genre", sa.String(length=64), nullable=False),
    sa.Column("content_rating", sa.String(length=32), nullable=False),
    sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
  )

  op.create_table(
    "room_sessions",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("room_code", sa.String(length=16), nullable=False),
    sa.Column("template_id", sa.String(length=64), sa.ForeignKey("templates.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("end_reason", sa.String(length=64), nullable=True),
  )
  op.create_index("ix_room_sessions_room_code", "room_sessions", ["room_code"])

  op.create_table(
    "rounds",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("room_session_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("room_sessions.id"), nullable=False),
    sa.Column("round_index", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("final_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("revealed_story_text", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )

  op.create_table(
    "share_artifacts",
    sa.Column("share_token", sa.String(length=128), primary_key=True),
    sa.Column("round_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("rounds.id"), nullable=True),
    sa.Column("room_code", sa.String(length=16), nullable=False),
    sa.Column("rendered_story_text", sa.Text(), nullable=False),
    sa.Column("audio_object_key", sa.String(length=512), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_share_artifacts_room_code", "share_artifacts", ["room_code"])
  op.create_index("ix_share_artifacts_expires_at", "share_artifacts", ["expires_at"])

  op.create_table(
    "tts_jobs",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("round_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("rounds.id"), nullable=True),
    sa.Column("provider", sa.String(length=64), nullable=False, server_default="tts-service"),
    sa.Column("voice_id", sa.String(length=64), nullable=False),
    sa.Column("cache_key", sa.String(length=128), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("audio_object_key", sa.String(length=512), nullable=True),
    sa.Column("error_code", sa.String(length=64), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_tts_jobs_cache_key", "tts_jobs", ["cache_key"])

  op.create_table(
    "tts_cache",
    sa.Column("cache_key", sa.String(length=128), primary_key=True),
    sa.Column("audio_object_key", sa.String(length=512), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_tts_cache_expires_at", "tts_cache", ["expires_at"])

  op.create_table(
    "moderation_events",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("scope", sa.String(length=64), nullable=False),
    sa.Column("result", sa.String(length=32), nullable=False),
    sa.Column("reason_code", sa.String(length=64), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )


def downgrade() -> None:
  op.drop_table("moderation_events")
  op.drop_index("ix_tts_cache_expires_at", table_name="tts_cache")
  op.drop_table("tts_cache")
  op.drop_index("ix_tts_jobs_cache_key", table_name="tts_jobs")
  op.drop_table("tts_jobs")
  op.drop_index("ix_share_artifacts_expires_at", table_name="share_artifacts")
  op.drop_index("ix_share_artifacts_room_code", table_name="share_artifacts")
  op.drop_table("share_artifacts")
  op.drop_table("rounds")
  op.drop_index("ix_room_sessions_room_code", table_name="room_sessions")
  op.drop_table("room_sessions")
  op.drop_table("templates")
