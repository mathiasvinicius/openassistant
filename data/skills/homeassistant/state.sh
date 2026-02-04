#!/bin/bash
# Get Home Assistant Entity State
# Usage: ./state.sh <entity_id>

ENTITY_ID="$1"
URL="${HOMEASSISTANT_URL:-http://172.16.0.2:8123}"

if [ -z "$HOMEASSISTANT_TOKEN" ]; then
  echo "Error: HOMEASSISTANT_TOKEN environment variable is missing."
  exit 1
fi

curl -s -X GET \
  -H "Authorization: Bearer $HOMEASSISTANT_TOKEN" \
  -H "Content-Type: application/json" \
  "$URL/api/states/$ENTITY_ID"

echo ""
