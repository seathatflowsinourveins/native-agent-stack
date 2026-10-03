"""Control shard 0 of the suite-shards trial: two passing tests (expected: Ran 2, OK, exit 0).

Never placed under tests/. The control job copies the four control modules alone into an empty directory and
runs each as one background step of a parallel group, with the arms' shard command shape.
"""

import unittest


class Pass(unittest.TestCase):
    def test_one(self):
        self.assertEqual(1 + 1, 2)

    def test_two(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
