#!/usr/bin/env python3
"""TTS bench harness for the Wolf Saga audiobook (review section 5.6).

Renders the same passages (pulled from books/1) with every AVAILABLE engine plugin and writes

    samples/<engine>/<lang>/<passage>.wav      loudness-matched to -16 LUFS
    samples/_scripts/<passage>.<lang>.jsonl    the neutral emotion-markup records every engine used
    samples/_blind/<lang>/<passage>/<X>.wav    blind copies + samples/_blind/key.json
    results.json                               machine-readable run log (merged across runs)
    index.html                                 listening page (blind A/B with reveal, scoring inputs)
    scores.csv                                 scoring sheet (existing scores are preserved)

Safety rules
------------
* No network or paid call happens unless you pass --allow-paid (keys engines) or --allow-online
  (free but unofficial web services such as edge-tts). Use --dry-run first: it prints what would run,
  the character counts and a rough cost.
* Keys are read ONLY from environment variables declared by each plugin.
* Local plugins never download models; they skip if the package or weights are absent.
* A failed utterance fails the passage. No partial audio is written.

Examples
--------
    python3 bench.py --list
    python3 bench.py --dry-run
    python3 bench.py --engines edge,say --allow-online
    ELEVENLABS_API_KEY=... python3 bench.py --engines elevenlabs --langs lt --allow-paid
    python3 bench.py --html-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "audiobook"))   # tts_helpers.loudnorm_wav (stdlib-only import)

import numpy as np  # noqa: E402

import audio_utils as au  # noqa: E402
import lexicon_tts as lex  # noqa: E402
import markup as mk  # noqa: E402
from engines import discover  # noqa: E402
from passages import load_passages  # noqa: E402

SAMPLES = HERE / "samples"
CACHE = HERE / "cache"
RESULTS = HERE / "results.json"
SCORES = HERE / "scores.csv"
INDEX = HERE / "index.html"
BENCH_LUFS = -16.0

SCORE_COLUMNS = ["lang", "passage", "engine", "blind_label", "naturalness_1_5", "emotion_fit_1_5",
                 "character_distinctness_1_5", "name_errors_count", "artefacts_count",
                 "skipped_or_repeated_words_yn", "notes"]


# --------------------------------------------------------------------------- helpers

def sha(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, ensure_ascii=False, sort_keys=True).encode("utf8"))
        h.update(b"\x00")
    return h.hexdigest()[:24]


def load_results() -> List[dict]:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text(encoding="utf8"))
    return []


def save_results(rows: List[dict]) -> None:
    RESULTS.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf8")


def upsert(rows: List[dict], row: dict) -> None:
    for i, r in enumerate(rows):
        if (r["engine"], r["lang"], r["passage"]) == (row["engine"], row["lang"], row["passage"]):
            rows[i] = row
            return
    rows.append(row)


def get_records(passage: dict, lang: str) -> List[dict]:
    text = passage["text"][lang]
    recs = mk.markup(text, lang, passage["id"], passage.get("context_names"))
    if not mk.fidelity_ok(text, recs):
        raise RuntimeError("markup fidelity check failed for %s/%s" % (passage["id"], lang))
    mk.write_jsonl(SAMPLES / "_scripts" / ("%s.%s.jsonl" % (passage["id"], lang)), recs)
    return recs


# --------------------------------------------------------------------------- rendering

def render_passage(engine, passage: dict, lang: str, records: List[dict], lexicon_override: Optional[str]) -> dict:
    mode = lex.mode_for(engine.family, lang, lexicon_override)
    out_dir = SAMPLES / engine.id / lang
    out_path = out_dir / (passage["id"] + ".wav")
    row = {"engine": engine.id, "lang": lang, "passage": passage["id"], "lexicon_mode": mode,
           "n_utterances": len(records), "chars": sum(len(r["text"]) for r in records)}
    t0 = time.time()
    parts = []
    cache_dir = CACHE / engine.id
    cache_dir.mkdir(parents=True, exist_ok=True)
    synth_calls = 0
    for utt in records:
        tts_text = lex.render(utt["text"], mode)
        text = engine.prepare_text(utt, lang, tts_text)
        voice = engine.voice_for(utt, lang)
        key = sha(engine.cache_key(), lang, voice, text, utt["emotion"], utt["intensity"])
        cpath = cache_dir / (key + ".wav")
        if cpath.exists():
            audio, sr = au.read_wav(cpath)
        else:
            audio, sr = engine.synth(text, voice, utt, lang)
            audio = au.resample(au.to_mono(audio), sr, au.TARGET_SR)
            audio = au.trim_edges(audio)
            if audio.size < au.TARGET_SR // 20:
                raise RuntimeError("utterance %s produced <50 ms of audio" % utt["id"])
            au.write_wav(cpath, audio)
            sr = au.TARGET_SR
            synth_calls += 1
        parts.append((audio, int(utt["pause_after_ms"])))
    final = au.join(parts)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / (passage["id"] + ".tmp.wav")
    au.write_wav(tmp, final)
    try:
        import tts_helpers
        tts_helpers.loudnorm_wav(tmp, i=BENCH_LUFS)
    except Exception as e:  # loudness matching is important for blind tests: say so loudly
        print("   WARNING: loudness match failed (%s); sample is NOT level-matched" % e)
    tmp.replace(out_path)
    dur = au.duration_s(out_path)
    wall = time.time() - t0
    row.update({"status": "ok", "file": str(out_path.relative_to(HERE)), "duration_s": round(dur, 1),
                "wall_s": round(wall, 1), "synth_calls": synth_calls,
                "rtf": round(wall / dur, 3) if dur and synth_calls else None, "error": ""})
    return row


# --------------------------------------------------------------------------- engine selection

def engine_status(engines: Dict[str, object], args) -> Dict[str, dict]:
    st = {}
    for eid, e in engines.items():
        ok, why = e.available()
        gate = ""
        if ok and e.paid and not args.allow_paid:
            gate = "needs --allow-paid"
        if ok and e.kind == "online-free" and not args.allow_online:
            gate = "needs --allow-online"
        st[eid] = {"available": ok, "reason": why, "gate": gate, "runnable": ok and not gate}
    return st


def print_list(engines, st):
    print("%-14s %-9s %-6s %-34s %s" % ("engine", "kind", "langs", "label", "status"))
    for eid, e in engines.items():
        s = st[eid]
        status = ("READY" if s["runnable"] else ("available, " + s["gate"] if s["available"] else "skip: " + s["reason"]))
        print("%-14s %-9s %-6s %-34s %s" % (eid, e.kind, ",".join(e.langs), e.label[:34], status))


# --------------------------------------------------------------------------- listening page

def assign_blind(results: List[dict], seed: int) -> Dict[str, Dict[str, str]]:
    """Stable blind labels: reuse the saved mapping, append new engines, drop vanished ones."""
    keyfile = SAMPLES / "_blind" / "key.json"
    old = json.loads(keyfile.read_text(encoding="utf8")) if keyfile.exists() else {}
    groups: Dict[str, List[str]] = {}
    for r in results:
        if r.get("status") == "ok":
            groups.setdefault("%s/%s" % (r["lang"], r["passage"]), []).append(r["engine"])
    key: Dict[str, Dict[str, str]] = {}
    for g, engines in groups.items():
        cur = {lab: eng for lab, eng in old.get(g, {}).items() if eng in engines}
        todo = [e for e in engines if e not in cur.values()]
        rnd = random.Random("%s:%s" % (seed, g))
        rnd.shuffle(todo)
        free = [chr(ord("A") + i) for i in range(26) if chr(ord("A") + i) not in cur]
        for lab, eng in zip(free, todo):
            cur[lab] = eng
        key[g] = dict(sorted(cur.items()))
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    keyfile.write_text(json.dumps(key, indent=1), encoding="utf8")
    # blind copies
    root = SAMPLES / "_blind"
    for g, mapping in key.items():
        lang, pid = g.split("/")
        d = root / lang / pid
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.wav"):
            f.unlink()
        for lab, eng in mapping.items():
            shutil.copyfile(SAMPLES / eng / lang / (pid + ".wav"), d / (lab + ".wav"))
    return key


def write_scores(results: List[dict], key: Dict[str, Dict[str, str]]) -> None:
    existing: Dict[tuple, dict] = {}
    if SCORES.exists():
        with open(SCORES, newline="", encoding="utf8") as fh:
            for row in csv.DictReader(fh):
                existing[(row["lang"], row["passage"], row["engine"])] = row
    rows = []
    for g, mapping in sorted(key.items()):
        lang, pid = g.split("/")
        for lab, eng in mapping.items():
            old = existing.get((lang, pid, eng), {})
            row = {c: old.get(c, "") for c in SCORE_COLUMNS}
            row.update({"lang": lang, "passage": pid, "engine": eng, "blind_label": lab})
            rows.append(row)
    with open(SCORES, "w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORE_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def build_index(passages: List[dict], results: List[dict], key: Dict[str, Dict[str, str]], engines) -> None:
    by = {(r["engine"], r["lang"], r["passage"]): r for r in results if r.get("status") == "ok"}
    labels = {eid: e.label for eid, e in engines.items()}
    data = {"key": key, "labels": labels, "criteria": ["naturalness", "emotion fit", "character distinctness",
                                                       "name errors (count)", "artefacts (count)"]}
    sections = {}
    for lang in ("lt", "en"):
        out = []
        for p in passages:
            g = "%s/%s" % (lang, p["id"])
            if g not in key:
                continue
            records = json.loads(json.dumps(mk.markup(p["text"][lang], lang, p["id"], p.get("context_names"))))
            hits = lex.report(p["text"][lang])
            verify = [h["entry"] for h in hits if h["verify"]]
            cards = []
            for lab, eng in key[g].items():
                r = by[(eng, lang, p["id"])]
                meta = "%.0f s audio, wall %.0f s%s, lexicon: %s" % (
                    r["duration_s"], r["wall_s"], (", RTF %.2f" % r["rtf"]) if r.get("rtf") else " (cached)", r["lexicon_mode"])
                cards.append(
                    '<div class="card" data-g="%s" data-label="%s"><div class="ct"><span class="lab">Sample %s</span>'
                    '<span class="eng" hidden> = %s</span></div>'
                    '<audio controls preload="none" data-blind="samples/_blind/%s/%s/%s.wav" data-open="%s"></audio>'
                    '<div class="meta">%s</div><div class="scores">%s</div></div>'
                    % (g, lab, lab, html.escape(labels.get(eng, eng)), lang, p["id"], lab, html.escape(r["file"]), html.escape(meta),
                       "".join('<label>%s <input type="number" min="0" max="%d" step="1" data-k="%s"></label>'
                               % (c, 99 if "count" in c else 5, i) for i, c in enumerate(data["criteria"]))
                       + '<input class="notes" placeholder="notes" data-k="notes">'))
            script = "".join('<div class="u u-%s"><b>%s</b> <i>%s %d</i> %s</div>' % (
                r["kind"], html.escape(r["speaker"]), r["emotion"], r["intensity"], html.escape(r["text"])) for r in records)
            out.append(
                '<section><h3>%s</h3><p class="tests">%s</p>'
                '<details><summary>Text (canonical spelling)</summary><div class="text">%s</div></details>'
                '<details><summary>Emotion markup used (speaker / emotion / intensity per sentence)</summary>%s</details>'
                '<details><summary>Lexicon hits (%d; verify=true: %s)</summary><div class="text">%s</div></details>'
                '<div class="cards">%s</div></section>'
                % (html.escape(p["title"]), html.escape(", ".join(p.get("tests", []))),
                   "<br><br>".join(html.escape(x) for x in p["text"][lang].split("\n\n")), script, len(hits),
                   html.escape(", ".join(verify) or "none"),
                   html.escape("; ".join("%s [%s]%s" % (h["entry"], h["ipa"], " ?" if h["verify"] else "") for h in hits)),
                   "".join(cards)))
        sections[lang] = "\n".join(out) or "<p>No samples rendered for this language yet. Run <code>bench.py</code>.</p>"
    page = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
               .replace("__LT__", sections["lt"]).replace("__EN__", sections["en"]) \
               .replace("__CSVCOLS__", json.dumps(SCORE_COLUMNS))
    INDEX.write_text(page, encoding="utf8")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wolf Saga TTS bench</title>
<style>
:root{--bg:#fafaf7;--fg:#1c1b19;--mut:#6b675f;--card:#fff;--line:#dcd8cf;--acc:#8a5a14}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--fg:#ece9e2;--mut:#9b968b;--card:#211f1c;--line:#3a3731;--acc:#d9a441}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:auto}
h1{margin:.2em 0}h3{margin:1.6em 0 .2em}.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:2}
button,select{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);cursor:pointer}
button.on{border-color:var(--acc);color:var(--acc)}.tests,.meta{color:var(--mut);font-size:.85em;margin:.1em 0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}.lab{font-weight:700;color:var(--acc)}
audio{width:100%;margin:6px 0}.scores{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;font-size:.8em}
.scores input{width:3.2em}.scores .notes{grid-column:1/3;width:auto}
.text,.u{font-size:.9em}.text{border-left:3px solid var(--line);padding:4px 10px;margin:4px 0}.u{padding:1px 0}.u-dialogue{margin-left:1em}.u-divine{margin-left:1em;color:var(--acc)}
summary{cursor:pointer;color:var(--mut);margin-top:4px}[hidden]{display:none!important}
</style></head><body>
<h1>Wolf Saga TTS bench</h1>
<p class="meta">Blind A/B: engine names are hidden and the order is shuffled. All clips are loudness-matched to -16 LUFS. Score each clip, then press Reveal.
Scores are kept in this browser; Download CSV exports them with the real engine names.</p>
<div class="bar">
<button id="tlt" class="on">Lithuanian</button><button id="ten">English</button>
<button id="blind" class="on">Blind mode: on</button><button id="reveal">Reveal engines</button><button id="shuffle">Shuffle order</button>
<button id="csv">Download scores CSV</button><span class="meta" id="msg"></span></div>
<div id="lt">__LT__</div><div id="en" hidden>__EN__</div>
<script>
const D=__DATA__, COLS=__CSVCOLS__;let blind=true;
const $=s=>[...document.querySelectorAll(s)];
function store(k,v){try{if(v===undefined)return localStorage.getItem('wsb:'+k);localStorage.setItem('wsb:'+k,v)}catch(e){}}
function applyMode(){$('audio').forEach(a=>{const t=blind?a.dataset.blind:a.dataset.open;if(!a.getAttribute('src')||!a.getAttribute('src').endsWith(t)){const p=a.paused;a.src=t}});
 $('.card .eng').forEach(e=>e.hidden=blind);$('#blind').textContent='Blind mode: '+(blind?'on':'off');$('#blind').classList.toggle('on',blind)}
$('#blind')[0].onclick=()=>{blind=!blind;applyMode()};
$('#reveal')[0].onclick=()=>{blind=false;applyMode()};
$('#shuffle')[0].onclick=()=>{$('.cards').forEach(c=>{const k=[...c.children];for(let i=k.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[k[i],k[j]]=[k[j],k[i]]}k.forEach(x=>c.appendChild(x))})};
$('#tlt')[0].onclick=()=>{lt.hidden=false;en.hidden=true;tlt.classList.add('on');ten.classList.remove('on')};
$('#ten')[0].onclick=()=>{en.hidden=false;lt.hidden=true;ten.classList.add('on');tlt.classList.remove('on')};
$('.card').forEach(c=>{const g=c.dataset.g,l=c.dataset.label;c.querySelectorAll('input').forEach(i=>{const k=g+'/'+l+'/'+i.dataset.k;const v=store(k);if(v!==null)i.value=v;i.oninput=()=>store(k,i.value)})});
$('#csv')[0].onclick=()=>{const rows=[COLS];const keys=Object.keys(D.key);keys.forEach(g=>{const [lang,pid]=g.split('/');Object.entries(D.key[g]).forEach(([lab,eng])=>{
 const v=i=>store(g+'/'+lab+'/'+i)||'';rows.push([lang,pid,eng,lab,v(0),v(1),v(2),v(3),v(4),'',v('notes')])})});
 const csv=rows.map(r=>r.map(x=>'"'+String(x).replace(/"/g,'""')+'"').join(',')).join('\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='scores.csv';a.click()};
applyMode();
</script></body></html>
"""


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engines", help="comma list (default: every runnable engine)")
    ap.add_argument("--langs", default="lt,en")
    ap.add_argument("--passages", help="comma list of passage ids (default: all)")
    ap.add_argument("--list", action="store_true", help="show engines and availability, then exit")
    ap.add_argument("--dry-run", action="store_true", help="show what would run, with char counts and cost, then exit")
    ap.add_argument("--allow-paid", action="store_true", help="permit calls to paid APIs (keys from env)")
    ap.add_argument("--allow-online", action="store_true", help="permit free unofficial web services (edge-tts)")
    ap.add_argument("--max-chars", type=int, default=20000, help="per-engine character budget guard for paid engines")
    ap.add_argument("--lexicon-mode", help="force one lexicon mode for every engine (none|ipa_slash|ssml_ipa|respell|respell_hy|lt_accent)")
    ap.add_argument("--seed", type=int, default=20261010, help="seed for blind labels")
    ap.add_argument("--html-only", action="store_true", help="rebuild index.html / scores.csv from results.json")
    ap.add_argument("--export-pls", metavar="PATH", help="write the lexicon as a PLS file and exit")
    ap.add_argument("--write-schema", metavar="PATH", help="write the utterance-record JSON schema and exit")
    ap.add_argument("--fail-fast", action="store_true")
    args = ap.parse_args(argv)

    if args.export_pls:
        print("wrote %d PLS rules to %s" % (lex.export_pls(Path(args.export_pls)), args.export_pls))
        return 0
    if args.write_schema:
        Path(args.write_schema).write_text(json.dumps(mk.SCHEMA, indent=1), encoding="utf8")
        return 0

    engines, import_errors = discover()
    for mod, err in import_errors.items():
        print("plugin %s failed to import: %s" % (mod, err))
    st = engine_status(engines, args)
    if args.list:
        print_list(engines, st)
        return 0

    langs = [l for l in args.langs.split(",") if l]
    passages = load_passages(args.passages.split(",") if args.passages else None)
    wanted = args.engines.split(",") if args.engines else None
    if wanted:
        unknown = [w for w in wanted if w not in engines]
        if unknown:
            print("unknown engines: %s (see --list)" % ", ".join(unknown))
            return 2

    results = load_results()
    if not args.html_only:
        plan = []
        for eid, e in engines.items():
            if wanted and eid not in wanted:
                continue
            s = st[eid]
            if not s["runnable"]:
                if wanted:
                    print("SKIP %-12s %s" % (eid, s["reason"] if not s["available"] else s["gate"]))
                continue
            for lang in langs:
                if lang in e.langs:
                    plan.append((e, lang))
        if not plan:
            print("nothing to run. Use --list to see engines; local ones need their model installed, API ones a key + --allow-paid.")
        totals: Dict[str, int] = {}
        for e, lang in plan:
            chars = sum(len(p["text"][lang]) for p in passages)
            totals[e.id] = totals.get(e.id, 0) + chars
        if args.dry_run:
            for e, lang in plan:
                chars = sum(len(p["text"][lang]) for p in passages)
                print("WOULD RUN %-12s %s: %d passages, %d chars, ~US$%.2f%s" % (
                    e.id, lang, len(passages), chars, chars / 1000 * e.cost_per_1k_chars_usd, "  (paid)" if e.paid else ""))
            return 0
        for e, lang in plan:
            if e.paid and totals[e.id] > args.max_chars:
                print("REFUSE %s: %d chars exceeds --max-chars %d" % (e.id, totals[e.id], args.max_chars))
                return 2
        for e, lang in plan:
            for p in passages:
                recs = get_records(p, lang)
                print("[%s/%s] %s ..." % (e.id, lang, p["id"]), end=" ", flush=True)
                try:
                    row = render_passage(e, p, lang, recs, args.lexicon_mode)
                    print("ok %.0fs audio in %.0fs" % (row["duration_s"], row["wall_s"]))
                except Exception as ex:
                    msg = "%s: %s" % (type(ex).__name__, str(ex)[:300])
                    print("FAILED", msg)
                    if args.fail_fast:
                        traceback.print_exc()
                    row = {"engine": e.id, "lang": lang, "passage": p["id"], "status": "error", "error": msg,
                           "lexicon_mode": lex.mode_for(e.family, lang, args.lexicon_mode), "n_utterances": len(recs), "chars": 0}
                upsert(results, row)
                save_results(results)
                if row["status"] == "error" and args.fail_fast:
                    return 1

    ok_rows = [r for r in results if r.get("status") == "ok" and (HERE / r["file"]).exists()]
    key = assign_blind(ok_rows, args.seed)
    write_scores(ok_rows, key)
    build_index(load_passages(), ok_rows, key, engines)
    print("wrote %s (%d samples) and %s" % (INDEX.relative_to(HERE), len(ok_rows), SCORES.relative_to(HERE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
