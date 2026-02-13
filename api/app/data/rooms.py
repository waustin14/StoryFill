from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import threading
import time
from secrets import token_urlsafe
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.core.jwt import create_host_token, create_player_token
from app.core.moderation import moderation_block_reason
from app.data.moderation_events import record_moderation_event
from app.data.polish import polish_story
from app.data.slot_types import get_slot_type
from app.data.templates import default_template_definition, get_template_definition
from app.data.tts import clear_room_tts, purge_room_tts
from app.db.models import RoomSession as RoomSessionRow
from app.db.models import Round as RoundRow
from app.db.session import SessionLocal
from app.redis.client import delete_key, get_value, scan_keys, set_value
from app.redis.keys import KEY_PREFIX, room_code_lookup, room_presence, room_state
from app.realtime.events import emit_room_expired

ROOM_TTL = timedelta(hours=1)
ROOM_TTL_SECONDS = int(ROOM_TTL.total_seconds())
DISCONNECT_GRACE = timedelta(seconds=30)
PROMPTS_PER_PLAYER = 3
MAX_PLAYERS = 6
MAX_DISPLAY_NAME_LENGTH = 30


def _now() -> datetime:
  return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
  return f"{prefix}_{token_urlsafe(8)}"


class RoomState(str, Enum):
  LOBBY_OPEN = "LobbyOpen"
  COLLECTING_PROMPTS = "CollectingPrompts"
  ALL_SUBMITTED = "AllSubmitted"
  REVEALED = "Revealed"
  CLOSED = "Closed"
  EXPIRED = "Expired"


_ALLOWED_STATE_TRANSITIONS = {
  RoomState.LOBBY_OPEN: {RoomState.COLLECTING_PROMPTS, RoomState.CLOSED, RoomState.EXPIRED},
  RoomState.COLLECTING_PROMPTS: {RoomState.ALL_SUBMITTED, RoomState.REVEALED, RoomState.COLLECTING_PROMPTS, RoomState.CLOSED, RoomState.EXPIRED},
  RoomState.ALL_SUBMITTED: {RoomState.REVEALED, RoomState.COLLECTING_PROMPTS, RoomState.CLOSED, RoomState.EXPIRED},
  RoomState.REVEALED: {RoomState.COLLECTING_PROMPTS, RoomState.CLOSED, RoomState.EXPIRED},
  RoomState.CLOSED: set(),
  RoomState.EXPIRED: set(),
}


def transition_room_state(room: "Room", next_state: RoomState) -> None:
  if room.state == next_state:
    return
  allowed = _ALLOWED_STATE_TRANSITIONS.get(room.state, set())
  if next_state not in allowed:
    raise ValueError(f"Invalid room state transition: {room.state} -> {next_state}.")
  room.state = next_state


class Player(BaseModel):
  id: str
  token: str
  display_name: str
  joined_at: datetime
  connected: bool
  disconnected_at: Optional[datetime]


class PromptAssignment(BaseModel):
  id: str
  slot_id: str
  label: str
  type: str
  original_assignee: str
  assigned_to: str
  value: Optional[str]
  submitted_at: Optional[datetime]

  def is_submitted(self) -> bool:
    return self.value is not None


class Room(BaseModel):
  id: str
  code: str
  round_id: str
  round_index: int
  state_version: int
  state: RoomState
  host_token: str
  locked: bool
  template_id: str
  revealed_story: Optional[str]
  revealed_at: Optional[datetime]
  tts_job_id: Optional[str]
  created_at: datetime
  updated_at: datetime
  players: List[Player]
  prompts: List[PromptAssignment]
  db_session_id: Optional[str]
  db_round_id: Optional[str]

  def touch(self) -> None:
    self.updated_at = _now()

  def expires_at(self) -> datetime:
    return self.updated_at + ROOM_TTL

  def is_expired(self) -> bool:
    return self.expires_at() <= _now()


def _room_payload(room: "Room") -> dict:
  if hasattr(room, "model_dump"):
    try:
      return room.model_dump(mode="json")
    except TypeError:
      return room.model_dump()
  return room.dict()


def _room_from_payload(payload: dict) -> "Room":
  if hasattr(Room, "model_validate"):
    return Room.model_validate(payload)
  return Room.parse_obj(payload)


def _serialize_room(room: "Room") -> str:
  payload = _room_payload(room)
  try:
    return json.dumps(payload)
  except TypeError:
    return json.dumps(payload, default=str)


def _deserialize_room(raw: str) -> "Room":
  return _room_from_payload(json.loads(raw))


class StorageUnavailableError(Exception):
  pass


def _persist_room(room: Room) -> None:
  payload = _serialize_room(room)
  set_value(room_state(room.id), payload, ttl_seconds=ROOM_TTL_SECONDS)
  set_value(room_code_lookup(room.code), room.id, ttl_seconds=ROOM_TTL_SECONDS)


