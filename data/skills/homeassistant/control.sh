#!/bin/bash
# Control Home Assistant Entity
# Usage: ./control.sh <domain> <service> <entity_id> [payload_json]
# Example: ./control.sh switch turn_on switch.luz_sala
# Example: ./control.sh light turn_on light.quarto '{"brightness": 255}'

DOMAIN="$1"
SERVICE="$2"
ENTITY_ID="$3"
EXTRA_PAYLOAD="${4:-{}}"

# Default URL if not set, but TOKEN is mandatory via env
URL="${HOMEASSISTANT_URL:-http://172.16.0.2:8123}"
# Strip trailing slash if present
URL="${URL%/}"

if [ -z "$HOMEASSISTANT_TOKEN" ]; then
  echo "Error: HOMEASSISTANT_TOKEN environment variable is missing."
  exit 1
fi

# Construct JSON payload
# We merge entity_id into the extra payload using jq if available, or simple string manipulation if simple
# For simplicity and robust dependency, we'll use a simple approach or assuming jq is installed (it usually is in openclaw images)

# Check for jq
if ! command -v jq &> /dev/null; then
    # Fallback for simple calls without extra payload
    DATA="{\"entity_id\": \"$ENTITY_ID\"}"
else
    # Merge entity_id into payload
    DATA=$(echo "$EXTRA_PAYLOAD" | jq --arg entity "$ENTITY_ID" '. + {entity_id: $entity}')
fi

echo "Calling $DOMAIN.$SERVICE for $ENTITY_ID..."

curl -s -X POST \
  -H "Authorization: Bearer $HOMEASSISTANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  "$URL/api/services/$DOMAIN/$SERVICE"

echo ""
