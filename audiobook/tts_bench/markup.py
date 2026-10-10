"""Emotion-markup pre-pass (STUB), review section 5.4.

Turns plain chapter text into engine-neutral utterance records, one per SENTENCE, tagged
with speaker, emotion and intensity. Engines that support tags (ElevenLabs audio tags,
Higgs control tokens, Gemini style prompts, Chatterbox exaggeration ...) render these
records with their own small adapter; engines without tags just read `text`.

This is the deterministic "Step A" of the plan plus a few keyword rules. It is NOT meant
to be final: step B (an LLM proposing speaker/emotion for the dialogue lines, with a
validator that forbids touching `text`) and step C (human overrides keyed by `id`) sit on
top. `apply_overrides()` shows the step-C hook.

Rules implemented
-----------------
* A paragraph starting with an em dash is dialogue. Split on " — ": segment 0 is spoken,
  segment 1 is the narrator's attribution, segment 2 is spoken again, and so on.
* Speaker of a dialogue paragraph = the cast name nearest to a speech verb in the
  attribution ("tare Vytautas", "Vytautas padejo kalavija ... "), else a pronoun matched
  against the most recently mentioned character of that gender, else alternation with the
  previous dialogue speaker, else `unknown` (confidence 0).
* `*"..."*` on its own is the divine / Amber Queen voice (kind `divine`).
* Emotion: keyword rules on the sentence and on the attribution ("whispered", "cried out",
  "wanted to cry out but ..." -> anguish), `!` raises intensity, a trailing `...` suggests
  anguish. Closed vocabulary, intensity 0..3.
* Pauses: 180 ms between sentences of one paragraph, 600 ms after narration paragraphs,
  350 ms after dialogue paragraphs, 900 ms after divine lines.

Record schema (JSON lines; see SCHEMA below)
    {"id": "p3_amber_queen#004", "kind": "dialogue", "speaker": "birute",
     "emotion": "anguish", "intensity": 3, "text": "Praurime, pasigailek...",
     "pause_after_ms": 350, "lang": "lt", "speaker_confidence": 0.9, "rule": "dash+name"}
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lexicon_tts import load_lexicon

EMOTIONS = ["neutral", "tender", "solemn", "awe", "fear", "anguish", "grief", "rage", "cold",
            "contempt", "sly", "exhausted", "whisper", "shout"]

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "wolf-saga utterance record (engine-neutral)",
    "type": "object",
    "required": ["id", "kind", "speaker", "emotion", "intensity", "text", "pause_after_ms", "lang"],
    "properties": {
        "id": {"type": "string", "description": "<passage-or-chapter-key>#<3-digit sequence>"},
        "kind": {"enum": ["narration", "dialogue", "divine", "inner"]},
        "speaker": {"type": "string", "description": "slug from the closed cast list, 'narrator', 'divine', or 'unknown'"},
        "emotion": {"enum": EMOTIONS},
        "intensity": {"type": "integer", "minimum": 0, "maximum": 3},
        "text": {"type": "string", "description": "canonical text, real spelling; never rewritten by later stages"},
        "pause_after_ms": {"type": "integer", "minimum": 0},
        "lang": {"enum": ["lt", "en"]},
        "speaker_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rule": {"type": "string", "description": "which rule produced speaker/emotion (provenance for QA)"},
    },
}

PAUSE_SENTENCE = 180
PAUSE_NARRATION = 600
PAUSE_DIALOGUE = 350
PAUSE_DIVINE = 900

_TRANSLIT = str.maketrans({"ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i", "š": "s", "ų": "u", "ū": "u", "ž": "z",
                           "Ą": "A", "Č": "C", "Ę": "E", "Ė": "E", "Į": "I", "Š": "S", "Ų": "U", "Ū": "U", "Ž": "Z"})


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.translate(_TRANSLIT).lower()).strip("_")


# --------------------------------------------------------------------------- cast

# Characters whose gender matters for pronoun resolution (lt "ji" / en "she").
FEMALE = {"birute", "jadvyga", "ona", "birutė"}

# Generic role nouns that are speakers without being named (lt and en stems).
ROLE_NOUNS = re.compile(r"\b(samdinys|sargybinis|pasiuntinys|vaitas|inžinierius|žemaitis|mercenary|sentry|guard|"
                        r"envoy|steward|engineer|bailiff)\b", re.I)

SPEECH_VERBS = re.compile(
    r"\b(tarė|tarė|pasakė|atsakė|paklausė|sušnibždėjo|sušnabždėjo|šnibždėjo|sušuko|surėkė|surikti|surikė|"
    r"šūktelėjo|riktelėjo|užriaumojo|atsiduso|pridūrė|ištarė|murmėjo|kalbėjo|pradėjo|pasigirdo|"
    r"said|asked|replied|answered|whispered|shouted|cried|murmured|added|growled|told|began|spoke|came a)\b", re.I)

_cast_cache: Optional[Tuple[re.Pattern, Dict[str, str]]] = None


def _cast():
    global _cast_cache
    if _cast_cache is None:
        surface: Dict[str, str] = {}
        for e in load_lexicon():
            if e["category"] != "character":
                continue
            slug = slugify(e["text"])
            for f in [e["text"], *e.get("variants", []), *e.get("ascii", [])]:
                surface.setdefault(f, slug)
        forms = sorted(surface, key=len, reverse=True)
        rx = re.compile(r"(?<!\w)(" + "|".join(re.escape(f) for f in forms) + r")(?!\w)")
        _cast_cache = (rx, surface)
    return _cast_cache


def names_in(text: str) -> List[Tuple[int, str]]:
    rx, surface = _cast()
    return [(m.start(1), surface[m.group(1)]) for m in rx.finditer(text)]


# --------------------------------------------------------------------------- emotion rules

# (emotion, regex) tried in order; first hit wins for the attribution, all counted for intensity.
EMOTION_RULES: List[Tuple[str, re.Pattern]] = [
    ("whisper", re.compile(r"šnibžd|šnabžd|pašnibžd|whisper|hushed|under his breath|murmur", re.I)),
    ("shout", re.compile(r"surik|surėk|sušuk|šūkt|riksm|riktel|užriaum|riaum|shout|cried out|cry out|roar|scream|bellow", re.I)),
    ("rage", re.compile(r"įnirt|pykt|pyk|kumšči|nagai įsmigo|susigniaužia|clench|anger|angry|fury|rage|snarl|through his teeth|pro dantis", re.I)),
    ("grief", re.compile(r"verk|ašar|gedul|raud|sielvart|skaus|weep|tears|grief|mourn|sob|sorrow", re.I)),
    ("anguish", re.compile(r"skend|dūst|gerkl|throat|drown|suffocat|bejėg|helpless", re.I)),
    ("fear", re.compile(r"baim|drebė|išsigand|fear|afraid|terror|tremb|shudder", re.I)),
    ("tender", re.compile(r"švelni|glost|tender|gently|softly|smelled of resin|kvepėjo derva", re.I)),
    ("awe", re.compile(r"regėjim|vibracij|vision|vibration|chorus|choras|šviesa užliejo", re.I)),
    ("cold", re.compile(r"šaltai|ledin|žmogžud|murder|cold-|coldly|icy|indifferent|abejingas", re.I)),
    ("contempt", re.compile(r"niekin|šaip|sneer|scorn|contempt|mocking", re.I)),
    ("sly", re.compile(r"šypsn|smirk|sly|cunning|slėpėsi sidabras", re.I)),
    ("exhausted", re.compile(r"pavarg|išsek|exhaust|weary|pasimetęs", re.I)),
    ("solemn", re.compile(r"iškilm|prisiek|oath|solemn|sacred|šventa", re.I)),
]
WANTED = re.compile(r"norėjo|bandė|wanted to|tried to", re.I)


def _emotion_from(text: str) -> Tuple[str, int]:
    hits = [(emo, len(rx.findall(text))) for emo, rx in EMOTION_RULES]
    hits = [(e, n) for e, n in hits if n]
    if not hits:
        return "neutral", 1
    emo, n = hits[0]
    return emo, min(3, 1 + (n - 1) + (1 if len(hits) > 1 else 0))


def emotion_for(sentence: str, attribution: str = "", kind: str = "narration") -> Tuple[str, int, str]:
    """-> (emotion, intensity, rule)"""
    base_emo, base_int = _emotion_from(attribution) if attribution else ("neutral", 1)
    if attribution and WANTED.search(attribution) and base_emo in ("shout", "whisper"):
        base_emo, base_int = "anguish", 2          # "wanted to cry out, but ..."
    s_emo, s_int = _emotion_from(sentence)
    if kind == "narration":
        emo, inten, rule = (s_emo, 1 if s_emo == "neutral" else s_int, "kw:sentence")
        if WANTED.search(sentence) and emo in ("shout", "whisper"):
            emo, inten, rule = "anguish", 2, "kw:wanted-to"      # "wanted to cry out, but ..."
        return emo, min(inten, 2), rule
    if kind == "divine":
        return "solemn", 2, "divine-default"
    # dialogue: the attribution is stronger than the sentence itself
    emo, inten, rule = (base_emo, base_int, "kw:attribution") if base_emo != "neutral" else (s_emo, s_int, "kw:sentence")
    if sentence.rstrip().endswith("!"):
        inten += 1
        if emo == "neutral":
            emo = "shout" if re.search(r"[A-ZĄČĘĖĮŠŲŪŽ]{3,}", sentence) else "rage"
            rule = "punct:!"
    if re.search(r"(\.\.\.|…)\s*$", sentence) and emo == "neutral":
        emo, inten, rule = "anguish", max(inten, 1), "punct:ellipsis"
    return emo, max(0, min(3, inten)), rule


# --------------------------------------------------------------------------- text structure

_SENT_SPLIT = re.compile(r"(?<=[.!?…])([\"”“»]?)\s+(?=[\"„“«—\-A-ZĄČĘĖĮŠŲŪŽ0-9])")
_DASH_SPLIT = re.compile(r"\s[—–]\s")
_ITALIC_WHOLE = re.compile(r"^\*+\s*[„\"“]?(.+?)[“\"”]?\s*\*+$", re.S)


def split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    out, pos = [], 0
    for m in _SENT_SPLIT.finditer(text):
        end = m.start() + len(m.group(1))
        out.append(text[pos:end].strip())
        pos = m.end()
    out.append(text[pos:].strip())
    return [s for s in out if s]


def _strip_md(text: str) -> str:
    text = re.sub(r"\{[^}]*\}", "", text)            # {.unnumbered}
    text = re.sub(r"\[\^[^\]]*\]", "", text)         # footnote refs
    text = text.replace("**", "")
    return text.strip()


def is_attribution(seg: str) -> bool:
    """Does an em-dash-delimited segment look like the narrator's attribution (as opposed to
    a parenthetical continuation of the speech)?"""
    head = seg[:40]
    if SPEECH_VERBS.search(seg[:60]) or ROLE_NOUNS.search(head):
        return True
    if any(p < 25 for p, _ in names_in(seg)):
        return True
    return bool(re.match(r"^(jis|ji|he|she)\b", seg, re.I))


def _resolve_speaker(attrib: str, dialogue_text: str, recent: List[str], last_speakers: List[str],
                     prev_was_dialogue: bool) -> Tuple[str, float, str]:
    """Pick the speaker for a dialogue paragraph (see module docstring)."""
    addressed = {n for _, n in names_in(dialogue_text)}      # vocatives are NOT the speaker
    if attrib:
        m = SPEECH_VERBS.search(attrib)
        names = [(p, n) for p, n in names_in(attrib)]
        roles = [(r.start(), "extra_" + slugify(r.group(1))) for r in ROLE_NOUNS.finditer(attrib)]
        if m and (names or roles):
            vpos = m.start()
            near = [(abs(p - vpos), n) for p, n in names + roles if abs(p - vpos) <= 40]
            if near:
                return min(near)[1], 0.9, "dash+name-near-verb"
        if not m and names:
            return names[0][1], 0.7, "dash+first-name"
        if roles:
            return roles[0][1], 0.6, "dash+role-noun"
        low = attrib.lower()
        if re.search(r"\b(ji|she)\b", low):
            for n in recent:
                if n in FEMALE:
                    return n, 0.6, "pronoun-she"
        if re.search(r"\b(jis|he)\b", low):
            for n in recent:
                if n not in FEMALE and n not in addressed:
                    return n, 0.5, "pronoun-he"
        if names:
            return names[0][1], 0.4, "dash+name-far"
        if SPEECH_VERBS.search(attrib):
            return "extra_unnamed", 0.3, "dash+unnamed"
    if last_speakers:
        if prev_was_dialogue:
            if len(last_speakers) >= 2 and last_speakers[-2] != last_speakers[-1]:
                return last_speakers[-2], 0.5, "alternate"
            for n in recent:
                if n != last_speakers[-1]:
                    return n, 0.35, "alternate-recent"
        else:
            return last_speakers[-1], 0.45, "continue-after-narration"
    return "unknown", 0.0, "none"


def markup(text: str, lang: str, passage_id: str, context_names: Optional[List[str]] = None) -> List[dict]:
    """Plain text (blank-line separated paragraphs) -> utterance records.

    `context_names`: slugs of characters established by text BEFORE this excerpt (newest first),
    used only to seed pronoun / alternation resolution.
    """
    paragraphs = [_strip_md(p) for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    records: List[dict] = []
    recent: List[str] = list(context_names or [])   # most recently mentioned characters, newest first
    last_speakers: List[str] = []   # speakers of consecutive dialogue paragraphs
    seq = 0
    queen_seen = False
    prev_was_dialogue = False

    def note_names(s: str):
        found = names_in(s) + [(r.start(), "extra_" + slugify(r.group(1))) for r in ROLE_NOUNS.finditer(s)]
        for _, n in sorted(found, key=lambda t: t[0], reverse=True):
            if n in recent:
                recent.remove(n)
            recent.insert(0, n)

    def emit(kind, speaker, sents, pause_last, attrib="", conf=1.0, rule="", sentence_rule=True):
        nonlocal seq
        for i, s in enumerate(sents):
            emo, inten, erule = emotion_for(s, attrib, kind)
            seq += 1
            records.append({
                "id": "%s#%03d" % (passage_id, seq), "kind": kind, "speaker": speaker,
                "emotion": emo, "intensity": inten, "text": s,
                "pause_after_ms": pause_last if i == len(sents) - 1 else PAUSE_SENTENCE,
                "lang": lang, "speaker_confidence": round(conf, 2), "rule": (rule + "|" + erule).strip("|"),
            })

    for para in paragraphs:
        if re.search(r"Gintaro Karalien|Amber Queen", para):
            queen_seen = True
        italic = _ITALIC_WHOLE.match(para)
        if italic and para.startswith("*"):
            inner = italic.group(1).strip()
            emit("divine", "amber_queen" if queen_seen else "divine", split_sentences(inner), PAUSE_DIVINE,
                 conf=0.8, rule="italic-whole")
            continue
        if re.match(r"^[—–-]\s", para):
            body = re.sub(r"^[—–-]\s*", "", para)
            raw = [s.strip() for s in _DASH_SPLIT.split(body) if s.strip()]
            # state machine: speech -> (attribution-looking segment) -> narration -> speech ...
            segs: List[Tuple[str, str]] = []       # (kind, text)
            state = "speech"
            for i, seg in enumerate(raw):
                if i == 0:
                    segs.append(("dialogue", seg))
                elif state == "speech":
                    if is_attribution(seg):
                        segs.append(("narration", seg)); state = "narr"
                    else:                                  # parenthetical dash inside the speech
                        k, t = segs[-1]; segs[-1] = (k, t + " — " + seg)
                else:
                    segs.append(("dialogue", seg)); state = "speech"
            attrib = " ".join(t for k, t in segs if k == "narration")
            dialogue_text = " ".join(t for k, t in segs if k == "dialogue")
            speaker, conf, rule = _resolve_speaker(attrib, dialogue_text, recent, last_speakers, prev_was_dialogue)
            for kind, seg in segs:
                if kind == "dialogue":
                    emit("dialogue", speaker, split_sentences(seg), PAUSE_SENTENCE, attrib=attrib, conf=conf, rule=rule)
                else:
                    emit("narration", "narrator", split_sentences(seg), PAUSE_SENTENCE, conf=1.0, rule="dash-attribution")
            # first dialogue sentence of a paragraph keeps its intensity; later ones are one notch softer
            seen_first = False
            for r in records[-sum(len(split_sentences(t)) for _, t in segs):]:
                if r["kind"] == "dialogue":
                    if seen_first and r["intensity"] > 1:
                        r["intensity"] -= 1
                    seen_first = True
            records[-1]["pause_after_ms"] = PAUSE_DIALOGUE if records[-1]["kind"] == "dialogue" else PAUSE_NARRATION
            if speaker != "unknown":
                last_speakers.append(speaker)
            note_names(attrib)
            prev_was_dialogue = True
        else:
            emit("narration", "narrator", split_sentences(para), PAUSE_NARRATION, conf=1.0, rule="narration")
            note_names(para)
            prev_was_dialogue = False
    return records


def apply_overrides(records: List[dict], overrides: Dict[str, dict]) -> List[dict]:
    """Step C: human overrides keyed by utterance id win over rules (never touch `text`)."""
    out = []
    for r in records:
        o = overrides.get(r["id"], {})
        if "text" in o:
            raise ValueError("overrides must not change text (%s)" % r["id"])
        out.append({**r, **o, "rule": r["rule"] + ("|override" if o else "")})
    return out


def write_jsonl(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def fidelity_ok(source_text: str, records: List[dict]) -> bool:
    """Validator from the plan: concatenated record text must equal the input text
    (ignoring whitespace, dashes, quotes and markdown italics)."""
    def norm(s):
        return re.sub(r"[\s—–\-\*„“”\"']+", "", s)
    return norm(_strip_md(source_text)) == norm("".join(r["text"] for r in records))


if __name__ == "__main__":
    import sys
    from passages import load_passages
    which = sys.argv[1] if len(sys.argv) > 1 else "p2_dialogue"
    lang = sys.argv[2] if len(sys.argv) > 2 else "lt"
    for p in load_passages():
        if p["id"] == which:
            for r in markup(p["text"][lang], lang, p["id"], p.get("context_names")):
                print(json.dumps(r, ensure_ascii=False))
            print("fidelity:", fidelity_ok(p["text"][lang], markup(p["text"][lang], lang, p["id"], p.get("context_names"))))
