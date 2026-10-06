#!/usr/bin/env python3
"""Stage 4 block: the gates around one promptfoo eval, then the eval itself (§4.1 CL1, §9).

  python3 -B <trial_root>/bin/b.py --cell <cell code or name> [--ref <test ref>] [--repeat K] [-j J] [--allow-timing]
  python3 -B block.py --run-root <root> --cell <cell> ...         (the same, from the run root's frozen harness)

Before: no STOP, STOP.<client>, DEFER.<client> or HOLD.<cell> flag; the host S7 view equals the baseline in force (the
stage-1 baseline or the run's one in-run re-baseline; a change found here becomes that re-baseline when decision 7 of
CC item task-ns2604-coop-20261006T105529Z allows it, and is refused otherwise); outside the blackout windows; Claude
blocks also need the host configuration settled for 30 minutes; Codex blocks run `scripts/codex_quota.py --gate 70`
under the real CODEX_HOME and check the gateway build is unchanged.
The eval: `PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true promptfoo eval -c <config> --repeat <k> -j <j> --no-cache --no-write
--no-share -o <results>` in a clean login environment (env -i semantics, the login shell's PATH), with telemetry and
update checks off. Every argv on the way is neutral (finding 10): promptfoo runs as `node <trial_root>/bin/r eval ...`
(a neutral link to its entry point), from the trial root, on configs and results under opaque names there; the results
are then copied into the run root. One test is selected with --filter-metadata ref=<opaque ref>.
After: the S7 view again against the baseline in force (a persistent change that no launcher absorbed writes STOP; a
CL7b trial that ran across an in-run re-baseline is carried forward), promptfoo's attempts per test (G9), and for Codex
the gateway's requests and limit errors in the block window. One row per block is appended to blocks.jsonl. CL7b (promptfoo's own app-server provider, no
launcher) gets its launched and exit ledger rows here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (append_jsonl, clean_login_env, current_s7_baseline, gateway_build, gateway_get, load_json,  # noqa: E402
                    rebaselines_between, run, s7_compare, s7_host_only, s7_persistent_change, sha256_file,
                    stable_s7_snapshot, stop_flag_names, trial_dir, try_rebaseline, utc_now, utc_stamp, write_json)


def stop_flags(root: Path, client: str, cell: str | None = None) -> list[str]:
    return [name for name in stop_flag_names(client, cell) if (root / name).exists()]


def straddled_rebaseline(root: Path, started: str, ended: str) -> str | None:
    """Decision 7 for a trial without a launcher (CL7b): a re-baseline recorded while it ran makes it a re-run."""
    during = rebaselines_between(root, started, ended)
    return f"re-baselined during the trial ({str(during[-1].get('baseline', '')).rsplit('/', 1)[-1]})" if during else None


def quota_gate(script: Path) -> dict:
    """scripts/codex_quota.py (frozen into the run root at stage 1) under the real CODEX_HOME (§9.2)."""
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
        case = row.get("testCase") or {}
        key = (case.get("metadata") or {}).get("ref") or (case.get("metadata") or {}).get("test_key") or case.get("description")
        per_test[key] = per_test.get(key, 0) + 1
        output = (row.get("response") or {}).get("output")
        if row.get("error"):
            errors += 1
        try:
            parsed = json.loads(output) if isinstance(output, str) else None
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and "trial_id" in parsed:
            trials.append({k: parsed.get(k) for k in ("trial_id", "rc", "censored", "reason")})
        elif output is not None or row.get("error"):
            trials.append({"provider_output_sha256": __import__("hashlib").sha256(str(output).encode()).hexdigest(),
                           "app_server": True, "error": bool(row.get("error"))})
    return {"rows": len(rows), "per_test": per_test, "trials": trials, "provider_errors": errors,
            "eval_id": data.get("evalId")}


def resolve_cell(cfg: dict, name_or_code: str) -> str:
    codes = cfg.get("cell_codes") or {}
    if name_or_code in codes:
        return codes[name_or_code]
    if name_or_code in cfg["cells"]:
        return name_or_code
    raise SystemExit(f"unknown cell: {name_or_code}")


def resolve_ref(cfg: dict, cell: str, ref: str | None, test_key: str | None) -> str | None:
    if ref:
        return ref
    if test_key:
        for candidate, test in (cfg.get("tests_by_ref") or {}).items():
            if test.get("test_key") == test_key and test.get("cell") == cell:
                return candidate
        raise SystemExit(f"unknown test key for {cell}: {test_key}")
    return None


def runner_argv(cfg: dict, config: Path, results: Path, repeat: int, jobs: int, ref: str | None, work: Path) -> list[str]:
    """node <trial_root>/bin/r eval ... with paths relative to the trial root (neutral argv)."""
    node = cfg["binaries"].get("node_neutral") or cfg["binaries"]["node_real"]
    argv = [node, str(work / "bin" / "r"), "eval", "-c", str(config.relative_to(work)),
            "--repeat", str(repeat), "-j", str(jobs), "--no-cache", "--no-write", "--no-share",
            "-o", str(results.relative_to(work)), "--no-progress-bar", "--no-table"]
    if ref:
        argv += ["--filter-metadata", f"ref={ref}"]
    return argv


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--cell", required=True, help="cell code (neutral) or cell name")
    parser.add_argument("--ref", default=None, help="run one test of the cell (its opaque ref)")
    parser.add_argument("--test-key", default=None, help="run one test by its clear key (operator use; mapped to its ref)")
    parser.add_argument("--repeat", type=int, default=None)
    parser.add_argument("-j", type=int, default=None)
    parser.add_argument("--allow-timing", action="store_true")
    parser.add_argument("--skip-quota", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.run_root)
    cfg = load_json(root / "run.json")
    cell_name = resolve_cell(cfg, args.cell)
    cell = cfg["cells"][cell_name]
    code = cell.get("code") or cell_name
    client = cell["client"]
    ref = resolve_ref(cfg, cell_name, args.ref, args.test_key)
    repeat = args.repeat or cell["repeat"]
    jobs = args.j or cell["j"]
    if client == "claude":
        jobs = 1
    work = trial_dir(cfg, root)
    row = {"cell": cell_name, "client": client, "ref": ref, "repeat": repeat, "j": jobs, "planned_at": utc_now()}
    refusals = []
    flags = stop_flags(root, client, cell_name)
    if flags:
        refusals.append(f"stop flags: {flags}")
    baseline, baseline_path = current_s7_baseline(cfg, root)
    pre, pre_read = stable_s7_snapshot({"fixture_tar": cfg["fixture"]["tar_path"]})
    host = s7_compare(s7_host_only(baseline), s7_host_only(pre))
    row["pre_vs_baseline"] = {k: v for k, v in host.items() if k != "new_trust_paths_private"}
    row["s7_reads_pre"] = pre_read
    row["s7_baseline_used"] = Path(baseline_path).name
    if not host["equal"] or any(host["new_trust"].values()):
        # Decision 7: a change between blocks costs no trial, so it becomes the run's in-run re-baseline if allowed.
        done, why = (False, "stop flags set") if flags else try_rebaseline(
            root, host, any(host["new_trust"].values()), pre, {"trigger": "block-start", "cell": cell_name, "arm": cell["arm"]})
        row["rebaseline"] = why
        if done:
            baseline, baseline_path = current_s7_baseline(cfg, root)
            row["s7_baseline_used"] = Path(baseline_path).name
        else:
            refusals.append(f"host exposure differs from the baseline in force ({why}): {host['changed'][:8]}")
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
    (work / "o").mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    if cell["kind"] == "app-server":
        for trial in cell.get("trials", []):
            if ref and trial["ref"] != ref:
                continue
            config = work / "p" / Path(trial["config_neutral"]).name
            configs.append((config, work / "o" / f"{config.stem}-{stamp}.json", trial))
    else:
        suffix = f"-{ref}" if ref else ""
        configs.append((work / "p" / f"{code}.yaml", work / "o" / f"{code}{suffix}-{stamp}.json", None))
    env = clean_login_env({"PATH": cfg.get("login_path") or os.environ.get("PATH", ""),
                           "PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER": "true", "PROMPTFOO_DISABLE_TELEMETRY": "1",
                           "PROMPTFOO_DISABLE_UPDATE": "1", "PROMPTFOO_CONFIG_DIR": str(work / "h")})
    outcomes = []
    for config, results, trial in configs:
        command = runner_argv(cfg, config, results, repeat, jobs, ref if cell["kind"] != "app-server" else None, work)
        log = root / "cells" / cell_name / f"eval-{stamp}{'-' + trial['ref'] if trial else ''}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        started = utc_now()
        if args.dry_run:
            outcomes.append({"command": command, "dry_run": True})
            continue
        if trial:
            # CL7b has no launcher, so its launched row carries the gateway build (CL9, G11) the launcher records for
            # the other Codex cells.
            append_jsonl(root / "ledger.jsonl", {"run_id": cfg["run_id"], "trial_id": trial["trial_id"], "cell": cell_name,
                                                 "client": "codex", "arm": cell["arm"], "ref": trial["ref"],
                                                 "test_key": trial["test_key"], "phase": "launched", "at": started,
                                                 "gateway_build": row.get("gateway_build"),
                                                 "launched_by": "block.py (CL7b: promptfoo's own provider, no launcher)"})
        with open(log, "wb") as handle:
            proc = subprocess.run(command, cwd=str(work), env=env, stdout=handle, stderr=subprocess.STDOUT)
        ended = utc_now()
        kept = root / "cells" / cell_name / results.name
        if results.exists():
            shutil.copy2(results, kept)
        attempts = promptfoo_attempts(kept) if kept.exists() else None
        outcome = {"command": [c.replace(str(Path.home()), "~") for c in command], "rc": proc.returncode, "started": started,
                   "ended": ended, "log": str(log), "results": str(kept), "results_sha256": sha256_file(kept) if kept.exists() else None,
                   "attempts": attempts}
        if trial:
            outcome["trial_id"] = trial["trial_id"]
            provider = (attempts or {}).get("trials") or [{}]
            failed = proc.returncode not in (0, 100) or not kept.exists() or any(t.get("error") for t in provider)
            reason = "app_server_provider_error" if failed else None
            rebaselined = straddled_rebaseline(root, started, ended)
            append_jsonl(root / "ledger.jsonl", {"run_id": cfg["run_id"], "trial_id": trial["trial_id"], "cell": cell_name,
                                                 "client": "codex", "arm": cell["arm"], "ref": trial["ref"],
                                                 "test_key": trial["test_key"], "phase": "exit", "at": ended,
                                                 "rc": proc.returncode, "censored": bool(failed or rebaselined),
                                                 "reason": "host_change_rebaselined" if rebaselined else reason,
                                                 "reason_before_rebaseline": reason if rebaselined else None,
                                                 "rebaseline": rebaselined,
                                                 "provider_output_sha256": provider[0].get("provider_output_sha256")})
        if client == "codex":
            outcome["gateway_window"] = gateway_window(started, ended)
        outcomes.append(outcome)
    post, post_read = stable_s7_snapshot({"fixture_tar": cfg["fixture"]["tar_path"]})
    # The baseline in force at the block's end: a trial's in-run re-baseline during the block (decision 7) is judged
    # there, and its own trials were carried forward by the launcher.
    baseline_end, baseline_end_path = current_s7_baseline(cfg, root)
    judged = s7_persistent_change(baseline_end, pre, post)
    within = judged["within"]
    row["s7_baseline_end"] = Path(baseline_end_path).name
    row.update({"outcomes": outcomes, "post_vs_pre": {k: v for k, v in within.items() if k != "new_trust_paths_private"},
                "post_vs_baseline": {k: v for k, v in judged["vs_baseline"].items() if k != "new_trust_paths_private"},
                "persistent_change": judged["persistent"], "transient_pre": judged["transient_before"],
                "s7_reads_post": post_read, "at": utc_now()})
    write_json(root / "s7" / f"block-{cell_name}-{utc_stamp()}.after.json", post, 0o600)
    if judged["persistent"]:
        # A change during the block that no launcher absorbed (CL7b has none, and a change after a block's last trial
        # exits is seen only here) stops the run as before decision 7; the block-start re-baseline is only for a change
        # made while no block ran.
        (root / "STOP").write_text(f"{utc_now()} host exposure or trust changed during block {cell_name}: "
                                   f"{judged['vs_baseline']['changed'][:6]} new_trust={judged['vs_baseline']['new_trust']}\n")
        row["stopped"] = "persistent change during the block"
    append_jsonl(root / "blocks.jsonl", row)
    print(json.dumps({"cell": cell_name, "outcomes": [{k: o.get(k) for k in ("rc", "results", "attempts", "dry_run")} for o in outcomes],
                      "host_unchanged": not judged["persistent"], "new_trust": judged["vs_baseline"]["new_trust"]}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
