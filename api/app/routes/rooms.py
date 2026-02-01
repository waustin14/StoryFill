from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import WEB_BASE_URL, WS_BASE_URL
from app.core.rate_limit import check_rate_limit
from app.data.rooms import (
  add_player,
  create_room,
  ensure_prompts_assigned,
  expire_room,
  get_room,
  get_player,
  get_player_by_token,
  is_ready_to_reveal,
  mark_connected,
  mark_disconnected,
  player_prompts,
  reclaim_prompts,
  record_room_activity,
  reassign_prompts_if_needed,
  reset_round,
  reveal_story,
  remove_player,
  set_room_locked,
  submit_prompt,
)
from app.data.shares import create_share, get_share
from app.data.templates import get_template_definition
from app.data.tts import get_room_job, request_narration

router = APIRouter(prefix="/v1", tags=["rooms"])

RATE_LIMITS = {
  "create_room": (5, 600),
  "join_room": (12, 300),
  "submit_prompt": (30, 180),
  "tts_request": (4, 300),
}


class CreateRoomResponse(BaseModel):
  room_code: str
  room_id: str
  round_id: str
  host_token: str
  ws_url: str
  template_id: str


class CreateRoomRequest(BaseModel):
  template_id: str | None = None


class JoinRoomRequest(BaseModel):
  display_name: str | None = None


class ReconnectPlayerRequest(BaseModel):
  player_token: str


class PlayerSnapshot(BaseModel):
  id: str
  display_name: str


class RoomSnapshot(BaseModel):
  room_id: str
  room_code: str
  round_id: str
  locked: bool
  template_id: str
  players: list[PlayerSnapshot]


class JoinRoomResponse(BaseModel):
  player_id: str
  player_token: str
  player_display_name: str
  room_snapshot: RoomSnapshot


class PromptSummary(BaseModel):
  id: str
  label: str
  type: str
  submitted: bool


class PromptListResponse(BaseModel):
  prompts: list[PromptSummary]


class SubmitPromptRequest(BaseModel):
  player_id: str
  value: str


class SubmitPromptResponse(BaseModel):
  status: str


class PlayerStatusResponse(BaseModel):
  status: str


class ReconnectPlayerResponse(BaseModel):
  player_id: str
  player_token: str
  player_display_name: str
  room_snapshot: RoomSnapshot
  prompts: list[PromptSummary]


class RoomProgressResponse(BaseModel):
  assigned_total: int
  submitted_total: int
  connected_total: int
  disconnected_total: int
  ready_to_reveal: bool


class RevealRoomRequest(BaseModel):
  host_token: str


class RevealRoomResponse(BaseModel):
  room_id: str
  round_id: str
  rendered_story: str


class ReplayRoomRequest(BaseModel):
  host_token: str


class ReplayRoomResponse(BaseModel):
  room_id: str
  round_id: str


class StoryResponse(BaseModel):
  room_id: str
  round_id: str
  rendered_story: str


class TTSRequest(BaseModel):
  host_token: str
  model: str | None = None
  voice_id: str | None = None


class TTSStatusResponse(BaseModel):
  job_id: str | None
  status: str
  playback_state: str | None = None
  audio_url: str | None = None
  error_code: str | None = None
  error_message: str | None = None
  from_cache: bool | None = None


class ShareRoomRequest(BaseModel):
  host_token: str


class ShareRoomResponse(BaseModel):
  share_token: str
  share_url: str
  expires_at: str


class ShareArtifactResponse(BaseModel):
  share_token: str
  room_code: str
  round_id: str
  rendered_story: str
  expires_at: str


class HostActionRequest(BaseModel):
  host_token: str


def _prompt_rejection_reason(value: str) -> str | None:
  if not value or not value.strip():
    return "Please add a response before submitting."
  for char in value:
    code = ord(char)
    if code < 32 or code > 126:
      return (
        "That response includes characters we can't read yet. "
        "Use letters, numbers, and common punctuation only, and remove emoji or control characters."
      )
  return None


def _require_host(room, host_token: str) -> None:
  if host_token != room.host_token:
    raise HTTPException(status_code=403, detail="Host token required.")


def _rate_limit_or_429(bucket: str, limit: int, window_seconds: int, message: str) -> None:
  result = check_rate_limit(bucket, limit, window_seconds)
  if result.allowed:
    return
  headers = {"Retry-After": str(result.retry_after)} if result.retry_after else None
  raise HTTPException(status_code=429, detail=message, headers=headers)


def _get_room_or_404(room_code: str):
  room = get_room(room_code)
  if not room:
    raise HTTPException(status_code=404, detail="Room not found.")
  if room.is_expired():
    expire_room(room)
    raise HTTPException(status_code=410, detail="Room expired.")
  return room


def _room_snapshot(room) -> RoomSnapshot:
  return RoomSnapshot(
    room_id=room.id,
    room_code=room.code,
    round_id=room.round_id,
    locked=room.locked,
    template_id=room.template_id,
    players=[PlayerSnapshot(id=p.id, display_name=p.display_name) for p in room.players],
  )


