#!/usr/bin/env python3
"""Check what a reproduce-vc-search.sh version does when it cannot establish that it owns the daemon.

Usage: ownership_failure_check.py <script-dir> <tarball> <search-outputs-dir>
  <script-dir>          holds the reproduce-vc-search.sh version under test and its helpers
  <tarball>             the real byterover-cli-3.16.1.tgz: the script checks its sha512 against the pin
  <search-outputs-dir>  a run directory whose 20-, 21- and 22-search-*.stdout files the stub replays

Runs the script with stub `npm` and `brv` commands and a fake daemon, all of its own, as PID 1's
children in a new user and PID namespace with its own /proc (`unshare --user --map-current-user
--pid --fork --mount-proc --kill-child`). Nothing outside the namespace is visible to the script,
and the kernel stops whatever is left there when the check ends. No ByteRover code runs and
nothing is sent over the network.

The stub npm answers `view` with the pinned integrity, copies <tarball> for `pack`, installs the
stub brv for `install` and succeeds for `ls`. The stub brv answers `--version`, `vc` and `status`
with a line of text and `search` with the retained output for that query. Its first `vc init`
starts the fake daemon: a Python sleeper in a new session that appends each SIGTERM, SIGINT or
SIGHUP it receives to a file outside the workspace and exits on SIGTERM.

Cases, each with a fresh TMPDIR, so the script's mktemp workspace is the only entry there:
  owned           the fake daemon carries a <workspace>/prefix/.../brv-server.js argument, and the
                  stub writes <workspace>/xdg/data/brv/daemon.json with its pid.
  record-fails    daemon.json names the fake daemon, but its brv-server.js argument lies outside
                  the prefix, so `owned_processes.py record` refuses it after every command.
  no-daemon-file  the fake daemon runs from the prefix, but no daemon.json is written.
  no-pidfd        as owned, but every python3 the script starts loses os.pidfd_open (a
                  sitecustomize.py on PYTHONPATH deletes it), as on a host without pidfd support.

Expected before the run:
  owned           exit 0, workspace removed, the daemon started, received SIGTERM and is gone;
                  the searches ran.
  record-fails    exit 4, workspace kept, the daemon started, received no signal and still runs;
                  the script stopped before the searches.
  no-daemon-file  exit 4, workspace kept, the daemon started, received no signal and still runs;
                  the searches ran.
  no-pidfd        exit 1, workspace removed, the daemon never started, no search ran.
Prints one JSON line per case, the processes still running in the namespace at the end, and a
summary. Exits 0 only when every expectation held. Local integration check.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PIN_INTEGRITY = "sha512-uI6zETcy5QO6H29/sdn4BKGWzJl658sjHWxcpO+LHYcmxQj1mAmmi9lluqQZYoXXrnrbp+an8NYhjd5MKmDTcw=="
EXPECTED = {
    "owned": {"exit": 0, "workspace_kept": False, "daemon_started": True, "daemon_signals": ["SIGTERM"],
              "daemon_running": False, "searches_ran": True},
    "record-fails": {"exit": 4, "workspace_kept": True, "daemon_started": True, "daemon_signals": [],
                     "daemon_running": True, "searches_ran": False},
    "no-daemon-file": {"exit": 4, "workspace_kept": True, "daemon_started": True, "daemon_signals": [],
                       "daemon_running": True, "searches_ran": True},
    "no-pidfd": {"exit": 1, "workspace_kept": False, "daemon_started": False, "daemon_signals": [],
                 "daemon_running": False, "searches_ran": False},
}
SITECUSTOMIZE = """import os
if os.environ.get("STUB_NO_PIDFD") == "1" and hasattr(os, "pidfd_open"):
    del os.pidfd_open
