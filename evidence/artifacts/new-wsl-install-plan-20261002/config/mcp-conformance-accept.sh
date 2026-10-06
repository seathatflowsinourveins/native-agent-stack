#!/usr/bin/env bash
# Local lifecycle checks around unchanged upstream conformance commands.
# conformance@c321dd3:src/sdk-runner/index.ts:70-126 (owned POSIX groups/escalation).
# util-linux@5305e6c:sys-utils/unshare.1.adoc:81-91,118-119;setsid.1.adoc:21-32.
set -euo pipefail
helper="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"
stage="${1:-post_install}"
package='@modelcontextprotocol/conformance@0.2.0-alpha.11'
source_dir="${tool_root:?}/mcp-conformance-source-0.2.0-alpha.11"
# External URL targets are unqualified in the private network namespace.
# Source: docs/decisions/2026-10-06-native-plan-gate1-repairs.md:23;
# conformance@c321dd3:src/sdk-runner/index.ts:70-126; util-linux@5305e6c:sys-utils/unshare.1.adoc:81-91.
if [[ ( "$stage" == after_sign_in || "$stage" == __isolated_after ) && -n "${MCP_CONFORMANCE_SERVER_URL:-}" ]]; then
  printf 'needs_owner: MCP_CONFORMANCE_SERVER_URL requires an owner-qualified startup adapter or fixture inside the isolated loopback namespace; external targets remain unqualified.\n' >&2
  exit 78
fi
snapshot_namespace() {
  if ss -ltnH > "$run_dir/namespace-listeners.pending"; then
    mv -- "$run_dir/namespace-listeners.pending" "$run_dir/namespace-listeners.txt"
  else
    rm -f -- "$run_dir/namespace-listeners.pending"
    return 1
  fi
}
case "$stage" in
  __isolated_post|__isolated_after)
    run_dir="${2:?}"
    ip link set lo up
    readlink /proc/self/ns/net > "$run_dir/net-namespace.txt"
    trap snapshot_namespace EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    if [[ "$stage" == __isolated_post ]]; then
      cd -- "$source_dir"
      npm test 2>&1 | tee "$run_dir/upstream-tests.log"
      cd -- "${plan_dir:?}"
      npx --offline --yes --ignore-scripts "$package" list --requirements 2026-07-28
    else
if [[ -z "${MCP_CONFORMANCE_SERVER_URL:-}" && -z "${MCP_CONFORMANCE_CLIENT_COMMAND:-}" ]]; then
  printf 'Select an owner-qualified MCP_CONFORMANCE_CLIENT_COMMAND or fixture that runs inside the isolated loopback namespace. External server URLs remain unqualified.\n' >&2
  exit 78
fi
extra=()
if [[ -n "${MCP_CONFORMANCE_EXPECTED_FAILURES:-}" ]]; then
  [[ -f "$MCP_CONFORMANCE_EXPECTED_FAILURES" ]]
  extra+=(--expected-failures "$MCP_CONFORMANCE_EXPECTED_FAILURES")
fi
umask 077
state="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/mcp-protocol-conformance"
install -d -m 0700 -- "$state"
run="$(mktemp -d "$state/conformance.XXXXXXXX")"
cd "$run"
if [[ -n "${MCP_CONFORMANCE_SERVER_URL:-}" ]]; then
  npx --offline --yes --ignore-scripts @modelcontextprotocol/conformance@0.2.0-alpha.11 server --url "$MCP_CONFORMANCE_SERVER_URL" --requirements 2026-07-28 "${extra[@]}"
fi
if [[ -n "${MCP_CONFORMANCE_CLIENT_COMMAND:-}" ]]; then
  npx --offline --yes --ignore-scripts @modelcontextprotocol/conformance@0.2.0-alpha.11 client --command "$MCP_CONFORMANCE_CLIENT_COMMAND" --requirements 2026-07-28 "${extra[@]}"
