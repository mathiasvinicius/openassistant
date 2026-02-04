#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${BASE_DIR}/scripts/bootstrap.sh"

exec "${BASE_DIR}/.venv/bin/python" "${BASE_DIR}/scripts/list_voices.py"

