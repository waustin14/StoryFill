from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import threading
from typing import Dict, Optional, Tuple
from uuid import uuid4

import httpx
from pydantic import BaseModel
from opentelemetry import trace

from app.core.config import (
  TTS_DEFAULT_MODEL,
  TTS_DEFAULT_VOICE,
  TTS_RESPONSE_FORMAT,
  TTS_SERVICE_URL,
)
from app.core.moderation import moderation_block_reason
from app.db.models import TTSCache as TTSCacheRow
from app.db.models import TTSJob as TTSJobRow
from app.db.session import SessionLocal
from app.data.moderation_events import record_moderation_event
from app.storage.minio import delete_object, get_object, object_exists, put_object


def _now() -> datetime:
  return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
  return f"{prefix}_{uuid4().hex[:12]}"


TTS_VERSION = "v2"
TTS_CACHE_TTL = timedelta(days=7)


class TTSJob(BaseModel):
  id: str
  room_code: str
  round_id: str
  status: str
  model: str
  voice_id: str
  cache_key: str
  audio_key: Optional[str]
  audio_content_type: Optional[str]
  error_code: Optional[str]
  error_message: Optional[str]
  from_cache: bool
  playback_state: str
  created_at: datetime
  updated_at: datetime


@dataclass
class TTSAudio:
  audio_key: str
  content_type: str
  created_at: datetime


TTS_JOBS: Dict[str, TTSJob] = {}
TTS_CACHE: Dict[str, TTSAudio] = {}
ROOM_TTS: Dict[tuple[str, str], str] = {}
_LOCK = threading.Lock()
_TRACER = trace.get_tracer(__name__)


def _cache_key(story: str, model: str, voice_id: str) -> str:
  payload = f"{story}|{model}|{voice_id}|{TTS_VERSION}".encode("utf-8")
  return hashlib.sha256(payload).hexdigest()


def _moderation_block_reason(story: str) -> Optional[str]:
  if not story:
    record_moderation_event("story", "block", "empty_story")
    return "Narration is unavailable because the story is empty."
  # Keep the messaging specific to narration, but rely on the shared moderation policy.
  reason = moderation_block_reason(story)
  record_moderation_event(
    "story",
    "block" if reason else "pass",
    "blocked_language" if reason else None,
  )
  return "Narration is disabled because the story contains blocked language." if reason else None


def _response_format() -> str:
  return TTS_RESPONSE_FORMAT or "mp3"


def _content_type(format_name: str) -> str:
  mapping = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
  }
  return mapping.get(format_name.lower(), "application/octet-stream")


def _content_type_from_key(audio_key: str) -> str:
  if not audio_key or "." not in audio_key:
    return "application/octet-stream"
  extension = audio_key.rsplit(".", maxsplit=1)[-1]
  return _content_type(extension)


def _storage_key(room_code: str, round_id: str, cache_key: str, response_format: str) -> str:
  extension = response_format.lower()
  return f"room/{room_code}/round/{round_id}/{cache_key}.{extension}"


def _persist_job(job: TTSJob) -> None:
  try:
    db = SessionLocal()
  except Exception:
    return

  try:
    row = db.query(TTSJobRow).filter(TTSJobRow.id == job.id).one_or_none()
    if row is None:
      row = TTSJobRow(
        id=job.id,
        round_id=None,  # Current app round ids are not DB UUIDs yet.
        provider=job.model,
        voice_id=job.voice_id,
        cache_key=job.cache_key,
        status=job.status,
        audio_object_key=job.audio_key,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
      )
      db.add(row)
    else:
      row.provider = job.model
      row.voice_id = job.voice_id
      row.cache_key = job.cache_key
      row.status = job.status
      row.audio_object_key = job.audio_key
      row.error_code = job.error_code
      row.error_message = job.error_message
      row.updated_at = job.updated_at
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _persist_cache(cache_key: str, audio_key: str) -> None:
  try:
    db = SessionLocal()
  except Exception:
    return

  expires_at = _now() + TTS_CACHE_TTL
  try:
    row = db.query(TTSCacheRow).filter(TTSCacheRow.cache_key == cache_key).one_or_none()
    if row is None:
      row = TTSCacheRow(cache_key=cache_key, audio_object_key=audio_key, expires_at=expires_at)
      db.add(row)
    else:
      row.audio_object_key = audio_key
      row.expires_at = expires_at
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _get_cached_audio(cache_key: str) -> Optional[TTSAudio]:
  with _LOCK:
    cached = TTS_CACHE.get(cache_key)
  if cached and object_exists(cached.audio_key):
    return cached
  if cached:
    with _LOCK:
      TTS_CACHE.pop(cache_key, None)

  try:
    db = SessionLocal()
  except Exception:
    return None

  try:
    row = db.query(TTSCacheRow).filter(TTSCacheRow.cache_key == cache_key).one_or_none()
  finally:
    db.close()

  if not row or not row.audio_object_key:
    return None
  if row.expires_at and row.expires_at <= _now():
    return None
  if not object_exists(row.audio_object_key):
    return None

  cached = TTSAudio(
    audio_key=row.audio_object_key,
    content_type=_content_type_from_key(row.audio_object_key),
    created_at=_now(),
  )
  with _LOCK:
    TTS_CACHE[cache_key] = cached
  return cached


