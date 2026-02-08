#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="python3"
if [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

if [ -z "${DATABASE_URL:-}" ] || [[ "${DATABASE_URL}" == *"@postgres:"* ]]; then
  export DATABASE_URL="postgresql+psycopg2://storyfill:storyfill@localhost:5432/storyfill"
fi

echo "Seeding database..."
(cd "${ROOT_DIR}/api" && "${PYTHON_BIN}" -m app.db.seed_templates)
