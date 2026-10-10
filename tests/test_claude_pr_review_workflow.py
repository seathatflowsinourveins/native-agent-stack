"""The on-demand pull request review: run its guard, binding, diff and accounting steps on synthetic inputs.

No model, network or credential is involved. The shell of each step is taken from
.github/workflows/claude-pr-review.yml as written and executed with a throwaway HOME and
RUNNER_TEMP, a local stand-in for `gh` and a local git repository, so the tests fail when
the workflow's own text stops enforcing a bound.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests.test_workflow_policy import load_workflow

try:
    import yaml
except ImportError:  # the macOS job installs no package; the hosted validate job has PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/claude-pr-review.yml"
ACTION = "anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b"
REPOSITORY = "synthetic/example"
HEAD = "a" * 40
TRANSCRIPT_MARKER = "SYNTHETIC-TRANSCRIPT-TEXT-MUST-NOT-LEAVE-THE-RUNNER"
WRITTEN_MARKER = "SYNTHETIC-TEXT-WRITTEN-BEFORE-THE-BUDGET-STOP"
SETTINGS_MARKER = "SYNTHETIC-SETTINGS-CONTENT-MUST-NOT-BE-PRINTED"
TITLE_MARKER = "SYNTHETIC-PULL-REQUEST-TITLE-MUST-NOT-REACH-THE-MODEL"

GUARD = "Refuse debug logging, pre-existing Claude settings and malformed inputs"
BIND = "Bind the request to an open same-repository pull request"
HEAD_CHECKOUT = "Check out the pull request head as data"
STRIP = "Remove symbolic links from the pull request head"
DIFF = "Write the diff from the merge base"
REVIEW = "Review the diff"
NUMBERS = "Keep the run's numbers and check the bounds"
REPORT = "Publish the review to the job summary"
FRESH = "Skip a head completed while this review waited"

# What the guard step's env holds when no debug logging is on: each repository setting binds false, and
# ${{ runner.debug }} renders empty because GitHub sets runner.debug only while debug logging is on.
DEBUG_OFF = {"STEP_DEBUG_SETTING": "false", "RUNNER_DIAGNOSTICS_SETTING": "false", "RUNNER_DEBUG_SIGNAL": ""}

# A stand-in for the path GitHub renders ${{ runner.temp }} as before the action reads claude_args.
RUNNER_TEMP_STAND_IN = "/runner-temp"

# The whole --settings JSON the review step passes.
SETTINGS = {"disableAllHooks": True, "claudeMdExcludes": ["**/pr-head/**"],
            "permissions": {"blockReadsOutsideWorkingDirectories": True,
                            "deny": ["Read(./.git/**)", "Read(./**/.git/**)", "Read(./pr-head/.git/**)",
                                     "Read(./**/.env)", "Read(./**/.env.*)", "Read(./**/*.pem)", "Read(./**/*.key)"]}}


def workflow():
    text = WORKFLOW.read_text(encoding="utf-8")
    return (yaml.safe_load(text) if yaml else load_workflow(text))


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


def canonical(value):
    """JSON text with sorted keys: unlike Python's ==, it tells true from 1 and false from 0."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def claude_args():
    """Every argument the action's parser receives, in order: ${{ runner.temp }} rendered, each line split as a shell
    would split it."""
    text = step(REVIEW)["with"]["claude_args"].replace("${{ runner.temp }}", RUNNER_TEMP_STAND_IN)
    return [token for line in text.split("\n") for token in shlex.split(line)]


def pull(**changes):
    data = {"state": "open", "draft": False, "title": TITLE_MARKER,
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


def execution(result=None, tools=("Read", "Glob", "Grep"), mcp_servers=(), init=True, turns=None, lists=True,
              **changes):
    final = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 7,
             "total_cost_usd": 0.7, "modelUsage": model_usage(), "result": "Verdict\nFinding 1"}
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


def budget_stop(cost=5.3, written=True):
    """A run the client stopped at its budget: its result record has no result text, so what the run produced is
    the text the model wrote before the stop (one block per turn here, or none)."""
    log = execution(subtype="error_max_budget_usd", is_error=True, total_cost_usd=cost)
    del log[-1]["result"]
    for message in log:
        for block in (message.get("message") or {}).get("content", []):
            if block.get("type") == "text":
                block["text"] = WRITTEN_MARKER if written else ""
    return log


