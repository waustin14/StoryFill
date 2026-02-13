from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import WEB_BASE_URL, WS_BASE_URL
from app.core.jwt import decode_token
from app.core.moderation import moderation_block_reason
from app.data.moderation_events import record_moderation_event
from app.core.rate_limit import check_rate_limit
from app.data.rooms import (
  StorageUnavailableError,
  add_player,
  create_room,
  MAX_DISPLAY_NAME_LENGTH,
  MAX_PLAYERS,
  RoomState,
  ensure_prompts_assigned,
  expire_room,
  get_room,
  get_player,
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
  room_progress,
  set_room_locked,
  set_room_template,
  submit_prompt,
)
from app.data.shares import create_share, get_share
from app.data.slot_types import slot_limits
from app.data.templates import get_template_definition
from app.data.tts import get_room_job, request_narration
from app.realtime.events import emit_room_snapshot

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
  player_id: str
  player_token: str
  player_display_name: str
  host_token: str
  ws_url: str
  template_id: str
  room_snapshot: "RoomSnapshot"


class CreateRoomRequest(BaseModel):
  template_id: str | None = None
  display_name: str | None = None


class JoinRoomRequest(BaseModel):
  display_name: str | None = None


class ReconnectPlayerRequest(BaseModel):
  player_token: str


class PlayerSnapshot(BaseModel):
  id: str
  display_name: str
  is_host: bool = False


class RoomSnapshot(BaseModel):
  room_id: str
  room_code: str
  round_id: str
  round_index: int
  state_version: int
  room_state: str
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


class DisconnectPlayerRequest(BaseModel):
  player_token: str


class SubmitPromptRequest(BaseModel):
  player_id: str
  player_token: str
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


class SetTemplateRequest(BaseModel):
  host_token: str
  template_id: str


class StartRoomRequest(BaseModel):
  host_token: str


class EndRoomRequest(BaseModel):
  host_token: str


class LeaveRoomRequest(BaseModel):
  player_id: str
  player_token: str


def _prompt_rejection_reason(value: str, slot_type: str | None = None) -> str | None:
  if not value or not value.strip():
    return "Please add a response before submitting."
  trimmed = value.strip()

  for char in trimmed:
    code = ord(char)
    if code < 32 or code > 126:
      return (
        "That response includes characters we can't read yet. "
        "Use letters, numbers, and common punctuation only, and remove emoji or control characters."
      )

  min_len, max_len = slot_limits((slot_type or "").lower())
  if len(trimmed) < min_len:
    return "That response is too short. Please add a little more detail."
  if len(trimmed) > max_len:
    return f"That response is too long. Please keep it under {max_len} characters."

  block_reason = moderation_block_reason(trimmed)
  record_moderation_event(
    "prompt",
    "block" if block_reason else "pass",
    "blocked_language" if block_reason else None,
  )
  if block_reason:
    return block_reason
  return None


def _require_host(room, host_token: str) -> None:
  claims = decode_token(host_token)
  if not claims or claims.get("role") != "host" or claims.get("room_id") != room.id:
    raise HTTPException(status_code=403, detail="Host token required.")


def _require_player(room, player_id: str, player_token: str) -> None:
  player = get_player(room, player_id)
  if not player:
    raise HTTPException(status_code=404, detail="Player not found.")
  claims = decode_token(player_token)
  if (
    not claims
    or claims.get("role") != "player"
    or claims.get("room_id") != room.id
    or claims.get("player_id") != player_id
  ):
    raise HTTPException(status_code=403, detail="Player token required.")

def _require_room_state(room, allowed: set[RoomState], detail: str, status_code: int = 409) -> None:
  if room.state not in allowed:
    raise HTTPException(status_code=status_code, detail=detail)


def _validate_display_name(name: str | None) -> str | None:
  if not name:
    return None
  trimmed = name.strip()
  if not trimmed:
    return None
  if len(trimmed) > MAX_DISPLAY_NAME_LENGTH:
    raise HTTPException(
      status_code=400,
      detail=f"Display name must be {MAX_DISPLAY_NAME_LENGTH} characters or fewer.",
    )
  for char in trimmed:
    code = ord(char)
    if code < 32 or (code > 126 and code < 160):
      raise HTTPException(
        status_code=400,
        detail="Display name contains invalid characters.",
      )
  return trimmed


def _rate_limit_or_429(bucket: str, limit: int, window_seconds: int, message: str) -> None:
  result = check_rate_limit(bucket, limit, window_seconds)
  if result.allowed:
    return
  headers = {"Retry-After": str(result.retry_after)} if result.retry_after else None
  raise HTTPException(status_code=429, detail=message, headers=headers)


def _get_room_or_404(room_code: str):
  try:
    room = get_room(room_code)
  except StorageUnavailableError:
    raise HTTPException(status_code=503, detail="Storage temporarily unavailable.")
  if not room:
    raise HTTPException(status_code=404, detail="Room not found.")
  if room.is_expired():
    expire_room(room, reason="expired")
    raise HTTPException(status_code=410, detail="Room expired.")
  return room


