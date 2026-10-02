#!/usr/bin/env python3
"""Summarize the missing-slot round: per slot, the candidates found and what each judge order selected.
Usage: summarize.py <gap-slots folder> [--json <out>]
"""
import json
import pathlib
import sys
from urllib.parse import urlsplit

root = pathlib.Path(sys.argv[1])
spec = json.loads((root / "gap-slots.json").read_text())


def ident(x):
    """One identity per candidate across orders: owner/name of its repository, else its name without the packet key."""
    url = (x.get("repository") or "").strip().lower().rstrip("/")
    parts = urlsplit(url)
    if parts.netloc in ("github.com", "www.github.com"):
        return "/".join(parts.path.strip("/").split("/")[:2])
    if parts.netloc in ("huggingface.co", "www.huggingface.co"):
        return "hf:" + "/".join(parts.path.strip("/").split("/")[:2])
    if url:
        return url
    name = (x.get("name") or "").strip()
    for sep in (" — ", ": ", " - "):
        head, _, tail = name.partition(sep)
        if tail and head.strip().upper().startswith("C") and head.strip()[1:].isdigit():
            name = tail
    if name.endswith(")") and "(C" in name:
        name = name[: name.rindex("(C")].strip()
    return name.lower()
rows = []
for s in spec["slots"]:
    lid = s["layer_id"]
    disc = root / "discover" / lid / "last.json"
    cands = json.loads(disc.read_text())["candidates"] if disc.exists() and disc.stat().st_size > 2 else None
    picks = {}
    for order in ("order-1", "order-2"):
        p = root / order / lid / "last.json"
        if not p.exists() or p.stat().st_size < 3:
            picks[order] = None
            continue
        try:
            d = json.loads(p.read_text())
        except ValueError:
            picks[order] = "unparseable"
            continue
        sel = []
        for L in d.get("layers", []):
            for x in L.get("selection", []):
                sel.append(ident(x))
        picks[order] = sorted(sel)
    both = [picks[o] for o in ("order-1", "order-2") if isinstance(picks[o], list)]
    agreed = sorted(set(both[0]) & set(both[1])) if len(both) == 2 else None
    rows.append({"slot": lid, "candidates": None if cands is None else len(cands), "order-1": picks["order-1"],
                 "order-2": picks["order-2"], "agreed": agreed,
                 "differ": None if agreed is None else sorted(set(both[0]) ^ set(both[1]))})
for r in rows:
    print(f"{r['slot']}: candidates {r['candidates']} | o1 {r['order-1']} | o2 {r['order-2']}"
          + ("" if r["agreed"] is None else f" | agreed {r['agreed']} | differ {r['differ']}"))
if "--json" in sys.argv:
    pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(rows, indent=1) + "\n")