def run_step(name, env_changes=None, execution_file=None, settings=None, pull_request=None, cwd=None):
    """Run one step's shell; returns (exit code, console, summary, usage.json or None, files left in pr-review)."""
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
               "PR_NUMBER": "12", "HEAD_SHA": HEAD, "DIFF_PATHS": "", "EVENT_NAME": "workflow_dispatch",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        if execution_file is not None:
            path = directory / "claude-execution-output.json"
            path.write_text(execution_file if isinstance(execution_file, str) else json.dumps(execution_file),
                            encoding="utf-8")
            env["EXECUTION_FILE"] = str(path)
        env.update(env_changes or {})
        if name == DIFF:
            (directory / "pr-review").mkdir()
        done = subprocess.run(["bash", "-c", step(name)["run"]], env=env, capture_output=True, text=True,
                              check=False, cwd=cwd or directory)
        usage = directory / "pr-review-usage/usage.json"
        review_dir = directory / "pr-review"
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
class PullRequestReviewShapeTests(unittest.TestCase):
    def test_the_triggers_are_a_manual_dispatch_and_a_15_minute_schedule(self):
        # No pull_request, pull_request_target or workflow_run: the review runs only from main's copy of this file
        # (docs/decisions/2026-10-08-claude-actions-pr-review.md, "Every pull request (2026-10-09)").
        triggers = workflow()[True] if True in workflow() else workflow()["on"]
        self.assertEqual(list(triggers), ["workflow_dispatch", "schedule"])
        self.assertEqual(triggers["schedule"], [{"cron": "*/15 * * * *"}])
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
                       "vars.CLAUDE_PR_REVIEW_ENABLED == 'true'"):
            self.assertIn(clause, condition)
        self.assertIn("needs.resolve.outputs.go == 'true'", condition)
        self.assertEqual(condition.count("&&"), 6)
        self.assertNotIn("||", condition)
        self.assertEqual(job()["needs"], "resolve")

    def test_the_resolve_job_holds_no_token_and_reads_only(self):
        resolve = workflow()["jobs"]["resolve"]
        self.assertEqual(resolve["permissions"], {"pull-requests": "read", "actions": "read"})
        condition = " ".join(resolve["if"].split())
        for clause in ("github.ref == 'refs/heads/main'", "github.actor == github.repository_owner",
                       "github.triggering_actor == github.repository_owner", "github.run_attempt == 1",
                       "vars.CLAUDE_PR_REVIEW_ENABLED == 'true'",
                       "(github.event_name == 'workflow_dispatch' || vars.CLAUDE_PR_REVIEW_EVERY_PR == 'true')"):
            self.assertIn(clause, condition)
        self.assertNotIn("uses: actions/checkout", json.dumps(resolve))
        self.assertNotIn("secrets.", json.dumps(resolve))

    def test_each_review_is_one_matrix_head_with_its_own_group_at_most_two_at_once(self):
        strategy = job()["strategy"]
        self.assertEqual(strategy["max-parallel"], 2)
        self.assertIs(strategy["fail-fast"], False)
        self.assertEqual(strategy["matrix"], {"include": "${{ fromJSON(needs.resolve.outputs.heads) }}"})
        self.assertEqual(job()["concurrency"], {
            "group": "claude-pr-review-pr${{ matrix.pr_number }}-${{ matrix.head_sha }}", "cancel-in-progress": False})
        self.assertTrue(job()["name"].startswith("Review "))  # the resolve step counts today's reviews by this prefix

    def test_the_job_holds_no_write_scope_and_no_id_token(self):
        # actions: read is for the completion-marker recheck (the fresh step) only.
        self.assertEqual(job()["permissions"], {"contents": "read", "pull-requests": "read", "actions": "read"})

    def test_the_job_timeout_leaves_room_for_the_30_turn_bound(self):
        # 30 assistant turns at the measured pace of about 43 s a turn take about 21.4 minutes before checkout and
        # setup; a 20-minute timeout would cancel a run inside the bounds before it writes execution_file.
        timeout = job()["timeout-minutes"]
        self.assertIs(type(timeout), int)
        self.assertEqual(timeout, 30)

    def test_main_is_at_the_workspace_root_and_the_head_is_data_in_a_subdirectory(self):
        root = step("Check out main at the workspace root")["with"]
        self.assertNotIn("ref", root)
        self.assertNotIn("path", root)
        self.assertIs(root["persist-credentials"], False)
        head = step("Check out the pull request head as data")["with"]
        self.assertEqual(head["ref"], "${{ matrix.head_sha }}")
        self.assertEqual(head["path"], "pr-head")
        self.assertIs(head["persist-credentials"], False)

    def test_steps_run_in_the_order_the_binding_depends_on(self):
        names = [item.get("name") for item in job()["steps"]]
        order = [FRESH, GUARD, "Check out main at the workspace root", BIND, HEAD_CHECKOUT, STRIP, DIFF, REVIEW, NUMBERS,
                 REPORT]
        self.assertEqual([n for n in names if n in order], order)
        self.assertEqual(names[0], "Harden the runner (audit-only network egress)")

    def test_symbolic_links_are_removed_right_after_the_head_checkout(self):
        names = [item.get("name") for item in job()["steps"]]
        self.assertEqual(names[names.index(HEAD_CHECKOUT) + 1], STRIP)
        self.assertEqual(step(STRIP), {
            "name": STRIP, "shell": "bash", "if": "${{ steps.fresh.outputs.go == 'true' }}",
            "run": "set -euo pipefail\nfind pr-head -path pr-head/.git -prune -o -type l -exec rm -f {} +\n"})

    def test_no_step_executes_anything_from_the_pull_request_head(self):
        for item in job()["steps"]:
            self.assertNotIn("working-directory", item)
            if item.get("name") == STRIP:
                continue  # it names pr-head/.git to leave it alone; the test above pins its whole text
            script = item.get("run", "")
            for token in ("pr-head/", "./pr-head", "cd pr-head", "bash pr-head", "source "):
                self.assertNotIn(token, script, item.get("name"))

    def test_git_diffs_in_the_trusted_checkout_without_external_drivers(self):
        script = step(DIFF)["run"]
        diffs = [line for line in script.split("\n") if "git diff" in line]
        self.assertEqual(len(diffs), 2)
        for line in diffs:
            self.assertIn("--no-ext-diff", line)
            self.assertIn("--no-textconv", line)
        self.assertNotIn("git -C", script)

    def test_the_action_is_pinned_and_takes_the_api_key_secret_only(self):
        run = step(REVIEW)
        self.assertEqual(run["uses"], ACTION)
        self.assertEqual(run["env"], {"ACTIONS_STEP_DEBUG": "false"})
        inputs = run["with"]
        for forbidden in ("claude_code_oauth_token", "allowed_non_write_users", "allowed_bots",
                          "plugins", "plugin_marketplaces"):
            self.assertNotIn(forbidden, inputs)
        # The owner's ruling of 2026-10-10: the repository secret ANTHROPIC_API_KEY, no federation input.
        self.assertEqual(inputs["anthropic_api_key"], "${{ secrets.ANTHROPIC_API_KEY }}")
        for name in ("anthropic_federation_rule_id", "anthropic_organization_id",
                     "anthropic_service_account_id", "anthropic_workspace_id"):
            self.assertNotIn(name, inputs)
        self.assertEqual(inputs["show_full_output"], "false")
        self.assertEqual(inputs["display_report"], "false")
        self.assertEqual(inputs["track_progress"], "false")
        text = WORKFLOW.read_text(encoding="utf-8")
        # The API key is the one credential (the owner's ruling of 2026-10-10); no other static one appears.
        for static_credential in ("ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertNotIn(static_credential, text)
        self.assertEqual(text.count("secrets.ANTHROPIC_API_KEY"), 1)

    def test_claude_has_three_read_tools_and_fixed_bounds(self):
        # The whole list, closed: a widened or second --add-dir, a repeated turn or budget flag, or any added flag
        # changes it. The --settings value is compared as canonical JSON text, so 1 does not pass for true.
        arguments = claude_args()
        settings = arguments.index("--settings") + 1
        arguments[settings] = canonical(json.loads(arguments[settings]))
        self.assertEqual(arguments, [
            "--model", "claude-opus-5-5", "--effort", "max", "--max-budget-usd", "5",
            "--tools", "Read,Glob,Grep", "--allowedTools", "Read,Glob,Grep", "--restricted",
            "--permission-prompts", "none", "--setting-sources", "user", "--strict-mcp-config",
            "--settings", canonical(SETTINGS), "--add-dir", RUNNER_TEMP_STAND_IN + "/pr-review"])

    def test_the_prompt_states_the_turn_bound_the_numbers_step_checks(self):
        # claude_args sets no --max-turns (the pinned action compares it with num_turns, a message count), so the
        # turn limit the prompt states is the numbers step's assistant-turn bound.
        (turns,) = re.findall(r"\.assistant_turns > (\d+) then", step(NUMBERS)["run"])
        self.assertIn(f"You have at most {turns} turns, so read in parallel.", step(REVIEW)["with"]["prompt"])
        self.assertNotIn("--max-turns", claude_args())

    def test_settings_turn_hooks_off_exclude_the_heads_instruction_files_and_confine_reads(self):
        # --restricted ignores every settings file, so the rules travel in --settings, not in the action's input.
        self.assertNotIn("settings", step(REVIEW)["with"])
        # The whole JSON, closed: a dropped deny rule, an allow list or permissions.additionalDirectories changes it.
        # Compared as canonical text, since in Python 1 == True: "disableAllHooks": 1 must fail.
        self.assertEqual(canonical(cli_settings()), canonical(SETTINGS))

    def test_a_green_run_always_has_an_execution_file(self):
        check = step("Require the run's execution file")
        self.assertEqual(check["if"], "${{ success() && steps.fresh.outputs.go == 'true' && "
                                    "steps.claude_review.outputs.execution_file == '' }}")
        self.assertIn("exit 1", check["run"])

    def test_the_review_is_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded(self):
        # The action fails its own step on a budget stop, which the numbers step can accept, but keeps its
        # execution_file output, so publication follows the numbers step's outcome, not success().
        self.assertEqual(step(REPORT)["if"], "${{ !cancelled() && steps.numbers.outcome == 'success' }}")
        self.assertEqual(step(NUMBERS)["id"], "numbers")
        self.assertEqual(step(NUMBERS)["if"], "${{ always() && steps.claude_review.outputs.execution_file != '' }}")
        upload = step("Keep the numeric usage record")
        self.assertTrue(upload["with"]["path"].endswith("/pr-review-usage/usage.json"))

    def test_the_usage_artifact_is_named_for_the_pull_request_and_its_head(self):
        # The resolve step skips a head whose artifact claude-pr-review-usage-pr<N>-<sha> exists, so the exact name is
        # pinned here.
        upload = step("Keep the numeric usage record")
        self.assertEqual(upload["with"]["name"],
                         "claude-pr-review-usage-pr${{ matrix.pr_number }}-${{ matrix.head_sha }}-${{ github.run_id }}")

    def test_the_completion_marker_is_written_only_after_the_bounds_passed_and_the_review_was_published(self):
        # A usage record is written for failed runs too, so it is never the dedupe key (GPT read of #932, P2 3).
        gate = "${{ !cancelled() && steps.numbers.outcome == 'success' && steps.publish.outcome == 'success' }}"
        self.assertEqual(step(REPORT)["id"], "publish")
        self.assertEqual(step("Write the completion marker")["if"], gate)
        keep = step("Keep the completion marker")
        self.assertEqual(keep["if"], gate)
        self.assertEqual(keep["with"]["name"], "claude-pr-review-done-pr${{ matrix.pr_number }}-${{ matrix.head_sha }}")
        self.assertEqual(keep["with"]["retention-days"], 90)
        self.assertEqual(keep["with"]["if-no-files-found"], "error")
        names = [item.get("name") for item in job()["steps"]]
        self.assertLess(names.index(REPORT), names.index("Write the completion marker"))

    def test_every_step_before_the_numbers_waits_for_the_recheck(self):
        # P2 4: a scheduled review that waited on its head's group skips when the head was completed meanwhile.
        names = [item.get("name") for item in job()["steps"]]
        self.assertEqual(names[1], FRESH)
        for item in job()["steps"][2:names.index(NUMBERS)]:
            self.assertEqual(item.get("if"), "${{ steps.fresh.outputs.go == 'true' }}", item.get("name"))
        self.assertIn("steps.fresh.outputs.go == 'true'", step("Require the run's execution file")["if"])

    def test_both_jobs_use_the_same_completion_check(self):
        def body(script):
            start = script.index("completed() {")
            return script[start:script.index("echo no", start)]
        resolve = next(item for item in workflow()["jobs"]["resolve"]["steps"] if item.get("name") == CHOOSE)
        self.assertEqual(body(resolve["run"]), body(step(FRESH)["run"]))


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"),
                     "jq and git are needed to run the workflow's steps")
