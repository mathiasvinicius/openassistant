#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/data/skills/wppconnect-wajs/config/wppconnect.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing config: $ENV_FILE"
  echo "Run: cp $ROOT_DIR/data/skills/wppconnect-wajs/config/wppconnect.env.example $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

# Load env into compose and start the service under the wppconnect profile.
docker compose --env-file "$ENV_FILE" --profile wppconnect up -d wppconnect-wajs

echo "Started: wppconnect-wajs (port ${WPP_PORT:-21465})"
