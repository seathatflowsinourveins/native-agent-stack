#!/usr/bin/env python3
"""In which order does CPython run the Python handlers of signals that are pending together? (finding F4 of the post-merge read, 2026-09-30). The three handled signals are blocked, two of them are sent to the process in a
chosen order, and they are unblocked together, so both are pending at the next dispatch. The probes' latch keeps the first signal its handler sees, so "first signal wins" holds for signals that arrive one dispatch apart and
not for signals that arrive together. Prints the order for three sending orders. Exit 0 when in every case the handlers ran in ascending signal number (SIGHUP, SIGINT, SIGTERM) whatever the sending order, 1 otherwise.
usage: signal_order_probe.py"""
import os
import signal
import sys

NUMBERS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
ascending = True
for first, second in ((signal.SIGTERM, signal.SIGHUP), (signal.SIGHUP, signal.SIGTERM), (signal.SIGTERM, signal.SIGINT)):
    seen = []
    for number in NUMBERS:
        signal.signal(number, lambda n, _frame: seen.append(n))
    signal.pthread_sigmask(signal.SIG_BLOCK, list(NUMBERS))
    os.kill(os.getpid(), first)
    os.kill(os.getpid(), second)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, list(NUMBERS))
    ascending = ascending and seen == sorted(seen)
    print(f"sent {signal.Signals(first).name} then {signal.Signals(second).name}: the handlers ran in the order {[signal.Signals(n).name for n in seen]}")
print(f"the handlers ran in ascending signal number in every case: {ascending}")
sys.exit(0 if ascending else 1)
