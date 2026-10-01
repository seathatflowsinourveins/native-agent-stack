#!/usr/bin/env python3
"""Negative controls for the signal handling of the two pty probes (alert_probe.py and its derivative push_notification_probe.py). Each mutant is a copy of the probe with one guard removed (a literal replacement in a private temporary directory; the
checkout itself is never touched), and the twelve cases of the probe's selftest that can see a guard are run against it, one driver process per case: one SIGTERM, two SIGTERMs, two SIGINTs, SIGTERM then SIGINT (the probe must end BY the first signal),
a SIGTERM at each line a dry run reaches in `main`, `with_private_dir`, `measure`, `end_by_latched_signal` and `emit_report` (the sweep: every run must end BY SIGTERM, and no client may have been started when the signal landed at or before the spawn
guard, counted by `subprocess.Popen` calls of the client), the measurement's own exit status (2, 1, 0), which is a quick case too, and six more quick cases: an inherited SIG_IGN that stays ignored (also at the end of the process), typing that stops at a latched signal and never writes
an Enter after it, a closed stdout (with a latched signal, and with none: the exit status must stay the measurement's), a stdout that is a full pipe (with a latched signal, and with one that arrives once the child is blocked in its write) or a blocked signal that does not keep the probe
from ending by the signal (the real `main` with a measurement that signals itself), a second signal after the cleanups that does not replace the first, a truncated sweep record that is reported while the stand-in is killed, and a static check that `measure` and `type_prompt` write nothing to stdout or stderr themselves. A mutant must make exactly the named cases fail (an exact set, so a case that passes whatever the
probe does would show), and the unmutated probe must pass all twelve. A mutant whose guard only the quick cases can see runs only those seven (the slow cases are not run for it: the line says how many cases it ran); one mutant must also fail for a stated
reason, not incidentally (the spawn mutant keeps the guard's `# SPAWN GUARD` marker and must fail through the sweep's client-start observation; the mutant that prints before the handoff must fail through the full-pipe child). It refuses to run when SIGINT, SIGTERM or SIGHUP is ignored in its own process (a background job of a non-interactive `sh` ignores SIGINT, and the probes honor an inherited ignore). A skipped case ends the run for
a mutant as for the baseline. The stand-in clients are `sleep 3137<digits>`, matched exactly by their PID and argv, never by pkill -f; a case kills its own stand-in after it has recorded the verdict, so a run leaves none behind (a run killed from outside,
by the 900 s limit or a SIGKILL, can leave `sleep 3137<digits>` processes and `/tmp/sweep-*` directories: remove them by that exact name). Needs the probe's working directory (~/code/native-agent-stack) and takes more than an hour per probe (the sweep case
alone runs about a hundred and thirty single-line runs against the unmutated probe and against every slow mutant, and a mutant whose handler never stops the run waits for the 30 s limit of each signal case). Output is flushed per verdict only with
PYTHONUNBUFFERED=1.
usage: python3 -B pty_probe_mutants.py <checkout> [alert] [push] [--quick] [--only <text>]     (default: both probes; --quick runs only the seven quick cases and --only the mutants whose name holds the text, without the baseline, for development: their output is not a record)"""
import json, signal, subprocess, sys, tempfile
from pathlib import Path

if any(signal.getsignal(number) is signal.SIG_IGN for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)):
    sys.exit("REFUSED: SIGINT, SIGTERM or SIGHUP is ignored in this process (nohup, or a background job of a non-interactive sh, which ignores SIGINT): the probes honor an inherited ignore, so every case that sends it would fail; start the runner from a shell that does not ignore it")

CHECKOUT = Path(sys.argv[1]).resolve()
PROBES = {"alert": ("ask", "evidence/artifacts/terminal-experience-20260928/alert_probe.py"),
          "push": ("push", "evidence/artifacts/notification-types-20260929/push_notification_probe.py")}
