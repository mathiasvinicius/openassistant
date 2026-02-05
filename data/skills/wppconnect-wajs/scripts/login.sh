#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )/../../../.." && pwd)"
ENV_FILE="$ROOT_DIR/data/skills/wppconnect-wajs/config/wppconnect.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing config: $ENV_FILE"
  echo "Run: cp $ROOT_DIR/data/skills/wppconnect-wajs/config/wppconnect.env.example $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

SESSION="${1:-NERDWHATS_AMERICA}"
SECRETKEY="${WPP_SECRETKEY:-}"
BASE_URL="${WPP_BASE_URL:-http://127.0.0.1:${WPP_PORT:-21465}}"

start_url="$BASE_URL/api/$SESSION/start-session"
qr_url="$BASE_URL/api/$SESSION/qrcode-session"

extract_token() {
  python3 - <<'PY' "$1"
import json,sys
raw=sys.argv[1].strip()
if not raw:
    print("")
    raise SystemExit(0)
try:
    data=json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
for k in ("token", "full", "data", "bearer", "access_token"):
    if k in data:
        v=data[k]
        if isinstance(v, dict) and "token" in v:
            print(v["token"])
        elif isinstance(v, str):
            print(v)
        else:
            print("")
        raise SystemExit(0)
print("")
PY
}

extract_qr_to_file() {
  python3 - <<'PY' "$1" "$2"
import base64,sys
raw=sys.argv[1]
out=sys.argv[2]
# Accept data URI or raw base64
if raw.startswith('data:image'):
    raw=raw.split(',',1)[1]
try:
    data=base64.b64decode(raw)
except Exception:
    sys.exit(1)
with open(out,'wb') as f:
    f.write(data)
print(out)
PY
}

render_ascii_qr() {
  python3 - <<'PY' "$1"
from PIL import Image
import sys
path=sys.argv[1]
try:
    img=Image.open(path)
except Exception as e:
    print(f"Failed to open image: {e}")
    raise SystemExit(1)
img=img.convert('1')
# Resize to fit terminal width
w,h=img.size
new_w=max(1, w//2)
new_h=max(1, h//4)
img=img.resize((new_w,new_h))
px=img.load()
for y in range(img.size[1]):
    line=[]
    for x in range(img.size[0]):
        line.append('██' if px[x,y]==0 else '  ')
    print(''.join(line))
PY
}

if [[ -z "$SECRETKEY" ]]; then
  echo "WPP_SECRETKEY not set in config/wppconnect.env" >&2
  exit 1
fi

echo "Generating token..."
TOKEN_JSON=$(curl -s -X POST "$BASE_URL/api/$SESSION/$SECRETKEY/generate-token" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json')
TOKEN=$(extract_token "$TOKEN_JSON")

if [[ -z "$TOKEN" ]]; then
  echo "Token generation failed. Response:" >&2
  echo "$TOKEN_JSON" >&2
  exit 1
fi

AUTH_HEADER=("-H" "Authorization: Bearer $TOKEN")

echo "Starting session: $SESSION"
START_RESP=$(curl -s -X POST "$start_url" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  "${AUTH_HEADER[@]}" \
  -d '{"webhook":"","waitQrCode":false}')

# Try to extract QR from start-session response
QR_DATA=$(python3 - <<'PY' "$START_RESP"
import json,sys
raw=sys.argv[1]
try:
    data=json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
for k in ("qrcode","qr","qrCode","qrcode64","base64","qrcodeBase64"):
    if k in data and isinstance(data[k], str):
        print(data[k])
        raise SystemExit(0)
print("")
PY
)

OUT="/tmp/wppconnect-${SESSION}.png"

if [[ -n "$QR_DATA" ]]; then
  if extract_qr_to_file "$QR_DATA" "$OUT" >/dev/null 2>&1; then
    render_ascii_qr "$OUT"
    exit 0
  else
    echo "$QR_DATA"
    exit 0
  fi
fi

sleep 1

echo "Fetching QR code..."
QR_JSON=$(curl -s -X GET "$qr_url" "${AUTH_HEADER[@]}")

if [[ -z "$QR_JSON" ]]; then
  echo "No response from qrcode-session" >&2
  exit 1
fi

QR_DATA=$(python3 - <<'PY' "$QR_JSON"
import json,sys
raw=sys.argv[1]
try:
    data=json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
for k in ("qrcode","qr","qrCode","qrcode64","base64","qrcodeBase64","data"):
    if k in data:
        val=data[k]
        if isinstance(val, dict):
            for k2 in ("qrcode","qr","qrCode","qrcode64","base64","qrcodeBase64"):
                if k2 in val:
                    val=val[k2]
                    break
        if isinstance(val, str):
            print(val)
            raise SystemExit(0)
print("")
PY
)

if [[ -n "$QR_DATA" ]]; then
  if extract_qr_to_file "$QR_DATA" "$OUT" >/dev/null 2>&1; then
    render_ascii_qr "$OUT"
    exit 0
  fi
  echo "$QR_DATA"
  exit 0
fi

# As fallback, attempt binary response to file
HTTP_CODE=$(curl -s -o "$OUT" -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$qr_url")
if [[ "$HTTP_CODE" == "200" ]]; then
  render_ascii_qr "$OUT"
  exit 0
fi

echo "QR fetch failed. Response:" >&2
cat "$OUT" >&2
exit 1
