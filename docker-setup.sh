#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

mkdir -p data/workspace

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

# In some restricted/containerized environments, $HOME/.docker may not be writable.
# Point Docker config (including buildx state) at a project-local folder.
export DOCKER_CONFIG="${DOCKER_CONFIG:-$ROOT_DIR/.docker-config}"
mkdir -p "$DOCKER_CONFIG"

echo "[1/4] Building image..."
docker compose build

echo "[2/4] Running onboarding wizard (interactive)..."
docker compose run --rm openclaw-cli onboard

echo "[3/4] Trying to capture gateway token into .env..."
set +e
DASHBOARD_OUT="$(docker compose run --rm openclaw-cli dashboard --no-open 2>/dev/null)"
set -e

TOKEN=""
if [[ -n "${DASHBOARD_OUT:-}" ]]; then
  # Extract `token=...` from the printed dashboard URL (best-effort).
  TOKEN="$(printf "%s\n" "$DASHBOARD_OUT" | sed -n 's/.*[?&]token=\\([^& ]\\+\\).*/\\1/p' | head -n 1)"
fi

if [[ -n "${TOKEN:-}" ]]; then
  cat > .env <<EOF
OPENCLAW_GATEWAY_TOKEN=$TOKEN
EOF
  echo "Wrote OPENCLAW_GATEWAY_TOKEN to .env"
else
  if [[ ! -f .env ]]; then
    cp .env.example .env
  fi
  echo "Could not auto-detect token. Run:"
  echo "  docker compose run --rm openclaw-cli dashboard --no-open"
  echo "and paste the token into .env (OPENCLAW_GATEWAY_TOKEN=...)."
fi

echo "[4/4] Starting gateway..."
docker compose up -d openclaw-gateway

echo "Done. Open: http://127.0.0.1:18789/"
echo "If it says 'unauthorized', run:"
echo "  docker compose run --rm openclaw-cli dashboard --no-open"
