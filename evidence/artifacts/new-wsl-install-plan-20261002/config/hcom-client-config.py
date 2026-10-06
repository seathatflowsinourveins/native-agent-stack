#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Apply the agent-messaging extension of the new-WSL client-config map.

The shared mapper (tools/adoption/new_wsl_client_config.py) enumerates existing
template pieces; it cannot add hcom's own configuration file or the
peer-instruction blocks. This bounded adapter reads only
slot_configs.agent-messaging from that same map, and reuses the mapper's
instruction-block writer and atomic writer.
Native format: aannoo/hcom@2c5f343:src/config.rs:126-152.
It writes no Claude permission rule and no Codex rule file: upstream's hcom.rules,
which `hcom codex` writes, is the only Codex hcom policy
(docs/decisions/2026-10-06-hcom-relaxation.md). It installs no hooks and
launches no client. Run --check-map without touching a client home; --check
checks the installed files; --apply writes missing settings.
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


BEGIN = "<!-- native-agent-stack:agent-messaging:begin -->"
END = "<!-- native-agent-stack:agent-messaging:end -->"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-map", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    sys.path.insert(0, str(root / "tools/adoption"))
    import new_wsl_client_config as cfg

    mapping = cfg.read_json(root / cfg.MAP_REL)
    spec = mapping["slot_configs"]["agent-messaging"]
    manifest = cfg.load_manifest(root)["agent-messaging"]
    if not cfg.installs(manifest) or "hcom 0.7.27" not in cfg.installed_default(manifest):
        raise ValueError("agent-messaging must install its adopted hcom 0.7.27 owner")
    # Check the shared mapper's authorization classification only. This adapter
    # never writes crossSessionInbound; only the shared mapper's --apply with
    # --with-authorization-settings may write that authorization setting.
    key = "claude/settings/setting/crossSessionInbound"
    entry = next(e for e in cfg.load_map(root)
                 if any(fnmatch.fnmatchcase(key, p) for p in e.match))
    if not entry.wiring.startswith("authorization:"):
        raise ValueError("crossSessionInbound must retain the mapper's authorization classification")
    inbound = entry.raw.get("override", cfg.template_data(root, "claude/settings")["crossSessionInbound"])
    if inbound != "accept":
        raise ValueError("the converged native messaging configuration is incomplete")
    if args.check_map:
        print("agent-messaging: map and native inbound setting present")
        return 0

    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    hcom_home = Path(os.environ.get("HCOM_DIR", Path.home() / ".hcom"))
    pending = []
    changes = []

    def original(path):
        cfg.file_io.refuse_symlink(path)
        if path.exists() and not path.is_file():
            raise ValueError("a messaging target is not a regular file")
        return path.read_bytes() if path.exists() else None

    def put(path, wanted, before):
        if wanted == before:
            return
        if args.check:
            raise ValueError("installed messaging files differ from their mapped settings")
        changes.append((path, wanted, before))

    # hcom's relay credentials can live in config.toml. Never parse or display
    # an existing file: compare its digest with our public template, and retain
    # anything different for the user's own configuration review.
    hcom_path = hcom_home / "config.toml"
    cfg.file_io.refuse_symlink(hcom_path)
    hcom_text = cfg.emit_toml(spec["hcom_config"], "# NativeStack2604 hcom messaging posture\n").encode()
    if hcom_path.exists():
        if cfg.lane.sha256_file(hcom_path) != hashlib.sha256(hcom_text).hexdigest():
            pending.append("existing hcom configuration differs; review the mapped posture yourself")
    else:
        put(hcom_path, hcom_text, None)

    if args.check:
        settings_bytes = original(claude_home / "settings.json")
        settings = json.loads(settings_bytes) if settings_bytes is not None else {}
        if "crossSessionInbound" in settings and settings["crossSessionInbound"] != inbound:
            print("agent-messaging: Claude crossSessionInbound differs; the user's authorization choice is retained")

    block = f"{BEGIN}\n{spec['peer_instructions'].strip()}\n{END}\n"
    for target in (claude_home / "CLAUDE.md", codex_home / "AGENTS.md"):
        before = original(target)
        current = before.decode() if before is not None else ""
        wanted = cfg.managed_block.with_block(current, block, BEGIN, END).encode()
        put(target, wanted, before)

    if args.apply:
        for path, wanted, before in changes:
            path.parent.mkdir(parents=True, exist_ok=True)
            cfg.file_io.refuse_symlink(path)
            mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o600
            if before is not None:
                cfg.file_io.write_backup(path)
            try:
                cfg.lane.atomic_write(path, wanted, mode,
                                      hashlib.sha256(before).hexdigest() if before is not None else None)
            except cfg.lane.Failed:
                raise ValueError("a messaging target changed during apply") from None

    if pending:
        for item in pending:
            print("needs_user: " + item)
        return 3
    print("agent-messaging: mapped configuration " + (
        "applied; running Claude Code and Codex sessions read the instruction block when they next start"
        if args.apply else "checked"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        # Do not print exception payloads: native settings may contain private
        # operator values.
        print("agent-messaging: native configuration check failed (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
