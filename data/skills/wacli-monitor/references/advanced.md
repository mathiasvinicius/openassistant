# Advanced Topics - wacli-monitor

## Installation Troubleshooting

### Problem: "wacli: command not found"

First authenticate wacli:
```bash
docker compose exec -T openclaw-gateway wacli auth
# Scan QR code with WhatsApp Linked Devices
```

Verify it works:
```bash
docker compose exec -T openclaw-gateway wacli chats list
```

### Problem: "Permission denied" when running daemon

The script needs sudo. If you want to run without password prompt:

```bash
sudo visudo
# Add at the end:
# node ALL=(ALL) NOPASSWD: /bin/systemctl
```

### Problem: Python dependencies missing

The daemon needs `pyyaml`. Install it:

```bash
pip3 install pyyaml
# or
python3 -m pip install pyyaml
```

## Configuration Patterns

### Pattern 1: VIP Contacts (instant notification)

```yaml
strategies:
  vip:
    type: "individual"
    contacts: ["Mom", "Boss", "Doctor"]
    notify_delay: "0s"
    priority: "high"
```

### Pattern 2: Work vs Personal

```yaml
blacklist:
  groups:
    - "Work Updates"
    - "Company Announcements"

strategies:
  personal:
    type: "individual"
    notify_delay: "0s"
  
  work_only:
    groups: ["Work - Urgent Only"]
    notify_delay: "5m"
```

### Pattern 3: Minimal notifications (save tokens)

```yaml
strategies:
  batched:
    type: "group"
    notify_delay: "30m"      # Batch 30 minutes
    summary: true
    collapse_threshold: 1    # Always summary

fields:
  capture:
    - "msg_id"
    - "chat_name"
    - "sender_name"
    - "text"
```

### Pattern 4: Time-based (quiet hours)

Use cron to stop daemon during night:

```bash
# Stop at 23:00
0 23 * * * sudo systemctl stop wacli-daemon

# Start at 08:00
0 8 * * * sudo systemctl start wacli-daemon
```

## Token Usage Analysis

### What uses tokens?

1. **Initial sync** - Fetching messages from DB (~5 tokens)
2. **Processing** - Analyzing/filtering (~2 tokens)
3. **Notification** - Sending to WhatsApp (~3 tokens)

**Daily estimate with optimal config:**
- 10-20 tokens/day for typical usage
- ~50 tokens/day for heavy usage (many groups)

### How to minimize

1. **Enable summaries** - Collapse many msgs to one
   ```yaml
   summary: true
   collapse_threshold: 2
   ```

2. **Increase delays** - Batch longer
   ```yaml
   notify_delay: "30m"  # Instead of 10m
   ```

3. **Reduce captured fields** - Only essentials
   ```yaml
   fields:
     capture:
       - "msg_id"
       - "chat_name"
       - "sender_name"
       - "text"
   ```

4. **Larger blacklist** - Fewer msgs processed
   ```yaml
   blacklist:
     groups:
       - "Everyone"  # Add all non-essential groups
   ```

## Debugging

### View daemon output in real-time

```bash
sudo journalctl -u wacli-daemon -f
```

### See only errors

```bash
sudo journalctl -u wacli-daemon -f --priority=err
```

### Check processed messages

```bash
# Last 20 processed messages
tail -20 ~/.openclaw/workspace/logs/wacli/messages.jsonl | python3 -m json.tool
```

### Monitor message flow

```bash
# Watch for new messages
watch -n 1 'tail -1 ~/.openclaw/workspace/logs/wacli/messages.jsonl'
```

### Check state/deduplication

```bash
cat ~/.openclaw/workspace/logs/wacli/.daemon_state.json | python3 -m json.tool
```

## Integration Examples

### Send to Discord instead of WhatsApp

Modify `notify_messages()` in `wacli-daemon.py`:

```python
def notify_messages():
    # Instead of wacli send:
    import requests
    
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    
    for message in messages:
        requests.post(webhook_url, json={
            "content": message["text"],
            "username": message["sender_name"]
        })
```

### Log to external database

Add to `process_messages()`:

```python
import requests

# Send to analytics service
analytics_url = "https://myapi.com/log"
requests.post(analytics_url, json={
    "chat": msg["chat_name"],
    "sender": msg["sender_name"],
    "timestamp": msg["timestamp"]
})
```

### Trigger Home Assistant automation

```python
# When VIP message arrives
import requests

ha_url = os.getenv("HOMEASSISTANT_URL")
ha_token = os.getenv("HOMEASSISTANT_TOKEN")

if message["priority"] == "high":
    requests.post(
        f"{ha_url}/api/services/automation/trigger",
        headers={"Authorization": f"Bearer {ha_token}"},
        json={"entity_id": "automation.incoming_vip_message"}
    )
```

## Performance Tuning

### High message volume (>50/min)

Increase batch intervals:
```yaml
monitor:
  processing:
    batch_interval: "30s"    # Was 10s
    max_messages_per_batch: 100
```

### Low latency (minimize delay)

```yaml
monitor:
  processing:
    batch_interval: "2s"
  
strategies:
  urgent:
    notify_delay: "0s"
```

## Scheduling

### Run daemon only during business hours

Create `/etc/systemd/system/wacli-daemon.timer`:

```ini
[Unit]
Description=Run wacli-daemon during business hours

[Timer]
OnCalendar=Mon-Fri *-*-* 09:00:00
OnCalendar=Mon-Fri *-*-* 17:01:00

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable --now wacli-daemon.timer
```

## Backup & Restore

### Backup configuration

```bash
cp ~/.openclaw/workspace/config/wacli-config.yaml backup-config-$(date +%Y%m%d).yaml
```

### Backup message history

```bash
cp ~/.openclaw/workspace/logs/wacli/messages.jsonl backup-messages-$(date +%Y%m%d).jsonl
```

### Export to CSV

```bash
python3 << 'EOF'
import json
import csv

with open("messages.jsonl") as f:
    with open("messages.csv", "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["timestamp", "chat_name", "sender_name", "text"])
        writer.writeheader()
        for line in f:
            writer.writerow(json.loads(line))

print("Exported to messages.csv")
EOF
```

## Security Notes

1. **Token security** - Keep `HOMEASSISTANT_TOKEN` in `.env`, not in config
2. **Message privacy** - Logs contain message text. Restrict file permissions:
   ```bash
   chmod 600 ~/.openclaw/workspace/logs/wacli/messages.jsonl
   ```
3. **Systemd access** - Only root can manage the service. This is intentional.

## License

Same as OpenClaw and wacli
