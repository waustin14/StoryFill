#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALEMBIC_BIN="alembic"
if [ -x "${ROOT_DIR}/.venv/bin/alembic" ]; then
  ALEMBIC_BIN="${ROOT_DIR}/.venv/bin/alembic"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="postgresql+psycopg2://storyfill:storyfill@localhost:5432/storyfill"
fi

"${ALEMBIC_BIN}" -c "${ROOT_DIR}/api/alembic.ini" upgrade head
