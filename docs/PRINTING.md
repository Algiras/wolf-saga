# Printing: KDP paperback interior and wrap cover

Each book has a print-ready interior (6 x 9 in trim, black and white, no bleed) and a wrap cover (back, spine, front,
0.125 in bleed). Both are built from the same repository state as the e-books. Amazon KDP does not accept Lithuanian
(see [PUBLISHING.md](PUBLISHING.md)), so these files serve the Lithuanian printers (section 5) now and an English
edition on KDP later; nothing in the template is Lithuanian-specific (the language comes from the project's `lang:`).

## 1. Build the interior

One shared definition, the Quarto format extension `books/_extensions/saga-print` (format `saga-print-pdf`, based on
`pdf`, LuaLaTeX, KOMA `scrbook`). Each book is its own Quarto project, so books 2 to 6 reach the extension through a
symlink `books/N/_extensions -> ../_extensions`; book 1 is the project in `books/` and uses it directly.

```bash
cd books      && quarto render --profile print --to saga-print-pdf --no-clean   # book 1 -> books/_book/saga-1-print.pdf
cd books/2    && quarto render --profile print --to saga-print-pdf --no-clean   # -> books/2/_book/saga-2-print.pdf
# ... likewise 3, 4, 5, 6
```

* The profile `books/N/_quarto-print.yml` holds only `book: output-file: saga-N-print` and the format. **Never put
  `chapters` in a profile**: Quarto merges the chapter lists. The profiles are generated:
  `python3 scripts/gen_book_quarto.py --profiles` (for books 4 and 5 `python3 scripts/gen_book_quarto.py 4 5` also
  rewrites their `_quarto.yml`).
* `--no-clean` keeps the html, pdf and epub already in `_book`. Without it Quarto empties the folder first.
* Needs Quarto 1.4 or newer and TeX Live with `scrlayer-scrpage`, `microtype` and `babel-lithuanian` (TinyTeX
  installs them on demand). **EB Garamond** (SIL OFL, Regular, Italic, Bold, Bold Italic) is bundled in
  `books/_extensions/saga-print/fonts`, so a local build and CI use the same font files; there is nothing to install.
  All fonts are embedded (check below).

What the template does: 6 x 9 in, two-sided, chapters open on a recto; margins inner 0.75 in, outer 0.6 in, top
0.7 in, bottom 0.8 in; EB Garamond 11 pt, line stretch 1.15, 1.25 em first-line indent; Lithuanian hyphenation,
microtype, no widows or orphans (clubpenalty and widowpenalty 10000), ragged bottom; running heads (book title on
the verso, chapter title on the recto, folios outside; plain footer folio on chapter-opening pages, no head);
chapter titles sunk to about one third of the page with an ornament; clean recto Part pages; front matter: half-title,
title page (series, book number, title, author), copyright verso (the licence text from `copyright.qmd`, moved from
the back or middle of the book), contents, foreword; story pages numbered in arabic starting at the first part or
chapter; back matter: the historical afterword and sources; hidden links (no coloured links); the web-only
"Skaitymo tvarka" page is left out; scene breaks (`---`, `* * *`) become a centred ornament; the file ends on a
verso so the page count is even. No images: the cover is not in the interior.

Checks after a build:

```bash
pdfinfo books/6/_book/saga-6-print.pdf     # Page size: 432 x 648 pts (6 x 9 in), Pages: even
pdffonts books/6/_book/saga-6-print.pdf    # every font: emb = yes
pdfimages -list books/6/_book/saga-6-print.pdf   # none
```

### Page counts and the gutter

Page counts of the last build (Oct 2026, all even, all in the 151 to 300 page row):

| Book | Pages | Spine (cream) | PDF |
|---|---|---|---|
| I. Vilko Tremtis | 152 (gutter 0.5 in required, 0.75 in used) | 0.380 in | `books/_book/saga-1-print.pdf` |
| II. Auksinis Šešėlis | 208 (gutter 0.5 in required, 0.75 in used) | 0.520 in | `books/2/_book/saga-2-print.pdf` |
| III. Žaliasis Miškas | 218 (gutter 0.5 in required, 0.75 in used) | 0.545 in | `books/3/_book/saga-3-print.pdf` |
| IV. Nematoma Karūna | 216 (gutter 0.5 in required, 0.75 in used) | 0.540 in | `books/4/_book/saga-4-print.pdf` |
| V. Vilko Palikimas | 226 (gutter 0.5 in required, 0.75 in used) | 0.565 in | `books/5/_book/saga-5-print.pdf` |
| VI. Šventasis Miškas | 200 (gutter 0.5 in required, 0.75 in used) | 0.500 in | `books/6/_book/saga-6-print.pdf` |

KDP's inside-margin (gutter) minimums (verified,
[KDP margins](https://kdp.amazon.com/en_US/help/topic/GVBQ3CMEQW3W2VL6)):

| Pages | Minimum inside margin (gutter) | Outside, top, bottom (no bleed) |
|---|---|---|
| 24 to 150 | 0.375 in | 0.25 in |
| 151 to 300 | 0.5 in | 0.25 in |
| 301 to 500 | 0.625 in | 0.25 in |
| 501 to 700 | 0.75 in | 0.25 in |
| 701 to 828 | 0.875 in | 0.25 in |

The interior uses an inside margin of 0.75 in, which satisfies every row up to 700 pages. If a book ever passes 700
pages, raise `inner` in `books/_extensions/saga-print/_extension.yml`.

## 2. Build the wrap cover

```bash
python3 scripts/make_covers.py print 4 --pages 260 --paper cream   # explicit page count
python3 scripts/make_covers.py print 4                              # page count read from books/4/_book/saga-4-print.pdf
python3 scripts/make_covers.py print all                            # all six
python3 scripts/make_covers.py --lang en print 4 --pages 260        # English title and blurb_en
```

Output in `books/covers/out/bookN/` (`.../bookN/en/` for English): `print_cover_kdp.pdf` (the file to upload),
`print_cover_kdp_preview.jpg` and `print_cover_kdp_guides.jpg` (red: trim and spine folds, green: the 0.25 in safe
zone). `books/covers/out/**` is git-ignored: regenerate rather than commit. Needs Pillow, numpy, PyYAML, fontTools;
PyMuPDF (`fitz`) is used when present to make the PDF page exactly 12.75 x 9.25 in rather than derived from pixels.

Geometry (all verified except the barcode box):

* **Spine width** = pages x 0.0025 in (cream) or x 0.002252 in (white), the black-and-white figures on KDP's cover
  page ([KDP cover help](https://kdp.amazon.com/en_US/help/topic/G201953020)). An odd page count is rounded up (KDP pads).
* **Full cover** = 0.125 + 6 + spine + 6 + 0.125 in wide by 9 + 2 x 0.125 = 9.25 in high, at 300 dpi
  (e.g. 200 pages cream: 12.75 x 9.25 in = 3826 x 2775 px).
* **Layout:** back cover left, spine, front right. The front is the existing cover art and type system re-set at
  6 x 9 in, bleed made by mirroring the edge pixels. The back carries the blurb (from `books/book_meta.yml`:
  `blurb_lt` or `blurb_en`), the series line, the title and the author over a darkened, blurred copy of the art.
* **Barcode:** a white 2 x 1.2 in box at the bottom right of the back, 0.25 in from the trim edges. KDP places the
  barcode there if the file does not contain one ("KDP places one on the back cover" if you supply none; verified).
  The 2 x 1.2 in size is the commonly used KDP template figure, **unverified** on the pages fetched.
* **Spine text** (series, title, author, rotated, reading top to bottom) only from 100 pages up (KDP's own minimum
  is 79 pages: spine text on a thinner book is rejected), with at least 0.0625 in clear of the spine edges
  (verified). Every typeset item is checked against the **0.25 in** safe zone (KDP asks for 0.125 in; the script
  stops with an error otherwise).
* **Fonts** are the series fonts plus EB Garamond for the blurb; `make_covers.py` runs its Lithuanian glyph check
  (ĄČĘĖĮŠŲŪŽąčęėįšųūž) on all of them.

Spine width depends on the exact page count KDP reports after you upload the interior. If KDP's count differs from the
PDF's, rebuild with `--pages` and use KDP's own cover calculator as the final word.

## 3. KDP upload settings (paperback)

| Setting | Value |
|---|---|
| Trim size | 6 x 9 in (15.24 x 22.86 cm) |
| Interior | Black ink, **cream** paper (spine factor 0.0025). White paper only if you change `--paper white`. |
| Bleed | **No bleed** for the interior (the interior has no images; bleed is only for fixed-format pages that print to the edge) |
| Cover | "Upload a print-ready PDF cover" = `print_cover_kdp.pdf` |
| Cover finish | Matte or glossy, your choice (KDP offers both; verified). Matte suits the dark art. |
| Manuscript | `saga-N-print.pdf` |
| ISBN | KDP's free ISBN (usable only through KDP) or your own |
| Pricing | See KDP's printing-cost calculator; a 200 to 230 page black-and-white book is cheap to print |

Risks to watch:

* **Colour mode.** KDP's cover page says images should be CMYK; `print_cover_kdp.pdf` is RGB (JPEG) at 300 dpi. KDP
  normally accepts RGB and converts, but colours (the amber and the oxblood) can shift slightly: order a proof copy.
* **Barcode placement** is KDP's; the white box is only a clear area.
* **Spine** can drift by a hair if KDP's page count differs from the PDF's.

## 4. CI

`.github/workflows/render.yml` renders each book's print PDF and store EPUB after the normal render, validates the
EPUBs with epubcheck, checks the PDFs (6 x 9 in, even page count, fonts embedded), and uploads
`saga-N-print.pdf` and `saga-N-store.epub` to the `latest` release with the other files. Covers are not built in CI: the art is
committed, the outputs are git-ignored, so run `make_covers.py print` locally once the page counts are final.

## 5. Lithuanian printers

The same PDF can go to a Lithuanian printer (see PUBLISHING.md, "Lietuvos rinka"). Send the interior PDF and a cover
file; most printers want the cover as its own wrap PDF with their spine width (ask them for it: their paper is not
KDP's, so recompute with `--pages` and the paper factor they give you). If a printer prefers A5, render the print
profile with a modified `geometry` (paperwidth 5.83 in, paperheight 8.27 in) in a copy of the extension.