def _tts_response(job) -> TTSStatusResponse:
  if not job:
    return TTSStatusResponse(job_id=None, status="idle")
  audio_url = f"/tts/audio/{job.id}" if job.status == "ready" and job.audio_key else None
  return TTSStatusResponse(
    job_id=job.id,
    status="from_cache" if job.from_cache and job.status == "ready" else job.status,
    playback_state=job.playback_state,
    audio_url=audio_url,
    error_code=job.error_code,
    error_message=job.error_message,
    from_cache=job.from_cache,
  )


@router.post("/rooms", response_model=CreateRoomResponse)
def create_room_handler(request: Request, payload: CreateRoomRequest | None = None):
  client_ip = request.client.host if request.client else "unknown"
  limit, window = RATE_LIMITS["create_room"]
  _rate_limit_or_429(
    f"ip:{client_ip}:create_room",
    limit,
    window,
    "Too many rooms created. Please wait a moment and try again.",
  )
  template_id = payload.template_id if payload else None
  if template_id and not get_template_definition(template_id):
    raise HTTPException(status_code=400, detail="Unknown template.")
  room = create_room(template_id)
  return CreateRoomResponse(
    room_code=room.code,
    room_id=room.id,
    round_id=room.round_id,
    host_token=room.host_token,
    ws_url=WS_BASE_URL,
    template_id=room.template_id,
  )


@router.post("/rooms/{room_code}/join", response_model=JoinRoomResponse)
def join_room_handler(room_code: str, payload: JoinRoomRequest, request: Request):
  room = _get_room_or_404(room_code)
  client_ip = request.client.host if request.client else "unknown"
  limit, window = RATE_LIMITS["join_room"]
  _rate_limit_or_429(
    f"ip:{client_ip}:join_room",
    limit,
    window,
    "Too many join attempts. Please wait a moment and try again.",
  )
  if room.locked:
    raise HTTPException(status_code=403, detail="Room locked.")

  player = add_player(room, payload.display_name)
  return JoinRoomResponse(
    player_id=player.id,
    player_token=player.token,
    player_display_name=player.display_name,
    room_snapshot=_room_snapshot(room),
  )


@router.get("/rooms/{room_code}/rounds/{round_id}/prompts", response_model=PromptListResponse)
def list_prompts_handler(room_code: str, round_id: str, player_id: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  if not get_player(room, player_id):
    raise HTTPException(status_code=404, detail="Player not found.")
  record_room_activity(room)
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  prompts = [
    PromptSummary(
      id=prompt.id,
      label=prompt.label,
      type=prompt.type,
      submitted=prompt.is_submitted(),
    )
    for prompt in player_prompts(room, player_id)
  ]
  return PromptListResponse(prompts=prompts)


@router.post(
  "/rooms/{room_code}/rounds/{round_id}/prompts/{prompt_id}:submit",
  response_model=SubmitPromptResponse,
)
def submit_prompt_handler(room_code: str, round_id: str, prompt_id: str, payload: SubmitPromptRequest):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  if room.revealed_story:
    raise HTTPException(status_code=409, detail="Story already revealed.")
  if not get_player(room, payload.player_id):
    raise HTTPException(status_code=404, detail="Player not found.")
  limit, window = RATE_LIMITS["submit_prompt"]
  _rate_limit_or_429(
    f"room:{room.code}:player:{payload.player_id}:submit_prompt",
    limit,
    window,
    "You're submitting too quickly. Please wait a moment and try again.",
  )
  rejection_reason = _prompt_rejection_reason(payload.value)
  if rejection_reason:
    raise HTTPException(status_code=400, detail=rejection_reason)
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  try:
    submit_prompt(room, payload.player_id, prompt_id, payload.value)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  return SubmitPromptResponse(status="ok")


@router.post("/rooms/{room_code}/players/{player_id}:disconnect", response_model=PlayerStatusResponse)
def disconnect_player_handler(room_code: str, player_id: str):
  room = _get_room_or_404(room_code)
  mark_disconnected(room, player_id)
  return PlayerStatusResponse(status="ok")


@router.post("/rooms/{room_code}/players/{player_id}:reconnect", response_model=ReconnectPlayerResponse)
def reconnect_player_handler(room_code: str, player_id: str, payload: ReconnectPlayerRequest):
  room = _get_room_or_404(room_code)
  player = get_player(room, player_id)
  if not player:
    raise HTTPException(status_code=404, detail="Player not found.")
  if player.token != payload.player_token:
    other_player = get_player_by_token(room, payload.player_token)
    if other_player and other_player.id != player_id:
      raise HTTPException(status_code=409, detail="Player token belongs to a different player.")
    raise HTTPException(status_code=403, detail="Player token required.")
  mark_connected(room, player_id)
  ensure_prompts_assigned(room)
  reclaim_prompts(room, player_id)
  prompts = [
    PromptSummary(
      id=prompt.id,
      label=prompt.label,
      type=prompt.type,
      submitted=prompt.is_submitted(),
    )
    for prompt in player_prompts(room, player_id)
  ]
  return ReconnectPlayerResponse(
    player_id=player.id,
    player_token=player.token,
    player_display_name=player.display_name,
    room_snapshot=_room_snapshot(room),
    prompts=prompts,
  )


@router.get("/rooms/{room_code}:snapshot", response_model=RoomSnapshot)
def room_snapshot_handler(room_code: str, host_token: str):
  room = _get_room_or_404(room_code)
  _require_host(room, host_token)
  record_room_activity(room)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}:lock", response_model=RoomSnapshot)
