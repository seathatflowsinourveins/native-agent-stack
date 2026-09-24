#!/usr/bin/env python3
"""Enforced isolation wrapper (fix round 1).

Usage: enforce.py SIDECAR_JSON -- COMMAND...

Runs COMMAND inside `unshare -rnm --fork --kill-child` with loopback up and an empty tmpfs mounted over
$HOME/.mcporter, so the shared per-user mcporter daemon socket does not exist for anything in the namespace
(pathname Unix sockets ignore network namespaces, so hiding the path is what blocks contact) and the live
loopback services (ai-memory 49374, Qdrant 16333) are unreachable. The shared daemon is stat()ed outside the
namespace before and after, and the result goes to SIDECAR_JSON.
"""
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import iso  # noqa: E402

sidecar = pathlib.Path(sys.argv[1])
cmd = sys.argv[sys.argv.index("--") + 1:]
mc = iso.SHARED_DAEMON_DIR.parent
before = iso.shared_daemon_snapshot()
t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
inner = 'ip link set lo up && mount -t tmpfs -o size=1m,mode=0700 tmpfs "$1" && shift && exec "$@"'
p = subprocess.run(["unshare", "-rnm", "--fork", "--kill-child", "bash", "-c", inner, "enforce", str(mc), *cmd])
after = iso.shared_daemon_snapshot()
sidecar.write_text(json.dumps({"command": [iso.sanitize(c) for c in cmd], "started_at": t0,
                               "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "exit": p.returncode,
                               "namespace": "unshare -rnm --fork --kill-child; lo up; tmpfs over $HOME/.mcporter",
                               "shared_daemon_outside_before": before, "shared_daemon_outside_after": after,
                               "shared_daemon_unchanged": before == after}, indent=1) + "\n")
print("enforce exit", p.returncode, "shared unchanged", before == after)
sys.exit(p.returncode)
