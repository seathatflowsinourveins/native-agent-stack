#!/usr/bin/env python3
"""Bring a Claude Code user settings file to the current linux-wsl2 overlay when the overlay's Notification matcher has changed.

The repository's merge tool de-duplicates hooks by command anywhere in an event (by shell words), so it never changes the matcher of a group that already runs the bell command
(adoption/platforms/linux-wsl2.md step 3). The documented way is: remove that group, then merge the overlay again. This script does exactly that on a private copy with the
repository's own tool, and only when it is safe. The bell command is found by the merge tool's shell words or with quotes and backslashes ignored (a hand-requoted spelling is found
too), in at most one group. That group is replaced only when it holds nothing else (another hook would be lost with it), the bell hook has no key beyond `type` and `command`
(a `timeout` or `async` would be lost), and its matcher names only types the overlay's matcher also names (a type the person added would be lost); otherwise the script refuses and
says which. The copy is then compared with the original: only the bell group and the overlay's own top-level keys (`$schema`, `preferredNotifChannel`) may differ, and those two only
when the original lacks them (the merge tool would overwrite a value the person set, so the script refuses that too). With --apply it installs the copy after a backup that is never
overwritten (the merge tool's own `write_backup`) through the merge tool's own `atomic_write` (a fresh random staging name in the same directory; the local file must not be a
symlink, as the merge tool also refuses), and a failed write or a read-back that differs exits nonzero. "Nothing to do" is reported only when the bell group equals the overlay's
and merging the overlay would change nothing. Prints booleans, counts and key names only, never a settings value.
usage: replace_bell_group.py <checkout> local|polaris [--apply]"""
import copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

USAGE = "usage: replace_bell_group.py <checkout> local|polaris [--apply]"
_flags = [a for a in sys.argv[1:] if a.startswith("--")]
_positional = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(_positional) != 2 or _positional[1] not in ("local", "polaris") or any(f != "--apply" for f in _flags):
    sys.exit(USAGE)
WORKTREE = Path(_positional[0]).resolve()
TARGET = _positional[1]
APPLY = "--apply" in _flags
OVERLAY = WORKTREE / "adoption/templates/claude.settings.linux-wsl2.overlay.json"
TOOL = WORKTREE / "tools/adoption/apply_claude_settings.py"
POLARIS_BACKUP = "settings.json.bak-20260929-push-notification"
OVERLAY_KEYS = ("$schema", "preferredNotifChannel")
WSL = "/mnt/c/Windows/System32/wsl.exe"
env = {**os.environ, "WSL_UTF8": "1"}
sys.path.insert(0, str(WORKTREE / "tools/adoption"))
import apply_claude_settings as acs  # noqa: E402  (the merge tool's own helpers, so holders are found and files written the way the tool does it)

overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
overlay_group = overlay["hooks"]["Notification"][0]
bell_command = overlay_group["hooks"][0]["command"]
want_matcher = overlay_group["matcher"]
want_types = frozenset(want_matcher.split("|"))


def refuse(message):
    sys.exit("refused: " + message)


def loose(command):
    """The command without quotes and backslashes. A hand-requoted spelling of the same bell (double quotes and a backslash before the dollar sign) is still the bell, but the merge
    tool's shell-word key does not equate it, and the tool would then add a second bell group beside the old one, so the script looks for both."""
    return " ".join(re.sub(r"[\"'\\]", "", command).split())


def holds_bell(group):
    return any(acs.command_key(acs.hook_command(h) or "") == acs.command_key(bell_command) or loose(acs.hook_command(h) or "") == loose(bell_command)
               for h in acs.hook_list(group))


def wsl(*args, stdin=None):
    return subprocess.run([WSL, "-d", "Polaris", "--exec", *args], stdin=stdin, capture_output=True, timeout=120, env=env, cwd=str(Path.home()))


