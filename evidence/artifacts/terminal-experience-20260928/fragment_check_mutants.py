#!/usr/bin/env python3
"""Negative controls for the host practice repository's checks/check-terminal-profiles.py.

Builds single-defect mutants of the current Windows Terminal fragment. Each mutant must exit 1 from the check with exactly
one failing rule (the text after the profile name), and that rule must be the expected one, so a failure is attributed to
the rule the mutant breaks and never to a neighbouring rule. The unmutated fragment must pass in fixture mode (host-only
comparisons skipped). Two mutants share one rule on purpose: `all` and a list holding `notification` are different value
shapes of the same rule.
usage: python3 -B fragment_check_mutants.py     (needs ~/code/nativestack-practice; writes only to a temporary directory)
"""
import json, subprocess, sys, tempfile
from pathlib import Path

root = Path.home() / "code/nativestack-practice"
base = json.loads((root / "windows/nativestack.json").read_text(encoding="utf-8"))
CLAUDE, CODEX, SHELL, OPS = "NativeStack - Claude", "NativeStack - Codex", "NativeStack - Shell", "NativeStack - Operations"

def profile(data, name):
    return next(p for p in data["profiles"] if p["name"] == name)

def loud_sound(data):
    for name in (CLAUDE, CODEX):
        profile(data, name)["bellSound"] = "C:\\Windows\\Media\\Windows Notify System Generic.wav"

def wrap_colorterm(data):
    claude = profile(data, CLAUDE)
    claude["commandline"] = claude["commandline"].replace("exec claude", "export COLORTERM=truecolor; exec claude")

# label -> (mutation, the one rule that must fail)
cases = {
    "title suppression on Claude": (lambda d: profile(d, CLAUDE).update(suppressApplicationTitle=True), "AI-client profiles must let program titles through"),
    "loud sound on both AI profiles": (loud_sound, "bellSound must be one of the measured quiet sounds"),
    "relative bellSound on Codex": (lambda d: profile(d, CODEX).update(bellSound="Windows Ding.wav"), "bellSound must be an absolute local Windows sound"),
    "AI bellStyle without taskbar": (lambda d: profile(d, CLAUDE).update(bellStyle=["audible"]), "expected the reviewed bellStyle"),
    "bellStyle all on a static profile": (lambda d: profile(d, SHELL).update(bellStyle="all"), "bellStyle must list flags explicitly, never all/notification"),
    "bellStyle notification on a static profile": (lambda d: profile(d, OPS).update(bellStyle=["taskbar", "notification"]), "bellStyle must list flags explicitly, never all/notification"),
    "audible static profile": (lambda d: profile(d, SHELL).update(bellStyle="audible"), "static profiles stay silent"),
    "no COLORTERM key": (lambda d: profile(d, CLAUDE).pop("environment"), "the profile environment must set COLORTERM=truecolor"),
    "COLORTERM in the command line": (wrap_colorterm, "use the profile environment key, not a shell wrapper"),
}

def run_check(path):
    return subprocess.run([sys.executable, "-B", str(root / "checks/check-terminal-profiles.py"), str(path)], capture_output=True, text=True)

def rules_of(stdout):
    """The failing rules: every FAIL line's text after '<profile name>: '."""
    return {line[len("FAIL "):].split(": ", 1)[1] for line in stdout.splitlines() if line.startswith("FAIL ") and ": " in line}

bad = 0
with tempfile.TemporaryDirectory(prefix="fragment-mutants-") as tmp:
    for label, (mutate, expected) in cases.items():
        data = json.loads(json.dumps(base))
        mutate(data)
        path = Path(tmp) / "mutant.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        run = run_check(path)
        rules = rules_of(run.stdout)
        ok = run.returncode == 1 and len(rules) == 1 and expected in next(iter(rules))
        print(("isolated " if ok else "WRONG    ") + label + " -> " + (sorted(rules)[0][:90] if len(rules) == 1 else f"{len(rules)} rules failed"))
        bad += 0 if ok else 1
    clean = run_check(root / "windows/nativestack.json")
    print("unmutated fragment (fixture mode):", clean.returncode, clean.stdout.strip()[:100])
    bad += 0 if clean.returncode == 0 else 1
distinct = len({expected for _, expected in cases.values()})
print(f"{len(cases)} mutants, {distinct} distinct rules, {bad} problems")
sys.exit(1 if bad else 0)
