"""Tests for tools/capability-gate: run_gate.py's verdict, control outcomes, Loki paging and reconciliation, the
promptfoo environment, the JavaScript assertions, the M13 row generator and hook, the profile launcher, and the
configs' provider references and row counts.

Evidence class (docs/acceptance-evidence-policy.md): synthetic. The promptfoo result rows below follow the shape that
promptfoo 0.123.1 wrote in the 2026-09-27 smoke (results.results[] with provider.label, success, failureReason,
response.raw holding the Codex item list as a JSON string, response.sessionId and gradingResult.componentResults), the
Codex items follow that smoke's raw items (arguments, status, error.message), and the Loki records follow the
collector's field names; nothing here runs promptfoo, Codex or Loki. The JavaScript tests run only when `node` is on
PATH.
"""

from __future__ import annotations

import json
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "capability-gate"
sys.path.insert(0, str(GATE))
import run_gate  # noqa: E402

NODE = shutil.which("node")
OWN, OTHER, STALE = "CGTOK-a-r01-0123456789abcdef", "CGTOK-b-r01-fedcba9876543210", "CGTOK-a-r00-0123456789abcdef"
REFUSAL = {"message": run_gate.REFUSED}
CTX_OK = {"shell": "own", "serena": "own"}


def session(index):
    return f"019a0000-0000-7000-8000-{index:012d}"


def mcp(server, tool, status="completed", error=None, text="", arguments=None):
    return {"type": "mcp_tool_call", "server": server, "tool": tool, "status": status, "error": error,
            "arguments": arguments or {},
            "result": {"content": [{"type": "text", "text": text}], "structured_content": None} if text else {}}


def shell(command, output, exit_code=0):
    return {"type": "command_execution", "command": command, "aggregated_output": output, "exit_code": exit_code,
            "status": "completed" if exit_code == 0 else "failed"}


def ctx_exec(text, code="cat .cg/r01/sentinel-ctx-execute.txt", status="completed", error=None, **extra):
    return mcp("context-mode", "ctx_execute", status, error, text, {"language": "shell", "code": code, **extra})


def ctx_file(text, path=".cg/r01/sentinel-ctx-file.txt", code='echo "$FILE_CONTENT"', status="completed", error=None):
    return mcp("context-mode", "ctx_execute_file", status, error, text, {"path": path, "language": "shell", "code": code})


def ctx_index(source="cg-sentinel-r01", status="completed"):
    return mcp("context-mode", "ctx_index", status, None, "Indexed 1 section",
               {"path": ".cg/r01/sentinel-index.md", "source": source})


def ctx_search(text, status="completed", error=None):
    return mcp("context-mode", "ctx_search", status, error, text,
               {"queries": ["CG sentinel token"], "source": "cg-sentinel-r01"})


def find_symbol(text, relative_path=".cg/r01/cg_sentinel.py", status="completed", error=None):
    return mcp("serena", "find_symbol", status, error, text,
               {"name_path_pattern": "cg_sentinel", "relative_path": relative_path, "include_body": True})


def prescribed(text, status="completed", error=None):
    """Each M13 class's prescribed calls for r01, as the brief words them, every call returning `text`."""
    return {
        "shell": [shell("/bin/bash -lc 'cat .cg/r01/sentinel-shell.txt'", text + "\n", 0 if status == "completed" else 1)],
        "ctx_execute": [ctx_exec(text, status=status, error=error)],
        "ctx_execute_file": [ctx_file(text, status=status, error=error)],
        "ctx_index_search": [ctx_index(), ctx_search(text, status, error)],
        "serena": [find_symbol(text, status=status, error=error)],
    }


def row(label, success, items, sid, reason=None, classes=None):
    components = [{"assertion": {"type": "javascript", "config": {"cls": cls}}, "reason": verdict, "pass": verdict == "own"}
                  for cls, verdict in (classes or {}).items()]
    return {"provider": {"id": "openai:codex-sdk", "label": label}, "success": success,
            "failureReason": 0 if success else (reason or run_gate.ASSERTION_FAILED),
            "response": {"raw": json.dumps({"items": items}), "sessionId": sid},
            "gradingResult": {"componentResults": components}}


def results(*rows):
    return {"results": {"results": list(rows)}}


def jcodemunch_matrix():
    """The full jcodemunch matrix: 6 passing gate rows, 2 refused ctrl-prompt rows and 2 ctrl-disabled rows."""
    rows = [row("gate", True, [mcp("jcodemunch", "order", text="relative_path: str")], session(i)) for i in range(6)]
    rows += [row("ctrl-prompt", False, [mcp("jcodemunch", "order", "failed", REFUSAL)], session(6 + i)) for i in range(2)]
    rows += [row("ctrl-disabled", False, [], session(8 + i)) for i in range(2)]
    return rows


