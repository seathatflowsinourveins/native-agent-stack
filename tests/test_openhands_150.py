"""Integration regression checks for the pinned SDK 1.50 recipe.

These checks use fixtures and patched native calls, not live model acceptance.
Upstream SDK tests and live provider/container acceptance are separate evidence.
"""

import asyncio
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import MagicMock, patch


RECIPE = Path(__file__).resolve().parents[1] / "blueprints/runtime-workers/openhands"


def load(name):
    spec = importlib.util.spec_from_file_location("openhands_150_" + name.removesuffix(".py").replace("/", "_"), RECIPE / name)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RECIPE))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class OpenHands150Profiles(unittest.TestCase):
    def test_profiles_are_bounded_and_services_are_task_scoped(self):
        recipe = load("recipe.py")
        name, baseline = recipe.task_profile({})
        self.assertEqual(name, "coding")
        self.assertFalse(baseline["browser"])
        self.assertEqual(baseline["children"], [])
        _, orchestration = recipe.task_profile({"OPENHANDS_PROFILE": "orchestration"})
        self.assertEqual(orchestration["delegation"]["tool_concurrency_limit"], 2)
        self.assertEqual(orchestration["delegation"]["child_max_iteration_per_run"], 12)
        self.assertEqual(orchestration["goal"]["max_iterations"], 3)
        for child in orchestration["children"]:
            self.assertEqual(recipe.task_profile({"OPENHANDS_PROFILE": child})[1]["children"], [])
        with self.assertRaises(ValueError):
            recipe.task_profile({"OPENHANDS_PROFILE": "unqualified-profile"})

    def test_skill_objects_are_role_selected_and_github_descriptions_are_scoped(self):
        recipe = load("recipe.py")
        objects = {name: object() for name in ("github", "gh-fix-ci", "research-brief", "verification-before-completion", "tdd")}
        manifest = {"roles": {"github": ["coding"], "gh-fix-ci": ["coding"], "research-brief": ["research"],
                              "tdd": ["coding"]}}
        profile = recipe.task_profile({"OPENHANDS_PROFILE": "github-workflow"})[1]
        selected = recipe.profile_skills(objects, manifest, profile)
        self.assertEqual(set(selected), {"github", "gh-fix-ci", "verification-before-completion"})
        self.assertIs(selected["github"], objects["github"])
        with self.assertRaises(ValueError):
            recipe.profile_skills(objects, {}, recipe.task_profile({"OPENHANDS_PROFILE": "research"})[1])

    def test_sampling_is_rejected_before_any_request(self):
        recipe = load("recipe.py")
        config = recipe.read_json(RECIPE / "config/worker.json")
        for key in ("temperature", "top_p", "top_k"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                recipe.llm_config({**config, "llm": {**config["llm"], key: 0.3}})

    def test_native_task_hook_refuses_ambient_and_recursive_agents(self):
        hook = load("mcp_guard.py")
        with patch.dict(os.environ, {"OPENHANDS_PROFILE": "orchestration"}):
            self.assertTrue(hook.permitted({"tool_name": "task", "tool_input": {"subagent_type": "worker-research"}}))
            self.assertFalse(hook.permitted({"tool_name": "task", "tool_input": {"subagent_type": "general-purpose"}}))
        with patch.dict(os.environ, {"OPENHANDS_PROFILE": "coding"}):
            self.assertFalse(hook.permitted({"tool_name": "task", "tool_input": {"subagent_type": "worker-research"}}))


class OpenHands150Transport(unittest.TestCase):
    def test_completion_bridge_preserves_native_contract_and_restores_methods(self):
        worker = load("worker.py")
        sentinel = object()
        calls = []
        class NativeLikeLLM:
            extra_headers = {"x-omniroute-session": "fixture-session"}
            def uses_responses_api(self):
                return True
            def generate(self, **kwargs):
                calls.append(kwargs)
                return sentinel
            async def agenerate(self, **kwargs):
                calls.append(kwargs)
                return sentinel
            def completion(self, *args, **kwargs):
                raise AssertionError("chat path called")
            async def acompletion(self, *args, **kwargs):
                raise AssertionError("async chat path called")
        originals = (NativeLikeLLM.generate, NativeLikeLLM.agenerate, NativeLikeLLM.completion, NativeLikeLLM.acompletion)
        llm = NativeLikeLLM()
        context, tools, callback = object(), [object()], lambda *_: None
        with worker.gateway_transport(NativeLikeLLM):
            self.assertIs(llm.completion(["message"], tools, True, callback, context, store=False), sentinel)
            self.assertIs(asyncio.run(llm.acompletion(["async"], tools, True, callback, context, store=False)), sentinel)
            for call in calls:
                self.assertIs(call["tools"], tools)
                self.assertIs(call["call_context"], context)
                self.assertIs(call["on_token"], callback)
                self.assertTrue(call["add_security_risk_prediction"])
                self.assertIs(call["store"], False)
                self.assertEqual(call["extra_headers"]["x-omniroute-session"], "fixture-session")
            self.assertNotEqual(calls[0]["extra_headers"]["Idempotency-Key"], calls[1]["extra_headers"]["Idempotency-Key"])
        self.assertEqual((NativeLikeLLM.generate, NativeLikeLLM.agenerate, NativeLikeLLM.completion, NativeLikeLLM.acompletion), originals)

    def test_actual_native_sdk_completion_uses_responses_dispatch(self):
        try:
            from openhands.sdk import LLM, Message, TextContent
        except ImportError:
            self.skipTest("Native SDK is tested in the isolated upstream installation")
        worker = load("worker.py")
        fields = worker.worker_llm_config({}, "rw-openhands-native-fixture")
        llm = LLM(**fields)
        sentinel = object()
        with patch.object(LLM, "responses", return_value=sentinel) as responses, \
                patch.object(LLM, "aresponses", return_value=sentinel) as aresponses, worker.gateway_transport(LLM):
            self.assertIs(llm.completion([Message(role="user", content=[TextContent(text="fixture")])]), sentinel)
            self.assertIs(asyncio.run(llm.acompletion([Message(role="user", content=[TextContent(text="fixture")])])), sentinel)
        self.assertEqual(responses.call_count, 1)
        self.assertEqual(aresponses.call_count, 1)
        self.assertEqual(type(llm), LLM)

    def test_actual_native_profiles_and_children_keep_explicit_route_tools_skills(self):
        try:
            from openhands.sdk.context import Skill
            from openhands.sdk.subagent import get_agent_factory
        except ImportError:
            self.skipTest("Native SDK is tested in the isolated upstream installation")
        worker = load("worker.py")
        cfg = json.loads((RECIPE / "config/worker.json").read_text())
        pins = json.loads((RECIPE / "pins.json").read_text())
        skills = {name: Skill(name=name, content="Verify the task with its frozen oracle.", description="Task verification")
                  for name in ("verification-before-completion", "coding-skill", "research-skill")}
        manifest = {"names": sorted(skills), "roles": {
            "verification-before-completion": ["coding", "research", "orchestration", "extraction-caller"],
            "coding-skill": ["coding", "orchestration"], "research-skill": ["research"],
        }}
        def read(path):
            name = Path(path).name
            if name == "skills.json":
                return manifest
            if name == "mcp.json":
                return {name: {"transport": "stdio", "command": "python", "args": ["-c", "pass"]}
                        for name in ("fixture-one", "fixture-two")}
            return json.loads(Path(path).read_text())
        with patch.object(worker, "read_json", side_effect=read), \
                patch("openhands.sdk.skills.load_skills_from_dir", return_value=({}, {}, skills)):
            for name in ("coding", "planning", "browser", "research", "review", "github-workflow", "orchestration", "completion-review"):
                with self.subTest(profile=name):
                    agent, versions, discovered = worker.build_agent({"OPENHANDS_PROFILE": name}, "rw-openhands-profile-fixture")
                    self.assertEqual(versions, {key: pins["version"] for key in ("openhands-sdk", "openhands-tools")})
                    self.assertEqual(agent.llm.api_mode, "responses")
                    self.assertEqual(agent.llm.reasoning_effort, "max")
                    self.assertEqual(agent.llm.model, "openai/cx/gpt-6-astra-max")
                    self.assertFalse(agent.agent_context.load_user_skills)
                    self.assertEqual(set(discovered), {skill.name for skill in agent.agent_context.skills})
            definition = get_agent_factory("worker-research")
            self.assertEqual(definition.definition.max_iteration_per_run, 12)
            self.assertEqual(definition.definition.model, "openai/cx/gpt-6-astra-max")
            parent = worker.build_agent({"OPENHANDS_PROFILE": "coding"}, "rw-openhands-profile-fixture")[0]
            child_llm = parent.llm.model_copy()
            child_llm.reset_metrics()
            child = definition.factory_func(child_llm)
            self.assertEqual(child.llm.usage_id, "child-research")
            self.assertEqual({skill.name for skill in child.agent_context.skills}, {"research-skill", "verification-before-completion"})
            self.assertNotIn("TaskToolSet", {tool.name for tool in child.tools})

    def test_goal_adapter_keeps_native_loop_and_separate_judge_metrics(self):
        class Judge:
            def __init__(self, usage_id="agent"):
                self.usage_id = usage_id
                self.reset = 0
            def model_copy(self, update):
                return Judge(update["usage_id"])
            def reset_metrics(self):
                self.reset += 1
        class NativeService:
            def __init__(self):
                self._conversation = SimpleNamespace(agent=SimpleNamespace(llm=Judge()))
            async def start_goal_loop(self, *args, **kwargs):
                return args, kwargs
            async def resume_goal_loop(self, *args, **kwargs):
                return args, kwargs
        context = MagicMock()
        modules = {"openhands.sdk": SimpleNamespace(LLM=Judge),
                   "openhands.agent_server.event_service": SimpleNamespace(EventService=NativeService),
                   "worker": SimpleNamespace(gateway_transport=MagicMock(return_value=context),
                                             capture_correlation=lambda _: None, register_worker_agents=lambda *_: None)}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {
                "OPENHANDS_OWNED_CONTAINER": "1", "OPENHANDS_RUN_ID": "rw-openhands-fixture"}), patch("atexit.register"):
            module = load("server_transport.py")
            service = NativeService()
            args, kwargs = asyncio.run(service.start_goal_loop("objective", max_iterations=3))
            self.assertEqual(args, ("objective",))
            self.assertEqual(kwargs["judge_llm"].usage_id, "goal-judge")
            self.assertEqual(kwargs["judge_llm"].reset, 1)
            self.assertEqual(service._conversation.agent.llm.usage_id, "agent")
            self.assertIsNot(kwargs["judge_llm"], service._conversation.agent.llm)
            with self.assertRaises(ValueError):
                asyncio.run(service.start_goal_loop("objective", max_iterations=4))
            self.assertEqual(asyncio.run(service.resume_goal_loop())[1]["judge_llm"].usage_id, "goal-judge")
            module._goal_transport.__exit__(None, None, None)

    def test_p3_native_tool_replay_and_query_denial_are_fixture_only(self):
        try:
            from openhands.sdk import LLM, Message, TextContent
        except ImportError:
            self.skipTest("Native SDK is tested in the isolated upstream installation")
        netprobe = load("e2e/netprobe.py")
        request_calls = []
        first = Message(role="assistant", content=[], tool_calls=[{
            "id": "call-p3-fixture", "origin": "responses",
            "name": "route_probe", "arguments": '{"text":"P3_OK"}',
        }])
        second = Message(role="assistant", content=[TextContent(text="P3_OK")])
        responses = iter((first, second))
        def generate(llm, **kwargs):
            request_calls.append(kwargs)
            kwargs["on_token"]("fixture-token")
            return SimpleNamespace(message=next(responses))
        connection = MagicMock()
        connection.getresponse.side_effect = [
            SimpleNamespace(status=403, getheader=lambda _: None), SimpleNamespace(status=200),
        ]
        with patch.object(LLM, "generate", new=generate), patch.object(netprobe.Path, "exists", return_value=True), \
                patch.object(netprobe.http.client, "HTTPConnection", return_value=connection):
            result = netprobe.p3_control_call({"OPENHANDS_OWNED_CONTAINER": "1"}, "rw-openhands-p3-fixture")
        self.assertTrue(result["sdk_probe_passed"])
        self.assertEqual(result["independent_gateway_verdict"], "pending")
        self.assertEqual(request_calls[0]["tools"][0].name, "route_probe")
        self.assertEqual(request_calls[1]["messages"][-1].tool_call_id, "call-p3-fixture")
        self.assertEqual(connection.request.call_args_list[0].args[:2], ("POST", "/v1/responses?p3=must-be-denied"))


