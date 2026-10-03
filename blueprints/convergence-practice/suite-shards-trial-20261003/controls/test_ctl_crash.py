"""Control shard 2 of the suite-shards trial: after SLEEP_SECONDS the test ends its process with os._exit(3).

Expected: the test starts, no summary is printed, the shard records exit status 3 and its step fails. The crash
comes only after SLEEP_SECONDS, beyond control shard 3's 1-minute step limit and control shard 1's failure at 90 s,
so this step must survive both to record its own exit status. Never placed under tests/.
"""

import os
import sys
import time
import unittest

SLEEP_SECONDS = 120


class Crash(unittest.TestCase):
    def test_exits(self):
        time.sleep(SLEEP_SECONDS)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(3)


if __name__ == "__main__":
    unittest.main()