def _load_room_from_redis(room_code: str) -> Optional[Room]:
  try:
    room_id = get_value(room_code_lookup(room_code))
  except Exception as exc:
    raise StorageUnavailableError("Redis unavailable") from exc
  if not room_id:
    return None
  try:
    raw = get_value(room_state(room_id))
  except Exception as exc:
    raise StorageUnavailableError("Redis unavailable") from exc
  if not raw:
    try:
      delete_key(room_code_lookup(room_code))
    except Exception:
      pass
    return None
  try:
    room = _deserialize_room(raw)
  except Exception:
    return None
  return room


def save_room(room: Room) -> None:
  _persist_room(room)


def list_rooms() -> List[Room]:
  rooms: list[Room] = []
  for key in scan_keys(f"{KEY_PREFIX}:room:*:state"):
    raw = get_value(key)
    if not raw:
      continue
    try:
      room = _deserialize_room(raw)
    except Exception:
      continue
    rooms.append(room)
  return rooms


def reset_rooms_for_tests() -> None:
  try:
    for key in scan_keys(f"{KEY_PREFIX}:room:*:state"):
      delete_key(key)
    for key in scan_keys(f"{KEY_PREFIX}:room_code:*"):
      delete_key(key)
  except Exception:
    return


def record_room_activity(room: Room) -> None:
  room.touch()
  _persist_room(room)


def record_room_mutation(room: Room) -> None:
  room.state_version += 1
  record_room_activity(room)


