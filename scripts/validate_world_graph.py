#!/usr/bin/env python3
"""Validate the saga's world graph and generate per-book relation maps.

Usage:
    python3 scripts/validate_world_graph.py            # validate + write Mermaid maps
    python3 scripts/validate_world_graph.py --check    # validate only (CI); exit 1 on errors

Checks are listed in CHECKS below; each returns (errors, warnings).
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "world_rules" / "graph" / "world_graph.json"
OUT_DIR = ROOT / "world_rules" / "graph"

LIVING_TYPES = {"character"}
TIMELESS_TYPES = {"god", "force", "school", "element", "faction", "place"}


def load():
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    return data, nodes, data["edges"], data.get("progressions", {})


def span(node):
    """Active year range of a node, or None if timeless."""
    t = node["type"]
    if t == "character":
        return node.get("born"), node.get("died")
    if t in ("book", "pact"):
        return node.get("start"), node.get("end")
    if t == "event":
        return node.get("year"), node.get("year")
    if t == "artifact":
        return node.get("created"), None
    return None


def edge_span(e, nodes):
    """Explicit from/to win; otherwise the overlap of both endpoints' spans."""
    los, his = [], []
    for nid in (e["s"], e["t"]):
        sp = span(nodes[nid])
        if not sp:
            continue
        a, b = sp
        if a is not None:
            los.append(a)
        if b is not None:
            his.append(b)
    lo = e["from"] if e.get("from") is not None else (max(los) if los else None)
    hi = e["to"] if e.get("to") is not None else (min(his) if his else None)
    return lo, hi


# ---------------------------------------------------------------- checks

def check_ids_and_types(data, nodes, edges, prog):
    errs, warns = [], []
    seen = set()
    for n in data["nodes"]:
        if n["id"] in seen:
            errs.append(f"duplicate node id: {n['id']}")
        seen.add(n["id"])
        if n["type"] not in data["meta"]["node_types"]:
            errs.append(f"{n['id']}: unknown node type {n['type']}")
    valid_edges = {t for group in data["meta"]["edge_types"].values() for t in group}
    for i, e in enumerate(edges):
        for k in ("s", "t"):
            if e[k] not in nodes:
                errs.append(f"edge #{i} {e['s']}-{e['type']}->{e['t']}: unknown node '{e[k]}'")
        if e["type"] not in valid_edges:
            errs.append(f"edge #{i}: unknown edge type {e['type']}")
    return errs, warns


def check_lifespans(data, nodes, edges, prog):
    """Explicit edge years must fall inside living endpoints' lifespans (±2y for approx)."""
    errs, warns = [], []
    for e in edges:
        if e["s"] not in nodes or e["t"] not in nodes:
            continue
        for nid in (e["s"], e["t"]):
            n = nodes[nid]
            if n["type"] not in LIVING_TYPES:
                continue
            born, died = n.get("born"), n.get("died")
            slack = 2 if n.get("approx") else 0
            dslack = 0 if n.get("died_exact") else slack
            for key in ("from", "to"):
                y = e.get(key)
                if y is None:
                    continue
                if born and y < born - slack:
                    errs.append(f"{e['s']} -{e['type']}-> {e['t']}: {key}={y} before {nid} born {born}")
                if died and y > died + dslack and e["type"] not in ("holds",):
                    errs.append(f"{e['s']} -{e['type']}-> {e['t']}: {key}={y} after {nid} died {died}")
        if e.get("from") and e.get("to") and e["from"] > e["to"]:
            errs.append(f"{e['s']} -{e['type']}-> {e['t']}: from {e['from']} > to {e['to']}")
    return errs, warns


def check_event_participants(data, nodes, edges, prog):
    errs, warns = [], []
    for e in edges:
        if e["type"] != "participant":
            continue
        who, ev = nodes.get(e["s"]), nodes.get(e["t"])
        if not who or not ev or ev["type"] != "event" or who["type"] != "character":
            continue
        y = ev["year"]
        slack = 2 if who.get("approx") else 0
        dslack = 0 if who.get("died_exact") else slack
        if who.get("born") and y < who["born"] - slack:
            errs.append(f"{who['id']} participates in {ev['id']} ({y}) before birth {who['born']}")
        dead_ok = e.get("note", "").lower().startswith("via")
        if who.get("died") and y > who["died"] + dslack and not dead_ok:
            errs.append(f"{who['id']} participates in {ev['id']} ({y}) after death {who['died']}")
    return errs, warns