"""
STUB_NPM = r"""#!/bin/sh
# Stub npm for ownership_failure_check.py.
after() {  # after <flag> <args...>: the argument that follows <flag>
  flag=$1; shift
  while [ $# -gt 1 ]; do [ "$1" = "$flag" ] && { printf '%s\n' "$2"; return 0; }; shift; done
  return 1
}
case "$1" in
  view) printf '%s\n' "$STUB_PIN_INTEGRITY" ;;
  pack) dest=$(after --pack-destination "$@") && cp "$STUB_TARBALL" "$dest/byterover-cli-3.16.1.tgz" \
          && echo byterover-cli-3.16.1.tgz ;;
  install) prefix=$(after --prefix "$@") && mkdir -p "$prefix/bin" && cp "$STUB_BRV" "$prefix/bin/brv" \
             && chmod 755 "$prefix/bin/brv" && echo "stub: installed brv" ;;
  ls) echo "stub npm ls" ;;
  *) echo "stub npm: unexpected arguments" >&2; exit 2 ;;
esac
"""
STUB_BRV = r"""#!/bin/sh
# Stub brv for ownership_failure_check.py.
prefix=$(cd "$(dirname "$0")/.." && pwd -P)
workspace=$(dirname "$prefix")
if [ "${1:-}" = vc ] && [ "${2:-}" = init ] && [ ! -e "$STUB_STATE/daemon.pid" ]; then
  server="$prefix/lib/node_modules/byterover-cli/dist/server/infra/daemon/brv-server.js"
  [ "$STUB_CASE" = record-fails ] && server="$workspace/elsewhere/brv-server.js"
  python3 "$STUB_DAEMON" "$STUB_STATE" "$server" < /dev/null > /dev/null 2>&1 &
  tries=0
  while [ ! -s "$STUB_STATE/daemon.pid" ] && [ "$tries" -lt 100 ]; do sleep 0.05; tries=$((tries + 1)); done
  if [ "$STUB_CASE" != no-daemon-file ]; then
    mkdir -p "$XDG_DATA_HOME/brv"
    printf '{"pid": %s, "port": 50000, "startedAt": 1, "version": "stub"}\n' "$(cat "$STUB_STATE/daemon.pid")" \
      > "$XDG_DATA_HOME/brv/daemon.json"
  fi
fi
case "${1:-}" in
  --version) echo "byterover-cli/3.16.1 (stub)" ;;
  vc|status) echo "stub brv $1" ;;
  search)
    case "$2" in
      "rate limiter") cat "$STUB_SEARCH_DIR/20-search-positive.stdout" ;;
      invoices) cat "$STUB_SEARCH_DIR/21-search-second-positive.stdout" ;;
      *) cat "$STUB_SEARCH_DIR/22-search-negative.stdout" ;;
    esac ;;
  *) echo "stub brv: unexpected arguments" >&2; exit 2 ;;
esac
"""
STUB_DAEMON = r"""import os, signal, sys, time
from pathlib import Path
state = Path(sys.argv[1])
os.setsid()
def on_signal(signum, frame):
    with open(state / "daemon.signals", "a", encoding="utf-8") as handle:
        handle.write(signal.Signals(signum).name + "\n")
    if signum == signal.SIGTERM:
        sys.exit(0)
for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(signum, on_signal)
(state / "daemon.pid").write_text(str(os.getpid()), encoding="utf-8")
while True:
    time.sleep(1)
