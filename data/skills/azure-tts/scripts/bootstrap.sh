#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${BASE_DIR}/.venv"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "${VENV_DIR}" >/dev/null
  else
    python3 -m venv "${VENV_DIR}"
  fi
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${VENV_DIR}/bin/python" \
    azure-cognitiveservices-speech >/dev/null
else
  "${VENV_DIR}/bin/python" -m pip install --no-cache-dir azure-cognitiveservices-speech >/dev/null
fi

