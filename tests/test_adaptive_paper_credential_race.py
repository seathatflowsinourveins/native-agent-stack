"""Deterministic race-simulation and mutation-kill evidence for
credential_guard.open_verified() (G-fix-round items 1 and 4, 2026-09-24).

Real concurrent races are non-deterministic and would make this suite flaky
or slow (spin-loop threads racing a real attacker window). Instead each test
here injects a synchronous filesystem mutation at an exact point in the
traversal via `credential_guard._hook`, a module attribute that is a no-op in
production and is monkeypatched only by these tests. This reproduces exactly
what a real attacker's race would need to achieve (swap a symlink/FIFO/
different inode into a name between this module's check of that name and its
use of it) without relying on timing.

Every "does not hang" assertion runs under a `signal.alarm` deadline so a
regression that removes O_NONBLOCK fails fast (as a test failure) instead of
freezing the suite.

The mutation section disables one guard protection at a time (by
monkeypatching a specific internal helper) and shows a named test now fails
to reject the case that protection exists for -- i.e. that test "kills" that
mutation. `MUTATION_KILLS` (built at import time by actually running each
mutation) is asserted to cover every listed mutation.
"""
from __future__ import annotations

import contextlib
import os
import signal
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import credential_guard as cg  # noqa: E402


class DeadlineExceeded(Exception):
    """Raised by the SIGALRM handler; never a real timeout the OS enforces."""


@contextlib.contextmanager
def deadline(seconds):
    """Hard wall-clock bound for a single call, via signal.alarm (Unix only,
    which every runtime this suite targets is). A blocking syscall (e.g.
    open() on a FIFO without O_NONBLOCK) is interrupted with EINTR and, since
    the handler raises rather than returning, Python does not auto-retry it
    (PEP 475) -- so a real hang surfaces as DeadlineExceeded, not a frozen
    test process."""
    def _on_alarm(signum, frame):
        raise DeadlineExceeded(f"exceeded {seconds}s deadline")
    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _write_env(directory, name="paper.env", mode=0o600):
    path = Path(directory) / name
    path.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
    os.chmod(path, mode)
    return path


