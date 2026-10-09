"""The on-demand security review: run its guard, binding, diff and accounting steps on synthetic inputs.

No model, network or credential is involved. The shell of each step is taken from
.github/workflows/claude-security-review.yml as written and executed with a throwaway HOME and
RUNNER_TEMP, a local stand-in for `gh` and a local git repository, so the tests fail when
the workflow's own text stops enforcing a bound.
"""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # the macOS job installs no package; the hosted validate job has PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/claude-security-review.yml"
ACTION = "anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b"
REPOSITORY = "synthetic/example"
HEAD = "a" * 40
TRANSCRIPT_MARKER = "SYNTHETIC-TRANSCRIPT-TEXT-MUST-NOT-LEAVE-THE-RUNNER"
SETTINGS_MARKER = "SYNTHETIC-SETTINGS-CONTENT-MUST-NOT-BE-PRINTED"
TITLE_MARKER = "SYNTHETIC-PULL-REQUEST-TITLE-MUST-NOT-REACH-THE-MODEL"

GUARD = "Refuse debug logging, pre-existing Claude settings and malformed inputs"
BIND = "Bind the request to an open same-repository pull request"
DIFF = "Write the diff from the merge base"
REVIEW = "Review the diff for security defects"
NUMBERS = "Keep the run's numbers and check the bounds"
REPORT = "Publish the security review to the job summary"


def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def job():
    return workflow()["jobs"]["review"]


def step(name):
    return next(item for item in job()["steps"] if item.get("name") == name)


def cli_settings():
    """The JSON the workflow passes to Claude Code with --settings, as the action's parser sees it."""
    lines = [line.strip() for line in step(REVIEW)["with"]["claude_args"].split("\n")]
    (line,) = [line for line in lines if line.startswith("--settings ")]
    (value,) = shlex.split(line)[1:]
    return json.loads(value)


def pull(**changes):
    data = {"state": "open", "title": TITLE_MARKER,
            "head": {"repo": {"full_name": REPOSITORY}, "sha": HEAD},
            "base": {"repo": {"full_name": REPOSITORY}, "ref": "main"}}
    for key, value in changes.items():
        target = data
        *parents, leaf = key.split(".")
        for parent in parents:
            target = target[parent]
        target[leaf] = value
    return data


def model_usage(read=160000, cost=0.7):
    return {"claude-opus-5-5": {"inputTokens": 30000, "outputTokens": 20000, "cacheReadInputTokens": read,
                                "cacheCreationInputTokens": 30000, "costUSD": cost}}


def execution(result=None, tools=("Read", "Glob", "Grep"), mcp_servers=(), init=True, turns=None, **changes):
    final = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 7,
             "total_cost_usd": 0.7, "modelUsage": model_usage(), "result": "Verdict NONE\nFinding 1"}
    final.update(changes)
    if result is not None:
        final["result"] = result
    messages = []
    if init:
        messages.append({"type": "system", "subtype": "init", "tools": list(tools),
                         "mcp_servers": list(mcp_servers), "claude_code_version": "2.1.295"})
    for turn in range(final["num_turns"] if turns is None else turns):
        # The client streams one message per content block, so one API turn spans several messages with one id.
        messages.append({"type": "assistant", "message": {"id": f"msg_{turn:02d}", "content": [
            {"type": "thinking", "thinking": ""}]}})
        messages.append({"type": "assistant", "message": {"id": f"msg_{turn:02d}", "content": [
            {"type": "text", "text": TRANSCRIPT_MARKER}]}})
    messages.append(final)
    return messages


