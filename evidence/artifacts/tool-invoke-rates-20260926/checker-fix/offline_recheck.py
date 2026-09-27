#!/usr/bin/env python3
"""Offline re-check of the FIXED privacy checker against the RETAINED exports of the u6 live host proof
(2026-09-26T23:47:42Z-23:49:21Z). No new host run: no live Loki query, no new model call, no new probe -- this
reads only a file that was already durably written to disk during that run, filtered to that run's own task id.

Two sinks, and they get different treatment here:
  * events-file sink (the Collector's persistent file exporter): its append-only rotated file from that run is
    still on disk. This script greps it for the run's exact task id (read from a one-line file, never argv, so
    it never appears in a process listing) and re-runs the FIXED checker's body-equality and no-floor
    forbidden-string assertions over just those lines. This is a genuine offline re-check on real data.
  * Loki sink: intentionally NOT re-queried here (no new host run). Loki was never asked to retain the raw
    record bodies from that run -- only prove_check.py's own derived PASS/FAIL text was saved (checks.txt /
    u6-prove-live.txt) -- so there is nothing on disk to re-run the new body-equality assertion against. The
    receipt README records this as a stated limit, with window-2's independent observation of the broader
    22:45-00:24Z window (which contains this run) as separate, corroborating evidence for that sink.

Usage: offline_recheck.py <events-file-glob> <task-id-file> <retained-forbidden.txt> <prove_check.py's directory>
  <task-id-file>: a one-line file holding the exact task id to grep for.
  <retained-forbidden.txt>: the forbidden-string list the live run actually generated (prove.sh's
    raw/prove-<UTC>/forbidden.txt); this script adds the one literal ("pwd") that the pre-fix prove.sh never
    added, matching the fixed prove.sh's own forbidden-list generation.
Prints only derived PASS/FAIL lines and counts -- never a raw line, task id or command/prompt text.
"""
import glob
import importlib.util
import json
import sys
from pathlib import Path

if len(sys.argv) != 5:
    sys.exit(__doc__)
events_glob, task_id_file, forbidden_path, pc_dir = sys.argv[1:5]

spec = importlib.util.spec_from_file_location("prove_check", Path(pc_dir) / "prove_check.py")
prove_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prove_check)  # side-effect free import (see prove_check.py's main())

task = open(task_id_file).read().strip()
if not task:
    sys.exit("task-id file is empty")
forbidden = prove_check.load_forbidden([forbidden_path])
added_pwd = "pwd" not in forbidden
if added_pwd:
    forbidden = forbidden + ["pwd"]  # the one literal the fixed prove.sh adds that the retained list lacks

paths = sorted(glob.glob(events_glob))
events_lines = [line for path in paths for line in open(path, errors="replace") if task in line]
print(f"INFO events files scanned: {len(paths)}; tagged lines found: {len(events_lines)}; "
      f"forbidden strings: {len(forbidden)} (added 'pwd': {added_pwd})")

results = {"pass": 0, "fail": 0}


def report(name, ok, detail=""):
    results["pass" if ok else "fail"] += 1
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))


parsed = []
for line in events_lines:
    try:
        parsed.append(json.loads(line))
    except json.JSONDecodeError:
        continue
report("every tagged events-file line parsed as JSON", len(parsed) == len(events_lines),
       f"lines={len(events_lines)} parsed={len(parsed)}")
bodies_values = [prove_check.otlp_body_and_values(obj) for obj in parsed]
not_fixed = sum(1 for body, _ in bodies_values if body is not None and body != prove_check.FIXED_BODY)
report(f"every tagged events-file record's body is exactly {prove_check.FIXED_BODY!r}",
       bool(bodies_values) and not_fixed == 0, f"records={len(bodies_values)} not_fixed={not_fixed}")
event_values = {v for body, vals in bodies_values for v in ([body] if isinstance(body, str) else []) + vals}
event_hits = sum(1 for f in forbidden if any(f in v for v in event_values))
banned_keys = [k for k in ("tool_parameters", "tool_input", "full_command", "arguments", "user.email")
               if any(f'"key":"{k}"' in line for line in events_lines)]
report("the events file holds this run's tagged records without command/prompt text (any length) or "
       "content/identity keys", bool(events_lines) and event_hits == 0 and not banned_keys,
       f"lines={len(events_lines)} value hits={event_hits} banned keys={banned_keys}")
print(f"SUMMARY offline_recheck (events-file sink only; Loki sink not re-queried): "
      f"{results['pass']} passed, {results['fail']} failed")
sys.exit(1 if results["fail"] else 0)
