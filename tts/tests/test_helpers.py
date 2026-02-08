import pytest
from fastapi import HTTPException

from app.main import _content_type, _parse_model, _provider_config


def test_parse_model_supports_explicit_provider():
  provider, model = _parse_model("openai/gpt-4o-mini-tts")
  assert provider == "openai"
  assert model == "gpt-4o-mini-tts"


def test_parse_model_uses_default_provider(monkeypatch):
  monkeypatch.setenv("TTS_DEFAULT_PROVIDER", "openai")
  provider, model = _parse_model("gpt-4o-mini-tts")
  assert provider == "openai"
  assert model == "gpt-4o-mini-tts"


def test_content_type_mapping():
  assert _content_type("mp3") == "audio/mpeg"
  assert _content_type("wav") == "audio/wav"


def test_provider_config_requires_env_for_unknown_provider():
  with pytest.raises(HTTPException):
    _provider_config("unknown")
