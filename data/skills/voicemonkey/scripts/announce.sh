#!/usr/bin/env bash
set -euo pipefail

TEXT="${1:-}"
DEVICE="${2:-${VOICEMONKEY_DEVICE:-cozinha}}"
TOKEN="${VOICEMONKEY_TOKEN:-}"

if [[ -z "$TEXT" ]]; then
  echo "Usage: announce.sh \"Text to speak\" [device]" >&2
  exit 2
fi

if [[ -z "$TOKEN" ]]; then
  echo "Missing VOICEMONKEY_TOKEN env var" >&2
  exit 2
fi

curl -G "https://api-v2.voicemonkey.io/announcement" \
  --data-urlencode "token=$TOKEN" \
  --data-urlencode "device=$DEVICE" \
  --data-urlencode "text=$TEXT" \
  --data-urlencode "voice=Ricardo" \
  --data-urlencode "language=pt-BR" \
  --silent

echo ""

