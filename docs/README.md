# Documentation

This folder contains user-facing documentation for StoryFill. Product and engineering specs live in `artifacts/`.

Planned docs:
- Getting Started
- How to Host a Game
- Player Guide
- Accessibility Notes
- Privacy & Safety Overview

Current setup notes:
- TTS runs in a dedicated `tts` container with an OpenAI-compatible `/v1/audio/speech` endpoint.
- Configure `OPENAI_API_KEY` (or another provider) in `.env` to enable narration.
- Audio files are stored in MinIO and served through the web app at `/tts/audio/{job_id}`.
