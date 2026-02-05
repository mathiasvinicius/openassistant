# Home Assistant REST API Guide

## Endpoint Structure

```
Base: {HOMEASSISTANT_URL}/api/

/states              - Get all entity states
/states/<entity_id>  - Get/set specific entity state
/services/<domain>/<service>  - Call service
/config              - Configuration
```

## Authentication

All requests require:
```
Authorization: Bearer {HOMEASSISTANT_TOKEN}
Content-Type: application/json
```

## Common Services

### Lights
- **Domain**: `light`
- **Services**: `turn_on`, `turn_off`, `toggle`
- **turn_on Parameters**:
  - `brightness` (0-255)
  - `rgb_color` ([R, G, B])
  - `color_temp` (kelvin)
  - `transition` (seconds)

### Switches
- **Domain**: `switch`
- **Services**: `turn_on`, `turn_off`, `toggle`

### Scenes
- **Domain**: `scene`
- **Service**: `turn_on` (activates scene)

### Automations
- **Domain**: `automation`
- **Services**: `trigger`, `turn_on`, `turn_off`

### Climate
- **Domain**: `climate`
- **Services**: `set_temperature`, `set_hvac_mode`, `set_fan_mode`
- **Modes**: `off`, `heat`, `cool`, `heat_cool`, `auto`

### Media Players
- **Domain**: `media_player`
- **Services**: `play_media`, `media_play`, `media_pause`, `volume_set`

## API Examples

### Get All States
```bash
curl -s -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "$URL/api/states" | python3 -m json.tool
```

### Get Specific Entity
```bash
curl -s -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "$URL/api/states/light.living_room"
```

### Turn On Light with Brightness
```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "light.living_room",
    "brightness": 200
  }' \
  "$URL/api/services/light/turn_on"
```

### Set Climate Temperature
```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "climate.living_room",
    "temperature": 22
  }' \
  "$URL/api/services/climate/set_temperature"
```

### Trigger Automation
```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "automation.morning_routine"}' \
  "$URL/api/services/automation/trigger"
```

## State Structure

Each entity has:
```json
{
  "entity_id": "light.living_room",
  "state": "on",
  "attributes": {
    "brightness": 254,
    "rgb_color": [255, 100, 50],
    "color_mode": "rgb",
    "friendly_name": "Living Room Light",
    "supported_features": 191
  },
  "last_changed": "2026-02-04T20:00:00.000000+00:00",
  "last_updated": "2026-02-04T20:05:00.000000+00:00",
  "context": {
    "id": "...",
    "parent_id": null,
    "user_id": "..."
  }
}
```

## Error Handling

HTTP Status Codes:
- `200` - Success
- `400` - Bad request (check payload syntax)
- `401` - Unauthorized (check token)
- `404` - Entity not found
- `429` - Rate limited
- `500` - Server error

Example error:
```json
{
  "type": "invalid_format",
  "message": "Invalid entity_id: invalid"
}
```

## Useful Queries

### Find all entities of a type
```bash
curl -s -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "$URL/api/states" | \
  python3 -c "
import json, sys
states = json.load(sys.stdin)
lights = [e for e in states if e['entity_id'].startswith('light.')]
for light in lights:
    print(f\"{light['entity_id']}: {light['state']}\")
"
```

### Track attribute changes
Read `last_changed` and `last_updated` timestamps to detect changes.

### Complex conditions
Use `attributes` for detailed state (e.g., `attributes.brightness`).
