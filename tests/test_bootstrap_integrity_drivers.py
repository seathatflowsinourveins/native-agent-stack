"""The WORK guard of the bootstrap-integrity evidence drivers.

evidence/artifacts/bootstrap-integrity-20260926/drivers/ holds the self-written local_integration
drivers of that change's end-to-end evidence. As first run, e2e.sh and uv_forms.sh began with an
unconditional `rm -rf WORK`, and bootstrap_once.sh deleted and wrote named paths under WORK, so an
existing checkout or home directory passed as WORK would have been destroyed (2026-09-26 review).
The drivers now source work_guard.sh: they accept only a WORK that does not exist, is an empty
directory, or holds the marker file that mark_work writes into every WORK a driver creates, and they
exit 2 before touching anything else. The as-run originals are kept byte for byte in drivers/as-run/.

The guard's first revision had three holes, each reproduced before its fix (the same day): a driver
copied without work_guard.sh carried on past the failed `.` to its `rm -rf WORK`; a WORK named
`-delete` made claim_work run `find -delete ...` in the current directory; and a non-empty directory
named `!` read as empty, because find takes a lone `!` as part of its expression. The drivers now
exit 2 when the guard cannot be sourced or defines no claim_work, claim_work refuses a WORK that begins
with `-`, and find lists a relative WORK as ./WORK.

bash runs only the guard itself and each driver's refusal path, which ends before any deletion,
download, build or tool run: no network and no installed tool is needed.
"""

from __future__ import annotations

import difflib
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/bootstrap-integrity-20260926"
DRIVERS = ARTIFACT / "drivers"
GUARD = DRIVERS / "work_guard.sh"
MARKER = ".bootstrap-integrity-work"
BASH = shutil.which("bash")
# sha256 of the three shell drivers as they ran for e2e-check.txt, bootstrap-runs.log and uv-forms.txt,
# which manifests/evidence.json registered for drivers/<name> before the guard was added.
AS_RUN_SHA256 = {
    "bootstrap_once.sh": "867f4f163571bc94b3c35c36e21315b436fbfa2ca62917ec0cf3c7e738464cf0",
    "e2e.sh": "6324b2d6cffacd018b91325a6f59b46b5fe86a9bbf9d2c9f6703dc7b5d458314",
    "uv_forms.sh": "706260004cdbab2bde23d30e1bc39e422cb7c8876dea38a4611399a72cefe701",
}
# The guard's two fail-closed lines: a driver whose guard cannot be sourced, or defines no claim_work,
# exits 2 instead of carrying on to its first deletion.
SOURCE = '. "$here/work_guard.sh" || exit 2'
CLAIM = 'claim_work "$work" || exit 2'
# The only lines a guarded driver adds to its as-run original.
GUARD_LINES = {
    'here="$(cd "$(dirname "$0")" && pwd -P)"',
    "# WORK must be new, an empty directory, or a directory these drivers created (work_guard.sh).",
    "# shellcheck source-path=SCRIPTDIR source=work_guard.sh",
    SOURCE,
    CLAIM,
    'mkdir -p "$work"',
    'mark_work "$work"',
}
SHELL_DRIVERS = ("e2e.sh", "uv_forms.sh", "bootstrap_once.sh", "upstream_checks.sh")
# A driver's first line that deletes, creates, copies or runs something.
ACTIONS = ("rm ", "mkdir ", "cp ", "git ", "jq ", "python3 ", '"$here/')


def refusal_args(driver: str, tmp: Path, work: Path) -> list[str]:
    """Arguments that reach the driver's guard: WORK is `work`, every other path does not exist."""
    missing = str(tmp / "missing")
    return {
        "e2e.sh": [missing, str(work)],
        "uv_forms.sh": [missing, str(work)],
        "bootstrap_once.sh": ["label", missing, missing, str(work), str(work / "uv-cache"), '["headroom"]'],
        "upstream_checks.sh": [missing, str(work)],
    }[driver]


def run_driver(path: Path, args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, str(path), *args], cwd=tmp, capture_output=True, text=True, timeout=120,
                          check=False, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp / "home")})


requires_bash = unittest.skipUnless(BASH, "bash is not installed")


def tree(path: Path) -> dict[str, tuple]:
    """Every entry under path, relative, with its kind and content (a link's target, a file's bytes)."""
    entries = {}
    for entry in sorted(path.rglob("*")):
        if entry.is_symlink():
            entries[str(entry.relative_to(path))] = ("link", os.readlink(entry))
        elif entry.is_dir():
            entries[str(entry.relative_to(path))] = ("dir",)
        else:
            entries[str(entry.relative_to(path))] = ("file", entry.read_bytes())
    return entries


