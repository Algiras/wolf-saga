#!/usr/bin/env python3
"""Write books/N/_quarto.yml for the later books from the chapter files on disk.

    python3 scripts/gen_book_quarto.py 4 5

Chapters are books/N/NN_slug.qmd; parts are chapters 1-10, 11-20 and 21-30.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = {
    4: dict(sub="IV Knyga: Nematoma Karūna", parts=["Krikštas be Ugnies", "Nuo Jūros iki Jūros", "Nematoma Karūna"],
            desc="Epinis tamsiosios fantastikos pasakojimas apie Žemaitijos krikštą, Vytauto imperiją ir sulaikytą karūną (1411–1430)."),
    5: dict(sub="V Knyga: Vilko Palikimas", parts=["Tuštuma", "Brolis prieš Brolį", "Vaiduoklių Amžius"],
            desc="Epinis tamsiosios fantastikos pasakojimas apie Paskutinės Liepsnos užgesimą, pilietinį karą ir paskutinį vilką (1430–1450)."),
}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
NAV = [("I knyga", "../"), ("II knyga", "../2/"), ("III knyga", "../3/"), ("IV knyga", "../4/"),
       ("V knyga", "../5/"), ("VI knyga (priešistorė)", "../6/"), ("Wiki", "../wiki/")]

FORMAT = """format:
  html:
    theme:
      - cosmo
  pdf:
    documentclass: scrreprt
    number-sections: false
    sec-num-depth: 0
    toc: true
    pdf-engine: lualatex
    mainfont: "DejaVu Serif"
    monofont: "DejaVu Sans Mono"
    header-includes: |
      \\usepackage{{fontspec}}
      \\renewcommand{{\\partformat}}{{}}
      \\renewcommand{{\\chapterformat}}{{}}
  epub:
    cover-image: cover.jpg
    title: "Geležinio Vilko Saga {roman}: {title}"
    author: "Algimantas Krasauskas"
    description: "{desc}"
"""


def build(n):
    cfg, d = BOOKS[n], ROOT / "books" / str(n)
    chapters = sorted(p.name for p in d.glob("[0-3][0-9]_*.qmd"))
    nums = [int(c[:2]) for c in chapters]
    missing = sorted(set(range(1, 31)) - set(nums))
    dupes = sorted({x for x in nums if nums.count(x) > 1})
    if dupes:
        raise SystemExit(f"book {n}: duplicate chapter numbers {dupes}")
    out = ["project:", "  type: book", "", "lang: lt", "", "book:", '  title: "Geležinio Vilko Saga"',
           f'  subtitle: "{cfg["sub"]}"', '  author: "Algimantas Krasauskas"', f"  output-file: saga-{n}",
           '  date: "10/12/2026"', "  cover-image: cover.jpg", "  navbar:", "    right:"]
    for text, href in NAV:
        out += [f'      - text: "{text}"', f"        href: {'index.html' if href == f'../{n}/' else href}"]
    out += ["  chapters:", "    - index.qmd"]
    for i, part in enumerate(cfg["parts"]):
        out += [f'    - part: "{part}"', "      chapters:"]
        out += [f"        - {c}" for c in chapters if i * 10 < int(c[:2]) <= (i + 1) * 10]
    out += ["    - copyright.qmd", ""]
    title = cfg["sub"].split(": ", 1)[1]
    (d / "_quarto.yml").write_text("\n".join(out) + FORMAT.format(roman=ROMAN[n], title=title, desc=cfg["desc"]),
                                   encoding="utf-8")
    print(f"book {n}: {len(chapters)} chapters" + (f", MISSING {missing}" if missing else ""))


if __name__ == "__main__":
    for a in sys.argv[1:] or ["4", "5"]:
        build(int(a))
