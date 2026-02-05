---
name: wacli-monitor
description: WhatsApp message monitoring daemon with intelligent batching, blacklist filtering, and multi-strategy notifications. Continuous sync with customizable notification delays for direct messages (instant) and groups (batched). Economizes tokens by capturing only essential fields and collapsing messages into summaries. v3 PID-Safe prevents duplicate instances and handles network timeouts gracefully.
---

# WhatsApp Monitor Skill (wacli-monitor) - v3 PID-Safe (Summaries)

Continuous WhatsApp monitoring with smart batching + blacklist filtering. This version is tuned to:

- summarize group/dm activity (no raw message replication)
- download media on-demand so the LLM can describe images
- deliver summaries via OpenClaw WhatsApp bot (and optionally as audio via Azure TTS)

## Overview

Monitor WhatsApp messages in real-time with:
- ✅ **Continuous sync** - Always connected to WhatsApp
- 🔄 **Intelligent batching** - Accumulate group messages, notify instantly on DMs
- 🚫 **Blacklist filtering** - Exclude unwanted groups/contacts
- 🔒 **PID-Safe locking** (v3) - Only one daemon instance can run
- 🔄 **Retry logic** (v3) - Auto-recovery from `wacli sync` timeouts
- 💬 **Multi-strategy routing** - Different rules for different chats
- 📊 **Token-efficient** - Only capture essential fields
- 📝 **Structured logging** - JSONL format for easy processing

## Version History

- **v3 (Current)** - PID-safe locking, retry logic, graceful shutdown
  - `wacli-daemon.py` → wacli-daemon-v3.py
  - Prevents duplicate instances
  - Auto-recovery from network timeouts
  
- **v2** - Conversation batching
  - `wacli-daemon-v2.py`
  - Batch messages from same person
  
- **v1** - Initial daemon
  - `wacli-daemon.py` (original)

## Quick Start

### 1. Configure

Copy the template and edit your local config:

```bash
cp config/wacli-config.example.yaml config/wacli-config.yaml
```

Then edit `config/wacli-config.yaml`:

```yaml
blacklist:
  groups:
    - "Group Name To Ignore"
    - "Propaganda"

monitor:
  conversation_batching:
    enabled: true
    default_wait: "2m"   # DMs
    group_wait: "30m"    # groups

notifications:
  delivery:
    mode: "openclaw"
    openclaw_channel: "whatsapp"
    openclaw_target: "+5511999999999"   # your number
    audio:
      enabled: true
      only_groups: true
      min_messages: 8
      min_chars: 450
  whatsapp:
    download_media: true
    media_max_mb: 15
```

### 2. Run the daemon

```bash
# In this repo the daemon is typically started inside the `openclaw-gateway` container.
# Logs are written to: ~/.openclaw/workspace/logs/wacli/daemon.log

nohup python3 {baseDir}/scripts/wacli-daemon.py >/dev/null 2>&1 &
```

### 3. Monitor

```bash
# Systemd
sudo journalctl -u wacli-daemon -f

# Or direct log
tail -f ~/.openclaw/workspace/logs/wacli/daemon.log
```

## Configuration

See `config/wacli-config.yaml` template.

### Conversation Batching

Wait for people to finish typing before notifying:

```yaml
monitor:
  conversation_batching:
    enabled: true
    default_wait: "2m"          # Aguarda 2 min da mesma pessoa
    short_message_threshold: 50 # Se <50 chars, aguarda mais
    vip_list:                   # Notifica IMEDIATAMENTE
      - "Mom"
      - "Boss"
      - "Emergency"
```

**How it works:**

1. Person sends "Olá" (short) → Wait 2 minutes
2. Person sends "Tudo bem? Estou com problemas..." → Still waiting
3. 2 minutes pass with no new messages → Send all together
4. vs. VIP sends anything → Notify immediately

**Examples:**

```
User sends: "Hi"
→ Wait 2 min (short message)
→ User sends: "Are you there?"
→ After 2 min total: Send both messages together

vs.

Mom sends: "Hi"
→ Notify IMMEDIATELY (VIP list)
```

### Strategies

