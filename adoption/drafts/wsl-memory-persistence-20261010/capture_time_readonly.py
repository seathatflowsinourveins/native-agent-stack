#!/usr/bin/env python3
"""Capture the two chrony endpoints and designated timer inputs without applying settings."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def timed(command, env=None):
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"command": command, "start_utc": start, "end_utc": end,
            "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def capture():
    # Explicit hosts bypass chronyc's default Unix-socket/network fallback.
    # WSL 3.0.1 main.cpp:3219-3222/:3698-3710 starts VM-init PHC synchronization;
    # chrony 4.8 chronyd.adoc:196-201 defines the distro monitor's -x behavior.
    endpoints = (("wsl-vm-init", "::1", "323"),
                 ("distro-observe-only", "127.0.0.1", "3323"))
    commands = []
    for role, host, port in endpoints:
        for query in ("tracking", "sources"):
            receipt = timed(["chronyc", "-h", host, "-p", port, query])
            receipt["daemon_role"] = role
            commands.append(receipt)
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    commands.extend([timed(["chronyd", "--version"]), timed(["timedatectl", "show"]),
                     timed(["systemctl", "--user", "list-timers", "--all", "--no-pager"], env)])
    commands[-1]["environment_override"] = {"XDG_RUNTIME_DIR": "/run/user/1000"}
    out = {"evidence_class": "native_proven", "mutations": [], "commands": commands,
           "chrony_interpretation": {
               "wsl-vm-init": "PHC0 measures agreement with the Hyper-V host clock, not accuracy against UTC",
               "distro-observe-only": "-x monitor estimates system-clock error against network time; source selection alone does not prove NTS negotiation",
           }, "timer_files": []}
    root = Path.home() / ".config/systemd/user"
    for path in sorted(root.glob("*.timer")):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if any(line.startswith("OnCalendar=") and not line.endswith((" UTC", " America/New_York"))
               for line in text.splitlines()):
            target = root / (path.name + ".d") / "90-native-stack-explicit-zone.conf"
            out["timer_files"].append({
                "file": "~/.config/systemd/user/" + path.name,
                "sha256": hashlib.sha256(raw).hexdigest(), "text": text,
                "draft_target": "~/.config/systemd/user/" + path.name + ".d/90-native-stack-explicit-zone.conf",
                "draft_target_precondition": "present" if target.exists() or target.is_symlink() else "absent",
            })
    # Do not search distro configuration for the VM-init daemon's PHC refclock.
    return out


if __name__ == "__main__":
    print("DATA=" + json.dumps(capture(), separators=(",", ":")))
