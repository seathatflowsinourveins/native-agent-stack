"""Exercise codex-broker-reaper's guards against real, live, synthetic processes.

Every fixture here is synthetic: a small Python stand-in plays the role of the
openai-codex plugin's `app-server-broker.mjs` (a real unix-socket server that
answers `broker/shutdown`, spawned with a script file literally named
`app-server-broker.mjs` so its real `/proc/<pid>/cmdline` matches guard (a)
exactly) and, separately, a live "claude" look-alike (comm forced to "claude"
via `prctl(PR_SET_NAME)`, since a Python-shebang script's own comm is the
interpreter's, not the script's -- checked by hand against the real
~/.local/bin/claude binary before writing this suite). No real broker, no
real Claude Code or Codex session, and no plugin state directory on this
host is read or touched: every state/workspace directory is a fresh
tempfile.mkdtemp(), and `--state-root`/direct function calls always point at
that synthetic tree.
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
from io import StringIO
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

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


class LiveCwdGuardTests(ReaperTestCase):
    """Guard (c): workspace gone, or no live claude/codex process is under it."""

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


class RpcTransportTests(ReaperTestCase):
    def test_send_shutdown_rpc_reports_socket_missing_for_a_stale_endpoint(self):
        result = module.send_shutdown_rpc(f"unix:{self.root}/nonexistent.sock")
        self.assertEqual(result, "socket_missing")

    def test_send_shutdown_rpc_reports_unsupported_endpoint_for_non_unix_schemes(self):
        self.assertEqual(module.send_shutdown_rpc("pipe:\\\\.\\pipe\\example"), "unsupported_endpoint")


if __name__ == "__main__":
    unittest.main()
