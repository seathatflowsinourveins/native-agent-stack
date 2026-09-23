"""Offline evidence/secret/ownership guards; no native application is started."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'blueprints/convergence-practice/offhost-app-state/run.py'
spec = importlib.util.spec_from_file_location('offhost_app_state', PATH)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class EvidenceGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='native-offhost-app.', dir='/tmp')
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def test_fixture_independent_dense_and_sparse_values(self):
        fixture = app.load(PATH.parent / 'qdrant-oracle.json')
        actual = app.canonical_points(fixture['points'])
        self.assertEqual([p['id'] for p in actual], list(range(1, 11)))
        self.assertEqual(actual[8]['vector']['sparse-text'], {'indices': [12, 66], 'values': [.5, .5]})
        dense = sorted(actual[:8], key=lambda p: p['vector'][''][0], reverse=True)
        self.assertEqual([p['id'] for p in dense], fixture['queries']['dense']['ids'])
        self.assertEqual([p['vector'][''][0] for p in dense], [app.f32(x) for x in fixture['queries']['dense']['scores']])

    def test_duplicate_point_refused(self):
        with self.assertRaises(ValueError): app.canonical_points([{'id': 1, 'vector': [1]}, {'id': 1, 'vector': [1]}])

    def test_malformed_sparse_vector_refused(self):
        with self.assertRaises(ValueError):
            app.canonical_points([{'id': 1, 'vector': {'sparse': {'indices': [1, 2], 'values': [1]}}}])

    def test_rust_missing_ignored_duplicate_and_sparse_skip_refused(self):
        good = 'test a::test ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured\n'
        app.check_rust_tests(good, ['a::test'])
        for text in ['', good.replace('... ok', '... ignored'), good + 'test a::test ... ok\n',
                     good + 'skipping restore_round_trips_a_real_gnu_sparse_sqlite_snapshot: '
                     'GNU tar with --sparse not available on PATH\n']:
            with self.subTest(text=text), self.assertRaises(ValueError): app.check_rust_tests(text, ['a::test'])

    def test_pytest_requires_all_four_native_cases_and_no_skip(self):
        cases = ''.join(f'<testcase name="{name}[{value}]"/>' for name in
                        ('test_collection_snapshot_operations', 'test_full_snapshot_operations') for value in ('False', 'True'))
        path = self.root / 'tests.xml'; path.write_text('<testsuites><testsuite>' + cases + '</testsuite></testsuites>')
        app.check_pytest(path)
        path.write_text(path.read_text().replace('/>', '><skipped/></testcase>', 1))
        with self.assertRaises(ValueError): app.check_pytest(path)

    def test_owned_root_refuses_outside_prefix_and_symlink(self):
        self.assertEqual(app.owned_root(self.root), self.root)
        with self.assertRaises(ValueError): app.owned_root(self.root.parent)
        link = self.root / 'alias'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): app.owned_root(link)

    def test_owned_root_refuses_a_symlinked_parent_that_resolves_to_tmp(self):
        # Round-2 security review: /tmp/x -> /tmp lets path.parent.resolve()
        # equal Path('/tmp').resolve() even though path.parent is NOT
        # literally /tmp -- and /tmp/x can be repointed elsewhere after this
        # check and before the root is actually used (TOCTOU). Must fail on
        # c1f30cb (path.parent.resolve() != Path('/tmp').resolve()) and pass
        # now that path.parent must literally be /tmp or its resolved form.
        alias = Path('/tmp') / ('native-offhost-app-alias.' + str(os.getpid()))
        self.addCleanup(lambda: alias.unlink() if alias.is_symlink() else None)
        alias.symlink_to('/tmp')
        victim = alias / self.root.name
        with self.assertRaises(ValueError):
            app.owned_root(victim)

    def test_password_requires_regular_0600_file(self):
        trial = app.Trial(self.root, 'test'); private = self.root / 'private'; private.mkdir()
        path = private / 'password'; path.write_text('public-unit-test-fixture\n'); path.chmod(0o644)
        with self.assertRaises(ValueError): trial.password()
        path.chmod(0o600); self.assertEqual(trial.password(), path)
        path.unlink(); path.symlink_to(self.root / 'plan.json')
        with self.assertRaises(ValueError): trial.password()

    def test_unknown_temporary_bearer_is_redacted_and_excluded(self):
        value = 'a' * 64
        text = 'Authorization: Bearer ' + value
        self.assertNotIn(value, app.public_auth_filter(text))
        raw = self.root / 'raw'; raw.mkdir(); (raw / 'native.stderr').write_text(text)
        with self.assertRaises(ValueError): app.proof_files(raw, ['unrelated-restic-password'])

    def test_known_password_never_enters_encrypted_proof(self):
        raw = self.root / 'raw'; raw.mkdir(); (raw / 'native.stdout').write_text('accidental private-fixture-key value')
        with self.assertRaises(ValueError): app.proof_files(raw, ['private-fixture-key'])

    def test_nested_auth_or_symlink_not_selected_as_proof(self):
        raw = self.root / 'raw'; raw.mkdir(); (raw / 'data').mkdir()
        with self.assertRaises(ValueError): app.proof_files(raw, [])
        (raw / 'data').rmdir(); (raw / 'native.stdout').symlink_to('/etc/hostname')
        with self.assertRaises(ValueError): app.proof_files(raw, [])
        (raw / 'native.stdout').unlink(); (raw / 'auth.json').write_text('{}')
        with self.assertRaises(ValueError): app.proof_files(raw, [])

    def test_command_launch_failure_is_durable(self):
        trial = app.Trial(self.root, 'test')
        with self.assertRaises(RuntimeError): trial.call('missing', [self.root / 'nonexistent-native-tool'])
        record = app.load(self.root / 'reports/test.json')['commands'][0]
        self.assertFalse(record['launched']); self.assertIsNone(record['exit_code'])
        self.assertEqual(record['launch_error']['type'], 'FileNotFoundError')
        self.assertEqual(record['argv'], ['$OWNED_RUN/nonexistent-native-tool'])
        self.assertEqual(record['stdout']['raw_bytes'], 0)
        self.assertIn('finished_at_utc', record)

    def test_command_nonzero_retains_output(self):
        trial = app.Trial(self.root, 'test')
        with self.assertRaises(RuntimeError):
            trial.call('failed', ['/usr/bin/python3', '-c', 'print("retained failure"); raise SystemExit(7)'])
        record = app.load(self.root / 'reports/test.json')['commands'][0]
        self.assertEqual(record['exit_code'], 7)
        self.assertEqual((self.root / 'reports/failed.stdout').read_text(), 'retained failure\n')

    def test_command_timeout_retains_output_and_stops_owned_group(self):
        trial = app.Trial(self.root, 'test')
        with self.assertRaises(RuntimeError):
            trial.call('timed', ['/usr/bin/python3', '-c', 'import time; print("before timeout", flush=True); time.sleep(3)'], timeout=.1)
        record = app.load(self.root / 'reports/test.json')['commands'][0]
        self.assertTrue(record['timed_out']); self.assertTrue(record['owned_process_group_signals_sent'])
        self.assertIn('before timeout', (self.root / 'reports/timed.stdout').read_text())

    def test_cleanup_excludes_exports_but_removes_password_and_state(self):
        trial = app.Trial(self.root, 'cleanup')
        (self.root / 'private').mkdir(); (self.root / 'private/password').write_text('test')
        (self.root / 'payload').mkdir(); (self.root / 'payload/db').write_text('synthetic')
        (self.root / 'encrypted-proof').mkdir(); (self.root / 'encrypted-proof/repository.json').write_text('{}')
        app.cleanup(trial)
        self.assertFalse((self.root / 'private/password').exists())
        self.assertFalse((self.root / 'payload').exists())
        self.assertTrue((self.root / 'encrypted-proof/repository.json').exists())

    def transfer(self):
        folder = self.root / 'incoming'; folder.mkdir()
        (folder / 'manifest.json').write_text('[]'); (folder / 'repository.json').write_text('{}')
        identity = {'head_sha': 'a' * 40, 'run_id': '123', 'run_attempt': '1', 'job': 'destination',
                    'boot_id_sha256': 'b' * 64, 'runner_environment': 'github-hosted'}
        source = {'status': 'source-prepared-only', 'plan_sha256': 'plan',
                  'identity': identity | {'job': 'source', 'boot_id_sha256': 'c' * 64},
                  'files': [{'name': 'memory.tar.gz'}, {'name': 'qdrant.snapshot'}],
                  'manifest_sha256': app.sha(folder / 'manifest.json'), 'envelope_sha256': app.sha(folder / 'repository.json')}
        app.save(folder / 'source.json', source)
        return folder, identity, source

    def test_transfer_identity_requires_distinct_boot_and_same_run_head_attempt(self):
        folder, identity, source = self.transfer()
        app.validate_source(folder, identity, 'plan', app.sha(folder / 'source.json'))
        for key, value in [('boot_id_sha256', source['identity']['boot_id_sha256']), ('head_sha', 'other'),
                           ('run_id', 'other'), ('run_attempt', '2'), ('job', 'source')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                app.validate_source(folder, identity | {key: value}, 'plan', app.sha(folder / 'source.json'))

    def test_transfer_platform_hash_changed_ciphertext_and_extra_members_refused(self):
        folder, identity, _ = self.transfer()
        with self.assertRaises(ValueError): app.validate_source(folder, identity, 'plan', 'wrong')
        (folder / 'repository.json').write_text('changed ciphertext')
        with self.assertRaises(ValueError): app.validate_source(folder, identity, 'plan', app.sha(folder / 'source.json'))
        (folder / 'unexpected').write_text('extra')
        with self.assertRaises(ValueError): app.validate_source(folder, identity, 'plan', app.sha(folder / 'source.json'))

    def test_transfer_symlink_refused_even_with_same_content(self):
        folder, identity, _ = self.transfer()
        target = self.root / 'ciphertext'; (folder / 'repository.json').rename(target)
        (folder / 'repository.json').symlink_to(target)
        with self.assertRaises(ValueError): app.validate_source(folder, identity, 'plan', app.sha(folder / 'source.json'))


if __name__ == '__main__': unittest.main()
