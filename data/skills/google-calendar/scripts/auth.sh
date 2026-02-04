#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${BASE_DIR}/scripts/bootstrap.sh"

exec env PYTHONUNBUFFERED=1 "${BASE_DIR}/.venv/bin/python" -u "${BASE_DIR}/scripts/gcal.py" auth
