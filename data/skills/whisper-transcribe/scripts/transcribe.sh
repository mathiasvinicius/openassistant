#!/usr/bin/env bash
set -euo pipefail

# Based on /home/louise/scripts/transcribe_whisper.sh, adapted for OpenClaw.
#
# - Accepts absolute paths OR workspace-relative paths (e.g. media/...).
# - Writes transcripts into ~/.openclaw/workspace/data/transcripts

INPUT="${1:-}"
shift || true

MODEL="${WHISPER_MODEL:-small}"
LANG="${WHISPER_LANGUAGE:-Portuguese}"
TASK="${WHISPER_TASK:-transcribe}"
PRINT="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="${2:-}"; shift 2;;
    --lang|--language) LANG="${2:-}"; shift 2;;
    --task) TASK="${2:-}"; shift 2;;
    --print) PRINT="1"; shift 1;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [ -z "$INPUT" ]; then
  echo "Usage: transcribe.sh <audio_path> [--model small|medium|large] [--lang Portuguese] [--task transcribe|translate] [--print]" >&2
  exit 2
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg not found." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found." >&2
  exit 1
fi

WORKSPACE="${OPENCLAW_WORKSPACE_DIR:-/home/node/.openclaw/workspace}"

# Allow passing workspace-relative paths (media/..., data/...).
if [[ "$INPUT" != /* ]]; then
  AUDIO="${WORKSPACE}/${INPUT}"
else
  AUDIO="$INPUT"
fi

if [ ! -f "$AUDIO" ]; then
  echo "ERROR: file not found: $AUDIO" >&2
  exit 2
fi

# Make sure whisper is present (it is installed in the OpenClaw image).
if ! python3 -c "import whisper" >/dev/null 2>&1; then
  echo "ERROR: python module 'whisper' not found. Rebuild the image or install openai-whisper." >&2
  exit 1
fi

OUT_DIR="${WORKSPACE}/data/transcripts"
mkdir -p "$OUT_DIR"

BASENAME="$(basename "$AUDIO")"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_PREFIX="$OUT_DIR/${BASENAME%.*}_$STAMP"

# Whisper CLI expects a file path; it uses ffmpeg internally.
python3 -m whisper "$AUDIO" \
  --language "$LANG" \
  --task "$TASK" \
  --model "$MODEL" \
  --output_format txt \
  --output_dir "$OUT_DIR" \
  --fp16 False \
  >/dev/null

# Whisper writes <original_filename>.txt into output_dir.
OUT_TXT="$OUT_DIR/${BASENAME%.*}.txt"
FINAL_TXT="$OUT_PREFIX.txt"

if [ -f "$OUT_TXT" ]; then
  mv -f "$OUT_TXT" "$FINAL_TXT"
fi

echo "TRANSCRIPT: $FINAL_TXT"

if [ "$PRINT" = "1" ]; then
  echo "---"
  cat "$FINAL_TXT"
fi

