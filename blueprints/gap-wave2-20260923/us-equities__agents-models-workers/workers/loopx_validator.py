#!/usr/bin/env python3
"""LoopX validator: saves the normalized host result from stdin and passes (exit 0) only
when some string in it holds a JSON object matching every gold fact (score_facts rules)."""
import json, subprocess, sys
from pathlib import Path
gold, save = sys.argv[1], sys.argv[2]
raw = sys.stdin.read(); Path(save).write_text(raw)
try:
    doc = json.loads(raw)
except ValueError:
    doc = raw
strings = []
def walk(x):
    if isinstance(x, dict): [walk(v) for v in x.values()]
    elif isinstance(x, list): [walk(v) for v in x]
    elif isinstance(x, str): strings.append(x)
walk(doc)
scorer = str(Path(__file__).with_name("score_facts.py"))
best = None
for s in strings:
    if "sdk_run_duration_ms" not in s: continue
    r = subprocess.run([sys.executable, scorer, gold], input=s, capture_output=True, text=True)
    best = r.stdout.strip()
    if r.returncode == 0:
        print(best); sys.exit(0)
print(best or '{"parsed": false}'); sys.exit(9)
