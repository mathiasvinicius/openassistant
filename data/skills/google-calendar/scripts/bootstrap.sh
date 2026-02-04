#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${BASE_DIR}/.venv"

recreate() {
  rm -rf "${VENV_DIR}"
  # Prefer uv because Debian images sometimes ship Python without ensurepip/venv.
  if command -v uv >/dev/null 2>&1; then
    uv venv "${VENV_DIR}" >/dev/null
  else
    python3 -m venv "${VENV_DIR}"
  fi
}

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  recreate
fi

if command -v uv >/dev/null 2>&1; then
  # uv can install deps into the venv even if the venv has no pip module.
  uv pip install --python "${VENV_DIR}/bin/python" \
    google-api-python-client \
    google-auth \
    google-auth-oauthlib \
    python-dateutil >/dev/null
else
  # Fallback requires pip in the venv (provided by python3-venv on Debian).
  if [[ ! -x "${VENV_DIR}/bin/pip" ]]; then
    echo "ERROR: venv has no pip. Install python3-venv in the image, or install uv." >&2
    exit 1
  fi
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "${VENV_DIR}/bin/python" -m pip install --no-cache-dir \
    google-api-python-client \
    google-auth \
    google-auth-oauthlib \
    python-dateutil >/dev/null
fi
