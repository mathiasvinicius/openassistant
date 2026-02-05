# OpenAssistant (OpenClaw via Docker)

This folder is prepared to run OpenClaw via Docker Compose, without needing the full source repo checkout.

## Git / privacy (important)

This repo is meant to be safe to push to GitHub. Do **not** commit personal data:

- `.env` (API keys, tokens)
- `data/openclaw.json*` (local runtime config)
- `data/agents/**` (provider auth profiles + sessions)
- `data/credentials/**` (channel creds + OAuth tokens)
- `data/workspace/MEMORY.md` and local `MEMORY.md` (assistant memory)

If you want to move your "assistant consciousness" (memory + auth + creds) to another machine without committing it:

```bash
./scripts/export_private_overlay.sh
```

Copy `./private-overlay/` to the new machine, then:

```bash
./scripts/import_private_overlay.sh
```

## Start

```bash
cp .env.example .env
chmod +x ./docker-setup.sh
./docker-setup.sh
```

If you don't have `data/ui/certs/openclaw.crt` and `data/ui/certs/openclaw.key` yet:

```bash
./scripts/gen_ui_certs.sh 172.16.0.2
```

Then open:

- http://127.0.0.1:18789/

Note: this setup now runs a small nginx front-proxy (`openclaw-ui`) on port 18789 to inject `./data/ui/theme.css`.
The actual gateway listens on port 18790.

LAN access: the proxy serves HTTPS so the Control UI works in a secure context when accessed via an IP.
Use:

- https://172.16.0.2:18789/

The certificate is self-signed; your browser will show a warning the first time.

If the UI shows "unauthorized", get a tokenized dashboard link:

```bash
docker compose run --rm openclaw-cli dashboard --no-open
```

## Useful commands

```bash
docker compose logs -f openclaw-gateway
docker compose logs -f openclaw-ui
docker compose exec openclaw-gateway openclaw gateway health --token "$OPENCLAW_GATEWAY_TOKEN"
docker compose run --rm openclaw-cli channels login
```

## Configure (wizard)

Interactive configuration wizard (workspace, model, gateway, channels, skills, etc.):

```bash
docker compose exec openclaw-gateway openclaw configure
```

Configure only the model section (swap LLM/provider defaults):

```bash
docker compose exec openclaw-gateway openclaw configure --section model
```

Note: provider authentication is managed separately (examples below).

## Model (LLM) management

Show current default model:

```bash
docker compose exec -T openclaw-gateway openclaw config get agents.defaults.model.primary
```

List configured models:

```bash
docker compose exec -T openclaw-gateway openclaw models list
```

Set the default model (example):

```bash
docker compose exec -T openclaw-gateway openclaw models set google/gemini-2.5-flash-lite
```

Show configured model status:

```bash
docker compose exec -T openclaw-gateway openclaw models status --plain
```

### Provider auth (API key / OAuth)

OpenClaw supports multiple auth profiles per provider. To authenticate a provider (including OAuth where supported), use:

```bash
docker compose exec -T openclaw-gateway openclaw models auth --help
```

Then re-run `openclaw configure --section model` (or `openclaw models set ...`) to point the agent to the newly authenticated provider/model.

## Channels (WhatsApp)

Login wizard for channels (QR where applicable):

```bash
docker compose exec -it openclaw-gateway openclaw channels login
```

Login only WhatsApp channel:

```bash
docker compose exec -it openclaw-gateway openclaw channels login --channel whatsapp
```

List channels:

```bash
docker compose exec -T openclaw-gateway openclaw channels list
```

## Restart / apply config

Restart the gateway container:

```bash
docker compose restart openclaw-gateway
```

If you changed `.env`, recreate the service so env vars are applied:

```bash
docker compose up -d --force-recreate openclaw-gateway
```

## wacli (WhatsApp CLI)