fi
    fi
    exit 0 ;;
  __worker)
    run_dir="${2:?}"
    job_stage="${3:?}"
    [[ "$$" == 1 ]] || { printf 'Refusing worker outside owned PID namespace.\n' >&2; exit 3; }
    trap 'exit 130' INT
    trap 'exit 143' TERM
    readlink /proc/self/ns/pid > "$run_dir/pid-namespace.txt"
    if [[ "$job_stage" == post_install ]]; then
      cd -- "$source_dir"
      npm ci --ignore-scripts
      npm run check
    fi
    # Pre-fetch release bytes; node -e 0 starts no application on host networking.
    cd -- "${plan_dir:?}"
    npx --yes --ignore-scripts --package "$package" -- node -e '0'
    isolated_stage=__isolated_post
    [[ "$job_stage" != after_sign_in ]] || isolated_stage=__isolated_after
    unshare --net "$BASH" "$helper" "$isolated_stage" "$run_dir"
    exit 0 ;;
  post_install|after_sign_in) ;;
  *) printf 'Unsupported conformance lifecycle stage.\n' >&2; exit 2 ;;
esac
if [[ "$stage" == after_sign_in && -z "${MCP_CONFORMANCE_SERVER_URL:-}" && -z "${MCP_CONFORMANCE_CLIENT_COMMAND:-}" ]]; then
  printf 'needs_user: select an adapter that runs inside the isolated loopback namespace.\n' >&2
  exit 78
fi
for command in setsid unshare ip ss ps python3 npm npx tee; do
  command -v "$command" >/dev/null || { printf 'needs_owner: missing lifecycle prerequisite %s.\n' "$command" >&2; exit 3; }
