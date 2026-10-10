"""Tests for tools/credentials/anthropic_key_health.py, the no-token health check of the Anthropic key slots.

Local integration checks, not upstream acceptance (docs/acceptance-evidence-policy.md). No test makes a network call
or reads a real store: the HTTP side is always a fake opener, and the runner is either a fake or the real
credential_run.py over a temporary XDG_CONFIG_HOME holding a synthetic key. Every key and organization id is generated
per test, so no file holds one.
"""
from __future__ import annotations

import contextlib
import email.message
import hashlib
import http.client
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
TOOL = TOOLS / "anthropic_key_health.py"
sys.path.insert(0, str(TOOLS))
import anthropic_key_health as health  # noqa: E402
import set_credential as writer  # noqa: E402

NAME = "ANTHROPIC_API_KEY"
SLOTS = ["anthropic-api", "anthropic-api-2", "anthropic-api-3", "anthropic-api-4", "anthropic-api-5",
         "anthropic-api-6", "anthropic-api-7", "anthropic-api-8", "anthropic-api-9", "anthropic-api-10"]
MODELS_URL = "https://api.anthropic.com/v1/models"
ORGANIZATION_URL = "https://api.anthropic.com/v1/organizations/me"
# Letters g-v stand in for hex digits, so no six-character piece of a value matches a hex digest by chance (the same
# convention as tests/test_credential_run.py).
FAKE_LETTERS = str.maketrans("0123456789abcdef", "ghijklmnopqrstuv")


def fake_key() -> str:
    return "sk-test-" + os.urandom(16).hex().translate(FAKE_LETTERS)


def fake_organization() -> str:
    return str(uuid.uuid4())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def headers(**values) -> email.message.Message:
    message = email.message.Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


class Response:
    def __init__(self, status: int, response_headers):
        self.status, self.headers, self.closed = status, response_headers, False

    def close(self):
        self.closed = True

    def read(self, *args):  # pragma: no cover - the probe must never read a body
        raise AssertionError("the probe read a response body")


