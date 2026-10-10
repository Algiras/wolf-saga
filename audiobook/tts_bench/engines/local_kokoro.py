"""Kokoro-82M (Apache-2.0). English (and es/fr/hi/it/ja/pt/zh); NO Lithuanian, no emotion control,
no cloning: a proof-listening baseline only (the author's speak-skill voice is af_heart).

Runtime probing order, nothing is ever downloaded:
  1. kokoro-onnx  with KOKORO_ONNX_MODEL / KOKORO_ONNX_VOICES (or ~/.cache/kokoro-onnx/*)
  2. mlx-audio    with a Kokoro repo already in the Hugging Face cache (KOKORO_MLX_REPO, default
                  mlx-community/Kokoro-82M-bf16; the 4bit repo found on the author's Mac fails to
                  load with mlx-audio 0.4.1: shape mismatch in predictor.F0 conv weights)
  3. kokoro (PyPI pipeline) with hexgrad/Kokoro-82M already cached
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .base import Engine

_state: dict = {}


def _hf_cached(repo: str) -> bool:
    root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub" / ("models--" + repo.replace("/", "--"))
    snaps = root / "snapshots"
    if not snaps.exists():
        return False
    return any((s / "config.json").exists() or any(s.glob("*.safetensors")) for s in snaps.iterdir())


def _onnx_paths() -> Optional[Tuple[str, str]]:
    m = os.environ.get("KOKORO_ONNX_MODEL") or str(Path.home() / ".cache" / "kokoro-onnx" / "kokoro-v1.0.onnx")
    v = os.environ.get("KOKORO_ONNX_VOICES") or str(Path.home() / ".cache" / "kokoro-onnx" / "voices-v1.0.bin")
    return (m, v) if Path(m).exists() and Path(v).exists() else None


def _load():
    if "model" in _state:
        return _state["model"]
    err = []
    if _onnx_paths():
        try:
            import kokoro_onnx
            m, v = _onnx_paths()
            _state["model"] = ("onnx", kokoro_onnx.Kokoro(m, v))
            return _state["model"]
        except Exception as e:
            err.append("onnx: %s" % e)
    repo = os.environ.get("KOKORO_MLX_REPO", "mlx-community/Kokoro-82M-bf16")
    if _hf_cached(repo):
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from mlx_audio.tts.utils import load_model
            _state["model"] = ("mlx", load_model(repo))
            return _state["model"]
        except Exception as e:
            err.append("mlx(%s): %s" % (repo, str(e)[:120]))
    if _hf_cached("hexgrad/Kokoro-82M"):
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from kokoro import KPipeline
            _state["model"] = ("pipeline", KPipeline(lang_code="a"))
            return _state["model"]
        except Exception as e:
            err.append("kokoro: %s" % e)
    _state["model"] = None
    _state["error"] = "; ".join(err) or "no Kokoro weights found locally (see SETUP.md)"
    return None


class Kokoro(Engine):
    id = "kokoro"
    family = "kokoro"
    label = "Kokoro-82M (local baseline, no lt)"
    kind = "local"
    langs = ("en",)

    def available(self):
        return (True, "ok") if _load() else (False, _state.get("error", "unavailable"))

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        kind, model = _load()
        speed = 0.92 if utt["emotion"] in ("grief", "solemn", "exhausted") else 1.0
        british = voice.startswith("b")
        if kind == "onnx":
            samples, sr = model.create(text, voice=voice, speed=speed, lang="en-gb" if british else "en-us")
            return np.asarray(samples, dtype=np.float32), int(sr)
        chunks = []
        if kind == "mlx":
            for r in model.generate(text, voice=voice, speed=speed, lang_code="b" if british else "a"):
                chunks.append(np.asarray(r.audio, dtype=np.float32).reshape(-1))
        else:
            for _, _, audio in model(text, voice=voice, speed=speed):
                chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
        if not chunks:
            raise RuntimeError("kokoro produced no audio")
        return np.concatenate(chunks), 24000


ENGINES = [Kokoro]
