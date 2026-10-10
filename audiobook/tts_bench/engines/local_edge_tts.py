"""edge-tts: free client for Microsoft's Edge "read aloud" service (the same neural voices as Azure,
incl. lt-LT-OnaNeural / lt-LT-LeonasNeural). NOT a licensed API: unofficial, no SLA, and Microsoft's
terms do not grant production/commercial use, so this is a bench baseline and a free proxy for
"what Azure lt-LT sounds like", not a publishing engine. It needs network access, so the bench
requires --allow-online. No key. Only rate/pitch/volume are available (no SSML styles).
"""

from __future__ import annotations

import asyncio
import time
from typing import Tuple

import numpy as np

from audio_utils import decode_bytes
from . import _emotion
from .base import Engine


class EdgeTTS(Engine):
    id = "edge"
    family = "edge"
    label = "edge-tts (free Edge read-aloud; = Azure voices, unofficial)"
    kind = "online-free"
    paid = False
    langs = ("lt", "en")

    def available(self):
        try:
            import edge_tts  # noqa: F401
        except Exception as e:
            return False, "edge-tts not installed (%s)" % e
        return True, "ok (network, unofficial)"

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        import edge_tts
        rate, pitch, vol = _emotion.EDGE_PROSODY.get(utt["emotion"], _emotion.EDGE_PROSODY["neutral"])

        async def run() -> bytes:
            comm = edge_tts.Communicate(text, voice, rate=rate, volume=vol, pitch=pitch)
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        last = None
        for attempt in range(6):          # the free endpoint throttles with sporadic HTTP 403: back off
            try:
                data = asyncio.run(run())
                if data:
                    time.sleep(0.4)       # polite pacing
                    return decode_bytes(data)
                last = RuntimeError("empty audio")
            except Exception as e:
                last = e
            time.sleep(2.0 * (attempt + 1))
        raise RuntimeError("edge-tts failed: %s" % str(last)[:120])


ENGINES = [EdgeTTS]
