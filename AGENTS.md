# Repository Guidelines

This repository packages an OpenClaw workspace as a Docker Compose project, plus local skills and helper scripts.
It is designed to be safe to publish publicly while keeping credentials and “assistant state” local.

## Project Structure & Module Organization

- `docker-compose.yml`: services (`openclaw-gateway`, `openclaw-ui`, optional CLI jobs).
- `.env` / `.env.example`: runtime environment (tokens/keys live only in `.env`).
- `data/`: persisted workspace volume (mounted into the container as `~/.openclaw/`).
  - `data/skills/`: custom skills (e.g. `wacli-monitor`, `azure-tts`, `whisper-transcribe`).
  - `data/workspace/MEMORY.md`: local operational notes (do not commit secrets).
  - `data/openclaw.json*`: local gateway config (treat as private).
- `scripts/`: helper utilities (cert generation, private overlay export/import, etc.).

## Build, Test, and Development Commands

Run and update services:

```bash
docker compose up -d
docker compose restart openclaw-gateway
docker compose logs -f openclaw-gateway
```

Interactive configuration:

```bash
docker compose exec openclaw-gateway openclaw configure
docker compose exec openclaw-gateway openclaw configure --section model
```

WhatsApp monitoring logs:

```bash
docker compose exec -T openclaw-gateway tail -f /home/node/.openclaw/workspace/logs/wacli/daemon.log
```

## Coding Style & Naming Conventions

- Prefer small, composable scripts under `data/skills/<skill>/scripts/`.
- Python: 4-space indentation, explicit error handling, log to `~/.openclaw/workspace/logs/...`.
- Shell: `bash`, `set -euo pipefail` where appropriate, avoid interactive prompts in containers.

## Testing Guidelines

There is no formal test harness in this repo. For changes that affect runtime behavior:

- Validate syntax (`python3 -m py_compile <file>.py`).
- Smoke-test inside the container (run the script/command once and check logs).

## Commit & Pull Request Guidelines

- Keep commits focused: one skill/feature per commit when possible.
- Do not commit secrets or personal state. Keep `.env`, `data/openclaw.json*`, `data/agents/**`,
  `data/credentials/**`, and `MEMORY.md` out of PRs.
- PRs should include: what changed, how to run/verify, and any config keys added/changed.

## Security & Configuration Tips

- Use `./scripts/export_private_overlay.sh` to move local state between machines without committing it.
- If exposing the UI on LAN, use the HTTPS proxy (`openclaw-ui`) and self-signed certs under `data/ui/certs/`.
