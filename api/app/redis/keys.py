KEY_PREFIX = "storyfill"


def room_state(room_id: str) -> str:
  return f"{KEY_PREFIX}:room:{room_id}:state"


def room_presence(room_id: str) -> str:
  return f"{KEY_PREFIX}:room:{room_id}:presence"


def player_session(player_id: str) -> str:
  return f"{KEY_PREFIX}:player:{player_id}:session"


def job_queue(name: str) -> str:
  return f"{KEY_PREFIX}:queue:{name}"


def share_artifact(token: str) -> str:
  return f"{KEY_PREFIX}:share:{token}"


def rate_limit_bucket(bucket: str) -> str:
  return f"{KEY_PREFIX}:rate:{bucket}"
