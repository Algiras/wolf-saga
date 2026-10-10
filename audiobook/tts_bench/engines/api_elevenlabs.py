"""ElevenLabs Eleven v4 / v3 (API). Lithuanian is on both language lists (vendor docs, Oct 2026).

Env: ELEVENLABS_API_KEY (required), ELEVENLABS_MODEL (default eleven_v4; eleven_v3 for comparison).
Emotion: free-text audio tags in square brackets before the line. IPA: inline /.../ (v4).
Output: raw PCM 24 kHz via output_format=pcm_24000.
"""

from __future__ import annotations

import os
from typing import Tuple

import numpy as np

from audio_utils import pcm16_to_float
from . import _emotion
from ._http import post
from .base import Engine


class ElevenLabs(Engine):
    id = "elevenlabs"
    family = "elevenlabs"
    label = "ElevenLabs Eleven v4 (audio tags)"
    kind = "api"
    paid = True
    langs = ("lt", "en")
    env = ("ELEVENLABS_API_KEY",)
    cost_per_1k_chars_usd = 0.08          # list price v3/v4 per vendor pricing page (promo 0.022 until 12 Oct 2026)
    supports_tags = True

    def _model(self) -> str:
        return os.environ.get("ELEVENLABS_MODEL", "eleven_v4")

    def cache_key(self) -> str:
        return "elevenlabs:" + self._model()

    def prepare_text(self, utt, lang, tts_text):
        tag = _emotion.eleven_tag(utt["emotion"], utt["intensity"])
        return (tag + " " + tts_text).strip()

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        r = post(
            "https://api.elevenlabs.io/v1/text-to-speech/%s" % voice,
            params={"output_format": "pcm_24000"},
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
            json={"text": text, "model_id": self._model()},
        )
        return pcm16_to_float(r.content), 24000


ENGINES = [ElevenLabs]
