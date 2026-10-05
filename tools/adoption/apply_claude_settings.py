#!/usr/bin/env python3
"""Deep-merge adoption/templates/claude.settings.template.json (rendered for
one host) into a live ~/.claude/settings.json, in place.

Never touches ~/.claude.json or any credential store. Backs up the current
settings file (never overwriting an earlier backup) before writing, refuses
to operate through a symlink, deep-merges nested objects (template scalars
win; host-only keys, permission rules and plugins are kept; a list gains a
missing template entry next to its template neighbours, so a deny rule stays
ahead of a `!` carve-out), combines hooks
per event de-duplicated by command, writes atomically, and preserves the
original file's mode bits. The one thing a merge removes from the live hooks is a hook
object whose command is, byte for byte, a held-out token-lane carrier command this repository shipped
(SHIPPED_CARRIER_COMMANDS, as shipped or rendered for the host's home in any spelling of it: render_config.py substitutes the
HOME it is given as written; any other hook, even one that runs a carrier, is the host's own and stays), so a host
that applied an older template ends up clean; a template that itself carries the
command keeps it, and --keep-held-out-hooks keeps the ones a host opted into (see
adoption/hooks/claude/README.md). Supports --dry-run (prints the would-be result and exits
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
import string
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"
# Hook files an earlier template installed and the clean default now holds out: the token-lane carriers, this
# repository's own adaptation (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md).
HELD_OUT_HOOK_FILES = ("token-lanes-subagent-start.py", "token-lanes-session-start.py")


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


def hook_list(group: dict) -> list:
    """A matcher group's `hooks` array, or [] when it is missing or malformed."""
    hooks = group.get("hooks")
    return hooks if isinstance(hooks, list) else []


def command_key(cmd: str) -> str:
    """Compare commands by their shell words, so quoting differences such as
    `python3 "/x/guard.py"` vs `python3 /x/guard.py` are one hook."""
    try:
        return "\0".join(shlex.split(cmd))
    except ValueError:
        return cmd


# The carrier commands this repository has shipped, as shipped, with where each first appeared (git log -S over the two files that
# carry hook commands, oldest first). A hook is retired only when its command is one of these strings, or one of them rendered for
# the host. render_config.py substitutes the HOME it is given into the template as written (one string.Template pass, no
# normalisation; tests/test_install_claude_profile.py shows the rendered form), so a carrier carries whatever spelling of its home the
# installer was given. The command must equal a shipped string exactly, no trimming (the shell treats a no-break space, a next-line
# character or a carriage return around a command as part of a word), except at one place: where the template says HOME, the text
# may be any plain absolute path that names the settings file's own home (names_home). Nothing else is parsed or expanded, so
# nothing a host wrote for itself, a wrapper, a chained command, an option, a substitution or a hand-edited carrier command can be
# mistaken for a carrier: it stays. Rounds 1 to 3 of the cross-family reads found a defect in each matcher that recognised a grammar;
# the allowlist is finite, and its one semantic check is on a path, not on shell syntax. A new shipped shape is added here, with its
# source, in the commit that ships it.
SHIPPED_CARRIER_COMMANDS = (
    ('python3 "${HOME}/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true',
     "adoption/templates/claude.settings.template.json, 0c33b37a9 (main, #378; first written as abaa8425d)"),
    ('python3 "${HOME}/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true',
     "adoption/templates/claude.settings.template.json, 2da4aaa77 (PR 684, branch c5/token-layer-2604-wide)"),
    ('python3 "$HOME/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true',
     "adoption/hooks/claude/held-out-hook-entries.json, the commit that added it (PR 699)"),
    ('python3 "$HOME/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true',
     "adoption/hooks/claude/held-out-hook-entries.json, the commit that added it (PR 699)"),
)


def carrier_frames() -> tuple:
    """What each shipped command has before and after the text that stands for HOME: the command with a NUL where the placeholder
    is, split there (the same one-pass string.Template substitution that renders it)."""
    frames = []
    for command, _ in SHIPPED_CARRIER_COMMANDS:
        before, hole, after = string.Template(command).substitute(HOME="\0").partition("\0")
        if not hole or "\0" in after:
            raise ValueError(f"a shipped carrier command must name HOME exactly once: {command!r}")
        frames.append((before, after))
    return tuple(dict.fromkeys(frames))


CARRIER_FRAMES = carrier_frames()


def carrier_commands(home: str | None) -> frozenset:
    """The strings that retire a hook on the host whose home directory is ``home`` (an absolute path; a trailing slash is
    dropped): each shipped command as shipped, and as the renderer writes it for that spelling of the home. A host whose home is not
    known (None, or not absolute) has none: retirement then removes nothing. runs_held_out_hook also accepts the other spellings of
    the home (names_home)."""
    if not home or not os.path.isabs(home):
        return frozenset()
    home = os.path.normpath(home)
    shipped = [command for command, _ in SHIPPED_CARRIER_COMMANDS]
    # One pass, as render_config.py substitutes: a home that itself contains "$HOME" is not expanded a second time.
    rendered = [string.Template(command).substitute(HOME=home) for command in shipped]
    return frozenset(shipped + rendered)


