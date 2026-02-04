#!/usr/bin/env bash
set -euo pipefail

# Import private runtime state from ./private-overlay/ into the local repo folder.
# Use this on a new machine AFTER cloning the repo.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IN_DIR="${ROOT_DIR}/private-overlay"
if [[ ! -d "$IN_DIR" ]]; then
  echo "missing: $IN_DIR"
  echo "create it by copying your private overlay, or run: scripts/export_private_overlay.sh"
  exit 1
fi

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "copied: ${src#$ROOT_DIR/} -> $dst"
  fi
}

copy_if_exists "${IN_DIR}/.env" ".env"
copy_if_exists "${IN_DIR}/data/openclaw.json" "data/openclaw.json"
copy_if_exists "${IN_DIR}/data/agents/main/agent/auth-profiles.json" "data/agents/main/agent/auth-profiles.json"
copy_if_exists "${IN_DIR}/data/credentials" "data/credentials"
copy_if_exists "${IN_DIR}/data/workspace/MEMORY.md" "data/workspace/MEMORY.md"

echo ""
echo "Done."

