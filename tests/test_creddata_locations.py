"""Local report-glue checks, not upstream scanner acceptance or quality scores."""

import itertools
import json
import unittest

from tools.qualification.creddata_locations import ReportError, _unique_keys, locations


def finding(**changes):
    return {"File": "data/repo/file.py", "StartLine": 2, "EndLine": 4,
            "StartColumn": 1, "EndColumn": 5, **changes}


class CredDataLocationTests(unittest.TestCase):
    def test_empty_native_representations_agree(self):
        self.assertEqual(locations(None), locations([]))

    def test_order_does_not_change_projection(self):
        items = [finding(StartLine=n, EndLine=n + 1) for n in (2, 7, 11)]
        expected = locations(items, data_root="/owned/data")
        for permutation in itertools.permutations(items):
            self.assertEqual(expected, locations(list(permutation), data_root="/owned/data"))

    def test_content_rule_and_author_fields_do_not_change_projection(self):
        expected = locations([finding()], data_root="/owned/data")
        for ignored in ("Secret", "Match", "Line", "RuleID", "Author", "Email", "Date"):
            self.assertEqual(expected, locations([finding(**{ignored: object()})], data_root="/owned/data"))

    def test_absolute_and_relative_data_paths_agree(self):
        self.assertEqual(locations([finding()], data_root="/owned/data"),
                         locations([finding(File="/owned/data/repo/file.py")], data_root="/owned/data"))

    def test_multiline_and_distinct_columns_are_preserved(self):
        output = locations([finding(), finding(StartColumn=3)], data_root="/owned/data")
        self.assertEqual(output["unique_location_count"], 2)
        self.assertEqual(output["unique_line_span_count"], 1)
        self.assertEqual(output["locations"][0]["end_line"], 4)
        self.assertFalse(output["quality_scored"])

    def test_rule_duplicate_is_counted_without_losing_position(self):
        output = locations([finding(RuleID="a"), finding(RuleID="b")], data_root="/owned/data")
        self.assertEqual((output["finding_count"], output["duplicate_location_count"]), (2, 1))

    def test_history_commits_keep_same_line_distinct(self):
        output = locations([finding(File="src/a.py", Commit=c * 40) for c in "ab"])
        self.assertEqual(output["unique_location_count"], 2)

    def test_invalid_coordinates_are_rejected(self):
        for change in ({"StartLine": True}, {"StartLine": 0}, {"EndLine": 1},
                       {"StartColumn": -1}, {"EndColumn": "5"},
                       {"EndLine": 2, "StartColumn": 8}):
            with self.subTest(change=change), self.assertRaises(ReportError):
                locations([finding(**change)], data_root="/owned/data")

    def test_missing_fields_invalid_shapes_and_paths_are_rejected(self):
        for report in ({}, [None], [{}], [finding(File="/outside/data/repo/file.py")],
                       [finding(File="data/repo/../file.py")], [finding(File="data//repo/file.py")],
                       [finding(File="data/repo/data/file.py")], [finding(File="data/repo/file.py\n")]):
            with self.subTest(report_type=type(report)), self.assertRaises(ReportError):
                locations(report, data_root="/owned/data")

    def test_history_requires_full_commit_and_relative_path(self):
        for change in ({"Commit": None}, {"Commit": "a" * 7}, {"Commit": "A" * 40},
                       {"Commit": "a" * 40, "File": "/outside/file.py"}):
            with self.subTest(change=change), self.assertRaises(ReportError):
                locations([finding(**change)])

    def test_invalid_roots_are_rejected_even_for_empty_reports(self):
        for root in ("owned/data", "/owned/../data", "/owned/./data", "/owned//data",
                     "/owned/data/", "/owned/data\n", "/owned/not-data", True):
            with self.subTest(root=root), self.assertRaises(ReportError):
                locations([], data_root=root)

    def test_duplicate_json_keys_fail_closed(self):
        with self.assertRaises(ReportError):
            json.loads('[{"File":"a","File":"b"}]', object_pairs_hook=_unique_keys)


if __name__ == "__main__":
    unittest.main()
