---
name: azure-tts
description: Generate pt-BR voice notes online using Azure Speech (chunked TTS) and output an OGG/Opus file usable as a WhatsApp voice note.
metadata:
  {
    "openclaw":
      {
        "emoji": "☁️",
        "os": ["linux"],
        "requires": { "bins": ["python3", "ffmpeg"], "env": ["AZURE_SPEECH_KEY"] },
        "primaryEnv": "AZURE_SPEECH_KEY"
      }
  }
---

# Azure Speech TTS (pt-BR) -> OGG/Opus

This skill synthesizes text using Azure Cognitive Services Speech, chunks long text, concatenates WAV chunks, and converts to OGG/Opus (WhatsApp voice-note friendly).

## Setup (.env)

Add to `/home/casaos/containers/openclaw/.env`:

```bash
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=brazilsouth
AZURE_SPEECH_VOICE=pt-BR-BrendaNeural
AZURE_SPEECH_RATE=23%
MAX_CHARS_PER_CHUNK=900
```

Apply env changes:

```bash
cd /home/casaos/containers/openclaw
docker compose up -d --force-recreate openclaw-gateway
```

## Generate audio

```bash
{baseDir}/scripts/speak.sh "Texto para falar."
```

Output:

```text
MEDIA: media/tts/tts_<id>.ogg
```

Host file path:

- `./data/workspace/media/tts/tts_<id>.ogg`

## List voices (pt-BR)

```bash
{baseDir}/scripts/list_voices.sh
```

## Pick a default voice (no env var required)

This writes `config.json` inside the skill folder (persisted in `./data`).

```bash
{baseDir}/scripts/set_voice.sh
```
