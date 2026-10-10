"""Google Cloud Text-to-Speech, Chirp 3: HD voices (REST, API key). lt-LT is on the Chirp 3 HD
language list. Vendor docs: custom pronunciation and pause control are NOT available for lt-LT;
pace control is. So emotion is expressed only through `speakingRate`.

Env: GOOGLE_TTS_API_KEY (a Cloud API key with the Text-to-Speech API enabled).
"""

from __future__ import annotations

import base64
import os
from typing import Tuple

import numpy as np

from audio_utils import decode_bytes
from ._http import post
from .base import Engine

_RATE = {"neutral": 1.0, "tender": 0.95, "solemn": 0.9, "awe": 0.93, "fear": 1.05, "anguish": 0.95, "grief": 0.88,
         "rage": 1.04, "cold": 0.95, "contempt": 0.95, "sly": 0.98, "exhausted": 0.88, "whisper": 0.92, "shout": 1.08}


class GoogleChirp(Engine):
    id = "google_chirp"
    family = "google"
    label = "Google Chirp 3: HD (pace only)"
    kind = "api"
    paid = True
    langs = ("lt", "en")
    env = ("GOOGLE_TTS_API_KEY",)
    cost_per_1k_chars_usd = 0.03          # list price assumption (US$30 / 1M chars); not verified this session

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        locale = "-".join(voice.split("-")[:2])
        r = post("https://texttospeech.googleapis.com/v1/text:synthesize",
                 params={"key": os.environ["GOOGLE_TTS_API_KEY"]},
                 json={"input": {"text": text},
                       "voice": {"languageCode": locale, "name": voice},
                       "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000,
                                       "speakingRate": _RATE.get(utt["emotion"], 1.0)}})
        return decode_bytes(base64.b64decode(r.json()["audioContent"]))


ENGINES = [GoogleChirp]
