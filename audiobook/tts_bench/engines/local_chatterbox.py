"""Chatterbox (Resemble AI, MIT; Perth watermark). English only: the 23-language multilingual card has
no Lithuanian. Current project engine (Chatterbox-Turbo, needs a reference clip). Emotion: exaggeration
and cfg_weight on the original model; Turbo ignores them (paralinguistic tags instead).

Never downloads: needs `chatterbox` importable and the model repo already in the HF cache
(ResembleAI/chatterbox-turbo or ResembleAI/chatterbox). Reference clips via CHATTERBOX_REF_<ROLE>=wav
(consented voices only). UNTESTED here (not installed).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from . import _emotion
from ._hf import hf_cached, role_ref
from .base import Engine

_state: dict = {}


class Chatterbox(Engine):
    id = "chatterbox"
    family = "chatterbox"
    label = "Chatterbox / Turbo (local, en only)"
    kind = "local"
    langs = ("en",)

    def available(self):
        try:
            import chatterbox  # noqa: F401
        except Exception as e:
            return False, "chatterbox not installed (%s)" % e
        if not (hf_cached("ResembleAI/chatterbox-turbo") or hf_cached("ResembleAI/chatterbox")):
            return False, "ResembleAI/chatterbox(-turbo) not in the HF cache (see SETUP.md)"
        return True, "ok"

    def _model(self):
        if "m" not in _state:
            import torch
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            if hf_cached("ResembleAI/chatterbox-turbo"):
                from chatterbox.tts_turbo import ChatterboxTurboTTS
                _state["m"] = ("turbo", ChatterboxTurboTTS.from_pretrained(device=dev))
            else:
                from chatterbox.tts import ChatterboxTTS
                _state["m"] = ("orig", ChatterboxTTS.from_pretrained(device=dev))
        return _state["m"]

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        kind, m = self._model()
        ref, _ = role_ref(self.id, self.role_for(utt))
        if kind == "turbo":
            if not ref:
                raise RuntimeError("Chatterbox-Turbo needs a reference clip: set CHATTERBOX_REF_%s" % self.role_for(utt).upper())
            wav = m.generate(text, audio_prompt_path=ref, norm_loudness=False)
        else:
            exa, cfg = _emotion.CHATTERBOX.get(utt["emotion"], (0.5, 0.5))
            wav = m.generate(text, audio_prompt_path=ref, exaggeration=exa, cfg_weight=cfg)
        a = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
        return a.astype(np.float32).reshape(-1), int(m.sr)


ENGINES = [Chatterbox]
