from datetime import datetime, timedelta, timezone
import threading
import time
from secrets import token_urlsafe
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.data.templates import default_template_definition, get_template_definition
from app.data.tts import clear_room_tts, purge_room_tts
from app.redis.client import delete_key, refresh_ttl, set_value
from app.redis.keys import room_presence, room_state
from app.realtime.events import emit_room_expired

ROOM_TTL = timedelta(hours=1)
ROOM_TTL_SECONDS = int(ROOM_TTL.total_seconds())
DISCONNECT_GRACE = timedelta(seconds=30)
PROMPTS_PER_PLAYER = 3


def _now() -> datetime:
  return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
  return f"{prefix}_{token_urlsafe(8)}"


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

  def touch(self) -> None:
    self.updated_at = _now()

  def expires_at(self) -> datetime:
    return self.updated_at + ROOM_TTL

  def is_expired(self) -> bool:
    return self.expires_at() <= _now()


ROOMS: Dict[str, Room] = {}
_SWEEPER_STARTED = False


def record_room_activity(room: Room) -> None:
  room.touch()
  try:
    refresh_ttl(room_state(room.id), ROOM_TTL_SECONDS)
  except Exception:
    return


def expire_room(room: Room) -> None:
  emit_room_expired(room.code, room.round_id)
  try:
    delete_key(room_state(room.id))
    delete_key(room_presence(room.id))
  except Exception:
    pass
  purge_room_tts(room.code)
  ROOMS.pop(room.code, None)


def _sweep_expired_rooms() -> None:
  while True:
    now = _now()
    for room in list(ROOMS.values()):
      if room.expires_at() <= now:
        expire_room(room)
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
  room = Room(
    id=_new_id("room"),
    code=_new_id("code").split("_", maxsplit=1)[1].upper()[:6],
    round_id=_new_id("round"),
    host_token=_new_id("host"),
    locked=False,
    template_id=template.id,
    revealed_story=None,
    revealed_at=None,
    tts_job_id=None,
    created_at=_now(),
    updated_at=_now(),
    players=[],
    prompts=[],
  )
  ROOMS[room.code] = room
  try:
    set_value(room_state(room.id), room.code, ttl_seconds=ROOM_TTL_SECONDS)
  except Exception:
    pass
  return room


def get_room(code: str) -> Optional[Room]:
  return ROOMS.get(code.upper())


def add_player(room: Room, display_name: Optional[str]) -> Player:
  name = display_name.strip() if display_name else ""
  player = Player(
    id=_new_id("player"),
    token=token_urlsafe(16),
    display_name=name if name else f"Player {len(room.players) + 1}",
    joined_at=_now(),
    connected=True,
    disconnected_at=None,
  )
  room.players.append(player)
  record_room_activity(room)
  return player


def remove_player(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    raise ValueError("Player not found.")
  room.players = [p for p in room.players if p.id != player_id]

  if not room.prompts:
    record_room_activity(room)
    return

  candidates = [p for p in room.players if p.connected] or list(room.players)
  if not candidates:
    record_room_activity(room)
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

  record_room_activity(room)


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
  record_room_activity(room)


def player_prompts(room: Room, player_id: str) -> List[PromptAssignment]:
  return [prompt for prompt in room.prompts if prompt.assigned_to == player_id]


def submit_prompt(room: Room, player_id: str, prompt_id: str, value: str) -> PromptAssignment:
  for prompt in room.prompts:
    if prompt.id == prompt_id and prompt.assigned_to == player_id:
      prompt.value = value
      prompt.submitted_at = _now()
      record_room_activity(room)
      return prompt
  raise ValueError("Prompt not found for player.")


def mark_disconnected(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    return
  player.connected = False
  player.disconnected_at = _now()
  record_room_activity(room)


def mark_connected(room: Room, player_id: str) -> None:
  player = get_player(room, player_id)
  if not player:
    return
  player.connected = True
  player.disconnected_at = None
  record_room_activity(room)


def set_room_locked(room: Room, locked: bool) -> None:
  if room.locked == locked:
    return
  room.locked = locked
  record_room_activity(room)


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
    record_room_activity(room)


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
    record_room_activity(room)


def is_ready_to_reveal(room: Room) -> bool:
  assigned_total = len(room.prompts)
  submitted_total = sum(1 for prompt in room.prompts if prompt.is_submitted())
  return assigned_total > 0 and submitted_total >= assigned_total


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
  slots = {slot.id for slot in template.slots}
  rendered = template.story
  for slot_id in slots:
    raw = values.get(slot_id, "something")
    value = raw
    if slot_id == "sound" and raw and not (raw.startswith("\"") and raw.endswith("\"")):
      value = f"\"{raw}\""
    rendered = rendered.replace(f"{{{slot_id}}}", value)
  return rendered


def reveal_story(room: Room) -> str:
  if room.revealed_story:
    return room.revealed_story
  story = render_story(room)
  room.revealed_story = story
  room.revealed_at = _now()
  record_room_activity(room)
  return story


def reset_round(room: Room) -> None:
  previous_round = room.round_id
  room.round_id = _new_id("round")
  room.prompts = []
  room.revealed_story = None
  room.revealed_at = None
  room.tts_job_id = None
  clear_room_tts(room.code, previous_round)
  record_room_activity(room)


start_expiry_sweeper()
