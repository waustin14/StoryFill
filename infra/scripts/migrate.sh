#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="postgresql+psycopg2://storyfill:storyfill@localhost:5432/storyfill"
fi

alembic -c api/alembic.ini upgrade head
