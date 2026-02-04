#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${BASE_DIR}/scripts/bootstrap.sh"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

"${BASE_DIR}/.venv/bin/python" "${BASE_DIR}/scripts/list_voices.py" >"$TMP"

SAMPLE_TEXT="${AZURE_TTS_SAMPLE_TEXT:-Olá Vinicius! como está hoje ? Espero que você esteja tendo um ótimo dia.}"
CFG="${BASE_DIR}/config.json"

echo "Voices (pt-BR):"
nl -ba "$TMP" | sed -n '1,220p'
echo
echo "Sample text:"
echo "  ${SAMPLE_TEXT}"
echo

while true; do
  read -r -p "Select a voice number (or 'q' to quit): " N
  if [[ "${N}" == "q" || "${N}" == "Q" ]]; then
    echo "Bye."
    exit 0
  fi

  VOICE="$(sed -n "${N}p" "$TMP" | awk -F'\t' '{print $1}')"
  if [[ -z "${VOICE}" ]]; then
    echo "Invalid selection." >&2
    continue
  fi

  echo
  echo "Generating sample with voice: ${VOICE}"
  # Generate a sample without persisting it as default yet.
  # azure_chunked_tts.py prints: MEDIA: media/tts/<file>.ogg
  MEDIA_LINE="$(
    env AZURE_SPEECH_VOICE="${VOICE}" \
      "${BASE_DIR}/.venv/bin/python" -u "${BASE_DIR}/scripts/azure_chunked_tts.py" "${SAMPLE_TEXT}" \
      | sed -n 's/^MEDIA: //p'
  )"
  if [[ -n "${MEDIA_LINE}" ]]; then
    echo "Saved: ${MEDIA_LINE}"
  else
    echo "ERROR: did not get MEDIA output" >&2
  fi

  echo
  read -r -p "Set this voice as default? (y/N): " ANS
  if [[ "${ANS}" != "y" && "${ANS}" != "Y" ]]; then
    echo
    continue
  fi

  python3 - <<PY
import json
from pathlib import Path
cfg_path = Path(${CFG@Q})
cfg = {}
if cfg_path.exists():
  try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
  except Exception:
    cfg = {}
cfg["voice"] = ${VOICE@Q}
cfg_path.write_text(json.dumps(cfg, ensure_ascii=True, indent=2) + "\\n", encoding="utf-8")
print("OK")
print("config_path=" + str(cfg_path))
print("voice=" + cfg["voice"])
PY
  exit 0
done
