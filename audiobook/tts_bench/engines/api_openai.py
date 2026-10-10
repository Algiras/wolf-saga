"""OpenAI gpt-4o-mini-tts (REST). Whisper-language coverage includes Lithuanian, but TTS voices are
tuned for English: Lithuanian support is NOT confirmed by vendor docs (test it).
Emotion: free-text `instructions`. Env: OPENAI_API_KEY; OPENAI_TTS_MODEL overrides the model.
"""

from __future__ import annotations

import os
from typing import Tuple

import numpy as np

from audio_utils import decode_bytes
from . import _emotion
from ._http import post
from .base import Engine


class OpenAITTS(Engine):
    id = "openai"
    family = "openai"
    label = "OpenAI gpt-4o-mini-tts (instructions)"
    kind = "api"
    paid = True
    langs = ("lt", "en")
    env = ("OPENAI_API_KEY",)
    cost_per_1k_chars_usd = 0.017         # ~US$0.015 per minute of audio (third-party estimate)
    supports_tags = True

    def cache_key(self):
        return "openai:" + os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        instr = ("Narrating a dark Baltic fantasy audiobook in %s. Deliver the line %s. Do not add or skip words; "
                 "pronounce Lithuanian names as Lithuanian."
                 % ("Lithuanian" if lang == "lt" else "English", _emotion.phrase(utt["emotion"], utt["intensity"])))
        r = post("https://api.openai.com/v1/audio/speech",
                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                 json={"model": os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"), "voice": voice,
                       "input": text, "instructions": instr, "response_format": "wav"})
        return decode_bytes(r.content)


ENGINES = [OpenAITTS]
