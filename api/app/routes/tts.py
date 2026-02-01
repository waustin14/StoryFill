from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.data.tts import get_audio_stream, get_job, update_playback_state

router = APIRouter(prefix="/v1", tags=["tts"])


class TTSJobStatusResponse(BaseModel):
  job_id: str
  status: str
  playback_state: str | None = None
  audio_url: str | None = None
  error_code: str | None = None
  error_message: str | None = None
  from_cache: bool | None = None


class TTSPlaybackRequest(BaseModel):
  action: str


def _job_response(job) -> TTSJobStatusResponse:
  audio_url = f"/tts/audio/{job.id}" if job.status == "ready" and job.audio_key else None
  return TTSJobStatusResponse(
    job_id=job.id,
    status="from_cache" if job.from_cache and job.status == "ready" else job.status,
    playback_state=job.playback_state,
    audio_url=audio_url,
    error_code=job.error_code,
    error_message=job.error_message,
    from_cache=job.from_cache,
  )


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
