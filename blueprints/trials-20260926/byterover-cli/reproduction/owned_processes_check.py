#!/usr/bin/env python3
"""Check owned_processes.py against fake processes, with every expectation written before the run.

Usage: owned_processes_check.py

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

HELPER = Path(__file__).resolve().parent / "owned_processes.py"
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


def helper(*args: str) -> tuple[int, list[dict]]:
    done = subprocess.run([sys.executable, str(HELPER), *args], capture_output=True, text=True, timeout=60)
    return done.returncode, [json.loads(line) for line in done.stdout.splitlines() if line.strip()]


def alive(process: subprocess.Popen) -> bool:
    return process.poll() is None


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
            stat = Path(f"/proc/{bystander.pid}/stat").read_text()
            real_start = int(stat[stat.rindex(")") + 2:].split()[19])
            ledger = root / "ledger-reused"
            ledger.write_text(json.dumps({"pid": bystander.pid, "starttime": real_start - 1, "ppid": os.getpid(),
                                          "pgrp": os.getpgrp(), "session": os.getsid(0), "role": "daemon",
                                          "script": "brv-server.js"}) + "\n")
            rc, rows = helper("stop", str(ledger))
            signals = [row["signals_sent"] for row in rows if "role" in row]
            held = rc == 0 and signals == [[]] and alive(bystander)
            results.append({"case": "reused-pid", "stop_exit": rc, "signals_sent": signals,
                            "bystander_alive": alive(bystander), "expectation_held": held})
        finally:
            for process in started:
                if alive(process):
                    process.send_signal(signal.SIGKILL)
                    process.wait(timeout=5)
    for row in results:
        print(json.dumps(row))
    passed = len(results) == 5 and all(row["expectation_held"] for row in results)
    print(json.dumps({"cases": len(results), "all_expectations_held": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
