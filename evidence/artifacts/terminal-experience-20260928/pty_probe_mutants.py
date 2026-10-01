#!/usr/bin/env python3
"""Negative controls for the signal handling of the two pty probes (alert_probe.py and its derivative push_notification_probe.py). Each mutant is a copy of the probe with one guard removed (a literal replacement in a
private temporary directory; the checkout itself is never touched), and the eight cases of the probe's selftest that can see a guard are run against it, one driver process per case: one SIGTERM, two SIGTERMs, two SIGINTs,
SIGTERM then SIGINT (the probe must end BY the first signal), a SIGTERM at each line a dry run reaches (the sweep, which also requires that no client was started when the signal landed at or before the spawn guard), the
measurement's own exit status (2, 1, 0), an inherited SIG_IGN that stays ignored and typing that stops at a latched signal (the last two are in-process and instant). A mutant must make exactly the named cases fail (an exact set,
so a case that passes whatever the probe does would show), and the unmutated probe must pass all eight. The stand-in clients are `sleep 3137<digits>`, matched exactly by their PID and argv, never by pkill -f; a case kills its
own stand-in after it has recorded the verdict, so a run leaves none behind (a run killed from outside, by the 900 s limit or a SIGKILL, can leave `sleep 3137<digits>` processes: remove them by that exact argv). Needs the
probe's working directory (~/code/native-agent-stack) and takes about three quarters of an hour per probe (the sweep case alone runs about a hundred single-line runs against the unmutated probe and against every mutant, and a
mutant whose handler never stops the run waits for the 30 s limit of each signal case). Its output is flushed per verdict only with PYTHONUNBUFFERED=1.
usage: python3 -B pty_probe_mutants.py <checkout> [alert] [push]      (default: both probes)"""
import json, subprocess, sys, tempfile
from pathlib import Path

CHECKOUT = Path(sys.argv[1]).resolve()
PROBES = {"alert": ("ask", "evidence/artifacts/terminal-experience-20260928/alert_probe.py"),
          "push": ("push", "evidence/artifacts/notification-types-20260929/push_notification_probe.py")}
SELECTED = [name for name in sys.argv[2:] if name in PROBES] or list(PROBES)
SWEEP = "a SIGTERM at each line a dry run reaches"
STATUS = "the measurement's exit status"
IGNORED = "an inherited SIG_IGN stays ignored"
TYPING = "typing stops at a latched signal"
CASES = {
    "one SIGTERM": 'probe.signal_case("KIND")',
    "two SIGTERMs": 'probe.signal_case("KIND", signums=(probe.signal.SIGTERM, probe.signal.SIGTERM))',
    "two SIGINTs": 'probe.signal_case("KIND", signums=(probe.signal.SIGINT, probe.signal.SIGINT))',
    "SIGTERM then SIGINT": 'probe.signal_case("KIND", signums=(probe.signal.SIGTERM, probe.signal.SIGINT))',
    SWEEP: 'probe.sweep_case("KIND")',
    STATUS: 'probe.status_case("ask")',
    IGNORED: 'probe.ignored_case()',
    TYPING: 'probe.typing_case()',
}
DRIVER = ("import importlib.util, json, sys\n"
          "spec = importlib.util.spec_from_file_location('probe', sys.argv[1]); probe = importlib.util.module_from_spec(spec); sys.modules['probe'] = probe; spec.loader.exec_module(probe)\n"
          "ok, detail = EXPRESSION\nprint(json.dumps([ok, detail]))\n")
