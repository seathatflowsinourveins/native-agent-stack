"""Enter the upstream test's already-created network namespace as its owner.

The workflow grants sudo only on its disposable hosted runner. This helper does
not install services, alter host interfaces or provide a general command API.
"""
import os
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    uid, gid = int(sys.argv[1]), int(sys.argv[2])
    expected = Path(__file__).with_name('run.py').resolve()
    if (os.geteuid() != 0 or uid <= 0 or gid <= 0 or len(sys.argv) != 8
            or Path(sys.argv[4]).resolve() != expected or sys.argv[5] != 'qdrant-tests'
            or sys.argv[6] != '--root'):
        raise SystemExit('only the fixed owned Qdrant test command is supported')
    subprocess.run(['/usr/sbin/ip', 'link', 'set', 'lo', 'up'], check=True, timeout=10)
    os.setgroups([]); os.setgid(gid); os.setuid(uid)
    os.execve(sys.argv[3], sys.argv[3:], dict(os.environ))
