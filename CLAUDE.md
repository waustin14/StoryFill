# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoryFill is a collaborative, host-led story game (similar to MadLibs). Players join a room, receive prompts to fill in, and the completed story is revealed by the host. The project includes TTS narration and shareable story links.

## Architecture

### Service Layout

The codebase is organized as a multi-service architecture running in Docker Compose:

- **web/** - Next.js 16 + TypeScript frontend (port 3000)
- **api/** - FastAPI backend with REST + WebSocket endpoints (port 8000)
- **worker/** - Background job processor using RQ (Redis Queue)
- **tts/** - Dedicated TTS microservice that proxies to OpenAI-compatible endpoints (port 7000)
- **postgres** - PostgreSQL 16 database (port 5432)
- **redis** - Redis 7 for session state and job queues (port 6379)
- **minio** - S3-compatible object storage for audio files (ports 9000/9001)

### Key Architecture Patterns

**State Management:**
- Room state is stored in-memory in `api/app/data/rooms.py` with a `ROOMS` dictionary
- Redis is used for session TTL tracking and pub/sub events (see `api/app/redis/conventions.md`)
- Redis keys follow pattern: `storyfill:room:{room_id}:state`
- Rooms expire after 1 hour of inactivity (configurable via `ROOM_TTL` in rooms.py)

**Player Sessions:**
- Frontend stores session data in localStorage (see `web/src/lib/multiplayer-session.ts` and `web/src/lib/solo-session.ts`)
- Each player gets a unique token for authentication
- Players can reconnect using their token if disconnected

**TTS Pipeline:**
- The `tts/` service acts as a proxy to OpenAI-compatible TTS providers
- Audio is generated, stored in MinIO, and served through the web app at `/tts/audio/{job_id}`
- Model format: `provider/model` or `provider:model` (e.g., `openai/tts-1`)
- Fallback to `TTS_DEFAULT_PROVIDER` environment variable if provider not specified

**Prompt Assignment:**
- Each player gets 3 prompts by default (`PROMPTS_PER_PLAYER` in rooms.py)
- If a player disconnects for >30 seconds (`DISCONNECT_GRACE`), their prompts are reassigned
- Prompts can be reclaimed if the original player reconnects

**Real-time Communication:**
- WebSocket events are published via Redis pub/sub (see `api/app/realtime/events.py`)
- Event channel: `storyfill:events`
- Example events: `room.expired`

**Rate Limiting:**
- Implemented in `api/app/core/rate_limit.py`
- Limits defined per-endpoint in `api/app/routes/rooms.py` (`RATE_LIMITS` dict)
- Rate limit buckets use patterns like `ip:{ip}:create_room` and `room:{code}:player:{id}:submit_prompt`

## Development Commands

### Initial Setup

```bash
# Copy environment template
cp .env.example .env

# Set OPENAI_API_KEY in .env to enable TTS narration

# Install Python dependencies
infra/scripts/setup-python.sh
```

### Running Services

```bash
# Start all services via Docker Compose
infra/scripts/dev.sh

# Run migrations (requires services to be running)
infra/scripts/migrate.sh

# Frontend dev server only (without Docker)
npm --prefix web run dev
```

### Database Migrations

```bash
# Run all pending migrations
infra/scripts/migrate.sh

# Create a new migration (from api/ directory)
cd api && alembic revision --autogenerate -m "description"
```

### Code Quality

```bash
# Lint frontend (backend linting not yet configured)
infra/scripts/lint.sh

# Format frontend
npm --prefix web run format:write

# Tests (not yet configured)
infra/scripts/test.sh
```

### Useful Service Commands

```bash
# View logs for a specific service
docker compose logs -f api
docker compose logs -f worker

# Restart a service
docker compose restart api

# Access MinIO console (object storage)
# Navigate to http://localhost:9001
# Credentials: minio / minio123

# Access Jaeger UI (trace viewer)
# Navigate to http://localhost:16686
```

## Code Structure Notes

**API Routes:**
- All routes are versioned under `/v1` prefix
- Router files: `api/app/routes/templates.py`, `api/app/routes/rooms.py`, `api/app/routes/tts.py`
- Host-only actions require `host_token` validation (see `_require_host()` in rooms.py)

**Configuration:**
- Environment variables are read in `api/app/core/config.py` and `worker/app/main.py`
- Uses helper pattern: `env(key, default)` for safe environment access
- CORS origins configured via `WEB_ORIGINS` (comma-separated)

**Observability:**
- OpenTelemetry tracing initialized in `api/app/otel.py` and `worker/app/otel.py`
- Service names configurable via `OTEL_SERVICE_NAME`
- Request ID middleware in `api/app/middleware/request_id.py`

**Frontend Structure:**
- App router pattern (Next.js 16)
- Pages: mode selection, room lobby, prompting, reveal, sharing (`web/src/app/`)
- Client-side state management via localStorage
- Uses TailwindCSS + shadcn/ui patterns
