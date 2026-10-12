#!/usr/bin/env python3
"""Post-render clean-up for the store e-book (saga-N-store.epub).

Quarto/pandoc build the EPUB; this script fixes what they leave out. It is wired in as a Quarto
`project: post-render` script in each books/N/_quarto-store.yml, and can also be run by hand:

    python3 scripts/polish_epub.py books/6/_book/saga-6-store.epub [more.epub ...]

What it does (in place, idempotent):
  * removes the inline <style> blocks Quarto injects into every page (callout CSS etc.), so the
    book is styled only by styles/stylesheet1.css (built from books/_extensions/saga-store/ebook.css);
  * gives each chapter file a real <title> instead of "ch007.xhtml";
  * sets <body epub:type> to frontmatter / bodymatter / backmatter by position in the book;
  * rebuilds the nav "landmarks" list: cover, titlepage, toc (the inline contents page), bodymatter
    (first story chapter or part) and backmatter (afterword);
  * drops the date, publisher and rights lines from the title page (the copyright page carries them).

Standard library only.
"""
from __future__ import annotations

import html
import os
import re
import sys
import zipfile
from pathlib import Path

LABELS = {
    "lt": {"cover": "Viršelis", "titlepage": "Titulinis puslapis", "toc": "Turinys",
           "bodymatter": "Knygos pradžia", "backmatter": "Pabaigos žodis"},
    "en": {"cover": "Cover", "titlepage": "Title page", "toc": "Contents",
           "bodymatter": "Start of the story", "backmatter": "Afterword"},
}


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _opf_path(files: dict[str, bytes]) -> str:
    m = re.search(rb'full-path="([^"]+)"', files["META-INF/container.xml"])
    return m.group(1).decode()


def _spine_files(opf: str, base: str) -> list[str]:
    manifest = {m.group(1): m.group(2) for m in re.finditer(r'<item\b[^>]*?\bid="([^"]+)"[^>]*?\bhref="([^"]+)"', opf)}
    manifest.update({m.group(2): m.group(1) for m in re.finditer(r'<item\b[^>]*?\bhref="([^"]+)"[^>]*?\bid="([^"]+)"', opf)
                     if m.group(2) not in manifest})
    out = []
    for m in re.finditer(r'<itemref\b[^>]*?\bidref="([^"]+)"', opf):
        href = manifest.get(m.group(1))
        if href:
            out.append(os.path.normpath(os.path.join(base, href)))
    return out


def polish(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        files = {i.filename: z.read(i.filename) for i in infos}
    order = [i.filename for i in infos]

    opf_name = _opf_path(files)
    base = os.path.dirname(opf_name)
    opf = files[opf_name].decode("utf-8")
    lang = (re.search(r'xml:lang="([a-z]+)', opf) or re.search(r"<dc:language>([a-z]+)", opf)).group(1)
    lab = LABELS.get(lang, LABELS["en"])
    spine = _spine_files(opf, base)
    nav_name = next(n for n in files if n.endswith("nav.xhtml"))

    # 1. strip inline styles, 2. real titles, 3. drop the title page date
    for name in list(files):
        if not name.endswith(".xhtml"):
            continue
        s = files[name].decode("utf-8")
        s = re.sub(r"\s*<style\b[^>]*>.*?</style>", "", s, flags=re.S)
        if "/text/ch" in name or os.path.basename(name).startswith("ch"):
            m = re.search(r"<h[12]\b[^>]*>(.*?)</h[12]>", s, flags=re.S)
            if m:
                s = re.sub(r"<title>.*?</title>", lambda _: f"<title>{html.escape(_strip_tags(m.group(1)), quote=False)}</title>", s, count=1, flags=re.S)
        if name.endswith("title_page.xhtml"):
            s = re.sub(r'\s*<p class="date">.*?</p>', "", s, flags=re.S)
            s = re.sub(r'\s*<p class="publisher">.*?</p>', "", s, flags=re.S)
            s = re.sub(r'\s*<div class="rights">.*?</div>', "", s, flags=re.S)
        files[name] = s.encode("utf-8")

    # 4. body epub:type by position
    chapters = [n for n in spine if re.search(r"/ch\d+\.xhtml$", n)]
    started = False
    ended = False
    first_body = first_back = toc_file = None
    for name in chapters:
        s = files[name].decode("utf-8")
        sec = re.search(r"<section\b[^>]*\bclass=\"([^\"]*)\"", s)
        classes = (sec.group(1) if sec else "").split()
        if "toc-page" in classes:
            toc_file = name
        is_part = "part" in classes
        if "copyright-page" in classes or "toc-page" in classes:
            kind = "frontmatter"
        elif not started and "unnumbered" in classes and not is_part:
            kind = "frontmatter"
        else:
            if not started:
                started = True
                first_body = name
            if started and "unnumbered" in classes and not is_part:
                ended = True
                if first_back is None:
                    first_back = name
            kind = "backmatter" if ended else "bodymatter"
        s = re.sub(r"<body\b[^>]*>", f'<body epub:type="{kind}">', s, count=1)
        files[name] = s.encode("utf-8")

    # 5. landmarks
    def rel(target: str, anchor: str = "") -> str:
        return os.path.relpath(target, os.path.dirname(nav_name)).replace(os.sep, "/") + anchor

    cover = next((n for n in files if n.endswith("cover.xhtml")), None)
    title = next((n for n in files if n.endswith("title_page.xhtml")), None)
    entries = []
    if cover:
        entries.append(("cover", rel(cover), lab["cover"]))
    if title:
        entries.append(("titlepage", rel(title), lab["titlepage"]))
    if toc_file:
        entries.append(("toc", rel(toc_file), lab["toc"]))
    if first_body:
        entries.append(("bodymatter", rel(first_body), lab["bodymatter"]))
    if first_back:
        entries.append(("backmatter", rel(first_back), lab["backmatter"]))
    li = "\n".join(f'    <li>\n      <a href="{href}" epub:type="{t}">{html.escape(text)}</a>\n    </li>' for t, href, text in entries)
    block = f'<nav epub:type="landmarks" id="landmarks" hidden="hidden">\n  <ol>\n{li}\n  </ol>\n</nav>'
    nav = files[nav_name].decode("utf-8")
    if "epub:type=\"landmarks\"" in nav:
        nav = re.sub(r'<nav\b[^>]*epub:type="landmarks".*?</nav>', lambda _: block, nav, flags=re.S)
    else:
        nav = nav.replace("</body>", block + "\n</body>")
    files[nav_name] = nav.encode("utf-8")

    # write back: mimetype first and stored, everything else deflated
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr("mimetype", files["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name in order:
            if name != "mimetype":
                z.writestr(name, files[name], compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(path)
    print(f"polished {path} ({len(chapters)} text files, landmarks: {', '.join(t for t, _, _ in entries)})")


def main(argv: list[str]) -> None:
    targets = [Path(a) for a in argv]
    if not targets:  # called by Quarto's post-render hook
        for line in os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "").splitlines():
            if line.strip().endswith("-store.epub"):
                targets.append(Path(line.strip()))
    for t in targets:
        if t.exists():
            polish(t)


if __name__ == "__main__":
    main(sys.argv[1:])