"""


def running(pid: int) -> bool:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat[stat.rindex(")") + 2:].split()[0] not in ("Z", "X")


def running_in_namespace() -> list[str]:
    """Names of the processes still running here besides this one; inside the namespace only."""
    names = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid() or not running(int(entry.name)):
            continue
        try:
            args = [part.decode(errors="replace") for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        names.append(Path(args[1] if len(args) > 1 else args[0] if args else "?").name)
    return sorted(names)


def run_case(case: str, script_dir: Path, root: Path, stub_bin: Path, tarball: Path, search_dir: Path) -> dict:
    case_dir = root / case
    tmp, state, out = case_dir / "tmp", case_dir / "stub-state", case_dir / "out"
    for directory in (tmp, state, out):
        directory.mkdir(parents=True)
    env = dict(os.environ)
    env.update({"PATH": f"{stub_bin}:{env.get('PATH', '/usr/bin:/bin')}", "TMPDIR": str(tmp), "STUB_CASE": case,
                "STUB_STATE": str(state), "STUB_TARBALL": str(tarball), "STUB_SEARCH_DIR": str(search_dir),
                "STUB_BRV": str(stub_bin / "stub-brv"), "STUB_DAEMON": str(stub_bin / "stub-daemon.py"),
                "STUB_PIN_INTEGRITY": PIN_INTEGRITY})
    if case == "no-pidfd":
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root / "pycustom"), env.get("PYTHONPATH")]))
        env["STUB_NO_PIDFD"] = "1"
    with open(case_dir / "script.stderr", "wb") as stderr:
        done = subprocess.run(["sh", str(script_dir / "reproduce-vc-search.sh"), str(out)], env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr, timeout=600)
    kept = [entry for entry in tmp.iterdir() if (entry / "prefix").is_dir()]
    pid_file, signal_file = state / "daemon.pid", state / "daemon.signals"
    pid = int(pid_file.read_text()) if pid_file.exists() else None
    steps = (out / "steps.log").read_text(encoding="utf-8").splitlines() if (out / "steps.log").exists() else []
    row = {"case": case, "exit": done.returncode, "workspace_kept": bool(kept),
           "kept_workspace_has_daemon_json": any((entry / "xdg/data/brv/daemon.json").exists() for entry in kept),
           "daemon_started": pid is not None,
           "daemon_signals": signal_file.read_text().split() if signal_file.exists() else [],
           "daemon_running": pid is not None and running(pid),
           "searches_ran": (out / "20-search-positive.stdout").exists(),
           "search_checks_matched": any(line.endswith("every check matched its intended outcome: yes")
                                        for line in steps),
           "steps_log_cleanup_lines": [line.split(" ", 1)[1].replace(str(root), "<check-root>") for line in steps
                                       if "FAIL" in line or "90-stop" in line or "cleanup:" in line]}
    row["expectation_held"] = all(row[key] == value for key, value in EXPECTED[case].items())
    return row


def inside(script_dir: Path, tarball: Path, search_dir: Path, root: Path) -> int:
    if os.getpid() != 1:
        print(json.dumps({"event": "abort: not PID 1 of a new PID namespace"}))
        return 2
    stub_bin = root / "bin"
    stub_bin.mkdir()
    for name, text, mode in (("npm", STUB_NPM, 0o755), ("stub-brv", STUB_BRV, 0o755),
                             ("stub-daemon.py", STUB_DAEMON, 0o644)):
        (stub_bin / name).write_text(text, encoding="utf-8")
        (stub_bin / name).chmod(mode)
    (root / "pycustom").mkdir()
    (root / "pycustom" / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    results =[run_case(case, script_dir, root, stub_bin, tarball, search_dir) for case in EXPECTED]
    for row in results:
        print(json.dumps(row))
    print(json.dumps({"event": "still running in the namespace besides the check", "processes": running_in_namespace()}))
    passed = len(results) == len(EXPECTED) and all(row["expectation_held"] for row in results)
    print(json.dumps({"cases": len(results), "all_expectations_held": passed}))
    sys.stdout.flush()
    return 0 if passed else 1


def main(argv: list[str]) -> int:
    if len(argv) == 5 and argv[0] == "--inside":
        return inside(*(Path(arg) for arg in argv[1:]))
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    script_dir, tarball, search_dir = (Path(arg).resolve() for arg in argv)
    root = Path(tempfile.mkdtemp(prefix="ownership-check-"))
    try:
        done = subprocess.run(["unshare", "--user", "--map-current-user", "--pid", "--fork", "--mount-proc",
                               "--kill-child", sys.executable, str(Path(__file__).resolve()), "--inside",
                               str(script_dir), str(tarball), str(search_dir), str(root)])
        return done.returncode
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