def _update_job(job_id: str, **updates) -> Optional[TTSJob]:
  job = TTS_JOBS.get(job_id)
  if not job:
    return None
  payload = job.model_dump()
  payload.update(updates)
  payload["updated_at"] = _now()
  updated = TTSJob(**payload)
  TTS_JOBS[job_id] = updated
  _persist_job(updated)
  return updated


def clear_room_tts(room_code: str, round_id: str) -> None:
  key = (room_code, round_id)
  with _LOCK:
    job_id = ROOM_TTS.pop(key, None)
    if job_id:
      TTS_JOBS.pop(job_id, None)


def purge_room_tts(room_code: str) -> None:
  audio_keys: list[str] = []
  with _LOCK:
    for job_id, job in list(TTS_JOBS.items()):
      if job.room_code != room_code:
        continue
      if job.audio_key:
        audio_keys.append(job.audio_key)
      TTS_JOBS.pop(job_id, None)
    for key in list(ROOM_TTS.keys()):
      if key[0] == room_code:
        ROOM_TTS.pop(key, None)
    for cache_key, cached in list(TTS_CACHE.items()):
      if cached.audio_key in audio_keys:
        TTS_CACHE.pop(cache_key, None)

  for audio_key in audio_keys:
    if not audio_key:
      continue
    try:
      delete_object(audio_key)
    except Exception:
      continue


def get_room_job(room_code: str, round_id: str) -> Optional[TTSJob]:
  job_id = ROOM_TTS.get((room_code, round_id))
  if not job_id:
    return None
  return TTS_JOBS.get(job_id)


def get_job(job_id: str) -> Optional[TTSJob]:
  return TTS_JOBS.get(job_id)


def get_audio_stream(job_id: str) -> Optional[Tuple[object, str, int]]:
  job = TTS_JOBS.get(job_id)
  if not job or job.status != "ready" or not job.audio_key:
    return None
  try:
    response = get_object(job.audio_key)
  except Exception:
    return None
  body = response.get("Body")
  content_type = response.get("ContentType") or job.audio_content_type or "application/octet-stream"
  content_length = response.get("ContentLength") or 0
  return body, content_type, content_length


