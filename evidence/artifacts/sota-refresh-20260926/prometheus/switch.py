#!/usr/bin/env python3
"""Switch ecosystem-prometheus.service from 3.14.0 to 3.15.0 on this host and read the result back.

Usage: switch.py <expected-unit-file> <out-dir>

The expected unit is observability/backends/configure.py's render with the 3.15.0 pin (host port overrides,
live roots substituted); it differs from the live unit only in the ExecStart prefix. Steps:
  S0 pre-state (unit, buildinfo, up, rules, head, a historical query_range hash)
  S1 private backup of the live unit; install the expected unit (temporary file + rename, same mode)
  S2 systemd-analyze --user verify; daemon-reload; restart; wait for /-/ready
  S3 post-state, the same historical query, journal ERROR lines since the restart
  S4 repoint bin/prometheus and bin/promtool at the 3.15.0 prefix (temporary link + rename)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

expected, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=False)
HOME = Path.home()
UNIT = HOME / ".config/systemd/user/ecosystem-prometheus.service"
ECO = HOME / ".local/share/codex-ecosystem"
NEW = ECO / "tools/ecosystem-prometheus-3.15.0"
PORT = 19090
record: dict = {"steps": []}


def note(step, **data):
    record["steps"].append({"step": step, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **data})
    print(step, json.dumps(data, default=str).replace(str(HOME), "~")[:600], flush=True)


def sh(argv):
    p = subprocess.run([str(a) for a in argv], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return p.returncode, (p.stdout + p.stderr).replace(str(HOME), "~")


def api(path, params=None):
    url = f"http://127.0.0.1:{PORT}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def unit_props():
    code, text = sh(["systemctl", "--user", "show", "ecosystem-prometheus.service", "-p", "MainPID", "-p",
                     "ActiveState", "-p", "SubState", "-p", "NRestarts", "-p", "ActiveEnterTimestamp", "-p", "ExecStart"])
    props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    exec_start = props.get("ExecStart", "")
    props["ExecStart"] = exec_start.split(" ;")[0].replace("{ path=", "")
    return props


def state(hist_end):
    s = {"unit": unit_props(), "buildinfo": api("/api/v1/status/buildinfo")["data"]}
    up = api("/api/v1/query", {"query": "up"})["data"]["result"]
    s["up"] = sorted((r["metric"]["job"], r["metric"]["instance"], r["value"][1]) for r in up)
    groups = api("/api/v1/rules")["data"]["groups"]
    rules = [r for g in groups for r in g["rules"]]
    s["rules"] = {"groups": len(groups), "rules": len(rules), "health": sorted({r["health"] for r in rules}),
                  "firing": sorted(r["name"] for r in rules if r.get("state") == "firing")}
    s["tsdb_head_series"] = api("/api/v1/status/tsdb")["data"]["headStats"]["numSeries"]
    hist = api("/api/v1/query_range", {"query": "up", "start": f"{hist_end - 6 * 3600:.3f}", "end": f"{hist_end:.3f}",
                                        "step": "300"})["data"]["result"]
    canon = json.dumps(sorted(hist, key=lambda r: json.dumps(r["metric"], sort_keys=True)), sort_keys=True)
    s["historical_up_6h"] = {"series": len(hist), "samples": sum(len(r["values"]) for r in hist),
                             "sha256": hashlib.sha256(canon.encode()).hexdigest()}
    runtime = api("/api/v1/status/runtimeinfo")["data"]
    s["runtimeinfo"] = {k: runtime.get(k) for k in ("reloadConfigSuccess", "storageRetention", "lastConfigTime",
                                                     "startTime")}
    return s


hist_end = time.time() - 120
pre = state(hist_end)
note("S0-pre", **pre)
if pre["buildinfo"]["version"] != "3.14.0":
    sys.exit("refusing: the running server is not 3.14.0")

# S1 backup and install the expected unit
backup = out / "backup"
backup.mkdir(mode=0o700)
shutil.copy2(UNIT, backup / UNIT.name)
live_text, expected_text = UNIT.read_text(), expected.read_text()
changed = [(a, b) for a, b in zip(live_text.splitlines(), expected_text.splitlines()) if a != b]
if len(live_text.splitlines()) != len(expected_text.splitlines()) or len(changed) != 1 \
        or not changed[0][0].startswith("ExecStart=") or "ecosystem-prometheus-3.15.0/prometheus" not in changed[0][1]:
    sys.exit("refusing: the expected unit differs from the live unit in more than the ExecStart prefix")
mode = UNIT.stat().st_mode & 0o777
temporary = UNIT.with_name(".ecosystem-prometheus.service.new")
temporary.write_text(expected_text)
os.chmod(temporary, mode)
os.replace(temporary, UNIT)
note("S1-unit-installed", backup=str(backup / UNIT.name), mode=oct(mode),
     sha256_before=hashlib.sha256(live_text.encode()).hexdigest(),
     sha256_after=hashlib.sha256(UNIT.read_bytes()).hexdigest())

# S2 verify, reload, restart, ready
code, text = sh(["systemd-analyze", "--user", "verify", UNIT])
note("S2-verify", exit=code, output=text.strip())
code_reload, text_reload = sh(["systemctl", "--user", "daemon-reload"])
restart_at = time.time()
code_restart, text_restart = sh(["systemctl", "--user", "restart", "ecosystem-prometheus.service"])
ready = None
for _ in range(480):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/-/ready", timeout=2) as r:
            if r.status == 200:
                ready = round(time.time() - restart_at, 2)
                break
    except Exception:
        pass
    time.sleep(0.25)
note("S2-restart", daemon_reload_exit=code_reload, restart_exit=code_restart, restart_output=text_restart.strip(),
     ready_seconds_after_restart_call=ready)
time.sleep(45)  # three scrape and evaluation intervals

# S3 post-state
post = state(hist_end)
note("S3-post", **post)
code, journal = sh(["journalctl", "--user", "-u", "ecosystem-prometheus.service", "--since",
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(restart_at - 1)), "--no-pager", "-o", "cat"])
lines = journal.splitlines()
note("S3-journal", lines=len(lines), errors=[l[:300] for l in lines if "level=ERROR" in l][:10],
     warnings=[l[:300] for l in lines if "level=WARN" in l][:10])
comparison = {
    "version_after": post["buildinfo"]["version"], "revision_after": post["buildinfo"]["revision"],
    "up_jobs_instances_equal": [x[:2] for x in pre["up"]] == [x[:2] for x in post["up"]],
    "up_all_one_after": all(x[2] == "1" for x in post["up"]),
    "rules_count_equal": (pre["rules"]["groups"], pre["rules"]["rules"]) == (post["rules"]["groups"], post["rules"]["rules"]),
    "rules_health_after": post["rules"]["health"],
    "historical_equal": pre["historical_up_6h"] == post["historical_up_6h"],
    "main_pid_changed": pre["unit"].get("MainPID") != post["unit"].get("MainPID"),
}
note("S3-compare", **comparison)

# S4 bin links
links = {}
for name in ("prometheus", "promtool"):
    link = ECO / "bin" / name
    before = os.readlink(link)
    tmp = ECO / "bin" / f".{name}.new"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(NEW / name, tmp)
    os.replace(tmp, link)
    links[name] = {"before": before, "after": os.readlink(link)}
note("S4-bin-links", **links)
(out / "switch.json").write_text(json.dumps(record, indent=2, default=str).replace(str(HOME), "~") + "\n")
print("DONE")
