"""The bounded harness audit: run its guard and accounting steps on synthetic inputs.

No model, network or credential is involved. The shell of each step is taken from
.github/workflows/harness-audit.yml as written and executed with a throwaway HOME and
RUNNER_TEMP, so the tests fail when the workflow's own text stops enforcing a bound.
"""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_workflow_policy import load_workflow

try:
    import yaml
except ImportError:  # the macOS job installs no package; the hosted validate job has PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/harness-audit.yml"
ACTION = "anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b"
TRANSCRIPT_MARKER = "SYNTHETIC-TRANSCRIPT-TEXT-MUST-NOT-LEAVE-THE-RUNNER"
SETTINGS_MARKER = "SYNTHETIC-SETTINGS-CONTENT-MUST-NOT-BE-PRINTED"

GUARD = "Refuse debug logging and pre-existing Claude settings"
AUDIT = "Run the audit"
NUMBERS = "Keep the run's numbers and check the bounds"
REPORT = "Publish the report to the job summary"


def job():
    text = WORKFLOW.read_text(encoding="utf-8")
    return (yaml.safe_load(text) if yaml else load_workflow(text))["jobs"]["audit"]


def step(name):
    return next(item for item in job()["steps"] if item.get("name") == name)


def arguments():
    return [line.strip() for line in step(AUDIT)["with"]["claude_args"].split("\n") if line.strip()]


def cli_settings():
    """The JSON the workflow passes to Claude Code with --settings, as the action's parser sees it."""
    (line,) = [line for line in arguments() if line.startswith("--settings ")]
    (value,) = shlex.split(line)[1:]
    return json.loads(value)


def model_usage(read=160000, cost=0.7):
    return {"claude-opus-5-5": {"inputTokens": 30000, "outputTokens": 20000, "cacheReadInputTokens": read,
                                "cacheCreationInputTokens": 30000, "costUSD": cost}}


def execution(result=None, tools=("Read", "Glob", "Grep"), mcp_servers=(), init=True, turns=None, lists=True,
              **changes):
    final = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 9,
             "total_cost_usd": 0.7, "modelUsage": model_usage(), "result": "Scorecard\nFinding 1"}
    final.update(changes)
    if result is not None:
        final["result"] = result
    messages = []
    if init:
        start = {"type": "system", "subtype": "init", "claude_code_version": "2.1.295"}
        if lists:
            start.update(tools=list(tools), mcp_servers=list(mcp_servers))
        messages.append(start)
    for turn in range(final["num_turns"] if turns is None else turns):
        # The client streams one message per content block, so one API turn spans several messages with one id.
        messages.append({"type": "assistant", "message": {"id": f"msg_{turn:02d}", "content": [
            {"type": "thinking", "thinking": ""}]}})
        messages.append({"type": "assistant", "message": {"id": f"msg_{turn:02d}", "content": [
            {"type": "text", "text": TRANSCRIPT_MARKER}]}})
    messages.append(final)
    return messages


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