def check_causality(data, nodes, edges, prog):
    errs, warns = [], []
    for e in edges:
        if e["type"] not in ("causes", "breaks", "ends"):
            continue
        a, b = nodes.get(e["s"]), nodes.get(e["t"])
        if not a or not b:
            continue
        ya = a.get("year")
        yb = b.get("year") or b.get("start") or b.get("created")
        if ya is not None and yb is not None and ya > yb and e["type"] == "causes":
            errs.append(f"causality: {a['id']} ({ya}) causes {b['id']} ({yb}) — effect before cause")
        if e["type"] in ("breaks", "ends") and b["type"] == "pact":
            if ya is not None and b.get("start") and ya < b["start"]:
                errs.append(f"{a['id']} ({ya}) {e['type']} {b['id']} before it exists ({b['start']})")
    return errs, warns


def check_books(data, nodes, edges, prog):
    errs, warns = [], []
    for b in (n for n in nodes.values() if n["type"] == "book"):
        prot = [e for e in edges if e["t"] == b["id"] and e["type"] == "protagonist_of"]
        ant = [e for e in edges if e["t"] == b["id"] and e["type"] == "antagonist_of"]
        if len(prot) != 1:
            errs.append(f"{b['id']}: needs exactly one protagonist (has {len(prot)})")
        kinds = {e.get("kind") for e in ant}
        for k in ("mortal", "mythic"):
            if k not in kinds:
                errs.append(f"{b['id']}: missing a {k} antagonist")
        for e in ant:
            if "outcome" not in e:
                warns.append(f"{b['id']}: antagonist {e['s']} has no outcome")
            who = nodes[e["s"]]
            if who["type"] == "character":
                lo, hi = who.get("born"), who.get("died")
                if (hi and hi < b["start"]) or (lo and lo > b["end"]):
                    errs.append(f"{b['id']}: antagonist {who['id']} not alive during {b['start']}-{b['end']}")
        for e in prot:
            who = nodes[e["s"]]
            if who.get("died") and who["died"] < b["start"]:
                errs.append(f"{b['id']}: protagonist {who['id']} dead before book starts")
    return errs, warns


def check_forces(data, nodes, edges, prog):
    errs, warns = [], []
    for f in (n for n in nodes.values() if n["type"] == "force"):
        out = {e["type"] for e in edges if e["s"] == f["id"]}
        if f.get("native"):
            if not out & {"face_of", "shard_of"}:
                errs.append(f"{f['id']}: native Force must be face_of/shard_of a god")
        else:
            if "egregore_fed_by" not in out:
                errs.append(f"{f['id']}: foreign Force must be egregore_fed_by an institution")
    return errs, warns


def check_magic(data, nodes, edges, prog):
    errs, warns = [], []
    for s in (n for n in nodes.values() if n["type"] == "school"):
        touching = [e for e in edges if s["id"] in (e["s"], e["t"])]
        if not touching:
            errs.append(f"school {s['id']} is disconnected")
        if s.get("family") == "granted" and not any(e["t"] == s["id"] and e["type"] == "patron_of" for e in edges):
            errs.append(f"granted school {s['id']} has no patron Force")
    for e in edges:
        if e["type"] == "practises":
            tier = e.get("tier")
            if tier is None or not 0 <= tier <= 5:
                errs.append(f"{e['s']} practises {e['t']}: tier must be 0..5")
            if nodes[e["t"]].get("family") == "bought" and tier not in (0, None):
                warns.append(f"{e['s']}: bought power should be tier 0 (no craft)")
    for el in (n for n in nodes.values() if n["type"] == "element"):
        if not any(e["t"] == el["id"] and e["type"] == "element_of" for e in edges):
            errs.append(f"element {el['id']} has no deity")
    # decline after the Pact ends
    rows = sorted(prog.get("practitioners", []), key=lambda r: r["year"])
    for a, b in zip(rows, rows[1:]):
        for k in ("tier4", "tier3", "tier2"):
            if b[k] > a[k]:
                errs.append(f"practitioners: {k} rises {a['year']}→{b['year']} ({a[k]}→{b[k]}); magic must decline")
    lv = sorted(prog.get("unbinding_level", []), key=lambda r: r["year"])
    for a, b in zip(lv, lv[1:]):
        if b["level"] < a["level"]:
            errs.append(f"unbinding_level falls {a['year']}→{b['year']}")
    st = sorted(prog.get("hene_stones", []), key=lambda r: r["year"])
    for a, b in zip(st, st[1:]):
        if b["stones"] > a["stones"]:
            errs.append(f"hene_stones increases {a['year']}→{b['year']}")
    return errs, warns


