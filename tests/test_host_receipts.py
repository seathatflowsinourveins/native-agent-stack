"""Tests for scripts/host_receipts.py: schema/code sync, fixture validation and a
recorder round trip. Never write evidence/hosts in the real repository tree from
these tests; everything mutating runs against a temporary copy."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import host_receipts as hr

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "host-receipts"
SCHEMA_PATH = REPO_ROOT / "adoption" / "host-receipt.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _init_support_tree(root: Path) -> str:
    """Minimal manifests/adoption/landscape/evidence tree plus a real git commit."""
    (root / "adoption").mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    (root / "catalogs" / "landscape").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "hosts").mkdir(parents=True, exist_ok=True)
    # validate_receipt_shape() now loads adoption/host-receipt.schema.json directly (single
    # source of truth); the tmp tree needs a real copy of it, not just the fixture/support
    # files this module writes by hand.
    (root / "adoption" / "host-receipt.schema.json").write_text(
        SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "adoption" / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "platform_profiles": [
            {"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64", "status": "accepted"},
        ],
    }), encoding="utf-8")
    (root / "manifests" / "stack.json").write_text(json.dumps({
        "schema_version": 1,
        "components": [
            {"id": "widget", "version": "1.0.0", "profile": "core", "commands": ["echo hi"]},
        ],
    }), encoding="utf-8")
    (root / "manifests" / "evidence.json").write_text(json.dumps({
        "schema_version": 1, "receipts": [], "files": [],
    }), encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test", "add", "-A")
    _git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test",
         "commit", "-q", "-m", "init")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _run_cli(argv: list[str], identity: str | None = "test-recorder") -> int:
    """Run the CLI with no inherited $CLAUDE_CODE_SESSION_ID (CI has none) and, for record and
    review, an explicit --identity unless the test passes identity=None or its own."""
    if identity is not None and argv and argv[0] in ("record", "review") and "--identity" not in argv:
        argv = [*argv, "--identity", identity]
    environment = {key: value for key, value in os.environ.items() if key != hr.IDENTITY_ENV}
    with mock.patch.dict(os.environ, environment, clear=True):
        return hr.main(argv)


def _register(root: Path, relative_path: str) -> None:
    evidence_path = root / "manifests" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    raw = (root / relative_path).read_bytes()
    evidence["files"].append({
        "path": relative_path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
    })
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")


class SchemaSyncTests(unittest.TestCase):
    """scripts/host_receipts.py hand-implements validation (stdlib only, no external
    JSON Schema library); these tests keep its required-key and enum constants in
    sync with adoption/host-receipt.schema.json."""

    def setUp(self):
        self.schema = _load_schema()

    def test_top_level_required_matches(self):
        self.assertEqual(set(self.schema["required"]), set(hr.TOP_LEVEL_REQUIRED))

    def test_host_required_matches(self):
        self.assertEqual(set(self.schema["properties"]["host"]["required"]), set(hr.HOST_REQUIRED))

    def test_command_required_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["commands"]["items"]["required"]), set(hr.COMMAND_REQUIRED))

    def test_review_required_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["reviews"]["items"]["required"]), set(hr.REVIEW_REQUIRED))

    def test_stage_enum_matches(self):
        self.assertEqual(set(self.schema["properties"]["stage"]["enum"]), hr.STAGES)

    def test_result_enum_matches(self):
        self.assertEqual(set(self.schema["properties"]["result"]["enum"]), hr.RESULTS)

    def test_evidence_class_enum_matches(self):
        self.assertEqual(set(self.schema["properties"]["evidence_class"]["enum"]), hr.EVIDENCE_CLASSES)

    def test_review_kind_enum_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["reviews"]["items"]["properties"]["kind"]["enum"]), hr.REVIEW_KINDS)

    def test_review_verdict_enum_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["reviews"]["items"]["properties"]["verdict"]["enum"]),
            hr.REVIEW_VERDICTS)

    def test_command_minitems_matches_nonempty_requirement(self):
        self.assertEqual(self.schema["properties"]["commands"]["minItems"], 1)

    def test_limitations_minitems_matches_nonempty_requirement(self):
        self.assertEqual(self.schema["properties"]["limitations"]["minItems"], 1)

    def test_reviews_minitems_matches_nonempty_requirement(self):
        self.assertEqual(self.schema["properties"]["reviews"]["minItems"], 1)

    def test_host_id_pattern_matches_code(self):
        self.assertEqual(self.schema["properties"]["host"]["properties"]["host_id"]["pattern"],
                          hr.HOST_ID_PATTERN.pattern)

    def test_id_pattern_accepts_colon_and_slash_in_component_segment(self):
        # manifests/stack.json and catalogs/landscape/*.json component ids legitimately
        # contain '/' (a repository-style id like "affaan-m/ECC") and ':' (a landscape
        # "candidate:*" alternative id); both the schema and the code must accept them
        # inside the id's component segment.
        schema_pattern = re.compile(self.schema["properties"]["id"]["pattern"])
        for candidate in (
            "host-20260101--candidate:astral-sh-uv--use--20260101",
            "host-20260101--affaan-m/ECC--use--20260101",
        ):
            self.assertTrue(schema_pattern.fullmatch(candidate), candidate)
            self.assertTrue(hr.ID_PATTERN.fullmatch(candidate), candidate)

    def test_id_pattern_rejects_percent(self):
        # '%' is reserved by receipt_filename_stem() to percent-escape '/' in filenames;
        # it must never be a valid id character in either the schema or the code.
        schema_pattern = re.compile(self.schema["properties"]["id"]["pattern"])
        candidate = "host-20260101--weird%2Fname--use--20260101"
        self.assertIsNone(schema_pattern.fullmatch(candidate))
        self.assertIsNone(hr.ID_PATTERN.fullmatch(candidate))


class _ReceiptFixtureCase(unittest.TestCase):
    """Shared tmp-tree/fixture/validate helpers, not itself collected as a test case
    (its name does not start with ``Test``... it does start with an underscore, which
    unittest's default discovery also skips)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.commit = _init_support_tree(self.root)

    def _place(self, fixture_name: str, *, filename: str | None = None, register: bool = True,
               patch=None) -> Path:
        data = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        data["catalog_revision"] = self.commit
        if patch is not None:
            patch(data)
        host_id = data["host"]["host_id"]
        target_name = filename or f"{data['id']}.json"
        host_dir = self.root / "evidence" / "hosts" / host_id
        host_dir.mkdir(parents=True, exist_ok=True)
        path = host_dir / target_name
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if register:
            _register(self.root, path.relative_to(self.root).as_posix())
        return path

    def _validate(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = hr.cmd_validate(argparse.Namespace(root=self.root))
        return exit_code, buffer.getvalue()


class ValidateFixtureTests(_ReceiptFixtureCase):
    def test_valid_fixture_passes(self):
        self._place("valid.json")
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 0, output)

    def test_wrong_platform_is_rejected(self):
        self._place("wrong-platform.json")
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("platform_profiles id", output)

    def test_unknown_component_is_rejected(self):
        self._place("unknown-component.json")
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("is not a known manifests/stack.json", output)

    def test_home_path_in_excerpt_is_rejected(self):
        # Built from parts, never as one literal string: a literal personal
        # home path here would also trip scripts/validate.py's repo-wide
        # PRIVATE_CONTENT scan of this tracked test file.
        a_personal_home_path = "/" + "home" + "/" + "alice"

        def substitute(data):
            command = data["commands"][0]
            command["output_excerpt"] = command["output_excerpt"].replace(
                "HOME_PATH_PLACEHOLDER", a_personal_home_path)

        self._place("home-path-in-excerpt.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("personal home path", output)

    def test_pass_with_nonzero_exit_is_rejected(self):
        self._place("pass-with-nonzero-exit.json")
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("result is 'pass' but exit", output)

    def test_unregistered_file_is_rejected(self):
        self._place("unregistered-file.json", register=False)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("not registered in manifests/evidence.json", output)

    def test_id_path_mismatch_is_rejected(self):
        self._place("id-path-mismatch.json", filename="mismatched-name.json")
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("does not match id", output)

    def test_id_component_segment_mismatch_is_rejected(self):
        # id says "widget" but component_id claims something else: previously only the
        # id's host segment and the filename stem were cross-checked against the receipt.
        self._place("valid.json", patch=lambda data: data.__setitem__("component_id", "not-widget"))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("id component segment", output)
        self.assertIn("does not match component_id", output)

    def test_id_stage_segment_mismatch_is_rejected(self):
        # id says stage "use" but the receipt's own stage field claims "install".
        self._place("valid.json", patch=lambda data: data.__setitem__("stage", "install"))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("id stage segment", output)
        self.assertIn("does not match stage", output)

    def test_id_date_segment_mismatch_is_rejected(self):
        # id says 20260101 but observed_at_utc claims a different day.
        self._place("valid.json", patch=lambda data: data.__setitem__("observed_at_utc", "2026-01-02T00:00:00Z"))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("id date segment", output)
        self.assertIn("does not match observed_at_utc date", output)

    def test_fabricated_catalog_revision_is_rejected(self):
        # A well-formed but nonexistent 40-hex SHA: git cat-file -e exits 128 for this,
        # not 1, and that must count as "missing", not "git unavailable, skip".
        self._place("valid.json", patch=lambda data: data.__setitem__("catalog_revision", "1" * 40))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("is not a commit present in this checkout", output)

    def test_slash_component_id_filename_is_percent_escaped(self):
        # A component id containing '/' (for example a repository-style stack id) cannot
        # be its own filename: the recorder must escape it rather than creating a nested
        # directory that _iter_receipt_files would silently skip.
        stack_path = self.root / "manifests" / "stack.json"
        stack = json.loads(stack_path.read_text(encoding="utf-8"))
        stack["components"].append(
            {"id": "vendor/tool", "version": "1.0.0", "profile": "core", "commands": ["echo hi"]})
        stack_path.write_text(json.dumps(stack), encoding="utf-8")

        def substitute(data):
            data["id"] = "fixture-host-20260101--vendor/tool--use--20260101"
            data["component_id"] = "vendor/tool"

        path = self._place("valid.json", filename="fixture-host-20260101--vendor%2Ftool--use--20260101.json",
                            patch=substitute)
        self.assertTrue(path.is_file())
        self.assertNotIn("/", path.name)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 0, output)

    def test_platform_os_architecture_mismatch_is_rejected(self):
        # A receipt claiming linux-wsl2-x86_64 (adoption/manifest.json: os=linux,
        # architecture=x86_64) while self-declaring os=darwin/architecture=arm64 is
        # internally contradictory; validate must reject it directly, not only exclude it
        # from build_summary's stricter macOS flip-rule list.
        def substitute(data):
            data["host"]["os"] = "darwin"
            data["host"]["architecture"] = "arm64"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("inconsistent with adoption/manifest.json platform_profiles", output)

    def test_json_escaped_personal_home_path_in_value_is_rejected(self):
        # A JSON / escape decodes to '/', hiding a personal home path from a scan of
        # only the file's raw serialized bytes. Built from parts/escapes at runtime, never
        # as one literal path string (a literal one here would also trip scripts/validate.py's
        # repo-wide PRIVATE_CONTENT scan of this tracked test file).
        backslash = chr(92)
        a_personal_home_path = "/" + "home" + "/" + "alice"
        escaped_home_path = backslash + "u002f" + "home" + backslash + "u002f" + "alice"
        data = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        data["catalog_revision"] = self.commit
        data["claim"] = "MARKER"
        text = json.dumps(data, indent=2) + "\n"
        self.assertNotIn(a_personal_home_path, text)  # sanity: the raw bytes never contain it
        text = text.replace("MARKER", escaped_home_path)
        decoded_claim = json.loads(text)["claim"]
        self.assertIn(a_personal_home_path, decoded_claim)  # sanity: decoding really hides it

        host_dir = self.root / "evidence" / "hosts" / data["host"]["host_id"]
        host_dir.mkdir(parents=True, exist_ok=True)
        path = host_dir / f"{data['id']}.json"
        path.write_text(text, encoding="utf-8")
        _register(self.root, path.relative_to(self.root).as_posix())

        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("personal home path", output)

    def test_json_escaped_personal_home_path_in_key_is_rejected(self):
        # The same JSON-escape hiding technique, but in an object *key* (tool_versions is an
        # open object per the schema); the privacy scan must walk keys, not only values.
        # Built from parts, never as one literal string (see the comment in the value-case
        # test above).
        backslash = chr(92)
        a_personal_home_path = "/" + "home" + "/" + "alice"
        escaped_home_path = backslash + "u002f" + "home" + backslash + "u002f" + "alice"
        data = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        data["catalog_revision"] = self.commit
        data["tool_versions"] = {"MARKERKEY": "1.0.0"}
        text = json.dumps(data, indent=2) + "\n"
        self.assertNotIn(a_personal_home_path, text)
        text = text.replace("MARKERKEY", escaped_home_path)
        decoded_key = next(iter(json.loads(text)["tool_versions"]))
        self.assertIn(a_personal_home_path, decoded_key)

        host_dir = self.root / "evidence" / "hosts" / data["host"]["host_id"]
        host_dir.mkdir(parents=True, exist_ok=True)
        path = host_dir / f"{data['id']}.json"
        path.write_text(text, encoding="utf-8")
        _register(self.root, path.relative_to(self.root).as_posix())

        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("personal home path", output)


class FullSchemaValidationTests(_ReceiptFixtureCase):
    """Codex review cases the previous hand-written validate_receipt_shape() missed:
    it checked required keys and a few enums/patterns but not the schema's full
    additionalProperties/minimum/minLength constraints. validate_receipt_shape() is now
    driven directly by adoption/host-receipt.schema.json (validate_against_schema()), so
    these must all fail."""

    def test_null_command_cmd_is_rejected(self):
        self._place("valid.json", patch=lambda data: data["commands"][0].__setitem__("cmd", None))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("commands[0].cmd", output)

    def test_negative_duration_is_rejected(self):
        self._place("valid.json", patch=lambda data: data["commands"][0].__setitem__("duration_s", -1))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("commands[0].duration_s", output)

    def test_extra_top_level_property_is_rejected(self):
        self._place("valid.json", patch=lambda data: data.__setitem__("unexpected_extra_field", "x"))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("unexpected additional property 'unexpected_extra_field'", output)

    def test_empty_review_ref_is_rejected(self):
        self._place("valid.json", patch=lambda data: data["reviews"][0].__setitem__("ref", ""))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("reviews[0].ref", output)

    def test_null_review_at_utc_is_rejected(self):
        self._place("valid.json", patch=lambda data: data["reviews"][0].__setitem__("at_utc", None))
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("reviews[0].at_utc", output)


class SchemaKeywordCoverageTests(unittest.TestCase):
    """Drift protection for the 'load the schema and implement its keyword subset'
    approach: if adoption/host-receipt.schema.json is ever edited to use a JSON Schema
    keyword validate_against_schema() does not implement, that keyword would silently
    stop constraining anything. Fail loudly instead."""

    def test_every_schema_keyword_is_supported(self):
        schema = _load_schema()
        used_keywords: set[str] = set()
        for node in hr.schema_nodes(schema):
            used_keywords.update(node.keys())
        used_keywords -= hr.SCHEMA_META_KEYWORDS
        unsupported = used_keywords - hr.SCHEMA_SUPPORTED_KEYWORDS
        self.assertEqual(unsupported, set(),
                          f"schema uses keyword(s) validate_against_schema() does not implement: {unsupported}")

    def test_supported_keywords_are_all_actually_used(self):
        # Catches the opposite drift: a keyword implemented in code that the schema no
        # longer uses, which would be dead/untested validation logic.
        schema = _load_schema()
        used_keywords: set[str] = set()
        for node in hr.schema_nodes(schema):
            used_keywords.update(node.keys())
        used_keywords -= hr.SCHEMA_META_KEYWORDS
        self.assertEqual(hr.SCHEMA_SUPPORTED_KEYWORDS - used_keywords, set())


class DefaultOsNormalizationTests(unittest.TestCase):
    """A Mac's platform.system() returns 'Darwin'; adoption/manifest.json's macos-arm64
    platform_profiles entry expects host.os == 'macos'. _default_os() must normalize."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)
        manifest_path = self.root / "adoption" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platform_profiles"].append(
            {"id": "macos-arm64", "os": "macos", "architecture": "arm64", "status": "drafted_not_accepted"})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def _run(self, argv: list[str]) -> int:
        return _run_cli(argv)

    def test_default_os_normalizes_darwin_to_macos(self):
        with mock.patch("platform.system", return_value="Darwin"):
            self.assertEqual(hr._default_os(), "macos")

    def test_default_os_leaves_linux_as_linux(self):
        with mock.patch("platform.system", return_value="Linux"):
            self.assertEqual(hr._default_os(), "linux")

    def test_mac_record_with_default_flags_satisfies_platform_identity(self):
        with mock.patch("platform.system", return_value="Darwin"), \
             mock.patch("platform.machine", return_value="arm64"):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = self._run([
                    "record", "--root", str(self.root),
                    "--host-id", "test-mac-20260101",
                    "--platform-id", "macos-arm64",
                    "--component-id", "widget",
                    "--stage", "use",
                    "--evidence-class", "native_proven",
                    "--second-physical-machine",
                    "--from-stack-commands",
                ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        receipt = json.loads((self.root / relative_path).read_text(encoding="utf-8"))
        self.assertEqual(receipt["host"]["os"], "macos")
        self.assertEqual(receipt["host"]["architecture"], "arm64")

        profiles = hr.platform_profile_map(self.root)
        self.assertEqual(receipt["host"]["os"], profiles["macos-arm64"]["os"])
        self.assertEqual(receipt["host"]["architecture"], profiles["macos-arm64"]["architecture"])

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())


class RecorderRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _run(self, argv: list[str]) -> int:
        return _run_cli(argv)

    def test_record_writes_a_valid_registered_receipt(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        self.assertTrue(relative_path.startswith("evidence/hosts/test-host-20260101/"))
        written = self.root / relative_path
        self.assertTrue(written.is_file())

        receipt = json.loads(written.read_text(encoding="utf-8"))
        self.assertEqual(receipt["result"], "pass")
        self.assertEqual(receipt["component_id"], "widget")
        self.assertEqual(len(receipt["commands"]), 1)
        self.assertEqual(receipt["commands"][0]["cmd"], "echo hi")
        self.assertEqual(len(receipt["reviews"]), 1)
        self.assertEqual(receipt["reviews"][0]["kind"], "self")

        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        registered = {entry["path"]: entry for entry in evidence["files"]}[relative_path]
        self.assertEqual(registered["sha256"], hashlib.sha256(written.read_bytes()).hexdigest())

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_record_percent_escapes_slash_in_component_id_filename(self):
        # manifests/stack.json and catalogs/landscape winners can carry a repository-style
        # component id like "vendor/tool"; recording it must not create a nested directory
        # under evidence/hosts/<host>/ that _iter_receipt_files would then silently skip.
        stack_path = self.root / "manifests" / "stack.json"
        stack = json.loads(stack_path.read_text(encoding="utf-8"))
        stack["components"].append(
            {"id": "vendor/tool", "version": "1.0.0", "profile": "core", "commands": ["echo hi"]})
        stack_path.write_text(json.dumps(stack), encoding="utf-8")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "vendor/tool",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        self.assertTrue(relative_path.startswith(
            "evidence/hosts/test-host-20260101/test-host-20260101--vendor%2Ftool--use--"))
        self.assertTrue(relative_path.endswith(".json"))
        written = self.root / relative_path
        self.assertTrue(written.is_file())
        # No nested "vendor" directory was created under the host directory.
        self.assertEqual(sorted(p.name for p in written.parent.iterdir()), [written.name])

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

        summary = hr.build_summary(self.root)
        self.assertIn("vendor/tool", summary["components"])

    def test_record_percent_escapes_colon_in_component_id_filename(self):
        # A landscape "candidate:*" alternative id like "candidate:cli-cli" previously
        # crashed register_file (safe_file rejects ':' in a path) after the receipt file
        # had already been written by target.write_text(), leaving an unregistered file on
        # disk. The colon must now be percent-escaped in the filename just like '/'.
        stack_path = self.root / "manifests" / "stack.json"
        stack = json.loads(stack_path.read_text(encoding="utf-8"))
        stack["components"].append(
            {"id": "candidate:cli-cli", "version": "1.0.0", "profile": "core", "commands": ["echo hi"]})
        stack_path.write_text(json.dumps(stack), encoding="utf-8")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "candidate:cli-cli",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        self.assertTrue(relative_path.startswith(
            "evidence/hosts/test-host-20260101/test-host-20260101--candidate%3Acli-cli--use--"))
        self.assertNotIn(":", Path(relative_path).name)
        written = self.root / relative_path
        self.assertTrue(written.is_file())

        receipt = json.loads(written.read_text(encoding="utf-8"))
        # The escaping applies only to the filename; the JSON id/component_id fields keep
        # the literal ':'.
        self.assertEqual(receipt["component_id"], "candidate:cli-cli")
        self.assertIn(":", receipt["id"])

        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        registered_paths = {entry["path"] for entry in evidence["files"]}
        self.assertIn(relative_path, registered_paths)

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_record_rolls_back_receipt_file_when_registration_fails(self):
        # If registering the just-written receipt in manifests/evidence.json fails for any
        # reason, record() must not leave a written-but-unregistered receipt file behind.
        buffer = io.StringIO()
        with mock.patch.object(hr, "register_file", side_effect=OSError("simulated registration failure")):
            with contextlib.redirect_stdout(buffer):
                exit_code = self._run([
                    "record", "--root", str(self.root),
                    "--host-id", "test-host-20260101",
                    "--platform-id", "linux-wsl2-x86_64",
                    "--component-id", "widget",
                    "--stage", "use",
                    "--evidence-class", "synthetic",
                    "--from-stack-commands",
                ])
        self.assertEqual(exit_code, 1, buffer.getvalue())
        host_dir = self.root / "evidence" / "hosts" / "test-host-20260101"
        leftover = list(host_dir.glob("*.json")) if host_dir.is_dir() else []
        self.assertEqual(leftover, [], f"receipt file(s) left on disk after a rolled-back record: {leftover}")

    def test_record_rejects_malformed_host_id(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root),
                "--host-id", "Not-Valid",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 2)

    def test_record_rejects_unknown_platform(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "not-a-real-platform",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 2)

    def test_review_round_trip_appends_and_reregisters(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        relative_path = buffer.getvalue().strip()

        review_buffer = io.StringIO()
        with contextlib.redirect_stdout(review_buffer):
            review_exit = self._run([
                "review", "--root", str(self.root),
                "--receipt", str(self.root / relative_path),
                "--kind", "independent_session",
                "--ref", "test-suite",
                "--verdict", "agree",
                "--identity", "test-reviewer",
            ])
        self.assertEqual(review_exit, 0, review_buffer.getvalue())

        receipt = json.loads((self.root / relative_path).read_text(encoding="utf-8"))
        kinds = [review["kind"] for review in receipt["reviews"]]
        self.assertEqual(kinds, ["self", "independent_session"])
        self.assertEqual(receipt["reviews"][1]["reviewer"]["identity_sha256"], hr.identity_digest("test-reviewer"))
        self.assertEqual(hr.review_state(receipt), "agree")

        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        registered = {entry["path"]: entry for entry in evidence["files"]}[relative_path]
        actual_sha256 = hashlib.sha256((self.root / relative_path).read_bytes()).hexdigest()
        self.assertEqual(registered["sha256"], actual_sha256)

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_summary_counts_component_results(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
            ])
        summary_buffer = io.StringIO()
        with contextlib.redirect_stdout(summary_buffer):
            summary_exit = hr.cmd_summary(argparse.Namespace(root=self.root, json=True, max_age_days=180))
        self.assertEqual(summary_exit, 0)
        summary = json.loads(summary_buffer.getvalue())
        bucket = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"]
        self.assertEqual(bucket["stages"]["use"]["pass"], 1)
        self.assertIsInstance(bucket["latest_age_days"], int)
        self.assertFalse(bucket["old"])
        self.assertEqual(bucket["receipts"][0]["component_version"], "1.0.0")

    def test_record_fails_closed_without_an_identity(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ], identity=None)
        self.assertEqual(exit_code, 2, buffer.getvalue())
        self.assertIn("--identity", buffer.getvalue())
        self.assertFalse((self.root / "evidence" / "hosts" / "test-host-20260101").exists())

    def test_record_hashes_the_claude_session_id_and_never_stores_it(self):
        # Built at run time: a literal UUID would trip the repository's own privacy scan.
        session_id = "-".join(("1" * 8, "2" * 4, "3" * 4, "4" * 4, "5" * 12))
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {hr.IDENTITY_ENV: session_id}), contextlib.redirect_stdout(buffer):
            exit_code = hr.main([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands", "--model", "claude-opus-5-5",
            ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        text = (self.root / buffer.getvalue().strip()).read_text(encoding="utf-8")
        self.assertNotIn(session_id, text)
        receipt = json.loads(text)
        self.assertEqual(receipt["recorded_by"], {"identity_sha256": hr.identity_digest(session_id),
                                                  "model": "claude-opus-5-5"})
        self.assertEqual(receipt["tool_versions"], {"widget": "1.0.0"})

    def test_record_needs_a_component_version_when_the_catalog_has_none(self):
        buffer = io.StringIO()
        argv = ["record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "unlisted-tool", "--stage", "use",
                "--evidence-class", "synthetic", "--cmd", "echo hi"]
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(self._run(argv), 2, buffer.getvalue())
        self.assertIn("--component-version", buffer.getvalue())

    def test_record_binds_a_landscape_only_winner_to_its_pin(self):
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "landscape-tool", "pin": "v2.0.0"}]},
            {"winners": [{"component_id": "landscape-tool", "pin": "v2.0.0"}]},
        ]}), encoding="utf-8")
        self.assertEqual(hr.catalog_component_version(self.root, "landscape-tool"), "v2.0.0")
        (self.root / "catalogs" / "landscape" / "us-equities.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "landscape-tool", "pin": "v3.0.0"}]},
        ]}), encoding="utf-8")
        self.assertIsNone(hr.catalog_component_version(self.root, "landscape-tool"))

    def _record_then_review(self, *, reviewer: str | None, kind: str = "independent_session") -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        relative_path = buffer.getvalue().strip()
        review_buffer = io.StringIO()
        argv = ["review", "--root", str(self.root), "--receipt", relative_path, "--kind", kind,
                "--ref", "test", "--verdict", "agree"]
        with contextlib.redirect_stdout(review_buffer):
            exit_code = _run_cli(argv, identity=reviewer)
        return exit_code, review_buffer.getvalue()

    def test_a_claude_session_cannot_pose_as_another_identity(self):
        # Review of #117 finding 3: with the session id set, --identity is refused.
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {hr.IDENTITY_ENV: "session-a"}), contextlib.redirect_stdout(buffer):
            exit_code = hr.main([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands", "--identity", "someone-else",
            ])
        self.assertEqual(exit_code, 2, buffer.getvalue())
        self.assertIn("--identity is for sessions without", buffer.getvalue())

    def test_identity_is_normalized(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(hr.resolve_identity("Alice"), hr.resolve_identity("  alice "))
            self.assertEqual(hr.resolve_identity("\uff21lice"), hr.resolve_identity("alice"))  # NFKC fullwidth A
            self.assertIsNone(hr.resolve_identity("   "))

    def test_record_refuses_a_version_without_a_digit(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands", "--component-version", "unpinned",
            ])
        self.assertEqual(exit_code, 2, buffer.getvalue())

    def test_default_version_prefers_the_landscape_pin_over_the_stack_version(self):
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "widget", "pin": "v1.0.0"}]}]}), encoding="utf-8")
        self.assertEqual(hr.catalog_component_version(self.root, "widget"), "v1.0.0")

    def test_review_refuses_when_the_clock_is_behind_the_observation(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        relative_path = buffer.getvalue().strip()
        review_buffer = io.StringIO()
        with mock.patch.object(hr, "utc_now", return_value="2000-01-01T00:00:00Z"), \
                contextlib.redirect_stdout(review_buffer):
            exit_code = _run_cli(["review", "--root", str(self.root), "--receipt", relative_path,
                                  "--kind", "independent_session", "--ref", "t", "--verdict", "disagree"],
                                 identity="test-reviewer")
        self.assertEqual(exit_code, 2, review_buffer.getvalue())
        self.assertIn("clock", review_buffer.getvalue())
        receipt = json.loads((self.root / relative_path).read_text(encoding="utf-8"))
        self.assertEqual(len(receipt["reviews"]), 1)

    def test_record_refuses_a_version_that_matches_no_winner_pin(self):
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "widget", "pin": "2.0.0rc5 (tag v2.0.0rc5)"}]}]}), encoding="utf-8")
        argv = ["record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands", "--component-version", "2.0.0rc5"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(self._run(argv), 2, buffer.getvalue())
        self.assertIn("--allow-unbound-version", buffer.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self._run([*argv, "--allow-unbound-version"]), 0)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([*argv[:-1], "2.0.0rc5 (tag v2.0.0rc5)"])
        self.assertEqual(exit_code, 0, buffer.getvalue())

    def test_review_from_the_recorders_identity_is_refused(self):
        exit_code, output = self._record_then_review(reviewer="test-recorder")
        self.assertEqual(exit_code, 2, output)
        self.assertIn("recorder's own identity", output)

    def test_review_fails_closed_without_an_identity(self):
        exit_code, output = self._record_then_review(reviewer=None)
        self.assertEqual(exit_code, 2, output)
        self.assertIn("--identity", output)

    def test_missing_git_is_a_clear_error_not_a_traceback(self):
        buffer = io.StringIO()
        with mock.patch.object(hr.shutil, "which", return_value=None), contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 2, buffer.getvalue())
        self.assertIn("git is not on PATH", buffer.getvalue())


class ReviewIndependenceTests(unittest.TestCase):
    """validate and review_state treat a review as independent only when its reviewer identity
    differs from recorded_by, it is not older than the observation, and no reviewer's latest
    verdict dissents (the audit's simulated same-session 'independent_session' review)."""

    RECORDER = hr.identity_digest("recorder")
    OTHER = hr.identity_digest("other")
    THIRD = hr.identity_digest("third")

    def _receipt(self, reviews: list[dict], *, recorded_by: bool = True) -> dict:
        receipt = {"observed_at_utc": "2026-01-01T00:00:00Z", "reviews": [
            {"kind": "self", "ref": "record", "verdict": "agree", "at_utc": "2026-01-01T00:00:00Z"}, *reviews]}
        if recorded_by:
            receipt["recorded_by"] = {"identity_sha256": self.RECORDER}
        return receipt

    @staticmethod
    def _review(identity: str | None, verdict: str = "agree", at_utc: str = "2026-01-01T01:00:00Z") -> dict:
        review = {"kind": "independent_session", "ref": "r", "verdict": verdict, "at_utc": at_utc}
        if identity is not None:
            review["reviewer"] = {"identity_sha256": identity}
        return review

    def test_same_identity_review_is_not_independent(self):
        self.assertEqual(hr.review_state(self._receipt([self._review(self.RECORDER)])), "none")

    def test_distinct_identity_agree_is_independent(self):
        self.assertEqual(hr.review_state(self._receipt([self._review(self.OTHER)])), "agree")

    def test_any_standing_dissent_vetoes(self):
        receipt = self._receipt([self._review(self.OTHER), self._review(self.THIRD, "needs_changes")])
        self.assertEqual(hr.review_state(receipt), "dissent")

    def test_a_reviewer_can_withdraw_a_dissent_with_a_newer_review(self):
        receipt = self._receipt([
            self._review(self.OTHER, "disagree", "2026-01-01T01:00:00Z"),
            self._review(self.OTHER, "agree", "2026-01-01T02:00:00Z"),
        ])
        self.assertEqual(hr.review_state(receipt), "agree")

    def test_review_dated_before_the_observation_does_not_count(self):
        receipt = self._receipt([self._review(self.OTHER, at_utc="2025-12-31T23:00:00Z")])
        self.assertEqual(hr.review_state(receipt), "none")

    def test_a_malformed_dissent_still_vetoes_and_cannot_be_withdrawn(self):
        # Review of #117 finding 4.
        for dissent in (self._review(None, "disagree"), self._review(self.RECORDER, "needs_changes"),
                        self._review(self.OTHER, "disagree", "2025-12-31T23:00:00Z")):
            receipt = self._receipt([self._review(self.THIRD), dissent,
                                     self._review(self.OTHER, "agree", "2026-01-01T05:00:00Z")])
            self.assertEqual(hr.review_state(receipt), "dissent", dissent)

    def test_a_malformed_agree_keeps_the_state_from_agree(self):
        receipt = self._receipt([self._review(self.OTHER), self._review(None)])
        self.assertEqual(hr.review_state(receipt), "none")

    def test_a_dissent_without_recorded_by_still_vetoes(self):
        receipt = self._receipt([self._review(self.OTHER, "disagree")], recorded_by=False)
        self.assertEqual(hr.review_state(receipt), "dissent")

    def test_receipt_without_recorded_by_has_no_independent_review(self):
        self.assertEqual(hr.review_state(self._receipt([self._review(self.OTHER)], recorded_by=False)), "none")

    def test_validate_rejects_same_identity_missing_reviewer_and_early_reviews(self):
        errors: list[str] = []
        receipt = self._receipt([self._review(self.RECORDER), self._review(None),
                                 self._review(self.OTHER, at_utc="2025-12-31T23:00:00Z")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_support_tree(root)
            path = root / "evidence" / "hosts" / "h-20260101" / "x.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}", encoding="utf-8")
            hr.validate_receipt_cross_references(root, "h-20260101", path, receipt, errors, set(), set(), set(), {})
        joined = "\n".join(errors)
        self.assertIn("recorder's own identity", joined)
        self.assertIn("must carry reviewer.identity_sha256", joined)
        self.assertIn("precedes observed_at_utc", joined)


class FlipRuleGatingTests(unittest.TestCase):
    """A receipt recorded and reviewed entirely by one host must not, on its own, enter
    build_summary's independently_reviewed_native_proven_pass_stages (the list
    scripts/component_matrix.py's macOS-acceptance flip rule reads): it also needs
    host.second_physical_machine: true and a host.os/architecture consistent with the
    claimed platform_id."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.commit = _init_support_tree(self.root)

    def _write_receipt(self, *, second_physical_machine: bool, os_value: str = "linux",
                        architecture: str = "x86_64", platform_id: str = "linux-wsl2-x86_64",
                        independent_review_ref: str = "another session") -> None:
        receipt = {
            "schema_version": 1,
            "id": "test-host-20260101--widget--use--20260101",
            "kind": "host_acceptance",
            "host": {
                "host_id": "test-host-20260101", "platform_id": platform_id, "os": os_value,
                "architecture": architecture, "second_physical_machine": second_physical_machine,
            },
            "catalog_revision": self.commit,
            "recorded_by": {"identity_sha256": hr.identity_digest("recorder")},
            "component_id": "widget",
            "stage": "use",
            "commands": [{
                "cmd": "echo hi", "exit": 0, "duration_s": 0.01,
                "output_sha256": hashlib.sha256(b"hi\n").hexdigest(), "output_excerpt": "hi",
            }],
            "tool_versions": {},
            "observed_at_utc": "2026-01-01T00:00:00Z",
            "result": "pass",
            "claim": "test claim",
            "limitations": ["test limitation"],
            "evidence_class": "native_proven",
            "reviews": [
                {"kind": "self", "ref": "record", "verdict": "agree", "at_utc": "2026-01-01T00:00:00Z"},
                {"kind": "independent_session", "ref": independent_review_ref, "verdict": "agree",
                 "at_utc": "2026-01-01T01:00:00Z", "reviewer": {"identity_sha256": hr.identity_digest("reviewer")}},
            ],
        }
        host_dir = self.root / "evidence" / "hosts" / "test-host-20260101"
        host_dir.mkdir(parents=True, exist_ok=True)
        (host_dir / f"{receipt['id']}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def test_reviewed_native_proven_pass_without_second_physical_machine_does_not_flip(self):
        self._write_receipt(second_physical_machine=False)
        summary = hr.build_summary(self.root)
        stages = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"][
            "independently_reviewed_native_proven_pass_stages"]
        self.assertEqual(stages, [])

    def test_reviewed_native_proven_pass_with_second_physical_machine_flips(self):
        self._write_receipt(second_physical_machine=True)
        summary = hr.build_summary(self.root)
        stages = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"][
            "independently_reviewed_native_proven_pass_stages"]
        self.assertEqual(stages, ["use"])

    def test_platform_identity_mismatch_does_not_flip(self):
        # adoption/manifest.json (written by _init_support_tree) declares linux-wsl2-x86_64
        # as os=linux/architecture=x86_64; a receipt claiming that platform_id while
        # self-declaring a different os/architecture must not satisfy the flip rule.
        self._write_receipt(second_physical_machine=True, os_value="macos", architecture="arm64")
        summary = hr.build_summary(self.root)
        stages = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"][
            "independently_reviewed_native_proven_pass_stages"]
        self.assertEqual(stages, [])

    def test_malformed_review_does_not_flip(self):
        # A review with an empty ref (schema: reviews[].ref minLength 1) is structurally
        # invalid; build_summary's stricter macOS-flip list must exclude a receipt whose
        # only independent review is malformed, even though it is otherwise
        # native_proven/pass/second_physical_machine/platform-identity-consistent.
        self._write_receipt(second_physical_machine=True, independent_review_ref="")
        summary = hr.build_summary(self.root)
        stages = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"][
            "independently_reviewed_native_proven_pass_stages"]
        self.assertEqual(stages, [])

    def test_platform_profile_map_reads_adoption_manifest(self):
        profiles = hr.platform_profile_map(self.root)
        self.assertEqual(profiles["linux-wsl2-x86_64"], {"os": "linux", "architecture": "x86_64"})



class JsonEqualityTests(unittest.TestCase):
    """A boolean must not satisfy a numeric const or enum (Python treats True == 1)."""

    def test_boolean_does_not_equal_numeric_const(self):
        errors = []
        hr.validate_against_schema(True, {"const": 1}, "schema_version", errors)
        self.assertTrue(errors)

    def test_numeric_const_still_matches(self):
        errors = []
        hr.validate_against_schema(1, {"const": 1}, "schema_version", errors)
        self.assertEqual(errors, [])

    def test_boolean_does_not_match_numeric_enum(self):
        errors = []
        hr.validate_against_schema(False, {"enum": [0, 1]}, "x", errors)
        self.assertTrue(errors)


class RegisterFileSortTests(unittest.TestCase):
    """register_file() keeps manifests/evidence.json files[] sorted by path
    (bisect insert) instead of always appending, so record/review stay
    conflict-friendly for parallel PRs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _paths(self) -> list[str]:
        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        return [entry["path"] for entry in evidence["files"]]

    def test_new_files_are_inserted_in_sorted_position(self):
        for relative in ("z-later.json", "a-earlier.json", "m-middle.json"):
            (self.root / relative).write_text("{}", encoding="utf-8")
            hr.register_file(self.root, relative)
        self.assertEqual(self._paths(), ["a-earlier.json", "m-middle.json", "z-later.json"])

    def test_updating_an_existing_path_keeps_its_position_and_hash(self):
        for relative in ("a-earlier.json", "m-middle.json", "z-later.json"):
            (self.root / relative).write_text("{}", encoding="utf-8")
            hr.register_file(self.root, relative)
        (self.root / "m-middle.json").write_text('{"changed": true}', encoding="utf-8")
        hr.register_file(self.root, "m-middle.json")
        self.assertEqual(self._paths(), ["a-earlier.json", "m-middle.json", "z-later.json"])
        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        updated = next(entry for entry in evidence["files"] if entry["path"] == "m-middle.json")
        self.assertEqual(updated["sha256"], hashlib.sha256(b'{"changed": true}').hexdigest())

    def test_insertion_order_does_not_matter_for_final_sort(self):
        for relative in ("delta.json", "alpha.json", "charlie.json", "bravo.json"):
            (self.root / relative).write_text("{}", encoding="utf-8")
            hr.register_file(self.root, relative)
        self.assertEqual(self._paths(), sorted(self._paths()))


if __name__ == "__main__":
    unittest.main()
