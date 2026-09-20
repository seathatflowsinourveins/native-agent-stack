"""Offline refusal cases; no native services, password reads or provider calls."""
import base64
import copy
from datetime import datetime
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'blueprints/convergence-practice/offhost-restore'
spec = importlib.util.spec_from_file_location('offhost_verify', HERE / 'verify.py')
verify = importlib.util.module_from_spec(spec); spec.loader.exec_module(verify)


class CiphertextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.expected = [{'path':'config','bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest()}]
        self.bundle = {'schema_version':1,'files':[{'path':'config','base64':base64.b64encode(b'abc').decode()}]}

    def test_exact_decode(self):
        verify.decode_repository(self.bundle, self.expected, self.root/'repository')
        self.assertEqual(verify.repository_manifest(self.root/'repository'), self.expected)

    def test_corrupted_ciphertext_refused_before_write(self):
        self.bundle['files'][0]['base64'] = base64.b64encode(b'bad').decode()
        with self.assertRaises(ValueError): verify.decode_repository(self.bundle, self.expected, self.root/'repository')
        self.assertFalse((self.root/'repository').exists())

    def test_traversal_and_extra_members_refused(self):
        for name in ['../password','/tmp/escape','config/../password','locks/anything']:
            bad = copy.deepcopy(self.bundle); bad['files'][0]['path'] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify.decode_repository(bad, self.expected, self.root/'repository')

    def test_duplicate_and_missing_members_refused(self):
        for entries in [[], self.bundle['files'] * 2]:
            bad = dict(self.bundle, files=entries)
            with self.assertRaises(ValueError): verify.decode_repository(bad, self.expected, self.root/'repository')

    def test_duplicate_manifest_refused(self):
        with self.assertRaises(ValueError): verify.decode_repository(self.bundle, self.expected*2, self.root/'repository')

    def test_existing_destination_refused(self):
        (self.root/'repository').mkdir()
        with self.assertRaises(FileExistsError): verify.decode_repository(self.bundle, self.expected, self.root/'repository')

    def test_symlink_destination_and_extra_files_refused(self):
        (self.root/'outside').mkdir(); (self.root/'repository').symlink_to(self.root/'outside',target_is_directory=True)
        with self.assertRaises(ValueError): verify.decode_repository(self.bundle, self.expected, self.root/'repository')
        (self.root/'repository').unlink()
        verify.decode_repository(self.bundle, self.expected, self.root/'repository')
        (self.root/'repository/secret').write_text('not ciphertext')
        with self.assertRaises(ValueError): verify.repository_manifest(self.root/'repository')

    def test_duplicate_json_keys_refused(self):
        p = self.root/'bad.json'; p.write_text('{"files": [], "files": []}')
        with self.assertRaises(ValueError): verify.load(p)

    def test_checked_in_envelope_if_prepared(self):
        if not (HERE/'repository.json').exists(): self.skipTest('one authorized preparation not executed yet')
        data = verify.load(HERE/'input.json')
        self.assertEqual(verify.digest(HERE/'repository.json'), data['repository_envelope_sha256'])
        expected = verify.load(HERE/'repository-manifest.json')
        verify.decode_repository(verify.load(HERE/'repository.json'),expected,self.root/'repository')
        self.assertEqual(verify.repository_manifest(self.root/'repository'),expected)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name)
        verify.fixture_module().materialize(self.target/'fixture',1)

    def test_unchanged_historical_oracle_matches(self):
        self.assertEqual(verify.verify_restore(self.target,1),verify.load(verify.BASELINE/'attempt-2/expected-1.json'))

    def test_root_mode_and_same_size_byte_change_refused(self):
        (self.target/'fixture').chmod(0o700)
        with self.assertRaises(ValueError): verify.verify_restore(self.target,1)
        (self.target/'fixture').chmod(0o750)
        p=self.target/'fixture/blobs/data.bin'; raw=bytearray(p.read_bytes());raw[123]^=1;p.write_bytes(raw)
        with self.assertRaises(ValueError): verify.verify_restore(self.target,1)

    def test_extra_parent_output_refused(self):
        (self.target/'unexpected').write_text('')
        with self.assertRaises(ValueError): verify.verify_restore(self.target,1)

    def test_sandbox_keeps_keys_and_repo_read_only_without_network(self):
        spec = importlib.util.spec_from_file_location('offhost_run', HERE/'run.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'verify':verify}): spec.loader.exec_module(module)
        command=module.sandbox_command(Path('/binary'),Path('/repo'),Path('/key'),Path('/out'),Path('/probe'),['check','--read-data'])
        self.assertIn('--unshare-net',command);self.assertIn('--clearenv',command)
        for source in ['/repo','/key']:
            self.assertEqual(command[command.index(source)-1],'--ro-bind')
        self.assertIn('--no-lock',command)
        self.assertIn('PWD',command)
        self.assertNotIn(str(HERE), ' '.join(command))
        self.assertEqual(module.sanitize('snapshot by privateuser@synthetic-wsl-restore'), 'snapshot by $SOURCE_USER@synthetic-wsl-restore')

    def test_workflow_is_manual_only_and_uploads_reports_not_root(self):
        text=(ROOT/'.github/workflows/native-offhost-restore.yml').read_text()
        self.assertIn('  workflow_dispatch:',text)
        self.assertNotIn('  push:',text);self.assertNotIn('pull_request',text)
        self.assertIn('path: ${{ env.FOUNDATION_RESTORE_ROOT }}/reports/',text)
        self.assertIn('secrets.FOUNDATION_RESTORE_FIXTURE_20260920',text)
        self.assertNotIn('bypass',text)

    def test_actual_recovery_workspace_keeps_negative_key_separate_from_every_command_output(self):
        # Reproduce the hosted setup with the exact encrypted input, no model,
        # correct password or native operation. The old wrong-password output
        # mkdir collided with the regular negative-key file here.
        spec = importlib.util.spec_from_file_location('offhost_run', HERE/'run.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'verify':verify}): spec.loader.exec_module(module)
        expected = verify.load(HERE/'repository-manifest.json')
        wrong = module.initialize_recovery(self.target, verify.load(HERE/'repository.json'), expected)
        for label in ['wrong-password','check-read-data','restore-1','restore-2']:
            output = module.create_command_output(self.target,label)
            self.assertTrue(output.is_dir())
            self.assertNotEqual(wrong,output)
        self.assertTrue(wrong.is_file())
        self.assertEqual(wrong.stat().st_mode & 0o777,0o600)
        self.assertEqual(verify.repository_manifest(self.target/'repository'),expected)


class UpstreamResultGuardTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('offhost_upstream',HERE/'upstream_tests.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'verify':verify}):spec.loader.exec_module(module)
        return module

    def test_only_exact_passed_upstream_tests_are_accepted(self):
        selected=[{'package':'upstream/package','name':'TestNative'}]
        event={'Package':'upstream/package','Test':'TestNative','Action':'pass'}
        self.assertEqual(self.module().check_test_events(json.dumps(event),selected)[0]['status'],'pass')
        for action in ['skip','fail']:
            with self.subTest(action=action),self.assertRaises(ValueError):
                self.module().check_test_events(json.dumps(dict(event,Action=action)),selected)
        with self.assertRaises(ValueError):self.module().check_test_events('',selected)
        with self.assertRaises(ValueError):self.module().check_test_events(json.dumps(event)+'\n'+json.dumps(event),selected)

    def test_launch_failures_retain_attempted_command_and_empty_streams(self):
        for error in [FileNotFoundError(errno.ENOENT,'missing executable'),
                      PermissionError(errno.EACCES,'executable permission denied')]:
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source=root/'source';source.mkdir();reports=root/'reports';reports.mkdir()
                module=self.module()
                argv=['upstream_tests.py','--source',str(source),'--reports',str(reports)]
                with patch.object(sys,'argv',argv), patch.object(module.subprocess,'run',side_effect=error), patch('builtins.print'):
                    self.assertTrue(module.main())
                report=json.loads((reports/'upstream-tests.json').read_text())
                self.assertEqual(report['status'],'failed')
                self.assertEqual(len(report['commands']),1)
                command=report['commands'][0]
                self.assertEqual(command['argv'],['git','rev-parse','HEAD'])
                self.assertEqual(command['cwd'],'$UPSTREAM_SOURCE')
                self.assertFalse(command['launched']);self.assertFalse(command['timeout'])
                self.assertIsNone(command['exit_code'])
                self.assertEqual(command['launch_error']['type'],type(error).__name__)
                self.assertEqual(command['launch_error']['errno'],error.errno)
                self.assertGreaterEqual(datetime.fromisoformat(command['finished_at_utc']),datetime.fromisoformat(command['started_at_utc']))
                self.assertGreaterEqual(command['seconds'],0)
                for name in ['stdout','stderr']:
                    self.assertEqual((reports/command[name]['path']).read_bytes(),b'')
                    self.assertEqual(command[name]['sha256'],hashlib.sha256(b'').hexdigest())


if __name__ == '__main__': unittest.main()
