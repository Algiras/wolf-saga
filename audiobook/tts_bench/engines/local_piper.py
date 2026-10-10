"""Piper with the community Lithuanian voice lt_LT-reginute1-medium (LIEPA corpus, CC-BY-4.0 data, one
studio actress, ~3 h; in rhasspy/piper-voices). Fast, offline, flat: no emotion control, one voice.

IMPORTANT (voice MODEL_CARD): the voice needs the Lithuanian phonemizer + stress dictionary
(lt_kirciai.tsv) that was merged into piper1-gpl as PhonemeType.LITHUANIAN on 2026-09-15, AFTER the
v1.8.0 release (2026-09-04). So `pip install piper-tts` (<= 1.8.0) cannot run it: install piper from
git master or a later release. The old piper 1.4.1 on this Mac lacks PhonemeType.LITHUANIAN, so this
plugin reports "unavailable" here. Never downloads: set PIPER_MODEL_LT=/path/to/lt_LT-reginute1-medium.onnx
(the .onnx.json must sit beside it; put lt_kirciai.tsv next to the model). Emotion: length_scale only.
The card recommends normalize_audio=False and warns that single short words come out hurried.
"""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path
from typing import Tuple

import numpy as np

from audio_utils import read_wav
from .base import Engine

_SCALE = {"grief": 1.18, "solemn": 1.15, "exhausted": 1.2, "whisper": 1.1, "rage": 0.95, "shout": 0.9, "fear": 0.95}
_voice_cache: dict = {}


def _model_path() -> Path:
    return Path(os.environ.get("PIPER_MODEL_LT") or Path.home() / ".local" / "share" / "piper" / "lt_LT-reginute1-medium.onnx")


class Piper(Engine):
    id = "piper"
    family = "piper"
    label = "Piper lt_LT-reginute1-medium (local, flat)"
    kind = "local"
    langs = ("lt",)

    def available(self):
        p = _model_path()
        if not p.exists():
            return False, "voice model not found at %s (see SETUP.md)" % p
        try:
            from piper.config import PhonemeType
        except Exception as e:
            return False, "piper-tts not importable (%s)" % e
        if not hasattr(PhonemeType, "LITHUANIAN"):
            return False, "installed piper-tts has no PhonemeType.LITHUANIAN (needs piper1-gpl master after 2026-09-15; see SETUP.md)"
        return True, "ok"

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        from piper import PiperVoice
        if "v" not in _voice_cache:
            _voice_cache["v"] = PiperVoice.load(str(_model_path()))
        v = _voice_cache["v"]
        kwargs = {}
        try:
            from piper import SynthesisConfig
            kwargs["syn_config"] = SynthesisConfig(length_scale=_SCALE.get(utt["emotion"], 1.0), normalize_audio=False)
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.wav")
            with wave.open(out, "wb") as wf:
                v.synthesize_wav(text, wf, **kwargs)
            return read_wav(Path(out))


ENGINES = [Piper]
