"""Hosted-model freshness: native catalogs, active selectors and dated evidence."""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import active_model_currency as mc

NOW = "2026-10-09T20:31:55Z"


def catalog():
    latest = {"gpt-sol": "gpt-6.1-sol", "gpt-astra": "gpt-6-astra", "gpt-luna": "gpt-6-luna",
              "claude-opus": "claude-opus-5-5", "claude-sonnet": "claude-sonnet-5-5",
              "claude-haiku": "claude-haiku-5-5", "claude-fable": "claude-fable-5-1"}
    aliases = {value: value for value in latest.values()}
    aliases["gpt-6.1-sol-max"] = "gpt-6.1-sol"
    aliases["claude-opus-5-5[1m]"] = "claude-opus-5-5"
    return {"schema_version": 1, "catalog_kind": "versioned_snapshot", "generated_at": NOW,
            "latest": latest, "aliases": aliases,
            "sources": [{"name": name, "observed_at": NOW, "sha256": "a" * 64, "rows": 1}
                        for name in ("codex", "omniroute", "claude")]}


class ActiveModelCurrencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.manifest = self.root / mc.MANIFEST
        self.write(mc.MANIFEST, json.dumps(catalog()))

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def check(self):
        return mc.check(catalog(), [self.root])

    def cli(self, *arguments, event=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                mock.patch("sys.stdin", io.StringIO(json.dumps(event) if event is not None else "")):
            rc = mc.main([*arguments, "--root", str(self.root), "--now", NOW, "--json"])
        return rc, stdout.getvalue(), stderr.getvalue()

    def test_current_models_and_observed_effort_alias_pass(self):
        self.write("adoption/templates/client.toml", 'model = "cx/gpt-6.1-sol-max"\nreview_model = "gpt-6-astra"\n')
        self.assertEqual(self.check()["status"], "current")
        self.assertEqual(self.cli("check")[0], 0)

    def test_committed_catalog_snapshot_still_checks_after_the_old_expiry(self):
        source = Path(mc.__file__).resolve().parents[1] / mc.MANIFEST
        self.manifest.write_bytes(source.read_bytes())
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = mc.main(["check", "--root", str(self.root), "--now", "2026-10-11T00:00:00Z", "--json"])
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["status"], "current")

    def test_stale_active_default_fails_and_reports_only_model_values(self):
        sentinel = "private-fixture-value-must-never-be-printed"
        self.write("config.json", json.dumps({"api_key": sentinel, "model": "gpt-6-sol"}))
        rc, stdout, _ = self.cli("check")
        self.assertEqual(rc, 1)
        result = json.loads(stdout)
        self.assertEqual(result["findings"][0]["expected"], "gpt-6.1-sol")
        self.assertNotIn(sentinel, stdout)
        self.assertNotIn("api_key", stdout)

    def test_active_markdown_agent_is_not_exempt(self):
        self.write("adoption/agents/claude/helper.md", '---\nmodel: claude-opus-5\n---\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_active_lane_and_date_named_config_are_not_exempt(self):
        self.write("lanes/wsl-lab/config-20261009.yaml", 'model: gpt-6-sol\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_active_research_or_notes_defaults_are_not_blanket_exempt(self):
        self.write("research/worker.py", 'DEFAULT_MODEL = "gpt-6-sol"\n')
        self.write("notes/agents/helper.md", 'model: claude-opus-5\n')
        self.assertEqual(self.check()["stale_count"], 2)

    def test_current_install_kit_configuration_remains_active(self):
        self.write("evidence/artifacts/new-wsl-install-plan-20261002/config/client.json", '{"model":"claude-opus-5"}')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_dated_record_and_decision_preserve_old_models(self):
        self.write("evidence/receipts/old.json", '{"model":"gpt-6-sol"}')
        self.write("docs/decisions/2026-09-20-route.md", 'model: claude-opus-5\n')
        receipt = self.write("observability/receipt.json", json.dumps({"recorded_at": "2026-09-20T00:00:00Z", "model": "gpt-6-sol"}))
        before = receipt.read_bytes()
        self.assertEqual(self.check()["stale_count"], 0)
        self.assertEqual(receipt.read_bytes(), before)

    def test_date_in_active_json_does_not_exempt_it(self):
        self.write("client.json", '{"generated_at":"2026-09-20T00:00:00Z","model":"gpt-6-sol"}')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_timestamped_measurements_inside_live_carrier_are_records(self):
        self.write("docs/live.json", json.dumps({"model": "gpt-6.1-sol", "observations": [
            {"started_at_utc": "2026-09-20T00:00:00Z", "exit_code": 0, "requested_model": "gpt-6-sol"}]}))
        self.assertEqual(self.check()["stale_count"], 0)

    def test_supported_catalog_is_not_a_python_default(self):
        self.write("tools/check.py", 'import re\nMODEL = re.compile(r"gpt-reserve|gpt-[0-9]+")\nDEFAULT_MODEL = "gpt-6.1-sol"\n')
        self.assertEqual(self.check()["stale_count"], 0)

    def test_python_cli_environment_and_mapping_defaults_are_checked(self):
        self.write("tools/run.py", 'import os\nMODEL = os.getenv("MODEL", "gpt-6-sol")\nparser.add_argument("--model", default="claude-opus-5")\nconfig = {"model": "gpt-6-sol"}\n')
        self.assertEqual(self.check()["stale_count"], 3)

    def test_runtime_worker_argv_model_mutation_is_flagged(self):
        root = Path(mc.__file__).resolve().parents[1]
        name = "blueprints/us-equities/research-runtime/run_worker.py"
        source = (root / name).read_text()
        original = "'--model', 'claude-opus-5-5'"
        self.assertIn(original, source)
        self.write(name, source.replace(original, "'--model', 'claude-opus-5'", 1))
        code, stdout, stderr = self.cli("check")
        self.assertEqual((code, stderr), (1, ""))
        self.assertTrue(any(item["model"] == "claude-opus-5" for item in json.loads(stdout)["findings"]))

    def test_install_plan_json_command_model_mutation_is_flagged(self):
        root = Path(mc.__file__).resolve().parents[1]
        name = "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json"
        document = json.loads((root / name).read_text())
        def mutate(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "command" and isinstance(child, str) and "gpt-6.1-sol" in child and "-m " in child:
                        value[key] = child.replace("gpt-6.1-sol", "gpt-6-sol", 1)
                        return True
                    if mutate(child):
                        return True
            elif isinstance(value, list):
                return any(mutate(child) for child in value)
            return False
        self.assertTrue(mutate(document), "native install plan no longer contains the reviewed model command")
        manifest = json.loads((root / mc.MANIFEST).read_text())
        manifest["generated_at"] = NOW
        self.manifest.write_text(json.dumps(manifest))
        self.write(name, json.dumps(document, indent=2))
        code, stdout, stderr = self.cli("check")
        self.assertEqual((code, stderr), (1, ""))
        self.assertTrue(any(item["model"] == "gpt-6-sol" for item in json.loads(stdout)["findings"]))

    def test_new_python_argv_file_is_checked(self):
        self.write("tools/new-worker.py", 'argv = ["claude", "--model", "claude-opus-5"]\n')
        code, stdout, stderr = self.cli("check")
        self.assertEqual((code, stderr), (1, ""))
        self.assertEqual(json.loads(stdout)["stale_count"], 1)

    def test_runtime_experiment_command_list_is_checked_at_an_active_path(self):
        root = Path(mc.__file__).resolve().parents[1]
        record = root / "blueprints/convergence-practice/omniroute-runtime-workers/experiment.json"
        commands = json.loads(record.read_text())["commands"]
        command, = [item for item in commands if "--model dva/claude-opus-5-max" in item]
        self.write("config/worker.json", json.dumps({"commands": [command]}, indent=2))
        code, stdout, stderr = self.cli("check")
        self.assertEqual((code, stderr), (1, ""))
        finding, = json.loads(stdout)["findings"]
        self.assertEqual(finding["model"], "claude-opus-5-max")
        self.assertEqual((finding["json_pointer"], finding["line"]), ("/commands/0", 3))

    def test_token_reference_upstream_commands_are_checked_at_an_active_path(self):
        root = Path(mc.__file__).resolve().parents[1]
        document = json.loads((root / "docs/token-efficiency-stack.json").read_text())
        def rows(value):
            if isinstance(value, dict):
                if value.get("component_id") == "omniroute":
                    yield value
                for child in value.values():
                    yield from rows(child)
            elif isinstance(value, list):
                for child in value:
                    yield from rows(child)
        row, = rows(document)
        commands = row["upstream_commands"]
        self.assertIn("--model claude/claude-opus-5", commands["use"][2])
        self.write("config/gateway.json", json.dumps({"upstream_commands": commands}, indent=2))
        code, stdout, stderr = self.cli("check")
        self.assertEqual((code, stderr), (1, ""))
        finding, = json.loads(stdout)["findings"]
        self.assertEqual(finding["model"], "claude-opus-5")
        self.assertEqual(finding["json_pointer"], "/upstream_commands/use/2")

    def test_command_lists_and_argv_keep_quoted_arguments_and_separate_locations(self):
        command = 'claude --model "claude-opus-5" --prompt "owner\'s task"'
        self.write("config/commands.json", json.dumps({
            "launchCommands": [command, command],
            "argv": ["claude", "--model", "claude-opus-5", "--prompt", "owner's task"],
            "execStart": "codex exec -m gpt-6-sol",
        }, indent=2))
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        findings = json.loads(stdout)["findings"]
        self.assertEqual({item["json_pointer"] for item in findings},
                         {"/launchCommands/0", "/launchCommands/1", "/argv/2", "/execStart"})
        self.assertEqual(len({item["line"] for item in findings}), 4)

    def test_confirmed_misses_are_explicitly_dated_records_with_unchanged_bytes(self):
        root = Path(mc.__file__).resolve().parents[1]
        records = {
            "blueprints/convergence-practice/omniroute-runtime-workers/experiment.json": "September 30",
            "docs/token-efficiency-stack.json": "2026-09-27",
        }
        for name, date_label in records.items():
            with self.subTest(record=name):
                original = (root / name).read_bytes()
                reason = mc.exempt(name)
                self.assertIsNotNone(reason)
                self.assertIn(date_label, reason)
                path = self.write(name, original.decode())
                self.assertEqual(self.cli("check")[0], 0)
                self.assertEqual(path.read_bytes(), original)

    def test_unquoted_selector_field_does_not_lex_its_apostrophe_prose(self):
        for name in ("config.yaml", "adoption/agents/claude/helper.md"):
            with self.subTest(source=name):
                self.write(name, "model: gpt-6.1-sol, the owner's choice\n")
                self.assertEqual(self.cli("check")[0], 0)
                self.write(name, "model: gpt-6-sol, the owner's choice\n")
                code, stdout, _ = self.cli("check")
                self.assertEqual(code, 1)
                self.assertTrue(any(item["model"] == "gpt-6-sol" for item in json.loads(stdout)["findings"]))
                (self.root / name).unlink()

    def test_git_message_is_not_a_short_model_flag_in_strings_or_argv(self):
        self.write("config/commands.json", json.dumps({
            "commands": ['git commit -m "claude-opus-5"', 'git commit -m "codex -m gpt-6-sol"'],
            "argv": ["git", "commit", "-m", "gpt-6-sol"],
        }))
        self.write("tools/message.py", 'argv = ["git", "commit", "-m", "claude-opus-5"]\n')
        self.write("tools/message.sh", 'git commit -m "codex -m gpt-6-sol"\n')
        self.assertEqual(self.cli("check")[0], 0)

    def test_real_git_messages_in_client_named_directories_are_not_selectors(self):
        environment = {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Synthetic Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Synthetic Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        executable = shutil.which("git")
        self.assertIsNotNone(executable)
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for name in ("codex", "claude"):
                subprocess.run([executable, "init", "-q", "--template=", str(parent / name)],
                               check=True, capture_output=True, env=environment)
                argv = ["git", "-C", name, "-c", "commit.gpgSign=false",
                        "commit", "--allow-empty", "-m", "gpt-6-sol"]
                subprocess.run([executable, *argv[1:]], cwd=parent, env=environment,
                               check=True, capture_output=True)
                subject = subprocess.check_output([executable, "-C", name, "log", "-1", "--format=%s"],
                                                  cwd=parent, env=environment, text=True).strip()
                self.assertEqual(subject, "gpt-6-sol")
                for form in ("command", "argv"):
                    with self.subTest(directory=name, form=form):
                        self.write("config/commands.json", json.dumps({
                            form: argv if form == "argv" else shlex.join(argv),
                        }))
                        self.assertEqual(self.check()["stale_count"], 0)

    def test_path_and_message_operands_do_not_establish_native_short_flag_context(self):
        commands = [
            ["echo", "codex", "-m", "gpt-6-sol"],
            ["echo", "claude", "-m", "gpt-6-sol"],
            ["python", "-m", "codex", "-m", "gpt-6-sol"],
            ["python", "script.py", "claude", "-m", "gpt-6-sol"],
            ["env", "-C", "codex", "git", "commit", "-m", "gpt-6-sol"],
            ["flock", "codex", "git", "commit", "-m", "gpt-6-sol"],
            ["nice", "-n", "5", "git", "-C", "codex", "commit", "-m", "gpt-6-sol"],
            ["exec", "-a", "codex", "git", "commit", "-m", "gpt-6-sol"],
            ["timeout", "-s", "codex", "5", "git", "commit", "-m", "gpt-6-sol"],
        ]
        for argv in commands:
            for form in ("command", "argv"):
                with self.subTest(argv=argv, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: argv if form == "argv" else shlex.join(argv),
                    }))
                    self.assertEqual(self.check()["stale_count"], 0)

    def test_native_context_stops_at_the_next_command_boundary(self):
        self.write("config/commands.json", json.dumps({"commands": [
            "codex exec -m gpt-6.1-sol && git -C codex commit -m gpt-6-sol",
            "codex exec -m gpt-6.1-sol # native client\necho codex -m gpt-6-sol",
        ]}))
        self.assertEqual(self.check()["stale_count"], 0)

    def test_literal_argv_shell_punctuation_does_not_create_an_executable_position(self):
        for delimiter in ("&&", ";", "\n"):
            with self.subTest(delimiter=delimiter):
                self.write("config/commands.json", json.dumps({
                    "argv": ["echo", delimiter, "codex", "-m", "gpt-6-sol"],
                }))
                self.assertEqual(self.check()["stale_count"], 0)

    def test_independent_markdown_spans_do_not_join_client_mentions_to_messages(self):
        self.write("docs/client-messages.md",
                   "Use `codex` alongside `git -C codex commit -m gpt-6-sol`.\n"
                   "Compare `codex exec -m gpt-6.1-sol` and `echo codex -m gpt-6-sol`.\n")
        self.assertEqual(self.check()["stale_count"], 0)

    def test_claude_has_only_the_advertised_long_model_flag(self):
        self.write("config/commands.json", json.dumps({"commands": [
            "claude -m claude-opus-5", "nice -n 5 claude -m claude-opus-5",
            "claude --model claude-opus-5", "nohup claude --model claude-opus-5",
        ]}))
        result = self.check()
        self.assertEqual(result["stale_count"], 2)
        self.assertEqual({item["json_pointer"] for item in result["findings"]}, {"/commands/2", "/commands/3"})

    def test_wrapper_option_operands_and_nested_wrappers_preserve_invoked_codex(self):
        prefixes = [
            ["env", "-C", "/tmp/codex", "-u", "MODEL", "FOO=bar", "/usr/bin/codex", "exec"],
            ["timeout", "-k", "2s", "-s", "TERM", "10s", "codex", "exec"],
            ["exec", "-a", "claude", "codex", "exec"],
            ["rtk", "--skip-env", "proxy", "codex", "exec"],
            ["nice", "--adjustment=5", "nohup", "flock", "-w", "2", "/tmp/claude",
             "timeout", "10", "codex", "exec"],
            ["command", "-p", "codex", "exec"],
        ]
        for prefix in prefixes:
            argv = [*prefix, "-m", "gpt-6-sol"]
            for form in ("command", "argv"):
                with self.subTest(prefix=prefix, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: argv if form == "argv" else shlex.join(argv),
                    }))
                    result = self.check()
                    self.assertEqual(result["stale_count"], 1)
                    finding, = result["findings"]
                    self.assertEqual(finding["model"], "gpt-6-sol")
                    pointer = f"/argv/{len(argv) - 1}" if form == "argv" else "/command"
                    self.assertEqual(finding["json_pointer"], pointer)

    def test_readiness_ionice_launch_reports_stale_model_in_strings_and_argv(self):
        # util-linux v2.41.3 schedutils/ionice.c:140-157; the readiness
        # launch uses attached class/classdata operands after nice.
        prefixes = [
            ["nice", "-n", "10", "ionice", "-c2", "-n7"],
            ["nice", "-n", "10", "ionice", "--class", "2", "--classdata=7", "--ignore"],
            ["nice", "-n", "10", "ionice", "-tc2", "-n", "7", "--"],
        ]
        for prefix in prefixes:
            argv = [*prefix, "codex", "exec", "-m", "gpt-6-sol"]
            for form in ("command", "argv"):
                with self.subTest(prefix=prefix, form=form):
                    self.write("catalogs/north-star/readiness.json", json.dumps({
                        "launch": {form: argv if form == "argv" else shlex.join(argv)},
                    }))
                    code, stdout, _ = self.cli("check")
                    self.assertEqual(code, 1)
                    result = json.loads(stdout)
                    self.assertEqual((result["status"], result["stale_count"]), ("stale", 1))
                    finding, = result["findings"]
                    self.assertEqual(finding["model"], "gpt-6-sol")
                    pointer = f"/launch/argv/{len(argv) - 1}" if form == "argv" else "/launch/command"
                    self.assertEqual(finding["json_pointer"], pointer)

    def test_hcom_launch_checks_only_the_invoked_codex_and_forwarded_model_option(self):
        # hcom v0.7.28 commands/launch.rs strips global and launcher operands
        # before forwarding the remaining arguments to its selected tool.
        prefixes = [
            ["hcom", "--go", "codex", "--tag", "fixture", "--dir", "/tmp/codex",
             "--hcom-prompt", "compare codex and claude", "exec"],
            ["hcom", "--name", "fixture", "--go", "2", "codex", "--terminal=wt-tmux"],
        ]
        for prefix in prefixes:
            argv = [*prefix, "-m", "gpt-6-sol"]
            for form in ("command", "argv"):
                with self.subTest(prefix=prefix, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: argv if form == "argv" else shlex.join(argv),
                    }))
                    self.assertEqual(self.check()["stale_count"], 1)

        for argv in (["hcom", "--name", "codex", "send", "claude", "-m", "gpt-6-sol"],
                     ["hcom", "--go", "claude", "-m", "claude-opus-5"],
                     ["hcom", "--go", "codex", "--tag", "-m", "gpt-6-sol"],
                     ["hcom", "--go", "codex", "--hcom-prompt", "-m", "gpt-6-sol"]):
            for form in ("command", "argv"):
                with self.subTest(argv=argv, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: argv if form == "argv" else shlex.join(argv),
                    }))
                    self.assertEqual(self.check()["stale_count"], 0)

    def test_markdown_formatting_preserves_surrounding_native_commands(self):
        documents = [
            "```sh\ncodex exec -m gpt-6-sol # select `default`\n```\n",
            "codex exec -m `gpt-6-sol`\n",
            "`codex` exec `-m` `gpt-6-sol`\n",
        ]
        for text in documents:
            with self.subTest(text=text):
                self.write("docs/launch.md", text)
                result = self.check()
                self.assertEqual((result["status"], result["stale_count"]), ("stale", 1))
                finding, = result["findings"]
                self.assertEqual(finding["model"], "gpt-6-sol")

    def test_formatted_non_native_executable_keeps_its_operand_context(self):
        for command in ("`echo` codex -m gpt-6-sol",
                        "`printf` codex -m gpt-6-sol",
                        "`/bin/echo` codex exec -m gpt-6-sol"):
            with self.subTest(command=command):
                self.write("docs/launch.md", command + "\n")
                result = self.check()
                self.assertEqual((result["status"], result["stale_count"]), ("current", 0))

    def test_comment_spans_do_not_hide_formatted_native_model_arguments(self):
        for comment in ("default model", "default"):
            for command in ("codex exec -m `gpt-6-sol`",
                            "`codex` exec `-m` `gpt-6-sol`"):
                with self.subTest(comment=comment, command=command):
                    self.write("docs/launch.md", command + f" # select `{comment}`\n")
                    result = self.check()
                    self.assertEqual((result["status"], result["stale_count"]), ("stale", 1))
                    finding, = result["findings"]
                    self.assertEqual((finding["model"], finding["line"]), ("gpt-6-sol", 1))

    def test_quoted_and_escaped_punctuation_remains_an_operand_in_command_strings(self):
        commands = ["echo ';' codex -m gpt-6-sol", r"echo \; codex -m gpt-6-sol",
                    'echo "&&" codex -m gpt-6-sol']
        for command in commands:
            for form in ("command", "argv"):
                with self.subTest(command=command, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: shlex.split(command) if form == "argv" else command,
                    }))
                    self.assertEqual(self.check()["stale_count"], 0)
        self.write("config/commands.json", json.dumps({
            "command": "echo x; codex exec -m gpt-6-sol",
        }))
        self.assertEqual(self.check()["stale_count"], 1)

    def test_ionice_targeting_and_message_operands_do_not_establish_native_context(self):
        prefixes = [
            ["ionice", "-p", "123", "codex"], ["ionice", "-P123", "codex"],
            ["ionice", "--uid=1000", "codex"], ["ionice", "-tp123", "codex"],
            ["ionice", "--help", "codex"], ["ionice", "--version", "codex"],
            ["ionice", "--class", "codex"],
            ["ionice", "-c2", "echo", "codex"],
            ["nice", "-n", "10", "ionice", "-c2", "git", "-C", "codex", "commit"],
        ]
        for prefix in prefixes:
            argv = [*prefix, "-m", "gpt-6-sol"]
            for form in ("command", "argv"):
                with self.subTest(prefix=prefix, form=form):
                    self.write("config/commands.json", json.dumps({
                        form: argv if form == "argv" else shlex.join(argv),
                    }))
                    self.assertEqual(self.check()["stale_count"], 0)

    def test_published_g5_catalog_record_does_not_mask_active_copies_or_size_gaps(self):
        name = "catalogs/landscape/grand-catalog-20261008.json"
        document = {"schema_version": 1, "kind": "g5-compact-landscape", "release_tag": "v2026.10.08",
                    "rows": [{"source_model_ids": ["gpt-6-sol"]}], "padding": "x" * mc.MAX_BYTES}
        text = json.dumps(document)
        path = self.write(name, text)
        self.assertEqual(self.check()["status"], "current")
        self.assertEqual(path.read_text(), text)
        active = self.write("config/grand-catalog-20261008.json", text)
        self.assertEqual(self.check()["status"], "unknown")
        active.write_text(json.dumps({"model": "gpt-6-sol"}))
        result = self.check()
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["stale_count"], 1)

    def test_multiline_commands_keep_comment_boundaries_for_short_flags(self):
        self.write("config/commands.json", json.dumps({"commands": [
            'codex exec --model gpt-6.1-sol # accepted\ngit commit -m "gpt-6-sol"',
            'git status # observe\ncodex exec -m gpt-6-sol',
        ]}))
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        finding, = json.loads(stdout)["findings"]
        self.assertEqual((finding["model"], finding["json_pointer"]), ("gpt-6-sol", "/commands/1"))

    def test_multiple_selector_fields_on_one_line_remain_independent(self):
        self.write("client.js", 'const MODEL = "gpt-6.1-sol"; const REVIEW_MODEL = "gpt-6-sol"; // owner\'s note\n')
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        finding, = json.loads(stdout)["findings"]
        self.assertEqual(finding["model"], "gpt-6-sol")

    def test_native_short_model_flags_are_still_checked(self):
        self.write("config/commands.json", json.dumps({"commands": [
            "codex exec -m gpt-6-sol", "rtk claude --model claude-opus-5",
            "git status && codex exec -m gpt-6-sol",
        ]}))
        self.assertEqual(self.check()["stale_count"], 3)

    def test_wrapped_native_short_flags_are_checked_in_strings_and_argv(self):
        wrappers = (["nice", "-n", "5"], ["flock", "/tmp/model.lock"], ["nohup"])
        clients = ((["/opt/bin/codex", "exec"], "gpt-6-sol"),
                   (["/opt/bin/claude"], "claude-opus-5"))
        for wrapper in wrappers:
            for client, model in clients:
                flag = "-m" if Path(client[0]).name == "codex" else "--model"
                argv = [*wrapper, *client, flag, model]
                for form in ("command", "argv", "shell"):
                    with self.subTest(wrapper=wrapper[0], client=client[0], form=form):
                        if form == "shell":
                            name = "tools/wrapped-model.sh"
                            text = " ".join(argv) + "\n"
                        else:
                            name = "config/wrapped-model.json"
                            text = json.dumps({form: argv if form == "argv" else " ".join(argv)})
                        path = self.write(name, text)
                        try:
                            result = self.check()
                        finally:
                            path.unlink()
                        self.assertEqual(result["stale_count"], 1)
                        finding, = result["findings"]
                        self.assertEqual(finding["model"], model)
                        if form != "shell":
                            pointer = f"/argv/{len(argv) - 1}" if form == "argv" else "/command"
                            self.assertEqual(finding["json_pointer"], pointer)

    def test_backticked_markdown_native_model_arguments_are_checked(self):
        for text in (
                "Use `--model gpt-6-sol` for the active client.\n",
                "Use `--model` `gpt-6-sol` for the active client.\n",
                "Use ``--model=gpt-6-sol`` for the active client.\n",
                "Use `codex exec -m gpt-6-sol` for the active client.\n",
                "Use `nice -n 5 codex exec -m gpt-6-sol` for the active client.\n"):
            with self.subTest(text=text):
                self.write("docs/model-selection.md", text)
                self.assertEqual(self.check()["stale_count"], 1)

    def test_markdown_code_spans_keep_prose_punctuation_out_of_model_values(self):
        for model, stale_count in (("gpt-6-sol", 1), ("gpt-6.1-sol", 0), ('"gpt-6.1-sol."', 1)):
            with self.subTest(model=model):
                self.write("docs/model-selection.md", f"Use `codex exec --model {model}`.\n")
                result = self.check()
                self.assertEqual(result["stale_count"], stale_count)
                if stale_count:
                    finding, = result["findings"]
                    self.assertEqual(finding["model"], model.strip('"'))
                else:
                    self.assertEqual(result["status"], "current")

    def test_an_unclosed_model_argument_remains_a_coverage_gap(self):
        self.write("config/commands.json", json.dumps({"command": 'codex exec --model "gpt-6-sol'}))
        self.assertEqual(self.cli("check")[0], 2)

    def test_frozen_research_comparison_keeps_its_exact_model_commands(self):
        name = "blueprints/us-equities/research-efficiency/experiment.py"
        path = self.write(name, 'command = ["claude", "--model", "claude-opus-5"]\n')
        before = path.read_bytes()
        self.assertEqual(self.cli("check")[0], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_non_model_command_description_is_not_a_shell_parse_error(self):
        self.write("config.json", json.dumps({"model": "gpt-6.1-sol", "command": "Run the owner's acceptance"}))
        self.assertEqual(self.cli("check")[0], 0)

    def test_large_non_model_text_does_not_make_model_coverage_unknown(self):
        self.write("large-source.md", "ordinary reference text\n" * (mc.MAX_BYTES // 10))
        self.assertEqual(self.cli("check")[0], 0)

    def test_non_utf8_non_model_file_does_not_make_model_coverage_unknown(self):
        (self.root / "unrelated.txt.py").write_bytes(b"unrelated binary marker\xff\xfe")
        self.assertEqual(self.cli("check")[0], 0)

    def test_oversized_model_candidate_still_reports_a_coverage_gap(self):
        self.write("oversized-model.py", 'MODEL = "gpt-6-sol"\n' + "# padding\n" * (mc.MAX_BYTES // 5))
        self.assertEqual(self.cli("check")[0], 2)

    def test_trailing_shell_comment_is_not_a_model_selector(self):
        self.write("client.toml", 'MODEL = "gpt-6.1-sol" # earlier gpt-6-sol\n')
        self.assertEqual(self.cli("check")[0], 0)

    def test_sentence_punctuation_is_not_part_of_the_documented_model(self):
        self.write("docs/operator.md", "model: gpt-6.1-sol.\n")
        self.assertEqual(self.cli("check")[0], 0)

    def test_trailing_javascript_comment_is_not_a_model_selector(self):
        self.write("client.js", 'const MODEL = "gpt-6.1-sol"; // earlier gpt-6-sol\n')
        self.assertEqual(self.cli("check")[0], 0)

    def test_quoted_runtime_model_with_a_period_is_still_invalid(self):
        self.write("client.json", '{"model":"gpt-6.1-sol."}')
        self.assertEqual(self.cli("check")[0], 1)

    def test_repeated_json_model_values_have_distinct_source_locations(self):
        self.write("clients.json", '{"first":{"model":"gpt-6-sol"},"second":{"model":"gpt-6-sol"}}')
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        findings = json.loads(stdout)["findings"]
        self.assertEqual(len(findings), 2)
        self.assertEqual({item["json_pointer"] for item in findings}, {"/first/model", "/second/model"})

    def test_json_locator_does_not_point_at_an_earlier_historical_value(self):
        self.write("client.json", '{\n "history":{"model":"gpt-6-sol"},\n "model":"gpt-6-sol"\n}\n')
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        finding, = json.loads(stdout)["findings"]
        self.assertEqual(finding["line"], 3)
        self.assertEqual(finding["json_pointer"], "/model")

    def test_additional_claude_family_is_visible_in_active_selectors(self):
        self.write("client.json", '{"model":"claude-mythos-5"}')
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout)["findings"][0]["model"], "claude-mythos-5")

    def test_claude_tool_names_are_not_model_generations(self):
        self.write("docs/operator.md", "model: gpt-6.1-sol; use claude-agent-sdk-python and claude-collect.\n")
        self.assertEqual(self.cli("check")[0], 0)

    def test_shell_line_continuation_does_not_make_the_check_incomplete(self):
        self.write("launch.sh", 'codex exec --model gpt-6.1-sol \\\n  --sandbox read-only\n')
        self.assertEqual(self.cli("check")[0], 0)

    def test_nonselector_prose_in_a_model_file_is_not_shell_syntax(self):
        self.write("docs/operator.md", 'model: gpt-6.1-sol\nThe owner\'s model: its source is authoritative.\n')
        self.assertEqual(self.cli("check")[0], 0)

    def test_adoption_guide_prose_does_not_require_shell_quotation(self):
        self.write("adoption/bootstrap.md", "model: gpt-6.1-sol, the owner's current source choice.\n")
        self.assertEqual(self.cli("check")[0], 0)

    def test_pinned_available_models_allowlist_is_checked(self):
        self.write("client.json", '{"availableModels":["gpt-6-sol","gpt-6.1-sol"]}')
        code, stdout, _ = self.cli("check")
        self.assertEqual(code, 1)
        finding, = json.loads(stdout)["findings"]
        self.assertEqual(finding["model"], "gpt-6-sol")
        self.assertEqual(finding["json_pointer"], "/availableModels/0")

    def test_shell_environment_default_and_model_flag_are_checked(self):
        self.write("tools/launch.sh", 'MODEL="gpt-6-sol"\ncodex exec --model gpt-6-sol\n')
        self.assertEqual(self.check()["stale_count"], 2)

    def test_claude_context_suffix_and_short_alias_override(self):
        self.write(".claude/settings.json", '{"model":"opus","env":{"ANTHROPIC_DEFAULT_OPUS_MODEL":"claude-opus-5"}}')
        result = self.check()
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["findings"][0]["model"], "claude-opus-5")

    def test_unknown_effort_alias_does_not_pass_by_prefix(self):
        self.write("client.toml", 'model="gpt-6.1-sol-unobserved"\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_missing_and_aged_manifest_are_unknown_not_current(self):
        self.manifest.unlink()
        self.assertEqual(self.cli("check")[0], 2)
        old = catalog();old["catalog_kind"] = "live_observation";old["generated_at"] = "2026-10-07T20:31:55Z"
        self.write(mc.MANIFEST, json.dumps(old))
        self.assertEqual(self.cli("check")[0], 2)

    def test_failed_source_and_unapproved_alias_target_are_rejected(self):
        value = catalog();value["sources"].pop()
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["aliases"]["bad"] = "gpt-6-sol"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["aliases"]["gpt-6-sol"] = "gpt-6.1-sol"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)

    def test_invalid_manifest_shapes_emit_incomplete_notice_instead_of_traceback(self):
        values = [[], {**catalog(), "latest": []}, {**catalog(), "sources": [None, None, None]},
                  {**catalog(), "generated_at": 123}]
        for value in values:
            with self.subTest(value=value):
                self.write(mc.MANIFEST, json.dumps(value))
                self.assertEqual(self.cli("check")[0], 2)
                rc, stdout, stderr = self.cli("notice", event={"hook_event_name": "SessionStart"})
                self.assertEqual((rc, stderr), (0, ""))
                self.assertIn("check incomplete", json.loads(stdout)["hookSpecificOutput"]["additionalContext"])

    def test_redating_manifest_does_not_refresh_old_source_observations(self):
        value = catalog()
        value["catalog_kind"] = "live_observation"
        value["sources"][0]["observed_at"] = "2026-10-07T20:31:55Z"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)

    def test_native_routing_aliases_cannot_exempt_a_stale_model(self):
        for routing in ["gpt-reserve", ["gpt-6-sol"], ["gpt-reserve", "gpt-reserve"], [{}]]:
            with self.subTest(routing=routing):
                value = catalog();value["native_routing_aliases"] = routing
                self.write(mc.MANIFEST, json.dumps(value))
                self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["native_routing_aliases"] = ["gpt-reserve", "codex-auto-review"]
        self.write(mc.MANIFEST, json.dumps(value))
        self.write("client.toml", 'model = "gpt-reserve"\nreview_model = "codex-auto-review"\n')
        self.assertEqual(self.cli("check")[0], 0)
        value["native_routing_aliases"] = []
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 1)

    def test_session_start_notice_is_informational_and_never_starts_models(self):
        self.write("client.json", '{"model":"gpt-6-sol"}')
        rc, stdout, _ = self.cli("notice", event={"hook_event_name": "SessionStart"})
        self.assertEqual(rc, 0)
        notice = json.loads(stdout)["hookSpecificOutput"]
        self.assertEqual(notice["hookEventName"], "SessionStart")
        self.assertIn("1 stale active selectors", notice["additionalContext"])
        self.assertEqual(self.cli("notice", event={"hook_event_name": "UserPromptSubmit"})[1], "")

    def test_current_session_is_quiet_and_incomplete_session_gets_notice(self):
        self.assertEqual(self.cli("notice", event={"hook_event_name": "SessionStart"})[:2], (0, ""))
        self.manifest.unlink()
        rc, stdout, _ = self.cli("notice", event={"hook_event_name": "SessionStart"})
        self.assertEqual(rc, 0)
        self.assertIn("check incomplete", json.loads(stdout)["hookSpecificOutput"]["additionalContext"])


class GenerateLatestModelsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root = Path(temp.name)
        self.codex = self.root / "codex.json";self.gateway = self.root / "gateway.json";self.claude = self.root / "claude.json"
        values = catalog()["latest"]
        self.codex.write_text(json.dumps({"models": [{"slug": x} for x in values.values() if x.startswith("gpt-")] + [{"slug": "gpt-6-sol"}]}))
        self.gateway.write_text(json.dumps({"data": [{"id": "cx/gpt-6.1-sol-max", "created": 9999999999}, {"id": "cx/gpt-6-sol", "created": 9999999999}]}))
        self.claude.write_text(json.dumps({"data": [{"id": x, "lifecycle": "active"} for x in values.values() if x.startswith("claude-")], "has_more": False}))

    def generate(self):
        return mc.generate(self.codex, self.gateway, self.claude, NOW)

    def test_native_sources_generate_seven_families_and_observed_aliases(self):
        value = self.generate()
        self.assertEqual(value["latest"], catalog()["latest"])
        self.assertEqual(value["aliases"]["cx/gpt-6.1-sol-max"], "gpt-6.1-sol")
        self.assertNotIn("gpt-6-sol", value["aliases"])
        self.assertFalse(value["limits"]["codex_network_refresh_certified"])
        self.assertFalse(value["limits"]["gateway_created_is_release_date"])

    def test_source_capture_times_are_not_invented_from_the_bundle_label(self):
        codex = json.loads(self.codex.read_text())
        codex["fetched_at"] = "2026-10-08T03:00:00Z"
        self.codex.write_text(json.dumps(codex))
        gateway = json.loads(self.gateway.read_text())
        gateway["captured_at"] = "2026-10-09T04:00:00Z"
        self.gateway.write_text(json.dumps(gateway))
        value = self.generate()
        sources = {source["name"]: source for source in value["sources"]}
        self.assertEqual(sources["codex"]["observed_at"], "2026-10-08T03:00:00Z")
        self.assertEqual(sources["omniroute"]["observed_at"], "2026-10-09T04:00:00Z")
        self.assertIsNone(sources["claude"]["observed_at"])
        self.assertEqual(value["recorded_at"], NOW)

    def test_committed_source_metadata_follows_the_native_generator_contract(self):
        root = Path(mc.__file__).resolve().parents[1]
        committed = json.loads((root / mc.MANIFEST).read_text())
        self.assertEqual(committed["catalog_kind"], "versioned_snapshot")
        generated = {row["name"]: row for row in self.generate()["sources"]}
        for source in committed["sources"]:
            with self.subTest(source=source["name"]):
                reference = generated[source["name"]]
                self.assertEqual(set(source), set(reference))
                if source["observed_at"] is None:
                    self.assertEqual(source["timestamp_origin"], reference["timestamp_origin"])

    def test_new_native_claude_family_is_not_silently_dropped(self):
        data = json.loads(self.claude.read_text())
        data["data"].append({"id": "claude-mythos-5-1", "lifecycle": "active"})
        self.claude.write_text(json.dumps(data))
        self.assertEqual(self.generate()["latest"]["claude-mythos"], "claude-mythos-5-1")

    def test_only_observed_native_routing_aliases_enter_manifest(self):
        data = json.loads(self.codex.read_text())
        data["models"].extend([{"slug": "gpt-reserve"}, {"slug": "gpt-reserve"}, {"slug": "codex-auto-review"}, {"slug": "unknown-router"}])
        self.codex.write_text(json.dumps(data))
        self.assertEqual(self.generate()["native_routing_aliases"], ["codex-auto-review", "gpt-reserve"])

    def test_new_stable_generation_updates_latest_without_hardcoded_era(self):
        data = json.loads(self.codex.read_text());data["models"].append({"slug": "gpt-6.2-sol"});self.codex.write_text(json.dumps(data))
        self.assertEqual(self.generate()["latest"]["gpt-sol"], "gpt-6.2-sol")

    def test_gateway_alias_cannot_invent_new_authoritative_generation(self):
        self.gateway.write_text('{"data":[{"id":"cx/gpt-99-sol","created":9999999999}]}')
        self.assertEqual(self.generate()["latest"]["gpt-sol"], "gpt-6.1-sol")

    def test_retired_claude_generation_and_epoch_dates_do_not_override_active_line(self):
        data=json.loads(self.claude.read_text());data["data"].append({"id":"claude-opus-9-9","lifecycle":"retired","created_at":"1970-01-01T00:00:00Z"});self.claude.write_text(json.dumps(data))
        self.assertEqual(self.generate()["latest"]["claude-opus"], "claude-opus-5-5")

    def test_incomplete_pagination_or_missing_family_fails_generation(self):
        data=json.loads(self.claude.read_text());data["has_more"]=True;self.claude.write_text(json.dumps(data))
        with self.assertRaises(mc.CurrencyError):self.generate()
        data["has_more"]=False;data["data"].pop();self.claude.write_text(json.dumps(data))
        with self.assertRaises(mc.CurrencyError):self.generate()


