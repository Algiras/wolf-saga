#!/usr/bin/env python3
"""Build the saga wiki (Quarto website in wiki/) from world_rules/graph/world_graph.json.

Usage:
    python3 scripts/build_wiki.py          # generate; then: quarto render wiki
    python3 scripts/build_wiki.py --clean  # also delete generated infoboxes first

What it does:
  * For every graph node, creates wiki/<section>/<id>.qmd from wiki/_templates/<type>.md
    ONLY IF the page does not exist yet. Hand-written prose is never overwritten.
  * Always regenerates wiki/_generated/<id>.md: infobox, relations (with backlinks),
    timeline, and a 1-hop relation graph. Pages pull it in with {{< include >}}.
  * Regenerates section indexes, the timeline page, and copies the world-bible
    docs into wiki/codex/ (generated, git-ignored).
  * If world_rules/graph/statblocks.json exists, renders a D&D-style stat block (creature / god /
    force), spell card or magic-item card into each node's generated include, right after the
    infobox. Missing or partial data is fine: nodes without an entry simply get no block.
Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "world_rules" / "graph" / "world_graph.json"
WIKI = ROOT / "wiki"
TEMPLATES = WIKI / "_templates"
IMAGES = WIKI / "images"
IMAGE_EXTS = (".jpg", ".jpeg", ".webp", ".png")
CREDITS = IMAGES / "credits.json"     # written by scripts/fetch_wiki_images.py; AI images have no entry
# Stat-block data (owned by the data agent / canon docs). Optional; STATBLOCKS=<path> overrides it for tests.
STATBLOCKS = Path(os.environ.get("STATBLOCKS") or ROOT / "world_rules" / "graph" / "statblocks.json")
GEN = WIKI / "_generated"
CODEX = WIKI / "codex"

SECTION = {
    "character": "characters", "god": "gods", "force": "forces", "school": "magic",
    "element": "magic", "pact": "magic", "artifact": "artifacts", "faction": "factions",
    "place": "places", "event": "events", "book": "books", "creature": "creatures", "house": "houses",
}
SECTION_TITLE = {
    "characters": "Characters", "gods": "Gods", "forces": "Forces", "magic": "Magic & Pacts",
    "artifacts": "Artifacts", "factions": "Factions", "places": "Places", "events": "Events",
    "books": "Books", "creatures": "Creatures", "houses": "Houses",
}
# (out-label, in-label); None in-label => symmetric (same label both ways)
LABEL = {
    "parent_of": ("Parent of", "Child of"), "spouse_of": ("Spouse", None), "sibling_of": ("Sibling", None),
    "ally_of": ("Ally", None), "enemy_of": ("Enemy", None), "vassal_of": ("Vassal of", "Overlord of"),
    "hostage_of": ("Hostage of", "Holds hostage"), "rules": ("Rules", "Ruled by"),
    "member_of": ("Member of", "Members"), "serves": ("Serves", "Served by"),
    "face_of": ("Force-face of", "Force-faces"), "shard_of": ("Shard of", "Shards"),
    "egregore_fed_by": ("Fed by", "Feeds"), "vessel_of": ("Vessel of", "Vessels"),
    "mask_of": ("Mask of", "Masks"), "claims": ("Claims", "Claimed by"),
    "bargain_with": ("Bargained with", "Bargained with"), "servant_of": ("Servant of", "Servants"),
    "patron_of": ("Patron of", "Patrons"), "feud_with": ("Feud with", None),
    "practises": ("Practises", "Practitioners"), "uses_element": ("Uses element", "Used by"),
    "element_of": ("Element", "Deity"), "binds": ("Binds", "Bound by"),
    "surety_for": ("Surety for", "Surety"), "counters": ("Counters", "Countered by"),
    "holds": ("Holds", "Held by"), "created_by": ("Created by", "Created"),
    "anchors": ("Anchors", "Anchored by"), "keeper_of": ("Keeps", "Kept by"), "participant": ("Took part in", "Participants"),
    "causes": ("Causes", "Caused by"), "breaks": ("Breaks", "Broken by"), "ends": ("Ends", "Ended by"),
    "occurs_at": ("Location", "Events here"), "protagonist_of": ("Protagonist of", "Protagonist"),
    "antagonist_of": ("Antagonist of", "Antagonists"),
}
CODEX_DOCS = [
    ("world_rules/canon_decisions.md", "Canon decisions"),
    ("world_rules/cosmology.md", "Cosmology"),
    ("world_rules/magic_rules.md", "Magic rules"),
    ("world_rules/power_systems.md", "Power systems"),
    ("world_rules/master_chronology.md", "Master chronology"),
    ("books/series_arc.md", "Series arc"),
    ("books/character_arcs.md", "Character arcs"),
    ("world_rules/bestiary.md", "Bestiary"),
    ("world_rules/iron_wolves.md", "The Iron Wolves"),
    ("world_rules/legends_and_songs.md", "Legends & songs"),
    ("world_rules/religion_and_clergy.md", "Faiths & clergy"),
    ("world_rules/geography_gazetteer.md", "Geography"),
    ("world_rules/peoples_and_cultures.md", "Peoples & cultures"),
    ("world_rules/houses_and_lineages.md", "Houses & lineages"),
    ("world_rules/powers_and_politics.md", "Powers & politics"),
    ("world_rules/languages_and_naming.md", "Languages & naming"),
    ("world_rules/pronunciation_guide.md", "Pronunciation guide"),
    ("world_rules/calendar_and_festivals.md", "Calendar & festivals"),
    ("world_rules/graph/relation_maps.md", "Relation maps by book"),
    ("books/1/story_review.md", "Book I review"),
    ("books/1/continuity_bible.md", "Book I continuity bible"),
]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def years(n):
    t = n["type"]
    if t == "character":
        b, d = n.get("born"), n.get("died")
        c = "c. " if n.get("approx") else ""
        return f"{c}{b or '?'}–{d or '?'}"
    if t in ("book", "pact"):
        return f"{n.get('start')}–{n.get('end')}"
    if t == "event":
        return n.get("date") or str(n.get("year"))
    if t == "artifact" and n.get("created"):
        return f"made {n['created']}"
    return ""


def link(n, from_section=True):
    return f"[{n['name']}](../{SECTION[n['type']]}/{n['id']}.qmd)"


def edge_years(e):
    a, b = e.get("from"), e.get("to")
    if a is None and b is None:
        return ""
    return f" ({a or '…'}–{b or '…'})"


def entity_image(n):
    """Return the site-relative path of wiki/images/<id>.(jpg|webp|png) if one exists, else None."""
    for ext in IMAGE_EXTS:
        if (IMAGES / f"{n['id']}{ext}").is_file():
            return f"images/{n['id']}{ext}"
    return None


def image_credits():
    try:
        return json.loads(CREDITS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def md_url(u):
    return u.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def credit_line(c):
    """Markdown 'Image: artist, licence via Wikimedia Commons', linked to the Commons file page."""
    artist = re.sub(r"([\[\]])", r"\\\1", c.get("artist") or "Unknown author")
    lic = c.get("license", "")
    return f"Image: [{artist}, {lic}]({md_url(c['page'])}) via Wikimedia Commons"


def book_banner(n):
    """Full-width banner above a book page's infobox (wiki/images/banners/<id>.jpg)."""
    for ext in IMAGE_EXTS:
        if (IMAGES / "banners" / f"{n['id']}{ext}").is_file():
            cap = f"{n['name']}<small>{years(n)}</small>" if years(n) else n["name"]
            alt = n["name"].replace('"', "'")
            return ["::: {.book-banner}",
                    f'<img src="../images/banners/{n["id"]}{ext}" alt="{alt}" loading="lazy">',
                    f'<div class="book-banner-cap">{cap}</div>', ":::", ""]
    return []


