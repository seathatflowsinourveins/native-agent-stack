#!/usr/bin/env python3
"""Post-hoc enumeration of Context Mode files touched during the c4 reruns (fix round 2).

Usage: ctxmode_window.py RUNS_DIR
Inputs: the name listing taken before c4-t1 (ctxmode-before-names.txt, 03:31:35Z)
and after c4-t3 (ctxmode-after-names.txt, 03:35:03Z), plus a read-only mtime scan
of ~/.codex/context-mode for 03:31:30-03:38:00Z (covers c4-t1-root, which ran after
the second listing). Stats files record their own pid and time window, so each
is listed with the worker runs whose interval contains its updated_at.
Limits: a file written in the window and rewritten later has a later mtime and is
missed; name listings cannot see content changes to existing files.
Writes RUNS_DIR/ctxmode-c4-window.json.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path(sys.argv[1])
ROOT = Path.home() / ".codex/context-mode"
START = datetime(2026, 9, 23, 3, 31, 30, tzinfo=timezone.utc).timestamp()
END = datetime(2026, 9, 23, 3, 38, 0, tzinfo=timezone.utc).timestamp()
RUN_FILES = ("c4-t1.json", "c4-t2.json", "c4-t3.json", "c4-t1-root.json")


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def names(path: Path) -> set[str]:
    # The listings hold `ls -a` names plus `ls -s` total-block lines (digits only); both are dropped.
    return {ln.strip() for ln in path.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith(".") and not ln.strip().isdigit()}


def main() -> int:
    rec: dict = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "window_utc": [iso(START), iso(END)]}
    before, after = names(RUNS / "ctxmode-before-names.txt"), names(RUNS / "ctxmode-after-names.txt")
    rec["name_listing_03_31_35Z_to_03_35_03Z"] = {"added": sorted(after - before), "removed": sorted(before - after)}
    runs = {n: (RUNS / n).stat().st_mtime for n in RUN_FILES}
    rec["run_receipt_written_at"] = {n: iso(t) for n, t in runs.items()}
    # Each run's interval: from the previous receipt (c4-inspect.json for the first) to its own.
    starts = [(RUNS / "c4-inspect.json").stat().st_mtime] + [runs[n] for n in RUN_FILES[:-1]]
    intervals = {n: (s, runs[n]) for n, s in zip(RUN_FILES, starts)}
    mcp_calls = {n: sum(1 for i in json.loads((RUNS / n).read_text()).get("items", []) if i.get("type") == "mcpToolCall")
                 for n in RUN_FILES}
    rec["receipt_mcp_tool_calls"] = mcp_calls
    touched = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and START <= p.stat().st_mtime <= END:
            row = {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "mtime": iso(p.stat().st_mtime)}
            if p.name.startswith("stats-pid-"):
                s = json.loads(p.read_text())
                row["stats"] = {k: s.get(k) for k in ("session_start", "updated_at", "uptime_ms", "total_calls",
                                                      "bytes_indexed", "by_tool")}
                upd = (s.get("updated_at") or 0) / 1000
                row["candidate_runs_by_interval"] = [n for n, (a, b) in intervals.items() if a < upd <= b]
            touched.append(row)
    rec["mtime_window_files"] = touched
    (RUNS / "ctxmode-c4-window.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({"files": len(touched), "candidates": [t.get("candidate_runs_by_interval") for t in touched]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
