"""Synthetic host-gateway adapter controls, not provider acceptance.

Actual worker parsers use inert native SDK imports and temporary host records.
No live record, native authentication store or model request is read or called.
"""
import asyncio
import builtins
import contextlib
import hashlib
from enum import Enum
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
E0 = "http://127.0.0.1:43080/v1"
HOST, IDENTITY, UNSET = "fixture-host", hashlib.sha256(("a" * 32).encode("ascii")).hexdigest(), object()


def provider_forbidden(*args, **kwargs):
    raise AssertionError("configuration test attempted a provider/runtime call")


def imports_without_providers():
    approval = Enum("ApprovalMode", {"deny_all": "never"})
    sandbox = Enum("Sandbox", {"read_only": "read-only", "workspace_write": "workspace-write"})
    effort = Enum("ReasoningEffort", {"max": "max", "ultra": "ultra"})
    exports = {
        "openai_codex": {"ApprovalMode": approval, "Sandbox": sandbox,
                         "AsyncCodex": provider_forbidden, "CodexConfig": SimpleNamespace},
        "openai_codex.async_client": {"AsyncCodexClient": provider_forbidden},
        "openai_codex.generated": {},
        "openai_codex.generated.v2_all": {name: provider_forbidden for name in
            ("ConfigReadResponse", "ListMcpServerStatusResponse", "SkillsListResponse")},
        "openai_codex.types": {"ReasoningEffort": effort},
        "deepagents": {name: provider_forbidden for name in
            ("GeneralPurposeSubagentProfile", "HarnessProfile", "create_deep_agent", "register_harness_profile")},
        "deepagents.backends": {"FilesystemBackend": provider_forbidden},
        "langchain": {}, "langchain.agents": {},
        "langchain.agents.middleware": {"ToolCallLimitMiddleware": provider_forbidden},
        "langchain_core": {}, "langchain_core.load": {"dumps": json.dumps},
        "langchain_openai": {"ChatOpenAI": provider_forbidden},
        "langgraph": {}, "langgraph.checkpoint": {},
        "langgraph.checkpoint.sqlite": {"SqliteSaver": provider_forbidden},
        "httpx": {"Client": SimpleNamespace, "AsyncClient": SimpleNamespace},
        "anyio": {"run": provider_forbidden},
        "claude_agent_sdk": {"ClaudeAgentOptions": SimpleNamespace, "ClaudeSDKClient": provider_forbidden,
            **{name: type(name, (), {}) for name in
               ("AssistantMessage", "ResultMessage", "SystemMessage", "ToolResultBlock", "ToolUseBlock", "UserMessage")}},
    }
    result = {}
    for name, values in exports.items():
        module = ModuleType(name)
        module.__path__ = []
        module.__dict__.update(values)
        result[name] = module
    return result


class GatewayWorkerDefaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workers = {}
        with patch.dict(os.environ, {}, clear=True), patch.dict(sys.modules, imports_without_providers()):
            for name, directory in (("codex", "omniroute-codex-sdk"),
                                    ("deepagents", "deepagents-omniroute"), ("claude", "claude-runtime-sdk")):
                spec = importlib.util.spec_from_file_location(
                    "gateway_default_" + name, ROOT / "examples" / directory / "worker.py")
                worker = importlib.util.module_from_spec(spec)
                with patch.dict(sys.modules, {spec.name: worker}):
                    spec.loader.exec_module(worker)
                cls.workers[name] = worker

    @contextlib.contextmanager
    def host(self, worker, record=UNSET, *, environment=None, patch_identity=True):
        import pwd
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            home = Path(directory)
            path = home / worker.HOST_GATEWAY_RECORD
            if record is UNSET:
                record = {"schema": worker.HOST_GATEWAY_SCHEMA, "host": HOST,
                          "machine_id_sha256": IDENTITY, "endpoint": E0}
            if record is not None:
                path.parent.mkdir(parents=True)
                path.write_text(record if isinstance(record, str) else json.dumps(record))
            stack.enter_context(patch.dict(os.environ, {
                "HOME": str(home / "wrong"), "XDG_CONFIG_HOME": str(home / "also-wrong"),
                **(environment or {})}, clear=True))
            stack.enter_context(patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(home))))
            stack.enter_context(patch.object(worker.socket, "gethostname", return_value=HOST))
            if patch_identity:
                stack.enter_context(patch.object(worker, "installation_id", return_value=IDENTITY))
            stack.enter_context(patch.object(worker.socket, "create_connection"))
            yield home, path

    def argv(self, name, explicit=UNSET, reason=UNSET, extra=()):
        if name == "claude":
            args = ["--cwd", str(ROOT)]
            if explicit is not UNSET:
                args += ["--gateway", explicit[:-3] if explicit.endswith("/v1") else explicit]
        else:
            args = ["--workspace", str(ROOT)]
            if explicit is not UNSET:
                args += ["--base-url", explicit]
            if name == "deepagents":
                args += ["--checkpoint", "unused.sqlite", "--thread-id", "fixture",
                         "--skill", "unused-skill", "--describe"]
        if reason is not UNSET:
            args += ["--unrecorded-gateway-reason", reason]
        return [*args, *extra]

    def selected(self, name, explicit=UNSET, reason=UNSET, extra=()):
        worker, argv = self.workers[name], self.argv(name, explicit, reason, extra)
        if name == "codex":
            args = worker.parse_args(argv)
            return args.gateway, args
        if name == "claude":
            args = worker.parser().parse_args(argv)
            options = worker.build_options(args)
            return args.gateway_resolution, options
        output = io.StringIO()
        with patch("importlib.metadata.version", return_value="synthetic"), contextlib.redirect_stdout(output):
            rc = worker.main(argv)
        data = json.loads(output.getvalue())["native"]
        if rc == 2:
            self.assertIsNone(data["underlying_lane"])
            raise worker.GatewayRefused(data["gateway_refusal"])
        self.assertEqual(rc, 0)
        self.assertEqual(data["underlying_lane"], data["gateway"]["endpoint"])
        return data["gateway"], data

    def refused(self, name, text, explicit=UNSET, reason=UNSET, extra=()):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            if name == "codex":
                with self.assertRaises(SystemExit) as result:
                    self.selected(name, explicit, reason, extra)
                self.assertEqual(result.exception.code, 2)
                self.assertRegex(output.getvalue(), text)
            else:
                with self.assertRaisesRegex(self.workers[name].GatewayRefused, text):
                    self.selected(name, explicit, reason, extra)

    def test_t1_t2_record_empty_and_normalized_explicit(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker):
                for explicit in (UNSET, "", E0, E0 + "/"):
                    if name == "claude" and explicit == E0 + "/":
                        explicit = E0[:-3] + "/"
                    self.assertEqual(self.selected(name, explicit)[0],
                                     {"endpoint": E0, "source": "host-record", "reason": None})

    def test_t3_t4_other_ports_refuse_unless_named_override(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker):
                for port in (20128, 20129, 43081):
                    endpoint = f"http://127.0.0.1:{port}/v1"
                    self.refused(name, "not this host's recorded gateway", endpoint)
                    self.assertEqual(self.selected(name, endpoint, "fixture endpoint")[0],
                                     {"endpoint": endpoint, "source": "unrecorded", "reason": "fixture endpoint"})

    def test_t1_old_distribution_keeps_its_own_recorded_route(self):
        for name, worker in self.workers.items():
            for host, port in (("nativestack", 20128), ("nativestack", 20129), ("nativestack2604", 21128)):
                endpoint = f"http://127.0.0.1:{port}/v1"
                record = {"schema": worker.HOST_GATEWAY_SCHEMA, "host": host,
                          "machine_id_sha256": IDENTITY, "endpoint": endpoint}
                with self.subTest(worker=name, host=host, port=port), self.host(worker, record), \
                        patch.object(worker.socket, "gethostname", return_value=host):
                    self.assertEqual(self.selected(name)[0]["endpoint"], endpoint)

    def test_t3b_gateway_shape_is_exact_ipv4(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker):
                for endpoint in ("http://localhost:43080/v1", "http://[::1]:43080/v1",
                                 "http://127.0.0.1:043080/v1"):
                    self.refused(name, "not a gateway endpoint", endpoint)

    def test_t5_missing_invisible_unreadable_and_passwd_failures(self):
        import pwd
        original = builtins.__import__
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker, None) as (home, _):
                self.refused(name, "no host gateway record")
                with patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(home / "missing"))):
                    self.refused(name, "passwd home is not visible")
                with patch.object(Path, "read_text", side_effect=PermissionError("fixture")):
                    self.refused(name, "cannot be read")
                with patch.object(pwd, "getpwuid", side_effect=KeyError("fixture")):
                    self.refused(name, "no passwd entry")
                def no_pwd(module, *args, **kwargs):
                    if module == "pwd":
                        raise ImportError("synthetic no passwd")
                    return original(module, *args, **kwargs)
                with patch.object(builtins, "__import__", side_effect=no_pwd):
                    self.refused(name, "no passwd database")
                self.assertEqual(self.selected(name, E0, "no-record fixture")[0]["source"], "unrecorded")

    def test_t6_malformed_schema_fields_and_nonobjects(self):
        good = {"schema": "native-agent-stack/host-gateway/v1", "host": HOST,
                "machine_id_sha256": IDENTITY, "endpoint": E0}
        cases = ["{broken", "[]", "null", {}, {"schema": "wrong"}]
        for key in good:
            missing, wrong = dict(good), dict(good)
            del missing[key]
            wrong[key] = 1
            cases += [missing, wrong]
        for name, worker in self.workers.items():
            for record in cases:
                with self.subTest(worker=name, record=record), self.host(worker, record):
                    self.refused(name, "malformed or has another schema")

    def test_t7_host_and_installation_match_exactly(self):
        for name, worker in self.workers.items():
            for host in (HOST[:-1], HOST + "-copy"):
                record = {"schema": worker.HOST_GATEWAY_SCHEMA, "host": host,
                          "machine_id_sha256": IDENTITY, "endpoint": E0}
                with self.subTest(worker=name, host=host), self.host(worker, record):
                    self.refused(name, "another host name")
            with self.host(worker), patch.object(worker, "installation_id", return_value="b" * 64):
                self.refused(name, "another installation")

    def test_t7b_record_machine_hash_is_mandatory_lowercase_hex(self):
        for name, worker in self.workers.items():
            for value in (UNSET, None, "", "A" * 64, "a" * 63):
                record = {"schema": worker.HOST_GATEWAY_SCHEMA, "host": HOST, "endpoint": E0}
                if value is not UNSET:
                    record["machine_id_sha256"] = value
                with self.subTest(worker=name, value=value), self.host(worker, record):
                    self.refused(name, "malformed or has another schema")

    def test_t7b_local_identity_has_no_hostname_fallback(self):
        original = Path.read_text
        for name, worker in self.workers.items():
            for value in ("", "0" * 32, "A" * 32, "a" * 31, PermissionError("fixture")):
                def read(path, *args, **kwargs):
                    if path == Path("/etc/machine-id"):
                        if isinstance(value, Exception):
                            raise value
                        return value
                    return original(path, *args, **kwargs)
                with self.subTest(worker=name, value=value), self.host(worker, patch_identity=False):
                    with patch.object(Path, "read_text", read):
                        self.refused(name, "machine-id")
                        self.assertEqual(self.selected(name, E0, "identity fixture")[0]["source"], "unrecorded")

    def test_t8_record_endpoints_outside_contract_never_default(self):
        for name, worker in self.workers.items():
            for endpoint in ("https://127.0.0.1:43080/v1", "http://example.invalid:43080/v1",
                             "http://127.0.0.1/v1", "http://fixture:fake@127.0.0.1:43080/v1",
                             E0 + "?x=1", E0 + "#x", E0.replace("/v1", "/other")):
                record = {"schema": worker.HOST_GATEWAY_SCHEMA, "host": HOST,
                          "machine_id_sha256": IDENTITY, "endpoint": endpoint}
                with self.subTest(worker=name, endpoint=endpoint), self.host(worker, record):
                    self.refused(name, "endpoint outside the contract")

    def test_t9_override_needs_endpoint_and_nonblank_reason(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker):
                self.refused(name, "needs an explicit gateway", reason="fixture")
                self.refused(name, "non-blank reason", E0, " ")

    def test_t10_real_shallow_copies_check_from_root_without_sdk(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker) as (home, _):
                path = home / "worker.py"
                path.write_text(Path(worker.__file__).read_text())
                source = path.read_text()
                original = Path.read_text
                def read(file, *args, **kwargs):
                    if file == Path("/etc/machine-id"):
                        return "a" * 32
                    return original(file, *args, **kwargs)
                output, previous = io.StringIO(), Path.cwd()
                try:
                    os.chdir("/")
                    with patch.object(sys, "argv", [str(path), "--gateway-check"]), \
                            patch.object(Path, "read_text", read), \
                            contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
                        exec(compile(source, str(path), "exec"),
                             {"__name__": "__main__", "__file__": str(path)})
                finally:
                    os.chdir(previous)
                self.assertEqual(result.exception.code, 0)
                self.assertEqual(json.loads(output.getvalue())["gateway"]["endpoint"], E0)

    def test_t11_public_environment_never_overrides_native_client_endpoint(self):
        for name, worker in self.workers.items():
            environment = {key: "https://public.invalid/v1" for key in worker.GATEWAY_VARIABLES}
            with self.subTest(worker=name), self.host(worker, environment=environment):
                gateway, data = self.selected(name)
                self.assertEqual(gateway["endpoint"], E0)
                if name == "codex":
                    config = worker.runtime_config(data)
                    self.assertIn(f'model_providers.{worker.PROVIDER}.base_url="{E0}"', config.config_overrides)
                    for key in ("NO_PROXY", "no_proxy"):
                        self.assertIn("127.0.0.1", config.env[key].split(","))
                elif name == "claude":
                    self.assertEqual(data.env["ANTHROPIC_BASE_URL"], E0[:-3])
                    self.assertEqual(json.loads(data.settings)["env"]["ANTHROPIC_BASE_URL"], E0[:-3])
                else:
                    with patch.dict(os.environ, {"FIXTURE_KEY": "synthetic-not-a-credential"}), \
                            patch.object(worker, "ChatOpenAI") as model:
                        worker.chat_model("FIXTURE_KEY", gateway["endpoint"])
                    self.assertEqual(model.call_args.kwargs["base_url"], E0)
                    for key in ("http_client", "http_async_client"):
                        self.assertFalse(getattr(model.call_args.kwargs[key], "trust_env"))
                        self.assertFalse(getattr(model.call_args.kwargs[key], "follow_redirects"))

    def test_t12_loopback_environment_spellings_require_named_override(self):
        for name, worker in self.workers.items():
            for key in worker.GATEWAY_VARIABLES:
                for scheme, host in (("http", "localhost"), ("http", "localhost."),
                                     ("http", "127.1"), ("http", "0.0.0.0"),
                                     ("http", "[::ffff:127.0.0.1]"), ("https", "127.0.0.1")):
                    environment = {key: f"{scheme}://{host}:20128/v1"}
                    with self.subTest(worker=name, key=key, host=host), self.host(worker, environment=environment):
                        self.refused(name, key)
                        self.assertEqual(self.selected(name, E0, "environment fixture")[0]["source"], "unrecorded")

    def test_t13_refusal_precedes_key_lookup_constructor_and_receipt(self):
        original = type(os.environ).__getitem__
        for name, worker in self.workers.items():
            def no_key(environment, key):
                if key == "FIXTURE_KEY":
                    raise AssertionError("credential lookup before gateway refusal")
                return original(environment, key)
            extra = ("--api-key-env", "FIXTURE_KEY") if name == "codex" else (
                ("--gateway-token-env", "FIXTURE_KEY") if name == "claude" else ())
            with self.subTest(worker=name), self.host(worker) as (home, _), \
                    patch.object(type(os.environ), "__getitem__", no_key), \
                    patch.object(worker, "probe_gateway") as probe, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                target = home / "must-not-be-created"
                artifact = ("--native-result", str(target)) if name == "codex" else (
                    ("--result-output", str(target)) if name == "claude" else ("--checkpoint", str(target)))
                argv = self.argv(name, "http://127.0.0.1:20128/v1", extra=(*extra, *artifact))
                if name == "codex":
                    with patch.object(worker, "initial_record", side_effect=provider_forbidden), \
                            patch.object(sys, "argv", ["worker.py", *argv]), self.assertRaises(SystemExit) as result:
                        worker.main()
                    self.assertEqual(result.exception.code, 2)
                elif name == "claude":
                    with patch.object(worker, "ClaudeAgentOptions", side_effect=provider_forbidden):
                        self.assertEqual(worker.main(argv), 2)
                else:
                    with patch.object(worker, "ChatOpenAI", side_effect=provider_forbidden):
                        self.assertEqual(worker.main(argv), 2)
                probe.assert_not_called()
                self.assertFalse(target.exists())

    def test_t14_dag_empty_binding_unexpanded_binding_and_conflict(self):
        source = (ROOT / "examples/omniroute-codex-sdk/runtime-worker.yaml").read_text()
        self.assertRegex(source, r"(?m)^  - WORKER_BASE_URL: \$\{WORKER_BASE_URL\}$")
        commands = re.findall(r"(?m)^    run: >-\n((?:^      .*\n)+)", source)
        self.assertEqual(len(commands), 2)
        binding = "$" + "{WORKER_BASE_URL}"
        for command in commands:
            self.assertEqual(command.count('--base-url "' + binding + '"'), 1)
        worker = self.workers["codex"]
        with self.host(worker):
            self.assertEqual(self.selected("codex", "")[0]["endpoint"], E0)
            self.refused("codex", "unexpanded variable", binding)
            self.refused("codex", "not this host", "http://127.0.0.1:20128/v1")

    def test_t18_abbreviations_fail_both_check_and_normal_parse(self):
        for name, worker in self.workers.items():
            for prefix in ("--gateway-c", "--unrec", "--gate" if name == "claude" else "--base"):
                extra = (prefix,) if prefix == "--gateway-c" else (prefix, "fixture")
                with self.subTest(worker=name, prefix=prefix), self.host(worker), \
                        contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        worker.gateway_check([*extra, "--gateway-check"], worker.GATEWAY_FLAGS,
                                             worker.GATEWAY_VARIABLES, worker.GATEWAY_OVERRIDES, worker.GATEWAY_HOMES)
                    self.assertEqual(result.exception.code, 2)
                    with self.assertRaises(SystemExit) as result:
                        self.selected(name, extra=extra)
                    self.assertEqual(result.exception.code, 2)

    def test_t19_probe_timeout_refuses_before_constructor(self):
        for name, worker in self.workers.items():
            with self.subTest(worker=name), self.host(worker), \
                    patch.object(worker.socket, "create_connection", side_effect=TimeoutError):
                self.refused(name, "within 3 s")

    def test_t25_codex_home_route_keys_check_in_both_entry_paths(self):
        worker = self.workers["codex"]
        for filename in ("config.toml", "fixture.config.toml"):
            for line in ('openai_base_url="http://127.0.0.1:20128/v1"',
                         'chatgpt_base_url="http://127.0.0.1:20128/v1"',
                         '[model_providers.fixture]\nbase_url="http://127.0.0.1:20128/v1"'):
                with self.subTest(file=filename, line=line), self.host(worker) as (home, _):
                    codex_home = home / "codex"
                    codex_home.mkdir()
                    config = codex_home / filename
                    config.write_text(line)
                    self.refused("codex", "Codex home names a loopback",
                                 extra=("--codex-home", str(codex_home)))
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                        worker.gateway_check(["--gateway-check", "--codex-home", str(codex_home)],
                                             worker.GATEWAY_FLAGS, worker.GATEWAY_VARIABLES,
                                             worker.GATEWAY_OVERRIDES, worker.GATEWAY_HOMES)
                    self.assertEqual(result.exception.code, 2)
                    config.write_text(f'[model_providers.fixture]\nbase_url="{E0}"')
                    self.assertEqual(self.selected("codex", extra=("--codex-home", str(codex_home)))[0]["endpoint"], E0)

    def test_t25_empty_home_does_not_read_record_and_old_python_refuses_toml(self):
        worker, original = self.workers["codex"], builtins.__import__
        with self.host(worker) as (home, _):
            codex_home = home / "codex"
            codex_home.mkdir()
            with patch.object(worker, "recorded_gateway", side_effect=AssertionError("unexpected record")):
                worker.refuse_home_endpoints(codex_home, None, worker.GATEWAY_VARIABLES)
            (codex_home / "config.toml").write_text("[features]\nplugins=false")
            def no_tomllib(module, *args, **kwargs):
                if module == "tomllib":
                    raise ImportError("synthetic Python < 3.11")
                return original(module, *args, **kwargs)
            with patch.object(builtins, "__import__", side_effect=no_tomllib):
                self.refused("codex", "no tomllib", extra=("--codex-home", str(codex_home)))

    def test_t26_deepagents_model_headers_are_paired_and_distinct(self):
        worker = self.workers["deepagents"]
        with self.host(worker, environment={"FIXTURE_KEY": "synthetic-not-a-credential"}), \
                patch.object(worker, "ChatOpenAI") as model, patch.object(worker, "register_harness_profile"), \
                patch.object(worker, "GeneralPurposeSubagentProfile"), patch.object(worker, "HarnessProfile"), \
                patch.object(worker, "FilesystemBackend"), patch.object(worker, "ToolCallLimitMiddleware"), \
                patch.object(worker, "create_deep_agent"):
            worker.build_graph(ROOT, [], object(), "FIXTURE_KEY", E0)
            worker.build_graph(ROOT, [], object(), "FIXTURE_KEY", E0)
        pairs = [(call.kwargs["default_headers"]["X-OmniRoute-Session-Id"],
                  call.kwargs["default_headers"]["X-Session-Id"]) for call in model.call_args_list]
        self.assertEqual(len(pairs), 4)
        self.assertEqual(len(set(pairs)), 4)
        for census, affinity in pairs:
            self.assertEqual(census, affinity)
            self.assertRegex(census, r"^nas-deepagents-omniroute-[0-9a-f]{32}$")

    def test_claude_native_header_has_distinct_invocation_markers(self):
        worker = self.workers["claude"]
        with self.host(worker):
            options = [worker.build_options(worker.parser().parse_args(["--cwd", str(ROOT)])) for _ in range(2)]
        headers = [option.env["ANTHROPIC_CUSTOM_HEADERS"] for option in options]
        self.assertNotEqual(headers[0], headers[1])
        for header in headers:
            self.assertRegex(header, r"^X-OmniRoute-Session-Id: nas-claude-runtime-sdk-[0-9a-f]{32}$")

    def test_t27_effective_mismatch_or_missing_key_refuses_start_and_resume(self):
        worker = self.workers["codex"]
        for resume in (None, "fixture-resume"):
            for providers in ({worker.PROVIDER: {"base_url": "http://127.0.0.1:20128/v1"}}, {}):
                for preflight in (False, True):
                    if resume and preflight:
                        continue
                    with self.subTest(resume=resume, providers=providers, preflight=preflight), self.host(worker) as (home, _):
                        output = home / "must-not-exist.json"
                        argv = self.argv("codex", extra=("--prompt", "fixture"))
                        argv += ["--preflight"] if preflight else ["--native-result", str(output)]
                        if resume:
                            argv += ["--resume", resume]
                        args, calls = worker.parse_args(argv), []
                        class Client:
                            def __init__(self, config):
                                self._client = self
                                self.metadata = SimpleNamespace(serverInfo=None, userAgent="codex/0.160.0")
                            async def __aenter__(self):
                                calls.append("start")
                                return self
                            async def start(self):
                                calls.append("start")
                            async def initialize(self):
                                return self.metadata
                            async def request(self, method, params, response_model):
                                calls.append(method)
                                if method != "config/read":
                                    raise AssertionError("refusal failed to stop native discovery")
                                return SimpleNamespace(config=SimpleNamespace(
                                    model=worker.DEFAULT_MODEL, model_provider=worker.PROVIDER,
                                    model_extra={"model_providers": providers}))
                            async def close(self):
                                calls.append("close")
                            async def thread_start(self, **kwargs):
                                raise AssertionError("mismatch did not prevent thread start")
                            async def thread_resume(self, *args, **kwargs):
                                raise AssertionError("mismatch did not prevent thread resume")
                        method = worker.run_preflight if preflight else worker.run_worker
                        invocation = method(args, sdk_factory=Client) if preflight else method(
                            args, "fixture", sdk_factory=Client, on_event=provider_forbidden)
                        result = asyncio.run(invocation)
                        self.assertEqual(result["status"], "gateway_refused")
                        if providers:
                            self.assertIn("http://127.0.0.1:20128/v1", result["error"])
                            self.assertIn(E0, result["error"])
                        self.assertFalse(result["model_inference_submitted"])
                        self.assertEqual(calls, ["start", "config/read", "close"])
                        self.assertFalse(output.exists())
                        defaults = dict(method.__kwdefaults__)
                        try:
                            method.__kwdefaults__["sdk_factory"] = Client
                            with patch.object(sys, "argv", ["worker.py", *argv]), contextlib.redirect_stdout(io.StringIO()):
                                self.assertEqual(worker.main(), 2)
                        finally:
                            method.__kwdefaults__.clear()
                            method.__kwdefaults__.update(defaults)

    def test_t27_invalid_effective_url_diagnostic_keeps_fixture_credentials_opaque(self):
        worker = self.workers["codex"]
        for endpoint in (
            "http://fixture-user:opaque-fixture@127.0.0.1:20128/v1",
            "http://127.0.0.1:20128/v1?token=opaque-fixture",
        ):
            with self.subTest(endpoint=endpoint), self.host(worker):
                args = worker.parse_args(self.argv("codex"))
                class Client:
                    async def request(self, *args, **kwargs):
                        return SimpleNamespace(config=SimpleNamespace(
                            model_provider=worker.PROVIDER,
                            model_extra={"model_providers": {
                                worker.PROVIDER: {"base_url": endpoint}}},
                        ))
                with self.assertRaises(worker.GatewayRefused) as raised:
                    asyncio.run(worker.read_effective_gateway(Client(), args))
                self.assertNotIn("opaque-fixture", str(raised.exception))