# ---------------------------------------------------------------------------------------------
# Stat blocks (world_rules/graph/statblocks.json -> raw HTML in wiki/_generated/<id>.md)
# ---------------------------------------------------------------------------------------------
KIND_BY_TYPE = {"creature": "creature", "god": "god", "force": "force", "school": "spell",
                "element": "spell", "pact": "spell", "artifact": "item"}
KIND_LABEL = {"creature": "Creature", "god": "God", "force": "Force", "spell": "Spell", "item": "Item"}
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_EM = re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])|(?<![\w])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w])")


def inline_md(text) -> str:
    """Tiny inline-Markdown subset -> HTML: [text](url), **strong**, *em* / _em_. Everything else is escaped."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    parts = []

    def stash(m):                       # links first, so '*' / '_' inside URLs are never touched
        url = m.group(2)
        url = re.sub(r"\.qmd(?=$|#)", ".html", url)
        parts.append(f'<a href="{html.escape(url, quote=True)}">{inline_md(m.group(1))}</a>')
        return f"\x00{len(parts) - 1}\x00"

    out = html.escape(_LINK.sub(stash, text), quote=False)
    out = _STRONG.sub(r"<strong>\1</strong>", out)
    out = _EM.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: parts[int(m.group(1))], out)


def load_statblocks() -> dict:
    """Return {node_id: entry}; {} when the file is missing, empty or unreadable (never fails the build)."""
    if not STATBLOCKS.is_file():
        return {}
    try:
        data = json.loads(STATBLOCKS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"warning: cannot read {STATBLOCKS.name}: {exc}; building without stat blocks", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"warning: {STATBLOCKS.name} must be a JSON object keyed by node id; ignoring it", file=sys.stderr)
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}


def _pairs(items, what, nid):
    """Yield (label, text) pairs from a list of [label, text] items, skipping malformed ones."""
    for it in items or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2 and it[0] is not None:
            yield str(it[0]), "" if it[1] is None else str(it[1])
        else:
            print(f"warning: statblocks[{nid}].{what}: skipped malformed item {it!r}", file=sys.stderr)


def statblock_html(n, sb) -> str:
    """Raw-HTML block (pandoc ```{=html} fence) for one node's stat block, or '' if there is nothing to show."""
    nid = n["id"]
    kind = sb.get("kind") or KIND_BY_TYPE.get(n["type"], "creature")
    if kind not in KIND_LABEL:
        print(f"warning: statblocks[{nid}]: unknown kind {kind!r}, using creature", file=sys.stderr)
        kind = "creature"
    fields = list(_pairs(sb.get("fields"), "fields", nid))
    sections = []
    for sec in sb.get("sections") or []:
        if isinstance(sec, dict) and sec.get("title"):
            sections.append((str(sec["title"]), list(_pairs(sec.get("entries"), f"sections[{sec['title']}]", nid))))
        else:
            print(f"warning: statblocks[{nid}].sections: skipped malformed section {sec!r}", file=sys.stderr)
    if not fields and not sections:
        return ""
    subtitle = str(sb.get("subtitle") or "").strip()
    source = str(sb.get("source") or "").strip()
    size = len(subtitle) + sum(len(a) + len(b) for a, b in fields) + sum(len(a) + len(b) for _, es in sections for a, b in es)
    out = []
    add = out.append
    rule = '<div class="sb-rule"></div>'

    def entry(name, text):
        return f'<p class="sb-entry"><strong><em>{inline_md(name).rstrip(".")}.</em></strong> {inline_md(text)}</p>'

    def sections_html():
        return [f'<div class="sb-section"><div class="sb-title" role="heading" aria-level="4">{inline_md(t)}</div>'
                + "".join(entry(a, b) for a, b in es) + "</div>" for t, es in sections]

    src = f'<div class="sb-source"><span>Source:</span> {inline_md(source)}</div>' if source else ""
    label = html.escape(f"{n['name']} ({KIND_LABEL[kind].lower()})", quote=True)
    if kind in ("creature", "god", "force"):
        size_cls = "sb-wide" if size > 1300 else "sb-compact"
        add(f'<div class="statblock sb-{kind} {size_cls}" role="group" aria-label="{label}">')
        add('<div class="sb-bar"></div><div class="sb-body">')
        add(f'<div class="sb-name">{inline_md(n["name"])}</div>')
        if subtitle:
            add(f'<div class="sb-sub">{inline_md(subtitle)}</div>')
        add(rule)
        for k, v in fields:
            add(f'<p class="sb-prop"><strong>{inline_md(k)}</strong> {inline_md(v)}</p>')
        for i, block in enumerate(sections_html()):
            if i == 0 and fields:
                add(rule)
            add(block)
        add("</div>" + src + '<div class="sb-bar"></div></div>')
    elif kind == "spell":
        add(f'<div class="statblock sb-card sb-spell" role="group" aria-label="{label}">')
        add(f'<div class="sb-name">{inline_md(n["name"])}</div>')
        if subtitle:
            add(f'<div class="sb-sub">{inline_md(subtitle)}</div>')
        add(rule)
        if fields:
            add('<dl class="sb-grid">' + "".join(
                f'<div class="sb-cell"><dt>{inline_md(k)}</dt><dd>{inline_md(v)}</dd></div>' for k, v in fields) + "</dl>")
        add("".join(sections_html()) + src + "</div>")
    else:  # item
        rarity = next((v for k, v in fields if k.strip().lower() == "rarity"), "")
        rest = [(k, v) for k, v in fields if k.strip().lower() != "rarity"]
        line = ", ".join(x for x in (subtitle, rarity.lower() if rarity else "") if x)
        add(f'<div class="statblock sb-card sb-item" role="group" aria-label="{label}">')
        add(f'<div class="sb-name">{inline_md(n["name"])}</div>')
        if line:
            add(f'<div class="sb-rarity"><em>{inline_md(line)}</em></div>')
        add(rule)
        for k, v in rest:
            add(f'<p class="sb-prop"><strong>{inline_md(k)}</strong> {inline_md(v)}</p>')
        if sections and rest:
            add(rule)
        add("".join(sections_html()) + src + "</div>")
    return "```{=html}\n" + "\n".join(out) + "\n```\n"


def infobox(n, nodes, out_e, in_e, events_of, prog, statblocks=None):
    rows = [("Type", n["type"])]
    if years(n):
        rows.append(("Years", years(n)))
    if "record" in n:
        rows.append(("Status", "Historical record" if n["record"] else "Saga invention"))
    for k, lab in (("incantation", "Incantation"), ("zenith", "Zenith"), ("family", "Family")):
        if n.get(k):
            rows.append((lab, f"*{n[k]}*" if k == "incantation" else n[k]))
    if n["type"] == "force":
        rows.append(("Origin", "Native (face of a god)" if n.get("native") else "Egregore (fed by institutions)"))
    if n.get("book") and n["book"] in nodes:
        rows.append(("Book", link(nodes[n["book"]])))
    if n.get("chapters"):
        rows.append(("Chapters", ", ".join(str(c) for c in n["chapters"])))
    if n.get("note"):
        rows.append(("Note", n["note"]))
    out = book_banner(n) if n["type"] == "book" else []
    out += ["::: {.infobox}", "", "::: {.infobox-title}", n["name"], ":::", ""]
    img = entity_image(n)
    if img:
        alt = n["name"].replace('"', "'")
        cap = f"{n['name']} · {n['type']}"
        cred = image_credits().get(n["id"])
        if cred:                                    # Wikimedia stand-in: CC BY / BY-SA require attribution
            cap += f" — {credit_line(cred)}"
        out += [f"![{cap}](../{img}){{.infobox-img fig-alt=\"{alt}\"}}", ""]
    out += ["| | |", "|---|---|"]
    out += [f"| **{k}** | {v.replace('|', '/')} |" for k, v in rows]
    out += ["", ":::", ""]
    sb = (statblocks or {}).get(n["id"])
    block = statblock_html(n, sb) if sb else ""

    groups = defaultdict(list)
    for e in out_e.get(n["id"], []):
        lab = LABEL[e["type"]][0]
        extra = f" — tier {e['tier']}" if "tier" in e else ""
        extra += f" — {e['kind']}, {e['outcome']}" if e["type"] == "antagonist_of" else ""
        groups[lab].append(f"{link(nodes[e['t']])}{edge_years(e)}{extra}" + (f" — *{e['note']}*" if e.get("note") else ""))
    for e in in_e.get(n["id"], []):
        o, i = LABEL[e["type"]]
        lab = i or o
        extra = f" — tier {e['tier']}" if "tier" in e else ""
        extra += f" — {e['kind']}, {e['outcome']}" if e["type"] == "antagonist_of" else ""
        groups[lab].append(f"{link(nodes[e['s']])}{edge_years(e)}{extra}" + (f" — *{e['note']}*" if e.get("note") else ""))
    if groups:
        out += ["## Relations", ""]
        for lab in sorted(groups):
            out.append(f"**{lab}:** " + " · ".join(sorted(set(groups[lab]))))
            out.append("")
    # stat block after the relations, so relations flow beside the floated infobox
    if block:
        out += [block]

    evs = sorted(events_of.get(n["id"], []), key=lambda ev: (ev["year"], ev.get("date", "")))
    if evs and n["type"] != "event":
        out += ["## Timeline", "", "| Year | Event | Book |", "|---|---|---|"]
        for ev in evs:
            b = nodes.get(ev.get("book"))
            out.append(f"| {ev.get('date') or ev['year']} | {link(ev)} | {b['name'] if b else ''} |")
        out.append("")

    if n["id"] == "vytautas" and prog.get("vytautas_forms"):
        out += ["## Forms (arc stages)", "", "| Form | Years | Ends with |", "|---|---|---|"]
        for f in prog["vytautas_forms"]:
            ev = nodes.get(f["ends_with"])
            out.append(f"| {f['form']} | {f['from']}–{f['to']} | {link(ev) if ev else ''} |")
        out.append("")
    if n["id"] == "pebble" and prog.get("pebble_state"):
        out += ["## State over time", "", "| Year | Ch. | State | Why |", "|---|---|---|---|"]
        for r in prog["pebble_state"]:
            out.append(f"| {r['year']} | {r.get('chapter', '')} | {r['state']} | {r.get('why', '')} |")
        out.append("")
    if n["id"] == "silent_pact" and prog.get("silent_pact_state"):
        out += ["## State over time", "", "| Year | State | Why |", "|---|---|---|"]
        for r in prog["silent_pact_state"]:
            out.append(f"| {r['year']} | {r['state']} | {r.get('why', '')} |")
        out.append("")

    # 1-hop ego graph
    nb = out_e.get(n["id"], [])[:20] + in_e.get(n["id"], [])[:20]
    if nb:
        out += ["## Relation graph", "", "```{mermaid}", "graph LR"]
        ids = {n["id"]} | {e["s"] for e in nb} | {e["t"] for e in nb}
        for i in sorted(ids):
            out.append(f'  {i}["{nodes[i]["name"].replace(chr(34), chr(39))}"]')
        for e in nb:
            out.append(f"  {e['s']} -->|{e['type']}| {e['t']}")
        out += [f"  style {n['id']} stroke-width:3px", "```", ""]
    return "\n".join(out)


def ensure_page(n):
    sec = SECTION[n["type"]]
    page = WIKI / sec / f"{n['id']}.qmd"
    if page.exists():
        return False
    tpl = (TEMPLATES / f"{n['type']}.md").read_text(encoding="utf-8")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(tpl.replace("{{name}}", n["name"].replace('"', "'")).replace("{{id}}", n["id"]), encoding="utf-8")
    return True


def write_indexes(nodes):
    by_sec = defaultdict(list)
    for n in nodes.values():
        by_sec[SECTION[n["type"]]].append(n)
    for sec in SECTION_TITLE:
        items = by_sec.get(sec, [])
        (WIKI / sec).mkdir(parents=True, exist_ok=True)
        lines = ["---", f'title: "{SECTION_TITLE[sec]}"', "---", ""]
        if not items:
            lines.append("*No entries yet. Add nodes of this type to `world_rules/graph/world_graph.json`.*")
        lines += ["", "| Name | Type | Years |", "|---|---|---|"]
        key = (lambda x: (x.get("year") or 0)) if sec == "events" else (lambda x: x["name"])
        for n in sorted(items, key=key):
            lines.append(f"| [{n['name']}]({n['id']}.qmd) | {n['type']} | {years(n)} |")
        (WIKI / sec / "index.qmd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_timeline(nodes):
    evs = sorted((n for n in nodes.values() if n["type"] == "event"), key=lambda e: (e["year"], e.get("date", "")))
    lines = ["---", 'title: "Timeline"', "---", "",
             "*Generated from the world graph. ✦ = historical record, ◇ = saga invention.*", "",
             "| Date | | Event | Book |", "|---|---|---|---|"]
    for e in evs:
        b = nodes.get(e.get("book"))
        mark = "✦" if e.get("record") else "◇"
        lines.append(f"| {e.get('date') or e['year']} | {mark} | [{e['name']}](events/{e['id']}.qmd) | {b['name'] if b else ''} |")
    (WIKI / "timeline.qmd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_image_credits(nodes):
    """wiki/image-credits.qmd: every Wikimedia-sourced image with author, licence and file page."""
    credits = image_credits()
    lines = ["---", 'title: "Image credits"', "---", "",
             "Until the saga has its own AI-generated art, many entries use **freely licensed images from "
             "Wikipedia and Wikimedia Commons** as stand-ins: period seals, manuscript miniatures, historical "
             "paintings, heraldry and photographs of the real places. Each credit below links to the Commons "
             "file page, which carries the full author and licence details. Entries without a credit here "
             "(e.g. Vytautas, Jogaila, Birutė, Perkūnas, Trakai, the Pebble, the book covers) use the saga's own "
             "AI-generated art.", "",
             "Fetched with `scripts/fetch_wiki_images.py` (mapping in `scripts/wiki_image_map.json`); only Public domain, "
             "CC0, CC BY and CC BY-SA files are accepted. Pictures are downscaled copies.", ""]
    by_sec = defaultdict(list)
    for i, c in credits.items():
        if i in nodes:
            by_sec[SECTION[nodes[i]["type"]]].append((nodes[i], c))
    n_total = sum(len(v) for v in by_sec.values())
    lines += [f"**{n_total} credited images.**", ""]
    for sec in SECTION_TITLE:
        rows = sorted(by_sec.get(sec, []), key=lambda x: x[0]["name"])
        if not rows:
            continue
        lines += [f"## {SECTION_TITLE[sec]}", "", "| Entry | Image | Author | Licence |", "|---|---|---|---|"]
        for n, c in rows:
            artist = (c.get("artist") or "Unknown author").replace("|", "/")
            lic = c.get("license", "")
            lic = f"[{lic}]({c['license_url']})" if c.get("license_url") else lic
            title = c["title"].replace("|", "/").replace("[", "(").replace("]", ")")
            lines.append(f"| [{n['name']}]({sec}/{n['id']}.qmd) | [{title}]({md_url(c['page'])}) | {artist} | {lic} |")
        lines.append("")
    (WIKI / "image-credits.qmd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_codex():
    if CODEX.exists():
        shutil.rmtree(CODEX)
    CODEX.mkdir(parents=True)
    listed = []
    for rel, title in CODEX_DOCS:
        src = ROOT / rel
        if not src.exists():
            continue
        body = src.read_text(encoding="utf-8")
        body = re.sub(r"^# .*\n", "", body, count=1)          # title comes from front matter
        body = body.replace("```mermaid", "```{mermaid}")      # render diagrams in Quarto
        body = body.replace("{{<", "{{</* ").replace(">}}", " */>}}") if "{{<" in body else body
        name = slug(title) + ".qmd"
        (CODEX / name).write_text(f'---\ntitle: "{title}"\n---\n\n*Source: `{rel}`*\n\n{body}', encoding="utf-8")
        listed.append((title, name))
    idx = ["---", 'title: "Codex"', "---", "", "The world bible, rendered from the source docs.", ""]
    idx += [f"- [{t}]({n})" for t, n in listed]
    (CODEX / "index.qmd").write_text("\n".join(idx) + "\n", encoding="utf-8")
    return listed


def write_explorer(data, out_html: Path, standalone: bool):
    """Inject the graph into the explorer template (an interactive year-scrubbed atlas)."""
    tpl = (ROOT / "world_rules" / "graph" / "explorer_template.html").read_text(encoding="utf-8")
    page = tpl.replace("/*__GRAPH__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if standalone:
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                "<style>body{margin:0}[hidden]{display:none!important}</style></head><body>" + page + "</body></html>")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explorer-out", help="also write a skeleton-less explorer page here (for publishing as an artifact)")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    edges, prog = data["edges"], data.get("progressions", {})
    if args.clean and GEN.exists():
        shutil.rmtree(GEN)
    GEN.mkdir(parents=True, exist_ok=True)

    out_e, in_e, events_of = defaultdict(list), defaultdict(list), defaultdict(list)
    for e in edges:
        if LABEL[e["type"]][1] is None and e["s"] > e["t"]:
            pass
        out_e[e["s"]].append(e)
        in_e[e["t"]].append(e)
        s, t = nodes[e["s"]], nodes[e["t"]]
        if e["type"] == "participant" and t["type"] == "event":
            events_of[s["id"]].append(t)
        if e["type"] == "occurs_at" and s["type"] == "event":
            events_of[t["id"]].append(s)

    statblocks = load_statblocks()
    for sid in statblocks:
        if sid not in nodes:
            print(f"warning: statblocks.json has an entry for unknown node id {sid!r}; ignored", file=sys.stderr)
    created = 0
    for n in nodes.values():
        created += ensure_page(n)
        (GEN / f"{n['id']}.md").write_text(infobox(n, nodes, out_e, in_e, events_of, prog, statblocks), encoding="utf-8")
    write_indexes(nodes)
    write_timeline(nodes)
    write_image_credits(nodes)
    listed = write_codex()
    write_explorer(data, WIKI / "graph-explorer.html", standalone=True)
    if args.explorer_out:
        write_explorer(data, Path(args.explorer_out), standalone=False)
    n_sb = sum(1 for i in statblocks if i in nodes)
    print(f"wiki: {len(nodes)} entities ({created} new pages from templates), {len(listed)} codex docs, {n_sb} stat blocks")


if __name__ == "__main__":
    main()
