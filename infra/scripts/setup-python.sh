#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.12 is required. Install it and re-run." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade pip

if [ -f "api/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install -r api/requirements.txt
fi

if [ -f "worker/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install -r worker/requirements.txt
fi

echo "Python environment ready in $VENV_DIR"
