"""OmniVoice (k2-fsa, 0.6B, diffusion-LM style, "600+ languages"; `lt` is in its language list).
Code Apache-2.0, but the PRE-TRAINED MODEL is CC-BY-NC (training-data constraint, model card), so it
is a research/non-monetised candidate. Voice cloning from a same-language reference is the stable
mode; voice design is trained on zh/en only. Inline tags: [laughter] [sigh] ...; whisper via instruct.

Requires: `pip install omnivoice`, weights k2-fsa/OmniVoice already in the HF cache. UNTESTED here
(not installed on this machine); the generate() call follows the model card.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from ._hf import hf_cached, role_ref
from .base import Engine

_state: dict = {}


class OmniVoice(Engine):
    id = "omnivoice"
    family = "omnivoice"
    label = "OmniVoice 0.6B (local, CC-BY-NC weights)"
    kind = "local"
    langs = ("lt", "en")

    def available(self):
        try:
            import omnivoice  # noqa: F401
        except Exception as e:
            return False, "omnivoice not installed (%s)" % e
        if not hf_cached("k2-fsa/OmniVoice"):
            return False, "k2-fsa/OmniVoice not in the HF cache (see SETUP.md)"
        return True, "ok"

    def _model(self):
        if "m" not in _state:
            import torch
            from omnivoice import OmniVoice as OV
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            _state["m"] = OV.from_pretrained("k2-fsa/OmniVoice", device_map=dev, dtype=torch.float32)
        return _state["m"]

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        m = self._model()
        role = self.role_for(utt)
        ref, ref_text = role_ref(self.id, role)
        kw = {"text": text}
        if ref:
            kw.update(ref_audio=ref, ref_text=ref_text)
        else:
            instruct = voice + (", whisper" if utt["emotion"] == "whisper" and "whisper" not in voice else "")
            kw["instruct"] = instruct
        if utt["emotion"] in ("grief", "solemn", "exhausted"):
            kw["speed"] = 0.92
        try:
            audio = m.generate(language=lang, **kw)
        except TypeError:
            audio = m.generate(**kw)
        a = audio[0] if isinstance(audio, (list, tuple)) else audio
        if hasattr(a, "detach"):
            a = a.detach().cpu().numpy()
        return np.asarray(a, dtype=np.float32).reshape(-1), 24000


ENGINES = [OmniVoice]
