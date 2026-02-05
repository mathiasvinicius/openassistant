#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
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

if [[ -n "$SECRETKEY" ]]; then
  # Generate token if the server expects auth
  token_url="$BASE_URL/api/$SESSION/$SECRETKEY/generate-token"
  echo "Generating token..."
  TOKEN=$(curl -sf -X POST "$token_url" | python3 - <<'PY'
import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
# Try common shapes
for k in ("token","data","bearer","access_token"):
    if k in data:
        v=data[k]
        if isinstance(v, dict) and "token" in v:
            print(v["token"])
        elif isinstance(v,str):
            print(v)
        else:
            print("")
        sys.exit(0)
print("")
PY
)
  if [[ -n "$TOKEN" ]]; then
    AUTH_HEADER=("-H" "Authorization: Bearer $TOKEN")
  else
    AUTH_HEADER=()
  fi
else
  AUTH_HEADER=()
fi

echo "Starting session: $SESSION"
# Minimal payload; you can pass webhook/proxy via env in the future.
curl -sf -X POST "$start_url" \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  "${AUTH_HEADER[@]}" \
  -d '{"webhook":"","waitQrCode":false}' >/dev/null || true

sleep 1

echo "Fetching QR code..."
QR_JSON=$(curl -sf -X GET "$qr_url" "${AUTH_HEADER[@]}")

# Try to print ASCII QR if present, else show the JSON.
python3 - <<'PY'
import json,sys
raw=sys.stdin.read()
try:
    data=json.loads(raw)
except Exception:
    print(raw)
    raise SystemExit(0)

# Common fields that may contain ASCII QR or base64
for key in ("qr","qrcode","qrcode64","base64","qrcodeBase64","qrCode","qrCodeImage","data"):
    if key in data:
        val=data[key]
        if isinstance(val, dict):
            # dig for nested qr/base64
            for k2 in ("qr","qrcode","base64","qrcode64","qrCode"):
                if k2 in val:
                    val=val[k2]
                    break
        if isinstance(val,str) and val.strip():
            print(val)
            raise SystemExit(0)
print(raw)
PY
<<< "$QR_JSON"
