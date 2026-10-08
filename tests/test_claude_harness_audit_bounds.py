"""The bounded harness audit: run its guard and accounting steps on synthetic inputs.

No model, network or credential is involved. The shell of each step is taken from
.github/workflows/harness-audit.yml as written and executed with a throwaway HOME and
RUNNER_TEMP, so the tests fail when the workflow's own text stops enforcing a bound.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # the macOS job installs no package; the hosted validate job has PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/harness-audit.yml"
ACTION = "anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b"
TRANSCRIPT_MARKER = "SYNTHETIC-TRANSCRIPT-TEXT-MUST-NOT-LEAVE-THE-RUNNER"
SETTINGS_MARKER = "SYNTHETIC-SETTINGS-CONTENT-MUST-NOT-BE-PRINTED"


def job():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["audit"]


def step(name):
    return next(item for item in job()["steps"] if item.get("name") == name)


def model_usage(read=160000, cost=0.7):
    return {"claude-opus-5-5": {"inputTokens": 30000, "outputTokens": 20000, "cacheReadInputTokens": read,
                                "cacheCreationInputTokens": 30000, "costUSD": cost}}


def execution(result=None, **changes):
    final = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 9,
             "total_cost_usd": 0.7, "modelUsage": model_usage(), "result": "Scorecard\nFinding 1"}
    final.update(changes)
    if result is not None:
        final["result"] = result
    return [{"type": "assistant", "message": {"content": [{"type": "text", "text": TRANSCRIPT_MARKER}]}}, final]


def run_step(name, execution_file=None, env_changes=None, settings=None):
    """Run one step's shell; returns (exit code, console text, summary text, usage.json text or None)."""
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        home = directory / "home"
        home.mkdir()
        if settings == "file":
            (home / ".claude").mkdir()
            (home / ".claude/settings.json").write_text(SETTINGS_MARKER, encoding="utf-8")
        elif settings == "dangling-symlink":
            (home / ".claude").mkdir()
            (home / ".claude/settings.json").symlink_to(directory / "missing-target")
        summary = directory / "summary.md"
        env = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "HOME": str(home),
               "RUNNER_TEMP": str(directory), "GITHUB_STEP_SUMMARY": str(summary), "TMPDIR": str(directory)}
        if execution_file is not None:
            path = directory / "claude-execution-output.json"
            path.write_text(execution_file if isinstance(execution_file, str) else json.dumps(execution_file),
                            encoding="utf-8")
            env["EXECUTION_FILE"] = str(path)
        env.update(env_changes or {})
        done = subprocess.run(["bash", "-c", step(name)["run"]], env=env, capture_output=True, text=True,
                              check=False)
        usage = directory / "harness-audit-usage/usage.json"
        return (done.returncode, done.stdout + done.stderr,
                summary.read_text(encoding="utf-8") if summary.exists() else "",
                usage.read_text(encoding="utf-8") if usage.exists() else None)


GUARD = "Refuse debug logging and pre-existing Claude settings"
NUMBERS = "Keep the run's numbers and check the bounds"
REPORT = "Publish the report to the job summary"


@unittest.skipUnless(yaml, "PyYAML is needed to read the workflow's steps")
class HarnessAuditShapeTests(unittest.TestCase):
    def test_the_job_needs_main_this_repository_and_the_enabling_variable(self):
        condition = " ".join(job()["if"].split())
        for clause in ("github.repository == 'seathatflowsinourveins/native-agent-stack'",
                       "github.ref == 'refs/heads/main'",
                       "vars.CLAUDE_HARNESS_AUDIT_ENABLED == 'true'",
                       "(github.event_name == 'schedule' || github.actor == github.repository_owner)"):
            self.assertIn(clause, condition)
        self.assertEqual(condition.count("&&"), 3)
        self.assertEqual(condition.count("||"), 1)

    def test_the_job_holds_the_oidc_token_and_no_write_scope(self):
        self.assertEqual(job()["permissions"], {"contents": "read", "id-token": "write"})

    def test_the_action_is_pinned_and_takes_federation_inputs_only(self):
        run = step("Run the audit")
        self.assertEqual(run["uses"], ACTION)
        inputs = run["with"]
        for forbidden in ("anthropic_api_key", "claude_code_oauth_token", "allowed_non_write_users", "allowed_bots"):
            self.assertNotIn(forbidden, inputs)
        for name in ("anthropic_federation_rule_id", "anthropic_organization_id",
                     "anthropic_service_account_id", "anthropic_workspace_id"):
            self.assertRegex(inputs[name], r"^\$\{\{ vars\.[A-Z_]+ \}\}$")
        self.assertEqual(inputs["show_full_output"], "false")
        self.assertNotIn("secrets.", json.dumps({k: v for k, v in inputs.items() if k != "github_token"}))

    def test_claude_has_three_read_tools_and_fixed_bounds(self):
        arguments = step("Run the audit")["with"]["claude_args"].split("\n")
        arguments = [line.strip() for line in arguments if line.strip()]
        for expected in ("--model claude-opus-5-5", "--max-turns 20", "--max-budget-usd 3",
                         "--tools Read,Glob,Grep", "--allowedTools Read,Glob,Grep",
                         "--setting-sources user", "--strict-mcp-config"):
            self.assertIn(expected, arguments)
        joined = " ".join(arguments)
        for tool in ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "Agent", "mcp__"):
            self.assertNotIn(tool, joined)
        for flag in ("--debug", "--dangerously-skip-permissions", "--permission-mode", "--mcp-config"):
            self.assertNotIn(flag, joined)

    def test_settings_turn_hooks_off_and_keep_reads_inside_the_working_directories(self):
        settings = json.loads(step("Run the audit")["with"]["settings"])
        self.assertIs(settings["disableAllHooks"], True)
        self.assertIs(settings["permissions"]["blockReadsOutsideWorkingDirectories"], True)
        self.assertIn("Read(./.git/**)", settings["permissions"]["deny"])
        self.assertNotIn("allow", settings["permissions"])

    def test_the_guard_runs_before_checkout_and_before_the_action(self):
        names = [item.get("name") for item in job()["steps"]]
        self.assertLess(names.index(GUARD), names.index("Check out"))
        self.assertLess(names.index(GUARD), names.index("Run the audit"))

    def test_the_report_is_published_only_after_the_bounds_check_passed(self):
        self.assertIn("success()", step(REPORT)["if"])
        self.assertIn("always()", step(NUMBERS)["if"])
        names = [item.get("name") for item in job()["steps"]]
        self.assertLess(names.index(NUMBERS), names.index(REPORT))

    def test_only_the_numeric_record_is_uploaded(self):
        upload = step("Keep the numeric usage record")
        self.assertTrue(upload["with"]["path"].endswith("/harness-audit-usage/usage.json"))
        self.assertNotIn("execution", upload["with"]["path"])


