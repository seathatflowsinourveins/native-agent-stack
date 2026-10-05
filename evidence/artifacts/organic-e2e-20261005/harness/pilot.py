#!/usr/bin/env python3
"""The pilot's stage order (pilot spec stages 0-6) as one command. A sequencer only: every trial is a promptfoo eval
started by block.py, which keeps its own gates (STOP flags, S7 baseline, blackout and settle rule, Codex quota gate,
gateway build), so a refusal stops that chain and nothing is retried.

  python3 -B pilot.py --run-id <id> [--prompted stage3.json] [--from-stage N] [--allow-timing]

0  grade.py replay (the v1 captures); G1 must hold.
1  prepare.py: every pilot cell, the stage-2 probes and canaries (stage2-canaries.json) plus any --prompted runs. If a
   host harness file moved since the protocol's hashes, one Claude probe is added and the give-way rule drops
   G1|claude-sdk, so the Claude total stays 14.
2  Codex gate 0: the probes and canaries, then one CL3 native trial on G1.
4  Codex blocks C1-C5 in order (C1 k=3, -j 3) and, in parallel, the Claude schedule (probe first if any, then G1, then
   the seeded order), one eval per test at -j 1 under the shared lock.
5  collect.py.  6  grade.py trials.
Stage 3's prompted oracle runs come in through --prompted (their prompts are the coordinator's); they run in stage 2's
order with the other prompted cells.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import HOME, RUNS_ROOT, load_json, sha256_file, utc_now  # noqa: E402

PROTOCOL_PREFIXES = {HOME / ".claude/CLAUDE.md": "b86ea2c4655637fa", HOME / ".claude/settings.json": "861959ff0e49803f"}
CLAUDE_PROBE = {"key": "probe-claude-native", "cell": "claude-native", "prompt": "Reply with the single word: ready."}
CODEX_BLOCKS = ("codex-native", "codex-env", "codex-native-ultra", "codex-sdk", "codex-app-server")


def step(label: str, cmd: list[str], log: list) -> int:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or (proc.stderr or "").strip().splitlines()[-1:]
    log.append({"at": utc_now(), "step": label, "rc": proc.returncode, "tail": tail[0][:600] if tail else ""})
    print(json.dumps(log[-1]), flush=True)
    refused = proc.returncode != 0 or (tail and '"refused"' in tail[0])
    return 1 if refused else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompted", default=None, help="extra prompted runs (stage 3 oracle runs), JSON list")
    parser.add_argument("--from-stage", type=int, default=0)
    parser.add_argument("--to-stage", type=int, default=6)
    parser.add_argument("--allow-timing", action="store_true")
    parser.add_argument("--cells", default=None, help="restrict stage 1 to these cells (self-tests); default every pilot cell")
    parser.add_argument("--tasks", default=None, help="restrict stage 1 to item_id:INSTANCE pairs (self-tests)")
    args = parser.parse_args(argv)
    py = [sys.executable, "-B"]
    root = RUNS_ROOT / args.run_id
    log: list = []
    timing = ["--allow-timing"] if args.allow_timing else []
    if args.from_stage <= 0:
        if step("stage 0 replay", py + [str(HERE / "grade.py"), "replay", "--out", str(RUNS_ROOT / f"stage0-{args.run_id}.json")], log):
            return 2
        report = load_json(RUNS_ROOT / f"stage0-{args.run_id}.json")
        if not report.get("G1"):
            print(json.dumps({"stop": "G1 (stage-0 reconciliations) did not hold"}))
            return 2
    if args.to_stage < 1:
        return 0
    if args.from_stage <= 1:
        prompted = load_json(HERE / "stage2-canaries.json")
        if args.prompted:
            prompted += load_json(Path(args.prompted))
        skip = []
        if any(not sha256_file(path).startswith(prefix) for path, prefix in PROTOCOL_PREFIXES.items()):
            prompted.append(CLAUDE_PROBE)
            skip.append("G1|claude-sdk")
        prompted_file = RUNS_ROOT / f"prompted-{args.run_id}.json"
        prompted_file.write_text(json.dumps(prompted, indent=1) + "\n", encoding="utf-8")
        cmd = py + [str(HERE / "prepare.py"), "--run-id", args.run_id, "--prompted", str(prompted_file)] + timing
        if skip:
            cmd += ["--skip-tests", ",".join(skip)]
        if args.cells:
            cmd += ["--cells", args.cells]
        if args.tasks:
            cmd += ["--tasks", args.tasks]
        if step("stage 1 prepare", cmd, log):
            return 2
    if args.to_stage < 2:
        return 0
    cfg = load_json(root / "run.json")
    block = py + [str(root / "harness" / "block.py"), "--run-root", str(root)] + timing
    if args.from_stage <= 2:
        for cell in ("prompted-codex-native", "prompted-codex-env"):
            if cell in cfg["cells"] and step(f"stage 2 {cell}", block + ["--cell", cell], log):
                return 2
        if "codex-native" in cfg["cells"] and "G1|codex-native" in cfg["cells"]["codex-native"]["tests"] and \
                step("stage 2 gate-0 G1", block + ["--cell", "codex-native", "--test-key", "G1|codex-native", "--repeat", "1"], log):
            return 2
    if args.to_stage < 4:
        return 0
    if args.from_stage <= 4:
        failures = []

        def codex_chain():
            for cell in CODEX_BLOCKS:
                if cell in cfg["cells"] and step(f"stage 4 {cell}", block + ["--cell", cell], log):
                    failures.append(cell)
                    return

        def claude_chain():
            schedule = load_json(root / "schedule.json")["claude"]
            order = [s for s in schedule if s["test_key"].startswith("probe-claude-native|")]
            order += [s for s in schedule if s not in order]
            for entry in order:
                if step(f"stage 4 {entry['test_key']}", block + ["--cell", entry["cell"], "--test-key", entry["test_key"]], log):
                    failures.append(entry["test_key"])
                    return

        threads = [threading.Thread(target=codex_chain), threading.Thread(target=claude_chain)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if failures:
            print(json.dumps({"stopped_chains_at": failures}))
    if args.to_stage < 5:
        return 0
    if args.from_stage <= 5:
        step("stage 5 collect", py + [str(root / "harness" / "collect.py"), "--run-root", str(root)], log)
    if args.to_stage < 6:
        (root / "pilot-log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
        return 0
    if args.from_stage <= 6:
        step("stage 6 grade", py + [str(root / "harness" / "grade.py"), "trials", "--run-root", str(root)], log)
    (root / "pilot-log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
