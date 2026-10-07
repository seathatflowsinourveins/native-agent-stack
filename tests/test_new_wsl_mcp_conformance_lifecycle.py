"""Local synthetic lifecycle checks using real Linux namespaces and sockets."""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/config/mcp-conformance-accept.sh"



class ConformanceTargetBoundaryTests(unittest.TestCase):
    """The unqualified URL boundary runs before any namespace, tool or model."""
    def test_external_url_is_owner_pending_without_startup_adapter(self):
        for stage in ("after_sign_in", "__isolated_after"):
            for client in ("", "owner-client --stdio"):
                with self.subTest(stage=stage,client=client), tempfile.TemporaryDirectory(prefix="ns-conformance-url-") as temp:
                    root = Path(temp)
                    env = {"PATH":"/usr/bin:/bin", "HOME":str(root), "tool_root":str(root/"tools"),
                           "XDG_STATE_HOME":str(root/"state"),
                           "MCP_CONFORMANCE_SERVER_URL":"http://127.0.0.1:12345/mcp",
                           "MCP_CONFORMANCE_CLIENT_COMMAND":client}
                    result = subprocess.run(["bash",str(HELPER),stage],env=env,text=True,
                                            capture_output=True,timeout=10)
                    self.assertEqual(result.returncode,78,result.stderr)
                    self.assertIn("needs_owner:",result.stderr)
                    self.assertIn("inside the isolated loopback namespace",result.stderr)
                    self.assertFalse((root/"state").exists())

    def test_missing_target_stays_needs_user(self):
        with tempfile.TemporaryDirectory(prefix="ns-conformance-target-") as temp:
            root = Path(temp)
            result = subprocess.run(["bash",str(HELPER),"after_sign_in"],
                                    env={"PATH":"/usr/bin:/bin","HOME":str(root),"tool_root":str(root/"tools"),
                                         "XDG_STATE_HOME":str(root/"state")},
                                    capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,78,result.stderr)
            self.assertIn("needs_user:",result.stderr)
            self.assertFalse((root/"state").exists())


class ConformanceLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(shutil.which(c) for c in ("unshare", "setsid", "ip", "ss")):
            raise unittest.SkipTest("Linux namespace tools unavailable")
        probe = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "--pid", "--fork",
                                "--mount-proc", "--kill-child", "true"], capture_output=True, timeout=10)
        if probe.returncode:
            raise unittest.SkipTest("Unprivileged namespaces unavailable; native acceptance still fails closed")

    def exercise(self, outcome, requested_signal=None, missing_snapshot=False, startup_signal=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / "bin"
            binaries.mkdir()
            source = root / "tools/mcp-conformance-source-0.2.0-alpha.11"
            source.mkdir(parents=True)
            with socket.socket() as candidate:
                candidate.bind(("127.0.0.1", 0))
                port = candidate.getsockname()[1]
            server = root / "server.py"
            server.write_text(
                "import json,os,socket,time\nfrom pathlib import Path\n"
                "with socket.socket() as s:\n"
                " s.bind(('0.0.0.0',int(os.environ['FIXTURE_PORT']))); s.listen()\n"
                " Path(os.environ['FIXTURE_READY']).write_text(json.dumps({'net':os.readlink('/proc/self/ns/net')}))\n"
                " while True: time.sleep(1)\n"
            )
            npm = binaries / "npm"
            npm.write_text(
                "#!/usr/bin/env python3\nimport os,subprocess,sys,time\nfrom pathlib import Path\n"
                "if sys.argv[1:] == ['test']:\n"
                " subprocess.Popen([sys.executable,os.environ['FIXTURE_SERVER']],start_new_session=True,"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                " while not Path(os.environ['FIXTURE_RELEASE']).exists(): time.sleep(.02)\n"
                " sys.exit(int(os.environ['FIXTURE_RETURN']))\n"
            )
            npm.chmod(0o755)
            npx = binaries / "npx"
            npx.write_text("#!/bin/sh\nexit 0\n")
            npx.chmod(0o755)
            starting = root / "starting"
            if startup_signal:
                real_setsid = shutil.which("setsid")
                delayed = binaries / "setsid"
                delayed.write_text("#!/usr/bin/env python3\nimport os,sys,time\nfrom pathlib import Path\n"
                                   "Path(os.environ['FIXTURE_STARTING']).touch(); time.sleep(.4)\n"
                                   "os.execv(os.environ['FIXTURE_SETSID'], ['setsid', *sys.argv[1:]])\n")
                delayed.chmod(0o755)
            if missing_snapshot:
                real_ss = shutil.which("ss")
                ss = binaries / "ss"
                ss.write_text("#!/usr/bin/env python3\nimport os,sys\n"
                              "if os.readlink('/proc/self/ns/net') != os.environ['FIXTURE_HOST_NET']: sys.exit(1)\n"
                              "os.execv(os.environ['FIXTURE_SS'], ['ss', *sys.argv[1:]])\n")
                ss.chmod(0o755)
            ready = root / "ready.json"
            release = root / "release"
            env = {"PATH": str(binaries) + os.pathsep + os.environ["PATH"], "HOME": os.environ["HOME"],
                   "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root),
                   "tool_root": str(root / "tools"), "plan_dir": str(root),
                   "FIXTURE_SERVER": str(server), "FIXTURE_READY": str(ready),
                   "FIXTURE_RELEASE": str(release), "FIXTURE_RETURN": str(outcome), "FIXTURE_PORT": str(port)}
            if missing_snapshot:
                env.update(FIXTURE_HOST_NET=os.readlink("/proc/self/ns/net"), FIXTURE_SS=real_ss)
            if startup_signal:
                env.update(FIXTURE_STARTING=str(starting), FIXTURE_SETSID=real_setsid)
            output = root / "output.txt"
            process = None
            try:
                with output.open("w") as log:
                    process = subprocess.Popen(["bash", str(HELPER), "post_install"], env=env,
                                               stdout=log, stderr=log, start_new_session=True)
                    deadline = time.monotonic() + 15
                    event = starting if startup_signal else ready
                    while not event.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue(event.is_file(), output.read_text())
                    if not startup_signal:
                        self.assertNotEqual(json.loads(ready.read_text())["net"], os.readlink("/proc/self/ns/net"))
                    host = subprocess.run(["ss", "-ltnH", f"sport = :{port}"], capture_output=True, text=True, check=True)
                    self.assertEqual(host.stdout, "", "Fixture wildcard listener escaped the private namespace")
                    if requested_signal is None:
                        release.touch()
                    else:
                        process.send_signal(requested_signal)
                    result = process.wait(timeout=20)
                expected = outcome if requested_signal is None else 128 + requested_signal
                if missing_snapshot:
                    self.assertNotEqual(result, 0, output.read_text())
                else:
                    self.assertEqual(result, expected, output.read_text())
                marker = re.search(r"CONFORMANCE_RUN_DIR=(.+)", output.read_text())
                self.assertIsNotNone(marker)
                run = Path(marker.group(1))
                proof = json.loads((run / "cleanup.json").read_text())
                if not startup_signal:
                    self.assertEqual(proof["owned_namespace_processes_remaining"], 0)
                self.assertEqual(proof["owned_group_processes_remaining"], 0)
                if not startup_signal:
                    self.assertEqual(proof["run_port_listeners_remaining"], None if missing_snapshot else 0)
                    self.assertEqual(proof["listener_observation_available"], not missing_snapshot)
                self.assertEqual(subprocess.run(["ss", "-ltnH", f"sport = :{port}"],
                                                capture_output=True, text=True, check=True).stdout, "")
                self.assertEqual(list((root / "mcp").glob("run.*")), [],
                                 "The owned IPC cache must be removed after process teardown")
            finally:
                if process is not None and process.poll() is None:
                    # Let the exact owned helper perform its identity-checked group
                    # cleanup; a numeric group file alone cannot prove ownership.
                    process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)

    def test_success_cleans_detached_wildcard_server(self):
        self.exercise(0)

    def test_failure_cleans_detached_wildcard_server_and_preserves_status(self):
        self.exercise(7)

    def test_interrupt_cleans_detached_wildcard_server(self):
        self.exercise(0, signal.SIGINT)

    def test_termination_cleans_detached_wildcard_server(self):
        self.exercise(0, signal.SIGTERM)

    def test_missing_listener_observation_is_unknown_and_fails_acceptance(self):
        self.exercise(0, missing_snapshot=True)

    def test_startup_termination_is_deferred_until_ownership_is_recorded(self):
        self.exercise(0, signal.SIGTERM, startup_signal=True)


class ConformanceEarlyCacheCleanupTests(unittest.TestCase):
    def test_path_length_failure_removes_only_its_allocation_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / ("cache-" + "x" * 90)
            temp_root = cache / "mcp"
            foreign = temp_root / "foreign"
            foreign.mkdir(parents=True)
            sentinel = foreign / "preserve.txt"
            sentinel.write_bytes(b"synthetic unrelated cache bytes\n")
            binary = root / "bin"
            binary.mkdir()
            marker = root / "unexpected-startup"
            for command in ("setsid", "unshare", "ip", "ss", "ps", "npm", "npx", "tee"):
                stub = binary / command
                stub.write_text('#!/bin/sh\nprintf "unexpected" > "$UNEXPECTED_STARTUP"\nexit 99\n')
                stub.chmod(0o755)
            result = subprocess.run(
                ["bash", str(HELPER), "post_install"],
                env={"PATH": str(binary) + os.pathsep + os.environ["PATH"], "HOME": str(root),
                     "XDG_CACHE_HOME": str(cache), "XDG_STATE_HOME": str(root / "state"),
                     "tool_root": str(root / "tools"), "UNEXPECTED_STARTUP": str(marker)},
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn("cache path is too long", result.stderr)
            self.assertFalse(marker.exists(), "The early failure must precede owned-process startup")
            self.assertEqual(list(temp_root.glob("run.*")), [])
            self.assertEqual(sentinel.read_bytes(), b"synthetic unrelated cache bytes\n")
            evidence = root / "state/new-wsl-native-stack/acceptance/mcp-protocol-conformance"
            runs = list(evidence.glob("lifecycle.*"))
            self.assertEqual(len(runs), 1, "The retained evidence directory must survive cache cleanup")
            self.assertTrue(runs[0].is_dir())
