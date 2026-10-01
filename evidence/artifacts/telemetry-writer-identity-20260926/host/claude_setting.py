#!/usr/bin/env python3
"""Read or set exactly one key, env.OTEL_METRICS_INCLUDE_SESSION_ID, in a Claude Code settings.json (local integration).

Prints only that key. Writes atomically with the original mode, refuses symlinks, and never prints or touches any
other key. `--set VALUE` writes VALUE (a JSON string); `--unset` removes the key; neither only reads.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

KEY = 'OTEL_METRICS_INCLUDE_SESSION_ID'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, default=Path.home() / '.claude/settings.json')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--set')
    group.add_argument('--unset', action='store_true')
    args = parser.parse_args()
    path = args.settings
    if path.is_symlink():
        sys.exit(f'refusing: {path} is a symlink')
    settings = json.loads(path.read_text(encoding='utf-8'))
    env = settings.get('env')
    current = env.get(KEY) if isinstance(env, dict) else None
    print(f'{KEY}: {"(unset)" if current is None else current}')
    if args.set is None and not args.unset:
        return 0
    if not isinstance(env, dict):
        if args.unset:
            return 0
        env = settings['env'] = {}
    if args.unset:
        env.pop(KEY, None)
    else:
        env[KEY] = args.set
    mode = path.stat().st_mode & 0o777
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.settings.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(settings, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    print(f'{KEY}: now {"(unset)" if args.unset else args.set}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
