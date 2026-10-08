"""Synthetic skill-probe events; no model call or installed client acceptance.

Event contract: openai/codex rust-v0.157.1,
codex-rs/exec/src/exec_events.rs. File-read policy/echo: mksglu/context-mode
v1.0.169, src/security.ts::evaluateProjectContainment and src/server.ts.
"""

from __future__ import annotations

import contextlib
import io
import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "adoption"))
import prove_codex_lane as prove  # noqa: E402

SKILL_CODE = "print(FILE_CONTENT.splitlines()[0])"


def run(*items, exit=0, timed_out=False):
    return {"events": [{"type": "item.completed", "item": item} for item in items],
            "exit": exit, "timed_out": timed_out}


def shell_item(path, output, **overrides):
    return {"type": "command_execution", "status": "completed", "exit_code": 0,
            "command": "/bin/bash -lc " + shlex.quote("rtk cat " + shlex.quote(str(path))),
            "aggregated_output": output, **overrides}


def mcp_item(path, output, **overrides):
    return {"type": "mcp_tool_call", "server": "context-mode", "tool": "ctx_execute_file",
            "status": "completed", "error": None,
            "arguments": {"path": str(path), "language": "python", "code": SKILL_CODE},
            "result": {"content": [{"type": "text", "text": output}], "structured_content": None}, **overrides}


class SkillVerdictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skill = Path(self.tmp.name) / "installed skill" / "SKILL.md"
        self.skill.parent.mkdir()
        self.skill.write_text("# Real first line  \nA different second line.\n", encoding="utf-8")

    def test_shell_reads_the_selected_files_real_first_line_and_records_route(self):
        item = shell_item(self.skill, self.skill.read_text())
        ok, detail = prove.skill_verdict(run(item), self.skill)
        self.assertTrue(ok, detail)
        self.assertIn("route shell (rtk cat)", detail)
        self.assertIn("first line exact True", detail)
        # The expected answer comes from the actual file, never a hardcoded header.
        self.skill.write_text("# Changed first line\n", encoding="utf-8")
        self.assertFalse(prove.skill_verdict(run(item), self.skill)[0])

    def test_prompt_limits_shell_reads_to_the_forms_the_verdict_accepts(self):
        prompt = prove.skill_prompt(self.skill)
        self.assertNotIn("A direct shell read is also acceptable", prompt)
        self.assertIn("For shell reads, use only rtk cat", prompt)
        self.assertIn(shlex.join(["rtk", "cat", str(self.skill)]), prompt)
        # The review permits narrowing the prompt instead of expanding the
        # parser. All alternative reads named by the reviewer are explicit
        # negative controls, even when they return the correct first line.
        for argv, accepted in ((["rtk", "cat", str(self.skill)], True),
                               (["rtk", "cat", "--", str(self.skill)], True),
                               (["cat", str(self.skill)], False),
                               (["head", "-n", "1", str(self.skill)], False),
                               (["rtk", "read", str(self.skill)], False),
                               (["rtk", "proxy", "cat", str(self.skill)], False)):
            command = shlex.join(argv)
            for wrapped in (command, "/bin/bash -lc " + shlex.quote(command)):
                with self.subTest(command=wrapped):
                    item = shell_item(self.skill, self.skill.read_text(), command=wrapped)
                    ok, detail = prove.skill_verdict(run(item), self.skill)
                    self.assertEqual(ok, accepted, detail)
                    self.assertIn("route shell (rtk cat)" if accepted else "route none", detail)

    def test_context_mode_direct_read_accepts_only_its_stdout(self):
        for echo in ("", f"```python\n{SKILL_CODE}\n```\n\n",
                     f"path={self.skill}\n```python\n{SKILL_CODE}\n```\n\n"):
            with self.subTest(echo=bool(echo)):
                item = mcp_item(self.skill, echo + "# Real first line  \n")
                ok, detail = prove.skill_verdict(run(item), self.skill)
                self.assertTrue(ok, detail)
                self.assertIn("route context-mode ctx_execute_file", detail)

    def test_project_boundary_refusal_can_fall_back_to_rtk_cat(self):
        # Shape observed in the builder's native Codex 0.157.1 event: the
        # refusal text is in result.content, status is failed, error is null.
        refused = mcp_item(self.skill, "File access blocked: resolves outside the project root (issue #852)",
                           status="failed", error=None)
        self.assertFalse(prove.skill_verdict(run(refused), self.skill)[0])
        ok, detail = prove.skill_verdict(run(refused, shell_item(self.skill, self.skill.read_text())), self.skill)
        self.assertTrue(ok, detail)
        self.assertIn("route shell (rtk cat)", detail)

    def test_empty_file_and_missing_stdout_do_not_prove_a_blank_first_line(self):
        self.skill.write_text("", encoding="utf-8")
        self.assertFalse(prove.skill_verdict(run(mcp_item(self.skill, "\n")), self.skill)[0])
        self.skill.write_text("\nSecond line\n", encoding="utf-8")
        self.assertFalse(prove.skill_verdict(run(mcp_item(self.skill, "")), self.skill)[0])
        self.assertTrue(prove.skill_verdict(run(mcp_item(self.skill, "\n")), self.skill)[0])

    def test_prose_and_unexecuted_command_strings_do_not_prove_a_read(self):
        real_command = "rtk cat " + shlex.quote(str(self.skill))
        for command in ("echo " + shlex.quote(real_command), "false && " + real_command,
                        real_command + " || echo '# Real first line  '",
                        "rtk cat /another/SKILL.md", "echo '# Real first line  ' # " + real_command):
            with self.subTest(command=command):
                self.assertFalse(prove.skill_verdict(
                    run(shell_item(self.skill, self.skill.read_text(), command=command)), self.skill)[0])
        self.assertFalse(prove.skill_verdict(
            run({"type": "agent_message", "text": self.skill.read_text()}), self.skill)[0])

    def test_wrong_line_whitespace_missing_file_and_failed_runs_refuse(self):
        for output in ("# Real first line\n", "A different second line.\n", "", "prefix\n# Real first line  \n"):
            with self.subTest(output=output):
                self.assertFalse(prove.skill_verdict(run(shell_item(self.skill, output)), self.skill)[0])
        item = shell_item(self.skill, self.skill.read_text())
        for overrides in ({"exit_code": 1}, {"status": "failed"}, {"status": "in_progress"}):
            with self.subTest(overrides=overrides):
                self.assertFalse(prove.skill_verdict(run({**item, **overrides}), self.skill)[0])
        for options in ({"exit": 1}, {"timed_out": True}):
            self.assertFalse(prove.skill_verdict(run(item, **options), self.skill)[0])
        self.skill.unlink()
        self.assertFalse(prove.skill_verdict(run(item), self.skill)[0])

    def test_mcp_wrong_arguments_and_errors_cannot_pass_with_the_right_line(self):
        good = mcp_item(self.skill, "# Real first line  \n")
        for changed in ({"path": "/another/SKILL.md"}, {"code": "print('# Real first line  ')"},
                        {"language": "shell"}, {"code": SKILL_CODE + "; print('spoof')"}):
            with self.subTest(changed=changed):
                item = {**good, "arguments": {**good["arguments"], **changed}}
                self.assertFalse(prove.skill_verdict(run(item), self.skill)[0])
        for changed in ({"status": "failed"}, {"error": {"message": "read failed"}}):
            with self.subTest(changed=changed):
                self.assertFalse(prove.skill_verdict(run({**good, **changed}), self.skill)[0])
        # A code echo alone is never the actual first-line output.
        echoed = mcp_item(self.skill, f"```python\n{SKILL_CODE}\n```\n\n")
        self.assertFalse(prove.skill_verdict(run(echoed), self.skill)[0])
        started = {"events": [{"type": "item.started", "item": good}], "exit": 0, "timed_out": False}
        self.assertFalse(prove.skill_verdict(started, self.skill)[0])