class CurrencyCollectorIntegrationTests(unittest.TestCase):
    def test_every_currency_check_runs_active_selector_check_and_fails_stale(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture=Checkout(self)
        fixture.set(cd.ACTIVE_MODELS[0], {"schema_version":1,"status":"stale","stale_count":1,
                    "findings":[{"path":"fixture/client.toml","line":1,"model":"gpt-6-sol","expected":"gpt-6.1-sol"}],"errors":[]}, code=1)
        code, stdout, stderr=fixture.run()
        self.assertEqual((code,stderr),(1,""))
        self.assertIn("1 stale model selector",stdout)
        args=fixture.recorded(cd.ACTIVE_MODELS[0]);self.assertEqual(args[0],"check");self.assertIn("--json",args)
        self.assertEqual(json.loads(fixture.due_file.read_text())["due"][cd.MODEL_KEY],1)

    def test_incomplete_selector_check_does_not_remove_existing_due_notice(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture=Checkout(self);fixture.state.mkdir();fixture.due_file.write_text("retained-notice")
        fixture.set(cd.ACTIVE_MODELS[0], {"schema_version":1,"status":"unknown","stale_count":0,"findings":[],"errors":["catalog unavailable"]},code=2)
        code,stdout,stderr=fixture.run()
        self.assertEqual((code,stderr),(0,""))
        self.assertIn("model check incomplete", stdout)
        self.assertEqual(fixture.due_file.read_text(),"retained-notice")

    def test_unknown_models_do_not_suppress_known_counts_or_the_due_file(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture = Checkout(self)
        fixture.something_due()
        fixture.set(cd.ACTIVE_MODELS[0], {"schema_version": 1, "status": "unknown", "stale_count": 0,
                                        "findings": [], "errors": ["catalog observation expired"]}, code=2)
        code, _, stderr = fixture.run()
        self.assertEqual((code, stderr), (0, ""))
        document = json.loads(fixture.due_file.read_text())
        self.assertEqual(document["due"]["pins_behind"], 1)
        self.assertEqual(document["details"][-1]["active_models"], "unknown")

    def test_collector_survives_the_committed_catalogs_old_expiry(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture = Checkout(self)
        subprocess.run(["git", "init", "-q", str(fixture.root)], check=True, capture_output=True)
        shutil.copyfile(mc.__file__, fixture.root / cd.ACTIVE_MODELS[0])
        destination = fixture.root / mc.MANIFEST
        destination.parent.mkdir(parents=True)
        destination.write_bytes((Path(mc.__file__).resolve().parents[1] / mc.MANIFEST).read_bytes())
        home = fixture.root.parent / "empty-home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            code, stdout, stderr = fixture.run("--dry-run", "--json", "--now", "2026-10-11T00:00:00Z")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout)["details"][-1]["active_models"], "current")
        self.assertFalse(fixture.due_file.exists())


class CheckoutIsolationTests(unittest.TestCase):
    def test_the_checkout_fixture_is_a_nonexpiring_comparison_snapshot(self):
        value = catalog()
        self.assertEqual(value.get("catalog_kind"), "versioned_snapshot")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "models.json"
            path.write_text(json.dumps(value))
            mc.load_manifest(path, mc.utc("2026-10-11T00:00:00Z"))

    def test_checkout_smoke_test_rejects_unknown_model_coverage(self):
        from tests import test_currency_due as due_tests
        fixture = due_tests.Checkout(self)
        fixture.set(due_tests.cd.ACTIVE_MODELS[0], {"schema_version": 1, "status": "unknown",
                    "stale_count": 0, "findings": [], "errors": ["fixture coverage gap"]}, code=2)
        case = due_tests.ThisCheckoutTests("test_the_real_checks_run_dry_and_write_nothing")
        result = unittest.TestResult()
        with mock.patch.object(due_tests, "ROOT", fixture.root):
            case.run(result)
        self.assertFalse(result.wasSuccessful(), "checkout smoke test accepted unknown model coverage")
        self.assertTrue(any("unknown" in message for _, message in result.failures), result.failures + result.errors)

    def test_checkout_smoke_test_ignores_callers_stale_host_agent(self):
        from tests import test_currency_due as due_tests
        fixture = due_tests.Checkout(self)
        subprocess.run(["git", "init", "-q", str(fixture.root)], check=True, capture_output=True)
        shutil.copyfile(mc.__file__, fixture.root / due_tests.cd.ACTIVE_MODELS[0])
        manifest = fixture.root / mc.MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(catalog()))
        home = fixture.root.parent / "caller-home"
        agent = home / ".codex/agents/active.md"
        agent.parent.mkdir(parents=True)
        agent.write_text('model: gpt-6-sol\n')
        result = unittest.TestResult()
        case = due_tests.ThisCheckoutTests("test_the_real_checks_run_dry_and_write_nothing")
        with mock.patch.object(due_tests, "ROOT", fixture.root), mock.patch.dict(os.environ, {"HOME": str(home)}):
            case.run(result)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)


class StartupPolicyTests(unittest.TestCase):
    def test_full_model_audit_hook_and_user_patch_are_withdrawn(self):
        root = Path(mc.__file__).resolve().parents[1]
        for name in ("model-currency.hooks.template.json", "model-currency.user-hooks.patch.json"):
            with self.subTest(proposal=name):
                self.assertFalse((root / "adoption/templates" / name).exists())

    def test_session_start_uses_the_precomputed_notice_without_a_model_scan(self):
        root = Path(mc.__file__).resolve().parents[1]
        commands = []
        for path in (root / "adoption/templates").glob("*.json"):
            document = json.loads(path.read_text())
            for group in document.get("hooks", {}).get("SessionStart", []):
                commands.extend(handler.get("command", "") for handler in group.get("hooks", []))
        self.assertTrue(any("currency-due-notice.py" in command for command in commands))
        self.assertFalse(any("active_model_currency.py" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
