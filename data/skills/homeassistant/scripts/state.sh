#!/usr/bin/env bash
set -euo pipefail

# Get Home Assistant entity state.
# Usage: state.sh <entity_id>

ENTITY_ID="${1:-}"

if [[ -z "$ENTITY_ID" ]]; then
  echo "Usage: state.sh <entity_id>" >&2
  exit 2
fi

URL="${HOMEASSISTANT_URL:-}"
TOKEN="${HOMEASSISTANT_TOKEN:-}"

if [[ -z "$URL" ]]; then
  echo "Missing HOMEASSISTANT_URL env var (example: http://172.16.0.2:8123)" >&2
  exit 2
fi

if [[ -z "$TOKEN" ]]; then
  echo "Missing HOMEASSISTANT_TOKEN env var" >&2
  exit 2
fi

curl -sS -X GET \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$URL/api/states/$ENTITY_ID"

echo ""

