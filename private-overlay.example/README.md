# private-overlay (example)

This folder is **NOT** committed. It exists to let you move your local assistant
state (secrets + OAuth tokens + memory) between machines.

Workflow:

1) On the current machine (where everything is configured):
   - `scripts/export_private_overlay.sh`

2) Copy `private-overlay/` to the new machine into the repo root.

3) On the new machine:
   - `scripts/import_private_overlay.sh`
   - `docker compose up -d`

What gets copied:
- `.env`
- `data/openclaw.json`
- `data/agents/main/agent/auth-profiles.json`
- `data/credentials/` (channel/OAuth tokens)
- `data/workspace/MEMORY.md` (personal assistant memory)

