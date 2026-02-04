#!/usr/bin/env python3
"""
Chunked Azure TTS -> OGG/Opus in OpenClaw workspace.

Env:
  AZURE_SPEECH_KEY (required)
  AZURE_SPEECH_REGION (default: brazilsouth)
  AZURE_SPEECH_VOICE (default: pt-BR-BrendaNeural)
  AZURE_SPEECH_RATE (default: 23%)
  MAX_CHARS_PER_CHUNK (default: 900)
  FFMPEG (default: ffmpeg)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_REGION = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
AZURE_VOICE = os.environ.get("AZURE_SPEECH_VOICE", "")
AZURE_RATE = os.environ.get("AZURE_SPEECH_RATE", "")
MAX_CHARS = int(os.environ.get("MAX_CHARS_PER_CHUNK", "900"))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CFG_PATH = SKILL_DIR / "config.json"


def load_config() -> dict:
    # Optional config file so users can set a default voice without env vars.
    path = Path(os.environ.get("AZURE_TTS_CONFIG", str(DEFAULT_CFG_PATH)))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to parse config JSON: {path} ({e})")


CFG = load_config()
if not AZURE_VOICE:
    AZURE_VOICE = str(CFG.get("voice") or "pt-BR-BrendaNeural")
if not AZURE_RATE:
    AZURE_RATE = str(CFG.get("rate") or "23%")


def split_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[\.!\?…])\s+|\s*\n+\s*", text)
    parts = [p.strip() for p in parts if p.strip()]

    chunks: list[str] = []
    cur = ""
    for p in parts:
        if not cur:
            cur = p
            continue
        if len(cur) + 1 + len(p) <= MAX_CHARS:
            cur = f"{cur} {p}"
        else:
            chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)

    fixed: list[str] = []
    for c in chunks:
        if len(c) <= MAX_CHARS:
            fixed.append(c)
        else:
            for i in range(0, len(c), MAX_CHARS):
                fixed.append(c[i : i + MAX_CHARS])
    return fixed


def azure_tts_to_wav(text: str, out_wav: str) -> None:
    if not AZURE_KEY:
        raise SystemExit("AZURE_SPEECH_KEY not set")

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    speech_config.speech_synthesis_language = "pt-BR"
    speech_config.speech_synthesis_voice_name = AZURE_VOICE

    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_wav)
    synth = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='pt-BR'>"
        f"<voice name='{AZURE_VOICE}'>"
        f"<prosody rate='{AZURE_RATE}'>{text}</prosody>"
        "</voice></speak>"
    )

    result = synth.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return
    if result.reason == speechsdk.ResultReason.Canceled:
        c = result.cancellation_details
        raise RuntimeError(f"Azure canceled: {c.reason} | {c.error_details}")
    raise RuntimeError(f"Azure failed: {result.reason}")


def wav_to_ogg(in_wav: str, out_ogg: str) -> None:
    subprocess.check_call(
        [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            in_wav,
            "-c:a",
            "libopus",
            "-b:a",
            "40k",
            "-vbr",
            "on",
            "-application",
            "voip",
            out_ogg,
        ]
    )


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: azure_chunked_tts.py "text..."', file=sys.stderr)
        return 2

    text = " ".join(sys.argv[1:]).strip()
    if not text:
        raise SystemExit("Empty text")

    chunks = split_text(text)

    work = Path(f"/tmp/azure_chunks_{uuid.uuid4().hex[:8]}")
    work.mkdir(parents=True, exist_ok=True)

    wavs: list[Path] = []
    for i, c in enumerate(chunks, 1):
        wav = work / f"chunk_{i:04d}.wav"
        azure_tts_to_wav(c, str(wav))
        wavs.append(wav)

    concat_list = work / "concat.txt"
    concat_list.write_text("\n".join([f"file '{p}'" for p in wavs]) + "\n", encoding="utf-8")

    final_wav = work / "final.wav"
    subprocess.check_call(
        [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(final_wav),
        ]
    )

    out_dir = Path(os.environ.get("OPENCLAW_TTS_DIR", "/home/node/.openclaw/workspace/media/tts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"tts_{uuid.uuid4().hex[:18]}.ogg"
    out_ogg = out_dir / out_name
    wav_to_ogg(str(final_wav), str(out_ogg))

    rel = f"media/tts/{out_name}"
    print(f"MEDIA: {rel}")
    # Extra details for debugging/metrics (safe to ignore by callers).
    print(
        json.dumps(
            {"provider": "azure", "chunks": len(chunks), "voice": AZURE_VOICE, "rate": AZURE_RATE, "path": str(out_ogg)},
            ensure_ascii=True,
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
