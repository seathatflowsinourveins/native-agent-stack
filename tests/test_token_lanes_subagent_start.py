"""Subprocess contract for the token-lanes carrier and its portable text.

Hook JSON reference: https://code.claude.com/docs/en/hooks#subagentstart
Blind-lane boundary: adoption/agents/claude/blind-judge.md.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "adoption/hooks/claude/token-lanes-subagent-start.py"
BLOCK = HOOK.with_name("token-lanes-block.md")
HANDBOOK = ROOT / "docs/token-session-handbook.md"
BUDGET_BYTES = 3_500  # the carrier's local budget, in UTF-8 bytes (docs/decisions/2026-09-27-token-lanes-subagent-start.md)
KEY_PHRASES = (
    "ToolSearch", "ctx_batch_execute", "rtk", "find_referencing_symbols",
    "codebase-memory", "jcodemunch", "TOON", "headroom",
    "verification-before-completion", "search-first",
)
CORRECTED_PHRASES = (
    # RTK 0.50.0, measured with `rtk hook check` and the `rtk hook claude` hook path.
    "&& chains and multi-line blocks are rewritten segment by segment",
    "a redirect to a file or a heredoc is never rewritten",
    "but not gh (gh pr view 1 | head -n 5 is not rewritten)",
    "uniform arrays of flat records (same keys in every item)",
    "this parameter is on trace_path, not search_graph",
    "treat edges below confidence 0.5 as unverified candidates",
)


def fits_budget(raw: bytes) -> bool:
    return len(raw) <= BUDGET_BYTES


class TokenLanesHookTests(unittest.TestCase):
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

    def test_injected_web_rule_routes_fetches_and_quotes_to_source_text(self):
        # context-mode v1.0.169 src/server.ts L3423-3478; Claude WebFetch contract:
        # https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior
        context = json.loads(self.run_hook('{"agent_type":"workflow-subagent"}'))[
            "hookSpecificOutput"]["additionalContext"]
        bootstrap = next(line for line in context.splitlines() if "ToolSearch" in line)
        self.assertIn("mcp__plugin_context-mode_context-mode__ctx_fetch_and_index", bootstrap)
        web_rule = next((line for line in context.splitlines() if line.startswith("- Fetch pages")), "")
        for phrase in ("ctx_fetch_and_index", "batch requests with concurrency", "quote with ctx_search",
                       "Do not use WebFetch for evidence", "small fast model's reading of the page"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, web_rule)

    def test_injected_execution_rule_sets_intent_and_shell_cwd(self):
        # context-mode v1.0.169 src/server.ts L1675-1690, L1728-1738.
        context = json.loads(self.run_hook('{"agent_type":"workflow-subagent"}'))[
            "hookSpecificOutput"]["additionalContext"]
        rule = next(line for line in context.splitlines() if line.startswith("- For output"))
        for phrase in ("output over ~5 KB", "ctx_execute with intent", "indexes output",
                       "returns only titles/previews", "ctx_search", "print derived answers",
                       "keep failures and original-output recovery", "ctx_execute cwd",
                       "shell only", "other languages run in sandbox temp"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)
        self.assertNotIn("explicitly cd", context)
        self.assertNotIn("server is bound to the main checkout", context)

    def test_injected_accounting_rule_preserves_verbatim_wrapper_returns(self):
        # measured-gaps.md: smoke-2 wrapper copy check 2/2; summaries/footers change that contract.
        context = json.loads(self.run_hook('{"agent_type":"workflow-subagent"}'))[
            "hookSpecificOutput"]["additionalContext"]
        rule = next(line for line in context.splitlines() if line.startswith("- Use one lane"))
        self.assertIn("Preserve verbatim wrapper returns", rule)

    def test_blind_roles_receive_zero_injection(self):
        for role in ("blind-lane-reviewer", "blind-judge", "blind-adjudicator", "blind-anything"):
            with self.subTest(agent_type=role):
                self.assertEqual(self.run_hook(json.dumps({"agent_type": role})), "")

    def test_only_documented_agent_type_controls_blind_gate(self):
        for payload in ({"agentType": "blind-judge"},
                        {"agent_type": "", "agentType": "blind-judge"},
                        {"agent_type": None, "agentType": "blind-judge"},
                        {"agent_type": "general-purpose", "agentType": "blind-judge"}):
            self.assertIn("TOKEN LANES", json.loads(self.run_hook(json.dumps(payload)))[
                "hookSpecificOutput"]["additionalContext"])

    def test_non_blind_roles_receive_one_exact_context_object(self):
        payloads = [{"agent_type": role} for role in
                    ("general-purpose", "source-scout", "workflow-subagent", "future-role")]
        payloads += [{}] + [{"agent_type": value} for value in
                            ("", None, 7, False, [], ["blind-judge"], {"name": "blind-judge"})]
        for payload in payloads:
            with self.subTest(payload=payload):
                stdout = self.run_hook(json.dumps(payload))
                self.assertEqual(len(stdout.splitlines()), 1)
                self.assertLess(len(stdout), 10_000)
                output = json.loads(stdout)
                self.assertEqual(output, {"hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": BLOCK.read_text(encoding="utf-8"),
                }})
                context = output["hookSpecificOutput"]["additionalContext"]
                self.assertTrue(context.startswith("TOKEN LANES"))
                for phrase in KEY_PHRASES:
                    self.assertIn(phrase, context)

    def test_malformed_stdin_is_silent(self):
        for stdin in ("not JSON", "", "{", "[]", "null", '"string"', "42"):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_hook(stdin), "")

    def test_missing_sibling_block_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            self.assertEqual(self.run_hook('{"agent_type":"general-purpose"}', script, Path(tmp)), "")

    def test_script_uses_its_own_sibling_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            expected = "TOKEN LANES\nSibling fixture, including its final newline.\n"
            script.with_name(BLOCK.name).write_text(expected, encoding="utf-8")
            result = json.loads(self.run_hook("{}", script, Path(tmp)))
            self.assertEqual(result["hookSpecificOutput"]["additionalContext"], expected)

    def test_empty_or_unreadable_sibling_block_is_silent(self):
        for content in (b"", b"\xff"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / HOOK.name
                shutil.copy2(HOOK, script)
                script.with_name(BLOCK.name).write_bytes(content)
                self.assertEqual(self.run_hook("{}", script, Path(tmp)), "")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            script.with_name(BLOCK.name).mkdir()
            self.assertEqual(self.run_hook("{}", script, Path(tmp)), "")


class TokenLanesTextTests(unittest.TestCase):
    def test_budget_counts_utf8_bytes_not_characters(self):
        # 3,280 characters but 3,520 UTF-8 bytes: a character count would accept it.
        text = "é" * 240 + "x" * 3_040
        self.assertEqual((len(text), len(text.encode("utf-8"))), (3_280, 3_520))
        self.assertFalse(fits_budget(text.encode("utf-8")))
        self.assertTrue(fits_budget(b"x" * BUDGET_BYTES))

    def test_block_fits_budget_and_matches_handbook(self):
        raw = BLOCK.read_bytes()
        block = raw.decode("utf-8")
        handbook = HANDBOOK.read_text(encoding="utf-8")
        self.assertTrue(block.startswith("TOKEN LANES"))
        self.assertTrue(fits_budget(raw), f"{len(raw)} bytes")
        for marker in ("/" + "home/", "/" + "tmp/claude-1000", "/" + "Users/", "/" + "mnt/c/"):
            self.assertNotIn(marker, block)
        for phrase in KEY_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, block)
                self.assertIn(phrase, handbook)
        for phrase in CORRECTED_PHRASES:
            with self.subTest(correction=phrase):
                self.assertIn(phrase, block)
                self.assertIn(phrase, handbook)
        # Every guidance line is copied verbatim from the source of truth.
        for line in block.splitlines():
            if line.startswith("- "):
                with self.subTest(line=line):
                    self.assertIn(line[2:], handbook)


if __name__ == "__main__":
    unittest.main()
