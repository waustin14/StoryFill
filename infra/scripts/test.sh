#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="python3"
if [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

# Avoid OTLP exporter noise during tests.
export OTEL_SDK_DISABLED="true"
export OTEL_TRACES_EXPORTER="none"

if [ -d "api" ]; then
  echo "Running backend tests..."
  (cd api && "${PYTHON_BIN}" -m pytest -q --cov=app --cov-report=term-missing)
else
  echo "api/ not found; skipping backend tests."
fi

if [ -d "worker" ]; then
  echo "Running worker tests..."
  (cd worker && "${PYTHON_BIN}" -m pytest -q --cov=app --cov-report=term-missing)
else
  echo "worker/ not found; skipping worker tests."
fi

if [ -d "tts" ]; then
  echo "Running tts tests..."
  (cd tts && "${PYTHON_BIN}" -m pytest -q --cov=app --cov-report=term-missing)
else
  echo "tts/ not found; skipping tts tests."
fi

if [ -d "web" ]; then
  echo "Running frontend tests..."
  (cd web && npm test)
else
  echo "web/ not found; skipping frontend tests."
fi
