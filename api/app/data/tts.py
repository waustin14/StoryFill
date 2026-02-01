from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import threading
import time
from typing import Dict, Optional, Tuple

import httpx
from pydantic import BaseModel
from opentelemetry import trace

from app.core.config import (
  TTS_DEFAULT_MODEL,
  TTS_DEFAULT_VOICE,
  TTS_RESPONSE_FORMAT,
  TTS_SERVICE_URL,
)
from app.storage.minio import delete_object, get_object, object_exists, put_object


def _now() -> datetime:
  return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
  token = hashlib.sha256(f"{prefix}:{time.time_ns()}".encode("utf-8")).hexdigest()
  return f"{prefix}_{token[:12]}"


BLOCKED_TERMS = {
  "fuck",
  "shit",
  "bitch",
  "cunt",
  "rape",
  "porn",
  "nazi",
  "terrorist",
}

TTS_VERSION = "v2"


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
    return "Narration is unavailable because the story is empty."
  normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", story).lower()
  for term in BLOCKED_TERMS:
    if re.search(rf"\b{re.escape(term)}\b", normalized):
      return "Narration is disabled because the story contains blocked language."
  return None


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


def _storage_key(room_code: str, round_id: str, cache_key: str, response_format: str) -> str:
  extension = response_format.lower()
  return f"room/{room_code}/round/{round_id}/{cache_key}.{extension}"


def _update_job(job_id: str, **updates) -> Optional[TTSJob]:
  job = TTS_JOBS.get(job_id)
  if not job:
    return None
  payload = job.model_dump()
  payload.update(updates)
  payload["updated_at"] = _now()
  updated = TTSJob(**payload)
  TTS_JOBS[job_id] = updated
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
    if not audio_key.startswith(f"room/{room_code}/"):
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
      TTS_JOBS[job.id] = job
      ROOM_TTS[(room_code, round_id)] = job.id
    return job

  cached = TTS_CACHE.get(cache_key)
  if cached and object_exists(cached.audio_key):
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
      TTS_JOBS[job.id] = job
      ROOM_TTS[(room_code, round_id)] = job.id
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
    TTS_JOBS[job.id] = job
    ROOM_TTS[(room_code, round_id)] = job.id

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
      header_key = response.headers.get("x-storyfill-audio-key")
      header_type = response.headers.get("content-type")
      content_type = header_type or _content_type(response_format)

      audio_key = header_key
      if not audio_key:
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
