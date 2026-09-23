#!/usr/bin/env python3
"""Review-2 fix (agent-sdks gap wave 2, round 3): post-hoc top-level listing of the four round-3 staging CODEX_HOMEs.

Evaluates the gap-2 fix criterion "no plugins directory created under the stage home". The 'bare' stage, which
downloaded the provider's remote curated plugins, is the positive control for the detection. The listing is taken
after the runs (dated below); nothing in this unit deletes entries from these homes.
Usage: stage_listing.py OUT
"""
import json
import sys
import time
from pathlib import Path

R3 = Path.home() / ".cache/gap-wave2-20260923/agent-sdks/round3"
rec = {"listed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stages": {}}
for name in ("bare", "events", "ctxmode", "bare-np"):
    home = R3 / name / "codex-home"
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in home.iterdir())
    rec["stages"][name] = {"codex_home": str(home).replace(str(Path.home()), "$HOME"), "entries": entries,
                           "plugins_dir": (home / "plugins").is_dir(),
                           "plugins_dir_mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime((home / "plugins").stat().st_mtime))
                           if (home / "plugins").is_dir() else None}
Path(sys.argv[1]).write_text(json.dumps(rec, indent=2) + "\n")
print(json.dumps({k: v["plugins_dir"] for k, v in rec["stages"].items()}))