def request_narration(
  room_code: str,
  round_id: str,
  story: str,
  model: Optional[str] = None,
  voice_id: Optional[str] = None,
) -> TTSJob:
  model = model or TTS_DEFAULT_MODEL
  voice_id = voice_id or TTS_DEFAULT_VOICE

  with _LOCK:
    existing = get_room_job(room_code, round_id)
    if existing and existing.status in {"queued", "generating", "ready", "blocked"}:
      return existing

  block_reason = _moderation_block_reason(story)
  cache_key = _cache_key(story, model, voice_id)

  if block_reason:
    block_message = f"{block_reason} Narration is disabled for this round."
    job = TTSJob(
      id=_new_id("tts"),
      room_code=room_code,
      round_id=round_id,
      status="blocked",
      model=model,
      voice_id=voice_id,
      cache_key=cache_key,
      audio_key=None,
      audio_content_type=None,
      error_code="safety_blocked",
      error_message=block_message,
      from_cache=False,
      playback_state="idle",
      created_at=_now(),
      updated_at=_now(),
    )
    with _LOCK:
      existing = get_room_job(room_code, round_id)
      if existing and existing.status in {"queued", "generating", "ready", "blocked"}:
        return existing
      TTS_JOBS[job.id] = job
      ROOM_TTS[(room_code, round_id)] = job.id
    _persist_job(job)
    return job

  cached = _get_cached_audio(cache_key)
  if cached:
    job = TTSJob(
      id=_new_id("tts"),
      room_code=room_code,
      round_id=round_id,
      status="ready",
      model=model,
      voice_id=voice_id,
      cache_key=cache_key,
      audio_key=cached.audio_key,
      audio_content_type=cached.content_type,
      error_code=None,
      error_message=None,
      from_cache=True,
      playback_state="idle",
      created_at=_now(),
      updated_at=_now(),
    )
    with _LOCK:
      existing = get_room_job(room_code, round_id)
      if existing and existing.status in {"queued", "generating", "ready", "blocked"}:
        return existing
      TTS_JOBS[job.id] = job
      ROOM_TTS[(room_code, round_id)] = job.id
    _persist_job(job)
    return job

  job = TTSJob(
    id=_new_id("tts"),
    room_code=room_code,
    round_id=round_id,
    status="queued",
    model=model,
    voice_id=voice_id,
    cache_key=cache_key,
    audio_key=None,
    audio_content_type=None,
    error_code=None,
    error_message=None,
    from_cache=False,
    playback_state="idle",
    created_at=_now(),
    updated_at=_now(),
  )
  with _LOCK:
    existing = get_room_job(room_code, round_id)
    if existing and existing.status in {"queued", "generating", "ready", "blocked"}:
      return existing
    TTS_JOBS[job.id] = job
    ROOM_TTS[(room_code, round_id)] = job.id
  _persist_job(job)

  def _worker(job_id: str, story_text: str, cache_key_value: str, model_name: str, voice: str) -> None:
    response_format = _response_format()
    try:
      with _LOCK:
        _update_job(job_id, status="generating")

      payload = {
        "model": model_name,
        "input": story_text,
        "voice": voice,
        "response_format": response_format,
      }

      with _TRACER.start_as_current_span("tts.provider.call") as span:
        span.set_attribute("tts.model", model_name)
        span.set_attribute("tts.voice", voice)
        span.set_attribute("tts.response_format", response_format)
        span.set_attribute("tts.service_url", TTS_SERVICE_URL)
        with httpx.Client(timeout=60.0) as client:
          response = client.post(f"{TTS_SERVICE_URL}/v1/audio/speech", json=payload)
        span.set_attribute("http.status_code", response.status_code)
        if response.status_code >= 400:
          raise RuntimeError(response.text or "Narration provider error.")

      audio_bytes = response.content
      content_type = response.headers.get("content-type") or _content_type(response_format)

      audio_key = _storage_key(room_code, round_id, cache_key_value, response_format)
      with _TRACER.start_as_current_span("tts.storage.put"):
        put_object(audio_key, audio_bytes, content_type)

      with _LOCK:
        TTS_CACHE[cache_key_value] = TTSAudio(
          audio_key=audio_key,
          content_type=content_type,
          created_at=_now(),
        )
        _update_job(
          job_id,
          status="ready",
          audio_key=audio_key,
          audio_content_type=content_type,
        )
      _persist_cache(cache_key_value, audio_key)
    except Exception as exc:  # pragma: no cover - defensive
      with _LOCK:
        _update_job(
          job_id,
          status="error",
          error_code="generation_failed",
          error_message=str(exc) or "Narration failed unexpectedly.",
        )

  thread = threading.Thread(
    target=_worker, args=(job.id, story, cache_key, model, voice_id), daemon=True
  )
  thread.start()
  return job


def update_playback_state(job_id: str, action: str) -> Optional[TTSJob]:
  mapping = {
    "play": "playing",
    "resume": "playing",
    "pause": "paused",
    "stop": "stopped",
    "complete": "complete",
  }
  if action not in mapping:
    return None
  with _LOCK:
    return _update_job(job_id, playback_state=mapping[action])


def tts_metrics() -> dict:
  with _LOCK:
    jobs = list(TTS_JOBS.values())
    jobs_by_status: dict[str, int] = {}
    for job in jobs:
      jobs_by_status[job.status] = jobs_by_status.get(job.status, 0) + 1
    return {
      "requests_total": len(jobs),
      "jobs_by_status": jobs_by_status,
      "cache_items": len(TTS_CACHE),
    }
