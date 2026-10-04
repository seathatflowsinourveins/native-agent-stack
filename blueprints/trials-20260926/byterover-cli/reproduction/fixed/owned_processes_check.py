#!/usr/bin/env python3
"""Check owned_processes.py against fake processes, with every expectation written before the run.

Usage: owned_processes_check.py [<owned_processes.py>]
  The helper under test defaults to the owned_processes.py next to this file.

Extended copy of ../owned_processes_check.py, which stays byte-identical as the version behind
owned-processes-check-20260926T110019Z.txt. The first five cases are that version's; the last
four are new and cover the helper when pidfd support is missing or broken.

Starts only its own short-lived Python sleepers, which stand in for ByteRover processes. Each
fake daemon starts in a new session, as ByteRover's transport client starts the real one, and
carries a <prefix>/.../brv-server.js argument; it forks one child carrying an agent-process.js
argument. A decoy carries a brv-server.js argument outside the prefix and is not a descendant.
The cases:

  graceful      the daemon exits on SIGTERM after stopping its child: record finds 2, stop sends
                SIGTERM to the daemon only, both are gone, the decoy is untouched.
  stubborn      daemon and child ignore SIGTERM: stop sends SIGTERM, then SIGKILL to both after
                10 s, both are gone, the decoy is untouched.
  foreign-file  the daemon file names the decoy: record exits 1 and records nothing.
  unreadable    the daemon file is not JSON: record exits 1 and records nothing.
  reused-pid    a ledger entry names a live sleeper with a different start time: stop sends it
                nothing and it keeps running.
  preflight     preflight exits 0 on this host.
  pidfd-open-missing, pidfd-open-enosys, pidfd-send-missing
                the helper runs in an interpreter where os.pidfd_open is deleted, where it raises
                OSError(ENOSYS) as on a kernel without the call, or where
                signal.pidfd_send_signal is deleted. A ledger names a live sleeper with its real
                start time, so a helper that signals by pid would stop it. Expected: stop exits 1
                and reports no signal, the sleeper keeps running, and preflight exits 1.

Prints one JSON line per case and exits 0 only when every expectation held. Every process it
started is stopped by this script at the end. Local integration check of our own helper.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HELPER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "owned_processes.py"
SLEEPER = ("import signal,sys,time\n"
           "if sys.argv[1]=='stubborn': signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
           "time.sleep(300)")
FAKE_DAEMON = r"""
import os, signal, sys, time
mode, server_arg, agent_arg = sys.argv[1:4]
child = os.fork()
if child == 0:
    os.execv(sys.executable, [sys.executable, "-c", SLEEPER, mode, agent_arg])
def on_term(signum, frame):
    os.kill(child, signal.SIGTERM)
    os.waitpid(child, 0)
    sys.exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN if mode == "stubborn" else on_term)
while True:
    time.sleep(1)
