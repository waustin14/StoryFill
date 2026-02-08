from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import TTS_DEFAULT_MODEL, TTS_DEFAULT_VOICE
from app.core.rate_limit import reset_local_rate_limits_for_tests
from app.data.rooms import get_room, reset_rooms_for_tests, save_room
from app.data.tts import ROOM_TTS, TTS_CACHE, TTS_JOBS, TTSAudio, _cache_key
from app.main import app

client = TestClient(app)


def setup_function():
  reset_rooms_for_tests()
  TTS_JOBS.clear()
  TTS_CACHE.clear()
  ROOM_TTS.clear()
  reset_local_rate_limits_for_tests()


def _create_room():
  response = client.post("/v1/rooms", json={"template_id": "t-forest-mishap"})
  assert response.status_code == 200
  return response.json()


def test_tts_request_blocks_on_moderation():
  room = _create_room()
  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  room_obj.revealed_story = "this is shit"
  save_room(room_obj)

  response = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:tts",
    json={"host_token": room["host_token"]},
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["status"] == "blocked"
  assert payload["error_code"] == "safety_blocked"


def test_tts_request_uses_cache_and_status_endpoint(monkeypatch):
  room = _create_room()
  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  room_obj.revealed_story = "A safe story for narration."
  save_room(room_obj)

  cache_key = _cache_key(room_obj.revealed_story, TTS_DEFAULT_MODEL, TTS_DEFAULT_VOICE)
  TTS_CACHE[cache_key] = TTSAudio(
    audio_key="room/test-cache.mp3",
    content_type="audio/mpeg",
    created_at=datetime.now(timezone.utc),
  )
  monkeypatch.setattr("app.data.tts.object_exists", lambda key: True)

  response = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:tts",
    json={
      "host_token": room["host_token"],
      "model": TTS_DEFAULT_MODEL,
      "voice_id": TTS_DEFAULT_VOICE,
    },
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["status"] in {"from_cache", "ready"}
  assert payload["from_cache"] is True

  status = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/tts",
  )
  assert status.status_code == 200
  status_payload = status.json()
  assert status_payload["job_id"] == payload["job_id"]
