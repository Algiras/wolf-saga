"""Neutral emotion vocabulary -> per-engine renderings (review section 5.4 renderers).

The neutral vocabulary is markup.EMOTIONS with intensity 0..3. Every table here is a
starting point to be tuned by listening, not a verified recipe.
"""

from __future__ import annotations

from typing import Dict, Tuple

# ElevenLabs v3 / v4 free-text audio tags. Tags are lowercase, in square brackets, before the line.
ELEVEN = {
    "neutral": "", "tender": "[softly]", "solemn": "[solemn]", "awe": "[in awe]", "fear": "[fearful]",
    "anguish": "[anguished]", "grief": "[sorrowful]", "rage": "[angry]", "cold": "[cold, flat]",
    "contempt": "[contemptuous]", "sly": "[sly]", "exhausted": "[weary]", "whisper": "[whispers]",
    "shout": "[shouts]",
}

# Natural-language direction (Gemini style prompt, OpenAI `instructions`).
PHRASE = {
    "neutral": "in a calm, steady storyteller voice",
    "tender": "tenderly and softly",
    "solemn": "solemnly, slowly, with weight",
    "awe": "in hushed awe",
    "fear": "fearfully, breath tight",
    "anguish": "in anguish, voice breaking",
    "grief": "grief-stricken, barely holding back tears",
    "rage": "with barely contained rage, low and hard",
    "cold": "coldly, flat and controlled",
    "contempt": "with quiet contempt",
    "sly": "slyly, with a hint of a smile",
    "exhausted": "wearily, drained",
    "whisper": "in a low urgent whisper",
    "shout": "shouting, full force",
}

INTENSITY_ADV = {0: "very slightly ", 1: "", 2: "quite ", 3: "intensely "}

# Azure SSML <prosody>: (rate, pitch, volume). Azure lt-LT voices have no styles/roles.
AZURE_PROSODY: Dict[str, Tuple[str, str, str]] = {
    "neutral": ("0%", "0%", "default"), "tender": ("-8%", "-2%", "soft"), "solemn": ("-12%", "-4%", "default"),
    "awe": ("-8%", "+0%", "soft"), "fear": ("+6%", "+6%", "default"), "anguish": ("-4%", "+4%", "default"),
    "grief": ("-14%", "-5%", "soft"), "rage": ("+4%", "-3%", "loud"), "cold": ("-6%", "-6%", "default"),
    "contempt": ("-6%", "-3%", "default"), "sly": ("-2%", "+0%", "default"), "exhausted": ("-14%", "-6%", "soft"),
    "whisper": ("-10%", "-4%", "x-soft"), "shout": ("+8%", "+8%", "x-loud"),
}

# Edge read-aloud accepts rate / pitch / volume strings only.
EDGE_PROSODY: Dict[str, Tuple[str, str, str]] = {
    "neutral": ("+0%", "+0Hz", "+0%"), "tender": ("-8%", "-2Hz", "-15%"), "solemn": ("-12%", "-4Hz", "+0%"),
    "awe": ("-8%", "+0Hz", "-15%"), "fear": ("+6%", "+6Hz", "+0%"), "anguish": ("-4%", "+4Hz", "+0%"),
    "grief": ("-14%", "-5Hz", "-15%"), "rage": ("+4%", "-3Hz", "+15%"), "cold": ("-6%", "-6Hz", "+0%"),
    "contempt": ("-6%", "-3Hz", "+0%"), "sly": ("-2%", "+0Hz", "+0%"), "exhausted": ("-14%", "-6Hz", "-15%"),
    "whisper": ("-10%", "-4Hz", "-40%"), "shout": ("+8%", "+8Hz", "+30%"),
}

# Higgs TTS 3 control tokens (<|category:value|>), sentence-level, placed at the start.
HIGGS = {
    "neutral": "", "tender": "<|emotion:affection|>", "solemn": "<|emotion:determination|>",
    "awe": "<|emotion:awe|>", "fear": "<|emotion:fear|>", "anguish": "<|emotion:helplessness|>",
    "grief": "<|emotion:sadness|>", "rage": "<|emotion:anger|>", "cold": "<|emotion:bitterness|>",
    "contempt": "<|emotion:disgust|>", "sly": "<|emotion:amusement|>", "exhausted": "<|emotion:sadness|><|prosody:speed_slow|>",
    "whisper": "<|style:whispering|>", "shout": "<|style:shouting|>",
}

# Chatterbox: (exaggeration, cfg_weight)
CHATTERBOX = {
    "neutral": (0.45, 0.5), "tender": (0.5, 0.4), "solemn": (0.5, 0.35), "awe": (0.6, 0.4), "fear": (0.7, 0.4),
    "anguish": (0.85, 0.3), "grief": (0.75, 0.3), "rage": (0.9, 0.3), "cold": (0.4, 0.5), "contempt": (0.55, 0.4),
    "sly": (0.55, 0.4), "exhausted": (0.4, 0.35), "whisper": (0.4, 0.3), "shout": (1.0, 0.25),
}


def eleven_tag(emotion: str, intensity: int) -> str:
    tag = ELEVEN.get(emotion, "")
    if tag and intensity >= 3:
        tag += " [intense]"
    return tag


def phrase(emotion: str, intensity: int) -> str:
    base = PHRASE.get(emotion, PHRASE["neutral"])
    if emotion == "neutral":
        return base
    return INTENSITY_ADV.get(intensity, "") + base
