"""Load the bench passages: Lithuanian verbatim from the chapters, English from passages_en/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def _lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf8").split("\n")


def load_passages(only: List[str] | None = None) -> List[dict]:
    spec = json.loads((HERE / "passages.json").read_text(encoding="utf8"))["passages"]
    out = []
    for p in spec:
        if only and p["id"] not in only:
            continue
        sources = p["source"] if isinstance(p["source"], list) else [p["source"]]
        line_sets = p["lines"] if isinstance(p["source"], list) else [p["lines"]]
        paras: List[str] = []
        for src, nums in zip(sources, line_sets):
            lines = _lines(REPO_ROOT / src)
            for n in nums:
                text = lines[n - 1].strip()
                if not text:
                    raise ValueError("%s line %d is empty" % (src, n))
                paras.append(text)
        lt = "\n\n".join(paras)
        en_path = HERE / "passages_en" / (p["id"] + ".txt")
        en = en_path.read_text(encoding="utf8").strip() if en_path.exists() else ""
        out.append({**p, "text": {"lt": lt, "en": en}})
    return out


def char_totals(passages: List[dict]) -> Dict[str, int]:
    return {lang: sum(len(p["text"][lang]) for p in passages) for lang in ("lt", "en")}


if __name__ == "__main__":
    ps = load_passages()
    for p in ps:
        print(p["id"], {k: len(v) for k, v in p["text"].items()})
    print(char_totals(ps))
