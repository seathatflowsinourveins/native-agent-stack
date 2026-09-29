"""For gpt6_workdir_rg.py's live-only lines that were found in a GPT-6 judge's recorded output: print each such
line, whether it is a whole line of the recorded output, and which recorded lines contain it.

usage: gpt6_workdir_liveonly.py J LIVE_CHECKOUT
"""
import json
import subprocess
import sys
from pathlib import Path

J, LIVE = Path(sys.argv[1]), Path(sys.argv[2])
for order in ("AB", "BA"):
    for line in (J / "runs" / "gpt6" / f"x9r2-judge-{order}" / "events.jsonl").read_text().splitlines():
        e = json.loads(line)
        it = e.get("item") or {}
        if e.get("type") != "item.completed" or it.get("type") != "command_execution" or " rg " not in it["command"]:
            continue
        cmd = it["command"]
        got = {name: subprocess.run(cmd, cwd=d, capture_output=True, text=True, shell=True).stdout
               for name, d in (("root", J / "root"), ("live", LIVE))}
        rec = it.get("aggregated_output") or ""
        rec_lines = rec.splitlines()
        lines = {k: [x for x in v.splitlines() if x.strip() and "rtk recall" not in x] for k, v in got.items()}
        live_only = [x for x in lines["live"] if x not in lines["root"]]
        for x in live_only:
            if x in rec:
                print(order, "live-only line found:", repr(x[:160]), "| whole recorded line:", x in rec_lines,
                      "| recorded lines containing it:", [y[:160] for y in rec_lines if x in y][:3])