SELECTED = [name for name in sys.argv[2:] if name in PROBES] or list(PROBES)
QUICK_MODE = "--quick" in sys.argv[2:]
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv[2:] else None      # development: only the mutants whose name holds this text, and no baseline run
A1, A2, A3, A4 = "one SIGTERM", "two SIGTERMs", "two SIGINTs", "SIGTERM then SIGINT"
SWEEP = "a SIGTERM at each line a dry run reaches"
STATUS = "the measurement's exit status"
IGNORED = "an inherited SIG_IGN stays ignored"
TYPING = "typing stops at a latched signal and never writes Enter after it"
FLUSH = "a closed or stuck stdout or a blocked signal does not keep the probe from ending by the signal, or from exiting with its own status"
HANDOFF = "a second signal after the cleanups does not replace the first"
PARTIAL = "a truncated sweep record is reported and the stand-in killed"
NOOUT = "no output is written while the latch is installed"
CASES = {
    A1: 'probe.signal_case("KIND")',
    A2: 'probe.signal_case("KIND", signums=(probe.signal.SIGTERM, probe.signal.SIGTERM))',
    A3: 'probe.signal_case("KIND", signums=(probe.signal.SIGINT, probe.signal.SIGINT))',
    A4: 'probe.signal_case("KIND", signums=(probe.signal.SIGTERM, probe.signal.SIGINT))',
    SWEEP: 'probe.sweep_case("KIND")',
    STATUS: 'probe.status_case("ask")',
    IGNORED: 'probe.ignored_case()',
    TYPING: 'probe.typing_case()',
    FLUSH: 'probe.flush_case("KIND")',
    HANDOFF: 'probe.handoff_case("KIND")',
    PARTIAL: 'probe.partial_case()',
    NOOUT: 'probe.noout_case()',
}
SIGNALS = {A1, A2, A3, A4}
QUICK = {STATUS, IGNORED, TYPING, FLUSH, HANDOFF, PARTIAL, NOOUT}
DRIVER = ("import importlib.util, json, sys\n"
          "spec = importlib.util.spec_from_file_location('probe', sys.argv[1]); probe = importlib.util.module_from_spec(spec); sys.modules['probe'] = probe; spec.loader.exec_module(probe)\n"
          "ok, detail = EXPRESSION\nprint(json.dumps([ok, detail]))\n")
