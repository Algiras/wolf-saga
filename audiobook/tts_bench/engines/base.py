"""Engine plugin base class for the TTS bench.

A plugin is a module in engines/ that defines one or more `Engine` subclasses and lists
them in a module-level `ENGINES = [...]`. The bench never imports heavy libraries at module
import time: do that inside `available()` / `load()` / `synth()` so that a missing package
or model makes the engine SKIP, never crash.

Rules for plugins
-----------------
* API plugins read credentials ONLY from environment variables (declare them in `env`) and
  are `paid = True`; the bench refuses to call them without --allow-paid.
* Local plugins must not download anything: `available()` checks that the package AND the
  model files are already present and returns (False, "reason") otherwise.
* `synth()` returns (mono float32 numpy array, sample_rate) for ONE utterance and raises on
  any failure (a failed utterance fails the passage; the bench never writes partial audio).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent.parent


def load_voices() -> dict:
    return json.loads((HERE / "voices.json").read_text(encoding="utf8"))


class Engine:
    id: str = ""                    # short slug, also the samples/<id>/ directory
    family: str = ""                # key used by lexicon_tts.POLICY ("elevenlabs", "azure", ...)
    label: str = ""
    kind: str = "local"             # "api" | "local" | "online-free"
    paid: bool = False
    langs: Tuple[str, ...] = ("en",)
    env: Tuple[str, ...] = ()       # env vars that must all be set for an API engine
    cost_per_1k_chars_usd: float = 0.0    # rough list price, for the pre-flight estimate only
    supports_tags: bool = False     # renders emotion markup itself (tags / style prompts / prosody)
    notes: str = ""

    # ---- availability -------------------------------------------------------------
    def available(self) -> Tuple[bool, str]:
        missing = [e for e in self.env if not os.environ.get(e)]
        if missing:
            return False, "missing env: " + ", ".join(missing)
        return True, "ok"

    # ---- voices -------------------------------------------------------------------
    def role_for(self, utt: dict) -> str:
        cfg = load_voices()
        role = cfg["speaker_roles"].get(utt["speaker"])
        if role:
            return role
        if utt["kind"] == "narration":
            return "narrator"
        if utt["kind"] == "divine":
            return "divine"
        return "extra"

    def voice_for(self, utt: dict, lang: str) -> str:
        """Voice id for an utterance: env override <ENGINE>_VOICE_<ROLE> first, then voices.json."""
        role = self.role_for(utt)
        override = os.environ.get("%s_VOICE_%s" % (self.id.upper(), role.upper()))
        if override:
            return override
        cfg = load_voices()
        eng = cfg["engines"].get(self.id, {})
        table = eng.get(lang) or eng.get("*") or {}
        return table.get(role) or table.get("narrator") or ""

    def cache_key(self) -> str:
        """Anything that changes the audio besides text/voice (model id, settings)."""
        return self.id

    # ---- text preparation ------------------------------------------------------------
    def prepare_text(self, utt: dict, lang: str, tts_text: str) -> str:
        """`tts_text` already has the lexicon applied. Engines with tag support add tags here."""
        return tts_text

    # ---- synthesis ------------------------------------------------------------------
    def synth(self, text: str, voice: str, utt: dict, lang: str) -> Tuple[np.ndarray, int]:
        raise NotImplementedError


def env_or(name: str, default: str) -> str:
    return os.environ.get(name) or default
