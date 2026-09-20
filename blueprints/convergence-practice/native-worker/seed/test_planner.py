"""Frozen acceptance oracle, visible to the worker; not a held-out benchmark."""
import copy
import unittest

from planner import order_tasks


class PlannerAcceptance(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(order_tasks({}), [])

    def test_one(self):
        self.assertEqual(order_tasks({"build": []}), ["build"])

    def test_dependency_before_alphabetic_name(self):
        self.assertEqual(order_tasks({"a": ["z"], "z": []}), ["z", "a"])

    def test_ready_ties_are_lexicographic(self):
        self.assertEqual(order_tasks({"z": [], "b": [], "a": ["b"]}), ["b", "a", "z"])

    def test_diamond(self):
        self.assertEqual(order_tasks({"ship": ["test", "package"], "test": ["build"],
                                     "package": ["build"], "build": []}),
                         ["build", "package", "test", "ship"])

    def test_duplicate_dependencies(self):
        self.assertEqual(order_tasks({"a": ["z", "z"], "z": []}), ["z", "a"])

    def test_unknown_dependency(self):
        with self.assertRaises(ValueError):
            order_tasks({"build": ["missing"]})

    def test_self_cycle(self):
        with self.assertRaises(ValueError):
            order_tasks({"build": ["build"]})

    def test_multi_node_cycle(self):
        with self.assertRaises(ValueError):
            order_tasks({"a": ["b"], "b": ["a"]})

    def test_cycle_in_disconnected_component(self):
        with self.assertRaises(ValueError):
            order_tasks({"ready": [], "a": ["b"], "b": ["a"]})

    def test_input_unchanged(self):
        data = {"a": ["z", "z"], "z": []}
        before = copy.deepcopy(data)
        order_tasks(data)
        self.assertEqual(data, before)

    def test_mapping_insertion_order_does_not_matter(self):
        left = {"d": ["b", "c"], "b": ["a"], "c": ["a"], "a": []}
        right = dict(reversed(list(left.items())))
        self.assertEqual(order_tasks(left), ["a", "b", "c", "d"])
        self.assertEqual(order_tasks(left), order_tasks(right))


if __name__ == "__main__":
    unittest.main()
