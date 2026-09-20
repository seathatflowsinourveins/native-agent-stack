"""Record the actual native process namespace, then replace this process with restic."""
import json
import os
from pathlib import Path
import sys

Path('/out/namespace.json').write_text(json.dumps({
    'network_namespace': os.readlink('/proc/self/ns/net'),
    'mount_namespace': os.readlink('/proc/self/ns/mnt'),
    'interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()) if Path('/sys/class/net').exists() else None,
    'uid': os.getuid(), 'gid': os.getgid(),
    'environment_keys': sorted(os.environ),
}) + '\n')
os.execv('/tool/restic', ['/tool/restic', *sys.argv[1:]])
