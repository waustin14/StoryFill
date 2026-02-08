from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.rate_limit import check_rate_limit
from app.data.tts import get_audio_stream, get_job, request_narration, update_playback_state

router = APIRouter(prefix="/v1", tags=["tts"])


class TTSJobStatusResponse(BaseModel):
  job_id: str
  status: str
  playback_state: str | None = None
  audio_url: str | None = None
  error_code: str | None = None
  error_message: str | None = None
  from_cache: bool | None = None


class TTSGenerateRequest(BaseModel):
  story: str
  session_id: str | None = None
  round_id: str | None = None


class TTSPlaybackRequest(BaseModel):
  action: str


def _job_response(job) -> TTSJobStatusResponse:
  audio_url = f"/v1/tts/jobs/{job.id}/audio" if job.status == "ready" and job.audio_key else None
  return TTSJobStatusResponse(
    job_id=job.id,
    status="from_cache" if job.from_cache and job.status == "ready" else job.status,
    playback_state=job.playback_state,
    audio_url=audio_url,
    error_code=job.error_code,
    error_message=job.error_message,
    from_cache=job.from_cache,
  )


@router.post("/tts/generate", response_model=TTSJobStatusResponse)
def generate_tts_handler(payload: TTSGenerateRequest, request: Request):
  client_ip = request.client.host if request.client else "unknown"
  result = check_rate_limit(f"ip:{client_ip}:solo_tts", limit=4, window_seconds=300)
  if not result.allowed:
    headers = {"Retry-After": str(result.retry_after)} if result.retry_after else None
    raise HTTPException(
      status_code=429,
      detail="Narration requests are rate limited. Please wait a moment and try again.",
      headers=headers,
    )
  session_id = payload.session_id or f"solo_{uuid4().hex[:12]}"
  round_id = payload.round_id or f"round_{uuid4().hex[:12]}"
  job = request_narration(session_id, round_id, payload.story)
  return _job_response(job)


@router.get("/tts/jobs/{job_id}", response_model=TTSJobStatusResponse)
def job_status_handler(job_id: str):
  job = get_job(job_id)
  if not job:
    raise HTTPException(status_code=404, detail="TTS job not found.")
  return _job_response(job)


@router.post("/tts/jobs/{job_id}:playback", response_model=TTSJobStatusResponse)
def playback_handler(job_id: str, payload: TTSPlaybackRequest):
  job = update_playback_state(job_id, payload.action)
  if not job:
    raise HTTPException(status_code=400, detail="Invalid playback action or job not found.")
  return _job_response(job)


@router.get("/tts/jobs/{job_id}/audio")
def audio_handler(job_id: str):
  job = get_job(job_id)
  stream = get_audio_stream(job_id)
  if not stream or not job:
    raise HTTPException(status_code=404, detail="Audio not available.")
  body, content_type, content_length = stream
  filename = "storyfill-narration"
  if job.audio_key and "." in job.audio_key:
    extension = job.audio_key.rsplit(".", maxsplit=1)[-1]
    filename = f"{filename}.{extension}"
  headers = {
    "Content-Disposition": f"attachment; filename={filename}",
  }
  if content_length:
    headers["Content-Length"] = str(content_length)
  return StreamingResponse(body, media_type=content_type, headers=headers)
