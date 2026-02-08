from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_local_rate_limits_for_tests
from app.data.rooms import PROMPTS_PER_PLAYER, ROOM_TTL, get_room, reset_rooms_for_tests, save_room
from app.data.tts import ROOM_TTS, TTS_CACHE, TTS_JOBS
from app.main import app

client = TestClient(app)


def setup_function():
  reset_rooms_for_tests()
  TTS_JOBS.clear()
  TTS_CACHE.clear()
  ROOM_TTS.clear()
  reset_local_rate_limits_for_tests()


def _create_room(display_name: str | None = None):
  payload = {"template_id": "t-forest-mishap"}
  if display_name:
    payload["display_name"] = display_name
  response = client.post("/v1/rooms", json=payload)
  assert response.status_code == 200
  return response.json()


def _join_room(room_code: str, display_name: str = "Alex"):
  response = client.post(f"/v1/rooms/{room_code}/join", json={"display_name": display_name})
  assert response.status_code == 200
  return response.json()


def _start_room(room_code: str, host_token: str):
  return client.post(f"/v1/rooms/{room_code}/start", json={"host_token": host_token})


def _set_template(room_code: str, host_token: str, template_id: str):
  return client.post(
    f"/v1/rooms/{room_code}:template",
    json={"host_token": host_token, "template_id": template_id},
  )


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


def test_room_creation_and_join_flow():
  room = _create_room("Host")
  join = _join_room(room["room_code"], "Guest")
  players = join["room_snapshot"]["players"]
  assert len(players) == 2
  assert any(player["display_name"] == "Host" for player in players)
  assert any(player["display_name"] == "Guest" for player in players)


def test_progress_tracking_updates_with_submissions():
  room = _create_room()
  join = _join_room(room["room_code"])
  started = _start_room(room["room_code"], room["host_token"])
  assert started.status_code == 200

  progress = client.get(f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/progress")
  assert progress.status_code == 200
  metrics = progress.json()
  assert metrics["assigned_total"] == PROMPTS_PER_PLAYER * 2
  assert metrics["submitted_total"] == 0
  assert metrics["ready_to_reveal"] is False

  prompts = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"], "player_token": join["player_token"]},
  )
  prompt_id = prompts.json()["prompts"][0]["id"]
  submit = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts/{prompt_id}:submit",
    json={"player_id": join["player_id"], "player_token": join["player_token"], "value": "test"},
  )
  assert submit.status_code == 200

  progress = client.get(f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/progress")
  metrics = progress.json()
  assert metrics["submitted_total"] == 1
  assert metrics["ready_to_reveal"] is False


def test_host_actions_lock_unlock_and_kick():
  room = _create_room()
  join = _join_room(room["room_code"])

  forbidden = client.post(
    f"/v1/rooms/{room['room_code']}:lock",
    json={"host_token": "bad-token"},
  )
  assert forbidden.status_code == 403

  locked = client.post(
    f"/v1/rooms/{room['room_code']}:lock",
    json={"host_token": room["host_token"]},
  )
  assert locked.status_code == 200
  assert locked.json()["locked"] is True

  blocked_join = client.post(
    f"/v1/rooms/{room['room_code']}/join",
    json={"display_name": "Late"},
  )
  assert blocked_join.status_code == 403

  unlocked = client.post(
    f"/v1/rooms/{room['room_code']}:unlock",
    json={"host_token": room["host_token"]},
  )
  assert unlocked.status_code == 200
  assert unlocked.json()["locked"] is False

  kicked = client.post(
    f"/v1/rooms/{room['room_code']}/players/{join['player_id']}:kick",
    json={"host_token": room["host_token"]},
  )
  assert kicked.status_code == 200
  assert len(kicked.json()["players"]) == 1


def test_host_can_update_template_in_lobby():
  room = _create_room()
  response = _set_template(room["room_code"], room["host_token"], "t-space-diner")
  assert response.status_code == 200
  assert response.json()["template_id"] == "t-space-diner"
  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  assert room_obj.template_id == "t-space-diner"


def test_template_update_blocked_after_start():
  room = _create_room()
  _join_room(room["room_code"])
  started = _start_room(room["room_code"], room["host_token"])
  assert started.status_code == 200
  response = _set_template(room["room_code"], room["host_token"], "t-space-diner")
  assert response.status_code == 409


def test_share_link_generation_and_retrieval():
  room = _create_room()
  join = _join_room(room["room_code"])
  _start_room(room["room_code"], room["host_token"])
  _submit_all_prompts(room["room_code"], room["round_id"], room["player_id"], room["player_token"])
  _submit_all_prompts(room["room_code"], room["round_id"], join["player_id"], join["player_token"])

  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 200
  rendered_story = reveal.json()["rendered_story"]

  share = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}:share",
    json={"host_token": room["host_token"]},
  )
  assert share.status_code == 200
  share_payload = share.json()
  assert share_payload["share_token"]
  assert "/s/" in share_payload["share_url"]

  artifact = client.get(f"/v1/shares/{share_payload['share_token']}")
  assert artifact.status_code == 200
  artifact_payload = artifact.json()
  assert artifact_payload["rendered_story"] == rendered_story


def test_rate_limit_enforced_for_room_creation():
  responses = []
  for _ in range(6):
    responses.append(client.post("/v1/rooms", json={"template_id": "t-forest-mishap"}))
  assert responses[-1].status_code == 429


def test_room_expiry_returns_410_and_clears_room():
  room = _create_room()
  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  room_obj.updated_at = datetime.now(timezone.utc) - ROOM_TTL - timedelta(seconds=5)
  save_room(room_obj)

  snapshot = client.get(
    f"/v1/rooms/{room['room_code']}:snapshot",
    params={"host_token": room["host_token"]},
  )
  assert snapshot.status_code == 410
  assert get_room(room["room_code"]) is None
