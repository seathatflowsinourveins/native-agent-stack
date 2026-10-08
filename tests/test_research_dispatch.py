"""Synthetic CLI/protocol checks, not upstream or live research acceptance.

The fixtures stand in for hcom's documented ``list self --json`` and the
installed embedded DeerFlow launcher's run-directory/answer/metadata contract.
No model, credential, network, service, or installed research runtime is used.
Cancellation controls use native procps and available real uutils/GNU timeout
executables to exercise their separate process groups within the owned session.
"""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "tools/research/dispatch"
NATIVE_PKILL = shutil.which("pkill")
NATIVE_PS = shutil.which("ps")


def native_session_tools_available():
    if not NATIVE_PKILL or not NATIVE_PS:
        return False
    pkill = subprocess.run([NATIVE_PKILL, "--help"], capture_output=True, text=True)
    ps = subprocess.run([NATIVE_PS, "--help", "all"], capture_output=True, text=True)
    return "--session" in pkill.stdout + pkill.stderr and "--sid" in ps.stdout + ps.stderr


NATIVE_SESSION_TOOLS = native_session_tools_available()


class ResearchDispatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="research-dispatch-fixture-"))
        self.addCleanup(shutil.rmtree, self.directory)
        self.config = self.directory / "config/new-wsl-native-stack"
        self.config.mkdir(parents=True)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.directory / "home"),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "XDG_CONFIG_HOME": str(self.directory / "config"),
            "XDG_STATE_HOME": str(self.directory / "state"),
            "SYNTHETIC_FIXTURE_ROOT": str(self.directory),
        }
        self.hcom = self.bin / "hcom"
        self.hcom.write_text(
            f"#!{sys.executable}\n"
            + textwrap.dedent(
                """
                import json, os, sys
                from pathlib import Path
                root = Path(os.environ["SYNTHETIC_FIXTURE_ROOT"])
                (root / "hcom-call.json").write_text(json.dumps(sys.argv[1:]))
                print(json.dumps({"name": "gala", "session_id": "synthetic-session", "tool": "codex"}))
                """
            ),
            encoding="utf-8",
        )
        self.hcom.chmod(0o755)
        # The ordinary CLI tests isolate the prerequisite contract too. Actual
        # cancellation tests remove these fixtures and use native procps.
        for tool, help_text in (("pkill", "--session SID"), ("ps", "--sid SID")):
            fixture = self.bin / tool
            fixture.write_text(
                f"#!{sys.executable}\n"
                + "import sys\n"
                + f"print({help_text!r}) if '--help' in sys.argv else None\n"
                + "raise SystemExit(0 if '--help' in sys.argv else 1)\n",
                encoding="utf-8",
            )
            fixture.chmod(0o755)
        self.launcher = self.config / "deer-flow-research.sh"
        self.launcher.write_text(
            "#!/usr/bin/env bash\n"
            + f"exec '{sys.executable}' - \"$1\" <<'PY'\n"
            + textwrap.dedent(
                """
                import json, os, sys
                from pathlib import Path
                root = Path(os.environ["SYNTHETIC_FIXTURE_ROOT"])
                (root / "launcher-call.json").write_text(json.dumps(sys.argv[1:]))
                run = root / "producer run"
                run.mkdir()
                (run / "answer.md").write_text("Synthetic answer. [Source](https://example.org/source)\\n")
                (run / "native-retrieval-metadata.json").write_text(json.dumps({
                    "integration_assertion_pass": True,
                    "cited_retrieved_url_matches": 1,
                    "cited_retrieved_url_sha256": ["synthetic-url-hash"],
                    "native_sdk_usage": None,
                }))
                print("run directory: " + str(run), flush=True)
                print("Synthetic native console answer")
                sys.exit(int(os.environ.get("SYNTHETIC_PRODUCER_EXIT", "0")))
                """
            )
            + "PY\n",
            encoding="utf-8",
        )

    def run_dispatch(self, *args):
        return subprocess.run(
            [sys.executable, str(DISPATCH), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def receipts(self):
        return list((self.directory / "state").rglob("dispatch.json"))

    def use_native_session_tools(self):
        for tool in ("pkill", "ps"):
            (self.bin / tool).unlink()

    def test_one_question_returns_the_original_cited_result_with_native_hcom_identity(self):
        question = "Compare maintained tools; literal $(touch NEVER) and `echo text` stay text."
        result = self.run_dispatch("--name", "gala", question)
        self.assertEqual(result.returncode, 0, result.stderr)
        answer = self.directory / "producer run/answer.md"
        self.assertEqual(result.stdout, f"{answer}\n")
        self.assertEqual(json.loads((self.directory / "launcher-call.json").read_text()), [question])
        self.assertEqual(
            json.loads((self.directory / "hcom-call.json").read_text()),
            ["list", "self", "--json", "--name", "gala"],
        )
        self.assertEqual(len(self.receipts()), 1)
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["hcom_identity"]["name"], "gala")
        self.assertEqual(receipt["hcom_identity"]["session_id"], "synthetic-session")
        self.assertEqual(receipt["native_exit_code"], 0)
        self.assertEqual(receipt["answer"]["path"], str(answer))
        self.assertEqual(receipt["answer"]["sha256"], hashlib.sha256(answer.read_bytes()).hexdigest())
        self.assertEqual(receipt["native_citations"]["cited_retrieved_url_matches"], 1)
        self.assertIn("Synthetic native console answer", (self.receipts()[0].parent / "producer.stdout").read_text())
        self.assertFalse((self.directory / "NEVER").exists())

    def test_the_hook_redirects_question_option_runs_the_same_native_producer(self):
        result = self.run_dispatch("--hcom-name", "gala", "--question", "One public question")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.directory / "launcher-call.json").read_text()), ["One public question"])
        self.assertEqual(result.stdout, f"{self.directory / 'producer run/answer.md'}\n")

    def test_a_native_failure_retains_its_partial_answer_and_never_returns_a_success_path(self):
        self.env["SYNTHETIC_PRODUCER_EXIT"] = "7"
        result = self.run_dispatch("--name", "gala", "--question", "A failing public question")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout, "")
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["native_exit_code"], 7)
        self.assertEqual(receipt["native_run_directory"], str(self.directory / "producer run"))
        answer = self.directory / "producer run/answer.md"
        self.assertEqual(receipt["answer"]["sha256"], hashlib.sha256(answer.read_bytes()).hexdigest())
        self.assertTrue((self.receipts()[0].parent / "producer.stdout").is_file())
        self.assertIn(str(self.receipts()[0]), result.stderr)

    def test_a_successful_process_cannot_promote_a_failed_native_retrieval_verdict(self):
        self.launcher.write_text(self.launcher.read_text().replace('"integration_assertion_pass": True', '"integration_assertion_pass": False'))
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertEqual(receipt["native_exit_code"], 0)
        self.assertFalse(receipt["native_citations"]["integration_assertion_pass"])
        self.assertEqual(receipt["status"], "failed")

    def test_a_verdict_without_witnessed_citations_is_not_returned(self):
        self.launcher.write_text(self.launcher.read_text().replace('"cited_retrieved_url_matches": 1', '"cited_retrieved_url_matches": 0'))
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertEqual(receipt["native_citations"]["cited_retrieved_url_matches"], 0)

    def test_unresolved_hcom_identity_prevents_a_model_operation(self):
        self.hcom.write_text(f"#!{sys.executable}\nprint('{{}}')\n")
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.directory / "launcher-call.json").exists())
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertIsNone(receipt["native_exit_code"])
        self.assertIn("no participating caller", result.stderr)

    def test_missing_installed_launcher_prevents_hcom_and_research(self):
        self.launcher.unlink()
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.directory / "hcom-call.json").exists())
        self.assertFalse((self.directory / "launcher-call.json").exists())
        self.assertEqual(len(self.receipts()), 1)

    def test_missing_native_session_control_prevents_hcom_and_research(self):
        (self.bin / "pkill").unlink()
        self.env["PATH"] = str(self.bin)
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("pkill", result.stderr)
        self.assertFalse((self.directory / "hcom-call.json").exists())
        self.assertFalse((self.directory / "launcher-call.json").exists())
        self.assertEqual(len(self.receipts()), 1)

    def test_empty_and_duplicate_questions_are_usage_failures_without_runtime_work(self):
        for args in ((), ("--question", " "), ("one", "--question", "two")):
            with self.subTest(args=args):
                result = self.run_dispatch(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertFalse((self.directory / "hcom-call.json").exists())
                self.assertFalse((self.directory / "launcher-call.json").exists())
        self.assertEqual(self.receipts(), [])

    def test_a_later_marker_in_native_answer_output_cannot_redirect_the_result(self):
        self.launcher.write_text(self.launcher.read_text().replace('print("Synthetic native console answer")', 'print("run directory: /unrelated-answer-path")'))
        result = self.run_dispatch("--name", "gala", "question")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"{self.directory / 'producer run/answer.md'}\n")

    @unittest.skipUnless(NATIVE_SESSION_TOOLS and hasattr(os, "killpg"), "needs the native procps session route")
    def test_cancellation_retires_a_term_ignoring_descendant_and_retains_the_failure(self):
        self.use_native_session_tools()
        self.launcher.write_text(
            "#!/usr/bin/env bash\n"
            + f"exec '{sys.executable}' - <<'PY'\n"
            + textwrap.dedent(
                """
                import os, subprocess, sys, time
                from pathlib import Path
                root = Path(os.environ["SYNTHETIC_FIXTURE_ROOT"])
                run = root / "producer run"
                run.mkdir()
                print("run directory: " + str(run), flush=True)
                child_code = (
                    "import pathlib,signal,time;"
                    "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                    "pathlib.Path('child.ready').touch();time.sleep(60)"
                )
                child = subprocess.Popen([sys.executable, "-c", child_code], cwd=root)
                (root / "child.pid").write_text(str(child.pid))
                (root / "producer.group").write_text(str(os.getpgrp()))
                while not (root / "child.ready").exists():
                    time.sleep(0.01)
                (root / "producer.ready").touch()
                time.sleep(60)
                """
            )
            + "PY\n"
        )
        process = subprocess.Popen(
            [sys.executable, str(DISPATCH), "--name", "gala", "question"],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not (self.directory / "producer.ready").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.directory / "producer.ready").exists())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 143, stderr)
            self.assertEqual(stdout, "")
            receipt = json.loads(self.receipts()[0].read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["native_run_directory"], str(self.directory / "producer run"))
            child_pid = int((self.directory / "child.pid").read_text())
            status = subprocess.run(["ps", "-o", "stat=", "-p", str(child_pid)], capture_output=True, text=True).stdout.strip()
            self.assertTrue(not status or status.startswith("Z"), f"descendant survived cancellation: {status}")
        finally:
            group = self.directory / "producer.group"
            if group.exists():
                try:
                    os.killpg(int(group.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    @unittest.skipUnless(NATIVE_SESSION_TOOLS and Path("/usr/bin/timeout").is_file(), "needs native procps and selected timeout")
    def test_cancellation_retires_real_selected_timeout_groups_without_terminating_a_peer(self):
        self.check_real_timeout_cancellation("/usr/bin/timeout")

    @unittest.skipUnless(NATIVE_SESSION_TOOLS and Path("/usr/bin/gnutimeout").is_file(), "needs native procps and GNU timeout")
    def test_cancellation_retires_real_gnu_timeout_groups_without_terminating_a_peer(self):
        self.check_real_timeout_cancellation("/usr/bin/gnutimeout")

    def check_real_timeout_cancellation(self, timer):
        self.use_native_session_tools()
        self.launcher.write_text(
            "#!/usr/bin/env bash\n"
            + 'printf "run directory: %s\\n" "$SYNTHETIC_FIXTURE_ROOT/producer run"\n'
            + f"'{timer}' 60 '{sys.executable}' - <<'PY'\n"
            + textwrap.dedent(
                """
                import json, os, subprocess, sys, time
                from pathlib import Path
                root = Path(os.environ["SYNTHETIC_FIXTURE_ROOT"])
                run = root / "producer run"
                run.mkdir()
                (run / "answer.md").write_text("Retained partial synthetic answer.\\n")
                (run / "native-retrieval-metadata.json").write_text(json.dumps({
                    "integration_assertion_pass": False, "cited_retrieved_url_matches": 0,
                }))
                child_code = (
                    "import pathlib,signal,time;"
                    "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                    "pathlib.Path('child.ready').touch();time.sleep(60)"
                )
                child = subprocess.Popen([sys.executable, "-c", child_code], cwd=root)
                (root / "child.pid").write_text(str(child.pid))
                scope = {"sid": os.getsid(0), "pgid": os.getpgrp(), "python_pid": os.getpid(), "timeout_pid": os.getppid()}
                (root / "producer.scope.json").write_text(json.dumps(scope))
                while not (root / "child.ready").exists():
                    time.sleep(0.01)
                (root / "producer.ready").touch()
                time.sleep(60)
                """
            )
            + "PY\nstatus=$?\nexit \"$status\"\n"
        )
        peer = subprocess.Popen(
            [sys.executable, "-c", "import time;time.sleep(60)"],
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        process = subprocess.Popen(
            [sys.executable, str(DISPATCH), "--name", "gala", "question"],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        scope = None
        try:
            deadline = time.monotonic() + 5
            while not (self.directory / "producer.ready").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.directory / "producer.ready").exists())
            scope = json.loads((self.directory / "producer.scope.json").read_text())
            self.assertNotEqual(scope["sid"], scope["pgid"], "the real timer must exercise a separate producer process group")
            self.assertNotEqual(scope["sid"], os.getsid(peer.pid))
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=12)
            self.assertEqual(process.returncode, 143, stderr)
            self.assertEqual(stdout, "")
            self.assertIsNone(peer.poll(), "cancellation terminated an unrelated peer session")
            states = subprocess.run(
                [NATIVE_PS, "--sid", str(scope["sid"]), "-o", "pid=,stat="], capture_output=True, text=True,
            )
            live = [line for line in states.stdout.splitlines() if not line.split()[1].startswith("Z")]
            self.assertEqual(live, [], f"native timeout session members survived cancellation: {live}")
            receipt = json.loads(self.receipts()[0].read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertIsInstance(receipt["native_exit_code"], int)
            self.assertNotEqual(receipt["native_exit_code"], 0)
            self.assertEqual(receipt["interrupted_by_signal"], signal.SIGTERM)
            self.assertEqual(receipt["cancellation"]["session_id"], scope["sid"])
            self.assertEqual(receipt["cancellation"]["status"], "retired")
            self.assertEqual(receipt["answer"]["sha256"], hashlib.sha256(b"Retained partial synthetic answer.\n").hexdigest())
            self.assertFalse(receipt["native_citations"]["integration_assertion_pass"])
            self.assertEqual((self.receipts()[0].parent / "producer.stdout").read_text().splitlines()[0], f"run directory: {self.directory / 'producer run'}")
        finally:
            if scope:
                subprocess.run([NATIVE_PKILL, "--signal", "KILL", "--session", str(scope["sid"])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.killpg(peer.pid, signal.SIGKILL)
            peer.wait(timeout=5)
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