@requires_bash
class ClaimWorkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def claim(self, work: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([BASH, "-c", 'source "$1"; claim_work "$2"; echo claimed', "claim", str(GUARD), work],
                              capture_output=True, text=True, timeout=30, check=False, env=env, cwd=cwd)

    def test_a_new_path_an_empty_directory_and_a_marked_directory_are_claimed_untouched(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        marked = self.tmp / "marked"
        (marked / "sub").mkdir(parents=True)
        (marked / MARKER).write_bytes(b"")
        (marked / "sub/result.log").write_text("an earlier run\n")
        before = tree(self.tmp)
        for work in (self.tmp / "new", self.tmp / "new/nested", empty, marked):
            with self.subTest(work=work.name):
                result = self.claim(str(work))
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "claimed\n", ""))
        self.assertEqual(tree(self.tmp), before)  # claim_work itself never creates or deletes anything

    def test_anything_else_is_refused_with_exit_2_and_left_untouched(self):
        checkout = self.tmp / "checkout"
        (checkout / ".git").mkdir(parents=True)
        (checkout / "README.md").write_text("someone's work\n")
        hidden = self.tmp / "hidden-only"
        hidden.mkdir()
        (hidden / ".profile").write_text("someone's settings\n")
        marker_dir = self.tmp / "marker-is-a-directory"
        (marker_dir / MARKER).mkdir(parents=True)
        marker_link = self.tmp / "marker-is-a-link"
        marker_link.mkdir()
        (marker_link / "data").write_text("someone's data\n")
        (marker_link / MARKER).symlink_to(self.tmp / "elsewhere")
        a_file = self.tmp / "file.txt"
        a_file.write_text("someone's file\n")
        empty = self.tmp / "empty"
        empty.mkdir()
        link = self.tmp / "link-to-empty"
        link.symlink_to(empty)
        before = tree(self.tmp)
        cases = {
            "a non-empty directory without the marker": checkout,
            "a directory holding only a hidden file": hidden,
            "a marker that is a directory": marker_dir,
            "a marker that is a symbolic link": marker_link,
            "a regular file": a_file,
            "a symbolic link, even to an empty directory": link,
            "an empty string": "",
        }
        for label, work in cases.items():
            with self.subTest(label):
                result = self.claim(str(work))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("refusing", result.stderr)
        self.assertEqual(tree(self.tmp), before)

    def test_a_work_that_rm_mkdir_or_find_would_read_as_syntax_is_refused_and_nothing_is_touched(self):
        # As first written, claim_work ran `find -delete ...` for a WORK named -delete, which deleted a
        # file of the current directory, and read a non-empty directory named ! as empty. Each case gets
        # a fresh directory, so one case's damage cannot fail another.
        for work in ("-delete", "-new", "./-delete", "!", "./!"):
            with self.subTest(work=work):
                cwd = self.tmp / f"case-{len(list(self.tmp.iterdir()))}"
                cwd.mkdir()
                for name in ("-delete", "!"):
                    (cwd / name).mkdir()
                    (cwd / name / "data").write_text("someone's data\n")
                (cwd / "bystander.txt").write_text("someone's file beside WORK\n")
                before = tree(cwd)
                result = self.claim(work, cwd=cwd)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("refusing", result.stderr)
                self.assertEqual(tree(cwd), before)

    def test_a_directory_that_cannot_be_listed_is_refused(self):
        locked = self.tmp / "locked"
        locked.mkdir()
        (locked / "data").write_text("someone's data\n")
        locked.chmod(0o000)
        self.addCleanup(locked.chmod, 0o700)
        result = self.claim(str(locked))
        locked.chmod(0o700)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual((locked / "data").read_text(), "someone's data\n")

    def test_a_failed_listing_refuses_rather_than_reading_as_empty(self):
        # With no find on PATH the listing fails; even an empty directory is then refused.
        empty = self.tmp / "empty"
        empty.mkdir()
        no_tools = self.tmp / "no-tools"
        no_tools.mkdir()
        result = self.claim(str(empty), env={"PATH": str(no_tools)})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("cannot be listed", result.stderr)

    def test_mark_work_writes_the_marker_that_claim_work_accepts(self):
        work = self.tmp / "work"
        work.mkdir()
        (work / "data").write_text("a driver's output\n")
        marked = subprocess.run([BASH, "-c", 'source "$1"; mark_work "$2"', "mark", str(GUARD), str(work)],
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(marked.returncode, 0, marked.stderr)
        self.assertTrue((work / MARKER).is_file())
        self.assertEqual(self.claim(str(work)).returncode, 0)


@requires_bash
class DriverRefusalTests(unittest.TestCase):
    """Each shell driver, given an existing WORK that holds someone's files, exits 2 before it deletes,
    creates, downloads or runs anything. Every other path argument names a path that does not exist."""

    def test_each_driver_refuses_a_non_empty_work_it_did_not_create(self):
        for driver in SHELL_DRIVERS:
            with self.subTest(driver=driver), tempfile.TemporaryDirectory() as tmp_name:
                tmp = Path(tmp_name)
                work = tmp / "work"
                (work / ".git").mkdir(parents=True)
                (work / "notes.txt").write_text("someone's notes\n")
                before = tree(tmp)
                result = run_driver(DRIVERS / driver, refusal_args(driver, tmp, work), tmp)
                self.assertEqual(result.returncode, 2, (result.stdout + result.stderr)[-400:])
                self.assertEqual(result.stdout, "")
                self.assertIn("refusing", result.stderr)
                self.assertEqual(sorted(tree(tmp)), sorted(before))
                self.assertEqual(tree(tmp), before)

    def test_a_driver_whose_guard_is_missing_or_defines_nothing_exits_2_before_touching_work(self):
        # As first written, a driver copied without work_guard.sh carried on past the failed `.` and the
        # missing claim_work to its `rm -rf WORK`.
        for driver in SHELL_DRIVERS:
            for guard in ("missing", "empty"):
                with self.subTest(driver=driver, guard=guard), tempfile.TemporaryDirectory() as tmp_name:
                    tmp = Path(tmp_name)
                    lone = tmp / "lone"
                    lone.mkdir()
                    shutil.copy2(DRIVERS / driver, lone / driver)
                    if guard == "empty":
                        (lone / "work_guard.sh").write_text("")
                    work = tmp / "work"
                    (work / ".git").mkdir(parents=True)
                    (work / "notes.txt").write_text("someone's notes\n")
                    before = tree(tmp)
                    result = run_driver(lone / driver, refusal_args(driver, tmp, work), tmp)
                    self.assertEqual(result.returncode, 2, (result.stdout + result.stderr)[-400:])
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(tree(tmp), before)


class AsRunOriginalTests(unittest.TestCase):
    def test_the_as_run_originals_are_kept_byte_for_byte_and_the_readme_names_their_hashes(self):
        readme = (ARTIFACT / "README.md").read_text()
        for name, digest in AS_RUN_SHA256.items():
            with self.subTest(name):
                self.assertEqual(hashlib.sha256((DRIVERS / "as-run" / name).read_bytes()).hexdigest(), digest)
                self.assertTrue(digest in readme, f"README.md does not name {name}'s as-run sha256 {digest}")

    def test_each_guarded_driver_is_its_as_run_original_plus_guard_lines_only(self):
        for name in AS_RUN_SHA256:
            with self.subTest(name):
                original = (DRIVERS / "as-run" / name).read_text().splitlines()
                guarded = (DRIVERS / name).read_text().splitlines()
                opcodes = difflib.SequenceMatcher(None, original, guarded, autojunk=False).get_opcodes()
                self.assertEqual({tag for tag, *_ in opcodes} - {"equal", "insert"}, set(), opcodes)
                added = [line for tag, _, _, start, end in opcodes if tag == "insert" for line in guarded[start:end]]
                self.assertLessEqual(set(added), GUARD_LINES)
                for line in (SOURCE, CLAIM, 'mark_work "$work"'):
                    self.assertIn(line, added)

    def test_every_shell_driver_sources_and_calls_the_guard_fail_closed_before_any_action(self):
        for name in SHELL_DRIVERS:
            with self.subTest(name):
                lines = (DRIVERS / name).read_text().splitlines()
                for line in (SOURCE, CLAIM):
                    self.assertTrue(line in lines, f"{name} has no line {line!r}")
                first_action = min(index for index, line in enumerate(lines) if line.startswith(ACTIONS))
                self.assertLess(lines.index(SOURCE), lines.index(CLAIM))
                self.assertLess(lines.index(CLAIM), first_action)


if __name__ == "__main__":
    unittest.main()
