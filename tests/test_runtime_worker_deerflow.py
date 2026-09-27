"""Offline integration contracts, not DeerFlow or provider acceptance.

Seams were specified by the 2026-09-27 builder request: recipe/configuration,
MCP restrictions, artifact pins, and the frozen task's executable checker.
Reference: bytedance/deer-flow v2.1.0 config.example.yaml and
extensions_config.example.json; repository tests/test_install_skills.py for
the stdlib subprocess test pattern. No installation or network is performed.
"""

import json
import importlib.util
from contextlib import closing
import sqlite3
import tomllib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/deerflow"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class DeerFlowRecipeTests(unittest.TestCase):
    def test_renderer_and_qmd_snapshot_keep_state_owned_and_index_scoped(self):
        renderer = module("deerflow_recipe", RECIPE / "recipe.py")
        collections = {n: {"path": "/catalog/" + n, "pattern": "**/*.md"} for n in (
            "foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog")}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "source.sqlite"
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("CREATE TABLE documents (collection TEXT)")
                conn.executemany("INSERT INTO documents VALUES (?)", [(n,) for n in collections])
            settings = {"variables": {"ECO_ROOT": "/opt/adopted", "HOST_PATH": "/usr/bin", "QDRANT_URL": "10.0.2.2:16333", "EMBED_URL": "10.0.2.2:18232"},
                        "skills_root": "/opt/pinned-skills", "mcp_mounts": [], "session_namespace": "offline-fixture",
                        "qmd_snapshot": {"database": str(db), "collections": collections}}
            state, prefix = root / "state", root / "prefix"
            before = db.read_bytes()
            renderer.seed_qmd(settings, state)
            self.assertEqual(db.read_bytes(), before)
            target = state / "data/mcp/qmd/cache/qmd/native-agent-stack-catalog.sqlite"
            self.assertTrue(target.is_file())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            compose = renderer.render(settings, prefix, state)
            config = json.loads((state / "config/config.yaml").read_text())
            self.assertEqual(config["models"][0]["base_url"], "http://10.0.2.2:20128/v1")
            self.assertEqual(compose["services"]["gateway"]["environment"]["DEERFLOW_MODEL"], "cx/gpt-6-astra-max")
            settings["model"] = "cx/gpt-next-max"
            compose = renderer.render(settings, prefix, state)
            self.assertEqual(compose["services"]["gateway"]["environment"]["DEERFLOW_MODEL"], "cx/gpt-next-max")
            ext = json.loads((state / "config/extensions_config.json").read_text())
            self.assertEqual(ext["mcpServers"]["qmd"]["env"]["XDG_CACHE_HOME"], "/state/mcp/qmd/cache")
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("INSERT INTO documents VALUES ('unrelated-private-collection')")
            with self.assertRaises(ValueError):
                renderer.seed_qmd(settings, root / "other-state")

    def test_mcp_launches_preserve_the_adoption_commands(self):
        ext = json.loads((RECIPE / "extensions_config.json.template").read_text())["mcpServers"]
        common = tomllib.loads((ROOT / "adoption/templates/codex.config.template.toml").read_text())["mcp_servers"]
        project = tomllib.loads((ROOT / "adoption/templates/project.codex.config.template.toml").read_text())["mcp_servers"]
        for name in ("context-mode", "serena", "socraticode", "qmd", "jcodemunch"):
            native = project[name] if name == "jcodemunch" else common[name]
            self.assertEqual(ext[name]["args"], [native["command"], *native.get("args", [])], name)
            self.assertEqual(ext[name]["command"], "/runtime/stdio.sh")

    def test_checker_accepts_a_computed_result_and_rejects_hard_coding(self):
        expected = json.loads((RECIPE / "e2e/expected.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "files.json").write_text(json.dumps(expected["files"]))
            (out / "report.json").write_text(json.dumps(expected["summary"]))
            script = out / "summarize.py"
            script.write_text("import json,sys,collections\nx=json.load(open(sys.argv[1]))\n"
                              "r={k:sum(f[k] for f in x) for k in ['additions','deletions','changes']}\n"
                              "r.update(file_count=len(x),by_status=dict(collections.Counter(f['status'] for f in x)),paths=sorted(f['filename'] for f in x))\n"
                              "print(json.dumps(r))\n")
            command = [sys.executable, str(RECIPE / "e2e/check.py"), tmp]
            good = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            script.write_text("print(" + repr(json.dumps(expected["summary"])) + ")\n")
            bad = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(bad.returncode, 1)
            self.assertFalse(json.loads(bad.stdout)["passed"])

    def test_gateway_reader_is_read_only_and_uses_only_approved_columns(self):
        receipt = module("deerflow_receipt", RECIPE / "e2e/receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "gateway.sqlite"
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, private_payload)")
                conn.execute("CREATE TABLE secrets (value)")
                conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (1000, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 100, 60, 9, "must-never-be-read"))
                conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (5000, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 1, 0, 0, "outside-window"))
                for stamp in ("1000", "1000.5", "1970-01-01T00:16:40Z"):
                    conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (stamp, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 100, 60, 9, "must-never-be-read"))
            before = db.read_bytes()
            rows = receipt.gateway_rows(db, 999, 1001)
            self.assertEqual(len(rows), 4)
            self.assertEqual(set(rows[0]), set(receipt.COLUMNS))
            self.assertEqual(rows[0]["tokens_cache_read"], 60)
            self.assertEqual(db.read_bytes(), before)
            with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
                conn.set_authorizer(receipt.sql_authorizer)
                for forbidden in ("SELECT private_payload FROM call_logs", "SELECT value FROM secrets", "DELETE FROM call_logs"):
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(forbidden)

    def test_native_trace_does_not_count_failed_children_as_completed(self):
        receipt = module("deerflow_trace", RECIPE / "e2e/receipt.py")
        events = [
            {"type": "values", "data": {"messages": [
                {"type": "ai", "tool_calls": [
                    {"name": "task", "id": "private-one", "args": {}},
                    {"name": "task", "id": "private-two", "args": {}},
                    {"name": "task", "id": "private-failure", "args": {}},
                    {"name": "task", "id": "private-timeout", "args": {}},
                    {"name": "read_file", "id": "private-three", "args": {"path": "/mnt/skills/legacy/search-first/SKILL.md"}}]},
                {"type": "tool", "tool_call_id": "private-one", "content": "Task Failed: native child error", "additional_kwargs": {"subagent_status": "failed"}},
                {"type": "tool", "tool_call_id": "private-two", "content": "Task completed", "additional_kwargs": {"subagent_status": "completed"}},
                {"type": "tool", "tool_call_id": "private-failure", "content": "Error: native child error", "additional_kwargs": {"subagent_status": "failed"}},
                {"type": "tool", "tool_call_id": "private-timeout", "content": "", "additional_kwargs": {"subagent_status": "polling_timed_out"}},
                {"type": "tool", "tool_call_id": "private-three", "content": "actual skill instructions"}]}},
            {"type": "messages-tuple", "data": {"type": "tool", "tool_call_id": "private-two", "content": "Task completed"}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in events))
            found = receipt.observations(path)
        self.assertEqual(found["completed_tasks_observed"], 1)
        self.assertEqual(found["failed_tasks_observed"], 3)
        self.assertEqual(found["task_results_observed"], 4)
        self.assertEqual(found["skill_reads_observed"], ["search-first"])
        self.assertNotIn("private-", json.dumps(found))

    def test_model_context_and_container_contract(self):
        config = json.loads((RECIPE / "config.yaml.template").read_text())
        model = config["models"][0]
        self.assertEqual(model["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(model["model"], "$DEERFLOW_MODEL")
        self.assertEqual(json.loads((RECIPE / "defaults.json").read_text())["model"], "cx/gpt-6-astra-max")
        self.assertEqual(model["api_key"], "local-loopback")
        self.assertTrue(model["use_responses_api"])
        self.assertTrue(model["streaming"])
        self.assertNotIn("temperature", model)
        self.assertNotIn("reasoning_effort", model)
        self.assertEqual(config["sandbox"]["bash_command_timeout"], 120)
        self.assertNotIn("bash_timeout", config["sandbox"])
        self.assertNotIn("tracing", config)
        self.assertEqual(config["database"], {"backend": "sqlite", "sqlite_dir": "$DEERFLOW_SQLITE_DIR"})
        for feature in ("summarization", "tool_output", "token_budget", "tool_search"):
            self.assertTrue(config[feature]["enabled"], feature)
        compose = json.loads((RECIPE / "compose.json.template").read_text())
        self.assertEqual(compose["services"]["gateway"]["environment"]["DEERFLOW_SQLITE_DIR"], "/state/deerflow/data")
        self.assertEqual(compose["services"]["nginx"]["ports"], ["127.0.0.1:3771:2026"])
        for name, service in compose["services"].items():
            if name != "nginx":
                self.assertNotIn("ports", service)
        self.assertNotIn("docker.sock", json.dumps(compose))
        self.assertEqual(compose["services"]["redis"]["entrypoint"], ["/runtime/redis-start.sh"])
        self.assertIn("-h", compose["services"]["redis"]["healthcheck"]["test"][1])

    def test_tool_limits_are_enforced_not_only_described(self):
        policy = module("deerflow_worker_policy", RECIPE / "runtime/worker_policy.py")
        for tool in ("context-mode_ctx_upgrade", "context-mode_ctx_purge", "ai-memory_memory_write", "socraticode_codebase_index", "jcodemunch_index_folder", "headroom_headroom_compress"):
            self.assertFalse(policy.tool_allowed(tool), tool)
        for tool in ("context-mode_ctx_execute", "serena_find_symbol", "jcodemunch_route", "jcodemunch_menu", "jcodemunch_order"):
            self.assertTrue(policy.tool_allowed(tool), tool)
        limits = json.loads((RECIPE / "runtime/tool-policy.json").read_text())
        self.assertEqual(limits["servers"]["ai-memory"]["allow"], ["memory_query", "memory_read_page", "memory_recent", "memory_status", "memory_briefing"])
        self.assertEqual(limits["servers"]["socraticode"]["allow"], ["codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"])
        self.assertEqual(set(limits["qmd_collections"]), {"foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog"})
        self.assertFalse(policy.arguments_allowed("qmd_query", {}))
        self.assertFalse(policy.arguments_allowed("qmd_query", {"collections": ["private"]}))
        self.assertTrue(policy.arguments_allowed("qmd_query", {"collections": ["foundation-docs"], "searches": [{"type": "lex", "query": "workers"}], "rerank": False}))
        self.assertFalse(policy.arguments_allowed("qmd_query", {"collections": ["foundation-docs"], "query": "expand me"}))
        self.assertFalse(policy.arguments_allowed("qmd_get", {"file": "#abc123"}))
        self.assertFalse(policy.arguments_allowed("qmd_get", {"file": "qmd://foundation-docs/../private/a.md"}))
        ext = json.loads((RECIPE / "extensions_config.json.template").read_text())
        self.assertEqual(ext["mcpServers"]["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(ext["mcpServers"]["context-mode"]["env"]["CONTEXT_MODE_PROJECT_DIR"], "/work")

    def test_gateway_headers_preserve_affinity_and_new_call_identity(self):
        headers = module("deerflow_worker_headers", RECIPE / "runtime/gateway_headers.py")
        one = headers.call_headers("conversation-a")
        two = headers.call_headers("conversation-a")
        self.assertEqual(one["x-omniroute-session"], two["x-omniroute-session"])
        self.assertNotEqual(one["Idempotency-Key"], two["Idempotency-Key"])
        self.assertNotEqual(one["x-omniroute-session"], headers.call_headers("conversation-b")["x-omniroute-session"])

    def test_pins_and_script_boundaries(self):
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(pins["commit"], "345f08be00c8a9495079b732a39b46aa9af1584e")
        self.assertRegex(pins["archive"]["sha256"], r"^[0-9a-f]{64}$")
        for image in pins["images"].values():
            self.assertRegex(image, r"@sha256:[0-9a-f]{64}$")
        for name in ("install.sh", "run-e2e.sh", "lifecycle.sh"):
            body = (RECIPE / name).read_text()
            self.assertIn("set -euo pipefail", body)
            self.assertNotIn("sudo ", body)
        for path in [*RECIPE.glob("*.template"), *RECIPE.glob("*.example"), *RECIPE.glob("*.sh"), *RECIPE.glob("runtime/*.py"), *RECIPE.glob("runtime/*.sh")]:
            content = path.read_text()
            self.assertNotIn("0.0.0.0", content, path.name)
            self.assertNotRegex(content, r"(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})")

    def test_reviewable_recipe_and_empty_result_rejection(self):
        for name in (
            "README.md", "install.sh", "config.yaml.template",
            "extensions_config.json.template", "pins.json", "run-e2e.sh",
            "e2e/check.py", "e2e/expected.json", "e2e/task.md", "e2e/receipt.py",
        ):
            with self.subTest(file=name):
                self.assertTrue((RECIPE / name).is_file(), name)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(RECIPE / "e2e/check.py"), tmp],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["passed"], False)


if __name__ == "__main__":
    unittest.main()