class OpenHands150Recovery(unittest.TestCase):
    def test_interrupt_resume_preserves_native_conversation_deadline_and_reservation(self):
        dispatch = load("dispatch.py")
        run_id, arm = "rw-openhands-recovery-fixture", "control"
        conversation_id = str(uuid.UUID(int=1))
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory).resolve()
            result = state / "runs" / run_id / arm
            result.mkdir(parents=True)
            status = {"status": "running", "conversation_id": conversation_id, "deadline": 1200, "port": 3730}
            (result / "status.json").write_text(json.dumps(status))
            (result / "window.json").write_text(json.dumps({"run_id": run_id, "arm": arm}))
            reservation = {"run_id": run_id, "arm": arm}
            lock = state / "active-dispatch.json"
            lock.write_text(json.dumps(reservation))
            with patch.object(dispatch, "api_request", return_value={"success": True}) as native, \
                    patch.object(dispatch.time, "time", return_value=100), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dispatch.execute("interrupt", state, run_id, arm), 0)
                self.assertEqual(json.loads((result / "status.json").read_text())["status"], "paused")
                self.assertEqual(dispatch.execute("resume", state, run_id, arm), 0)
                self.assertEqual(dispatch.execute("resume", state, run_id, arm), 3)
            self.assertEqual([call.args[:2] for call in native.call_args_list], [
                ("POST", f"/api/conversations/{conversation_id}/interrupt"),
                ("POST", f"/api/conversations/{conversation_id}/run"),
            ])
            current = json.loads((result / "status.json").read_text())
            self.assertEqual(current["conversation_id"], conversation_id)
            self.assertEqual(current["deadline"], 1200)
            self.assertEqual(json.loads(lock.read_text()), reservation)

    def test_goal_status_is_lifecycle_output_and_preserves_active_judge_round(self):
        dispatch = load("dispatch.py")
        with patch.object(dispatch, "api_request", return_value={"items": [
            {"key": "stats", "value": {}}, {"key": "goal", "value": {"active": True, "status": "running"}},
        ]}):
            self.assertEqual(dispatch.native_goal_status("fixture", 3730, Path("fixture")), {"active": True, "status": "running"})

    def test_independent_observer_rejects_fixture_and_model_store_sources(self):
        receipt = load("receipt.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observer = root / "observer"
            observer.mkdir()
            for evidence_class, source_kind in (("integration_fixture", "isolated_native_executor"),
                                                ("independent_native_observation", "native_event_api")):
                path = observer / "receipt.json"
                path.write_text(json.dumps({"evidence_class": evidence_class, "source_kind": source_kind}))
                path.chmod(0o600)
                self.assertEqual(receipt.independent_observations(root, {}, pins)["status"], "not_collected")


if __name__ == "__main__":
    unittest.main()
