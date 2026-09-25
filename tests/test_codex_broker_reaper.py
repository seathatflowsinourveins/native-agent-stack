"""Exercise codex-broker-reaper's guards against real, live, synthetic processes.

Every fixture here is synthetic: a small Python stand-in plays the role of the
openai-codex plugin's `app-server-broker.mjs` (a real unix-socket server that
answers `broker/shutdown`, spawned with a script file literally named
`app-server-broker.mjs` so its real `/proc/<pid>/cmdline` matches guard (a)
exactly) and, separately, a live "claude" look-alike (comm forced to "claude"
via `prctl(PR_SET_NAME)`, since a Python process run as `python3 script.py`
reports comm == "python3", the interpreter's own name, not the script's --
checked by hand against the real ~/.local/bin/claude binary before writing
this suite; corrected in the 2026-09-25 fix round, see the tool's own
`is_claude_or_codex_process` docstring for why -- it is not shebang
rewriting). No real broker, no real Claude Code or Codex session, and no
plugin state directory on this host is ever acted on: every state/workspace
directory is a fresh tempfile.mkdtemp(), and `--state-root`/direct function
calls always point at that synthetic tree.

This suite spawns real processes and reads their live /proc/<pid> state
(cmdline, comm, cwd, stat, uptime) plus sets a process's name with
prctl(PR_SET_NAME) via ctypes -- all Linux-only, like the tool itself; see
LINUX_ONLY below (precedent: tests/test_adoption_bootstrap.py's
LINUX_X86_64_ONLY, applied there per-method since only some of that file's
tests are platform-specific -- applied here per-class since this whole
suite is).

Disclosed, fixed exception (fourth fix round, 2026-09-25), not hidden: every
`LiveCwdGuardTests` test that reaches guard (c) calls `evaluate_broker()`,
which calls the tool's own real `find_live_broker_pids()` -- a scan of this
HOST's actual `/proc` for every live `app-server-broker.mjs`, not only this
test's own fixtures. An earlier version of this suite left that scan
unrestricted, so a real broker already running on this host (this rollout's
own host was, 17 found, docs/decisions/2026-09-25-codex-broker-reaper.md),
or, worse, a live ancestor of this very test process (a coordinator
dispatching through `/codex:review` is itself a live broker's ancestor;
verified directly against this rollout's own process during review, not
only reasoned about), would have that real broker's own descendant set --
which can include this test process itself, and so every fixture it
spawned -- excluded from guard (c)'s live-session scan too, silently
swallowing a fixture a test means to prove BLOCKS eligibility. Fixed:
`LiveCwdGuardTests.setUp` patches `find_live_broker_pids` to filter its real
result down to this test's own spawned pids (`self._procs`) before guard
(c) ever sees it, so every test in that class stays hermetic regardless of
what else this host, or this test process's own ancestry, happens to be
running; see `test_find_live_broker_pids_is_restricted_to_this_tests_own_fixtures`
for a direct proof the patch itself does what it claims.
"""
from __future__ import annotations

import ctypes
import importlib.machinery
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "adoption/tools/codex-broker-reaper"

# This suite needs /proc (cmdline, comm, cwd, stat, uptime) and
# prctl(PR_SET_NAME); both are Linux-only, like the tool under test. Without
# this guard the *required* validate-macos CI check (.github/workflows/
# adoption-bootstrap.yml, gated by .github/main-ruleset.json) would run this
# whole module's `python3 -m unittest -v` on macos-15 and fail every class.
LINUX_ONLY = unittest.skipUnless(
    sys.platform.startswith("linux"),
    "codex-broker-reaper and this suite read /proc directly and are Linux-only",
)

FAKE_BROKER_SOURCE = '''
import json
import os
import socket
import subprocess
import sys

def main():
    argv = sys.argv[1:]
    endpoint = argv[argv.index("--endpoint") + 1]
    ignore_shutdown = "--ignore-shutdown" in argv
    child_proc = None
    if "--spawn-child" in argv:
        index = argv.index("--spawn-child")
        child_script, child_name = argv[index + 1], argv[index + 2]
        # Mimics app-server-broker.mjs's own non-detached `codex app-server`
        # child (app-server.mjs SpawnedCodexAppServerClient.initialize():
        # spawn("codex", ["app-server"], {cwd: this.cwd})): a direct child
        # of the broker, inheriting its cwd (no cwd= override here), alive
        # for the broker's whole lifetime.
        child_proc = subprocess.Popen([sys.executable, child_script, child_name])
    path = endpoint[len("unix:"):]
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    while True:
        conn, _ = server.accept()
        conn.settimeout(5)
        buffer = b""
        try:
            while b"\\n" not in buffer:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
        except socket.timeout:
            buffer = b""
        message = json.loads(buffer.decode("utf-8").strip()) if buffer.strip() else {}
        if message.get("method") == "broker/shutdown":
            conn.sendall((json.dumps({"id": message.get("id"), "result": {}}) + "\\n").encode("utf-8"))
            conn.close()
            if not ignore_shutdown:
                if child_proc is not None:
                    child_proc.kill()
                try:
                    os.unlink(path)
                except OSError:
                    pass
                sys.exit(0)
            continue
        conn.close()

if __name__ == "__main__":
    main()
'''

FAKE_SESSION_SOURCE = '''
import ctypes
import sys
import time

name = sys.argv[1].encode("utf-8")
ctypes.CDLL(None, use_errno=True).prctl(15, name, 0, 0, 0)  # PR_SET_NAME
while True:
    time.sleep(0.2)
'''


