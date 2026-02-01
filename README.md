# StoryFill (MVP)

StoryFill is a collaborative, host-led story game. This repository contains the MVP implementation and supporting documentation.

## Repository Layout

- `web/` Next.js + TypeScript frontend
- `api/` FastAPI backend (REST + WebSocket)
- `worker/` background jobs (TTS, cleanup)
- `infra/` Docker, scripts, and local environment wiring
- `docs/` user-facing documentation
- `artifacts/` product specs, architecture notes, and UI design assets

## Local Development

Scaffolding is in progress. Current local workflows:

- Copy `.env.example` to `.env` and adjust as needed.
- Set `OPENAI_API_KEY` (or another provider config) to enable TTS narration.
- Python dependencies: `infra/scripts/setup-python.sh`
- Start services (Docker Compose): `infra/scripts/dev.sh`
- Run migrations: `infra/scripts/migrate.sh`
- Frontend dev server only: `npm --prefix web run dev`

## License

See `LICENSE`.
