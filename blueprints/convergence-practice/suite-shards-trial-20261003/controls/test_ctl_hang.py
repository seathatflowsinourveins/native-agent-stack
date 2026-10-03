"""Control shard 3 of the suite-shards trial: the test sleeps far beyond its step's limit.

The workflow gives this step `timeout-minutes: 1`. Expected: the test starts, the runner stops the step at the
limit, so the step writes no exit status and no summary appears; the step fails. If the limit were not
enforced on a background step, the test would pass after SLEEP_SECONDS and the shard would record exit 0,
which the control check rejects. Never placed under tests/.
"""

import time
import unittest

SLEEP_SECONDS = 300


class Hang(unittest.TestCase):
    def test_sleeps(self):
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    unittest.main()
