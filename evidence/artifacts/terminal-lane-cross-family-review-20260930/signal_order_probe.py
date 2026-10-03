#!/usr/bin/env python3
"""In which order does CPython run the Python handlers of signals that are pending together? (finding F4 of the post-merge read and U11 of the post-merge GPT read, 2026-10). The three handled signals are blocked, two of them are
sent to the process in a chosen order, and they are unblocked together, so both are pending at the next dispatch. The probes' latch keeps the first signal its handler sees, so "the first signal wins" holds for signals that arrive
one dispatch apart and not for signals that arrive together. For each of three sending orders the recorded order of the handlers must EQUAL the expected list: both signals, in ascending signal number (SIGHUP, SIGINT, SIGTERM),
whatever the sending order. An empty or incomplete observation is a failure, never a pass. `--selftest` runs the same check against two broken recorders (one that records nothing, one that records only the first handler) and
requires both to be rejected. CPython runs the Python-level handlers of the signals that are pending in ascending signal number: `_PyErr_CheckSignalsTstate`, called by `PyErr_CheckSignals`, loops `for (int i = 1; i < Py_NSIG; i++)`
(Modules/signalmodule.c at v3.13.0, read 2026-10-01); signal(7) says "If multiple standard signals are pending for a process, the order in which the signals are delivered is unspecified", which is why the order is
measured here and not assumed. Exit 0 when every case equals its expectation (or, with --selftest, when both broken recorders are rejected), 1 otherwise. usage: signal_order_probe.py [--selftest]"""
import os
import signal
import sys

NUMBERS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
CASES = ((signal.SIGTERM, signal.SIGHUP), (signal.SIGHUP, signal.SIGTERM), (signal.SIGTERM, signal.SIGINT))


def records_everything(seen):
    return lambda number, _frame: seen.append(number)


def records_nothing(seen):
    return lambda number, _frame: None


def records_only_the_first(seen):
    return lambda number, _frame: seen.append(number) if not seen else None


def observe(first, second, recorder):
    """The order in which the handlers ran when `first` and then `second` were sent with both blocked."""
    seen = []
    for number in NUMBERS:
        signal.signal(number, recorder(seen))
    signal.pthread_sigmask(signal.SIG_BLOCK, list(NUMBERS))
    os.kill(os.getpid(), first)
    os.kill(os.getpid(), second)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, list(NUMBERS))
    return seen


def accepted(first, second, seen):
    """The check: both handlers ran, in ascending signal number, exactly."""
    return seen == sorted([int(first), int(second)])


def run(recorder):
    results = []
    for first, second in CASES:
        seen = observe(first, second, recorder)
        ok = accepted(first, second, seen)
        results.append(ok)
        print(f"sent {signal.Signals(first).name} then {signal.Signals(second).name}: the handlers ran in the order {[signal.Signals(n).name for n in seen]}; equals the expected ascending pair: {ok}")
    return all(results)


if "--selftest" in sys.argv[1:]:
    rejected = [not run(recorder) for recorder in (records_nothing, records_only_the_first)]
    print("the check rejects a recorder that records nothing and one that records only the first handler:", all(rejected))
    sys.exit(0 if all(rejected) else 1)
everything = run(records_everything)
print("the handlers ran in ascending signal number, both of them, in every case:", everything)
sys.exit(0 if everything else 1)
