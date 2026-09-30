"""tools/adoption/managed_block.py: the ~/.claude/CLAUDE.md and ~/.profile blocks of --configure-full-profile.

Against real files in a temporary HOME: each block is created, appended after operator text, replaced in place when
the source changes, and left alone (no write, no backup) when current. rtk's `@RTK.md` import and every line outside
the markers survive; an earlier hand copy of the example is replaced only when it equals the current example, and any
other copy, a damaged block, a symlink or a non-UTF-8 file is refused with nothing written. The PATH block is sourced
by a real POSIX sh: its first PATH entry is the ecosystem's bin directory whatever characters the root holds, and a
second sourcing adds nothing.
"""

import contextlib
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import managed_block  # noqa: E402

EXAMPLE = (ROOT / "examples/claude-native/CLAUDE.md").read_text(encoding="utf-8")
HEADING = EXAMPLE.splitlines()[0]
SH = shutil.which("sh")


def run(*argv: str) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = managed_block.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ManagedBlockCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.home.mkdir()

    def backups(self, path: Path) -> list:
        return sorted(item.name for item in path.parent.glob(path.name + ".bak.*"))


class ClaudeMdBlockTests(ManagedBlockCase):
    def setUp(self):
        super().setUp()
        self.target = self.home / ".claude" / "CLAUDE.md"

    def apply(self, *extra: str) -> tuple:
        return run("--home", str(self.home), *extra, "claude-md")

    def test_an_absent_file_gets_only_the_block(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        text = self.target.read_text(encoding="utf-8")
        self.assertEqual(text, managed_block.claude_block(EXAMPLE))
        self.assertTrue(text.startswith(managed_block.CLAUDE_BEGIN) and text.endswith(managed_block.CLAUDE_END + "\n"))
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o644)
        self.assertEqual(self.backups(self.target), [])
        self.assertIn("(new file)", out)

    def test_rtk_import_and_operator_text_stay_outside_and_a_rerun_writes_nothing(self):
        self.target.parent.mkdir()
        self.target.write_text("@RTK.md\n\n# Mine\n\n- Prefer short answers.\n", encoding="utf-8")
        self.target.chmod(0o600)
        self.assertEqual(self.apply()[0], 0)
        text = self.target.read_text(encoding="utf-8")
        self.assertEqual(text, "@RTK.md\n\n# Mine\n\n- Prefer short answers.\n\n" + managed_block.claude_block(EXAMPLE))
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(len(self.backups(self.target)), 1)
        before = (text, self.target.stat().st_mtime_ns)
        code, out, _ = self.apply()
        self.assertEqual(code, 0)
        self.assertIn("already current, nothing written", out)
        self.assertEqual((self.target.read_text(encoding="utf-8"), self.target.stat().st_mtime_ns), before)
        self.assertEqual(len(self.backups(self.target)), 1)

    def test_a_changed_example_replaces_the_block_in_place_and_backs_up_first(self):
        self.target.parent.mkdir()
        old = "@RTK.md\n\n" + managed_block.claude_block("# Native engineering defaults\n\nOld rule.\n") + "\n# After\n"
        self.target.write_text(old, encoding="utf-8")
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"),
                         "@RTK.md\n\n" + managed_block.claude_block(EXAMPLE) + "\n# After\n")
        [backup] = self.backups(self.target)
        self.assertEqual((self.target.parent / backup).read_text(encoding="utf-8"), old)

    def test_an_rtk_import_inside_an_earlier_block_moves_above_it(self):
        self.target.parent.mkdir()
        self.target.write_text(f"{managed_block.CLAUDE_BEGIN_LINE}\n@RTK.md\nold\n{managed_block.CLAUDE_END}\n",
                               encoding="utf-8")
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "@RTK.md\n" + managed_block.claude_block(EXAMPLE))

    def test_a_hand_copy_equal_to_the_example_becomes_the_block_once(self):
        self.target.parent.mkdir()
        self.target.write_text("@RTK.md\n\n" + EXAMPLE, encoding="utf-8")
        self.assertEqual(self.apply()[0], 0)
        text = self.target.read_text(encoding="utf-8")
        self.assertEqual(text, "@RTK.md\n\n" + managed_block.claude_block(EXAMPLE))
        self.assertEqual(text.count(HEADING), 1)

    def test_an_older_hand_copy_is_refused_with_nothing_written(self):
        self.target.parent.mkdir()
        older = "@RTK.md\n\n" + EXAMPLE.replace("Core rule", "Core rules", 1)
        self.target.write_text(older, encoding="utf-8")
        code, _, err = self.apply()
        self.assertEqual(code, managed_block.EXIT_REFUSED)
        self.assertIn("unmanaged copy", err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), older)
        self.assertEqual(self.backups(self.target), [])

    def test_a_second_copy_beside_the_block_is_refused(self):
        self.target.parent.mkdir()
        text = managed_block.claude_block(EXAMPLE) + "\n" + EXAMPLE
        self.target.write_text(text, encoding="utf-8")
        code, _, err = self.apply()
        self.assertEqual(code, managed_block.EXIT_REFUSED)
        self.assertIn("another copy", err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), text)

    def test_damaged_markers_are_refused(self):
        self.target.parent.mkdir()
        for text in (f"{managed_block.CLAUDE_BEGIN_LINE}\nno end\n",
                     f"{managed_block.CLAUDE_END}\n{managed_block.CLAUDE_BEGIN_LINE}\n",
                     managed_block.claude_block("a\n") + managed_block.claude_block("b\n")):
            with self.subTest(text=text[:60]):
                self.target.write_text(text, encoding="utf-8")
                self.assertEqual(self.apply()[0], managed_block.EXIT_REFUSED)
                self.assertEqual(self.target.read_text(encoding="utf-8"), text)

    def test_a_symlink_or_a_non_utf8_file_is_refused(self):
        self.target.parent.mkdir()
        real = self.home / "real-claude.md"
        real.write_text("@RTK.md\n", encoding="utf-8")
        self.target.symlink_to(real)
        self.assertEqual(self.apply()[0], managed_block.EXIT_REFUSED)
        # Refused when read, not only right before the write: a dry run reports the refusal too.
        self.assertEqual(self.apply("--dry-run")[0], managed_block.EXIT_REFUSED)
        self.assertEqual(real.read_text(encoding="utf-8"), "@RTK.md\n")
        self.target.unlink()
        self.target.write_bytes(b"\xff\xfe")
        self.assertEqual(self.apply()[0], managed_block.EXIT_REFUSED)
        self.assertEqual(self.target.read_bytes(), b"\xff\xfe")

    def test_dry_run_prints_the_diff_and_writes_nothing(self):
        code, out, _ = self.apply("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN, nothing written", out)
        self.assertIn("+" + managed_block.CLAUDE_END, out)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.target.parent.exists())


