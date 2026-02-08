from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(title="StoryFill TTS")


class SpeechRequest(BaseModel):
  model: str
  input: str
  voice: str | dict | None = None
  response_format: Optional[str] = None
  format: Optional[str] = None
  speed: Optional[float] = None
  instructions: Optional[str] = None
  language: Optional[str] = None
  stream_format: Optional[str] = None


def _content_type(format_name: str) -> str:
  mapping = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
  }
  return mapping.get(format_name.lower(), "application/octet-stream")


def _parse_model(model: str) -> tuple[str, str]:
  if "/" in model:
    provider, provider_model = model.split("/", 1)
    return provider.lower(), provider_model
  if ":" in model:
    provider, provider_model = model.split(":", 1)
    return provider.lower(), provider_model
  default_provider = os.getenv("TTS_DEFAULT_PROVIDER", "openai")
  return default_provider.lower(), model


def _provider_config(provider: str) -> tuple[str, Optional[str]]:
  provider_upper = provider.upper()
  if provider == "openai":
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
    api_key = os.getenv("OPENAI_API_KEY")
    return base_url, api_key

  base_url = os.getenv(f"TTS_PROVIDER_{provider_upper}_BASE_URL")
  api_key = os.getenv(f"TTS_PROVIDER_{provider_upper}_API_KEY")
  if not base_url:
    raise HTTPException(status_code=400, detail=f"Unknown TTS provider: {provider}.")
  return base_url, api_key


@app.get("/health")
async def health_check():
  return {"status": "ok"}


@app.post("/v1/audio/speech")
async def speech_handler(payload: SpeechRequest):
  provider, provider_model = _parse_model(payload.model)
  base_url, api_key = _provider_config(provider)
  if provider == "openai" and not api_key:
    raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

  response_format = payload.response_format or payload.format or os.getenv("TTS_RESPONSE_FORMAT", "mp3")
  content_type = _content_type(response_format)

  request_body = {
    "model": provider_model,
    "input": payload.input,
    "voice": payload.voice or os.getenv("TTS_DEFAULT_VOICE", "alloy"),
    "response_format": response_format,
  }
  if payload.instructions is not None:
    request_body["instructions"] = payload.instructions
  if payload.language is not None:
    request_body["language"] = payload.language
  if payload.stream_format is not None:
    request_body["stream_format"] = payload.stream_format
  if payload.speed is not None:
    request_body["speed"] = payload.speed

  headers = {}
  if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

  url = f"{base_url.rstrip('/')}/v1/audio/speech"
  async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(url, json=request_body, headers=headers)

  if response.status_code >= 400:
    raise HTTPException(status_code=502, detail=response.text or "TTS provider error.")

  return Response(
    content=response.content,
    media_type=content_type,
  )
