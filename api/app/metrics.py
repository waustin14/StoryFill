from datetime import datetime, timezone

from app.core.rate_limit import rate_limit_metrics
from app.data.rooms import list_rooms
from app.data.tts import tts_metrics


def _now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def collect_metrics() -> dict:
  try:
    rooms = list_rooms()
  except Exception:
    rooms = []
  rooms_by_state: dict[str, int] = {}
  players_total = 0
  players_connected = 0
  prompts_assigned = 0
  prompts_submitted = 0

  for room in rooms:
    state = getattr(room, "state", None)
    if state is not None:
      key = state.value if hasattr(state, "value") else str(state)
      rooms_by_state[key] = rooms_by_state.get(key, 0) + 1
    players_total += len(room.players)
    players_connected += sum(1 for player in room.players if player.connected)
    prompts_assigned += len(room.prompts)
    prompts_submitted += sum(1 for prompt in room.prompts if prompt.is_submitted())

  return {
    "ts": _now_iso(),
    "rooms_active": len(rooms),
    "rooms_by_state": rooms_by_state,
    "players_total": players_total,
    "players_connected": players_connected,
    "prompts_assigned": prompts_assigned,
    "prompts_submitted": prompts_submitted,
    "tts": tts_metrics(),
    "rate_limits": rate_limit_metrics(),
  }
