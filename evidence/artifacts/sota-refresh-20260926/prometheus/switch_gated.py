#!/usr/bin/env python3
"""Gated switch of a Prometheus systemd --user unit from one installed prefix to another.

Supersedes switch.py, which is kept byte-identical as it ran on 2026-09-26: that script logged the verify,
daemon-reload and restart exit codes and the post-switch comparisons but repointed the bin links whatever they
said (review finding). Here the links move only after every gate passes, and a failed gate restores the unit.

Usage:
  switch_gated.py --unit NAME --unit-file PATH --expected-unit PATH --port N --bin-dir DIR
                  --from-version V --from-prefix DIR --to-version V --to-revision SHA --to-prefix DIR --out NEW_DIR
                  [--ready-timeout SECONDS] [--settle SECONDS]

The 2026-09-26 switch on this host, expressed with this script (the rollback swaps the two versions and prefixes and
passes revision d7598b7141418fa35be2b5ec5d0fefb634199610 with an expected unit rendered with the 3.14.0 pin):
  switch_gated.py --unit ecosystem-prometheus.service --unit-file ~/.config/systemd/user/ecosystem-prometheus.service
    --expected-unit <observability/backends/configure.py render with the 3.15.0 pin> --port 19090
    --bin-dir ~/.local/share/codex-ecosystem/bin
    --from-version 3.14.0 --from-prefix ~/.local/share/codex-ecosystem/tools/ecosystem-prometheus-3.14.0
    --to-version 3.15.0 --to-revision 5241a27fe3c6983549fccc32f6e65917408c63cd
    --to-prefix ~/.local/share/codex-ecosystem/tools/ecosystem-prometheus-3.15.0 --out <new directory>

Exit 0: switched and links promoted. Exit 1: a preflight gate failed and nothing was changed. Exit 2: a gate after
the unit was replaced failed and the previous unit is running again. Exit 3: that restore failed too. Exit 4: the
server passed every gate but a link could not be promoted. The record is written to <out>/switch.json in every case.

  P0 preflight: the unit is active and running, has no pending on-disk change (NeedDaemonReload=no), runs
     <from-prefix>/prometheus, and its server reports --from-version; <to-prefix>/prometheus and promtool report
     --to-version and --to-revision; <to-prefix>/promtool check config passes on the unit's --config.file; the
     expected unit equals the live unit with <from-prefix>/prometheus replaced by <to-prefix>/prometheus at the
     start of ExecStart and no other change
  P1 back up the unit; install the expected unit (temporary file + rename, same mode) and read it back
  P2 systemd-analyze --user verify and daemon-reload exit 0, and systemd has loaded the new unit
     (NeedDaemonReload=no, ExecStart runs <to-prefix>/prometheus)
  P3 restart exits 0; /-/ready within --ready-timeout; a new MainPID
  P4 after --settle seconds, every check is recorded and all must pass: buildinfo version and revision; ExecStart;
     NRestarts 0; the same job/instance set in `up` and no target that was up is down; the same rule group and rule
     counts and no rule health outside the health seen before plus ok; the six-hour `up` history before the run
     unchanged; no level=ERROR journal line since the restart
  P5 repoint <bin-dir>/prometheus and promtool at <to-prefix> (temporary link + rename) and read them back
Restore (after P1): put the backup back (copy that keeps its mtime, then rename), daemon-reload, and when the server
was restarted or no longer reports --from-version: reset-failed (a crash loop can exhaust the start limit), restart,
/-/ready, --from-version and <from-prefix>/prometheus in ExecStart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
for flag in ("unit", "unit-file", "expected-unit", "bin-dir", "from-version", "from-prefix", "to-version",
             "to-revision", "to-prefix", "out"):
    parser.add_argument(f"--{flag}", required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--ready-timeout", type=float, default=120.0)
parser.add_argument("--settle", type=float, default=45.0)
args = parser.parse_args()


def absolute(value: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(value)))


UNIT = args.unit
UNIT_FILE, EXPECTED, BIN_DIR, OUT = (absolute(v) for v in (args.unit_file, args.expected_unit, args.bin_dir, args.out))
FROM, TO = absolute(args.from_prefix), absolute(args.to_prefix)
FROM_BIN, TO_BIN = str(FROM / "prometheus"), str(TO / "prometheus")
HOME = str(Path.home())
OUT.mkdir(parents=True, exist_ok=False)
record: dict = {"procedure": "switch_gated.py", "arguments": vars(args), "steps": [], "gates": []}


class GateFailed(Exception):
    pass


def scrub(value):
    return json.loads(json.dumps(value, default=str).replace(HOME, "~"))


def note(step: str, **data) -> None:
    record["steps"].append({"step": step, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **data})
    print(step, json.dumps(scrub(data))[:700], flush=True)


def check(name: str, ok, **detail) -> bool:
    record["gates"].append({"gate": name, "passed": bool(ok), **detail})
    print("PASS" if ok else "FAIL", name, json.dumps(scrub(detail))[:400], flush=True)
    return bool(ok)


def gate(name: str, ok, **detail) -> None:
    if not check(name, ok, **detail):
        raise GateFailed(name)


def sh(*argv, timeout: float = 180, full: bool = False) -> dict:
    """Run a command; the recorded output keeps its last 2000 characters unless full (scans need every line)."""
    command = [str(a) for a in argv]
    try:
        p = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout)
        output = (p.stdout + p.stderr).strip()
        return {"argv": command, "exit": p.returncode, "output": output if full else output[-2000:]}
    except subprocess.TimeoutExpired:
        return {"argv": command, "exit": None, "output": f"timed out after {timeout} s"}


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def api(path: str, params: dict | None = None, timeout: float = 10):
    url = f"http://127.0.0.1:{args.port}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def running_build() -> tuple[str | None, str | None]:
    try:
        data = api("/api/v1/status/buildinfo", timeout=5)["data"]
        return data["version"], data["revision"]
    except Exception:
        return None, None


def wait_ready(started: float) -> float | None:
    while time.time() < started + args.ready_timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/-/ready", timeout=2) as response:
                if response.status == 200:
                    return round(time.time() - started, 2)
        except Exception:
            pass
        time.sleep(0.25)
    return None


def unit_props() -> dict:
    p = subprocess.run(["systemctl", "--user", "show", UNIT, "-p", "MainPID", "-p", "ActiveState", "-p", "SubState",
                        "-p", "Result", "-p", "NRestarts", "-p", "NeedDaemonReload", "-p", "ActiveEnterTimestamp",
                        "-p", "ExecStart"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    props = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    match = re.search(r"path=(\S+)", props.pop("ExecStart", ""))
    props["ExecStartPath"] = match.group(1) if match else None
    return props


def state(hist_end: float) -> dict:
    s = {"unit": unit_props()}
    build = api("/api/v1/status/buildinfo")["data"]
    s["buildinfo"] = {"version": build["version"], "revision": build["revision"]}
    up = api("/api/v1/query", {"query": "up"})["data"]["result"]
    s["up"] = sorted([r["metric"].get("job", ""), r["metric"].get("instance", ""), r["value"][1]] for r in up)
    groups = api("/api/v1/rules")["data"]["groups"]
    rules = [r for g in groups for r in g["rules"]]
    s["rules"] = {"groups": len(groups), "rules": len(rules), "health": sorted({r["health"] for r in rules}),
                  "firing": sorted(r["name"] for r in rules if r.get("state") == "firing")}
    hist = api("/api/v1/query_range", {"query": "up", "start": f"{hist_end - 6 * 3600:.3f}", "end": f"{hist_end:.3f}",
                                        "step": "300"})["data"]["result"]
    canon = json.dumps(sorted(hist, key=lambda r: json.dumps(r["metric"], sort_keys=True)), sort_keys=True)
    s["historical_up_6h"] = {"series": len(hist), "samples": sum(len(r["values"]) for r in hist), "sha256": sha256(canon)}
    return s


def exec_line(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("ExecStart=")]


def restore(backup: Path, mode: int, restarted: bool) -> bool:
    result: dict = {}
    temporary = UNIT_FILE.with_name(f".{UNIT_FILE.name}.restore")
    shutil.copy2(backup, temporary)
    os.chmod(temporary, mode)
    os.replace(temporary, UNIT_FILE)
    result["unit_equals_backup"] = UNIT_FILE.read_bytes() == backup.read_bytes()
    result["daemon_reload"] = sh("systemctl", "--user", "daemon-reload")
    version, _ = running_build()
    result["restart_needed"] = restarted or version != args.from_version
    if result["restart_needed"]:
        result["reset_failed"] = sh("systemctl", "--user", "reset-failed", UNIT)
        started = time.time()
        result["restart"] = sh("systemctl", "--user", "restart", UNIT)
        result["ready_seconds"] = wait_ready(started)
    result["version_after"], result["revision_after"] = running_build()
    result["unit_after"] = unit_props()
    result["restored"] = bool(result["unit_equals_backup"] and result["version_after"] == args.from_version
                              and result["unit_after"]["ExecStartPath"] == FROM_BIN)
    note("R-restore", **result)
    return result["restored"]


def finish(code: int) -> None:
    record["exit"] = code
    (OUT / "switch.json").write_text(json.dumps(scrub(record), indent=2) + "\n")
    print("EXIT", code, flush=True)
    sys.exit(code)


# P0 preflight: nothing is changed before every check here passes
hist_end = time.time() - 120
try:
    live_text, expected_text = UNIT_FILE.read_text(), EXPECTED.read_text()
    props = unit_props()
    version, revision = running_build()
    live_exec, expected_exec = exec_line(live_text), exec_line(expected_text)
    config = None
    if len(live_exec) == 1:
        match = re.search(r"--config\.file=(\S+)", live_exec[0])
        config = match.group(1) if match else None
    to_versions = {name: sh(TO / name, "--version") for name in ("prometheus", "promtool")}
    promtool_check = sh(TO / "promtool", "check", "config", config) if config else None
    note("P0-preflight", unit=props, running={"version": version, "revision": revision}, to_versions=to_versions,
         promtool_check_config=promtool_check, live_unit_sha256=sha256(live_text), expected_unit_sha256=sha256(expected_text))
    others_equal = ([line for line in live_text.splitlines() if not line.startswith("ExecStart=")]
                    == [line for line in expected_text.splitlines() if not line.startswith("ExecStart=")])
    exec_swap = (len(live_exec) == 1 and len(expected_exec) == 1 and live_exec[0].startswith(f"ExecStart={FROM_BIN} ")
                 and expected_exec[0] == live_exec[0].replace(f"ExecStart={FROM_BIN} ", f"ExecStart={TO_BIN} ", 1))
    preflight = [
        check("unit-active", props.get("ActiveState") == "active" and props.get("SubState") == "running",
              value=[props.get("ActiveState"), props.get("SubState")]),
        check("unit-has-no-pending-change", props.get("NeedDaemonReload") == "no", value=props.get("NeedDaemonReload")),
        check("unit-runs-from-prefix", props.get("ExecStartPath") == FROM_BIN, value=props.get("ExecStartPath")),
        check("running-from-version", version == args.from_version, value=version),
        check("to-prefix-reports-to-version", all(r["exit"] == 0 and f"version {args.to_version} " in r["output"]
                                                  and f"revision: {args.to_revision}" in r["output"]
                                                  for r in to_versions.values())),
        check("to-promtool-check-config", promtool_check is not None and promtool_check["exit"] == 0, config=config),
        check("expected-unit-changes-only-the-exec-prefix", others_equal and exec_swap),
    ]
except Exception as error:  # an unreadable file or an unreachable server: still nothing changed
    note("P0-error", error=repr(error))
    finish(1)
if not all(preflight):
    finish(1)

# P1-P5: a failure from here on restores the previous unit
backup = OUT / "backup" / UNIT_FILE.name
mode = UNIT_FILE.stat().st_mode & 0o777
restarted = False
try:
    backup.parent.mkdir(mode=0o700)
    shutil.copy2(UNIT_FILE, backup)
    temporary = UNIT_FILE.with_name(f".{UNIT_FILE.name}.new")
    temporary.write_text(expected_text)
    os.chmod(temporary, mode)
    os.replace(temporary, UNIT_FILE)
    installed = UNIT_FILE.read_text()
    note("P1-unit-installed", backup=str(backup), mode=oct(mode), sha256_before=sha256(live_text),
         sha256_after=sha256(installed))
    gate("unit-installed", installed == expected_text)

    verify = sh("systemd-analyze", "--user", "verify", UNIT_FILE)
    gate("verify", verify["exit"] == 0, result=verify)
    reload_result = sh("systemctl", "--user", "daemon-reload")
    gate("daemon-reload", reload_result["exit"] == 0, result=reload_result)
    loaded = unit_props()
    gate("unit-loaded", loaded.get("NeedDaemonReload") == "no" and loaded.get("ExecStartPath") == TO_BIN,
         need_daemon_reload=loaded.get("NeedDaemonReload"), exec_start=loaded.get("ExecStartPath"))

    pre = state(hist_end)
    note("P3-pre-state", **pre)
    restart_at = time.time()
    restarted = True
    restart = sh("systemctl", "--user", "restart", UNIT)
    gate("restart", restart["exit"] == 0, result=restart)
    ready = wait_ready(restart_at)
    gate("ready", ready is not None, seconds_after_restart_call=ready, timeout=args.ready_timeout)
    after_restart = unit_props()
    gate("new-main-pid", after_restart.get("MainPID") not in (None, "0", pre["unit"].get("MainPID")),
         before=pre["unit"].get("MainPID"), after=after_restart.get("MainPID"))

    time.sleep(args.settle)
    post = state(hist_end)
    note("P4-post-state", **post)
    journal = sh("journalctl", "--user", "-u", UNIT, "--since",
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(restart_at - 1)), "--no-pager", "-o", "cat",
                 full=True)
    journal_lines = journal.pop("output").splitlines()
    errors = [line[:300] for line in journal_lines if "level=ERROR" in line]
    note("P4-journal", exit=journal["exit"], lines=len(journal_lines),
         warnings=[line[:300] for line in journal_lines if "level=WARN" in line][:10])
    was_up = [row[:2] for row in pre["up"] if row[2] == "1"]
    now_up = [row[:2] for row in post["up"] if row[2] == "1"]
    acceptance = [
        check("version", post["buildinfo"]["version"] == args.to_version, value=post["buildinfo"]["version"]),
        check("revision", post["buildinfo"]["revision"] == args.to_revision, value=post["buildinfo"]["revision"]),
        check("exec-start", post["unit"].get("ExecStartPath") == TO_BIN, value=post["unit"].get("ExecStartPath")),
        check("no-automatic-restart", post["unit"].get("NRestarts") == "0", value=post["unit"].get("NRestarts")),
        check("same-targets", [row[:2] for row in pre["up"]] == [row[:2] for row in post["up"]]),
        check("no-target-went-down", all(row in now_up for row in was_up),
              down=[row for row in was_up if row not in now_up]),
        check("same-rule-counts", (pre["rules"]["groups"], pre["rules"]["rules"])
              == (post["rules"]["groups"], post["rules"]["rules"])),
        check("rule-health", set(post["rules"]["health"]) <= set(pre["rules"]["health"]) | {"ok"},
              before=pre["rules"]["health"], after=post["rules"]["health"]),
        check("history-unchanged", pre["historical_up_6h"] == post["historical_up_6h"],
              before=pre["historical_up_6h"], after=post["historical_up_6h"]),
        check("journal-has-no-error", journal["exit"] == 0 and not errors, errors=errors[:10]),
    ]
    if not all(acceptance):
        raise GateFailed("acceptance")
except BaseException as error:  # a gate, an unexpected error or an interrupt: put the previous unit back
    note("P-failed", error=repr(error), restarted=restarted, unit=unit_props())
    try:
        restored = restore(backup, mode, restarted)
    except Exception as restore_error:  # never report a failed restore as "nothing changed"
        note("R-restore-error", error=repr(restore_error))
        restored = False
    finish(2 if restored else 3)

links = {}
try:
    for name in ("prometheus", "promtool"):
        link = BIN_DIR / name
        before = os.readlink(link) if link.is_symlink() else None
        temporary = BIN_DIR / f".{name}.new"
        if temporary.is_symlink() or temporary.exists():
            temporary.unlink()
        os.symlink(TO / name, temporary)
        os.replace(temporary, link)
        links[name] = {"before": before, "after": os.readlink(link)}
    note("P5-bin-links", **links)
    gate("links", all(links[name]["after"] == str(TO / name) for name in ("prometheus", "promtool")))
except Exception as error:
    note("P5-failed", error=repr(error), links=links)
    finish(4)
finish(0)
