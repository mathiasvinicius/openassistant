#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT_DIR/skills/wppconnect-wajs/config/wppconnect.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing config: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

if docker compose ps --services --status running | grep -qx "wppconnect-wajs"; then
  echo "running"
else
  echo "stopped"
fi
