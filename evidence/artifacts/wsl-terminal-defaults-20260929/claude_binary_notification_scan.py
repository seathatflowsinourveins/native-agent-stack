#!/usr/bin/env python3
"""Count the notification-related literals in installed Claude Code binaries, to say which release knows what.

Read-only: it maps each binary and counts byte strings, and prints JSON of counts per binary (named by its file name, a version). With no argument
it scans every file in the versions directory of the native install (~/.local/share/claude/versions); a path argument scans that file instead
(for a binary in another distro, where Python may be missing, `grep -a -c <literal> <binary>` counts lines with the literal and is what was used).

Literals: `notifications_disabled` (a preferredNotifChannel value), `terminalSequence` (the hook output field the bell hook uses), and
`notificationType:"worker_permission_prompt"`, one entry per call site that emits that Notification type from the agent-team inbox, so a
release that has it rings the whole matcher of the linux-wsl2 overlay.
usage: python3 -B claude_binary_notification_scan.py [<binary> ...]
"""
import json, mmap, re, sys
from pathlib import Path

LITERALS = {"notifications_disabled": b"notifications_disabled", "terminalSequence": b"terminalSequence",
            "worker_permission_prompt_call_sites": b'notificationType:"worker_permission_prompt"', "worker_permission_prompt_any": b'"worker_permission_prompt"'}
targets = [Path(arg) for arg in sys.argv[1:]] or sorted((p for p in (Path.home() / ".local/share/claude/versions").iterdir() if p.is_file()),
                                                       key=lambda p: [int(part) for part in re.findall(r"\d+", p.name)])
report = {}
for binary in targets:
    with open(binary, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        report[binary.name] = {label: len(re.findall(re.escape(needle), data)) for label, needle in LITERALS.items()}
print(json.dumps(report, indent=2))