def run_step(name, env_changes=None, execution_file=None, settings=None, pull_request=None, cwd=None):
    """Run one step's shell; returns (exit code, console, summary, usage.json or None, files left in security-review)."""
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
        bin_dir = directory / "bin"
        bin_dir.mkdir()
        if pull_request is not None:
            (directory / "pull.fixture.json").write_text(json.dumps(pull_request), encoding="utf-8")
            tool = bin_dir / "gh"
            tool.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, sys
                args = sys.argv[1:]
                if len(args) == 2 and args[0] == "api" and args[1].startswith("repos/") and "/pulls/" in args[1]:
                    sys.stdout.write(open(os.path.join(os.environ["RUNNER_TEMP"], "pull.fixture.json")).read())
                else:
                    sys.exit(99)
                """), encoding="utf-8")
            tool.chmod(0o755)
        summary = directory / "summary.md"
        env = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8",
               "HOME": str(home), "RUNNER_TEMP": str(directory), "GITHUB_STEP_SUMMARY": str(summary),
               "TMPDIR": str(directory), "GH_REPO": REPOSITORY, "GH_TOKEN": "synthetic-not-a-token",
               "PR_NUMBER": "12", "HEAD_SHA": HEAD, "DIFF_PATHS": "",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        if execution_file is not None:
            path = directory / "claude-execution-output.json"
            path.write_text(execution_file if isinstance(execution_file, str) else json.dumps(execution_file),
                            encoding="utf-8")
            env["EXECUTION_FILE"] = str(path)
        env.update(env_changes or {})
        if name == DIFF:
            (directory / "security-review").mkdir()
        done = subprocess.run(["bash", "-c", step(name)["run"]], env=env, capture_output=True, text=True,
                              check=False, cwd=cwd or directory)
        usage = directory / "security-review-usage/usage.json"
        review_dir = directory / "security-review"
        left = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in review_dir.iterdir()} \
            if review_dir.is_dir() else {}
        return (done.returncode, done.stdout + done.stderr,
                summary.read_text(encoding="utf-8") if summary.exists() else "",
                usage.read_text(encoding="utf-8") if usage.exists() else None, left)


def git(cwd, *args):
    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(cwd), "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_SYSTEM": os.devnull, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def repository_pair(directory, big=False):
    """An `origin` with main and one branch, and a clone on main, as the root checkout is in the job."""
    origin = directory / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    (origin / "kept.txt").write_text("base\n", encoding="utf-8")
    (origin / "docs").mkdir()
    (origin / "docs/note.md").write_text("note\n", encoding="utf-8")
    git(origin, "add", ".")
    git(origin, "commit", "-q", "-m", "base")
    git(origin, "checkout", "-q", "-b", "change")
    (origin / "kept.txt").write_text("base\nCHANGED-IN-THE-PULL-REQUEST\n", encoding="utf-8")
    (origin / "docs/note.md").write_text("note\nDOCS-CHANGE\n", encoding="utf-8")
    if big:
        (origin / "big.txt").write_text("x" * 80 + "\n" + ("line of filler text\n" * 20000), encoding="utf-8")
    git(origin, "add", ".")
    git(origin, "commit", "-q", "-m", "change")
    head = git(origin, "rev-parse", "HEAD")
    git(origin, "checkout", "-q", "main")
    (origin / "later.txt").write_text("main moved on\n", encoding="utf-8")
    git(origin, "add", ".")
    git(origin, "commit", "-q", "-m", "later on main")
    clone = directory / "clone"
    git(directory, "clone", "-q", "--branch", "main", str(origin), str(clone))
    return clone, head


@unittest.skipUnless(yaml, "PyYAML is needed to read the workflow's steps")
class SecurityReviewShapeTests(unittest.TestCase):
    def test_the_only_trigger_is_a_manual_dispatch_with_a_number_and_a_commit(self):
        triggers = workflow()[True] if True in workflow() else workflow()["on"]
        self.assertEqual(list(triggers), ["workflow_dispatch"])
        inputs = triggers["workflow_dispatch"]["inputs"]
        self.assertTrue(inputs["pr_number"]["required"])
        self.assertTrue(inputs["head_sha"]["required"])
        self.assertEqual(workflow()["permissions"], {})

    def test_the_job_needs_main_the_owner_a_first_attempt_and_the_enabling_variable(self):
        condition = " ".join(job()["if"].split())
        for clause in ("github.repository == 'seathatflowsinourveins/native-agent-stack'",
                       "github.ref == 'refs/heads/main'",
                       "github.actor == github.repository_owner",
                       "github.triggering_actor == github.repository_owner",
                       "github.run_attempt == 1",
                       "vars.CLAUDE_SECURITY_REVIEW_ENABLED == 'true'"):
            self.assertIn(clause, condition)
        self.assertEqual(condition.count("&&"), 5)
        self.assertNotIn("||", condition)

    def test_the_job_holds_the_oidc_token_and_no_write_scope(self):
        self.assertEqual(job()["permissions"],
                         {"contents": "read", "pull-requests": "read", "id-token": "write"})

    def test_main_is_at_the_workspace_root_and_the_head_is_data_in_a_subdirectory(self):
        root = step("Check out main at the workspace root")["with"]
        self.assertNotIn("ref", root)
        self.assertNotIn("path", root)
        self.assertIs(root["persist-credentials"], False)
        head = step("Check out the pull request head as data")["with"]
        self.assertEqual(head["ref"], "${{ inputs.head_sha }}")
        self.assertEqual(head["path"], "pr-head")
        self.assertIs(head["persist-credentials"], False)

    def test_steps_run_in_the_order_the_binding_depends_on(self):
        names = [item.get("name") for item in job()["steps"]]
        order = [GUARD, "Check out main at the workspace root", BIND, "Check out the pull request head as data",
                 DIFF, REVIEW, NUMBERS, REPORT]
        self.assertEqual([n for n in names if n in order], order)
        self.assertEqual(names[0], "Harden the runner (audit-only network egress)")

    def test_no_step_executes_anything_from_the_pull_request_head(self):
        for item in job()["steps"]:
            script = item.get("run", "")
            for token in ("pr-head/", "./pr-head", "cd pr-head", "bash pr-head", "source "):
                self.assertNotIn(token, script, item.get("name"))
            self.assertNotIn("working-directory", item)

    def test_git_diffs_in_the_trusted_checkout_without_external_drivers(self):
        script = step(DIFF)["run"]
        diffs = [line for line in script.split("\n") if "git diff" in line]
        self.assertEqual(len(diffs), 2)
        for line in diffs:
            self.assertIn("--no-ext-diff", line)
            self.assertIn("--no-textconv", line)
        self.assertNotIn("git -C", script)

    def test_the_action_is_pinned_and_takes_federation_inputs_only(self):
        run = step(REVIEW)
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
        text = WORKFLOW.read_text(encoding="utf-8")
        for static_credential in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertNotIn(static_credential, text)

    def test_claude_has_three_read_tools_and_fixed_bounds(self):
        arguments = [line.strip() for line in step(REVIEW)["with"]["claude_args"].split("\n") if line.strip()]
        for expected in ("--model claude-opus-5-5", "--effort max", "--max-turns 12", "--max-budget-usd 3",
                         "--tools Read,Glob,Grep", "--allowedTools Read,Glob,Grep",
                         "--restricted", "--permission-prompts none",
                         "--setting-sources user", "--strict-mcp-config",
                         "--add-dir ${{ runner.temp }}/security-review"):
            self.assertIn(expected, arguments)
        joined = " ".join(line for line in arguments if not line.startswith("--settings "))
        for tool in ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "Agent", "mcp__"):
            self.assertNotIn(tool, joined)
        for flag in ("--debug", "--dangerously-skip-permissions", "--permission-mode", "--mcp-config",
                     "--add-dir pr-head"):
            self.assertNotIn(flag, joined)

    def test_settings_turn_hooks_off_exclude_the_heads_instruction_files_and_confine_reads(self):
        # --restricted ignores every settings file, so the rules travel in --settings, not in the action's input.
        self.assertNotIn("settings", step(REVIEW)["with"])
        settings = cli_settings()
        self.assertIs(settings["disableAllHooks"], True)
        self.assertEqual(settings["claudeMdExcludes"], ["**/pr-head/**"])
        self.assertIs(settings["permissions"]["blockReadsOutsideWorkingDirectories"], True)
        for rule in ("Read(./.git/**)", "Read(./**/.git/**)"):
            self.assertIn(rule, settings["permissions"]["deny"])
        self.assertNotIn("allow", settings["permissions"])

    def test_the_review_is_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded(self):
        self.assertIn("success()", step(REPORT)["if"])
        self.assertIn("always()", step(NUMBERS)["if"])
        upload = step("Keep the numeric usage record")
        self.assertTrue(upload["with"]["path"].endswith("/security-review-usage/usage.json"))


@unittest.skipUnless(yaml and shutil.which("jq") and shutil.which("git"),
                     "PyYAML, jq and git are needed to run the workflow's steps")
class SecurityReviewStepTests(unittest.TestCase):
    def test_well_formed_inputs_pass_the_guard(self):
        for paths in ("", "docs", "docs tests/test_a.py scripts/x-y_z.py"):
            with self.subTest(paths=paths):
                code, console, *_ = run_step(GUARD, {"DIFF_PATHS": paths})
                self.assertEqual(code, 0, console)

    def test_each_debug_signal_and_a_pre_existing_settings_file_stop_the_job(self):
        for name, value in (("ACTIONS_STEP_DEBUG", "true"), ("ACTIONS_RUNNER_DEBUG", "true"),
                            ("RUNNER_DEBUG", "1"), ("RUNNER_DEBUG_SIGNAL", "1")):
            with self.subTest(signal=name):
                self.assertEqual(run_step(GUARD, {name: value})[0], 2)
        for kind in ("file", "dangling-symlink"):
            with self.subTest(kind=kind):
                code, console, *_ = run_step(GUARD, settings=kind)
                self.assertEqual(code, 2)
                self.assertNotIn(SETTINGS_MARKER, console)

    def test_malformed_inputs_stop_the_job_before_anything_uses_them(self):
        cases = [("PR_NUMBER", v) for v in ("", "0", "abc", "12;id", "12 13", "-1", "12345678", "$(id)")]
        cases += [("HEAD_SHA", v) for v in ("", "a" * 39, "a" * 41, "A" * 40, "g" * 40, "main", "a" * 39 + " ")]
        cases += [("DIFF_PATHS", v) for v in ("-rf", "docs -x", "a/../b", "..", "docs;id", "$(id)", "docs  tests",
                                               " docs", "docs ", "a|b", "docs\ntests", "*", "'x'")]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                code, console, *_ = run_step(GUARD, {name: value})
                self.assertEqual(code, 2, console)

    def test_an_open_same_repository_pull_request_with_the_requested_head_is_bound(self):
        code, console, _, _, left = run_step(BIND, pull_request=pull())
        self.assertEqual(code, 0, console)
        self.assertEqual(left, {}, "pull request metadata must not stay where the model can read it")
        self.assertNotIn(TITLE_MARKER, console)

    def test_any_other_pull_request_state_is_refused(self):
        cases = {
            "closed": {"state": "closed"},
            "from a fork": {"head.repo.full_name": "someone/fork"},
            "base in another repository": {"base.repo.full_name": "someone/else"},
            "not targeting main": {"base.ref": "release"},
            "a different head": {"head.sha": "b" * 40},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                code, console, _, _, _ = run_step(BIND, pull_request=pull(**changes))
                self.assertEqual(code, 2, console)
                self.assertNotIn(TITLE_MARKER, console)

    def test_the_diff_is_taken_from_the_merge_base_in_the_trusted_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone, head = repository_pair(Path(temporary))
            code, console, _, _, left = run_step(DIFF, {"HEAD_SHA": head}, cwd=clone)
            self.assertEqual(code, 0, console)
            self.assertIn("CHANGED-IN-THE-PULL-REQUEST", left["pr.diff"])
            self.assertIn("DOCS-CHANGE", left["pr.diff"])
            self.assertNotIn("later.txt", left["pr.diff"], "main's later commits are not part of the change")
            self.assertIn("kept.txt", left["pr.stat"])

    def test_paths_limit_the_diff(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone, head = repository_pair(Path(temporary))
            code, console, _, _, left = run_step(DIFF, {"HEAD_SHA": head, "DIFF_PATHS": "docs"}, cwd=clone)
            self.assertEqual(code, 0, console)
            self.assertIn("DOCS-CHANGE", left["pr.diff"])
            self.assertNotIn("CHANGED-IN-THE-PULL-REQUEST", left["pr.diff"])

    def test_an_empty_or_oversized_diff_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone, head = repository_pair(Path(temporary), big=True)
            code, console, *_ = run_step(DIFF, {"HEAD_SHA": head}, cwd=clone)
            self.assertEqual(code, 2, console)
            self.assertIn("pass paths", console)
            code, console, *_ = run_step(DIFF, {"HEAD_SHA": head, "DIFF_PATHS": "absent-directory"}, cwd=clone)
            self.assertEqual(code, 2, console)
            self.assertIn("empty", console)
            code, console, *_ = run_step(DIFF, {"HEAD_SHA": head, "DIFF_PATHS": "docs"}, cwd=clone)
            self.assertEqual(code, 0, console)

    def test_a_bounded_cached_read_only_run_is_accepted_and_only_numbers_and_fixed_names_are_kept(self):
        code, console, summary, usage, _ = run_step(NUMBERS, execution_file=execution())
        self.assertEqual(code, 0, console)
        record = json.loads(usage)
        self.assertEqual(sorted(record), ["assistant_turns", "claude_code_version", "forbidden_tools", "mcp_servers", "models",
                                          "num_turns", "session_started", "successful_result", "tools",
                                          "total_cost_usd"])
        self.assertEqual(record["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(record["forbidden_tools"], [])
        for text in (usage, summary, console):
            self.assertNotIn(TRANSCRIPT_MARKER, text)
            self.assertNotIn("Verdict", text)
        self.assertIn("| 7 | 7 | 0.7 | true | 2.1.295 | Read Glob Grep | 0 |", summary)

    def test_an_unmet_bound_fails_after_the_numbers_were_kept(self):
        cases = {
            "no cache read": {"modelUsage": model_usage(read=0)},
            "over the client budget": {"total_cost_usd": 3.01},
            "over the turn limit": {"turns": 13},
            "an error result": {"is_error": True},
            "a turn-limit stop": {"subtype": "error_max_turns"},
            "a shell tool in the session": {"tools": ("Read", "Glob", "Grep", "Bash")},
            "a write tool in the session": {"tools": ("Read", "Edit")},
            "an MCP tool in the session": {"tools": ("Read", "mcp__github__create_issue")},
            "an MCP server in the session": {"mcp_servers": ({"name": "x", "status": "connected"},)},
            "no session start record": {"init": False},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                code, _, _, usage, _ = run_step(NUMBERS, execution_file=execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertIsInstance(json.loads(usage)["total_cost_usd"], (int, float))

    def test_the_turn_bound_counts_assistant_turns_not_transcript_messages(self):
        # On Claude Code 2.1.295 a 12-request run with parallel reads reported num_turns 57 (api-actions LR
        # receipt, 2026-10-08): num_turns counts transcript messages, tool results included.
        code, console, *_ = run_step(NUMBERS, execution_file=execution(turns=12, num_turns=57))
        self.assertEqual(code, 0, console)
        code, *_ = run_step(NUMBERS, execution_file=execution(turns=13, num_turns=13))
        self.assertNotEqual(code, 0)

    def test_names_that_are_not_plain_identifiers_are_replaced(self):
        hostile = "<img src=x onerror=alert(1)> | injected"
        log = execution(tools=("Read", hostile), modelUsage={hostile: model_usage()["claude-opus-5-5"]})
        log[0]["claude_code_version"] = hostile
        _, console, summary, usage, _ = run_step(NUMBERS, execution_file=log)
        for text in (usage, summary, console):
            self.assertNotIn("onerror", text)
        record = json.loads(usage)
        self.assertEqual(record["tools"], ["Read", "other"])
        self.assertEqual(record["models"][0]["model"], "other")
        self.assertEqual(record["claude_code_version"], "other")

    def test_an_unreadable_execution_file_fails_and_leaves_no_record(self):
        broken = {
            "an object, not a message list": {"type": "result"},
            "no result message": [{"type": "assistant"}],
            "no model usage": execution(modelUsage={}),
            "a text cost": execution(total_cost_usd="0.7"),
            "not JSON": "not json at all",
        }
        for label, content in broken.items():
            with self.subTest(case=label):
                code, _, summary, usage, _ = run_step(NUMBERS, execution_file=content)
                self.assertNotEqual(code, 0)
                self.assertIsNone(usage, "a failed extraction must not leave an empty record to upload")
                self.assertNotIn("completed", summary)

    def test_the_review_is_escaped_preformatted_and_capped(self):
        hostile = "<script>alert(1)</script> ![x](https://example.invalid/a.png) & [link](https://example.invalid)\n"
        code, console, summary, _, _ = run_step(REPORT, execution_file=execution(result=hostile + "A" * 200000))
        self.assertEqual(code, 0, console)
        self.assertIn(f"#12 at {HEAD}", summary)
        self.assertIn("<pre>", summary)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", summary)
        self.assertNotIn("<script>", summary)
        self.assertLess(len(summary.encode("utf-8")), 61000)
        self.assertNotIn(TRANSCRIPT_MARKER, summary)


FLAG = ROOT / ".github/workflows/security-review-flag.yml"


def flag_workflow():
    return yaml.safe_load(FLAG.read_text(encoding="utf-8"))


def run_flag(env_changes=None):
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        summary = directory / "summary.md"
        env = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "HOME": str(directory),
               "GITHUB_STEP_SUMMARY": str(summary), "PR_NUMBER": "12", "HEAD_SHA": HEAD}
        env.update(env_changes or {})
        script = flag_workflow()["jobs"]["flag"]["steps"][1]["run"]
        done = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, check=False)
        return done.returncode, summary.read_text(encoding="utf-8") if summary.exists() else ""


@unittest.skipUnless(yaml, "PyYAML is needed to read the workflow's steps")
class SecurityReviewFlagTests(unittest.TestCase):
    def test_it_runs_on_pull_requests_that_touch_the_watched_paths_only(self):
        data = flag_workflow()
        triggers = data[True] if True in data else data["on"]
        self.assertEqual(list(triggers), ["pull_request"])
        self.assertEqual(triggers["pull_request"]["paths"], [
            ".github/workflows/**", "scripts/hooks/**", "tools/credentials/**",
            "adoption/credential-inventory.json", "blueprints/us-equities/adaptive-paper/**",
            "blueprints/us-equities/alpaca-paper/**"])

    def test_it_holds_no_scope_no_secret_and_no_model(self):
        data = flag_workflow()
        self.assertEqual(data["permissions"], {})
        job = data["jobs"]["flag"]
        self.assertNotIn("permissions", job)
        self.assertNotIn("if", job)
        uses = [item["uses"] for item in job["steps"] if "uses" in item]
        self.assertEqual(len(uses), 1)
        self.assertTrue(uses[0].startswith("step-security/harden-runner@"))
        text = FLAG.read_text(encoding="utf-8")
        for token in ("secrets.", "vars.", "id-token", "claude-code-action", "checkout", "GITHUB_TOKEN", "github.token"):
            self.assertNotIn(token, text.split("jobs:", 1)[1])

    def test_the_event_values_reach_the_shell_as_environment_variables_only(self):
        step = flag_workflow()["jobs"]["flag"]["steps"][1]
        self.assertEqual(step["env"], {"PR_NUMBER": "${{ github.event.pull_request.number }}",
                                       "HEAD_SHA": "${{ github.event.pull_request.head.sha }}"})
        self.assertNotIn("${{", step["run"])

    @unittest.skipUnless(shutil.which("bash"), "bash is needed to run the step")
    def test_the_notice_names_the_exact_dispatch_and_refuses_malformed_values(self):
        code, summary = run_flag()
        self.assertEqual(code, 0)
        self.assertIn(f"gh workflow run claude-security-review.yml --ref main -f pr_number=12 -f head_sha={HEAD}",
                      summary)
        for name, value in (("PR_NUMBER", "12; id"), ("PR_NUMBER", ""), ("HEAD_SHA", "main"), ("HEAD_SHA", "$(id)")):
            with self.subTest(name=name, value=value):
                code, summary = run_flag({name: value})
                self.assertEqual(code, 2)
                self.assertEqual(summary, "")


if __name__ == "__main__":
    unittest.main()
