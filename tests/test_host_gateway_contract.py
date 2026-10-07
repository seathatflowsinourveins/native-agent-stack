"""The revision 3.1 A6/F8/T15/T16 contract checks (synthetic local fixtures).

The four A holders are required now. Other registered holders are checked when
their marker/call arrives; A6c makes every row required after A/B/C/E1/F merge.
No native unit, host record, gateway, provider or Windows command is exercised.
"""

import ast
import builtins
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/omniroute/host_gateway.py"
BEGIN = "# --- host-gateway " + "contract v2 (identical in every holder; tests/test_host_gateway_contract.py) ---"
END = "# --- end host-gateway " + "contract v2 ---"
ADAPTER_NAMES = ("GATEWAY_FLAGS", "GATEWAY_VARIABLES", "GATEWAY_OVERRIDES", "GATEWAY_HOMES")
GATEWAY_ENV = ("OPENAI_BASE_URL", "WORKER_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_BASE_URL")
IDENTITY = "1234567890abcdef1234567890abcdef"
IDENTITY_HASH = hashlib.sha256(IDENTITY.encode("ascii")).hexdigest()
HOST = "fixture-host"
PORT = 45432
OTHER = 45433
ENDPOINT = f"http://127.0.0.1:{PORT}/v1"
UNIT = "fixture-gateway.service"
PID = 876543210


def adapter(flags=None, variables=(), overrides=(), homes=()):
    return {"GATEWAY_FLAGS": flags or {}, "GATEWAY_VARIABLES": variables,
            "GATEWAY_OVERRIDES": overrides, "GATEWAY_HOMES": homes}


