"""Control shard 3 of the suite-shards trial: the test runs far beyond its step's limit.

The workflow gives this step `timeout-minutes: 1`. Expected: the test starts, the runner stops the step at the
limit, so the step writes no exit status and no summary appears; the step fails. If the limit were not enforced
on a background step, the test would pass after SLEEP_SECONDS and the shard would record exit 0, which the
control check rejects. Never placed under tests/.

Every HEARTBEAT_SECONDS the test appends `<time.monotonic_ns()> <parent process id>` to HEARTBEAT_FILE in its
working directory (the control suite's directory, outside the checkout). The control job's finish step records
the file, so the oracle can tell how long this process lived after its step started and whether it outlived the
step (its parent, the step's shell, gone, or the heartbeat still advancing after the parallel group ended).
"""

import os
import time
import unittest

SLEEP_SECONDS = 300
HEARTBEAT_SECONDS = 1
HEARTBEAT_FILE = "test_ctl_hang.heartbeat"


class Hang(unittest.TestCase):
    def test_sleeps(self):
        deadline = time.monotonic() + SLEEP_SECONDS
        while time.monotonic() < deadline:
            with open(HEARTBEAT_FILE, "a", encoding="utf-8") as beats:
                beats.write(f"{time.monotonic_ns()} {os.getppid()}\n")
            time.sleep(HEARTBEAT_SECONDS)


if __name__ == "__main__":
    unittest.main()
