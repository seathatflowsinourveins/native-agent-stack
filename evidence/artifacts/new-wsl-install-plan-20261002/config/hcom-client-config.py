#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Apply the agent-messaging extension of the new-WSL client-config map.

The shared mapper enumerates existing template pieces; it cannot add new deny
rules or a rules file (this PR: tools/adoption/new_wsl_client_config.py:549-579).
This bounded adapter reads only slot_configs.agent-messaging from that same map,
and reuses its settings merge, instruction-block writer and atomic writer.
Native formats: aannoo/hcom@2c5f343:src/config.rs:126-152;
https://code.claude.com/docs/en/permissions; https://developers.openai.com/codex/rules.
It installs no hooks and launches no client. Run --check-map without touching a
client home; --check checks the installed files; --apply writes missing settings.
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


BEGIN = "<!-- native-agent-stack:agent-messaging:begin -->"
END = "<!-- native-agent-stack:agent-messaging:end -->"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--rules-source", type=Path, help="the installer's plan-owned copied rule source")
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
    rules = args.rules_source or root / spec["codex_rule_file"]
    cfg.file_io.refuse_symlink(rules)
    # Check the shared mapper's authorization classification only. This adapter
    # never writes crossSessionInbound; only the shared mapper's --apply with
    # --with-authorization-settings may write that authorization setting.
    key = "claude/settings/setting/crossSessionInbound"
    entry = next(e for e in cfg.load_map(root)
                 if any(fnmatch.fnmatchcase(key, p) for p in e.match))
    if not entry.wiring.startswith("authorization:"):
        raise ValueError("crossSessionInbound must retain the mapper's authorization classification")
    inbound = entry.raw.get("override", cfg.template_data(root, "claude/settings")["crossSessionInbound"])
    if inbound != "accept" or not rules.is_file() or not spec["claude_settings"]["permissions"]["deny"]:
        raise ValueError("the converged native messaging configuration is incomplete")
    if args.check_map:
        print("agent-messaging: map, native inbound setting and rule source present")
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

    settings_path = claude_home / "settings.json"
    settings_bytes = original(settings_path)
    settings = json.loads(settings_bytes) if settings_bytes is not None else {}
    incoming = dict(spec["claude_settings"])
    if args.check and "crossSessionInbound" in settings and settings["crossSessionInbound"] != inbound:
        print("agent-messaging: Claude crossSessionInbound differs; the user's authorization choice is retained")
    merged = cfg.file_io.merge_settings(settings, incoming)
    if merged != settings:
        put(settings_path, (json.dumps(merged, indent=2, ensure_ascii=False) + "\n").encode(), settings_bytes)

    rule_target = codex_home / "rules/hcom-deny.rules"
    rule_bytes = original(rule_target)
    wanted_rules = rules.read_bytes()
    if rule_bytes is not None and rule_bytes != wanted_rules:
        pending.append("existing hcom-deny.rules differs; review it before replacing it")
    else:
        put(rule_target, wanted_rules, rule_bytes)

    block = f"{BEGIN}\n{spec['peer_instructions'].strip()}\n{END}\n"
    for target in (claude_home / "CLAUDE.md", codex_home / "AGENTS.md"):
        before = original(target)
        current = before.decode() if before is not None else ""
        wanted = cfg.managed_block.with_block(current, block, BEGIN, END).encode()
        put(target, wanted, before)

    if args.apply and changes:
        # Reuse the shared mapper's process guard. Its native rule loader reads
        # rules on startup; an active client must close before this apply.
        if cfg.running_codex_pids("codex") or cfg.running_codex_pids("codex-daemon"):
            print("needs_user: close Codex, rerun the messaging row, then restart Codex")
            return 3
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
    if args.check:
        done = subprocess.run(["codex", "execpolicy", "check", "--pretty", "--rules", str(rule_target),
                               "--", "hcom", "term", "inject", "luna", "hi"],
                              capture_output=True, text=True, check=True)
        if json.loads(done.stdout).get("decision") != "forbidden":
            raise ValueError("installed Codex rule file did not forbid terminal injection")
    print("agent-messaging: mapped posture " + ("applied; restart Codex to load its rules" if args.apply else "checked"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        # Do not print exception payloads: native settings may contain private
        # operator values, and subprocess output is not public acceptance data.
        print("agent-messaging: native configuration check failed (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
