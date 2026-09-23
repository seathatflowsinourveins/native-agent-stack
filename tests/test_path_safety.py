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

    def _mock_top_level_symlink(self, name):
        """Pretend Path(path.anchor)/name is a symlink, without touching the
        real filesystem root. Real is_symlink()/lstat() calls for every
        other path (including the real root itself) pass through unchanged,
        so this only fakes the one synthetic top-level candidate the test
        constructs; a real symlink can't be planted directly under / here
        (no permission, and it would not be sandboxed to this test)."""
        fake = Path(Path('/').anchor) / name
        real_is_symlink, real_lstat = Path.is_symlink, Path.lstat

        def is_symlink(self, *a, **kw):
            return True if self == fake else real_is_symlink(self, *a, **kw)

        return fake, mock.patch.object(Path, 'is_symlink', is_symlink)

    def test_root_owned_link_not_directly_under_root_is_refused(self):
        # Round-3 security review, finding A: tolerating a root-owned
        # symlink ANYWHERE (not just directly under /) let the walk follow
        # a root-owned link deeper in the tree -- e.g. a hard link to, or a
        # copy of, a relative framework link such as macOS's
        # Versions/Current planted under /tmp. This link sits under a real
        # tempdir, not directly under /, so it must be refused regardless
        # of ownership; mocked root-owned uid proves ownership alone no
        # longer buys tolerance once position is wrong.
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
            with self.assertRaisesRegex(ValueError, 'refused'):
                refuse_untrusted_symlinks(target, 'refused')

    def test_link_directly_under_root_with_writable_parent_is_refused(self):
        # Round-3 security review, finding B: checking the LINK's own mode
        # does nothing (a symlink's permission bits do not gate replacing
        # it; Linux does not even enforce them -- lstat reports 0o777 for
        # every symlink regardless of chmod). What actually controls
        # whether an unprivileged account can repoint or replace the link
        # is whether it can write to the directory the link lives in -- with
        # finding A's fix that parent is always /, so this mocks /'s own
        # lstat to be writable and confirms refusal even though the
        # (irrelevant) link position is otherwise exactly macOS's shape.
        fake, patch_is_symlink = self._mock_top_level_symlink('nas-path-safety-writable-parent')
        target = fake / 'leaf'
        real_lstat = Path.lstat
        root = Path('/')

        class WritableRoot:
            def __init__(self, info):
                self.st_uid = 0
                self.st_mode = (info.st_mode & ~0o777) | 0o777  # world-writable

        def fake_lstat(self, *a, **kw):
            info = real_lstat(self, *a, **kw)
            return WritableRoot(info) if self == root else info

        with patch_is_symlink, mock.patch.object(Path, 'lstat', fake_lstat):
            with self.assertRaisesRegex(ValueError, 'refused'):
                refuse_untrusted_symlinks(target, 'refused')

    def test_link_directly_under_root_with_owned_non_writable_parent_is_tolerated(self):
        # The positive case matching macOS's real /tmp -> /private/tmp,
        # /var -> /private/var, /etc -> /private/etc: a link directly under
        # / (mocked, since a real one can't be planted at the actual
        # filesystem root here), whose parent (/) is root-owned and not
        # group/world-writable -- true of / on every real host, so no lstat
        # mock is needed for the parent check itself.
        fake, patch_is_symlink = self._mock_top_level_symlink('nas-path-safety-owned-parent')
        target = fake / 'leaf'
        with patch_is_symlink:
            self.assertEqual(refuse_untrusted_symlinks(target, 'refused'), target)

    def test_symlinked_leaf_is_refused(self):
        real = self.root / 'leaf-real'; real.mkdir()
        alias = self.root / 'leaf-alias'; alias.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'refused'):
            refuse_untrusted_symlinks(alias, 'refused')


if __name__ == '__main__':
    unittest.main()