Authenticate `wacli` (separate from OpenClaw's WhatsApp channel; persists under the OpenClaw volume):

```bash
docker compose exec openclaw-gateway wacli auth --store /home/node/.openclaw/wacli
```

Check status:

```bash
docker compose exec -T openclaw-gateway wacli auth status --store /home/node/.openclaw/wacli
```

## Skills in this workspace

Workspace skills live on the host at:

- `./data/skills` (mounted into the container at `~/.openclaw/skills`)

Local notes / checklist (persisted in the workspace):

- `./data/workspace/MEMORY.md`

### wacli-monitor (WhatsApp summaries)

This repo includes a custom `wacli-monitor` daemon that:

- syncs WhatsApp via `wacli` into `./data/wacli/wacli.db`
- batches messages per-chat (groups wait longer)
- downloads media on-demand (`wacli media download`) so the LLM can describe images
- asks the OpenClaw agent to produce a **short summary** (no message replication)
- delivers the summary to you via the OpenClaw WhatsApp bot (and can send audio for long group blocks using Azure TTS)

Config:

- `./data/skills/wacli-monitor/config/wacli-config.yaml`
- Template (safe to commit):
  - `./data/skills/wacli-monitor/config/wacli-config.example.yaml` (copy to `wacli-config.yaml`)

Key settings (most edited):

```yaml
monitor:
  conversation_batching:
    default_wait: "2m"     # DMs
    group_wait: "30m"      # groups

notifications:
  whatsapp:
    download_media: true
    media_max_mb: 15
  delivery:
    mode: "openclaw"
    openclaw_target: "+55..." # your number
    audio:
      enabled: true
      only_groups: true
      min_messages: 8
      min_chars: 450
```

Logs (inside the container):

```bash
docker compose exec -T openclaw-gateway tail -f /home/node/.openclaw/workspace/logs/wacli/daemon.log
```

Restart the daemon (inside the container):

```bash
docker compose exec -T openclaw-gateway sh -lc 'kill $(cat /home/node/.openclaw/workspace/logs/wacli/.daemon.pid) 2>/dev/null || true'
```

Notes:

- If you see `Resumo indisponível...`, it usually means the LLM call failed (rate limit / auth / provider error). The daemon still sends a minimal non-empty notification.
- Image-only messages can arrive with `text=NULL`; the monitor now tags them like `[image]` and downloads the file so the LLM can describe it.

Notification flow (diagram):

```text
WhatsApp (mobile / linked device)
  |
  | 1) wacli sync --once --json  (runs periodically; updates wacli.db)
  v
wacli store (SQLite): ~/.openclaw/wacli/wacli.db
  |
  | 2) wacli-monitor daemon
  |    - reads new rows
  |    - blacklist/filter
  |    - per-chat batching (DM: default_wait, group: group_wait)
  v
Ready conversation block (per chat_jid)
  |
  | 3) Media handling (optional)
  |    - if media_type and no/empty text -> placeholder [image]/[video]/...
  |    - wacli media download --chat <jid> --id <msg_id> --json
  |    - attach MEDIA_PATH=<local file> into the LLM prompt (never echoed back)
  v
LLM summary (OpenClaw agent)
  |
  | 4) openclaw agent --json
  |    - returns short bullets (no message replication)
  |    - if fails -> fallback "Resumo indisponivel..."
  v
Delivery decision
  |
  | 5a) Text summary
  |     openclaw message send --channel whatsapp --target <your number>
  |
  | 5b) Audio summary (if enabled + big block + (only_groups))
  |     azure-tts speak.sh -> OGG/Opus
  |     openclaw message send --media <ogg> --message "(audio) Resumo: <chat>"
  v
You (owner/admin WhatsApp)
```

### Google Calendar skill (OAuth)

Authenticate once (opens a local callback server and prints a Google login URL):

```bash
docker compose exec openclaw-gateway /home/node/.openclaw/skills/google-calendar/scripts/auth.sh
```

List next events:

```bash
docker compose exec -T openclaw-gateway /home/node/.openclaw/skills/google-calendar/scripts/list.sh 10
```

Create an event:

```bash
docker compose exec -T openclaw-gateway /home/node/.openclaw/skills/google-calendar/scripts/add.sh "Teste OpenClaw" "2026-02-04T10:00:00-03:00" "2026-02-04T10:15:00-03:00"
```

### Azure TTS skill (online)

Generate an OGG/Opus voice note using Azure Speech:

```bash
docker compose exec -T openclaw-gateway /home/node/.openclaw/skills/azure-tts/scripts/speak.sh "Ola, teste de voz Azure."
```

List pt-BR voices:

```bash
docker compose exec -T openclaw-gateway /home/node/.openclaw/skills/azure-tts/scripts/list_voices.sh
```

Pick/test voices in a loop (generates sample audio and optionally saves as default to `./data/skills/azure-tts/config.json`):

```bash
docker compose exec -it openclaw-gateway /home/node/.openclaw/skills/azure-tts/scripts/set_voice.sh
```

Note: `wacli-monitor` can use this skill to send long group summaries as WhatsApp voice notes.

### Whisper Transcribe skill (local)

Transcribe a WhatsApp inbound OGG file to a timestamped `.txt` transcript:

```bash
docker compose exec -T openclaw-gateway /home/node/.openclaw/skills/whisper-transcribe/scripts/transcribe.sh /home/node/.openclaw/media/inbound/fb3c68a5-2299-4aff-af14-3e7a723ea320.ogg --model medium --print
```

### Default STT (auto-transcribe inbound audio)

This workspace is configured to auto-transcribe inbound audio attachments (e.g. WhatsApp voice notes)
using the local Whisper CLI (CPU) in Portuguese.

- Config: `tools.media.audio`
- Model: `medium`
- Language: `pt` (Whisper uses `pt` for pt-BR)

If you change `data/openclaw.json`, restart the gateway:

```bash
docker compose restart openclaw-gateway
```

### TOON (JSON compression)

This workspace ships a small plugin that converts fenced JSON blocks into a compact
TOON format (Token-Optimized Object Notation) to reduce prompt size.

- Plugin id: `toon`
- Location: `./data/workspace/.openclaw/extensions/toon/`
- Config: `plugins.entries.toon.config` in `./data/openclaw.json`

After changing the plugin code or config, restart:

```bash
docker compose restart openclaw-gateway
```