```yaml
strategies:
  # Direct messages (individuals)
  direct_messages:
    type: "individual"
    contacts: []            # Empty = all DMs
    notify_delay: "0s"      # Instant
    summary: false
    priority: "high"
  
  # Groups (default: batch 10 min)
  group_pais_escola:
    type: "group"
    groups: ["Grupo Pais Escola 3° Ano CP - 2026"]
    notify_delay: "10m"     # Wait before batching
    summary: true           # Collapse into summary
    collapse_threshold: 3   # If >3 msgs, just send summary
    priority: "normal"
  
  # Urgent groups (5 min)
  group_urgent:
    type: "group"
    groups: ["Work Urgent"]
    notify_delay: "5m"
    summary: false
    priority: "high"
```

### Blacklist

```yaml
blacklist:
  groups:
    - "Group Name"
    - "Propaganda"
  
  contacts:
    - "Bot notifications"
    - "Automated service"
```

### Fields Captured (Token Economy)

Default captures only essential:
- `msg_id` - Message ID
- `timestamp` - When sent
- `chat_name` - Group/contact
- `sender_name` - Who sent
- `text` - Content (first 200 chars)
- `media_type` - Type of media

## Files

- `SKILL.md` - This documentation
- `CONVERSTION_BATCHING.md` - Conversation batching guide
- `scripts/wacli-daemon.py` - Main daemon (v1)
- `scripts/wacli-daemon-v2.py` - Daemon with conversation batching
- `scripts/wacli-notify-changes.py` - Real-time change notifications
- `scripts/install-daemon.sh` - Systemd installer
- `config/wacli-config.yaml` - Configuration template
- `references/advanced.md` - Advanced topics

## Output format

The daemon builds a compact per-chat "timeline" and asks the OpenClaw agent to:

- describe images using a downloaded local file (media is downloaded with `wacli media download`)
- produce a short summary (max ~6 bullets)
- avoid leaking technical IDs or local paths

Delivery:

- default: `openclaw message send` (WhatsApp bot -> your number)
- optional: audio note via `azure-tts` when a group block is large

## Commands

```bash
# Systemd (if available)
sudo systemctl status wacli-daemon
sudo systemctl restart wacli-daemon
sudo journalctl -u wacli-daemon -f

# Direct (no systemd)
ps aux | grep wacli-daemon
tail -f ~/.openclaw/workspace/logs/wacli/daemon.log
kill $(cat ~/.openclaw/workspace/logs/wacli/.daemon.pid)

# Monitor for changes (audio alerts)
python3 {baseDir}/scripts/wacli-notify-changes.py
```

## Troubleshooting

### "Daemon já rodando (PID XXXX). Abortando."

**Cause:** Another daemon instance is running.

**Fix:**
```bash
# Check if PID is actually running
ps -p XXXX

# If not running (PID doesn't exist), remove lock and restart
rm ~/.openclaw/workspace/logs/wacli/.daemon.pid
python3 {baseDir}/scripts/wacli-daemon.py
```

### "wacli sync ... timed out after 60 seconds"

**Cause:** WhatsApp connection slow or network issues.

**Fix:**
- Daemon auto-retries with backoff (15s, 20s, 25s)
- If persists, check WhatsApp connectivity: `wacli sync --once`
- Monitor logs: `tail -f ~/.openclaw/workspace/logs/wacli/daemon.log`

### Multiple "Lock adquirido" messages in logs

**Cause:** Daemon restarting repeatedly (likely crash).

**Fix:**
```bash
# Check last error in logs
tail -30 ~/.openclaw/workspace/logs/wacli/daemon.log | grep ERROR

# Verify config is valid
python3 -c "import yaml; yaml.safe_load(open('skills/wacli-monitor/config/wacli-config.yaml'))"

# Restart daemon
kill $(cat ~/.openclaw/workspace/logs/wacli/.daemon.pid) 2>/dev/null || true
sleep 2
python3 {baseDir}/scripts/wacli-daemon.py
```

### Daemon stops after a few minutes

**Cause:** unhandled exception or signal.

**Fix:**
- Run in foreground to see errors:
  ```bash
  cd ~/.openclaw/workspace
  python3 {baseDir}/scripts/wacli-daemon.py
  ```
- Check system resources: `free -h`, `df -h`
- See `PID_SAFETY.md` for advanced debugging

See `references/advanced.md` and `PID_SAFETY.md` for:
- Installation issues
- Configuration debugging
- Token optimization
- PID lock troubleshooting
- Integration examples
