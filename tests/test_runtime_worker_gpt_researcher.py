"""Offline recipe contracts; not upstream or live-provider acceptance.

Oracle: user runtime-worker brief (2026-09-27), and GPT Researcher v3.7.0
config/variables/default.py, utils/llm.py, mcp/client.py. No framework install.
"""

import json
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
            verdict = json.loads(checked.stdout)
            self.assertFalse(verdict["passed"])
            self.assertIn("empty_report", verdict["failures"])

    def test_frozen_oracle_rejects_wrong_facts_and_unfetched_citations(self):
        checker = load("gptr_check", RECIPE / "e2e/check.py")
        urls = ["https://peps.python.org/pep-0695/", "https://peps.python.org/pep-0701/",
                "https://peps.python.org/pep-0632/"]
        # Synthetic control: proves checker discrimination, never native acceptance.
        facts = ["Python 3.12 introduced type parameter syntax and the type statement (PEP 695).",
                 "Python 3.12 formalized f-string grammar and allowed quote reuse and backslashes in expressions (PEP 701).",
                 "Python 3.12 removed distutils from the standard library (PEP 632)."]
        result = {"report": "\n".join(f"- {fact} [Primary source]({url})" for fact, url in zip(facts, urls)),
                  "sources": [{"url": url, "raw_content": "Synthetic fetched-page control. " * 20} for url in urls]}
        self.assertTrue(checker.check(result)["passed"])
        missing = {**result, "sources": result["sources"][:2]}
        self.assertIn("unfetched_citation", checker.check(missing)["failures"])
        wrong = {**result, "report": result["report"].replace("removed distutils", "retained distutils")}
        self.assertIn("missing_fact_3", checker.check(wrong)["failures"])
        outside = {**result, "report": result["report"] + " [extra](https://peps.python.org.evil.test/fake)"}
        self.assertIn("citation_outside_allowed_domains", checker.check(outside)["failures"])
        snippets = {**result, "sources": [{"url": u, "raw_content": "search snippet"} for u in urls]}
        self.assertIn("unfetched_citation", checker.check(snippets)["failures"])
        fragments = {**result, "report": result["report"].replace(urls[1], urls[0] + "#another")}
        self.assertIn("too_few_distinct_citations", checker.check(fragments)["failures"])

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
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE call_logs(timestamp TEXT,path TEXT,status INTEGER,model TEXT,"
                            "reasoning_effort_requested TEXT,reasoning_effort_upstream TEXT,tokens_in INTEGER,"
                            "tokens_cache_read INTEGER,tokens_reasoning INTEGER)")
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:01Z", "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 123, 100, 20))
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:02Z", "/private/path", 500, "synthetic@example.invalid", None, None, None, None, None))
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


if __name__ == "__main__":
    unittest.main()