def lock_room_handler(room_code: str, payload: HostActionRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  set_room_locked(room, True)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}:unlock", response_model=RoomSnapshot)
def unlock_room_handler(room_code: str, payload: HostActionRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  set_room_locked(room, False)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}/players/{player_id}:kick", response_model=RoomSnapshot)
def kick_player_handler(room_code: str, player_id: str, payload: HostActionRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  try:
    remove_player(room, player_id)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  return _room_snapshot(room)


@router.get("/rooms/{room_code}/rounds/{round_id}/progress", response_model=RoomProgressResponse)
def room_progress_handler(room_code: str, round_id: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  record_room_activity(room)
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  assigned_total = len(room.prompts)
  submitted_total = sum(1 for prompt in room.prompts if prompt.is_submitted())
  connected_total = sum(1 for player in room.players if player.connected)
  disconnected_total = sum(1 for player in room.players if not player.connected)
  ready_to_reveal = assigned_total > 0 and submitted_total >= assigned_total
  return RoomProgressResponse(
    assigned_total=assigned_total,
    submitted_total=submitted_total,
    connected_total=connected_total,
    disconnected_total=disconnected_total,
    ready_to_reveal=ready_to_reveal,
  )


@router.post("/rooms/{room_code}/reveal", response_model=RevealRoomResponse)
def reveal_room_handler(room_code: str, payload: RevealRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  if not is_ready_to_reveal(room):
    raise HTTPException(status_code=409, detail="All prompts must be submitted before reveal.")
  story = reveal_story(room)
  return RevealRoomResponse(room_id=room.id, round_id=room.round_id, rendered_story=story)


@router.get("/rooms/{room_code}/rounds/{round_id}/story", response_model=StoryResponse)
def story_handler(room_code: str, round_id: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  if not room.revealed_story:
    raise HTTPException(status_code=409, detail="Story not revealed yet.")
  record_room_activity(room)
  return StoryResponse(room_id=room.id, round_id=room.round_id, rendered_story=room.revealed_story)


@router.get("/rooms/{room_code}/rounds/{round_id}/tts", response_model=TTSStatusResponse)
def tts_status_handler(room_code: str, round_id: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  record_room_activity(room)
  job = get_room_job(room.code, room.round_id)
  return _tts_response(job)


@router.post("/rooms/{room_code}/rounds/{round_id}:tts", response_model=TTSStatusResponse)
def request_tts_handler(room_code: str, round_id: str, payload: TTSRequest):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  _require_host(room, payload.host_token)
  if not room.revealed_story:
    raise HTTPException(status_code=409, detail="Story not revealed yet.")
  limit, window = RATE_LIMITS["tts_request"]
  _rate_limit_or_429(
    f"room:{room.code}:tts_request",
    limit,
    window,
    "Narration requests are rate limited. Please wait a moment and try again.",
  )
  record_room_activity(room)
  job = request_narration(
    room_code=room.code,
    round_id=room.round_id,
    story=room.revealed_story,
    model=payload.model,
    voice_id=payload.voice_id,
  )
  room.tts_job_id = job.id
  return _tts_response(job)


@router.post("/rooms/{room_code}/replay", response_model=ReplayRoomResponse)
def replay_room_handler(room_code: str, payload: ReplayRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  reset_round(room)
  return ReplayRoomResponse(room_id=room.id, round_id=room.round_id)


@router.post("/rooms/{room_code}/rounds/{round_id}:share", response_model=ShareRoomResponse)
def share_room_handler(room_code: str, round_id: str, payload: ShareRoomRequest):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  _require_host(room, payload.host_token)
  if not room.revealed_story:
    raise HTTPException(status_code=409, detail="Story not revealed yet.")
  record_room_activity(room)
  artifact = create_share(room.code, room.round_id, room.revealed_story)
  share_url = f"{WEB_BASE_URL.rstrip('/')}/s/{artifact.token}"
  return ShareRoomResponse(
    share_token=artifact.token,
    share_url=share_url,
    expires_at=artifact.expires_at.isoformat(),
  )


@router.get("/shares/{share_token}", response_model=ShareArtifactResponse)
def share_artifact_handler(share_token: str):
  artifact = get_share(share_token)
  if not artifact:
    raise HTTPException(status_code=404, detail="Share link not found.")
  return ShareArtifactResponse(
    share_token=artifact.token,
    room_code=artifact.room_code,
    round_id=artifact.round_id,
    rendered_story=artifact.rendered_story,
    expires_at=artifact.expires_at.isoformat(),
  )
