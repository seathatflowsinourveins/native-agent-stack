"""Subprocess contract for the main-session token-lanes carrier, its text and its Claude registration.

Hook JSON reference: https://code.claude.com/docs/en/hooks#sessionstart (read 2026-10-04): SessionStart input
carries `source` ("startup", "resume", "clear", "compact" or "fork") and, for `claude --agent <name>`, `agent_type`;
`hookSpecificOutput.additionalContext` reaches Claude before the first prompt. A matcher of letters and `|` only is a
list of exact strings ("Matcher patterns" on the same page).
Pattern and silent roles: adoption/hooks/claude/token-lanes-subagent-start.py and its test.
Decision: the 2026-10-04 main-session addendum of docs/decisions/2026-09-27-token-lanes-subagent-start.md.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402

HOOK = ROOT / "adoption/hooks/claude/token-lanes-session-start.py"
BLOCK = HOOK.with_name("token-lanes-block.main.md")
SUBAGENT_HOOK = HOOK.with_name("token-lanes-subagent-start.py")
SHA256SUMS = HOOK.with_name("SHA256SUMS")
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
HANDBOOK = ROOT / "docs/token-session-handbook.md"
SECTION = "Token lanes carried into the main session"
BUDGET_BYTES = 2_600
# Every documented SessionStart source; fork has its own value since v2.1.214 and re-runs SessionStart hooks.
SOURCES = ("startup", "resume", "clear", "compact", "fork")
MATCHER = "startup|resume|clear|compact|fork"
# Neutral paths and ids: scripts/validate.py rejects personal home paths and UUID-shaped session ids.
EVENT = {"session_id": "fixture-session", "transcript_path": "/srv/project/.transcript.jsonl",
         "cwd": "/srv/project", "hook_event_name": "SessionStart", "model": "claude-opus-5-5"}
# One phrase per rule the block must carry, in block order.
KEY_PHRASES = (
    "before the first tool call of each step", "context_guidance", "stop sign, not a hint", "ToolSearch",
    "8 KB", "wc -c", "ctx_execute_file", "ctx_execute with intent", "ctx_search", "qmd query", "line window",
    "5 KB", "ctx_batch_execute", "derived answer", "keep failures", "Bash", "Read, Grep and Glob bypass RTK",
    "subagent", "role block", "find_symbol", "find_referencing_symbols", "jcodemunch route (no execute)",
    "socraticode", "semble", "trace_path", "original source", "memory_query", "historical evidence only",
    "never the whole file", "one lane per artifact", "client's own counters", "if exposed",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected(block: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": block}}


class SessionStartHookTests(unittest.TestCase):
    def run_hook(self, stdin, script=HOOK, home=None):
        env = os.environ.copy()
        if home is not None:
            env["HOME"] = str(home)
        result = subprocess.run([sys.executable, str(script)], input=stdin,
                                capture_output=True, text=True, timeout=10,
                                cwd=ROOT, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def test_each_source_receives_one_exact_context_object(self):
        block = BLOCK.read_text(encoding="utf-8")
        for source in SOURCES:
            with self.subTest(source=source):
                stdout = self.run_hook(json.dumps({**EVENT, "source": source}))
                self.assertEqual(len(stdout.splitlines()), 1, stdout)
                self.assertEqual(json.loads(stdout), expected(block))

    def test_blind_and_silent_agent_sessions_receive_nothing(self):
        silent = load(SUBAGENT_HOOK).SILENT_ROLES
        for agent_type in ("blind-judge", "blind-lane-reviewer", "blind-anything", *sorted(silent)):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(self.run_hook(json.dumps({**EVENT, "source": "startup", "agent_type": agent_type})),
                                 "")
        block = BLOCK.read_text(encoding="utf-8")
        # Other agent sessions get the block; only the documented agent_type field controls the gate.
        for payload in ({"agent_type": "stack-verifier"}, {"agent_type": "general-purpose"},
                        {"agentType": "blind-judge"}, {"agent_type": None, "agentType": "blind-judge"}):
            with self.subTest(payload=payload):
                self.assertEqual(json.loads(self.run_hook(json.dumps({**EVENT, "source": "resume", **payload}))),
                                 expected(block))

    def test_silent_set_is_the_subagent_carriers(self):
        self.assertEqual(load(HOOK).SILENT_ROLES, load(SUBAGENT_HOOK).SILENT_ROLES)

    def test_malformed_stdin_is_silent(self):
        for stdin in ("not JSON", "", "{", "[]", "null", '"string"', "42"):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_hook(stdin), "")

    def test_missing_empty_or_unreadable_block_is_silent(self):
        payload = json.dumps({**EVENT, "source": "startup"})
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            self.assertEqual(self.run_hook(payload, script, Path(tmp)), "")
            for content in (b"", b"\xff"):
                with self.subTest(content=content):
                    script.with_name(BLOCK.name).write_bytes(content)
                    self.assertEqual(self.run_hook(payload, script, Path(tmp)), "")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            script.with_name(BLOCK.name).mkdir()
            self.assertEqual(self.run_hook(payload, script, Path(tmp)), "")

    def test_script_uses_its_own_sibling_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            fixture = "TOKEN LANES\nSibling fixture, including its final newline.\n"
            script.with_name(BLOCK.name).write_text(fixture, encoding="utf-8")
            self.assertEqual(json.loads(self.run_hook("{}", script, Path(tmp))), expected(fixture))


class MainBlockTextTests(unittest.TestCase):
    def test_block_fits_budget_ends_with_newline_and_names_its_source(self):
        raw = BLOCK.read_bytes()
        block = raw.decode("utf-8")
        self.assertLessEqual(len(raw), BUDGET_BYTES)
        self.assertTrue(raw.endswith(b"\n"))
        first, *rules = block.splitlines()
        self.assertTrue(first.startswith("TOKEN LANES"))
        self.assertIn(f'docs/token-session-handbook.md, "{SECTION}"', first)
        self.assertIn(f"\n### {SECTION}\n", HANDBOOK.read_text(encoding="utf-8"))
        self.assertTrue(rules)
        for rule in rules:
            with self.subTest(rule=rule[:40]):
                self.assertTrue(rule.startswith("- "))
        for marker in ("/" + "home/", "/" + "tmp/claude-1000", "/" + "Users/", "/" + "mnt/c/"):
            self.assertNotIn(marker, block)

    def test_block_states_each_rule(self):
        block = BLOCK.read_text(encoding="utf-8")
        for phrase in KEY_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, block)

    def test_block_leaves_out_withdrawn_lanes_ids_and_execute(self):
        block = BLOCK.read_text(encoding="utf-8")
        for absent in ("headroom", "hindsight"):
            self.assertNotIn(absent, block.lower())
        # Plain server names keep it host-neutral and outside the user-scope coverage union of mcp__ ids.
        self.assertIsNone(re.search(r"mcp__[A-Za-z0-9_-]+__", block))
        self.assertNotIn("execute?", block)

    def test_handbook_section_names_both_files(self):
        handbook = HANDBOOK.read_text(encoding="utf-8")
        section = handbook.split(f"\n### {SECTION}\n", 1)[1].split("\n#", 1)[0]
        for name in (BLOCK.name, HOOK.name):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", section)


class RegistrationTests(unittest.TestCase):
    def template(self, home: str) -> dict:
        return json.loads(string.Template(TEMPLATE.read_text(encoding="utf-8")).safe_substitute(HOME=home))

    def test_sha256sums_rows_match_and_the_installer_copies_both(self):
        rows = {name: digest for digest, name in
                (line.split() for line in SHA256SUMS.read_text(encoding="utf-8").splitlines())}
        for path in (BLOCK, HOOK):
            with self.subTest(name=path.name):
                self.assertEqual(rows[path.name], icp.sha256_of(path))
                self.assertEqual(icp.expected_sha256(path), icp.sha256_of(path))
                self.assertEqual(icp.HOOKS[path.name], path)

    def test_template_registers_one_group_that_merges_once(self):
        import apply_claude_settings as acs
        with tempfile.TemporaryDirectory() as tmp:
            template = self.template(tmp)
            wanted = f'python3 "{tmp}/.claude/hooks/{HOOK.name}" 2>/dev/null || true'
            groups = [group for group in template["hooks"]["SessionStart"]
                      if any(acs.command_key(hook["command"]) == acs.command_key(wanted) for hook in group["hooks"])]
            self.assertEqual(groups, [{"matcher": MATCHER, "hooks": [
                {"type": "command", "command": wanted, "timeout": 5}]}])
            # The exact-string path: letters and `|` only, each value a documented source.
            self.assertRegex(MATCHER, r"^[a-z|]+$")
            self.assertEqual(tuple(MATCHER.split("|")), SOURCES)
            for event, event_groups in template["hooks"].items():
                if event != "SessionStart":
                    with self.subTest(event=event):
                        self.assertNotIn(HOOK.name, json.dumps(event_groups))
            memory = next(hook for group in template["hooks"]["SessionStart"] for hook in group["hooks"]
                          if "--event session-start" in hook["command"])
            for initial in ({}, {"hooks": {"SessionStart": [{"matcher": "", "hooks": [memory]}]}}):
                merged = initial
                for application in (1, 2):
                    previous, merged = merged, acs.merge_settings(merged, template)
                    keys = [acs.command_key(hook["command"]) for group in merged["hooks"]["SessionStart"]
                            for hook in group["hooks"]]
                    with self.subTest(existing=bool(initial), application=application):
                        self.assertEqual(keys.count(acs.command_key(wanted)), 1)
                        self.assertEqual(keys.count(acs.command_key(memory["command"])), 1)
                        if application == 2:
                            self.assertEqual(merged, previous)

    def test_installed_hook_runs_from_the_template_command(self):
        # The rendered command through a POSIX shell, as Claude Code runs a command hook: absent, then installed.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (group,) = [group for group in self.template(tmp)["hooks"]["SessionStart"]
                        if HOOK.name in json.dumps(group)]
            env = {**os.environ, "HOME": tmp}

            def run():
                result = subprocess.run(["/bin/sh", "-c", group["hooks"][0]["command"]],
                                        input=json.dumps({**EVENT, "source": "clear"}), capture_output=True,
                                        text=True, timeout=10, env=env, cwd=tmp)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                return result.stdout

            self.assertEqual(run(), "")  # not installed yet: exits 0 and adds nothing
            with contextlib.redirect_stdout(io.StringIO()):
                icp.install_guards(home, dry_run=False, names=[HOOK.name, BLOCK.name])
            self.assertEqual(json.loads(run()), expected(BLOCK.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
