"""scripts/path_safety.refuse_untrusted_symlinks(): the shared helper behind
every collector/verifier symlink-ancestor check touched by the round-2
security review. This file tests the helper directly; each caller's own
message string and integration are covered in that caller's own test file.
"""
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from scripts.path_safety import refuse_untrusted_symlinks


class PathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_plain_path_with_no_symlinks_is_accepted(self):
        target = self.root / 'plain' / 'leaf'
        self.assertEqual(refuse_untrusted_symlinks(target, 'refused'), target)

    def test_dotdot_component_is_refused(self):
        target = self.root / 'a' / '..' / 'b'
        with self.assertRaisesRegex(ValueError, 'refused'):
            refuse_untrusted_symlinks(target, 'refused')

    def test_non_root_owned_ancestor_symlink_refused_even_set_as_tmpdir(self):
        # Round-2 security review, item 3: the TMPDIR exemption trusted
        # $TMPDIR unconditionally. Must fail on c1f30cb's per-caller
        # TMPDIR-anchored walk (which never checked ownership at all) and
        # pass now that $TMPDIR grants no exemption whatsoever.
        real = self.root / 'real'; real.mkdir()
        alias = self.root / 'alias-as-tmpdir'; alias.symlink_to(real)
        saved_tempdir = tempfile.tempdir
        self.addCleanup(setattr, tempfile, 'tempdir', saved_tempdir)
        tempfile.tempdir = None
        with mock.patch.dict('os.environ', {'TMPDIR': str(alias)}):
            self.assertEqual(tempfile.gettempdir(), str(alias))
            with self.assertRaisesRegex(ValueError, 'refused'):
                refuse_untrusted_symlinks(alias / 'victim', 'refused')

    def test_non_root_owned_symlink_outside_any_temp_dir_refused(self):
        # A symlinked component that has nothing to do with TMPDIR at all
        # (well outside tempfile.gettempdir()) must still be refused.
        real = self.root / 'elsewhere-real'; real.mkdir()
        alias = self.root / 'elsewhere-alias'; alias.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'refused'):
            refuse_untrusted_symlinks(alias / 'victim', 'refused')

    def test_root_owned_non_writable_ancestor_symlink_is_tolerated(self):
        # Simulates macOS's own /tmp -> /private/tmp, /var -> /private/var,
        # /etc -> /private/etc: root-owned, not group/world-writable. Linux
        # does not enforce meaningful permission bits on a symlink itself
        # (lstat always reports mode 0o777 for a symlink on Linux, unlike
        # BSD/macOS where lchmod is meaningful), so this is simulated with a
        # mock of Path.lstat rather than an actual Linux symlink -- exactly
        # as the ownership/mode condition needs on this platform.
        real = self.root / 'system-real'; real.mkdir()
        link = self.root / 'system-link'; link.symlink_to(real)
        target = link / 'leaf'
        real_lstat = Path.lstat

        class RootOwnedNonWritable:
            def __init__(self, info):
                self.st_uid = 0
                self.st_mode = (info.st_mode & ~0o777) | 0o755

        def fake_lstat(self, *a, **kw):
            info = real_lstat(self, *a, **kw)
            return RootOwnedNonWritable(info) if self == link else info

        with mock.patch.object(Path, 'lstat', fake_lstat):
            self.assertEqual(refuse_untrusted_symlinks(target, 'refused'), target)

    def test_root_owned_but_group_writable_ancestor_symlink_is_still_refused(self):
        # Root ownership alone is not sufficient; the link must also not be
        # group- or world-writable (an attacker with group access could
        # still repoint a root-owned-but-writable link).
        real = self.root / 'system-real2'; real.mkdir()
        link = self.root / 'system-link2'; link.symlink_to(real)
        target = link / 'leaf'
        real_lstat = Path.lstat

        class RootOwnedWritable:
            def __init__(self, info):
                self.st_uid = 0
                self.st_mode = (info.st_mode & ~0o777) | 0o775  # group-writable

        def fake_lstat(self, *a, **kw):
            info = real_lstat(self, *a, **kw)
            return RootOwnedWritable(info) if self == link else info

        with mock.patch.object(Path, 'lstat', fake_lstat):
            with self.assertRaisesRegex(ValueError, 'refused'):
                refuse_untrusted_symlinks(target, 'refused')

    def test_symlinked_leaf_is_refused(self):
        real = self.root / 'leaf-real'; real.mkdir()
        alias = self.root / 'leaf-alias'; alias.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'refused'):
            refuse_untrusted_symlinks(alias, 'refused')


if __name__ == '__main__':
    unittest.main()
