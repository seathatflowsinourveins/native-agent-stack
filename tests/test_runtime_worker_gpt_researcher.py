"""Offline recipe contracts; not upstream or live-provider acceptance.

Oracle: user runtime-worker brief (2026-09-27), and GPT Researcher v3.7.0
config/variables/default.py, utils/llm.py, mcp/client.py. No framework install.
"""

import json
import copy
import hashlib
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/gpt-researcher"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeWorkerGPTResearcherTests(unittest.TestCase):
    def test_recipe_contract_and_empty_result(self):
        for name in ("README.md", "install.sh", "run-e2e.sh", "config.template.json",
                     "mcp-policy.json", "pins.json", "e2e/check.py", "e2e/task.json",
                     "e2e/receipt.py", "requirements.lock"):
            self.assertTrue((RECIPE / name).is_file(), name)
        cfg = json.loads((RECIPE / "config.template.json").read_text())
        self.assertEqual(cfg["LLM_KWARGS"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(cfg["LLM_KWARGS"]["api_key"], "local-loopback")
        self.assertIsNone(cfg["LLM_KWARGS"]["temperature"])
        self.assertTrue(cfg["LLM_KWARGS"]["use_responses_api"])
        self.assertEqual(cfg["CONTEXT_FILTER"], "keyword")
        self.assertEqual(cfg["RETRIEVER"], "duckduckgo")
        for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
            self.assertEqual(cfg[role], "openai:${GPTR_MODEL}")
        runner = (RECIPE / "run-e2e.sh").read_text()
        self.assertIn("${GPTR_MODEL:-cx/gpt-6-astra-max}", runner)
        self.assertIn("set -euo pipefail", runner)
        installer = (RECIPE / "install.sh").read_text()
        self.assertIn("set -euo pipefail", installer)
        self.assertIn("--require-hashes", installer)
        policy = json.loads((RECIPE / "mcp-policy.json").read_text())
        self.assertEqual(policy["servers"]["context-mode"]["disabled_tools"],
                         ["ctx_upgrade", "ctx_purge"])
        self.assertEqual(policy["servers"]["ai-memory"]["enabled_tools"],
                         ["memory_query", "memory_read_page", "memory_recent",
                          "memory_status", "memory_briefing"])
        self.assertEqual(policy["servers"]["socraticode"]["enabled_tools"],
                         ["codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"])
        self.assertEqual(policy["servers"]["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(policy["servers"]["headroom"]["enabled_tools"],
                         ["headroom_compress", "headroom_retrieve", "headroom_stats"])
        self.assertEqual(policy["servers"]["qmd"]["collections"],
                         ["foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog"])
        # A policy file alone is not enforcement; direct unfiltered MCP is disabled.
        self.assertEqual(cfg["MCP_SERVERS"], [])
        self.assertFalse(policy["direct_servers_enabled"])
        for path in RECIPE.rglob("*"):
            if ".research" in path.parts:
                continue
            if path.is_file() and path.suffix in {".sh", ".py", ".json", ".toml"}:
                data = path.read_text()
                self.assertNotIn("0.0.0.0", data, str(path))
                self.assertNotRegex(data, r"sk-[A-Za-z0-9]{20,}", str(path))
                self.assertNotRegex(data, r"(?i)reasoning_effort[\"']?\s*[:=]\s*[\"']auto", str(path))
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.json"
            result.write_text("{}")
            checked = subprocess.run([sys.executable, str(RECIPE / "e2e/check.py"), str(result)],
                                     capture_output=True, text=True)
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            sanity = json.loads(checked.stdout)
            self.assertFalse(sanity["ready_for_grading"])
            self.assertNotIn("passed", sanity)
            self.assertIn("empty_report", sanity["errors"])

    def test_report_transport_controls_do_not_grade_content(self):
        checker = load("gptr_check", RECIPE / "e2e/check.py")
        # A valid report and an obviously wrong report both reach the UPSTREAM
        # grader unchanged. Transport success must never become a quality pass.
        for report in ("# Report\nAn evidence-bearing answer.\n", "The moon is cheese.\n"):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as tmp:
                result = {"report": report}
                self.assertTrue(checker.check(result)["ready_for_grading"])
                self.assertNotIn("passed", checker.check(result))
                destination = Path(tmp) / "idx-12.md"
                checker.export_report(result, destination)
                self.assertEqual(destination.read_bytes(), report.encode("utf-8"))
        for result in ({}, {"report": " \n"}, {"report": None}, {"report": 7}, [], None):
            with self.subTest(result=result):
                self.assertFalse(checker.check(result)["ready_for_grading"])

    def test_graded_report_binding_rejects_replaced_and_mismatched_exports(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        report = b"Original worker report\n"
        expected = hashlib.sha256(report).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            exported = run_dir / "frozen-reports/gptr/idx-12.md"
            exported.parent.mkdir(parents=True)
            (run_dir / "report.md").write_bytes(report)
            exported.write_bytes(report)
            self.assertEqual(grader.read_report(run_dir, 12, expected), report)
            exported.write_bytes(b"Changed report\n")
            with self.assertRaises(ValueError):
                grader.read_report(run_dir, 12, expected)
            (run_dir / "report.md").write_bytes(b"Changed report\n")
            with self.assertRaises(ValueError):
                grader.read_report(run_dir, 12, expected)

    def test_upstream_grade_controls_preserve_scores_and_reject_malformed_output(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        task = {"idx": 12, "content": {"task": "Frozen control", "rubric": {
            "info_recall": ["Fact"], "analysis": ["Analysis"], "presentation": ["Presentation"]}}}
        for score in (1, 0, -1):
            row = {"model": "gptr", "idx": 12, "result": {"task": "Frozen control", "scores": {
                dimension: {item: {"score": score, "reason": "Control", "evidence": ""}}
                for dimension, (item,) in task["content"]["rubric"].items()}}}
            with self.subTest(score=score):
                self.assertEqual(grader.validate_grade([row], task), row["result"])
                self.assertNotIn("passed", grader.validate_grade([row], task))
        for bad in ([], [row, row], [{"model": "gptr", "idx": 12, "result": {"error": "batch failed"}}],
                    [{**row, "idx": 13}], [{**row, "model": "wrong-arm"}], [None]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                grader.validate_grade(bad, task)
        for replacement in ({"score": 2}, {"score": True}, {"score": 1, "reason": [], "evidence": ""}):
            bad = copy.deepcopy(row)
            bad["result"]["scores"]["info_recall"]["Fact"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                grader.validate_grade([bad], task)
        bad = copy.deepcopy(row)
        bad["result"]["scores"]["analysis"] = {}
        with self.assertRaises(ValueError):
            grader.validate_grade([bad], task)

    def test_gateway_transport_headers_and_strict_schema_controls(self):
        gateway = load("gptr_gateway", RECIPE / "gateway.py")
        transport = gateway.GatewayTransport("fixed-conversation")
        payload = {"model": "cx/gpt-6-astra-max", "messages": [{"role": "user", "content": "Grade"}]}
        first = transport.headers(payload)
        second = transport.headers(payload)
        self.assertEqual(first["x-omniroute-session"], "fixed-conversation")
        self.assertEqual(second["x-omniroute-session"], first["x-omniroute-session"])
        self.assertNotEqual(first["Idempotency-Key"], second["Idempotency-Key"])
        # Public wire schema is copied from the upstream DRB-II prompt.
        strict = {**payload, "response_format": gateway.DRB_RESPONSE_FORMAT}
        self.assertTrue(transport.headers(strict))
        bad_schema = copy.deepcopy(strict)
        del bad_schema["response_format"]["json_schema"]["schema"]["properties"]["results"]["items"]["additionalProperties"]
        for bad in ({**payload, "model": "claude-opus-5-5"},
                    {**payload, "model": "openai/gpt-5"},
                    {**payload, "temperature": 0.1},
                    {**payload, "temperature": float("nan")},
                    {**payload, "response_format": {"type": "json_object"}}, bad_schema):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                transport.headers(bad)
        self.assertTrue(transport.headers({**payload, "tools": [{"type": "function"}]}))
        calls = []
        def sender(url, **kwargs):
            calls.append((url, kwargs))
            return "native response"
        post = transport.grader_post(sender)
        self.assertEqual(post(gateway.CHAT_URL, headers={"Authorization": "Bearer local-loopback"},
                              json=payload, timeout=600, stream=False), "native response")
        self.assertEqual(calls[0][1]["json"]["messages"], payload["messages"])
        self.assertEqual(calls[0][1]["json"]["response_format"], gateway.DRB_RESPONSE_FORMAT)
        self.assertNotIn("temperature", calls[0][1]["json"])
        self.assertIn("Idempotency-Key", calls[0][1]["headers"])
        with self.assertRaises(ValueError):
            post("https://example.invalid/v1/chat/completions", json=payload)

    def test_frozen_task_rejects_changed_bytes_and_recipe_wires_native_grader(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        data = b'{"idx":12,"prompt":"Frozen upstream prompt","content":{"task":"Frozen"}}\n'
        selection = {"idx": 12, "row_sha256": hashlib.sha256(data).hexdigest(),
                     "prompt_sha256": hashlib.sha256(b"Frozen upstream prompt").hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tasks_and_rubrics.jsonl"
            source.write_bytes(data)
            task, row = grader.load_task(source, selection)
            self.assertEqual(task["prompt"], "Frozen upstream prompt")
            self.assertEqual(row, data)
            source.write_bytes(data.replace(b"Frozen", b"Changed"))
            with self.assertRaises(ValueError):
                grader.load_task(source, selection)
            source.write_bytes(data + data)
            with self.assertRaises(ValueError):
                grader.load_task(source, selection)
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(pins["grader"]["commit"], "b38f360603db9531b102aef8c166cedb8509b6f6")
        self.assertEqual(pins["grader"]["runner_up_commit"], "852f4022d1f98fb707222e395405136e8f0e8d52")
        self.assertIn("uv sync --locked", (RECIPE / "install.sh").read_text())
        runner = (RECIPE / "run-e2e.sh").read_text()
        self.assertIn("${GPTR_JUDGE_MODEL:-cx/gpt-6-astra-max}", runner)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", runner)
        native = (RECIPE / "e2e/run.py").read_text()
        self.assertIn("worker_clients()", native)
        self.assertIn("grader-venv/bin/python", native)

    def test_mcp_policy_enforces_calls_and_collection_arguments(self):
        proxy = load("gptr_proxy", RECIPE / "mcp_proxy.py")
        host = {"MEMORY_PROJECT": "synthetic-project", "MEMORY_WORKSPACE": "synthetic-workspace"}
        for server, tool in [("context-mode", "ctx_upgrade"), ("context-mode", "ctx_purge"),
                             ("ai-memory", "memory_write_page"), ("qmd", "multi_get"),
                             ("socraticode", "codebase_search")]:
            with self.subTest(server=server, tool=tool), self.assertRaises(ValueError):
                proxy.scope_arguments(server, tool, {}, host)
        args = proxy.scope_arguments("qmd", "query", {"query": "token practice", "limit": 100}, host)
        self.assertEqual(args["collections"], ["foundation-docs", "foundation-adoption",
                                               "us-equities-foundation", "us-equities-catalog"])
        self.assertEqual(args["searches"], [{"type": "lex", "query": "token practice"}])
        self.assertFalse(args["rerank"])
        self.assertEqual(args["limit"], 5)
        with self.assertRaises(ValueError):
            proxy.scope_arguments("qmd", "query", {"query": "x", "collections": ["private"]}, host)
        for file in ["#abc123", "/etc/passwd", "qmd://private/doc.md", "qmd://foundation-docs/../x",
                     "qmd://foundation-docs/%2e%2e/x", "qmd://foundation-docs/*"]:
            with self.subTest(file=file), self.assertRaises(ValueError):
                proxy.scope_arguments("qmd", "get", {"file": file}, host)
        self.assertEqual(proxy.scope_arguments("qmd", "get",
                         {"file": "qmd://foundation-docs/token-practice.md", "maxLines": 900}, host)["maxLines"], 120)
        self.assertEqual(proxy.scope_arguments("ai-memory", "memory_query", {"project": "other"}, host)["project"],
                         "synthetic-project")
        scoped = proxy.scope_arguments("ai-memory", "memory_query",
                                       {"workspace": "other", "global": True, "scopes": [{"project": "other"}]}, host)
        self.assertEqual(scoped["workspace"], "synthetic-workspace")
        self.assertFalse(scoped["global"])
        self.assertFalse(scoped["answer"])
        self.assertNotIn("scopes", scoped)

    def test_gateway_reader_uses_only_authorized_columns_and_is_read_only(self):
        # Import the public receipt helper without installing either runtime.
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "synthetic.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE call_logs(timestamp TEXT,path TEXT,status INTEGER,model TEXT,"
                            "reasoning_effort_requested TEXT,reasoning_effort_upstream TEXT,tokens_in INTEGER,"
                            "tokens_cache_read INTEGER,tokens_reasoning INTEGER)")
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:01Z", "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 123, 100, 20))
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:02Z", "/private/path", 500, "synthetic@example.invalid", None, None, None, None, None))
                con.commit()
            before = db.read_bytes()
            rows = receipt.gateway_rows(db, "2026-09-27T17:20:00Z", "2026-09-27T17:20:03Z", "cx/gpt-6-astra-max")
            self.assertEqual(rows["status"], "observed")
            self.assertEqual(rows["rows"][0]["tokens_cache_read"], 100)
            self.assertEqual(rows["rows"][1]["model"], "<other-model>")
            self.assertEqual(rows["rows"][1]["path"], "<other-path>")
            self.assertEqual(set(rows["rows"][0]), set(receipt.COLUMNS))
            self.assertEqual(before, db.read_bytes())
            absent = Path(tmp) / "absent.sqlite"
            self.assertEqual(receipt.gateway_rows(absent, "x", "y", "cx/gpt-6-astra-max")["status"], "unavailable")
            self.assertFalse(absent.exists())

    def test_receipt_cannot_promote_report_sanity_to_quality_verdict(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "result.json").write_text('{"report":"A complete-looking but ungraded report"}')
            result = receipt.write_receipt(run_dir, "2026-09-27T00:00:00Z", "2026-09-27T00:01:00Z",
                                           "cx/gpt-6-astra-max", "0.16.0", database=run_dir / "absent.sqlite")
            self.assertNotIn("passed", result)
            self.assertFalse(result["execution_complete"])
            self.assertEqual(result["evaluation"]["status"], "unavailable_or_malformed")
            self.assertTrue(result["report_sanity"]["ready_for_grading"])
            self.assertEqual(result["skills"]["listed_at_start"], [])
            self.assertEqual(result["skills"]["activation_events"], [])
            (run_dir / "result.json").write_text('{"report":')
            interrupted = receipt.write_receipt(run_dir, "2026-09-27T00:00:00Z", "2026-09-27T00:01:00Z",
                                                 "cx/gpt-6-astra-max", None, database=run_dir / "absent.sqlite")
            self.assertFalse(interrupted["execution_complete"])

    def test_skills_lifecycle_and_no_listener_recipe(self):
        readme = (RECIPE / "README.md").read_text()
        for value in ("tools/adoption/install_skills.py", "--manifest blueprints/runtime-workers/skills/manifest.json",
                      '--project-dir "$worker_workspace" --agent universal', "pending the skills-program PR",
                      "127.0.0.1:3730-3799", "rw-gpt-researcher-",
                      "com.native-agent-stack.owner=gpt6-omniroute-framework-integration"):
            self.assertIn(value, readme)
        # This SDK/stdio recipe allocates no Docker resources or listener ports.
        for name in ("install.sh", "run-e2e.sh", "run-upstream-tests.sh"):
            source = (RECIPE / name).read_text()
            self.assertNotIn("docker ", source)
            self.assertNotRegex(source, r"(?:127\.0\.0\.1|localhost):(?:37[12]\d|543[3-9]|38[01]\d)\b")


if __name__ == "__main__":
    unittest.main()
