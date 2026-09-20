#!/usr/bin/env python3
"""Read-only boot observer: reports files and manager state, never activates it."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

WORK = Path('/var/lib/service-reboot')


def observe():
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    deadline = time.monotonic() + 600
    seen = set()
    while time.monotonic() < deadline:
        for phase in ('before', 'after'):
            path = WORK / (phase + '.json')
            if phase in seen or not path.exists():
                continue
            value = json.loads(path.read_text())
            if value['boot_id'] != boot:
                continue
            manager = subprocess.run(
                ['systemctl', 'show', 'user@1001.service', '-p', 'ActiveState', '--value'],
                check=True, capture_output=True, text=True, timeout=10).stdout.strip()
            record = {'phase': phase, 'boot_id': boot,
                      'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'linger': Path('/var/lib/systemd/linger/example').is_file(),
                      'user_manager': manager}
            print('NATIVE_REBOOT_OBSERVER ' + json.dumps(record, sort_keys=True), flush=True)
            seen.add(phase)
            if phase == 'after':
                return
        time.sleep(0.2)
    raise TimeoutError('No automatic completion within observer deadline')


if __name__ == '__main__':
    observe()