def m13_matrix():
    """The full M13 matrix: 40 gate rows, 6 ctrl-disabled rows and 6 ctrl-wrongroot rows with their predicted classes."""
    own_all = {cls: "own" for cls in ("shell", "ctx_execute", "ctx_execute_file", "ctx_index_search", "serena")}
    disabled = {**CTX_OK, "ctx_execute": "no_call", "ctx_execute_file": "no_call", "ctx_index_search": "no_call"}
    wrongroot = {**CTX_OK, "ctx_execute": "wrong_root_or_stale", "ctx_execute_file": "miss", "ctx_index_search": "error_only"}
    rows = [row(f"gate-{'ab'[i % 2]}", True, [], session(i), classes=own_all) for i in range(40)]
    rows += [row(f"ctrl-disabled-{'ab'[i % 2]}", False, [], session(40 + i), classes=disabled) for i in range(6)]
    rows += [row(f"ctrl-wrongroot-{'ab'[i % 2]}", False, [], session(46 + i), classes=wrongroot) for i in range(6)]
    return rows


class VerdictTests(unittest.TestCase):
    def test_complete_matrices_pass(self):
        for gate, rows in (("jcodemunch", jcodemunch_matrix()), ("m13", m13_matrix())):
            result = run_gate.verdict(run_gate.parse_rows(results(*rows), gate), gate)
            self.assertTrue(result["matrix_ok"] and result["sessions_ok"], gate)
            self.assertTrue(result["gate_ok"] and result["controls_ok"], gate)
        parsed = run_gate.parse_rows(results(*jcodemunch_matrix()), "jcodemunch")
        self.assertEqual(parsed[6]["calls"], Counter({"jcodemunch": 1}))
        self.assertEqual(parsed[6]["refused"], Counter({"jcodemunch": 1}))
        self.assertEqual(parsed[6]["completed"], Counter())
        self.assertEqual(parsed[0]["completed"], Counter({"jcodemunch": 1}))

    def test_missing_extra_or_errored_rows_fail(self):
        def check(rows):
            return run_gate.verdict(run_gate.parse_rows(results(*rows), "jcodemunch"), "jcodemunch")

        full = jcodemunch_matrix()
        self.assertFalse(check(full[1:])["matrix_ok"])  # a gate repetition missing
        self.assertFalse(check(full[:-2])["matrix_ok"])  # a control arm missing
        self.assertFalse(check(full[:-2])["controls_ok"])
        extra = check(full + [row("ctrl-other", False, [], session(20))])
        self.assertFalse(extra["matrix_ok"])
        seventh = check(full + [row("gate", True, [], session(21))])
        self.assertFalse(seventh["matrix_ok"] or seventh["gate_ok"])
        errored = full[:6] + [row("ctrl-prompt", False, [], session(6), reason=2)] + full[7:]
        self.assertFalse(check(errored)["controls_ok"])
        self.assertEqual(check(errored)["arms"]["ctrl-prompt"]["errored"], 1)
        passing = full[:6] + [row("ctrl-prompt", True, [], session(6))] + full[7:]
        self.assertFalse(check(passing)["controls_ok"])
        failed_gate = [row("gate", False, [], session(0))] + full[1:]
        self.assertFalse(check(failed_gate)["gate_ok"])

    def test_sessions_must_be_present_and_distinct(self):
        full = jcodemunch_matrix()
        repeated = full[:-1] + [row("ctrl-disabled", False, [], session(8))]
        result = run_gate.verdict(run_gate.parse_rows(results(*repeated), "jcodemunch"), "jcodemunch")
        self.assertTrue(result["matrix_ok"])
        self.assertFalse(result["sessions_ok"])
        self.assertEqual(result["distinct_sessions"], 9)
        missing = full[:-1] + [row("ctrl-disabled", False, [], None)]
        self.assertFalse(run_gate.verdict(run_gate.parse_rows(results(*missing), "jcodemunch"), "jcodemunch")["sessions_ok"])

    def test_approval_controls_fail_only_for_their_predicted_reason(self):
        def outcome(label, items):
            return run_gate.control_outcome(run_gate.parse_rows(results(row(label, False, items, session(1))),
                                                                "jcodemunch")[0], "jcodemunch")

        self.assertTrue(outcome("ctrl-prompt", [mcp("jcodemunch", "order", "failed", REFUSAL)]))
        self.assertFalse(outcome("ctrl-prompt", []))  # never attempted
        self.assertFalse(outcome("ctrl-prompt", [mcp("jcodemunch", "order", "failed", {"message": "server exited"})]))
        self.assertFalse(outcome("ctrl-prompt", [mcp("jcodemunch", "order", "failed", REFUSAL),
                                                 mcp("jcodemunch", "order", text="relative_path: str")]))
        self.assertTrue(outcome("ctrl-disabled", []))
        self.assertFalse(outcome("ctrl-disabled", [mcp("jcodemunch", "order", "failed", {"message": "x"})]))

    def test_m13_controls_need_their_classes_and_working_unaffected_classes(self):
        def outcome(label, classes):
            return run_gate.control_outcome(run_gate.parse_rows(results(row(label, False, [], session(1),
                                                                            classes=classes)), "m13")[0], "m13")

        ctx = ("ctx_execute", "ctx_execute_file", "ctx_index_search")
        # The review's case: context-mode reads its own tree under the wrong-root binding, and only the shell fails.
        self.assertFalse(outcome("ctrl-wrongroot-a", {"shell": "miss", "serena": "own", **{c: "own" for c in ctx}}))
        self.assertTrue(outcome("ctrl-wrongroot-a", {**CTX_OK, "ctx_execute": "wrong_root_or_stale",
                                                     "ctx_execute_file": "error_only", "ctx_index_search": "miss"}))
        self.assertFalse(outcome("ctrl-wrongroot-b", {**CTX_OK, **{c: "wrong_root_or_stale" for c in ctx},
                                                      "ctx_execute": "own"}))
        self.assertFalse(outcome("ctrl-wrongroot-b", {**CTX_OK, **{c: "miss" for c in ctx},
                                                      "ctx_execute_file": "not_prescribed"}))
        self.assertFalse(outcome("ctrl-wrongroot-b", {**CTX_OK, **{c: "no_call" for c in ctx}}))
        self.assertTrue(outcome("ctrl-disabled-a", {**CTX_OK, **{c: "no_call" for c in ctx}}))
        self.assertFalse(outcome("ctrl-disabled-a", {**CTX_OK, **{c: "no_call" for c in ctx}, "ctx_execute": "miss"}))
        self.assertFalse(outcome("ctrl-disabled-b", {"shell": "own", "serena": "error_only",
                                                     **{c: "no_call" for c in ctx}}))

    def test_m13_labels_group_by_arm_and_classes_are_tallied(self):
        rows = run_gate.parse_rows(results(
            row("gate-a", True, [mcp("context-mode", "ctx_execute"), mcp("serena", "find_symbol")], session(1),
                classes={"shell": "own", "serena": "own"}),
            row("gate-b", True, [mcp("context-mode", "ctx_search")], session(2), classes={"shell": "own"}),
            row("ctrl-wrongroot-a", False, [mcp("context-mode", "ctx_execute")], session(3),
                classes={"ctx_execute": "wrong_root_or_stale"}),
        ), "m13")
        self.assertEqual([r["arm"] for r in rows], ["gate", "gate", "ctrl-wrongroot"])
        self.assertEqual(rows[0]["calls"], Counter({"context-mode": 1, "serena": 1}))
        tallies = run_gate.class_tallies(rows)
        self.assertEqual(tallies["gate"]["shell"], Counter({"own": 2}))
        self.assertEqual(tallies["ctrl-wrongroot"]["ctx_execute"], Counter({"wrong_root_or_stale": 1}))

    def test_unparseable_raw_counts_no_calls(self):
        broken = row("gate", True, [], session(1))
        broken["response"]["raw"] = "not json"
        self.assertEqual(run_gate.parse_rows(results(broken), "jcodemunch")[0]["calls"], Counter())