class SkillLaunchTests(unittest.TestCase):
    def test_live_probe_uses_installed_skill_and_persists_the_observed_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            worker_env = {"CODEX_HOME": str(codex_home)}
            skill = root / ".agents" / "skills" / "example" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# Unprompted answer\n", encoding="utf-8")
            launched = []

            def workers(specs, timeout):
                launched.extend(specs)
                return [{"name": spec["name"], "exit": 0, "timed_out": False, "seconds": 0.1,
                         "cleanup_error": None,
                         "events": run(shell_item(skill, skill.read_text()))["events"]}
                        for spec in specs]

            report = root / "report.json"
            with mock.patch.object(Path, "home", return_value=root), \
                 mock.patch.object(prove, "make_repo", return_value=b"fixture"), \
                 mock.patch.object(prove, "static_checks"), \
                 mock.patch.object(prove, "quota_gate", return_value=(True, "synthetic gate")), \
                 mock.patch.object(prove, "worker_env", return_value=worker_env) as env_factory, \
                 mock.patch.object(prove, "run_workers", side_effect=workers), \
                 mock.patch.object(prove, "pwd_verdict", return_value=(True, "synthetic")), \
                 mock.patch.object(prove, "approval_verdict", return_value=(True, "synthetic")), \
                 mock.patch.object(prove, "rtk_verdict", return_value=(True, "synthetic")), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = prove.main(["--codex", "/synthetic/codex", "--codex-home", str(codex_home),
                                   "--provider", "native", "--live", "--json", str(report)])
            env_factory.assert_called_once_with(codex_home, provider="native")
            self.assertEqual(code, 0)
            data = json.loads(report.read_text())
        self.assertEqual(len(launched), 6)
        self.assertTrue(all(spec["env"] == worker_env for spec in launched))
        probe = next(spec for spec in launched if spec["name"] == "skill-worker")
        prompt = probe["argv"][-1]
        self.assertIn(str(skill), prompt)
        self.assertIn("ctx_execute_file", prompt)
        self.assertIn("rtk cat", prompt)
        self.assertNotIn("# Unprompted answer", prompt)
        self.assertEqual(probe["argv"], prove.exec_argv("/synthetic/codex", prompt, True, provider="native"))
        row = next(row for row in data["checks"] if row["check"] == "skill-worker")
        self.assertTrue(row["ok"])
        self.assertIn("route shell (rtk cat)", row["detail"])
        self.assertEqual(len(data["live_runs"]), 6)

    def test_missing_installed_skill_fails_without_fabricating_a_sixth_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            worker_env = {"CODEX_HOME": str(codex_home)}
            report = root / "report.json"

            def workers(specs, timeout):
                return [{"name": spec["name"], "exit": 0, "timed_out": False, "seconds": 0,
                         "cleanup_error": None, "events": []} for spec in specs]

            with mock.patch.object(Path, "home", return_value=root), \
                 mock.patch.object(prove, "make_repo", return_value=b"fixture"), \
                 mock.patch.object(prove, "static_checks"), \
                 mock.patch.object(prove, "quota_gate", return_value=(True, "synthetic gate")), \
                 mock.patch.object(prove, "worker_env", return_value=worker_env) as env_factory, \
                 mock.patch.object(prove, "run_workers", side_effect=workers), \
                 mock.patch.object(prove, "pwd_verdict", return_value=(True, "synthetic")), \
                 mock.patch.object(prove, "approval_verdict", return_value=(True, "synthetic")), \
                 mock.patch.object(prove, "rtk_verdict", return_value=(True, "synthetic")), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = prove.main(["--codex", "/synthetic/codex", "--codex-home", str(codex_home),
                                   "--provider", "native", "--live", "--json", str(report)])
            env_factory.assert_called_once_with(codex_home, provider="native")
            self.assertEqual(code, 1)
            data = json.loads(report.read_text())
        row = next(row for row in data["checks"] if row["check"] == "skill-worker")
        self.assertFalse(row["ok"])
        self.assertIn("SKILL.md", row["detail"])
        self.assertEqual(len(data["live_runs"]), 5)


if __name__ == "__main__":
    unittest.main()