LATCH = '    if STOP["signal"] is None:\n        STOP["signal"] = signum\n'
GUARD = "        if not stopped():   # SPAWN GUARD: a signal latched before this point starts no client\n"
UNBLOCK = "    signal.pthread_sigmask(signal.SIG_UNBLOCK, {number})      # a mask inherited from the parent would leave the signal pending\n"
# name: (replacements, the cases that must fail, the cases to run (None = all), a text that the failing case's detail must hold)
MUTANTS = {
    "no signal handler is installed": ([("            previous[number] = signal.signal(number, latch)\n", "            pass\n")], SIGNALS | {SWEEP, FLUSH, IGNORED}, None, None),   # FLUSH: the real `main` is killed by the measurement's own SIGTERM and leaves its payload directory; IGNORED: SIGINT keeps Python's own handler, not the default action the handoff gives back
    "the handler raises (the earlier design)": ([(LATCH, LATCH + "    raise SystemExit(128 + signum)\n")], {A2, A3, A4, SWEEP, TYPING}, None, None),   # not A1 and not HANDOFF: `main`'s `finally` turns the raised exit into death BY the latched signal, whatever the handler does; a second signal during the cleanup raises inside it and leaves the client
    "the last signal wins": ([(LATCH, '    STOP["signal"] = signum\n')], {A4, HANDOFF}, None, None),
    "the observation loop does not poll the latch": ([("        while not stopped() and ", "        while ")], SIGNALS | {SWEEP, HANDOFF}, None, None),
    "the client is not stopped in the cleanup": ([("            os.killpg(proc.pid, signal.SIGTERM)\n", "            pass\n"), ("            os.killpg(proc.pid, signal.SIGKILL)\n", "            pass\n")], SIGNALS | {SWEEP}, None, None),
    "the private directory is not removed": ([("            shutil.rmtree(private, ignore_errors=True)\n", "            pass\n")], SIGNALS | {SWEEP, STATUS, HANDOFF, FLUSH}, None, None),   # FLUSH: its children now check that no payload directory is left
    "the spawn is not guarded": ([(GUARD, "        if True:   # SPAWN GUARD: MUTANT, the guard is gone\n")], {SWEEP}, None, (SWEEP, "a client was started although the signal landed at or before the spawn guard")),
    "a latched signal ends in an exit status instead of the signal": ([(UNBLOCK + "    os.kill(os.getpid(), number)\n", UNBLOCK + "    sys.exit(128 + number)\n")], SIGNALS | {FLUSH, HANDOFF, SWEEP}, None, None),   # SWEEP: it now accepts only death BY SIGTERM, not an exit status 143
    "the measurement ignores exit_status": ([[("    status = exit_status(t_open, args.control, sum(n for t, n in bel_events if t_open and t >= t_open - 0.5))\n", "    status = 0\n"),
                                              ("    return exit_status(t_open, args.control, total)\n", "    return 0\n")]], {STATUS}, QUICK, None),
    "an ignored signal is latched anyway": ([("        if signal.getsignal(number) is not signal.SIG_IGN:   # a signal the parent ignored (nohup, a background job) stays ignored\n", "        if True:\n")], {IGNORED}, QUICK, None),
    "typing: the check before each keystroke is gone": ([("    for character in prompt:\n        if stopped():\n            return False\n        write(master, character.encode())\n", "    for character in prompt:\n        write(master, character.encode())\n")], {TYPING}, QUICK, None),
    "typing: the check before the wait is gone": ([("        sleep(0.004)\n    if stopped():\n        return False\n    sleep(0.4)\n", "        sleep(0.004)\n    sleep(0.4)\n")], {TYPING}, QUICK, None),
    "typing: the check before the Enter is gone": ([("    try:\n        if stopped():\n            return False\n        write(master, b\"\\r\")\n", "    try:\n        write(master, b\"\\r\")\n")], {TYPING}, QUICK, None),
    "typing: the Enter is not written under the signal block": ([("    before = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)\n    try:\n", "    before = None\n    try:\n"),
                                                               ("    finally:\n        signal.pthread_sigmask(signal.SIG_SETMASK, before)\n    return True\n", "    finally:\n        pass\n    return True\n")], {TYPING}, QUICK, None),
    "a truncated sweep record raises": ([("            try:\n                info = json.loads(record.read_text()) if record.exists() else {}\n            except (OSError, ValueError):\n"
                                           "                info = {\"unreadable_record\": True}      # a driver killed while it wrote its record: a finding of this trial, not an exception that skips the cleanup\n",
                                           "            info = json.loads(record.read_text()) if record.exists() else {}\n")], {PARTIAL}, QUICK, None),
    "a flush comes back before the final kill": ([("    signal.signal(number, signal.SIG_DFL)\n    signal.pthread_sigmask(", "    sys.stdout.flush()\n    signal.signal(number, signal.SIG_DFL)\n    signal.pthread_sigmask(")], {FLUSH}, QUICK, None),
    "the previous handlers are restored before the process ends": ([("        status = with_private_dir(work, restore=False)\n", "        status = with_private_dir(work)\n")], {HANDOFF}, QUICK, None),
    "the signal is not unblocked before the final kill": ([(UNBLOCK, "")], SIGNALS | {SWEEP, HANDOFF, FLUSH}, None, None),   # the handoff blocks the handled signals itself, so without the unblock the kill leaves the signal pending in every latched run
    "the snapshot of the latch is read without a block": ([("    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)      # nothing below can be overtaken by a handler\n", "    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])\n")], {SWEEP}, None, None),
    "the latch is not handed back to the default action when nothing was latched": ([("        for each in HANDLED:\n            if signal.getsignal(each) is latch:\n                signal.signal(each, signal.SIG_DFL)\n", "")], {SWEEP, IGNORED, FLUSH}, None, None),   # FLUSH: a signal during the blocked write of the report is latched and lost
    "an ignored signal is handed to the default action too": ([("            if signal.getsignal(each) is latch:\n", "            if True:\n")], {IGNORED}, QUICK, None),
    "the diagnostic is printed before the handoff": ([("        end_by_latched_signal()   # the last safe point", "        emit_report(used)   # MUTANT: the output comes first\n        end_by_latched_signal()   # the last safe point"),
                                                     ("        emit_report(used)         # so a signal during the output", "        pass                      # so a signal during the output")], {FLUSH}, QUICK, (FLUSH, "full-pipe: the child was still running")),
    "a failed report leaves its bytes for the final flush": ([("            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())\n", "            pass\n")], {FLUSH}, QUICK, (FLUSH, "closed-stdout-exit: the child ended with 120")),
    "the measurement writes a result line itself": ([('    say(f"kind={args.kind} control={args.control} state={state} dialog_opened=', '    print(f"kind={args.kind} control={args.control} state={state} dialog_opened=')], {NOOUT}, QUICK, None),
}


