#!/usr/bin/env python3
"""
Batch video generator for audiobook chapters.

Walks one book in listening order (intro, chapters from book_manifest, outro)
and creates one folder per item under output/youtube_uploads/b<N>/, e.g.
  output/youtube_uploads/b1/02_b1_00_pradzia/
containing:
  - <key>.mp4            (cover image + waveform overlay, reused if already rendered)
  - description.txt      (YouTube description for the Geležinio Vilko Saga project)

Order, keys, WAV names and chapter titles all come from audiobook/book_manifest.py.
Items whose WAV has not been generated yet are skipped with a message.

Usage:
  python3 audiobook/generate_chapter_videos.py            # book 1
  python3 audiobook/generate_chapter_videos.py --book 2
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple

from tqdm import tqdm

AUDIOBOOK_DIR = Path(__file__).resolve().parent
if str(AUDIOBOOK_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIOBOOK_DIR))

import book_manifest as bm  # noqa: E402

OUTPUT_DIR = bm.OUTPUT_DIR
UPLOADS_DIR = OUTPUT_DIR / "youtube_uploads"


def default_cover_image(book):
    """This saga's cover for one book: books/<N>/cover.png."""
    return bm.BOOKS_DIR / str(book) / "cover.png"

SERIES_TITLE = "Geležinio Vilko Saga"
BOOK_TITLE = "I knyga: Vilko Tremtis"
WEB_EDITION_URL = "https://Algiras.github.io/wolf-saga/"
REPO_URL = "https://github.com/Algiras/wolf-saga"
LICENCE_LINE = (
    "Licensed under CC BY-NC-SA 4.0 "
    "(Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International)."
)
AUTHOR_LINE = "© Algimantas Krasauskas."
TTS_LINE = "Narrated with AI text-to-speech."
TAGS = "#Audiobook #WolfSaga #GeležinioVilkoSaga #Fantasy #Lithuania"


class UploadItem(NamedTuple):
    folder: str   # folder name under youtube_uploads/b<N>/
    wav: Path     # narrated audio to render
    title: str    # title used in the description


def build_upload_plan(book):
    """Intro, then every chapter in manifest order, then outro, for one book."""
    manifest_entries = {e["key"]: e for e in bm.load_manifest(book)}

    plan = [UploadItem(
        folder=f"00_b{book}_intro",
        wav=OUTPUT_DIR / bm.intro_wav_name(book),
        title="Intro",
    )]
    for chapter in bm.discover_chapters(book):
        key = chapter["key"]
        title = manifest_entries.get(key, {}).get("title") or chapter["title"]
        plan.append(UploadItem(
            folder=f"{chapter['order']:02d}_{key}",
            wav=bm.audio_path(key),
            title=title,
        ))
    plan.append(UploadItem(
        folder=f"99_b{book}_outro",
        wav=OUTPUT_DIR / bm.outro_wav_name(book),
        title="Outro",
    ))
    return plan


def build_description(chapter_title):
    """YouTube description for one chapter."""
    return (
        f"🎧 {SERIES_TITLE} — {BOOK_TITLE}\n"
        f"📖 Chapter: {chapter_title}\n"
        "\n"
        f'Part of "{SERIES_TITLE}" (The Iron Wolf Saga), a Lithuanian fantasy series '
        "by Algimantas Krasauskas.\n"
        f"{TTS_LINE}\n"
        "\n"
        "---\n"
        f"🌐 Web edition: {WEB_EDITION_URL}\n"
        f"💻 Source and project: {REPO_URL}\n"
        "\n"
        "---\n"
        f"⚖️ {AUTHOR_LINE} {LICENCE_LINE}\n"
        "\n"
        f"📌 TAGS: {TAGS}\n"
    )


def create_video_with_metadata(audio_path, image_path, chapter_dir, chapter_title):
    """Create video and description file in the chapter directory."""
    video_path = chapter_dir / f"{audio_path.stem}.mp4"
    desc_path = chapter_dir / "description.txt"
    old_video_path = OUTPUT_DIR / "chapter_videos" / f"{audio_path.stem}.mp4"

    # 1. Description
    desc_path.write_text(build_description(chapter_title), encoding="utf-8")

    # 2. Video
    if not video_path.exists():
        # Reuse an older render if one exists
        if old_video_path.exists():
            print(f"📦 Moving existing video: {old_video_path.name}")
            shutil.move(str(old_video_path), str(video_path))
            return True

        # Otherwise render it
        filter_complex = (
            "[1:a]showwaves=s=1920x150:mode=cline:colors=white:scale=sqrt:draw=full,"
            "format=yuva420p,colorchannelmixer=aa=0.8[wave];"
            "[0:v][wave]overlay=0:H-150:shortest=1[outv]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(video_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FFmpeg failed for {audio_path.name}: {e.stderr.decode(errors='replace')}")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Build YouTube upload folders for one book.")
    parser.add_argument("--book", type=int, default=1, help="book number (default: 1)")
    parser.add_argument("--image", type=Path, default=None,
                        help="background image (default: books/<N>/cover.png)")
    args = parser.parse_args()

    cover_image = args.image or default_cover_image(args.book)
    if not cover_image.exists():
        print(f"❌ Cover image not found: {cover_image}")
        return

    plan = build_upload_plan(args.book)
    ready = []
    for item in plan:
        if item.wav.exists():
            ready.append(item)
        else:
            print(f"⏭  Skipping {item.folder}: {item.wav.name} not generated yet")

    book_uploads = UPLOADS_DIR / f"b{args.book}"
    book_uploads.mkdir(parents=True, exist_ok=True)

    print(f"🎬 Book {args.book}: {len(ready)} of {len(plan)} items have audio; "
          f"building folders in {book_uploads}.")

    for item in tqdm(ready, desc="Batch Processing Chapters"):
        chapter_dir = book_uploads / item.folder
        chapter_dir.mkdir(parents=True, exist_ok=True)
        create_video_with_metadata(item.wav, cover_image, chapter_dir, item.title)

    print(f"\n✅ All uploads ready in: {book_uploads}")


if __name__ == "__main__":
    main()
