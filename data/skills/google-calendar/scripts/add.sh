#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${BASE_DIR}/scripts/bootstrap.sh"

SUMMARY="${1:?summary required}"
START="${2:?start datetime required (ISO-8601, e.g. 2026-02-05T10:00:00-03:00)}"
END="${3:?end datetime required (ISO-8601, e.g. 2026-02-05T11:00:00-03:00)}"

exec "${BASE_DIR}/.venv/bin/python" "${BASE_DIR}/scripts/gcal.py" add \
  --summary "${SUMMARY}" \
  --start "${START}" \
  --end "${END}"

