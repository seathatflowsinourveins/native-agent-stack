#!/usr/bin/env python3
"""Stage 4 block: the gates around one promptfoo eval, then the eval itself (§4.1 CL1, §9).

  python3 -B block.py --run-root <root> --cell <cell> [--test-key <key>] [--repeat K] [-j J] [--allow-timing]

Before: no STOP flag; the host S7 view equals the stage-1 baseline (a change needs a reviewed new baseline); outside
the blackout windows; Claude blocks also need the host configuration settled for 30 minutes; Codex blocks run
`scripts/codex_quota.py --gate 70` under the real CODEX_HOME and check the gateway build is unchanged.
The eval: `PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true promptfoo eval -c cells/<cell>/promptfooconfig.yaml --repeat <k>
-j <j> --no-cache --no-write --no-share -o cells/<cell>/results.json` from the run root, in a clean login shell (env -i,
bash -l), with telemetry and update checks off and promptfoo's state directory inside the run root.
After: the S7 view again, promptfoo's attempts per test (G9), and for Codex the gateway's requests and limit errors in
the block window. One row per block is appended to blocks.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (append_jsonl, clean_login_env, gateway_build, gateway_get, load_json, read_jsonl, run,  # noqa: E402
                    s7_compare, s7_snapshot, sha256_file, utc_now, utc_stamp, write_json)


def stop_flags(root: Path, client: str) -> list[str]:
    return [name for name in ("STOP", f"STOP.{client}") if (root / name).exists()]


def quota_gate(script: Path) -> dict:
    """scripts/codex_quota.py (frozen into the run root at stage 1) under the real CODEX_HOME (§9.2)."""
    import os
    env = {k: v for k, v in os.environ.items() if k != "CODEX_HOME"}
    proc = run(["python3", "-B", str(script), "--json", "--gate", "70"], timeout=120, env=env)
    try:
        snap = json.loads(proc.stdout.decode() or "{}")
    except ValueError:
        snap = {}
    return {"rc": proc.returncode, "used_percent": snap.get("used_percent"),
            "secondary_used_percent": (snap.get("secondary") or {}).get("used_percent"), "gate": snap.get("gate")}


def gateway_window(since: str, until: str) -> dict:
    rows, offset, errors = [], 0, []
    while True:
        try:
            page = gateway_get(f"/api/usage/call-logs?limit=500&offset={offset}")
        except Exception as error:  # noqa: BLE001
            errors.append(type(error).__name__)
            break
        if not page:
            break
        offset += len(page)
        rows += [r for r in page if since <= (r.get("timestamp") or "") <= until]
        if (page[-1].get("timestamp") or "") < since or offset >= 5000:
            break
    limited = [r for r in rows if r.get("status") == 429 or re.search(r"rate|limit|quota", json.dumps(r.get("error") or ""), re.I)]
    return {"requests": len(rows), "limit_errors": len(limited), "non_200": sum(1 for r in rows if r.get("status") != 200),
            "errors": errors}


def promptfoo_attempts(results_path: Path) -> dict:
    """Attempts per test and the launcher's JSON line per result (G9: one attempt per test and repeat)."""
    try:
        data = load_json(results_path)
    except (OSError, ValueError) as error:
        return {"error": type(error).__name__}
    rows = (data.get("results") or {}).get("results") or []
    per_test, trials, errors = {}, [], 0
    for row in rows:
        key = ((row.get("testCase") or {}).get("metadata") or {}).get("test_key") or (row.get("testCase") or {}).get("description")
        per_test[key] = per_test.get(key, 0) + 1
        output = (row.get("response") or {}).get("output")
        if row.get("error"):
            errors += 1
        try:
            parsed = json.loads(output) if isinstance(output, str) else None
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            trials.append({k: parsed.get(k) for k in ("trial_id", "rc", "censored", "reason")})
        elif output is not None:
            trials.append({"provider_output_sha256": __import__("hashlib").sha256(str(output).encode()).hexdigest(),
                           "app_server": True})
    return {"rows": len(rows), "per_test": per_test, "trials": trials, "provider_errors": errors,
            "eval_id": data.get("evalId")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--test-key", default=None, help="run one test of the cell (--filter-metadata test_key=...)")
    parser.add_argument("--repeat", type=int, default=None)
    parser.add_argument("-j", type=int, default=None)
    parser.add_argument("--allow-timing", action="store_true")
    parser.add_argument("--skip-quota", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.run_root)
    cfg = load_json(root / "run.json")
    cell = cfg["cells"][args.cell]
    client = cell["client"]
    repeat = args.repeat or cell["repeat"]
    jobs = args.j or cell["j"]
    if client == "claude":
        jobs = 1
    row = {"cell": args.cell, "client": client, "test_key": args.test_key, "repeat": repeat, "j": jobs, "planned_at": utc_now()}
    refusals = []
    flags = stop_flags(root, client)
    if flags:
        refusals.append(f"stop flags: {flags}")
    baseline = load_json(cfg["s7_baseline"])
    pre = s7_snapshot({"fixture_tar": cfg["fixture"]["tar_path"]})
    host = s7_compare(baseline, pre)
    row["pre_vs_baseline"] = {k: v for k, v in host.items() if k != "new_trust_paths_private"}
    if not host["equal"] or any(host["new_trust"].values()):
        refusals.append(f"host exposure differs from the stage-1 baseline: {host['changed'][:8]}")
    from prepare import config_settled, in_blackout
    if in_blackout() and not args.allow_timing:
        refusals.append("blackout window")
    if client == "claude":
        settled = config_settled()
        row["config_settled"] = settled
        if not settled["settled"] and not args.allow_timing:
            refusals.append("host configuration changed within 30 minutes")
    else:
        build = gateway_build()
        row["gateway_build"] = build
        if build != cfg.get("gateway_build"):
            refusals.append("gateway build changed since stage 1 (pause the block)")
        if not args.skip_quota:
            quota = quota_gate(root / "harness" / "codex_quota.py")
            row["quota"] = quota
            if quota.get("rc") != 0:
                refusals.append(f"quota gate exit {quota.get('rc')}")
    if refusals:
        row.update({"refused": refusals, "at": utc_now()})
        append_jsonl(root / "blocks.jsonl", row)
        print(json.dumps({"refused": refusals}))
        return 2
    configs = []
    if cell["kind"] == "app-server":
        for trial in cell.get("trials", []):
            if args.test_key and trial["test_key"] != args.test_key:
                continue
            configs.append((Path(trial["config"]), Path(trial["config"]).parent / "results.json", trial["trial_id"]))
    else:
        suffix = "" if not args.test_key else "-" + re.sub(r"[^A-Za-z0-9_.-]", "_", args.test_key)
        configs.append((root / "cells" / args.cell / "promptfooconfig.yaml",
                        root / "cells" / args.cell / f"results{suffix}.json", None))
    outcomes = []
    for config, results, trial_id in configs:
        command = ["promptfoo", "eval", "-c", str(config.relative_to(root)), "--repeat", str(repeat), "-j", str(jobs),
                   "--no-cache", "--no-write", "--no-share", "-o", str(results.relative_to(root)), "--no-progress-bar",
                   "--no-table"]
        if args.test_key and cell["kind"] != "app-server":
            command += ["--filter-metadata", f"test_key={args.test_key}"]
        line = ("PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1 "
                f"PROMPTFOO_CONFIG_DIR={shlex.quote(str(root / 'promptfoo-home'))} " + " ".join(shlex.quote(c) for c in command))
        log = root / "cells" / args.cell / f"eval-{utc_stamp()}.log"
        started = utc_now()
        if args.dry_run:
            outcomes.append({"command": line, "dry_run": True})
            continue
        with open(log, "wb") as handle:
            proc = subprocess.run(["bash", "-lc", f"cd {shlex.quote(str(root))} && {line}"], env=clean_login_env(),
                                  stdout=handle, stderr=subprocess.STDOUT)
        ended = utc_now()
        outcome = {"command": line, "rc": proc.returncode, "started": started, "ended": ended, "log": str(log),
                   "results": str(results), "results_sha256": sha256_file(results) if results.exists() else None,
                   "attempts": promptfoo_attempts(results) if results.exists() else None}
        if trial_id:
            outcome["trial_id"] = trial_id
        if client == "codex":
            outcome["gateway_window"] = gateway_window(started, ended)
        outcomes.append(outcome)
    post = s7_snapshot({"fixture_tar": cfg["fixture"]["tar_path"]})
    within = s7_compare(pre, post)
    row.update({"outcomes": outcomes, "post_vs_pre": {k: v for k, v in within.items() if k != "new_trust_paths_private"},
                "at": utc_now()})
    write_json(root / "s7" / f"block-{args.cell}-{utc_stamp()}.after.json", post, 0o600)
    append_jsonl(root / "blocks.jsonl", row)
    print(json.dumps({"cell": args.cell, "outcomes": [{k: o.get(k) for k in ("rc", "results", "attempts", "dry_run")} for o in outcomes],
                      "host_unchanged": within["equal"], "new_trust": within["new_trust"]}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