def fake_loki(entries):
    """A query_range stand-in over (timestamp, line) entries in one stream: timestamps >= start and < end, oldest
    first, at most run_gate.LOKI_PAGE entries (Loki v3.7.8 docs/sources/reference/loki-http-api.md#L474-L475)."""
    meta = {"structuredMetadata": {"event_name": "codex.tool_result", "conversation_id": session(1),
                                   "tool_namespace": "mcp__jcodemunch"}}

    def page(start, end):
        values = [[str(ts), line, meta] for ts, line in sorted(entries) if start <= ts < end][:run_gate.LOKI_PAGE]
        return {"data": {"result": [{"stream": {"service_name": "codex_sdk_ts"}, "values": values}]}}
    return page


class ReconcileTests(unittest.TestCase):
    def records(self):
        return [
            {"event_name": "codex.tool_result", "conversation_id": session(1), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": session(1), "tool_namespace": "functions"},
            {"event_name": "codex.tool_decision", "conversation_id": session(1), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": session(9), "tool_namespace": "mcp__jcodemunch"},
            {"event_name": "codex.tool_result", "conversation_id": session(2), "tool_namespace": "mcp__ai_memory"},
        ]

    def test_counts_only_tool_results_of_known_sessions_and_servers(self):
        counts = run_gate.loki_counts(self.records(), {session(1), session(2)}, ("jcodemunch",))
        self.assertEqual(counts, {session(1): Counter({"jcodemunch": 1})})
        dashed = run_gate.loki_counts(self.records(), {session(2)}, ("ai-memory",))
        self.assertEqual(dashed, {session(2): Counter({"ai-memory": 1})})

    def test_every_row_must_match_and_a_missing_session_is_a_mismatch(self):
        rows = [{"session": session(1), "calls": Counter({"jcodemunch": 1})},
                {"session": session(2), "calls": Counter()}]
        counts = {session(1): Counter({"jcodemunch": 1})}
        self.assertEqual(run_gate.reconcile(rows, counts), (2, 2, 1))
        rows.append({"session": None, "calls": Counter()})
        self.assertEqual(run_gate.reconcile(rows, counts), (2, 3, 1))
        self.assertEqual(run_gate.reconcile(rows[:1], {session(1): Counter({"jcodemunch": 2})})[0], 0)

    def test_pages_resume_at_the_boundary_timestamp_without_skips_or_repeats(self):
        # A page boundary inside timestamp 2: resuming after it (the earlier `last + 1`) would lose (2, "c").
        entries = [(1, "a"), (1, "b"), (2, "a"), (2, "b"), (2, "c"), (3, "a")]
        with mock.patch.object(run_gate, "LOKI_PAGE", 4):
            records = run_gate.loki_records(0, 10, page=fake_loki(entries))
        self.assertEqual(len(records), 6)
        self.assertEqual(run_gate.loki_counts(records, {session(1)}, ("jcodemunch",)),
                         {session(1): Counter({"jcodemunch": 6})})

    def test_a_full_page_within_one_timestamp_fails_closed(self):
        entries = [(1, "a"), (2, "a"), (2, "b"), (2, "c"), (2, "d")]
        with mock.patch.object(run_gate, "LOKI_PAGE", 3), self.assertRaises(run_gate.LokiPageError):
            run_gate.loki_records(0, 10, page=fake_loki(entries))

    def test_the_query_filters_tool_results_of_the_sdk_service(self):
        self.assertEqual(run_gate.LOKI_QUERY, '{service_name="codex_sdk_ts"} | event_name="codex.tool_result"')

    def test_summary_fits_the_receipt_excerpt_and_needs_every_condition(self):
        versions = "promptfoo 0.123.1, codex-cli 0.157.1, run 2026-09-27T20:00:00Z"
        sha = "0123456789abcdef" * 4
        result = run_gate.verdict(run_gate.parse_rows(results(*jcodemunch_matrix()), "jcodemunch"), "jcodemunch")
        line, ok = run_gate.summary("jcodemunch", result, (10, 10, 8), versions, sha)
        self.assertTrue(ok)
        self.assertIn(f" | results {sha} | promptfoo 0.123.1", line)
        self.assertTrue(line.startswith("capability-gate jcodemunch: PASS | gate 6/6 pass; ctrl-disabled 2/2 fail as "
                                        "predicted; ctrl-prompt 2/2 fail as predicted | 10 rows as expected, 10 "
                                        "distinct sessions | loki 10/10 rows match"), line)
        self.assertFalse(run_gate.summary("jcodemunch", result, (0, 0, 0), "", sha)[1])
        self.assertFalse(run_gate.summary("jcodemunch", result, (9, 10, 8), "", sha)[1])
        unretained, unretained_ok = run_gate.summary("jcodemunch", result, (10, 10, 8), versions)
        self.assertFalse(unretained_ok)
        self.assertIn("| results NOT retained |", unretained)
        for key in ("matrix_ok", "sessions_ok", "gate_ok", "controls_ok"):
            self.assertFalse(run_gate.summary("jcodemunch", {**result, key: False}, (10, 10, 8), versions, sha)[1], key)
        m13_pass = run_gate.verdict(run_gate.parse_rows(results(*m13_matrix()), "m13"), "m13")
        m13_pass_line, m13_pass_ok = run_gate.summary("m13", m13_pass, (52, 52, 236), versions, sha)
        self.assertTrue(m13_pass_ok)
        m13 = run_gate.verdict(run_gate.parse_rows(results(*m13_matrix()[1:]), "m13"), "m13")
        m13_line, m13_ok = run_gate.summary("m13", m13, (51, 51, 230), versions, sha)
        self.assertFalse(m13_ok)
        self.assertIn("51 rows NOT the expected 52 by arm", m13_line)
        self.assertLessEqual(max(len(line), len(m13_pass_line), len(m13_line)), 400)


class EnvironmentTests(unittest.TestCase):
    def test_promptfoo_state_and_logs_stay_in_the_private_directory(self):
        private = Path("/private-dir")
        inherited = {"PROMPTFOO_LOG_DIR": "/elsewhere/logs", "PROMPTFOO_CACHE_PATH": "/elsewhere/cache",
                     "PROMPTFOO_CONFIG_DIR": "/elsewhere/config"}
        with mock.patch.dict(os.environ, inherited):
            env = run_gate.promptfoo_env(private, "/main", provider="native")
        self.assertEqual(env["PROMPTFOO_LOG_DIR"], "/private-dir/logs")
        self.assertEqual(env["PROMPTFOO_CONFIG_DIR"], "/private-dir/promptfoo")
        self.assertNotIn("PROMPTFOO_CACHE_PATH", env)
        self.assertEqual({k for k in env if k.startswith("PROMPTFOO_")},
                         {"PROMPTFOO_DISABLE_TELEMETRY", "PROMPTFOO_DISABLE_UPDATE", "PROMPTFOO_CONFIG_DIR",
                          "PROMPTFOO_LOG_DIR"})
        self.assertEqual(env["CAPABILITY_GATE_MAIN_CHECKOUT"], "/main")


class RetentionTests(unittest.TestCase):
    def test_results_are_copied_privately_hashed_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "results.json"
            source.write_bytes(b'{"results": {"results": []}}')
            root = Path(tmp) / "state" / "capability-gate"
            sha, relative = run_gate.retain(source, root, "m13-20260927T220000Z-1")
            target = root / relative
            self.assertEqual(relative, "m13-20260927T220000Z-1/results.json")
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(sha, __import__("hashlib").sha256(source.read_bytes()).hexdigest())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(FileExistsError):
                run_gate.retain(source, root, "m13-20260927T220000Z-1")

    def test_m13_rows_need_their_own_sentinel_in_the_results(self):
        def results(*variables):
            return {"results": {"results": [{"vars": v} for v in variables]}}
        own = {"tree": "a", "rep": "r07", "sentinel": "CGTOK-a-r07-0123456789abcdef"}
        self.assertEqual(run_gate.rows_without_sentinel(results(own), "m13"), 0)
        redacted = {**own, "sentinel": "[REDACTED]"}
        other_rep = {**own, "sentinel": "CGTOK-a-r08-0123456789abcdef"}
        old_name = {"tree": "a", "rep": "r07", "token": own["sentinel"]}
        self.assertEqual(run_gate.rows_without_sentinel(results(own, redacted, other_rep, old_name), "m13"), 3)
        self.assertEqual(run_gate.rows_without_sentinel(results(redacted), "jcodemunch"), 0)

    def test_the_retention_root_is_private_state_outside_the_checkout(self):
        with mock.patch.dict(os.environ, {"CAPABILITY_GATE_RETAIN": "/r", "XDG_STATE_HOME": "/s"}):
            self.assertEqual(run_gate.retain_root(), Path("/r"))
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "/s"}):
            os.environ.pop("CAPABILITY_GATE_RETAIN", None)
            self.assertEqual(run_gate.retain_root(), Path("/s/native-agent-stack/capability-gate"))


