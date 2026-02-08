from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import TTS_DEFAULT_MODEL, TTS_DEFAULT_VOICE
from app.core.rate_limit import reset_local_rate_limits_for_tests
from app.data.rooms import reset_rooms_for_tests
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


def _join_room(room_code: str, display_name: str = "Alex"):
  response = client.post(f"/v1/rooms/{room_code}/join", json={"display_name": display_name})
  assert response.status_code == 200
  return response.json()


def _start_room(room_code: str, host_token: str):
  response = client.post(f"/v1/rooms/{room_code}/start", json={"host_token": host_token})
  assert response.status_code == 200
  return response.json()


def _submit_all_prompts(room_code: str, round_id: str, player_id: str, player_token: str):
  response = client.get(
    f"/v1/rooms/{room_code}/rounds/{round_id}/prompts",
    params={"player_id": player_id, "player_token": player_token},
  )
  assert response.status_code == 200
  prompts = response.json()["prompts"]
  for prompt in prompts:
    submit = client.post(
      f"/v1/rooms/{room_code}/rounds/{round_id}/prompts/{prompt['id']}:submit",
      json={"player_id": player_id, "player_token": player_token, "value": "test"},
    )
    assert submit.status_code == 200


def test_multiplayer_flow_end_to_end_with_share_and_tts_cache(monkeypatch):
  room = _create_room()
  join = _join_room(room["room_code"], "Guest")
  _start_room(room["room_code"], room["host_token"])

  _submit_all_prompts(room["room_code"], room["round_id"], room["player_id"], room["player_token"])
  _submit_all_prompts(room["room_code"], room["round_id"], join["player_id"], join["player_token"])

  progress = client.get(f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/progress")
  assert progress.status_code == 200
  assert progress.json()["ready_to_reveal"] is True

  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 200
  story = reveal.json()["rendered_story"]

  share = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:share",
    json={"host_token": room["host_token"]},
  )
  assert share.status_code == 200
  token = share.json()["share_token"]
  artifact = client.get(f"/v1/shares/{token}")
  assert artifact.status_code == 200
  assert artifact.json()["rendered_story"] == story

  cache_key = _cache_key(story, TTS_DEFAULT_MODEL, TTS_DEFAULT_VOICE)
  TTS_CACHE[cache_key] = TTSAudio(
    audio_key="room/integration-cache.mp3",
    content_type="audio/mpeg",
    created_at=datetime.now(timezone.utc),
  )
  monkeypatch.setattr("app.data.tts.object_exists", lambda key: True)

  tts = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:tts",
    json={"host_token": room["host_token"], "model": TTS_DEFAULT_MODEL, "voice_id": TTS_DEFAULT_VOICE},
  )
  assert tts.status_code == 200
  payload = tts.json()
  assert payload["from_cache"] is True

  tts_again = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:tts",
    json={"host_token": room["host_token"], "model": TTS_DEFAULT_MODEL, "voice_id": TTS_DEFAULT_VOICE},
  )
  assert tts_again.status_code == 200
  assert tts_again.json()["job_id"] == payload["job_id"]


def test_reconnect_and_ws_snapshot_flow():
  room = _create_room()
  join = _join_room(room["room_code"], "Guest")
  _start_room(room["room_code"], room["host_token"])

  prompts = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"], "player_token": join["player_token"]},
  )
  assert prompts.status_code == 200

  disconnect = client.post(
    f"/v1/rooms/{room['room_code']}/players/{join['player_id']}:disconnect",
    json={"player_token": join["player_token"]},
  )
  assert disconnect.status_code == 200

  reconnect = client.post(
    f"/v1/rooms/{room['room_code']}/players/{join['player_id']}:reconnect",
    json={"player_token": join["player_token"]},
  )
  assert reconnect.status_code == 200
  reconnect_payload = reconnect.json()
  assert reconnect_payload["prompts"]

  with client.websocket_connect(
    f"/v1/ws?room_code={room['room_code']}&token={join['player_token']}"
  ) as ws:
    snapshot = ws.receive_json()
  assert snapshot["type"] == "room.snapshot"
  assert snapshot["room_code"] == room["room_code"]
