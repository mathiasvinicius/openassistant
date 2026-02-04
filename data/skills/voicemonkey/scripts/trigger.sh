#!/usr/bin/env bash
set -euo pipefail

MONKEY="${1:-}"
TOKEN="${VOICEMONKEY_TOKEN:-}"

if [[ -z "$MONKEY" ]]; then
  echo "Usage: trigger.sh \"monkey_name\"" >&2
  exit 2
fi

if [[ -z "$TOKEN" ]]; then
  echo "Missing VOICEMONKEY_TOKEN env var" >&2
  exit 2
fi

curl -G "https://api-v2.voicemonkey.io/trigger" \
  --data-urlencode "token=$TOKEN" \
  --data-urlencode "monkey=$MONKEY" \
  --silent

echo ""

