from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_local_rate_limits_for_tests
from app.data.rooms import ensure_prompts_assigned, get_room, reset_rooms_for_tests, save_room
from app.main import app

client = TestClient(app)


def setup_function():
  reset_rooms_for_tests()
  reset_local_rate_limits_for_tests()


def _create_room():
  response = client.post("/v1/rooms", json={"template_id": "t-forest-mishap"})
  assert response.status_code == 200
  return response.json()


def _join_room(room_code: str):
  response = client.post(f"/v1/rooms/{room_code}/join", json={"display_name": "Alex"})
  assert response.status_code == 200
  return response.json()

def _start_room(room_code: str, host_token: str):
  response = client.post(f"/v1/rooms/{room_code}/start", json={"host_token": host_token})
  assert response.status_code == 200
  return response.json()


def test_prompt_submit_rejects_blocked_language():
  room = _create_room()
  join = _join_room(room["room_code"])
  _start_room(room["room_code"], room["host_token"])
  prompts = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"], "player_token": join["player_token"]},
  )
  assert prompts.status_code == 200
  prompt_id = prompts.json()["prompts"][0]["id"]

  submit = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts/{prompt_id}:submit",
    json={"player_id": join["player_id"], "player_token": join["player_token"], "value": "f u c k"},
  )
  assert submit.status_code == 400


def test_reveal_rejects_blocked_story_and_does_not_persist():
  room = _create_room()
  join = _join_room(room["room_code"])

  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  ensure_prompts_assigned(room_obj)
  now = datetime.now(timezone.utc)
  # Force a blocked term into one prompt (for the joined player) and mark
  # every other prompt submitted so reveal reaches story generation.
  for prompt in room_obj.prompts:
    if not prompt.assigned_to:
      continue
    if prompt.assigned_to == join["player_id"]:
      prompt.value = "shit"
    else:
      prompt.value = "test"
    prompt.submitted_at = now
  save_room(room_obj)

  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 400

  story = client.get(f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/story")
  assert story.status_code == 409

  room_obj = get_room(room["room_code"])
  assert room_obj is not None
  assert room_obj.revealed_story is None