work = Path(tempfile.mkdtemp(prefix="rb"))
os.chmod(work, 0o700)
try:
    if TARGET == "local":
        live_path = Path.home() / ".claude/settings.json"
        if live_path.is_symlink():
            refuse("the local settings file is a symlink (the merge tool refuses it too)")
        original = live_path.read_bytes()
        mode = live_path.stat().st_mode & 0o777
    else:
        read = wsl("/bin/sh", "-c", '[ ! -L "$HOME/.claude/settings.json" ] && cat "$HOME/.claude/settings.json"')
        if read.returncode != 0 or not read.stdout:
            refuse("could not read the second distro's settings (missing, empty or a symlink)")
        original = read.stdout
        mode = 0o600
    try:
        before = json.loads(original)
    except ValueError:
        refuse("the settings file is not valid JSON")
    if not isinstance(before, dict):
        refuse("the settings file does not hold a JSON object")
    print(TARGET, "| read", len(original), "bytes | sha256 prefix", hashlib.sha256(original).hexdigest()[:12], "| top-level keys", len(before))
    hooks_before = before.get("hooks", {})
    groups = hooks_before.get("Notification", []) if isinstance(hooks_before, dict) else None
    if groups is None or not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
        refuse("the Notification hooks are not a list of groups")
    holders = [g for g in groups if holds_bell(g)]
    print("groups holding the bell command:", len(holders), "| their matcher already equals the overlay's:", [g.get("matcher") == want_matcher for g in holders])
    if len(holders) == 1 and holders[0] == overlay_group and acs.merge_settings(before, overlay) == before:
        print("nothing to do: the bell group equals the overlay's and merging the overlay would change nothing")
        sys.exit(0)
    if len(holders) > 1:
        refuse("more than one group holds the bell command")
    if holders:
        holder = holders[0]
        if len(acs.hook_list(holder)) != 1:
            refuse("the bell group also holds another hook, which removing the group would lose; edit that file by hand")
        extra_keys = sorted(set(acs.hook_list(holder)[0]) - {"type", "command"})
        if extra_keys:
            refuse(f"the bell hook has {len(extra_keys)} key(s) beyond type and command ({', '.join(re.sub(r'[^a-zA-Z_]', '?', k) for k in extra_keys)}), which replacing it would lose; edit that file by hand")
        held = holder.get("matcher")
        held_types = frozenset(held.split("|")) if isinstance(held, str) and held else None
        if held_types is None or not held_types <= want_types:
            beyond = sorted(held_types - want_types) if held_types is not None else []
            names = [t for t in beyond if re.fullmatch(r"[a-z_]+", t)]
            refuse("the bell group's matcher " + ("is absent or empty (rings for every type)" if held_types is None else
                   f"names {len(beyond)} type(s) the overlay's matcher does not ({', '.join(names)}{' and other patterns' if len(names) < len(beyond) else ''})")
                   + ", which replacing it would drop; edit that file by hand")
    trimmed = copy.deepcopy(before)
    if holders:
        trimmed["hooks"]["Notification"] = [g for g in groups if g not in holders]
        if not trimmed["hooks"]["Notification"]:
            del trimmed["hooks"]["Notification"]
    copy_path = work / "settings.json"
    copy_path.write_text(json.dumps(trimmed, indent=2) + "\n", encoding="utf-8")
    os.chmod(copy_path, 0o600)
    merged_run = subprocess.run([sys.executable, "-B", str(TOOL), "--template", str(OVERLAY), "--target", str(copy_path)], capture_output=True, text=True, timeout=60)
    print("merge tool exit:", merged_run.returncode)
    if merged_run.returncode != 0:
        refuse("the merge tool failed")
    after = json.loads(copy_path.read_text(encoding="utf-8"))
    changed = sorted(key for key in list(before) + [k for k in after if k not in before] if before.get(key) != after.get(key))
    print("top-level keys that differ from the original:", changed)
    overwritten = [key for key in changed if key in OVERLAY_KEYS and key in before]
    if overwritten:
        refuse(f"merging would overwrite the value the file already sets for {', '.join(overwritten)}; edit that file by hand")
    other_events = [e for e in list(before.get("hooks", {})) + list(after.get("hooks", {})) if e != "Notification"]
    other_hooks_equal = all(before.get("hooks", {}).get(e) == after.get("hooks", {}).get(e) for e in other_events)
    notify = after["hooks"]["Notification"]
    bells = [g for g in notify if holds_bell(g)]
    bell_ok = len(bells) == 1 and bells[0].get("matcher") == want_matcher and bells[0].get("hooks") == overlay_group["hooks"]
    others_before = [g for g in groups if g not in holders]
    others_after = [g for g in notify if g not in bells]
    other_groups_equal = sorted(json.dumps(g, sort_keys=True) for g in others_before) == sorted(json.dumps(g, sort_keys=True) for g in others_after)
    print("every other hook event equal:", other_hooks_equal, "| exactly one bell group equal to the overlay's:", bell_ok, "| every other Notification group equal:", other_groups_equal)
    only_expected = all(key == "hooks" or key in OVERLAY_KEYS for key in changed) and other_hooks_equal and bell_ok and other_groups_equal
    print("only the bell group and the overlay's own keys changed:", only_expected, "| overlay keys added:", [key for key in changed if key in OVERLAY_KEYS])
    if not only_expected:
        refuse("an unexpected difference")
    if not APPLY:
        print("dry run: nothing installed")
        sys.exit(0)
    new_bytes = copy_path.read_bytes()
    try:
        if TARGET == "local":
            acs.refuse_symlink(live_path)
            backup = acs.write_backup(live_path)
            print("backup written:", backup.name)
            acs.atomic_write(live_path, new_bytes.decode("utf-8"), mode)
            installed, write_ok = live_path.read_bytes(), True
        else:
            script = ('set -e; umask 077; d="$HOME/.claude"; f="$d/settings.json"; [ ! -L "$f" ]; [ -f "$f" ]; '
                      f'(set -C; cat "$f" > "$d/{POLARIS_BACKUP}"); t=$(mktemp "$d/.settings.json.XXXXXX"); trap \'rm -f "$t"\' EXIT; cat > "$t"; chmod 600 "$t"; mv -f "$t" "$f"')
            push = wsl("/bin/sh", "-c", script, stdin=open(copy_path, "rb"))
            write_ok = push.returncode == 0
            print("write back exit:", push.returncode)
            installed = wsl("/bin/sh", "-c", 'cat "$HOME/.claude/settings.json"').stdout
    except (OSError, acs.ApplyError) as error:
        sys.exit(f"the write failed: {type(error).__name__}")
    matches = json.loads(installed) == after
    print("read-back equals the merged copy:", matches, "| sha256 prefix", hashlib.sha256(installed).hexdigest()[:12])
    if not (write_ok and matches):
        sys.exit("the write or its read-back failed")
finally:
    shutil.rmtree(work, ignore_errors=True)
    print("scratch removed:", not work.exists())
