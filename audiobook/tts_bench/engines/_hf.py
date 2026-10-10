"""Offline Hugging Face cache probe (never downloads)."""

from __future__ import annotations

import os
from pathlib import Path


def hf_cached(repo: str) -> bool:
    home = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    snaps = home / "hub" / ("models--" + repo.replace("/", "--")) / "snapshots"
    if not snaps.exists():
        return False
    return any(any(s.glob("*.safetensors")) or any(s.glob("*.pt")) or any(s.glob("*.pth")) for s in snaps.iterdir())


def role_ref(engine_id: str, role: str):
    """(path, transcript) for a cloning reference from env: <ENGINE>_REF_<ROLE>[_TEXT]."""
    base = "%s_REF_%s" % (engine_id.upper(), role.upper())
    p = os.environ.get(base)
    return (p, os.environ.get(base + "_TEXT", "")) if p and Path(p).exists() else (None, "")
