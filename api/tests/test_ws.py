import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


def test_ws_rejects_invalid_token():
  room = _create_room()
  _join_room(room["room_code"])
  with pytest.raises(WebSocketDisconnect) as exc_info:
    with client.websocket_connect(f"/v1/ws?room_code={room['room_code']}&token=bad-token") as ws:
      ws.receive_text()
  assert exc_info.value.code == 4403


def test_ws_sends_snapshot_with_request_id():
  room = _create_room()
  with client.websocket_connect(f"/v1/ws?room_code={room['room_code']}&token={room['host_token']}") as ws:
    payload = ws.receive_json()

  assert payload["type"] == "room.snapshot"
  assert payload["room_code"] == room["room_code"]
  assert payload["round_id"] == room["round_id"]
  assert isinstance(payload.get("request_id"), str)
  assert payload.get("request_id")
  assert "payload" in payload
  assert "room_snapshot" in payload["payload"]
  assert "progress" in payload["payload"]
