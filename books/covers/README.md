# Covers: Geležinio Vilko Saga

One typography system for all six books, composited onto textless art by `scripts/make_covers.py`. Everything is driven by `books/covers/covers.yml`.

## Layout

```
books/covers/
  covers.yml        per-book config: titles lt/en, years, author, colour key, art paths, art prompts
  art_prompts.md    human-readable art prompts, historical cautions, aspect ratios
  art/              DROP ART HERE (bookN.png and bookN_wide.png)
  fonts/            Grenze Gotisch (display) + Cormorant SC (secondary), with their OFL licences
  out/bookN/        generated: front_ebook_1600x2560.png, front_square_3000.png,
                    video_bg_1920x1080.png, thumb_1280x720.png, thumbs/chNN_*.png
  out/contact_sheet.png, out/contact_sheet_wide.png
```

## 1. Make the art

Prompts are in `art_prompts.md` (readable) and in `covers.yml` (`art_prompt`, `art_wide_prompt`, `art_negative`; machine-readable). The art must be **textless**: the compositor adds all type.

- Portrait: 2:3, at least 2048 x 3072 px -> save as `books/covers/art/book1.png` ... `book6.png`
- Wide: 16:9, at least 3840 x 2160 px -> save as `books/covers/art/book1_wide.png` ... (optional; without it the portrait art is cropped for the video and thumbnails)
- Keep the top 14 percent and bottom 30 percent of the portrait calm; the title block lives there.
- Before accepting an image, check that it has no accidental lettering, and read the historical cautions in `art_prompts.md` for that book (e.g. Trakai's island castle was unfinished in 1382).

Until `art_file` exists, the compositor falls back to `interim_art` (Book I: `books/1/cover_art.png`; Book II: the textless top of `books/2_teaser.png`) and then to a generated placeholder marked "PLACEHOLDER ART". Dropping in real art replaces the fallback automatically.

## 2. Generate the covers

```bash
pip install pillow numpy pyyaml fonttools      # once
python3 scripts/make_covers.py all              # all books + contact sheets
python3 scripts/make_covers.py book 3           # one book
python3 scripts/make_covers.py --lang en all    # English titles (written to out/bookN/en/)
python3 scripts/make_covers.py check-fonts      # Lithuanian glyph-coverage check only
```

Every run first checks that each font contains `ĄČĘĖĮŠŲŪŽąčęėįšųūž` and aborts with an error if any glyph is missing, and again before drawing any string.

## 3. Per-part (chapter) thumbnails

```bash
python3 scripts/make_covers.py part --book 1 --number 3 --title "Gintaro Sapnas"
python3 scripts/make_covers.py chapters --book 1     # one per books/1/NN_*.qmd, title from its H1
```

Output: `out/book1/thumbs/ch03_gintaro_sapnas.png` (1280 x 720, big numeral + "SKYRIUS" + title). From Python: `make_covers.render_part_thumb(ctx, book_number, number, title)`.

## 4. KDP paperback wrap cover

```bash
python3 scripts/make_covers.py print 4 --pages 260 --paper cream   # or: print all  (page counts read from the print PDFs)
```

Output: `out/bookN/print_cover_kdp.pdf` (back | spine | front, 0.125 in bleed, 300 dpi), plus `_preview.jpg` and `_guides.jpg`.
The back-cover blurb comes from `books/book_meta.yml`. Details, spine formula and KDP settings: `docs/PRINTING.md`.

## Changing things

- Author and titles are config values (`series.author`, `title_lt`, `title_en`). Book II's title is an open author decision ("Auksinis Šešėlis" vs "Vytis ir Šešėlis"): edit `title_lt` in `covers.yml` and re-run.
- Colours: `colors: [darkest, mid, accent]` per book. The title colour is the same on every book (`series.title_color`); the accent colours the rules, years and book numeral.
- `focus: [x, y]` tells the compositor where the subject is when it crops art to another aspect ratio.
- Fonts are OFL (Google Fonts). Licences sit beside the font files.
