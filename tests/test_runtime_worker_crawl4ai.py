"""Offline recipe contracts, not upstream or provider acceptance.

Sources inspected before authoring: unclecode/crawl4ai v0.9.4 release,
pyproject.toml, utils.py:1820-1837, extraction_strategy.py:556-691,
docs/examples/llm_extraction_openai_pricing.py, docs/md_v2/core/fit-markdown.md;
adoption/templates/codex{,.stack-worker}.config.toml. Public seams and
fail-first workflow were specified in the user's runtime-worker task.
"""

import json
import hashlib
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/crawl4ai"


class Crawl4AIRecipeTests(unittest.TestCase):
    def test_recipe_is_reviewable_and_pinned(self):
        for name in ("README.md", "install.sh", "run-e2e.sh", "e2e/check.py",
                     "e2e/receipt.py", "config/worker.json", "pins.json",
                     "requirements.lock", "research.md"):
            self.assertTrue((RECIPE / name).is_file(), name)
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(pins["version"], "0.9.4")
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(pins["image"], r"^unclecode/crawl4ai@sha256:[0-9a-f]{64}$")
        self.assertIn(pins["image"], (RECIPE / "config/compose.yaml").read_text())
        self.assertEqual(hashlib.sha256((RECIPE / "requirements.lock").read_bytes()).hexdigest(), pins["requirements_lock_sha256"])

    def test_gateway_model_is_configurable_and_has_no_sampling_default(self):
        config = json.loads((RECIPE / "config/worker.json").read_text())
        self.assertEqual(config["llm"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(config["llm"]["container_base_url"], "http://10.0.2.2:20128/v1")
        self.assertEqual(config["llm"]["model"], "cx/gpt-6-astra-max")
        self.assertEqual(config["llm"]["model_env"], "CRAWL4AI_MODEL")
        self.assertEqual(config["llm"]["api_token"], "local-loopback")
        self.assertEqual(config["comparison"]["model"], "cx/gpt-6-sol")
        self.assertEqual(config["comparison"]["reasoning_effort"], "medium")
        source = (RECIPE / "worker.py").read_text()
        self.assertNotIn('"cx/gpt-6-astra-max"', source)
        self.assertNotIn('"temperature": 0', source)
        self.assertIn('"temperature": None', source)
        self.assertIn("x-omniroute-session", source)
        self.assertIn("Idempotency-Key", source)
        self.assertIn("fit_markdown", source)

    def test_mcp_limits_are_explicit_and_not_claimed_as_loaded(self):
        policy = json.loads((RECIPE / "config/mcp-policy.json").read_text())
        self.assertEqual(policy["loaded_servers"], [])
        self.assertEqual(policy["role"], "mcp-server")
        limits = policy["consumer_limits"]
        self.assertEqual(set(limits["context-mode"]["disabled_tools"]), {"ctx_upgrade", "ctx_purge"})
        self.assertEqual(set(limits["ai-memory"]["enabled_tools"]), {
            "memory_query", "memory_read_page", "memory_recent", "memory_status", "memory_briefing"})
        self.assertEqual(set(limits["socraticode"]["enabled_tools"]), {
            "codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"})
        self.assertEqual(limits["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(set(limits["headroom"]["enabled_tools"]), {
            "headroom_compress", "headroom_retrieve", "headroom_stats"})
        self.assertEqual(set(limits["qmd"]["collections"]), {
            "foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog"})

    def test_install_is_scoped_hash_checked_and_loopback_only(self):
        source = (RECIPE / "install.sh").read_text()
        self.assertIn("set -euo pipefail", source)
        self.assertIn("--require-hashes", source)
        self.assertIn("--only-binary", source)
        self.assertNotIn("--with-deps", source)
        self.assertNotRegex(source, r"\bsudo\b")
        for name in ("install.sh", "run-e2e.sh", "config/compose.yaml", "container.sh"):
            text = (RECIPE / name).read_text()
            self.assertNotIn("0.0.0.0", text, name)
        compose = (RECIPE / "config/compose.yaml").read_text()
        self.assertIn("127.0.0.1:", compose)
        self.assertIn("/run/secrets/api_token", compose)
        self.assertNotRegex(compose, r"(?im)^\s*(api_token|SECRET_KEY):\s*[A-Za-z0-9]{10}")

    def test_check_rejects_empty_and_wrong_fields(self):
        check = RECIPE / "e2e/check.py"
        self.assertTrue(check.is_file())
        expected = json.loads((RECIPE / "e2e/expected.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            for payload, code in (({}, 1), ({"records": []}, 1), (expected, 0)):
                result.write_text(json.dumps(payload))
                run = subprocess.run([sys.executable, str(check), str(result)], capture_output=True, text=True)
                self.assertEqual(run.returncode, code, run.stdout + run.stderr)
            expected["records"][0]["price_usd"] = "999.00"
            result.write_text(json.dumps(expected))
            self.assertEqual(subprocess.run([sys.executable, str(check), str(result)], capture_output=True).returncode, 1)

    def test_three_frozen_pages_and_both_arms(self):
        self.assertEqual(len(list((RECIPE / "e2e/fixtures").glob("*.html"))), 3)
        config = json.loads((RECIPE / "config/worker.json").read_text())
        self.assertEqual(config["e2e"]["arms"], ["primary", "comparison"])
        source = (RECIPE / "e2e/run.py").read_text()
        self.assertIn('config["e2e"]["arms"]', source)
        self.assertIn("receipt", source)

    def test_receipt_uses_only_allowed_rows_and_never_exports_private_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            database = work / "gateway.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute("""CREATE TABLE call_logs (
                    timestamp TEXT, path TEXT, status INTEGER, model TEXT,
                    reasoning_effort_requested TEXT, reasoning_effort_upstream TEXT,
                    tokens_in INTEGER, tokens_cache_read INTEGER, tokens_reasoning INTEGER,
                    prompt TEXT, request_id TEXT, email TEXT)""")
                for second, model, effort in (
                    (3, "cx/gpt-6-astra-max", "max"), (5, "cx/gpt-6-astra-max", "max"), (7, "cx/gpt-6-astra-max", "max"),
                    (23, "cx/gpt-6-sol", "medium"), (25, "cx/gpt-6-sol", "medium"), (27, "cx/gpt-6-sol", "medium"),
                ):
                    connection.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                        f"2026-09-27T12:00:{second:02d}+00:00", "/v1/chat/completions", 200, model,
                        None if effort == "max" else effort, effort, 120, None, 15,
                        "PRIVATE_PROMPT", "PRIVATE_ID", "PRIVATE_EMAIL"))
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            for arm in ("primary", "comparison"):
                (work / arm).mkdir()
                (work / arm / "result.json").write_text((RECIPE / "e2e/expected.json").read_text())
                (work / arm / "native.log").write_text("PRIVATE_PATH PRIVATE_EMAIL PRIVATE_ID")
            (work / "container.log").write_text(
                "INFO Processing request of type CallToolRequest\nPOST /md HTTP/1.1 200\nPRIVATE_ID")
            info = {
                "framework_version": "0.9.4", "cleanup_passed": True,
                "probes": {key: True for key in ("auth_/mcp/sse", "auth_/mcp/ws", "auth_/crawl", "api_fit", "sse", "websocket")},
                "arms": {
                    "primary": {"model": "cx/gpt-6-astra-max", "start": "2026-09-27T12:00:00+00:00", "end": "2026-09-27T12:00:10+00:00"},
                    "comparison": {"model": "cx/gpt-6-sol", "start": "2026-09-27T12:00:20+00:00", "end": "2026-09-27T12:00:30+00:00"},
                },
            }
            (work / "run.json").write_text(json.dumps(info))
            output = work / "receipt.json"
            command = [sys.executable, str(RECIPE / "e2e/receipt.py"), "--run-dir", str(work),
                       "--db", str(database), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(output.read_text())
            self.assertTrue(receipt["passed"])
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            for marker in ("PRIVATE_", str(work), "prompt", "request_id", "email"):
                # Human-readable sanitization text may name emails, but no DB fields escape.
                self.assertNotIn(marker, json.dumps(receipt["arms"]))
            allowed = {"timestamp", "path", "status", "model", "reasoning_effort_requested",
                       "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning"}
            for arm in receipt["arms"]:
                self.assertEqual(len(arm["gateway"]["rows"]), 3)
                self.assertEqual(set(arm["gateway"]["rows"][0]), allowed)
                self.assertIsNone(arm["gateway"]["rows"][0]["tokens_cache_read"])
            # Fail closed if either model's own deterministic result is empty.
            (work / "comparison/result.json").write_text('{"records": []}')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(json.loads(output.read_text())["passed"])
            (work / "comparison/result.json").write_text((RECIPE / "e2e/expected.json").read_text())
            native_log_text = (work / "container.log").read_text()
            (work / "container.log").unlink()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            missing_log_receipt = json.loads(output.read_text())
            self.assertEqual(missing_log_receipt["mcp_observation"]["native_call_tool_request_count"], 0)
            self.assertTrue(all(a["check_passed"] and a["routing_observed_in_window"] for a in missing_log_receipt["arms"]))
            (work / "container.log").write_text(native_log_text)
            # Every page must have the requested upstream effort, not merely one.
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE call_logs SET reasoning_effort_upstream='low' WHERE timestamp='2026-09-27T12:00:25+00:00'")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            wrong_effort = json.loads(output.read_text())
            self.assertFalse(wrong_effort["passed"])
            self.assertTrue(all(a["check_passed"] for a in wrong_effort["arms"]))
            self.assertFalse(wrong_effort["arms"][1]["routing_observed_in_window"])

    def test_receipt_cannot_certify_absent_db_or_missing_native_mcp_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            arms = {}
            for arm, model in (("primary", "cx/gpt-6-astra-max"), ("comparison", "cx/gpt-6-sol")):
                (work / arm).mkdir()
                (work / arm / "result.json").write_text((RECIPE / "e2e/expected.json").read_text())
                arms[arm] = {"model": model, "start": "2026-09-27T12:00:00+00:00", "end": "2026-09-27T12:01:00+00:00"}
            (work / "container.log").write_text("Processing request of type CallToolRequest\nPOST /md HTTP/1.1 200\n")
            probes = {key: True for key in ("auth_/mcp/sse", "auth_/mcp/ws", "auth_/crawl", "api_fit", "sse", "websocket")}
            (work / "run.json").write_text(json.dumps({"framework_version": "0.9.4", "arms": arms, "cleanup_passed": True, "probes": probes}))
            output = work / "receipt.json"
            result = subprocess.run([sys.executable, str(RECIPE / "e2e/receipt.py"), "--run-dir", str(work),
                "--db", str(work / "absent.sqlite"), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(json.loads(output.read_text())["passed"])
            self.assertTrue(all(a["gateway"]["status"] == "unavailable" for a in json.loads(output.read_text())["arms"]))
            self.assertFalse((work / "absent.sqlite").exists())

    def test_schema_check_is_type_strict(self):
        payload = json.loads((RECIPE / "e2e/expected.json").read_text())
        payload["records"][0]["in_stock"] = 1
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            result.write_text(json.dumps(payload))
            command = [sys.executable, str(RECIPE / "e2e/check.py"), str(result)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
