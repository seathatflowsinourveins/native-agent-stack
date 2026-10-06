"""The IBKR paper gateway's recreate script, run against stub docker, ss and sleep commands.

Local integration class with synthetic fixtures: PATH holds only the stubs and the core utilities the script names, so
the real Docker daemon, and with it the live gateway container, is never reached. The pointer files hold fake values
generated per test; nothing here reads a real credential store.
"""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "blueprints/us-equities/runtime-2604/ibkr-gateway-recreate-durable.sh"
TOOLS = ("dirname", "realpath", "date", "mkdir", "chmod", "wc", "grep", "cat")
NAME = "native-trading-ibkr-paper-20261005"

DOCKER_STUB = """#!/bin/sh
# Records each call's arguments (paths and options, never a file's contents) and answers like a rootless daemon.
printf '%s\\n' "$*" >> "$STUB_LOG"
case "$1" in
  info)
    if [ "$STUB_ROOTLESS" = 1 ]; then echo '[name=seccomp,profile=builtin name=rootless name=cgroupns]'
    else echo '[name=seccomp,profile=builtin name=cgroupns]'; fi ;;
  inspect)
    if [ "$#" -eq 2 ]; then
      if [ "$STUB_EXISTS" = 1 ] || [ -e "$STUB_STARTED" ]; then echo "[{\\"Config\\": {\\"Env\\": [\\"TWS_USERID=$STUB_USER\\"]}}]"
      else exit 1; fi
    else
      case "$4" in
        *Config.Env*) printf 'TWS_USERID=%s\\nTRADING_MODE=paper\\nAUTO_RESTART_TIME=11:00 PM\\n' "$STUB_USER" ;;
        *) printf 'state=running started=2026-10-06T00:00:00Z restart=unless-stopped\\n' ;;
      esac
    fi ;;
  run)
    case " $* " in *" -d "*)
      if [ "$STUB_START_FAILS" = 1 ]; then echo "docker: Error response from daemon: stub start failure" >&2; exit 125; fi
      : > "$STUB_STARTED"; echo 0123456789abcdef ;;
    esac ;;
esac
exit 0
"""
SS_STUB = """#!/bin/sh
i=0
while [ "$i" -lt "$SS_CONNECTIONS" ]; do echo "ESTAB 0 0 127.0.0.1:5000$i 127.0.0.1:4002"; i=$((i + 1)); done
"""


class RecreateScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(os.path.realpath(temporary.name))
        if any((parent / ".git").exists() for parent in (self.base, *self.base.parents)):
            self.skipTest("the temporary directory is inside a Git worktree, where the script refuses to keep records")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool)
            self.assertIsNotNone(found, tool)
            (self.bin / tool).symlink_to(found)
        for name, body in (("docker", DOCKER_STUB), ("ss", SS_STUB), ("sleep", "#!/bin/sh\nexit 0\n")):
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        self.home = self.base / "home"
        self.home.mkdir()
        store = self.base / "store"
        store.mkdir(mode=0o700)
        self.user = "FAKEUSER" + os.urandom(6).hex()
        self.tws_fake = "FAKETWS" + os.urandom(6).hex()  # stands in for the paper password
        self.pointers = {}
        for variable, name, text in (("IBKR_PAPER_LOGIN_ENV", "login.env", f"TWS_USERID={self.user}\n"),
                                     ("IBKR_PAPER_TWS_FILE", "tws.password", self.tws_fake),
                                     ("IBKR_PAPER_VNC_FILE", "vnc.password", "fakevnc1")):
            path = store / name
            path.write_text(text)
            path.chmod(0o600)
            self.pointers[variable] = str(path)
        self.log = self.base / "docker.log"
        self.state = self.base / "state"

    def run_script(self, *, exists=True, rootless=True, connections=0, state=None, start_fails=False, **overrides):
        env = {"PATH": str(self.bin), "HOME": str(self.home), "XDG_STATE_HOME": str(self.state if state is None else state),
               "STUB_LOG": str(self.log), "STUB_STARTED": str(self.base / "started"), "STUB_USER": self.user,
               "STUB_EXISTS": "1" if exists else "0", "STUB_ROOTLESS": "1" if rootless else "0",
               "STUB_START_FAILS": "1" if start_fails else "0",
               "SS_CONNECTIONS": str(connections), **self.pointers, **overrides}
        result = subprocess.run(["/bin/bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
        for value in (self.user, self.tws_fake):
            self.assertNotIn(value, result.stdout + result.stderr)
        return result

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def records(self, state=None):
        root = (self.state if state is None else state) / "native-agent-stack" / "ibkr-gateway"
        return sorted(root.glob("recreate-*")) if root.exists() else []

    def assert_nothing_changed(self):
        self.assertFalse([call for call in self.calls() if call.split()[0] in {"run", "stop", "rename"}])
        self.assertEqual(self.records(), [])

    def test_recreates_and_keeps_records_private_outside_every_worktree(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        chowns = [call for call in calls if call.startswith("run --rm --user 0 --entrypoint chown")]
        self.assertEqual(chowns, [f"run --rm --user 0 --entrypoint chown -v {self.pointers[v]}:/s "
                                  "ghcr.io/gnzsnz/ib-gateway:10.51.1b@sha256:"
                                  "69db6310cd75d5d0aca3a70c05dc5ad77b2be29ad75360a3f1e393454f2efa59 1000:1000 /s"
                                  for v in ("IBKR_PAPER_VNC_FILE", "IBKR_PAPER_TWS_FILE")])
        verbs = [call.split()[0] for call in calls]
        # The client check reads ss before any change; the chown, the rollback rename and the new container follow.
        self.assertLess(verbs.index("info"), calls.index(chowns[0]))
        self.assertIn(f"rename {NAME} {NAME}-pre-durable-", "\n".join(calls))
        self.assertLess(verbs.index("stop"), verbs.index("rename"))
        start = next(call for call in calls if call.startswith("run -d"))
        settings = "/home/" + "ibgateway/Jts"  # the image's settings directory, spelled so that no home path sits in this file
        for option in (f"-v {NAME}-settings-rw:{settings}", f"-e TWS_SETTINGS_PATH={settings}",
                       f"--env-file {self.pointers['IBKR_PAPER_LOGIN_ENV']}",
                       f"-v {self.pointers['IBKR_PAPER_TWS_FILE']}:/run/secrets/tws_password:ro",
                       f"-v {self.pointers['IBKR_PAPER_VNC_FILE']}:/run/secrets/vnc_password:ro",
                       "-e TRADING_MODE=paper", "-e TWOFA_TIMEOUT_ACTION=restart", "-e RELOGIN_AFTER_TWOFA_TIMEOUT=yes",
                       "-p 127.0.0.1:4002:4004", "-p 127.0.0.1:5900:5900"):
            self.assertIn(option, start)
        (record,) = self.records()
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o700)
        self.assertEqual(sorted(p.name for p in record.iterdir()),
                         ["after-inspect.json", "before-inspect.json", "container-id.txt"])
        for path in record.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)
        # The full inspect output, which holds the user ID, is only in the private records; the printed settings omit it.
        self.assertIn(self.user, (record / "after-inspect.json").read_text())
        self.assertIn("TRADING_MODE=paper", result.stdout)
        self.assertIn("rollback: docker stop", result.stdout)
        # The pointer files are only named, never rewritten.
        self.assertEqual(Path(self.pointers["IBKR_PAPER_TWS_FILE"]).read_text(), self.tws_fake)

    def test_refuses_a_record_directory_inside_a_git_worktree(self):
        repository = self.base / "checkout"
        (repository / ".git").mkdir(parents=True)
        linked = self.base / "linked-worktree"
        linked.mkdir()
        (linked / ".git").write_text("gitdir: /nonexistent/worktrees/x\n")
        symlinked = self.base / "state-link"
        (repository / "state").mkdir()
        symlinked.symlink_to(repository / "state")
        for label, state in (("inside a checkout", repository / "deep" / "state"),
                             ("inside a linked worktree", linked / "state"),
                             ("a symbolic link into a checkout", symlinked)):
            with self.subTest(state=label):
                self.log.unlink(missing_ok=True)
                result = self.run_script(state=state)
                self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
                self.assertIn("inside a Git worktree", result.stdout)
                self.assertEqual(self.calls(), [])  # refused before the first docker call
                self.assertEqual(self.records(state), [])
        # An unset or relative XDG_STATE_HOME means $HOME/.local/state, and a HOME inside a checkout is refused too.
        self.log.unlink(missing_ok=True)
        result = self.run_script(state="relative/state", HOME=str(repository / "home"))
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertEqual(self.calls(), [])

    def test_refuses_while_an_api_client_is_connected(self):
        result = self.run_script(connections=1)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("refused: an API client is connected; nothing changed", result.stdout)
        self.assert_nothing_changed()

    def test_refuses_without_ss_and_under_a_rootful_daemon(self):
        (self.bin / "ss").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assert_nothing_changed()
        self.log.unlink()
        result = self.run_script(rootless=False)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.calls(), ["info --format {{.SecurityOptions}}"])
        self.assert_nothing_changed()

    def test_refuses_missing_or_empty_pointer_targets(self):
        Path(self.pointers["IBKR_PAPER_TWS_FILE"]).write_text("")
        result = self.run_script()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.calls(), [])
        Path(self.pointers["IBKR_PAPER_TWS_FILE"]).write_text(self.tws_fake)
        result = self.run_script(IBKR_PAPER_VNC_FILE=str(self.base / "absent"))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_first_start_has_nothing_to_roll_back(self):
        result = self.run_script(exists=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        verbs = [call.split()[0] for call in self.calls()]
        self.assertNotIn("stop", verbs)
        self.assertNotIn("rename", verbs)
        (record,) = self.records()
        self.assertEqual(sorted(p.name for p in record.iterdir()), ["after-inspect.json", "container-id.txt"])
        self.assertNotIn("rollback: docker stop", result.stdout)
        self.assertNotIn("rollback, if", result.stdout)

    def test_a_failed_start_still_shows_the_rollback(self):
        # The old container is already stopped and renamed when `docker run -d` fails; set -e ends the run there, so the
        # way back must be on screen before the start, and it must work with no new container.
        result = self.run_script(start_fails=True)
        self.assertEqual(result.returncode, 125, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        kept = next(i for i, line in enumerate(lines) if line.startswith(f"kept for rollback: {NAME}-pre-durable-"))
        stamp = lines[kept].split("-pre-durable-", 1)[1].split()[0]
        self.assertEqual(lines[kept + 1],
                         f"rollback, if the new container does not come up: docker stop {NAME} 2>/dev/null; "
                         f"docker rename {NAME} {NAME}-durable-failed-{stamp} 2>/dev/null; "
                         f"docker rename {NAME}-pre-durable-{stamp} {NAME} && docker start {NAME}")
        verbs = [call.split()[0] for call in self.calls()]
        self.assertLess(verbs.index("rename"), max(i for i, verb in enumerate(verbs) if verb == "run"))
        self.assertNotIn("rollback record:", result.stdout)
        (record,) = self.records()
        self.assertEqual(sorted(p.name for p in record.iterdir()), ["before-inspect.json", "container-id.txt"])


if __name__ == "__main__":
    unittest.main()