class Opener:
    """A fake opener: records each request and answers in order with (status, headers) or by raising an exception.
    A status of 400 or more is raised as HTTPError, as urllib's HTTPErrorProcessor does."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        status, response_headers = answer
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error", response_headers, None)
        return Response(status, response_headers)


def assert_never_echoed(case: unittest.TestCase, text: str, *values: str) -> None:
    """Neither a value nor any six-character piece of one."""
    for value in values:
        case.assertNotIn(value, text)
        pieces = {value[i:i + 6] for i in range(len(value) - 5)}
        case.assertEqual(sorted(piece for piece in pieces if piece in text), [])


class ProbeTests(unittest.TestCase):
    """The --probe child, which holds the key: fake HTTP only."""

    def test_two_gets_with_the_key_from_the_environment_and_the_headers_from_stdin(self):
        key, organization = fake_key(), fake_organization()
        opener = Opener((200, headers(anthropic_organization_id=organization, request_id="req_x")), (200, headers()))
        result = health.probe(health.read_spec(health.spec()), {NAME: key}, opener=opener)
        self.assertEqual([(request.get_method(), request.full_url) for request, _ in opener.requests],
                         [("GET", MODELS_URL), ("GET", ORGANIZATION_URL)])
        for request, timeout in opener.requests:
            self.assertEqual(request.get_header("X-api-key"), key)
            self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")
            self.assertEqual(request.get_header("User-agent"), health.REQUEST_HEADERS["user-agent"])
            self.assertIsNone(request.data)
            self.assertEqual(timeout, health.REQUEST_SECONDS)
        self.assertEqual(result, {"models": {"status": 200}, "organization": {"status": 200},
                                  "organization_id_prefix": organization[:8]})
        rendered = json.dumps(result)
        assert_never_echoed(self, rendered, key)
        self.assertNotIn(organization, rendered)

    def test_http_errors_report_their_status_only(self):
        key, organization = fake_key(), fake_organization()
        result = health.probe(health.read_spec(health.spec()), {NAME: key},
                              opener=Opener((401, headers()), (401, headers())))
        self.assertEqual(result, {"models": {"status": 401}, "organization": {"status": 401},
                                  "organization_id_prefix": None})
        # A throttled key still names its organization in the response header.
        result = health.probe(health.read_spec(health.spec()), {NAME: key}, opener=Opener(
            (429, headers(anthropic_organization_id=organization)), (403, headers())))
        self.assertEqual(result, {"models": {"status": 429}, "organization": {"status": 403},
                                  "organization_id_prefix": organization[:8]})

    def test_failures_report_only_the_error_type(self):
        key = fake_key()
        for error in (urllib.error.URLError("down"), http.client.BadStatusLine("junk"), TimeoutError("slow"),
                      ValueError(f"invalid header value {key!r}")):
            with self.subTest(error=type(error).__name__):
                result = health.probe(health.read_spec(health.spec()), {NAME: key},
                                      opener=Opener(error, (200, headers())))
                self.assertEqual(result["models"], {"status": None, "error": type(error).__name__})
                self.assertEqual(result["organization"], {"status": 200})
                assert_never_echoed(self, json.dumps(result), key)

    def test_the_organization_prefix_is_kept_only_when_plain(self):
        key = fake_key()
        for value in ("<script>alert", "short", "org id with spaces", ""):
            with self.subTest(value=value):
                result = health.probe(health.read_spec(health.spec()), {NAME: key}, opener=Opener(
                    (200, headers(anthropic_organization_id=value)), (200, headers())))
                self.assertIsNone(result["organization_id_prefix"])

    def test_stdin_may_name_only_the_allowed_headers(self):
        key = fake_key()
        refused = {
            b"not json": "spec_not_json",
            json.dumps({"headers": {"x-api-key": key, "anthropic-version": "2023-06-01"}}).encode():
                "header_not_allowed",
            json.dumps({"headers": {"Authorization": "Bearer " + key, "anthropic-version": "2023-06-01"}}).encode():
                "header_not_allowed",
            json.dumps({"headers": {"anthropic-version": "2023-06-01\r\nx-api-key: " + key}}).encode():
                "header_value_not_plain",
            json.dumps({"headers": {"anthropic-version": "2023-06-01"}, "url": "https://example.com"}).encode():
                "spec_shape",
            json.dumps({"headers": {"user-agent": "x"}}).encode(): "anthropic_version_missing",
            json.dumps({"headers": {"anthropic-version": "x" * health.MAX_SPEC_BYTES}}).encode(): "spec_too_large",
        }
        for data, reason in refused.items():
            with self.subTest(reason=reason):
                opener = Opener()
                stdout = io.StringIO()
                code = health.probe_main(io.BytesIO(data), stdout, {NAME: key}, opener=opener)
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(stdout.getvalue()), {"error": reason})
                self.assertEqual(opener.requests, [])
                assert_never_echoed(self, stdout.getvalue(), key)

    def test_no_request_without_a_key(self):
        opener = Opener()
        self.assertEqual(health.probe(health.read_spec(health.spec()), {}, opener=opener), {"error": "key_absent"})
        self.assertEqual(opener.requests, [])

    def test_the_default_opener_follows_no_redirect(self):
        request = urllib.request.Request(MODELS_URL, headers={"x-api-key": "k"})
        self.assertIsNone(health._NoRedirect().redirect_request(request, None, 302, "Found", headers(),
                                                                "https://elsewhere.example/stolen"))
        built = []

        def build_opener(*handlers):
            built.append(handlers)
            return Opener((200, headers()), (200, headers()))

        with mock.patch.object(health.urllib.request, "build_opener", build_opener):
            health.probe(health.read_spec(health.spec()), {NAME: fake_key()})
        self.assertEqual(len(built), 1)
        self.assertEqual([type(handler) for handler in built[0]], [health._NoRedirect])

    def test_probe_mode_prints_one_json_line(self):
        key, organization = fake_key(), fake_organization()
        stdin = mock.Mock(buffer=io.BytesIO(health.spec()))
        stdout = io.StringIO()
        opener = Opener((200, headers(anthropic_organization_id=organization)), (200, headers()))
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", stdout), \
                mock.patch.dict(os.environ, {NAME: key}), \
                mock.patch.object(health.urllib.request, "build_opener", return_value=opener):
            code = health.main(["--probe"])
        self.assertEqual(code, 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["organization_id_prefix"], organization[:8])
        assert_never_echoed(self, stdout.getvalue(), key)

    def test_unexpected_errors_print_only_their_type(self):
        key = fake_key()

        class Broken:
            def open(self, request, timeout):
                raise RuntimeError("would quote " + key)

        stdout = io.StringIO()
        code = health.probe_main(io.BytesIO(health.spec()), stdout, {NAME: key}, opener=Broken())
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), {"error": "unexpected_RuntimeError"})


class FakeRunner:
    """Stands in for subprocess.run: answers credential_run.py --check for each slot state and the probe with a canned
    child line, and records every call."""

    def __init__(self, states: dict, probes: dict | None = None, stderr: bytes = b""):
        self.states, self.probes, self.stderr, self.calls = states, probes or {}, stderr, []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        slot = argv[2]
        if argv[3:] == ["--check"]:
            state = self.states.get(slot, "missing")
            text = {"ok": f"{slot}: ok; would inject {NAME} (masked)\n",
                    "missing": f"{slot}: missing (<store>/{slot}.env); add it with: "
                               f"bash tools/credentials/open_credential_terminal.sh {slot}\n",
                    "unsafe": f"{slot}: unsafe (mode_not_0600)\n"}[state]
            return subprocess.CompletedProcess(argv, 0 if state == "ok" else 1, text.encode(), b"")
        line = self.probes[slot]
        stdout = line if isinstance(line, bytes) else (json.dumps(line) + "\n").encode()
        return subprocess.CompletedProcess(argv, 0, stdout, self.stderr)


def child_line(models=200, organization=200, prefix=None) -> dict:
    return {"models": {"status": models}, "organization": {"status": organization}, "organization_id_prefix": prefix}


class ParentTests(unittest.TestCase):
    """The parent, which never holds a key: fake runner only."""

    def run_main(self, runner, *args) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = health.main(list(args), run=runner, stdout=stdout)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_the_slots_are_the_ten_anthropic_api_entries_in_inventory_order(self):
        self.assertEqual(health.slots(), SLOTS)

    def test_commands_carry_no_value_and_the_headers_go_on_stdin(self):
        prefix = fake_organization()[:8]
        runner = FakeRunner({"anthropic-api-4": "ok"}, {"anthropic-api-4": child_line(prefix=prefix)})
        code, _out, _err = self.run_main(runner, "--slot", "anthropic-api-4")
        self.assertEqual(code, 0)
        (check_argv, check_kwargs), (probe_argv, probe_kwargs) = runner.calls
        self.assertEqual(check_argv, [sys.executable, str(health.RUNNER), "anthropic-api-4", "--check"])
        self.assertIs(check_kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(probe_argv, [sys.executable, str(health.RUNNER), "anthropic-api-4", "--only", NAME, "--",
                                      sys.executable, "-I", "-S", str(TOOL), "--probe"])
        self.assertEqual(json.loads(probe_kwargs["input"]),
                         {"headers": {"anthropic-version": "2023-06-01",
                                      "user-agent": "native-agent-stack-anthropic-key-health/1"}})
        self.assertNotIn(b"x-api-key", probe_kwargs["input"].lower())
        for _argv, kwargs in runner.calls:
            self.assertTrue(kwargs["capture_output"])
            self.assertEqual(kwargs["timeout"], health.RUNNER_SECONDS)

    def test_every_state_is_reported_and_only_stored_problems_fail(self):
        first, second = fake_organization()[:8], fake_organization()[:8]
        runner = FakeRunner({"anthropic-api-4": "ok", "anthropic-api-3": "ok", "anthropic-api-7": "unsafe"},
                            {"anthropic-api-4": child_line(prefix=first),
                             "anthropic-api-3": child_line(401, 401)})
        code, out, err = self.run_main(runner, "--slot", "anthropic-api-4", "--slot", "anthropic-api-3",
                                       "--slot", "anthropic-api-6", "--slot", "anthropic-api-7")
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertEqual(out.splitlines(), [
            f"anthropic-api-4: stored; valid (GET /v1/models 200, 2xx); GET /v1/organizations/me 200; "
            f"organization {first}",
            "anthropic-api-3: stored; invalid (GET /v1/models 401, 4xx); GET /v1/organizations/me 401; "
            "organization ?",
            "anthropic-api-6: not stored",
            "anthropic-api-7: unsafe (mode_not_0600)"])
        runner = FakeRunner({"anthropic-api-5": "ok"}, {"anthropic-api-5": child_line(prefix=second)})
        code, out, _err = self.run_main(runner)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.splitlines()), len(SLOTS))
        self.assertEqual(sum(line.endswith(": not stored") for line in out.splitlines()), len(SLOTS) - 1)
        # A slot that is not stored starts nothing beyond its --check.
        self.assertEqual([argv[3:] for argv, _kwargs in runner.calls].count(["--check"]), len(SLOTS))
        self.assertEqual(len(runner.calls), len(SLOTS) + 1)

    def test_validity_follows_the_status_class(self):
        expected = {200: ("valid", "2xx"), 204: ("valid", "2xx"), 401: ("invalid", "4xx"),
                    403: ("forbidden", "4xx"), 429: ("rate_limited", "4xx"), 404: ("unexpected", "4xx"),
                    302: ("unexpected", "3xx"), 500: ("server_error", "5xx"), 529: ("server_error", "5xx"),
                    None: ("unreachable", "none")}
        for status, (word, cls) in expected.items():
            with self.subTest(status=status):
                self.assertEqual((health.validity(status), health.status_class(status)), (word, cls))

    def test_json_report(self):
        prefix = fake_organization()[:8]
        runner = FakeRunner({"anthropic-api-5": "ok"}, {"anthropic-api-5": child_line(prefix=prefix)})
        code, out, _err = self.run_main(runner, "--json", "--slot", "anthropic-api-5", "--slot", "anthropic-api-6")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertRegex(report["checked_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(report["slots"], [
            {"id": "anthropic-api-5", "state": "stored", "models_status": 200, "status_class": "2xx",
             "validity": "valid", "organization_status": 200, "organization_id_prefix": prefix},
            {"id": "anthropic-api-6", "state": "not stored", "detail": "<store>/anthropic-api-6.env"}])

    def test_unknown_words_are_usage_errors_and_never_repeated(self):
        typed = fake_key()
        for args in (["--slot", typed], [typed], ["--slot"], ["--probe", "--json"]):
            with self.subTest(args=len(args)):
                runner = FakeRunner({})
                code, out, err = self.run_main(runner, *args)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("usage error", err)
                assert_never_echoed(self, err, typed)
                self.assertEqual(runner.calls, [])

    def test_unreadable_child_output_reports_only_the_runners_own_message(self):
        runner = FakeRunner({"anthropic-api-4": "ok"}, {"anthropic-api-4": b"not json\n"},
                            stderr=b"credential_run: anthropic-api-4: unsafe: mode_not_0600\n")
        code, out, _err = self.run_main(runner, "--slot", "anthropic-api-4")
        self.assertEqual(code, 1)
        self.assertEqual(out, "anthropic-api-4: stored; probe failed "
                              "(credential_run: anthropic-api-4: unsafe: mode_not_0600)\n")
        secret = fake_key()
        runner = FakeRunner({"anthropic-api-4": "ok"}, {"anthropic-api-4": b""},
                            stderr=f"Traceback: {secret}\n".encode())
        code, out, _err = self.run_main(runner, "--slot", "anthropic-api-4")
        self.assertEqual(code, 1)
        self.assertEqual(out, "anthropic-api-4: stored; probe failed (probe_output_unreadable (exit 0))\n")
        assert_never_echoed(self, out, secret)

    def test_fields_outside_the_child_contract_never_reach_the_report(self):
        name, body = "Example Organization Name", fake_key()
        line = {**child_line(prefix="abcd1234"), "organization_name": name, "body": body,
                "models": {"status": 200, "body": body}}
        runner = FakeRunner({"anthropic-api-4": "ok"}, {"anthropic-api-4": line})
        for args in ((), ("--json",)):
            with self.subTest(json=bool(args)):
                code, out, _err = self.run_main(runner, *args, "--slot", "anthropic-api-4")
                self.assertEqual(code, 0)
                self.assertNotIn(name, out)
                assert_never_echoed(self, out, body)
        bad = {**child_line(prefix="abcd1234"), "error": "quote\nme " + body}
        runner = FakeRunner({"anthropic-api-4": "ok"}, {"anthropic-api-4": bad})
        _code, out, _err = self.run_main(runner, "--slot", "anthropic-api-4")
        self.assertEqual(out, "anthropic-api-4: stored; probe failed (unprintable)\n")


def _host_hands_cores_to_a_collector() -> bool:
    try:
        with open("/proc/sys/kernel/core_pattern", "rb") as handle:
            return handle.read(1) in (b"|", b"@")
    except OSError:
        return False


# credential_run.py refuses to start where crash dumps go to a collector (a CI runner commonly does). There the real
# runner is started through this launcher, which points its CORE_PATTERN_FILE at a temporary file holding "core", as
# tests/test_credential_run.py does. The variable is read here, in the test's launcher, never by either tool.
HOST_PIPES_CORES = os.environ.get("CREDENTIAL_RUN_TEST_LAUNCHER") == "1" or _host_hands_cores_to_a_collector()
LAUNCHER = ("import os, sys\n"
            f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
            "import credential_run\n"
            "credential_run.CORE_PATTERN_FILE = os.environ.pop('CORE_PATTERN_TEST_FILE')\n"
            "sys.exit(credential_run.main(sys.argv[1:]))\n")
# The probe child with a fake opener in place of the network: it runs the tool's own probe_main on its real stdin and
# environment, and writes what the opener saw (the key only as its SHA-256) to the file named by argv[1]. argv[2] is
# the synthetic organization id the fake response header carries.
CHILD = ("import email.message, hashlib, json, os, sys\n"
         f"sys.path.insert(0, {str(TOOLS)!r})\n"
         "import anthropic_key_health as tool\n"
         "seen = []\n"
         "class Response:\n"
         "    status = 200\n"
         "    def __init__(self, headers):\n"
         "        self.headers = headers\n"
         "    def close(self):\n"
         "        pass\n"
         "class Opener:\n"
         "    def open(self, request, timeout):\n"
         "        seen.append({'method': request.get_method(), 'url': request.full_url,\n"
         "                     'key_sha256': hashlib.sha256(request.get_header('X-api-key').encode()).hexdigest(),\n"
         "                     'version': request.get_header('Anthropic-version')})\n"
         "        headers = email.message.Message()\n"
         "        headers['anthropic-organization-id'] = sys.argv[2]\n"
         "        return Response(headers)\n"
         "code = tool.probe_main(sys.stdin.buffer, sys.stdout, os.environ, opener=Opener())\n"
         "with open(sys.argv[1], 'w', encoding='utf-8') as handle:\n"
         "    json.dump(seen, handle)\n"
         "sys.exit(code)\n")


class RealRunnerTests(unittest.TestCase):
    """The real credential_run.py over a temporary store with a synthetic key; the HTTP side is the fake above."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.store = self.base / "cfg" / "native-agent-stack"
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.base / "home"),
                    "XDG_CONFIG_HOME": str(self.base / "cfg")}
        if HOST_PIPES_CORES:
            core_pattern = self.base / "core_pattern"
            core_pattern.write_text("core\n")
            self.env["CORE_PATTERN_TEST_FILE"] = str(core_pattern)

    def plant(self, slot: str, value: str) -> None:
        self.store.mkdir(parents=True, exist_ok=True)
        self.store.chmod(0o700)
        path = self.store / f"{slot}.env"
        path.write_text(writer.encode(NAME, value), encoding="ascii")
        path.chmod(0o600)

    def runner(self, observed: Path, organization: str):
        def run(argv, **kwargs):
            argv = list(argv)
            self.assertEqual(argv[:2], [sys.executable, str(health.RUNNER)])
            if "--" in argv:
                cut = argv.index("--")
                self.assertEqual(argv[cut + 1:], [sys.executable, "-I", "-S", str(TOOL), "--probe"])
                argv = [*argv[:cut + 1], sys.executable, "-I", "-S", "-c", CHILD, str(observed), organization]
            if HOST_PIPES_CORES:
                argv = [sys.executable, "-I", "-S", "-c", LAUNCHER, *argv[2:]]
            return subprocess.run(argv, env=self.env, **kwargs)
        return run

    def test_the_real_runner_injects_the_key_and_the_report_holds_none_of_it(self):
        key, organization = fake_key(), fake_organization()
        self.plant("anthropic-api-5", key)
        observed = self.base / "observed.json"
        stdout = io.StringIO()
        code = health.main(["--slot", "anthropic-api-5", "--slot", "anthropic-api-6"],
                           run=self.runner(observed, organization), stdout=stdout)
        out = stdout.getvalue()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines(), [
            "anthropic-api-5: stored; valid (GET /v1/models 200, 2xx); GET /v1/organizations/me 200; "
            f"organization {organization[:8]}",
            "anthropic-api-6: not stored"])
        seen = json.loads(observed.read_text(encoding="utf-8"))
        self.assertEqual([(entry["method"], entry["url"]) for entry in seen],
                         [("GET", MODELS_URL), ("GET", ORGANIZATION_URL)])
        self.assertEqual({entry["key_sha256"] for entry in seen}, {sha(key)})
        self.assertEqual({entry["version"] for entry in seen}, {"2023-06-01"})
        assert_never_echoed(self, out, key)
        self.assertNotIn(organization, out)
        self.assertNotIn(str(self.base), out)


if __name__ == "__main__":
    unittest.main()