def load_module():
    # TOOL_PATH has no .py suffix (matching every other adoption/tools/*
    # script), so spec_from_file_location can't infer a loader from the
    # extension; build a SourceFileLoader explicitly instead.
    loader = importlib.machinery.SourceFileLoader("codex_broker_reaper", str(TOOL_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


module = load_module()


def wait_until(predicate, timeout=5.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def write_broker_json(state_dir: Path, *, endpoint: str, pid: int) -> None:
    (state_dir / "broker.json").write_text(json.dumps(
        {"endpoint": endpoint, "pidFile": None, "logFile": None, "sessionDir": None, "pid": pid}
    ))


def write_state_json(state_dir: Path, *, jobs: list) -> None:
    (state_dir / "state.json").write_text(json.dumps(
        {"version": 1, "config": {"stopReviewGate": False}, "jobs": jobs}
    ))


def iso(epoch: float) -> str:
    """A `Date.prototype.toISOString()`-style string for `epoch`, matching plugin timestamps."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ReaperTestCase(unittest.TestCase):
    """Common synthetic-fixture plumbing; no production path is ever touched."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._procs: list[subprocess.Popen] = []
        self.addCleanup(self._reap_all)

    def _reap_all(self):
        for proc in self._procs:
            if proc.poll() is None:
                try:
                    # start_new_session=True in spawn() makes each fixture
                    # its own process-group leader (mirroring Node's
                    # detached:true for the real broker); killing the whole
                    # group also cleans up any child the fixture spawned
                    # itself (spawn_fake_broker's spawn_child_named mimics
                    # the broker's own non-detached `codex app-server`
                    # child) without touching any other fixture's separate
                    # group or this test process's own group.
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass

    def spawn(self, source: str, script_name: str, args: list[str], *, cwd: Path) -> subprocess.Popen:
        script_path = self.root / script_name
        script_path.write_text(source)
        proc = subprocess.Popen(
            [sys.executable, str(script_path), *args],
            cwd=str(cwd),
            start_new_session=True,  # own process group, like Node's detached:true
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._procs.append(proc)
        # A real orphaned broker's original parent is already gone, so the
        # kernel has already reparented it to init, which reaps it the
        # instant it exits -- /proc/<pid> disappears right away. Here the
        # fake broker is a direct child of *this* test process, so without
        # reaping it ourselves it would sit as an unreaped zombie (whose
        # /proc/<pid> directory still exists) for the guard's whole exit-wait
        # window. Reap it in the background as soon as it exits, matching
        # init's behavior for the real orphaned case this tool targets.
        threading.Thread(target=proc.wait, daemon=True).start()
        return proc

    def spawn_fake_broker(self, *, cwd: Path, extra_args: list[str] | None = None,
                           spawn_child_named: str | None = None) -> tuple[subprocess.Popen, str]:
        sock_dir = tempfile.mkdtemp()  # short path: AF_UNIX sun_path is capped near 108 bytes
        self.addCleanup(lambda: shutil.rmtree(sock_dir, ignore_errors=True))
        sock_path = os.path.join(sock_dir, "broker.sock")
        endpoint = f"unix:{sock_path}"
        args = ["serve", "--endpoint", endpoint, *(extra_args or [])]
        if spawn_child_named:
            # A real broker's own `codex app-server` child (guard (c)'s
            # 2026-09-25 fix round target); written once per test (root is
            # per-test, from setUp's TemporaryDirectory).
            child_script = self.root / "fake-broker-child.py"
            if not child_script.exists():
                child_script.write_text(FAKE_SESSION_SOURCE)
            args += ["--spawn-child", str(child_script), spawn_child_named]
        proc = self.spawn(FAKE_BROKER_SOURCE, "app-server-broker.mjs", args, cwd=cwd)
        self.assertTrue(wait_until(lambda: os.path.exists(sock_path)), "fake broker never bound its socket")
        return proc, endpoint

    def spawn_fake_session(self, *, name: str, cwd: Path) -> subprocess.Popen:
        proc = self.spawn(FAKE_SESSION_SOURCE, "fake-session.py", [name], cwd=cwd)
        self.assertTrue(
            wait_until(lambda: module.read_proc_comm(proc.pid) == name),
            "fake session process never reported the forced comm",
        )
        return proc


@LINUX_ONLY
class PathIsUnderTests(ReaperTestCase):
    """path_is_under(): used by guard (c) for the workspace root, its git toplevel, and its worktree parent."""

    def test_normal_root_matches_itself_and_children_only(self):
        # "/home/example/..." (not a real user, scripts/validate.py's own
        # "personal home path" scan exempts "example"): plain string
        # literals, not this test's own tmp fixtures.
        self.assertTrue(module.path_is_under("/home/example/x", "/home/example/x"))
        self.assertTrue(module.path_is_under("/home/example/x/sub", "/home/example/x"))
        self.assertFalse(module.path_is_under("/home/example/y", "/home/example/x"))
        # A sibling that merely shares a string prefix must not match: the
        # separator-aware boundary check must not regress into a naive
        # substring test.
        self.assertFalse(module.path_is_under("/home/example/xylophone", "/home/example/x"))

    def test_filesystem_root_workspace_is_not_a_safety_hole(self):
        # Fix-round finding: with root "/", the old `root + os.sep` was
        # "//", which only the literal string "/" ever starts with -- so
        # path_is_under(anything, "/") returned False for every real
        # absolute path. Improbable in practice (a broker's workspace root
        # or nearest .git ancestor resolving to "/"), but wrong in the
        # unsafe direction for a live-session safety check.
        self.assertTrue(module.path_is_under("/", "/"))
        self.assertTrue(module.path_is_under("/home/example/anything", "/"))


@LINUX_ONLY
class PidReuseGuardTests(ReaperTestCase):
    """Guard (a): cmdline must still name app-server-broker.mjs serve --endpoint <same>."""

    def test_rejects_a_live_but_unrelated_process(self):
        # The test runner's own pid is real and alive, but it is plainly not
        # a broker; this is exactly the upstream #743 pid-reuse scenario --
        # a stale broker.json pid now belongs to something else entirely.
        self.assertFalse(module.broker_cmdline_matches(module.read_proc_cmdline(os.getpid()), "unix:/tmp/whatever.sock"))

    def test_accepts_a_live_matching_broker(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        self.assertTrue(module.broker_cmdline_matches(module.read_proc_cmdline(proc.pid), endpoint))
        # A different, still-correct-looking cmdline but the wrong endpoint must not match.
        self.assertFalse(module.broker_cmdline_matches(module.read_proc_cmdline(proc.pid), endpoint + "-different"))

    def test_evaluate_broker_reports_dead_pid_as_ineligible(self):
        state_dir = self.root / "workspace-slug-deadbeef"
        state_dir.mkdir()
        write_broker_json(state_dir, endpoint="unix:/tmp/does-not-exist.sock", pid=999999999)
        write_state_json(state_dir, jobs=[])
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["eligible"])
        self.assertFalse(record["guards"]["a_pid_cmdline_match"])
        self.assertIn("not running", record["reasons"][0])

    def test_evaluate_broker_reports_reused_pid_as_ineligible(self):
        # broker.json's pid is alive, but now belongs to this test process,
        # not to a broker -- must be refused, not treated as a match.
        state_dir = self.root / "workspace-slug-reused"
        state_dir.mkdir()
        write_broker_json(state_dir, endpoint="unix:/tmp/does-not-exist.sock", pid=os.getpid())
        write_state_json(state_dir, jobs=[])
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["eligible"])
        self.assertFalse(record["guards"]["a_pid_cmdline_match"])
        self.assertIn("pid reuse", record["reasons"][0])


@LINUX_ONLY
class RunningJobGuardTests(ReaperTestCase):
    """Guard (b): no job in state.json may have a non-terminal status."""

    def test_running_job_blocks_and_completed_allows(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-jobs"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)

        write_state_json(state_dir, jobs=[{"id": "fixture-job-1", "status": "running", "workspaceRoot": str(workspace)}])
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["guards"]["b_no_active_jobs"])
        self.assertFalse(record["eligible"])

        write_state_json(state_dir, jobs=[{"id": "fixture-job-1", "status": "completed", "workspaceRoot": str(workspace)}])
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["guards"]["b_no_active_jobs"])
        self.assertTrue(record["eligible"])  # workspace exists but no live session claims it; age 0 >= min_age 0

    def test_unrecognized_status_is_treated_as_active(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-unknown-status"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[{"id": "fixture-job-2", "status": "some-future-status"}])
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["guards"]["b_no_active_jobs"])
        self.assertFalse(record["eligible"])


@LINUX_ONLY
class LiveCwdGuardTests(ReaperTestCase):
    """Guard (c): workspace gone, or no live claude/codex process is under it."""

    def setUp(self):
        # Fourth fix round, 2026-09-25 (minor finding): every test below that
        # reaches guard (c) calls evaluate_broker() -> the tool's own real
        # find_live_broker_pids(), which scans this HOST's actual /proc for
        # every live app-server-broker.mjs, not only this test's own
        # fixtures -- see the module docstring above for the contamination
        # this can cause (a real host broker, or a live ancestor of this
        # very test process, swallowing this suite's own fixtures into that
        # broker's excluded descendant set). Patched here, not in the base
        # ReaperTestCase, since only this class's tests reach guard (c) with
        # a workspace directory that still exists (the branch that calls
        # find_live_broker_pids() at all). `fixture_pids` is read fresh on
        # every call, not captured once at patch time, so it reflects
        # whatever this test has spawned (via self._procs) by the time each
        # evaluate_broker() call actually runs, not only what existed when
        # setUp ran.
        super().setUp()
        real_find_live_broker_pids = module.find_live_broker_pids

        def fixture_only_find_live_broker_pids():
            fixture_pids = frozenset(proc.pid for proc in self._procs)
            return [pid for pid in real_find_live_broker_pids() if pid in fixture_pids]

        patcher = mock.patch.object(module, "find_live_broker_pids", fixture_only_find_live_broker_pids)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_find_live_broker_pids_is_restricted_to_this_tests_own_fixtures(self):
        # Direct proof the setUp patch above does what it claims, rather
        # than only reasoning about it: a second fake broker, deliberately
        # dropped from self._procs right after spawning, stands in for "a
        # real broker this test did not itself mean to exercise" (a real
        # host broker, or one reached only via a live ancestor of this test
        # process -- see the module docstring). The patched
        # find_live_broker_pids() must not return it, even though it is a
        # real, live process whose cmdline genuinely matches
        # is_broker_serve_cmdline (the UNPATCHED function, called directly
        # below, does find it).
        workspace = self.root / "workspace"
        workspace.mkdir()
        owned_proc, _ = self.spawn_fake_broker(cwd=workspace)

        other_workspace = self.root / "other-workspace"
        other_workspace.mkdir()
        other_proc, _ = self.spawn_fake_broker(cwd=other_workspace)
        self._procs.remove(other_proc)  # stand-in for a real, unrelated host broker

        def kill_other_proc():
            # Mirrors ReaperTestCase._reap_all's own tolerance for the
            # process already being gone by cleanup time; other_proc is no
            # longer in self._procs, so _reap_all itself will not reach it.
            try:
                os.killpg(os.getpgid(other_proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

        self.addCleanup(kill_other_proc)

        # The UNPATCHED scan (reimplemented from iter_pids + is_broker_serve_cmdline,
        # exactly what the real find_live_broker_pids() does, rather than calling
        # module.find_live_broker_pids() itself, which setUp has already patched)
        # must still see other_proc: it is a real, live process whose cmdline
        # genuinely matches. This confirms the assertNotIn below is because of
        # the patch, not because other_proc was never really running.
        unpatched_result = [
            pid for pid in module.iter_pids() if module.is_broker_serve_cmdline(module.read_proc_cmdline(pid))
        ]
        self.assertIn(other_proc.pid, unpatched_result)

        patched_result = module.find_live_broker_pids()
        self.assertIn(owned_proc.pid, patched_result)
        self.assertNotIn(other_proc.pid, patched_result)

    def test_live_claude_session_under_workspace_blocks_eligibility(self):
        workspace = self.root / "workspace"
        (workspace / "subdir").mkdir(parents=True)
        state_dir = self.root / "workspace-slug-live"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])

        # "equal to or under": the live session's cwd is a SUBdirectory of the workspace root.
        session_proc = self.spawn_fake_session(name="claude", cwd=workspace / "subdir")
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["guards"]["c_workspace_unused"])
        self.assertFalse(record["eligible"])

        session_proc.kill()
        session_proc.wait(timeout=5)
        self.assertTrue(wait_until(lambda: not module.process_exists(session_proc.pid)))
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["guards"]["c_workspace_unused"])
        self.assertTrue(record["eligible"])

    def test_unrelated_codex_session_elsewhere_does_not_block(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        state_dir = self.root / "workspace-slug-elsewhere"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])
        self.spawn_fake_session(name="codex", cwd=elsewhere)
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["guards"]["c_workspace_unused"])
        self.assertTrue(record["eligible"])

    def test_deleted_workspace_directory_is_unused_without_scanning_for_sessions(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-deleted"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["guards"]["c_workspace_unused"])
        self.assertIn("no longer exists", " ".join(record["reasons"]))
        self.assertTrue(record["eligible"])

    def test_brokers_own_codex_app_server_child_does_not_block_its_own_eligibility(self):
        # Regression (fix round, 2026-09-25): guard (c) must exclude the
        # broker's own descendants, not just its own pid, from the live-
        # session scan. The real plugin's broker always has exactly such a
        # child for its whole lifetime (app-server-broker.mjs ->
        # CodexAppServerClient.connect -> a non-detached `codex app-server`,
        # spawned with the broker's own cwd -- app-server.mjs
        # SpawnedCodexAppServerClient.initialize()); before the fix, that
        # child's cwd == the workspace root always looked like a live
        # session, so a live orphan whose workspace directory still exists
        # (the common retained-worktree case) could never become eligible.
        # The other guard (c) tests' fake broker spawns no child at all,
        # which is why this needs its own test with spawn_child_named.
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-own-child"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=workspace, spawn_child_named="codex")
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])

        def child_is_alive():
            return any(
                module.read_proc_comm(candidate) == "codex"
                for candidate in module.collect_child_pids(broker_proc.pid)
            )

        self.assertTrue(wait_until(child_is_alive), "fake broker never spawned its own fake codex child")
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["guards"]["c_workspace_unused"])
        self.assertTrue(record["eligible"])

        # An unrelated live session elsewhere must still not block (proves
        # the fix excludes only the broker's own descendants, not every
        # codex-named process).
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        self.spawn_fake_session(name="codex", cwd=elsewhere)
        still_unused = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(still_unused["eligible"])

        # A genuine live session under the SAME workspace must still block
        # (proves the fix does not over-exclude: this session is a child of
        # the *test process*, not of the broker, so collect_descendant_pids
        # must not sweep it in).
        self.spawn_fake_session(name="claude", cwd=workspace)
        blocked = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(blocked["guards"]["c_workspace_unused"])
        self.assertFalse(blocked["eligible"])

    def test_review_broker_in_a_git_subdirectory_is_blocked_by_a_session_at_the_checkout_root(self):
        # Disclosed, fix-round-mitigated gap (docs/decisions/2026-09-25-
        # codex-broker-reaper.md, "Known limitations"): a *review* command's
        # broker is spawned with the raw command cwd (codex-companion.mjs
        # resolveCommandCwd), which can be a subdirectory of the git
        # checkout a live session actually started from, rather than that
        # checkout root (only task-run brokers get resolveWorkspaceRoot's
        # git-toplevel cwd). Guard (c) also checks the workspace root's
        # nearest .git-bearing ancestor for a live session to cover this.
        checkout = self.root / "checkout"
        subdir = checkout / "sub" / "dir"
        subdir.mkdir(parents=True)
        (checkout / ".git").mkdir()  # enough for find_git_toplevel; no real git needed
        state_dir = self.root / "workspace-slug-subdir-broker"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=subdir)
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])

        # No session anywhere yet: the subdirectory workspace looks unused.
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["eligible"])

        # A live session at the checkout ROOT (not the broker's own
        # subdirectory cwd) must still block, via the git-toplevel check.
        self.spawn_fake_session(name="claude", cwd=checkout)
        blocked = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(blocked["guards"]["c_workspace_unused"])
        self.assertFalse(blocked["eligible"])
        self.assertIn(str(checkout), " ".join(blocked["reasons"]))

    def test_a_live_session_at_the_worktrees_main_checkout_blocks_eligibility(self):
        # Fix-round finding (major): a coordinator that dispatches into a
        # worktree by prefixing every Bash command with `cd <worktree> &&`
        # -- rather than changing its own OS process cwd -- never itself has
        # a cwd under the worktree at all, so before this fix neither the
        # workspace-root nor git-toplevel scan above could ever see it.
        # Simulates a real `git worktree add` layout with plain directories
        # and a hand-written `.git` pointer file (no real git needed, same
        # style as the checkout-root test above): `main_checkout` stands in
        # for the repository the coordinating session was launched from,
        # `worktree` for the linked worktree the broker's own cwd is set to.
        main_checkout = self.root / "main-checkout"
        main_checkout.mkdir()
        (main_checkout / ".git").mkdir()
        worktree = self.root / "worktree"
        worktree.mkdir()
        (worktree / ".git").write_text(f"gitdir: {main_checkout}/.git/worktrees/demo\n")
        state_dir = self.root / "workspace-slug-worktree"
        state_dir.mkdir()
        broker_proc, endpoint = self.spawn_fake_broker(cwd=worktree)
        write_broker_json(state_dir, endpoint=endpoint, pid=broker_proc.pid)
        write_state_json(state_dir, jobs=[])

        # No session anywhere yet: the worktree looks unused, same as any
        # other workspace with no live process under it.
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(record["eligible"])

        # A live session at the worktree's MAIN checkout (not the worktree
        # itself, and not reachable via find_git_toplevel(worktree), which
        # only ever resolves back to the worktree's own root) must still
        # block, via the worktree-to-parent check.
        self.spawn_fake_session(name="claude", cwd=main_checkout)
        blocked = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(blocked["guards"]["c_workspace_unused"])
        self.assertFalse(blocked["eligible"])
        self.assertIn(str(main_checkout), " ".join(blocked["reasons"]))

    def test_two_orphaned_brokers_of_one_repository_do_not_block_each_other(self):
        # Regression (major finding, third fix round, 2026-09-25): guard (c)
        # excluded only the EVALUATED broker's own descendants. Once guard
        # (c) also scans a worktree's main-checkout parent
        # (read_worktree_parent_root, second fix round above), that left
        # every OTHER live broker's own `codex app-server` child looking
        # like a live session. Two orphaned brokers of one repository then
        # permanently blocked each other: a main-checkout broker and a
        # worktree broker nested under it (Claude Code's own
        # `.claude/worktrees/<name>/` layout -- reproduced here with a
        # hand-written `.git` pointer file, no real `git worktree` needed,
        # same style as the tests above) each found the OTHER's app-server
        # child as a "live" pid -- the main broker's child's cwd IS the
        # main checkout (found directly by the worktree broker's own
        # worktree-parent scan), and the worktree broker's child's cwd is
        # nested under the main checkout (found by the main broker's own
        # plain workspace-root scan).
        main_checkout = self.root / "main-checkout"
        main_checkout.mkdir()
        (main_checkout / ".git").mkdir()
        worktree = main_checkout / ".claude" / "worktrees" / "demo"
        worktree.mkdir(parents=True)
        (worktree / ".git").write_text(f"gitdir: {main_checkout}/.git/worktrees/demo\n")

        main_state_dir = self.root / "workspace-slug-main-checkout"
        main_state_dir.mkdir()
        main_broker, main_endpoint = self.spawn_fake_broker(cwd=main_checkout, spawn_child_named="codex")
        write_broker_json(main_state_dir, endpoint=main_endpoint, pid=main_broker.pid)
        write_state_json(main_state_dir, jobs=[])

        worktree_state_dir = self.root / "workspace-slug-worktree"
        worktree_state_dir.mkdir()
        worktree_broker, worktree_endpoint = self.spawn_fake_broker(cwd=worktree, spawn_child_named="codex")
        write_broker_json(worktree_state_dir, endpoint=worktree_endpoint, pid=worktree_broker.pid)
        write_state_json(worktree_state_dir, jobs=[])

        def child_is_alive(broker_proc):
            return any(
                module.read_proc_comm(candidate) == "codex"
                for candidate in module.collect_child_pids(broker_proc.pid)
            )

        self.assertTrue(wait_until(lambda: child_is_alive(main_broker)), "main-checkout broker never spawned its fake codex child")
        self.assertTrue(wait_until(lambda: child_is_alive(worktree_broker)), "worktree broker never spawned its fake codex child")

        # Neither broker is blocked by the OTHER's own app-server child.
        main_record = module.evaluate_broker(main_state_dir, min_age=0.0, now=time.time())
        worktree_record = module.evaluate_broker(worktree_state_dir, min_age=0.0, now=time.time())
        self.assertTrue(main_record["guards"]["c_workspace_unused"])
        self.assertTrue(main_record["eligible"])
        self.assertTrue(worktree_record["guards"]["c_workspace_unused"])
        self.assertTrue(worktree_record["eligible"])

        # A genuine live session (not a broker) at the shared main checkout
        # must still block BOTH brokers -- proves the fix excludes only
        # live brokers' own descendants, not every codex-named process.
        self.spawn_fake_session(name="claude", cwd=main_checkout)
        main_blocked = module.evaluate_broker(main_state_dir, min_age=0.0, now=time.time())
        worktree_blocked = module.evaluate_broker(worktree_state_dir, min_age=0.0, now=time.time())
        self.assertFalse(main_blocked["guards"]["c_workspace_unused"])
        self.assertFalse(main_blocked["eligible"])
        self.assertFalse(worktree_blocked["guards"]["c_workspace_unused"])
        self.assertFalse(worktree_blocked["eligible"])

    def test_read_worktree_parent_root_resolves_a_relative_gitdir(self):
        # Regression (minor finding, third fix round, 2026-09-25): git
        # writes a relative `gitdir:` line relative to the directory
        # holding the `.git` FILE itself (git 2.48+'s
        # worktree.useRelativePaths / `git worktree add --relative-paths`),
        # not relative to this process's own cwd. Unresolved, the returned
        # parent stayed relative and never matched an absolute /proc cwd in
        # path_is_under(), silently dropping the worktree-parent protection
        # for such a worktree.
        main_checkout = self.root / "main-checkout"
        main_checkout.mkdir()
        (main_checkout / ".git").mkdir()
        worktree = self.root / "nested" / "worktree"
        worktree.mkdir(parents=True)
        relative_gitdir = os.path.relpath(main_checkout / ".git" / "worktrees" / "demo", start=worktree)
        (worktree / ".git").write_text(f"gitdir: {relative_gitdir}\n")

        resolved = module.read_worktree_parent_root(str(worktree))
        self.assertEqual(resolved, str(main_checkout))

    def test_read_worktree_parent_root_ignores_a_normal_checkout(self):
        # A normal checkout's (or the repository's own main worktree's)
        # `.git` is a directory, not a `gitdir:` pointer file; must not be
        # misread as a linked worktree.
        normal = self.root / "normal-checkout"
        (normal / ".git").mkdir(parents=True)
        self.assertIsNone(module.read_worktree_parent_root(str(normal)))
        # No `.git` at all: also None, not an error.
        no_git = self.root / "no-git"
        no_git.mkdir()
        self.assertIsNone(module.read_worktree_parent_root(str(no_git)))


