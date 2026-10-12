#!/usr/bin/env python3
"""Prompt builder and image post-processor for the wiki entity art.

Used by scripts/generate_wiki_art_codex.sh, but also usable by hand:

    python3 scripts/wiki_art_prompts.py list [--types character,place] [--ids a,b]
    python3 scripts/wiki_art_prompts.py prompt vytautas         # print the full prompt
    python3 scripts/wiki_art_prompts.py process RAW.png OUT.jpg ASPECT   # ASPECT: portrait|landscape

Everything is read from world_rules/graph/world_graph.json plus persona/<Name>/description.md (when it exists).
One shared style block keeps every image consistent with the book covers (books/covers/art_prompts.md).
Stdlib + Pillow (only for `process`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "world_rules" / "graph" / "world_graph.json"
PERSONA = ROOT / "persona"

# ---- Style (same language as books/covers/art_prompts.md) -----------------------------------------------------
STYLE = (
    "Painterly dark-realist historical fantasy illustration, oil-on-canvas look with visible brushwork and "
    "restrained, desaturated natural pigments (umber, iron grey, moss, bone), cinematic low-key lighting with a "
    "single warm amber light source and cold iron-blue shadows, grounded and gritty rather than glossy, high detail, "
    "atmospheric depth. Same visual series as a set of dark-fantasy book covers set in the Grand Duchy of Lithuania "
    "and its neighbours, 14th-15th century."
)

PERIOD = (
    "Strict historical accuracy for late-medieval Lithuania, Poland and the Teutonic Order (c. 1340-1450). "
    "Dress: wool and linen tunics, long kaftan-like coats with fur trim (Ruthenian and steppe influence), fur caps "
    "and hoods, leather belts and boots, cloaks fastened with a brooch; Western courts wear velvet doublets, houppelandes "
    "and chaperon hoods. Arms: single-hand swords, spears, axes, round and kite shields, mail hauberks, gambesons, "
    "open helmets and kettle hats; early plate only as partial arm and leg harness after c. 1400; never full Renaissance "
    "plate, no visors from the 16th century, no horned or winged helmets. Architecture: red-brick Gothic castles with "
    "stepped gables and pointed arches, timber-and-earth hillforts (piliakalniai) with palisades, thatched or shingled "
    "wooden halls, carved wooden idols and sacred oaks, open fire altars; no stone Romanesque or Renaissance palaces, no "
    "onion domes, no windmills or watermills as scenery. Heraldry only when it matters and then only simple, wordless "
    "devices: the Columns of Gediminas, the Vytis (a mounted knight with raised sword on a red field), the Teutonic "
    "Order's black cross on a white mantle, the Polish white eagle on red. No Norse, Celtic, Greek, Roman or "
    "Japanese motifs, no runes, no modern or fantasy-game armour."
)

NEGATIVE = (
    "text, letters, words, numbers, runes, inscriptions, captions, subtitles, watermark, signature, logo, banner "
    "lettering, readable heraldry, modern objects, power lines, plastic, anachronistic plate armour, horned helmets, "
    "cartoon, anime, 3D render look, glossy CGI, extra fingers, deformed hands, duplicated figures, cluttered composition"
)

# ---- Kinds: type -> (kind, aspect) ---------------------------------------------------------------------------
KIND = {
    "character": ("portrait", "portrait"),
    "god": ("god", "portrait"),
    "force": ("force", "portrait"),
    "creature": ("creature", "portrait"),
    "place": ("place", "landscape"),
    "event": ("event", "landscape"),
    "faction": ("group", "landscape"),
    "house": ("group", "landscape"),
    "artifact": ("artifact", "landscape"),
    "pact": ("symbol", "landscape"),
    "school": ("symbol", "landscape"),
    "element": ("symbol", "landscape"),
}
SKIP_TYPES = {"book"}  # covers already exist (wiki/images/bookN.jpg)

COMPOSITION = {
    "portrait": (
        "Waist-up (or head-and-shoulders) character portrait, subject three-quarter turned, eyes toward the viewer, "
        "dark atmospheric background hinting at their world, face clearly lit by a warm amber light. Vertical 3:4 "
        "composition, subject centred, nothing important within the outer 8 percent."
    ),
    "god": (
        "A pagan deity of the Baltic peoples shown as a majestic, slightly uncanny figure, half-real and half-vision, "
        "painted with the same grounded realism (carved-wood, fur, iron, amber, fire, weather) rather than a glossy "
        "fantasy-game look, standing in or rising from a recognisable natural setting. Vertical 3:4 composition."
    ),
    "force": (
        "A vast, half-seen supernatural presence rendered as atmosphere and silhouette (mist, smoke, ash, amber light, "
        "frost) in the manner of the translucent Iron Wolf on the book covers, with a small human figure or landscape "
        "for scale. Vertical 3:4 composition."
    ),
    "creature": (
        "A folkloric creature from Baltic and Slavic legend, painted as a believable natural animal-like being in its "
        "habitat (forest, bog, lake shore), not cute, not a game monster. Vertical 3:4 composition."
    ),
    "place": (
        "Establishing landscape of the place, wide and atmospheric, with period architecture and a few small figures "
        "for scale. Horizontal 4:3 composition, main subject in the central two thirds."
    ),
    "event": (
        "A single decisive moment of the event as a painted scene, figures in period dress and arms, strong amber "
        "key light. Horizontal 4:3 composition, main subject in the central two thirds."
    ),
    "group": (
        "A group or emblematic scene representing the faction or family: a few figures in authentic period dress and "
        "arms in their characteristic setting; no readable banners. Horizontal 4:3 composition."
    ),
    "artifact": (
        "A single object, centred, shown as a museum-grade painted still life on a dark, near-black background "
        "(worn wood or oiled leather surface barely visible), lit by one warm amber light with soft glow, "
        "fine period-accurate craftsmanship and the wear of centuries. Horizontal 4:3 composition, plenty of dark "
        "margin around the object."
    ),
    "symbol": (
        "An evocative still-life or ritual tableau symbolising the concept (fire, amber, water, ash, oath-stones, "
        "wood), no human face in focus, dark background. Horizontal 4:3 composition."
    ),
}

# Hand-written guidance for specific entities (overrides / enriches graph + persona data).
HINTS = {
    "vytautas": (
        "Vytautas the Great, c. 1350-1430, shown as a man of about 45: dark hair cut short, short dark beard, "
        "piercing grey eyes, a hard, intelligent face with a hint of weariness. Wolf-fur-collared dark coat over a "
        "mail coif and hauberk, plain belt, a single-hand sword at the hip; he holds in one open palm a small raw, "
        "unpolished honey-amber pebble that glows like a live ember and lights his face. No crown, no plate harness."
    ),
    "jogaila": (
        "Jogaila (Wladyslaw II Jagiello), c. 1362-1434, shown as a man of about 35: slender, clean-shaven, dark "
        "restless watchful eyes, long dark hair to the ears. Rich Western court dress of c. 1390: a deep red velvet "
        "houppelande with fur trim and a plain gold circlet, a heavy chain of office; behind him the shadowy hall of "
        "Wawel with a single window of cold light. Calculating, slightly haunted expression."
    ),
    "birute": (
        "Birute, pagan priestess-duchess (vaidilute) of Palanga and wife of Kestutis, about 50: long pale silver-blonde "
        "hair loose under a simple linen veil, a terrible, serene grace, sea-dark eyes. White linen robe with a woollen "
        "mantle and a necklace of raw amber beads, standing at the Baltic dunes at dusk beside a small sacred fire; a "
        "faint amber glow gathers in her cupped hands. Historic Baltic dress only."
    ),
    "trakai": (
        "Trakai Island Castle as it stood in the early 15th century: a red-brick Gothic castle with a tall "
        "cylindrical donjon tower and stepped gables rising from a small island in lake Galve, brick curtain walls "
        "reflected in the water, a wooden bridge to the shore, tall dark pines and a few moored wooden boats; cold "
        "dusk light with a warm amber glow in a few narrow windows and a thin mist on the lake."
    ),
    "pebble": (
        "A single small, raw, unpolished, honey-coloured piece of Baltic amber, the size of a pigeon's egg, rounded "
        "by the sea, with a few frozen insects and dark inclusions visible inside, glowing from within like a live "
        "ember, resting on a scrap of dark worn wool beside a short length of leather thong. No cut or faceted gem, "
        "no jewellery setting."
    ),
    "perkunas": (
        "Perkunas, the Baltic god of thunder, lightning and oaks: a powerful, grim, bearded man of middle age, wild "
        "dark hair and beard, a mantle of storm cloud, holding a heavy axe crackling with a thin thread of lightning, "
        "seen as a half-carved, half-living wooden idol of dark oak that is becoming flesh and storm, rising above a "
        "sacred oak grove at the edge of a hillfort, with a small fire burning at his feet and a small figure of a "
        "pagan priest (krivis) in a linen robe in front. Thunderheads behind, amber light on the carved face. "
        "No Thor, no Zeus, no Norse imagery."
    ),
}


# ---- data helpers ---------------------------------------------------------------------------------------------
def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]+", "_", "".join(c for c in s if not unicodedata.combining(c)).lower()).strip("_")


def load_nodes() -> dict:
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    return {n["id"]: n for n in data["nodes"]}


def persona_dir(n: dict) -> Path | None:
    if not PERSONA.is_dir():
        return None
    want = {fold(n["id"]), fold(re.split(r"[ (]", n["name"])[0])}
    for d in PERSONA.iterdir():
        if d.is_dir() and fold(d.name) in want:
            return d
    return None


def persona_text(n: dict, limit: int = 900) -> str:
    d = persona_dir(n)
    f = d / "description.md" if d else None
    if not f or not f.exists():
        return ""
    txt = f.read_text(encoding="utf-8")
    out = []
    for key in ("Title", "Age"):
        m = re.search(rf"^\*\*{key}\*\*:\s*(.+)$", txt, re.M)
        if m:
            out.append(f"{key}: {m.group(1).strip()}")
    m = re.search(r"^## Appearance\s*\n(.*?)(?=^## |\Z)", txt, re.M | re.S)
    if m:
        out.append("Appearance: " + " ".join(l.strip("*- \t") for l in m.group(1).strip().splitlines() if l.strip()))
    return " ".join(out)[:limit]


def facts(n: dict) -> str:
    bits = [f"Name: {n['name']}", f"Kind: {n['type']}"]
    if n["type"] == "character":
        bits.append(f"Lived c. {n.get('born', '?')}-{n.get('died', '?')}")
    elif n.get("created"):
        bits.append(f"Made {n['created']}")
    elif n.get("year") or n.get("date"):
        bits.append(f"Date: {n.get('date') or n.get('year')}")
    elif n.get("start"):
        bits.append(f"Years: {n['start']}-{n.get('end')}")
    if n.get("note"):
        bits.append(f"Note: {n['note']}")
    return ". ".join(bits) + "."


def build_prompt(n: dict) -> str:
    kind, aspect = KIND[n["type"]]
    parts = [STYLE, "", PERIOD, "", f"SUBJECT. {facts(n)}"]
    if n["id"] in HINTS:
        parts.append(HINTS[n["id"]])
    else:
        pt = persona_text(n)
        if pt:
            parts.append(f"From the character sheet: {pt}")
        if not pt and not n.get("note"):
            parts.append(
                "Invent a plausible, historically grounded depiction from the name and kind; keep it sober and period-accurate."
            )
    parts += ["", "COMPOSITION. " + COMPOSITION[kind], "",
              "RULES. Absolutely no text, letters, runes, numbers or watermark anywhere in the image; no signature; "
              "no modern elements. Avoid: " + NEGATIVE + "."]
    return "\n".join(parts)


def aspect_of(n: dict) -> str:
    return KIND[n["type"]][1]


# ---- post-processing ------------------------------------------------------------------------------------------
def process(src: Path, dst: Path, aspect: str, long_side: int = 1200, max_kb: int = 380) -> None:
    from PIL import Image  # lazy: only needed here

    im = Image.open(src).convert("RGB")
    ratio = 3 / 4 if aspect == "portrait" else 4 / 3  # w/h
    w, h = im.size
    if w / h > ratio:  # too wide: crop sides
        nw = round(h * ratio)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:  # too tall: crop, biased towards the top (faces)
        nh = round(w / ratio)
        top = round((h - nh) * 0.3)
        im = im.crop((0, top, w, top + nh))
    im.thumbnail((long_side, long_side), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    for q in range(88, 40, -4):
        im.save(dst, "JPEG", quality=q, optimize=True, progressive=True)
        if dst.stat().st_size <= max_kb * 1024:
            break
    print(f"{dst} {im.size[0]}x{im.size[1]} {dst.stat().st_size // 1024} KB (q{q})")


def select(nodes: dict, types: str, ids: str) -> list[dict]:
    want_ids = ids.replace(",", " ").split()
    want_types = types.replace(",", " ").split()
    out = []
    for n in nodes.values():
        if n["type"] in SKIP_TYPES or n["type"] not in KIND:
            continue
        if want_ids and n["id"] not in want_ids:
            continue
        if want_types and n["type"] not in want_types:
            continue
        out.append(n)
    if want_ids:  # keep the caller's order, report unknown ids
        order = {i: k for k, i in enumerate(want_ids)}
        out.sort(key=lambda n: order[n["id"]])
        for i in want_ids:
            if i not in nodes:
                print(f"warning: unknown id '{i}'", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list", help="print 'id aspect' lines for the selected entities")
    l.add_argument("--types", default="")
    l.add_argument("--ids", default="")
    p = sub.add_parser("prompt", help="print the prompt for one id")
    p.add_argument("id")
    q = sub.add_parser("process", help="crop + downscale a raw image into a wiki JPEG")
    q.add_argument("src")
    q.add_argument("dst")
    q.add_argument("aspect", choices=["portrait", "landscape"])
    a = ap.parse_args()
    if a.cmd == "process":
        process(Path(a.src), Path(a.dst), a.aspect)
        return
    nodes = load_nodes()
    if a.cmd == "list":
        for n in select(nodes, a.types, a.ids):
            print(n["id"], aspect_of(n))
    else:
        if a.id not in nodes or nodes[a.id]["type"] not in KIND:
            sys.exit(f"no generatable entity '{a.id}'")
        print(build_prompt(nodes[a.id]))


if __name__ == "__main__":
    main()
