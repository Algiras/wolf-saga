"""Azure AI Speech neural TTS (REST). lt-LT-OnaNeural / lt-LT-LeonasNeural are standard voices with
no styles or roles (Microsoft language-support table); only SSML <prosody> and <break> apply.
For en-US voices an <mstts:express-as> style is added (Azure ignores styles a voice lacks).

Env: AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (both required).
"""

from __future__ import annotations

import os
import re
from typing import Tuple
from xml.sax.saxutils import escape

import numpy as np

from audio_utils import pcm16_to_float
from . import _emotion
from ._http import post
from .base import Engine

_STYLE = {"whisper": "whispering", "shout": "shouting", "rage": "angry", "grief": "sad", "anguish": "sad",
          "fear": "terrified", "tender": "gentle", "cold": "unfriendly"}
_PHONEME = re.compile(r"(<phoneme\b[^>]*>.*?</phoneme>)", re.S)


def _escape_keep_phoneme(text: str) -> str:
    parts = _PHONEME.split(text)
    return "".join(p if i % 2 else escape(p) for i, p in enumerate(parts))


class Azure(Engine):
    id = "azure"
    family = "azure"
    label = "Azure Neural (lt-LT Ona/Leonas; SSML prosody)"
    kind = "api"
    paid = True
    langs = ("lt", "en")
    env = ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")
    cost_per_1k_chars_usd = 0.016         # list price assumption; the free F0 tier is 0.5M chars/month (vendor page)
    supports_tags = True

    def prepare_text(self, utt, lang, tts_text):
        return tts_text        # SSML is assembled in synth() so the voice name is known

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        rate, pitch, vol = _emotion.AZURE_PROSODY.get(utt["emotion"], _emotion.AZURE_PROSODY["neutral"])
        body = _escape_keep_phoneme(text)
        inner = '<prosody rate="%s" pitch="%s" volume="%s">%s</prosody>' % (rate, pitch, vol, body)
        style = _STYLE.get(utt["emotion"])
        if style and voice.startswith("en-US-"):
            inner = '<mstts:express-as style="%s">%s</mstts:express-as>' % (style, inner)
        locale = "-".join(voice.split("-")[:2])
        ssml = ("<speak version='1.0' xml:lang='%s' xmlns='http://www.w3.org/2001/10/synthesis' "
                "xmlns:mstts='https://www.w3.org/2001/mstts'><voice name='%s'>%s</voice></speak>" % (locale, voice, inner))
        region = os.environ["AZURE_SPEECH_REGION"]
        r = post("https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region,
                 headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                          "Content-Type": "application/ssml+xml",
                          "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
                          "User-Agent": "wolf-saga-tts-bench"},
                 data=ssml.encode("utf8"))
        return pcm16_to_float(r.content), 24000


ENGINES = [Azure]
