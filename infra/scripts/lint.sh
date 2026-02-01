#!/usr/bin/env bash
set -euo pipefail

if [ -d "web" ]; then
  npm --prefix web run lint
else
  echo "web/ not found; skipping frontend lint."
fi

echo "No Python linter configured yet."
