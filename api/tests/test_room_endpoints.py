from fastapi.testclient import TestClient

from app.core.rate_limit import reset_local_rate_limits_for_tests
from app.data.rooms import reset_rooms_for_tests
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


def test_leave_requires_player_token_and_removes_player():
  room = _create_room()
  join = _join_room(room["room_code"])

  bad = client.post(
    f"/v1/rooms/{room['room_code']}/leave",
    json={"player_id": join["player_id"], "player_token": "bad-token"},
  )
  assert bad.status_code == 403

  ok = client.post(
    f"/v1/rooms/{room['room_code']}/leave",
    json={"player_id": join["player_id"], "player_token": join["player_token"]},
  )
  assert ok.status_code == 200

  snapshot = client.get(
    f"/v1/rooms/{room['room_code']}:snapshot",
    params={"host_token": room["host_token"]},
  )
  assert snapshot.status_code == 200
  players = snapshot.json()["players"]
  assert len(players) == 1
  assert players[0]["id"] == room["player_id"]
  assert players[0]["display_name"] == room["player_display_name"]


def test_end_expires_room():
  room = _create_room()
  ended = client.post(f"/v1/rooms/{room['room_code']}/end", json={"host_token": room["host_token"]})
  assert ended.status_code == 200

  snapshot = client.get(f"/v1/rooms/{room['room_code']}:snapshot", params={"host_token": room["host_token"]})
  assert snapshot.status_code == 404


def test_start_returns_snapshot():
  room = _create_room()
  _join_room(room["room_code"])
  started = client.post(f"/v1/rooms/{room['room_code']}/start", json={"host_token": room["host_token"]})
  assert started.status_code == 200
  payload = started.json()
  assert payload["room_code"] == room["room_code"]
  assert payload["round_id"] == room["round_id"]


def test_state_machine_blocks_join_and_prompts_before_start():
  room = _create_room()
  join = _join_room(room["room_code"])

  prompts = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"], "player_token": join["player_token"]},
  )
  assert prompts.status_code == 409

  submit = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts/prompt_fake:submit",
    json={"player_id": join["player_id"], "player_token": join["player_token"], "value": "test"},
  )
  assert submit.status_code == 409

  started = client.post(f"/v1/rooms/{room['room_code']}/start", json={"host_token": room["host_token"]})
  assert started.status_code == 200

  late_join = client.post(f"/v1/rooms/{room['room_code']}/join", json={"display_name": "Late"})
  assert late_join.status_code == 409
