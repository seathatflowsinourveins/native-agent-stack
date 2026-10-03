"""Offline regressions for selected WSL native retrieval evidence."""
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
RECORDING_SPEC = importlib.util.spec_from_loader('wsl_retrieval_recording_archive',
        SourceFileLoader('wsl_retrieval_recording_archive', str(ROOT/'run-recording-aid.py.txt')))
RECORDING_ARCHIVE = importlib.util.module_from_spec(RECORDING_SPEC)
RECORDING_SPEC.loader.exec_module(RECORDING_ARCHIVE)


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
            'package-original.json.txt': '7bbf63c5eafd347ae5ae56c684be06ef2589d38f2aab580ca7986ca4122bc6a8',
            'run-recording-aid.py.txt': 'be852ce99501f5bc4567b846b90fb0e91d91de77b0eafbd3b72bb4484a2f7d12',
            'package-lock.json': '5c51ee65cc477f2c1488a38ff5cad1c0a737f81a5b61bbd70d5edc4d15bfc3bb',
            'source-review.json': '9ecd2bf01d7c19248b848dcbd0b77f286b4f1aee775068d7778fabf37721d423',
            'verification.json': '1cb605f4574a662272194625d75689ab5cdcae3e3dbb3ba35afbbd827a474cbe',
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

    def test_original_manifest_is_resolved_without_rewriting_receipt_names(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'leaf'
            shutil.copytree(ROOT, target)
            archive = target/'package-original.json.txt'
            (target/'package.json').write_text('{"private": true}\n')
            try:
                result = self.audit(target)
            except ValueError as exc:
                self.fail('historical manifest must resolve to its preserved archive: '+str(exc))
            self.assertTrue(result['evidence_consistent'])

    def test_changed_original_manifest_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'leaf'
            shutil.copytree(ROOT, target)
            archive = target/'package-original.json.txt'
            archive.write_bytes(archive.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError, 'changed frozen input: package.json'):
                self.audit(target)

    def test_unknown_usage_or_global_scope_claim_rejected(self):
        self.qmd['whole_task_provider_usage'] = 0
        with self.assertRaises(ValueError):
            self.audit()
        self.setUp()
        self.qmd['global_or_client_changes'] = True
        with self.assertRaises(ValueError):
            self.audit()


class ArchivedCommandRecordingTests(unittest.TestCase):
    def record(self, directory, response=None, error=None):
        run = Path(directory)
        argv = [run/'owned tools/node', '--index', 'named index', 'aéé.md',
                '--input=' + str(run/'corpus/a file.md')]
        facts = []
        result = {'facts': facts, 'cleanup': {'timed_out_commands': 0}}
        with patch.object(RECORDING_ARCHIVE.subprocess, 'run', return_value=response, side_effect=error) as invoked:
            try:
                RECORDING_ARCHIVE.record_command('test', argv, run, {'LANG': 'C.UTF-8'},
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


class RetiredRunnerTests(unittest.TestCase):
    def test_old_modes_fail_before_subprocess_or_output_creation(self):
        for mode in ['source', 'qmd']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                run = Path(folder)/'uncreated-output'
                stderr, stdout = io.StringIO(), io.StringIO()
                argv = [str(ROOT/'run.py'), '--mode', mode, '--run-dir', str(run)]
                argv += ['--source', str(ROOT/'seed/planner.py'), '--rg', str(Path(folder)/'unused-rg'),
                         '--ast-grep', str(Path(folder)/'unused-ast-grep'),
                         '--node', str(Path(folder)/'unused-node'), '--package-prefix', folder]
                with patch.object(sys, 'argv', argv), redirect_stderr(stderr), redirect_stdout(stdout), \
                        patch.object(subprocess, 'run', side_effect=AssertionError('retired runner launched a subprocess')) as invoked:
                    try:
                        status = RUNNER.main()
                    except SystemExit as exc:
                        status = exc.code
                self.assertEqual(status, 1)
                self.assertFalse(run.exists(), 'retired mode created its output directory')
                invoked.assert_not_called()
                self.assertIn('retired', stderr.getvalue().lower())
                self.assertEqual(stdout.getvalue(), '')

    def test_offline_cli_rejects_changed_recording_aid_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'leaf'
            shutil.copytree(ROOT, target)
            archive = target/'run-recording-aid.py.txt'
            archive.write_bytes(archive.read_bytes()+b'\n')
            result = subprocess.run([sys.executable, str(target/'audit.py')],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn('changed retirement artifact: run-recording-aid.py.txt', result.stderr)

    def test_offline_cli_checks_retirement_without_qualifying_history(self):
        result = subprocess.run([sys.executable, str(ROOT/'audit.py')],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        assessment = json.loads(result.stdout)
        self.assertFalse(assessment['native_acceptance_established'])
        self.assertEqual(assessment['status'], 'incomplete_historical_reference')
        self.assertIn('current_retirement_assessment', assessment)
        current = assessment['current_retirement_assessment']
        self.assertTrue(current['artifacts_consistent'])
        self.assertEqual(current['active_qmd_advisory_status'], 'unresolved')
        self.assertFalse(current['native_npm_guard_acceptance_established'])

    def test_offline_cli_rejects_restored_install_routes(self):
        for change in ['missing-runtime-guard', 'restored-dependency', 'restored-script']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/'leaf'
                shutil.copytree(ROOT, target)
                manifest = {
                    'name': 'retired-wsl-retrieval', 'version': '1.0.0', 'private': True,
                    'devEngines': {'runtime': {'name': 'retired-wsl-retrieval', 'onFail': 'error'}},
                }
                if change == 'missing-runtime-guard':
                    del manifest['devEngines']
                elif change == 'restored-dependency':
                    manifest['dependencies'] = {'@tobilu/qmd': '2.8.3'}
                else:
                    manifest['scripts'] = {'install': 'node replay.js'}
                (target/'package.json').write_text(json.dumps(manifest)+'\n')
                result = subprocess.run([sys.executable, str(target/'audit.py')],
                                        text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertIn('retirement manifest', result.stderr)


if __name__ == '__main__':
    unittest.main()
