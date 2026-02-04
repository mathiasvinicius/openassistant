#!/usr/bin/env bash
set -euo pipefail

# Export private runtime state (secrets, tokens, memory) into ./private-overlay/
# so you can back it up or move it to another machine without committing it to git.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${ROOT_DIR}/private-overlay"
mkdir -p "$OUT_DIR"

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "copied: $src -> ${dst#$ROOT_DIR/}"
  fi
}

# Secrets/env
copy_if_exists ".env" "${OUT_DIR}/.env"

# OpenClaw runtime config
copy_if_exists "data/openclaw.json" "${OUT_DIR}/data/openclaw.json"

# Provider auth profiles (tokens/OAuth)
copy_if_exists "data/agents/main/agent/auth-profiles.json" "${OUT_DIR}/data/agents/main/agent/auth-profiles.json"

# Channel credentials / OAuth tokens
copy_if_exists "data/credentials" "${OUT_DIR}/data/credentials"

# Personal memory (if you keep it there)
copy_if_exists "data/workspace/MEMORY.md" "${OUT_DIR}/data/workspace/MEMORY.md"

echo ""
echo "Done. NOTE: ./private-overlay is gitignored on purpose."