@LINUX_ONLY
class MinAgeGuardTests(ReaperTestCase):
    """Guard (d): broker process age, from /proc/<pid>/stat, not a file mtime."""

    def test_fresh_broker_fails_a_large_min_age_and_passes_a_zero_one(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-age"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])

        old_enough = module.evaluate_broker(state_dir, min_age=3600.0, now=time.time())
        self.assertFalse(old_enough["guards"]["d_min_age"])
        self.assertFalse(old_enough["eligible"])
        self.assertIsNotNone(old_enough["age_seconds"])
        self.assertLess(old_enough["age_seconds"], 3600.0)

        young_enough = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertTrue(young_enough["guards"]["d_min_age"])

    def test_process_start_epoch_matches_wall_clock_within_a_couple_seconds(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        before = time.time()
        proc, _ = self.spawn_fake_broker(cwd=workspace)
        started = module.process_start_epoch(proc.pid)
        self.assertIsNotNone(started)
        self.assertGreaterEqual(started, before - 2.0)
        self.assertLessEqual(started, time.time() + 2.0)

    def test_age_is_correct_even_with_an_artificially_stale_reference_time(self):
        # A fix-round review finding alleged age is "overstated by the
        # elapsed evaluation time" because run() passes one `now`, captured
        # once, as both process_start_epoch's `reference` and the external
        # age subtrahend. Checked against the source (not just re-argued):
        # algebraically that cancels exactly --
        #   age = now - started = now - ((now - uptime) + ticks/clk)
        #       = uptime - ticks/clk
        # -- which does not depend on `now`/`reference` at all; it is always
        # the broker's true instantaneous age as of the live /proc/uptime
        # read, not a value skewed by how stale the caller's `now` is.
        # Proven here with a reference an hour stale, far beyond any real
        # scan lag, so a real dependence on `reference` would be unmissable.
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-stale-reference"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])

        stale_reference = time.time() - 3600.0  # 1 hour stale
        record = module.evaluate_broker(state_dir, min_age=0.0, now=stale_reference)
        self.assertIsNotNone(record["age_seconds"])
        # True age is close to 0 (the broker was just spawned); a real
        # staleness bug of the kind alleged would shift this by ~3600s.
        self.assertGreaterEqual(record["age_seconds"], 0.0)
        self.assertLess(record["age_seconds"], 5.0)


@LINUX_ONLY
class JobIdleGuardTests(ReaperTestCase):
    """Guard (e): time since the most recent recorded job activity, not just broker-process age."""

    def _patch_process_start_epoch(self, epoch: float) -> None:
        # Guard (d)'s age is deliberately independent of the caller's `now`
        # (see MinAgeGuardTests.test_age_is_correct_even_with_an_
        # artificially_stale_reference_time's algebra: `now` cancels out of
        # process_start_epoch's own math), so a synthetic future `now` alone
        # cannot make guard (d) see a large age in a fast unit test. Guard
        # (e) must be isolated from guard (d) some other way: monkeypatch
        # process_start_epoch directly, matching this file's established
        # pattern for deterministic sub-second simulation of time-dependent
        # guards (e.g. ApplyAndEscalationTests' os.getpgid/read_proc_cmdline
        # monkeypatches above).
        original = module.process_start_epoch
        module.process_start_epoch = lambda pid, reference=None: epoch
        self.addCleanup(setattr, module, "process_start_epoch", original)

    def test_recent_job_activity_blocks_even_when_the_broker_process_looks_old(self):
        # Fix-round finding (major): guard (d) alone only measures the
        # broker PROCESS's own age, so a broker that has been running for
        # hours but did a job a minute ago was already eligible once guard
        # (d)'s min-age passed -- even though the workspace was plainly
        # still in active use moments before.
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-recent-job"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        shutil.rmtree(workspace)  # guard c satisfied regardless of live-process scan timing
        now = time.time()
        write_state_json(state_dir, jobs=[
            {"id": "fixture-job-recent", "status": "completed", "updatedAt": iso(now - 10.0)}
        ])
        self._patch_process_start_epoch(now - 7200.0)  # broker process looks 2h old

        record = module.evaluate_broker(state_dir, min_age=3600.0, now=now)
        self.assertTrue(record["guards"]["d_min_age"])         # broker process looks old enough
        self.assertTrue(record["guards"]["b_no_active_jobs"])  # the job itself is "completed"
        self.assertFalse(record["guards"]["e_job_idle"])       # but activity was 10s ago
        self.assertFalse(record["eligible"])
        self.assertIn("guard e failed", " ".join(record["reasons"]))

    def test_old_job_activity_allows_once_past_min_age(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-old-job"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        shutil.rmtree(workspace)
        now = time.time()
        write_state_json(state_dir, jobs=[
            {"id": "fixture-job-old", "status": "completed", "updatedAt": iso(now - 9000.0)}
        ])
        self._patch_process_start_epoch(now - 7200.0)

        record = module.evaluate_broker(state_dir, min_age=3600.0, now=now)
        self.assertTrue(record["guards"]["d_min_age"])
        self.assertTrue(record["guards"]["e_job_idle"])
        self.assertTrue(record["eligible"])

    def test_no_job_timestamp_leaves_guard_d_as_the_sole_age_signal(self):
        # A broker that has never run a job (or whose job dicts predate this
        # guard) has no activity timestamp at all; guard (e) must pass
        # trivially rather than block forever, leaving guard (d) exactly as
        # capable as before this guard existed (disclosed residual gap: see
        # docs/decisions/2026-09-25-codex-broker-reaper.md).
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-no-job-timestamp"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        shutil.rmtree(workspace)
        write_state_json(state_dir, jobs=[])  # never ran a job
        now = time.time()
        self._patch_process_start_epoch(now - 7200.0)

        record = module.evaluate_broker(state_dir, min_age=3600.0, now=now)
        self.assertTrue(record["guards"]["d_min_age"])
        self.assertTrue(record["guards"]["e_job_idle"])
        self.assertIn("no job activity timestamp recorded", " ".join(record["reasons"]))
        self.assertTrue(record["eligible"])


@LINUX_ONLY
class MalformedStateTests(ReaperTestCase):
    """One broker's malformed on-disk state must never crash evaluation of the rest."""

    def test_broker_json_that_is_not_an_object_is_ineligible_not_a_crash(self):
        # Fix-round finding: broker.json that parses as valid JSON but is
        # not an object (e.g. a bare list) used to crash evaluate_broker at
        # `broker.get(...)` with an uncaught AttributeError.
        state_dir = self.root / "workspace-slug-non-object"
        state_dir.mkdir()
        (state_dir / "broker.json").write_text(json.dumps([1, 2, 3]))
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["eligible"])
        self.assertIn("does not contain a JSON object", " ".join(record["reasons"]))

    def test_non_utf8_broker_json_is_ineligible_not_a_crash(self):
        # Fix-round finding: a non-UTF-8 broker.json used to raise an
        # uncaught UnicodeDecodeError (not caught by the old `except
        # (OSError, json.JSONDecodeError)`), crashing the whole evaluation.
        state_dir = self.root / "workspace-slug-non-utf8"
        state_dir.mkdir()
        (state_dir / "broker.json").write_bytes(b"\xff\xfe\x00not valid utf-8")
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["eligible"])
        self.assertIn("cannot read broker.json", " ".join(record["reasons"]))

    def test_non_utf8_state_json_is_ineligible_not_a_crash(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        state_dir = self.root / "workspace-slug-state-non-utf8"
        state_dir.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        (state_dir / "state.json").write_bytes(b"\xff\xfe\x00not valid utf-8")
        record = module.evaluate_broker(state_dir, min_age=0.0, now=time.time())
        self.assertFalse(record["guards"]["b_no_active_jobs"])
        self.assertFalse(record["eligible"])
        self.assertIn("cannot read state.json", " ".join(record["reasons"]))

    def test_safe_evaluate_broker_never_raises_and_run_continues_past_a_broken_broker(self):
        # The outer safety net: run()/main() must keep evaluating every
        # OTHER broker even when one directory's state is broken in a way
        # evaluate_broker() itself does not anticipate (simulated here via
        # monkeypatching, deterministic rather than constructing a real
        # never-anticipated failure mode).
        state_root = self.root / "state"
        broken_dir = state_root / "workspace-slug-broken"
        broken_dir.mkdir(parents=True)
        write_broker_json(broken_dir, endpoint="unix:/tmp/does-not-exist.sock", pid=999999999)
        write_state_json(broken_dir, jobs=[])

        healthy_dir = state_root / "workspace-slug-healthy"
        healthy_dir.mkdir(parents=True)
        write_broker_json(healthy_dir, endpoint="unix:/tmp/also-does-not-exist.sock", pid=999999998)
        write_state_json(healthy_dir, jobs=[])

        original_evaluate = module.evaluate_broker

        def flaky_evaluate(broker_dir, *, min_age, now):
            if broker_dir.name == "workspace-slug-broken":
                raise RuntimeError("simulated unexpected failure")
            return original_evaluate(broker_dir, min_age=min_age, now=now)

        module.evaluate_broker = flaky_evaluate
        self.addCleanup(setattr, module, "evaluate_broker", original_evaluate)

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--list", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report["summary"]["total"], 2)
        by_dir = {record["state_dir"]: record for record in report["brokers"]}
        broken_record = by_dir[str(broken_dir)]
        self.assertFalse(broken_record["eligible"])
        self.assertIn("unexpected error evaluating this broker", " ".join(broken_record["reasons"]))
        # The healthy broker was still evaluated normally (both dead pids
        # here, so both are ineligible at guard (a), but its own real reason
        # -- not the broken one's fallback -- must show up).
        healthy_record = by_dir[str(healthy_dir)]
        self.assertIn("not running", " ".join(healthy_record["reasons"]))


@LINUX_ONLY
class ReceiptShapeTests(ReaperTestCase):
    def test_list_mode_receipt_shape_and_file_written(self):
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-receipt"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[{"id": "fixture-job-3", "status": "queued"}])
        receipt_path = self.root / "receipt.json"

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main([
                "--list", "--state-root", str(state_root), "--receipt", str(receipt_path),
            ])
        self.assertEqual(exit_code, 0)
        printed = json.loads(buffer.getvalue())
        on_disk = json.loads(receipt_path.read_text())
        self.assertEqual(printed, on_disk)

        for key in ("tool", "generated_at", "mode", "min_age_seconds", "escalate", "state_roots",
                    "mem_available_kib_before", "mem_available_kib_after", "brokers", "summary"):
            self.assertIn(key, on_disk)
        self.assertEqual(on_disk["mode"], "list")
        self.assertEqual(on_disk["summary"]["total"], 1)
        self.assertEqual(on_disk["summary"]["eligible"], 0)  # the queued job blocks it
        broker_record = on_disk["brokers"][0]
        for key in ("state_dir", "broker_json", "endpoint", "pid", "job_count", "workspace_root",
                    "age_seconds", "guards", "reasons", "eligible", "action", "rpc_result", "exit_observed"):
            self.assertIn(key, broker_record)
        self.assertEqual(broker_record["action"], "none")
        # --list must not have touched the broker.
        self.assertTrue(module.process_exists(proc.pid))

    def test_list_mode_with_an_eligible_broker_still_exits_zero(self):
        # Regression: exit_observed is None (not-attempted) for every record
        # under --list, including an eligible one, since stop_broker() is
        # never called in list mode. failed_to_stop must not be derived from
        # "eligible and exit_observed is not True" without also gating on
        # apply mode, or a pure dry run with an eligible broker would wrongly
        # report a stop failure and exit 2.
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-eligible-list"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)  # guard c satisfied; min-age 0 satisfies guard d

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--list", "--min-age", "0", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report["summary"]["eligible"], 1)
        self.assertEqual(report["summary"]["failed_to_stop"], 0)
        self.assertEqual(report["summary"]["stopped"], 0)
        record = report["brokers"][0]
        self.assertTrue(record["eligible"])
        self.assertEqual(record["action"], "none")
        self.assertIsNone(record["exit_observed"])
        self.assertTrue(module.process_exists(proc.pid))  # --list touched nothing

    def test_apply_mode_never_touches_an_ineligible_broker(self):
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-ineligible"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[{"id": "fixture-job-4", "status": "running"}])

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--apply", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report["summary"]["eligible"], 0)
        self.assertEqual(report["brokers"][0]["action"], "none")
        self.assertTrue(module.process_exists(proc.pid))


@LINUX_ONLY
class ApplyAndEscalationTests(ReaperTestCase):
    def test_apply_stops_an_eligible_broker_via_rpc_alone(self):
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-stop"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)  # guard c satisfied without depending on process-scan timing
        receipt_path = self.root / "receipt.json"

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main([
                "--apply", "--min-age", "0", "--state-root", str(state_root), "--receipt", str(receipt_path),
            ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(wait_until(lambda: not module.process_exists(proc.pid), timeout=5.0))
        report = json.loads(receipt_path.read_text())
        record = report["brokers"][0]
        self.assertEqual(record["action"], "rpc_shutdown")
        self.assertTrue(record["exit_observed"])
        self.assertEqual(record["rpc_result"], "ok")
        self.assertEqual(report["summary"]["stopped"], 1)
        self.assertEqual(report["summary"]["failed_to_stop"], 0)
        self.assertIsInstance(report["mem_available_kib_before"], int)
        self.assertIsInstance(report["mem_available_kib_after"], int)

    def test_apply_removes_broker_json_after_a_confirmed_stop(self):
        # Fix-round finding: stop_broker() confirmed the broker PROCESS
        # exited but never touched broker.json itself, so a workspace's
        # plugin state kept pointing at the dead endpoint/pid until that
        # workspace's own next SessionEnd ran.
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-cleanup"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)
        broker_json_path = state_dir / "broker.json"
        self.assertTrue(broker_json_path.exists())

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--apply", "--min-age", "0", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(wait_until(lambda: not module.process_exists(proc.pid), timeout=5.0))
        self.assertFalse(broker_json_path.exists())

    def test_apply_leaves_broker_json_when_it_now_names_a_different_broker(self):
        # Race safety: clear_broker_json_if_stopped() must re-read
        # broker.json and compare pid/endpoint rather than trusting the
        # in-memory record, since a NEW broker could have started (and
        # written its own broker.json) for the same workspace while this
        # stop was waiting for the old one to exit.
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-raced"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)

        record = {
            "state_dir": str(state_dir), "broker_json": str(state_dir / "broker.json"),
            "pid": proc.pid, "endpoint": endpoint, "reasons": [], "rpc_result": None,
            "action": "none", "exit_observed": None,
        }
        module.stop_broker(record, escalate=False)
        self.assertTrue(wait_until(lambda: not module.process_exists(proc.pid), timeout=5.0))
        # Simulate a new broker's broker.json having been written for this
        # same workspace, as if a fresh session attached during the wait.
        write_broker_json(state_dir, endpoint="unix:/tmp/a-new-broker.sock", pid=424242)
        module.clear_broker_json_if_stopped(record)
        self.assertTrue((state_dir / "broker.json").exists())
        on_disk = json.loads((state_dir / "broker.json").read_text())
        self.assertEqual(on_disk["pid"], 424242)

    def test_escalate_sends_sigterm_only_after_rpc_gets_no_exit(self):
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-escalate"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace, extra_args=["--ignore-shutdown"])
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)

        original_exit_wait = module.EXIT_WAIT_SECONDS
        module.EXIT_WAIT_SECONDS = 0.5  # the fake broker ignores RPC; keep the test fast
        self.addCleanup(setattr, module, "EXIT_WAIT_SECONDS", original_exit_wait)

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main([
                "--apply", "--min-age", "0", "--escalate", "--state-root", str(state_root),
            ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(wait_until(lambda: not module.process_exists(proc.pid), timeout=5.0))
        report = json.loads(buffer.getvalue())
        record = report["brokers"][0]
        self.assertEqual(record["action"], "escalated_sigterm")
        self.assertTrue(record["exit_observed"])
        self.assertEqual(report["summary"]["failed_to_stop"], 0)

    def test_never_sends_sigkill_and_reports_failure_without_escalate(self):
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-stuck"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace, extra_args=["--ignore-shutdown"])
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)

        original_exit_wait = module.EXIT_WAIT_SECONDS
        module.EXIT_WAIT_SECONDS = 0.3
        self.addCleanup(setattr, module, "EXIT_WAIT_SECONDS", original_exit_wait)

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--apply", "--min-age", "0", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 2)  # an eligible broker failed to stop
        report = json.loads(buffer.getvalue())
        record = report["brokers"][0]
        self.assertEqual(record["action"], "rpc_shutdown")  # no SIGTERM: --escalate was not given
        self.assertFalse(record["exit_observed"])
        self.assertEqual(report["summary"]["failed_to_stop"], 1)
        # The broker (never signaled) is still alive; a real reaper without
        # --escalate must never have killed it.
        self.assertTrue(module.process_exists(proc.pid))

    def test_escalation_is_skipped_when_the_pid_no_longer_matches_on_recheck(self):
        # Deterministic simulation of pid reuse landing exactly between the
        # RPC wait and the escalation signal: monkeypatch the guard-(a)
        # reader stop_broker() re-checks, rather than racing real OS pid
        # reuse. Proves the broker is never signaled in that case.
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace, extra_args=["--ignore-shutdown"])
        record = {"pid": proc.pid, "endpoint": endpoint, "reasons": [], "rpc_result": None,
                  "action": "none", "exit_observed": None}

        original_wait = module.EXIT_WAIT_SECONDS
        original_reader = module.read_proc_cmdline
        module.EXIT_WAIT_SECONDS = 0.3
        module.read_proc_cmdline = lambda pid: ["some-unrelated-process"]  # simulates pid reuse
        self.addCleanup(setattr, module, "EXIT_WAIT_SECONDS", original_wait)
        self.addCleanup(setattr, module, "read_proc_cmdline", original_reader)

        module.stop_broker(record, escalate=True)

        self.assertEqual(record["action"], "rpc_shutdown")  # never upgraded to escalated_sigterm
        self.assertIn("pid reuse", " ".join(record["reasons"]))
        self.assertFalse(record["exit_observed"])
        # The real process must be untouched: no signal was actually sent to it.
        self.assertTrue(module.process_exists(proc.pid))

    def test_escalation_is_skipped_when_broker_is_not_its_own_process_group_leader(self):
        # Fix-round finding: --escalate sent SIGTERM to os.getpgid(pid)
        # without checking pgid == pid; the docstring asserted the broker is
        # always its own group leader (Node's detached:true) but the code
        # never checked it. Deterministic simulation via monkeypatching
        # os.getpgid, since a real pgid mismatch is racy/platform-dependent
        # to set up portably.
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace, extra_args=["--ignore-shutdown"])
        record = {"pid": proc.pid, "endpoint": endpoint, "reasons": [], "rpc_result": None,
                  "action": "none", "exit_observed": None}

        original_wait = module.EXIT_WAIT_SECONDS
        original_getpgid = os.getpgid
        module.EXIT_WAIT_SECONDS = 0.3
        os.getpgid = lambda target: target + 1 if target == proc.pid else original_getpgid(target)
        self.addCleanup(setattr, module, "EXIT_WAIT_SECONDS", original_wait)
        self.addCleanup(setattr, os, "getpgid", original_getpgid)

        module.stop_broker(record, escalate=True)

        self.assertEqual(record["action"], "escalation_skipped_not_group_leader")
        self.assertIn("not its own process-group leader", " ".join(record["reasons"]))
        self.assertFalse(record["exit_observed"])
        # No signal was actually sent: the real process is untouched.
        self.assertTrue(module.process_exists(proc.pid))

    def test_apply_rechecks_each_broker_immediately_before_stopping_it(self):
        # Fix-round finding: all brokers were evaluated up front and stopped
        # one after another later, with no re-check of guards before each
        # RPC; an earlier broker's own stop can take long enough for a
        # session to attach to a later one in the same run. Deterministic
        # simulation: make the *second* evaluate_broker() call (the pre-stop
        # re-check inside run()) report a live session, rather than racing a
        # real session attaching against real stop timing.
        state_root = self.root / "state"
        state_dir = state_root / "workspace-slug-recheck"
        state_dir.mkdir(parents=True)
        workspace = self.root / "workspace"
        workspace.mkdir()
        proc, endpoint = self.spawn_fake_broker(cwd=workspace)
        write_broker_json(state_dir, endpoint=endpoint, pid=proc.pid)
        write_state_json(state_dir, jobs=[])
        shutil.rmtree(workspace)  # guard c satisfied for the initial scan

        call_count = {"n": 0}
        original_evaluate = module.evaluate_broker

        def fake_evaluate(broker_dir, *, min_age, now):
            call_count["n"] += 1
            record = original_evaluate(broker_dir, min_age=min_age, now=now)
            if call_count["n"] > 1:
                # Simulate a session that attached between the initial scan
                # and this broker's turn to be stopped.
                record["eligible"] = False
                record["guards"]["c_workspace_unused"] = False
                record["reasons"].append("fixture: simulated live session attached before stop")
            return record

        module.evaluate_broker = fake_evaluate
        self.addCleanup(setattr, module, "evaluate_broker", original_evaluate)

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["--apply", "--min-age", "0", "--state-root", str(state_root)])
        self.assertEqual(exit_code, 0)
        report = json.loads(buffer.getvalue())
        record = report["brokers"][0]
        self.assertEqual(record["action"], "skipped_recheck_failed")
        self.assertFalse(record["eligible"])
        self.assertEqual(report["summary"]["eligible"], 0)
        self.assertEqual(report["summary"]["stopped"], 0)
        self.assertEqual(report["summary"]["failed_to_stop"], 0)
        # The broker (never signaled) must still be alive.
        self.assertTrue(module.process_exists(proc.pid))


@LINUX_ONLY
class RpcTransportTests(ReaperTestCase):
    def test_send_shutdown_rpc_reports_socket_missing_for_a_stale_endpoint(self):
        result = module.send_shutdown_rpc(f"unix:{self.root}/nonexistent.sock")
        self.assertEqual(result, "socket_missing")

    def test_send_shutdown_rpc_reports_unsupported_endpoint_for_non_unix_schemes(self):
        self.assertEqual(module.send_shutdown_rpc("pipe:\\\\.\\pipe\\example"), "unsupported_endpoint")


@LINUX_ONLY
class PlatformGuardTests(ReaperTestCase):
    def test_main_refuses_to_run_without_proc(self):
        # Fix-round finding: on a host with no /proc at all, every broker's
        # own evaluation silently fails the same way a dead pid would ("pid
        # N is not running"), reporting 0 eligible instead of an honest
        # unsupported-platform error. proc_is_available() lets main() fail
        # closed instead of misleading an operator; simulated here since
        # this test host does have /proc.
        original = module.proc_is_available
        module.proc_is_available = lambda: False
        self.addCleanup(setattr, module, "proc_is_available", original)

        stderr_buffer = StringIO()
        with redirect_stderr(stderr_buffer):
            exit_code = module.main(["--list"])
        # Exit 3, not 2 (fix round, 2026-09-25 second round): 2 is this
        # tool's documented code for "an eligible broker was not confirmed
        # stopped" (README, rollout brief); this platform refusal used to
        # share it via parser.error(), which a monitor following the
        # documented contract could not tell apart. main() now returns 3
        # directly here rather than raising SystemExit through argparse,
        # matching every other exit path in main() (a plain return, wrapped
        # in SystemExit only by the `if __name__ == "__main__":` guard).
        self.assertEqual(exit_code, 3)
        self.assertIn("/proc", stderr_buffer.getvalue())

    def test_bad_usage_still_exits_2_via_argparse(self):
        # Distinguishes the platform refusal (3) from an ordinary invalid
        # invocation, which keeps argparse's own conventional exit code 2 --
        # unlike the platform refusal, this genuinely is "bad usage", and
        # every argparse-based CLI already treats 2 that way.
        stderr_buffer = StringIO()
        with redirect_stderr(stderr_buffer), self.assertRaises(SystemExit) as raised:
            module.main(["--min-age", "-1"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
