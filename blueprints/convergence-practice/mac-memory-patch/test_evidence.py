import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mac_patch_audit', ROOT/'audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((ROOT/'receipt-attempt-1.json').read_text())
        self.attempts = json.loads((ROOT/'prior-attempts.json').read_text())

    def test_retained_incomplete_attempt(self):
        result = module.audit(self.receipt, self.attempts)
        self.assertTrue(result['evidence_consistent'])
        self.assertFalse(result['functional_acceptance'])

    def test_no_promotion_from_distribution_checks(self):
        self.receipt['passed'] = True
        with self.assertRaises(ValueError):
            module.audit(self.receipt, self.attempts)

    def test_guard_failure_cannot_be_erased(self):
        self.receipt['checks']['sandbox_network_and_write_guards'] = True
        with self.assertRaises(ValueError):
            module.audit(self.receipt, self.attempts)

    def test_gatekeeper_assessment_cannot_be_relabelled(self):
        self.receipt['signature_assessment']['gatekeeper_accepted'] = True
        with self.assertRaises(ValueError):
            module.audit(self.receipt, self.attempts)

    def test_failed_attempt_cannot_be_dropped(self):
        self.attempts['attempts'] = []
        with self.assertRaises(ValueError):
            module.audit(self.receipt, self.attempts)

    def test_changed_frozen_oracle_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in self.receipt['frozen_inputs']:
                (root/name).write_bytes((ROOT/name).read_bytes())
            (root/'oracle.json').write_text('{}')
            with self.assertRaises(ValueError):
                module.audit(self.receipt, self.attempts, root)


class FunctionalFactsTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((ROOT/'receipt.json').read_text())
        self.native = json.loads((ROOT/'native-facts.json').read_text())
        self.oracle = json.loads((ROOT/'oracle-functional.json').read_text())

    def check(self):
        return module.audit_functional(self.receipt, self.native, self.oracle)

    def test_selected_native_facts_satisfy_oracle(self):
        self.assertTrue(self.check()['functional_acceptance'])

    def test_cross_scope_leakage_fails(self):
        fact = next(f for f in self.native['facts'] if f['tool'] == 'memory_query' and f.get('value', {}).get('hits') == [])
        fact['value']['hits'] = [{'path': 'notes/alpha.md'}]
        with self.assertRaises(ValueError):
            self.check()

    def test_unrelated_failure_cannot_count_as_negative_read(self):
        fact = next(f for f in self.native['facts'] if 'error' in f)
        fact['error']['message'] = 'database unavailable'
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_native_call_fails(self):
        self.native['facts'].pop()
        with self.assertRaises(ValueError):
            self.check()

    def test_wrong_restart_body_fails(self):
        fact = next(f for f in self.native['facts'] if f['phase'] == 'candidate-restart' and f['tool'] == 'memory_read_page' and 'value' in f)
        fact['value']['body'] = self.oracle['alpha']['body']
        with self.assertRaises(ValueError):
            self.check()

    def test_forced_cleanup_not_accepted(self):
        self.receipt['cleanup'][0]['forced_termination'] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_capture_population_fails(self):
        self.receipt['candidate_database']['forbidden_population']['observations'] = 1
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