""".replace("SLEEPER", repr(SLEEPER))
# Each patch runs before the helper, in the same interpreter; RUN_HELPER then runs the helper as __main__.
PATCHES = {
    "pidfd-open-missing": "import os\ndel os.pidfd_open\n",
    "pidfd-open-enosys": ("import errno, os\n"
                          "def _enosys(*args, **kwargs):\n"
                          "    raise OSError(errno.ENOSYS, os.strerror(errno.ENOSYS))\n"
                          "os.pidfd_open = _enosys\n"),
    "pidfd-send-missing": "import signal\ndel signal.pidfd_send_signal\n",
}
RUN_HELPER = "import runpy, sys\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n"


def helper(*args: str, patch: str | None = None) -> tuple[int, list[dict]]:
    command = [sys.executable, str(HELPER), *args] if patch is None else \
        [sys.executable, "-c", PATCHES[patch] + RUN_HELPER, str(HELPER), *args]
    done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    rows = []
    for line in done.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            rows.append({"unparsed_output_line": True})
    return done.returncode, rows


def alive(process: subprocess.Popen) -> bool:
    return process.poll() is None


def start_time(pid: int) -> int:
    stat = Path(f"/proc/{pid}/stat").read_text()
    return int(stat[stat.rindex(")") + 2:].split()[19])


def main() -> int:
    results = []
    started: list[subprocess.Popen] = []
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        prefix = root / "prefix"
        server = prefix / "lib/node_modules/byterover-cli/dist/server/infra/daemon/brv-server.js"
        agent = prefix / "lib/node_modules/byterover-cli/dist/server/infra/daemon/agent-process.js"
        decoy = subprocess.Popen([sys.executable, "-c", SLEEPER, "plain", str(root / "other-install/brv-server.js")])
        started.append(decoy)
        try:
            for mode in ("graceful", "stubborn"):
                daemon = subprocess.Popen([sys.executable, "-c", FAKE_DAEMON, mode, str(server), str(agent)],
                                          start_new_session=True)
                started.append(daemon)
                time.sleep(0.5)
                daemon_file = root / f"daemon-{mode}.json"
                daemon_file.write_text(json.dumps({"pid": daemon.pid, "port": 50000, "startedAt": 1}))
                ledger = root / f"ledger-{mode}"
                rc_record, recorded = helper("record", str(ledger), str(daemon_file), f"{prefix}/")
                rc_stop, stopped = helper("stop", str(ledger))
                daemon.wait(timeout=5)
                rows = [row for row in stopped if "role" in row]
                summary = stopped[-1] if stopped else {}
                roles = sorted(row["role"] for row in recorded if row.get("event") == "recorded")
                signals = {row["role"]: row["signals_sent"] for row in rows}
                expected_signals = ({"daemon": ["SIGTERM"], "descendant of the daemon": []} if mode == "graceful"
                                    else {"daemon": ["SIGTERM", "SIGKILL"], "descendant of the daemon": ["SIGKILL"]})
                daemon_row = next((row for row in recorded if row.get("role") == "daemon"), {})
                held = (rc_record == 0 and roles == ["daemon", "descendant of the daemon"]
                        and daemon_row.get("pgrp") == daemon.pid == daemon_row.get("session")
                        and rc_stop == 0 and summary.get("all_gone") is True and signals == expected_signals
                        and alive(decoy))
                results.append({"case": mode, "record_exit": rc_record, "recorded_roles": roles,
                                "daemon_pgrp_and_session_equal_its_pid": daemon_row.get("pgrp") == daemon.pid
                                == daemon_row.get("session"),
                                "stop_exit": rc_stop, "signals_sent": signals, "all_gone": summary.get("all_gone"),
                                "stop_seconds": summary.get("seconds"), "decoy_alive": alive(decoy),
                                "expectation_held": held})

            foreign = root / "daemon-foreign.json"
            foreign.write_text(json.dumps({"pid": decoy.pid, "port": 50000, "startedAt": 1}))
            rc, rows = helper("record", str(root / "ledger-foreign"), str(foreign), f"{prefix}/")
            written = (root / "ledger-foreign").exists()
            held = rc == 1 and not written and alive(decoy)
            results.append({"case": "foreign-file", "record_exit": rc, "ledger_written": written,
                            "decoy_alive": alive(decoy), "expectation_held": held})

            broken = root / "daemon-broken.json"
            broken.write_text("{not json")
            rc, rows = helper("record", str(root / "ledger-broken"), str(broken), f"{prefix}/")
            written = (root / "ledger-broken").exists()
            held = rc == 1 and not written
            results.append({"case": "unreadable", "record_exit": rc, "ledger_written": written,
                            "expectation_held": held})

            bystander = subprocess.Popen([sys.executable, "-c", SLEEPER, "plain", str(server)])
            started.append(bystander)
            time.sleep(0.3)
            real_start = start_time(bystander.pid)
            ledger = root / "ledger-reused"
            ledger.write_text(json.dumps({"pid": bystander.pid, "starttime": real_start - 1, "ppid": os.getpid(),
                                          "pgrp": os.getpgrp(), "session": os.getsid(0), "role": "daemon",
                                          "script": "brv-server.js"}) + "\n")
            rc, rows = helper("stop", str(ledger))
            signals = [row["signals_sent"] for row in rows if "role" in row]
            held = rc == 0 and signals == [[]] and alive(bystander)
            results.append({"case": "reused-pid", "stop_exit": rc, "signals_sent": signals,
                            "bystander_alive": alive(bystander), "expectation_held": held})

            rc, rows = helper("preflight")
            results.append({"case": "preflight", "preflight_exit": rc, "expectation_held": rc == 0})

            for patch in PATCHES:
                sleeper = subprocess.Popen([sys.executable, "-c", SLEEPER, "plain", str(server)],
                                           start_new_session=True)
                started.append(sleeper)
                time.sleep(0.3)
                ledger = root / f"ledger-{patch}"
                ledger.write_text(json.dumps({"pid": sleeper.pid, "starttime": start_time(sleeper.pid),
                                              "ppid": os.getpid(), "pgrp": sleeper.pid, "session": sleeper.pid,
                                              "role": "daemon", "script": "brv-server.js"}) + "\n")
                rc_stop, rows = helper("stop", str(ledger), patch=patch)
                time.sleep(0.3)
                signals = [signal_name for row in rows for signal_name in row.get("signals_sent", [])]
                rc_preflight, _rows = helper("preflight", patch=patch)
                held = rc_stop == 1 and signals == [] and alive(sleeper) and rc_preflight == 1
                results.append({"case": patch, "stop_exit": rc_stop, "signals_sent": signals,
                                "sleeper_alive": alive(sleeper), "preflight_exit": rc_preflight,
                                "expectation_held": held})
        finally:
            for process in started:
                if alive(process):
                    process.send_signal(signal.SIGKILL)
                    process.wait(timeout=5)
    for row in results:
        print(json.dumps(row))
    passed = len(results) == 6 + len(PATCHES) and all(row["expectation_held"] for row in results)
    print(json.dumps({"cases": len(results), "all_expectations_held": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
