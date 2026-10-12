#!/usr/bin/env python3
"""Lint the wiki's Markdown sources and verify the rendered site.

    python3 scripts/check_wiki.py            # sources + rendered site (wiki/_site)
    python3 scripts/check_wiki.py --source   # sources only (no render needed)
    python3 scripts/check_wiki.py --strict   # warnings fail too

Source checks (wiki/**/*.qmd): front matter with a title, entity pages keep their generated
include, balanced bold/shortcodes/fenced divs/HTML comments, relative links and images resolve.
Warnings: sections left empty (only the template's guidance comment).
Rendered checks (wiki/_site/**/*.html): every page has an <h1>, no raw Markdown leaked into
visible text (**, ](, {{<, :::, #-headings), internal links and images resolve.
Exits 1 on any error. Stdlib only, so it runs as-is in CI.
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
SITE = WIKI / "_site"
SKIP_DIRS = {"_site", "_templates", "_generated", ".quarto", "images", "styles"}
ENTITY_DIRS = {"artifacts", "books", "characters", "creatures", "events", "factions", "forces",
               "gods", "houses", "magic", "places"}

errors: list[str] = []
warnings: list[str] = []


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def source_files():
    for p in sorted(WIKI.rglob("*.qmd")):
        if not SKIP_DIRS.intersection(p.relative_to(WIKI).parts):
            yield p


def check_source(p: Path):
    text = p.read_text(encoding="utf-8")
    where = rel(p)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        errors.append(f"{where}: missing YAML front matter")
        return
    if not re.search(r"^title:\s*\S", m.group(1), re.M):
        errors.append(f"{where}: front matter has no title")
    body = text[m.end():]
    section = p.relative_to(WIKI).parts[0]
    if section in ENTITY_DIRS and p.name != "index.qmd" and "{{< include ../_generated/" not in body:
        errors.append(f"{where}: entity page lost its generated include (infobox)")

    # balance checks on prose (ignore code fences and comments)
    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    if prose.count("<!--") != prose.count("-->"):
        errors.append(f"{where}: unclosed HTML comment")
    prose = re.sub(r"<!--.*?-->", "", prose, flags=re.S)
    if prose.count("{{<") != prose.count(">}}"):
        errors.append(f"{where}: unbalanced shortcode {{< >}}")
    opens = len(re.findall(r"^:::+\s*\{", prose, re.M))
    closes = len(re.findall(r"^:::+\s*$", prose, re.M))
    if opens != closes:
        errors.append(f"{where}: unbalanced fenced div (::: {{...}} vs :::), {opens} open / {closes} close")
    for n, line in enumerate(prose.splitlines(), 1):
        if line.lstrip().startswith(("|", "<")):
            continue  # tables and raw HTML are checked after rendering
        if line.count("**") % 2:
            warnings.append(f"{where}: odd number of ** on a line: {line.strip()[:70]}")

    # empty sections: a heading whose body holds only a guidance comment / whitespace
    # (a heading followed directly by a deeper subheading is a parent, not empty)
    parts = re.split(r"^(#{2,6} .+)$", body, flags=re.M)
    heads = parts[1::2]
    for i, (heading, content) in enumerate(zip(heads, parts[2::2])):
        if re.sub(r"<!--.*?-->", "", content, flags=re.S).strip():
            continue
        level = len(heading) - len(heading.lstrip("#"))
        nxt = heads[i + 1] if i + 1 < len(heads) else None
        if nxt and len(nxt) - len(nxt.lstrip("#")) > level:
            continue
        warnings.append(f"{where}: empty section '{heading.strip()}'")

    # relative links and images
    for target in re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", prose):
        u = urlparse(target)
        if u.scheme or target.startswith(("#", "mailto:")):
            continue
        path = unquote(u.path)
        if not path or path.startswith("/"):
            continue
        dest = (p.parent / path).resolve()
        if ROOT / "wiki" not in dest.parents and dest.parent != WIKI:
            continue  # links to the books (../index.html, ../2/) live outside the wiki project
        if not dest.exists():
            errors.append(f"{where}: broken link → {target}")


class Page(HTMLParser):
    SKIP = {"script", "style", "code", "pre", "svg", "math", "textarea"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.text: list[str] = []
        self.refs: list[tuple[str, str]] = []
        self.h1 = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        if tag == "h1":
            self.h1 = True
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.refs.append(("link", a["href"]))
        if tag == "img" and a.get("src"):
            self.refs.append(("image", a["src"]))

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.text.append(data)


LEAKS = [
    (re.compile(r"\*\*\S[^*]{0,80}\*\*"), "raw **bold**"),
    (re.compile(r"\]\((?:\.\./|https?://|[\w-]+\.qmd)"), "raw Markdown link ]("),
    (re.compile(r"\{\{<"), "unrendered shortcode {{<"),
    (re.compile(r"(?m)^\s*:::"), "unrendered fenced div :::"),
    (re.compile(r"(?m)^\s*#{2,4} \w"), "unrendered heading ##"),
    (re.compile(r"\|\s*(?:-{3,}|[—–]+)\s*\|"), "unrendered table (|---| row)"),
    (re.compile(r"(?:^|\s)[*+-] {2,}\S"), "unrendered list item (*   …)"),
]


def check_rendered():
    pages = sorted(SITE.rglob("*.html"))
    if not pages:
        errors.append("wiki/_site has no HTML: run `quarto render wiki` first (or use --source)")
        return
    for p in pages:
        if p.name == "graph-explorer.html" or "site_libs" in p.parts:
            continue
        where = rel(p)
        parser = Page()
        parser.feed(p.read_text(encoding="utf-8", errors="replace"))
        if not parser.h1 and p.name != "404.html":
            warnings.append(f"{where}: no <h1> title")
        visible = "\n".join(parser.text)
        for rx, what in LEAKS:
            hit = rx.search(visible)
            if hit:
                errors.append(f"{where}: {what} leaked into page text: …{visible[max(0, hit.start()-30):hit.end()+30].strip()!r}…")
        for kind, ref in parser.refs:
            u = urlparse(ref)
            if u.scheme or ref.startswith(("#", "mailto:", "data:", "javascript:")):
                continue
            path = unquote(u.path)
            if not path:
                continue
            dest = (p.parent / path).resolve()
            if SITE not in dest.parents and dest != SITE:
                continue  # ../ links to the books, outside the wiki site
            if dest.is_dir():
                dest = dest / "index.html"
            if not dest.exists():
                errors.append(f"{where}: broken {kind} → {ref}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="store_true", help="only lint the .qmd sources")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--quiet-warnings", action="store_true", help="print only the warning count")
    args = ap.parse_args()
    files = list(source_files())
    for p in files:
        check_source(p)
    if not args.source:
        check_rendered()
    if warnings and not args.quiet_warnings:
        print(f"{len(warnings)} warning(s):")
        for w in warnings:
            print("  warn ", w)
    for e in errors:
        print("  ERROR", e)
    print(f"checked {len(files)} source pages" + ("" if args.source else " + rendered site")
          + f": {len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors or (args.strict and warnings) else 0)


if __name__ == "__main__":
    main()
