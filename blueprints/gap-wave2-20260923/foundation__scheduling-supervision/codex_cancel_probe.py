#!/usr/bin/env python3
"""Gap 1 (provider-cancellation arm only): abort a streaming model-provider request
from the scheduler and record what the provider/CLI returned.

One Dagu 2.16.6 step runs ONE bounded `codex exec --json --sandbox read-only --ephemeral`
request whose stdout (the JSONL event stream) goes to a file. After the stream has
emitted `turn.started` (the provider request is in flight) plus a short delay, the
driver issues native `dagu stop`. It then records the Dagu status, whether the codex
process tree is gone, and every event the CLI emitted, searching them recursively for
any `usage` object. The same detector finds usage in a completed call's events
(gap-2 run), which is how the probe is shown able to see usage when it exists.

No broker, no paid API key, no credential reads. Billing cessation is not observable here.

Usage: codex_cancel_probe.py --work /new/absolute/dir [--delay 5]
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import time

import dagu_common as dc
import real_steps as rs

PROMPT = ("Without using any tools, write a detailed explanation of at least 1500 words of how "
          "five-field cron expressions are evaluated, with twenty worked examples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=5.0)
    args = parser.parse_args()
    work = args.work
    if not work.is_absolute() or work.exists():
        raise SystemExit("--work must name a new absolute directory")
    work.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    home = work / "dagu-home"
    home.mkdir()
    (work / "model-cwd").mkdir()
    if rs.digest(dc.DAGU) != dc.DAGU_2166_SHA256:
        raise SystemExit("Dagu binary is not the pinned 2.16.6 executable")
    config = work / "config.yaml"
    config.write_text("check_updates: false\n", encoding="utf-8")
    codex = shlex.join(["env", "HOME=" + str(Path.home()), "PATH=" + dc.CODEX_BIN_DIR + ":/usr/bin:/bin",
                        dc.CODEX_BIN_DIR + "/codex", "exec", "--json", "--sandbox", "read-only", "--ephemeral",
                        "--skip-git-repo-check", "-C", str(work / "model-cwd"), PROMPT])
    step = f"sh -c {shlex.quote(codex + ' < /dev/null > events.jsonl 2> codex-stderr.txt')}"
    workflow = work / "cancelprobe.yaml"
    workflow.write_text("\n".join([
        "type: graph", "timeout_sec: 300", "max_active_runs: 1", "working_dir: " + json.dumps(str(work)),
        "steps:", "  - id: provider_call", "    run: " + json.dumps(step), ""]), encoding="utf-8")
    env = {"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DAGU_HOME": str(home),
           "TMPDIR": str(work), "DO_NOT_TRACK": "1"}
    base = [str(dc.DAGU), "--context", "local", "--dagu-home", str(home), "--config", str(config)]
    rec = dc.Recorder(work, env)
    rec.call("version", [str(dc.DAGU), "version"])
    rec.call("validate", base + ["validate", str(workflow)])
    run_id = "cancelprobe-" + os.urandom(6).hex()
    codex_gate = dc.codex_gate()  # fix round 1: wait while 2 or more other real codex exec processes run (not re-run)
    events_file = work / "events.jsonl"
    timeline = {}
    process = None
    try:
        with (work / "native" / "start.stdout").open("x") as out, (work / "native" / "start.stderr").open("x") as err:
            process = subprocess.Popen(base + ["start", "--run-id", run_id, str(workflow)], cwd=work, env=env,
                                       stdout=out, stderr=err, start_new_session=True)
        timeline["start_issued"] = datetime.now(timezone.utc).isoformat()
        started = dc.wait_for(lambda: events_file.exists() and "turn.started" in events_file.read_text(), 90, 0.05)
        timeline["turn_started_seen"] = datetime.now(timezone.utc).isoformat() if started else None
        if not started:
            raise ValueError("turn.started never observed")
        time.sleep(args.delay)
        owned = dc.descendants(process.pid, include_self=False)
        owned_cmds = {pid: subprocess.run(["/bin/ps", "-o", "comm=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() for pid in owned}
        text_before_stop = events_file.read_text()
        completed_before_stop = "turn.completed" in text_before_stop
        rec.call("stop", base + ["stop", "--run-id", run_id, str(workflow)])
        timeline["stop_issued"] = datetime.now(timezone.utc).isoformat()
        process.wait(timeout=60)
        retired = dc.wait_for(lambda: not dc.live(owned), 30)
        timeline["processes_retired"] = datetime.now(timezone.utc).isoformat() if retired else None
        time.sleep(3)
        rows = [r for r in dc.history_rows(rec.call("history", base + ["history", "--run-id", run_id, "--format", "json"]))
                if r.get("dagRunId") == run_id]
        events = []
        for line in events_file.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                events.append({"unparsed": line[:200]})
        usage = rs.find_usage(events)
        result = {
            "dagu_version": (work / "native" / "version.stdout").read_text().strip(),
            "codex_version": subprocess.run([dc.CODEX_BIN_DIR + "/codex", "--version"], capture_output=True, text=True).stdout.strip(),
            "platform": platform.system() + " " + platform.release(), "run_id": run_id, "timeline_utc": timeline,
            "delay_after_turn_started_s": args.delay, "turn_completed_before_stop": completed_before_stop,
            "owned_processes_at_stop": sorted(owned_cmds.values()),
            "owned_processes_remaining_after_stop": len(dc.live(owned)),
            "dagu_status_after_stop": rows[0]["status"] if rows else None,
            "event_types": [e.get("type", "unparsed") for e in events],
            "usage_found": usage, "turn_completed_present": any(e.get("type") == "turn.completed" for e in events),
            "codex_stderr_tail": (work / "codex-stderr.txt").read_text()[-600:] if (work / "codex-stderr.txt").exists() else None,
            "start_exit": process.returncode, "command_exit_codes": rec.codes, "codex_gate": codex_gate,
        }
    finally:
        dc.stop_group(process)
    rs.exclusive(work / "result.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
