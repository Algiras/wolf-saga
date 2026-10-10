"""Higgs TTS 3 (Boson AI, 4.65B BF16, 102 languages incl. Lithuanian in the "WER < 5" tier; 43 inline
control tokens for emotion / style / prosody / sfx; zero-shot cloning). The weights are served by
sglang-omni or vLLM-Omni (CUDA / Docker), NOT by anything that runs natively on Apple silicon, so
this plugin is an HTTP client for an OpenAI-compatible /v1/audio/speech endpoint you run on a rented
GPU box.  Env: HIGGS_TTS_URL=http://host:8000.  Cloning references live on the SERVER:
HIGGS_REF_<ROLE>=/server/path.wav and HIGGS_REF_<ROLE>_TEXT=transcript.

Licence: Boson Higgs TTS 3 Research and Non-Commercial License, with a Creator Use Grant that
allows monetised content (podcasts, videos) for free if credit is given in the description.
Hosting it as a service or embedding it in a product needs a commercial licence.
"""

from __future__ import annotations

import os
from typing import Tuple

import numpy as np

from audio_utils import decode_bytes
from . import _emotion
from ._http import post
from .base import Engine


class Higgs(Engine):
    id = "higgs"
    family = "higgs"
    label = "Higgs TTS 3 (self-hosted GPU server)"
    kind = "local"
    langs = ("lt", "en")
    env = ("HIGGS_TTS_URL",)
    supports_tags = True

    def prepare_text(self, utt, lang, tts_text):
        return _emotion.HIGGS.get(utt["emotion"], "") + tts_text

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        body = {"input": text, "temperature": 0.8, "top_k": 50, "max_new_tokens": 1024}
        base = "HIGGS_REF_" + self.role_for(utt).upper()
        if os.environ.get(base):
            body["references"] = [{"audio_path": os.environ[base], "text": os.environ.get(base + "_TEXT", "")}]
        r = post(os.environ["HIGGS_TTS_URL"].rstrip("/") + "/v1/audio/speech", json=body, timeout=300)
        return decode_bytes(r.content)


ENGINES = [Higgs]
