#!/usr/bin/env python3
"""Opt-in T17/T17c/T17d native SDK transport fixtures; never a live-gateway run.

Run once per client in its pinned SDK interpreter. All listeners and homes are
owned fixtures. This uses unittest and the existing upstream-derived Codex SSE
FixtureGateway, not an A/B or model-evaluation runner.

Sources:
- openai/codex@a956835d sdk/python/src/openai_codex/client.py:196-211,242-302
  (native config, child launch/close); api.py:316-324 (native async client).
- anthropics/claude-agent-sdk-python@f2204bb9
  src/claude_agent_sdk/_internal/transport/subprocess_cli.py:657-660,797-915,962-1061
  (native settings, launch and close).
- examples/omniroute-codex-sdk/test_worker.py::FixtureGateway cites the unchanged
  Codex upstream SSE fixture sources; its class is loaded directly below.
- https://code.claude.com/docs/en/env-vars (read 2026-10-07):
  CLAUDE_CONFIG_DIR and the documented nonessential-traffic/update opt-outs.
- https://curl.se/docs/manpage.html#-L : native 307-following observer control.
- https://platform.claude.com/docs/en/build-with-claude/streaming
  (read 2026-10-07): authored success response uses the vendor's SSE grammar.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PINS = {"codex": "0.160.0", "claude": "0.2.162"}
PACKAGES = {"codex": "openai-codex", "claude": "claude-agent-sdk"}
CLI_PINS = {"codex": "0.160.0", "claude": "2.1.285"}
SAFE_ENV = ("PATH", "LANG", "LC_ALL", "TMPDIR")
OPTOUTS = {
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_UPDATES": "1",
}
FIXTURE_PROMPT = "Return one short deterministic fixture response."
CORRELATION = "nas-gateway-transport-fixture"
CASES = {
    "codex": ("test_redirect", "test_proxy", "test_scanned_home",
              "test_inherited_config_precedence"),
    "claude": ("test_redirect", "test_proxy", "test_user_settings_precedence"),
}


def safe_environment():
    """Read only noncredential launcher values, then remove all other names."""
    allowed = {key: os.environ[key] for key in SAFE_ENV if key in os.environ}
    for key in tuple(os.environ):
        del os.environ[key]
    os.environ.update(allowed)
    return allowed


def load_worker(client):
    kit = ROOT / "examples" / (
        "omniroute-codex-sdk" if client == "codex" else "claude-runtime-sdk")
    spec = importlib.util.spec_from_file_location("transport_worker_" + client, kit / "worker.py")
    worker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = worker
    spec.loader.exec_module(worker)
    return worker


def fixture_gateway_class():
    """Reuse only the existing fixture class, without importing a second SDK."""
    source = (ROOT / "examples/omniroute-codex-sdk/test_worker.py").read_text()
    definition = next(node for node in ast.parse(source).body
                      if isinstance(node, ast.ClassDef) and node.name == "FixtureGateway")
    namespace = {
        "json": json, "threading": threading,
        "BaseHTTPRequestHandler": BaseHTTPRequestHandler,
        "ThreadingHTTPServer": ThreadingHTTPServer,
    }
    exec(compile(ast.Module(body=[definition], type_ignores=[]),
                 "existing-upstream-derived-FixtureGateway", "exec"), namespace)
    return namespace["FixtureGateway"]


def anthropic_fixture_sse(model):
    """Authored text-only reply using the official Messages streaming grammar."""
    events = [
        {"type": "message_start", "message": {
            "id": "msg_fixture_transport", "type": "message", "role": "assistant",
            "content": [], "model": model, "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 25, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Fixture response."}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": {"output_tokens": 3}},
        {"type": "message_stop"},
    ]
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()


def codex_http_status(error):
    """Read only the pinned typed public status field, never error messages."""
    info = getattr(error, "codex_error_info", None)
    root = getattr(info, "root", None)
    # openai/codex@a956835d generated/v2_all.py:559-622,7628-7650.
    for name in ("http_connection_failed", "response_stream_connection_failed",
                 "response_stream_disconnected", "response_too_many_failed_attempts"):
        payload = getattr(root, name, None)
        value = getattr(payload, "http_status_code", None)
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            return value
    return None


class CountingFixture:
    """Ephemeral HTTP listener with metadata counters and the existing SSE reply."""
    def __init__(self, label, *, redirect=None, model="claude-opus-5"):
        self.label, self.redirect, self.model = label, redirect, model
        self.native = fixture_gateway_class()()
        self.url = self.native.url
        self.rows = []
        owner, native = self, self.native
        original_handler = native.server.RequestHandlerClass

        class Handler(original_handler):
            def record(self):
                # No body, authentication field, or arbitrary header is retained.
                path = urlsplit(self.path).path
                self._metadata_row = {
                    "method": self.command, "path": path,
                    "correlation": self.headers.get("x-request-id")
                        or self.headers.get("x-correlation-id"),
                }
                owner.rows.append(self._metadata_row)

            def send_response(self, code, message=None):
                if hasattr(self, "_metadata_row"):
                    self._metadata_row["response_status"] = code
                super().send_response(code, message)

            def do_GET(self):
                self.record()
                body = json.dumps({
                    "data": [{"id": owner.model, "type": "model",
                              "display_name": "Fixture", "created_at": "2026-10-07T00:00:00Z"}],
                    "has_more": False, "first_id": owner.model, "last_id": owner.model,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.record()
                if owner.redirect:
                    self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    self.send_response(307)
                    self.send_header("Location", owner.redirect + urlsplit(self.path).path)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if urlsplit(self.path).path.endswith("/messages"):
                    self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    body = anthropic_fixture_sse(owner.model)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                try:
                    # Native Codex SSE grammar is the existing cited fixture.
                    super().do_POST()
                finally:
                    native.requests.clear()

        native.server.RequestHandlerClass = Handler

    @property
    def root(self):
        return self.url[:-3]

    def __enter__(self):
        self.native.__enter__()
        return self

    def __exit__(self, *args):
        return self.native.__exit__(*args)

    def counts(self):
        return {
            "listener": self.label, "total": len(self.rows),
            "post": sum(row["method"] == "POST" for row in self.rows),
            "model_post": sum(row["method"] == "POST" and
                              row["path"].endswith(("/responses", "/messages"))
                              for row in self.rows),
            "served_307": sum(row.get("response_status") == 307 for row in self.rows),
            "correlations": sorted({row["correlation"] for row in self.rows if row["correlation"]}),
        }


def fixture_counts(listeners):
    return {listener.label: listener.counts() for listener in listeners}


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class NativeTransportCells(unittest.TestCase):
    args = None
    worker = None
    observations = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gateway-transport-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.project = Path(self.temp.name) / "project"
        self.codex_home = self.home / ".codex"
        self.claude_home = self.home / ".claude"
        for directory in (self.project, self.codex_home, self.claude_home):
            directory.mkdir(parents=True, exist_ok=True)
        # These are fixture configuration files, never the actual user's homes.
        (self.codex_home / "config.toml").write_text("[features]\nplugins=false\n")
        os.environ.update(self.args.base_environment)
        os.environ.update(OPTOUTS)
        os.environ.update({
            "HOME": str(self.home), "CODEX_HOME": str(self.codex_home),
            "CLAUDE_CONFIG_DIR": str(self.claude_home),
        })
        for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
                    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
            os.environ.pop(key, None)
        self.started = []
        self.closed = set()
        self.terminal = {}

    @contextlib.contextmanager
    def observe_native_children(self):
        if self.args.client == "codex":
            from openai_codex.client import CodexClient
            from openai_codex import _run
            original = CodexClient.start
            original_close = CodexClient.close
            original_raise = _run._raise_for_failed_turn
            def start(client):
                original(client)
                if client._proc is not None:
                    self.started.append(client._proc.pid)
            def close(client):
                process = client._proc
                original_close(client)
                if process is not None and process.poll() is not None:
                    self.closed.add(process.pid)
            def completed(turn):
                # _run.py at the exact SDK pin raises RuntimeError for a failed
                # completed turn. Observe typed fields and preserve that raise.
                self.terminal = {
                    "native_terminal_kind": "TurnCompleted",
                    "native_terminal_status": turn.status.value,
                    "native_api_error_status": codex_http_status(turn.error),
                }
                return original_raise(turn)
            with patch.object(CodexClient, "start", start), \
                    patch.object(CodexClient, "close", close), \
                    patch.object(_run, "_raise_for_failed_turn", completed):
                yield
        else:
            from claude_agent_sdk import ClaudeSDKClient
            from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
            original = SubprocessCLITransport.connect
            original_close = ClaudeSDKClient.__aexit__
            async def connect(transport):
                await original(transport)
                if transport._process is not None:
                    self.started.append(transport._process.pid)
            async def close(client, *args):
                value = await original_close(client, *args)
                # Successful __aexit__ plus independent PID liveness is the
                # cleanup observation; no status is guessed from a POST.
                self.closed.update(pid for pid in self.started if not alive(pid))
                return value
            with patch.object(SubprocessCLITransport, "connect", connect), \
                    patch.object(ClaudeSDKClient, "__aexit__", close):
                yield

    def proxy_environment(self, proxy):
        for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
            os.environ[key] = proxy.root

    def invoke(self, endpoint, *, scanned_home=True, remove_pin=False, remove_proxy_guard=False):
        worker = self.worker
        with contextlib.ExitStack() as stack:
            if remove_proxy_guard:
                stack.enter_context(patch.object(
                    worker, "child_env",
                    lambda env: {key: value for key, value in env.items()
                                 if key not in {"NO_PROXY", "no_proxy"}}))
            if self.args.client == "codex":
                argv = [
                    "--workspace", str(self.project), "--base-url", endpoint,
                    worker.HOST_GATEWAY_OVERRIDE, "owned transport fixture",
                    "--codex-bin", str(self.args.native_bin), "--request-id", CORRELATION,
                    "--timeout", str(self.args.timeout), "--no-provider-retries", "--sandbox", "read-only",
                ]
                if scanned_home:
                    argv += ["--codex-home", str(self.codex_home)]
                argv += ["--prompt", FIXTURE_PROMPT]
                if remove_pin:
                    original = worker.runtime_config
                    prefix = f"model_providers.{worker.PROVIDER}.base_url="
                    def runtime_config(args):
                        config = original(args)
                        return replace(config, config_overrides=tuple(
                            value for value in config.config_overrides if not value.startswith(prefix)))
                    stack.enter_context(patch.object(worker, "runtime_config", runtime_config))
                stdout = io.StringIO()
                with patch.object(sys, "argv", ["worker.py", *argv]), contextlib.redirect_stdout(stdout):
                    exit_code = worker.main()
                result = json.loads(stdout.getvalue().splitlines()[-1])
                result["_worker_exit"] = exit_code
                result.update(self.terminal)
                return result
            argv = [
                "--cwd", str(self.project), "--gateway", endpoint[:-3],
                worker.HOST_GATEWAY_OVERRIDE, "owned transport fixture",
                "--timeout", str(self.args.timeout), "--max-turns", "1",
                "--setting-source", "user",
            ]
            original = worker.build_options
            def build_options(args):
                options = original(args)
                options.cli_path = str(self.args.native_bin)
                options.env["ANTHROPIC_CUSTOM_HEADERS"] += "\nX-Correlation-Id: " + CORRELATION
                if remove_pin:
                    options.settings = None
                return options
            stdout = io.StringIO()
            with patch.object(worker, "build_options", build_options), \
                    patch.object(sys, "stdin", io.StringIO(FIXTURE_PROMPT)), \
                    contextlib.redirect_stdout(stdout):
                exit_code = worker.main(argv)
            result = json.loads(stdout.getvalue().splitlines()[-1])
            observation = result.get("observation", {})
            terminal = observation.get("last_result") or {}
            return {"status": result.get("status") or result.get("observation", {}).get("status"),
                    "_worker_exit": exit_code,
                    "native_terminal_kind": "ResultMessage" if observation.get("result_count", 0) else None,
                    "native_result_is_error": terminal.get("is_error"),
                    "native_api_error_status": terminal.get("api_error_status"),
                    "native_terminal_reason": terminal.get("terminal_reason")}

    def observe(self, phase, result, listeners, *, exit_code=None):
        row = {
            "case": self._testMethodName, "phase": phase,
            "client": self.args.client, "status": result.get("status"),
            "requested_model": self.worker.DEFAULT_MODEL,
            "native_children_started": len(set(self.started)),
            "native_children_alive": sum(alive(pid) for pid in set(self.started)),
            "cleanup_settled": bool(self.started) and set(self.started).issubset(self.closed),
            "counts": fixture_counts(listeners), "usage": "UNKNOWN",
        }
        if exit_code is not None or "_worker_exit" in result:
            row["exit_code"] = result.get("_worker_exit") if exit_code is None else exit_code
        for name in ("cleanup_status", "phase", "error_type", "native_terminal_kind",
                     "native_terminal_status", "native_api_error_status",
                     "native_result_is_error", "native_terminal_reason"):
            if name in result:
                row[name] = result[name]
        self.observations.append(row)
        self.assertEqual(row["native_children_alive"], 0, "fixture native child remains alive")
        return row

    def assert_routed(self, row):
        self.assertGreater(row["counts"]["first"]["model_post"], 0, "no model-shaped fixture POST observed")
        self.assertEqual(row["counts"]["second"]["total"], 0, "second listener was reached")
        self.assertEqual(row["counts"]["proxy"]["total"], 0, "proxy listener was reached")

    def assert_completed(self, row):
        self.assertEqual(row["status"], "completed", "normal cell did not complete")
        self.assertEqual(row["exit_code"], 0, "normal cell exited nonzero")
        self.assertTrue(row["cleanup_settled"], "native cleanup did not settle")
        self.assertEqual(row["native_children_alive"], 0)
        if row["client"] == "codex":
            self.assertEqual(row["cleanup_status"], "closed")
            self.assertEqual(row["native_terminal_kind"], "TurnCompleted")
            self.assertEqual(row["native_terminal_status"], "completed")
        else:
            self.assertEqual(row["native_terminal_kind"], "ResultMessage")
            self.assertIs(row["native_result_is_error"], False)

    def assert_armed(self, row):
        self.assert_routed(row)
        self.assert_completed(row)

    def assert_redirect_refused(self, row):
        self.assert_routed(row)
        self.assertGreater(row["counts"]["first"]["served_307"], 0, "no 307 was served")
        self.assertTrue(row["cleanup_settled"], "native cleanup did not settle")
        self.assertEqual(row["native_children_alive"], 0)
        self.assertEqual(row.get("native_api_error_status"), 307,
                         "typed native result did not identify HTTP307")
        if row["client"] == "codex":
            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["exit_code"], 2)
            self.assertEqual(row["cleanup_status"], "closed")
            self.assertEqual(row.get("phase"), "turn_run")
            self.assertEqual(row.get("error_type"), "RuntimeError")
            self.assertEqual(row.get("native_terminal_kind"), "TurnCompleted")
            self.assertEqual(row.get("native_terminal_status"), "failed")
        else:
            self.assertEqual(row["status"], "native_error")
            self.assertEqual(row["exit_code"], 1)
            self.assertEqual(row.get("native_terminal_kind"), "ResultMessage")
            self.assertIs(row.get("native_result_is_error"), True)
            self.assertIn(row.get("native_terminal_reason"), (None, "completed"))

    def test_redirect(self):
        with CountingFixture("second", model=self.worker.DEFAULT_MODEL) as second, \
                CountingFixture("proxy", model=self.worker.DEFAULT_MODEL) as proxy, \
                CountingFixture("first", redirect=second.root, model=self.worker.DEFAULT_MODEL) as first:
            self.proxy_environment(proxy)
            with self.observe_native_children():
                result = self.invoke(first.url)
            row = self.observe("armed-307", result, (first, second, proxy))
            self.assert_redirect_refused(row)
            # curl's documented -L control proves both counters respond to a
            # POST-preserving 307 follow; it is not SDK/provider acceptance.
            before_first, before_second = len(first.rows), len(second.rows)
            control = subprocess.run([
                str(self.args.curl), "-q", "--noproxy", "*", "--location", "--request", "POST",
                "--data-binary", "{}", "--max-time", "3", "--output", os.devnull,
                first.url + "/responses",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            self.assertEqual(control.returncode, 0, "native curl redirect control failed")
            self.assertGreater(len(first.rows), before_first)
            self.assertGreater(len(second.rows), before_second)
            self.observe("curl-observer-control", {"status": "observed"}, (first, second, proxy),
                         exit_code=control.returncode)

    def test_proxy(self):
        with CountingFixture("second", model=self.worker.DEFAULT_MODEL) as second, \
                CountingFixture("proxy", model=self.worker.DEFAULT_MODEL) as proxy, \
                CountingFixture("first", model=self.worker.DEFAULT_MODEL) as first:
            self.proxy_environment(proxy)
            with self.observe_native_children():
                result = self.invoke(first.url)
            row = self.observe("armed-proxy", result, (first, second, proxy))
            self.assert_armed(row)
            for listener in (first, second, proxy):
                listener.rows.clear()
            with self.observe_native_children():
                result = self.invoke(first.url, remove_proxy_guard=True)
            row = self.observe("no-proxy-guard-control", result, (first, second, proxy))
            self.assert_completed(row)
            self.assertGreater(row["counts"]["proxy"]["model_post"], 0,
                               "disarmed native proxy guard did not exercise proxy counter")
            self.assertEqual(row["counts"]["second"]["total"], 0)

    def test_scanned_home(self):
        with CountingFixture("second") as second, CountingFixture("proxy") as proxy, \
                CountingFixture("first") as first:
            (self.codex_home / "fixture.config.toml").write_text(
                f'[model_providers.fixture]\nbase_url={json.dumps(second.url)}\n')
            with self.observe_native_children(), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as refused:
                self.invoke(first.url)
            self.assertEqual(refused.exception.code, 2)
            row = self.observe("scanned-home-refusal", {"status": "refused"}, (first, second, proxy),
                               exit_code=refused.exception.code)
            self.assertEqual(row["native_children_started"], 0)
            self.assertEqual(sum(v["total"] for v in row["counts"].values()), 0)

    def test_inherited_config_precedence(self):
        with CountingFixture("second") as second, CountingFixture("proxy") as proxy, \
                CountingFixture("first") as first:
            (self.codex_home / "config.toml").write_text(
                f'[features]\nplugins=false\n[model_providers.{self.worker.PROVIDER}]\n'
                f'base_url={json.dumps(second.url)}\n')
            with self.observe_native_children():
                result = self.invoke(first.url, scanned_home=False)
            row = self.observe("armed-inherited-config", result, (first, second, proxy))
            self.assert_armed(row)
            for listener in (first, second, proxy):
                listener.rows.clear()
            with self.observe_native_children():
                result = self.invoke(first.url, scanned_home=False, remove_pin=True)
            row = self.observe("endpoint-pin-removed-control", result, (first, second, proxy))
            self.assertEqual(row["exit_code"], 2)
            self.assertEqual(result["status"], "gateway_refused")
            self.assertIn(second.url, result.get("error", ""), "V2 did not name the owned effective listener")
            self.assertFalse(result["model_inference_submitted"])
            self.assertEqual(sum(v["total"] for v in row["counts"].values()), 0)

    def test_user_settings_precedence(self):
        with CountingFixture("second", model=self.worker.DEFAULT_MODEL) as second, \
                CountingFixture("proxy", model=self.worker.DEFAULT_MODEL) as proxy, \
                CountingFixture("first", model=self.worker.DEFAULT_MODEL) as first:
            (self.claude_home / "settings.json").write_text(
                json.dumps({"env": {"ANTHROPIC_BASE_URL": second.root}}))
            with self.observe_native_children():
                result = self.invoke(first.url)
            row = self.observe("armed-user-settings", result, (first, second, proxy))
            self.assert_armed(row)
            for listener in (first, second, proxy):
                listener.rows.clear()
            with self.observe_native_children():
                result = self.invoke(first.url, remove_pin=True)
            row = self.observe("settings-pin-removed-control", result, (first, second, proxy))
            self.assert_completed(row)
            self.assertGreater(row["counts"]["second"]["model_post"], 0,
                               "pin-removed control did not load the fixture user settings")
            self.assertEqual(row["counts"]["first"]["total"], 0)
            self.assertEqual(row["counts"]["proxy"]["total"], 0)


class MetadataResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append({"case": test._testMethodName, "result": "pass"})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.rows.append({"case": test._testMethodName, "result": "fail",
                          "error_type": error[0].__name__})

    def addError(self, test, error):
        super().addError(test, error)
        self.rows.append({"case": test._testMethodName, "result": "unfinished",
                          "error_type": error[0].__name__})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--client", choices=tuple(PINS), required=True)
    parser.add_argument("--native-bin", type=Path, required=True)
    parser.add_argument("--curl", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args(argv)
    args.base_environment = safe_environment()
    receipt = {
        "schema": "native-agent-stack/gateway-transport-fixtures/v1",
        "evidence_class": "local_native_sdk_integration_with_authored_fixtures",
        "client": args.client, "head": args.expected_head,
        "utc": datetime.now(timezone.utc).isoformat(), "host_label": "owned-fixture",
        "expected_cases": list(CASES[args.client]),
        "ran": 0, "skipped": 0, "status": "unfinished",
        "usage": "UNKNOWN", "cases": [], "observations": [],
    }
    try:
        if not args.output.is_absolute() or args.output.exists():
            raise ValueError("output must be a new absolute durable path")
        if not 0 < args.timeout <= 60:
            raise ValueError("fixture timeout must be bounded")
        for executable in (args.native_bin, args.curl):
            if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
                raise ValueError("a caller-supplied executable is unavailable")
        head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        if head != args.expected_head:
            raise ValueError("tested head differs from the caller's expected head")
        receipt["sdk_version"] = importlib.metadata.version(PACKAGES[args.client])
        if receipt["sdk_version"] != PINS[args.client]:
            raise ValueError("SDK differs from the required pin")
        # Native SDKs read these system policy sources regardless of HOME.
        # Presence is value-free; do not open them or qualify through them.
        if Path("/etc/claude-code" if args.client == "claude" else "/etc/codex").exists():
            raise ValueError("a system configuration source prevents a fixture-only run")
        worker = load_worker(args.client)
        receipt["source_sha256"] = {
            str(Path(worker.__file__).relative_to(ROOT)): hashlib.sha256(Path(worker.__file__).read_bytes()).hexdigest(),
            "examples/omniroute-codex-sdk/test_worker.py": hashlib.sha256(
                (ROOT / "examples/omniroute-codex-sdk/test_worker.py").read_bytes()).hexdigest(),
            "tests/lane_gateway_transport.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        # A head label alone is inadequate if the tested implementation or
        # observer differs from that commit. Root commits preparation first.
        for path, digest in receipt["source_sha256"].items():
            blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{head}:{path}"],
                                           stderr=subprocess.DEVNULL)
            if hashlib.sha256(blob).hexdigest() != digest:
                raise ValueError("a tested input differs from the expected committed head")
        with tempfile.TemporaryDirectory(prefix="gateway-native-version-") as home:
            version_env = {**args.base_environment, **OPTOUTS, "HOME": home,
                           "CODEX_HOME": home, "CLAUDE_CONFIG_DIR": home}
            version = subprocess.run([str(args.native_bin), "--version"], env=version_env,
                                     capture_output=True, text=True, timeout=5, check=False)
            if version.returncode != 0 or not re.search(
                    r"(?<![0-9])" + re.escape(CLI_PINS[args.client]) + r"(?![0-9])", version.stdout):
                raise ValueError("native runtime differs from the required pin")
        receipt["native_version"] = CLI_PINS[args.client]
        NativeTransportCells.args, NativeTransportCells.worker = args, worker
        NativeTransportCells.observations = receipt["observations"]
        suite = unittest.TestSuite(NativeTransportCells(name) for name in CASES[args.client])
        result = MetadataResult()
        suite.run(result)
        receipt.update(ran=result.testsRun, skipped=len(result.skipped), cases=result.rows)
        complete = result.testsRun == len(CASES[args.client]) and not result.skipped and result.wasSuccessful()
        receipt["status"] = "passed" if complete else "unfinished"
    except Exception as error:
        # Never serialize a native SDK exception message, config, stdout or body.
        receipt["error_type"] = type(error).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        json.dump(receipt, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"client": args.client, "status": receipt["status"],
                      "ran": receipt["ran"], "skipped": receipt["skipped"]}, sort_keys=True))
    return 0 if receipt["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
