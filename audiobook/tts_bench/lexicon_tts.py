"""Pronunciation lexicon matcher and per-engine renderers (review section 5.5).

One matcher, many outputs. `find_spans()` returns spans over the CANONICAL text; the
canonical text (real Lithuanian spelling, diacritics intact) is what captions and the
listening page show. `render()` only produces the string that is sent to an engine.

Modes
-----
none        send the text untouched (default for Lithuanian voices: they read Lithuanian)
ipa_slash   replace the match with /IPA/  (ElevenLabs v4 inline IPA)
ssml_ipa    replace with <phoneme alphabet="ipa" ph="..."> (Azure / Google en voices)
respell     replace with a TTS-friendly respelling built from `respelling_en`
            (hyphens removed, caps lowered; "VEE-tow-tahs" -> "Veetowtahs")
respell_hy  same but keeps the hyphens ("Vee-tow-tahs"), for engines that need syllables
lt_accent   EXPERIMENTAL: Lithuanian stress mark (acute) on the stressed syllable, from `stress`
            ("kęs-TU-tis" -> "kęstútis"). Test whether the voice honours it.

Inflected forms: the lexicon holds IPA/respelling for the base form only. In English
narration the translated text uses the base form, so inflected `variants` are mapped to
the base form's rendering. For Lithuanian text with a non-"none" mode this changes the
case ending, so use it for diagnostics only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape, quoteattr

REPO_ROOT = Path(__file__).resolve().parents[2]
LEXICON_PATH = REPO_ROOT / "world_rules" / "pronunciation_lexicon.json"

# (engine family, language) -> default mode. Overridable on the CLI with --lexicon-mode.
POLICY: Dict[tuple, str] = {
    ("elevenlabs", "lt"): "none",
    ("elevenlabs", "en"): "ipa_slash",
    ("gemini", "lt"): "none",
    ("gemini", "en"): "respell",
    ("google", "lt"): "none",       # Chirp 3 HD: custom pronunciation not supported for lt-LT (vendor docs)
    ("google", "en"): "respell",
    ("azure", "lt"): "none",        # <phoneme> for lt-LT is not documented; test lt_accent separately
    ("azure", "en"): "ssml_ipa",
    ("openai", "lt"): "none",
    ("openai", "en"): "respell",
    ("edge", "lt"): "none",
    ("edge", "en"): "respell",
    ("say", "en"): "respell",
    ("kokoro", "en"): "respell",
    ("piper", "lt"): "none",
    ("omnivoice", "lt"): "none",
    ("omnivoice", "en"): "respell",
    ("higgs", "lt"): "none",
    ("higgs", "en"): "respell",
    ("chatterbox", "en"): "respell",
}


@dataclass
class Span:
    start: int
    end: int
    surface: str
    entry: dict
    inflected: bool


@lru_cache(maxsize=1)
def load_lexicon() -> List[dict]:
    with open(LEXICON_PATH, encoding="utf8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _matcher():
    surface_map: Dict[str, tuple] = {}
    for e in load_lexicon():
        surface_map[e["text"]] = (e, False)
    for e in load_lexicon():
        for v in e.get("variants", []):
            surface_map.setdefault(v, (e, True))
        for a in e.get("ascii", []):
            surface_map.setdefault(a, (e, True))
    forms = sorted(surface_map, key=len, reverse=True)
    rx = re.compile(r"(?<!\w)(" + "|".join(re.escape(f) for f in forms) + r")(?!\w)")
    return rx, surface_map


def find_spans(text: str) -> List[Span]:
    rx, surface_map = _matcher()
    spans: List[Span] = []
    for m in rx.finditer(text):
        entry, inflected = surface_map[m.group(1)]
        spans.append(Span(m.start(1), m.end(1), m.group(1), entry, inflected))
    return spans


def _respell(entry: dict, keep_hyphens: bool) -> str:
    raw = entry.get("respelling_en") or entry["text"]
    syl = raw.split("-")
    if keep_hyphens:
        return "-".join(s.lower() for s in syl).capitalize()
    return "".join(s.lower() for s in syl).capitalize()


_ACUTE = "́"
_VOWELS = "aeiouyąęėįųūAEIOUYĄĘĖĮŲŪ"


def _lt_accent(entry: dict, surface: str) -> str:
    """Put an acute mark on the first vowel of the capitalised syllable in `stress`."""
    stress = entry.get("stress") or ""
    syl = stress.split("-")
    base = "".join(s.lower() for s in syl)
    out = []
    for s in syl:
        if s.isupper() or (any(c.isupper() for c in s) and s == s.upper()):
            marked = []
            done = False
            for ch in s.lower():
                marked.append(ch)
                if not done and ch in _VOWELS.lower():
                    marked.append(_ACUTE)
                    done = True
            out.append("".join(marked))
        else:
            out.append(s.lower())
    result = "".join(out)
    if not base:
        return surface
    return result.capitalize() if surface[:1].isupper() else result


def render(text: str, mode: str) -> str:
    """Return `text` with every lexicon hit rewritten for `mode` (see module docstring)."""
    if mode in (None, "", "none"):
        return text
    spans = find_spans(text)
    if not spans:
        return text
    out, pos = [], 0
    for sp in spans:
        out.append(text[pos:sp.start])
        e = sp.entry
        if mode == "ipa_slash":
            out.append("/" + e["ipa"] + "/")
        elif mode == "ssml_ipa":
            out.append('<phoneme alphabet="ipa" ph=%s>%s</phoneme>' % (quoteattr(e["ipa"]), xml_escape(sp.surface)))
        elif mode == "respell":
            out.append(_respell(e, keep_hyphens=False))
        elif mode == "respell_hy":
            out.append(_respell(e, keep_hyphens=True))
        elif mode == "lt_accent":
            out.append(_lt_accent(e, sp.surface))
        else:
            raise ValueError("unknown lexicon mode: %s" % mode)
        pos = sp.end
    out.append(text[pos:])
    return "".join(out)


def mode_for(engine_family: str, lang: str, override: Optional[str] = None) -> str:
    if override:
        return override
    return POLICY.get((engine_family, lang), "none")


def report(text: str) -> List[dict]:
    """Lexicon hits in `text`, flagged with verify=true rows (QA report for the author)."""
    seen: Dict[str, dict] = {}
    for sp in find_spans(text):
        e = sp.entry
        row = seen.setdefault(e["text"], {"entry": e["text"], "category": e["category"], "ipa": e["ipa"],
                                         "verify": bool(e.get("verify")), "surfaces": set()})
        row["surfaces"].add(sp.surface)
    out = []
    for row in seen.values():
        row["surfaces"] = sorted(row["surfaces"])
        out.append(row)
    return sorted(out, key=lambda r: r["entry"])


def export_pls(path: Path, lang: str = "lt") -> int:
    """Write the lexicon as a W3C PLS file (IPA phonemes) for engines that take lexicons
    (ElevenLabs pronunciation dictionaries, Azure/Polly lexicons). Returns the rule count."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" '
             'alphabet="ipa" xml:lang="%s">' % lang]
    n = 0
    for e in load_lexicon():
        forms = [e["text"]] + list(e.get("variants", []))
        for f in forms:
            if f != e["text"] and e.get("stress_notes"):
                continue  # inflected form with a stress shift: do not reuse the base IPA
            lines.append("  <lexeme><grapheme>%s</grapheme><phoneme>%s</phoneme></lexeme>"
                         % (xml_escape(f), xml_escape(e["ipa"])))
            n += 1
    lines.append("</lexicon>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf8")
    return n


if __name__ == "__main__":
    import sys
    demo = "Kęstutis ir Vytautas sėdėjo Trakuose; Jogailos pasiuntiniai atvyko iš Rygos."
    for m in ("none", "ipa_slash", "ssml_ipa", "respell", "respell_hy", "lt_accent"):
        print(m.ljust(11), render(demo, m))
    if len(sys.argv) > 1:
        print(json.dumps(report(Path(sys.argv[1]).read_text(encoding="utf8")), ensure_ascii=False, indent=1))