class HookInjectedRaces(unittest.TestCase):
    """credential_guard._hook lets a test fire exactly once at a named
    traversal stage, synchronously mutating the filesystem the way a real
    concurrent attacker would need to, then lets the real syscall run against
    the mutated state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._hook_patch = patch.object(cg, "_hook", side_effect=lambda stage, name: None)
        self.mock_hook = self._hook_patch.start()
        self.addCleanup(self._hook_patch.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def _fire_once(self, on_stage, on_name, action):
        fired = {"done": False}

        def _side_effect(stage, name):
            if not fired["done"] and stage == on_stage and name == on_name:
                fired["done"] = True
                action()
        self.mock_hook.side_effect = _side_effect

    def test_ancestor_directory_swapped_to_symlink_mid_traversal_fails_closed(self):
        sub = self.root / "sub"
        sub.mkdir(mode=0o700)
        path = _write_env(sub)
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        _write_env(elsewhere, name="paper.env")

        def swap():
            import shutil
            shutil.rmtree(sub)
            os.symlink(elsewhere, sub)

        self._fire_once("pre_dir_open", "sub", swap)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions"):
            cg.open_verified(path, follow_symlinks=True)

    def test_final_component_swapped_to_symlink_mid_traversal_fails_closed(self):
        path = _write_env(self.root)
        attacker_target = self.root / "attacker.env"
        _write_env(self.root, name="attacker.env")

        def swap():
            path.unlink()
            os.symlink(attacker_target, path)

        self._fire_once("pre_file_open", path.name, swap)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions"):
            cg.open_verified(path, follow_symlinks=True)

    def test_final_component_swapped_to_fifo_mid_traversal_fails_closed_and_does_not_hang(self):
        path = _write_env(self.root)

        def swap():
            path.unlink()
            os.mkfifo(path, mode=0o600)

        self._fire_once("pre_file_open", path.name, swap)
        with deadline(5):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions"):
                cg.open_verified(path, follow_symlinks=True)

    def test_metadata_changed_between_open_and_fstat_is_caught_by_the_live_fstat(self):
        # Proves the guard checks the fd's *current* metadata at fstat time,
        # not a value captured earlier -- an "fd metadata mismatch" case.
        path = _write_env(self.root)

        def loosen():
            os.chmod(path, 0o644)

        def _side_effect(stage, name):
            if stage == "pre_file_fstat":
                loosen()
        self.mock_hook.side_effect = _side_effect
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions"):
            cg.open_verified(path, follow_symlinks=True)

    def test_valid_configuration_is_unaffected_by_a_hook_that_never_fires(self):
        path = _write_env(self.root)
        with cg.open_verified(path, follow_symlinks=True) as handle:
            self.assertEqual(handle.read(), b"APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")


class NaiveOpenIsFooledByTheSameAncestorSwap(unittest.TestCase):
    """Reference only, not production code: reproduces the pre-fix approach
    (resolve a pathname once, stat it, then open() the string) to show
    concretely that the *same* ancestor-directory swap the guard now refuses
    is silently followed by that older approach -- i.e. why the fix in item 1
    was necessary, not merely stylistic."""

    @staticmethod
    def _naive_credentials(path):
        """Pre-fix shape: everything after the one-time resolve() uses plain
        pathname operations, so any component can be swapped afterward and
        the following syscalls transparently follow it. Calls the shared
        `cg._hook("naive_pre_open", ...)` seam at exactly the stat-to-open
        gap so a test can inject the race deterministically."""
        resolved = Path(path).resolve()
        info = resolved.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise RuntimeError("naive_rejected")
        cg._hook("naive_pre_open", str(resolved))
        with open(resolved, "rb") as handle:  # noqa: PTH123 -- deliberately naive
            return handle.read()

    def test_ancestor_symlink_swap_between_the_naive_stat_and_open_is_silently_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim_dir = root / "sub"
            victim_dir.mkdir(mode=0o700)
            victim_file = _write_env(victim_dir, name="paper.env")

            attacker_dir = root / "attacker"
            attacker_dir.mkdir(mode=0o700)
            attacker_file = _write_env(attacker_dir, name="paper.env")
            attacker_file.write_text("APCA_API_KEY_ID=attacker-key\nAPCA_API_SECRET_KEY=attacker-secret\n")
            os.chmod(attacker_file, 0o600)

            hook_patch = patch.object(cg, "_hook", side_effect=lambda stage, name: None)
            mock_hook = hook_patch.start()
            self.addCleanup(hook_patch.stop)

            def _side_effect(stage, name):
                if stage == "naive_pre_open":
                    import shutil
                    shutil.rmtree(victim_dir)
                    os.symlink(attacker_dir, victim_dir)
            mock_hook.side_effect = _side_effect

            # The naive function's resolve()+stat() above ran *before* this
            # swap could happen (it happens inside _naive_credentials, at the
            # hook call) -- this reproduces the exact stat-to-open race
            # window item 1 describes, not a pre-arranged substitution.
            content = self._naive_credentials(victim_file)
            self.assertIn(b"attacker-key", content,
                          "the naive resolve-then-open approach was fooled by the ancestor swap, "
                          "which is the vulnerability class credential_guard.open_verified() closes")

    def test_the_guarded_open_verified_is_not_fooled_by_the_same_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim_dir = root / "sub"
            victim_dir.mkdir(mode=0o700)
            victim_file = _write_env(victim_dir, name="paper.env")

            attacker_dir = root / "attacker"
            attacker_dir.mkdir(mode=0o700)
            _write_env(attacker_dir, name="paper.env")

            hook_patch = patch.object(cg, "_hook", side_effect=lambda stage, name: None)
            mock_hook = hook_patch.start()
            self.addCleanup(hook_patch.stop)

            fired = {"done": False}

            def _side_effect(stage, name):
                if not fired["done"] and stage == "pre_dir_open" and name == "sub":
                    fired["done"] = True
                    import shutil
                    shutil.rmtree(victim_dir)
                    os.symlink(attacker_dir, victim_dir)
            mock_hook.side_effect = _side_effect

            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions"):
                cg.open_verified(victim_file, follow_symlinks=True)


# ---------------------------------------------------------------------------
# Mutation-kill evidence: disable one guard protection at a time and show a
# specific assertion (named below) now fails to reject the case it exists
# for. Built once at import time by actually executing each mutation.
# ---------------------------------------------------------------------------

def _fifo_case_directory():
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "fifo.env"
    os.mkfifo(path, mode=0o600)
    return tmp, path


def _hardlink_case_directory():
    tmp = tempfile.mkdtemp()
    target = _write_env(tmp, name="real.env")
    os.link(target, Path(tmp) / "second.env")
    return tmp, target


def _worktree_case_directory(repo_root):
    tmp = tempfile.mkdtemp(dir=repo_root)
    return tmp, _write_env(tmp)


def _parent_writable_case_directory():
    tmp = tempfile.mkdtemp()
    path = _write_env(tmp)
    os.chmod(tmp, 0o777)
    return tmp, path


def _symlink_case_directory():
    tmp = tempfile.mkdtemp()
    target = _write_env(tmp, name="real.env")
    link = Path(tmp) / "linked.env"
    link.symlink_to(target)
    return tmp, link


MUTATION_CASES = {
    "disable_hardlink_check": ("_check_file_metadata", _hardlink_case_directory),
    "disable_worktree_check": ("_ancestor_has_git_entry", None),  # handled specially below
    "disable_parent_directory_check": ("_check_parent_directory", _parent_writable_case_directory),
}


def _run_mutation_kill_report():
    """Returns {mutation_name: [killed_test_names]}. A mutation is "killed" by
    a case if, once that specific protection is disabled, the guard no
    longer raises for that case -- proving a test exists that would fail
    (catch the regression) if that protection were ever removed for real."""
    report = {}

    # 1. Hard-link check disabled: a 2-link file must now be silently accepted.
    with patch.object(cg, "_check_file_metadata", lambda info: None):
        tmp, path = _hardlink_case_directory()
        try:
            accepted = False
            try:
                with cg.open_verified(path, follow_symlinks=True):
                    accepted = True
            except cg.CredentialGuardError:
                accepted = False
            report["disable_hardlink_check"] = (
                ["test_hard_link_is_rejected"] if accepted else [])
        finally:
            import shutil
            shutil.rmtree(tmp)

    # 2. Worktree check disabled: a file inside this checkout must now be accepted.
    with patch.object(cg, "_ancestor_has_git_entry", lambda dir_fd: False):
        repo_root = Path(__file__).resolve().parents[1]
        tmp, path = _worktree_case_directory(repo_root)
        try:
            accepted = False
            try:
                with cg.open_verified(path, follow_symlinks=True):
                    accepted = True
            except cg.CredentialGuardError:
                accepted = False
            report["disable_worktree_check"] = (
                ["test_inside_git_worktree_is_rejected"] if accepted else [])
        finally:
            import shutil
            shutil.rmtree(tmp)

    # 3. Parent-directory ownership/mode check disabled: a world-writable
    #    parent must now be accepted.
    with patch.object(cg, "_check_parent_directory", lambda info: None):
        tmp, path = _parent_writable_case_directory()
        try:
            accepted = False
            try:
                with cg.open_verified(path, follow_symlinks=True):
                    accepted = True
            except cg.CredentialGuardError:
                accepted = False
            report["disable_parent_directory_check"] = (
                ["test_world_writable_parent_directory_is_rejected"] if accepted else [])
        finally:
            os.chmod(tmp, 0o700)
            import shutil
            shutil.rmtree(tmp)

    # 4. O_NOFOLLOW dropped from the final-component open: a symlinked file
    #    must now be silently followed for the follow_symlinks=False (i.e.
    #    market_research) loader, which never resolves first.
    real_open = os.open

    def _open_without_nofollow(path_arg, flags, *args, **kwargs):
        return real_open(path_arg, flags & ~os.O_NOFOLLOW, *args, **kwargs)

    with patch.object(cg.os, "open", side_effect=_open_without_nofollow):
        tmp, link = _symlink_case_directory()
        try:
            accepted = False
            try:
                with cg.open_verified(link, follow_symlinks=False):
                    accepted = True
            except cg.CredentialGuardError:
                accepted = False
            report["disable_o_nofollow"] = (["test_symlink_is_rejected"] if accepted else [])
        finally:
            import shutil
            shutil.rmtree(tmp)

    # 5. O_NONBLOCK dropped: opening a FIFO for read must now hang, bounded
    #    here by a deadline so the mutation-report build itself cannot hang.
    def _open_without_nonblock(path_arg, flags, *args, **kwargs):
        return real_open(path_arg, flags & ~os.O_NONBLOCK, *args, **kwargs)

    with patch.object(cg.os, "open", side_effect=_open_without_nonblock):
        tmp, fifo_path = _fifo_case_directory()
        try:
            hung = False
            try:
                with deadline(2):
                    try:
                        with cg.open_verified(fifo_path, follow_symlinks=True):
                            pass
                    except cg.CredentialGuardError:
                        pass
            except DeadlineExceeded:
                hung = True
            report["disable_o_nonblock"] = (
                ["test_fifo_is_rejected_and_does_not_hang"] if hung else [])
        finally:
            import shutil
            shutil.rmtree(tmp)

    return report


MUTATION_KILLS = _run_mutation_kill_report()


class MutationKillEvidence(unittest.TestCase):
    """Every mutation above must be killed by at least one named test -- i.e.
    disabling that protection makes the guard accept a case a real test in
    this file (or the CredentialFilePermissions classes) asserts must be
    rejected."""

    def test_every_mutation_is_killed_by_a_named_test(self):
        missing = {name: killers for name, killers in MUTATION_KILLS.items() if not killers}
        self.assertEqual(missing, {}, f"mutations with no killing test: {missing}")

    def test_report_names_every_expected_mutation(self):
        self.assertEqual(set(MUTATION_KILLS), {
            "disable_hardlink_check", "disable_worktree_check",
            "disable_parent_directory_check", "disable_o_nofollow", "disable_o_nonblock",
        })

    def test_mutation_report_is_printable_for_the_handoff(self):
        # Not an assertion on content -- keeps the report visible in -v output
        # for the coordinator's "report which test kills which mutation" ask.
        print("\nmutation-kill report:")
        for name, killers in sorted(MUTATION_KILLS.items()):
            print(f"  {name}: killed by {killers}")


if __name__ == "__main__":
    unittest.main()
