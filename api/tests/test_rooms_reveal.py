from fastapi.testclient import TestClient

from app.data.rooms import ROOMS
from app.main import app

client = TestClient(app)


def setup_function():
  ROOMS.clear()


def _create_room():
  response = client.post("/v1/rooms", json={"template_id": "t-forest-mishap"})
  assert response.status_code == 200
  return response.json()


def _join_room(room_code: str):
  response = client.post(f"/v1/rooms/{room_code}/join", json={"display_name": "Alex"})
  assert response.status_code == 200
  return response.json()


def _submit_all_prompts(room_code: str, round_id: str, player_id: str):
  response = client.get(
    f"/v1/rooms/{room_code}/rounds/{round_id}/prompts",
    params={"player_id": player_id},
  )
  assert response.status_code == 200
  prompts = response.json()["prompts"]
  for prompt in prompts:
    submit = client.post(
      f"/v1/rooms/{room_code}/rounds/{round_id}/prompts/{prompt['id']}:submit",
      json={"player_id": player_id, "value": "test"},
    )
    assert submit.status_code == 200


def test_reveal_requires_host_and_locks_story():
  room = _create_room()
  join = _join_room(room["room_code"])
  _submit_all_prompts(room["room_code"], room["round_id"], join["player_id"])

  forbidden = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": "bad-token"},
  )
  assert forbidden.status_code == 403

  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 200
  rendered_story = reveal.json()["rendered_story"]
  assert rendered_story

  story = client.get(f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/story")
  assert story.status_code == 200
  assert story.json()["rendered_story"] == rendered_story

  prompts = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"]},
  )
  prompt_id = prompts.json()["prompts"][0]["id"]
  submit = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts/{prompt_id}:submit",
    json={"player_id": join["player_id"], "value": "late"},
  )
  assert submit.status_code == 409


def test_reveal_requires_all_prompts():
  room = _create_room()
  join = _join_room(room["room_code"])
  response = client.get(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts",
    params={"player_id": join["player_id"]},
  )
  prompt_id = response.json()["prompts"][0]["id"]
  submit = client.post(
    f"/v1/rooms/{room['room_code']}/rounds/{room['round_id']}/prompts/{prompt_id}:submit",
    json={"player_id": join["player_id"], "value": "test"},
  )
  assert submit.status_code == 200

  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 409


def test_replay_resets_round_and_story():
  room = _create_room()
  join = _join_room(room["room_code"])
  _submit_all_prompts(room["room_code"], room["round_id"], join["player_id"])
  reveal = client.post(
    f"/v1/rooms/{room['room_code']}/reveal",
    json={"host_token": room["host_token"]},
  )
  assert reveal.status_code == 200

  replay = client.post(
    f"/v1/rooms/{room['room_code']}/replay",
    json={"host_token": room["host_token"]},
  )
  assert replay.status_code == 200
  new_round_id = replay.json()["round_id"]
  assert new_round_id != room["round_id"]

  story = client.get(f"/v1/rooms/{room['room_code']}/rounds/{new_round_id}/story")
  assert story.status_code == 409
