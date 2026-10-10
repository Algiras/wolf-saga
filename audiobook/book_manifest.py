#!/usr/bin/env python3
"""
Shared chapter discovery and manifest helpers for the audiobook pipeline.

Pure standard library + PyYAML: importing this module never loads torch, langchain
or any model, and never touches the network. Every stage imports it, because the
stage scripts start with a digit and cannot import each other cleanly.

Concepts
--------
- Chapters are discovered from books/_quarto.yml (for ORDER) and filtered to one
  book's directory (books/<N>/).
- Each chapter gets a STABLE KEY derived from its source file name
  (books/1/03_gintaro_sapnas.qmd -> "b1_03_gintaro_sapnas"). Output and cache
  file names use the key, never the position in the list, so inserting a chapter
  (00_pradzia, 28b_krevos_sutartis, ...) never renames or invalidates others.
- A separate integer "order" field in preprocessed/manifest.json gives the
  listening sequence.
- A sha256 content hash of the source text lets later stages skip unchanged
  chapters.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

AUDIOBOOK_DIR = Path(__file__).parent
BOOKS_DIR = AUDIOBOOK_DIR.parent / "books"
PREPROCESSED_DIR = AUDIOBOOK_DIR / "preprocessed"
CACHE_DIR = AUDIOBOOK_DIR / "cache"
OUTPUT_DIR = AUDIOBOOK_DIR / "output"
TRANSCRIPTS_DIR = AUDIOBOOK_DIR / "transcripts"
MANIFEST_PATH = PREPROCESSED_DIR / "manifest.json"

# --------------------------------------------------------------------------- #
# Which pages are story chapters
# --------------------------------------------------------------------------- #

# Quarto pages that are never narrated.
NON_STORY_STEMS = {"index", "copyright", "sources", "references"}
# Files numbered at or above this are appendices / editorial notes
# (31_senoves_kalba, 32_redakcines_pastabos, ...), not story.
APPENDIX_FROM_NUMBER = 31

# --------------------------------------------------------------------------- #
# Book metadata (spoken in intro / outro)
# --------------------------------------------------------------------------- #

SERIES_TITLE = "Wolf Saga"
AUTHOR = "Algimantas Krasauskas"
BOOK_TITLES_EN = {
    1: "Exile of the Wolf",
    2: "The Golden Shadow",  # working title, see books/2/detailed_outline.md
    3: "The Green Wood",
    4: "The Invisible Crown",
    5: "The Wolf's Legacy",
    6: "The Holy Forest",
}
NUMBER_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
                7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}

# English renderings of the Quarto part titles, used for the optional spoken
# heading before the first chapter of a part. Unknown parts fall back to a
# plain ASCII transliteration of the Lithuanian title.
PART_TITLES_EN = {
    "Nuosmukis": "Decline",
    "Pabėgimas": "Flight",
    "Karas ir Tvarka": "War and Order",
}

_LT_TRANSLIT = str.maketrans({
    "ą": "a", "č": "ch", "ę": "e", "ė": "e", "į": "i", "š": "sh", "ų": "u", "ū": "u", "ž": "zh",
    "Ą": "A", "Č": "Ch", "Ę": "E", "Ė": "E", "Į": "I", "Š": "Sh", "Ų": "U", "Ū": "U", "Ž": "Zh",
})


def book_label(book: int) -> str:
    """'Book One'"""
    return f"Book {NUMBER_WORDS.get(book, str(book))}"


def book_title_en(book: int) -> str:
    return BOOK_TITLES_EN.get(book, f"Book {book}")


def intro_text(book: int) -> str:
    return (
        f"{SERIES_TITLE}. {book_label(book)}: {book_title_en(book)}.\n\n"
        f"Written by {AUTHOR}.\n\n"
        "We begin.\n"
    )


def outro_text(book: int) -> str:
    return (
        f"\nThis was {SERIES_TITLE}. {book_label(book)}: {book_title_en(book)}.\n\n"
        "Licensed under Creative Commons Attribution Non-Commercial Share-Alike 4.0 International.\n\n"
        "Thank you for listening.\n\n"
        "End of audiobook.\n"
    )


def spoken_part_heading(part_number: Optional[int], part_title: Optional[str]) -> Optional[str]:
    """'Part Two. Flight.' for the first chapter of a Quarto part, else None."""
    if not part_title:
        return None
    title_en = PART_TITLES_EN.get(part_title) or part_title.translate(_LT_TRANSLIT)
    if part_number:
        return f"Part {NUMBER_WORDS.get(part_number, part_number)}. {title_en}."
    return f"{title_en}."


# --------------------------------------------------------------------------- #
# File naming (single source of truth for every stage)
# --------------------------------------------------------------------------- #

def chapter_key(book: int, source: str) -> str:
    """'1/03_gintaro_sapnas.qmd' -> 'b1_03_gintaro_sapnas'."""
    return f"b{book}_{Path(source).stem}"


def preprocessed_path(key: str) -> Path:
    return PREPROCESSED_DIR / f"{key}.txt"


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.txt"


def cache_hash_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.hash"


def audio_path(key: str) -> Path:
    return OUTPUT_DIR / f"{key}.wav"


def audio_meta_path(key: str) -> Path:
    return OUTPUT_DIR / f"{key}.meta.json"


def srt_path(key: str) -> Path:
    return TRANSCRIPTS_DIR / f"{key}.srt"


def intro_wav_name(book: int) -> str:
    # Book I keeps the historical names (other tooling filters on them).
    return "000_intro.wav" if book == 1 else f"b{book}_000_intro.wav"


def outro_wav_name(book: int) -> str:
    return "99_outro.wav" if book == 1 else f"b{book}_99_outro.wav"


def master_wav_name(book: int) -> str:
    return f"GelezinioVilkoSaga_Book{book}_Complete.wav"


def master_srt_name(book: int) -> str:
    return f"GelezinioVilkoSaga_Book{book}_Complete.srt"


def video_name(book: int, captioned: bool = False) -> str:
    return f"GelezinioVilkoSaga_Book{book}_YouTube{'_captioned' if captioned else ''}.mp4"


def timestamps_name(book: int) -> str:
    return "timestamps.txt" if book == 1 else f"timestamps_book{book}.txt"


# --------------------------------------------------------------------------- #
# Hashing / titles
# --------------------------------------------------------------------------- #

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_title(text: str, fallback: str = "") -> str:
    """First markdown H1 of a .qmd file (without a trailing {#id} attribute)."""
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+?)(\s+\{[^}]*\})?\s*$", line)
        if m:
            return m.group(1).strip()
    return fallback


