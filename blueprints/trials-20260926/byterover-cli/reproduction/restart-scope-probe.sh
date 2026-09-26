#!/bin/sh
# Shows which processes a reproduce-vc-search.sh version's cleanup signals, without letting it
# see or signal any process outside the probe.
#
# Usage: sh restart-scope-probe.sh <script-dir> <output-dir>
#   <script-dir> holds the reproduce-vc-search.sh version under test and the helpers it calls
#   (check_search.py; owned_processes.py for the current version).
#
# The probe re-runs itself as PID 1 of a new user and PID namespace with its own /proc
# (`unshare --user --map-current-user --pid --fork --mount-proc --kill-child`). A process
# inside can see and signal only processes of that namespace, and the kernel kills whatever
# is left when the probe exits. Inside, the probe starts four decoys of its own: Python
# sleepers whose only link to ByteRover is one command-line argument.
#   control          /probe-decoys/unrelated-tool/worker.js       (matches no restart pattern)
#   other_client     /probe-decoys/other-install/bin/brv          (bin/brv: another install's CLI)
#   other_daemon     /probe-decoys/other-install/dist/server/infra/daemon/brv-server.js
#   unrelated_agent  /probe-decoys/unrelated-tool/agent-process.js (a generic file name)
# None of them belongs to the reproduction's install, data directory or process tree. The
# probe runs the script version and then reports, for each decoy, whether it is still running
# and its wait status (137 = killed by SIGKILL, 143 = the probe's own SIGTERM afterwards).
# Last, it lists the processes left in the namespace, which can only be the probe's own.
#
# Expected before the run: the version that ends with `brv restart` (run-20260926T0454Z)
# kills other_client, other_daemon and unrelated_agent and spares control. The current
# version spares all four. Both pass their search checks. TMPDIR and npm_config_cache pass
# through from the caller. Local integration check.
set -u
script_dir=${1:?usage: sh restart-scope-probe.sh <script-dir> <output-dir>}
out=${2:?usage: sh restart-scope-probe.sh <script-dir> <output-dir>}

if [ "${RESTART_SCOPE_PROBE_INSIDE:-}" != yes ]; then
  mkdir -p "$out"
  outer_ns=$(readlink /proc/self/ns/pid)
  exec env RESTART_SCOPE_PROBE_INSIDE=yes RESTART_SCOPE_PROBE_OUTER_NS="$outer_ns" \
    unshare --user --map-current-user --pid --fork --mount-proc --kill-child sh "$0" "$script_dir" "$out"
fi

script_dir=$(cd "$script_dir" && pwd)
out=$(cd "$out" && pwd)
report="$out/probe.log"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$report"; }
inner_ns=$(readlink /proc/self/ns/pid)
if [ "$$" -ne 1 ] || [ "$inner_ns" = "${RESTART_SCOPE_PROBE_OUTER_NS:-}" ]; then
  say "ABORT: not PID 1 of a new PID namespace (pid $$, namespace $inner_ns)"
  exit 2
fi
say "probe is PID $$ in PID namespace $inner_ns; the caller's is $RESTART_SCOPE_PROBE_OUTER_NS"
say "script under test: reproduce-vc-search.sh sha256 $(sha256sum "$script_dir/reproduce-vc-search.sh" | cut -d' ' -f1)"

decoys=""
start_decoy() {  # start_decoy <name> <argument>
  python3 -c 'import sys, time; time.sleep(float(sys.argv[1]))' 1800 "$2" &
  decoys="$decoys $1:$!"
  say "decoy $1: pid $! with argument $2"
}
start_decoy control /probe-decoys/unrelated-tool/worker.js
start_decoy other_client /probe-decoys/other-install/bin/brv
start_decoy other_daemon /probe-decoys/other-install/dist/server/infra/daemon/brv-server.js
start_decoy unrelated_agent /probe-decoys/unrelated-tool/agent-process.js
sleep 1

sh "$script_dir/reproduce-vc-search.sh" "$out/run"
say "reproduce-vc-search.sh exit status: $?"

for entry in $decoys; do
  name=${entry%%:*}
  pid=${entry#*:}
  state=$(sed 's/.*) //' "/proc/$pid/stat" 2>/dev/null | cut -d' ' -f1)
  if [ -n "$state" ] && [ "$state" != Z ]; then
    kill "$pid"
    wait "$pid"
    say "decoy $name: RUNNING after the script; stopped by the probe now (wait status $?)"
  else
    wait "$pid"
    say "decoy $name: NOT RUNNING after the script (wait status $?)"
  fi
done

left=$(python3 -c '
import os
from pathlib import Path
skip = {1, os.getpid(), os.getppid()}
rows = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit() or int(entry.name) in skip:
        continue
    try:
        stat = (entry / "stat").read_text()
        args = (entry / "cmdline").read_bytes().split(b"\0")
    except OSError:
        continue
    state = stat[stat.rindex(")") + 2:].split()[0]
    name = next((a for a in args[1:] if a.endswith(b".js")), args[0]).decode(errors="replace")
    rows.append((int(entry.name), state, os.path.basename(name) or "?"))
print(" ".join(f"{pid}:{state}:{name}" for pid, state, name in sorted(rows)) or "none")
')
say "processes left in this namespace besides the probe and its lister (pid:state:name): $left"
