#!/usr/bin/env bash
set -euo pipefail

# Generate a self-signed cert for the nginx front-proxy (LAN "secure context").
# Output:
#   data/ui/certs/openclaw.crt
#   data/ui/certs/openclaw.key

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CERT_DIR="data/ui/certs"
mkdir -p "$CERT_DIR"

CRT="${CERT_DIR}/openclaw.crt"
KEY="${CERT_DIR}/openclaw.key"

if [[ -f "$CRT" && -f "$KEY" ]]; then
  echo "already exists: $CRT, $KEY"
  exit 0
fi

CN="${1:-openassistant.local}"

openssl req -x509 -newkey rsa:2048 \
  -keyout "$KEY" -out "$CRT" \
  -days 3650 -nodes \
  -subj "/CN=${CN}" >/dev/null 2>&1

chmod 600 "$KEY"
chmod 644 "$CRT"

echo "generated: $CRT"
echo "generated: $KEY"

