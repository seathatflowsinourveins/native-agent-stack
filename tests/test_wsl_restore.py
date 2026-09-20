"""Offline oracle checks; the separate native receipt records actual restic execution."""
import importlib.util
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

PATH = Path(__file__).resolve().parents[1] / 'blueprints/convergence-practice/wsl-restore/fixture.py'
SPEC = importlib.util.spec_from_file_location('wsl_restore_fixture', PATH)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class RestoreOracleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'fixture'
        fixture.materialize(self.root, 1)

    def test_both_frozen_snapshots_cover_transition_and_modes(self):
        fixture.assert_restored(self.root, 1)
        fixture.materialize(self.root, 2)
        fixture.assert_restored(self.root, 2)
        self.assertFalse((self.root / 'state/deleted.txt').exists())
        self.assertTrue((self.root / 'state/added.txt').exists())
        self.assertEqual((self.root / 'blobs/data.bin').stat().st_size, 1048576)

    def test_same_size_byte_corruption_fails(self):
        p = self.root / 'blobs/data.bin'
        raw = bytearray(p.read_bytes()); raw[len(raw)//2] ^= 1; p.write_bytes(raw)
        with self.assertRaises(ValueError): fixture.assert_restored(self.root, 1)

    def test_missing_empty_directory_fails(self):
        (self.root / 'empty-directory').rmdir()
        with self.assertRaises(ValueError): fixture.assert_restored(self.root, 1)

    def test_unexpected_path_fails(self):
        (self.root / 'unexpected').write_bytes(b'')
        with self.assertRaises(ValueError): fixture.assert_restored(self.root, 1)

    def test_mode_change_fails(self):
        (self.root / 'tools/check.sh').chmod(0o640)
        with self.assertRaises(ValueError): fixture.assert_restored(self.root, 1)

    def test_symlink_is_not_followed(self):
        p = self.root / 'empty'; p.unlink(); p.symlink_to('state/decision.json')
        with self.assertRaises(ValueError): fixture.assert_restored(self.root, 1)

    def test_transition_refuses_unexpected_state(self):
        (self.root / 'state/decision.json').write_bytes(b'changed')
        with self.assertRaises(ValueError): fixture.materialize(self.root, 2)


class CopyCorruptionTests(unittest.TestCase):
    def test_read_only_pack_changes_only_in_new_copy(self):
        spec=importlib.util.spec_from_file_location('wsl_restore_corruption',PATH.with_name('corruption.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); source=root/'source'; target=root/'copy'
            pack=source/'data/aa/pack';pack.parent.mkdir(parents=True);pack.write_bytes(b'original encrypted synthetic pack');pack.chmod(0o444)
            original=pack.read_bytes()
            module.corrupt_repository_copy(source,target)
            self.assertEqual(pack.read_bytes(),original)
            self.assertEqual(pack.stat().st_mode & 0o777,0o444)
            self.assertNotEqual((target/'data/aa/pack').read_bytes(),original)
            with self.assertRaises(ValueError): module.corrupt_repository_copy(source,source)
            with self.assertRaises(ValueError): module.corrupt_repository_copy(source,source/'child')
            with self.assertRaises(ValueError): module.corrupt_repository_copy(source,target)


class RecoveryTargetTests(unittest.TestCase):
    setUp = RestoreOracleTests.setUp
    def recover_module(self):
        spec=importlib.util.spec_from_file_location('wsl_restore_recover',PATH.with_name('recover.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {'fixture':fixture}):spec.loader.exec_module(module)
        return module

    def test_parent_target_preserves_fixture_root_check(self):
        module=self.recover_module()
        self.assertEqual(module.verify_target(self.root.parent,1),fixture.expected_manifest(1))
        self.root.chmod(0o700)
        with self.assertRaises(ValueError):module.verify_target(self.root.parent,1)

    def test_extra_restored_top_level_directory_fails(self):
        module=self.recover_module()
        (self.root.parent/'unselected').mkdir()
        with self.assertRaises(ValueError):module.verify_target(self.root.parent,1)
