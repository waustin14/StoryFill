import time

import jwt as pyjwt

from app.core.config import JWT_SECRET
from app.core.jwt import create_host_token, create_player_token, decode_token


def test_host_token_round_trip():
  token = create_host_token("room_1", "ABC123", 3600, "jti_1")
  claims = decode_token(token)
  assert claims is not None
  assert claims["role"] == "host"
  assert claims["room_id"] == "room_1"
  assert claims["room_code"] == "ABC123"
  assert claims["jti"] == "jti_1"
  assert "iat" in claims
  assert "exp" in claims


def test_player_token_round_trip():
  token = create_player_token("room_1", "ABC123", "player_1", 3600, "jti_2")
  claims = decode_token(token)
  assert claims is not None
  assert claims["role"] == "player"
  assert claims["room_id"] == "room_1"
  assert claims["room_code"] == "ABC123"
  assert claims["player_id"] == "player_1"
  assert claims["jti"] == "jti_2"


def test_expired_token_returns_none():
  token = create_host_token("room_1", "ABC123", 0, "jti_3")
  time.sleep(1)
  claims = decode_token(token)
  assert claims is None


def test_wrong_secret_returns_none():
  token = create_host_token("room_1", "ABC123", 3600, "jti_4")
  tampered = pyjwt.encode(
    pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"]),
    "wrong-secret",
    algorithm="HS256",
  )
  claims = decode_token(tampered)
  assert claims is None


def test_host_token_missing_player_id():
  token = create_host_token("room_1", "ABC123", 3600, "jti_5")
  claims = decode_token(token)
  assert claims is not None
  assert "player_id" not in claims


def test_player_token_has_player_role():
  token = create_player_token("room_1", "ABC123", "player_1", 3600, "jti_6")
  claims = decode_token(token)
  assert claims is not None
  assert claims["role"] == "player"
  # A player token should not pass host validation
  assert claims["role"] != "host"


def test_garbage_token_returns_none():
  assert decode_token("not-a-jwt") is None
  assert decode_token("") is None
