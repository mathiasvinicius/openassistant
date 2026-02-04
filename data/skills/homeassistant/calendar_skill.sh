#!/bin/bash
# Home Assistant Calendar Skill
# Usage: ./calendar_skill.sh <action> <entity_id> [details]

ACTION="$1"
ENTITY_ID="$2"
DETAILS="$3"

URL="${HOMEASSISTANT_URL:-http://172.16.0.2:8123}"
# Remove trailing slash if present
URL="${URL%/}"
TOKEN="$HOMEASSISTANT_TOKEN"

if [ -z "$TOKEN" ]; then
  echo "Error: HOMEASSISTANT_TOKEN environment variable is missing."
  exit 1
fi

# Endpoint for calendar events
API_URL="$URL/api/calendars/$ENTITY_ID"

if [ "$ACTION" = "list" ]; then
    echo "Listing events for $ENTITY_ID..."
    # 'list' on the entity endpoint often returns current/upcoming events depending on HA version
    # Safer to query a range if list fails, but let's try the base endpoint first
    curl -s -X GET \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      "$API_URL?start=$(date +%Y-%m-%dT00:00:00)&end=$(date -d "+30 days" +%Y-%m-%dT23:59:59)"

elif [ "$ACTION" = "get" ]; then
    if [ -z "$DETAILS" ]; then
      echo "Error: Date required for 'get' (YYYY-MM-DD)"
      exit 1
    fi
    echo "Getting events for $ENTITY_ID on $DETAILS..."
    START="${DETAILS}T00:00:00"
    END="${DETAILS}T23:59:59"
    
    curl -s -X GET \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      "$API_URL?start=$START&end=$END"

else
    echo "Usage: $0 list <entity_id> OR $0 get <entity_id> <YYYY-MM-DD>"
    exit 1
fi

echo ""