class PullRequestReviewStepTests(unittest.TestCase):
    def test_well_formed_inputs_pass_the_guard(self):
        # With the values a run without debug logging binds, so a guard that refuses those fails here.
        for paths in ("", "docs", "docs tests/test_a.py scripts/x-y_z.py"):
            with self.subTest(paths=paths):
                code, console, *_ = run_step(GUARD, {**DEBUG_OFF, "DIFF_PATHS": paths})
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

    def test_each_debug_signal_and_a_pre_existing_settings_file_stop_the_job(self):
        for name, value in (("ACTIONS_STEP_DEBUG", "true"), ("ACTIONS_RUNNER_DEBUG", "true"),
                            ("RUNNER_DEBUG", "1"), ("RUNNER_DEBUG_SIGNAL", "1"), ("STEP_DEBUG_SETTING", "true"),
                            ("RUNNER_DIAGNOSTICS_SETTING", "true")):
            with self.subTest(signal=name):
                self.assertEqual(run_step(GUARD, {**DEBUG_OFF, name: value})[0], 2)
        for kind in ("file", "dangling-symlink"):
            with self.subTest(kind=kind):
                code, console, *_ = run_step(GUARD, DEBUG_OFF, settings=kind)
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

    def test_a_draft_is_bound_on_a_dispatch_and_refused_on_a_scheduled_review(self):
        code, console, _, _, _ = run_step(BIND, pull_request=pull(draft=True))
        self.assertEqual(code, 0, console)
        code, console, _, _, _ = run_step(BIND, {"EVENT_NAME": "schedule"}, pull_request=pull(draft=True))
        self.assertEqual(code, 2, console)
        code, console, _, _, _ = run_step(BIND, {"EVENT_NAME": "schedule"}, pull_request=pull())
        self.assertEqual(code, 0, console)

    def test_symbolic_links_in_the_head_are_removed_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / ".git").mkdir()
            (workspace / ".git/config").write_text("ROOT-CONFIG\n", encoding="utf-8")
            head = workspace / "pr-head"
            (head / ".git").mkdir(parents=True)
            (head / ".git/config").write_text("HEAD-CONFIG\n", encoding="utf-8")
            (head / ".git/link").symlink_to("config")  # the checkout's own directory is pruned, not cleaned
            (head / "kept.txt").write_text("kept\n", encoding="utf-8")
            (head / "docs").mkdir()
            (head / "docs/note.md").write_text("note\n", encoding="utf-8")
            links = {"environ": "/proc/self/environ", "config": "../.git/config", "docs/workspace": "../.."}
            for name, target in links.items():
                (head / name).symlink_to(target)
            code, console, *_ = run_step(STRIP, cwd=workspace)
            self.assertEqual(code, 0, console)
            for name in links:
                self.assertFalse(os.path.lexists(head / name), name)  # lexists: a dangling link counts as present
            self.assertEqual((head / "kept.txt").read_text(encoding="utf-8"), "kept\n")
            self.assertEqual((head / "docs/note.md").read_text(encoding="utf-8"), "note\n")
            self.assertEqual((head / ".git/config").read_text(encoding="utf-8"), "HEAD-CONFIG\n")
            self.assertTrue((head / ".git/link").is_symlink())
            self.assertEqual((workspace / ".git/config").read_text(encoding="utf-8"), "ROOT-CONFIG\n")
            # A head with no link, the usual case, passes too: find then starts no rm.
            code, console, *_ = run_step(STRIP, cwd=workspace)
            self.assertEqual(code, 0, console)
            self.assertEqual((head / "kept.txt").read_text(encoding="utf-8"), "kept\n")

    def test_the_diff_is_taken_from_the_merge_base_in_the_trusted_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone, head = repository_pair(Path(temporary))
            code, console, _, _, left = run_step(DIFF, {"HEAD_SHA": head}, cwd=clone)
            self.assertEqual(code, 0, console)
            self.assertIn("CHANGED-IN-THE-PULL-REQUEST", left["pr.diff"])
            self.assertIn("DOCS-CHANGE", left["pr.diff"])
            self.assertNotIn("later.txt", left["pr.diff"], "main's later commits are not part of the change")
            self.assertIn("kept.txt", left["pr.stat"])

    def test_no_paths_expands_safely_under_set_u_on_old_bash(self):
        # bash before 4.4 treats an empty array as unset under set -u; the step must not expand it bare.
        script = step(DIFF)["run"]
        self.assertNotIn('-- "${scope[@]}"', script)
        self.assertEqual(script.count('${scope[@]+"${scope[@]}"}'), 2)

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
        self.assertEqual(sorted(record), ["assistant_turns", "budget_stop", "claude_code_version", "error_class", "forbidden_tools", "mcp_servers", "models", "num_turns", "result_chars", "session_started", "successful_result", "tools", "tools_listed", "total_cost_usd"])
        self.assertIs(record["budget_stop"], False)
        self.assertNotIn("Budget stop", summary)
        self.assertNotIn("Over the cost bound", summary)
        self.assertEqual(record["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(record["forbidden_tools"], [])
        for text in (usage, summary, console):
            self.assertNotIn(TRANSCRIPT_MARKER, text)
            self.assertNotIn("Verdict", text)
        self.assertIn("| 7 | 7 | 0.7 | true | 2.1.295 | Read Glob Grep | 0 |", summary)

    def test_an_unmet_bound_fails_after_the_numbers_were_kept(self):
        cases = {
            "no cache read": {"modelUsage": model_usage(read=0)},
            "over the cost bound": {"total_cost_usd": 5.51},
            "over the turn limit": {"turns": 31},
            "an error result": {"is_error": True},
            "a turn-limit stop": {"subtype": "error_max_turns"},
            "a shell tool in the session": {"tools": ("Read", "Glob", "Grep", "Bash")},
            "a write tool in the session": {"tools": ("Read", "Edit")},
            "an MCP tool in the session": {"tools": ("Read", "mcp__github__create_issue")},
            "an MCP server in the session": {"mcp_servers": ({"name": "x", "status": "connected"},)},
            "no session start record": {"init": False},
            "a tool outside the allow-list": {"tools": ("Read", "Glob", "Grep", "Skill")},
            "no tool or MCP list in the session start record": {"lists": False},
            "no result text": {"result": ""},
        }
        for label, changes in cases.items():
            with self.subTest(case=label):
                code, _, _, usage, _ = run_step(NUMBERS, execution_file=execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertIsInstance(json.loads(usage)["total_cost_usd"], (int, float))

    def test_the_step_names_every_unmet_bound(self):
        code, console, *_ = run_step(NUMBERS, execution_file=execution(turns=31, total_cost_usd=6,
                                                         tools=("Read", "Skill"), result=""))
        self.assertNotEqual(code, 0)
        for words in ("31 assistant turns, outside 1 to 30", "above the 5.5 USD bound", "Skill", "no result text"):
            self.assertIn(words, console)

    def test_the_bounds_hold_at_30_turns_and_5_50_usd_and_fail_just_above_or_with_no_turn(self):
        # The cost bound is the $5 budget times the measured overrun factor 1.10: the client stops only after it
        # crosses its budget.
        code, console, summary, *_ = run_step(NUMBERS, execution_file=execution(turns=30, total_cost_usd=5.5))
        self.assertEqual(code, 0, console)
        self.assertNotIn("Over the cost bound", summary)
        overrun = ("client cost estimate 5.51 USD, above the 5.5 USD bound (the 5 USD budget times its measured "
                   "overrun factor 1.10)")
        for changes, words in (({"turns": 31}, "Bounds not met: 31 assistant turns, outside 1 to 30"),
                               ({"total_cost_usd": 5.51}, "Bounds not met: " + overrun),
                               ({"turns": 0}, "Bounds not met: 0 assistant turns, outside 1 to 30")):
            with self.subTest(**changes):
                code, console, *_ = run_step(NUMBERS, execution_file=execution(**changes))
                self.assertNotEqual(code, 0)
                self.assertIn(words, console)
        _, _, summary, *_ = run_step(NUMBERS, execution_file=execution(total_cost_usd=5.51))
        self.assertIn("Over the cost bound: the client cost estimate is 5.51 USD, above 5.5 USD (the 5 USD budget "
                      "times its measured overrun factor 1.10).", summary)

    def test_a_budget_stop_at_or_under_the_bound_publishes_what_the_run_wrote_and_names_the_stop(self):
        written = "\n\n".join([WRITTEN_MARKER] * 7)
        for cost in (5.3, 5.5):
            with self.subTest(cost=cost):
                code, console, summary, usage, _ = run_step(NUMBERS, execution_file=budget_stop(cost))
                self.assertEqual(code, 0, console)
                record = json.loads(usage)
                self.assertIs(record["budget_stop"], True)
                self.assertIs(record["successful_result"], False)
                self.assertEqual(record["result_chars"], len(written))  # the text the publish step shows
                self.assertIn("Budget stop: the client stopped the run at its 5 USD budget (error_max_budget_usd), "
                              "before a final report.", summary)
                code, console, summary, *_ = run_step(REPORT, execution_file=budget_stop(cost))
                self.assertEqual(code, 0, console)
                self.assertIn("<pre>\n" + written + "\n</pre>\n", summary)
                self.assertIn("Budget stop: the client stopped the run at its budget (error_max_budget_usd) before "
                              "a final report; shown is the text the model wrote until then.", summary)
        _, _, summary, *_ = run_step(REPORT, execution_file=execution())
        self.assertNotIn("Budget stop", summary)

    def test_a_budget_stop_above_the_bound_or_without_text_fails(self):
        code, console, summary, *_ = run_step(NUMBERS, execution_file=budget_stop(5.51))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: client cost estimate 5.51 USD, above the 5.5 USD bound", console)
        self.assertIn("Budget stop:", summary)
        self.assertIn("Over the cost bound:", summary)
        code, console, *_ = run_step(NUMBERS, execution_file=budget_stop(5.3, written=False))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: no result text", console)
        code, console, *_ = run_step(NUMBERS, execution_file=execution(subtype="error_max_turns", is_error=True))
        self.assertIn("the run did not end in success or in a budget stop", console)

    def assert_refused_as_a_non_string_tool_entry(self, entry):
        # A non-string entry in the session's tool list is a tool outside the allow-list, not one dropped unchecked.
        code, console, _, usage, _ = run_step(NUMBERS, execution_file=execution(tools=("Read", "Glob", "Grep", entry)))
        self.assertNotEqual(code, 0)
        self.assertIn("Bounds not met: tools outside Read, Glob and Grep: non-string tool entry", console)
        self.assertEqual(json.loads(usage)["forbidden_tools"], ["non-string tool entry"])

    def test_an_object_in_the_tool_list_is_refused_and_named(self):
        self.assert_refused_as_a_non_string_tool_entry({"name": "Bash"})

    def test_a_null_in_the_tool_list_is_refused_and_named(self):
        self.assert_refused_as_a_non_string_tool_entry(None)

    def test_a_number_in_the_tool_list_is_refused_and_named(self):
        self.assert_refused_as_a_non_string_tool_entry(17)

    def test_the_turn_bound_counts_assistant_turns_not_transcript_messages(self):
        # On Claude Code 2.1.295 a 12-request run with parallel reads reported num_turns 57 (api-actions LR
        # receipt, 2026-10-08): num_turns counts transcript messages, tool results included.
        code, console, *_ = run_step(NUMBERS, execution_file=execution(turns=12, num_turns=57))
        self.assertEqual(code, 0, console)
        # 31 assistant turns fail although num_turns, 30, is within the cap.
        code, *_ = run_step(NUMBERS, execution_file=execution(turns=31, num_turns=30))
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
        self.assertIn("bytes; the first 60,000 are shown.", summary)

    def test_a_report_of_exactly_the_cap_has_no_notice_and_one_byte_more_has_one(self):
        # J8 micro read of #892 (2026-10-09): `jq -r` added a newline, so a 60,000-byte report was announced as cut.
        code, console, summary, *_ = run_step(REPORT, execution_file=execution(result="a" * 60000))
        self.assertEqual(code, 0, console)
        self.assertIn("a" * 60000, summary)
        self.assertNotIn("are shown.", summary)
        code, console, summary, *_ = run_step(REPORT, execution_file=execution(result="a" * 60001))
        self.assertEqual(code, 0, console)
        self.assertIn("The report is 60001 bytes; the first 60,000 are shown.", summary)

    def test_report_notice_normalizes_padded_wc_byte_count(self):
        # BSD wc pads redirected byte counts; the notice must still contain an ordinary decimal number.
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "wc"
            binary.write_text("#!/bin/sh\nprintf '    %s\\n' \"$(" +
                              shlex.quote(shutil.which("wc")) + " \"$@\")\"\n", encoding="utf-8")
            binary.chmod(0o755)
            code, console, summary, *_ = run_step(
                REPORT, env_changes={"PATH": temporary + os.pathsep + os.environ["PATH"]},
                execution_file=execution(result="a" * 60001))
        self.assertEqual(code, 0, console)
        self.assertIn("The report is 60001 bytes; the first 60,000 are shown.", summary)

    def test_a_report_one_byte_under_the_cap_is_published_whole_without_a_notice(self):
        report = "a" * 59998 + "Z"
        code, console, summary, *_ = run_step(REPORT, execution_file=execution(result=report))
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>\n" + report + "\n</pre>\n", summary)
        self.assertNotIn("are shown.", summary)

    def test_the_cap_never_splits_a_character_and_a_short_report_has_no_notice(self):
        # 80,001 bytes: the 60,000-byte cap falls inside a two-byte character, so the 59,999 bytes before it are
        # published whole and the cut character is dropped.
        code, console, summary, *_ = run_step(REPORT, execution_file=execution(result="a" + "é" * 40000))
        self.assertEqual(code, 0, console)
        summary.encode("utf-8")  # the summary file decoded as UTF-8 when it was read
        self.assertNotIn("\ufffd", summary)
        self.assertIn("<pre>\n" + "a" + "é" * 29999 + "\n</pre>\n", summary)
        self.assertIn("The report is 80001 bytes;", summary)
        code, console, summary, *_ = run_step(REPORT, execution_file=execution(result="short report"))
        self.assertEqual(code, 0, console)
        self.assertIn("<pre>\nshort report\n</pre>\n", summary)
        self.assertNotIn("are shown.", summary)

    def test_the_report_is_the_last_result_with_text(self):
        log = execution(result="the report")
        log.append({"type": "result", "subtype": "success", "is_error": False, "num_turns": 0, "result": "",
                    "total_cost_usd": 0.7, "modelUsage": model_usage()})
        code, console, summary, *_ = run_step(REPORT, execution_file=log)
        self.assertEqual(code, 0, console)
        self.assertIn("the report", summary)


if __name__ == "__main__":
    unittest.main()



CHOOSE = "Choose the heads"
WORKFLOW_ID = 4242
# A stand-in for `gh api` with the GitHub REST shapes the workflow reads: --paginate walks pages of 100 and applies
# --jq to each page, as gh does; without --paginate only the first page comes back. `fail` names an endpoint whose
# call exits 1, as an API error does.
FAKE_GH = """\
#!/usr/bin/env python3
import json, os, re, subprocess, sys
fx = json.load(open(os.path.join(os.environ["RUNNER_TEMP"], "fixtures.json")))
args = sys.argv[1:]
if not args or args[0] != "api":
    sys.exit(99)
paginate = "--paginate" in args
rest = [a for a in args[1:] if a != "--paginate"]
path = rest[0]
jq = rest[rest.index("--jq") + 1] if "--jq" in rest else None
def pages(items, key=None):
    chunks = [items[i:i + 100] for i in range(0, len(items), 100)] or [[]]
    chunks = chunks if paginate else chunks[:1]
    return [chunk if key is None else {key: chunk} for chunk in chunks]
if path.endswith("/actions/workflows/claude-pr-review.yml"):
    kind, bodies = "workflow", [{"id": fx["workflow_id"]}]
elif "/actions/workflows/claude-pr-review.yml/runs?" in path:
    kind, bodies = "runs", pages(fx["runs"], "workflow_runs")
elif re.search(r"/actions/runs/[0-9]+/jobs", path):
    run = re.search(r"/actions/runs/([0-9]+)/jobs", path).group(1)
    jobs = [{"id": i + 1, "name": "Review pull request 1 (read-only, bounded)", "conclusion": "success"}
            for i in range(fx["jobs"].get(run, 0))]
    jobs.append({"id": 0, "name": "Choose the pull request heads to review (no token)", "conclusion": "success"})
    kind, bodies = "jobs", pages(jobs, "jobs")
elif re.search(r"/actions/runs/[0-9]+$", path):
    info = fx["run_info"].get(path.rsplit("/", 1)[1])
    kind = "run"
    bodies = None if info is None else [{"workflow_id": info[0], "event": info[1], "head_branch": info[2],
                                         "head_repository": {"full_name": info[3]}}]
elif "/pulls?" in path:
    kind, bodies = "pulls", pages(fx["pulls"])
elif "/actions/artifacts?name=" in path:
    name = path.split("name=", 1)[1].split("&", 1)[0]
    arts = [{"name": name, "expired": False, "workflow_run": {"id": run_id}}
            for run_id in fx["artifacts"].get(name, [])]
    kind, bodies = "artifacts", pages(arts, "artifacts")
else:
    sys.exit(98)
if fx["fail"] == kind or bodies is None:
    sys.stderr.write("gh: HTTP 502\\n")
    sys.exit(1)
for body in bodies:
    text = json.dumps(body)
    if jq is None:
        sys.stdout.write(text)
    else:
        sys.stdout.write(subprocess.run(["jq", "-r", jq], input=text, capture_output=True, text=True,
                                        check=True).stdout)
"""


def open_pull(number, sha, **changes):
    data = pull(**changes)
    data["number"] = number
    data["head"]["sha"] = sha
    return data


def sha_of(n):
    return f"{n:040x}"


class Api:
    """Fixtures for the stand-in gh: today's runs, their review jobs, open pull requests and completion markers."""

    def __init__(self, pulls=(), fail=None):
        self.data = {"workflow_id": WORKFLOW_ID, "runs": [], "jobs": {}, "pulls": list(pulls), "artifacts": {},
                     "run_info": {}, "fail": fail}

    def marker(self, pr, sha, run_id, workflow_id=WORKFLOW_ID, event="schedule", branch="main", repo=REPOSITORY):
        self.data["artifacts"].setdefault(f"claude-pr-review-done-pr{pr}-{sha}", []).append(run_id)
        self.data["run_info"][str(run_id)] = [workflow_id, event, branch, repo]
        return self

    def reviews_today(self, run_id, count, event="schedule", branch="main"):
        self.data["runs"].append({"id": run_id, "head_branch": branch, "event": event})
        self.data["jobs"][str(run_id)] = count
        return self


def run_api_step(script, api, values):
    """Run a step's shell against the stand-in gh. Returns (exit code, console, outputs, summary)."""
    if subprocess.run(["bash", "-c", "shopt -s inherit_errexit"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode:
        raise unittest.SkipTest(
            "Ubuntu resolve/recheck integration requires Bash inherit_errexit (4.4+); macOS system Bash 3.2 lacks it")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        (directory / "fixtures.json").write_text(json.dumps(api.data), encoding="utf-8")
        bin_dir = directory / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH, encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        output, summary = directory / "output", directory / "summary.md"
        variables = {"PATH": str(bin_dir) + os.pathsep + SEARCH_PATH,
                     "LANG": "C.UTF-8", "HOME": str(directory), "RUNNER_TEMP": str(directory),
                     "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary), "GH_REPO": REPOSITORY,
                     "GH_TOKEN": "synthetic-not-a-token"}
        variables.update(values)
        done = subprocess.run(["bash", "-c", script], env=variables, capture_output=True, text=True, check=False,
                              cwd=directory)
        outputs = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
        return (done.returncode, done.stdout + done.stderr, outputs,
                summary.read_text(encoding="utf-8") if summary.exists() else "")


SEARCH_PATH = os.environ.get("PATH", os.defpath)


def run_choose(api, event="schedule", changes=None):
    choose = next(item for item in workflow()["jobs"]["resolve"]["steps"] if item.get("name") == CHOOSE)
    values = {"EVENT_NAME": event, "PR_NUMBER": "", "HEAD_SHA": "", "DAILY_USD": "55"}
    values.update(changes or {})
    return run_api_step(choose["run"], api, values)


def heads_of(outputs):
    return [(h["pr_number"], h["head_sha"]) for h in json.loads(outputs.get("heads", "[]"))]


@unittest.skipUnless(shutil.which("jq"), "jq is needed to run the resolve step")
class ResolveStepTests(unittest.TestCase):
    """The tokenless resolve job: which heads a tick reviews. A skipped tick exits 0 with go=false and no heads."""

    def test_a_dispatch_passes_its_checked_inputs_through(self):
        code, console, outputs, _ = run_choose(Api(), "workflow_dispatch", {"PR_NUMBER": "12", "HEAD_SHA": HEAD})
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs["go"], "true")
        self.assertEqual(heads_of(outputs), [(12, HEAD)])

    def test_a_malformed_dispatch_is_refused(self):
        for changes in ({"PR_NUMBER": "12; x", "HEAD_SHA": HEAD}, {"PR_NUMBER": "12", "HEAD_SHA": "main"}):
            with self.subTest(changes=changes):
                code, console, outputs, _ = run_choose(Api(), "workflow_dispatch", changes)
                self.assertEqual(code, 2, console)
                self.assertNotIn("go", outputs)

    def test_an_open_same_repository_non_draft_head_not_yet_reviewed_is_chosen(self):
        code, console, outputs, summary = run_choose(Api([open_pull(7, HEAD)]))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs["go"], "true")
        self.assertEqual(heads_of(outputs), [(7, HEAD)])
        self.assertIn(f"Review: pull request #7 at {HEAD}", summary)
        self.assertNotIn(TITLE_MARKER, console + summary)

    def test_a_fork_head_a_draft_another_base_and_a_closed_pull_request_are_never_chosen(self):
        pulls = [open_pull(1, sha_of(1), **{"head.repo.full_name": "someone/fork"}),
                 open_pull(2, sha_of(2), draft=True),
                 open_pull(3, sha_of(3), **{"base.ref": "release"}),
                 open_pull(4, sha_of(4), state="closed"),
                 open_pull(5, sha_of(5), **{"base.repo.full_name": "someone/else"})]
        code, console, outputs, summary = run_choose(Api(pulls))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "false", "heads": "[]"})
        self.assertIn("No review this run", summary)

    def test_a_completed_head_is_skipped_and_a_new_head_of_the_same_pull_request_is_chosen(self):
        code, console, outputs, _ = run_choose(Api([open_pull(7, HEAD)]).marker(7, HEAD, 9001))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs["go"], "false")
        code, console, outputs, _ = run_choose(Api([open_pull(7, "c" * 40)]).marker(7, HEAD, 9001))
        self.assertEqual(code, 0, console)
        self.assertEqual(heads_of(outputs), [(7, "c" * 40)])

    def test_a_marker_from_anything_but_this_workflows_schedule_or_dispatch_on_main_here_is_ignored(self):
        # GPT read of #932, P2 1: a fork's branch can be named main, and any workflow can upload an artifact with the
        # marker's name; the uploading run is looked up and must be this workflow's own on main in this repository.
        spoofs = {
            "a fork's branch named main": dict(repo="someone/fork"),
            "a pull_request run": dict(event="pull_request"),
            "another workflow": dict(workflow_id=999),
            "another branch": dict(branch="feature"),
        }
        for label, changes in spoofs.items():
            with self.subTest(spoof=label):
                code, console, outputs, _ = run_choose(Api([open_pull(7, HEAD)]).marker(7, HEAD, 9002, **changes))
                self.assertEqual(code, 0, console)
                self.assertEqual(heads_of(outputs), [(7, HEAD)])
        api = Api([open_pull(7, HEAD)]).marker(7, HEAD, 9003, event="workflow_dispatch")
        self.assertEqual(run_choose(api)[2]["go"], "false")

    def test_a_usage_record_without_a_completion_marker_does_not_count_as_reviewed(self):
        # P2 3: a failed review leaves a usage record but no marker, so the head is tried again.
        api = Api([open_pull(7, HEAD)])
        api.data["artifacts"][f"claude-pr-review-usage-pr7-{HEAD}-9004"] = [9004]
        api.data["run_info"]["9004"] = [WORKFLOW_ID, "schedule", "main", REPOSITORY]
        self.assertEqual(heads_of(run_choose(api)[2]), [(7, HEAD)])

    def test_more_than_a_page_of_pull_requests_still_reaches_every_head(self):
        # P2 2: with 101 eligible pull requests and the oldest 100 completed, the 101st is chosen.
        api = Api([open_pull(n, sha_of(n)) for n in range(1, 102)])
        for n in range(1, 101):
            api.marker(n, sha_of(n), 10000 + n)
        code, console, outputs, _ = run_choose(api)
        self.assertEqual(code, 0, console)
        self.assertEqual(heads_of(outputs), [(101, sha_of(101))])

    def test_the_daily_ceiling_counts_reviews_past_the_first_page_of_runs(self):
        # P2 2: 100 newer runs without reviews come before an older run with ten; the ceiling still holds.
        api = Api([open_pull(7, HEAD)])
        for run_id in range(1, 101):
            api.reviews_today(run_id, 0)
        api.reviews_today(500, 10)
        code, console, outputs, summary = run_choose(api)
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "false", "heads": "[]"})
        self.assertIn("daily ceiling of 55 USD", summary)

    def test_at_most_two_heads_per_tick_oldest_first(self):
        code, console, outputs, _ = run_choose(Api([open_pull(n, sha_of(n)) for n in (3, 4, 5)]))
        self.assertEqual(code, 0, console)
        self.assertEqual([n for n, _ in heads_of(outputs)], [3, 4])

    def test_the_daily_ceiling_stops_new_reviews_and_reports_it(self):
        code, console, outputs, summary = run_choose(Api([open_pull(7, HEAD)]).reviews_today(101, 10))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "false", "heads": "[]"})
        self.assertIn("daily ceiling of 55 USD", summary)
        api = Api([open_pull(7, HEAD), open_pull(8, "d" * 40)]).reviews_today(101, 9)
        self.assertEqual(heads_of(run_choose(api)[2]), [(7, HEAD)])  # room for one more review at 5.50 USD

    def test_runs_from_pull_request_events_or_other_branches_do_not_count_toward_the_ceiling(self):
        api = Api([open_pull(7, HEAD)]).reviews_today(101, 50, event="pull_request")
        api.reviews_today(102, 50, branch="feature")
        self.assertEqual(heads_of(run_choose(api)[2]), [(7, HEAD)])

    def test_a_malformed_ceiling_skips(self):
        code, console, outputs, _ = run_choose(Api([open_pull(7, HEAD)]), changes={"DAILY_USD": "1e9"})
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs["go"], "false")

    def test_an_api_failure_fails_the_job_and_chooses_nothing(self):
        for endpoint in ("workflow", "runs", "jobs", "pulls", "artifacts", "run"):
            with self.subTest(endpoint=endpoint):
                api = Api([open_pull(7, "e" * 40)], fail=endpoint).reviews_today(101, 1).marker(7, "e" * 40, 9005)
                code, console, outputs, _ = run_choose(api)
                self.assertNotEqual(code, 0, console)
                self.assertNotEqual(outputs.get("go"), "true")

    def test_another_event_skips(self):
        code, console, outputs, _ = run_choose(Api([open_pull(7, HEAD)]), "push")
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs["go"], "false")


