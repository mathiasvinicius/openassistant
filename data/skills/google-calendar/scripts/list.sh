#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${BASE_DIR}/scripts/bootstrap.sh"

LIMIT="${1:-10}"
exec "${BASE_DIR}/.venv/bin/python" "${BASE_DIR}/scripts/gcal.py" list --limit "${LIMIT}"

