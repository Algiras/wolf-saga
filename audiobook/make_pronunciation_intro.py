#!/usr/bin/env python3
"""English pronunciation introduction for the audiobook / YouTube series.

For each key name the English narrator (Kokoro, af_heart) gives the English sound-alike and a
one-line gloss, then a native Lithuanian voice (edge-tts, lt-LT) says the real name.

    python3 audiobook/make_pronunciation_intro.py            # render
    python3 audiobook/make_pronunciation_intro.py --dry-run  # print the script only

Outputs (audiobook/intro/): en_pronunciation_intro.wav (-14 LUFS), .srt (real spellings on screen),
cards.json (name / respelling / gloss for video cards), script.md (readable script).
Needs: kokoro-onnx + model files in ~/.cache/kokoro-onnx, edge-tts (network), ffmpeg.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
LEXICON = ROOT / "world_rules" / "pronunciation_lexicon.json"
OUT = ROOT / "audiobook" / "intro"
SR = 24000
NARRATOR = "af_heart"
LT_VOICE = {"f": "lt-LT-OnaNeural", "m": "lt-LT-LeonasNeural"}

# (name as in the books, English gloss, voice gender for the native sample)
ENTRIES = [
    ("section", "First, the people."),
    ("Vytautas", "the hero of the saga, later Grand Duke of Lithuania", "m"),
    ("Kęstutis", "his father, the Old Boar of Trakai", "m"),
    ("Birutė", "his mother, a priestess of the amber shore", "f"),
    ("Ona", "Vytautas's wife", "f"),
    ("Jogaila", "his cousin, who will become King of Poland", "m"),
    ("Skirgaila", "Jogaila's brother, the hand that did the work", "m"),
    ("Algirdas", "Jogaila's father, who ruled the east", "m"),
    ("Gediminas", "founder of the dynasty, who dreamed the Iron Wolf", "m"),
    ("Švitrigaila", "the youngest and wildest of Jogaila's brothers", "m"),
    ("Jadvyga", "the young Queen of Poland", "f"),
    ("Eglė", "the last priestess of the sacred flame, later the voice of the swamp", "f"),
    ("Galminas", "a Samogitian priest who bleeds sap instead of blood", "m"),
    ("Henė", "the jester, who is not what he seems", "m"),
    ("Žiežirba", "the boy who keeps the last fire", "m"),
    ("section", "Now, the places."),
    ("Vilnius", "the capital", "m"),
    ("Trakai", "Kęstutis's castle among the lakes", "m"),
    ("Krėva", "the castle where it all begins", "m"),
    ("Palanga", "the amber shore of the Baltic", "f"),
    ("Šventaragis", "the sacred valley of the eternal flame in Vilnius", "m"),
    ("Žemaitija", "Samogitia, the stubborn pagan west", "f"),
    ("Žalgiris", "the field the Germans call Grunwald", "m"),
    ("section", "And a few words of the old world."),
    ("Perkūnas", "the thunder god", "m"),
    ("Žemyna", "the earth mother", "f"),
    ("Senovės Kalba", "the Ancient Tongue, the old craft of asking", "f"),
    ("vilkatas", "a wolf-warrior; many of them are vilkatai", "m"),
]
EXTRA = {  # names missing from the lexicon (verify with a native speaker)
    "Žiežirba": {"respelling_en": "zhyeh-ZHEER-bah", "stress": "žie-ŽIR-ba", "verify": True},
}
INTRO = ("Before we begin, a short guide to the names you will hear. The story is Lithuanian, and its "
         "names carry sounds English does not have. For each one, I will give you a simple way to say it, "
         "and then you will hear it spoken in Lithuanian.")
OUTRO = "That is all you need. Don't worry about getting them perfect. The story will carry you. Let us begin."


def lexicon():
    data = json.loads(LEXICON.read_text(encoding="utf-8"))
    lex = {e["text"]: e for e in data}
    lex.update({k: {"text": k, **v} for k, v in EXTRA.items()})
    return lex


def respell_names(text, lex):
    """Replace any lexicon name (and its case forms) inside narrator text with its English respelling."""
    import re
    forms = []
    for rec in lex.values():
        stem = rec["text"][:3].lower()
        for f in [rec["text"], *rec.get("variants", [])]:
            # case forms only (same stem); foreign equivalents like "Grunwald" stay as English words
            if len(f) > 2 and f[:1].isupper() and f[:3].lower() == stem:
                forms.append((f, rec["respelling_en"]))
    for f, r in sorted(forms, key=lambda x: -len(x[0])):
        text = re.sub(rf"(?<![\w-]){re.escape(f)}(?=('s)?\b)", r, text)
    return text


def build_script():
    lex = lexicon()
    items = [("narr", INTRO, None)]
    for e in ENTRIES:
        if e[0] == "section":
            items.append(("narr", e[1], None))
            continue
        name, gloss, g = e
        rec = lex.get(name)
        if not rec:
            raise SystemExit(f"no lexicon entry for {name}")
        resp = rec["respelling_en"]
        spoken_gloss = respell_names(gloss[0].upper() + gloss[1:], lex)
        items.append(("narr", f"{resp}. {spoken_gloss}.", {"name": name, "respelling": resp,
                      "stress": rec.get("stress"), "gloss": gloss, "verify": rec.get("verify", False)}))
        items.append(("lt", name, {"voice": LT_VOICE[g]}))
    items.append(("narr", OUTRO, None))
    return items


def kokoro():
    import kokoro_onnx
    base = Path.home() / ".cache" / "kokoro-onnx"
    return kokoro_onnx.Kokoro(str(base / "kokoro-v1.0.onnx"), str(base / "voices-v1.0.bin"))


def edge_lt(text, voice):
    import edge_tts

    async def run():
        buf = b""
        async for chunk in edge_tts.Communicate(text, voice, rate="-10%").stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return buf

    import time
    for attempt in range(6):
        try:
            mp3 = asyncio.run(run())
            break
        except Exception as e:  # the unofficial endpoint returns sporadic 403s
            if attempt == 5:
                raise
            time.sleep(2 * (attempt + 1))
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(mp3)
        f.flush()
        wav = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f.name, "-ac", "1", "-ar", str(SR),
                              "-f", "wav", "-"], capture_output=True, check=True).stdout
    a, _ = sf.read(io.BytesIO(wav), dtype="float32")
    return a


def ts(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h:02d}:{m:02d}:{t % 60:06.3f}".replace(".", ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    items = build_script()
    if args.dry_run:
        for kind, text, meta in items:
            print(("  🇱🇹 " if kind == "lt" else "") + text)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    k = kokoro()
    gap = lambda s: np.zeros(int(SR * s), dtype=np.float32)
    audio, subs, cards, t = [gap(0.6)], [], [], 0.6
    for kind, text, meta in items:
        if kind == "narr":
            a, sr = k.create(text, voice=NARRATOR, speed=0.95, lang="en-us")
            assert sr == SR
            caption = f"{meta['name']}  ·  {meta['respelling']}" if meta else text
            if meta:
                cards.append(meta)
        else:
            a = edge_lt(text, meta["voice"])
            caption = f"{text}  (lietuviškai)"
        a = np.asarray(a, dtype=np.float32)
        subs.append((t, t + len(a) / SR, caption))
        pause = 0.45 if kind == "narr" and meta else (1.0 if kind == "lt" else 0.8)
        audio += [a, gap(pause)]
        t += len(a) / SR + pause
    raw = OUT / "en_pronunciation_intro_raw.wav"
    sf.write(raw, np.concatenate(audio), SR)
    out = OUT / "en_pronunciation_intro.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(out)], check=True)
    raw.unlink()
    (OUT / "en_pronunciation_intro.srt").write_text(
        "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n" for i, (a, b, c) in enumerate(subs, 1)), encoding="utf-8")
    (OUT / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# English pronunciation introduction", "", f"> {INTRO}", "",
          "| Name | Say it | Stress | Who / what | Verify |", "|---|---|---|---|---|"]
    md += [f"| **{c['name']}** | {c['respelling']} | {c['stress']} | {c['gloss']} | {'⚠' if c['verify'] else ''} |"
           for c in cards]
    md += ["", f"> {OUTRO}"]
    (OUT / "script.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({t:.0f}s), .srt, cards.json, script.md")


if __name__ == "__main__":
    main()
