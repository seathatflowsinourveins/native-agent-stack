#!/usr/bin/env python3
"""Controls for replace_bell_group.py: each case runs the script as a subprocess against a synthetic HOME (a temporary directory with a synthetic ~/.claude/settings.json), never a
real settings file, and checks the exit code and the words the script prints. The cases prove the refusals work (a bell group that holds another hook, two bell groups, a symlinked
file, an unknown target) and that the safe cases still succeed (an old matcher, a re-quoted bell command, a file with no bell group, a file that already matches).
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
assert OLD != group["matcher"] and REQUOTED != BELL


def settings(groups):
    body = {"model": "synthetic", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}}
    if groups is not None:
        body["hooks"]["Notification"] = groups
    return body


def bell(matcher, command=BELL, extra=()):
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}, *extra]}


def run(name, body, args, expect_exit, words, symlink=False):
    with tempfile.TemporaryDirectory(prefix="rbc") as home:
        claude = Path(home) / ".claude"
        claude.mkdir()
        target = claude / "settings.json"
        if symlink:
            real = Path(home) / "real.json"
            real.write_text(json.dumps(body), encoding="utf-8")
            target.symlink_to(real)
        else:
            target.write_text(json.dumps(body), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(CHECKOUT), *args], capture_output=True, text=True, timeout=120,
                                env={"HOME": home, "PATH": os.environ["PATH"]})
        text = result.stdout + result.stderr
        ok = (result.returncode == 0) == (expect_exit == 0) and all(w in text for w in words)
        print(("isolated " if ok else "WRONG    ") + f"{name}: exit {result.returncode}, expected {'0' if expect_exit == 0 else 'nonzero'}")
        return ok


cases = [
    ("an old matcher in a lone bell group is replaced (dry run)", settings([bell(OLD)]), ["local"], 0, ["only the bell group changed: True", "dry run"]),
    ("a hand-requoted bell command is still found (quotes and backslashes ignored)", settings([bell(OLD, REQUOTED)]), ["local"], 0, ["groups holding the bell command: 1", "only the bell group changed: True"]),
    ("a file with no bell group gets one", settings([]), ["local"], 0, ["groups holding the bell command: 0", "only the bell group changed: True"]),
    ("a file that already matches has nothing to do", settings([bell(group["matcher"])]), ["local"], 0, ["nothing to do"]),
    ("another hook in the bell group is refused, not lost", settings([bell(OLD, extra=[{"type": "command", "command": "echo mine"}])]), ["local"], 1, ["refused", "another hook"]),
    ("two bell groups are refused", settings([bell(OLD), bell("idle_prompt")]), ["local"], 1, ["refused", "more than one group"]),
    ("an unrelated Notification group is kept beside the new bell group", settings([bell(OLD), {"matcher": "auth_success", "hooks": [{"type": "command", "command": "echo other"}]}]), ["local"], 0, ["every other Notification group equal: True", "only the bell group changed: True"]),
    ("an unknown target is refused", settings([bell(OLD)]), ["locall"], 1, ["usage"]),
]
bad = 0
for name, body, args, code, words in cases:
    bad += 0 if run(name, body, args, code, words) else 1
bad += 0 if run("a symlinked settings file is refused", settings([bell(OLD)]), ["local"], 1, ["refused", "symlink"], symlink=True) else 1
print(f"{len(cases) + 1} cases, {bad} problems")
sys.exit(1 if bad else 0)
