#!/usr/bin/env python3
"""Cover compositor for "Geležinio Vilko Saga" (The Iron Wolf Saga).

Reads books/covers/covers.yml and composites ONE consistent typography system onto each
book's textless art (or a generated placeholder when the art is missing).

Outputs, per book, in books/covers/out/bookN/ (and bookN/en/ with --lang en):
    front_ebook_1600x2560.png   e-book front cover (5:8)
    front_square_3000.png       audiobook cover (1:1)
    video_bg_1920x1080.png      video background, title lower-left, quiet
    thumb_1280x720.png          thumbnail template (series line, title)
    (+ per-part thumbnails via `part` / `chapters`, e.g. thumbs/ch03_gintaro_sapnas.png)
and books/covers/out/contact_sheet.png (all e-book fronts side by side).

Usage (from the repository root):
    python3 scripts/make_covers.py all                  # every book + contact sheets
    python3 scripts/make_covers.py book 3               # one book
    python3 scripts/make_covers.py part --book 1 --number 3 --title "Gintaro Sapnas"
    python3 scripts/make_covers.py chapters --book 1    # a thumbnail per chapter file (H1 titles)
    python3 scripts/make_covers.py contact              # rebuild the contact sheets only
    python3 scripts/make_covers.py check-fonts          # Lithuanian glyph-coverage check only
    python3 scripts/make_covers.py print 4 --pages 260 --paper cream   # KDP 6x9 paperback wrap cover
    python3 scripts/make_covers.py print all            # all six, page counts read from the print PDFs
Add --lang en for the English-title variants (also for `print`: English title, blurb_en).

`print` writes books/covers/out/bookN/print_cover_kdp.pdf (+ _preview.jpg and a _guides.jpg showing trim,
spine, safe zone) at 300 dpi: 0.125 in bleed, back cover | spine | front, spine = pages x 0.0025 in (cream)
or 0.002252 in (white). The blurb comes from books/book_meta.yml. See docs/PRINTING.md.

Art lookup order for each format (see books/covers/README.md):
    video/thumbnail:  art_wide_file  ->  crop of art_file  ->  interim_art  ->  placeholder
    e-book/audiobook: art_file       ->  interim_art       ->  placeholder
Requires: Pillow, numpy, PyYAML, fontTools (all standard in this repo's environment).
"""
from __future__ import annotations

import argparse
import functools
import re
import sys
from pathlib import Path

import numpy as np
import yaml
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "books" / "covers" / "covers.yml"

# Every one of these must exist in every font we typeset with. Fails loudly otherwise.
LITHUANIAN_REQUIRED = "ĄČĘĖĮŠŲŪŽąčęėįšųūž"

SIZES = {
    "ebook": (1600, 2560),
    "print_front": (1800, 2700),   # 6 x 9 in trim at 300 dpi (front panel of the KDP wrap cover)
    "square": (3000, 3000),
    "video": (1920, 1080),
    "thumb": (1280, 720),
}
FILENAMES = {
    "ebook": "front_ebook_1600x2560.png",
    "square": "front_square_3000.png",
    "video": "video_bg_1920x1080.png",
    "thumb": "thumb_1280x720.png",
}


# --------------------------------------------------------------------------- config / fonts

