"""Metadata bridge contract; local synthetic inputs, not upstream acceptance."""
import importlib.util
from pathlib import Path
import sys
import unittest
from uuid import UUID

DIRECTORY = Path(__file__).resolve().parents[1] / 'observability/grand-dashboard'
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location('hcom_status', DIRECTORY / 'hcom_status.py')
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)


class HcomStatusTests(unittest.TestCase):
    def test_missing_registered_root_is_unknown_and_native_status_joins_by_id(self):
        one = str(UUID(int=1))
        two = str(UUID(int=2))
        roots = {'canonical_roots': [{'root_id': one, 'lane': 'one', 'name': 'one-abcd'},
                                     {'root_id': two, 'lane': 'two', 'name': 'two-efgh'}]}
        native = [{'session_id': one, 'name': 'one-abcd', 'tool': 'codex', 'status': 'active',
                   'status_context': 'tool:list', 'status_age_seconds': 4, 'unread_count': 1,
                   'directory': '/private', 'description': 'unselected'}]
        rows = {row['identity']: row for row in H.snapshot(native, roots)}
        self.assertEqual(2, len(rows))
        self.assertEqual(('one', 'active', 4, 1),
                         tuple(rows[one][key] for key in ('lane', 'status', 'status_age_seconds', 'unread_count')))
        self.assertEqual('unknown', rows[two]['status'])
        self.assertIsNone(rows[two]['unread_count'])
        self.assertNotIn('directory', rows[one])
        self.assertNotIn('description', rows[one])

    def test_arbitrary_context_and_invalid_numbers_are_not_exported(self):
        rows = H.snapshot([{'session_id': str(UUID(int=1)),
                            'name': 'one-abcd', 'status_context': 'arbitrary private text',
                            'status_age_seconds': True, 'unread_count': -1}])
        self.assertEqual('omitted', rows[0]['status_context'])
        self.assertIsNone(rows[0]['status_age_seconds'])
        self.assertIsNone(rows[0]['unread_count'])
        with self.assertRaises(ValueError):
            H.snapshot({'unexpected': []})


if __name__ == '__main__':
    unittest.main()
