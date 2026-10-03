"""Synthetic integration controls; no provider calls or native session claims."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
)
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

SCRIPT = Path(__file__).resolve().parents[1] / "worker.py"
SPEC = importlib.util.spec_from_file_location("claude_runtime_worker", SCRIPT)
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)
# Construct a reproducible fixture identity; never publish a native session ID.
SESSION = str(uuid.uuid5(uuid.NAMESPACE_DNS, "claude-runtime-sdk.synthetic-session"))


def result(**kwargs):
    fields = {
        "subtype": "success",
        "duration_ms": 10,
        "duration_api_ms": 5,
        "is_error": False,
        "num_turns": 1,
        "session_id": SESSION,
        "terminal_reason": "completed",
        "result": "fixture result",
    }
    fields.update(kwargs)
    return ResultMessage(**fields)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def options(self, *args):
        return worker.build_options(worker.parser().parse_args(["--cwd", str(self.cwd), *args]))

    def command(self, options):
        # Build SDK argv only. This synthetic executable is never launched.
        options.cli_path = sys.executable
        return SubprocessCLITransport(prompt="fixture", options=options)._build_command()

    def test_native_transport_has_full_preset_and_scoped_route(self):
        options = self.options()
        command = self.command(options)
        self.assertEqual(command[command.index("--model") + 1], worker.DEFAULT_MODEL)
        self.assertEqual(command[command.index("--effort") + 1], "max")
        self.assertNotIn("--tools", command)
        self.assertEqual(options.system_prompt, {"type": "preset", "preset": "claude_code"})
        self.assertEqual(options.env["ANTHROPIC_BASE_URL"], worker.DEFAULT_GATEWAY)
        self.assertEqual(options.env["ANTHROPIC_AUTH_TOKEN"], "omniroute-no-auth")
        self.assertEqual(options.env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"], "1")
        self.assertNotIn("ANTHROPIC_API_KEY", options.env)
        self.assertIsNone(options.fallback_model)
        self.assertNotIn("190000", str(options))

    def test_exact_skills_use_native_permissions_without_body_preload(self):
        options = self.options("--skill", "search-first", "--skill", "context-mode:context-mode")
        command = self.command(options)
        grants = command[command.index("--allowedTools") + 1]
        self.assertIn("Skill(search-first)", grants)
        self.assertIn("Skill(context-mode:context-mode)", grants)
        self.assertNotIn("--tools", command)
        self.assertEqual(options.allowed_tools, [])
        self.assertIsNone(options.agents)
        self.assertIn("--setting-sources=user,project", command)
        self.assertNotIn("SKILL.md", " ".join(command))

    def test_all_skills_keeps_native_discovery(self):
        options = self.options("--skill", "all")
        command = self.command(options)
        self.assertEqual(command[command.index("--allowedTools") + 1], "Skill")
        self.assertEqual(options.skills, "all")
        self.assertEqual(options.allowed_tools, [])

    def test_project_only_selected_plugin_and_mcp_path(self):
        plugin = self.cwd / "plugin"
        plugin.mkdir()
        mcp = self.cwd / "mcp.json"
        mcp.write_text('{"mcpServers":{}}')
        options = self.options(
            "--setting-source",
            "project",
            "--plugin",
            str(plugin),
            "--mcp-config",
            str(mcp),
            "--allow-tool",
            "Read",
        )
        read_text = Path.read_text

        def observe_read(path, *args, **kwargs):
            if path == mcp:
                raise AssertionError("no caller settings reads")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", observe_read):
            summary = worker.preflight(options)
        command = self.command(options)
        self.assertIn("--setting-sources=project", command)
        self.assertIn("--plugin-dir", command)
        self.assertIn("--mcp-config", command)
        self.assertTrue(summary["tools_unrestricted"])
        self.assertEqual(summary["plugin_count"], 1)
        self.assertNotIn(str(self.cwd), str(summary))

    def test_wrong_family_is_rejected_without_substitution(self):
        for model in ("gpt-6.1-sol", "openai/gpt-6.1-sol", "opus", "gpt-claude-opus-5"):
            with (
                self.subTest(model=model),
                self.assertRaisesRegex(ValueError, "Claude-family"),
            ):
                self.options("--model", model)

    def test_wrong_route_is_rejected_before_a_client_exists(self):
        for gateway in (
            "https://api.anthropic.com",
            "http://127.0.0.1:20128/v1",
            "http://user:fixture-secret@127.0.0.1:20128",
            "http://127.0.0.1:20128?token=fixture-secret",
            "http://127.0.0.1:99999",
        ):
            with self.subTest(gateway=gateway), self.assertRaises(ValueError):
                self.options("--gateway", gateway)

    def test_inherited_effort_fails_closed_and_is_not_printed(self):
        os.environ["CLAUDE_CODE_EFFORT_LEVEL"] = "fixture-private-value"
        with self.assertRaises(ValueError) as raised:
            self.options()
        self.assertNotIn("fixture-private-value", str(raised.exception))
        self.assertEqual(os.environ["CLAUDE_CODE_EFFORT_LEVEL"], "fixture-private-value")

    def test_parent_environment_and_credentials_stay_opaque(self):
        os.environ.update(
            {
                "ANTHROPIC_BASE_URL": "https://fixture-native.invalid",
                "ANTHROPIC_AUTH_TOKEN": "opaque-fixture",
            }
        )
        before = dict(os.environ)
        self.options()
        self.assertEqual(dict(os.environ), before)

    def test_native_anthropic_keys_are_removed_from_worker_scope(self):
        os.environ.update(
            {
                "ANTHROPIC_API_KEY": "opaque-native-fixture",
                "ANTHROPIC_AUTH_TOKEN": "opaque-native-fixture",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "fixture-native-model",
                "UNRELATED_FIXTURE": "retained",
            }
        )
        options = self.options()
        self.assertEqual(worker.prepare_worker_environment(), 3)
        self.assertFalse(any(name.startswith("ANTHROPIC_") for name in os.environ))
        self.assertEqual(os.environ["UNRELATED_FIXTURE"], "retained")
        self.assertEqual(options.env["ANTHROPIC_AUTH_TOKEN"], "omniroute-no-auth")

    def test_gateway_specific_binding_remains_opaque(self):
        os.environ["OMNIROUTE_FIXTURE_TOKEN"] = "opaque-gateway-fixture"
        options = self.options("--gateway-token-env", "OMNIROUTE_FIXTURE_TOKEN")
        summary = worker.preflight(options)
        self.assertEqual(options.env["ANTHROPIC_AUTH_TOKEN"], "opaque-gateway-fixture")
        self.assertNotIn("opaque-gateway-fixture", str(summary))

    def test_missing_or_native_token_binding_fails_closed(self):
        for binding in (
            "OMNIROUTE_ABSENT_FIXTURE",
            "ANTHROPIC_AUTH_TOKEN",
            "invalid fixture",
        ):
            with self.subTest(binding=binding), self.assertRaises(ValueError):
                self.options("--gateway-token-env", binding)

    def test_resume_passes_native_identity_and_no_new_fork_by_default(self):
        options = self.options("--resume", SESSION)
        command = self.command(options)
        self.assertIn("--resume=" + SESSION, command)
        self.assertNotIn("--fork-session", command)
        with self.assertRaisesRegex(ValueError, "UUID"):
            self.options("--resume", "/private/transcript.jsonl")

    def test_nonexistent_cwd_plugin_and_mixed_skill_selection_fail(self):
        for args in (
            ["--plugin", str(self.cwd / "absent")],
            ["--skill", "all", "--skill", "search-first"],
            ["--cwd", str(self.cwd / "absent")],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.options(*args)


class AccountingTests(unittest.TestCase):
    def test_cumulative_snapshots_replace_without_cache_double_count(self):
        observation = worker.Observation()
        first = result(
            usage={"input_tokens": 3, "cache_read_input_tokens": 9},
            model_usage={"claude-fixture": {"inputTokens": 100, "cacheReadInputTokens": 60}},
            total_cost_usd=0.1,
        )
        last = result(
            usage={"input_tokens": 4, "cache_read_input_tokens": 12},
            model_usage={"claude-fixture": {"inputTokens": 180, "cacheReadInputTokens": 90}},
            total_cost_usd=0.2,
        )
        observation.observe(first)
        observation.observe(last)
        summary = observation.summary()
        self.assertEqual(
            summary["model_usage_latest_session_snapshot"]["claude-fixture"]["inputTokens"],
            180,
        )
        self.assertNotEqual(
            summary["model_usage_latest_session_snapshot"]["claude-fixture"]["inputTokens"],
            280,
        )
        self.assertEqual(summary["usage_last_native_result"]["input_tokens"], 4)
        self.assertEqual(summary["usage_last_native_result"]["cache_read_input_tokens"], 12)
        self.assertFalse(summary["cache_counters_added_to_input"])
        self.assertEqual(summary["native_reported_cost_usd"], 0.2)
        self.assertIsNone(summary["billing_cost_usd"])

    def test_unknown_counters_replace_prior_known_values_with_unknown(self):
        observation = worker.Observation()
        observation.observe(
            result(
                usage={"input_tokens": 1},
                model_usage={"claude-fixture": {"inputTokens": 1}},
                total_cost_usd=0.01,
            )
        )
        observation.observe(result())
        summary = observation.summary()
        self.assertIsNone(summary["usage_last_native_result"])
        self.assertIsNone(summary["model_usage_latest_session_snapshot"])
        self.assertIsNone(summary["native_reported_cost_usd"])

    def test_result_and_arbitrary_usage_fields_are_omitted(self):
        observation = worker.Observation()
        observation.observe(
            result(
                result="fixture-private-result",
                usage={"arbitrary": "fixture-private-value", "input_tokens": 5},
            )
        )
        summary = observation.summary()
        self.assertNotIn("fixture-private", str(summary))
        self.assertEqual(summary["result_bytes"], len("fixture-private-result"))
        self.assertEqual(summary["usage_last_native_result"], {"input_tokens": 5})

    def test_skill_event_preserves_identity_without_args_or_body(self):
        observation = worker.Observation()
        observation.observe(
            AssistantMessage(
                content=[
                    ToolUseBlock(
                        id="fixture-call",
                        name="Skill",
                        input={"skill": "bridge-proof", "args": "fixture-private-text"},
                    )
                ],
                model="claude-fixture",
            )
        )
        summary = observation.summary()
        self.assertEqual(
            summary["tool_events"],
            [{"id": "fixture-call", "name": "Skill", "skill": "bridge-proof"}],
        )
        self.assertNotIn("fixture-private-text", str(summary))

    def test_snapshot_is_detached_from_summary_mutation(self):
        observation = worker.Observation()
        observation.observe(result(model_usage={"claude-fixture": {"inputTokens": 180}}))
        summary = observation.summary()
        summary["model_usage_latest_session_snapshot"]["claude-fixture"]["inputTokens"] = 999
        self.assertEqual(observation.model_usage["claude-fixture"]["inputTokens"], 180)


class SyntheticClient:
    """Native-client-shaped control fixture; not an SDK or provider run."""

    def __init__(self, *, wait=False, missing=False, error=False, terminal="completed"):
        self.wait, self.missing, self.error = wait, missing, error
        self.interrupted = False
        self.events = []
        self.terminal = terminal
        self.signal = anyio.Event()

    async def __aenter__(self):
        self.events.append("connect")
        return self

    async def __aexit__(self, *exc):
        self.events.append("disconnect")

    async def query(self, prompt):
        self.events.append("query")
        if self.error:
            raise RuntimeError("fixture-secret /private/path")

    async def interrupt(self):
        self.events.append("interrupt")
        self.interrupted = True
        self.signal.set()

    async def receive_response(self):
        if self.wait and not self.interrupted:
            await self.signal.wait()
        yield SystemMessage(
            subtype="init",
            data={
                "session_id": SESSION,
                "tools": ["Read", "Skill"],
                "skills": ["fixture"],
            },
        )
        if not self.missing:
            yield AssistantMessage(
                content=[ToolUseBlock(id="fixture", name="Read", input={"secret": "omitted"})],
                model="claude-fixture",
            )
            yield result(terminal_reason="aborted_streaming" if self.interrupted else self.terminal)


class LifecycleTests(unittest.TestCase):
    def test_slow_connection_uses_operation_deadline_and_still_cleans_up(self):
        class SlowConnectClient(SyntheticClient):
            async def __aenter__(self):
                self.events.append("connect")
                await anyio.sleep(0.15)
                return self

            async def __aexit__(self, *exc):
                await anyio.sleep(0.15)
                self.events.append("disconnect")

        async def case():
            client = SlowConnectClient()
            observation = await worker.run_worker(
                worker.ClaudeAgentOptions(),
                "fixture",
                timeout=0.05,
                client_factory=lambda **_: client,
            )
            return observation, client

        observation, client = anyio.run(case)
        self.assertEqual(observation.status, "timeout")
        self.assertEqual(client.events, ["connect", "disconnect"])
        self.assertFalse(observation.interrupt_sent)
        self.assertIsNone(observation.last_result)

    def test_connection_error_still_cleans_up_without_exposing_error_text(self):
        class FailedConnectClient(SyntheticClient):
            async def __aenter__(self):
                self.events.append("connect")
                raise RuntimeError("fixture-secret /private/path")

        async def case():
            client = FailedConnectClient()
            observation = await worker.run_worker(
                worker.ClaudeAgentOptions(),
                "fixture",
                timeout=0.1,
                client_factory=lambda **_: client,
            )
            return observation, client

        observation, client = anyio.run(case)
        self.assertEqual(observation.status, "sdk_error")
        self.assertEqual(client.events, ["connect", "disconnect"])
        self.assertNotIn("fixture-secret", str(observation.summary()))

    def run_case(self, **kwargs):
        async def case():
            client = SyntheticClient(**kwargs)
            observation = await worker.run_worker(
                worker.ClaudeAgentOptions(),
                "fixture",
                timeout=0.1,
                client_factory=lambda **_: client,
            )
            return observation, client

        return anyio.run(case)

    def test_one_query_and_native_result_closes_the_client(self):
        observation, client = self.run_case()
        self.assertEqual(observation.status, "completed")
        self.assertEqual(client.events, ["connect", "query", "disconnect"])
        self.assertEqual(observation.tool_calls, {"Read": 1})
        self.assertEqual(observation.init["skills_count"], 1)

    def test_missing_native_result_is_a_failed_condition(self):
        observation, client = self.run_case(missing=True)
        self.assertEqual(observation.status, "missing_native_result")
        self.assertNotEqual(observation.status, "completed")
        self.assertEqual(client.events[-1], "disconnect")

    def test_native_turn_limit_is_not_reported_as_completion(self):
        observation, client = self.run_case(terminal="max_turns")
        self.assertEqual(observation.status, "native_incomplete")
        self.assertEqual(observation.last_result["terminal_reason"], "max_turns")
        self.assertEqual(client.events[-1], "disconnect")

    def test_timeout_interrupts_then_cleans_up_without_retry(self):
        observation, client = self.run_case(wait=True)
        self.assertEqual(observation.status, "timeout")
        self.assertTrue(observation.interrupt_sent)
        self.assertEqual(client.events, ["connect", "query", "interrupt", "disconnect"])
        recovered, recovered_client = self.run_case()
        self.assertEqual(recovered.status, "completed")
        self.assertEqual(recovered_client.events.count("query"), 1)

    def test_explicit_native_interrupt_is_observed(self):
        async def case():
            client = SyntheticClient(wait=True)
            observation = await worker.run_worker(
                worker.ClaudeAgentOptions(),
                "fixture",
                timeout=0.2,
                interrupt_after=0.01,
                client_factory=lambda **_: client,
            )
            return observation, client

        observation, client = anyio.run(case)
        self.assertEqual(observation.status, "interrupted")
        self.assertTrue(observation.interrupt_sent)
        self.assertEqual(client.events, ["connect", "query", "interrupt", "disconnect"])

    def test_exception_text_is_omitted_and_client_cleanup_runs(self):
        observation, client = self.run_case(error=True)
        self.assertEqual(observation.status, "sdk_error")
        self.assertNotIn("fixture-secret", str(observation.summary()))
        self.assertNotIn("/private/path", str(observation.summary()))
        self.assertEqual(client.events[-1], "disconnect")


if __name__ == "__main__":
    unittest.main()
