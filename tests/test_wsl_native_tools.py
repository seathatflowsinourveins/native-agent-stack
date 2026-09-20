"""Offline failure guards; these checks never run or install native tools."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'blueprints/convergence-practice/wsl-native-tools'


def load(name):
    spec = importlib.util.spec_from_file_location('wsl_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALL = load('install')
RUN = load('run')


class ArchiveChecks(unittest.TestCase):
    def test_modified_asset_rejected(self):
        expected = hashlib.sha256(b'publisher bytes').hexdigest()
        INSTALL.check_digest(b'publisher bytes', expected)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            INSTALL.check_digest(b'changed bytes', expected)

    def test_checksum_requires_exact_unique_filename_and_digest(self):
        expected = 'a' * 64
        INSTALL.check_publisher_checksum(expected + '  asset.tar.gz\n', 'asset.tar.gz', expected)
        for text in [expected + '  other.tar.gz', 'b' * 64 + '  asset.tar.gz',
                     (expected + '  asset.tar.gz\n') * 2, '']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                INSTALL.check_publisher_checksum(text, 'asset.tar.gz', expected)

    def test_archive_rejects_path_escape_links_and_special_files(self):
        for name, kind in [('../escaped', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('nested/../../escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE),
                           ('hardlink', tarfile.LNKTYPE), ('pipe', tarfile.FIFOTYPE)]:
            with self.subTest(name=name, kind=kind):
                content = io.BytesIO()
                with tarfile.open(fileobj=content, mode='w') as archive:
                    member = tarfile.TarInfo(name); member.type = kind; archive.addfile(member)
                content.seek(0)
                with tarfile.open(fileobj=content) as archive, self.assertRaisesRegex(ValueError, 'Unsafe'):
                    INSTALL.checked_members(archive)

    def test_archive_accepts_regular_nested_files(self):
        content = io.BytesIO()
        with tarfile.open(fileobj=content, mode='w') as archive:
            member = tarfile.TarInfo('tool/'); member.type = tarfile.DIRTYPE; archive.addfile(member)
            member = tarfile.TarInfo('tool/wt'); archive.addfile(member)
        content.seek(0)
        with tarfile.open(fileobj=content) as archive:
            self.assertEqual([m.name for m in INSTALL.checked_members(archive)], ['tool', 'tool/wt'])


class QualificationChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        platform_patch = patch.object(RUN.platform, 'platform', return_value='offline test platform')
        platform_patch.start()
        self.addCleanup(platform_patch.stop)
        self.positive = [{'RuleID': 'github-pat', 'Secret': 'REDACTED', 'Match': 'REDACTED'}]

    def release_fixture(self):
        data = b'fake executable, never run'
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            member = tarfile.TarInfo('gitleaks'); member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        downloads = self.root / 'downloads'; downloads.mkdir()
        (downloads / 'release.tar').write_bytes(stream.getvalue())
        (self.root / 'gitleaks').write_bytes(data)
        pin = {'name': 'gitleaks', 'version': '8.30.1', 'source_commit': 'a' * 40, 'license': 'MIT',
               'archive': {'name': 'release.tar', 'sha256': RUN.sha(stream.getvalue())},
               'executable': 'gitleaks'}
        installed = {key: pin[key] for key in ['name', 'version', 'source_commit', 'license']}
        installed.update(archive_sha256=pin['archive']['sha256'], binary='gitleaks', binary_sha256=RUN.sha(data))
        return {'components': [pin]}, {'components': [installed]}

    def test_oracle_accepts_redacted_positive_and_clean_negative(self):
        RUN.validate_reports(self.positive, [], RUN.inert_token(), ['redacted scanner log'])

    def test_oracle_rejects_missing_duplicate_or_wrong_rule(self):
        for value in [[], self.positive * 2, [{'RuleID': 'other', 'Secret': 'REDACTED'}]]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'exactly one'):
                RUN.validate_reports(value, [], RUN.inert_token(), [])

    def test_oracle_rejects_unredacted_report_and_log(self):
        for where in ['Secret', 'Match', 'log']:
            positive = copy.deepcopy(self.positive)
            logs = []
            if where == 'log':
                logs.append(RUN.inert_token())
            else:
                positive[0][where] = RUN.inert_token()
            with self.subTest(where=where), self.assertRaisesRegex(ValueError, 'redacted'):
                RUN.validate_reports(positive, [], RUN.inert_token(), logs)

    def test_clean_false_positive_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Clean fixture'):
            RUN.validate_reports(self.positive, self.positive, RUN.inert_token(), [])

    def test_worktree_oracle_rejects_extra_missing_and_outside_paths(self):
        expected = {'main': self.root / 'repo'}
        good = {'schema': 2, 'collected': {'ci': False, 'summary': False},
                'items': [{'branch': 'main', 'worktree': {'path': str(expected['main'])}}]}
        RUN.validate_listing(good, expected)
        for kind in ['extra', 'missing', 'outside', 'model']:
            value = copy.deepcopy(good)
            if kind == 'extra': value['items'].append({'branch': 'unowned'})
            elif kind == 'missing': value['items'] = []
            elif kind == 'outside': value['items'][0]['worktree']['path'] = str(self.root / 'unowned')
            else: value['collected']['summary'] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                RUN.validate_listing(value, expected)

    def test_dirty_data_must_survive_unchanged(self):
        (self.root / 'fixture.txt').write_bytes(RUN.DIRTY)
        (self.root / 'untracked.txt').write_bytes(RUN.UNTRACKED)
        RUN.verify_dirty(self.root)
        (self.root / 'fixture.txt').write_bytes(RUN.CLEAN)
        with self.assertRaisesRegex(ValueError, 'changed synthetic data'):
            RUN.verify_dirty(self.root)
        self.assertEqual((self.root / 'untracked.txt').read_bytes(), RUN.UNTRACKED)

    def test_reuse_preserves_existing_directory_before_any_command(self):
        work = self.root / 'existing'; work.mkdir(); marker = work / 'keep'; marker.write_text('unchanged')
        with patch.object(RUN.subprocess, 'run') as native, self.assertRaises(FileExistsError):
            RUN.qualification(self.root, work)
        native.assert_not_called(); self.assertEqual(marker.read_text(), 'unchanged')

    def test_run_outside_private_prefix_is_rejected(self):
        with patch.object(RUN.subprocess, 'run') as native, self.assertRaisesRegex(ValueError, 'direct child'):
            RUN.qualification(self.root, self.root / 'nested' / 'run')
        native.assert_not_called(); self.assertFalse((self.root / 'nested').exists())

    def test_native_failure_retains_exit_and_failed_receipt(self):
        binaries = []
        for name in ['gitleaks', 'worktrunk']:
            (self.root / name).write_bytes(b'fake unexecuted bytes')
            binaries.append({'name': name, 'binary': name, 'binary_sha256': RUN.sha(b'fake unexecuted bytes')})
        (self.root / 'installation.json').write_text(json.dumps({'components': binaries}))
        result = subprocess.CompletedProcess(['git', '--version'], 17, b'', b'synthetic failure\n')
        with patch.object(RUN, 'pinned_binaries', return_value={'gitleaks': 'unused', 'worktrunk': 'unused'}), \
                patch.object(RUN.subprocess, 'run', return_value=result), self.assertRaisesRegex(ValueError, 'exit 17'):
            RUN.qualification(self.root, self.root / 'attempt')
        receipt = json.loads((self.root / 'attempt/receipt.json').read_text())
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['commands'][0]['exit_code'], 17)
        self.assertEqual((self.root / 'attempt/logs/git-version.stderr').read_bytes(), b'synthetic failure\n')

    def test_changed_binary_fails_before_native_execution(self):
        pins, installed = self.release_fixture()
        (self.root / 'gitleaks').write_bytes(b'changed')
        with patch.object(RUN.subprocess, 'run') as native, self.assertRaisesRegex(ValueError, 'changed'):
            RUN.pinned_binaries(self.root, pins, installed)
        native.assert_not_called()

    def test_release_identity_rejects_changed_or_duplicate_components(self):
        pins, installed = self.release_fixture()
        self.assertEqual(RUN.pinned_binaries(self.root, pins, installed), {'gitleaks': self.root / 'gitleaks'})
        for field in ['name', 'version', 'source_commit', 'archive_sha256', 'license', 'duplicate']:
            changed = copy.deepcopy(installed)
            if field == 'duplicate': changed['components'] *= 2
            else: changed['components'][0][field] = 'wrong identity'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identit'):
                RUN.pinned_binaries(self.root, pins, changed)

    def test_modified_manifest_cannot_reauthorize_changed_binary(self):
        pins, installed = self.release_fixture()
        (self.root / 'gitleaks').write_bytes(b'changed')
        installed['components'][0]['binary_sha256'] = RUN.sha(b'changed')
        with self.assertRaisesRegex(ValueError, 'pinned release'):
            RUN.pinned_binaries(self.root, pins, installed)

    def test_retained_archive_must_match_frozen_pin(self):
        pins, installed = self.release_fixture()
        (self.root / 'downloads/release.tar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'archive.*changed'):
            RUN.pinned_binaries(self.root, pins, installed)

    def test_native_version_must_match_pins_before_qualification(self):
        pins = json.loads((HERE / 'pins.json').read_text())
        versions = {'gitleaks': '8.30.1', 'worktrunk': 'wt v0.78.0'}
        RUN.verify_versions(versions, pins)
        for name in versions:
            changed = dict(versions); changed[name] = 'wrong version'
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'version'):
                RUN.verify_versions(changed, pins)

    def test_timeout_retains_redacted_partial_streams_and_null_exit(self):
        (self.root / 'installation.json').write_text('{}')
        timeout = subprocess.TimeoutExpired(['git', '--version'], 60,
                                            output=('partial ' + RUN.inert_token()).encode(), stderr=b'partial error')
        with patch.object(RUN, 'pinned_binaries', return_value={'gitleaks': 'unused', 'worktrunk': 'unused'}), \
                patch.object(RUN.subprocess, 'run', side_effect=timeout), self.assertRaisesRegex(ValueError, 'timed out'):
            RUN.qualification(self.root, self.root / 'attempt')
        receipt = json.loads((self.root / 'attempt/receipt.json').read_text())
        command = receipt['commands'][0]
        self.assertEqual(receipt['status'], 'failed')
        self.assertIsNone(command['exit_code']); self.assertTrue(command['timed_out'])
        self.assertEqual((self.root / 'attempt/logs/git-version.stdout').read_bytes(), b'partial REDACTED')
        self.assertEqual((self.root / 'attempt/logs/git-version.stderr').read_bytes(), b'partial error')

    def test_child_environment_excludes_inherited_tokens_and_configuration(self):
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'inert sentinel', 'GITLEAKS_CONFIG': 'unowned',
                                      'WORKTRUNK_CONFIG_PATH': 'unowned'}):
            env = RUN.environment(self.root)
        self.assertNotIn('GITHUB_TOKEN', env)
        self.assertNotIn('GITLEAKS_CONFIG', env)
        self.assertEqual(env['WORKTRUNK_CONFIG_PATH'], str(self.root / 'user.toml'))
        self.assertEqual(env['GIT_CONFIG_VALUE_0'], '/dev/null')


if __name__ == '__main__':
    unittest.main()