def names_home(text: str, home: str) -> bool:
    """True when ``text``, what stands where a rendered carrier command has its home, runs as written and names the directory
    ``home``: an absolute path (a relative one resolves against whatever directory the hook runs in) with no control character,
    quote, dollar sign, backtick or backslash (the shell expands or interprets those inside the double quotes the command puts around
    it, so ".../$X/.." is the home to a lexical reading and its parent to the shell) whose realpath is the realpath of ``home``. A
    trailing slash, a "." or ".." segment, a doubled or doubled leading slash and a symlink alias of the home are thus the home they
    spell, which is what render_config.py wrote when it was given one of them."""
    if not text.startswith("/") or any(not char.isprintable() or char in '"$`\\' for char in text):
        return False
    try:
        return os.path.realpath(text) == os.path.realpath(home)
    except (OSError, ValueError):
        return False


def runs_held_out_hook(entry: dict, home: str | None = None) -> bool:
    """True when a hooks-array entry's command is a carrier command this repository shipped: exactly a SHIPPED_CARRIER_COMMANDS
    string, as shipped or rendered for ``home``, or one of them whose home text is another spelling of ``home`` (names_home). No
    trimming. Without a known ``home`` nothing is retired."""
    cmd = hook_command(entry)
    if cmd is None or not home or not os.path.isabs(home):
        return False
    if cmd in carrier_commands(home):
        return True
    return any(len(cmd) > len(before) + len(after) and cmd.startswith(before) and cmd.endswith(after)
               and names_home(cmd[len(before):len(cmd) - len(after)], home) for before, after in CARRIER_FRAMES)


def retire_held_out_hooks(base_hooks, incoming_hooks, home: str | None = None):
    """`base_hooks` without the hook objects that run a held-out carrier file, unless the incoming template runs the
    same command. A group left with no hook is dropped, and so is an event left with no group; every other group,
    hook object and key keeps its value and order."""
    if not isinstance(base_hooks, dict):
        return base_hooks
    wanted = set()
    if isinstance(incoming_hooks, dict):
        for groups in incoming_hooks.values():
            for group in groups if isinstance(groups, list) else []:
                for hook in hook_list(group) if isinstance(group, dict) else []:
                    cmd = hook_command(hook)
                    if cmd is not None:
                        wanted.add(command_key(cmd))
    retired = {}
    for event, groups in base_hooks.items():
        if not isinstance(groups, list):
            retired[event] = copy.deepcopy(groups)
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept_groups.append(copy.deepcopy(group))
                continue
            kept = [hook for hook in group["hooks"]
                    if not (runs_held_out_hook(hook, home) and command_key(hook_command(hook)) not in wanted)]
            if len(kept) == len(group["hooks"]):
                kept_groups.append(copy.deepcopy(group))
            elif kept:
                kept_groups.append({**copy.deepcopy(group), "hooks": copy.deepcopy(kept)})
        if kept_groups:
            retired[event] = kept_groups
    return retired


def separate_template_hook_groups(base_groups: list, incoming_groups: list) -> list:
    """Preserve canonical ownership boundaries without reordering hooks.

    ai-memory 2.4.2 replaces a whole entry if any inner command is its own:
    akitaonrails/ai-memory a0ca8d1a5fbd5920799411fa891fe6d49c90efc1,
    install_hooks.rs:1513-1565. Its classifier/overlay still does so in v2.5.2
    (tag object af8c6820; commit 7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83):
    install_hooks.rs:1583 is_ai_memory_hook_entry and :1619 overlay_event_hooks;
    uninstall.rs:825 hook_command_is_ours defines native/legacy signatures.
    The canonical template keeps memory and carrier commands in separate entries.
    Repair older combined entries by splitting contiguous membership runs;
    preserve every original hook value, matcher and other outer field.
    """
    membership = {}
    for index, group in enumerate(incoming_groups):
        if isinstance(group, dict):
            for hook in hook_list(group):
                cmd = hook_command(hook)
                if cmd is not None:
                    membership.setdefault(command_key(cmd), index)
    result = []
    for group in base_groups:
        if not isinstance(group, dict) or not hook_list(group):
            result.append(copy.deepcopy(group))
            continue
        previous = object()
        for hook in hook_list(group):
            cmd = hook_command(hook)
            owner = membership.get(command_key(cmd)) if cmd is not None else None
            if owner != previous:
                part = copy.deepcopy(group)
                part["hooks"] = []
                result.append(part)
                previous = owner
            result[-1]["hooks"].append(copy.deepcopy(hook))
    return result


