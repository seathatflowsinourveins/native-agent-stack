"""Control shard 1 of the suite-shards trial: one failure after SLEEP_SECONDS, then one pass (expected: Ran 2,
FAILED (failures=1), a non-zero exit).

Never placed under tests/. A failing shard must fail its step, so the parallel group and the job fail closed. The
failure comes only after SLEEP_SECONDS, beyond control shard 3's 1-minute step limit, so this step must survive the
runner stopping that step to record its own exit status.
"""

import time
import unittest

SLEEP_SECONDS = 90


class Fail(unittest.TestCase):
    def test_fails(self):
        time.sleep(SLEEP_SECONDS)
        self.fail("planted control failure")

    def test_passes(self):
        self.assertEqual("control", "control")


if __name__ == "__main__":
    unittest.main()
