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

# The whole of claude_args, each line split with shlex.split as cli_settings() splits the --settings line. GitHub
# substitutes ${{ runner.temp }} before the action parses the text, so its three tokens here are the workflow's text,
# not the value Claude Code receives.
SETTINGS_TEXT = ('{"disableAllHooks":true,"permissions":{"blockReadsOutsideWorkingDirectories":true,"deny":['
                 '"Read(./.git/**)","Read(./**/.git/**)","Read(./**/.env)","Read(./**/.env.*)","Read(./**/*.pem)",'
                 '"Read(./**/*.key)"]}}')
CLAUDE_ARGS = ["--model", "claude-opus-5-5", "--effort", "max", "--max-budget-usd", "5",
               "--tools", "Read,Glob,Grep", "--allowedTools", "Read,Glob,Grep", "--restricted",
               "--permission-prompts", "none", "--setting-sources", "user", "--strict-mcp-config",
               "--settings", SETTINGS_TEXT, "--add-dir", "${{", "runner.temp", "}}/harness-audit"]
SETTINGS = {"disableAllHooks": True,
            "permissions": {"blockReadsOutsideWorkingDirectories": True,
                            "deny": ["Read(./.git/**)", "Read(./**/.git/**)", "Read(./**/.env)", "Read(./**/.env.*)",
                                     "Read(./**/*.pem)", "Read(./**/*.key)"]}}

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
        # Codex P2 thread at harness-audit.yml:125 (R10): no CLAUDE.md memory file loads in the audit session.
        self.assertEqual(run["env"], {"ACTIONS_STEP_DEBUG": "false", "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"})
        inputs = run["with"]
        # The complete reviewed input set (J8 micro N8; GPT read of 0cf13fc2): an input added to the action step, such
        # as claude_code_version or settings, fails here even when no test names it.
        self.assertEqual(sorted(inputs), ["anthropic_federation_rule_id", "anthropic_organization_id",
                                          "anthropic_service_account_id", "anthropic_workspace_id", "claude_args",
                                          "display_report", "github_token", "prompt", "show_full_output",
                                          "track_progress"])
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
        for expected in ("--model claude-opus-5-5", "--effort max", "--max-budget-usd 5",
                         "--tools Read,Glob,Grep", "--allowedTools Read,Glob,Grep",
                         "--restricted", "--permission-prompts none",
                         "--setting-sources user", "--strict-mcp-config"):
            self.assertIn(expected, arguments())
        joined = " ".join(line for line in arguments() if not line.startswith("--settings "))
        for tool in ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "Agent", "mcp__"):
            self.assertNotIn(tool, joined)
        # No --max-turns: the action fails a success whose num_turns exceeds it, and num_turns counts transcript
        # messages, not turns. The numbers step bounds the assistant turns instead.
        for flag in ("--debug", "--dangerously-skip-permissions", "--permission-mode", "--mcp-config", "--max-turns"):
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

    def test_claude_args_and_the_settings_json_are_pinned_exactly(self):
        # The checks above look for one flag or rule at a time, so a widened or repeated --add-dir, a second turn or
        # budget flag, or a new settings key such as permissions.additionalDirectories passed them (command center
        # security read of #892, 2026-10-09). These compare the whole token list and the whole JSON.
        self.assertEqual([token for line in arguments() for token in shlex.split(line)], CLAUDE_ARGS)
        # Canonical JSON, not dict equality: in Python 1 == True, so a dict comparison passes "disableAllHooks": 1.
        self.assertEqual(json.dumps(cli_settings(), sort_keys=True, separators=(",", ":")),
                         json.dumps(SETTINGS, sort_keys=True, separators=(",", ":")))

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
        # The action fails its own step on a budget stop, so the report step reads the check's outcome (R6).
        self.assertEqual(step(NUMBERS)["id"], "bounds")
        self.assertEqual(step(REPORT)["if"], "${{ !cancelled() && steps.bounds.outcome == 'success' }}")
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
            "over the cost bound": {"total_cost_usd": 5.51},
            "over the turn limit": {"turns": 21},
            "an error result": {"is_error": True},
            "a turn-limit stop": {"subtype": "error_max_turns"},
            "a budget stop above the cost bound": {"subtype": "error_max_budget_usd", "total_cost_usd": 5.51},
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

    def test_a_non_string_tool_entry_is_a_forbidden_tool(self):
        # GPT designated read of #895 (2026-10-09, P2): the step filtered non-string entries out of the session's tool
        # list, so a list holding {"name": "Bash"}, null or 17 passed the bounds and reached publication.
        for entry in ({"name": "Bash"}, None, 17):
            with self.subTest(entry=entry):
                code, console, _, usage = run_step(NUMBERS, execution(tools=("Read", "Glob", "Grep", entry)))
                self.assertNotEqual(code, 0)
                self.assertIn("Bounds not met: tools outside Read, Glob and Grep: non-string tool entry\n", console)
                self.assertEqual(json.loads(usage)["forbidden_tools"], ["non-string tool entry"])

    def test_the_step_names_every_unmet_bound(self):
        code, console, *_ = run_step(NUMBERS, execution(turns=21, total_cost_usd=6.5,
                                                         tools=("Read", "Skill"), result=""))
        self.assertNotEqual(code, 0)
        for words in ("21 assistant turns, outside 1 to 20", "6.5 USD, above 5.5", "Skill", "no result text"):
            self.assertIn(words, console)

    def test_a_run_that_did_not_succeed_is_named_by_its_result_subtype(self):
        # A turn-limit stop and a budget stop call for different changes, so the record, the summary row and the
        # failure message each carry the result's subtype; a success result flagged as an error keeps its own. A
        # budget stop fails only above the cost bound (R6).
        cases = {
            "error_max_turns": {"subtype": "error_max_turns", "is_error": True},
            "error_max_budget_usd": {"subtype": "error_max_budget_usd", "is_error": True, "total_cost_usd": 5.51},
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
        # Every row of each table has as many cells as its header, the result subtype column included, and a budget
        # stop's note stays outside the tables.
        for subtype in ("success", "error_max_turns", "error_max_budget_usd"):
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
        # The lower bound too: a run with no assistant message fails, although its num_turns of 9 is within bounds.
        code, console, *_ = run_step(NUMBERS, execution_file=execution(turns=0, num_turns=9))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: 0 assistant turns, outside 1 to 20\n", console)

    def test_the_cost_bound_is_the_budget_times_1_10(self):
        # R6 (command center, 2026-10-09): the client stops only after crossing its $5 budget, and measured runs ended
        # up to 9.2% above it, so the bound is $5.50. A run at the bound passes; one a cent above it fails, named.
        code, console, *_ = run_step(NUMBERS, execution(total_cost_usd=5.5))
        self.assertEqual(code, 0, console)
        code, console, *_ = run_step(NUMBERS, execution(total_cost_usd=5.51))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: client cost estimate 5.51 USD, above 5.5\n", console)

    def test_a_budget_stop_within_the_bound_is_published_and_named(self):
        # A budget stop at or under the bound passes the check, even without result text; the report step publishes
        # what the run returned and names the stop under it (R7: the note moved there from the numbers step, so it is
        # written only once every bound has passed). Above the bound it fails, naming the stop and overrun.
        for cost, result in ((5.5, None), (5.2, "partial report")):
            with self.subTest(cost=cost, result=result):
                log = execution(subtype="error_max_budget_usd", is_error=True, total_cost_usd=cost)
                if result is None:
                    del log[-1]["result"]
                else:
                    log[-1]["result"] = result
                code, console, summary, usage = run_step(NUMBERS, log)
                self.assertEqual(code, 0, console)
                self.assertEqual(json.loads(usage)["result_subtype"], "error_max_budget_usd")
                self.assertNotIn("The run stopped at its client budget", summary)
                for message in log:
                    if message["type"] == "assistant" and message["message"]["content"][0]["type"] == "text":
                        message["message"]["content"][0]["text"] = "written " + message["message"]["id"]
                code, console, summary, _ = run_step(REPORT, log)
                self.assertEqual(code, 0, console)
                # Without result text, the report is what the model wrote before the stop (Codex P2 thread at
                # harness-audit.yml:231, R10); with it, the result text alone.
                shown = result or "\n\n".join(f"written msg_{turn:02d}" for turn in range(9))
                self.assertIn(f"<pre>\n{shown}\n</pre>\n\nThe run stopped at its client budget "
                              f"(error_max_budget_usd), at a client cost estimate of {cost} USD, within the 5.5 bound "
                              f"(the budget times 1.10). The report above is the result text it returned or, without "
                              f"one, the text the model wrote until then.\n", summary)
        code, console, summary, _ = run_step(NUMBERS, execution(subtype="error_max_budget_usd", is_error=True,
                                                                total_cost_usd=5.51))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: the run did not end in success (subtype error_max_budget_usd); client cost "
                      "estimate 5.51 USD, above 5.5\n", console)
        self.assertNotIn("The run stopped at its client budget", summary)

    def test_written_text_counts_and_is_published_only_for_a_budget_stop_without_result_text(self):
        # R10: the written-text fallback counts toward result_chars for a budget stop only; a success without result
        # text still fails "no result text", and its written text is never published.
        log = execution(subtype="error_max_budget_usd", is_error=True, total_cost_usd=5.2)
        del log[-1]["result"]
        code, console, _, usage = run_step(NUMBERS, log)
        self.assertEqual(code, 0, console)
        self.assertEqual(json.loads(usage)["result_chars"], 9 * len(TRANSCRIPT_MARKER) + 8 * 2)
        log = execution(result="")
        code, console, _, usage = run_step(NUMBERS, log)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(usage)["result_chars"], 0)
        self.assertIn("no result text", console)
        code, console, summary, _ = run_step(REPORT, log)
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>\n\n</pre>", summary)
        self.assertNotIn(TRANSCRIPT_MARKER, summary)

    def test_a_budget_stop_has_no_lower_cost_limit(self):
        # J8 micro N9 (GPT read of 0cf13fc2): the exemption takes any budget stop at or under the bound, however low
        # its cost; a floor such as `.total_cost_usd >= 5` would fail these.
        for cost in (0.01, 1.0, 4.99):
            with self.subTest(cost=cost):
                log = execution(subtype="error_max_budget_usd", is_error=True, total_cost_usd=cost,
                                modelUsage=model_usage(cost=cost))
                code, console, _, _ = run_step(NUMBERS, log)
                self.assertEqual(code, 0, console)

    def test_a_budget_stop_within_the_bound_is_exempt_only_from_the_success_and_text_checks(self):
        # R7 (J8 micro read, N1): the exemption waives the success and result-text checks only. A budget stop within
        # the bound that breaks any other bound fails, named, and writes no budget-stop note (N3).
        cases = {
            "a forbidden tool": ({"tools": ("Read", "Glob", "Grep", "Bash")},
                                 "Bounds not met: tools outside Read, Glob and Grep: Bash\n"),
            "an MCP server": ({"mcp_servers": ("github",)}, "Bounds not met: 1 MCP servers in the session\n"),
            "21 assistant turns": ({"turns": 21}, "Bounds not met: 21 assistant turns, outside 1 to 20\n"),
            "no session start record": ({"init": False}, "no session start record"),
            "no cache read": ({"modelUsage": model_usage(read=0, cost=5.2)}, "Bounds not met: no cache read\n"),
        }
        for label, (changes, message) in cases.items():
            with self.subTest(case=label):
                log = execution(subtype="error_max_budget_usd", is_error=True, total_cost_usd=5.2, **changes)
                code, console, summary, _ = run_step(NUMBERS, log)
                self.assertNotEqual(code, 0, console)
                self.assertIn(message, console)
                self.assertNotIn("The run stopped at its client budget", summary)

    def test_the_report_step_names_no_stop_after_a_success(self):
        _, console, summary, _ = run_step(REPORT, execution())
        self.assertNotIn("The run stopped at its client budget", summary, console)

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
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>\nshort report\n</pre>", summary)
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