def merge_hooks(base: dict, incoming: dict) -> dict:
    """Combine hooks per event, de-duplicated by command across the event.

    A template hook is skipped when any base group of the same event already
    runs the same command (by shell words). Canonical ownership boundaries
    split existing mixed entries before deduplication; remaining template hooks
    form their own groups even when matchers match. An absent matcher and ""
    remain distinct. Base hook objects are never dropped or reordered.
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
        base_groups = separate_template_hook_groups(base_groups, incoming_groups)
        seen = {command_key(c) for g in base_groups if isinstance(g, dict)
                for c in map(hook_command, hook_list(g)) if c is not None}
        for incoming_group in incoming_groups:
            if not isinstance(incoming_group, dict):
                base_groups.append(copy.deepcopy(incoming_group))
                continue
            fresh = []
            for hook in hook_list(incoming_group):
                cmd = hook_command(hook)
                if cmd is not None and command_key(cmd) in seen:
                    continue
                fresh.append(copy.deepcopy(hook))
                if cmd is not None:
                    seen.add(command_key(cmd))
            if not fresh:
                continue
            group = copy.deepcopy(incoming_group)
            group["hooks"] = fresh
            base_groups.append(group)
        merged[event] = base_groups
    return merged


def union_in_template_order(current: list, incoming: list) -> list:
    """Union of two lists that keeps every base entry in its order and puts each
    template entry the base lacks next to its template neighbours: right after
    the nearest earlier template entry already in the result, else right before
    the nearest later one, else at the end (so a list with no template entry in
    it gets the template entries after its own, as a plain union would).

    Order carries meaning in permission lists: a `!` gitignore negation in a
    Read/Edit deny or ask list carves paths out of only the rules listed before
    it in the same settings file (code.claude.com/docs/en/permissions). A plain
    append would put a new template rule after a host's existing carve-outs."""
    merged = list(current)
    for position, item in enumerate(incoming):
        if item in merged:
            continue
        earlier = next((prior for prior in reversed(incoming[:position]) if prior in merged), None)
        if earlier is not None:
            index = merged.index(earlier) + 1
        else:
            later = next((following for following in incoming[position + 1:] if following in merged), None)
            index = merged.index(later) if later is not None else len(merged)
        merged.insert(index, copy.deepcopy(item))
    return merged


def deep_merge_dict(base: dict, incoming: dict) -> dict:
    """Recursive merge: nested dicts merge key by key, lists union (base
    entries keep their order; an absent template entry joins next to its
    template neighbours, see union_in_template_order), other template values
    win; base keys the template does not mention are kept."""
    merged = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(incoming, dict):
        return merged
    for key, value in incoming.items():
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = deep_merge_dict(current, value)
        elif isinstance(value, list) and isinstance(current, list):
            merged[key] = union_in_template_order(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def merge_settings(base: dict, template: dict, keep_held_out: bool = False, home: str | None = None) -> dict:
    """Merge `template` (the rendered adoption template) into `base` (the
    live settings), returning a new dict. Rules:
      - `hooks`: combined per event, de-duplicated by command (merge_hooks), after the hook objects that
        run a held-out carrier file are removed from the live hooks (retire_held_out_hooks) unless
        keep_held_out is true (``home``: the home directory the host's carrier commands were rendered with; without
        one nothing is retired)
      - nested objects (modelSettings, env, permissions, statusLine,
        enabledPlugins, ...): deep-merged, so host-only keys such as extra
        permission rules, plugins or per-model levels are kept
      - lists: union; host entries keep their order and a missing template
        entry joins next to its template neighbours (union_in_template_order)
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
        live = base.get("hooks") if keep_held_out else retire_held_out_hooks(base.get("hooks"), hooks, home)
        merged["hooks"] = merge_hooks(live, hooks)
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
    while os.path.lexists(candidate):
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


def host_home(target_path: Path) -> str | None:
    """The home directory a settings file belongs to: its resolved path (relative paths made absolute, symlinks followed, so an
    alias of a home names the real one) must be <home>/.claude/settings.json. Any other path has no home that this tool can
    name, and retirement then removes nothing: it never borrows the operator's own home for a file that is not theirs."""
    try:
        resolved = target_path.resolve()
    except (OSError, RuntimeError):
        return None
    if resolved.name == "settings.json" and resolved.parent.name == ".claude":
        return str(resolved.parent.parent)
    return None


def apply(template_path: Path, target_path: Path, dry_run: bool, keep_held_out: bool = False) -> dict:
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

    merged = merge_settings(base, template, keep_held_out, host_home(target_path))
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
    parser.add_argument("--keep-held-out-hooks", action="store_true",
                         help="Keep the live hook entries that run a held-out token-lane carrier file instead of "
                              "removing them (for a host that opted in; adoption/hooks/claude/README.md)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the merged result to stdout; write nothing, back up nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        apply(Path(args.template), Path(args.target), args.dry_run, args.keep_held_out_hooks)
    except ApplyError as error:
        print(f"apply failed: {error}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"apply failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
