---
name: voicemonkey
description: Control Alexa via Voice Monkey API (announce TTS and trigger routines).
metadata:
  {
    "openclaw":
      {
        "emoji": "🗣️",
        "requires": { "bins": ["curl"], "env": ["VOICEMONKEY_TOKEN"] },
        "primaryEnv": "VOICEMONKEY_TOKEN"
      }
  }
---

# Voice Monkey (Alexa)

Control Alexa via Voice Monkey API.

## Setup

Set your token:

- Env var: `VOICEMONKEY_TOKEN`
- Optional default device: `VOICEMONKEY_DEVICE` (default: `cozinha`)

## TTS announcement (Alexa speak)

```bash
{baseDir}/scripts/announce.sh "Mensagem" [device]
```

## Trigger a routine (Monkey)

```bash
{baseDir}/scripts/trigger.sh "nome_do_monkey"
```

