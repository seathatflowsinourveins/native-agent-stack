#!/usr/bin/env python3
"""PID-1 of one disposable 'boot' (an unprivileged user+pid+mount namespace).

boot1: record the boot identity, start the real workflow with native `dagu start`,
       and on SIGTERM perform an orderly shutdown: forward SIGTERM to every process in
       the namespace, wait up to 20 s, record who exited, then exit (the kernel then
       SIGKILLs anything left in the namespace).
boot2: the 'boot service': require a different boot identity, release only the
       finalize step and run native `dagu retry --run-id <same> --step finalize`.

Arguments: ns_init.py boot1|boot2 WORK RUN_ID (Dagu argv prefix comes from WORK/dagu-base.json)
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

phase, work, run_id = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
base = json.loads((work / "dagu-base.json").read_text())
env = json.loads((work / "dagu-env.json").read_text())
workflow = str(work / "realboot.yaml")
boot = {"phase": phase, "pid_in_namespace": os.getpid(), "pid_namespace": os.readlink("/proc/self/ns/pid"),
        "boot_token": os.urandom(8).hex(), "at": time.time()}
(work / f"{phase}-identity.json").write_text(json.dumps(boot, indent=2) + "\n")


def namespace_pids():
    return sorted(int(p) for p in os.listdir("/proc") if p.isdigit() and int(p) != 1)


if phase == "boot1":
    shutdown = {"requested": False}

    def on_term(signum, frame):
        shutdown["requested"] = True

    signal.signal(signal.SIGTERM, on_term)
    with (work / "native" / "boot1-start.stdout").open("x") as out, (work / "native" / "boot1-start.stderr").open("x") as err:
        child = subprocess.Popen(base + ["start", "--run-id", run_id, workflow], cwd=work, env=env, stdout=out, stderr=err)
    while not shutdown["requested"] and child.poll() is None:
        time.sleep(0.05)
    record = {"shutdown_requested": shutdown["requested"], "start_exit_before_shutdown": child.poll(),
              "pids_at_shutdown": namespace_pids()}
    for pid in record["pids_at_shutdown"]:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            while os.waitpid(-1, os.WNOHANG)[0] > 0:
                pass
        except ChildProcessError:
            pass
        if not namespace_pids():
            break
        time.sleep(0.05)
    record["start_exit"] = child.poll()
    record["pids_left_for_kernel_kill"] = namespace_pids()
    record["orderly_seconds"] = round(20 - max(0.0, deadline - time.monotonic()), 2)
    (work / "boot1-shutdown.json").write_text(json.dumps(record, indent=2) + "\n")
    sys.exit(0)

if phase == "boot2":
    first = json.loads((work / "boot1-identity.json").read_text())
    # A pid-namespace inode number can be recycled once the old namespace is destroyed
    # (observed in the first full run), so identity is the random per-boot token plus
    # boot1's completed shutdown record, not the inode alone.
    if first["boot_token"] == boot["boot_token"] or not (work / "boot1-shutdown.json").exists():
        raise SystemExit("Boot identity did not change")
    (work / "release-finalize").touch(exist_ok=False)
    result = subprocess.run(base + ["retry", "--run-id", run_id, "--step", "finalize", workflow],
                            cwd=work, env=env, capture_output=True, text=True, timeout=240)
    (work / "native" / "boot2-retry.stdout").write_text(result.stdout)
    (work / "native" / "boot2-retry.stderr").write_text(result.stderr)
    (work / "boot2-service.json").write_text(json.dumps({"retry_exit": result.returncode,
                                                         "pids_after_retry": namespace_pids()}, indent=2) + "\n")
    sys.exit(result.returncode)
