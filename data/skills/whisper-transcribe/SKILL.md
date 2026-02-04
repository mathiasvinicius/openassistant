---
name: whisper-transcribe
description: Transcribe audio (e.g. WhatsApp OGG voice notes) to text locally using Whisper (openai-whisper). Saves a .txt transcript into the OpenClaw workspace.
metadata:
  {
    "openclaw":
      {
        "emoji": "📝",
        "os": ["linux"],
        "requires": { "bins": ["python3", "ffmpeg"] }
      }
  }
---

# Whisper Transcribe (local)

Transcribe an audio file (OGG/MP3/WAV/etc.) into a timestamped `.txt` transcript inside the OpenClaw workspace.

## Defaults

- Model: `small` (fast)
- Language: `Portuguese`
- Task: `transcribe`

You can override via flags or env vars.

## Usage

Transcribe an absolute path:

```bash
{baseDir}/scripts/transcribe.sh /path/to/audio.ogg
```

Transcribe a workspace-relative path (recommended for OpenClaw media):

```bash
{baseDir}/scripts/transcribe.sh media/inbound/some_audio.ogg
```

Choose a better model:

```bash
{baseDir}/scripts/transcribe.sh media/inbound/some_audio.ogg --model medium
```

Print the transcript after writing it:

```bash
{baseDir}/scripts/transcribe.sh media/inbound/some_audio.ogg --print
```

## Env vars (optional)

```bash
WHISPER_MODEL=small
WHISPER_LANGUAGE=Portuguese
WHISPER_TASK=transcribe
```

## Output

- Writes to: `~/.openclaw/workspace/data/transcripts/`
- Prints:
  - `TRANSCRIPT: <path>`
  - optionally the transcript content (when `--print` is used)