def check_artifacts(data, nodes, edges, prog):
    errs, warns = [], []
    for a in (n for n in nodes.values() if n["type"] == "artifact"):
        if not any(e["s"] == a["id"] and e["type"] == "created_by" for e in edges):
            warns.append(f"artifact {a['id']} has no created_by")
        holds = sorted(
            (e for e in edges if e["t"] == a["id"] and e["type"] == "holds"),
            key=lambda e: edge_span(e, nodes)[0] or 0,
        )
        for x, y in zip(holds, holds[1:]):
            xs, ys = edge_span(x, nodes), edge_span(y, nodes)
            if xs[1] is not None and ys[0] is not None and ys[0] < xs[1]:
                errs.append(f"artifact {a['id']}: held by {x['s']} ({xs[0]}-{xs[1]}) and {y['s']} ({ys[0]}-{ys[1]}) at once")
            if xs[1] is not None and ys[0] is not None and ys[0] - xs[1] > 5:
                warns.append(f"artifact {a['id']}: gap {xs[1]}→{ys[0]} with no holder (where is it?)")
        created = a.get("created")
        for e in holds:
            lo, _ = edge_span(e, nodes)
            if created and lo and lo < created:
                errs.append(f"artifact {a['id']} held by {e['s']} in {lo} before creation {created}")
    return errs, warns


def check_forms(data, nodes, edges, prog):
    errs, warns = [], []
    forms = prog.get("vytautas_forms", [])
    for a, b in zip(forms, forms[1:]):
        if b["from"] < a["to"]:
            errs.append(f"vytautas_forms overlap: {a['form']} → {b['form']}")
        if b["from"] - a["to"] > 1:
            errs.append(f"vytautas_forms gap: {a['form']} ends {a['to']}, {b['form']} starts {b['from']}")
    for f in forms:
        ev = nodes.get(f.get("ends_with"))
        if not ev:
            errs.append(f"form {f['form']}: ends_with unknown event")
        elif not (f["from"] <= ev["year"] <= f["to"] + 1):
            errs.append(f"form {f['form']} ({f['from']}-{f['to']}) ends with {ev['id']} in {ev['year']}")
    return errs, warns


def check_orphans(data, nodes, edges, prog):
    errs, warns = [], []
    linked = {e["s"] for e in edges} | {e["t"] for e in edges}
    for nid, n in nodes.items():
        if nid not in linked and n["type"] != "book":
            warns.append(f"orphan node (no edges): {nid}")
    for ev in (n for n in nodes.values() if n["type"] == "event"):
        if not any(e["s"] == ev["id"] and e["type"] == "occurs_at" for e in edges):
            warns.append(f"event {ev['id']} has no place")
        if ev.get("book") and ev["book"] in nodes:
            b = nodes[ev["book"]]
            if not b["start"] <= ev["year"] <= b["end"]:
                errs.append(f"event {ev['id']} ({ev['year']}) outside its book {b['id']} ({b['start']}-{b['end']})")
    return errs, warns


CHECKS = [
    check_ids_and_types, check_lifespans, check_event_participants, check_causality,
    check_books, check_forces, check_magic, check_artifacts, check_forms, check_orphans,
]

# ---------------------------------------------------------------- mermaid

