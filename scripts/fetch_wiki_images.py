#!/usr/bin/env python3
"""Fetch freely licensed stand-in images from Wikipedia / Wikimedia Commons for the saga wiki.

Usage:
    python3 scripts/fetch_wiki_images.py                    # every mapped entity that has no image yet
    python3 scripts/fetch_wiki_images.py --ids kestutis,vilnius
    python3 scripts/fetch_wiki_images.py --dry-run          # look up + license-check, write nothing
    python3 scripts/fetch_wiki_images.py --force            # re-fetch ids that already have a Commons image

Inputs / outputs:
    scripts/wiki_image_map.json   {id: {"wiki": "en:Vytautas" | "lt:...", "file": "File:..." (optional)}}
                                   "wiki" names the Wikipedia article whose lead image is used; "file" overrides it
                                   with an explicit Commons file (use it when the lead image is a poor choice).
    wiki/images/<id>.jpg          downscaled to <= 900 px on the long side, JPEG < 250 KB
    wiki/images/credits.json      {id: {title, page, artist, license, license_url, source}}  (read by build_wiki.py)

Rules:
  * Only Public domain, CC0, CC BY and CC BY-SA files are accepted (read from extmetadata LicenseShortName).
    Anything else (non-free, fair use, NC/ND, unknown) is skipped and reported.
  * AI-generated art (an image in wiki/images/ with no credits.json entry) is never overwritten, not even
    with --force. Only images this script created (listed in credits.json) can be refreshed.
  * Polite to Wikimedia: descriptive User-Agent, strictly sequential requests, a small delay between them.

Requires Pillow (pip install Pillow).
"""
from __future__ import annotations

import argparse
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "world_rules" / "graph" / "world_graph.json"
MAP = ROOT / "scripts" / "wiki_image_map.json"
IMAGES = ROOT / "wiki" / "images"
CREDITS = IMAGES / "credits.json"
IMAGE_EXTS = (".jpg", ".jpeg", ".webp", ".png")

UA = "wolf-saga-wiki/1.0 (https://github.com/Algiras/wolf-saga)"
DELAY = 0.7           # seconds between requests
MAX_SIDE = 900
MAX_BYTES = 250 * 1024
THUMB_WIDTH = 960     # a standard Wikimedia thumbnail step; Pillow shrinks it to MAX_SIDE


