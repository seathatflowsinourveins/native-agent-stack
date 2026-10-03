"""Control shard 2 of the suite-shards trial: the test ends its process with os._exit(3).

Expected: the test starts, no summary is printed, the shard records exit status 3 and its step fails. Never
placed under tests/.
"""

import os
import sys
import unittest


class Crash(unittest.TestCase):
    def test_exits(self):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(3)


if __name__ == "__main__":
    unittest.main()
