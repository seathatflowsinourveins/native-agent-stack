"""Evidence regressions only: no native process, network, or production state."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'blueprints/convergence-practice/wsl-memory-maintenance'
SPEC = importlib.util.spec_from_file_location('wsl_memory_audit', ROOT/'audit.py')
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WslMemoryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((ROOT/'receipt.json').read_text())
        self.native = json.loads((ROOT/'native-facts.json').read_text())
        self.oracle = json.loads((ROOT/'oracle.json').read_text())

    def audit(self, root=ROOT):
        return MODULE.audit(self.receipt, self.native, self.oracle, root)

    def test_recorded_native_trial_consistent(self):
        self.assertTrue(self.audit()['synthetic_restart_backup_restore_accepted'])
        self.assertFalse(self.audit()['production_or_client_acceptance'])

    def test_cross_scope_leakage_rejected(self):
        fact = next(f for f in self.native['facts'] if f['tool'] == 'memory_query' and f.get('value', {}).get('hits') == [])
        fact['value']['hits'] = [{'path': 'notes/alpha.md'}]
        with self.assertRaises(ValueError):
            self.audit()

    def test_database_error_not_accepted_as_negative(self):
        fact = next(f for f in self.native['facts'] if 'error' in f)
        fact['error']['message'] = 'database unavailable'
        with self.assertRaises(ValueError):
            self.audit()

    def test_error_not_accepted_as_empty_query(self):
        fact = next(f for f in self.native['facts'] if f.get('value', {}).get('hits') == [])
        fact['error'] = {'code': -32603, 'message': 'failed'}
        with self.assertRaises(ValueError):
            self.audit()

    def test_wrong_restore_body_rejected(self):
        fact = next(f for f in self.native['facts'] if f['phase'] == 'restored' and f['tool'] == 'memory_read_page' and 'value' in f)
        fact['value']['body'] = 'wrong restored content'
        with self.assertRaises(ValueError):
            self.audit()

    def test_missing_call_rejected(self):
        self.native['facts'].pop()
        with self.assertRaises(ValueError):
            self.audit()

    def test_duplicate_call_cannot_replace_missing_call(self):
        self.native['facts'][-1] = self.native['facts'][0]
        with self.assertRaises(ValueError):
            self.audit()

    def test_capture_or_embeddings_rejected(self):
        for key in ['database_after_restart', 'backup_database', 'restored_database', 'database_final']:
            with self.subTest(phase=key):
                self.setUp()
                self.receipt[key]['forbidden_population']['page_embeddings'] = 1
                with self.assertRaises(ValueError):
                    self.audit()

    def test_failed_backup_not_accepted(self):
        self.receipt['backup']['exit_code'] = 1
        with self.assertRaises(ValueError):
            self.audit()

    def test_blocked_restore_not_accepted_as_round_trip(self):
        self.receipt['restore'] = {'status': 'blocked_by_native_sibling_process_guard', 'exit_code': 1}
        with self.assertRaises(ValueError):
            self.audit()

    def test_missing_cleanup_rejected(self):
        self.receipt['cleanup'].pop()
        with self.assertRaises(ValueError):
            self.audit()

    def test_forced_cleanup_rejected(self):
        self.receipt['cleanup'][0]['forced_termination'] = True
        with self.assertRaises(ValueError):
            self.audit()

    def test_production_or_confinement_claim_rejected(self):
        for key in ['production_state_opened', 'production_promoted', 'client_registration_changed', 'os_confinement_established']:
            with self.subTest(claim=key):
                self.setUp()
                self.receipt[key] = True
                with self.assertRaises(ValueError):
                    self.audit()

    def test_unknown_whole_task_usage_cannot_be_zeroed(self):
        self.receipt['whole_task_provider_usage'] = 0
        with self.assertRaises(ValueError):
            self.audit()

    def test_changed_frozen_oracle_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in self.receipt['frozen_inputs']:
                shutil.copyfile(ROOT/name, target/name)
            (target/'oracle.json').write_text('{}')
            with self.assertRaises(ValueError):
                self.audit(target)


if __name__ == '__main__':
    unittest.main()
