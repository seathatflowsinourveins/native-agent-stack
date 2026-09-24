"""Deterministic race-simulation, targeted regression, and real mutation-kill
evidence for credential_guard.open_verified() (fix rounds 2026-09-24).

Real concurrent races are non-deterministic and would make this suite flaky
or slow (spin-loop threads racing a real attacker window). Most tests here
instead inject a synchronous filesystem mutation at an exact point in the
traversal via `credential_guard._hook`, a module attribute that is a no-op in
production and is monkeypatched only by these tests. This reproduces exactly
what a real attacker's race would need to achieve (swap a symlink/FIFO/
different inode/ownership into a name between this module's check of that
name and its use of it) without relying on timing.

The `RealMutationKills` class at the bottom is different: it applies actual
textual source mutations to a private temporary copy of the whole
`blueprints/us-equities/adaptive-paper` tree and runs the actually-named
tests against that mutated copy in a subprocess (see
`tests/_credential_mutation_driver.py`). This replaces an earlier in-process
`MUTATION_KILLS` meta-test that only patched Python objects and asserted a
hardcoded string mapping without ever running the named tests -- flagged by
an independent security review as not establishing what it claimed to.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _credential_mutation_driver as driver  # noqa: E402

CG = "blueprints/us-equities/adaptive-paper/credential_guard.py"
MR = "blueprints/us-equities/adaptive-paper/market_research.py"
RUNNER = "blueprints/us-equities/adaptive-paper/runner.py"


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


def _open_fd_count():
    return len(os.listdir(f"/proc/{os.getpid()}/fd"))


class _FakeFstat:
    """Monkeypatches os.open (to remember the fd opened for one specific
    component name) and os.fstat (to return a modified stat_result for that
    fd only), so a test can simulate "this one ancestor/file has different
    metadata" without touching process-wide os.getuid() or any other
    global -- the "patch fstat per fd, not process-wide getuid" the
    fix-round explicitly asked for (item 1's test and item 7(a))."""

    def __init__(self, target_name, *, uid=None, mode=None):
        self.target_name = target_name
        self.uid = uid
        self.mode = mode
        self.target_fd = None
        self._real_open = os.open
        self._real_fstat = os.fstat

    def _open(self, name, flags, *args, **kwargs):
        fd = self._real_open(name, flags, *args, **kwargs)
        if name == self.target_name:
            self.target_fd = fd
        return fd

    def _fstat(self, fd, *args, **kwargs):
        info = self._real_fstat(fd, *args, **kwargs)
        if fd == self.target_fd:
            values = list(info)
            if self.mode is not None:
                values[0] = self.mode
            if self.uid is not None:
                values[4] = self.uid
            return os.stat_result(tuple(values[:10]))
        return info

    def __enter__(self):
        self._open_patch = patch.object(cg.os, "open", side_effect=self._open)
        self._fstat_patch = patch.object(cg.os, "fstat", side_effect=self._fstat)
        self._open_patch.start()
        self._fstat_patch.start()
        return self

    def __exit__(self, *exc):
        self._open_patch.stop()
        self._fstat_patch.stop()


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
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:"):
            cg.open_verified(path, follow_symlinks=True)

    def test_final_component_swapped_to_symlink_mid_traversal_fails_closed(self):
        path = _write_env(self.root)
        attacker_target = self.root / "attacker.env"
        _write_env(self.root, name="attacker.env")

        def swap():
            path.unlink()
            os.symlink(attacker_target, path)

        self._fire_once("pre_file_open", path.name, swap)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:"):
            cg.open_verified(path, follow_symlinks=True)

    def test_final_component_swapped_to_fifo_mid_traversal_fails_closed_and_does_not_hang(self):
        path = _write_env(self.root)

        def swap():
            path.unlink()
            os.mkfifo(path, mode=0o600)

        self._fire_once("pre_file_open", path.name, swap)
        with deadline(5):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:not_regular"):
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
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:mode"):
            cg.open_verified(path, follow_symlinks=True)

    def test_worktree_marker_added_just_before_ancestor_open_is_caught_by_the_per_fd_check(self):
        # Item 7(b): proves the worktree check runs at the moment each
        # ancestor's own fd is opened, not from a name list precomputed
        # before any traversal happened -- a by-name-precomputed check
        # (driver mutation "worktree_final_path_by_name") would have already
        # finished its scan before this hook could ever fire, and would
        # therefore miss a marker added here.
        sub = self.root / "sub"
        sub.mkdir(mode=0o700)
        path = _write_env(sub)

        def inject_git():
            (sub / ".git").mkdir()

        self._fire_once("pre_dir_open", "sub", inject_git)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:worktree"):
            cg.open_verified(path, follow_symlinks=True)

    def test_valid_configuration_is_unaffected_by_a_hook_that_never_fires(self):
        path = _write_env(self.root)
        with cg.open_verified(path, follow_symlinks=True) as handle:
            self.assertEqual(handle.read(), b"APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")


class AncestorRenameResistance(unittest.TestCase):
    """Fix-round item 1 (Codex, MEDIUM): the whole ancestor chain must be
    rename-resistant, OpenSSH `safe_path`/`secure_filename`-style -- not
    only the immediate parent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_attacker_writable_non_sticky_ancestor_is_rejected_even_when_the_parent_is_fine(self):
        # The reported scenario: /shared is attacker-writable (no sticky
        # bit); /shared/private is victim-owned 0700 with a compliant file.
        # The immediate parent (private) is perfectly fine -- the ancestor
        # above it is what must be refused, independent of what an attacker
        # later renames underneath it.
        shared = self.root / "shared"
        shared.mkdir(mode=0o777)  # writable by everyone, no sticky bit
        os.chmod(shared, 0o777)  # mkdir's mode is subject to umask; force the exact bits
        private = shared / "private"
        private.mkdir(mode=0o700)
        path = _write_env(private)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:ancestor"):
            cg.open_verified(path, follow_symlinks=True)

    def test_sticky_world_writable_ancestor_is_accepted_as_a_container(self):
        # The coordinator's required accepted configuration: a private
        # directory under /tmp (sticky, world-writable) still passes.
        shared = self.root / "tmp-like"
        shared.mkdir(mode=0o1777)  # sticky + world-writable, like /tmp
        os.chmod(shared, 0o1777)  # mkdir's mode is subject to umask; force the exact bits
        private = shared / "private"
        private.mkdir(mode=0o700)
        path = _write_env(private)
        with cg.open_verified(path, follow_symlinks=True) as handle:
            self.assertIn(b"fixture-key", handle.read())

    def test_group_writable_non_sticky_ancestor_two_levels_up_is_rejected(self):
        shared = self.root / "shared"
        shared.mkdir(mode=0o770)  # group-writable, no sticky bit
        os.chmod(shared, 0o770)  # mkdir's mode is subject to umask; force the exact bits
        private = shared / "sub" / "private"
        private.mkdir(mode=0o700, parents=True)
        os.chmod(shared / "sub", 0o700)
        path = _write_env(private)
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:ancestor"):
            cg.open_verified(path, follow_symlinks=True)

    def test_root_owned_ancestor_is_accepted(self):
        # Simulated: real root ownership isn't available to this test
        # process, so the immediate ancestor's fd metadata is faked via
        # _FakeFstat (per-fd, not process-wide getuid) to look root-owned --
        # covers the "under /home or /Users owned by root" accepted
        # configuration.
        home_like = self.root / "home-like"
        home_like.mkdir(mode=0o755)
        private = home_like / "me"
        private.mkdir(mode=0o700)
        path = _write_env(private)
        with _FakeFstat("home-like", uid=0):
            with cg.open_verified(path, follow_symlinks=True) as handle:
                self.assertIn(b"fixture-key", handle.read())

    def test_foreign_owned_non_root_ancestor_is_rejected(self):
        home_like = self.root / "not-mine"
        home_like.mkdir(mode=0o755)
        private = home_like / "me"
        private.mkdir(mode=0o700)
        path = _write_env(private)
        with _FakeFstat("not-mine", uid=os.getuid() + 1):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:ancestor"):
                cg.open_verified(path, follow_symlinks=True)


class NoPathLeakInErrors(unittest.TestCase):
    """Fix-round items 2 and 6 (both reviewers): a symlink loop's
    RuntimeError, an embedded-NUL ValueError, and a permission-error OSError
    must never leak a path -- not in the message, not in __context__, not in
    __cause__."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _assert_clean(self, ctx, *tell_tales):
        text = str(ctx.exception)
        for tell_tale in tell_tales:
            self.assertNotIn(tell_tale, text)
        self.assertIsNone(ctx.exception.__context__)
        self.assertIsNone(ctx.exception.__cause__)

    def test_missing_file_error_never_contains_the_path(self):
        with self.assertRaises(cg.CredentialGuardError) as ctx:
            cg.open_verified(self.root / "tell-tale-missing-name.env", follow_symlinks=True)
        self._assert_clean(ctx, "tell-tale-missing-name")
        self.assertRegex(str(ctx.exception), "credential_file_permissions:missing")

    def test_symlink_loop_error_never_contains_the_path(self):
        a = self.root / "loop-a-tell-tale"
        b = self.root / "loop-b-tell-tale"
        a.symlink_to(b)
        b.symlink_to(a)
        with self.assertRaises(cg.CredentialGuardError) as ctx:
            cg.open_verified(a, follow_symlinks=True)
        self._assert_clean(ctx, "loop-a-tell-tale", "loop-b-tell-tale")
        self.assertRegex(str(ctx.exception), "credential_file_permissions:symlink")

    def test_nul_byte_in_path_error_never_contains_the_path(self):
        bad = str(self.root / "tell-tale-nul-name") + "\x00" + "more"
        with self.assertRaises(cg.CredentialGuardError) as ctx:
            cg.open_verified(bad, follow_symlinks=False)
        self._assert_clean(ctx, "tell-tale-nul-name")

    def test_permission_error_never_contains_the_path(self):
        blocked = self.root / "blocked-tell-tale"
        blocked.mkdir(mode=0o700)
        inner = blocked / "inner"
        inner.mkdir(mode=0o700)
        path = _write_env(inner)
        os.chmod(blocked, 0o600)  # no execute bit: cannot traverse into it
        try:
            with self.assertRaises(cg.CredentialGuardError) as ctx:
                cg.open_verified(path, follow_symlinks=True)
            self._assert_clean(ctx, "blocked-tell-tale")
        finally:
            os.chmod(blocked, 0o700)


class DotDotIsRejected(unittest.TestCase):
    """Fix-round item 3 (both reviewers): a `..` component must never be
    lexically collapsed for follow_symlinks=False -- that would silently
    skip inspecting an intermediate symlinked component, contradicting "a
    symlinked component is always refused"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dotdot_through_a_symlinked_component_is_refused_not_normalized_away(self):
        safe = self.root / "safe"
        safe.mkdir(mode=0o700)
        _write_env(safe, name="paper.env")
        link = self.root / "link"
        link.symlink_to(safe)
        # Lexically, "root/link/../paper.env" normalizes to "root/paper.env"
        # -- a file that does not even exist here -- without ever visiting
        # "link". The guard must refuse the ".." component outright instead.
        path = link / ".." / "paper.env"
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:symlink"):
            cg.open_verified(path, follow_symlinks=False)

    def test_plain_dotdot_with_no_symlink_involved_is_still_refused(self):
        sub = self.root / "sub"
        sub.mkdir(mode=0o700)
        _write_env(self.root, name="paper.env")
        path = sub / ".." / "paper.env"
        with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:symlink"):
            cg.open_verified(path, follow_symlinks=False)


class FdOpenFailureCleanup(unittest.TestCase):
    """Fix-round item 4 (Codex, LOW): if fdopen() fails after the file
    descriptor is otherwise fully verified, the descriptor must not leak."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fd_is_closed_when_wrapping_the_verified_descriptor_raises(self):
        # open_verified() builds io.FileIO(file_fd, ...) first (closefd=True,
        # so it now owns file_fd), then wraps that object in a
        # BufferedReader; simulate the wrapping step failing (e.g. an audit
        # hook) and confirm the already-constructed FileIO *object* is
        # closed -- never a bare os.close(file_fd), which risks a
        # double-close/EBADF or closing an unrelated, since-reused fd if
        # FileIO's own constructor is what fails instead.
        path = _write_env(self.root)
        before = _open_fd_count()
        with patch.object(cg.io, "BufferedReader", side_effect=OSError("simulated wrapping failure")):
            with self.assertRaises(OSError):
                cg.open_verified(path, follow_symlinks=True)
        after = _open_fd_count()
        self.assertEqual(before, after, "the verified descriptor leaked when wrapping it failed")


class FdLeakOnRefusal(unittest.TestCase):
    """Fix-round item 7(g): every refusal path must close every descriptor
    it opened -- not only the success path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _assert_no_leak(self, path, follow_symlinks=True):
        before = _open_fd_count()
        with self.assertRaises(cg.CredentialGuardError):
            cg.open_verified(path, follow_symlinks=follow_symlinks)
        after = _open_fd_count()
        self.assertEqual(before, after)

    def test_no_leak_on_missing_file(self):
        self._assert_no_leak(self.root / "does-not-exist.env")

    def test_no_leak_on_wrong_mode(self):
        self._assert_no_leak(_write_env(self.root, mode=0o644))

    def test_no_leak_on_hard_link(self):
        target = _write_env(self.root, name="real.env")
        os.link(target, self.root / "second.env")
        self._assert_no_leak(target)

    def test_no_leak_on_inside_worktree(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as inside:
            self._assert_no_leak(_write_env(Path(inside)))

    def test_no_leak_on_success_after_close(self):
        path = _write_env(self.root)
        before = _open_fd_count()
        with cg.open_verified(path, follow_symlinks=True) as handle:
            handle.read()
        after = _open_fd_count()
        self.assertEqual(before, after)


class RootMarkerIsChecked(unittest.TestCase):
    """Fix-round item 7(g): the root marker check ("/" itself, not only
    deeper ancestors) actually runs, not only "every ancestor below root"."""

    def test_root_fd_git_check_is_invoked(self):
        path = _write_env(tempfile.mkdtemp())
        calls = []
        real = cg._ancestor_has_git_entry

        def _spy(dir_fd):
            # fstat *inside* the spy: open_verified closes every ancestor fd
            # (including root_fd) in its `finally` block once traversal
            # finishes, so the fd is no longer valid by the time this
            # `with` block below exits -- record its identity now.
            calls.append(os.fstat(dir_fd))
            return real(dir_fd)

        with patch.object(cg, "_ancestor_has_git_entry", side_effect=_spy):
            with cg.open_verified(path, follow_symlinks=True) as handle:
                handle.read()
        self.assertGreaterEqual(len(calls), 1)
        # The first recorded fd must actually refer to "/" (same device and
        # inode), proving root itself is walked, not skipped as a special
        # case starting only at the first named component.
        root_info = os.stat(os.sep, follow_symlinks=False)
        self.assertEqual((root_info.st_dev, root_info.st_ino), (calls[0].st_dev, calls[0].st_ino))


class RootDirectoryOwnershipIsChecked(unittest.TestCase):
    """Fix-round-4 item 4: root's own ownership/mode check must actually be
    enforced, not merely invoked -- a simulated foreign-owned, world-writable
    "/" (via per-fd fstat faking, not a process-wide os.getuid() patch) must
    be rejected."""

    def test_foreign_owned_world_writable_root_is_rejected(self):
        path = _write_env(tempfile.mkdtemp())
        with _FakeFstat(os.sep, uid=os.getuid() + 1, mode=stat.S_IFDIR | 0o777):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:ancestor"):
                cg.open_verified(path, follow_symlinks=True)


class ForeignFileOwnerAloneIsRejected(unittest.TestCase):
    """Fix-round item 7(a): the file-owner check must be independently
    exercised -- not masked by a coincidentally-also-failing parent check.
    Simulated via per-fd fstat faking (item 1's required test technique),
    not a process-wide os.getuid() patch, so the parent's real ownership is
    genuinely unaffected."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_foreign_file_owner_is_rejected_with_a_correctly_owned_parent(self):
        path = _write_env(self.root)
        with _FakeFstat(path.name, uid=os.getuid() + 1):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:owner"):
                cg.open_verified(path, follow_symlinks=True)


class FstatNotPathnameStat(unittest.TestCase):
    """Fix-round item 7(f): rejection must be driven by fstat() on the
    opened descriptor, not a by-name stat() of the path -- a mutant that
    swapped in a by-name pre-stat (driver mutation
    "skip_fstat_use_prestat") would be fooled by a lying pathname stat that
    this test makes available."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.real_stat = os.stat

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejection_uses_the_fds_own_metadata_not_a_pathname_restat(self):
        path = _write_env(self.root, mode=0o644)  # actually non-compliant

        def _lying_stat(name, *args, **kwargs):
            real = self.real_stat(name, *args, **kwargs)
            if name == path.name:
                values = list(real)
                values[0] = stat.S_IFREG | 0o600  # lies: "this file is 0600"
                return os.stat_result(tuple(values[:10]))
            return real

        with patch.object(cg.os, "stat", side_effect=_lying_stat):
            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:mode"):
                cg.open_verified(path, follow_symlinks=True)


class BoundedReadIsActuallyBounded(unittest.TestCase):
    """Fix-round item 7(d): assert the *call contract* (the size argument
    each loader's read() call actually uses), not only the outcome -- a
    static oversized fixture rejects identically whether the implementation
    reads MAX+1 bytes or the whole file, so outcome alone does not establish
    boundedness."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _recording_open_verified(self, real_open_verified, sizes):
        def _wrapped(path, **kwargs):
            handle = real_open_verified(path, **kwargs)
            real_read = handle.read

            def _read(n=-1):
                sizes.append(n)
                return real_read(n)
            handle.read = _read
            return handle
        return _wrapped

    def test_market_research_reads_at_most_cap_plus_one(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("market_research_bound_check", SOURCE / "market_research.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        path = _write_env(self.root)
        sizes = []
        with patch.object(m, "open_verified", self._recording_open_verified(m.open_verified, sizes)):
            m.credentials(path)
        self.assertEqual(sizes, [m.MAX_CREDENTIAL_BYTES + 1])

    def test_runner_reads_at_most_cap_plus_one(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("runner_bound_check", SOURCE / "runner.py")
        try:
            r = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(r)
        except ImportError:
            self.skipTest("runner.py's optional native imports are unavailable")
            return
        path = _write_env(self.root)
        sizes = []
        with patch.object(r, "open_verified", self._recording_open_verified(r.open_verified, sizes)):
            r.credentials(path)
        self.assertEqual(sizes, [cg.MAX_CREDENTIAL_BYTES + 1])


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

            with self.assertRaisesRegex(cg.CredentialGuardError, "credential_file_permissions:"):
                cg.open_verified(victim_file, follow_symlinks=True)


# ---------------------------------------------------------------------------
# Real, subprocess-executed mutation-kill evidence (fix-round item 7(h)).
# Each mutation applies an exact-count textual change to a private temporary
# copy of the source tree and actually runs the named test id(s) against
# that copy -- "killed" means that subprocess genuinely exited non-zero.
# ---------------------------------------------------------------------------

MUTATIONS = {
    "disable_hardlink_check": {
        "mutation": [(CG, "    if info.st_nlink != 1:\n        raise CredentialGuardError(REASON_HARDLINK)\n",
                     "", 1)],
        "test_ids": ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_hard_link_is_rejected"],
        "extra_test_files": ["tests/test_adaptive_paper_runner.py"],
    },
    "disable_o_nofollow": {
        "mutation": [
            (CG, "os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY", "os.O_DIRECTORY | os.O_RDONLY", 1),
            (CG, "os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY",
                 "os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY", 1)],
        "test_ids": ["tests.test_adaptive_market_research.MarketResearchCredentialFilePermissions.test_symlink_is_rejected"],
        "extra_test_files": ["tests/test_adaptive_market_research.py"],
    },
    "disable_o_nonblock": {
        "mutation": [(CG, "os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY",
                          "os.O_RDONLY | os.O_NOFOLLOW | os.O_NOCTTY", 1)],
        "test_ids": ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_fifo_is_rejected_and_does_not_hang"],
        "extra_test_files": ["tests/test_adaptive_paper_runner.py"],
        "timeout": 30,
    },
    "disable_parent_directory_check": {
        # Genuinely skips the strict, non-sticky-excused parent check *only*
        # for the immediate parent (the non-parent ancestor branch, and the
        # root-is-parent branch, are untouched); "pass" rather than falling
        # into a shared branch that would also run the (looser, sticky-
        # excused) generic ancestor check, which for a world-writable,
        # non-sticky directory would still reject it for an unrelated
        # reason and mask whether the parent-specific rule was disabled.
        "mutation": [(CG, "            if is_immediate_parent:\n"
                          "                _check_parent_directory(os.fstat(current_fd))\n"
                          "            else:\n",
                          "            if is_immediate_parent:\n"
                          "                pass\n"
                          "            else:\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_world_writable_parent_directory_is_rejected"],
        "extra_test_files": ["tests/test_adaptive_paper_runner.py"],
    },
    "disable_worktree_check": {
        "mutation": [(CG, "    try:\n        os.stat(\".git\", dir_fd=dir_fd, follow_symlinks=False)\n        return True\n",
                          "    return False\n    try:\n        os.stat(\".git\", dir_fd=dir_fd, follow_symlinks=False)\n"
                          "        return True\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_inside_git_worktree_is_rejected"],
        "extra_test_files": ["tests/test_adaptive_paper_runner.py"],
    },
    "worktree_final_path_by_name": {
        # Removes only the loop-level (per-descendant-ancestor) fd-bound
        # worktree check, leaving the root-level one untouched -- simulates
        # a design that only scanned once, by name, before any traversal,
        # rather than at each opened ancestor's own inspection time. The
        # test's injected marker lands on a nested "sub" directory, only
        # reachable through the loop-level check this removes.
        "mutation": [
            (CG, "            if _ancestor_has_git_entry(current_fd):\n                raise CredentialGuardError(REASON_WORKTREE)\n",
                 "", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.HookInjectedRaces."
                     "test_worktree_marker_added_just_before_ancestor_open_is_caught_by_the_per_fd_check"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "skip_fstat_owner_identity": {
        "mutation": [(CG, "    if info.st_uid != os.getuid():\n        raise CredentialGuardError(REASON_OWNER)\n",
                          "", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.ForeignFileOwnerAloneIsRejected."
                     "test_foreign_file_owner_is_rejected_with_a_correctly_owned_parent"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "skip_fstat_use_prestat": {
        "mutation": [
            (CG, "        _hook(\"pre_file_open\", file_name)\n",
                 "        try:\n            _pre_info = os.stat(file_name, dir_fd=current_fd, follow_symlinks=False)\n"
                 "        except OSError:\n            raise CredentialGuardError(REASON_MISSING) from None\n"
                 "        _hook(\"pre_file_open\", file_name)\n", 1),
            (CG, "        info = os.fstat(file_fd)\n", "        info = _pre_info\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.FstatNotPathnameStat."
                     "test_rejection_uses_the_fds_own_metadata_not_a_pathname_restat"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "read_whole_file_market_research": {
        "mutation": [(MR, "raw = handle.read(MAX_CREDENTIAL_BYTES + 1)", "raw = handle.read()", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.BoundedReadIsActuallyBounded."
                     "test_market_research_reads_at_most_cap_plus_one"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "allow_ancestor_writable_without_sticky": {
        "mutation": [(CG, "    if (mode & _WRITABLE_BITS) != 0 and not (mode & stat.S_ISVTX):\n",
                          "    if False:\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.AncestorRenameResistance."
                     "test_attacker_writable_non_sticky_ancestor_is_rejected_even_when_the_parent_is_fine"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "normalize_dotdot_lexically": {
        "mutation": [(CG, "        if \"..\" in base.parts:\n            raise CredentialGuardError(REASON_SYMLINK)\n"
                          "        resolved = base\n",
                          "        resolved = Path(__import__(\"os\").path.normpath(str(base)))\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.DotDotIsRejected."
                     "test_dotdot_through_a_symlinked_component_is_refused_not_normalized_away"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "leak_fd_on_fdopen_failure": {
        "mutation": [(CG, "    raw = io.FileIO(file_fd, \"rb\", closefd=True)\n    try:\n"
                          "        return io.BufferedReader(raw)\n    except BaseException:\n"
                          "        raw.close()\n        raise\n",
                          "    raw = io.FileIO(file_fd, \"rb\", closefd=True)\n    return io.BufferedReader(raw)\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.FdOpenFailureCleanup."
                     "test_fd_is_closed_when_wrapping_the_verified_descriptor_raises"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "disable_root_ancestor_check": {
        "mutation": [(CG, "        if dir_names:\n"
                          "            _check_ancestor_directory(os.fstat(current_fd), reason_owner=REASON_ANCESTOR,\n"
                          "                                       reason_writable=REASON_ANCESTOR)\n"
                          "        else:\n"
                          "            # The file sits directly in \"/\" -- root is the immediate parent,\n"
                          "            # not merely a container ancestor, so the strict (not\n"
                          "            # sticky-excused) parent rule applies here too: this rejects\n"
                          "            # \"/file\" the same way it rejects \"/tmp/file\".\n"
                          "            _check_parent_directory(os.fstat(current_fd))\n",
                          "        pass\n", 1)],
        "test_ids": ["tests.test_adaptive_paper_credential_race.RootDirectoryOwnershipIsChecked."
                     "test_foreign_owned_world_writable_root_is_rejected"],
        "extra_test_files": ["tests/test_adaptive_paper_credential_race.py", "tests/_credential_mutation_driver.py"],
    },
    "disable_runner_size_check": {
        "mutation": [(RUNNER, "    if len(raw) > MAX_CREDENTIAL_BYTES:\n        raise SafetyError(REASON_SIZE)\n",
                             "", 1)],
        "test_ids": ["tests.test_adaptive_paper_runner.CredentialFilePermissions."
                     "test_oversized_file_is_rejected_not_silently_truncated_and_accepted"],
        "extra_test_files": ["tests/test_adaptive_paper_runner.py"],
    },
}


class MutationDriverSelfTests(unittest.TestCase):
    """Fix-round-4 item 2: the driver itself must not report a false kill.
    An empty mutation (no change at all) and a mutation that only breaks
    an unrelated import (never touching the rule under test) must both be
    reported "not killed" -- a sound driver requires a real "FAIL" on the
    named test id, not merely a non-zero subprocess exit."""

    def test_empty_mutation_is_not_a_kill(self):
        result = driver.run_mutation(
            "selftest-empty",
            [],
            ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_hard_link_is_rejected"],
            ["tests/test_adaptive_paper_runner.py"])
        self.assertFalse(result["killed"], result)

    def test_import_error_mutation_is_not_a_kill(self):
        result = driver.run_mutation(
            "selftest-import-error",
            [(CG, "import errno\n", "import errno_does_not_exist_at_all\n", 1)],
            ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_hard_link_is_rejected"],
            ["tests/test_adaptive_paper_runner.py"])
        self.assertFalse(result["killed"], result)
        self.assertIn(result["verdict"], ("not_collected", "error_not_fail"))

    def test_mistyped_test_id_is_not_a_kill(self):
        result = driver.run_mutation(
            "selftest-typo",
            [],
            ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_hard_link_is_rejectedd"],
            ["tests/test_adaptive_paper_runner.py"])
        self.assertFalse(result["killed"], result)

    def test_pristine_worktree_precondition_holds_in_the_copy(self):
        # The false kill fix-round 4 closed: disable_worktree_check's target
        # test asserts `(repo_root / ".git").exists()` as its own
        # precondition. Before `git init`-ing the copy, that assertion
        # failed on completely unmutated code, which the old "any non-zero
        # exit counts" rule miscounted as a kill.
        result = driver.run_mutation(
            "selftest-worktree-precondition",
            [],
            ["tests.test_adaptive_paper_runner.CredentialFilePermissions.test_inside_git_worktree_is_rejected"],
            ["tests/test_adaptive_paper_runner.py"])
        self.assertFalse(result["killed"], result)
        self.assertNotEqual(result.get("verdict"), "pristine_baseline_failed", result)


class RealMutationKills(unittest.TestCase):
    """Applies each mutation in MUTATIONS to a real temporary source copy
    and actually runs the named test(s) against it via subprocess: first on
    the pristine copy (must pass), then on the mutated copy. A mutation is
    only "killed" if a named test transitions to a genuine "FAIL" (never
    merely a non-zero exit, and never an "ERROR")."""

    @classmethod
    def setUpClass(cls):
        cls.report = {}
        for name, spec in MUTATIONS.items():
            result = driver.run_mutation(name, spec["mutation"], spec["test_ids"], spec["extra_test_files"],
                                         timeout=spec.get("timeout", 90))
            cls.report[name] = result

    def test_every_mutation_is_really_killed_by_the_named_test(self):
        not_killed = {name: r for name, r in self.report.items() if not r["killed"]}
        self.assertEqual(not_killed, {},
                         f"mutations NOT killed by their named test (a real FAIL, confirmed against a "
                         f"passing pristine baseline first): {not_killed}")

    def test_report_covers_every_declared_mutation(self):
        self.assertEqual(set(self.report), set(MUTATIONS))

    def test_mutation_report_is_printable_for_the_handoff(self):
        print("\nreal mutation-kill report (subprocess-executed, pristine-baseline-verified):")
        for name, result in sorted(self.report.items()):
            status = "KILLED" if result["killed"] else result.get("verdict", "SURVIVED").upper()
            print(f"  {name}: {status} (test_ids={result['test_ids']}, returncode={result['returncode']}, "
                 f"diff_lines={result['diff_lines']})")


if __name__ == "__main__":
    unittest.main()
