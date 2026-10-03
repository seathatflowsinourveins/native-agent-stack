"""Prospective binding negatives; no native package is imported."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/engine-nautilus/spy-parity'
LEAF = 'mapping-manifest-six-cases-20261003.json'


def bindings():
    spec = importlib.util.spec_from_file_location('six_bindings_test', SOURCE / 'six_bindings.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ProspectiveBindingTests(unittest.TestCase):
    def test_all_six_are_frozen_policy_cases_and_old_seals_are_retained(self):
        b = bindings()
        m, hashes = b.load_mapping(SOURCE / LEAF)
        self.assertEqual(list(m['cases']), ['one_zero', 'one_stress', 'two_zero', 'two_stress',
                                            'adaptive_stress', 'over_limit'])
        self.assertEqual(m['cases']['two_zero']['target'], '2')
        self.assertEqual(m['cases']['over_limit']['target'], '4')
        self.assertFalse(m['native']['liquidation_enabled'])
        self.assertFalse(m['native']['risk_bypass'])
        self.assertEqual(hashes[LEAF], hashlib.sha256((SOURCE / LEAF).read_bytes()).hexdigest())

    def test_source_guard_removal_and_dependency_hash_drift_are_refused(self):
        b = bindings()
        with tempfile.TemporaryDirectory() as temp:
            s = Path(temp)
            for p in SOURCE.iterdir():
                if p.is_file():
                    shutil.copyfile(p, s / p.name)
            for name in ('run.py', 'margin_policy.py', 'requirements-stress-linux-arm64-py313.lock'):
                original = (s / name).read_bytes()
                (s / name).write_bytes(original + b'\nchanged')
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'source_seal'):
                    b.load_mapping(s / LEAF, source=s)
                (s / name).write_bytes(original)

    def test_symlink_foreign_and_arbitrary_selector_are_refused(self):
        b = bindings()
        with tempfile.TemporaryDirectory() as temp:
            s = Path(temp)
            p = s / LEAF
            p.symlink_to(SOURCE / LEAF)
            with self.assertRaisesRegex(ValueError, 'selection'):
                b.load_mapping(p, source=s)
            with self.assertRaisesRegex(ValueError, 'selection'):
                b.load_mapping(SOURCE / 'mapping-manifest-v2.json')

    def test_new_runtime_case_or_tolerance_policy_cannot_drift(self):
        b = bindings()
        with tempfile.TemporaryDirectory() as temp:
            s = Path(temp)
            for p in SOURCE.iterdir():
                if p.is_file(): shutil.copyfile(p, s / p.name)
            original = json.loads((s / LEAF).read_text())
            mutations = [('case', lambda m: m['cases']['two_zero'].update(target='3')),
                         ('automatic_liquidation', lambda m: m['native'].update(liquidation_enabled=True)),
                         ('bypass', lambda m: m['native'].update(risk_bypass=True)),
                         ('numeric_false', lambda m: m['native'].update(risk_bypass=0)),
                         ('oracle', lambda m: m['frozen'].update(oracle_sha256='0'*64))]
            for label, mutate in mutations:
                m = copy.deepcopy(original); mutate(m)
                (s / LEAF).write_text(json.dumps(m))
                with self.subTest(label=label), self.assertRaises(ValueError):
                    b.load_mapping(s / LEAF, source=s)

    def test_review_must_bind_selected_manifest_every_source_and_exact_argv(self):
        b = bindings()
        m, hashes = b.load_mapping(SOURCE / LEAF)
        argv = ['/harness/run.py', '--case', 'two_zero', '--mapping-manifest', '/harness/'+LEAF]
        review = {'schema': 'spy-six-case-harness-review/1', 'independent_review': True, 'case': 'two_zero',
                  'unresolved_findings': 0, 'reviewed_commit': 'source-head',
                  'completed_utc': '2026-10-03T10:00:00Z',
                  'reviewed_local_source_sha256': hashes,
                  'authorized_run_argvs': [argv], 'authorized_compare_argvs': [['compare']],
                  'mapping_manifest': {'path': LEAF, 'sha256': hashes[LEAF]},
                  'runtime': m['runtime'], 'frozen': m['frozen'],
                  'fence': {'status': 'pass', 'sha256': '1'*64},
                  'source_snapshot_sha256': '2'*64, 'full_wrapper_freeze_sha256': '3'*64}
        b.require_review(review, hashes, m, 'two_zero', 'source-head', '2026-10-03T10:01:00Z', argv)
        for field, value in [('unresolved_findings', 1), ('completed_utc', '2026-10-03T10:02:00Z'),
                             ('reviewed_commit', 'old-head'), ('reviewed_local_source_sha256', {}),
                             ('authorized_run_argvs', []), ('mapping_manifest', {}), ('fence', {})]:
            bad = copy.deepcopy(review); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                b.require_review(bad, hashes, m, 'two_zero', 'source-head', '2026-10-03T10:01:00Z', argv)


if __name__ == '__main__': unittest.main()
