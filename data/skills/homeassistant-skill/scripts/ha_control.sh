#!/bin/bash

# Home Assistant Control Script
# Usage: ha_control.sh <entity_id> <action> [params...]
# Examples:
#   ha_control.sh light.living_room on
#   ha_control.sh light.living_room brightness 200
#   ha_control.sh light.living_room color 255 100 50
#   ha_control.sh scene.bedtime activate
#   ha_control.sh climate.living_room temperature 22

set -e

if [ -z "$HOMEASSISTANT_URL" ] || [ -z "$HOMEASSISTANT_TOKEN" ]; then
  echo "❌ Error: HOMEASSISTANT_URL and HOMEASSISTANT_TOKEN environment variables required"
  exit 1
fi

ENTITY_ID="$1"
ACTION="$2"
PARAM1="$3"
PARAM2="$4"
PARAM3="$5"

if [ -z "$ENTITY_ID" ] || [ -z "$ACTION" ]; then
  echo "Usage: ha_control.sh <entity_id> <action> [params...]"
  echo "Examples:"
  echo "  ha_control.sh light.living_room on"
  echo "  ha_control.sh light.living_room brightness 200"
  echo "  ha_control.sh scene.bedtime activate"
  exit 1
fi

URL="${HOMEASSISTANT_URL%/}/api/services"

# Determine service and payload based on entity type and action
ENTITY_TYPE="${ENTITY_ID%%.*}"  # Extract domain (light, switch, etc.)

case "$ACTION" in
  on)
    SERVICE="turn_on"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\"}"
    ;;
  off)
    SERVICE="turn_off"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\"}"
    ;;
  toggle)
    SERVICE="toggle"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\"}"
    ;;
  brightness)
    if [ -z "$PARAM1" ]; then
      echo "❌ brightness requires a value (0-255)"
      exit 1
    fi
    SERVICE="turn_on"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\", \"brightness\": $PARAM1}"
    ;;
  color)
    if [ -z "$PARAM1" ] || [ -z "$PARAM2" ] || [ -z "$PARAM3" ]; then
      echo "❌ color requires 3 values: R G B (0-255)"
      exit 1
    fi
    SERVICE="turn_on"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\", \"rgb_color\": [$PARAM1, $PARAM2, $PARAM3]}"
    ;;
  activate)
    SERVICE="turn_on"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\"}"
    ;;
  trigger)
    SERVICE="trigger"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\"}"
    ;;
  temperature)
    if [ -z "$PARAM1" ]; then
      echo "❌ temperature requires a value"
      exit 1
    fi
    SERVICE="set_temperature"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\", \"temperature\": $PARAM1}"
    ;;
  hvac_mode)
    if [ -z "$PARAM1" ]; then
      echo "❌ hvac_mode requires a value (off, heat, cool, heat_cool, auto)"
      exit 1
    fi
    SERVICE="set_hvac_mode"
    PAYLOAD="{\"entity_id\": \"$ENTITY_ID\", \"hvac_mode\": \"$PARAM1\"}"
    ;;
  *)
    echo "❌ Unknown action: $ACTION"
    echo "Supported: on, off, toggle, brightness, color, activate, trigger, temperature, hvac_mode"
    exit 1
    ;;
esac

# Call service
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $HOMEASSISTANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$URL/$ENTITY_TYPE/$SERVICE" 2>&1)

if [ $? -eq 0 ]; then
  echo "✅ $ENTITY_ID: $ACTION"
  if [ -n "$PARAM1" ]; then
    echo "   Parameters: $PARAM1 $PARAM2 $PARAM3"
  fi
else
  echo "❌ Error: Failed to execute command"
  echo "$RESPONSE"
  exit 1
fi