@unittest.skipUnless(shutil.which("jq"), "jq is needed to run the recheck step")
class RecheckStepTests(unittest.TestCase):
    """P2 4: the review job's recheck once it holds its head's group."""

    def run_fresh(self, api, event="schedule"):
        return run_api_step(step(FRESH)["run"], api, {"EVENT_NAME": event, "PR_NUMBER": "7", "HEAD_SHA": HEAD})

    def test_a_scheduled_review_of_a_head_completed_while_it_waited_is_skipped(self):
        code, console, outputs, summary = self.run_fresh(Api().marker(7, HEAD, 9010, event="workflow_dispatch"))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "false"})
        self.assertIn("was reviewed while this run waited", summary)

    def test_a_scheduled_review_of_an_uncompleted_head_goes_ahead(self):
        code, console, outputs, _ = self.run_fresh(Api().marker(7, HEAD, 9011, repo="someone/fork"))
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "true"})

    def test_a_dispatch_always_reviews(self):
        code, console, outputs, _ = self.run_fresh(Api().marker(7, HEAD, 9012), "workflow_dispatch")
        self.assertEqual(code, 0, console)
        self.assertEqual(outputs, {"go": "true"})

    def test_an_api_failure_fails_the_step(self):
        for endpoint in ("workflow", "artifacts", "run"):
            with self.subTest(endpoint=endpoint):
                code, console, outputs, _ = self.run_fresh(Api(fail=endpoint).marker(7, HEAD, 9013))
                self.assertNotEqual(code, 0, console)
                self.assertNotEqual(outputs.get("go"), "true")