@unittest.skipUnless(yaml, "PyYAML is needed to read the workflow's steps")
class HarnessAuditShapeTests(unittest.TestCase):
    def test_the_job_needs_main_this_repository_a_first_attempt_and_the_enabling_variable(self):
        condition = " ".join(job()["if"].split())
        for clause in ("github.repository == 'seathatflowsinourveins/native-agent-stack'",
                       "github.ref == 'refs/heads/main'",
                       "github.run_attempt == 1",
                       "vars.CLAUDE_HARNESS_AUDIT_ENABLED == 'true'",
                       "(github.event_name == 'schedule' || (github.actor == github.repository_owner && "
                       "github.triggering_actor == github.repository_owner))"):
            self.assertIn(clause, condition)
        self.assertEqual(condition.count("&&"), 5)
        self.assertEqual(condition.count("||"), 1)

    def test_the_job_holds_the_oidc_token_and_no_write_scope(self):
        self.assertEqual(job()["permissions"], {"contents": "read", "id-token": "write"})

    def test_the_action_is_pinned_and_takes_federation_inputs_only(self):
        run = step(AUDIT)
        self.assertEqual(run["uses"], ACTION)
        self.assertEqual(run["env"], {"ACTIONS_STEP_DEBUG": "false"})
        inputs = run["with"]
        for forbidden in ("anthropic_api_key", "claude_code_oauth_token", "allowed_non_write_users", "allowed_bots",
                          "plugins", "plugin_marketplaces"):
            self.assertNotIn(forbidden, inputs)
        for name in ("anthropic_federation_rule_id", "anthropic_organization_id",
                     "anthropic_service_account_id", "anthropic_workspace_id"):
            self.assertRegex(inputs[name], r"^\$\{\{ vars\.[A-Z_]+ \}\}$")
        self.assertEqual(inputs["show_full_output"], "false")
        self.assertEqual(inputs["display_report"], "false")
        self.assertEqual(inputs["track_progress"], "false")
        text = WORKFLOW.read_text(encoding="utf-8")
        for static_credential in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertNotIn(static_credential, text)

    def test_claude_has_three_read_tools_and_fixed_bounds(self):
        for expected in ("--model claude-opus-5-5", "--effort max", "--max-turns 20", "--max-budget-usd 3",
                         "--tools Read,Glob,Grep", "--allowedTools Read,Glob,Grep",
                         "--restricted", "--permission-prompts none",
                         "--setting-sources user", "--strict-mcp-config"):
            self.assertIn(expected, arguments())
        joined = " ".join(line for line in arguments() if not line.startswith("--settings "))
        for tool in ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "Agent", "mcp__"):
            self.assertNotIn(tool, joined)
        for flag in ("--debug", "--dangerously-skip-permissions", "--permission-mode", "--mcp-config"):
            self.assertNotIn(flag, joined)

    def test_settings_turn_hooks_off_and_deny_every_git_directory(self):
        # --restricted ignores every settings file, so the rules travel in --settings, not in the action's input.
        self.assertNotIn("settings", step(AUDIT)["with"])
        settings = cli_settings()
        self.assertIs(settings["disableAllHooks"], True)
        self.assertIs(settings["permissions"]["blockReadsOutsideWorkingDirectories"], True)
        for rule in ("Read(./.git/**)", "Read(./**/.git/**)"):
            self.assertIn(rule, settings["permissions"]["deny"])
        self.assertNotIn("allow", settings["permissions"])

    def test_the_guard_runs_before_checkout_and_before_the_action(self):
        names = [item.get("name") for item in job()["steps"]]
        self.assertEqual(names[0], "Harden the runner (audit-only network egress)")
        self.assertLess(names.index(GUARD), names.index("Check out"))
        self.assertLess(names.index(GUARD), names.index(AUDIT))

    def test_a_green_run_always_has_an_execution_file(self):
        check = step("Require the run's execution file")
        self.assertEqual(check["if"], "${{ success() && steps.claude_audit.outputs.execution_file == '' }}")
        self.assertIn("exit 1", check["run"])

    def test_the_report_is_published_only_after_the_bounds_check_passed(self):
        self.assertIn("success()", step(REPORT)["if"])
        self.assertIn("always()", step(NUMBERS)["if"])
        names = [item.get("name") for item in job()["steps"]]
        self.assertLess(names.index(NUMBERS), names.index(REPORT))

    def test_only_the_numeric_record_is_uploaded(self):
        upload = step("Keep the numeric usage record")
        self.assertTrue(upload["with"]["path"].endswith("/harness-audit-usage/usage.json"))
        self.assertNotIn("execution", upload["with"]["path"])


