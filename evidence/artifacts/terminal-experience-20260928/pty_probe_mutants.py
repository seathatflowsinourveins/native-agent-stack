#!/usr/bin/env python3
"""Negative controls for the pty probes' signal handling and their end-to-end cases (alert_probe.py and its derivative push_notification_probe.py). Each mutant is a copy of the probe with one guard
removed (a literal replacement in a private temporary directory; the checkout itself is never touched), and the six signal cases of the probe's selftest (the end-to-end ones also require that the stand-in inherited no blocked signal) are run against it, one driver process per case:
one SIGTERM, two SIGTERMs, two SIGINTs, one SIGTERM while the probe's own normal-exit cleanup runs, a signal while the client is being created, a signal at the start of the final cleanup. A mutant must
make exactly the named cases fail (an exact set, so a case that passes whatever the probe does would show), and the unmutated probe must pass all six. The stand-in clients are `sleep 3137<digits>`, matched exactly by their PID and
argv, never by pkill -f; a failing case kills its own stand-in after it has recorded the verdict, so a run leaves none behind. Needs the probe's working directory (~/code/native-agent-stack) and takes about five minutes per probe.
usage: python3 -B pty_probe_mutants.py <checkout> [alert] [push]      (default: both probes)"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

CHECKOUT = Path(sys.argv[1]).resolve()
PROBES = {"alert": ("ask", "evidence/artifacts/terminal-experience-20260928/alert_probe.py"),
          "push": ("push", "evidence/artifacts/notification-types-20260929/push_notification_probe.py")}
SELECTED = [name for name in sys.argv[2:] if name in PROBES] or list(PROBES)
CASES = {
    "one SIGTERM": 'probe.signal_case("KIND")',
    "two SIGTERMs": 'probe.signal_case("KIND", signals=2)',
    "two SIGINTs": 'probe.signal_case("KIND", signals=2, signum=probe.signal.SIGINT)',
    "one SIGTERM during the normal-exit cleanup": 'probe.signal_case("KIND", stand_in="trust", delay=6.5)',
    "a signal while the client is being created": 'probe.client_boundary_case("KIND")',
    "a signal at the start of the final cleanup": "probe.cleanup_phase_case()",
}
DRIVER = ("import importlib.util, json, sys\n"
          "spec = importlib.util.spec_from_file_location('probe', sys.argv[1]); probe = importlib.util.module_from_spec(spec); sys.modules['probe'] = probe; spec.loader.exec_module(probe)\n"
          "ok, detail = EXPRESSION\nprint(json.dumps([ok, detail]))\n")
LEAVE_LOOP = "    for number in HANDLED:\n        signal.signal(number, signal.SIG_IGN)   # the first signal wins: the exit it starts must not be cut short by a second one\n"
CLIENT_CLEANUP = "        with deferred_signals():   # the client's cleanup must not be cut short; a signal that arrives meanwhile is delivered when it is done\n"
CLIENT_CREATE = '        SPAWN["active"], SPAWN["signal"] = True, None   # a signal while the client is created waits until the client is recorded (a mask would be inherited by the client)\n'
CLIENT_SPAWN_END = '        finally:\n            SPAWN["active"] = False\n'
MASK_CREATE = "        signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)\n"
MASK_CREATE_END = "        finally:\n            signal.pthread_sigmask(signal.SIG_UNBLOCK, HANDLED)\n"
DIR_CLEANUP = "        with deferred_signals():\n            shutil.rmtree(private, ignore_errors=True)\n"
EVERY = set(CASES)
# name: ([(old, new), ...], the cases that must fail)
MUTANTS = {
    "no signal handler is installed": ([("    previous = {number: signal.signal(number, leave) for number in HANDLED}\n", "    previous = {}\n")],
                                       EVERY - {"a signal at the start of the final cleanup"}),   # that case is guarded by the deferral, which this mutant leaves in place
    "SIGINT is not handled": ([("HANDLED = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)\n", "HANDLED = (signal.SIGTERM, signal.SIGHUP)\n")], {"two SIGINTs"}),
    "the client's cleanup is not deferred and the first signal does not silence the rest": ([(CLIENT_CLEANUP, "        if True:\n"), (LEAVE_LOOP, "")],
                                                                                         {"two SIGTERMs", "two SIGINTs", "one SIGTERM during the normal-exit cleanup"}),
    "the client is created without the spawn flag": ([(CLIENT_CREATE, '        SPAWN["active"], SPAWN["signal"] = False, None\n')], {"a signal while the client is being created"}),
    "the client is created under a signal mask (it inherits the mask)": ([(CLIENT_CREATE, MASK_CREATE), (CLIENT_SPAWN_END, MASK_CREATE_END)], EVERY - {"a signal at the start of the final cleanup"}),
    "the private directory's cleanup is not deferred": ([(DIR_CLEANUP, "        if True:\n            shutil.rmtree(private, ignore_errors=True)\n")], {"a signal at the start of the final cleanup"}),
}


def failing_cases(path, kind):
    failed, notes = set(), []
    for label, expression in CASES.items():
        run = subprocess.run([sys.executable, "-B", "-c", DRIVER.replace("EXPRESSION", expression.replace("KIND", kind)), str(path)], capture_output=True, text=True, timeout=240)
        try:
            ok, detail = json.loads(run.stdout.strip().splitlines()[-1])
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
        for old, new in replacements:
            assert mutated.count(old) == 1, f"{probe_name}: mutation site not found exactly once: {old[:70]!r}"
            mutated = mutated.replace(old, new)
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
