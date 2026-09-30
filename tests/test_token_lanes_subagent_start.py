"""Subprocess contract for the token-lanes carrier and its portable text.

Hook JSON reference: https://code.claude.com/docs/en/hooks#subagentstart
Blind-lane boundary: adoption/agents/claude/blind-judge.md.
Role blocks: the role-matched addendum in docs/decisions/2026-09-27-token-lanes-subagent-start.md.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "adoption/hooks/claude/token-lanes-subagent-start.py"
BLOCK = HOOK.with_name("token-lanes-block.md")
AGENTS = ROOT / "adoption/agents/claude"
HANDBOOK = ROOT / "docs/token-session-handbook.md"
BUDGET_BYTES = 4_100  # 4,088 measured bytes; verification-line addendum in docs/decisions/2026-09-27-token-lanes-subagent-start.md
# Exact agent_type -> sibling block; every other non-blind type receives BLOCK.
ROLE_BLOCKS = {
    "stack-researcher": "token-lanes-block.researcher.md",
    "stack-verifier": "token-lanes-block.verifier.md",
    "evidence-reviewer": "token-lanes-block.reviewer.md",
    "security-reviewer": "token-lanes-block.reviewer.md",
    "isolated-builder": "token-lanes-block.builder.md",
    "source-scout": "token-lanes-block.scout.md",
}
SILENT_ROLES = ("semantic-evidence-reviewer",)
BLOCK_FILES = (BLOCK,) + tuple(HOOK.with_name(name) for name in sorted(set(ROLE_BLOCKS.values())))
KEY_PHRASES = (  # the default block only; role blocks carry ROLE_KEY_PHRASES
    "ToolSearch", "ctx_batch_execute", "rtk", "find_referencing_symbols",
    "codebase-memory", "jcodemunch", "TOON", "headroom",
    "Show evidence before a success claim", "search-first",
)
# No block file names the withdrawn verification skill (Opus 5 guide L61, L81; verification-line addendum).
# A literal-name check: it does not detect other verification wording. Since 2026-09-28 no agent preloads
# the skill (builder evidence-sentence addendum); the builder block carries the evidence sentence instead.
WITHDRAWN_PHRASES = ("verification-before-completion",)
ROLE_KEY_PHRASES = {
    "token-lanes-block.researcher.md": (
        "ToolSearch", "ctx_fetch_and_index", "ctx_batch_execute", "rtk", "find_referencing_symbols",
        "jcodemunch", "menu(query?)", "qmd query", "memory_query", "TOON", "one lane per artifact",
        "discover skills with find-skills", "a claim needs its upstream citation"),
    "token-lanes-block.verifier.md": (
        "ToolSearch", "ctx_execute_file", "ctx_batch_execute", "rtk", "TOON", "one lane per artifact",
        "relay a claim only with its citation"),
    "token-lanes-block.reviewer.md": (
        "ToolSearch", "ctx_batch_execute", "find_referencing_symbols", "jcodemunch", "codebase_search",
        "memory_query", "TOON", "one lane per artifact", "relay a claim only with its citation"),
    "token-lanes-block.builder.md": (
        "ToolSearch", "ctx_batch_execute", "cwd = the owned worktree your brief names", "rtk",
        "find_referencing_symbols", "jcodemunch", "codebase_search", "memory_query", "TOON",
        "one lane per artifact", "Show evidence before a success claim",
        "a claim needs its upstream citation"),
    "token-lanes-block.scout.md": ("rtk", "rtk proxy <cmd>", "TOON", "one lane per artifact",
                                   "the upstream source your task names"),
}
CORRECTED_PHRASES = (
    # RTK 0.50.0, measured with `rtk hook check` and the `rtk hook claude` hook path.
    "&& chains and multi-line blocks are rewritten segment by segment",
    "a redirect to a file or a heredoc is never rewritten",
    "but not gh (gh pr view 1 | head -n 5 is not rewritten)",
    "uniform arrays of flat records (same keys in every item)",
    "this parameter is on trace_path, not search_graph",
    "treat edges below confidence 0.5 as unverified candidates",
)
# A tool the text names or needs, and the grant that admits it. An explicit `tools:` allowlist admits only
# the tools it lists (https://code.claude.com/docs/en/sub-agents), and ToolSearch returns only granted tools
# (evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md).
CTX = "mcp__plugin_context-mode_context-mode__"
NEEDS = (
    (r"\bToolSearch\b", "ToolSearch"),
    (r"Automatic RTK|\bBash\b", "Bash"),
    (r"\bctx_execute\b", CTX + "ctx_execute"),
    (r"\bctx_execute_file\b", CTX + "ctx_execute_file"),
    (r"\bctx_batch_execute\b", CTX + "ctx_batch_execute"),
    (r"\bctx_search\b", CTX + "ctx_search"),
    (r"\bctx_fetch_and_index\b", CTX + "ctx_fetch_and_index"),
    (r"\bfind_symbol\b", "mcp__serena__find_symbol"),
    (r"\bfind_referencing_symbols\b", "mcp__serena__find_referencing_symbols"),
    (r"\broute\(", "mcp__jcodemunch__route"),
    (r"\bmenu\(", "mcp__jcodemunch__menu"),
    (r"\border\(", "mcp__jcodemunch__order"),
    (r"\bcodebase_search\b", "mcp__socraticode__codebase_search"),
    (r"\bqmd query\b", "mcp__qmd__query"),
    (r"\bget a line window\b", "mcp__qmd__get"),
    (r"\bmemory_query\b", "mcp__ai-memory__memory_query"),
    (r"\bsearch_graph\b", "mcp__codebase-memory__search_graph"),
    (r"\btrace_path\b", "mcp__codebase-memory__trace_path"),
    (r"\bheadroom_compress\b", "mcp__headroom__headroom_compress"),
    (r"\bheadroom_retrieve\b", "mcp__headroom__headroom_retrieve"),
)
SKILLS = ("verification-before-completion", "search-first", "find-skills")


def fits_budget(raw: bytes) -> bool:
    return len(raw) <= BUDGET_BYTES


def frontmatter(path: Path) -> tuple[str, list[str] | None, list[str]]:
    """(name, tools or None when the line is absent, preloaded skills) from an agent file."""
    lines = path.read_text(encoding="utf-8").split("---\n", 2)[1].splitlines()
    name = next(line.split(":", 1)[1].strip() for line in lines if line.startswith("name:"))
    tools = next(([tool.strip() for tool in line.split(":", 1)[1].split(",")]
                  for line in lines if line.startswith("tools:")), None)
    skills, in_skills = [], False
    for line in lines:
        if line.startswith("skills:"):
            in_skills = True
        elif in_skills and line.startswith("  - "):
            skills.append(line[4:].strip())
        else:
            in_skills = False
    return name, tools, skills


def block_name(agent_type) -> str:
    return ROLE_BLOCKS.get(agent_type, BLOCK.name) if isinstance(agent_type, str) else BLOCK.name


def expected_context(agent_type) -> str:
    if isinstance(agent_type, str) and (agent_type.startswith("blind-") or agent_type in SILENT_ROLES):
        return ""
    return HOOK.with_name(block_name(agent_type)).read_text(encoding="utf-8")


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

    def injected(self, agent_type) -> str:
        stdout = self.run_hook(json.dumps({"agent_type": agent_type}))
        return json.loads(stdout)["hookSpecificOutput"]["additionalContext"] if stdout else ""

    def test_injected_bootstrap_names_granted_lane_tools_explicitly(self):
        # Claude MCP tool-search contract; the 2026-09-27 coordinator matrix
        # (Claude 2.1.283) in measured-gaps.md records grants, not inferred access.
        context = json.loads(self.run_hook('{"agent_type":"workflow-subagent"}'))[
            "hookSpecificOutput"]["additionalContext"]
        bootstrap = next(line for line in context.splitlines() if "ToolSearch" in line)
        self.assertIn("ONE ToolSearch call", bootstrap)
        self.assertIn("append task-needed ids to that same call", bootstrap)
        self.assertIn("ToolSearch returns only tools the agent is granted", bootstrap)
        self.assertIn("Select names exposed by the active client", bootstrap)
        for tool in ("mcp__jcodemunch__route", "mcp__jcodemunch__menu", "mcp__jcodemunch__order",
                     "mcp__socraticode__codebase_search", "mcp__qmd__query", "mcp__qmd__get",
                     "mcp__ai-memory__memory_query", "mcp__codebase-memory__search_graph",
                     "mcp__codebase-memory__trace_path", "mcp__headroom__headroom_compress",
                     "mcp__headroom__headroom_retrieve"):
            with self.subTest(tool=tool):
                self.assertIn(tool, bootstrap)

    def test_injected_web_rule_routes_fetches_and_quotes_to_source_text(self):
        # context-mode v1.0.169 src/server.ts L3423-3478; Claude WebFetch contract:
        # https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior
        for agent_type in ("workflow-subagent", "stack-researcher"):
            with self.subTest(agent_type=agent_type):
                context = self.injected(agent_type)
                bootstrap = next(line for line in context.splitlines() if "ToolSearch" in line)
                self.assertIn("mcp__plugin_context-mode_context-mode__ctx_fetch_and_index", bootstrap)
                web_rule = next((line for line in context.splitlines() if line.startswith("- Fetch pages")), "")
                for phrase in ("ctx_fetch_and_index", "batch requests with concurrency", "quote with ctx_search",
                               "Do not use WebFetch for evidence", "small fast model's reading of the page"):
                    self.assertIn(phrase, web_rule)

    def test_injected_search_rule_limits_specific_queries(self):
        # context-mode v1.0.169 src/search/ctx-search-schema.ts L88-94:
        # default limit 3; <=3 is local retrieval policy, not a byte-size cap.
        for agent_type in ("workflow-subagent", "stack-researcher", "stack-verifier",
                           "evidence-reviewer", "isolated-builder"):
            with self.subTest(agent_type=agent_type):
                self.assertIn("Use ctx_search with specific queries and limit <=3", self.injected(agent_type))

    def test_injected_execution_rule_sets_intent_and_worktree_cwd(self):
        # context-mode v1.0.169 src/executor.ts L290-312 (#788),
        # hooks/core/routing.mjs L939-941; src/server.ts L1822, L1979-1980.
        # isolated-builder.md: the builder starts in the coordinator's cwd, so its cwd is the owned worktree.
        for agent_type, cwd_phrase in (("workflow-subagent", "cwd = your working directory for every language"),
                                       ("stack-researcher", "cwd = your working directory for every language"),
                                       ("stack-verifier", "cwd = your working directory for every language"),
                                       ("evidence-reviewer", "cwd = your working directory for every language"),
                                       ("isolated-builder",
                                        "cwd = the owned worktree your brief names for every language")):
            with self.subTest(agent_type=agent_type):
                context = self.injected(agent_type)
                rule = next(line for line in context.splitlines() if line.startswith("- For output"))
                for phrase in ("output over ~5 KB", "ctx_execute with intent", "indexes output",
                               "returns only titles/previews", "ctx_search", "print derived answers",
                               "keep failures and original-output recovery", "ctx_execute cwd", cwd_phrase,
                               "without it, non-shell code runs at the server's project root",
                               "(the coordinator's checkout) and its writes persist",
                               "Rust runs in temp; use absolute project paths"):
                    self.assertIn(phrase, rule)
                self.assertNotIn("explicitly cd", context)
                self.assertNotIn("sandbox temp", context)
                self.assertNotIn("shell only", rule)
        self.assertNotIn("your working directory", self.injected("isolated-builder"))

    def test_injected_accounting_rule_preserves_verbatim_wrapper_returns(self):
        # tools/sota-convergence/landscape-sweep/sweep.js L83-87 at 5f3a7c21:
        # return complete stdout unmodified; routing and footers must both yield.
        for agent_type in ("workflow-subagent", *sorted(ROLE_BLOCKS)):
            with self.subTest(agent_type=agent_type):
                rule = next(line for line in self.injected(agent_type).splitlines()
                            if line.startswith("- Use one lane"))
                for phrase in ("Agents told to return output unmodified",
                               "skip output-routing and footer rules",
                               "otherwise list token tools used and why at the end of your return"):
                    self.assertIn(phrase, rule)

    def test_blind_and_silent_roles_receive_zero_injection(self):
        for role in ("blind-lane-reviewer", "blind-judge", "blind-adjudicator", "blind-anything",
                     *SILENT_ROLES):
            with self.subTest(agent_type=role):
                self.assertEqual(self.run_hook(json.dumps({"agent_type": role})), "")

    def test_only_documented_agent_type_controls_blind_gate(self):
        for payload in ({"agentType": "blind-judge"},
                        {"agent_type": "", "agentType": "blind-judge"},
                        {"agent_type": None, "agentType": "blind-judge"},
                        {"agent_type": "general-purpose", "agentType": "blind-judge"},
                        {"agentType": "semantic-evidence-reviewer"},
                        {"agentType": "stack-verifier"}):
            self.assertEqual(json.loads(self.run_hook(json.dumps(payload)))[
                "hookSpecificOutput"]["additionalContext"], BLOCK.read_text(encoding="utf-8"))

    def test_each_agent_type_receives_one_exact_context_object(self):
        payloads = [{"agent_type": role} for role in
                    ("general-purpose", "workflow-subagent", "teammate", "future-role", "Explore",
                     "landscape-sweep-worker", *ROLE_BLOCKS)]
        payloads += [{}] + [{"agent_type": value} for value in
                            ("", None, 7, False, [], ["blind-judge"], {"name": "blind-judge"},
                             ["stack-verifier"], {"stack-verifier": 1})]
        for payload in payloads:
            with self.subTest(payload=payload):
                name = block_name(payload.get("agent_type"))
                expected = expected_context(payload.get("agent_type"))
                if name != BLOCK.name:
                    self.assertNotEqual(expected, BLOCK.read_text(encoding="utf-8"))
                stdout = self.run_hook(json.dumps(payload))
                self.assertEqual(len(stdout.splitlines()), 1)
                self.assertLess(len(stdout), 10_000)
                output = json.loads(stdout)
                self.assertEqual(output, {"hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": expected,
                }})
                context = output["hookSpecificOutput"]["additionalContext"]
                self.assertTrue(context.startswith("TOKEN LANES"))
                for phrase in ROLE_KEY_PHRASES.get(name, KEY_PHRASES):
                    self.assertIn(phrase, context)

    def test_role_selection_matches_exact_names_only(self):
        # The hook never builds a path from agent_type; near-misses and plugin-scoped names get the default.
        for agent_type in ("stack-verifier ", "Stack-Verifier", "my-plugin:stack-verifier", "verifier",
                           "token-lanes-block.verifier.md", "../token-lanes-block.verifier",
                           "semantic-evidence-reviewer ", "my-plugin:semantic-evidence-reviewer"):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(self.injected(agent_type), BLOCK.read_text(encoding="utf-8"))

    def test_injected_text_names_only_tools_each_shipped_allowlist_grants(self):
        # For each shipped agent with an exact `tools:` allowlist, every mcp__ id the hook injects for its
        # agent_type is granted, and so is every tool a line names or needs (Bash for RTK, ToolSearch,
        # ctx_fetch_and_index); a named skill is invocable (Skill) or preloaded (`skills:`).
        checked = 0
        for path in sorted(AGENTS.glob("*.md")):
            name, tools, skills = frontmatter(path)
            if tools is None:  # no allowlist: the agent inherits every tool, as the default block assumes
                continue
            checked += 1
            context = self.injected(name)
            with self.subTest(agent_type=name):
                for tool in sorted(set(re.findall(r"mcp__[\w-]+", context))):
                    self.assertIn(tool, tools, f"{name} is told to load ungranted {tool}")
                for pattern, tool in NEEDS:
                    if re.search(pattern, context):
                        self.assertIn(tool, tools, f"{name} is told to use ungranted {tool} ({pattern})")
                for skill in SKILLS:
                    if skill in context:
                        self.assertTrue("Skill" in tools or skill in skills,
                                        f"{name} is told to follow {skill} without Skill or a preload")
        self.assertEqual(checked, 10)

    def test_malformed_stdin_is_silent(self):
        for stdin in ("not JSON", "", "{", "[]", "null", '"string"', "42"):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_hook(stdin), "")

    def test_missing_sibling_block_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            self.assertEqual(self.run_hook('{"agent_type":"general-purpose"}', script, Path(tmp)), "")
        # A missing role block is silent too: falling back to the default would name ungranted tools.
        for agent_type, name in ROLE_BLOCKS.items():
            with self.subTest(agent_type=agent_type), tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / HOOK.name
                shutil.copy2(HOOK, script)
                shutil.copy2(BLOCK, script.with_name(BLOCK.name))
                payload = json.dumps({"agent_type": agent_type})
                self.assertEqual(self.run_hook(payload, script, Path(tmp)), "")
                self.assertIn("TOKEN LANES", self.run_hook('{"agent_type":"teammate"}', script, Path(tmp)))

    def test_script_uses_its_own_sibling_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / HOOK.name
            shutil.copy2(HOOK, script)
            expected = "TOKEN LANES\nSibling fixture, including its final newline.\n"
            script.with_name(BLOCK.name).write_text(expected, encoding="utf-8")
            result = json.loads(self.run_hook("{}", script, Path(tmp)))
            self.assertEqual(result["hookSpecificOutput"]["additionalContext"], expected)
            for agent_type, name in ROLE_BLOCKS.items():
                with self.subTest(agent_type=agent_type):
                    fixture = f"TOKEN LANES\nFixture {name}.\n"
                    script.with_name(name).write_text(fixture, encoding="utf-8")
                    result = json.loads(self.run_hook(json.dumps({"agent_type": agent_type}), script, Path(tmp)))
                    self.assertEqual(result["hookSpecificOutput"]["additionalContext"], fixture)

    def test_empty_or_unreadable_sibling_block_is_silent(self):
        for agent_type, name in (("general-purpose", BLOCK.name), *ROLE_BLOCKS.items()):
            for content in (b"", b"\xff"):
                with self.subTest(agent_type=agent_type, content=content), tempfile.TemporaryDirectory() as tmp:
                    script = Path(tmp) / HOOK.name
                    shutil.copy2(HOOK, script)
                    for block in BLOCK_FILES:
                        shutil.copy2(block, script.with_name(block.name))
                    script.with_name(name).write_bytes(content)
                    self.assertEqual(self.run_hook(json.dumps({"agent_type": agent_type}), script, Path(tmp)), "")
            with self.subTest(agent_type=agent_type, content="directory"), tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / HOOK.name
                shutil.copy2(HOOK, script)
                script.with_name(name).mkdir()
                self.assertEqual(self.run_hook(json.dumps({"agent_type": agent_type}), script, Path(tmp)), "")


class TokenLanesTextTests(unittest.TestCase):
    def test_budget_counts_utf8_bytes_not_characters(self):
        # 3,880 characters but 4,120 UTF-8 bytes: a character count would accept it.
        text = "é" * 240 + "x" * 3_640
        self.assertEqual((len(text), len(text.encode("utf-8"))), (3_880, 4_120))
        self.assertFalse(fits_budget(text.encode("utf-8")))
        self.assertTrue(fits_budget(b"x" * BUDGET_BYTES))

    def test_block_fits_budget_and_matches_handbook(self):
        handbook = HANDBOOK.read_text(encoding="utf-8")
        header = BLOCK.read_text(encoding="utf-8").splitlines()[0]
        for path in BLOCK_FILES:
            raw = path.read_bytes()
            block = raw.decode("utf-8")
            with self.subTest(block=path.name):
                self.assertTrue(block.startswith("TOKEN LANES"))
                self.assertEqual(block.splitlines()[0], header)
                self.assertTrue(fits_budget(raw), f"{len(raw)} bytes")
                self.assertIn(f"`{path.name}`", handbook)
                for marker in ("/" + "home/", "/" + "tmp/claude-1000", "/" + "Users/", "/" + "mnt/c/"):
                    self.assertNotIn(marker, block)
            for phrase in ROLE_KEY_PHRASES.get(path.name, KEY_PHRASES):
                with self.subTest(block=path.name, phrase=phrase):
                    self.assertIn(phrase, block)
                    self.assertIn(phrase, handbook)
            for phrase in WITHDRAWN_PHRASES:
                with self.subTest(block=path.name, withdrawn=phrase):
                    self.assertNotIn(phrase, block)
            # Every guidance line is copied verbatim from the source of truth.
            for line in block.splitlines()[1:]:
                with self.subTest(block=path.name, line=line):
                    self.assertTrue(line.startswith("- "))
                    self.assertIn(line[2:], handbook)
        block = BLOCK.read_text(encoding="utf-8")
        for phrase in CORRECTED_PHRASES:
            with self.subTest(correction=phrase):
                self.assertIn(phrase, block)
                self.assertIn(phrase, handbook)

    def test_role_blocks_are_the_hook_map(self):
        hook = HOOK.read_text(encoding="utf-8")
        for agent_type, name in ROLE_BLOCKS.items():
            with self.subTest(agent_type=agent_type):
                self.assertIn(f'"{agent_type}": "{name}"', hook)
        for agent_type in SILENT_ROLES:
            self.assertIn(f'"{agent_type}"', hook)


if __name__ == "__main__":
    unittest.main()
