#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/data/skills/wppconnect-wajs/config/wppconnect.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing config: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

# Stop and remove the container, keep data directory intact.
docker compose --env-file "$ENV_FILE" --profile wppconnect rm -sf wppconnect-wajs

echo "Removed container: wppconnect-wajs (data preserved)"
