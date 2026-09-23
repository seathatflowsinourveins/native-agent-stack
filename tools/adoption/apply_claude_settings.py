#!/usr/bin/env python3
"""Deep-merge adoption/templates/claude.settings.template.json (rendered for
one host) into a live ~/.claude/settings.json, in place.

Never touches ~/.claude.json or any credential store. Backs up the current
settings file before writing, refuses to operate through a symlink, merges
scalars template-wins / modelSettings deep-merged / hooks combined per event
and de-duplicated by command, writes atomically, and preserves the original
file's mode bits. Supports --dry-run (prints the would-be result and exits
without touching anything).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"


class ApplyError(ValueError):
    """The merge or the target file could not be safely applied."""


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def hook_command(entry: dict) -> str | None:
    """A single hooks-array entry's own inner command string, if any."""
    if not isinstance(entry, dict):
        return None
    cmd = entry.get("command")
    return cmd if isinstance(cmd, str) else None


def merge_hook_matcher_group(base_group: dict, incoming_group: dict) -> dict:
    """Merge one {"matcher": ..., "hooks": [...]} entry pair.

    Combines the two `hooks` arrays, de-duplicating by each inner entry's own
    `command` string (base entries keep their position; a template hook whose
    command already exists in the base is skipped, never duplicated).
    """
    merged = copy.deepcopy(base_group)
    base_hooks = merged.get("hooks")
    if not isinstance(base_hooks, list):
        base_hooks = []
        merged["hooks"] = base_hooks
    existing_commands = {hook_command(h) for h in base_hooks if hook_command(h) is not None}
    for hook in incoming_group.get("hooks", []) if isinstance(incoming_group.get("hooks"), list) else []:
        cmd = hook_command(hook)
        if cmd is not None and cmd in existing_commands:
            continue
        base_hooks.append(copy.deepcopy(hook))
        if cmd is not None:
            existing_commands.add(cmd)
    return merged


def matcher_key(group) -> tuple:
    """A stable identity for one hook matcher-group entry.

    Distinct groups sharing the same (or absent) matcher are combined into
    one merged group rather than appended as separate list entries, so a
    template group and a base group for the same matcher merge their
    `hooks` arrays instead of duplicating the whole group.
    """
    if not isinstance(group, dict):
        return ("__non_dict__", json.dumps(group, sort_keys=True))
    return ("matcher", group.get("matcher", ""))


def merge_hooks(base: dict, incoming: dict) -> dict:
    """Combine hooks per event, de-duplicated by command (never dropped)."""
    merged: dict = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(incoming, dict):
        return merged
    for event, incoming_groups in incoming.items():
        if not isinstance(incoming_groups, list):
            continue
        base_groups = merged.get(event)
        if not isinstance(base_groups, list):
            merged[event] = copy.deepcopy(incoming_groups)
            continue
        by_key = {matcher_key(g): i for i, g in enumerate(base_groups)}
        for incoming_group in incoming_groups:
            key = matcher_key(incoming_group)
            if key in by_key and isinstance(incoming_group, dict):
                idx = by_key[key]
                base_groups[idx] = merge_hook_matcher_group(base_groups[idx], incoming_group)
            else:
                base_groups.append(copy.deepcopy(incoming_group))
                by_key[key] = len(base_groups) - 1
        merged[event] = base_groups
    return merged


def deep_merge_dict(base: dict, incoming: dict) -> dict:
    """Generic recursive dict merge: template (incoming) scalars win;
    nested dicts merge deeply; incoming keys not in base are added."""
    merged = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(incoming, dict):
        return merged
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def merge_settings(base: dict, template: dict) -> dict:
    """Merge `template` (the rendered adoption template) into `base` (the
    live settings), returning a new dict. Rules:
      - scalars: template wins (overwrites base)
      - `modelSettings`: deep-merged (per-model dicts merge key by key)
      - `hooks`: combined per event, de-duplicated by inner `command`
      - everything else the template does not mention: kept from base
      - everything else new in the template: added
    """
    if not isinstance(base, dict):
        raise ApplyError("live settings file does not contain a JSON object")
    if not isinstance(template, dict):
        raise ApplyError("rendered template does not contain a JSON object")

    merged = copy.deepcopy(base)
    for key, value in template.items():
        if key == "hooks":
            merged["hooks"] = merge_hooks(base.get("hooks"), value)
        elif key == "modelSettings":
            merged["modelSettings"] = deep_merge_dict(base.get("modelSettings", {}), value)
        elif key == "env":
            # env is a flat map; template keys win, base-only keys are kept.
            merged_env = dict(base.get("env") or {})
            merged_env.update(value if isinstance(value, dict) else {})
            merged["env"] = merged_env
        else:
            # Template scalars (including nested non-modelSettings dicts
            # like permissions, statusLine, enabledPlugins) win outright.
            merged[key] = copy.deepcopy(value)
    return merged


def refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ApplyError(f"refusing to operate through a symlink: {path}")


def backup_path(target: Path) -> Path:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return target.with_name(f"{target.name}.bak.{timestamp}")


def atomic_write(target: Path, text: str, mode: int) -> None:
    directory = target.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def apply(template_path: Path, target_path: Path, dry_run: bool) -> dict:
    if not template_path.is_file():
        raise ApplyError(f"template not found: {template_path}")
    template = load_json(template_path)

    refuse_symlink(target_path)
    if target_path.exists() and not target_path.is_file():
        raise ApplyError(f"target is not a regular file: {target_path}")

    if target_path.is_file():
        base = load_json(target_path)
        original_mode = stat.S_IMODE(target_path.stat().st_mode)
    else:
        base = {}
        original_mode = 0o600

    merged = merge_settings(base, template)
    rendered = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"

    if dry_run:
        print(rendered, end="")
        return merged

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.is_file():
        refuse_symlink(target_path)  # re-check right before mutating: TOCTOU-narrow
        backup = backup_path(target_path)
        shutil.copy2(target_path, backup)
        print(f"Backed up {target_path} -> {backup}", file=sys.stderr)

    atomic_write(target_path, rendered, original_mode)
    print(f"Wrote {target_path}", file=sys.stderr)
    return merged


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                         help="Rendered claude.settings.template.json to merge in "
                              "(render it first with tools/adoption/render_config.py --out; "
                              "this tool does not substitute ${...} placeholders itself)")
    parser.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"),
                         help="Live settings.json to merge into (default: ~/.claude/settings.json)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the merged result to stdout; write nothing, back up nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        apply(Path(args.template), Path(args.target), args.dry_run)
    except ApplyError as error:
        print(f"apply failed: {error}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"apply failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