def _persist_room_session(room: Room) -> None:
  if room.db_session_id:
    return
  try:
    db = SessionLocal()
  except Exception:
    return
  try:
    row = RoomSessionRow(
      room_code=room.code,
      template_id=room.template_id,
      created_at=room.created_at,
      ended_at=None,
      end_reason=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    room.db_session_id = row.id
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _persist_room_session_template(room: Room) -> None:
  if not room.db_session_id:
    return
  try:
    db = SessionLocal()
  except Exception:
    return
  try:
    row = db.query(RoomSessionRow).filter(RoomSessionRow.id == room.db_session_id).one_or_none()
    if not row:
      return
    row.template_id = room.template_id
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _persist_round(room: Room) -> None:
  if room.db_round_id:
    return
  if not room.db_session_id:
    return
  try:
    db = SessionLocal()
  except Exception:
    return
  try:
    row = RoundRow(
      room_session_id=room.db_session_id,
      round_index=room.round_index,
      final_state=None,
      revealed_story_text=None,
      created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    room.db_round_id = row.id
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _round_final_state(room: Room) -> dict:
  submitted_total = sum(1 for prompt in room.prompts if prompt.is_submitted())
  return {
    "room_code": room.code,
    "round_id": room.round_id,
    "template_id": room.template_id,
    "state": room.state.value,
    "state_version": room.state_version,
    "players_total": len(room.players),
    "assigned_total": len(room.prompts),
    "submitted_total": submitted_total,
  }


def _persist_round_reveal(room: Room, story: str) -> None:
  if not room.db_round_id:
    return
  try:
    db = SessionLocal()
  except Exception:
    return
  try:
    row = db.query(RoundRow).filter(RoundRow.id == room.db_round_id).one_or_none()
    if not row:
      return
    row.revealed_story_text = story
    row.final_state = _round_final_state(room)
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def _end_room_session(room: Room, reason: str) -> None:
  if not room.db_session_id:
    return
  try:
    db = SessionLocal()
  except Exception:
    return
  try:
    row = db.query(RoomSessionRow).filter(RoomSessionRow.id == room.db_session_id).one_or_none()
    if not row:
      return
    row.ended_at = _now()
    row.end_reason = reason
    db.commit()
  except Exception:
    try:
      db.rollback()
    except Exception:
      pass
  finally:
    db.close()


def expire_room(room: Room, reason: str = "expired") -> None:
  _end_room_session(room, reason)
  emit_room_expired(room.code, room.round_id)
  try:
    delete_key(room_state(room.id))
    delete_key(room_code_lookup(room.code))
    delete_key(room_presence(room.id))
  except Exception:
    pass
  purge_room_tts(room.code)


_SWEEPER_STARTED = False


def _sweep_expired_rooms() -> None:
  while True:
    try:
      for key in scan_keys(f"{KEY_PREFIX}:room:*:state"):
        raw = get_value(key)
        if not raw:
          continue
        try:
          room = _deserialize_room(raw)
        except Exception:
          continue
        if room.is_expired():
          expire_room(room, reason="expired")
    except Exception:
      pass
    time.sleep(60)


def start_expiry_sweeper() -> None:
  global _SWEEPER_STARTED
  if _SWEEPER_STARTED:
    return
  _SWEEPER_STARTED = True
  thread = threading.Thread(target=_sweep_expired_rooms, daemon=True)
  thread.start()


def create_room(template_id: Optional[str] = None) -> Room:
  template = get_template_definition(template_id) or default_template_definition()
  room_id = _new_id("room")
  room_code = _new_id("code").split("_", maxsplit=1)[1].upper()[:6]
  host_token = create_host_token(room_id, room_code, ROOM_TTL_SECONDS, _new_id("jti"))
  room = Room(
    id=room_id,
    code=room_code,
    round_id=_new_id("round"),
    round_index=0,
    state_version=1,
    state=RoomState.LOBBY_OPEN,
    host_token=host_token,
    locked=False,
    template_id=template.id,
    revealed_story=None,
    revealed_at=None,
    tts_job_id=None,
    created_at=_now(),
    updated_at=_now(),
    players=[],
    prompts=[],
    db_session_id=None,
    db_round_id=None,
  )
  _persist_room_session(room)
  _persist_round(room)
  _persist_room(room)
  return room


def get_room(code: str) -> Optional[Room]:
  normalized = code.upper()
  return _load_room_from_redis(normalized)


def add_player(room: Room, display_name: Optional[str]) -> Player:
  if len(room.players) >= MAX_PLAYERS:
    raise ValueError(f"Room is full (max {MAX_PLAYERS} players).")
  name = display_name.strip() if display_name else ""
  if len(name) > MAX_DISPLAY_NAME_LENGTH:
    name = name[:MAX_DISPLAY_NAME_LENGTH]
  player_id = _new_id("player")
  token = create_player_token(room.id, room.code, player_id, ROOM_TTL_SECONDS, _new_id("jti"))
  player = Player(
    id=player_id,
    token=token,
    display_name=name if name else f"Player {len(room.players) + 1}",
    joined_at=_now(),
    connected=True,
    disconnected_at=None,
  )
  room.players.append(player)
  record_room_mutation(room)
  return player


def remove_player(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    raise ValueError("Player not found.")
  room.players = [p for p in room.players if p.id != player_id]

  if not room.prompts:
    record_room_mutation(room)
    return

  candidates = [p for p in room.players if p.connected] or list(room.players)
  if not candidates:
    record_room_mutation(room)
    return

  outstanding_counts = {p.id: 0 for p in candidates}
  for prompt in room.prompts:
    if prompt.assigned_to in outstanding_counts and not prompt.is_submitted():
      outstanding_counts[prompt.assigned_to] += 1

  def next_assignee() -> str:
    return min(outstanding_counts, key=outstanding_counts.get)

  for prompt in room.prompts:
    if prompt.assigned_to == player_id and not prompt.is_submitted():
      assignee = next_assignee()
      prompt.assigned_to = assignee
      outstanding_counts[assignee] += 1

  record_room_mutation(room)


def get_player(room: Room, player_id: str) -> Optional[Player]:
  for player in room.players:
    if player.id == player_id:
      return player
  return None


def get_player_by_token(room: Room, token: str) -> Optional[Player]:
  for player in room.players:
    if player.token == token:
      return player
  return None


def _prompt_pool(room: Room) -> List[dict]:
  template = get_template_definition(room.template_id) or default_template_definition()
  return [
    {"slot_id": slot.id, "label": slot.label, "type": slot.type}
    for slot in template.slots
  ]


def ensure_prompts_assigned(room: Room) -> None:
  if room.prompts or not room.players:
    return

  if not room.db_session_id:
    _persist_room_session(room)
  if not room.db_round_id:
    _persist_round(room)

  pool = _prompt_pool(room)
  pool_index = 0
  for player in room.players:
    for _ in range(PROMPTS_PER_PLAYER):
      prompt = pool[pool_index % len(pool)]
      pool_index += 1
      room.prompts.append(
        PromptAssignment(
          id=_new_id("prompt"),
          slot_id=prompt["slot_id"],
          label=prompt["label"],
          type=prompt["type"],
          original_assignee=player.id,
          assigned_to=player.id,
          value=None,
          submitted_at=None,
        )
      )
  transition_room_state(room, RoomState.COLLECTING_PROMPTS)
  record_room_mutation(room)


def player_prompts(room: Room, player_id: str) -> List[PromptAssignment]:
  return [prompt for prompt in room.prompts if prompt.assigned_to == player_id]


def submit_prompt(room: Room, player_id: str, prompt_id: str, value: str) -> PromptAssignment:
  for prompt in room.prompts:
    if prompt.id == prompt_id and prompt.assigned_to == player_id:
      prompt.value = value
      prompt.submitted_at = _now()
      if is_ready_to_reveal(room):
        transition_room_state(room, RoomState.ALL_SUBMITTED)
      record_room_mutation(room)
      return prompt
  raise ValueError("Prompt not found for player.")


def mark_disconnected(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    return
  player.connected = False
  player.disconnected_at = _now()
  record_room_mutation(room)


def mark_connected(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    return
  player.connected = True
  player.disconnected_at = None
  record_room_mutation(room)


def set_room_locked(room: Room, locked: bool) -> None:
  if room.locked == locked:
    return
  room.locked = locked
  record_room_mutation(room)


def set_room_template(room: Room, template_id: str) -> None:
  if room.template_id == template_id:
    return
  room.template_id = template_id
  record_room_mutation(room)
  _persist_room_session_template(room)


def reassign_prompts_if_needed(room: Room) -> None:
  if not room.prompts:
    return

  now = _now()
  disconnected_players = {
    player.id
    for player in room.players
    if not player.connected and player.disconnected_at and player.disconnected_at + DISCONNECT_GRACE <= now
  }
  if not disconnected_players:
    return

  connected_players = [player for player in room.players if player.connected]
  if not connected_players:
    return

  outstanding_counts = {player.id: 0 for player in connected_players}
  for prompt in room.prompts:
    if prompt.assigned_to in outstanding_counts and not prompt.is_submitted():
      outstanding_counts[prompt.assigned_to] += 1

  def next_assignee() -> str:
    return min(outstanding_counts, key=outstanding_counts.get)

  changed = False
  for prompt in room.prompts:
    if prompt.assigned_to in disconnected_players and not prompt.is_submitted():
      assignee = next_assignee()
      prompt.assigned_to = assignee
      outstanding_counts[assignee] += 1
      changed = True

  if changed:
    record_room_mutation(room)


def reclaim_prompts(room: Room, player_id: str) -> None:
  if not room.prompts:
    return
  changed = False
  for prompt in room.prompts:
    if (
      prompt.original_assignee == player_id
      and not prompt.is_submitted()
      and prompt.assigned_to != player_id
    ):
      prompt.assigned_to = player_id
      changed = True
  if changed:
    record_room_mutation(room)


def is_ready_to_reveal(room: Room) -> bool:
  assigned_total = len(room.prompts)
  submitted_total = sum(1 for prompt in room.prompts if prompt.is_submitted())
  return assigned_total > 0 and submitted_total >= assigned_total


def room_progress(room: Room) -> dict:
  assigned_total = len(room.prompts)
  submitted_total = sum(1 for prompt in room.prompts if prompt.is_submitted())
  connected_total = sum(1 for player in room.players if player.connected)
  disconnected_total = sum(1 for player in room.players if not player.connected)
  ready_to_reveal = assigned_total > 0 and submitted_total >= assigned_total
  return {
    "assigned_total": assigned_total,
    "submitted_total": submitted_total,
    "connected_total": connected_total,
    "disconnected_total": disconnected_total,
    "ready_to_reveal": ready_to_reveal,
  }


def _prompt_values_by_slot(room: Room) -> Dict[str, str]:
  values: Dict[str, str] = {}
  for prompt in room.prompts:
    if not prompt.value:
      continue
    if prompt.slot_id not in values:
      values[prompt.slot_id] = prompt.value.strip()
  return values


def render_story(room: Room) -> str:
  template = get_template_definition(room.template_id) or default_template_definition()
  values = _prompt_values_by_slot(room)
  rendered = template.story
  for slot in template.slots:
    raw = values.get(slot.id, "something")
    value = raw
    if get_slot_type(slot.type).quote_in_story and raw and not (raw.startswith("\"") and raw.endswith("\"")):
      value = f"\"{raw}\""
    rendered = rendered.replace(f"{{{slot.id}}}", value)
  return rendered


def reveal_story(room: Room) -> str:
  if room.revealed_story:
    return room.revealed_story
  story = render_story(room)
  story = polish_story(story)
  block_reason = moderation_block_reason(story)
  record_moderation_event(
    "story",
    "block" if block_reason else "pass",
    "blocked_language" if block_reason else None,
  )
  if block_reason:
    raise ValueError(
      "We couldn't reveal this story because it includes language we can't accept. "
      "Please replay and try different responses."
      )
  room.revealed_story = story
  room.revealed_at = _now()
  transition_room_state(room, RoomState.REVEALED)
  record_room_mutation(room)
  _persist_round_reveal(room, story)
  return story


def reset_round(room: Room) -> None:
  previous_round = room.round_id
  room.round_id = _new_id("round")
  room.round_index += 1
  room.prompts = []
  room.revealed_story = None
  room.revealed_at = None
  room.tts_job_id = None
  room.db_round_id = None
  transition_room_state(room, RoomState.COLLECTING_PROMPTS)
  clear_room_tts(room.code, previous_round)
  record_room_mutation(room)
  _persist_round(room)


start_expiry_sweeper()
