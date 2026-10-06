#!/usr/bin/env python3
"""The pilot's stage order (pilot spec stages 0-6) as one command. A sequencer only: every trial is a promptfoo eval
started by block.py, which keeps its own gates (STOP and DEFER flags, S7 baseline, blackout and settle rule, Codex quota
gate, gateway build), so a refusal stops that chain and nothing is retried.

  python3 -B pilot.py --run-id <id> [--prompted stage3-oracles.json] [--to-stage N] [stage-1 options]   stages 0-1, then re-exec
  python3 -B ~/.cache/wsr/<8 hex>/bin/p.py [--from-stage N] [--to-stage M] [--allow-timing]       resume (neutral argv)

Start it from a clean login shell (never from inside a Claude or Codex session, §4.1): the launcher lints every
ancestor's argv and refuses a trial whose process tree names a client, an item or the experiment. After stage 1 this
process re-executes itself through the run's neutral stub bin/p.py, so the process table shows no run id, cell, item
or experiment word while sessions run.

0  grade.py replay (the v1 captures); G1 must hold.
1  prepare.py: every pilot cell, the stage-2 probes and canaries (stage2-canaries.json) plus any --prompted runs. If a
   host harness file moved since the protocol's hashes, one Claude probe is added and the give-way rule drops
   G1|claude-sdk, so the Claude total stays 14. Stage 1 refuses a Claude schedule above 14.
2  Gate 0: the Codex probes and canaries (gh auth through the shell, and through ctx_batch_execute in both Codex arms;
   the exec-rules canary), the gate-0 CL3 native trial on G1 (the designated call-id calibration cell, CC item
   task-ns2604-coop-20261006T170607Z: grade.call_id_calibration, required by gate 0 and G11), then the Claude probe if one is required; collect.py on those trials and
   grade.py gate0. Stages 3 and 4 never start unless gate0.json passes.
3  The prompted oracle runs: --prompted entries with "stage": 3 (stage3-oracles.json for the pilot), in their own
   oracle-<base cell> cells, one block per cell.
4  Codex blocks C1-C5 in order and, in parallel, the Claude schedule (G1 first, then the seeded order), one eval per
   test at -j 1 under the shared lock. Needs gate0.json passing and a reviewed routing-file registry (or a recorded
   development allowance); the Claude chain also needs the run's completion policy decided by a CC amendment. Stage 1
   records decision 1 of CC item task-ns2604-coop-20261006T105529Z by default (complete-at-result, T = 1,800 s); another
   policy or T goes in through prepare.py --claude-completion ... --claude-t-seconds ... --amendment-ref .... After the
   first Claude block with usable meter readings, the expected usage per trial (0.15 of a window to start) becomes the
   measured p90 per trial, written to meter-calibration.json in the run root (recalibrate_meter; confirmed at 11:43Z).
5  collect.py.  6  grade.py trials.
Resume: --from-stage 2, 3 or 4 runs only tests whose completed or still-running attempts are fewer than their repeat;
a test refused before launch (meter, lock, DEFER, HOLD), or an attempt carried forward (common.CARRY_FORWARD_REASONS:
killed at its own first meter reading, rate-limited, re-run after an in-run re-baseline, interrupted, or a launcher
error after launch), runs again. An attempt that launched but has no exit row and no live process is first given its
interrupted exit (reconcile_orphans). Each attempt has its own trial id, CL7b's included.
--from-stage 2 --rerun-gate0-failures runs once more only the stage-2 tests whose gate-0 check failed (for example a
Claude probe stopped by the meter, in the next 5-hour window), then collects and checks gate 0 again. A DEFER.claude
flag is cleared on resume once the newest meter reading leaves headroom for the run's expected usage (decision 6);
STOP flags, and the HOLD.<cell> flag a Claude trial without a result event by T sets for the operator's diagnosis
(decision 1), stay until the operator removes them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CARRY_FORWARD_REASONS, CC_V11_DECISIONS, HOME, METER_CALIBRATION, RUNS_ROOT,  # noqa: E402
                    append_jsonl, headroom_allows, load_json, meter_calibration, newest_meter_reading, read_jsonl,
                    run_expected_usage, sha256_file, utc_now, write_json)

PROTOCOL_PREFIXES = {HOME / ".claude/CLAUDE.md": "b86ea2c4655637fa", HOME / ".claude/settings.json": "861959ff0e49803f"}
CLAUDE_PROBE = {"key": "probe-claude-native", "cell": "claude-native", "prompt": "Reply with the single word: ready."}
# Round 6d (GPT read of 50752dde, P2): the calibration cell runs first, and is collected and checked before any other.
CALIBRATION_CELL = "codex-native-gate0"
CODEX_STAGE2 = (CALIBRATION_CELL, "prompted-codex-native", "prompted-codex-env")
CLAUDE_STAGE2 = ("prompted-claude-native", "prompted-claude-env")
CODEX_BLOCKS = ("codex-native", "codex-env", "codex-native-ultra", "codex-sdk", "codex-app-server")
PREPARE_FLAGS = ("--claude-completion", "--amendment-ref", "--claude-grace-s", "--claude-t-seconds", "--registry-review",
                 "--repeat-override", "--seed", "--claude-expected-usage", "--gateway-pipeline-details")
PREPARE_SWITCHES = ("--allow-provisional-registry", "--skip-oracle-tests", "--skip-quota", "--allow-timing")


def step(label: str, cmd: list[str], log: list) -> int:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or (proc.stderr or "").strip().splitlines()[-1:]
    log.append({"at": utc_now(), "step": label, "rc": proc.returncode, "tail": tail[0][:600] if tail else ""})
    print(json.dumps(log[-1]), flush=True)
    refused = proc.returncode != 0 or (tail and '"refused"' in tail[0])
    return 1 if refused else 0


def launched_by_ref(root: Path) -> dict:
    """Attempts per test ref that use up its repeat (GPT read of 5aa2bfdc, findings 3 and 5). Each attempt (trial id)
    counts on its own: when its last exit row is terminal and not carried forward (common.CARRY_FORWARD_REASONS), or,
    with no exit row yet, while it is still in flight (reconcile_orphans() gives an ended one its interrupted exit
    first). A carried attempt therefore never suppresses a later attempt of the same ref, and an attempt that launched
    without an exit is never taken for a completed one. The launcher's Claude session cap still counts every launch."""
    rows = read_jsonl(root / "ledger.jsonl")
    last_exit = {}
    for row in rows:
        if row.get("phase") == "exit" and row.get("trial_id"):
            last_exit[row["trial_id"]] = row
    attempts: dict = {}
    for row in rows:
        if row.get("phase") != "launched" or not row.get("ref"):
            continue
        exit_row = last_exit.get(row.get("trial_id"))
        if exit_row is None or exit_row.get("reason") not in CARRY_FORWARD_REASONS:
            attempts.setdefault(row["ref"], set()).add(row.get("trial_id"))
    return {ref: len(ids) for ref, ids in attempts.items()}