class ProfilePathBlockTests(ManagedBlockCase):
    def setUp(self):
        super().setUp()
        self.target = self.home / ".profile"

    def apply(self, eco_root: str, *extra: str) -> tuple:
        return run("--home", str(self.home), *extra, "profile-path", "--eco-root", eco_root)

    def path_after_sourcing(self, times: int = 1) -> list:
        script = ". \"$HOME/.profile\"; " * times + 'printf "%s" "$PATH"'
        result = subprocess.run([SH, "-c", script], env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.split(":")

    def test_an_eco_root_under_home_is_written_relative_to_home(self):
        eco = self.home / ".local/share/codex-ecosystem"
        self.assertEqual(self.apply(str(eco))[0], 0)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn('PATH="$HOME/.local/share/codex-ecosystem/bin${PATH:+:$PATH}"', text)
        self.assertNotIn(str(self.home), text)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o644)

    @unittest.skipUnless(SH, "needs a POSIX sh")
    def test_sh_puts_the_bin_directory_first_once_for_any_root(self):
        for eco in (self.home / ".local/share/codex-ecosystem", Path("/opt/eco root/with $dollar `tick` \"quote\"")):
            with self.subTest(eco=str(eco)):
                if self.target.exists():
                    self.target.unlink()
                self.assertEqual(self.apply(str(eco))[0], 0)
                path = self.path_after_sourcing()
                self.assertEqual(path, [str(eco / "bin"), "/usr/bin", "/bin"])
                self.assertEqual(self.path_after_sourcing(times=2), path)

    def test_existing_text_is_kept_the_block_goes_last_and_a_rerun_writes_nothing(self):
        self.target.write_text("# ~/.profile\numask 022\n", encoding="utf-8")
        self.assertEqual(self.apply("/opt/eco")[0], 0)
        text = self.target.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# ~/.profile\numask 022\n\n" + managed_block.PROFILE_BEGIN_LINE + "\n"), text)
        self.assertTrue(text.endswith(managed_block.PROFILE_END + "\n"))
        self.assertEqual(len(self.backups(self.target)), 1)
        code, out, _ = self.apply("/opt/eco")
        self.assertEqual(code, 0)
        self.assertIn("already current", out)
        self.assertEqual(self.target.read_text(encoding="utf-8"), text)
        self.assertEqual(len(self.backups(self.target)), 1)
        self.assertEqual(self.apply("/opt/other-eco")[0], 0)
        self.assertEqual(self.target.read_text(encoding="utf-8").count(managed_block.PROFILE_BEGIN), 1)
        self.assertIn('"/opt/other-eco/bin${PATH:+:$PATH}"', self.target.read_text(encoding="utf-8"))

    def test_a_relative_root_or_a_damaged_block_is_refused(self):
        self.assertEqual(self.apply("relative/eco")[0], managed_block.EXIT_REFUSED)
        self.assertFalse(self.target.exists())
        self.target.write_text(f"{managed_block.PROFILE_BEGIN_LINE}\nPATH=x\n", encoding="utf-8")
        self.assertEqual(self.apply("/opt/eco")[0], managed_block.EXIT_REFUSED)
        self.assertEqual(self.target.read_text(encoding="utf-8"), f"{managed_block.PROFILE_BEGIN_LINE}\nPATH=x\n")

    def test_the_cli_needs_a_block_name_and_the_eco_root(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in ([], ["profile-path"]):
                with self.subTest(argv=argv), self.assertRaises(SystemExit) as exit_:
                    managed_block.main(argv)
                self.assertEqual(exit_.exception.code, managed_block.EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
