#!/usr/bin/env python3
"""Generate textless cover art for each book with the Gemini / Imagen image API.

Prompts live in books/covers/covers.yml (fields: art_prompt, art_negative,
art_file, art_wide_file). Candidates are written to books/covers/art/candidates/
so the author can choose; `--select` copies the chosen candidate into place.
Typography is added afterwards by scripts/make_covers.py, never by the model:
image models garble Lithuanian diacritics.

Usage:
    python3 scripts/generate_cover_art.py --dry-run                  # print prompts, no API calls
    python3 scripts/generate_cover_art.py --book 3 --n 4             # 4 portrait + 4 wide candidates
    python3 scripts/generate_cover_art.py --book 3 --only portrait
    python3 scripts/generate_cover_art.py --select 3 portrait 2      # use candidate v2 as books/covers/art/book3.png

API key: GEMINI_API_KEY or GOOGLE_API_KEY from the environment, or from a
git-ignored .env file in the repo root or audiobook/ (KEY=value lines).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "books" / "covers" / "covers.yml"
CANDIDATES = ROOT / "books" / "covers" / "art" / "candidates"

# Imagen supports 1:1, 3:4, 4:3, 9:16, 16:9. Portrait art is generated at 3:4 and
# cover-cropped to 2:3 by make_covers.py; wide art feeds video backgrounds/thumbnails.
ASPECT = {"portrait": "3:4", "wide": "16:9"}
DEFAULT_MODEL = "imagen-4.0-generate-001"
STYLE_GUARD = (
    " Painterly dark-realist book-cover illustration, cinematic lighting, "
    "historically grounded late-14th-century Lithuania. Leave calm negative space "
    "in the upper third and lower quarter for title typography."
)


def load_key() -> str | None:
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_file in (ROOT / ".env", ROOT / "audiobook" / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and value.strip():
                return value.strip().strip('"').strip("'")
    return None


def load_books() -> dict[int, dict]:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    books = data.get("books", data)
    out = {}
    for key, cfg in (books.items() if isinstance(books, dict) else enumerate(books, 1)):
        num = int(cfg.get("number", key) if isinstance(cfg, dict) else key)
        out[num] = cfg
    return out


def full_prompt(cfg: dict, kind: str = "portrait") -> str:
    base = cfg.get("art_wide_prompt") if kind == "wide" and cfg.get("art_wide_prompt") else cfg["art_prompt"]
    prompt = base.strip() + STYLE_GUARD
    negative = cfg.get("art_negative")
    if negative:
        # Imagen 4 has no negative-prompt parameter; state exclusions in the prompt.
        prompt += f" Strictly avoid: {negative.strip().rstrip('.')}."
    return prompt


def generate(book: int, cfg: dict, kinds: list[str], n: int, model: str, key: str) -> list[Path]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    written = []
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        print(f"Book {book} · {kind} ({ASPECT[kind]}) · {n} candidate(s) via {model} …")
        resp = client.models.generate_images(
            model=model,
            prompt=full_prompt(cfg, kind),
            config=types.GenerateImagesConfig(
                number_of_images=n,
                aspect_ratio=ASPECT[kind],
                person_generation="allow_adult",
            ),
        )
        images = getattr(resp, "generated_images", None) or []
        if not images:
            print(f"  ✗ no images returned (filtered or refused). Adjust the prompt for book {book}.")
            continue
        for i, gen in enumerate(images, 1):
            path = CANDIDATES / f"book{book}_{kind}_v{i}.png"
            path.write_bytes(gen.image.image_bytes)
            written.append(path)
            print(f"  ✓ {path.relative_to(ROOT)}")
    return written


def select(book: int, kind: str, version: int, books: dict[int, dict]) -> None:
    cfg = books[book]
    src = CANDIDATES / f"book{book}_{kind}_v{version}.png"
    if not src.exists():
        sys.exit(f"Candidate not found: {src.relative_to(ROOT)}")
    dest = ROOT / cfg["art_file" if kind == "portrait" else "art_wide_file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    print(f"Selected {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}. Now run: python3 scripts/make_covers.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", type=int, action="append", help="book number (repeatable; default: all)")
    ap.add_argument("--n", type=int, default=3, help="candidates per kind (1–4)")
    ap.add_argument("--only", choices=["portrait", "wide"], help="generate only one kind")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dry-run", action="store_true", help="print prompts; make no API calls")
    ap.add_argument("--select", nargs=3, metavar=("BOOK", "KIND", "VERSION"), help="copy a candidate into place")
    args = ap.parse_args()

    books = load_books()
    if args.select:
        b, kind, v = args.select
        select(int(b), kind, int(v), books)
        return

    targets = args.book or sorted(books)
    kinds = [args.only] if args.only else ["portrait", "wide"]
    if args.dry_run:
        for b in targets:
            for kind in kinds:
                print(f"\n=== Book {b} · {kind} ===\n{full_prompt(books[b], kind)}")
        return

    key = load_key()
    if not key:
        sys.exit("No GEMINI_API_KEY/GOOGLE_API_KEY found. Export it, or add it to a git-ignored .env in the repo root.")
    total = []
    for b in targets:
        total += generate(b, books[b], kinds, max(1, min(args.n, 4)), args.model, key)
    print(f"\n{len(total)} candidate image(s) in {CANDIDATES.relative_to(ROOT)}. Pick with --select BOOK KIND VERSION.")


if __name__ == "__main__":
    main()
