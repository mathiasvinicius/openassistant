#!/bin/bash

# Home Assistant Query Script
# Usage: ha_query.sh [entity_type_or_id]

set -e

if [ -z "$HOMEASSISTANT_URL" ] || [ -z "$HOMEASSISTANT_TOKEN" ]; then
  echo "❌ Error: HOMEASSISTANT_URL and HOMEASSISTANT_TOKEN environment variables required"
  exit 1
fi

QUERY="${1:-}"
URL="${HOMEASSISTANT_URL%/}/api/states"

# Fetch all states
STATES=$(curl -s -X GET \
  -H "Authorization: Bearer $HOMEASSISTANT_TOKEN" \
  -H "Content-Type: application/json" \
  "$URL")

if [ -z "$QUERY" ]; then
  # List all entities
  echo "$STATES" | python3 -m json.tool 2>/dev/null | head -200
elif [[ "$QUERY" == *.* ]]; then
  # Specific entity ID (e.g., light.living_room)
  echo "$STATES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
entity = next((e for e in data if e['entity_id'] == '$QUERY'), None)
if entity:
  print(json.dumps(entity, indent=2))
else:
  print('❌ Entity not found: $QUERY')
" 2>/dev/null
else
  # Filter by type (e.g., 'light', 'switch')
  echo "$STATES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
matching = [e for e in data if e['entity_id'].startswith('$QUERY.')]
if matching:
  for e in matching:
    print(f\"{e['entity_id']}: {e['state']}\")
else:
  print(f'❌ No entities found matching type: $QUERY')
" 2>/dev/null
fi