LATCH = '    if STOP["signal"] is None:\n        STOP["signal"] = signum\n'
EVERY = {label for label in CASES if label not in (IGNORED, TYPING)}   # the six cases of the signal handling proper; the two in-process cases fail only for their own mutants
WITHOUT_STATUS = EVERY - {STATUS}   # the exit-status case sends no signal and does not look at the client
# name: ([(old, new), ...], the cases that must fail)
MUTANTS = {
    "no signal handler is installed": ([("            previous[number] = signal.signal(number, latch)\n", "            pass\n")], WITHOUT_STATUS),
    "the handler raises (the earlier design)": ([(LATCH, LATCH + "    raise SystemExit(128 + signum)\n")], WITHOUT_STATUS),   # every signal case: the probe exits 128 + N instead of ending BY the signal
    "the last signal wins": ([(LATCH, '    STOP["signal"] = signum\n')], {"SIGTERM then SIGINT"}),
    "the observation loop does not poll the latch": ([("        while not stopped() and ", "        while ")], WITHOUT_STATUS),   # the sweep fails it too: a signal before the client starts leaves a loop with no client and no dialog to end it
    "the client is not stopped in the cleanup": ([("            os.killpg(proc.pid, signal.SIGTERM)\n", "            pass\n"), ("            os.killpg(proc.pid, signal.SIGKILL)\n", "            pass\n")], WITHOUT_STATUS),
    "the private directory is not removed": ([("            shutil.rmtree(private, ignore_errors=True)\n", "            pass\n")], EVERY),
    "the measurement ignores exit_status": ([[("    status = exit_status(t_open, args.control, sum(n for t, n in bel_events if t_open and t >= t_open - 0.5))\n", "    status = 0\n"),
                                              ("    return exit_status(t_open, args.control, total)\n", "    return 0\n")]], {STATUS}),
    "the spawn is not guarded": ([("        if not stopped():   # a signal latched before this point: no client is started\n", "        if True:   # MUTANT: the guard is gone\n")], {SWEEP}),
    "a latched signal ends in an exit status instead of the signal": ([("    signal.signal(number, signal.SIG_DFL)\n    os.kill(os.getpid(), number)\n", "    signal.signal(number, signal.SIG_DFL)\n    sys.exit(128 + number)\n")],
                                                                      {"one SIGTERM", "two SIGTERMs", "two SIGINTs", "SIGTERM then SIGINT"}),
    "an ignored signal is latched anyway": ([("        if signal.getsignal(number) is not signal.SIG_IGN:   # a signal the parent ignored (nohup, a background job) stays ignored\n", "        if True:\n")], {IGNORED}),
    "typing ignores the latch": ([("    for character in prompt:\n        if stopped():\n            return False\n        write(master, character.encode())\n", "    for character in prompt:\n        write(master, character.encode())\n"),
                                  ("    if stopped():\n        return False\n    sleep(0.4)\n    if stopped():\n        return False\n    write(master, b\"\\r\")\n", "    sleep(0.4)\n    write(master, b\"\\r\")\n")], {TYPING}),
}


def failing_cases(path, kind):
    failed, notes = set(), []
    for label, expression in CASES.items():
        try:
            run = subprocess.run([sys.executable, "-B", "-c", DRIVER.replace("EXPRESSION", expression.replace("KIND", kind)), str(path)], capture_output=True, text=True, timeout=900)
            ok, detail = json.loads(run.stdout.strip().splitlines()[-1])
        except subprocess.TimeoutExpired:
            ok, detail = False, "the driver ran into the 900 s limit"   # a failed case, not an aborted run
        except (ValueError, IndexError):
            ok, detail = False, f"driver exit {run.returncode}, no result"
        if ok is None:
            notes.append(f"{label}: skipped ({detail})")
        elif not ok:
            failed.add(label)
    return failed, notes


bad = 0
for probe_name in SELECTED:
    kind, relative = PROBES[probe_name]
    text = (CHECKOUT / relative).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="pm-", dir="/var/tmp") as raw:
        base = Path(raw) / "baseline_probe.py"
        base.write_text(text, encoding="utf-8")
        failed, notes = failing_cases(base, kind)
    if notes:
        print(f"{probe_name}: {'; '.join(notes)}")
        sys.exit(1)
    ok = not failed
    bad += 0 if ok else 1
    print(("ok    " if ok else "WRONG ") + f"{probe_name}, the unmutated probe passes every case" + ("" if ok else f" | failing {sorted(failed)}"))
    for name, (replacements, expected) in MUTANTS.items():
        mutated = text
        for entry in replacements:
            options = entry if isinstance(entry, list) else [entry]   # a list holds one alternative per probe: the one whose site is present exactly once is used
            matching = [(old, new) for old, new in options if mutated.count(old) == 1]
            assert len(matching) == 1, f"{probe_name}: mutation site not found exactly once: {options[0][0][:70]!r}"
            mutated = mutated.replace(*matching[0])
        with tempfile.TemporaryDirectory(prefix="pm-", dir="/var/tmp") as raw:
            path = Path(raw) / "mutant_probe.py"
            path.write_text(mutated, encoding="utf-8")
            failed, _notes = failing_cases(path, kind)
        ok = failed == expected
        bad += 0 if ok else 1
        print(("ok    " if ok else "WRONG ") + f"{probe_name}, mutant, {name}: failing {len(failed)} of {len(CASES)} (expected {len(expected)})"
              + ("" if ok else f" | unexpected {sorted(failed - expected)}, missed {sorted(expected - failed)}"))
print(f"{len(SELECTED) * (len(MUTANTS) + 1)} runs, {bad} problems")
sys.exit(1 if bad else 0)
