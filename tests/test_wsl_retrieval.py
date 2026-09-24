"""Offline regressions for selected WSL native retrieval evidence."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'blueprints/convergence-practice/wsl-retrieval'
SPEC = importlib.util.spec_from_file_location('wsl_retrieval_audit', ROOT/'audit.py')
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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


if __name__ == '__main__':
    unittest.main()
