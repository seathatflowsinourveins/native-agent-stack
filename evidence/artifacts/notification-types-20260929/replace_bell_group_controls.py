#!/usr/bin/env python3
"""Controls for replace_bell_group.py: each case runs the script as a subprocess against a synthetic HOME (a temporary directory with a synthetic ~/.claude/settings.json), never a
real settings file, and checks the exit code, the words the script prints (and words it must not print) and, for --apply, the files afterwards. The cases prove the refusals work (a
bell group that holds another hook, a bell hook with a key beyond type and command, a matcher naming a type the overlay's does not, an absent matcher, an existing different
`preferredNotifChannel`, two bell groups, a symlinked file, an unknown target or flag), that the safe cases still succeed (an old matcher, a re-quoted bell command, a file with no bell
group, an unrelated group beside the bell group), that "nothing to do" is reported only when merging would change nothing, and that --apply installs the merged copy after a backup that
equals the original, keeps the file mode, leaves no staging file, does not follow a symlink at the old fixed staging name, writes nothing when it refuses, and is idempotent.
usage: python3 -B replace_bell_group_controls.py <checkout>"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

CHECKOUT = Path(sys.argv[1]).resolve()
SCRIPT = CHECKOUT / "evidence/artifacts/notification-types-20260929/replace_bell_group.py"
overlay = json.loads((CHECKOUT / "adoption/templates/claude.settings.linux-wsl2.overlay.json").read_text(encoding="utf-8"))
group = overlay["hooks"]["Notification"][0]
BELL = group["hooks"][0]["command"]
REQUOTED = BELL.replace("'{terminalSequence:$s}'", '"{terminalSequence:\\$s}"')
OLD = "permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input|quota_auto_resume_stale|quota_auto_resume_disabled|worker_permission_prompt"
OTHER = {"matcher": "auth_success", "hooks": [{"type": "command", "command": "echo other"}]}
assert OLD != group["matcher"] and REQUOTED != BELL and set(OLD.split("|")) < set(group["matcher"].split("|"))


def settings(groups, **top):
    body = {"model": "synthetic", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}, **top}
    if groups is not None:
        body["hooks"]["Notification"] = groups
    return body


def bell(matcher, command=BELL, extra=(), hook_extra=None):
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command, **(hook_extra or {})}, *extra]}


def invoke(home, args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), str(CHECKOUT), *args], capture_output=True, text=True, timeout=120, env={"HOME": str(home), "PATH": os.environ["PATH"]})


def backups(claude):
    return sorted(claude.glob("settings.json.bak.*"))


def run(name, body, args, expect_exit, words=(), absent=(), setup=None, check=None, symlink=False, second=None):
    with tempfile.TemporaryDirectory(prefix="rbc") as raw:
        home = Path(raw)
        claude = home / ".claude"
        claude.mkdir()
        target = claude / "settings.json"
        original = json.dumps(body, indent=2).encode()
        if symlink:
            real = home / "real.json"
            real.write_bytes(original)
            target.symlink_to(real)
        else:
            target.write_bytes(original)
            os.chmod(target, 0o600)
        if setup:
            setup(home, claude)
        result = invoke(home, args)
        text = result.stdout + result.stderr
        problems = []
        if (result.returncode == 0) != (expect_exit == 0):
            problems.append(f"exit {result.returncode}, expected {'0' if expect_exit == 0 else 'nonzero'}")
        problems += [f"missing words: {w!r}" for w in words if w not in text]
        problems += [f"unexpected words: {a!r}" for a in absent if a in text]
        if check:
            problems += check(home, claude, original)
        if second and not problems:
            again = invoke(home, second["args"])
            again_text = again.stdout + again.stderr
            if (again.returncode == 0) != (second["exit"] == 0) or not all(w in again_text for w in second["words"]):
                problems.append(f"second run: exit {again.returncode}, words missing: {[w for w in second['words'] if w not in again_text]}")
            problems += second["check"](home, claude, original) if second.get("check") else []
        print(("isolated " if not problems else "WRONG    ") + f"{name}: exit {result.returncode}, expected {'0' if expect_exit == 0 else 'nonzero'}" + ("" if not problems else " | " + "; ".join(problems)))
        return not problems


def untouched(home, claude, original):
    """The refused run wrote nothing: the settings file is byte-identical, there is no backup and no staging file."""
    problems = []
    if (claude / "settings.json").read_bytes() != original:
        problems.append("the settings file changed")
    if backups(claude):
        problems.append("a backup was written")
    if [p.name for p in claude.iterdir() if p.name.endswith((".tmp", ".new"))]:
        problems.append("a staging file was left")
    return problems


def installed(home, claude, original):
    problems = []
    before, now = json.loads(original), json.loads((claude / "settings.json").read_text(encoding="utf-8"))
    notify = now["hooks"]["Notification"]
    if [g for g in notify if g.get("matcher") == group["matcher"]] != [group]:
        problems.append("the bell group is not the overlay's")
    if [g for g in notify if g != group] != [g for g in before["hooks"]["Notification"] if g.get("matcher") == OTHER["matcher"]]:
        problems.append("the unrelated group did not survive")
    if now["hooks"]["Stop"] != before["hooks"]["Stop"] or now["model"] != before["model"]:
        problems.append("another key changed")
    if not all(now.get(k) == overlay[k] for k in ("$schema", "preferredNotifChannel")):
        problems.append("the overlay's own keys were not added")
    made = backups(claude)
    if len(made) != 1 or made[0].read_bytes() != original:
        problems.append("the backup is missing or differs from the original")
    if (claude / "settings.json").stat().st_mode & 0o777 != 0o600:
        problems.append("the mode changed")
    if [p.name for p in claude.iterdir() if p.name.endswith(".tmp") or (p.name.endswith(".new") and not p.is_symlink())]:
        problems.append("a staging file was left")
    return problems


def decoy_setup(home, claude):
    (home / "decoy.txt").write_text("keep", encoding="utf-8")
    (claude / "settings.json.new").symlink_to(home / "decoy.txt")


def decoy_kept(home, claude, original):
    problems = installed(home, claude, original)
    if (home / "decoy.txt").read_text(encoding="utf-8") != "keep":
        problems.append("the symlink at the old staging name was followed")
    if not (claude / "settings.json.new").is_symlink():
        problems.append("the symlink at the old staging name was removed")
    return problems


def symlink_untouched(home, claude, original):
    return (["the real file changed"] if (home / "real.json").read_bytes() != original else []) + (["a backup was written"] if backups(claude) else [])


FULL = {"$schema": overlay["$schema"], "preferredNotifChannel": overlay["preferredNotifChannel"]}
NEW = "only the bell group and the overlay's own keys changed: True"
cases = [
    ("an old matcher in a lone bell group is replaced (dry run)", settings([bell(OLD)]), ["local"], 0, dict(words=[NEW, "dry run"], check=untouched)),
    ("a hand-requoted bell command is still found (quotes and backslashes ignored)", settings([bell(OLD, REQUOTED)]), ["local"], 0, dict(words=["groups holding the bell command: 1", NEW])),
    ("a file with no bell group gets one", settings([]), ["local"], 0, dict(words=["groups holding the bell command: 0", NEW])),
    ("a file that already equals the overlay has nothing to do", settings([bell(group["matcher"])], **FULL), ["local"], 0, dict(words=["nothing to do"], check=untouched)),
    ("an equal bell group is not 'nothing to do' while the overlay's own keys are missing", settings([bell(group["matcher"])]), ["local"], 0,
     dict(words=[NEW, "overlay keys added:", "dry run"], absent=["nothing to do"])),
    ("another hook in the bell group is refused, not lost", settings([bell(OLD, extra=[{"type": "command", "command": "echo mine"}])]), ["local", "--apply"], 1, dict(words=["refused", "another hook"], check=untouched)),
    ("a bell hook with a key beyond type and command is refused", settings([bell(OLD, hook_extra={"timeout": 5})]), ["local", "--apply"], 1, dict(words=["refused", "beyond type and command", "timeout"], check=untouched)),
    ("a matcher naming a type the overlay's does not is refused, not dropped", settings([bell(OLD + "|idle_prompt")]), ["local", "--apply"], 1, dict(words=["refused", "idle_prompt", "would drop"], check=untouched)),
    ("an absent matcher is refused", settings([{"hooks": [{"type": "command", "command": BELL}]}]), ["local", "--apply"], 1, dict(words=["refused", "absent or empty"], check=untouched)),
    ("an existing different preferredNotifChannel is refused, not overwritten", settings([bell(OLD)], preferredNotifChannel="terminal_bell"), ["local", "--apply"], 1, dict(words=["refused", "overwrite", "preferredNotifChannel"], check=untouched)),
    ("two bell groups are refused", settings([bell(OLD), bell("idle_prompt")]), ["local", "--apply"], 1, dict(words=["refused", "more than one group"], check=untouched)),
    ("an unrelated Notification group is kept beside the new bell group", settings([bell(OLD), OTHER]), ["local"], 0, dict(words=["every other Notification group equal: True", NEW])),
    ("an unknown target is refused", settings([bell(OLD)]), ["locall"], 1, dict(words=["usage"], check=untouched)),
    ("an unknown flag is refused", settings([bell(OLD)]), ["local", "--force"], 1, dict(words=["usage"], check=untouched)),
    ("--apply installs the merged copy after a backup equal to the original, keeps the mode, leaves no staging file", settings([bell(OLD), OTHER]), ["local", "--apply"], 0,
     dict(words=["backup written:", "read-back equals the merged copy: True", "scratch removed: True"], check=installed,
          second=dict(args=["local"], exit=0, words=["nothing to do"], check=lambda h, c, o: [] if len(backups(c)) == 1 else ["the second run wrote a backup"]))),
    ("--apply does not follow a symlink at the old fixed staging name", settings([bell(OLD), OTHER]), ["local", "--apply"], 0, dict(words=["read-back equals the merged copy: True"], setup=decoy_setup, check=decoy_kept)),
]
bad = 0
for name, body, args, code, options in cases:
    bad += 0 if run(name, body, args, code, **options) else 1
bad += 0 if run("a symlinked settings file is refused, also with --apply, and the real file is untouched", settings([bell(OLD)]), ["local", "--apply"], 1,
                words=["refused", "symlink"], check=symlink_untouched, symlink=True) else 1
print(f"{len(cases) + 1} cases, {bad} problems")
sys.exit(1 if bad else 0)