STYLE = {
    "character": ":::char", "force": ":::force", "god": ":::god", "artifact": ":::art",
    "faction": ":::fac", "pact": ":::pact", "school": ":::school", "element": ":::school",
}
SHOW_EDGES = {
    "parent_of", "spouse_of", "enemy_of", "ally_of", "vassal_of", "hostage_of", "rules",
    "vessel_of", "mask_of", "claims", "bargain_with", "servant_of", "surety_for", "holds",
    "binds", "patron_of", "face_of", "shard_of", "egregore_fed_by",
}


def active(e, nodes, lo, hi):
    a, b = edge_span(e, nodes)
    return (a is None or a <= hi) and (b is None or b >= lo)


def mermaid_for(book, nodes, edges):
    lo, hi = book["start"], book["end"]
    sel = [e for e in edges if e["type"] in SHOW_EDGES and active(e, nodes, lo, hi)]
    keep = set()
    for e in sel:
        for nid in (e["s"], e["t"]):
            n = nodes[nid]
            sp = span(n)
            if n["type"] == "character" and sp and ((sp[1] and sp[1] < lo) or (sp[0] and sp[0] > hi)):
                break
        else:
            keep.add(e["s"])
            keep.add(e["t"])
    sel = [e for e in sel if e["s"] in keep and e["t"] in keep]
    lines = ["```mermaid", "graph LR"]
    for nid in sorted(keep):
        n = nodes[nid]
        label = n["name"].replace('"', "'")
        lines.append(f'  {nid}["{label}"]{STYLE.get(n["type"], "")}')
    for e in sel:
        arrow = "-.->" if e["type"] in {"claims", "bargain_with", "mask_of", "patron_of", "egregore_fed_by"} else "-->"
        if e["type"] == "enemy_of":
            arrow = "--x"
        lines.append(f"  {e['s']} {arrow}|{e['type']}| {e['t']}")
    lines += [
        "  classDef char fill:#f3efe6,stroke:#6b5b3e,color:#222",
        "  classDef force fill:#2d2a3e,stroke:#a08cff,color:#fff",
        "  classDef god fill:#1f3b4d,stroke:#7fc8f8,color:#fff",
        "  classDef art fill:#f9d77e,stroke:#a8741a,color:#222",
        "  classDef fac fill:#e2e8f0,stroke:#475569,color:#222",
        "  classDef pact fill:#7f1d1d,stroke:#fca5a5,color:#fff",
        "  classDef school fill:#14532d,stroke:#86efac,color:#fff",
        "```",
    ]
    return "\n".join(lines), len(keep), len(sel)


def write_maps(nodes, edges, prog):
    books = sorted((n for n in nodes.values() if n["type"] == "book"), key=lambda b: b["start"])
    parts = [
        "# Relation Maps by Book",
        "",
        "*Generated by `scripts/validate_world_graph.py` from `world_graph.json`. Do not edit by hand.*",
        "",
    ]
    for b in books:
        diagram, nn, ne = mermaid_for(b, nodes, edges)
        parts += [f"## {b['name']} ({b['start']}–{b['end']})", "", f"{nn} nodes · {ne} relations", "", diagram, ""]
    parts += ["## Progressions", ""]
    for key, rows in prog.items():
        parts.append(f"### {key}")
        parts.append("")
        cols = list(rows[0].keys())
        parts.append("| " + " | ".join(cols) + " |")
        parts.append("|" + "---|" * len(cols))
        for r in rows:
            parts.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
        parts.append("")
    (OUT_DIR / "relation_maps.md").write_text("\n".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only, no file output")
    args = ap.parse_args()
    data, nodes, edges, prog = load()
    all_e, all_w = [], []
    for chk in CHECKS:
        e, w = chk(data, nodes, edges, prog)
        all_e += [f"[{chk.__name__[6:]}] {x}" for x in e]
        all_w += [f"[{chk.__name__[6:]}] {x}" for x in w]
    print(f"World graph: {len(nodes)} nodes, {len(edges)} edges")
    for w in all_w:
        print("  warn  ", w)
    for e in all_e:
        print("  ERROR ", e)
    print(f"{len(all_e)} errors, {len(all_w)} warnings")
    if not args.check:
        write_maps(nodes, edges, prog)
        print(f"wrote {OUT_DIR.relative_to(ROOT)}/relation_maps.md")
    sys.exit(1 if all_e else 0)


if __name__ == "__main__":
    main()
