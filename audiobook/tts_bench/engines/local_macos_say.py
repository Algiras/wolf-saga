"""macOS `say` (built in, offline). English only; a crude baseline, useful to check the harness
and as a floor for the listening test. Rate is varied with emotion; whisper is approximated
with the [[volm]] embedded command.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from typing import Tuple

import numpy as np

from audio_utils import decode_bytes
from .base import Engine

_WPM = {"neutral": 170, "tender": 155, "solemn": 140, "awe": 150, "fear": 185, "anguish": 160, "grief": 135,
        "rage": 180, "cold": 155, "contempt": 155, "sly": 165, "exhausted": 135, "whisper": 150, "shout": 195}


class MacSay(Engine):
    id = "say"
    family = "say"
    label = "macOS say (baseline)"
    kind = "local"
    langs = ("en",)

    def available(self):
        if platform.system() != "Darwin" or not shutil.which("say"):
            return False, "macOS `say` not found"
        return True, "ok"

    def synth(self, text, voice, utt, lang) -> Tuple[np.ndarray, int]:
        text = text.replace("[[", "(").replace("]]", ")")
        if utt["emotion"] == "whisper":
            text = "[[volm 0.35]] " + text
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.aiff")
            subprocess.run(["say", "-v", voice, "-r", str(_WPM.get(utt["emotion"], 170)), "-o", out, "--", text],
                           check=True, capture_output=True)
            with open(out, "rb") as fh:
                return decode_bytes(fh.read())


ENGINES = [MacSay]