done
umask 077
state="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/mcp-protocol-conformance"
mkdir -p -- "$state"
run_dir="$(mktemp -d "$state/lifecycle.XXXXXXXX")"
# node@v24.21.0:doc/api/net.md IPC paths are limited to 107 bytes on Linux.
# Keep tsx's UID/PID pipe suffix beneath that limit; never fall back to /tmp.
temp_root="${XDG_CACHE_HOME:-$HOME/.cache}/mcp"
mkdir -p -- "$temp_root"
TMPDIR="$(mktemp -d "$temp_root/run.XXXXXXXX")"
export TMPDIR
python3 - "$TMPDIR" <<'PY'
import os, sys
assert len(os.fsencode(sys.argv[1])) <= 85, "needs_owner: conformance cache path is too long for native IPC"
PY
printf 'CONFORMANCE_RUN_DIR=%s\n' "$run_dir" >&2
owned_group=''
leader_start=''
pending_signal=0
leader_matches() {
  [[ -n "$owned_group" && -n "$leader_start" ]] || return 1
  local current_start
  current_start="$(awk '{print $22}' "/proc/$owned_group/stat" 2>/dev/null)" || return 1
  [[ "$current_start" == "$leader_start" ]]
}
group_matches() {
  leader_matches || return 1
  local group_session
  group_session="$(ps -o pgid=,sid= -p "$owned_group")" || return 1
  [[ "$(xargs <<< "$group_session")" == "$owned_group $owned_group" ]]
}
cleanup() {
  rc=$?
  trap - EXIT
  trap '' INT TERM
  # Do not signal a recycled PID/group after its owned leader has exited.
  if group_matches; then
    kill -TERM -- "-$owned_group" 2>/dev/null || true
    for ((i=0; i<50; i++)); do
      group_matches || break
      sleep 0.1
    done
    if group_matches; then
      kill -KILL -- "-$owned_group" 2>/dev/null || true
    fi
  elif leader_matches; then
    # A live launched child whose group was never established is our exact PID.
    kill -KILL "$owned_group" 2>/dev/null || true
  fi
  [[ -z "$owned_group" ]] || wait "$owned_group" 2>/dev/null || true
  ss -ltnpH > "$run_dir/host-after.txt" || rc=1
  if ! python3 - "$run_dir" "$owned_group" "$rc" <<'PY'
import json, os, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
pid_file = root / "pid-namespace.txt"
pid_namespace = pid_file.read_text().strip() if pid_file.is_file() else None
net_file = root / "net-namespace.txt"
net_namespace = net_file.read_text().strip() if net_file.is_file() else None
remaining = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdecimal():
        continue
    for kind, expected in (("pid", pid_namespace), ("net", net_namespace)):
        if expected is None:
            continue
        try:
            actual = os.readlink(entry / "ns" / kind)
        except OSError:
            continue
        if actual == expected:
            remaining.append(int(entry.name))
assert not remaining, "Owned namespace processes remain"
group = sys.argv[2]
if group:
    rows = subprocess.run(["ps", "-eo", "pgid=,stat="], capture_output=True, text=True, check=True).stdout.splitlines()
    assert not any(parts[0] == group and not parts[1].startswith("Z")
                   for row in rows if len(parts := row.split()) == 2), "Owned process group remains"
def ports(path):
    result = set()
    if path.is_file():
        for line in path.read_text().splitlines():
            result.add(int(line.split()[3].rsplit(":", 1)[1]))
    return result
snapshot = root / "namespace-listeners.txt"
observed = snapshot.is_file()
used = ports(snapshot) if observed else None
# Port numbers alone cannot attribute a foreign host service to this run.
# No process remains in the private, non-persistent network/PID namespaces.
proof = {"owned_namespace_processes_remaining": 0 if pid_namespace is not None else None,
         "owned_group_processes_remaining": 0,
         "run_port_listeners_remaining": 0 if observed and net_namespace is not None else None,
         "observed_namespace_ports": sorted(used) if used is not None else None,
         "listener_observation_available": observed,
         "host_services_on_observed_ports": sorted(used & ports(root / "host-after.txt")) if used is not None else None,
         "scope": "owned run; unchanged upstream tests and host acceptance are separate"}
(root / "cleanup.json").write_text(json.dumps(proof) + "\n")
if int(sys.argv[3]) == 0:
    assert pid_namespace is not None and net_namespace is not None and observed, "Successful run lacks complete cleanup observations"
print("Conformance owned namespace/group cleanup observed; listener snapshot " + ("available" if observed else "unavailable"), file=sys.stderr)
PY
  then [[ "$rc" != 0 ]] || rc=1; fi
  exit "$rc"
}
trap cleanup EXIT
# Defer cancellation through the bounded ownership-registration section.
trap 'pending_signal=130' INT
trap 'pending_signal=143' TERM
set +m
setsid --wait unshare --user --map-root-user --pid --fork --mount-proc --kill-child \
  "$BASH" "$helper" __worker "$run_dir" "$stage" &
owned_group=$!
# Capture the exact launched child before group registration can be delayed.
[[ ! -r "/proc/$owned_group/stat" ]] || leader_start="$(awk '{print $22}' "/proc/$owned_group/stat" 2>/dev/null)" || leader_start=''
for ((i=0; i<100; i++)); do
  group="$(ps -o pgid= -p "$owned_group" | tr -d ' ')" || group=''
  if [[ "$group" == "$owned_group" ]]; then
    leader_start="$(awk '{print $22}' "/proc/$owned_group/stat" 2>/dev/null)" || leader_start=''
    [[ -n "$leader_start" ]] && break
  fi
  kill -0 "$owned_group" 2>/dev/null || break
  sleep 0.01
done
if kill -0 "$owned_group" 2>/dev/null && ! group_matches; then
  printf 'needs_owner: owned process group not established.\n' >&2
  exit 3
fi
printf '%s\n' "$owned_group" > "$run_dir/owned-group.txt"
trap 'exit 130' INT
trap 'exit 143' TERM
[[ "$pending_signal" == 0 ]] || exit "$pending_signal"
rc=0
wait "$owned_group" || rc=$?
exit "$rc"
