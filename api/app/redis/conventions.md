# Redis Key Conventions

All keys are namespaced with `storyfill` to avoid collisions across services.

Patterns:
- `storyfill:room:{room_id}:state` — authoritative room state
- `storyfill:room:{room_id}:presence` — connected players
- `storyfill:player:{player_id}:session` — player session metadata
- `storyfill:queue:{name}` — worker queues

TTL:
- Room state keys should be refreshed on activity.
- Use `refresh_ttl(key, seconds)` from `app.redis.client`.
