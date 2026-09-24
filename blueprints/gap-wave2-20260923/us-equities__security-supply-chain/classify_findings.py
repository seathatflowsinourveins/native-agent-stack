#!/usr/bin/env python3
"""Reduce unredacted gitleaks reports (private temp dir) to redacted, classified summaries.

For each finding: rule, file/commit, line, value shape (hex40, hex64 or other with length),
and the number of HEAD-tracked files other than docs/ecosystem/index.html that contain the
exact value (git grep -F -f <private pattern file>, so the value never reaches argv).
Secret values and full matches are never written; the match context keeps only the text
around the value with the value replaced by <SECRET>.
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PRIV, OUT, REPO = (Path(a) for a in sys.argv[1:4])
EXCL = "docs/ecosystem/index.html"


def shape(v: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", v):
        return "hex40"
    if re.fullmatch(r"[0-9a-f]{64}", v):
        return "hex64"
    return f"other(len={len(v)})"


_cache: dict[str, list[str]] = {}


def elsewhere(v: str) -> list[str]:
    if v not in _cache:
        with tempfile.NamedTemporaryFile("w", dir=PRIV, delete=False) as f:
            f.write(v + "\n")
        r = subprocess.run(["git", "-C", str(REPO), "grep", "-l", "-F", "-f", f.name, "HEAD", "--", ".", f":!{EXCL}"],
                           capture_output=True, text=True)
        Path(f.name).unlink()
        _cache[v] = sorted({l.split(":", 1)[1] for l in r.stdout.splitlines() if ":" in l})
    return _cache[v]


def reduce(report: Path) -> dict:
    rows = json.loads(report.read_text() or "[]")
    out = []
    for x in rows:
        v = x.get("Secret", "")
        files = elsewhere(v) if v else []
        out.append({"rule": x["RuleID"], "file": Path(x["File"]).name, "commit": x.get("Commit", "")[:12],
                    "line": x["StartLine"], "shape": shape(v), "other_tracked_files": len(files),
                    "other_tracked_examples": files[:2],
                    "context": (x.get("Match", "").replace(v, "<SECRET>") if v else "")[:120]})
    digest_elsewhere = sum(1 for r in out if r["shape"] in ("hex40", "hex64") and r["other_tracked_files"] > 0)
    return {"report": report.stem, "findings": len(out),
            "by_rule": dict(collections.Counter(r["rule"] for r in out)),
            "by_shape": dict(collections.Counter(r["shape"] for r in out)),
            "digest_shaped_and_in_other_tracked_files": digest_elsewhere,
            "unclassified": [r for r in out if not (r["shape"] in ("hex40", "hex64") and r["other_tracked_files"] > 0)],
            "unique_values": len({(r["shape"], r["context"]) for r in out}),
            "rows": out}


def main() -> None:
    summaries = {p.stem: reduce(p) for p in sorted(PRIV.glob("*.json"))}
    # Controls: report per-file counts and whether the planted value was found (never the value).
    for k in ("merge-control-default", "merge-control-first-parent"):
        if k in summaries:
            for r in summaries[k]["rows"]:
                r["other_tracked_files"] = None; r["other_tracked_examples"] = []
    prev = OUT / "classified.json"
    merged = json.loads(prev.read_text()) if prev.exists() else {}
    merged.update(summaries)
    prev.write_text(json.dumps(merged, indent=1) + "\n")
    for k, s in summaries.items():
        print(k, "findings", s["findings"], "by_rule", s["by_rule"], "by_shape", s["by_shape"],
              "unclassified", len(s["unclassified"]))


if __name__ == "__main__":
    main()
