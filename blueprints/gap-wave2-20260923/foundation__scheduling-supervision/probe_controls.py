#!/usr/bin/env python3
"""Fix round 1: positive and negative controls for the two probes added to dagu_common.py.

1. listeners(): a loopback listener opened here must be reported for this pid (positive),
   and a pid set with no sockets must yield no rows (negative).
2. codex_exec_processes(): a synthetic process whose argv is `codex exec -F` (GNU tail run
   under argv[0] `codex`, waiting on a missing file named `exec` in a temp dir) must be counted
   (positive); a wrapper-shaped argv `timeout 30 codex exec -F` (tail again, under argv[0]
   `timeout`) must not be counted (negative), matching how a `timeout N codex exec` wrapper
   is excluded while its real codex child is counted.
Writes JSON to stdout. Every started process is killed.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dagu_common as dc  # noqa: E402


def spawn_as(argv0, args, cwd):
    return subprocess.Popen(["bash", "-c", 'exec -a "$0" tail "$@"', argv0, *args], cwd=cwd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    out = {"listener_positive": dc.listener_probe_self_test()}
    idle = subprocess.Popen(["sleep", "30"])
    try:
        out["listener_negative"] = {"pid": idle.pid, "rows": dc.listeners([idle.pid])}
    finally:
        idle.kill()
    with tempfile.TemporaryDirectory() as tmp:
        direct = spawn_as("codex", ["exec", "-F"], tmp)
        wrapper = spawn_as("timeout", ["30", "codex", "exec", "-F"], tmp)
        try:
            time.sleep(0.5)
            seen = dc.codex_exec_processes()
            out["codex_matcher_positive"] = {"argv": ["codex", "exec", "-F"], "counted": direct.pid in seen}
            out["codex_matcher_negative_wrapper"] = {"argv": ["timeout", "30", "codex", "exec", "-F"], "counted": wrapper.pid in seen}
            out["other_real_codex_exec_now"] = len({p for p in seen if p not in (direct.pid, wrapper.pid)})
        finally:
            direct.kill()
            wrapper.kill()
    out["all_controls_behaved"] = (out["listener_positive"]["detected"] and not out["listener_negative"]["rows"]
                                   and out["codex_matcher_positive"]["counted"]
                                   and not out["codex_matcher_negative_wrapper"]["counted"])
    out["ran_at"] = __import__("datetime").datetime.now().astimezone().isoformat()
    out["pid"] = os.getpid()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
