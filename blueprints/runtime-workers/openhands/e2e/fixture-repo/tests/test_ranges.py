import unittest

from range_utils import compress_ranges


class RangeTests(unittest.TestCase):
    def test_ranges_follow_the_spec(self):
        inputs = [[], [4], [8, 2, 1, 3, 5, 5, 7], [-2, -1, 0, 4, 4, 5]]
        before = [list(values) for values in inputs]
        self.assertEqual(
            [compress_ranges(values) for values in inputs],
            [[], [(4, 4)], [(1, 3), (5, 5), (7, 8)], [(-2, 0), (4, 5)]],
        )
        self.assertEqual(inputs, before)


if __name__ == "__main__":
    unittest.main()
