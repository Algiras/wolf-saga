#!/usr/bin/env python3
"""
Offline checks for book_manifest chapter discovery (no network, no models).

Run from the repository root:  python3 audiobook/test_preprocessor.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import book_manifest as bm  # noqa: E402

BOOK = 1


def test_discovery_includes_prologue_and_pradzia(chapters):
    keys = [c["key"] for c in chapters]
    assert "b1_prologue" in keys, f"b1_prologue missing from {keys[:5]}..."
    assert "b1_00_pradzia" in keys, "b1_00_pradzia missing"
    print(f"ok: discovery includes b1_prologue and b1_00_pradzia ({len(chapters)} chapters)")


def test_non_story_pages_excluded(chapters):
    for c in chapters:
        stem = Path(c["source"]).stem
        assert stem not in bm.NON_STORY_STEMS, f"non-story page narrated: {c['source']}"
        assert not c["source"].startswith(("index", "copyright", "sources")), c["source"]
        assert c["source"].startswith(f"{BOOK}/"), f"chapter from another book: {c['source']}"
    print("ok: index, copyright and sources are excluded")


def test_keys_unique(chapters):
    keys = [c["key"] for c in chapters]
    assert len(keys) == len(set(keys)), "duplicate chapter keys"
    print("ok: keys are unique")


def test_order_contiguous(chapters):
    orders = [c["order"] for c in chapters]
    assert orders == list(range(1, len(chapters) + 1)), f"order not contiguous: {orders}"
    print("ok: order is contiguous 1..N")


def test_sources_exist(chapters):
    books_dir = bm.BOOKS_DIR
    for c in chapters:
        assert (books_dir / c["source"]).exists(), f"discovered source missing: {c['source']}"
    print("ok: every discovered source file exists")


def test_missing_sources_are_reported(skipped):
    for source, reason in skipped:
        if reason == "source file not found":
            print(f"note: {source} is listed in _quarto.yml but absent; skipped")


def test_output_names():
    assert bm.intro_wav_name(1) == "000_intro.wav"
    assert bm.outro_wav_name(1) == "99_outro.wav"
    assert bm.audio_path("b1_prologue").name == "b1_prologue.wav"
    print("ok: intro, outro and chapter WAV names")


def main():
    chapters, skipped = bm.discover_chapters_report(BOOK)
    assert chapters, "no chapters discovered for book 1"
    test_discovery_includes_prologue_and_pradzia(chapters)
    test_non_story_pages_excluded(chapters)
    test_keys_unique(chapters)
    test_order_contiguous(chapters)
    test_sources_exist(chapters)
    test_missing_sources_are_reported(skipped)
    test_output_names()
    print("\nall book_manifest checks passed")


if __name__ == "__main__":
    main()
