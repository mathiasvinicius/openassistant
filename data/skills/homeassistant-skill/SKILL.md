---
name: homeassistant-skill
description: Control Home Assistant entities (lights, switches, scenes, automations, climate). Execute states queries, toggle devices, trigger automations, set climate modes, and manage entity properties via REST API with authenticated requests.
---

# Home Assistant Skill

Interact with your Home Assistant instance through REST API. Control lights, switches, scenes, automations, climate devices, and query entity states.

## Setup

1. **Environment Variables:**
   - `HOMEASSISTANT_URL` - Base URL (e.g., `http://172.16.0.2:8123/`)
   - `HOMEASSISTANT_TOKEN` - Long-lived access token

2. **Get Token:**
   - Log in to Home Assistant
   - Profile → Create Long-Lived Access Token
   - Store securely as env var

## Quick Commands

### Query States

List all entities:
```bash
scripts/ha_query.sh
```

Search by entity type:
```bash
scripts/ha_query.sh "light"
scripts/ha_query.sh "switch"
scripts/ha_query.sh "scene"
```

Get specific entity:
```bash
scripts/ha_query.sh "light.living_room"
```

### Control Lights

Turn on:
```bash
scripts/ha_control.sh light.living_room on
```

Turn off:
```bash
scripts/ha_control.sh light.living_room off
```

Brightness (0-255):
```bash
scripts/ha_control.sh light.living_room brightness 200
```

Color (RGB):
```bash
scripts/ha_control.sh light.living_room color 255 100 50
```

Toggle:
```bash
scripts/ha_control.sh light.living_room toggle
```

### Control Switches

Turn on/off:
```bash
scripts/ha_control.sh switch.device_name on
scripts/ha_control.sh switch.device_name off
```

Toggle:
```bash
scripts/ha_control.sh switch.device_name toggle
```

### Activate Scenes

```bash
scripts/ha_control.sh scene.hora_de_dormir activate
scripts/ha_control.sh scene.living_room_movie activate
```

### Trigger Automations

```bash
scripts/ha_control.sh automation.my_automation trigger
```

### Climate Control

Set temperature:
```bash
scripts/ha_control.sh climate.living_room temperature 22
```

Set mode:
```bash
scripts/ha_control.sh climate.living_room hvac_mode heat
# Modes: off, heat, cool, heat_cool, auto
```

### Advanced

See `references/api-guide.md` for:
- Attribute manipulation
- Complex state queries
- Error handling
- JSON payloads

## Entity ID Format

Home Assistant uses dot notation:
- `light.living_room` - A light entity named "living_room"
- `switch.kitchen` - A switch entity
- `scene.bedtime` - A scene
- `automation.morning_routine` - An automation
- `climate.bedroom` - A climate device

Use `scripts/ha_query.sh` to discover entity IDs.
