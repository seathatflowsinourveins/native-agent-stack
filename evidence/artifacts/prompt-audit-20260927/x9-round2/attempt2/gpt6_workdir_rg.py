"""Re-run each GPT-6 judge's read-only `rtk rg` command in the attempt-2 root and in the live checkout, and say which
output the recorded output matches (booleans only).

usage: gpt6_workdir_rg.py J LIVE_CHECKOUT
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
        assert cmd.startswith("/bin/bash -lc ")
        got = {}
        for name, d in (("root", J / "root"), ("live", LIVE)):
            r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, shell=True)  # the recorded command line
            got[name] = r.stdout + r.stderr
        rec = it.get("aggregated_output") or ""
        lines = {k: [x for x in v.splitlines() if x.strip() and "rtk recall" not in x] for k, v in got.items()}
        only = {k: [x for x in lines[k] if x not in lines["live" if k == "root" else "root"]] for k in lines}
        print(order, "lines only in the root rerun found in the recorded output:",
              f"{sum(x in rec for x in only['root'])}/{len(only['root'])};",
              "lines only in the live rerun found:", f"{sum(x in rec for x in only['live'])}/{len(only['live'])}")
        print(order, "files named differ in output between dirs:", got["root"] != got["live"],
              "| recorded == root:", rec.strip() == got["root"].strip(),
              "| recorded == live:", rec.strip() == got["live"].strip(), "|", cmd[14:90])
