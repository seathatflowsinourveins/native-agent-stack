"""Offline regressions for selected WSL native retrieval evidence."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]/'blueprints/convergence-practice/wsl-retrieval'
SPEC = importlib.util.spec_from_file_location('wsl_retrieval_audit', ROOT/'audit.py')
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RUN_SPEC = importlib.util.spec_from_file_location("wsl_retrieval_runner", ROOT/"run.py")
RUNNER = importlib.util.module_from_spec(RUN_SPEC)
RUN_SPEC.loader.exec_module(RUNNER)


class WslRetrievalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT/'source-receipt.json').read_text())
        self.qmd = json.loads((ROOT/'qmd-receipt.json').read_text())
        self.failed = json.loads((ROOT/'qmd-attempt-1.json').read_text())
        self.inventory = json.loads((ROOT/'install-inventory.json').read_text())

    def audit(self, root=ROOT):
        return MODULE.audit(self.source, self.qmd, self.failed, self.inventory, root)

    def fact(self, receipt, label):
        return next(f for f in receipt['facts'] if f['label'] == label)

    def test_recorded_native_outputs_pass(self):
        self.assertTrue(self.audit()['evidence_consistent'])
        self.assertFalse(self.audit()['semantic_rag_or_client_integration'])
        self.assertFalse(self.audit()['native_acceptance_established'])
        self.assertEqual(self.audit()['status'], 'incomplete_historical_reference')

    def test_every_frozen_input_is_required_in_every_attempt(self):
        for name in ['source', 'qmd', 'failed']:
            for key in list(getattr(self, name)['frozen_inputs']):
                with self.subTest(attempt=name, removed=key):
                    self.setUp()
                    del getattr(self, name)['frozen_inputs'][key]
                    with self.assertRaisesRegex(ValueError, 'required frozen input names'):
                        self.audit()

    def test_same_count_frozen_input_substitution_rejected(self):
        for name in ['source', 'qmd', 'failed']:
            with self.subTest(attempt=name):
                self.setUp()
                inputs = getattr(self, name)['frozen_inputs']
                del inputs['run.py']
                inputs['run-initial.py.txt'] = hashlib.sha256((ROOT/'run-initial.py.txt').read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'required frozen input names'):
                    self.audit()

    def test_same_count_check_substitution_rejected_for_every_passed_check(self):
        for name in ['source', 'qmd', 'failed']:
            for key, value in list(getattr(self, name)['checks'].items()):
                if value is not True:
                    continue
                with self.subTest(attempt=name, replaced=key):
                    self.setUp()
                    checks = getattr(self, name)['checks']
                    del checks[key]
                    checks['unrelated_replacement'] = True
                    with self.assertRaisesRegex(ValueError, 'required check names'):
                        self.audit()

    def test_failed_attempt_cannot_add_an_unrelated_check(self):
        self.failed['checks']['unrelated_extra'] = True
        with self.assertRaisesRegex(ValueError, 'required check names'):
            self.audit()

    def test_archived_runner_and_native_receipts_remain_original_bytes(self):
        originals = {
            'run-initial.py.txt': '50012822197f88a736b1eddfa7f3b81a425a86af183051cc3da06bc0514cb2f0',
            'run-qmd-attempt-2.py.txt': '4cbcceac02158629ca78262aaa826c995c21bbe45fa83481f7c139f16a6c52d2',
            'source-receipt.json': '34e5537e8d39a282d165618b461293f2dcfa08fd8a6f49974775267ed9985c01',
            'qmd-attempt-1.json': '452901227a56f61229b249a56c8b4233faeb3763058610856d399149f81655e6',
            'qmd-receipt.json': 'cad5b3dc802323e5aad8fcdb4ca98f7d1c3e92749b8e891dc32149c70d3f9527',
            'install-receipt.json': '8a3f343e92aa6b0b4ce814ed1b21b56851a37e26f88488cc5ae1119f83063654',
        }
        for name, digest in originals.items():
            with self.subTest(artifact=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)

    def test_incomplete_evidence_does_not_qualify_component_or_adoption(self):
        repo = ROOT.parents[2]
        receipt = json.loads((repo/'evidence/receipts/wsl-retrieval-20260920.json').read_text())
        self.assertEqual(receipt['kind'], 'historical_inventory')
        for component in json.loads((repo/'manifests/stack.json').read_text())['components']:
            self.assertNotIn(receipt['id'], component['evidence_ids'])
        audit = json.loads((repo/'blueprints/token-native-focus/saturation-audit.json').read_text())
        for component in audit['components']:
            self.assertNotIn(receipt['id'], [r['id'] for r in component['functional_evidence']['public_receipts']])
        experiment = json.loads((ROOT/'experiment.json').read_text())
        self.assertEqual(experiment['decision_and_scope']['decision'], 'defer')
        self.assertEqual(experiment['decision_and_scope']['qualification_run_ids'], [])


    def test_lexical_byte_span_mismatch_rejected(self):
        self.fact(self.source, 'rg-positive')['matches'][0]['spans'][0]['start'] += 1
        with self.assertRaises(ValueError):
            self.audit()

    def test_lexical_source_line_mismatch_rejected(self):
        self.fact(self.source, 'rg-positive')['matches'][0]['line_text'] = 'fake line'
        with self.assertRaises(ValueError):
            self.audit()

    def test_ast_range_mismatch_rejected(self):
        self.fact(self.source, 'ast-positive')['matches'][0]['range']['end']['line'] += 1
        with self.assertRaises(ValueError):
            self.audit()

    def test_ast_source_bytes_mismatch_rejected(self):
        self.fact(self.source, 'ast-positive')['matches'][0]['text'] = 'raise ValueError("wrong")'
        with self.assertRaises(ValueError):
            self.audit()

    def test_wrong_named_index_or_collection_rejected(self):
        for uri in ['qmd://wsl-primary/recovery.md?index=other',
                    'qmd://wsl-decoy/recovery.md?index=wsl-retrieval-fixture',
                    'qmd://wsl-primary/other.md?index=wsl-retrieval-fixture']:
            with self.subTest(uri=uri):
                self.setUp()
                self.fact(self.qmd, 'qmd-positive-0')['rows'][0]['file'] = uri
                with self.assertRaises(ValueError):
                    self.audit()

    def test_missing_body_or_wrong_line_rejected(self):
        for field, value in [('body', ''), ('line', 99)]:
            with self.subTest(field=field):
                self.setUp()
                self.fact(self.qmd, 'qmd-positive-1')['rows'][0][field] = value
                with self.assertRaises(ValueError):
                    self.audit()

    def test_bounded_get_cannot_return_extra_lines(self):
        self.fact(self.qmd, 'qmd-bounded-get')['output'] += 'unrelated extra material\n'
        with self.assertRaises(ValueError):
            self.audit()

    def test_error_is_not_successful_absence(self):
        self.fact(self.qmd, 'qmd-negative-0')['exit_code'] = 1
        with self.assertRaises(ValueError):
            self.audit()

    def test_negative_cannot_return_cross_scope_content(self):
        self.fact(self.qmd, 'qmd-negative-1')['rows'] = [{'file': 'qmd://wsl-decoy/other.md'}]
        with self.assertRaises(ValueError):
            self.audit()

    def test_stale_content_after_update_rejected(self):
        self.fact(self.qmd, 'qmd-updated')['rows'][0]['body'] = '# old content\n'
        with self.assertRaises(ValueError):
            self.audit()

    def test_embeddings_or_model_artifact_rejected(self):
        self.qmd['database']['content_vector_rows'] = 1
        with self.assertRaises(ValueError):
            self.audit()
        self.setUp()
        self.inventory['model_files_under_owned_prefix'] = ['model.gguf']
        with self.assertRaises(ValueError):
            self.audit()

    def test_optional_inference_backend_rejected(self):
        self.inventory['installed_optional_llama_backends'] = ['@node-llama-cpp/linux-x64-cuda']
        with self.assertRaises(ValueError):
            self.audit()

    def test_retained_failure_cannot_be_erased(self):
        self.failed['passed'] = True
        with self.assertRaises(ValueError):
            self.audit()

    def test_missing_failed_commands_rejected(self):
        self.failed['facts'] = []
        with self.assertRaises(ValueError):
            self.audit()

    def test_unrelated_failure_cannot_be_relabeled_uri_compatibility(self):
        self.fact(self.failed, 'qmd-positive-0')['rows'] = []
        with self.assertRaises(ValueError):
            self.audit()

    def test_changed_frozen_input_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'leaf'
            shutil.copytree(ROOT, target)
            (target/'seed/planner.py').write_text('pass\n')
            with self.assertRaises(ValueError):
                self.audit(target)

    def test_unknown_usage_or_global_scope_claim_rejected(self):
        self.qmd['whole_task_provider_usage'] = 0
        with self.assertRaises(ValueError):
            self.audit()
        self.setUp()
        self.qmd['global_or_client_changes'] = True
        with self.assertRaises(ValueError):
            self.audit()


class FutureCommandRecordingTests(unittest.TestCase):
    def record(self, directory, response=None, error=None):
        run = Path(directory)
        argv = [run/'owned tools/node', '--index', 'named index', 'aéé.md',
                '--input=' + str(run/'corpus/a file.md')]
        facts = []
        result = {'facts': facts, 'cleanup': {'timed_out_commands': 0}}
        with patch.object(RUNNER.subprocess, 'run', return_value=response, side_effect=error) as invoked:
            try:
                RUNNER.record_command('test', argv, run, {'LANG': 'C.UTF-8'},
                                      {str(run): '<RUN>'}, facts, result)
            except (subprocess.TimeoutExpired, OSError):
                if error is None:
                    raise
            invoked.assert_called_once_with([str(x) for x in argv], cwd=run, env={'LANG': 'C.UTF-8'},
                                             text=True, capture_output=True, timeout=30, check=False)
        retained = json.loads((run/'receipt.partial.json').read_text())
        self.assertEqual(retained['facts'], facts)
        self.assertEqual(facts[0]['argv'], ['<RUN>/owned tools/node', '--index', 'named index',
                                         'aéé.md', '--input=<RUN>/corpus/a file.md'])
        self.assertEqual(facts[0]['cwd'], '<RUN>')
        self.assertNotIn(str(run), json.dumps(facts))
        return retained

    def test_exact_argument_boundaries_and_cwd_retained_for_success_and_failure(self):
        for code in [0, 7]:
            with self.subTest(exit_code=code), tempfile.TemporaryDirectory() as folder:
                response = subprocess.CompletedProcess([], code, 'selected output\n', 'diagnostic\n')
                result = self.record(folder, response=response)
                self.assertEqual(result['facts'][0]['exit_code'], code)
                self.assertEqual((Path(folder)/'test.stdout').read_text(), response.stdout)
                self.assertEqual((Path(folder)/'test.stderr').read_text(), response.stderr)

    def test_timeout_retains_started_command_and_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            error = subprocess.TimeoutExpired(['ignored'], 30, output=b'partial', stderr=b'diagnostic')
            result = self.record(folder, error=error)
            self.assertEqual(result['cleanup']['timed_out_commands'], 1)
            self.assertEqual(result['facts'][0]['failure'], 'timeout')
            self.assertIsNone(result['facts'][0]['exit_code'])
            self.assertEqual((Path(folder)/'test.stdout').read_bytes(), b'partial')

    def test_launch_error_retains_attempted_command(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.record(folder, error=FileNotFoundError('unavailable executable'))
            self.assertEqual(result['facts'][0]['failure'], 'launch_error')
            self.assertIsNone(result['facts'][0]['exit_code'])


if __name__ == '__main__':
    unittest.main()
