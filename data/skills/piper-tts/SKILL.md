---
name: piper-tts
description: Generate pt-BR voice notes locally (Piper TTS) and send them as WhatsApp voice messages.
metadata:
  {
    "openclaw":
      {
        "emoji": "🗣️",
        "os": ["linux"],
        "requires": { "bins": ["ffmpeg"] }
      }
  }
---

# Piper TTS (pt-BR) -> WhatsApp voice note

This skill uses the local Piper TTS engine to generate an OGG/Opus file compatible with WhatsApp voice notes.

## Generate audio

Run:

```bash
/home/node/.openclaw/piper/speak.sh "Texto que voce quer que eu fale."
```

It prints a line like:

```text
MEDIA: media/tts/tts_123.ogg
```

## Send as voice note (WhatsApp)

Use `message` with `asVoice: true`:

```js
message({
  action: "send",
  channel: "whatsapp",
  to: "+55...",
  media: "media/tts/tts_123.ogg",
  asVoice: true,
  message: "Audio via Piper"
})
```

## Notes

- Requires WhatsApp channel to be configured and logged in.
- The generator script is: `/home/node/.openclaw/piper/speak.sh`

