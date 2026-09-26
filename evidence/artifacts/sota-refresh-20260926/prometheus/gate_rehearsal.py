#!/usr/bin/env python3
"""Failure-injection rehearsal of switch_gated.py on a scratch systemd --user unit; the production unit, its port and
its bin links are only read.

Usage: gate_rehearsal.py <tools-root> <switch_gated.py> <work-dir>

Scratch set-up: sota-refresh-gate-rehearsal-prometheus.service in $XDG_RUNTIME_DIR/systemd/user (tmpfs) with the live
unit's [Unit]/[Service]/[Install] settings (Type=simple, Restart=on-failure, RestartSec=5, StartLimitIntervalSec=60,
StartLimitBurst=3, UMask=0077, NoNewPrivileges, TimeoutStopSec=60), a fresh TSDB, a config that scrapes only itself
every 5 s on 127.0.0.1:29390 with one recording and one always-firing alerting rule and no alerting section, and a
scratch bin directory whose prometheus and promtool links start at the 3.14.0 prefix. The installed 3.14.0 and 3.15.0
prefixes are only executed. Two fake prefixes answer --version with the real 3.15.0 output, so preflight passes, and
then either exit 1 (a server that cannot start) or run the 3.14.0 server (a restart that leaves the old version
serving). For one case each, a systemctl shim first in PATH makes daemon-reload exit 1, or exit 0 without reloading.

  G0 --from-version 3.13.0 while 3.14.0 runs: exit 1, nothing changed
  G1 3.14.0 -> 3.15.0: exit 0, links promoted
  G2 the rollback with the same script, 3.15.0 -> 3.14.0: exit 0, links back
  G3 daemon-reload exits 1: exit 2 at gate daemon-reload, unit restored without a restart, links unchanged
  G4 daemon-reload exits 0 without reloading (the review's scenario): exit 2 at gate unit-loaded, as G3
  G5 the new server exits at start and crash-loops into the start limit: exit 2 at gate ready, restored
  G6 the restarted server reports 3.14.0: exit 2 at gates version and revision, restored
Each case starts with reset-failed on the scratch unit, so the start limit one case reaches does not carry over.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

tools, script, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
work.mkdir(parents=True, exist_ok=False)
HOME = str(Path.home())
UNIT = "sota-refresh-gate-rehearsal-prometheus.service"
RUNTIME = Path(os.environ["XDG_RUNTIME_DIR"]) / "systemd" / "user"
UNIT_FILE = RUNTIME / UNIT
OWNED = [UNIT_FILE, RUNTIME / f".{UNIT}.new", RUNTIME / f".{UNIT}.restore"]  # the only paths removed at teardown
PORT = 29390
SYSTEMCTL = "/usr/bin/systemctl"
V14, V15 = tools / "ecosystem-prometheus-3.14.0", tools / "ecosystem-prometheus-3.15.0"
REVISION = {"3.14.0": "d7598b7141418fa35be2b5ec5d0fefb634199610", "3.15.0": "5241a27fe3c6983549fccc32f6e65917408c63cd"}
PROD = "ecosystem-prometheus.service"
PROD_BIN = Path(HOME) / ".local/share/codex-ecosystem/bin"
WARMUP = 200
results: dict = {"unit": UNIT, "port": PORT, "cases": []}


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S"), message.replace(HOME, "~"), flush=True)


def run(argv, env=None, timeout: float = 900) -> tuple[int, str]:
    p = subprocess.run([str(a) for a in argv], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env,
                       timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def systemctl(*argv) -> tuple[int, str]:
    return run([SYSTEMCTL, "--user", *argv])


def props(unit: str) -> dict:
    _, text = systemctl("show", unit, "-p", "LoadState", "-p", "ActiveState", "-p", "SubState", "-p", "Result",
                        "-p", "MainPID", "-p", "NRestarts", "-p", "NeedDaemonReload", "-p", "ActiveEnterTimestamp",
                        "-p", "ExecStart")
    data = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    match = re.search(r"path=(\S+)", data.pop("ExecStart", ""))
    data["ExecStartPath"] = match.group(1) if match else None
    return data


def build() -> list:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/status/buildinfo", timeout=5) as response:
            data = json.loads(response.read())["data"]
            return [data["version"], data["revision"]]
    except Exception:
        return [None, None]


def wait_ready(timeout: float = 60) -> float | None:
    started = time.time()
    while time.time() < started + timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/-/ready", timeout=2) as response:
                if response.status == 200:
                    return round(time.time() - started, 2)
        except Exception:
            pass
        time.sleep(0.25)
    return None


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def render(prefix: Path) -> str:
    return (f"[Unit]\nDescription=Gate rehearsal prometheus (scratch)\nAfter=network.target\nStartLimitIntervalSec=60\n"
            f"StartLimitBurst=3\n\n[Service]\nType=simple\nUMask=0077\nNoNewPrivileges=true\nWorkingDirectory={work}/data\n"
            f"ExecStart={prefix}/prometheus --config.file={work}/config/prometheus.yml --storage.tsdb.path={work}/data "
            f"--storage.tsdb.retention.time=1d --web.listen-address=127.0.0.1:{PORT}\nRestart=on-failure\nRestartSec=5\n"
            f"TimeoutStopSec=60\n\n[Install]\nWantedBy=default.target\n")


def links() -> dict:
    return {name: os.readlink(work / "bin" / name) for name in ("prometheus", "promtool")}


def production() -> dict:
    unit = props(PROD)
    return {"unit": {k: unit.get(k) for k in ("ActiveState", "SubState", "MainPID", "NRestarts", "ActiveEnterTimestamp",
                                              "NeedDaemonReload", "ExecStartPath")},
            "links": {name: os.readlink(PROD_BIN / name) for name in ("prometheus", "promtool")}}


def write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chmod(path, mode)


def snapshot() -> dict:
    return {"unit": props(UNIT), "build": build(), "links": links(), "unit_sha256": sha256(UNIT_FILE.read_bytes()),
            "unit_mtime_ns": UNIT_FILE.stat().st_mtime_ns}


def case(name: str, what: str, *, from_version: str, from_prefix: Path, to_version: str, to_prefix: Path,
         failed: list[str], exit_code: int, serving: Path, restart: bool, shim: str | None = None) -> None:
    directory = work / name
    write(directory / "expected.service", render(to_prefix))
    reset = systemctl("reset-failed", UNIT)
    before = snapshot()
    env = dict(os.environ)
    if shim:
        env.update(PATH=f"{work / 'shim'}:{env['PATH']}", SHIM_MODE=shim)
    argv = [sys.executable, script, "--unit", UNIT, "--unit-file", UNIT_FILE, "--expected-unit",
            directory / "expected.service", "--port", PORT, "--bin-dir", work / "bin", "--from-version", from_version,
            "--from-prefix", from_prefix, "--to-version", to_version, "--to-revision", REVISION[to_version],
            "--to-prefix", to_prefix, "--out", directory / "out", "--ready-timeout", "30", "--settle", "20"]
    log(f"{name}: {what}")
    started = time.time()
    code, output = run(argv, env=env)
    seconds = round(time.time() - started, 1)
    (directory / "run.log").write_text(output + "\n")
    record = json.loads((directory / "out" / "switch.json").read_text())
    gates_failed = [g["gate"] for g in record["gates"] if not g["passed"]]
    after = snapshot()
    reload_needed = after["unit"].get("NeedDaemonReload")
    if reload_needed != "no":  # a shimmed reload leaves the manager behind the files; catch it up before the next case
        after["harness_daemon_reload"] = systemctl("daemon-reload")[0]
        after["need_daemon_reload_after_harness_reload"] = props(UNIT).get("NeedDaemonReload")
    expected_version = "3.15.0" if serving == V15 else "3.14.0"
    expectations = {
        "exit": code == exit_code,
        "failed_gates": gates_failed == failed,
        "running_version": after["build"] == [expected_version, REVISION[expected_version]],
        "unit_file_is_render_of_serving_prefix": after["unit_sha256"] == sha256(render(serving)),
        "serving_exec_start": after["unit"].get("ExecStartPath") == str(serving / "prometheus"),
        "links_follow_serving_prefix": after["links"] == {n: str(serving / n) for n in ("prometheus", "promtool")},
        "restart_as_expected": (after["unit"].get("MainPID") != before["unit"].get("MainPID")) == restart,
        "active_running": [after["unit"].get("ActiveState"), after["unit"].get("SubState")] == ["active", "running"],
    }
    if not restart and exit_code != 0:
        expectations["unit_file_mtime_kept"] = after["unit_mtime_ns"] == before["unit_mtime_ns"]
    entry = {"case": name, "what": what, "shim": shim, "exit": code, "seconds": seconds, "failed_gates": gates_failed,
             "gates": [[g["gate"], g["passed"]] for g in record["gates"]],
             "restore": next((s for s in record["steps"] if s["step"] == "R-restore"), None),
             "failure": next((s for s in record["steps"] if s["step"] == "P-failed"), None),
             "reset_failed_before_case": reset[0], "before": before, "after": after, "expectations": expectations,
             "passed": all(expectations.values())}
    results["cases"].append(entry)
    log(f"{name}: exit {code} in {seconds} s, failed gates {gates_failed}, expectations "
        f"{'met' if entry['passed'] else [k for k, v in expectations.items() if not v]}")


created_runtime = not RUNTIME.exists()
if UNIT_FILE.exists() or build() != [None, None]:
    sys.exit("refusing: the scratch unit file exists or something already answers on the scratch port")
results["systemd"] = run([SYSTEMCTL, "--version"])[1].splitlines()[0]
results["production_before"] = production()
try:
    write(work / "config" / "prometheus.yml",
          f"global:\n  scrape_interval: 5s\n  evaluation_interval: 5s\nrule_files:\n  - {work}/config/rules.yml\n"
          f"scrape_configs:\n  - job_name: gate-rehearsal\n    static_configs:\n      - targets: ['127.0.0.1:{PORT}']\n")
    write(work / "config" / "rules.yml",
          "groups:\n  - name: gate-rehearsal\n    rules:\n      - record: job:up:sum\n        expr: sum by (job) (up)\n"
          "      - alert: GateRehearsalAlwaysFiring\n        expr: vector(1)\n")
    (work / "data").mkdir(mode=0o700)
    (work / "bin").mkdir()
    for name in ("prometheus", "promtool"):
        os.symlink(V14 / name, work / "bin" / name)
    for fake, tail in (("fake-start-fails", 'echo "gate rehearsal: simulated start failure" >&2\nexit 1\n'),
                       ("fake-serves-3.14.0", f'exec {V14}/prometheus "$@"\n')):
        write(work / fake / "prometheus", f'#!/bin/sh\nif [ "$1" = "--version" ]; then exec {V15}/prometheus --version; fi\n'
              + tail, 0o755)
        os.symlink(V15 / "promtool", work / fake / "promtool")
    write(work / "shim" / "systemctl",
          '#!/bin/sh\n# SHIM_MODE=fail: daemon-reload exits 1; SHIM_MODE=skip: daemon-reload exits 0 without reloading;\n'
          '# every other call goes to /usr/bin/systemctl unchanged\nfor arg in "$@"; do\n'
          '  if [ "$arg" = "daemon-reload" ]; then\n    case "$SHIM_MODE" in\n'
          '      fail) echo "gate rehearsal shim: simulated daemon-reload failure" >&2; exit 1 ;;\n'
          '      skip) exit 0 ;;\n    esac\n  fi\ndone\nexec /usr/bin/systemctl "$@"\n', 0o755)
    write(UNIT_FILE, render(V14))
    results["setup"] = {"daemon_reload": systemctl("daemon-reload")[0], "start": systemctl("start", UNIT)[0],
                        "ready_seconds": wait_ready(), "build": build()}
    log(f"setup {results['setup']}; warming up {WARMUP} s so the six-hour history window holds samples")
    time.sleep(WARMUP)

    common = dict(from_version="3.14.0", from_prefix=V14, to_version="3.15.0")
    case("G0", "--from-version 3.13.0 while 3.14.0 runs", from_version="3.13.0", from_prefix=V14, to_version="3.15.0",
         to_prefix=V15, failed=["running-from-version"], exit_code=1, serving=V14, restart=False)
    case("G1", "switch 3.14.0 -> 3.15.0", **common, to_prefix=V15, failed=[], exit_code=0, serving=V15, restart=True)
    case("G2", "rollback 3.15.0 -> 3.14.0 with the same script", from_version="3.15.0", from_prefix=V15,
         to_version="3.14.0", to_prefix=V14, failed=[], exit_code=0, serving=V14, restart=True)
    case("G3", "daemon-reload exits 1", **common, to_prefix=V15, failed=["daemon-reload"], exit_code=2, serving=V14,
         restart=False, shim="fail")
    case("G4", "daemon-reload exits 0 without reloading", **common, to_prefix=V15, failed=["unit-loaded"], exit_code=2,
         serving=V14, restart=False, shim="skip")
    case("G5", "the new server exits at start", **common, to_prefix=work / "fake-start-fails", failed=["ready"],
         exit_code=2, serving=V14, restart=True)
    case("G6", "the restarted server reports 3.14.0", **common, to_prefix=work / "fake-serves-3.14.0",
         failed=["version", "revision"], exit_code=2, serving=V14, restart=True)
finally:
    teardown = {"stop": systemctl("stop", UNIT)[0]}
    teardown["removed"] = []
    for path in OWNED:
        if path.exists() or path.is_symlink():
            path.unlink()
            teardown["removed"].append(str(path))
    teardown["daemon_reload"] = systemctl("daemon-reload")[0]
    teardown["reset_failed"] = systemctl("reset-failed", UNIT)[0]
    teardown["runtime_dir_left"] = sorted(p.name for p in RUNTIME.iterdir()) if RUNTIME.exists() else None
    if created_runtime and RUNTIME.exists() and not any(RUNTIME.iterdir()):
        RUNTIME.rmdir()
        teardown["runtime_dir_removed"] = True
        teardown["daemon_reload_after_rmdir"] = systemctl("daemon-reload")[0]
    teardown["scratch_unit_load_state"] = props(UNIT).get("LoadState")
    results["teardown"] = teardown
    results["production_after"] = production()
    results["production_unchanged"] = results["production_after"] == results["production_before"]
    results["all_cases_passed"] = bool(results["cases"]) and all(c["passed"] for c in results["cases"])
    (work / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    log(f"teardown {teardown}; production unchanged {results['production_unchanged']}; "
        f"all cases passed {results['all_cases_passed']}")