# One row per holder. Paths and adapter literals follow the reviewed A/B/E1/F
# change sets. F2's four host entries need its owner's final adapter metadata;
# a marker there fails until that metadata is supplied. netprobe.py is a
# container-side consumer, deliberately not a block holder (F2 revision 3).
HOLDERS = (
    {"path": "tools/omniroute/host_gateway.py", "kind": "block", "owner_row": "A4", "required_now": True,
     "adapter": adapter({"--base-url": "lambda value: value"}), "routing_test": "tests/test_host_gateway_contract.py:T16"},
    {"path": "examples/omniroute-codex-sdk/worker.py", "kind": "block", "owner_row": "A1", "required_now": True,
     "adapter": adapter({"--base-url": "lambda value: value"}, ("OPENAI_BASE_URL", "WORKER_BASE_URL"), homes=("--codex-home",)),
     "routing_test": "tests/test_gateway_worker_defaults.py:T25,T27; tests/lane_gateway_transport.py:T17,T17d"},
    {"path": "examples/deepagents-omniroute/worker.py", "kind": "block", "owner_row": "A2", "required_now": True,
     "adapter": adapter({"--base-url": "lambda value: value"}, ("OPENAI_BASE_URL", "OPENAI_API_BASE")),
     "routing_test": "tests/test_gateway_worker_defaults.py:T11,T26"},
    {"path": "examples/claude-runtime-sdk/worker.py", "kind": "block", "owner_row": "A3", "required_now": True,
     "adapter": adapter({"--gateway": 'lambda v: v.strip().rstrip("/") + "/v1"'}, ("ANTHROPIC_BASE_URL",)),
     "routing_test": "tests/test_gateway_worker_defaults.py:T11; tests/lane_gateway_transport.py:T17,T17d"},
    {"path": "blueprints/us-equities/workers/native_worker.py", "kind": "block", "owner_row": "B1", "required_now": False,
     "adapter": adapter({"--gateway-base-url": "lambda v: v"}, ("OPENAI_BASE_URL",), ("--config-override",), ("--codex-home",)),
     "routing_test": "tests/test_native_worker_route.py:T20,T25,T27; B lane:T17"},
    {"path": "blueprints/us-equities/routing/omniroute-astra.py", "kind": "block", "owner_row": "B2", "required_now": False,
     "adapter": adapter({"--base-url": "lambda v: v"}, ("OPENAI_BASE_URL",)),
     "routing_test": "tests/test_omniroute_astra.py:T11,T19; B lane:T17"},
    {"path": "tools/sota-convergence/landscape-sweep/build_args.py", "kind": "block", "owner_row": "E1a", "required_now": False,
     "adapter": adapter({"--omniroute-base-url": "lambda v: v", "--fallback-codex-host": 'lambda v: f"http://{v.strip()}/v1"'}, ("OPENAI_BASE_URL",)),
     "routing_test": "tests/test_sota_convergence_sweep.py:T23,T24"},
    {"path": "tools/sota-convergence/landscape-sweep/codex_job.py", "kind": "block", "owner_row": "E1b", "required_now": False,
     "adapter": adapter(variables=("OPENAI_BASE_URL",)),
     "routing_test": "tests/test_sota_convergence_sweep.py:T24,T24p; E1 lane:T17p"},
    {"path": "blueprints/runtime-workers/openhands/recipe.py", "kind": "block", "owner_row": "F2", "required_now": False,
     "adapter": None, "adapter_pending": "F2 owner final reviewed adapter", "routing_test": "tests/test_runtime_worker_openhands.py:T28"},
    {"path": "blueprints/runtime-workers/openhands/dispatch.py", "kind": "block", "owner_row": "F2", "required_now": False,
     "adapter": None, "adapter_pending": "F2 owner final reviewed adapter", "routing_test": "tests/test_runtime_worker_openhands.py:T28"},
    {"path": "blueprints/runtime-workers/openhands/host.py", "kind": "block", "owner_row": "F2", "required_now": False,
     "adapter": None, "adapter_pending": "F2 owner final reviewed adapter", "routing_test": "tests/test_runtime_worker_openhands.py:T28"},
    {"path": "examples/openhands-native-capabilities/native-config.py", "kind": "block", "owner_row": "F2", "required_now": False,
     "adapter": None, "adapter_pending": "F2 owner final reviewed adapter", "routing_test": "tests/test_openhands_native_capabilities.py:T28"},
    {"path": "tools/token-e2e/freeze_snapshot.py", "kind": "block", "owner_row": "F5", "required_now": False,
     "adapter": adapter(), "routing_test": "tests/test_freeze_snapshot.py:T30"},
    {"path": "tools/omniroute/gateway_record.py", "kind": "block", "owner_row": "F6", "required_now": False,
     "adapter": adapter(), "routing_test": "tests/test_gateway_record_guard.py:T28 (no management routes)"},
    {"path": "tools/research/gpt_researcher.sh", "kind": "delegate", "owner_row": "F1", "required_now": False,
     "adapter": "python3 -I tools/omniroute/host_gateway.py print", "routing_test": "tests/test_research_entry.py:T28 (stub print child)"},
    {"path": "observability/native-data/render.py", "kind": "delegate", "owner_row": "F3", "required_now": False,
     "adapter": "python3 -I tools/omniroute/host_gateway.py print --root", "routing_test": "tests/test_native_dashboard_data.py:T28 (mocked print child or injected run)"},
    {"path": "tools/adoption/apply_codex_lane.py", "kind": "delegate", "owner_row": "F10", "required_now": False,
     "adapter": "python3 -I tools/omniroute/host_gateway.py print", "routing_test": "tests/test_codex_worker_lane.py:T29 (mocked print child; opt-in real host)"},
    {"path": "tools/adoption/new_wsl_client_config.py", "kind": "delegate", "owner_row": "C7", "required_now": False,
     "adapter": "python3 -I tools/omniroute/host_gateway.py print", "routing_test": "tests/test_new_wsl_client_config.py:C7 (mocked print child)"},
)


def block_text(source):
    lines = source.splitlines(keepends=True)
    starts = [n for n, line in enumerate(lines) if line.rstrip("\r\n") == BEGIN]
    ends = [n for n, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise AssertionError("holder must have exactly one ordered begin and end marker, as whole lines")
    return "".join(lines[starts[0]:ends[0] + 1])


def adapter_ast(source):
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ADAPTER_NAMES:
                    if target.id in found:
                        raise AssertionError(f"adapter constant defined twice: {target.id}")
                    found[target.id] = node.value
    if set(found) != set(ADAPTER_NAMES):
        raise AssertionError("holder must define all four adapter constants")
    return found


def expected_adapter_ast(row):
    expected = {}
    for name, value in row["adapter"].items():
        if name == "GATEWAY_FLAGS":
            text = "{" + ",".join(repr(k) + ": " + v for k, v in value.items()) + "}"
        else:
            text = repr(value)
        expected[name] = ast.parse(text, mode="eval").body
    return expected


def fixed_ports(source):
    errors = []
    shape = re.compile(r"(?:localhost\.?|127(?:\.\d{1,3}){0,3}|0\.0\.0\.0|\[(?:::1|::ffff:127\.0\.0\.1)\]):[0-9]+", re.I)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int) and not isinstance(node.value, bool) and node.value in {20128, 20129, 21128, 21129}:
                errors.append(f"line {node.lineno}: fixed port integer")
            if isinstance(node.value, str) and shape.search(node.value):
                errors.append(f"line {node.lineno}: fixed loopback URL")
    return errors