@unittest.skipUnless(yaml and shutil.which("jq"), "PyYAML and jq are needed to run the workflow's steps")
class HarnessAuditStepTests(unittest.TestCase):
    def test_a_clean_runner_passes_the_guard(self):
        code, console, _, _ = run_step(GUARD)
        self.assertEqual(code, 0, console)

    def test_each_debug_signal_stops_the_job(self):
        for name, value in (("ACTIONS_STEP_DEBUG", "true"), ("ACTIONS_RUNNER_DEBUG", "true"),
                            ("RUNNER_DEBUG", "1"), ("RUNNER_DEBUG_SIGNAL", "1")):
            with self.subTest(signal=name):
                code, console, _, _ = run_step(GUARD, env_changes={name: value})
                self.assertEqual(code, 2)
                self.assertIn("debug logging is enabled", console)

    def test_a_pre_existing_settings_file_or_link_stops_the_job_unread(self):
        for kind in ("file", "dangling-symlink"):
            with self.subTest(kind=kind):
                code, console, _, _ = run_step(GUARD, settings=kind)
                self.assertEqual(code, 2)
                self.assertNotIn(SETTINGS_MARKER, console)

    def test_a_bounded_cached_run_is_accepted_and_only_numbers_are_kept(self):
        code, console, summary, usage = run_step(NUMBERS, execution())
        self.assertEqual(code, 0, console)
        record = json.loads(usage)
        self.assertEqual(sorted(record), ["models", "num_turns", "successful_result", "total_cost_usd"])
        self.assertEqual(sorted(record["models"][0]), ["cache_creation_input_tokens", "cache_read_input_tokens",
                                                       "cost_usd", "input_tokens", "model", "output_tokens"])
        for text in (usage, summary, console):
            self.assertNotIn(TRANSCRIPT_MARKER, text)
            self.assertNotIn("Scorecard", text)
        self.assertIn("| 9 | 0.7 | true |", summary)

    def test_an_unmet_bound_fails_after_the_numbers_were_kept(self):
        cases = {
            "no cache read": {"modelUsage": model_usage(read=0)},
            "over the client budget": {"total_cost_usd": 3.01},
            "over the turn limit": {"num_turns": 21},
            "an error result": {"is_error": True},
            "a turn-limit stop": {"subtype": "error_max_turns"},
            "a budget stop": {"subtype": "error_max_budget_usd"},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                code, _, _, usage = run_step(NUMBERS, execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertIsNotNone(usage)
                self.assertIsInstance(json.loads(usage)["total_cost_usd"], (int, float))

    def test_an_unreadable_execution_file_fails(self):
        broken = {
            "an object, not a message list": {"type": "result"},
            "no result message": [{"type": "assistant"}],
            "no model usage": execution(modelUsage={}),
            "a text cost": execution(total_cost_usd="0.7"),
            "a fractional token count": execution(modelUsage={"m": {"inputTokens": 1.5, "outputTokens": 1,
                                                                   "cacheReadInputTokens": 1,
                                                                   "cacheCreationInputTokens": 1, "costUSD": 0.1}}),
            "not JSON": "not json at all",
        }
        for label, content in broken.items():
            with self.subTest(case=label):
                code, _, summary, _ = run_step(NUMBERS, content)
                self.assertNotEqual(code, 0)
                self.assertNotIn("completed", summary)

    def test_the_report_is_escaped_preformatted_and_capped(self):
        hostile = "<script>alert(1)</script> ![x](https://example.invalid/a.png) & [link](https://example.invalid)\n"
        code, console, summary, _ = run_step(REPORT, execution(result=hostile + "A" * 200000))
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>", summary)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", summary)
        self.assertIn("&amp;", summary)
        self.assertNotIn("<script>", summary)
        self.assertLess(len(summary.encode("utf-8")), 61000)
        self.assertNotIn(TRANSCRIPT_MARKER, summary)

    def test_a_run_without_result_text_publishes_an_empty_report(self):
        final = execution()
        del final[-1]["result"]
        code, console, summary, _ = run_step(REPORT, final)
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>", summary)


if __name__ == "__main__":
    unittest.main()
