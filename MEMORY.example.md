# OpenAssistant Local Memory (template)

This repo keeps only *non-personal* operational notes.

Keep your real assistant memory, tokens, and auth profiles out of git:
- `.env` (secrets)
- `data/openclaw.json` (local runtime config)
- `data/agents/**` (provider auth profiles, sessions)
- `data/credentials/**` (channel auth, OAuth tokens)
- `data/workspace/MEMORY.md` (personal memory)

## Paths

- Project root: `/home/casaos/containers/openassistant`
- Host OpenClaw data: `./data` (mounted to `/home/node/.openclaw` in the gateway container)
- Skills: `./data/skills` (mounted to `/home/node/.openclaw/skills`)

## Core Commands

- Start: `docker compose up -d`
- Restart gateway: `docker compose restart openclaw-gateway`
- Recreate gateway (reload `.env`): `docker compose up -d --force-recreate openclaw-gateway`