def forbidden_definitions(source):
    """Definitions are forbidden outside holders; fixture strings alone are not definitions."""
    if "GatewayRefused" not in source and "--unrecorded-gateway-reason" not in source:
        return []
    errors = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == "GatewayRefused":
            errors.append(f"line {node.lineno}: GatewayRefused defined outside registry")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if any(isinstance(arg, ast.Constant) and arg.value == "--unrecorded-gateway-reason" for arg in node.args):
                errors.append(f"line {node.lineno}: gateway override defined outside registry")
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "HOST_GATEWAY_OVERRIDE" for t in node.targets):
                errors.append(f"line {node.lineno}: gateway override constant outside registry")
    return errors


def delegate_call(source, shell=False):
    if shell:
        return bool(re.search(r"python\S*\s+-I\s+[^\n]*tools/omniroute/host_gateway\.py[^\n]*\sprint\b", source))
    tree = ast.parse(source)
    bindings = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Name)}

    def strings(node, seen=()):
        result = []
        for part in ast.walk(node):
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                result.append(part.value)
            elif isinstance(part, ast.Name) and part.id in bindings and part.id not in seen:
                result.extend(strings(bindings[part.id], (*seen, part.id)))
        return result

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        if name not in {"run", "check_output", "Popen"}:
            continue
        values = strings(node.args[0])
        named = "tools/omniroute/host_gateway.py" in values or {"tools", "omniroute", "host_gateway.py"} <= set(values)
        if named and "-I" in values and "print" in values:
            return True
    return False


