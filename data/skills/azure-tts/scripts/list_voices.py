#!/usr/bin/env python3
"""
List Azure Speech voices for pt-BR.

Env:
  AZURE_SPEECH_KEY (required)
  AZURE_SPEECH_REGION (default: brazilsouth)
"""

import os
import sys

import azure.cognitiveservices.speech as speechsdk

key = os.environ.get("AZURE_SPEECH_KEY")
region = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
if not key:
    raise SystemExit("AZURE_SPEECH_KEY not set")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
synth = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
result = synth.get_voices_async("pt-BR").get()

if result.reason != speechsdk.ResultReason.VoicesListRetrieved:
    print(f"Failed: {result.reason}", file=sys.stderr)
    raise SystemExit(1)

voices = sorted(result.voices, key=lambda v: v.short_name)
for v in voices:
    print(f"{v.short_name}\t{v.gender}\t{v.locale}\t{v.local_name}")
print(f"TOTAL\t{len(voices)}")