def running_trials(markers: dict) -> set:
    """Trial ids with a live process of this user whose argv names one of the attempt's markers: its trial id (every
    launcher line carries it: --session-id, otel.environment, --trial-id) or a CL7b attempt's config name."""
    found = set()
    uid = os.getuid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid != uid:
                continue
            argv = Path(f"/proc/{entry}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        found.update(tid for tid, marks in markers.items() if any(m and m in argv for m in marks))
    return found


def reconcile_orphans(root: Path, log: list) -> list:
    """Finding 3: an attempt with a launched row and no exit row, whose processes have ended (the pilot, the launcher
    or the host stopped mid-trial), gets its exit: interrupted, censored and carried forward, so a resume re-runs it.
    One still running is left alone and still counts. Launched rows are never removed, so every actual Claude launch
    stays in the session-cap count."""
    rows = read_jsonl(root / "ledger.jsonl")
    exited = {r.get("trial_id") for r in rows if r.get("phase") == "exit"}
    orphans = {r["trial_id"]: r for r in rows if r.get("phase") == "launched" and r.get("trial_id")
               and r["trial_id"] not in exited}
    if not orphans:
        return []
    running = running_trials({tid: [tid, r.get("config_name")] for tid, r in orphans.items()})
    reconciled = []
    for tid, row in orphans.items():
        if tid in running:
            continue
        append_jsonl(root / "ledger.jsonl", {k: row.get(k) for k in ("run_id", "trial_id", "cell", "client", "arm", "task",
                                                                      "instance", "lane", "ref", "test_key")}
                     | {"phase": "exit", "at": utc_now(), "rc": None, "censored": True, "reason": "interrupted",
                        "launched": True, "reconciled_by": "pilot.py (launched, no exit, no live process)"})
        reconciled.append(tid)
    log.append({"at": utc_now(), "step": "orphan reconciliation", "reconciled": reconciled,
                "still_running": sorted(running & set(orphans))})
    return reconciled


def recalibrate_meter(root: Path, cfg: dict, log: list, after: str) -> dict | None:
    """Point 5 of the 11:43Z confirmations (CC item task-ns2604-coop-20261006T114319Z): 0.15 of a window is the
    starting expected usage per trial; after the first pilot block that yields an organic Claude trial with two meter
    readings, the measured p90 per trial (common.meter_calibration) replaces it. The value goes to
    <run root>/meter-calibration.json, which the launcher reads for every later start and records, as the value used, in
    each trial's ledger rows. Runs once; the operator can recompute with grade.py meter-calibration."""
    path = root / METER_CALIBRATION
    if path.exists():
        return None
    calibration = meter_calibration(root)
    if not calibration["expected_usage"]:
        log.append({"at": utc_now(), "step": "meter calibration", "after": after,
                    "skipped": "no organic Claude trial with two meter readings yet; tried again after the next block"})
        return None
    record = {**calibration, "at": utc_now(), "after_block": after, "previous": run_expected_usage(cfg),
              "source": "pilot.py, after the first stage-4 Claude block with usable readings",
              "decision": f"{CC_V11_DECISIONS} #6; confirmed by task-ns2604-coop-20261006T114319Z point 5"}
    write_json(path, record, 0o600)
    log.append({"at": utc_now(), "step": "meter calibration", "after": after,
                "expected_usage": record["expected_usage"], "trials": record["trials"], "previous": record["previous"]})
    return record


def cell_plan(cfg: dict, cell: str, launched: dict) -> list[tuple[str | None, int]]:
    """[(ref or None for the whole cell, repeat)]: the whole cell when nothing ran, else each test still short of its
    repeat (resume never relaunches a completed test; a test refused before launch counts as not run)."""
    record = cfg["cells"][cell]
    repeat = record["repeat"]
    remaining = {ref: repeat - launched.get(ref, 0) for ref in record.get("refs") or []}
    if remaining and all(n == repeat for n in remaining.values()):
        return [(None, repeat)]
    return [(ref, n) for ref, n in remaining.items() if n > 0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompted", default=None, help="extra prompted runs (stage 3 oracle runs), JSON list")
    parser.add_argument("--from-stage", type=int, default=0)
    parser.add_argument("--to-stage", type=int, default=6)
    parser.add_argument("--cells", default=None, help="restrict stage 1 to these cells (self-tests, smoke); default every pilot cell")
    parser.add_argument("--tasks", default=None, help="restrict stage 1 to item_id:INSTANCE pairs (self-tests, smoke)")
    parser.add_argument("--from-stub", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-reexec", action="store_true", help="stay in this process after stage 1 (self-tests)")
    parser.add_argument("--keep-defer", action="store_true", help="do not clear DEFER.claude on resume")
    parser.add_argument("--rerun-gate0-failures", action="store_true",
                        help="stage 2 on resume: run once more each stage-2 test whose gate-0 check failed (the failed "
                        "part only; a Claude one belongs in a later 5-hour window), then collect and gate 0 again")
    for flag in PREPARE_FLAGS:
        parser.add_argument(flag, default=None)
    for switch in PREPARE_SWITCHES:
        parser.add_argument(switch, action="store_true")
    parser.add_argument("--answer-source-path", action="append", default=[],
                        help="passed to prepare.py: a further grader expected-output path (decision 3, confirmed at 11:43Z)")
    args = parser.parse_args(argv)
    py = [sys.executable, "-B"]
    root = RUNS_ROOT / args.run_id
    log: list = []
    timing = ["--allow-timing"] if args.allow_timing else []
    quota = ["--skip-quota"] if args.skip_quota else []
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
        cmd = py + [str(HERE / "prepare.py"), "--run-id", args.run_id, "--prompted", str(prompted_file)]
        for flag in PREPARE_FLAGS:
            value = getattr(args, flag[2:].replace("-", "_"))
            if value is not None:
                cmd += [flag, str(value)]
        for switch in PREPARE_SWITCHES:
            if getattr(args, switch[2:].replace("-", "_")):
                cmd.append(switch)
        for path in args.answer_source_path:
            cmd += ["--answer-source-path", path]
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
    work = Path(cfg["trial_root"])
    neutral_py = cfg["binaries"].get("python_neutral") or sys.executable
    if not args.from_stub and not args.no_reexec:
        # Session stages run under neutral argv (finding 10): this process becomes bin/py bin/p.py.
        os.execv(neutral_py, [neutral_py, "-B", str(work / "bin" / "p.py"), "--from-stage", str(max(args.from_stage, 2)),
                              "--to-stage", str(args.to_stage)] + timing + quota + (["--keep-defer"] if args.keep_defer else [])
                 + (["--rerun-gate0-failures"] if args.rerun_gate0_failures else []))
    if args.from_stub:
        py = [neutral_py, "-B"]
    stub = py + [str(work / "bin" / "b.py")] if args.from_stub else py + [str(root / "harness" / "block.py"), "--run-root", str(root)]
    flags = timing + quota

    def block(cell: str, ref: str | None = None, repeat: int | None = None) -> list[str]:
        cmd = stub + ["--cell", cfg["cells"][cell].get("code") or cell] + flags
        if ref:
            cmd += ["--ref", ref]
        if repeat:
            cmd += ["--repeat", str(repeat)]
        return cmd

    def run_cell(label: str, cell: str) -> int:
        for ref, repeat in cell_plan(cfg, cell, launched_by_ref(root)):
            if step(f"{label} {cell}{' ' + ref if ref else ''}", block(cell, ref, repeat), log):
                return 1
        return 0

    def clear_defer() -> None:
        if not args.keep_defer and (root / "DEFER.claude").exists():
            allowed, why = headroom_allows(newest_meter_reading(), run_expected_usage(cfg, root))
            log.append({"at": utc_now(), "step": "DEFER.claude", "cleared": allowed, "why": why})
            if allowed:
                (root / "DEFER.claude").unlink()

    def gate_key(test: dict) -> str:
        return test.get("probe_key") or ("gate0-G1" if test.get("gate_trial") else test.get("test_key"))

    if args.from_stage <= 4:
        reconcile_orphans(root, log)   # finding 3: before any stage counts attempts
    if args.from_stage <= 2:
        clear_defer()
        if args.rerun_gate0_failures and (root / "gate0.json").exists():
            failed = {k for k, check in (load_json(root / "gate0.json").get("checks") or {}).items() if not check.get("pass")}
            for ref, test in (cfg.get("tests_by_ref") or {}).items():
                if test.get("stage") == 2 and gate_key(test) in failed:
                    if step(f"stage 2 rerun {gate_key(test)}", block(test["cell"], ref, 1), log):
                        write_log(root, log)
                        return 2
        else:
            # The call-id calibration cell first (CC item task-ns2604-coop-20261006T170607Z (2)): run, collect and check
            # it before advancing to any other cell; a failed calibration stops the pilot (fail closed).
            if CALIBRATION_CELL in cfg["cells"]:
                if run_cell("stage 2 calibration", CALIBRATION_CELL):
                    write_log(root, log)
                    return 2
                gate_refs = {ref for ref, test in (cfg.get("tests_by_ref") or {}).items() if test.get("gate_trial")}
                cal_ids = sorted({r["trial_id"] for r in read_jsonl(root / "ledger.jsonl")
                                  if r.get("phase") == "launched" and r.get("ref") in gate_refs})
                step("stage 2 calibration collect", py + [str(root / "harness" / "collect.py"), "--run-root", str(root),
                                                          "--trials", ",".join(cal_ids)], log)
                if step("stage 2 calibration check", py + [str(root / "harness" / "grade.py"), "calibration",
                                                           "--run-root", str(root)], log):
                    print(json.dumps({"refused": ["the call-id calibration failed (calibration.json): fix the key from "
                                                  "the deployed build's source and re-run the calibration"]}))
                    write_log(root, log)
                    return 2
            for cell in CODEX_STAGE2[1:] + CLAUDE_STAGE2:
                if cell in cfg["cells"] and run_cell("stage 2", cell):
                    write_log(root, log)
                    return 2
        stage2_refs = {ref for ref, test in (cfg.get("tests_by_ref") or {}).items() if test.get("stage") == 2}
        trial_ids = sorted({r["trial_id"] for r in read_jsonl(root / "ledger.jsonl")
                            if r.get("phase") == "launched" and r.get("ref") in stage2_refs})
        step("stage 2 collect", py + [str(root / "harness" / "collect.py"), "--run-root", str(root), "--trials", ",".join(trial_ids)], log)
        step("stage 2 gate0", py + [str(root / "harness" / "grade.py"), "gate0", "--run-root", str(root)], log)
    if args.to_stage < 3:
        write_log(root, log)
        return 0
    # Stage 2 is a gate for every later session: the stage-3 oracle runs and the stage-4 trials (a resume at stage 5 or
    # 6 only collects and grades, so it is not refused).
    g0 = load_json(root / "gate0.json") if (root / "gate0.json").exists() else {}
    if args.from_stage <= 4 and not g0.get("pass"):
        print(json.dumps({"refused": ["gate0.json does not pass (stage 2 is a gate)"]}))
        write_log(root, log)
        return 2
    if args.from_stage <= 3:
        # Stage 3: the prompted oracle runs (cells oracle-<base cell>, lane organic-e2e-prompted), one block per cell;
        # a refused block stops the pilot here.
        clear_defer()
        for cell in sorted(c for c in cfg["cells"] if c.startswith("oracle-")):
            if run_cell("stage 3", cell):
                write_log(root, log)
                return 2
    if args.to_stage < 4:
        write_log(root, log)
        return 0
    if args.from_stage <= 4:
        refusals = []
        registry = cfg.get("registry") or {}
        if registry.get("status") != "reviewed" and not registry.get("allow_provisional"):
            refusals.append("routing-file registry is provisional (prepare.py --registry-review)")
        if refusals:
            print(json.dumps({"refused": refusals}))
            write_log(root, log)
            return 2
        clear_defer()
        failures = []

        def codex_chain():
            for cell in CODEX_BLOCKS:
                if cell in cfg["cells"] and run_cell("stage 4", cell):
                    failures.append(cell)
                    return

        def claude_chain():
            completion = cfg.get("claude_completion") or {}
            if not completion.get("decided"):
                log.append({"at": utc_now(), "step": "stage 4 claude", "refused": "completion policy undecided: the CC "
                            "amendment goes in through prepare.py --claude-completion ... --amendment-ref ..."})
                failures.append("claude: completion policy undecided")
                return
            launched = launched_by_ref(root)
            for entry in load_json(root / "schedule.json")["claude"]:
                if launched.get(entry["ref"], 0) >= cfg["cells"][entry["cell"]]["repeat"]:
                    continue
                if step(f"stage 4 {entry['test_key']}", block(entry["cell"], entry["ref"]), log):
                    failures.append(entry["test_key"])
                    return
                recalibrate_meter(root, cfg, log, f"stage 4 {entry['test_key']}")

        threads = [threading.Thread(target=codex_chain), threading.Thread(target=claude_chain)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if failures:
            print(json.dumps({"stopped_chains_at": failures}))
    if args.to_stage < 5:
        write_log(root, log)
        return 0
    if args.from_stage <= 5:
        step("stage 5 collect", py + [str(root / "harness" / "collect.py"), "--run-root", str(root)], log)
    if args.to_stage >= 6 and args.from_stage <= 6:
        step("stage 6 grade", py + [str(root / "harness" / "grade.py"), "trials", "--run-root", str(root)], log)
    write_log(root, log)
    return 0


def write_log(root: Path, log: list) -> None:
    path = root / "pilot-log.json"
    previous = load_json(path) if path.exists() else []
    path.write_text(json.dumps(previous + log, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