def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def rpath(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else REPO / path


class Fonts:
    """Resolves the series' two typefaces and verifies glyph coverage."""

    def __init__(self, cfg: dict):
        fc = cfg["series"]["fonts"]
        self.paths = {
            "display": rpath(fc["display"]),
            "secondary": rpath(fc["secondary"]),
            "secondary_light": rpath(fc.get("secondary_light", fc["secondary"])),
        }
        for role in ("body", "body_italic"):   # optional: running text on the print wrap cover
            if fc.get(role):
                self.paths[role] = rpath(fc[role])
        self.weight = fc.get("display_weight", 700)
        self._cmaps: dict[Path, set[int]] = {}
        self.check_coverage()

    def cmap(self, role: str) -> set[int]:
        p = self.paths[role]
        if p not in self._cmaps:
            self._cmaps[p] = set(TTFont(str(p)).getBestCmap().keys())
        return self._cmaps[p]

    def check_coverage(self) -> None:
        problems = []
        for role, p in self.paths.items():
            if not p.exists():
                problems.append(f"{role}: font file not found: {p}")
                continue
            cm = self.cmap(role)
            missing = [ch for ch in LITHUANIAN_REQUIRED if ord(ch) not in cm]
            if missing:
                problems.append(f"{role} ({p.name}) is MISSING Lithuanian glyphs: {' '.join(missing)}")
        if problems:
            sys.exit("FONT COVERAGE CHECK FAILED\n  " + "\n  ".join(problems)
                     + f"\nRequired: {LITHUANIAN_REQUIRED}")

    def report(self) -> str:
        out = []
        for role, p in self.paths.items():
            out.append(f"  OK  {role:16s} {p.name}: all {len(LITHUANIAN_REQUIRED)} required glyphs "
                       f"({LITHUANIAN_REQUIRED}) present")
        return "\n".join(out)

    def ensure_text(self, role: str, text: str) -> None:
        cm = self.cmap(role)
        bad = sorted({c for c in text if not c.isspace() and ord(c) not in cm})
        if bad:
            sys.exit(f"FONT ERROR: {self.paths[role].name} cannot render {bad} in {text!r}")

    @functools.lru_cache(maxsize=256)
    def font(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        f = ImageFont.truetype(str(self.paths[role]), max(6, int(size)))
        if role == "display":
            try:
                f.set_variation_by_axes([self.weight])
            except Exception:  # static font: nothing to set
                pass
        return f


# --------------------------------------------------------------------------- colour helpers

def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def lerp_c(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# --------------------------------------------------------------------------- text engine

def measure(fonts: Fonts, role, size, text, tracking=0.0) -> float:
    f = fonts.font(role, size)
    if not tracking:
        return f.getlength(text)
    return sum(f.getlength(c) for c in text) + tracking * size * (len(text) - 1)


def fit_size(fonts: Fonts, role, text, max_w, max_size, min_size=10) -> int:
    ref = measure(fonts, role, 200, text)
    size = int(200 * max_w / ref) if ref else max_size
    return max(min_size, min(size, int(max_size)))


def _draw_run(draw, x, y, text, font, fill, tracking_px, **kw):
    if not tracking_px:
        draw.text((x, y), text, font=font, fill=fill, anchor="ls", **kw)
        return
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor="ls", **kw)
        x += font.getlength(ch) + tracking_px


def paint_text(img: Image.Image, fonts: Fonts, x, baseline, text, role, size, color,
               align="l", tracking=0.0, shadow=0.75, stroke=0, alpha=1.0, gradient_to=None,
               shadow_blur=None):
    """Draw text with a soft drop shadow (and optional dark outline) for legibility.
    x is the left edge / centre / right edge depending on `align`; baseline is the y of the baseline."""
    fonts.ensure_text(role, text)
    f = fonts.font(role, size)
    tpx = tracking * size
    w = measure(fonts, role, size, text, tracking)
    if align == "c":
        x0 = x - w / 2
    elif align == "r":
        x0 = x - w
    else:
        x0 = x
    asc, desc = f.getmetrics()
    blur = shadow_blur if shadow_blur is not None else max(2, int(size * 0.035))
    pad = int(blur * 3 + stroke + size * 0.15) + 4
    rw, rh = int(w + 2 * pad), int(asc + desc + 2 * pad)
    ox, oy = int(round(x0)) - pad, int(round(baseline)) - asc - pad
    bx, by = pad + (x0 - int(round(x0))), pad + asc

    fill_mask = Image.new("L", (rw, rh), 0)
    _draw_run(ImageDraw.Draw(fill_mask), bx, by, text, f, 255, tpx)
    if alpha < 1.0:
        fill_mask = fill_mask.point(lambda v: int(v * alpha))

    if shadow > 0:
        sh = Image.new("L", (rw, rh), 0)
        _draw_run(ImageDraw.Draw(sh), bx, by, text, f, 255, tpx, stroke_width=stroke, stroke_fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(min(255, v * 1.5 * shadow)))
        dx, dy = int(blur * 0.25), int(blur * 0.6)
        img.paste((0, 0, 0), (ox + dx, oy + dy, ox + dx + rw, oy + dy + rh), sh)
    if stroke:
        ol = Image.new("L", (rw, rh), 0)
        _draw_run(ImageDraw.Draw(ol), bx, by, text, f, 255, tpx, stroke_width=stroke, stroke_fill=255)
        img.paste((6, 6, 8), (ox, oy, ox + rw, oy + rh), ol.point(lambda v: int(v * 0.8)))
    if gradient_to is not None:
        top = Image.new("RGB", (rw, rh), color)
        bot = Image.new("RGB", (rw, rh), gradient_to)
        g = np.linspace(0, 1, rh)[:, None].repeat(rw, axis=1)
        # gradient spans cap-height region only
        t = np.clip((np.arange(rh)[:, None] - (by - asc * 0.85)) / max(1, asc * 0.85), 0, 1) * np.ones((1, rw))
        layer = Image.composite(bot, top, Image.fromarray((t * 255).astype("uint8")))
        img.paste(layer, (ox, oy, ox + rw, oy + rh), fill_mask)
    else:
        img.paste(color, (ox, oy, ox + rw, oy + rh), fill_mask)
    return w


def flank(img: Image.Image, x_in, sgn, length, y, color, thick, d):
    """Thin rule running away from the text (sgn = -1 left, +1 right), ending in a small diamond:
    the saga's one ornament."""
    dr = ImageDraw.Draw(img)
    x_out = x_in + sgn * length
    dr.line([(x_in, y), (x_out, y)], fill=color, width=max(1, int(round(thick))))
    dr.polygon([(x_out - d, y), (x_out, y - d), (x_out + d, y), (x_out, y + d)], fill=color)


# --------------------------------------------------------------------------- art sources

class ArtSource:
    def __init__(self, image: Image.Image | None, kind: str, label: str):
        self.image, self.kind, self.label = image, kind, label  # kind: real | interim | placeholder

    @property
    def is_placeholder(self):
        return self.image is None


def _open(path: Path, crop=None) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(tuple(crop))
    return im


def pick_art(book: dict, wide: bool) -> ArtSource:
    """Choose the best available art for a format. See module docstring for the lookup order."""
    art = rpath(book["art_file"])
    art_wide = rpath(book["art_wide_file"]) if book.get("art_wide_file") else None
    if wide and art_wide and art_wide.exists():
        return ArtSource(_open(art_wide), "real", f"{art_wide.name} (wide art)")
    if art.exists():
        return ArtSource(_open(art), "real", art.name + (" (cropped for wide)" if wide else ""))
    if book.get("interim_art"):
        p = rpath(book["interim_art"])
        if p.exists():
            return ArtSource(_open(p, book.get("interim_crop")), "interim", f"INTERIM {book['interim_art']}")
    return ArtSource(None, "placeholder", "placeholder")


def cover_crop(src: Image.Image, size, focus=(0.5, 0.5)) -> Image.Image:
    W, H = size
    sw, sh = src.size
    s = max(W / sw, H / sh)
    nw, nh = max(W, int(round(sw * s))), max(H, int(round(sh * s)))
    im = src.resize((nw, nh), Image.LANCZOS)
    cx, cy = focus[0] * nw, focus[1] * nh
    left = int(min(max(cx - W / 2, 0), nw - W))
    top = int(min(max(cy - H / 2, 0), nh - H))
    return im.crop((left, top, left + W, top + H))


def extend_below(src: Image.Image, size, focus, c0, zone_frac=0.62) -> Image.Image:
    """For square or wide art on a portrait canvas: cover-crop the art into the top zone and
    extend it downward into a darkened, blurred continuation so the title area stays quiet."""
    W, H = size
    zh = int(H * zone_frac)
    zone = cover_crop(src, (W, zh), (focus[0], 0.5))
    feather = int(zh * 0.22)
    ext_top = zh - feather                      # the continuation starts under the feathered part of the art
    ext_h = H - ext_top
    strip_h = max(8, int(zh * 0.05))
    strip = zone.crop((0, zh - strip_h, W, zh)).resize((W, ext_h), Image.BILINEAR)
    strip = strip.filter(ImageFilter.GaussianBlur(W * 0.025))
    arr = np.asarray(strip, np.float32)
    g = np.linspace(0.95, 0.08, ext_h, dtype=np.float32)[:, None, None] ** 1.3
    tint = np.array(c0, np.float32)[None, None, :]
    arr = arr * g + tint * 0.6 * (1 - g)
    full = Image.new("RGB", (W, H), c0)
    full.paste(Image.fromarray(np.clip(arr, 0, 255).astype("uint8")), (0, ext_top))
    m = np.ones(zh, np.float32)
    m[zh - feather:] = 1 - smoothstep(np.linspace(0, 1, feather))
    mask = Image.fromarray((m[:, None].repeat(W, axis=1) * 255).astype("uint8"))
    full.paste(zone, (0, 0), mask)
    return full


def noise_field(size, octaves, rng) -> np.ndarray:
    W, H = size
    acc = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    for cells in octaves:
        cw, ch = max(2, cells), max(2, int(cells * H / W))
        small = rng.rand(ch, cw).astype(np.float32)
        im = Image.fromarray((small * 255).astype("uint8")).resize((W, H), Image.BICUBIC)
        acc += np.asarray(im, np.float32) / 255 * amp
        tot += amp
        amp *= 0.55
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)


def make_placeholder(size, colors, number, wide=False) -> Image.Image:
    """Dark vertical gradient in the book's colour key, soft fog, a faint accent glow, vignette, grain."""
    W, H = size
    rng = np.random.RandomState(1000 + number)
    c0, c1, c2 = (np.array(hex_rgb(c), np.float32) for c in colors)
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    # top: mid tone darkened; middle: a little lighter; bottom: darkest
    top = c0 * 0.55 + c1 * 0.30
    mid = c0 * 0.55 + c1 * 0.52
    bot = c0 * 0.75
    t1 = smoothstep(y / 0.45)
    t2 = smoothstep((y - 0.45) / 0.55)
    base = (top[None, None, :] * (1 - t1[..., None]) + mid[None, None, :] * t1[..., None])
    base = base * (1 - t2[..., None]) + bot[None, None, :] * t2[..., None]
    base = np.broadcast_to(base, (H, W, 3)).copy()

    # fog bands (low-res noise, upscaled)
    sw, sh = max(64, W // 4), max(64, H // 4)
    fog = noise_field((sw, sh), [3, 6, 12], rng)
    fog = np.asarray(Image.fromarray((fog * 255).astype("uint8")).resize((W, H), Image.BICUBIC), np.float32) / 255
    band = np.exp(-(((y - 0.62) / 0.22) ** 2)) * 0.7 + np.exp(-(((y - 0.30) / 0.18) ** 2)) * 0.35
    fog_col = c1 * 0.9 + 40
    base += (fog ** 1.6 * band)[..., None] * (fog_col[None, None, :] - base) * 0.30

    # accent glow where the Iron Wolf's eye / central image would sit
    gx, gy = (0.66, 0.40) if wide else (0.58, 0.36)
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    asp = W / H
    r2 = ((xx - gx) * asp) ** 2 + (y - gy) ** 2
    glow = np.exp(-r2 / (2 * 0.16 ** 2))
    base += glow[..., None] * (c2[None, None, :] * 0.22)

    out = Image.fromarray(np.clip(base, 0, 255).astype("uint8"))
    return out


def finish_art(img: Image.Image, number: int, vignette=0.38, grain=3.2) -> Image.Image:
    """Subtle vignette + film grain, applied to real and placeholder art alike so they match."""
    W, H = img.size
    rng = np.random.RandomState(number)
    arr = np.asarray(img, np.float32)
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    r = np.sqrt((xx * 0.9) ** 2 + (yy * 0.9) ** 2)
    v = 1 - vignette * smoothstep((r - 0.45) / 0.85)
    arr *= v[..., None]
    lo = rng.normal(0, grain, (max(1, H // 2), max(1, W // 2))).astype(np.float32)
    ng = np.asarray(Image.fromarray(np.clip(lo * 8 + 128, 0, 255).astype("uint8")).resize((W, H), Image.BICUBIC),
                    np.float32)
    arr += ((ng - 128) / 8)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))


def gradient_plate(img: Image.Image, color, side, start, end, a0, a1):
    """Darkening plate for legibility. side: 'top' | 'bottom' | 'left'. start/end are fractions of the axis;
    alpha runs from a0 at `start` to a1 at `end` (smoothstep)."""
    W, H = img.size
    if side in ("top", "bottom"):
        t = (np.arange(H, dtype=np.float32) / H - start) / (end - start)
        a = a0 + (a1 - a0) * smoothstep(t)
        m = np.broadcast_to(a[:, None], (H, W))
    else:
        t = (np.arange(W, dtype=np.float32) / W - start) / (end - start)
        a = a0 + (a1 - a0) * smoothstep(t)
        m = np.broadcast_to(a[None, :], (H, W))
    mask = Image.fromarray((np.clip(m, 0, 1) * 255).astype("uint8"))
    img.paste(color, (0, 0), mask)


# --------------------------------------------------------------------------- context

class Ctx:
    def __init__(self, cfg: dict, lang: str = "lt"):
        self.cfg = cfg
        self.lang = lang
        self.fonts = Fonts(cfg)
        self.title_color = hex_rgb(cfg["series"].get("title_color", "#EFE6D2"))
        self.series_name = cfg["series"]["name"] if lang == "lt" else cfg["series"].get("name_en", cfg["series"]["name"])
        self.out_root = rpath(cfg["series"].get("out_dir", "books/covers/out"))

    def book(self, n: int) -> dict:
        for b in self.cfg["books"]:
            if b["number"] == n:
                return b
        sys.exit(f"No book {n} in {CONFIG}")

    def title(self, b):
        return b["title_lt"] if self.lang == "lt" else b["title_en"]

    def series_line(self, b):
        return b["series_line"] if self.lang == "lt" else b.get("series_line_en", b["series_line"])

    def numeral_line(self, b):
        # "GELEŽINIO VILKO SAGA · I KNYGA" -> "I KNYGA"
        return self.series_line(b).split("·")[-1].strip()

    def out_dir(self, b) -> Path:
        d = self.out_root / f"book{b['number']}"
        if self.lang != "lt":
            d = d / self.lang
        d.mkdir(parents=True, exist_ok=True)
        return d


def palette(b):
    c0, c1, c2 = (hex_rgb(c) for c in b["colors"])
    plate = lerp_c(c0, (0, 0, 0), 0.55)
    return c0, c1, c2, plate


# --------------------------------------------------------------------------- base canvases

def base_canvas(ctx: Ctx, b: dict, kind: str, size) -> tuple[Image.Image, ArtSource]:
    W, H = size
    wide = kind in ("video", "thumb")
    c0, c1, c2, _ = palette(b)
    src = pick_art(b, wide)
    focus = tuple(b.get("focus", [0.5, 0.5]))
    if src.is_placeholder:
        img = make_placeholder(size, b["colors"], b["number"], wide=wide)
    elif wide:
        if "wide art" in src.label:
            img = cover_crop(src.image, size, (0.5, 0.5))
        else:
            img = cover_crop(src.image, size, focus)
    else:
        sw, sh = src.image.size
        target_aspect = W / H
        if sw / sh > 0.9 and target_aspect < 0.9:      # squarish art on a portrait cover: extend downward
            img = extend_below(src.image, size, focus, c0)
        else:
            img = cover_crop(src.image, size, focus)
    img = finish_art(img, b["number"])
    return img, src


def placeholder_label(ctx: Ctx, img: Image.Image, b, y_frac, size_px, x_frac=0.5, align="c"):
    paint_text(img, ctx.fonts, img.width * x_frac, img.height * y_frac, "PLACEHOLDER ART", "secondary",
               size_px, ctx.title_color, align=align, tracking=0.28, shadow=0.0, alpha=0.5)


# --------------------------------------------------------------------------- front covers

def title_lines(title: str, stack: bool):
    words = title.split()
    if stack and len(words) > 1:
        if len(words) == 2:
            return words
        half = (len(words) + 1) // 2
        return [" ".join(words[:half]), " ".join(words[half:])]
    return [title]


def render_front(ctx: Ctx, b: dict, kind: str) -> tuple[Image.Image, ArtSource]:
    size = SIZES[kind]
    W, H = size
    f = ctx.fonts
    c0, c1, c2, plate = palette(b)
    img, src = base_canvas(ctx, b, kind, size)
    tc = ctx.title_color
    tc2 = lerp_c(tc, c2, 0.28)          # title gradient bottom: bone warming toward the accent

    # legibility plates (top band for the series name, bottom band for title block)
    gradient_plate(img, plate, "top", 0.0, 0.22, 0.72, 0.0)
    gradient_plate(img, plate, "bottom", 0.50, 0.90, 0.0, 0.90)

    mx = W * 0.09
    if kind in ("ebook", "print_front"):
        top_m, bot_m = H * 0.058, H * 0.06
        sn_max, num_sz = H * 0.060, H * 0.021
        stack, t_cap, t_w = True, H * 0.105, W * 0.82
        years_sz, author_sz = H * 0.024, H * 0.0295
    else:  # square: single-line title, same system
        top_m, bot_m = H * 0.055, H * 0.062
        sn_max, num_sz = H * 0.075, H * 0.0215
        stack, t_cap, t_w = False, H * 0.125, W * 0.84
        years_sz, author_sz = H * 0.0235, H * 0.0315

    # --- top: series name (display) + book numeral line (secondary)
    sn_size = fit_size(f, "display", ctx.series_name, W - 2 * mx, sn_max)
    sn_base = top_m + sn_size * 0.80
    paint_text(img, f, W / 2, sn_base, ctx.series_name, "display", sn_size, tc, align="c",
               stroke=max(1, int(sn_size * 0.012)), gradient_to=tc2)
    nl = ctx.numeral_line(b)
    nl_sz = int(num_sz)
    nl_base = sn_base + sn_size * 0.34 + nl_sz
    nw = paint_text(img, f, W / 2, nl_base, nl, "secondary", nl_sz, c2, align="c", tracking=0.34, shadow=0.8)
    rule_y = nl_base - nl_sz * 0.33
    for sgn in (-1, 1):
        flank(img, W / 2 + sgn * (nw / 2 + nl_sz * 0.9), sgn, W * 0.11, rule_y, c2, H * 0.0007, nl_sz * 0.18)

    # --- bottom block, laid out bottom-up: author / years+ornament / title
    author_base = H - bot_m
    paint_text(img, f, W / 2, author_base, b["author"], "secondary", int(author_sz), tc, align="c",
               tracking=0.16, shadow=0.85)
    years_base = author_base - author_sz * 2.05
    ysz = int(years_sz)
    yw = paint_text(img, f, W / 2, years_base, b["years"].replace("–", " – "), "secondary_light", ysz, c2,
                    align="c", tracking=0.22, shadow=0.85)
    for sgn in (-1, 1):
        flank(img, W / 2 + sgn * (yw / 2 + ysz * 1.0), sgn, W * 0.13, years_base - ysz * 0.30, c2, H * 0.0007, ysz * 0.20)

    lines = title_lines(ctx.title(b), stack)
    t_size = min(fit_size(f, "display", max(lines, key=lambda s: measure(f, "display", 200, s)), t_w, t_cap), int(t_cap))
    lh = t_size * 0.96
    base_last = years_base - ysz * 1.9 - t_size * 0.08
    for i, line in enumerate(lines):
        yb = base_last - (len(lines) - 1 - i) * lh
        paint_text(img, f, W / 2, yb, line, "display", t_size, tc, align="c",
                   stroke=max(1, int(t_size * 0.012)), gradient_to=tc2, shadow=0.85)

    if src.is_placeholder:
        placeholder_label(ctx, img, b, 0.46, int(H * 0.0155))
    return img, src


# --------------------------------------------------------------------------- video / thumbnail

def render_wide(ctx: Ctx, b: dict, kind: str, sparse=False) -> tuple[Image.Image, ArtSource]:
    """Video background (1920x1080) or thumbnail template (1280x720): title lower-left, quiet."""
    size = SIZES[kind]
    W, H = size
    f = ctx.fonts
    c0, c1, c2, plate = palette(b)
    img, src = base_canvas(ctx, b, kind, size)
    tc = ctx.title_color
    tc2 = lerp_c(tc, c2, 0.28)
    # a quiet image: dim slightly, then left and bottom plates under the text
    dim = Image.new("RGB", size, plate)
    img = Image.blend(img, dim, 0.12 if kind == "video" else 0.18)
    gradient_plate(img, plate, "left", 0.0, 0.72, 0.80 if kind == "video" else 0.86, 0.0)
    gradient_plate(img, plate, "bottom", 0.45, 1.0, 0.0, 0.70)

    mx = W * 0.075
    if kind == "video":
        bot_m = H * 0.10
        t_max_w, t_cap = W * 0.54, H * 0.185
        sl_sz, au_sz, yr_sz = H * 0.033, H * 0.038, H * 0.034
    else:  # thumbnail template: larger relative type for small sizes
        bot_m = H * 0.11
        t_max_w, t_cap = W * 0.60, H * 0.25
        sl_sz, au_sz, yr_sz = H * 0.042, H * 0.045, H * 0.040

    base = H - bot_m
    if kind == "video":
        paint_text(img, f, mx, base, b["author"], "secondary", int(au_sz), tc, tracking=0.16, shadow=0.9)
        base -= au_sz * 1.9
    t = ctx.title(b)
    t_size = min(fit_size(f, "display", t, t_max_w, t_cap), int(t_cap))
    # years on the baseline row, then title above, then the series line above the title
    yw = paint_text(img, f, mx, base, b["years"].replace("–", " – "), "secondary_light", int(yr_sz), c2, tracking=0.22,
                    shadow=0.9)
    ImageDraw.Draw(img).line([(mx + yw + yr_sz * 0.9, base - yr_sz * 0.3), (mx + yw + yr_sz * 0.9 + W * 0.12, base - yr_sz * 0.3)],
                             fill=c2, width=max(1, int(H * 0.0016)))
    title_base = base - yr_sz * 2.25
    paint_text(img, f, mx, title_base, t, "display", t_size, tc, stroke=max(1, int(t_size * 0.012)),
               gradient_to=tc2, shadow=0.9)
    sl = ctx.series_line(b)
    sl_base = title_base - t_size * 1.0 - sl_sz * 0.35
    paint_text(img, f, mx, sl_base, sl, "secondary", int(sl_sz), c2, tracking=0.26, shadow=0.9)

    if src.is_placeholder:
        placeholder_label(ctx, img, b, 0.40, int(H * 0.026))
    return img, src


# --------------------------------------------------------------------------- per-part thumbnails

def wrap_to_box(f: Fonts, text, role, max_w, max_h, max_size, max_lines=3, line_gap=1.0):
    """Largest size (<= max_size) at which `text` wraps into <= max_lines lines inside the box."""
    words = text.split()
    for size in range(int(max_size), 20, -4):
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if measure(f, role, size, trial) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if (len(lines) <= max_lines and all(measure(f, role, size, l) <= max_w for l in lines)
                and len(lines) * size * line_gap <= max_h):
            return size, lines
    return 24, [text]


def render_part_thumb(ctx: Ctx, book_number: int, number, title: str, out_path: Path | None = None) -> Path:
    """Chapter thumbnail ("3 skyrius · Gintaro Sapnas" style): big numeral + chapter title, readable at ~320 px wide."""
    b = ctx.book(book_number)
    size = SIZES["thumb"]
    W, H = size
    f = ctx.fonts
    c0, c1, c2, plate = palette(b)
    tc = ctx.title_color
    tc2 = lerp_c(tc, c2, 0.28)
    img, src = base_canvas(ctx, b, "thumb", size)
    img = Image.blend(img, Image.new("RGB", size, plate), 0.30)
    gradient_plate(img, plate, "left", 0.0, 0.95, 0.88, 0.40)
    gradient_plate(img, plate, "bottom", 0.7, 1.0, 0.0, 0.5)

    mx, my = W * 0.06, H * 0.08
    label_word = "SKYRIUS" if ctx.lang == "lt" else "CHAPTER"
    num_s = str(number)
    is_num = num_s.isdigit()
    col_w = 0
    if is_num:
        n_size = int(H * 0.62) if len(num_s) <= 2 else int(H * 0.50)
        n_size = min(n_size, fit_size(f, "display", num_s, W * 0.30, n_size))
        l_size = int(H * 0.068)
        nb = H * 0.62 + (n_size - H * 0.62) * 0.0
        nw = paint_text(img, f, mx, H * 0.60, num_s, "display", n_size, c2, stroke=max(2, int(n_size * 0.012)), shadow=0.9)
        lw = paint_text(img, f, mx + 4, H * 0.60 + l_size * 2.4, label_word, "secondary", l_size, tc, tracking=0.30, shadow=0.9)
        col_w = max(nw, lw)
        ImageDraw.Draw(img).line([(mx + col_w + W * 0.03, H * 0.16), (mx + col_w + W * 0.03, H * 0.74)],
                                 fill=c2, width=max(2, int(H * 0.004)))
        tx = mx + col_w + W * 0.06
    else:
        tx = mx
        paint_text(img, f, mx, my + H * 0.07, number.upper() if hasattr(number, "upper") else str(number),
                   "secondary", int(H * 0.075), c2, tracking=0.30, shadow=0.9)
    box_w = W - tx - W * 0.05
    box_h = H * 0.60
    t_size, lines = wrap_to_box(f, title, "display", box_w, box_h, int(H * 0.30), max_lines=3, line_gap=0.98)
    block_h = len(lines) * t_size * 0.98
    top = H * 0.46 - block_h / 2 + t_size * 0.80
    for i, line in enumerate(lines):
        paint_text(img, f, tx, top + i * t_size * 0.98, line, "display", t_size, tc,
                   stroke=max(1, int(t_size * 0.012)), gradient_to=tc2, shadow=0.9)
    # small book tag, bottom-left
    paint_text(img, f, mx, H - my * 0.9, ctx.title(b).upper(), "secondary", int(H * 0.05), c2, tracking=0.24, shadow=0.9)
    if src.is_placeholder:
        placeholder_label(ctx, img, b, 0.075, int(H * 0.028), x_frac=0.94, align="r")
    if out_path is None:
        d = ctx.out_dir(b) / "thumbs"
        d.mkdir(exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_slug(title)).strip("_")
        out_path = d / f"ch{num_s.zfill(2) if is_num else num_s}_{slug}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def ascii_slug(s: str) -> str:
    table = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")
    return s.translate(table).lower()


def chapter_files(book_number: int):
    """Yield (number_label, title, path) for NN_*.qmd chapter files of a book (H1 as title)."""
    d = REPO / "books" / str(book_number)
    for p in sorted(d.glob("[0-9][0-9]*_*.qmd")):
        m = re.match(r"(\d+)([a-z]?)_", p.name)
        if not m:
            continue
        title = None
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        if not title:
            continue
        title = re.sub(r"^\d+[.:)]?\s*", "", title)
        yield (str(int(m.group(1))) + m.group(2)), title, p


# --------------------------------------------------------------------------- orchestration

def build_book(ctx: Ctx, n: int, kinds=("ebook", "square", "video", "thumb")):
    b = ctx.book(n)
    od = ctx.out_dir(b)
    status = []
    for kind in kinds:
        img, src = render_front(ctx, b, kind) if kind in ("ebook", "square") else render_wide(ctx, b, kind)
        p = od / FILENAMES[kind]
        img.save(p)
        if kind in ("ebook", "video"):
            # Web/EPUB copies: these JPEGs are the committed, published versions.
            img.convert("RGB").save(p.with_suffix(".jpg"), quality=90, optimize=True, progressive=True)
        status.append(f"{FILENAMES[kind]} <- {src.label}")
    print(f"book {n} ({ctx.title(b)}): " + "; ".join(status))


def _save_preview(img, path, max_w=1600):
    """Contact sheets are committed previews: keep them small and deterministic."""
    if img.width > max_w:
        img = img.resize((max_w, round(img.height * max_w / img.width)), Image.LANCZOS)
    img.convert("RGB").save(path, optimize=True)


def contact_sheets(ctx: Ctx):
    od = ctx.out_root
    od.mkdir(parents=True, exist_ok=True)
    books = ctx.cfg["books"]
    suffix = "" if ctx.lang == "lt" else f"_{ctx.lang}"

    def open_out(b, kind):
        d = ctx.out_root / f"book{b['number']}" / ("" if ctx.lang == "lt" else ctx.lang)
        return Image.open(d / FILENAMES[kind]).convert("RGB")

    # fronts in one row
    ch, gap = 1000, 36
    thumbs = []
    for b in books:
        im = open_out(b, "ebook")
        thumbs.append(im.resize((int(im.width * ch / im.height), ch), Image.LANCZOS))
    total_w = sum(t.width for t in thumbs) + gap * (len(thumbs) + 1)
    sheet = Image.new("RGB", (total_w, ch + 2 * gap), (14, 14, 16))
    x = gap
    for t in thumbs:
        sheet.paste(t, (x, gap))
        x += t.width + gap
    _save_preview(sheet, od / f"contact_sheet{suffix}.png")

    # video backgrounds and thumbnails, 3 x 2
    cw, chh = 960, 540
    cols = 3
    rows = (len(books) + cols - 1) // cols
    sheet2 = Image.new("RGB", (cols * cw + (cols + 1) * gap, rows * chh + (rows + 1) * gap), (14, 14, 16))
    for i, b in enumerate(books):
        im = open_out(b, "video").resize((cw, chh), Image.LANCZOS)
        sheet2.paste(im, (gap + (i % cols) * (cw + gap), gap + (i // cols) * (chh + gap)))
    _save_preview(sheet2, od / f"contact_sheet_wide{suffix}.png")
    print(f"contact sheets: {od / ('contact_sheet' + suffix + '.png')}, {od / ('contact_sheet_wide' + suffix + '.png')}")


# --------------------------------------------------------------------------- KDP print wrap cover

DPI = 300
TRIM_W_IN, TRIM_H_IN, BLEED_IN = 6.0, 9.0, 0.125
SPINE_IN_PER_PAGE = {"cream": 0.0025, "white": 0.002252}    # KDP: black & white interior
SPINE_TEXT_MIN_PAGES = 100
SPINE_CLEAR_IN = 0.0625          # clearance each side of the spine text
SAFE_IN = 0.25                   # nothing but the background within 0.25 in of the trim edge
BARCODE_IN = (2.0, 1.2)          # white barcode box, bottom right of the back cover
BARCODE_MARGIN_IN = 0.25


def px(inches: float) -> int:
    return int(round(inches * DPI))


def pdf_pages(path: Path) -> int:
    """Page count of a PDF: PyMuPDF if present, else pdfinfo, else a /Type /Page count."""
    try:
        import fitz  # PyMuPDF
        with fitz.open(str(path)) as doc:
            return doc.page_count
    except ImportError:
        pass
    import shutil
    import subprocess
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True).stdout
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        if m:
            return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page[^s]", path.read_bytes()))


def print_pdf_path(n: int) -> Path:
    """Where `quarto render --profile print` leaves the interior PDF (book 1 renders into books/_book)."""
    d = REPO / "books" / ("" if n == 1 else str(n)) / "_book"
    return d / f"saga-{n}-print.pdf"


def spine_inches(pages: int, paper: str) -> float:
    return pages * SPINE_IN_PER_PAGE[paper]


def wrap_text(f: Fonts, role: str, size: int, text: str, max_w: float) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if measure(f, role, size, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def mirror_bleed(trim: Image.Image, left: int, top: int, right: int, bottom: int) -> Image.Image:
    """Grow a trim-size panel by mirroring its own edges into the bleed (art and plates stay continuous)."""
    W, H = trim.size
    out = Image.new("RGB", (W + left + right, H + top + bottom))
    out.paste(trim, (left, top))
    if left:
        out.paste(trim.crop((0, 0, left, H)).transpose(Image.FLIP_LEFT_RIGHT), (0, top))
    if right:
        out.paste(trim.crop((W - right, 0, W, H)).transpose(Image.FLIP_LEFT_RIGHT), (left + W, top))
    if top:
        out.paste(out.crop((0, top, out.width, 2 * top)).transpose(Image.FLIP_TOP_BOTTOM), (0, 0))
    if bottom:
        out.paste(out.crop((0, top + H - bottom, out.width, top + H)).transpose(Image.FLIP_TOP_BOTTOM), (0, top + H))
    return out


def blurb_for(ctx: Ctx, b: dict) -> str:
    meta_path = REPO / "books" / "book_meta.yml"
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    entry = next(x for x in meta["books"] if x["number"] == b["number"])
    key = f"blurb_{ctx.lang}"
    if not entry.get(key):
        sys.exit(f"{meta_path}: book {b['number']} has no {key}")
    return " ".join(entry[key].split())


class SafeZone:
    """Collects the extents of everything typeset and fails if any lies inside the 0.25 in safe margin."""

    def __init__(self, w, h):
        self.box = (px(SAFE_IN), px(SAFE_IN), w - px(SAFE_IN), h - px(SAFE_IN))
        self.items = []

    def add(self, label, x0, y0, x1, y1):
        bx0, by0, bx1, by1 = self.box
        if x0 < bx0 or y0 < by0 or x1 > bx1 or y1 > by1:
            sys.exit(f"SAFE ZONE VIOLATION: {label} spans x {x0:.0f}-{x1:.0f}, y {y0:.0f}-{y1:.0f}; "
                     f"must stay inside x {bx0}-{bx1}, y {by0}-{by1} (0.25 in from the trim)")
        self.items.append(label)


def render_back_panel(ctx: Ctx, b: dict) -> Image.Image:
    """Back cover at trim size (1800 x 2700): blurred, darkened cover art, series line, blurb, author,
    and a clear white barcode box at the bottom right."""
    W, H = SIZES["print_front"]
    f = ctx.fonts
    c0, c1, c2, plate = palette(b)
    tc = ctx.title_color
    img, _src = base_canvas(ctx, b, "print_front", (W, H))
    img = img.filter(ImageFilter.GaussianBlur(26))
    img = Image.blend(img, Image.new("RGB", (W, H), plate), 0.74)
    gradient_plate(img, plate, "top", 0.0, 0.30, 0.45, 0.0)
    gradient_plate(img, plate, "bottom", 0.62, 1.0, 0.0, 0.55)
    zone = SafeZone(W, H)

    # series line + ornament
    sl = ctx.series_line(b)
    sl_sz = int(H * 0.0185)
    sl_base = int(H * 0.105)
    sw = paint_text(img, f, W / 2, sl_base, sl, "secondary", sl_sz, c2, align="c", tracking=0.30, shadow=0.8)
    zone.add("series line", W / 2 - sw / 2, sl_base - sl_sz, W / 2 + sw / 2, sl_base + sl_sz * 0.3)
    rule_y = sl_base - sl_sz * 0.33
    for sgn in (-1, 1):
        flank(img, W / 2 + sgn * (sw / 2 + sl_sz * 0.9), sgn, W * 0.10, rule_y, c2, H * 0.0007, sl_sz * 0.18)

    # book title (small, display face) above the blurb
    t = ctx.title(b)
    t_size = min(fit_size(f, "display", t, W * 0.70, int(H * 0.058)), int(H * 0.058))
    t_base = int(H * 0.205)
    tw = paint_text(img, f, W / 2, t_base, t, "display", t_size, tc, align="c", stroke=max(1, int(t_size * 0.012)),
                    gradient_to=lerp_c(tc, c2, 0.28), shadow=0.85)
    zone.add("title", W / 2 - tw / 2, t_base - t_size, W / 2 + tw / 2, t_base + t_size * 0.3)

    # blurb: largest size that fits between the title and the author line
    box_x = px(0.62)
    box_w = W - 2 * box_x
    top_y = t_base + int(H * 0.06)
    bar_w, bar_h = px(BARCODE_IN[0]), px(BARCODE_IN[1])
    bar_x1, bar_y1 = W - px(BARCODE_MARGIN_IN), H - px(BARCODE_MARGIN_IN)
    bar_x0, bar_y0 = bar_x1 - bar_w, bar_y1 - bar_h
    author_base = bar_y0 - px(0.42)
    bottom_y = author_base - px(0.55)
    text = blurb_for(ctx, b)
    for size in range(58, 30, -2):
        lines = wrap_text(f, "body", size, text, box_w)
        lh = int(size * 1.36)
        if top_y + len(lines) * lh <= bottom_y:
            break
    else:
        sys.exit(f"book {b['number']}: the blurb does not fit on the back cover even at 31 px")
    block_h = len(lines) * lh
    y = top_y + int((bottom_y - top_y - block_h) * 0.35) + size   # centred in the free band, a little high
    for line in lines:
        w = paint_text(img, f, W / 2, y, line, "body", size, tc, align="c", shadow=0.9)
        zone.add("blurb line", W / 2 - w / 2, y - size, W / 2 + w / 2, y + size * 0.3)
        y += lh

    # author
    au_sz = int(H * 0.0255)
    aw = paint_text(img, f, W / 2, author_base, b["author"], "secondary", au_sz, tc, align="c", tracking=0.16, shadow=0.85)
    zone.add("author", W / 2 - aw / 2, author_base - au_sz, W / 2 + aw / 2, author_base + au_sz * 0.3)

    # barcode box (KDP prints the barcode here when it assigns or prints an ISBN; keep it clear)
    ImageDraw.Draw(img).rectangle([bar_x0, bar_y0, bar_x1, bar_y1], fill=(255, 255, 255))
    zone.add("barcode box", bar_x0, bar_y0, bar_x1, bar_y1)
    return img


def render_spine(ctx: Ctx, b: dict, spine_px: int, height_px: int, with_text: bool) -> Image.Image:
    """Spine panel. Text reads top to bottom (rotated 90 degrees clockwise), centred on the spine width."""
    f = ctx.fonts
    c0, c1, c2, plate = palette(b)
    tc = ctx.title_color
    sp = Image.new("RGB", (spine_px, height_px), plate)
    if not with_text:
        return sp
    clear = px(SPINE_CLEAR_IN)
    inner_w = spine_px - 2 * clear                  # the text must fit inside this band
    L = height_px - 2 * px(BLEED_IN) - 2 * px(0.5)   # 0.5 in kept clear at head and tail
    strip = Image.new("RGB", (L, inner_w), plate)
    # three pieces along the length: series (+numeral), title, author
    sn_sz = max(10, int(inner_w * 0.40))
    ti_sz = max(10, int(inner_w * 0.72))
    au_sz = max(10, int(inner_w * 0.34))
    mid = inner_w * 0.5
    pieces = [
        ("series", ctx.series_name, "display", sn_sz, tc),
        ("title", ctx.title(b), "display", ti_sz, tc),
        ("author", b["author"].upper(), "secondary", au_sz, c2),
    ]
    widths = [measure(f, r, sz, t, 0.16 if r == "secondary" else 0.0) for _, t, r, sz, _ in pieces]
    gap = px(0.35)
    total = sum(widths) + 2 * gap
    while total > L and ti_sz > 12:     # shrink uniformly if a long title does not fit
        k = 0.95
        sn_sz, ti_sz, au_sz = int(sn_sz * k), int(ti_sz * k), int(au_sz * k)
        pieces = [(a, t, r, int(sz * k), col) for a, t, r, sz, col in pieces]
        widths = [measure(f, r, sz, t, 0.16 if r == "secondary" else 0.0) for _, t, r, sz, _ in pieces]
        total = sum(widths) + 2 * gap
    x = (L - total) / 2
    for (name, text, role, size, col), w in zip(pieces, widths):
        base = mid + size * (0.28 if role == "display" else 0.30)
        paint_text(strip, f, x, base, text, role, size, col, align="l",
                   tracking=0.16 if role == "secondary" else 0.0, shadow=0.0)
        x += w + gap
    strip = strip.rotate(-90, expand=True)          # clockwise: reads top to bottom
    sp.paste(strip, (clear, px(BLEED_IN) + px(0.5)))
    return sp


def save_cover_pdf(img: Image.Image, path: Path, width_in: float, height_in: float) -> None:
    """One-page PDF whose page box is exactly width_in x height_in (72 pt per inch). PyMuPDF places the
    image on an exact page; without it, Pillow writes the page size from the pixel size and a dpi."""
    try:
        import fitz
    except ImportError:
        img.save(path, "PDF", resolution=img.width / width_in)
        return
    import io
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0, optimize=True, dpi=(DPI, DPI))
    doc = fitz.open()
    page = doc.new_page(width=width_in * 72, height=height_in * 72)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.set_metadata({"title": "KDP wrap cover", "creator": "scripts/make_covers.py"})
    doc.save(str(path), deflate=True)
    doc.close()


def build_print_cover(ctx: Ctx, n: int, pages: int, paper: str, guides: bool = True) -> Path:
    b = ctx.book(n)
    spine_in = spine_inches(pages, paper)
    bleed = px(BLEED_IN)
    back_w = front_w = px(BLEED_IN + TRIM_W_IN)
    spine_w = px(spine_in)
    W = back_w + spine_w + front_w
    H = px(TRIM_H_IN + 2 * BLEED_IN)
    total_in = 2 * (BLEED_IN + TRIM_W_IN) + spine_in

    front_trim, src = render_front(ctx, b, "print_front")
    back_trim = render_back_panel(ctx, b)
    front = mirror_bleed(front_trim, 0, bleed, bleed, bleed)     # bleed top, bottom and the outer edge
    back = mirror_bleed(back_trim, bleed, bleed, 0, bleed)       # bleed top, bottom and the outer edge
    with_text = pages >= SPINE_TEXT_MIN_PAGES
    spine = render_spine(ctx, b, spine_w, H, with_text)

    cover = Image.new("RGB", (W, H))
    cover.paste(back, (0, 0))
    cover.paste(spine, (back_w, 0))
    cover.paste(front, (back_w + spine_w, 0))

    od = ctx.out_dir(b)
    pdf = od / "print_cover_kdp.pdf"
    save_cover_pdf(cover, pdf, total_in, TRIM_H_IN + 2 * BLEED_IN)
    prev = cover.copy()
    prev.thumbnail((1800, 1800))
    prev.save(od / "print_cover_kdp_preview.jpg", quality=88, optimize=True)
    if guides:
        g = cover.copy()
        d = ImageDraw.Draw(g)
        lw = 3
        def vline(x, col): d.line([(x, 0), (x, H)], fill=col, width=lw)
        def hline(y, col): d.line([(0, y), (W, y)], fill=col, width=lw)
        for x in (bleed, back_w, back_w + spine_w, W - bleed):       # trim / spine folds
            vline(x, (255, 40, 40))
        for y in (bleed, H - bleed):
            hline(y, (255, 40, 40))
        for x in (bleed + px(SAFE_IN), back_w - px(0.0) - px(SAFE_IN), back_w + spine_w + px(SAFE_IN), W - bleed - px(SAFE_IN)):
            vline(x, (40, 220, 90))
        for y in (bleed + px(SAFE_IN), H - bleed - px(SAFE_IN)):
            hline(y, (40, 220, 90))
        g.thumbnail((1800, 1800))
        g.save(od / "print_cover_kdp_guides.jpg", quality=85, optimize=True)
    print(f"book {n}: {pages} pages ({paper}) -> spine {spine_in:.4f} in ({spine_w} px), full cover "
          f"{total_in:.4f} x {TRIM_H_IN + 2 * BLEED_IN:.3f} in = {W} x {H} px @ {DPI} dpi, "
          f"spine text {'yes' if with_text else 'no (< %d pages)' % SPINE_TEXT_MIN_PAGES}; art: {src.label}\n"
          f"        {pdf}")
    return pdf


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["lt", "en"], default="lt", help="title language (default lt)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("all", help="all books + contact sheets")
    p = sub.add_parser("book", help="one book")
    p.add_argument("number", type=int)
    p = sub.add_parser("part", help="one chapter thumbnail")
    p.add_argument("--book", type=int, required=True)
    p.add_argument("--number", required=True, help="chapter number (or a label such as 'Prologas')")
    p.add_argument("--title", required=True)
    p.add_argument("--out", type=Path)
    p = sub.add_parser("chapters", help="thumbnails for every NN_*.qmd chapter of a book")
    p.add_argument("--book", type=int, required=True)
    sub.add_parser("contact", help="rebuild contact sheets from existing output")
    sub.add_parser("check-fonts", help="Lithuanian glyph-coverage check only")
    p = sub.add_parser("print", help="KDP paperback wrap cover (6 x 9 in trim) for one book or 'all'")
    p.add_argument("number", help="book number 1-6, or 'all'")
    p.add_argument("--pages", type=int, help="interior page count (default: read it from the print PDF)")
    p.add_argument("--paper", choices=sorted(SPINE_IN_PER_PAGE), default="cream",
                   help="paper colour; sets the spine factor (cream 0.0025 in/page, white 0.002252)")
    p.add_argument("--pdf", type=Path, help="interior PDF to read the page count from")
    p.add_argument("--no-guides", action="store_true", help="skip the *_guides.jpg overlay")
    args = ap.parse_args(argv)

    cfg = load_config()
    ctx = Ctx(cfg, args.lang)
    print("Font coverage check (" + LITHUANIAN_REQUIRED + "):\n" + ctx.fonts.report())
    if args.cmd == "check-fonts":
        return
    if args.cmd == "all":
        for b in cfg["books"]:
            build_book(ctx, b["number"])
        contact_sheets(ctx)
    elif args.cmd == "book":
        build_book(ctx, args.number)
    elif args.cmd == "part":
        print(render_part_thumb(ctx, args.book, args.number, args.title, args.out))
    elif args.cmd == "chapters":
        for label, title, _ in chapter_files(args.book):
            print(render_part_thumb(ctx, args.book, label, title))
    elif args.cmd == "contact":
        contact_sheets(ctx)
    elif args.cmd == "print":
        nums = [b["number"] for b in cfg["books"]] if args.number == "all" else [int(args.number)]
        if args.pages and len(nums) > 1:
            sys.exit("--pages applies to a single book; use --pdf or the default for 'all'")
        for n in nums:
            pages = args.pages
            if not pages:
                pdf = args.pdf if (args.pdf and len(nums) == 1) else print_pdf_path(n)
                if not pdf.exists():
                    sys.exit(f"no page count for book {n}: {pdf} not found (render the print PDF or pass --pages)")
                pages = pdf_pages(pdf)
                if pages % 2:
                    pages += 1   # KDP pads an odd page count with a blank page
            build_print_cover(ctx, n, pages, args.paper, guides=not args.no_guides)


if __name__ == "__main__":
    main()
