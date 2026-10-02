#!/usr/bin/env python3
"""Combine the three GPT samples with the Claude record per foundation layer, by RULE.md.

G1 = pull request 595's selection-gpt.json (read from git), G2/G3 = the two orders of the Sol-ultra round (last.json per
layer), C = the merged definitive manifest's defaults. Prints one line per layer and writes combined.json.
Usage: combine.py <repo checkout> <blind-run folder> <output folder> [<git ref of the peer's selection>]
"""
import json
import pathlib
import subprocess
import sys

repo, blind, out = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
ref = sys.argv[4] if len(sys.argv) > 4 else "pr/595"


def show(spec):
    return json.loads(subprocess.run(["git", "-C", repo, "show", spec], capture_output=True, text=True, check=True).stdout)


def norm(url):
    u = (url or "").strip().lower().rstrip("/")
    if "github.com/" in u:
        return "/".join(u.split("github.com/")[1].split("/")[:2])
    return u


manifest = show("origin/main:evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
g1 = show(f"{ref}:evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/selection-gpt.json")
C, KEEP = {}, {}
for s in manifest["slots"]:
    if s["catalog"] != "foundation":
        continue
    lid = s["layer_id"]
    C.setdefault(lid, {})
    for one in (s.get("repository") or "").split(";"):
        if norm(one):
            C[lid][norm(one)] = s
    if s.get("state") in ("measurement", "split") or s["row_kind"] in ("pinned", "project_practice"):
        KEEP.setdefault(lid, []).append(s["slot_id"])
G1 = {L["layer_id"]: {norm(p.get("repository")) or p.get("name", "").lower() for p in L.get("picks", [])} for L in g1["layers"]}


def order(n, lid):
    name = lid.replace("cross:", "cross_")
    p = blind / f"order-{n}" / name / "last.json"
    if not p.exists():  # the lane's first memory unit was written as flat files beside the layer folders
        p = blind / f"order-{n}" / f"{name}.last.json"
    if not p.exists():  # the committed copy of the round: order-N/<layer>.json
        p = blind / f"order-{n}" / f"{name}.json"
    if not p.exists() or p.stat().st_size < 3:
        return None
    try:
        d = json.loads(p.read_text())
    except ValueError:
        return None
    picks = set()
    for L in d.get("layers", []):
        for x in L.get("selection", []):
            picks.add(norm(x.get("repository")) or (x.get("name") or "").lower())
    return picks


# RULE.md, amendment 1: on these layers G1 saw instructions naming candidates (pull request 595's own record), so it is
# not counted and both orders of the Sol-ultra round must agree.
G1_NOT_COUNTED = {"semantic-rag", "document-retrieval", "web-research", "durable-memory", "token-efficiency",
                  "code-navigation", "quality-evaluation"}

rows = []
for lid in [L["layer_id"] for L in manifest["layers"] if L["catalog"] == "foundation"]:
    g = [None if lid in G1_NOT_COUNTED else G1.get(lid), order(1, lid), order(2, lid)]
    have = [x for x in g if x is not None]
    c = set(C.get(lid, {}))
    every = set().union(c, *have) if have else c
    final, claude_only, gpt_only, other = [], [], [], []
    for r in sorted(every):
        votes = sum(1 for x in have if r in x)
        if r in c and votes >= 2:
            final.append(r)
        elif r in c:
            claude_only.append((r, votes))
        elif votes >= 2:
            gpt_only.append((r, votes))
        else:
            other.append((r, votes))
    rows.append({"layer_id": lid, "gpt_samples_present": len(have), "g1_counted": lid not in G1_NOT_COUNTED,
                 "orders_present": sum(1 for x in g[1:] if x is not None), "final": final, "claude_only": claude_only,
                 "gpt_only": gpt_only, "single_gpt_votes": other, "untouched_slots": KEEP.get(lid, [])})
out.mkdir(parents=True, exist_ok=True)
(out / "combined.json").write_text(json.dumps({"rule": "RULE.md", "rows": rows}, indent=1))
tot = {"final": 0, "claude_only": 0, "gpt_only": 0}
for r in rows:
    for k in tot:
        tot[k] += len(r[k])
    n = r["gpt_samples_present"]
    line = f"{r['layer_id']} [{n} GPT samples, orders {r['orders_present']}/2] FINAL: {', '.join(r['final']) or '-'}"
    if r["claude_only"]:
        line += " | Claude only: " + ", ".join(f"{a} ({v}/{n})" for a, v in r["claude_only"])
    if r["gpt_only"]:
        line += " | GPT only: " + ", ".join(f"{a} ({v}/{n})" for a, v in r["gpt_only"])
    if r["single_gpt_votes"]:
        line += " | one GPT vote: " + ", ".join(a for a, v in r["single_gpt_votes"] if v)
    if r["untouched_slots"]:
        line += " | untouched: " + ", ".join(r["untouched_slots"])
    print(line)
print("totals:", tot, "| layers with both orders:", sum(1 for r in rows if r["orders_present"] == 2),
      "| layers still waiting for an order:", [r["layer_id"] for r in rows if 0 < r["orders_present"] < 2])
