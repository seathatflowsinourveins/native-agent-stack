"""Offline integration contracts, not DeerFlow or provider acceptance.

Seams were specified by the 2026-09-27 Round-2 builder request: recipe/config,
MCP restrictions, artifact pins, native trace transport and upstream grading.
Reference: bytedance/deer-flow v2.1.0 config.example.yaml and
extensions_config.example.json; repository tests/test_install_skills.py for
the stdlib subprocess test pattern. External clients use test doubles; the real
upstream scorer control is skipped if unavailable. No installation or network.
"""

import json
import copy
import asyncio
import importlib.util
from contextlib import closing
import sqlite3
import tomllib
import subprocess
import sys
import tempfile
import unittest
import types
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/deerflow"

# install_grader creates its venv from sys.executable and refuses any interpreter but the lock's CPython 3.13;
# the grader tests stand in that interpreter through the recipe module's own sys name, never the global one.
LOCK_TARGET_PYTHON = types.SimpleNamespace(executable=sys.executable, version_info=(3, 13, 0, "final", 0))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(path.parent), *sys.path]):
        spec.loader.exec_module(result)
    return result


class DeerFlowRecipeTests(unittest.TestCase):
    def test_owned_compose_resources_and_loopback_ports(self):
        compose = json.loads((RECIPE / "compose.json.template").read_text())
        owner = {"com.native-agent-stack.owner": "gpt6-omniroute-framework-integration"}
        self.assertEqual(compose["name"], "rw-deerflow")
        for name, service in compose["services"].items():
            self.assertEqual(service["container_name"], "rw-deerflow-" + name)
            self.assertEqual(service["labels"], owner)
            for published in service.get("ports", []):
                host, port, _ = published.split(":")
                self.assertEqual(host, "127.0.0.1")
                self.assertIn(int(port), range(3730, 3800))
        for kind in ("networks", "volumes"):
            for resource in compose.get(kind, {}).values():
                self.assertTrue(resource["name"].startswith("rw-deerflow-"))
                self.assertEqual(resource["labels"], owner)
        self.assertIn("default", compose["networks"])

    def test_literal_cleanup_continues_after_already_absent_resource(self):
        renderer = module("deerflow_cleanup", RECIPE / "recipe.py")
        calls = []
        def docker(settings, *args, **kwargs):
            calls.append(args)
            if args[-1] in {"rw-deerflow-nginx", "rw-deerflow-network"}:
                raise subprocess.CalledProcessError(1, args, stderr="Error: No such container or network")
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch.object(renderer, "read", return_value={}), patch.object(renderer, "require_rootless"), \
                patch.object(renderer, "docker", docker):
            renderer.lifecycle("down")
        self.assertEqual([c[-1] for c in calls], ["rw-deerflow-nginx", "rw-deerflow-frontend", "rw-deerflow-gateway", "rw-deerflow-redis", "rw-deerflow-egress", "rw-deerflow-network", "rw-deerflow-egress-network"])

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
                        "mcp_mounts": [], "session_namespace": "offline-fixture",
                        "qmd_snapshot": {"database": str(db), "collections": collections}}
            state, prefix = root / "state", root / "prefix"
            before = db.read_bytes()
            renderer.seed_qmd(settings, state)
            self.assertEqual(db.read_bytes(), before)
            target = state / "qmd-seed/cache/qmd/native-agent-stack-catalog.sqlite"
            self.assertTrue(target.is_file())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            compose = renderer.render(settings, prefix, state)
            config = json.loads((state / "config/config.yaml").read_text())
            self.assertEqual(config["models"][0]["base_url"], "$DEERFLOW_BASE_URL")
            self.assertEqual(compose["services"]["gateway"]["environment"]["DEERFLOW_MODEL"], "cx/gpt-6-astra-max")
            settings["model"] = "cx/gpt-6-sol-max"
            compose = renderer.render(settings, prefix, state)
            self.assertEqual(compose["services"]["gateway"]["environment"]["DEERFLOW_MODEL"], "cx/gpt-6-sol-max")
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
            expected = [native["command"], *native.get("args", [])]
            if name == "serena":
                expected[expected.index("--enable-web-dashboard") + 1] = "false"
            self.assertEqual(ext[name]["args"], expected, name)
            self.assertEqual(ext[name]["command"], "/runtime/stdio.sh")

    def test_adapter_preserves_known_pass_and_fail_without_a_local_verdict(self):
        adapter = module("deerflow_transport", RECIPE / "e2e/check.py")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework-events.jsonl"
            # Upstream tests/gaia/test_scorer.py: 42/42 passes, 99/42 fails.
            # Transport accepts both; only the real upstream scorer judges them.
            for answer in ("42", "99"):
                records = [
                    {"type": "values", "data": {"messages": [
                        {"type": "ai", "content": "earlier draft"}]}},
                    {"type": "messages-tuple", "data": {"type": "ai", "content": answer}},
                    {"type": "values", "data": {"messages": [
                        {"type": "ai", "content": answer}]}},
                    {"type": "end", "data": {"usage": {}}},
                ]
                path.write_text("\n".join(json.dumps(x) for x in records))
                self.assertEqual(adapter.read_completion(path), answer)

    def test_adapter_rejects_missing_malformed_and_unfinished_output(self):
        adapter = module("deerflow_transport_bad", RECIPE / "e2e/check.py")
        valid = {"type": "values", "data": {"messages": [{"type": "ai", "content": "42"}]}}
        end = {"type": "end", "data": {"usage": {}}}
        bad_records = [[], [valid], [end], [valid, end, end],
                       [valid, {"type": "error", "data": {}}, end],
                       [{"type": "values", "data": {"messages": [{"type": "ai", "content": {"answer": 42}}]}}, end],
                       [{"type": "values", "data": {"messages": [{"type": "ai", "content": "", "tool_calls": [{"name": "task"}]}]}}, end],
                       [valid, {"type": "values", "data": {"messages": [{"type": "tool", "content": "42"}]}}, end]]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework-events.jsonl"
            with self.assertRaises((ValueError, OSError)):
                adapter.read_completion(path)
            for records in bad_records:
                with self.subTest(records=records):
                    path.write_text("\n".join(json.dumps(x) for x in records))
                    with self.assertRaises(ValueError):
                        adapter.read_completion(path)
            for malformed in ("not-json", "null", "[]", '42'):
                path.write_text(malformed)
                with self.assertRaises(ValueError):
                    adapter.read_completion(path)

    def test_inspect_solver_transports_only_input_and_preserves_upstream_task(self):
        native_task = types.SimpleNamespace(dataset=[types.SimpleNamespace(id="frozen", files={})],
                                            sandbox="docker", scorer=object())
        original_scorer = native_task.scorer
        calls = []

        def gaia(**kwargs):
            calls.append(kwargs)
            return native_task

        def output(model, content):
            return types.SimpleNamespace(model=model, completion=content)

        class InputState:
            input_text = "upstream question and format instructions"
            sample_id = "frozen"
            epoch = 1
            metadata = {}

            @property
            def target(self):
                raise AssertionError("transport must never read the answer target")

        with patch.dict(sys.modules, {
            "inspect_ai": types.SimpleNamespace(task=lambda f: f),
            "inspect_ai.model": types.SimpleNamespace(ModelOutput=types.SimpleNamespace(from_content=output)),
            "inspect_ai.solver": types.SimpleNamespace(solver=lambda f: f),
            "inspect_evals.gaia": types.SimpleNamespace(gaia=gaia),
            "run": types.SimpleNamespace(run_worker=lambda *a: {"completion": "99", "model": "cx/gpt-6-astra-max", "receipt": {}}),
        }):
            adapter = module("deerflow_gaia", RECIPE / "e2e/gaia.py")
            task = adapter.deerflow_gaia(instance_ids="frozen")
            self.assertIs(task.scorer, original_scorer)
            self.assertIsNone(task.sandbox)
            self.assertEqual(calls[0]["instance_ids"], ["frozen"])
            self.assertEqual(calls[0]["split"], "validation")
            async def inline_thread(function, *args):
                # Offline sandbox cannot wake asyncio's executor shutdown pipe.
                # Transport is already doubled; avoid creating an OS worker here.
                return function(*args)

            with patch.object(adapter, "run_worker", return_value={"completion": "99", "model": "cx/gpt-6-astra-max", "receipt": {}}) as transport:
                with patch.object(adapter.asyncio, "to_thread", inline_thread):
                    state = asyncio.run(adapter.deerflow()(InputState(), None))
                transport.assert_called_once_with(InputState.input_text, "frozen", 1)
                self.assertEqual(state.output.completion, "99")
                self.assertTrue(state.completed)
            for ids in ("", "unknown", ["frozen", "frozen"]):
                with self.assertRaises(ValueError):
                    adapter.deerflow_gaia(instance_ids=ids)
            native_task.dataset[0].files = {"/shared_files/asset.pdf": "/private/asset.pdf"}
            with self.assertRaises(ValueError):
                adapter.deerflow_gaia(instance_ids="frozen")

    def test_transport_runs_owned_container_and_retains_failed_attempts(self):
        runner = module("deerflow_run", RECIPE / "e2e/run.py")
        with tempfile.TemporaryDirectory() as tmp:
            state, prefix = Path(tmp) / "state", Path(tmp) / "prefix"
            state.mkdir()
            prefix.mkdir()
            (prefix / "pins.json").write_text((RECIPE / "pins.json").read_text())
            (state / "host.json").write_text(json.dumps({"docker_bin": "docker"}))
            (state / "compose.json").write_text(json.dumps({"services": {"gateway": {
                "environment": {}, "volumes": [{"target": "/work", "source": "placeholder"}],
            }}}))
            invocations = []
            exit_code = 0
            malformed = False

            def native(command, **kwargs):
                invocations.append(command)
                if "compose" in command and "run" in command:
                    if malformed:
                        kwargs["stdout"].write('{"type":"worker-version","data":null}\n')
                        return subprocess.CompletedProcess(command, 0)
                    kwargs["stdout"].write(json.dumps({"type": "values", "data": {"messages": [{"type": "ai", "content": "99"}]}}) + "\n")
                    kwargs["stdout"].write(json.dumps({"type": "end", "data": {}}) + "\n")
                    return subprocess.CompletedProcess(command, exit_code)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(runner, "STATE", state), patch.object(runner, "PREFIX", prefix), \
                    patch.object(runner, "require_rootless"), patch.object(runner.subprocess, "run", native), \
                    patch.object(runner, "compression_snapshot", return_value={"state":"not_applicable"}), \
                    patch.object(runner.Path, "home", return_value=Path(tmp)):
                result = runner.run_worker("unchanged question", "frozen", 1)
                self.assertEqual(result["completion"], "99")
                self.assertNotIn("passed", result)
                self.assertTrue(result["receipt"]["transport"]["ok"])
                self.assertIsNone(result["receipt"]["grader"]["verdict"])
                launch = next(c for c in invocations if "compose" in c and "run" in c)
                self.assertTrue(launch[launch.index("--name") + 1].startswith("rw-deerflow-"))
                self.assertEqual(launch[launch.index("--label") + 1], "com.native-agent-stack.owner=gpt6-omniroute-framework-integration")
                self.assertIn("down", invocations[-1])
                exit_code = 2
                with self.assertRaises(ValueError):
                    runner.run_worker("unchanged question", "frozen", 2)
                malformed = True
                with self.assertRaises(ValueError):
                    runner.run_worker("unchanged question", "frozen", 3)
            runs = list((state / "runs").iterdir())
            self.assertEqual(len(runs), 3)
            self.assertEqual({json.loads((r / "window.json").read_text())["framework_exit_code"] for r in runs}, {0, 2})
            self.assertTrue(all((r / "receipt.json").is_file() for r in runs))

    def test_round3_attempt_has_fresh_state_and_network_and_no_stack_secrets(self):
        runner = module("deerflow_attempt", RECIPE / "e2e/run.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, prefix, run = root / "state", root / "prefix", root / "run"
            (state / "config").mkdir(parents=True)
            for file in ("config.yaml", "extensions_config.json"):
                (state / "config" / file).write_text("{}")
            (state / "qmd-seed").mkdir()
            (state / "qmd-seed" / "snapshot.json").write_text("{}")
            run.mkdir()
            settings = {"variables":{}, "mcp_mounts":[]}
            pins = json.loads((RECIPE / "pins.json").read_text())
            arm = {"arm":"engines-on", "model":"sharedgw/gpt-6-astra-max", "base_url":"http://10.0.2.2:20129/v1"}
            compose = runner.attempt_compose(settings, pins, prefix, state, run, "aabbcc", arm)
            self.assertEqual(compose["name"], "rw-deerflow-e2e-aabbcc")
            self.assertEqual(set(compose["services"]), {"gateway", "egress"})
            svc = compose["services"]["gateway"]
            self.assertNotIn("env_file", svc)
            self.assertNotIn("depends_on", svc)
            self.assertEqual(svc["environment"]["DEERFLOW_BASE_URL"], arm["base_url"])
            self.assertEqual(svc["environment"]["RUNTIME_WORKER_ARM"], "engines-on")
            self.assertEqual(svc["environment"]["DEER_FLOW_STREAM_BRIDGE_REDIS_URL"], "")
            for volume in svc["volumes"]:
                if not volume.get("read_only", False):
                    self.assertTrue(Path(volume["source"]).is_relative_to(run))
                self.assertNotIn("private.env", str(volume))
                self.assertNotIn("redis-password", str(volume))
            self.assertTrue((run / "data/mcp/qmd/snapshot.json").is_file())
            self.assertTrue(all(n["name"].startswith(compose["name"]) for n in compose["networks"].values()))

    def test_gateway_reader_is_read_only_and_uses_only_approved_columns(self):
        receipt = module("deerflow_receipt", RECIPE / "e2e/receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "gateway.sqlite"
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, private_payload, correlation_id)")
                conn.execute("CREATE TABLE secrets (value)")
                conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (1000, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 100, 60, 9, "must-never-be-read", "one"))
                conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (5000, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 1, 0, 0, "outside-window", "two"))
                for stamp in ("1000", "1000.5", "1970-01-01T00:16:40Z"):
                    conn.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (stamp, "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 100, 60, 9, "must-never-be-read", stamp))
            before = db.read_bytes()
            rows = receipt.gateway_rows(db, 999, 1001)
            self.assertEqual(len(rows), 4)
            self.assertEqual(set(rows[0]), set(receipt.COLUMNS) - {"correlation_id"})
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
                {"type": "tool", "tool_call_id": "private-three", "content": "---\nname: search-first\n---\nactual skill instructions"}]}},
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

    def test_native_trace_distinguishes_skill_inventory_metadata_and_loads(self):
        receipt = module("deerflow_skill_trace", RECIPE / "e2e/receipt.py")
        events = [
            {"type": "worker-skills", "data": {"names": ["search-first", "verification-before-completion"]}},
            {"type": "values", "data": {"messages": [
                {"type": "ai", "tool_calls": [
                    {"name": "describe_skill", "id": "metadata", "args": {"name": "verification-before-completion"}},
                    {"name": "read_file", "id": "loaded", "args": {"path": "/mnt/skills/legacy/search-first/SKILL.md"}},
                    {"name": "read_file", "id": "failed", "args": {"path": "/mnt/skills/legacy/verification-before-completion/SKILL.md"}}]},
                {"type": "tool", "tool_call_id": "metadata", "content": "Skill metadata and path"},
                {"type": "tool", "tool_call_id": "loaded", "content": "---\nname: search-first\n---\nActual instructions"},
                {"type": "tool", "tool_call_id": "failed", "content": "The requested SKILL.md could not be opened\nname: verification-before-completion\n"}]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in events))
            found = receipt.observations(path)
        self.assertEqual(found["skills_listed_at_start"], ["search-first", "verification-before-completion"])
        self.assertEqual(found["skill_reads_observed"], ["search-first"])
        self.assertFalse(found["required_skills_activated"])

    def test_round3_usage_correlates_entry_gateway_once_and_separates_effort(self):
        receipt = module("deerflow_usage", RECIPE / "e2e/receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "entry.sqlite"
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id)")
                conn.executemany("INSERT INTO call_logs VALUES (?,?,?,?,?,?,?,?,?,?)", [
                    (1000, "/v1/responses", 200, "sharedgw/gpt-6-astra-max", "max", "max", 100, 60, 9, "private-a"),
                    (1001, "/v1/responses", 200, "gpt-6-astra-max", None, None, 50, 10, 0, "private-b"),
                    (1001, "/v1/responses", 200, "gpt-6-astra-max", "max", "max", 999, 0, 3, "unrelated"),
                    (1001, "/other", 200, "gpt-6-astra-max", "max", "max", 999, 0, 3, "private-a"),
                    (1001, "/v1/responses", 200, "gpt-6-sol-max", "max", "max", 999, 0, 3, "private-a"),
                ])
            result = receipt.gateway_observation(db, {"start_epoch":999, "end_epoch":1002,
                "model":"sharedgw/gpt-6-astra-max", "arm":"engines-on"}, {"private-a", "private-b"})
            self.assertEqual(len(result["rows"]), 2)
            self.assertEqual(result["usage_total"]["tokens_in"], 150)
            self.assertEqual(result["effort"]["with_reasoning_max"], 1)
            self.assertEqual(result["effort"]["no_returned_reasoning"], 1)
            self.assertNotIn("private-", json.dumps(result))
            self.assertNotIn("correlation_id", json.dumps(result["rows"]))
            fallback = receipt.gateway_observation(db, {"start_epoch":999, "end_epoch":1002,
                "model":"sharedgw/gpt-6-astra-max", "arm":"engines-on"}, set())
            self.assertEqual(len(fallback["rows"]), 3)
            self.assertIsNone(fallback["usage_total"])
            self.assertIn("time window + model + path", fallback["scope"])

    def test_model_context_and_container_contract(self):
        config = json.loads((RECIPE / "config.yaml.template").read_text())
        model = config["models"][0]
        self.assertEqual(model["base_url"], "$DEERFLOW_BASE_URL")
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
        with patch.dict("os.environ", {"DEERFLOW_CONVERSATION_ID": "gaia-conversation"}):
            lead = headers.call_headers("lead-thread")
            child = headers.call_headers("child-thread")
            self.assertEqual(lead["x-omniroute-session"], child["x-omniroute-session"])

    def test_gateway_structured_output_uses_upstream_tool_calling(self):
        # External-client double tests only our adapter seam, not LangChain itself.
        class NativeClient:
            def with_structured_output(self, schema, **kwargs):
                return schema, kwargs

            def _get_request_payload(self, input_, **kwargs):
                return copy.deepcopy(input_)

        headers = module("worker_headers", RECIPE / "runtime/gateway_headers.py")
        with patch.dict(sys.modules, {
            "langchain_openai": types.SimpleNamespace(ChatOpenAI=NativeClient),
            "langgraph.config": types.SimpleNamespace(get_config=lambda: {"configurable": {"thread_id": "conversation"}}),
            "gateway_headers": headers,
        }):
            extension = module("worker_model", RECIPE / "runtime/gateway_model.py")
            client = extension.ChatOpenAI()
            schema = {"title": "Answer", "type": "object", "properties": {"answer": {"type": "string"}}}
            for requested in ({}, {"method": "json_mode"}, {"method": "json_schema", "strict": True}):
                returned, args = client.with_structured_output(schema, include_raw=True, **requested)
                self.assertEqual(returned, schema)
                self.assertEqual(args["method"], "function_calling")
                self.assertFalse(args["strict"])
                self.assertTrue(args["include_raw"])
            payload = {"input": [], "temperature": 0.0, "extra_headers": {"custom": "preserved"}}
            one, two = client._get_request_payload(payload), client._get_request_payload(payload)
            self.assertNotIn("temperature", one)
            self.assertEqual(one["reasoning"]["effort"], "max")
            self.assertEqual(one["extra_headers"]["custom"], "preserved")
            self.assertEqual(one["extra_headers"]["x-omniroute-session"], two["extra_headers"]["x-omniroute-session"])
            self.assertNotEqual(one["extra_headers"]["Idempotency-Key"], two["extra_headers"]["Idempotency-Key"])
            for raw in ({"response_format": {"type": "json_object"}},
                        {"text": {"format": {"type": "json_schema"}}}):
                with self.assertRaises(ValueError):
                    client._get_request_payload(raw)

    def test_gateway_rejects_non_gpt6_model_routes(self):
        renderer = module("deerflow_route", RECIPE / "recipe.py")
        self.assertEqual(renderer.worker_model({}), "cx/gpt-6-astra-max")
        self.assertEqual(renderer.worker_model({"model": "cx/gpt-6-sol-max"}), "cx/gpt-6-sol-max")
        for model in ("claude-opus-5-5", "cx/claude-opus-5-5", "cx/gpt-next-max", "gpt-6"):
            with self.assertRaises(ValueError):
                renderer.worker_model({"model": model})

    def test_round3_arms_render_endpoint_model_and_only_selected_header(self):
        renderer = module("deerflow_arms", RECIPE / "recipe.py")
        headers = module("deerflow_arm_headers", RECIPE / "runtime/gateway_headers.py")
        for arm, model, port in (("control", "cx/gpt-6-astra-max", 20128),
                                 ("engines-on", "sharedgw/gpt-6-astra-max", 20129)):
            with patch.dict("os.environ", {"RUNTIME_WORKER_ARM": arm}):
                selection = renderer.arm_settings({})
                self.assertEqual(selection["arm"], arm)
                self.assertEqual(selection["model"], model)
                self.assertEqual(selection["base_url"], f"http://10.0.2.2:{port}/v1")
                self.assertEqual(selection["host_base_url"], f"http://127.0.0.1:{port}/v1")
                self.assertEqual(selection["reasoning_effort"], "max")
                actual = headers.call_headers("same-thread")
                self.assertNotIn("X-OmniRoute-No-Cache", actual)
                self.assertEqual(actual.get("x-omniroute-compression"),
                                 "allow-lossy" if arm == "engines-on" else None)
                self.assertEqual(selection["header_names"], sorted(actual))
                with tempfile.TemporaryDirectory() as tmp:
                    settings = {"variables":{"ECO_ROOT":"/opt/eco", "HOST_PATH":"/usr/bin", "QDRANT_URL":"10.0.2.2:16333", "EMBED_URL":"10.0.2.2:18232"}, "mcp_mounts":[], "session_namespace":"fixture"}
                    compose = renderer.render(settings, Path(tmp) / "prefix", Path(tmp) / "state")
                    labels = compose["services"]["gateway"]["labels"]
                    self.assertEqual(labels["com.native-agent-stack.arm"], arm)
                    self.assertEqual(labels["com.native-agent-stack.model"], model)
        self.assertEqual(renderer.worker_model({"model": "sharedgw/gpt-6-astra-max"}),
                         "sharedgw/gpt-6-astra-max")
        for value in ("sharedgw/cx/gpt-6-astra-max", "sharedgw/gpt-6-sol-max"):
            with self.assertRaises(ValueError):
                renderer.worker_model({"model": value})
        with self.assertRaises(ValueError):
            renderer.arm_settings({}, "invalid")
        with self.assertRaises(ValueError):
            renderer.arm_settings({"model": "sharedgw/gpt-6-astra-max"}, "control")


    def test_skills_use_coordinator_project_installer(self):
        renderer = module("deerflow_skills", RECIPE / "recipe.py")
        with tempfile.TemporaryDirectory() as tmp, patch.object(renderer.subprocess, "run") as run:
            workspace = Path(tmp) / "worker"
            renderer.install_skills(workspace)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [
                sys.executable, str(ROOT / "tools/adoption/install_skills.py"),
                "--manifest", str(ROOT / "blueprints/runtime-workers/skills/manifest.json"),
                "--project-dir", str(workspace), "--agent", "universal",
            ])
            self.assertTrue(run.call_args.kwargs["check"])
        source = (RECIPE / "recipe.py").read_text()
        self.assertNotIn('skills_root', source)
        self.assertNotIn('symlink_to', source)
        self.assertIn('mount(state / "work/.agents/skills", "/skills/custom")', source)

    def test_grader_install_and_launch_use_exact_upstream_pins(self):
        renderer = module("deerflow_grader_install", RECIPE / "recipe.py")
        with tempfile.TemporaryDirectory() as tmp, patch.object(renderer.subprocess, "run") as run, \
                patch.object(renderer, "sys", LOCK_TARGET_PYTHON):
            prefix = Path(tmp)
            renderer.install_grader(prefix)
            commands = [c.args[0] for c in run.call_args_list]
            self.assertIn([sys.executable, "-m", "venv", str(prefix / "grader")], commands)
            self.assertTrue(any(c[:4] == [str(prefix / "grader/bin/python"), "-m", "pip", "install"] for c in commands))
        requirements = (RECIPE / "e2e/requirements.txt").read_text()
        self.assertIn("inspect-evals[gaia]==0.22.0", requirements)
        self.assertIn("inspect-ai==0.3.271", requirements)
        launch = (RECIPE / "run-e2e.sh").read_text() + (RECIPE / "e2e/evaluate.py").read_text()
        self.assertIn("grader/bin/inspect", launch)
        self.assertIn("gaia.py@deerflow_gaia", launch)
        self.assertIn('"--max-samples", "1"', launch)
        self.assertNotIn("check.py", launch)

    def test_round3_inspect_launch_has_no_model_and_publishes_stable_result(self):
        supervisor = module("deerflow_eval_supervisor", RECIPE / "e2e/evaluate.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, prefix = root / "state", root / "prefix"
            state.mkdir()
            (state / "host.json").write_text("{}")
            def inspect(command, **kwargs):
                self.assertEqual(command[command.index("--model") + 1], "none")
                self.assertNotIn("--model-base-url", command)
                self.assertEqual(command[command.index("--log-format") + 1], "json")
                run = state / "runs/frozen-run"
                self.assertTrue((run / "status.json").is_file())
                logdir = Path(command[command.index("--log-dir") + 1])
                logdir.mkdir(exist_ok=True)
                (logdir / "native.json").write_text(json.dumps({"status":"success",
                    "results":{"total_samples":1, "completed_samples":1,
                        "scores":[{"name":"gaia_scorer", "metrics":{"accuracy":{"value":0}}}]}}))
                return subprocess.CompletedProcess(command, 0)
            with patch.object(supervisor, "STATE", state), patch.object(supervisor, "PREFIX", prefix), \
                    patch.object(supervisor.subprocess, "run", inspect):
                self.assertEqual(supervisor.evaluate("gaia-id", "frozen-run", "control", 1), 1)
            result = json.loads((state / "runs/frozen-run/result.json").read_text())
            self.assertEqual(result["verdict"], "negative")
            self.assertEqual(result["inspect_exit_code"], 0)
            self.assertTrue(Path(result["inspect_log"]).is_file())
            self.assertEqual(result["arm"], "control")

    def test_round3_inspect_verdict_rejects_incomplete_evidence(self):
        supervisor = module("deerflow_eval_verdict", RECIPE / "e2e/evaluate.py")
        success = {"status":"success", "results":{"total_samples":1,"completed_samples":1,
            "scores":[{"name":"gaia_scorer", "metrics":{"accuracy":{"value":1}}}]}}
        self.assertEqual(supervisor.verdict(success, False), (3, "incomplete"))
        self.assertEqual(supervisor.verdict(success, True), (0, "pass"))
        for missing in ({}, {"status":"error"}, {"status":"success", "results":{"scores":[]}}):
            self.assertEqual(supervisor.verdict(missing, True), (3, "incomplete"))

    def test_round3_dispatch_start_wait_result_uses_pat_native_runs_and_stable_paths(self):
        dispatch = module("deerflow_dispatch", RECIPE / "dispatch.py")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "host.json").write_text("{}")
            requests = []
            status = "running"
            def api(method, path, body=None, headers=None):
                requests.append((method,path,body,headers))
                if path == "/threads":
                    self.assertTrue((state / "dispatch/stable/status.json").exists())
                    return {"thread_id":"native-thread"}, "trace-thread"
                if method == "POST" and path.endswith("/runs"):
                    return {"thread_id":"native-thread", "run_id":"native-run", "status":"pending"}, "trace-run"
                if path.endswith("/messages?limit=200"):
                    # Native RunEvent envelope, journal.py:13,124,153-173.
                    return {"data":[{"seq":1,"category":"message", "event_type":"llm.ai.response",
                        "metadata":{"caller":"lead_agent"}, "content":{"type":"ai",
                        "content":[{"type":"text","text":"answer"}],
                        "response_metadata":{"headers":{"x-correlation-id":"private-correlation"}}}}], "has_more":False}, "trace-result"
                if path.endswith("/cancel"):
                    return {}, "trace-cancel"
                return {"status":status,"llm_call_count":1,"total_input_tokens":12,
                    "total_output_tokens":4,"total_tokens":16,"message_count":2,"stop_reason":"completed","updated_at":"2026-09-27T00:00:00Z"}, "trace-wait"
            with patch.object(dispatch, "STATE", state), patch.object(dispatch, "api", api), \
                    patch.object(dispatch, "require_server_arm"), \
                    patch.object(dispatch, "gateway_observation", return_value={"evidence_complete":True,"usage_total":{"tokens_in":12}}):
                code, pointers = dispatch.start("stable", "control", "question", "pro", "workflow/stage")
                self.assertEqual(code, 0)
                self.assertEqual(Path(pointers["result_path"]), state / "dispatch/stable/result.json")
                post = requests[1]
                self.assertEqual(post[0:2], ("POST", "/threads/native-thread/runs"))
                self.assertEqual(post[2]["context"], {"thinking_enabled":True,"is_plan_mode":True,
                    "subagent_enabled":False,"thread_id":"native-thread","model_name":"worker"})
                self.assertEqual(post[2]["on_disconnect"], "continue")
                self.assertEqual(post[2]["metadata"]["caller"], "workflow/stage")
                self.assertIn("Idempotency-Key", post[3])
                self.assertEqual(dispatch.wait_run("stable", "control", 0, 1)[0], 3)
                status = "success"
                wait_code, waited = dispatch.wait_run("stable", "control", 0, 1)
                self.assertEqual(wait_code, 0)
                self.assertEqual(waited["stop_reason"], "completed")
                code, result = dispatch.result_run("stable", "control")
                self.assertEqual(code, 0)
                self.assertEqual(result["answer"], "answer")
                receipt = json.loads((state / "dispatch/stable/receipt.json").read_text())
                self.assertNotIn("private-correlation", json.dumps(receipt))
                self.assertNotIn("native-run", json.dumps(receipt))
                self.assertEqual(receipt["server_reported"]["llm_call_count"], 1)
                with self.assertRaises(ValueError):
                    dispatch.start("stable", "control", "another", "pro", "workflow/stage")
                with self.assertRaises(ValueError):
                    dispatch.result_run("stable", "engines-on")
            ledger = (state / "dispatch.jsonl").read_text().splitlines()
            self.assertEqual(len(ledger), 1)
            self.assertEqual((state / "dispatch.jsonl").stat().st_mode & 0o777, 0o600)

    def test_round3_dispatch_reports_negative_setup_and_missing_evidence(self):
        dispatch = module("deerflow_dispatch_failures", RECIPE / "dispatch.py")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "host.json").write_text("{}")
            with patch.object(dispatch, "STATE", state), patch.object(dispatch, "require_server_arm", side_effect=ValueError("wrong arm")):
                code, value = dispatch.start("wrong-arm", "engines-on", "question", "ultra", "child")
                self.assertEqual(code, 2)
                self.assertTrue((state / "dispatch/wrong-arm/status.json").is_file())
            with patch.object(dispatch, "STATE", state):
                run = state / "dispatch/negative"
                run.mkdir()
                dispatch.write(run / "status.json", {"arm":"control", "thread_id":"t", "run_id":"r", "status":"running"})
                with patch.object(dispatch, "api", return_value=({"status":"error"}, "trace")):
                    self.assertEqual(dispatch.wait_run("negative", "control", 0, 1)[0], 1)
                with patch.object(dispatch, "api", return_value=({"status":"interrupted"}, "trace")):
                    self.assertEqual(dispatch.wait_run("negative", "control", 0, 1)[0], 3)

    def test_round3_compression_deltas_are_separate_and_reject_counter_resets(self):
        receipt = module("deerflow_compression", RECIPE / "e2e/receipt.py")
        before = {"state":"observed", "totalRequests":5,"totalTokensSaved":100,"totalSkipped":2}
        after = {"state":"observed", "totalRequests":7,"totalTokensSaved":140,"totalSkipped":3}
        delta = receipt.compression_delta(before, after)
        self.assertEqual(delta["delta"], {"totalRequests":2,"totalTokensSaved":40,"totalSkipped":1})
        self.assertIn("not provider usage", delta["scope"])
        self.assertIsNone(receipt.compression_delta(after, before)["delta"])
        with patch.object(receipt, "urlopen", side_effect=AssertionError("control must not request analytics")):
            self.assertEqual(receipt.compression_snapshot("control")["state"], "not_applicable")

    def test_round3_grader_install_is_hash_locked_and_wheel_only(self):
        renderer = module("deerflow_locked_grader", RECIPE / "recipe.py")
        import hashlib
        lock = RECIPE / "e2e/requirements.lock"
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(hashlib.sha256(lock.read_bytes()).hexdigest(), pins["grader"]["lock_sha256"])
        for requirement in lock.read_text().replace("\\\n", "").splitlines():
            if requirement.strip() and not requirement.lstrip().startswith("#"):
                self.assertRegex(requirement, r"==[^ ]+.*--hash=sha256:[0-9a-f]{64}")
        with tempfile.TemporaryDirectory() as tmp, patch.object(renderer.subprocess, "run") as run, \
                patch.object(renderer, "sys", LOCK_TARGET_PYTHON):
            renderer.install_grader(Path(tmp))
            install = next(c.args[0] for c in run.call_args_list if "install" in c.args[0])
            for arg in ("--require-hashes", "--only-binary=:all:", "--no-deps"):
                self.assertIn(arg, install)
            self.assertEqual(install[-1], str(lock))

    def test_grader_install_refuses_an_interpreter_the_lock_does_not_target(self):
        renderer = module("deerflow_grader_guard", RECIPE / "recipe.py")
        other = types.SimpleNamespace(executable=sys.executable, version_info=(3, 12, 3, "final", 0))
        with tempfile.TemporaryDirectory() as tmp, patch.object(renderer.subprocess, "run") as run, \
                patch.object(renderer, "sys", other):
            with self.assertRaisesRegex(ValueError, "CPython 3.13"):
                renderer.install_grader(Path(tmp))
            run.assert_not_called()

    def test_round3_container_network_hardening_and_resolved_mount_guards(self):
        renderer = module("deerflow_security", RECIPE / "recipe.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = {"variables": {"ECO_ROOT": str(root / "eco"), "HOST_PATH": "/usr/bin",
                        "QDRANT_URL": "10.0.2.2:16333", "EMBED_URL": "10.0.2.2:18232"},
                        "mcp_mounts": [], "session_namespace": "fixture"}
            compose = renderer.render(settings, root / "prefix", root / "state")
            self.assertTrue(compose["networks"]["default"]["internal"])
            self.assertEqual(compose["services"]["gateway"]["networks"], ["default"])
            self.assertEqual(set(compose["services"]["egress"]["networks"]), {"default", "egress"})
            for service in compose["services"].values():
                self.assertEqual(service["cap_drop"], ["ALL"])
                self.assertIn("no-new-privileges:true", service["security_opt"])
                self.assertTrue(service["read_only"])
            proxy = (root / "state/config/egress.conf").read_text()
            self.assertIn("http://10.0.2.2:20128", proxy)
            self.assertNotIn("20129", proxy)
            self.assertIn("return 403", proxy)
            self.assertIn("$upstream_http_x_correlation_id", proxy)
            self.assertIn("proxy_buffering off", proxy)
            ext = json.loads((root / "state/config/extensions_config.json").read_text())["mcpServers"]
            self.assertFalse(ext["ai-memory"]["enabled"])
            self.assertFalse(ext["socraticode"]["enabled"])
            self.assertEqual(ext["serena"]["args"][ext["serena"]["args"].index("--enable-web-dashboard") + 1], "false")
            home = root / "home"
            forbidden = home / ".config/native-agent-stack"
            forbidden.mkdir(parents=True)
            allowed = root / "eco/bin"
            allowed.parent.mkdir()
            allowed.symlink_to(forbidden, target_is_directory=True)
            with patch.object(renderer.Path, "home", return_value=home):
                for source in (home.parent, home / ".config", forbidden, allowed):
                    settings["mcp_mounts"] = [{"source":str(source), "target":str(source), "read_only":True}]
                    with self.assertRaises(ValueError):
                        renderer.render(settings, root / "prefix", root / "state")
        self.assertIn("requirepass", (RECIPE / "runtime/redis-start.sh").read_text())

    def test_round3_lifecycle_rejects_active_dispatch_and_recreates_selected_arm(self):
        renderer = module("deerflow_lifecycle_arm", RECIPE / "recipe.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            (state / "host.json").write_text("{}")
            run = state / "dispatch/active"
            run.mkdir(parents=True)
            (run / "status.json").write_text('{"status":"running"}')
            with patch.object(renderer, "STATE", state), patch.object(renderer, "PREFIX", root / "prefix"), \
                    patch.object(renderer, "require_rootless"), patch.object(renderer, "render") as render, \
                    patch.object(renderer, "docker") as docker:
                with self.assertRaises(ValueError):
                    renderer.lifecycle("up")
                docker.assert_not_called()
                (run / "status.json").write_text('{"status":"success"}')
                renderer.lifecycle("up")
                render.assert_called_once()
                self.assertIn("--force-recreate", docker.call_args.args)
        template = json.loads((RECIPE / "config.yaml.template").read_text())
        self.assertTrue(template["models"][0]["include_response_headers"])
        self.assertEqual(template["models"][0]["openai_proxy"], "http://egress:3128")

    def test_round3_nginx_and_preflight_match_hardened_configuration(self):
        compose = json.loads((RECIPE / "compose.json.template").read_text())
        self.assertFalse(any(m.startswith("/etc/nginx:") for m in compose["services"]["nginx"]["tmpfs"]))
        self.assertEqual(compose["services"]["nginx"]["user"], "101:101")
        script = (RECIPE / "runtime/nginx-start.sh").read_text()
        self.assertIn("/tmp/nginx.conf", script)
        self.assertIn("/tmp/nginx.pid", script)
        preflight = (RECIPE / "runtime/preflight.py").read_text()
        self.assertIn("server_config.enabled", preflight)

    def test_round3_installed_entrypoints_have_their_local_dependencies(self):
        renderer = module("deerflow_entrypoints", RECIPE / "recipe.py")
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            renderer.install_entrypoints(prefix)
            for name in ("deerflow-run", "dispatch.py", "recipe.py", "defaults.json", "pins.json", "run-e2e.sh", "lifecycle.sh", "egress.conf.template"):
                self.assertEqual((prefix / name).read_bytes(), (RECIPE / name).read_bytes())
            self.assertEqual((prefix / "deerflow-run").stat().st_mode & 0o777, 0o700)

    def test_round3_dispatch_pat_uses_header_and_refuses_redirects_and_unsafe_token_files(self):
        dispatch = module("deerflow_pat", RECIPE / "dispatch.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            token = root / "pat"
            token.write_text("dfp_" + "a" * 40)
            token.chmod(0o600)
            class Response:
                headers = {"X-Trace-Id":"private-trace"}
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, bound): return b'{"thread_id":"fixture"}'
            class Opener:
                def open(inner, request, timeout):
                    self.assertEqual(request.full_url, "http://127.0.0.1:3771/api/langgraph/threads")
                    self.assertEqual(request.get_header("Authorization"), "Bearer dfp_" + "a" * 40)
                    return Response()
            with patch.dict("os.environ", {"DEERFLOW_PAT_FILE":str(token), "DEERFLOW_URL":"http://127.0.0.1:3771"}), \
                    patch.object(dispatch, "REPO", root / "checkout"), \
                    patch.object(dispatch, "build_opener", return_value=Opener()):
                self.assertEqual(dispatch.api("POST", "/threads", {})[0], {"thread_id":"fixture"})
                token.chmod(0o644)
                with self.assertRaises(ValueError):
                    dispatch.api("POST", "/threads", {})
                token.chmod(0o600)
                with patch.dict("os.environ", {"DEERFLOW_URL":"http://example.com"}):
                    with self.assertRaises(ValueError):
                        dispatch.api("POST", "/threads", {})
            self.assertIsNone(dispatch.NoRedirect().redirect_request(None, None, 302, None, {}, "http://example.com"))

    def test_round3_dispatch_cli_accepts_prompt_after_options(self):
        dispatch = module("deerflow_dispatch_cli", RECIPE / "dispatch.py")
        with patch.object(sys, "argv", ["deerflow-run", "start", "--run-id", "frozen", "--arm", "control", "literal prompt"]), \
                patch.object(dispatch, "start", return_value=(0, {"result_path":"fixture"})) as start:
            self.assertEqual(dispatch.main(), 0)
            start.assert_called_once_with("frozen", "control", "literal prompt", "pro", "claude-code/workflow")

    def test_round3_dispatch_ambiguous_start_is_incomplete_and_retries_same_native_key(self):
        dispatch = module("deerflow_dispatch_retry", RECIPE / "dispatch.py")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "host.json").write_text("{}")
            keys = []
            calls = 0
            def api(method, path, body=None, headers=None):
                nonlocal calls
                if path == "/threads":
                    return {"thread_id":"t"}, "trace"
                keys.append(headers["Idempotency-Key"])
                calls += 1
                if calls == 1:
                    raise TimeoutError("response lost after native create")
                return {"run_id":"r", "status":"pending"}, "trace"
            with patch.object(dispatch, "STATE", state), patch.object(dispatch, "api", api), patch.object(dispatch, "require_server_arm"):
                code, pointers = dispatch.start("retry", "control", "prompt", "pro", "child")
                self.assertEqual(code, 3)
                self.assertEqual(json.loads((state / "dispatch/retry/status.json").read_text())["status"], "pending")
                self.assertEqual(dispatch.start("retry", "control", "prompt", "pro", "child")[0], 0)
            self.assertEqual(len(keys), 2)
            self.assertEqual(keys[0], keys[1])
            self.assertEqual(len((state / "dispatch.jsonl").read_text().splitlines()), 1)

    def test_round3_missing_host_setup_still_writes_status_and_result(self):
        dispatch = module("deerflow_missing_setup", RECIPE / "dispatch.py")
        supervisor = module("deerflow_missing_grader_setup", RECIPE / "e2e/evaluate.py")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            with patch.object(dispatch, "STATE", state):
                code, result = dispatch.start("missing", "control", "prompt", "pro", "child")
                self.assertEqual(code, 2)
                self.assertTrue((state / "dispatch/missing/status.json").is_file())
                self.assertEqual(json.loads((state / "dispatch/missing/result.json").read_text())["exit_code"], 2)
            with patch.object(supervisor, "STATE", state), patch.object(supervisor.subprocess, "run") as native:
                self.assertEqual(supervisor.evaluate("frozen", "missing", "control", 1), 2)
                native.assert_not_called()
                self.assertTrue((state / "runs/missing/status.json").is_file())

    def test_round3_duplicate_correlation_is_incomplete_and_dispatch_counts_are_sanitized(self):
        receipt = module("deerflow_duplicate_correlation", RECIPE / "e2e/receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "duplicate.sqlite"
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id)")
                conn.executemany("INSERT INTO call_logs VALUES (?,?,?,?,?,?,?,?,?,?)", [
                    (1000,"/v1/responses",200,"gpt-6-astra-max","max","max",10,0,1,"duplicate"),
                    (1000,"/v1/responses",200,"gpt-6-astra-max","max","max",20,0,1,"duplicate")])
            found = receipt.gateway_observation(db, {"start_epoch":999,"end_epoch":1001,"model":"cx/gpt-6-astra-max"}, {"duplicate"})
            self.assertIsNone(found["usage_total"])
            self.assertFalse(found["evidence_complete"])
        dispatch = module("deerflow_counter_sanitization", RECIPE / "dispatch.py")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            run = state / "dispatch/counters"
            run.mkdir(parents=True)
            dispatch.write(run / "status.json", {"arm":"control", "thread_id":"t", "run_id":"r"})
            with patch.object(dispatch, "STATE", state), patch.object(dispatch, "api", return_value=(
                    {"status":"success", "llm_call_count":"private-text", "total_tokens":-1}, "trace")):
                code, result = dispatch.wait_run("counters", "control", 0, 1)
                self.assertNotIn("private-text", json.dumps(result))
                self.assertIsNone(result["total_tokens"])

    @unittest.skipUnless(importlib.util.find_spec("inspect_ai") and importlib.util.find_spec("inspect_evals"),
                         "pinned upstream grader unavailable; installation prohibited in builder")
    def test_real_upstream_gaia_known_pass_and_fail_controls(self):
        import importlib.metadata
        from inspect_ai.model import ChatMessageUser, ModelName
        from inspect_ai.scorer import CORRECT, INCORRECT, Target
        from inspect_ai.solver import TaskState
        from inspect_evals.gaia.scorer import gaia_scorer
        self.assertEqual(importlib.metadata.version("inspect-evals"), "0.22.0")
        self.assertEqual(importlib.metadata.version("inspect-ai"), "0.3.271")
        adapter = module("deerflow_real_controls", RECIPE / "e2e/check.py")

        async def controls():
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.jsonl"
                for answer, expected in (("42", CORRECT), ("99", INCORRECT)):
                    path.write_text(json.dumps({"type": "values", "data": {"messages": [{"type": "ai", "content": answer}]}})
                                    + "\n" + json.dumps({"type": "end", "data": {}}))
                    state = TaskState(model=ModelName("mockllm/model"), sample_id="transport-control", epoch=1,
                                      input="test input", messages=[ChatMessageUser(content="test input")])
                    state.output.completion = adapter.read_completion(path)
                    score = await gaia_scorer()(state, Target("42"))
                    self.assertEqual(score.value, expected)
        asyncio.run(controls())

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
            "e2e/check.py", "e2e/gaia.py", "e2e/task.md", "e2e/receipt.py",
        ):
            with self.subTest(file=name):
                self.assertTrue((RECIPE / name).is_file(), name)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(RECIPE / "e2e/check.py"), tmp],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["transport_ok"], False)


if __name__ == "__main__":
    unittest.main()