def http(url: str, *, binary: bool = False, tries: int = 4):
    """GET with the Wikimedia User-Agent, a politeness delay and backoff on 429/5xx."""
    for attempt in range(tries):
        time.sleep(DELAY)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                wait = int(e.headers.get("Retry-After", "0") or 0) or 5 * (attempt + 1)
                print(f"    HTTP {e.code}, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def api(host: str, **params) -> dict:
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    return http(f"https://{host}/w/api.php?" + urllib.parse.urlencode(params))


def lead_file(ref: str) -> tuple[str, str]:
    """'en:Vytautas' -> ('File:Vytautas.jpg', resolved article title) via the article's page image."""
    lang, title = ref.split(":", 1)
    d = api(f"{lang}.wikipedia.org", action="query", prop="pageimages", piprop="name", redirects="1", titles=title)
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or not pages[0].get("pageimage"):
        raise LookupError(f"no lead image for {ref}")
    return "File:" + pages[0]["pageimage"].replace("_", " "), pages[0]["title"]


def file_info(file_title: str) -> dict:
    d = api("commons.wikimedia.org", action="query", prop="imageinfo", titles=file_title,
            iiprop="url|extmetadata|size|mime", iiurlwidth=str(THUMB_WIDTH), iiextmetadatalanguage="en")
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "imageinfo" not in pages[0]:
        raise LookupError(f"{file_title} is not on Commons")
    return pages[0]["imageinfo"][0] | {"_title": pages[0]["title"]}


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def clean_artist(raw: str) -> str:
    a = strip_html(raw)
    a = re.sub(r"\(\s*(talk|page)\s*\)", "", a, flags=re.I).strip()
    a = re.sub(r"^This W3C-unspecified vector image was created with Inkscape by\s*", "", a)
    a = re.sub(r"\b(?:en|de|pl|lt|fr|ru|d):(?=\S)", "", a)             # wiki-link residue like "en:Jogaila"
    short = re.sub(r"\s+\(.*$", "", a)
    a = short if len(short) >= 6 else a                                # drop trailing "(1538-1614) ..."
    a = re.sub(r"^Anonymous\s+Unknown author$|^Unknown au[a-z]+$", "Unknown author", a, flags=re.I)
    # "Unknown authorUnknown author" style duplication
    half = len(a) // 2
    if half and a[:half].strip().lower() == a[half:].strip().lower():
        a = a[:half].strip()
    if len(a) > 70:
        a = a[:70].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return a or "Unknown author"


def license_ok(short: str) -> bool:
    s = short.strip().lower()
    if not s:
        return False
    if s.startswith(("public domain", "cc0", "pd ", "pd-", "pdm")):
        return True
    m = re.match(r"^cc[ -]by(?:[ -]sa)?[ -]\d(?:\.\d)?(?: [a-z]{2,3})?$", s)   # CC BY 4.0 / CC BY-SA 3.0 DE ...
    return bool(m) and "nc" not in s and "nd" not in s


def save_jpeg(raw: bytes, dest: Path) -> int:
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    data = b""
    for q in (88, 82, 76, 70, 64, 58, 50):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        data = buf.getvalue()
        if len(data) <= MAX_BYTES:
            break
    else:                                   # still too big: shrink further
        while len(data) > MAX_BYTES and max(im.size) > 400:
            im = im.resize((int(im.width * 0.85), int(im.height * 0.85)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=70, optimize=True, progressive=True)
            data = buf.getvalue()
    dest.write_bytes(data)
    return len(data)


def existing_image(i: str) -> Path | None:
    for ext in IMAGE_EXTS:
        if (IMAGES / f"{i}{ext}").is_file():
            return IMAGES / f"{i}{ext}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", help="comma-separated entity ids (default: every id in the map)")
    ap.add_argument("--force", action="store_true", help="re-fetch ids that already have a Commons-sourced image")
    ap.add_argument("--dry-run", action="store_true", help="look up and license-check only; write nothing")
    args = ap.parse_args()

    nodes = {n["id"] for n in json.loads(GRAPH.read_text(encoding="utf-8"))["nodes"]}
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    mapping = {k: v for k, v in mapping.items() if not k.startswith("_")}
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else list(mapping)

    ok, skipped, failed = [], [], []
    for i in ids:
        spec = mapping.get(i)
        if i not in nodes:
            print(f"- {i}: not a graph node, skipping")
            skipped.append((i, "not a graph node"))
            continue
        if not spec:
            print(f"- {i}: not in {MAP.name}, skipping")
            skipped.append((i, "not in map"))
            continue
        have = existing_image(i)
        if have and i not in credits:
            print(f"- {i}: has own (AI/hand-made) image {have.name}, never overwritten")
            skipped.append((i, "own image"))
            continue
        if have and not args.force:
            print(f"- {i}: already has {have.name}, skipping (use --force)")
            skipped.append((i, "exists"))
            continue
        try:
            file_title = spec.get("file")
            article = spec.get("wiki", "")
            if not file_title:
                file_title, article = lead_file(article)
            if not file_title.lower().startswith("file:"):
                file_title = "File:" + file_title
            info = file_info(file_title)
            meta = info.get("extmetadata", {})
            lic = (meta.get("LicenseShortName") or {}).get("value", "")
            if not license_ok(lic):
                print(f"- {i}: REJECTED {info['_title']} (license: {lic or 'unknown'})")
                failed.append((i, f"license {lic or 'unknown'}: {info['_title']}"))
                continue
            artist = spec.get("artist") or clean_artist((meta.get("Artist") or {}).get("value", ""))
            credit = {
                "title": re.sub(r"\.[A-Za-z0-9]+$", "", info["_title"].split(":", 1)[1]),
                "page": info["descriptionurl"],
                "artist": artist,
                "license": lic,
                "license_url": (meta.get("LicenseUrl") or {}).get("value", ""),
                "source": "wikimedia",
            }
            if args.dry_run:
                print(f"- {i}: OK (dry run) {info['_title']} | {artist} | {lic}")
                ok.append(i)
                continue
            raw = http(info.get("thumburl") or info["url"], binary=True)
            size = save_jpeg(raw, IMAGES / f"{i}.jpg")
            for ext in (".jpeg", ".webp", ".png"):          # keep exactly one image per id
                (IMAGES / f"{i}{ext}").unlink(missing_ok=True)
            credits[i] = credit
            CREDITS.write_text(json.dumps(dict(sorted(credits.items())), ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            print(f"- {i}: saved {size // 1024} KB <- {info['_title']} | {artist} | {lic}")
            ok.append(i)
        except Exception as e:                              # noqa: BLE001 - report and continue
            print(f"- {i}: FAILED {type(e).__name__}: {e}")
            failed.append((i, str(e)))

    print(f"\n{len(ok)} fetched, {len(skipped)} skipped, {len(failed)} failed")
    for i, why in failed:
        print(f"  failed {i}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