# --------------------------------------------------------------------------- #
# Chapter discovery
# --------------------------------------------------------------------------- #

def _walk_quarto(items: List[Any], part: Optional[str], out: List[Tuple[str, Optional[str]]]) -> None:
    """Flatten _quarto.yml 'chapters', remembering the enclosing part title.

    A 'part' is only a label here: part titles are NOT chapters. If a part is
    given as a .qmd file, its H1 is used as the label and the page itself is not
    narrated as a chapter.
    """
    for item in items or []:
        if isinstance(item, str):
            out.append((item, part))
        elif isinstance(item, dict):
            if "part" in item:
                label = item["part"]
                if isinstance(label, str) and label.endswith(".qmd"):
                    page = BOOKS_DIR / label
                    label = extract_title(page.read_text(encoding="utf-8"), Path(label).stem) if page.exists() else Path(label).stem
                _walk_quarto(item.get("chapters", []), label, out)
            elif "file" in item:
                out.append((item["file"], part))
            elif "chapters" in item:
                _walk_quarto(item["chapters"], part, out)


def quarto_entries() -> List[Tuple[str, Optional[str]]]:
    """All (relative .qmd path, part title) pairs in book order from _quarto.yml."""
    with open(BOOKS_DIR / "_quarto.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    raw: List[Tuple[str, Optional[str]]] = []
    _walk_quarto(config["book"]["chapters"], None, raw)
    seen, out = set(), []
    for source, part in raw:  # a page listed twice is narrated once
        if source not in seen:
            seen.add(source)
            out.append((source, part))
    return out


def _skip_reason(source: str) -> Optional[str]:
    stem = Path(source).stem
    if stem in NON_STORY_STEMS:
        return "non-story page"
    m = re.match(r"^(\d+)", stem)
    if m and int(m.group(1)) >= APPENDIX_FROM_NUMBER:
        return f"appendix/editorial (number >= {APPENDIX_FROM_NUMBER})"
    return None


def discover_chapters_report(book: int = 1) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """Return (chapters, skipped) for one book.

    chapters: dicts with book, key, order (1-based), title, source (path relative
    to books/), source_hash, part, part_number, first_in_part.
    skipped: (source, reason) for pages of this book that are not narrated.
    """
    prefix = f"{book}/"
    chapters: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []
    part_numbers: Dict[str, int] = {}
    seen_parts: set = set()

    for source, part in quarto_entries():
        if not source.startswith(prefix):
            # Pages outside this book (index.qmd, sources.qmd, other books) are
            # not reported as skipped unless they are plain non-story pages.
            if _skip_reason(source):
                skipped.append((source, _skip_reason(source)))
            continue
        reason = _skip_reason(source)
        if reason:
            skipped.append((source, reason))
            continue
        path = BOOKS_DIR / source
        if not path.exists():
            skipped.append((source, "source file not found"))
            continue
        text = path.read_text(encoding="utf-8")
        if part and part not in part_numbers:
            part_numbers[part] = len(part_numbers) + 1
        first_in_part = bool(part) and part not in seen_parts
        if part:
            seen_parts.add(part)
        chapters.append({
            "book": book,
            "key": chapter_key(book, source),
            "order": len(chapters) + 1,
            "title": extract_title(text, Path(source).stem.replace("_", " ").title()),
            "source": source,
            "source_hash": sha256_text(text),
            "part": part,
            "part_number": part_numbers.get(part) if part else None,
            "first_in_part": first_in_part,
        })
    return chapters, skipped


def discover_chapters(book: int = 1) -> List[Dict[str, Any]]:
    return discover_chapters_report(book)[0]


# --------------------------------------------------------------------------- #
# Manifest (preprocessed/manifest.json)
# --------------------------------------------------------------------------- #

def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_manifest(book: Optional[int] = None) -> List[Dict[str, Any]]:
    """Manifest entries (all books, or one), sorted by (book, order).

    Entries from the legacy index/name format (no 'key') are ignored.
    """
    if not MANIFEST_PATH.exists():
        return []
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    entries = [e for e in data if isinstance(e, dict) and "key" in e]
    if book is not None:
        entries = [e for e in entries if e.get("book") == book]
    return sorted(entries, key=lambda e: (e.get("book", 0), e.get("order", 0)))


def save_manifest(book: int, entries: List[Dict[str, Any]]) -> None:
    """Replace this book's entries, keeping every other book's entries."""
    others = [e for e in load_manifest() if e.get("book") != book]
    merged = sorted(others + list(entries), key=lambda e: (e.get("book", 0), e.get("order", 0)))
    atomic_write_json(MANIFEST_PATH, merged)


def build_manifest_entries(book: int, previous: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Fresh discovery merged with what is already recorded as preprocessed.

    'preprocessed_hash' is the source hash the preprocessed text was generated
    from (None while pending). A chapter is ready for TTS when it equals
    'source_hash' and the text file exists.
    """
    prev = {e["key"]: e for e in (previous if previous is not None else load_manifest(book))}
    entries = []
    for ch in discover_chapters(book):
        entry = dict(ch)
        entry["file"] = str(preprocessed_path(ch["key"]).absolute())
        entry["preprocessed_hash"] = prev.get(ch["key"], {}).get("preprocessed_hash")
        entries.append(entry)
    return entries


def is_ready(entry: Dict[str, Any]) -> bool:
    """Preprocessed text exists and matches the current source."""
    p = Path(entry["file"])
    return (
        entry.get("preprocessed_hash") == entry.get("source_hash")
        and p.exists()
        and p.stat().st_size >= 10
    )


def audio_is_current(entry: Dict[str, Any]) -> bool:
    """WAV exists and was generated from the current source hash."""
    wav = audio_path(entry["key"])
    if not (wav.exists() and wav.stat().st_size > 1000):
        return False
    meta = audio_meta_path(entry["key"])
    if not meta.exists():
        return True  # legacy output without a sidecar: trust it, do not re-spend TTS
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("source_hash") == entry.get("source_hash")
    except (OSError, ValueError):
        return False


def write_audio_meta(entry: Dict[str, Any], narration_text: str) -> None:
    """Record which source version a chapter WAV was narrated from."""
    import time
    atomic_write_json(audio_meta_path(entry["key"]), {
        "key": entry["key"],
        "book": entry.get("book"),
        "order": entry.get("order"),
        "source_hash": entry.get("source_hash"),
        "text_sha256": sha256_text(narration_text),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
