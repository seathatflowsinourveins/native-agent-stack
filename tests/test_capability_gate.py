"""Tests for tools/capability-gate: run_gate.py's verdict and Loki reconciliation, the JavaScript assertions, the M13
row generator and hook, the profile launcher, and the configs' provider references.

Evidence class (docs/acceptance-evidence-policy.md): synthetic. The promptfoo result rows below follow the shape that
promptfoo 0.123.1 wrote in the 2026-09-27 smoke (results.results[] with provider.label, success, failureReason,
response.raw holding the Codex item list as a JSON string, response.sessionId and gradingResult.componentResults), and
the Loki records follow the collector's field names; nothing here runs promptfoo, Codex or Loki. The JavaScript tests
run only when `node` is on PATH.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "capability-gate"
sys.path.insert(0, str(GATE))
import run_gate  # noqa: E402

NODE = shutil.which("node")
SESSION = "019a0000-0000-7000-8000-00000000000{}"


def mcp(server, tool, status="completed", error=None, text=""):
    return {"type": "mcp_tool_call", "server": server, "tool": tool, "status": status, "error": error,
            "result": {"content": [{"type": "text", "text": text}], "structured_content": None} if text else {}}


def row(label, success, items, session, reason=None, classes=None):
    components = [{"assertion": {"type": "javascript", "config": {"cls": cls}}, "reason": verdict, "pass": verdict == "own"}
                  for cls, verdict in (classes or {}).items()]
    return {"provider": {"id": "openai:codex-sdk", "label": label}, "success": success,
            "failureReason": 0 if success else (reason or run_gate.ASSERTION_FAILED),
            "response": {"raw": json.dumps({"items": items}), "sessionId": session},
            "gradingResult": {"componentResults": components}}


def results(*rows):
    return {"results": {"results": list(rows)}}


class VerdictTests(unittest.TestCase):
    def test_gate_passes_and_controls_fail_by_assertion(self):
        rows = run_gate.parse_rows(results(
            row("gate", True, [mcp("jcodemunch", "route", text="relative_path: str")], SESSION.format(1)),
            row("ctrl-prompt", False, [mcp("jcodemunch", "route", "failed", {"message": "requires approval"})],
                SESSION.format(2)),
            row("ctrl-disabled", False, [], SESSION.format(3)),
        ), "jcodemunch")
        self.assertEqual([r["calls"] for r in rows], [Counter({"jcodemunch": 1}), Counter({"jcodemunch": 1}), Counter()])
        result = run_gate.verdict(rows)
        self.assertTrue(result["gate_ok"])
        self.assertTrue(result["controls_ok"])

    def test_a_passing_control_or_a_provider_error_fails_the_gate(self):
        passing_control = run_gate.verdict(run_gate.parse_rows(results(
            row("gate", True, [], SESSION.format(1)), row("ctrl-prompt", True, [], SESSION.format(2))), "jcodemunch"))
        self.assertFalse(passing_control["controls_ok"])
        errored_control = run_gate.verdict(run_gate.parse_rows(results(
            row("gate", True, [], SESSION.format(1)), row("ctrl-prompt", False, [], SESSION.format(2), reason=2)),
            "jcodemunch"))
        self.assertFalse(errored_control["controls_ok"])
        self.assertEqual(errored_control["arms"]["ctrl-prompt"]["errored"], 1)
        failed_gate = run_gate.verdict(run_gate.parse_rows(results(
            row("gate", False, [], SESSION.format(1)), row("ctrl-prompt", False, [], SESSION.format(2))), "jcodemunch"))
        self.assertFalse(failed_gate["gate_ok"])

    def test_m13_labels_group_by_arm_and_classes_are_tallied(self):
        rows = run_gate.parse_rows(results(
            row("gate-a", True, [mcp("context-mode", "ctx_execute"), mcp("serena", "find_symbol")], SESSION.format(1),
                classes={"shell": "own", "serena": "own"}),
            row("gate-b", True, [mcp("context-mode", "ctx_search")], SESSION.format(2), classes={"shell": "own"}),
            row("ctrl-wrongroot-a", False, [mcp("context-mode", "ctx_execute")], SESSION.format(3),
                classes={"ctx_execute": "wrong_root_or_stale"}),
        ), "m13")
        self.assertEqual([r["arm"] for r in rows], ["gate", "gate", "ctrl-wrongroot"])
        self.assertEqual(rows[0]["calls"], Counter({"context-mode": 1, "serena": 1}))
        tallies = run_gate.class_tallies(rows)
        self.assertEqual(tallies["gate"]["shell"], Counter({"own": 2}))
        self.assertEqual(tallies["ctrl-wrongroot"]["ctx_execute"], Counter({"wrong_root_or_stale": 1}))

    def test_unparseable_raw_counts_no_calls(self):
        broken = row("gate", True, [], SESSION.format(1))
        broken["response"]["raw"] = "not json"
        self.assertEqual(run_gate.parse_rows(results(broken), "jcodemunch")[0]["calls"], Counter())


class ReconcileTests(unittest.TestCase):
    def records(self):
        return [
            {"event_name": "codex.tool_result", "conversation_id": SESSION.format(1), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": SESSION.format(1), "tool_namespace": "functions"},
            {"event_name": "codex.tool_decision", "conversation_id": SESSION.format(1), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": SESSION.format(9), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": SESSION.format(2), "tool_namespace": "mcp__ai_memory"},
        ]

    def test_counts_only_tool_results_of_known_sessions_and_servers(self):
        counts = run_gate.loki_counts(self.records(), {SESSION.format(1), SESSION.format(2)}, ("jcodemunch",))
        self.assertEqual(counts, {SESSION.format(1): Counter({"jcodemunch": 1})})
        dashed = run_gate.loki_counts(self.records(), {SESSION.format(2)}, ("ai-memory",))
        self.assertEqual(dashed, {SESSION.format(2): Counter({"ai-memory": 1})})

    def test_every_row_must_match_and_a_missing_session_is_a_mismatch(self):
        rows = [{"session": SESSION.format(1), "calls": Counter({"jcodemunch": 1})},
                {"session": SESSION.format(2), "calls": Counter()}]
        counts = {SESSION.format(1): Counter({"jcodemunch": 1})}
        self.assertEqual(run_gate.reconcile(rows, counts), (2, 2, 1))
        rows.append({"session": None, "calls": Counter()})
        self.assertEqual(run_gate.reconcile(rows, counts), (2, 3, 1))
        self.assertEqual(run_gate.reconcile(rows[:1], {SESSION.format(1): Counter({"jcodemunch": 2})})[0], 0)

    def test_summary_fits_the_receipt_excerpt_and_needs_rows(self):
        arms = {"gate": Counter(rows=6, passed=6), "ctrl-disabled": Counter(rows=2, failed=2),
                "ctrl-prompt": Counter(rows=2, failed=2)}
        line, ok = run_gate.summary("jcodemunch", {"arms": arms, "gate_ok": True, "controls_ok": True}, (10, 10, 8),
                                    "promptfoo 0.123.1, codex-cli 0.157.1, run 2026-09-27T20:00:00Z")
        self.assertTrue(ok)
        self.assertTrue(line.startswith("capability-gate jcodemunch: PASS | gate 6/6 pass; ctrl-disabled 2/2 fail"))
        self.assertLessEqual(len(line), 400)
        _, empty_ok = run_gate.summary("jcodemunch", {"arms": arms, "gate_ok": True, "controls_ok": True}, (0, 0, 0), "")
        self.assertFalse(empty_ok)
        _, mismatch_ok = run_gate.summary("jcodemunch", {"arms": arms, "gate_ok": True, "controls_ok": True},
                                          (9, 10, 8), "")
        self.assertFalse(mismatch_ok)


@unittest.skipUnless(NODE, "node is not on PATH")
class AssertionTests(unittest.TestCase):
    def call(self, function, output_context):
        script = (f"const a = require({json.dumps(str(GATE / 'assertions.js'))});"
                  f"const c = {json.dumps(output_context)};"
                  f"c.providerResponse = {{raw: JSON.stringify({{items: c.items}})}};"
                  f"console.log(JSON.stringify(a.{function}('', c)));")
        return json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True).stdout)

    def test_completed_result_needs_a_completed_error_free_matching_call(self):
        base = {"prompt": "find register_file", "vars": {"detail": "relative_path: str"}, "config": {"server": "jcodemunch"}}
        ok = self.call("completedResult", {**base, "items": [mcp("jcodemunch", "route", text="relative_path: str")]})
        self.assertTrue(ok["pass"])
        failed = self.call("completedResult", {**base, "items": [
            mcp("jcodemunch", "route", "failed", {"message": "requires approval"}, text="relative_path: str")]})
        self.assertFalse(failed["pass"])
        self.assertIn("route:failed requires approval", failed["reason"])
        other_server = self.call("completedResult", {**base, "items": [mcp("serena", "find_symbol", text="relative_path: str")]})
        self.assertFalse(other_server["pass"])
        in_prompt = self.call("completedResult", {**base, "prompt": "relative_path: str",
                                                  "items": [mcp("jcodemunch", "route", text="relative_path: str")]})
        self.assertFalse(in_prompt["pass"])

    def test_m13_class_verdicts(self):
        own, other = "CGTOK-a-r01-0123456789abcdef", "CGTOK-b-r01-fedcba9876543210"
        base = {"prompt": "read .cg/r01/...", "vars": {"token": own}, "config": {"cls": "ctx_execute"}}
        verdict = lambda items: self.call("m13Class", {**base, "items": items})["reason"]  # noqa: E731
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", text=own)]), "own")
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", text=own + "\n" + other)]), "wrong_root_or_stale")
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", text=other)]), "wrong_root_or_stale")
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", text="nothing")]), "miss")
        self.assertEqual(verdict([]), "miss")
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", "failed", {"message": "x"})]), "error_only")
        stale = "CGTOK-a-r00-0123456789abcdef"
        self.assertEqual(verdict([mcp("context-mode", "ctx_execute", text=stale)]), "wrong_root_or_stale")
        shell = self.call("m13Class", {**base, "config": {"cls": "shell"}, "items": [
            {"type": "command_execution", "command": "cat .cg/r01/sentinel-shell.txt", "aggregated_output": own + "\n",
             "status": "completed", "exit_code": 0}]})
        self.assertEqual(shell["reason"], "own")
        in_prompt = self.call("m13Class", {**base, "prompt": own, "items": [mcp("context-mode", "ctx_execute", text=own)]})
        self.assertFalse(in_prompt["pass"])

    def test_m13_rows_interleave_and_name_configured_providers(self):
        script = (f"require({json.dumps(str(GATE / 'm13_tests.js'))})().then(t => console.log(JSON.stringify(t)))")
        rows = json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True).stdout)
        self.assertEqual(len(rows), 52)
        self.assertEqual([r["vars"]["tree"] for r in rows[:4]], ["a", "b", "a", "b"])
        self.assertEqual(len({r["vars"]["rep"] for r in rows}), 26)
        labels = set(re.findall(r"^    label: (\S+)$", (GATE / "m13.yaml").read_text(), re.M))
        self.assertEqual({p for r in rows for p in r["providers"]}, labels)

    def test_m13_hook_writes_a_fresh_token_into_its_own_tree_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            trees = {tree: Path(tmp) / f"wt-{tree}" for tree in "ab"}
            for path in trees.values():
                (path / ".git").mkdir(parents=True)
            script = (f"require({json.dumps(str(GATE / 'm13_hooks.js'))}).beforeEach("
                      "{test: {vars: {tree: 'a', rep: 'r07'}}}).then(o => console.log(JSON.stringify(o)))")
            env = {**os.environ, "CAPABILITY_GATE_WT_A": str(trees["a"]), "CAPABILITY_GATE_WT_B": str(trees["b"])}
            out = json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True,
                                            env=env).stdout)
            token = out["test"]["vars"]["token"]
            self.assertRegex(token, r"^CGTOK-a-r07-[0-9a-f]{16}$")
            written = sorted(p.name for p in (trees["a"] / ".cg" / "r07").iterdir())
            self.assertEqual(written, ["cg_sentinel.py", "sentinel-ctx-execute.txt", "sentinel-ctx-file.txt",
                                       "sentinel-index.md", "sentinel-shell.txt"])
            self.assertTrue(all(token in p.read_text() for p in (trees["a"] / ".cg" / "r07").iterdir()))
            self.assertFalse((trees["b"] / ".cg").exists())
            bad = subprocess.run([NODE, "-e", script.replace("'r07'", "'x'")], capture_output=True, text=True, env=env)
            self.assertNotEqual(bad.returncode, 0)


class LauncherAndConfigTests(unittest.TestCase):
    def test_launcher_inserts_the_profile_after_exec_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "codex"
            fake.write_text('#!/bin/sh\nprintf "%s|" "$@"\n')
            fake.chmod(0o755)
            env = {**os.environ, "CAPABILITY_GATE_CODEX": str(fake), "CODEX_PROFILE": "stack-worker"}
            launcher = str(GATE / "codex-profile-exec")
            run = lambda *a, e=env: subprocess.run([launcher, *a], capture_output=True, text=True, env=e)  # noqa: E731
            self.assertEqual(run("exec", "--experimental-json", "--cd", "/x").stdout,
                             "exec|--profile|stack-worker|--experimental-json|--cd|/x|")
            self.assertEqual(run("--version").stdout, "--version|")
            missing = run("exec", e={k: v for k, v in env.items() if k != "CODEX_PROFILE"})
            self.assertNotEqual(missing.returncode, 0)

    def test_every_test_provider_reference_is_a_configured_label(self):
        for name in ("jcodemunch.yaml", "ai-memory.yaml"):
            text = (GATE / name).read_text()
            labels = set(re.findall(r"^    label: (\S+)$", text, re.M))
            used = {p for group in re.findall(r"^    providers: \[(.+)\]$", text, re.M) for p in group.split(", ")}
            self.assertEqual(used, labels, name)
            self.assertEqual(labels, {"gate", "ctrl-prompt", "ctrl-disabled"}, name)
            self.assertNotIn("trace-error-spans", text, name)
            for brief in re.findall(r"file://(briefs/\S+\.md)", text):
                self.assertTrue((GATE / brief).is_file(), brief)

    def test_fixture_details_are_absent_from_their_briefs(self):
        for name in ("jcodemunch.yaml", "ai-memory.yaml"):
            text = (GATE / name).read_text()
            for brief, detail in re.findall(r"instruction: file://(briefs/\S+\.md)\n      detail: '(.+)'", text):
                self.assertIsNone(re.search(detail.replace("''", "'"), (GATE / brief).read_text()), (name, brief))


if __name__ == "__main__":
    unittest.main()
