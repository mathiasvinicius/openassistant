---
name: google-calendar
description: Connect to Google Calendar (OAuth) and list/create events from the local OpenClaw container.
metadata:
  {
    "openclaw":
      {
        "emoji": "🗓️",
        "os": ["linux"],
        "requires": { "bins": ["python3"] }
      }
  }
---

# Google Calendar (OAuth)

This skill uses Google OAuth (installed app) to access your Google Calendar.

## Setup

1) Put your OAuth client JSON on the OpenClaw volume (recommended):

- Host path: `./data/credentials/google-calendar/client_secret.json`
- Container path: `/home/node/.openclaw/credentials/google-calendar/client_secret.json`

2) (Optional) Set env vars (in `/home/casaos/containers/openclaw/.env`):

```bash
# Defaults (you can omit all of this if you use the default paths):
# GCAL_CLIENT_SECRET_PATH=/home/node/.openclaw/credentials/google-calendar/client_secret.json
# GCAL_TOKEN_PATH=/home/node/.openclaw/credentials/google-calendar/token.json
# GCAL_CALENDAR_ID=primary
# GCAL_AUTH_MODE=localserver
# GCAL_OAUTH_HOST=localhost
# GCAL_OAUTH_PORT=8765

# Alternative (if you don't want to store a JSON file on disk):
# GCAL_CLIENT_ID=...
# GCAL_CLIENT_SECRET=...
```

3) Authenticate once (prints a URL + waits for callback):

```bash
{baseDir}/scripts/auth.sh
```

## Usage

List next events (default 10):

```bash
{baseDir}/scripts/list.sh 10
```

Create an event:

```bash
{baseDir}/scripts/add.sh "Reuniao" "2026-02-05T10:00:00-03:00" "2026-02-05T11:00:00-03:00"
```

Notes:

- Credentials + tokens are stored under `/home/node/.openclaw/credentials/google-calendar/` (persisted by `./data` volume).
- If auth expires or you revoke access, re-run `auth.sh`.
