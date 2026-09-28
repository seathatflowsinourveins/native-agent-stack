#!/usr/bin/env python3
"""Private host state, following docs/secret-storage.md and Python secrets/os APIs.

Only init writes; the builder never invokes it. Values are not printed.
"""
import argparse
import json
import os
import secrets
import stat
from pathlib import Path


def locations():
    prefix = Path.home() / ".local/share/codex-ecosystem/tools/crawl4ai-0.9.4"
    state = Path.home() / ".local/state/native-agent-stack/runtime-workers/crawl4ai"
    return prefix, state


def outside_repository(path, *, mapped_leaf=False):
    resolved = path.resolve()
    # A previously initialized container mount can be owned by a mapped UID and
    # mode 0700. Its host-owned ancestors remain inspectable; do not enter it.
    parents = resolved.parents if mapped_leaf else (resolved, *resolved.parents)
    if any((parent / ".git").exists() for parent in parents):
        raise ValueError("private installation/state must be outside every Git repository")
    if path.is_symlink():
        raise ValueError("refusing symlink at private root")


def private_file(path):
    mode = path.lstat()
    if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600 or mode.st_uid != os.getuid():
        raise ValueError("private file must be owned regular file with mode 0600")
    outside_repository(path)


def load_host():
    _, state = locations()
    path = state / "host.json"
    private_file(path)
    data = json.loads(path.read_text())
    ports = [data[key] for key in ("api_port", "fixture_port", "mirror_port", "e2e_api_port")]
    if any(type(p) is not int or not 3730 <= p <= 3799 for p in ports) or len(set(ports)) != 4:
        raise ValueError("private host ports must be distinct integers in 3730..3799")
    for key in ("docker", "python", "working_directory"):
        if not Path(data[key]).is_absolute() or "\n" in data[key]:
            raise ValueError("host paths must be absolute single-line values")
    if data["docker_context"] != "rootless":
        raise ValueError("this recipe requires the rootless Docker context")
    return data


def initialize():
    prefix, state = locations()
    for root in (prefix, state):
        outside_repository(root)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
    for name in ("secrets", "cache", "crawl", "work", "runs", "downloads", "browser-cache", "tmp", "containers"):
        path = state / name
        outside_repository(path)
        path.mkdir(mode=0o700, exist_ok=True)
        path.chmod(0o700)
    for store in ("persistent", "e2e"):
        parent = state / "containers" / store
        outside_repository(parent)
        parent.mkdir(mode=0o700, exist_ok=True)
        for kind in ("crawl", "cache", "redis"):
            path = parent / kind
            mapped = path.exists() and path.lstat().st_uid != os.getuid()
            outside_repository(path, mapped_leaf=mapped)
            # After first startup these are owned by appuser inside rootless Docker.
            # Do not attempt to chmod/chown an existing mapped-UID directory on host.
            path.mkdir(mode=0o700, exist_ok=True)
    host = state / "host.json"
    if not host.exists():
        template = Path(__file__).parent / "config/host.example.json"
        data = json.loads(template.read_text())
        content = json.dumps({key: value.replace("${HOME}", str(Path.home())) if isinstance(value, str) else value
                              for key, value in data.items()}, indent=2) + "\n"
        with os.fdopen(os.open(host, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(content)
    load_host()
    for name in ("api_token", "secret_key", "redis_password"):
        path = state / "secrets" / name
        if not path.exists():
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                stream.write(secrets.token_hex(32) + "\n")
        private_file(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "get"))
    parser.add_argument("key", nargs="?")
    args = parser.parse_args()
    if args.action == "init":
        initialize()
    else:
        print(load_host()[args.key])