def _room_snapshot(room) -> RoomSnapshot:
  return RoomSnapshot(
    room_id=room.id,
    room_code=room.code,
    round_id=room.round_id,
    round_index=room.round_index,
    state_version=room.state_version,
    room_state=getattr(room, "state", "LobbyOpen"),
    locked=room.locked,
    template_id=room.template_id,
    players=[
      PlayerSnapshot(id=p.id, display_name=p.display_name, is_host=(i == 0))
      for i, p in enumerate(room.players)
    ],
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


def _publish_room_snapshot(room) -> None:
  emit_room_snapshot(
    room_code=room.code,
    round_id=room.round_id,
    state_version=room.state_version,
    room_snapshot=_room_snapshot(room).model_dump(),
    progress=room_progress(room),
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
  raw_name = payload.display_name if payload else None
  validated_name = _validate_display_name(raw_name)
  template_id = payload.template_id if payload else None
  if template_id and not get_template_definition(template_id):
    raise HTTPException(status_code=400, detail="Unknown template.")
  try:
    room = create_room(template_id)
    host_player = add_player(room, validated_name)
  except StorageUnavailableError:
    raise HTTPException(status_code=503, detail="Storage temporarily unavailable.")
  _publish_room_snapshot(room)
  return CreateRoomResponse(
    room_code=room.code,
    room_id=room.id,
    round_id=room.round_id,
    player_id=host_player.id,
    player_token=host_player.token,
    player_display_name=host_player.display_name,
    host_token=room.host_token,
    ws_url=WS_BASE_URL,
    template_id=room.template_id,
    room_snapshot=_room_snapshot(room),
  )


@router.post("/rooms/{room_code}/join", response_model=JoinRoomResponse)
def join_room_handler(room_code: str, payload: JoinRoomRequest, request: Request):
  room = _get_room_or_404(room_code)
  _require_room_state(room, {RoomState.LOBBY_OPEN}, "Game already started.")
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
  if len(room.players) >= MAX_PLAYERS:
    raise HTTPException(status_code=409, detail=f"Room is full (max {MAX_PLAYERS} players).")
  validated_name = _validate_display_name(payload.display_name)
  player = add_player(room, validated_name)
  _publish_room_snapshot(room)
  return JoinRoomResponse(
    player_id=player.id,
    player_token=player.token,
    player_display_name=player.display_name,
    room_snapshot=_room_snapshot(room),
  )


@router.post("/rooms/{room_code}/start", response_model=RoomSnapshot)
def start_room_handler(room_code: str, payload: StartRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  _require_room_state(room, {RoomState.LOBBY_OPEN}, "Game already started.")
  if len(room.players) < 2:
    raise HTTPException(status_code=409, detail="Need at least 2 players to start.")
  ensure_prompts_assigned(room)
  record_room_activity(room)
  _publish_room_snapshot(room)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}/end", response_model=PlayerStatusResponse)
def end_room_handler(room_code: str, payload: EndRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  expire_room(room, reason="ended")
  return PlayerStatusResponse(status="ok")


@router.post("/rooms/{room_code}/leave", response_model=PlayerStatusResponse)
def leave_room_handler(room_code: str, payload: LeaveRoomRequest):
  room = _get_room_or_404(room_code)
  _require_player(room, payload.player_id, payload.player_token)
  try:
    remove_player(room, payload.player_id)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  _publish_room_snapshot(room)
  return PlayerStatusResponse(status="ok")


@router.get("/rooms/{room_code}/rounds/{round_id}/prompts", response_model=PromptListResponse)
def list_prompts_handler(room_code: str, round_id: str, player_id: str, player_token: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  _require_player(room, player_id, player_token)
  _require_room_state(
    room,
    {RoomState.COLLECTING_PROMPTS, RoomState.ALL_SUBMITTED, RoomState.REVEALED},
    "Game has not started yet.",
  )
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
  _require_room_state(room, {RoomState.COLLECTING_PROMPTS}, "Prompt collection is closed.")
  if room.revealed_story:
    raise HTTPException(status_code=409, detail="Story already revealed.")
  _require_player(room, payload.player_id, payload.player_token)
  limit, window = RATE_LIMITS["submit_prompt"]
  _rate_limit_or_429(
    f"room:{room.code}:player:{payload.player_id}:submit_prompt",
    limit,
    window,
    "You're submitting too quickly. Please wait a moment and try again.",
  )
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  prompt = next(
    (candidate for candidate in room.prompts if candidate.id == prompt_id and candidate.assigned_to == payload.player_id),
    None,
  )
  if not prompt:
    raise HTTPException(status_code=404, detail="Prompt not found for player.")
  if prompt.submitted_at:
    raise HTTPException(status_code=409, detail="Prompt already submitted.")
  rejection_reason = _prompt_rejection_reason(payload.value, prompt.type)
  if rejection_reason:
    raise HTTPException(status_code=400, detail=rejection_reason)
  try:
    submit_prompt(room, payload.player_id, prompt_id, payload.value)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  _publish_room_snapshot(room)
  return SubmitPromptResponse(status="ok")


@router.post("/rooms/{room_code}/players/{player_id}:disconnect", response_model=PlayerStatusResponse)
def disconnect_player_handler(room_code: str, player_id: str, payload: DisconnectPlayerRequest):
  room = _get_room_or_404(room_code)
  _require_player(room, player_id, payload.player_token)
  mark_disconnected(room, player_id)
  _publish_room_snapshot(room)
  return PlayerStatusResponse(status="ok")


@router.post("/rooms/{room_code}/players/{player_id}:reconnect", response_model=ReconnectPlayerResponse)
def reconnect_player_handler(room_code: str, player_id: str, payload: ReconnectPlayerRequest):
  room = _get_room_or_404(room_code)
  player = get_player(room, player_id)
  if not player:
    raise HTTPException(status_code=404, detail="Player not found.")
  claims = decode_token(payload.player_token)
  if (
    not claims
    or claims.get("role") != "player"
    or claims.get("room_id") != room.id
    or claims.get("player_id") != player_id
  ):
    raise HTTPException(status_code=403, detail="Player token required.")
  mark_connected(room, player_id)
  if room.state != RoomState.LOBBY_OPEN:
    ensure_prompts_assigned(room)
    reclaim_prompts(room, player_id)
  _publish_room_snapshot(room)
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
  _publish_room_snapshot(room)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}:unlock", response_model=RoomSnapshot)
def unlock_room_handler(room_code: str, payload: HostActionRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  set_room_locked(room, False)
  _publish_room_snapshot(room)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}:template", response_model=RoomSnapshot)
def set_room_template_handler(room_code: str, payload: SetTemplateRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  _require_room_state(room, {RoomState.LOBBY_OPEN}, "Game already started.")
  if not payload.template_id or not get_template_definition(payload.template_id):
    raise HTTPException(status_code=400, detail="Unknown template.")
  set_room_template(room, payload.template_id)
  _publish_room_snapshot(room)
  return _room_snapshot(room)


@router.post("/rooms/{room_code}/players/{player_id}:kick", response_model=RoomSnapshot)
def kick_player_handler(room_code: str, player_id: str, payload: HostActionRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  try:
    remove_player(room, player_id)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  _publish_room_snapshot(room)
  return _room_snapshot(room)


@router.get("/rooms/{room_code}/rounds/{round_id}/progress", response_model=RoomProgressResponse)
def room_progress_handler(room_code: str, round_id: str):
  room = _get_room_or_404(room_code)
  if room.round_id != round_id:
    raise HTTPException(status_code=404, detail="Room or round not found.")
  record_room_activity(room)
  reassign_prompts_if_needed(room)
  if room.state != RoomState.LOBBY_OPEN:
    ensure_prompts_assigned(room)
  metrics = room_progress(room)
  return RoomProgressResponse(
    assigned_total=metrics["assigned_total"],
    submitted_total=metrics["submitted_total"],
    connected_total=metrics["connected_total"],
    disconnected_total=metrics["disconnected_total"],
    ready_to_reveal=metrics["ready_to_reveal"],
  )


@router.post("/rooms/{room_code}/reveal", response_model=RevealRoomResponse)
def reveal_room_handler(room_code: str, payload: RevealRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  _require_room_state(
    room,
    {RoomState.COLLECTING_PROMPTS, RoomState.ALL_SUBMITTED, RoomState.REVEALED},
    "Game has not started yet.",
  )
  reassign_prompts_if_needed(room)
  ensure_prompts_assigned(room)
  if not is_ready_to_reveal(room):
    raise HTTPException(status_code=409, detail="All prompts must be submitted before reveal.")
  try:
    story = reveal_story(room)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  _publish_room_snapshot(room)
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
  job = request_narration(
    room_code=room.code,
    round_id=room.round_id,
    story=room.revealed_story,
    model=payload.model,
    voice_id=payload.voice_id,
  )
  room.tts_job_id = job.id
  record_room_activity(room)
  return _tts_response(job)


@router.post("/rooms/{room_code}/replay", response_model=ReplayRoomResponse)
def replay_room_handler(room_code: str, payload: ReplayRoomRequest):
  room = _get_room_or_404(room_code)
  _require_host(room, payload.host_token)
  _require_room_state(
    room,
    {RoomState.REVEALED, RoomState.ALL_SUBMITTED, RoomState.COLLECTING_PROMPTS},
    "Game has not started yet.",
  )
  reset_round(room)
  _publish_room_snapshot(room)
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
