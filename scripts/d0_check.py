#!/usr/bin/env python3
"""Read-only WSL clock-agent census plus Windows-time persistence checks.

Ports the staged D0 reader (sha256 4b5d02b55f65fa255ad53ae9a38144a70a0cb8f0cce8458573c661165340601b).
The Windows reads use the native SCM, Registry and ScheduledTasks interfaces.
Automatic/backoff sources are the two pinned Microsoft documents in the runbook;
SERVICE_TRIGGER actions 1/2 are documented in Microsoft's winsvc.h reference
(2021-04-02). No service, registry, clock or task mutation is performed here.
WSL's system-distro PHC agent is started by mini_init, independently of user distros:
https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3219-L3222
https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3665-L3708
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.util
from functools import lru_cache
import json
import subprocess
import sys
import time

POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
CHRONY_PORT = 323  # WSL platform PHC agent; the distro's NTP observer is on 3323.
REMEDIATION = (
    "The user re-applies CLOCK-R2 fixes 1 and 2 as Windows administrator: "
    "sc.exe config w32time start= auto; ResolvePeerBackoffMinutes=1, leaving MaxTimes=7. "
    "Read back the values. Preserve triggers; unresolved STOP/unknown triggers go to the command center."
)

WINDOWS_READBACK = r"""
$ErrorActionPreference = 'Stop'
$root = Get-Item -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time'
$ntp = Get-Item -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient'
$triggers = @()
$triggerPath = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\TriggerInfo'
if (Test-Path -LiteralPath $triggerPath) {
    foreach ($key in @(Get-ChildItem -LiteralPath $triggerPath)) {
        $triggers += [ordered]@{
            key = $key.PSChildName
            action = $key.GetValue('Action', $null)
            type = $key.GetValue('Type', $null)
        }
    }
}
function Read-SCM {
    param([string[]]$ScArguments)
    $text = @(& "$env:SystemRoot\System32\sc.exe" @ScArguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw 'SCM read failed' }
    return ($text -join "`n")
}
$qc = Read-SCM -ScArguments @('qc', 'w32time')
$query = Read-SCM -ScArguments @('query', 'w32time')
$triggerText = Read-SCM -ScArguments @('qtriggerinfo', 'w32time')
$task = Get-ScheduledTask -TaskPath '\Microsoft\Windows\Time Synchronization\' -TaskName 'SynchronizeTime'
$maxPresent = @($ntp.GetValueNames()) -contains 'ResolvePeerBackoffMaxTimes'
[ordered]@{
    schema_version = 1
    start_type = $root.GetValue('Start', $null)
    delayed_auto_start = $root.GetValue('DelayedAutoStart', 0)
    service_state = (Get-Service -Name 'w32time').Status.ToString()
    triggers = @($triggers)
    sc_qc = $qc
    sc_query = $query
    sc_triggers = $triggerText
    synchronize_time = [ordered]@{ state = $task.State.ToString(); enabled = $task.Settings.Enabled }
    resolve_peer_backoff_minutes = $ntp.GetValue('ResolvePeerBackoffMinutes', $null)
    resolve_peer_backoff_max_times = $ntp.GetValue('ResolvePeerBackoffMaxTimes', 7)
    max_times_value_present = $maxPresent
} | ConvertTo-Json -Depth 8 -Compress
"""


def windows_persistence(snapshot: object) -> dict:
    """Fail closed on missing/malformed reads; record START triggers/task state."""
    failures: list[str] = []
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        return {"passed": False, "failures": ["windows_snapshot_unreadable"], "start_triggers": []}

    def exact_integer(name: str, expected: int) -> bool:
        value = snapshot.get(name)
        return type(value) is int and value == expected

    if not exact_integer("start_type", 2):
        failures.append("start_type_not_automatic_2")
    if not exact_integer("delayed_auto_start", 0) or "DELAYED" in str(snapshot.get("sc_qc", "")).upper():
        failures.append("delayed_start_or_unreadable_delay")
    if str(snapshot.get("service_state", "")).upper() != "RUNNING":
        failures.append("w32time_not_running")
    for name in ("sc_qc", "sc_query", "sc_triggers"):
        if not isinstance(snapshot.get(name), str) or not snapshot[name].strip():
            failures.append(f"{name}_unreadable")

    starts: list[dict] = []
    triggers = snapshot.get("triggers")
    if not isinstance(triggers, list):
        failures.append("trigger_list_unreadable")
    else:
        for trigger in triggers:
            if not isinstance(trigger, dict) or type(trigger.get("action")) is not int:
                failures.append("trigger_action_unreadable")
            elif trigger["action"] == 2:
                failures.append("stop_trigger_present")
            elif trigger["action"] == 1:
                starts.append(trigger)
            else:
                failures.append("unknown_trigger_action")
    if "STOP SERVICE" in str(snapshot.get("sc_triggers", "")).upper() and "stop_trigger_present" not in failures:
        failures.append("stop_trigger_present")

    task = snapshot.get("synchronize_time")
    if not isinstance(task, dict) or not isinstance(task.get("state"), str) or not task["state"]:
        failures.append("synchronize_time_state_unreadable")
    if not exact_integer("resolve_peer_backoff_minutes", 1):
        failures.append("resolve_peer_backoff_minutes_not_1")
    if not exact_integer("resolve_peer_backoff_max_times", 7):
        failures.append("resolve_peer_backoff_max_times_not_7")
    return {"passed": not failures, "failures": list(dict.fromkeys(failures)),
            "start_triggers": starts, "synchronize_time": task}


def read_windows(powershell: str = POWERSHELL) -> dict:
    encoded = base64.b64encode(WINDOWS_READBACK.encode("utf-16-le")).decode("ascii")
    result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(f"Windows persistence reader exited {result.returncode}")
    snapshot = json.loads(result.stdout.strip().lstrip("\ufeff"))
    if not isinstance(snapshot, dict):
        raise ValueError("Windows reader did not return an object")
    return snapshot


class Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class Timex(ctypes.Structure):
    _fields_ = [("modes", ctypes.c_uint), ("offset", ctypes.c_long), ("freq", ctypes.c_long),
                ("maxerror", ctypes.c_long), ("esterror", ctypes.c_long), ("status", ctypes.c_int),
                ("constant", ctypes.c_long), ("precision", ctypes.c_long), ("tolerance", ctypes.c_long),
                ("time", Timeval), ("tick", ctypes.c_long), ("ppsfreq", ctypes.c_long), ("jitter", ctypes.c_long),
                ("shift", ctypes.c_int), ("stabil", ctypes.c_long), ("jitcnt", ctypes.c_long),
                ("calcnt", ctypes.c_long), ("errcnt", ctypes.c_long), ("stbcnt", ctypes.c_long),
                ("tai", ctypes.c_int), ("_pad", ctypes.c_int * 11)]


@lru_cache(maxsize=1)
def timex_libc():
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.adjtimex.argtypes = [ctypes.POINTER(Timex)]
    libc.adjtimex.restype = ctypes.c_int
    return libc


def sample_timex() -> dict:
    libc = timex_libc()
    value = Timex()
    value.modes = 0  # Linux adjtimex query only, never a write mask.
    if libc.adjtimex(ctypes.byref(value)) < 0:
        raise OSError(ctypes.get_errno(), "adjtimex query failed")
    return {"maxerror": value.maxerror, "freq": value.freq, "status": value.status, "tick": value.tick}


def read_agent_reference() -> str:
    for address in ("::1", "127.0.0.1"):
        try:
            result = subprocess.run(["chronyc", "-h", address, "-p", str(CHRONY_PORT), "-n", "tracking"],
                                    capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and "Reference ID" in result.stdout:
            ref = next((line.split(":", 1)[1].strip() for line in result.stdout.splitlines()
                        if line.startswith("Reference ID")), "none")
            interval = next((line.split(":", 1)[1].strip() for line in result.stdout.splitlines()
                             if line.startswith("Update interval")), "")
            return f"{ref} | {interval}"
    return "none"


def agent_census(seconds: int) -> dict:
    resets: list[float] = []
    last = None
    pll = 0
    started = time.monotonic()
    for _ in range(seconds):
        row = sample_timex()
        elapsed = round(time.monotonic() - started, 2)
        if last is not None and row["maxerror"] < last:
            resets.append(elapsed)
        pll += bool(row["status"] & 0x0001)
        last = row["maxerror"]
        time.sleep(1)
    gaps = [round(b - a, 1) for a, b in zip(resets, resets[1:])]
    refs = []
    for _ in range(10):
        refs.append(read_agent_reference())
        time.sleep(0.5)
    phc0 = sum(ref.startswith("50484330") for ref in refs)
    alive = len(gaps) >= 3 and all(6.5 <= gap <= 9.5 for gap in gaps) and phc0 >= 1
    return {"seconds": seconds, "maxerror_resets": len(resets), "reset_gaps_s": gaps,
            "pll_status_samples": pll, "chrony_port": CHRONY_PORT,
            "chrony_phc0_answers": f"{phc0}/10", "chrony_refs": sorted(set(refs)),
            "agent_alive": alive}


def main(seconds: int = 60, mode: str = "both", powershell: str = POWERSHELL) -> int:
    report = {"utc": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip(),
              "mode": mode, "windows": None, "windows_persistence": None, "agent_alive": None,
              "remediation": REMEDIATION}
    passed = True
    if mode != "agent-only":
        try:
            report["windows"] = read_windows(powershell)
            report["windows_persistence"] = windows_persistence(report["windows"])
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            report["windows_persistence"] = {"passed": False, "failures": ["windows_read_failed"],
                                             "error_type": type(error).__name__}
        passed = report["windows_persistence"]["passed"]
    # A persistence failure alerts immediately, before the minute-long census.
    if mode != "persistence-only" and passed:
        try:
            report.update(agent_census(seconds))
            passed = report["agent_alive"]
        except (OSError, ValueError) as error:
            report["agent_error_type"] = type(error).__name__
            passed = False
    report["passed"] = passed
    print(json.dumps(report, sort_keys=True))
    return 0 if passed else 1


def positive_seconds(value: str) -> int:
    seconds = int(value)
    if not 1 <= seconds <= 86400:
        raise argparse.ArgumentTypeError("seconds must be between 1 and 86400")
    return seconds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seconds_positional", nargs="?", type=positive_seconds)
    parser.add_argument("--seconds", type=positive_seconds)
    parser.add_argument("--powershell", default=POWERSHELL)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--agent-only", action="store_true", help="retain the original D0-only census")
    modes.add_argument("--persistence-only", action="store_true", help="query Windows without a census")
    args = parser.parse_args()
    if args.seconds is not None and args.seconds_positional is not None:
        parser.error("choose either positional seconds or --seconds")
    selected_mode = "agent-only" if args.agent_only else "persistence-only" if args.persistence_only else "both"
    sys.exit(main(args.seconds or args.seconds_positional or 60, selected_mode, args.powershell))
