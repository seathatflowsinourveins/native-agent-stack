#!/usr/bin/env python3
"""Bring a Claude Code user settings file to the current linux-wsl2 overlay when the overlay's Notification matcher has changed.

The repository's merge tool de-duplicates hooks by command anywhere in an event (by shell words), so it never changes the matcher of a group that already runs the bell command
(adoption/platforms/linux-wsl2.md step 3). The documented way is: remove that group, then merge the overlay again. This script does exactly that on a private copy with the
repository's own tool, and only when it is safe: the bell command must be found (by the merge tool's shell words, or with quotes and backslashes ignored, so a hand-requoted spelling
is found too), in at most one group, and that group must hold
nothing else (another hook in the same group would be lost with it: the script refuses and says so). It then compares the whole Notification list before and after (the other groups
unchanged, the bell group equal to the overlay's) and every other key, and with --apply installs the copy atomically after a backup (the local file must not be a symlink, as the merge
tool also refuses). A failed write or a read-back that differs exits nonzero. Prints booleans and key names only, never a settings value.
usage: replace_bell_group.py <checkout> local|polaris [--apply]"""
import copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

if len(sys.argv) < 3 or sys.argv[2] not in ("local", "polaris"):
    sys.exit("usage: replace_bell_group.py <checkout> local|polaris [--apply]")
WORKTREE = Path(sys.argv[1]).resolve()
TARGET = sys.argv[2]
APPLY = "--apply" in sys.argv
OVERLAY = WORKTREE / "adoption/templates/claude.settings.linux-wsl2.overlay.json"
TOOL = WORKTREE / "tools/adoption/apply_claude_settings.py"
BACKUP = "settings.json.bak-20260929-push-notification"
WSL = "/mnt/c/Windows/System32/wsl.exe"
env = {**os.environ, "WSL_UTF8": "1"}
sys.path.insert(0, str(WORKTREE / "tools/adoption"))
import apply_claude_settings as acs  # noqa: E402  (the merge tool's own command_key, so holders are found the way the tool finds them)

overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
overlay_group = overlay["hooks"]["Notification"][0]
bell_command = overlay_group["hooks"][0]["command"]
want_matcher = overlay_group["matcher"]


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
        read = wsl("/bin/sh", "-c", 'cat "$HOME/.claude/settings.json"')
        if read.returncode != 0 or not read.stdout:
            refuse("could not read the second distro's settings")
        original = read.stdout
        mode = 0o600
    before = json.loads(original)
    print(TARGET, "| read", len(original), "bytes | sha256 prefix", hashlib.sha256(original).hexdigest()[:12], "| top-level keys", len(before))
    groups = before.get("hooks", {}).get("Notification", [])
    holders = [g for g in groups if holds_bell(g)]
    print("groups holding the bell command:", len(holders), "| their matcher already equals the overlay's:", [g.get("matcher") == want_matcher for g in holders])
    if len(holders) == 1 and holders[0].get("matcher") == want_matcher:
        print("nothing to do: the live matcher already equals the overlay's")
        sys.exit(0)
    if len(holders) > 1:
        refuse("more than one group holds the bell command")
    if holders and len(acs.hook_list(holders[0])) != 1:
        refuse("the bell group also holds another hook, which removing the group would lose; edit that file by hand")
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
    other_events = [e for e in list(before.get("hooks", {})) + list(after.get("hooks", {})) if e != "Notification"]
    other_hooks_equal = all(before.get("hooks", {}).get(e) == after.get("hooks", {}).get(e) for e in other_events)
    notify = after["hooks"]["Notification"]
    bells = [g for g in notify if holds_bell(g)]
    bell_ok = len(bells) == 1 and bells[0].get("matcher") == want_matcher and bells[0].get("hooks") == overlay_group["hooks"]
    others_before = [g for g in groups if g not in holders]
    others_after = [g for g in notify if g not in bells]
    other_groups_equal = sorted(json.dumps(g, sort_keys=True) for g in others_before) == sorted(json.dumps(g, sort_keys=True) for g in others_after)
    print("every other hook event equal:", other_hooks_equal, "| exactly one bell group equal to the overlay's:", bell_ok, "| every other Notification group equal:", other_groups_equal)
    only_expected = all(key in ("hooks", "$schema", "preferredNotifChannel") for key in changed) and other_hooks_equal and bell_ok and other_groups_equal
    print("only the bell group changed:", only_expected)
    if not only_expected:
        refuse("an unexpected difference")
    if not APPLY:
        print("dry run: nothing installed")
        sys.exit(0)
    new_bytes = copy_path.read_bytes()
    if TARGET == "local":
        backup = live_path.parent / BACKUP
        if backup.exists():
            refuse("the backup already exists; not overwriting an earlier backup")
        shutil.copy2(live_path, backup)
        os.chmod(backup, 0o600)
        staging = live_path.parent / (live_path.name + ".new")
        staging.write_bytes(new_bytes)
        os.chmod(staging, mode)
        os.replace(staging, live_path)
        installed, write_ok = live_path.read_bytes(), True
    else:
        push = wsl("/bin/sh", "-c", f'set -e; d="$HOME/.claude"; [ ! -e "$d/{BACKUP}" ]; cp -p "$d/settings.json" "$d/{BACKUP}"; cat > "$d/settings.json.new"; chmod 600 "$d/settings.json.new"; mv "$d/settings.json.new" "$d/settings.json"',
                   stdin=open(copy_path, "rb"))
        write_ok = push.returncode == 0
        print("write back exit:", push.returncode)
        installed = wsl("/bin/sh", "-c", 'cat "$HOME/.claude/settings.json"').stdout
    matches = json.loads(installed) == after
    print("read-back equals the merged copy:", matches, "| sha256 prefix", hashlib.sha256(installed).hexdigest()[:12])
    if not (write_ok and matches):
        sys.exit("the write or its read-back failed")
finally:
    shutil.rmtree(work, ignore_errors=True)
    print("scratch removed:", not work.exists())
