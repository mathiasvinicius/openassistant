---
name: wppconnect-wajs
description: Run and operate a WPPConnect WA-JS WhatsApp gateway (Docker Compose). Provides start/stop/status helpers and a local env template.
---

# WPPConnect WA-JS Skill

This skill runs a WPPConnect WA-JS gateway in Docker Compose and provides helper scripts to manage the service.

## Quick start

1) Copy the env template and edit it:

```bash
cp config/wppconnect.env.example config/wppconnect.env
```

2) Start the gateway:

```bash
./scripts/start.sh
```

3) Check status/logs:

```bash
./scripts/status.sh
./scripts/logs.sh
```

4) Stop the gateway:

```bash
./scripts/stop.sh
```

## Notes

- The container runs inside this repo's `docker-compose.yml` as service `wppconnect-wajs`.
- This skill only manages the WA-JS gateway process. You still need to wire webhooks/events to OpenClaw.
- Keep `config/wppconnect.env` local (it may contain tokens or URLs).
