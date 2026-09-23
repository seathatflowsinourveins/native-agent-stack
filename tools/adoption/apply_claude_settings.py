#!/usr/bin/env python3
"""Deep-merge adoption/templates/claude.settings.template.json (rendered for
one host) into a live ~/.claude/settings.json, in place.

Never touches ~/.claude.json or any credential store. Backs up the current
settings file (never overwriting an earlier backup) before writing, refuses
to operate through a symlink, deep-merges nested objects (template scalars
win; host-only keys, permission rules and plugins are kept), combines hooks
per event de-duplicated by command, writes atomically, and preserves the
original file's mode bits. Supports --dry-run (prints the would-be result and exits
without touching anything).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
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


def command_key(cmd: str) -> str:
    """Compare commands by their shell words, so quoting differences such as
    `python3 "/x/guard.py"` vs `python3 /x/guard.py` are one hook."""
    try:
        return "\0".join(shlex.split(cmd))
    except ValueError:
        return cmd


def merge_hooks(base: dict, incoming: dict) -> dict:
    """Combine hooks per event, de-duplicated by command across the event.

    A template hook is skipped when any base group of the same event already
    runs the same command (by shell words). Remaining template hooks join the
    first base group with the identical matcher (an absent matcher and "" are
    kept distinct, so the host's structure is preserved), or form a new group.
    Base hooks are never dropped or reordered.
    """
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
        seen = {command_key(c) for g in base_groups if isinstance(g, dict)
                for c in map(hook_command, g.get("hooks") or []) if c is not None}
        for incoming_group in incoming_groups:
            if not isinstance(incoming_group, dict):
                base_groups.append(copy.deepcopy(incoming_group))
                continue
            fresh = []
            for hook in incoming_group.get("hooks") or []:
                cmd = hook_command(hook)
                if cmd is not None and command_key(cmd) in seen:
                    continue
                fresh.append(copy.deepcopy(hook))
                if cmd is not None:
                    seen.add(command_key(cmd))
            if not fresh:
                continue
            has_matcher = "matcher" in incoming_group
            target = next((g for g in base_groups if isinstance(g, dict)
                           and ("matcher" in g) == has_matcher
                           and g.get("matcher") == incoming_group.get("matcher")
                           and isinstance(g.get("hooks"), list)), None)
            if target is not None:
                target["hooks"].extend(fresh)
            else:
                group = copy.deepcopy(incoming_group)
                group["hooks"] = fresh
                base_groups.append(group)
        merged[event] = base_groups
    return merged


def deep_merge_dict(base: dict, incoming: dict) -> dict:
    """Recursive merge: nested dicts merge key by key, lists union (base
    entries first, template entries appended when absent), other template
    values win; base keys the template does not mention are kept."""
    merged = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(incoming, dict):
        return merged
    for key, value in incoming.items():
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = deep_merge_dict(current, value)
        elif isinstance(value, list) and isinstance(current, list):
            merged[key] = current + [copy.deepcopy(item) for item in value if item not in current]
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def merge_settings(base: dict, template: dict) -> dict:
    """Merge `template` (the rendered adoption template) into `base` (the
    live settings), returning a new dict. Rules:
      - `hooks`: combined per event, de-duplicated by command (merge_hooks)
      - nested objects (modelSettings, env, permissions, statusLine,
        enabledPlugins, ...): deep-merged, so host-only keys such as extra
        permission rules, plugins or per-model levels are kept
      - lists: union, host entries first
      - scalars: template wins
      - keys the template does not mention: kept from base
    """
    if not isinstance(base, dict):
        raise ApplyError("live settings file does not contain a JSON object")
    if not isinstance(template, dict):
        raise ApplyError("rendered template does not contain a JSON object")
    hooks = template.get("hooks")
    merged = deep_merge_dict(base, {k: v for k, v in template.items() if k != "hooks"})
    if hooks is not None:
        merged["hooks"] = merge_hooks(base.get("hooks"), hooks)
    return merged


def refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ApplyError(f"refusing to operate through a symlink: {path}")


def backup_path(target: Path) -> Path:
    """A new, not-yet-existing backup name (UTC timestamp plus a counter when
    two applies land in the same second)."""
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    candidate = target.with_name(f"{target.name}.bak.{timestamp}")
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.bak.{timestamp}.{counter}")
        counter += 1
    return candidate


def write_backup(target: Path) -> Path:
    """Copy target to a fresh backup, never overwriting an existing one."""
    while True:
        backup = backup_path(target)
        try:
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(target.stat().st_mode))
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as handle, open(target, "rb") as source:
            shutil.copyfileobj(source, handle)
        return backup


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
        backup = write_backup(target_path)
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
