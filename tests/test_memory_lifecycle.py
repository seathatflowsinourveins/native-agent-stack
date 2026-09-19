import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'blueprints/us-equities/memory-lifecycle'
spec = importlib.util.spec_from_file_location('memory_lifecycle_analyze', FOLDER / 'analyze.py')
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = json.loads((FOLDER / 'outcomes.json').read_text())

    def test_retained_native_outcomes(self):
        self.assertTrue(analyze.summarize(self.outcomes)['passed'])

    def test_native_failure_is_not_empty_retrieval(self):
        self.outcomes['alpha_search_beta'] = {'error': {'code': -32603, 'message': 'database unavailable'}}
        with self.assertRaises(ValueError):
            analyze.summarize(self.outcomes)

    def test_mcp_tool_error_is_not_empty_retrieval(self):
        self.outcomes['alpha_search_beta']['result']['isError'] = True
        with self.assertRaises(ValueError):
            analyze.summarize(self.outcomes)

    def test_wrong_historical_version_fails(self):
        self.outcomes['old_as_of'] = copy.deepcopy(self.outcomes['new_now'])
        value = json.loads(self.outcomes['old_as_of']['result']['content'][0]['text'])
        value['streams_active'] = ['fts']
        self.outcomes['old_as_of']['result']['content'][0]['text'] = json.dumps(value)
        self.assertFalse(analyze.summarize(self.outcomes)['passed'])

    def test_project_cross_contamination_fails(self):
        self.outcomes['alpha_search_beta'] = copy.deepcopy(self.outcomes['future_default'])
        self.assertFalse(analyze.summarize(self.outcomes)['passed'])

    def test_unexpected_success_of_negative_case_fails(self):
        self.outcomes['missing_scope'] = copy.deepcopy(self.outcomes['alpha_read'])
        with self.assertRaises(ValueError):
            analyze.summarize(self.outcomes)

    def test_missing_call_fails(self):
        del self.outcomes['deleted_as_of']
        with self.assertRaises(ValueError):
            analyze.summarize(self.outcomes)


if __name__ == '__main__':
    unittest.main()
