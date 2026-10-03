"""Control shard 1 of the suite-shards trial: one pass, one failure (expected: Ran 2, FAILED (failures=1), exit 1).

Never placed under tests/. A failing shard must fail its step, so the parallel group and the job fail closed.
"""

import unittest


class Fail(unittest.TestCase):
    def test_passes(self):
        self.assertEqual("control", "control")

    def test_fails(self):
        self.fail("planted control failure")


if __name__ == "__main__":
    unittest.main()