@unittest.skipUnless(NODE, "node is not on PATH")
class AssertionTests(unittest.TestCase):
    def batch(self, function, contexts):
        script = (f"const a = require({json.dumps(str(GATE / 'assertions.js'))});"
                  f"const cs = {json.dumps(contexts)};"
                  "console.log(JSON.stringify(cs.map((c) => {"
                  "c.providerResponse = {raw: JSON.stringify({items: c.items})};"
                  f"return a.{function}('', c); }})));")
        return json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True).stdout)

    def test_completed_result_needs_the_prescribed_call_completed_and_matching(self):
        call = {"action": "search_symbols", "args": {"repo": "native-agent-stack", "query": "register_file"}}
        sent = {"action": "search_symbols", "args": {**call["args"], "kind": "function", "max_results": 1}}
        base = {"prompt": "find register_file", "vars": {"detail": "relative_path: str", "call": json.dumps(call)},
                "config": {"server": "jcodemunch", "tool": "order"}}
        hit = "relative_path: str"
        ok, failed, other_server, in_prompt, other_tool, other_args, no_call, no_tool = self.batch("completedResult", [
            {**base, "items": [mcp("jcodemunch", "order", text=hit, arguments=sent)]},
            {**base, "items": [mcp("jcodemunch", "order", "failed", {"message": "requires approval"}, text=hit,
                                   arguments=sent)]},
            {**base, "items": [mcp("serena", "find_symbol", text=hit, arguments=sent)]},
            {**base, "prompt": hit, "items": [mcp("jcodemunch", "order", text=hit, arguments=sent)]},
            {**base, "items": [mcp("jcodemunch", "route", text=hit, arguments={"task": "find register_file"})]},
            {**base, "items": [mcp("jcodemunch", "order", text=hit,
                                   arguments={"action": "search_symbols", "args": {"repo": "native-agent-stack",
                                                                                    "query": "register"}})]},
            {**base, "vars": {"detail": hit}, "items": [mcp("jcodemunch", "order", text=hit, arguments=sent)]},
            {**base, "config": {"server": "jcodemunch"}, "items": [mcp("jcodemunch", "order", text=hit, arguments=sent)]},
        ])
        self.assertTrue(ok["pass"], ok["reason"])
        self.assertFalse(failed["pass"])
        self.assertIn("order:failed requires approval", failed["reason"])
        self.assertFalse(other_server["pass"])
        self.assertFalse(in_prompt["pass"])
        self.assertFalse(other_tool["pass"])
        self.assertFalse(other_args["pass"])
        self.assertTrue(no_call["reason"].startswith("misconfigured"))
        self.assertTrue(no_tool["reason"].startswith("misconfigured"))

    def test_the_jcodemunch_details_need_the_symbol_id_and_the_full_signature(self):
        # search_symbols results of jcodemunch-mcp 1.108.319 for the two fixtures, as the MCP server returned them on
        # 2026-09-27 (text content, abridged to the fields the details use).
        found = {
            "register_file": '{"result_count":1,"results":[{"id":"scripts/host_receipts.py::register_file#function",'
                             '"kind":"function","name":"register_file","file":"scripts/host_receipts.py","line":710,'
                             '"signature":"def register_file(root: Path, relative_path: str) -> None"}]}',
            "profile_servers_without_base":
                '{"result_count":1,"results":[{"id":"tools/sota-convergence/landscape-sweep/build_args.py::'
                'profile_servers_without_base#function","kind":"function","name":"profile_servers_without_base",'
                '"file":"tools/sota-convergence/landscape-sweep/build_args.py","line":195,"signature":'
                '"def profile_servers_without_base(profile_bytes: bytes, base_servers: list) -> list"}]}',
        }
        text = (GATE / "jcodemunch.yaml").read_text()
        details = re.findall(r"detail: '(.+)'\n      call: '(.+)'", text)
        self.assertEqual(len(details), 6)
        contexts = []
        for detail, call in details:
            query = json.loads(call)["args"]["query"]
            other = next(value for key, value in found.items() if key != query)
            for result in (found[query], other, found[query].replace(") -> None", ")").replace(") -> list", ")")):
                contexts.append({"prompt": "", "vars": {"detail": detail, "call": call},
                                 "config": {"server": "jcodemunch", "tool": "order"},
                                 "items": [mcp("jcodemunch", "order", text=result, arguments=json.loads(call))]})
        verdicts = self.batch("completedResult", contexts)
        self.assertEqual([v["pass"] for v in verdicts], [True, False, False] * 6)

    def test_m13_class_verdicts(self):
        good = prescribed(OWN)
        failed = {"message": "x"}
        cases = [(f"{cls} own", cls, items, "own") for cls, items in good.items()]
        cases += [
            ("no call", "ctx_execute", [], "no_call"),
            ("completed without the token", "ctx_execute", [ctx_exec("nothing")], "miss"),
            ("failed", "ctx_execute", [ctx_exec("", status="failed", error=failed)], "error_only"),
            ("a failed call carrying the own token is not own", "ctx_execute",
             [ctx_exec(OWN, status="failed", error=failed)], "error_only"),
            ("other tree", "ctx_execute", [ctx_exec(OTHER)], "wrong_root_or_stale"),
            ("own and other", "ctx_execute", [ctx_exec(OWN + "\n" + OTHER)], "wrong_root_or_stale"),
            ("stale repetition", "ctx_execute", [ctx_exec(STALE)], "wrong_root_or_stale"),
            ("a failed foreign call beside a completed own call", "ctx_execute",
             [ctx_exec(OTHER, status="failed", error=failed), ctx_exec(OWN)], "wrong_root_or_stale"),
            ("absolute path", "ctx_execute", [ctx_exec(OWN, "cat /w/wt-a/.cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("echoed token", "ctx_execute", [ctx_exec(OWN, f"echo {OWN}")], "not_prescribed"),
            ("directory change", "ctx_execute", [ctx_exec(OWN, "cd /w/wt-a && cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("explicit cwd", "ctx_execute", [ctx_exec(OWN, cwd="/w/wt-a")], "not_prescribed"),
            ("pushd", "ctx_execute", [ctx_exec(OWN, "pushd /w/wt-a; cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("os.chdir", "ctx_execute", [ctx_exec(OWN, "import os; os.chdir('/w/wt-a'); "
                                                       "print(open('.cg/r01/sentinel-ctx-execute.txt').read())")],
             "not_prescribed"),
            ("process.chdir", "ctx_execute", [ctx_exec(OWN, "process.chdir('/w/wt-a'); "
                                                            "require('fs').readFileSync('.cg/r01/sentinel-ctx-execute.txt')")],
             "not_prescribed"),
            ("git -C", "ctx_execute", [ctx_exec(OWN, "git -C /w/wt-a show HEAD:.cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("env --chdir", "ctx_execute", [ctx_exec(OWN, "env --chdir=/w/wt-a cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("Set-Location", "ctx_execute", [ctx_exec(OWN, "Set-Location /w/wt-a; cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("Push-Location", "ctx_execute", [ctx_exec(OWN, "Push-Location /w/wt-a; cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("attached -C", "shell", [shell("/bin/bash -lc 'env -C/w/wt-a cat .cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("grouped -C", "ctx_execute", [ctx_exec(OWN, "tar -xC/w/wt-a -f x.tar; cat .cg/r01/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("-C in an argument list", "ctx_execute",
             [ctx_exec(OWN, "subprocess.run(['git', '-C', '/w/wt-a', 'show', 'HEAD:.cg/r01/sentinel-ctx-execute.txt'])")],
             "not_prescribed"),
            ("git --work-tree", "ctx_execute",
             [ctx_exec(OWN, "git --work-tree=/w/wt-a show HEAD:.cg/r01/sentinel-ctx-execute.txt")], "not_prescribed"),
            ("sudo -D", "shell", [shell("/bin/bash -lc 'sudo -D /w/wt-a cat .cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("unshare -w", "shell", [shell("/bin/bash -lc 'unshare -w /w/wt-a cat .cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("systemd-run --working-directory", "shell",
             [shell("/bin/bash -lc 'systemd-run --working-directory=/w/wt-a cat .cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("directory change in the file snippet", "ctx_execute_file",
             [ctx_file(OWN, code='cd /w/wt-a && echo "$FILE_CONTENT"')], "not_prescribed"),
            ("shell pushd", "shell", [shell("/bin/bash -lc 'pushd /w/wt-a && cat .cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("another repetition's path", "ctx_execute", [ctx_exec(OWN, "cat .cg/r02/sentinel-ctx-execute.txt")],
             "not_prescribed"),
            ("token in the file snippet", "ctx_execute_file", [ctx_file(OWN, code=f"echo {OWN}")], "not_prescribed"),
            ("absolute file path", "ctx_execute_file", [ctx_file(OWN, path="/w/wt-a/.cg/r01/sentinel-ctx-file.txt")],
             "not_prescribed"),
            ("search without an index", "ctx_index_search", [ctx_search(OWN)], "not_prescribed"),
            ("search before the index", "ctx_index_search", [ctx_search(OWN), ctx_index()], "not_prescribed"),
            ("index under another source", "ctx_index_search", [ctx_index("cg-sentinel-r02"), ctx_search(OWN)],
             "not_prescribed"),
            ("failed index", "ctx_index_search", [ctx_index(status="failed"), ctx_search(OWN)], "error_only"),
            ("shell exit 1", "shell", [shell("/bin/bash -lc 'cat .cg/r01/sentinel-shell.txt'", OWN, 1)], "error_only"),
            ("shell absolute path", "shell", [shell("/bin/bash -lc 'cat /w/wt-a/.cg/r01/sentinel-shell.txt'", OWN)],
             "not_prescribed"),
            ("a foreign token from another shell call", "shell",
             good["shell"] + [shell("/bin/bash -lc 'ls'", OTHER)], "wrong_root_or_stale"),
            ("serena on another path", "serena", [find_symbol(OWN, ".cg/r02/cg_sentinel.py")], "not_prescribed"),
        ]
        base = {"prompt": "read .cg/r01/...", "vars": {"sentinel": OWN, "rep": "r01"}}
        verdicts = self.batch("m13Class", [{**base, "config": {"cls": cls}, "items": items} for _, cls, items, _ in cases])
        for (name, _, _, expected), got in zip(cases, verdicts):
            self.assertEqual(got["reason"], expected, name)
            self.assertEqual(got["pass"], expected == "own", name)
        in_prompt, no_rep = self.batch("m13Class", [
            {**base, "prompt": OWN, "config": {"cls": "ctx_execute"}, "items": good["ctx_execute"]},
            {**base, "vars": {"sentinel": OWN}, "config": {"cls": "ctx_execute"}, "items": good["ctx_execute"]},
        ])
        self.assertFalse(in_prompt["pass"])
        self.assertTrue(no_rep["reason"].startswith("misconfigured"))

    def test_m13_rows_interleave_match_the_expected_arms_and_name_configured_providers(self):
        script = (f"require({json.dumps(str(GATE / 'm13_tests.js'))})().then(t => console.log(JSON.stringify(t)))")
        rows = json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True).stdout)
        self.assertEqual(Counter(r["vars"]["arm"] for r in rows), Counter(run_gate.GATES["m13"]["rows"]))
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
            token = out["test"]["vars"]["sentinel"]
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

    def test_expected_rows_match_the_configs(self):
        for gate, name in (("jcodemunch", "jcodemunch.yaml"), ("ai-memory", "ai-memory.yaml")):
            tests = (GATE / name).read_text().split("\ntests:\n", 1)[1]
            counts = Counter()
            for block in re.split(r"^  - description: ", tests, flags=re.M)[1:]:
                provider = re.search(r"^    providers: \[(\S+)\]$", block, re.M).group(1)
                repeat = re.search(r"^      repeat: (\d+)$", block, re.M)
                counts[provider] += int(repeat.group(1)) if repeat else 1
            self.assertEqual(counts, Counter(run_gate.GATES[gate]["rows"]), name)

    def test_each_row_prescribes_its_briefs_call_and_the_assertion_names_the_tool(self):
        for name, tool in (("jcodemunch.yaml", "order"), ("ai-memory.yaml", "memory_query")):
            text = (GATE / name).read_text()
            self.assertIn(f"        tool: {tool}\n", text, name)
            rows = re.findall(r"instruction: file://(briefs/\S+\.md)\n      detail: '.+'\n      call: '(.+)'", text)
            self.assertEqual(len(rows), 6, name)  # two fixtures, each in the gate and both controls
            for brief, call in rows:
                brief_text = (GATE / brief).read_text()
                self.assertIn(f"Call {name.split('.')[0]} {tool} once with ", brief_text, brief)
                sent = json.loads(re.search(r" once with (\{.*\})\. Make no other", brief_text).group(1))
                expected = json.loads(call)
                self.assertTrue(expected and _subset(expected, sent), (brief, call))

    def test_fixture_details_are_absent_from_their_briefs(self):
        for name in ("jcodemunch.yaml", "ai-memory.yaml"):
            text = (GATE / name).read_text()
            for brief, detail in re.findall(r"instruction: file://(briefs/\S+\.md)\n      detail: '(.+)'", text):
                self.assertIsNone(re.search(detail.replace("''", "'"), (GATE / brief).read_text()), (name, brief))


def _subset(expected, actual):
    """assertions.js subset() in Python: every key of expected is in actual with an equal value."""
    if not isinstance(expected, dict):
        return expected == actual
    return isinstance(actual, dict) and all(k in actual and _subset(v, actual[k]) for k, v in expected.items())


class ExplicitProviderTests(unittest.TestCase):
    def test_gate_refuses_absent_or_invalid_provider_before_process_or_state(self):
        for flags in [[], ["--provider", ""], ["--provider", "unsupported"], ["--provider", "omniroute"],
                      ["--provider", "omniroute", "--omniroute-base-url", "https://example.org/v1"]]:
            with self.subTest(flags=flags), mock.patch.object(run_gate, "run") as process, \
                 mock.patch.object(run_gate.tempfile, "mkdtemp") as state, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    run_gate.main(["ai-memory", *flags])
                self.assertEqual(raised.exception.code, 2)
                process.assert_not_called()
                state.assert_not_called()

    def test_gateway_env_skips_credential_by_name_before_value_lookup(self):
        class ValueGuard(dict):
            def __getitem__(self, key):
                if key == "OMNIROUTE_API_KEY":
                    raise AssertionError("credential value must not be retrieved")
                return super().__getitem__(key)
        inherited = ValueGuard({"PATH": os.defpath, "OMNIROUTE_API_KEY": "synthetic-not-read",
                                "NAS_CODEX_PROVIDER": "unvalidated", "NAS_CODEX_BASE_URL": "unvalidated",
                                "PROMPTFOO_LOG_DIR": "/elsewhere"})
        with mock.patch.object(run_gate.os, "environ", inherited):
            env = run_gate.promptfoo_env(Path("/private"), "/main", provider="omniroute", base_url="http://127.0.0.1:21128/v1")
        self.assertEqual(env["OMNIROUTE_API_KEY"], "local")
        self.assertEqual(env["NAS_CODEX_PROVIDER"], "omniroute")
        self.assertEqual(env["NAS_CODEX_BASE_URL"], "http://127.0.0.1:21128/v1")
        self.assertEqual(env["PROMPTFOO_LOG_DIR"], "/private/logs")
        with mock.patch.dict(os.environ, {"NAS_CODEX_BASE_URL": "unvalidated"}, clear=True):
            native = run_gate.promptfoo_env(Path("/private"), "/main", provider="native")
        self.assertEqual(native["NAS_CODEX_PROVIDER"], "native")
        self.assertNotIn("NAS_CODEX_BASE_URL", native)

    def test_actual_wrapper_forwards_explicit_provider_fast_profile_and_sdk_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "codex"
            fake.write_text(f"#!{sys.executable}\nimport json,os,sys\nprint(json.dumps({{'argv':sys.argv[1:], 'public_key':os.environ.get('OMNIROUTE_API_KEY'), 'stdin':sys.stdin.read()}}))\n")
            fake.chmod(0o755)
            for provider in ["native", "omniroute"]:
                env = {"PATH": os.environ["PATH"], "CAPABILITY_GATE_CODEX": str(fake), "CODEX_PROFILE": "stack-worker",
                       "NAS_CODEX_PROVIDER": provider, "PYTHONDONTWRITEBYTECODE": "1"}
                if provider == "omniroute":
                    env["NAS_CODEX_BASE_URL"] = "http://127.0.0.1:21128/v1"
                sdk_args = ["--experimental-json", "--cd", "/synthetic-worktree", "-c", 'mcp_servers.synthetic.enabled=false', "literal prompt"]
                result = subprocess.run([str(GATE / "codex-profile-exec"), "exec", *sdk_args], env=env,
                                        input="synthetic SDK prompt\nsecond line\n", text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads(result.stdout)
                self.assertEqual(record["stdin"], "synthetic SDK prompt\nsecond line\n")
                argv = record["argv"]
                self.assertEqual(argv[:3], ["exec", "--profile", "stack-worker"])
                self.assertEqual(argv[-len(sdk_args):], sdk_args)
                self.assertIn('service_tier="fast"', argv)
                self.assertIn('model_provider="openai"' if provider == "native" else 'model_provider="omniroute"', argv)
                if provider == "omniroute":
                    self.assertEqual(record["public_key"], "local")

    def test_invalid_wrapper_metadata_fails_closed_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "executed"
            fake = Path(tmp) / "codex"
            fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
            fake.chmod(0o755)
            base = {"PATH": os.environ["PATH"], "CAPABILITY_GATE_CODEX": str(fake), "CODEX_PROFILE": "stack-worker",
                    "PYTHONDONTWRITEBYTECODE": "1"}
            for metadata in [{"NAS_CODEX_PROVIDER": ""}, {"NAS_CODEX_PROVIDER": "unsupported"},
                             {"NAS_CODEX_PROVIDER": "omniroute"}, {"NAS_CODEX_BASE_URL": "http://127.0.0.1:21128/v1"},
                             {"NAS_CODEX_PROVIDER": "omniroute", "NAS_CODEX_BASE_URL": "http://example.org/v1"}]:
                result = subprocess.run([str(GATE / "codex-profile-exec"), "exec", "literal prompt"],
                                        env={**base, **metadata}, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
