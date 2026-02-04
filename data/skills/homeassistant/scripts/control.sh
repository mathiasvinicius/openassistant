#!/usr/bin/env bash
set -euo pipefail

# Control Home Assistant entity by calling a service.
# Usage: control.sh <domain> <service> <entity_id> [payload_json]

DOMAIN="${1:-}"
SERVICE="${2:-}"
ENTITY_ID="${3:-}"
EXTRA_PAYLOAD="${4:-{}}"

if [[ -z "$DOMAIN" || -z "$SERVICE" || -z "$ENTITY_ID" ]]; then
  echo "Usage: control.sh <domain> <service> <entity_id> [payload_json]" >&2
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

DATA="$(echo "$EXTRA_PAYLOAD" | jq --arg entity "$ENTITY_ID" '. + {entity_id: $entity}')"

curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  "$URL/api/services/$DOMAIN/$SERVICE"

echo ""

