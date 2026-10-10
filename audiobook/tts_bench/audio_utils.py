"""Small audio helpers for the bench: decode anything via ffmpeg, resample, join, write WAV.

Only numpy, scipy and soundfile are needed (all common). ffmpeg must be on PATH for
mp3/aiff decoding and for loudness matching.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np

TARGET_SR = 24000


def decode_bytes(data: bytes, fmt_hint: str = "") -> Tuple[np.ndarray, int]:
    """Decode an audio container (mp3, wav, aiff, ogg ...) to mono float32 via ffmpeg."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-f", "f32le", "-ac", "1", "-ar", str(TARGET_SR), "pipe:1"]
    res = subprocess.run(cmd, input=data, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: " + res.stderr.decode("utf8", "replace")[:300])
    audio = np.frombuffer(res.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise RuntimeError("decoded audio is empty")
    return audio, TARGET_SR


def pcm16_to_float(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


def resample(audio: np.ndarray, sr: int, target: int = TARGET_SR) -> np.ndarray:
    if sr == target:
        return audio.astype(np.float32, copy=False)
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(sr, target)
    return resample_poly(audio, target // g, sr // g).astype(np.float32)


def to_mono(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 2:
        # (channels, samples) or (samples, channels): collapse the short axis
        axis = 0 if audio.shape[0] < audio.shape[1] else 1
        audio = audio.mean(axis=axis)
    return audio.reshape(-1)


def silence(ms: int, sr: int = TARGET_SR) -> np.ndarray:
    return np.zeros(int(sr * ms / 1000.0), dtype=np.float32)


def trim_edges(audio: np.ndarray, sr: int = TARGET_SR, thresh: float = 0.003, keep_ms: int = 40) -> np.ndarray:
    """Trim leading/trailing near-silence (engines differ a lot in padding)."""
    idx = np.flatnonzero(np.abs(audio) > thresh)
    if idx.size == 0:
        return audio
    keep = int(sr * keep_ms / 1000.0)
    return audio[max(0, idx[0] - keep): min(audio.size, idx[-1] + keep)]


def join(parts: Iterable[Tuple[np.ndarray, int]], sr: int = TARGET_SR) -> np.ndarray:
    """parts = (audio, pause_after_ms) pairs, all at `sr`."""
    out: List[np.ndarray] = []
    for audio, pause_ms in parts:
        out.append(audio)
        if pause_ms:
            out.append(silence(pause_ms, sr))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def write_wav(path: Path, audio: np.ndarray, sr: int = TARGET_SR) -> None:
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(str(path), audio, sr, subtype="PCM_16")


def read_wav(path: Path) -> Tuple[np.ndarray, int]:
    import soundfile as sf
    audio, sr = sf.read(str(path), dtype="float32")
    return to_mono(audio), sr


def duration_s(path: Path) -> float:
    import soundfile as sf
    info = sf.info(str(path))
    return info.frames / float(info.samplerate)