def load_tool():
    spec = importlib.util.spec_from_file_location("host_gateway_contract_fixture", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HolderRegistryTests(unittest.TestCase):
    def test_registry_has_one_row_per_path_and_only_four_A_rows_required(self):
        self.assertEqual(len(HOLDERS), len({row["path"] for row in HOLDERS}))
        self.assertEqual({row["owner_row"] for row in HOLDERS if row["required_now"]}, {"A1", "A2", "A3", "A4"})
        self.assertEqual({row["path"] for row in HOLDERS if row["owner_row"] == "F2"}, {
            "blueprints/runtime-workers/openhands/recipe.py", "blueprints/runtime-workers/openhands/dispatch.py",
            "blueprints/runtime-workers/openhands/host.py", "examples/openhands-native-capabilities/native-config.py"})
        for row in HOLDERS:
            self.assertTrue(row["routing_test"], row["path"])
            self.assertFalse(row["path"].startswith(("docs/", "evidence/")))

    def test_current_holders_are_byte_and_ast_equal_and_adapters_match(self):
        canonical = block_text(TOOL.read_text())
        canonical_ast = ast.dump(ast.parse(canonical), include_attributes=False)
        for row in HOLDERS:
            if row["kind"] != "block":
                continue
            with self.subTest(path=row["path"]):
                path = ROOT / row["path"]
                source = path.read_text() if path.exists() else ""
                if not row["required_now"] and BEGIN not in source:
                    continue
                self.assertEqual(block_text(source), canonical)
                self.assertEqual(ast.dump(ast.parse(block_text(source)), include_attributes=False), canonical_ast)
                self.assertIsNotNone(row["adapter"], row.get("adapter_pending", "adapter metadata missing"))
                actual, expected = adapter_ast(source), expected_adapter_ast(row)
                for name in ADAPTER_NAMES:
                    self.assertEqual(ast.dump(actual[name]), ast.dump(expected[name]), name)

    def test_marked_delegates_call_isolated_print_and_define_no_contract_names(self):
        canonical_names = {node.name for node in ast.parse(block_text(TOOL.read_text())).body
                           if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        canonical_names.update({target.id for node in ast.parse(block_text(TOOL.read_text())).body
                                if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)})
        for row in HOLDERS:
            if row["kind"] != "delegate":
                continue
            with self.subTest(path=row["path"]):
                path = ROOT / row["path"]
                source = path.read_text() if path.exists() else ""
                carries = "host_gateway.py" in source
                if not row["required_now"] and not carries:
                    continue
                self.assertTrue(delegate_call(source, path.suffix == ".sh"), "delegate must call isolated print")
                if path.suffix == ".py":
                    defined = {node.name for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
                    defined.update({target.id for node in ast.parse(source).body if isinstance(node, ast.Assign)
                                    for target in node.targets if isinstance(target, ast.Name)})
                    self.assertFalse(defined & canonical_names, "delegate copied shared definitions")

    def test_t15_fixed_port_lint_in_current_holders_and_canonical_block(self):
        self.assertEqual(fixed_ports(block_text(TOOL.read_text())), [])
        for row in HOLDERS:
            if row["kind"] == "block":
                path = ROOT / row["path"]
                source = path.read_text() if path.exists() else ""
                if row["required_now"] or BEGIN in source:
                    with self.subTest(path=row["path"]):
                        self.assertEqual(fixed_ports(source), [])

    def test_negative_no_tracked_python_outside_registry_defines_contract(self):
        result = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, capture_output=True, check=True)
        allowed = {row["path"] for row in HOLDERS if row["kind"] == "block"}
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            name = os.fsdecode(raw)
            if name in allowed or name.startswith(("docs/", "evidence/")):
                continue
            with self.subTest(path=name):
                self.assertEqual(forbidden_definitions((ROOT / name).read_text()), [])

    def test_lint_controls_reject_adjacent_literals_fstrings_and_integer_ports(self):
        cases = ['p = 20128', 'p = 20129', 'p = 21128', 'p = 21129',
                 'url = "http://127.0.0.1:" "45432/v1"', 'url = f"http://localhost:45432/{thing}"',
                 'url = "http://[::1]:45432/v1"', 'url = "http://0.0.0.0:45432/v1"']
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(fixed_ports(source))
        self.assertEqual(fixed_ports('url = f"http://127.0.0.1:{port}/v1"'), [])

    def test_registry_controls_reject_changed_bytes_duplicate_markers_and_adapter(self):
        canonical = block_text(TOOL.read_text())
        for source in [canonical + BEGIN + "\n", canonical + END + "\n", canonical.replace(BEGIN, BEGIN + " extra")]:
            with self.subTest(source=source[-80:]):
                with self.assertRaises(AssertionError):
                    block_text(source)
        self.assertNotEqual(block_text(canonical.replace('"native-agent-stack/host-gateway/v1"', '"wrong"')), canonical)
        with self.assertRaises(AssertionError):
            adapter_ast("GATEWAY_FLAGS = {}\n")

    def test_negative_definition_and_delegate_controls(self):
        self.assertTrue(forbidden_definitions("class " + "GatewayRefused(ValueError): pass\n"))
        self.assertTrue(forbidden_definitions('parser.add_argument("--unrecorded-gateway-reason")'))
        self.assertEqual(forbidden_definitions('fixture = "--unrecorded-gateway-reason"'), [])
        good = 'subprocess.run(["python3", "-I", "tools/omniroute/host_gateway.py", "print"])'
        self.assertTrue(delegate_call(good))
        self.assertFalse(delegate_call(good.replace('"-I", ', "")))
        self.assertFalse(delegate_call(good.replace('"print"', '"check"')))


class HostGatewayToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.temp = tempfile.TemporaryDirectory(prefix="host-gateway-contract-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "passwd-home"
        self.home.mkdir()
        self.record = self.home / self.tool.HOST_GATEWAY_RECORD
        self.addCleanup(mock.patch.stopall)
        mock.patch("pwd.getpwuid", return_value=types.SimpleNamespace(pw_dir=str(self.home))).start()
        mock.patch.object(self.tool.os, "getuid", return_value=1000).start()
        mock.patch.object(self.tool.socket, "gethostname", return_value=HOST).start()
        clean_env = {name: value for name, value in os.environ.items() if name not in GATEWAY_ENV}
        mock.patch.dict(os.environ, clean_env, clear=True).start()
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path == Path("/etc/machine-id"):
                return IDENTITY + "\n"
            return original(path, *args, **kwargs)

        mock.patch.object(Path, "read_text", read).start()
        self.real_exists = Path.exists
        mock.patch.object(Path, "exists", lambda path: self.exists(path)).start()

    def exists(self, path):
        if path == self.tool.WINDOWS_NETSTAT:
            return False
        if path == Path(f"/proc/{PID}"):
            return True
        return self.real_exists(path)

    def fake_run(self, argv, **kwargs):
        if argv[:3] == ["systemctl", "--user", "show"]:
            output = str(PID) + "\n"
        elif argv[:2] == ["scutil", "--get"]:
            output = HOST + "\n"
        elif argv[0] == "ps":
            output = "fixture-process\n"
        elif argv[:2] == ["ss", "-ltnH"]:
            output = ""
        else:
            raise AssertionError(f"unexpected native command in a fixture: {argv}")
        return subprocess.CompletedProcess(argv, 0, output, "")

    def invoke(self, argv, **injections):
        output, error = io.StringIO(), io.StringIO()
        options = {"platform": "linux", "listeners": lambda port: [("127.0.0.1", PID)],
                   "unit_of": lambda pid: UNIT, "run": self.fake_run}
        options.update(injections)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                code = self.tool.main(argv, **options)
            except SystemExit as exception:
                code = exception.code
        return code, output.getvalue(), error.getvalue()

    def write(self, **injections):
        return self.invoke(["write", "--port", str(PORT), "--unit", UNIT], **injections)

    def fixture_record(self, **changes):
        self.record.parent.mkdir(parents=True, exist_ok=True)
        value = {"schema": self.tool.HOST_GATEWAY_SCHEMA, "host": HOST, "endpoint": ENDPOINT,
                 "machine_id_sha256": IDENTITY_HASH, "unit": UNIT}
        value.update(changes)
        self.record.write_text(json.dumps(value) + "\n")
        return value

    def test_linux_write_binds_machine_id_and_private_modes(self):
        code, output, error = self.write()
        self.assertEqual((code, error), (0, ""))
        value = json.loads(output)
        self.assertEqual(value["machine_id_sha256"], IDENTITY_HASH)
        self.assertRegex(value["machine_id_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn(IDENTITY, output)
        self.assertEqual(value["endpoint"], ENDPOINT)
        self.assertEqual(value["host"], HOST)
        self.assertEqual(value["unit"], UNIT)
        self.assertEqual(json.loads(self.record.read_text()), value)
        self.assertEqual(stat.S_IMODE(self.record.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.record.parent.stat().st_mode), 0o700)

    def test_write_refuses_each_listener_ownership_failure(self):
        cases = {"none": [], "two": [("127.0.0.1", PID), ("127.0.0.1", PID + 1)],
                 "ipv6": [("::1", PID)], "no process": [("127.0.0.1", None)],
                 "foreign address": [("10.0.0.2", PID)]}
        for name, rows in cases.items():
            with self.subTest(case=name):
                code, output, error = self.write(listeners=lambda port, rows=rows: rows)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("gateway refused", error)
                self.assertFalse(self.record.exists())
        self.assertEqual(self.write(unit_of=lambda pid: "different.service")[0], 2)
        self.assertFalse(self.record.exists())

    def test_write_accepts_wildcard_ipv4_owned_listener(self):
        self.assertEqual(self.write(listeners=lambda port: [("0.0.0.0", PID)])[0], 0)

    def test_write_refuses_uid_zero_before_identity_or_listener(self):
        with mock.patch.object(self.tool.os, "getuid", return_value=0), mock.patch.object(self.tool, "installation_id") as identity:
            code, output, error = self.write(listeners=mock.Mock(side_effect=AssertionError("listener called")))
        self.assertEqual((code, output), (2, ""))
        identity.assert_not_called()
        self.assertIn("uid 0", error)

    def test_write_and_reader_refuse_every_bad_installation_identity(self):
        self.fixture_record()
        original = Path.read_text
        for identity in ["", "0" * 32, "A" * 32, "abc", "g" * 32]:
            with self.subTest(identity=identity):
                def read(path, *args, **kwargs):
                    return identity if path == Path("/etc/machine-id") else original(path, *args, **kwargs)
                with mock.patch.object(Path, "read_text", read):
                    for argv in [["write", "--port", str(PORT), "--unit", UNIT], ["print"]]:
                        code, output, error = self.invoke(argv)
                        self.assertEqual((code, output), (2, ""))
                        self.assertIn("32-digit lowercase hex", error)
        def unreadable(path, *args, **kwargs):
            if path == Path("/etc/machine-id"):
                raise PermissionError("fixture")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "read_text", unreadable):
            self.assertEqual(self.write()[0], 2)
            self.assertIn("cannot be read", self.invoke(["print"])[2])

    def test_darwin_real_identity_gap_refuses_before_lsof_or_scutil(self):
        original = Path.read_text
        def read(path, *args, **kwargs):
            if path == Path("/etc/machine-id"):
                raise FileNotFoundError("Darwin fixture has no machine-id")
            return original(path, *args, **kwargs)
        run = mock.Mock(side_effect=AssertionError("no Darwin command before identity"))
        with mock.patch.object(Path, "read_text", read):
            code, output, error = self.write(platform="darwin", run=run)
        self.assertEqual((code, output), (2, ""))
        self.assertIn("machine-id cannot be read", error)
        run.assert_not_called()

    def test_darwin_identity_patched_requires_pinned_hostname(self):
        with mock.patch.object(self.tool, "installation_id", return_value=IDENTITY_HASH):
            for output in ["", "different-host\n"]:
                run = lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, output, "")
                code, _, error = self.write(platform="darwin", run=run)
                self.assertEqual(code, 2)
                self.assertIn("pin it first: sudo scutil --set HostName", error)
            self.assertEqual(self.write(platform="darwin")[0], 0)

    def test_without_unit_records_process_name(self):
        code, output, error = self.invoke(["write", "--port", str(PORT)])
        self.assertEqual((code, error), (0, ""))
        self.assertIsNone(json.loads(output)["unit"])
        self.assertEqual(json.loads(output)["process"], "fixture-process")

    def test_topology_endpoint_uses_same_shape_contract(self):
        topology = self.home / "topology.json"
        topology.write_text(json.dumps({"gateway": {"endpoint": ENDPOINT}}))
        code, output, _ = self.invoke(["write", "--from-topology", str(topology), "--unit", UNIT])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["endpoint"], ENDPOINT)
        old = self.record.read_bytes()
        topology.write_text(json.dumps({"gateway": {"endpoint": "https://example.test/v1"}}))
        self.assertEqual(self.invoke(["write", "--from-topology", str(topology), "--unit", UNIT])[0], 2)
        self.assertEqual(self.record.read_bytes(), old)

    def test_existing_different_host_or_endpoint_needs_replace(self):
        for changed in [{"host": "different"}, {"endpoint": f"http://127.0.0.1:{OTHER}/v1"}]:
            with self.subTest(changed=changed):
                self.fixture_record(**changed)
                old = self.record.read_bytes()
                self.assertEqual(self.write()[0], 2)
                self.assertEqual(self.record.read_bytes(), old)
                self.assertEqual(self.invoke(["write", "--port", str(PORT), "--unit", UNIT, "--replace"])[0], 0)
                self.assertEqual(json.loads(self.record.read_text())["endpoint"], ENDPOINT)

    def test_atomic_write_order_unique_same_directory_and_failed_replace_keeps_old(self):
        self.fixture_record()
        old = self.record.read_bytes()
        observed = []
        actual_fsync = os.fsync
        def sync(fd):
            observed.append("fsync")
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
            actual_fsync(fd)
        def replace(source, destination):
            observed.append("replace")
            self.assertEqual(Path(source).parent, self.record.parent)
            self.assertEqual(Path(destination), self.record)
            self.assertEqual(self.record.read_bytes(), old)
            self.assertEqual(json.loads(Path(source).read_text())["machine_id_sha256"], IDENTITY_HASH)
            raise PermissionError("injected replacement failure")
        with mock.patch.object(self.tool.os, "fsync", sync), mock.patch.object(self.tool.os, "replace", replace):
            code, _, error = self.write()
        self.assertEqual(code, 2)
        self.assertIn("old record kept", error)
        self.assertEqual(observed, ["fsync", "replace"])
        self.assertEqual(self.record.read_bytes(), old)
        self.assertEqual(list(self.record.parent.glob(".gateway-*.json")), [])

    def test_failed_fsync_keeps_old_and_cleans_temporary(self):
        self.fixture_record()
        old = self.record.read_bytes()
        with mock.patch.object(self.tool.os, "fsync", side_effect=OSError("fixture")), mock.patch.object(self.tool.os, "replace") as replace:
            self.assertEqual(self.write()[0], 2)
        replace.assert_not_called()
        self.assertEqual(self.record.read_bytes(), old)
        self.assertEqual(list(self.record.parent.glob(".gateway-*.json")), [])

    def test_print_uses_passwd_record_not_home_xdg_and_checks_variables(self):
        self.fixture_record()
        with mock.patch.dict(os.environ, {"HOME": str(self.home / "wrong"), "XDG_CONFIG_HOME": str(self.home / "wrong"), "OPENAI_BASE_URL": f"http://localhost:{OTHER}/v1"}):
            self.assertEqual(self.invoke(["print"])[1].strip(), ENDPOINT)
            code, output, error = self.invoke(["print", "--variable", "OPENAI_BASE_URL"])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("OPENAI_BASE_URL", error)
            self.assertEqual(self.invoke(["print", "--base-url", f"http://127.0.0.1:{OTHER}/v1", "--unrecorded-gateway-reason", "fixture", "--variable", "OPENAI_BASE_URL"])[0], 0)
        self.assertEqual(self.invoke(["print", "--root"])[1].strip(), ENDPOINT[:-3])

    def test_print_missing_record_requires_named_explicit_override(self):
        self.assertEqual(self.invoke(["print"])[0], 2)
        self.assertEqual(self.invoke(["print", "--base-url", ENDPOINT])[0], 2)
        self.assertEqual(self.invoke(["print", "--unrecorded-gateway-reason", "fixture"])[0], 2)
        self.assertEqual(self.invoke(["print", "--base-url", ENDPOINT, "--unrecorded-gateway-reason", " "])[0], 2)
        code, output, error = self.invoke(["print", "--base-url", ENDPOINT, "--unrecorded-gateway-reason", "fixture"])
        self.assertEqual((code, output.strip(), error), (0, ENDPOINT, ""))

    def test_record_machine_hash_missing_null_empty_or_bad_is_malformed(self):
        for value in [None, "", "A" * 64, "abc", "g" * 64]:
            with self.subTest(value=value):
                self.fixture_record(machine_id_sha256=value)
                self.assertIn("malformed", self.invoke(["print"])[2])
        value = self.fixture_record()
        del value["machine_id_sha256"]
        self.record.write_text(json.dumps(value))
        self.assertIn("malformed", self.invoke(["print"])[2])

    def test_check_reports_owner_profile_match_and_timestamp(self):
        self.fixture_record()
        profile = self.home / "fixture.config.toml"
        profile.write_text(f'[model_providers.omniroute]\nbase_url = "{ENDPOINT}"\n')
        code, output, error = self.invoke(["check", "--codex-profile", str(profile)])
        self.assertEqual((code, error), (0, ""))
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertTrue(result["profile_match"])
        self.assertEqual(result["owner"]["unit"], UNIT)
        self.assertRegex(result["checked_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        profile.write_text(f'[model_providers.omniroute]\nbase_url = "http://127.0.0.1:{OTHER}/v1"\n')
        code, output, _ = self.invoke(["check", "--codex-profile", str(profile)])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["profile_match"])

    def test_check_mainpid_not_visible_is_exit_three(self):
        self.fixture_record()
        original = self.exists
        with mock.patch.object(Path, "exists", lambda path: False if path == Path(f"/proc/{PID}") else original(path)):
            code, output, _ = self.invoke(["check"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output)["owner"], "not verifiable from this context")
        self.assertFalse(json.loads(output)["ok"])

    def windows_run(self, tcp, tcpv6, linux=""):
        def run(argv, **kwargs):
            if argv[0] == str(self.tool.WINDOWS_NETSTAT):
                result = tcp if argv[-1] == "tcp" else tcpv6
                if isinstance(result, BaseException):
                    raise result
                return subprocess.CompletedProcess(argv, result[0], result[1], "")
            if argv == ["ss", "-ltnH"]:
                return subprocess.CompletedProcess(argv, 0, linux, "")
            return self.fake_run(argv, **kwargs)
        return run

    def windows_present(self):
        original = self.exists
        return mock.patch.object(Path, "exists", lambda path: True if path == self.tool.WINDOWS_NETSTAT else original(path))

    def test_t16_every_bad_tcp_read_with_valid_tcpv6_is_not_verifiable(self):
        self.fixture_record()
        valid = (0, f"TCP [::]:{OTHER} [::]:0 LISTENING 77\n")
        bad = [(1, "failed"), (0, ""), (0, "Active Connections\nProto Local Address Foreign Address State PID\n"),
               (0, "unparseable text"), (0, f"TCP 127.0.0.1:{OTHER} 127.0.0.1:1 ESTABLISHED 77\n"),
               (0, f"TCP 127.0.0.1:{OTHER} 0.0.0.0:0 ESCUTANDO 77\n"), OSError("cannot execute")]
        for index, failure in enumerate(bad):
            with self.subTest(form=index), self.windows_present():
                code, output, _ = self.invoke(["check", "--legacy-port", "20128", "--legacy-port", "20129"], run=self.windows_run(failure, valid))
                self.assertEqual(code, 3)
                self.assertFalse(json.loads(output)["windows_read"])
                self.assertFalse(json.loads(output)["ok"])
                self.assertTrue(all(not row["windows_read"] and row["windows"] is None
                                    for row in json.loads(output)["legacy_ports"]))

    def test_t16_every_bad_tcpv6_read_with_valid_tcp_is_not_verifiable(self):
        self.fixture_record()
        valid = (0, f"TCP 127.0.0.1:{OTHER} 0.0.0.0:0 LISTENING 77\n")
        bad = [(1, "failed"), (0, ""), (0, "Active Connections\nProto Local Address Foreign Address State PID\n"),
               (0, "unparseable text"), (0, f"TCP [::]:{OTHER} [::]:1 ESTABLISHED 77\n"),
               (0, f"TCP [::]:{OTHER} [::]:0 ESCUTANDO 77\n"), OSError("cannot execute")]
        for index, failure in enumerate(bad):
            with self.subTest(form=index), self.windows_present():
                code, output, _ = self.invoke(["check", "--legacy-port", "20128", "--legacy-port", "20129"], run=self.windows_run(valid, failure))
                self.assertEqual(code, 3)
                self.assertFalse(json.loads(output)["windows_read"])
                self.assertFalse(json.loads(output)["ok"])
                self.assertTrue(all(not row["windows_read"] and row["windows"] is None
                                    for row in json.loads(output)["legacy_ports"]))

    def test_t16_both_valid_tables_set_windows_read_and_check_each_legacy_port(self):
        self.fixture_record()
        valid_tcp = (0, f"TCP 127.0.0.1:{OTHER} 0.0.0.0:0 LISTENING 77\n")
        valid_v6 = (0, f"TCP [::]:{OTHER} [::]:0 LISTENING 78\n")
        for table, port in [(None, None), ("tcp", 20128), ("tcpv6", 20128), ("tcp", 20129), ("tcpv6", 20129)]:
            tcp, v6 = valid_tcp, valid_v6
            if table == "tcp":
                tcp = (0, f"TCP 0.0.0.0:{port} 0.0.0.0:0 LISTENING 77\n")
            elif table == "tcpv6":
                v6 = (0, f"TCP [::]:{port} [::]:0 LISTENING 78\n")
            with self.subTest(table=table, port=port), self.windows_present():
                code, output, _ = self.invoke(["check", "--legacy-port", "20128", "--legacy-port", "20129"], run=self.windows_run(tcp, v6))
                result = json.loads(output)
                self.assertEqual(code, 0 if table is None else 2)
                self.assertEqual(result["ok"], table is None)
                self.assertTrue(all(row["windows_read"] for row in result["legacy_ports"]))

    def test_windows_listener_at_recorded_port_also_fails(self):
        self.fixture_record()
        tcp = (0, f"TCP 127.0.0.1:{PORT} 0.0.0.0:0 LISTENING 77\n")
        v6 = (0, f"TCP [::]:{OTHER} [::]:0 LISTENING 78\n")
        with self.windows_present():
            code, output, _ = self.invoke(["check"], run=self.windows_run(tcp, v6))
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["ok"])

    def test_linux_legacy_listener_without_process_fails_and_absence_does_not_claim_windows(self):
        self.fixture_record()
        for address in ["127.0.0.1", "[::]", "0.0.0.0"]:
            with self.subTest(address=address):
                linux = f"LISTEN 0 128 {address}:20128 *:*\n"
                code, output, _ = self.invoke(["check", "--legacy-port", "20128"], run=self.windows_run((0, ""), (0, ""), linux))
                result = json.loads(output)
                self.assertEqual(code, 2)
                self.assertTrue(result["legacy_ports"][0]["linux"])
                self.assertFalse(result["legacy_ports"][0]["windows_read"])

    def test_native_listener_parsers_are_exercised_only_through_injected_run(self):
        def run(argv, **kwargs):
            if argv[0] == "ss":
                output = f'LISTEN 0 128 127.0.0.1:{PORT} 0.0.0.0:* users:(("fixture",pid={PID},fd=3))\n'
            elif argv[0] == "lsof":
                output = f"p{PID}\ncfixture\n"
            elif argv[0] == "scutil":
                output = HOST + "\n"
            else:
                raise AssertionError(argv)
            return subprocess.CompletedProcess(argv, 0, output, "")
        self.assertEqual(self.write(listeners=None, run=run)[0], 0)
        with mock.patch.object(self.tool, "installation_id", return_value=IDENTITY_HASH):
            self.assertEqual(self.write(platform="darwin", listeners=None, run=run)[0], 0)


if __name__ == "__main__":
    unittest.main()
