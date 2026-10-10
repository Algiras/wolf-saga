"""Google Gemini TTS via the Gemini API (google-genai SDK). gemini-3.8-flash-tts lists Lithuanian
(Gemini 3.8 Flash-Lite TTS does not). Env: GEMINI_API_KEY; GEMINI_TTS_MODEL overrides the model.

Emotion: natural-language direction as a prefix ("Say <style>: <text>"). The vendor docs also
describe inline English tags such as <sigh> / <long pause> and a per-turn style field; the
prefix form is the long-documented one and works on every Gemini TTS model, so it is used here.
Output: PCM 24 kHz mono 16-bit in the response's inline_data.
"""

from __future__ import annotations

import os
from typing import Tuple

import numpy as np

from audio_utils import pcm16_to_float
from . import _emotion
from .base import Engine


class Gemini(Engine):
    id = "gemini"
    family = "gemini"
    label = "Gemini 3.8 Flash TTS (style prompts)"
    kind = "api"
    paid = True
    langs = ("lt", "en")
    env = ("GEMINI_API_KEY",)
    cost_per_1k_chars_usd = 0.02          # ~70 s of speech per 1k chars at $0.00225 per 10 s (2026 price)
    supports_tags = True

    def _model(self) -> str:
        return os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")

    def available(self):
        ok, why = super().available()
        if not ok:
            return ok, why
        try:
            import google.genai  # noqa: F401
        except Exception as e:
            return False, "google-genai not installed (%s)" % e
        return True, "ok"

    def cache_key(self):
        return "gemini:" + self._model()

    def prepare_text(self, utt, lang, tts_text):
        style = _emotion.phrase(utt["emotion"], utt["intensity"])
        return "Say %s: %s" % (style, tts_text)

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=self._model(),
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))),
        )
        part = resp.candidates[0].content.parts[0]
        data = part.inline_data.data
        return pcm16_to_float(data), 24000


ENGINES = [Gemini]