@unittest.skipUnless(shutil.which("jq"), "jq is needed to run the workflow's steps")
class HarnessAuditStepTests(unittest.TestCase):
    def test_a_clean_runner_passes_the_guard(self):
        code, console, _, _ = run_step(GUARD)
        self.assertEqual(code, 0, console)

    def test_the_guard_binds_debug_logging_set_as_a_repository_secret_or_variable(self):
        # GitHub's "Enabling debug logging": step debug logging and runner diagnostic logging are each enabled by a
        # secret or a variable of that name, the secret taking precedence; neither reaches a step's shell unbound.
        env = step(GUARD)["env"]
        self.assertEqual(env["STEP_DEBUG_SETTING"],
                         "${{ (secrets.ACTIONS_STEP_DEBUG || vars.ACTIONS_STEP_DEBUG) == 'true' }}")
        self.assertEqual(env["RUNNER_DIAGNOSTICS_SETTING"],
                         "${{ (secrets.ACTIONS_RUNNER_DEBUG || vars.ACTIONS_RUNNER_DEBUG) == 'true' }}")
        self.assertEqual(env["RUNNER_DEBUG_SIGNAL"], "${{ runner.debug }}")

    def test_each_debug_signal_stops_the_job(self):
        for name, value in (("ACTIONS_STEP_DEBUG", "true"), ("ACTIONS_RUNNER_DEBUG", "true"),
                            ("RUNNER_DEBUG", "1"), ("RUNNER_DEBUG_SIGNAL", "1"), ("STEP_DEBUG_SETTING", "true"),
                            ("RUNNER_DIAGNOSTICS_SETTING", "true")):
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

    def test_a_bounded_cached_read_only_run_is_accepted_and_only_numbers_and_fixed_names_are_kept(self):
        code, console, summary, usage = run_step(NUMBERS, execution())
        self.assertEqual(code, 0, console)
        record = json.loads(usage)
        self.assertEqual(sorted(record), ["assistant_turns", "claude_code_version", "forbidden_tools", "mcp_servers", "models", "num_turns", "result_chars", "result_subtype", "session_started", "successful_result", "tools", "tools_listed", "total_cost_usd"])
        self.assertEqual(record["result_subtype"], "success")
        self.assertEqual(record["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(sorted(record["models"][0]), ["cache_creation_input_tokens", "cache_read_input_tokens",
                                                       "cost_usd", "input_tokens", "model", "output_tokens"])
        for text in (usage, summary, console):
            self.assertNotIn(TRANSCRIPT_MARKER, text)
            self.assertNotIn("Scorecard", text)
        self.assertIn("| 9 | 9 | 0.7 | true | success | 2.1.295 | Read Glob Grep | 0 |", summary)

    def test_an_unmet_bound_fails_after_the_numbers_were_kept(self):
        cases = {
            "no cache read": {"modelUsage": model_usage(read=0)},
            "over the client budget": {"total_cost_usd": 3.01},
            "over the turn limit": {"turns": 21},
            "an error result": {"is_error": True},
            "a turn-limit stop": {"subtype": "error_max_turns"},
            "a budget stop": {"subtype": "error_max_budget_usd"},
            "a shell tool in the session": {"tools": ("Read", "Glob", "Grep", "Bash")},
            "a write tool in the session": {"tools": ("Read", "Write")},
            "an MCP tool in the session": {"tools": ("Read", "mcp__github__create_issue")},
            "an MCP server in the session": {"mcp_servers": ({"name": "x", "status": "connected"},)},
            "no session start record": {"init": False},
            "a tool outside the allow-list": {"tools": ("Read", "Glob", "Grep", "Skill")},
            "no tool or MCP list in the session start record": {"lists": False},
            "no result text": {"result": ""},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                code, _, _, usage = run_step(NUMBERS, execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertIsInstance(json.loads(usage)["total_cost_usd"], (int, float))

    def test_the_step_names_every_unmet_bound(self):
        code, console, *_ = run_step(NUMBERS, execution(turns=21, total_cost_usd=3.5,
                                                         tools=("Read", "Skill"), result=""))
        self.assertNotEqual(code, 0)
        for words in ("21 assistant turns, outside 1 to 20", "above 3", "Skill", "no result text"):
            self.assertIn(words, console)

    def test_a_run_that_did_not_succeed_is_named_by_its_result_subtype(self):
        # A turn-limit stop and a budget stop call for different changes, so the record, the summary row and the
        # failure message each carry the result's subtype; a success result flagged as an error keeps its own.
        cases = {
            "error_max_turns": {"subtype": "error_max_turns", "is_error": True},
            "error_max_budget_usd": {"subtype": "error_max_budget_usd", "is_error": True},
            "success": {"is_error": True},
        }
        for subtype, changes in cases.items():
            with self.subTest(subtype=subtype):
                code, console, summary, usage = run_step(NUMBERS, execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertEqual(json.loads(usage)["result_subtype"], subtype)
                self.assertIn(f"| false | {subtype} | 2.1.295 |", summary)
                self.assertIn(f"the run did not end in success (subtype {subtype})", console)
        log = execution()
        del log[-1]["subtype"]
        code, console, _, usage = run_step(NUMBERS, log)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(usage)["result_subtype"], "unknown")
        self.assertIn("the run did not end in success (subtype unknown)", console)

    def test_the_summary_tables_are_well_formed(self):
        # Every row of each table has as many cells as its header, the result subtype column included.
        for subtype in ("success", "error_max_turns"):
            with self.subTest(subtype=subtype):
                _, _, summary, _ = run_step(NUMBERS, execution(subtype=subtype))
                tables = [block.splitlines() for block in summary.split("\n\n") if block.startswith("|")]
                self.assertEqual(len(tables), 2, summary)
                for table in tables:
                    self.assertGreaterEqual(len(table), 3, table)
                    self.assertEqual({row.count("|") for row in table}, {table[0].count("|")}, table)

    def test_the_turn_bound_counts_assistant_turns_not_transcript_messages(self):
        # On Claude Code 2.1.295 a 12-request run with parallel reads reported num_turns 57 (api-actions LR
        # receipt, 2026-10-08): num_turns counts transcript messages, tool results included.
        code, console, *_ = run_step(NUMBERS, execution_file=execution(turns=20, num_turns=57))
        self.assertEqual(code, 0, console)
        code, *_ = run_step(NUMBERS, execution_file=execution(turns=21, num_turns=21))
        self.assertNotEqual(code, 0)

    def test_names_that_are_not_plain_identifiers_are_replaced(self):
        hostile = "<img src=x onerror=alert(1)> | injected"
        log = execution(tools=("Read", hostile), modelUsage={hostile: model_usage()["claude-opus-5-5"]})
        log[0]["claude_code_version"] = hostile
        log[-1]["subtype"] = hostile
        _, console, summary, usage = run_step(NUMBERS, log)
        for text in (usage, summary, console):
            self.assertNotIn("onerror", text)
        record = json.loads(usage)
        self.assertEqual(record["tools"], ["Read", "other"])
        self.assertEqual(record["models"][0]["model"], "other")
        self.assertEqual(record["claude_code_version"], "other")
        self.assertEqual(record["result_subtype"], "other")
        self.assertIn("the run did not end in success (subtype other)", console)

    def test_an_unreadable_execution_file_fails_and_leaves_no_record(self):
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
                code, _, summary, usage = run_step(NUMBERS, content)
                self.assertNotEqual(code, 0)
                self.assertIsNone(usage, "a failed extraction must not leave an empty record to upload")
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
        self.assertIn("bytes; the first 60,000 are shown.", summary)

    def test_a_report_of_exactly_the_cap_has_no_notice_and_one_byte_more_has_one(self):
        # J8 micro read of #892 (2026-10-09): `jq -r` added a newline, so a 60,000-byte report was announced as cut.
        code, console, summary, *_ = run_step(REPORT, execution(result="a" * 60000))
        self.assertEqual(code, 0, console)
        self.assertIn("a" * 60000, summary)
        self.assertNotIn("are shown.", summary)
        code, console, summary, *_ = run_step(REPORT, execution(result="a" * 60001))
        self.assertEqual(code, 0, console)
        self.assertIn("The report is 60001 bytes; the first 60,000 are shown.", summary)

    def test_the_cap_never_splits_a_character_and_a_short_report_has_no_notice(self):
        code, console, summary, _ = run_step(REPORT, execution(result="a" + "é" * 40000))
        self.assertEqual(code, 0, console)
        summary.encode("utf-8")  # the summary file decoded as UTF-8 when it was read
        self.assertNotIn("\ufffd", summary)
        code, console, summary, _ = run_step(REPORT, execution(result="short report"))
        self.assertNotIn("are shown.", summary)

    def test_the_report_is_the_last_result_with_text(self):
        log = execution(result="the report")
        log.append({"type": "result", "subtype": "success", "is_error": False, "num_turns": 0, "result": "",
                    "total_cost_usd": 0.7, "modelUsage": model_usage()})
        code, console, summary, _ = run_step(REPORT, log)
        self.assertEqual(code, 0, console)
        self.assertIn("the report", summary)

    def test_a_run_without_result_text_publishes_an_empty_report(self):
        final = execution()
        del final[-1]["result"]
        code, console, summary, _ = run_step(REPORT, final)
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>", summary)


if __name__ == "__main__":
    unittest.main()