def failing_cases(path, kind, only=None):
    failed, notes, details = set(), [], {}
    for label, expression in CASES.items():
        if only is not None and label not in only:
            continue
        try:
            run = subprocess.run([sys.executable, "-B", "-c", DRIVER.replace("EXPRESSION", expression.replace("KIND", kind)), str(path)], capture_output=True, text=True, timeout=900)
            ok, detail = json.loads(run.stdout.strip().splitlines()[-1])
        except subprocess.TimeoutExpired:
            ok, detail = False, "the driver ran into the 900 s limit"   # a failed case, not an aborted run
        except (ValueError, IndexError):
            ok, detail = False, f"driver exit {run.returncode}, no result"
        details[label] = detail
        if ok is None:
            notes.append(f"{label}: skipped ({detail})")
        elif not ok:
            failed.add(label)
    return failed, notes, details


bad = 0
runs = 0
for probe_name in SELECTED:
    kind, relative = PROBES[probe_name]
    text = (CHECKOUT / relative).read_text(encoding="utf-8")
    if ONLY is None:
        with tempfile.TemporaryDirectory(prefix="pm-", dir="/var/tmp") as raw:
            base = Path(raw) / "baseline_probe.py"
            base.write_text(text, encoding="utf-8")
            failed, notes, _details = failing_cases(base, kind, QUICK if QUICK_MODE else None)
        if notes:
            print(f"{probe_name}: {'; '.join(notes)}")
            sys.exit(1)
        ok = not failed
        bad += 0 if ok else 1
        runs += 1
        print(("ok    " if ok else "WRONG ") + f"{probe_name}, the unmutated probe passes every case" + ("" if ok else f" | failing {sorted(failed)}"))
    for name, (replacements, expected, only, reason) in MUTANTS.items():
        if ONLY is not None and ONLY not in name:
            continue
        mutated = text
        for entry in replacements:
            options = entry if isinstance(entry, list) else [entry]   # a list holds one alternative per probe: the one whose site is present exactly once is used
            matching = [(old, new) for old, new in options if mutated.count(old) == 1]
            assert len(matching) == 1, f"{probe_name}: mutation site not found exactly once: {options[0][0][:70]!r}"
            mutated = mutated.replace(*matching[0])
        run_only = QUICK if QUICK_MODE else only
        want = expected if run_only is None else expected & run_only
        with tempfile.TemporaryDirectory(prefix="pm-", dir="/var/tmp") as raw:
            path = Path(raw) / "mutant_probe.py"
            path.write_text(mutated, encoding="utf-8")
            failed, notes, details = failing_cases(path, kind, run_only)
        if notes:
            print(f"{probe_name}, mutant, {name}: {'; '.join(notes)}")
            sys.exit(1)
        ok = failed == want
        if ok and reason is not None and reason[0] in details and reason[1] not in details[reason[0]]:   # the reason is checked when its case was run
            ok = False
            why = f" | failed, but not for the stated reason {reason[1]!r}: {details.get(reason[0], '')[:200]}"
        else:
            why = "" if ok else f" | unexpected {sorted(failed - want)}, missed {sorted(want - failed)}"
        bad += 0 if ok else 1
        runs += 1
        total = len(CASES) if run_only is None else len(run_only)
        print(("ok    " if ok else "WRONG ") + f"{probe_name}, mutant, {name}: failing {len(failed)} of {total} cases run (expected {len(want)})" + why)
print(f"{runs} runs, {bad} problems")
sys.exit(1 if bad else 0)
