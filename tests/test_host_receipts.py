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
import shutil
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

    def test_id_pattern_accepts_a_supersede_generation_suffix(self):
        # A receipt recorded with 'record --supersedes' gets a '-N' (N >= 2) generation
        # suffix on the same host/component/stage/date id; both the schema and the code
        # must accept it.
        schema_pattern = re.compile(self.schema["properties"]["id"]["pattern"])
        for candidate in (
            "host-20260101--widget--use--20260101-2",
            "host-20260101--widget--use--20260101-10",
            "host-20260101--widget--use--20260101-999",
        ):
            self.assertTrue(schema_pattern.fullmatch(candidate), candidate)
            match = hr.ID_PATTERN.fullmatch(candidate)
            self.assertIsNotNone(match, candidate)
            self.assertEqual(match.group("date"), "20260101")

    def test_id_pattern_rejects_a_malformed_generation_suffix(self):
        # Generation 1 is the bare id with no suffix: '-0' and '-1' are never valid, and
        # neither is a leading zero ('-02') or a dangling hyphen.
        schema_pattern = re.compile(self.schema["properties"]["id"]["pattern"])
        for candidate in (
            "host-20260101--widget--use--20260101-0",
            "host-20260101--widget--use--20260101-1",
            "host-20260101--widget--use--20260101-02",
            "host-20260101--widget--use--20260101-",
        ):
            self.assertIsNone(schema_pattern.fullmatch(candidate), candidate)
            self.assertIsNone(hr.ID_PATTERN.fullmatch(candidate), candidate)

    def test_supersedes_property_shares_the_id_pattern_and_is_optional(self):
        self.assertEqual(self.schema["properties"]["supersedes"]["pattern"], self.schema["properties"]["id"]["pattern"])
        self.assertNotIn("supersedes", self.schema["required"])


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

    def test_supersedes_component_mismatch_is_rejected(self):
        # 'widget' appears exactly once in valid.json's id (the component segment); a
        # supersedes pointing at a different component id is a nonsensical cross-link.
        def substitute(data):
            data["supersedes"] = data["id"].replace("widget", "not-widget", 1)

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("supersedes component segment", output)
        self.assertIn("does not match component_id", output)

    def test_supersedes_referencing_an_unregistered_receipt_is_rejected(self):
        # supersedes must resolve to a receipt manifests/evidence.json actually knows about;
        # a dangling reference (the named original was never placed/registered) is rejected.
        def substitute(data):
            original_id = data["id"]
            data["supersedes"] = original_id
            data["id"] = f"{original_id}-2"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("is not registered in manifests/evidence.json", output)

    def test_supersedes_well_formed_and_registered_is_accepted(self):
        # The happy path at the validate_receipt_cross_references level: supersedes names a
        # real, registered receipt for the same host/component/stage/date.
        original_path = self._place("valid.json")
        original_id = json.loads(original_path.read_text(encoding="utf-8"))["id"]

        def substitute(data):
            data["supersedes"] = original_id
            data["id"] = f"{original_id}-2"

        self._place("valid.json", filename=f"{original_id}-2.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 0, output)

    def test_supersedes_host_mismatch_is_rejected(self):
        def substitute(data):
            data["id"] = f"{data['id']}-2"
            data["supersedes"] = "other-host-20260101--widget--use--20260101"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("supersedes host segment", output)

    def test_supersedes_stage_mismatch_is_rejected(self):
        def substitute(data):
            data["id"] = f"{data['id']}-2"
            data["supersedes"] = "fixture-host-20260101--widget--install--20260101"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("supersedes stage segment", output)

    def test_supersedes_date_mismatch_is_rejected(self):
        # 'same day' is the UTC date segment carried in the id itself.
        def substitute(data):
            data["id"] = f"{data['id']}-2"
            data["supersedes"] = "fixture-host-20260101--widget--use--20260102"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("supersedes date segment", output)

    def test_supersedes_self_reference_is_rejected(self):
        def substitute(data):
            data["id"] = f"{data['id']}-2"
            data["supersedes"] = data["id"]

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("must not equal this receipt's own id", output)

    def test_supersedes_higher_generation_is_rejected(self):
        # supersedes must be a *lower* generation than this receipt's own id.
        def substitute(data):
            original_id = data["id"]
            data["id"] = f"{original_id}-2"
            data["supersedes"] = f"{original_id}-3"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("must be a lower generation", output)

    def test_bare_id_with_supersedes_is_rejected(self):
        # Generation 1 (no '-N' suffix) must not carry a supersedes field at all.
        def substitute(data):
            data["supersedes"] = "fixture-host-20260101--widget--use--20260100"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("must not carry a supersedes field", output)

    def test_generation_suffixed_id_without_supersedes_is_rejected(self):
        # A '-N' id must carry a supersedes field naming what it supersedes.
        def substitute(data):
            data["id"] = f"{data['id']}-2"

        self._place("valid.json", patch=substitute)
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("must carry a supersedes field", output)

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
                # host.os/architecture are auto-detected unless overridden; pin them to
                # match the linux-wsl2-x86_64 platform_id so this test's later
                # cmd_validate() cross-check is consistent on every host OS/arch.
                "--os", "linux", "--architecture", "x86_64",
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
                # See test_record_writes_a_valid_registered_receipt: pin host.os/
                # architecture so cmd_validate()'s cross-check is host-independent.
                "--os", "linux", "--architecture", "x86_64",
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
                # See test_record_writes_a_valid_registered_receipt: pin host.os/
                # architecture so cmd_validate()'s cross-check is host-independent.
                "--os", "linux", "--architecture", "x86_64",
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
                # See test_record_writes_a_valid_registered_receipt: pin host.os/
                # architecture so cmd_validate()'s cross-check is host-independent.
                "--os", "linux", "--architecture", "x86_64",
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
        # This test records twice for the same host/component/stage; pin the clock so both
        # calls land on the same UTC date regardless of when the test happens to run.
        with mock.patch.object(hr, "utc_now", return_value="2026-01-01T00:00:00Z"):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(self._run(argv), 2, buffer.getvalue())
            self.assertIn("--allow-unbound-version", buffer.getvalue())
            allow_buffer = io.StringIO()
            with contextlib.redirect_stdout(allow_buffer):
                self.assertEqual(self._run([*argv, "--allow-unbound-version"]), 0, allow_buffer.getvalue())
            # Re-recording the same host/component/stage/date with the version written
            # correctly (no --allow-unbound-version needed) must not silently overwrite the
            # receipt just written above; --supersedes records it as the newer, corrected
            # receipt instead.
            superseded_id = json.loads(
                (self.root / allow_buffer.getvalue().strip()).read_text(encoding="utf-8"))["id"]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = self._run([*argv[:-1], "2.0.0rc5 (tag v2.0.0rc5)", "--supersedes", superseded_id])
            self.assertEqual(exit_code, 0, buffer.getvalue())

    def test_overlong_model_is_refused_before_anything_is_written(self):
        # Codex review of #117: a --model over the schema's 100 characters used to write a receipt
        # that validate then rejected.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands", "--model", "m" * 101,
            ])
        self.assertEqual(exit_code, 2, buffer.getvalue())
        self.assertFalse((self.root / "evidence" / "hosts" / "test-host-20260101").exists())
        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["files"], [])

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        relative_path = out.getvalue().strip()
        before = (self.root / relative_path).read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as review_out:
            exit_code = _run_cli(["review", "--root", str(self.root), "--receipt", relative_path, "--kind",
                                  "independent_session", "--ref", "t", "--verdict", "agree", "--model", "m" * 101],
                                 identity="test-reviewer")
        self.assertEqual(exit_code, 2, review_out.getvalue())
        self.assertEqual((self.root / relative_path).read_bytes(), before)

    def test_validate_refuses_future_dated_observations_and_reviews(self):
        # Codex review of #117: a future date would stay the "latest" receipt or review.
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        path = self.root / out.getvalue().strip()
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["reviews"].append({"kind": "independent_session", "ref": "t", "verdict": "agree",
                                   "at_utc": "2099-01-01T00:00:00Z",
                                   "reviewer": {"identity_sha256": hr.identity_digest("x")}})
        errors: list[str] = []
        hr.validate_receipt_cross_references(self.root, path.parent.name, path, receipt, errors,
                                             set(), set(), set(), {})
        self.assertTrue(any("reviews[1].at_utc: 2099-01-01T00:00:00Z is later" in e for e in errors), errors)
        receipt["observed_at_utc"] = "2099-01-01T00:00:00Z"
        errors = []
        hr.validate_receipt_cross_references(self.root, path.parent.name, path, receipt, errors,
                                             set(), set(), set(), {})
        self.assertTrue(any("observed_at_utc: 2099-01-01T00:00:00Z is later" in e for e in errors), errors)

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


class SupersedeRecordTests(unittest.TestCase):
    """2026-09-25 incident: re-recording the same host/component/stage on the same day
    silently overwrote the existing receipt file, erasing an appended independent_session
    'needs_changes' review. record must now refuse (before running any command) instead of
    overwriting, and --supersedes is the reviewable way to record a new receipt for that same
    host/component/stage/date, leaving the original file byte-identical."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)
        # Every test here records more than once and relies on the calls landing on the same
        # UTC date; pin the clock so a run that happens to straddle midnight UTC cannot flake.
        patcher = mock.patch.object(hr, "utc_now", return_value="2026-01-01T00:00:00Z")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, argv: list[str]) -> int:
        return _run_cli(argv)

    def _record_argv(self, extra: list[str] | None = None) -> list[str]:
        return [
            "record", "--root", str(self.root),
            "--host-id", "test-host-20260101",
            "--platform-id", "linux-wsl2-x86_64",
            "--os", "linux", "--architecture", "x86_64",
            "--component-id", "widget",
            "--stage", "use",
            "--evidence-class", "synthetic",
            "--from-stack-commands",
            *(extra or []),
        ]

    def test_record_refuses_to_overwrite_an_existing_receipt(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        path = self.root / relative_path

        # An independent review with a needs_changes verdict: exactly the kind of review the
        # 2026-09-25 incident's silent overwrite erased.
        review_buffer = io.StringIO()
        with contextlib.redirect_stdout(review_buffer):
            review_exit = self._run([
                "review", "--root", str(self.root), "--receipt", relative_path,
                "--kind", "independent_session", "--ref", "t", "--verdict", "needs_changes",
                "--identity", "reviewer",
            ])
        self.assertEqual(review_exit, 0, review_buffer.getvalue())
        before = path.read_bytes()

        # A marker file a second record run must never touch if it refuses before running commands.
        marker = self.root / "executed.marker"
        second_buffer = io.StringIO()
        with contextlib.redirect_stdout(second_buffer):
            second_exit = self._run(self._record_argv(["--cmd", f"touch {marker}"]))
        second_output = second_buffer.getvalue()

        self.assertEqual(second_exit, 2, second_output)
        self.assertIn(relative_path, second_output)
        self.assertIn("independent_session:needs_changes", second_output)
        self.assertFalse(marker.exists(), "record ran a command before refusing to overwrite")
        self.assertEqual(path.read_bytes(), before,
                         "the existing receipt was not byte-identical after a refused overwrite")

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_supersedes_writes_a_distinct_receipt_and_leaves_the_original_untouched(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        original_relative = buffer.getvalue().strip()
        original_path = self.root / original_relative
        original_id = json.loads(original_path.read_text(encoding="utf-8"))["id"]
        before = original_path.read_bytes()

        second_buffer = io.StringIO()
        with contextlib.redirect_stdout(second_buffer):
            second_exit = self._run(self._record_argv(["--supersedes", original_id]))
        self.assertEqual(second_exit, 0, second_buffer.getvalue())
        superseding_relative = second_buffer.getvalue().strip()
        self.assertNotEqual(superseding_relative, original_relative)
        self.assertTrue(superseding_relative.endswith(f"{original_id}-2.json"), superseding_relative)

        self.assertEqual(original_path.read_bytes(), before, "supersedes touched the original receipt file")

        superseding_receipt = json.loads((self.root / superseding_relative).read_text(encoding="utf-8"))
        self.assertEqual(superseding_receipt["supersedes"], original_id)
        self.assertEqual(superseding_receipt["id"], f"{original_id}-2")
        # No reviews are inherited: the new receipt starts with only its own fresh 'self' entry.
        self.assertEqual([review["kind"] for review in superseding_receipt["reviews"]], ["self"])

        # A third recording must supersede the *latest* generation (the second, "-2"), not
        # the original: --supersedes requires the latest, so it finds generation 3.
        third_buffer = io.StringIO()
        with contextlib.redirect_stdout(third_buffer):
            third_exit = self._run(self._record_argv(["--supersedes", f"{original_id}-2"]))
        self.assertEqual(third_exit, 0, third_buffer.getvalue())
        self.assertTrue(third_buffer.getvalue().strip().endswith(f"{original_id}-3.json"))
        third_receipt = json.loads((self.root / third_buffer.getvalue().strip()).read_text(encoding="utf-8"))
        self.assertEqual(third_receipt["supersedes"], f"{original_id}-2")

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_refusal_names_the_latest_generation_to_supersede(self):
        # Generations 1 and 2 both exist; a plain re-record (no --supersedes) must name
        # generation 2 (the latest), not generation 1, as the receipt to supersede.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        original_id = json.loads((self.root / buffer.getvalue().strip()).read_text(encoding="utf-8"))["id"]

        second_buffer = io.StringIO()
        with contextlib.redirect_stdout(second_buffer):
            second_exit = self._run(self._record_argv(["--supersedes", original_id]))
        self.assertEqual(second_exit, 0, second_buffer.getvalue())

        third_buffer = io.StringIO()
        with contextlib.redirect_stdout(third_buffer):
            third_exit = self._run(self._record_argv())
        self.assertEqual(third_exit, 2, third_buffer.getvalue())
        self.assertIn(f"{original_id}-2", third_buffer.getvalue())

    def test_supersedes_an_older_generation_while_a_newer_one_exists_is_refused(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        original_id = json.loads((self.root / buffer.getvalue().strip()).read_text(encoding="utf-8"))["id"]

        second_buffer = io.StringIO()
        with contextlib.redirect_stdout(second_buffer):
            second_exit = self._run(self._record_argv(["--supersedes", original_id]))
        self.assertEqual(second_exit, 0, second_buffer.getvalue())

        # Generation 2 now exists; superseding generation 1 (no longer the latest) is refused,
        # naming generation 2 as the one to supersede instead.
        third_buffer = io.StringIO()
        with contextlib.redirect_stdout(third_buffer):
            third_exit = self._run(self._record_argv(["--supersedes", original_id]))
        self.assertEqual(third_exit, 2, third_buffer.getvalue())
        self.assertIn(f"{original_id}-2", third_buffer.getvalue())
        self.assertFalse((self.root / "evidence" / "hosts" / "test-host-20260101" /
                          f"{original_id}-3.json").exists())

    def test_record_deletes_the_file_it_created_and_reraises_on_a_write_failure(self):
        # The exclusive-create write only ever creates a file this run itself made; a failure
        # partway through (mocked here as json.dumps raising) must delete it and propagate the
        # original error rather than leaving a truncated receipt or swallowing the failure.
        with mock.patch.object(hr.json, "dumps", side_effect=ValueError("simulated write failure")):
            with self.assertRaises(ValueError):
                self._run(self._record_argv())
        host_dir = self.root / "evidence" / "hosts" / "test-host-20260101"
        leftover = list(host_dir.glob("*.json")) if host_dir.is_dir() else []
        self.assertEqual(leftover, [], f"receipt file(s) left on disk after a failed write: {leftover}")
        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["files"], [])

    def test_supersedes_rejects_an_id_for_a_different_host_component_stage_or_date(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        relative_path = buffer.getvalue().strip()
        real_id = json.loads((self.root / relative_path).read_text(encoding="utf-8"))["id"]
        host_id, component_id, stage, date_stamp = real_id.split("--")

        for bad_id in (
            f"other-host-20260101--{component_id}--{stage}--{date_stamp}",
            f"{host_id}--not-{component_id}--{stage}--{date_stamp}",
            f"{host_id}--{component_id}--install--{date_stamp}",
            f"{host_id}--{component_id}--{stage}--20200101",
            "not-a-well-formed-id",
        ):
            bad_buffer = io.StringIO()
            with contextlib.redirect_stdout(bad_buffer):
                bad_exit = self._run(self._record_argv(["--supersedes", bad_id]))
            self.assertEqual(bad_exit, 2, f"{bad_id}: {bad_buffer.getvalue()}")

        # None of the rejected attempts touched the original receipt.
        self.assertEqual(json.loads((self.root / relative_path).read_text(encoding="utf-8"))["id"], real_id)

    def test_supersedes_rejects_a_nonexistent_receipt_id(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run(self._record_argv())
        self.assertEqual(exit_code, 0, buffer.getvalue())
        real_id = json.loads((self.root / buffer.getvalue().strip()).read_text(encoding="utf-8"))["id"]

        # Well-formed and same-family, but generation 2 was never actually recorded.
        missing_buffer = io.StringIO()
        with contextlib.redirect_stdout(missing_buffer):
            exit_code = self._run(self._record_argv(["--supersedes", f"{real_id}-2"]))
        self.assertEqual(exit_code, 2, missing_buffer.getvalue())
        self.assertIn("does not exist", missing_buffer.getvalue())


class ReviewAppendSafetyTests(unittest.TestCase):
    """review takes an exclusive flock on a lock file beside the receipt, re-reads under the
    lock, and writes via a temp file + os.replace() so concurrent reviews cannot lose one and
    a crash mid-write cannot truncate the receipt that was there before."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _run(self, argv: list[str]) -> int:
        return _run_cli(argv)

    def _record(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = self._run([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                "--component-id", "widget", "--stage", "use",
                "--evidence-class", "synthetic", "--from-stack-commands",
            ])
        self.assertEqual(exit_code, 0, buffer.getvalue())
        return buffer.getvalue().strip()

    def test_two_sequential_reviews_both_persist(self):
        relative_path = self._record()

        first_buffer = io.StringIO()
        with contextlib.redirect_stdout(first_buffer):
            first_exit = self._run(["review", "--root", str(self.root), "--receipt", relative_path,
                                    "--kind", "independent_session", "--ref", "first", "--verdict", "agree",
                                    "--identity", "reviewer-one"])
        self.assertEqual(first_exit, 0, first_buffer.getvalue())

        second_buffer = io.StringIO()
        with contextlib.redirect_stdout(second_buffer):
            second_exit = self._run(["review", "--root", str(self.root), "--receipt", relative_path,
                                     "--kind", "independent_session", "--ref", "second",
                                     "--verdict", "needs_changes", "--identity", "reviewer-two"])
        self.assertEqual(second_exit, 0, second_buffer.getvalue())

        receipt = json.loads((self.root / relative_path).read_text(encoding="utf-8"))
        self.assertEqual([review["ref"] for review in receipt["reviews"]],
                         ["scripts/host_receipts.py record", "first", "second"])

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

        # No lock or temp artifacts were left in a state that would block a later review.
        host_dir = self.root / "evidence" / "hosts" / "test-host-20260101"
        self.assertEqual(list(host_dir.glob("*.tmp-*")), [])

    def test_a_write_failure_leaves_the_original_receipt_byte_identical(self):
        relative_path = self._record()
        path = self.root / relative_path
        before = path.read_bytes()

        with mock.patch.object(hr.os, "replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaises(OSError):
                self._run(["review", "--root", str(self.root), "--receipt", relative_path,
                          "--kind", "independent_session", "--ref", "t", "--verdict", "agree",
                          "--identity", "reviewer"])

        self.assertEqual(path.read_bytes(), before, "a failed atomic replace changed the original receipt")
        leftover = list(path.parent.glob(f"{path.name}.tmp-*"))
        self.assertEqual(leftover, [], f"temp file(s) left behind after a failed write: {leftover}")

        # The lock was released despite the failure (via the finally block): a subsequent
        # normal review still succeeds rather than deadlocking.
        recover_buffer = io.StringIO()
        with contextlib.redirect_stdout(recover_buffer):
            recover_exit = self._run(["review", "--root", str(self.root), "--receipt", relative_path,
                                      "--kind", "independent_session", "--ref", "t2", "--verdict", "agree",
                                      "--identity", "reviewer"])
        self.assertEqual(recover_exit, 0, recover_buffer.getvalue())


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


class SanitizeUserNameTests(unittest.TestCase):
    """sanitize() redacts the user name only as a whole token. A substring match cut a
    two-letter account name such as "ed" out of "recorded", "used" or "cached": under it,
    hardware_profile.py --record-host refused "recorded-host-20260101" and a recorded excerpt
    read "cach<user>". Every case runs as that account, whatever the test host's own user is,
    and home paths must stay redacted in every form. Home paths are spelled through variables
    so that this file passes the repository's own home-path scan (scripts/validate.py)."""

    USERS, HOME_DIR = "Users", "home"
    HOME = f"/{USERS}/ed"

    def _sanitize(self, text: str) -> str:
        with mock.patch.dict(os.environ, {"USER": "ed", "LOGNAME": "ed", "HOME": self.HOME}):
            return hr.sanitize(text)

    def test_words_that_contain_a_two_letter_name_are_kept(self):
        for text in ("recorded-host-20260101", "used embedded cached shared edge",
                     "ed2 edx ed_old ED", '{"hosts": ["cached-a"]}'):
            with self.subTest(text=text):
                self.assertEqual(self._sanitize(text), text)

    def test_the_name_as_a_whole_token_is_redacted(self):
        for text, expected in (("ed", "<user>"), ("ed@mbp:~", "<user>@mbp:~"), ('"ed"', '"<user>"'),
                               ("owner ed staff", "owner <user> staff"), ("~ed/", "~<user>/")):
            with self.subTest(text=text):
                self.assertEqual(self._sanitize(text), expected)

    def test_home_paths_stay_redacted_in_every_form(self):
        # $HOME itself becomes ~. The name in any other home-path form (another OS's layout, a
        # Windows path, a Claude project slug, URL-encoded, JSON-escaped) is still a token: an
        # escape ending in a letter or digit ("%2F", "\u002f", "\n") is not part of its word.
        # Another account whose name merely starts with it falls to the private-content pattern.
        users, home = self.USERS, self.HOME_DIR
        for text, expected in (
                (f"/{users}/ed/code/x.py", "~/code/x.py"),
                (f"/{home}/ed/x", f"/{home}/<user>/x"),
                (f"C:\\{users}\\ed\\x", f"C:\\{users}\\<user>\\x"),
                (f"-{users}-ed-src-app", f"-{users}-<user>-src-app"),
                (f"file%3A%2F%2F%2F{users}%2Fed%2Fx", f"file%3A%2F%2F%2F{users}%2F<user>%2Fx"),
                (f"\\u002f{users}\\u002fed\\u002fx", f"\\u002f{users}\\u002f<user>\\u002fx"),
                (f"\\x2f{home}\\x2fed", f"\\x2f{home}\\x2f<user>"),
                ('"line\\ned@mbp"', '"line\\n<user>@mbp"'),
                (f"/{home}/ed_old/x", "[redacted]x")):
            with self.subTest(text=text):
                self.assertEqual(self._sanitize(text), expected)

    def test_record_keeps_words_in_the_excerpt_and_redacts_the_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_support_tree(root)
            buffer = io.StringIO()
            with mock.patch.dict(os.environ, {"USER": "ed", "LOGNAME": "ed"}), contextlib.redirect_stdout(buffer):
                exit_code = _run_cli([
                    "record", "--root", str(root), "--host-id", "test-host-20260101",
                    "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                    "--component-id", "widget", "--stage", "install", "--evidence-class", "synthetic",
                    "--cmd", "printf '%s\\n' 'embedded model cached (used 2 GB)' 'owner: ed'"])
            self.assertEqual(exit_code, 0, buffer.getvalue())
            receipt = json.loads((root / buffer.getvalue().strip()).read_text(encoding="utf-8"))
        self.assertEqual(receipt["commands"][0]["output_excerpt"],
                         "embedded model cached (used 2 GB)\nowner: <user>\n")


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


class QualifiedModelSchemaSyncTests(unittest.TestCase):
    """adoption/host-receipt.schema.json qualified_models[] item required keys and result
    enum must match the code's constants, the same way SchemaSyncTests covers the top-level
    fields."""

    def setUp(self):
        self.schema = _load_schema()

    def test_qualified_model_required_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["qualified_models"]["items"]["required"]),
            set(hr.QUALIFIED_MODEL_REQUIRED))

    def test_qualified_model_result_enum_matches(self):
        self.assertEqual(
            set(self.schema["properties"]["qualified_models"]["items"]["properties"]["result"]["enum"]),
            hr.QUALIFIED_MODEL_RESULTS)

    def test_qualified_models_is_not_in_top_level_required(self):
        # Optional field: a receipt with no local model qualification is still valid.
        self.assertNotIn("qualified_models", self.schema["required"])


class UseStageLintTests(unittest.TestCase):
    """#164: ``record`` refuses ``--stage use`` only when every command is exactly a program and one help or version
    argument, a convenience that is knowingly incomplete; the independent review is the control, and no status is
    derived from command text (Codex re-check of be09a5e2)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _record(self, stage: str, commands: list[str], extra: list[str] | None = None) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli([
                "record", "--root", str(self.root), "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                "--component-id", "widget", "--stage", stage, "--evidence-class", "synthetic",
                *[argument for command in commands for argument in ("--cmd", command)],
                *(extra or [])])
        return exit_code, buffer.getvalue()

    def test_only_an_exact_help_or_version_argv_matches(self):
        for command in ("rtk --version", "ccusage --help", "uv version", "rtk -V", "git help"):
            self.assertTrue(hr.bare_help_or_version(command), command)
        # Functional commands are never refused, and wrapped help calls pass the lint (left to the review).
        for command in ("du -h /dev/null", "df -h", "python3 -c 'print(6*7)' --version", "ccusage daily --json",
                        "sh -c 'rtk --version'", "true && rtk -V", "rtk help gain", "echo hi"):
            self.assertFalse(hr.bare_help_or_version(command), command)

    def test_record_refuses_a_use_stage_of_only_bare_help_and_version_calls(self):
        exit_code, output = self._record("use", ["true --help", "true --version"])
        self.assertEqual(exit_code, 2, output)
        self.assertIn("help or", output)
        self.assertFalse((self.root / "evidence" / "hosts").exists()
                         and list((self.root / "evidence" / "hosts").rglob("*.json")))

    def test_help_calls_record_as_install_and_a_functional_command_as_use(self):
        # This test records twice at stage 'use'; pin the clock so both land on the same UTC
        # date regardless of when the test happens to run.
        with mock.patch.object(hr, "utc_now", return_value="2026-01-01T00:00:00Z"):
            self.assertEqual(self._record("install", ["true --help"])[0], 0)
            use_exit, use_output = self._record("use", ["true --version", "echo hi"])
            self.assertEqual(use_exit, 0, use_output)
            # A second 'use' receipt for the same host/component/date must not silently
            # overwrite the one just written; supersede it explicitly instead.
            use_id = json.loads((self.root / use_output.strip()).read_text(encoding="utf-8"))["id"]
            exit_code, output = self._record("use", ["du -h /dev/null"], extra=["--supersedes", use_id])
            self.assertEqual(exit_code, 0, output)

    def test_validate_derives_nothing_from_command_text(self):
        self.assertEqual(self._record("use", ["echo hi"])[0], 0)
        path = next((self.root / "evidence" / "hosts").rglob("*.json"))
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["commands"][0]["cmd"] = "widget --help"
        errors: list[str] = []
        hr.validate_receipt_cross_references(self.root, path.parent.name, path, receipt, errors, set(), set(), set(),
                                             {})
        self.assertFalse(any("help" in error for error in errors), errors)


class QualifiedModelRecordTests(unittest.TestCase):
    """scripts/host_receipts.py record --qualified-model / --qualified-models-file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _record(self, extra_argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                # host.os/architecture are auto-detected unless overridden; pin them
                # to match linux-wsl2-x86_64 so test_qualified_model_flag_is_recorded_
                # and_validates' cmd_validate() cross-check is host-independent (see
                # test_record_writes_a_valid_registered_receipt for the same fix).
                "--os", "linux", "--architecture", "x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--from-stack-commands",
                *extra_argv,
            ])
        return exit_code, buffer.getvalue()

    def test_qualified_model_flag_is_recorded_and_validates(self):
        qm = json.dumps({
            "model_id": "Qwen/Qwen3-8B-AWQ", "revision": "abc123", "runtime": "vllm",
            "runtime_version": "0.9.0", "bars": "20/20 tool calls, 4/5 tasks", "result": "pass",
        })
        exit_code, output = self._record(["--qualified-model", qm])
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual(receipt["qualified_models"], [json.loads(qm)])

        validate_buffer = io.StringIO()
        with contextlib.redirect_stdout(validate_buffer):
            validate_exit = hr.cmd_validate(argparse.Namespace(root=self.root))
        self.assertEqual(validate_exit, 0, validate_buffer.getvalue())

    def test_repeated_qualified_model_flags_accumulate(self):
        qm1 = json.dumps({"model_id": "a", "revision": "r1", "runtime": "vllm", "runtime_version": "1",
                          "bars": "bars", "result": "pass"})
        qm2 = json.dumps({"model_id": "b", "revision": "r2", "runtime": "mlx-lm", "runtime_version": "2",
                          "bars": "bars", "result": "fail"})
        exit_code, output = self._record(["--qualified-model", qm1, "--qualified-model", qm2])
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual(len(receipt["qualified_models"]), 2)

    def test_qualified_models_file_is_merged(self):
        models_file = self.root / "models.json"
        models_file.write_text(json.dumps([
            {"model_id": "a", "revision": "r1", "runtime": "vllm", "runtime_version": "1",
             "bars": "bars", "result": "pass"},
        ]), encoding="utf-8")
        exit_code, output = self._record(["--qualified-models-file", str(models_file)])
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual(len(receipt["qualified_models"]), 1)

    def test_no_qualified_model_flag_omits_the_key(self):
        exit_code, output = self._record([])
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertNotIn("qualified_models", receipt)

    def test_malformed_qualified_model_json_is_rejected(self):
        exit_code, output = self._record(["--qualified-model", "{not json"])
        self.assertEqual(exit_code, 2, output)

    def test_qualified_model_missing_required_key_is_rejected(self):
        qm = json.dumps({"model_id": "a", "revision": "r1", "runtime": "vllm"})  # no runtime_version/bars/result
        exit_code, output = self._record(["--qualified-model", qm])
        self.assertEqual(exit_code, 2, output)

    def test_qualified_model_bad_result_is_rejected(self):
        qm = json.dumps({"model_id": "a", "revision": "r1", "runtime": "vllm", "runtime_version": "1",
                         "bars": "bars", "result": "maybe"})
        exit_code, output = self._record(["--qualified-model", qm])
        self.assertEqual(exit_code, 2, output)

    def _record_without_from_stack_commands(self, extra_argv: list[str], marker: Path) -> tuple[int, str]:
        """Like _record, but with an explicit --cmd (that would touch ``marker`` if it ran)
        instead of --from-stack-commands, so a test can assert nothing executed."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli([
                "record", "--root", str(self.root),
                "--host-id", "test-host-20260101",
                "--platform-id", "linux-wsl2-x86_64",
                "--component-id", "widget",
                "--stage", "use",
                "--evidence-class", "synthetic",
                "--cmd", f"touch {marker}",
                *extra_argv,
            ])
        return exit_code, buffer.getvalue()

    def test_overlong_bars_is_rejected_before_any_command_runs(self):
        # Every schema constraint (not just required keys and the result enum) must be
        # checked up front: an over-length `bars` (schema maxLength 400) previously slipped
        # past the CLI's own ad hoc check, ran the qualification command(s), and failed only
        # at the pre-write validate_receipt_shape() call.
        marker = self.root / "executed.marker"
        qm = json.dumps({
            "model_id": "a", "revision": "r1", "runtime": "vllm", "runtime_version": "1",
            "bars": "x" * 401, "result": "pass",
        })
        exit_code, output = self._record_without_from_stack_commands(["--qualified-model", qm], marker)
        self.assertEqual(exit_code, 2, output)
        self.assertIn("checked before running any command", output)
        self.assertFalse(marker.exists(), "the qualification command ran despite the invalid entry")

    def test_result_as_a_list_is_rejected_without_crashing(self):
        # `entry.get("result") not in {"pass", "fail"}` raises TypeError: unhashable type on
        # a non-hashable value like a list; the schema-driven validator's equality-based enum
        # check must reject this cleanly (exit 2, no traceback) and run nothing.
        marker = self.root / "executed.marker"
        qm = json.dumps({
            "model_id": "a", "revision": "r1", "runtime": "vllm", "runtime_version": "1",
            "bars": "bars", "result": [],
        })
        exit_code, output = self._record_without_from_stack_commands(["--qualified-model", qm], marker)
        self.assertEqual(exit_code, 2, output)
        self.assertFalse(marker.exists(), "the qualification command ran despite the invalid entry")



ALIAS_REPOSITORY = "https://github.com/example/widget"
ALIAS_PIN = "v2.0.0 (tag v2.0.0; source 0123456789abcdef0123456789abcdef01234567)"


def _add_alias_catalog(root: Path) -> None:
    """A stack id 'widget-alias' sharing its repository with landscape winner 'widget-winner'."""
    stack_path = root / "manifests" / "stack.json"
    stack = json.loads(stack_path.read_text(encoding="utf-8"))
    stack["components"].append({"id": "widget-alias", "version": "2.0.0", "profile": "core",
                                "repository": ALIAS_REPOSITORY, "commands": ["echo hi"]})
    stack_path.write_text(json.dumps(stack), encoding="utf-8")
    (root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
        {"winners": [{"component_id": "widget-winner", "repository": ALIAS_REPOSITORY + ".git/",
                      "pin": ALIAS_PIN}]}]}), encoding="utf-8")


class StackAliasResolverTests(unittest.TestCase):
    """host_receipts.stack_aliases_of_winners: a manifests/stack.json id whose repository is a
    landscape winner's repository, and which is not itself a winner id, is an alias."""

    def test_same_repository_is_an_alias_of_the_winner(self):
        aliases = hr.stack_aliases_of_winners(
            [{"id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py"}],
            [{"component_id": "data-alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py"}])
        self.assertEqual(aliases, {"alpaca-py": ("data-alpaca-py",)})

    def test_different_repository_is_not_an_alias(self):
        aliases = hr.stack_aliases_of_winners(
            [{"id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py"}],
            [{"component_id": "data-alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py2"}])
        self.assertEqual(aliases, {})

    def test_repository_normalization_variants_match_exactly(self):
        winner = [{"component_id": "data-alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py"}]
        for variant in (" https://github.com/alpacahq/alpaca-py ", "https://github.com/alpacahq/alpaca-py/",
                        "https://github.com/alpacahq/alpaca-py.git", "https://GitHub.com/AlpacaHQ/Alpaca-Py.git/",
                        "http://github.com/alpacahq/alpaca-py", "HTTPS://www.github.com/alpacahq/alpaca-py",
                        "github.com/alpacahq/alpaca-py",
                        # manifests/stack.json records some repositories as release or tree URLs
                        "https://github.com/alpacahq/alpaca-py/releases/tag/v0.44.0",
                        "https://github.com/alpacahq/alpaca-py/tree/v0.44.0/alpaca",
                        "https://github.com/alpacahq/alpaca-py/blob/master/README.md",
                        "https://github.com/alpacahq/alpaca-py#readme", "https://github.com/alpacahq/alpaca-py?tab=x"):
            with self.subTest(variant=variant):
                self.assertEqual(
                    hr.stack_aliases_of_winners([{"id": "alpaca-py", "repository": variant}], winner),
                    {"alpaca-py": ("data-alpaca-py",)})
        for other in ("https://github.com/alpacahq", "https://github.com/alpacahq/alpaca-py2",
                      "https://gitlab.com/alpacahq/alpaca-py", "https://notgithub.com/alpacahq/alpaca-py",
                      None, ""):
            with self.subTest(other=other):
                self.assertEqual(hr.stack_aliases_of_winners([{"id": "alpaca-py", "repository": other}], winner), {})
        self.assertIsNone(hr.normalize_repository(" / "))
        self.assertEqual(hr.normalize_repository("https://x/y.git/.git/"), "x/y")
        # Another forge keeps its full path (groups nest there) and only loses scheme, www., '/' and '.git'.
        self.assertEqual(hr.normalize_repository("https://www.GitLab.com/g/sub/r.git/"), "gitlab.com/g/sub/r")
        self.assertNotEqual(hr.normalize_repository("https://gitlab.com/g/sub/r"),
                            hr.normalize_repository("https://gitlab.com/g/sub"))

    def test_real_stack_release_and_tree_urls_reduce_to_their_repository(self):
        stack = json.loads((REPO_ROOT / "manifests" / "stack.json").read_text(encoding="utf-8"))
        shaped = [component for component in stack["components"]
                  if any(part in (component.get("repository") or "") for part in ("/releases/", "/tree/"))]
        self.assertTrue(shaped, "expected release/tree repository URLs in manifests/stack.json")
        for component in shaped:
            with self.subTest(component=component["id"]):
                self.assertEqual(hr.normalize_repository(component["repository"]).count("/"), 2)

    def test_an_id_that_is_itself_a_winner_is_not_an_alias(self):
        winners = [{"component_id": "codex", "repository": "https://github.com/openai/codex"},
                   {"component_id": "codex-native-sdk", "repository": "https://github.com/openai/codex"}]
        self.assertEqual(
            hr.stack_aliases_of_winners([{"id": "codex", "repository": "https://github.com/openai/codex"}], winners),
            {})

    def test_multiple_winners_sharing_a_repository_are_all_named(self):
        winners = [{"component_id": "tool-b", "repository": "https://github.com/example/tool"},
                   {"component_id": "tool-a", "repository": "https://github.com/example/tool"},
                   {"component_id": "tool-a", "repository": "https://github.com/example/tool"}]
        self.assertEqual(
            hr.stack_aliases_of_winners([{"id": "tool", "repository": "https://github.com/example/tool"}], winners),
            {"tool": ("tool-a", "tool-b")})

    def test_a_winner_without_a_repository_matches_nothing(self):
        self.assertEqual(hr.stack_aliases_of_winners([{"id": "tool"}], [{"component_id": "tool-winner"}]), {})

    def test_root_resolver_reads_stack_and_landscape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_support_tree(root)
            _add_alias_catalog(root)
            self.assertEqual(hr.winner_stack_aliases(root), {"widget-alias": ("widget-winner",)})

    def test_real_repository_alias_set(self):
        # The exact set of stack ids that share a repository with a differently named landscape winner
        # on 2026-09-24 (ai-memory, socraticode and codex are winners themselves, so not aliases). An
        # added or dropped alias fails here and must be reviewed (record refuses every alias).
        aliases = hr.winner_stack_aliases(REPO_ROOT)
        self.assertEqual(aliases, {
            "alpaca-py": ("data-alpaca-py",),
            "duckdb": ("data-duckdb",),
            "edgartools": ("data-edgartools",),
            "exchange-calendars": ("data-exchange-calendars",),
            "nautilus-trader": ("nautilustrader",),
        })
        for winner_id in ("ai-memory", "socraticode", "codex"):
            self.assertNotIn(winner_id, aliases)


class AliasRefusalMessageTests(unittest.TestCase):
    """host_receipts.alias_refusal names every winner a stack id aliases, with its current pin(s)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "catalogs" / "landscape").mkdir(parents=True)

    def _winners(self, winners):
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(
            json.dumps({"layers": [{"winners": winners}]}), encoding="utf-8")

    def test_not_an_alias_is_not_refused(self):
        self._winners([])
        self.assertIsNone(hr.alias_refusal(self.root, "tool", {}))

    def test_multi_winner_message_names_each_winner_and_pin(self):
        self._winners([{"component_id": "tool-a", "pin": "1.0.0"}, {"component_id": "tool-b", "pin": "2.0.0"},
                       {"component_id": "tool-b", "pin": "2.1.0"}])
        message = hr.alias_refusal(self.root, "tool", {"tool": ("tool-a", "tool-b")})
        self.assertIn("landscape winner 'tool-a' (current pin: '1.0.0'), 'tool-b' (current pin: '2.0.0' | '2.1.0') "
                      "(same repository)", message)
        self.assertIn("--component-id 'tool'", message)

    def test_winner_without_a_pin_says_current_pin_none(self):
        self._winners([{"component_id": "tool-a"}, {"component_id": "tool-b", "pin": "  "}])
        message = hr.alias_refusal(self.root, "tool", {"tool": ("tool-a", "tool-b")})
        self.assertIn("'tool-a' (current pin: none), 'tool-b' (current pin: none)", message)


class StackAliasRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)
        _add_alias_catalog(self.root)

    def _record(self, component_id: str, *extra: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli(["record", "--root", str(self.root), "--host-id", "test-host-20260101",
                                  "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                                  "--component-id", component_id, "--stage", "use", "--evidence-class", "synthetic",
                                  "--cmd", "echo hi", *extra])
        return exit_code, buffer.getvalue()

    def test_record_refuses_a_stack_alias_and_names_the_canonical_winner(self):
        evidence_before = (self.root / "manifests" / "evidence.json").read_bytes()
        for extra in ((), ("--component-version", ALIAS_PIN), ("--component-version", "2.0.0", "--allow-unbound-version")):
            with self.subTest(extra=extra):
                exit_code, output = self._record("widget-alias", *extra)
                self.assertEqual(exit_code, 2, output)
                self.assertIn("'widget-winner'", output)
                self.assertIn(ALIAS_PIN, output)
                self.assertIn("never bind", output)
        self.assertEqual(list((self.root / "evidence" / "hosts").iterdir()), [])
        self.assertEqual((self.root / "manifests" / "evidence.json").read_bytes(), evidence_before)

    def test_record_under_the_canonical_winner_id_still_works(self):
        exit_code, output = self._record("widget-winner")
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual(receipt["tool_versions"], {"widget-winner": ALIAS_PIN})

    def test_refusal_says_stack_commands_remain_reachable(self):
        exit_code, output = self._record("widget-alias")
        self.assertEqual(exit_code, 2, output)
        self.assertIn("--from-stack-commands still reuses the commands documented under 'widget-alias'", output)

    def _record_from_stack(self, component_id: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli(["record", "--root", str(self.root), "--host-id", "test-host-20260101",
                                  "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                                  "--component-id", component_id, "--stage", "use", "--evidence-class", "synthetic",
                                  "--from-stack-commands"])
        return exit_code, buffer.getvalue()

    def test_from_stack_commands_reuses_the_alias_commands_for_the_canonical_winner(self):
        exit_code, output = self._record_from_stack("widget-winner")
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual([command["cmd"] for command in receipt["commands"]], ["echo hi"])
        self.assertEqual(receipt["component_id"], "widget-winner")

    def test_from_stack_commands_refuses_to_guess_between_several_alias_ids(self):
        stack_path = self.root / "manifests" / "stack.json"
        stack = json.loads(stack_path.read_text(encoding="utf-8"))
        stack["components"].append({"id": "widget-alias-2", "version": "2.0.0", "profile": "core",
                                    "repository": ALIAS_REPOSITORY + "/releases/tag/v2.0.0",
                                    "commands": ["echo other"]})
        stack_path.write_text(json.dumps(stack), encoding="utf-8")
        exit_code, output = self._record_from_stack("widget-winner")
        self.assertEqual(exit_code, 2, output)
        self.assertIn("several stack ids sharing its repository carry commands (widget-alias, widget-alias-2)", output)
        self.assertEqual(list((self.root / "evidence" / "hosts").iterdir()), [])

    def test_from_stack_commands_without_any_names_every_id_searched(self):
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "lonely-winner", "repository": "https://github.com/example/lonely",
                          "pin": "1.0.0"}]}]}), encoding="utf-8")
        exit_code, output = self._record_from_stack("lonely-winner")
        self.assertEqual(exit_code, 2, output)
        self.assertIn("no plain-string commands found for component 'lonely-winner'", output)
        self.assertIn("pass --cmd", output)

    def test_stack_commands_for_record_prefers_the_ids_own_commands(self):
        aliases = {"widget-alias": ("widget",)}
        self.assertEqual(hr.stack_commands_for_record(self.root, "widget", aliases), (["echo hi"], None))


class StackAliasValidateTests(_ReceiptFixtureCase):
    ALIAS_PATH = "evidence/hosts/fixture-host-20260101/fixture-host-20260101--widget-alias--use--20260101.json"
    ENTRY = {"canonical_component_id": "widget-winner", "date": "2026-09-24", "reason": "test"}

    def setUp(self):
        super().setUp()
        _add_alias_catalog(self.root)

    @property
    def GRANDFATHERED(self):
        """The fixture entry, naming the current claim of ALIAS_PATH by claim_sha256 (or a placeholder)."""
        path = self.root / self.ALIAS_PATH
        try:
            digest = hr.receipt_claim_sha256(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            digest = "0" * 64
        return {self.ALIAS_PATH: {**self.ENTRY, "claim_sha256": digest}}

    def _place_alias(self):
        def substitute(data):
            data["id"] = "fixture-host-20260101--widget-alias--use--20260101"
            data["component_id"] = "widget-alias"
            data["tool_versions"] = {"widget-alias": "2.0.0"}
        return self._place("valid.json", patch=substitute)

    def _validate_with(self, grandfathered):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = hr.cmd_validate(argparse.Namespace(root=self.root, grandfathered_alias_receipts=grandfathered))
        return exit_code, buffer.getvalue()

    def test_alias_receipt_outside_the_grandfather_list_is_rejected(self):
        self._place_alias()
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn("is the manifests/stack.json id of landscape winner(s) widget-winner", output)

    def test_grandfathered_alias_receipt_passes(self):
        self._place_alias()
        exit_code, output = self._validate_with(self.GRANDFATHERED)
        self.assertEqual(exit_code, 0, output)

    def test_an_altered_claim_at_a_grandfathered_path_loses_the_exemption(self):
        self._place_alias()
        grandfathered = self.GRANDFATHERED
        path = self.root / self.ALIAS_PATH
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["tool_versions"] = {"widget-alias": "2.0.1"}   # an edit to what was recorded
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        exit_code, output = self._validate_with(grandfathered)
        self.assertEqual(exit_code, 1, output)
        self.assertIn(f"{self.ALIAS_PATH}: claim_sha256 {hr.receipt_claim_sha256(receipt)} is not the "
                      f"GRANDFATHERED_ALIAS_RECEIPTS claim_sha256 {grandfathered[self.ALIAS_PATH]['claim_sha256']}",
                      output)
        # The exemption is gone, so the alias rejection applies to the altered file as to any other.
        self.assertIn(f"{self.ALIAS_PATH}: component_id 'widget-alias' is the manifests/stack.json id", output)

    def test_an_appended_review_or_reformatting_keeps_the_exemption(self):
        # review appends to reviews[] and rewrites the file (main's #209 did so on a grandfathered receipt);
        # the recorded claim, and so the exemption, is unchanged.
        self._place_alias()
        grandfathered = self.GRANDFATHERED
        path = self.root / self.ALIAS_PATH
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt.setdefault("reviews", []).append(dict(receipt["reviews"][0]))
        path.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
        self.assertEqual(hr.grandfather_digest_error(self.root, self.ALIAS_PATH, grandfathered[self.ALIAS_PATH]),
                         None)
        self.assertEqual(hr.grandfathered_alias_paths(self.root, grandfathered), {self.ALIAS_PATH})

    def test_review_command_on_a_grandfathered_receipt_keeps_validate_passing(self):
        # End to end through the supported writer: review appends, rewrites and re-registers the file.
        self._place_alias()
        grandfathered = self.GRANDFATHERED
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _run_cli(["review", "--root", str(self.root), "--receipt", self.ALIAS_PATH, "--kind",
                             "self", "--ref", "test", "--verdict", "agree"],
                            identity="an-independent-reviewer-token")
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertEqual(len(json.loads((self.root / self.ALIAS_PATH).read_text(encoding="utf-8"))["reviews"]), 2)
        exit_code, output = self._validate_with(grandfathered)
        self.assertEqual(exit_code, 0, output)

    def test_a_lone_surrogate_in_a_grandfathered_claim_is_a_mismatch_not_a_crash(self):
        self._place_alias()
        grandfathered = self.GRANDFATHERED
        path = self.root / self.ALIAS_PATH
        path.write_text(path.read_text(encoding="utf-8").replace('"claim": "', '"claim": "\\ud800', 1),
                        encoding="utf-8")
        problem = hr.grandfather_digest_error(self.root, self.ALIAS_PATH, grandfathered[self.ALIAS_PATH])
        self.assertIn("is not the GRANDFATHERED_ALIAS_RECEIPTS claim_sha256", problem)

    def test_claim_digest_ignores_reviews_and_formatting_only(self):
        receipt = {"b": 1, "a": {"y": "é", "x": [1, 2]}, "reviews": [{"verdict": "agree"}]}
        reordered = {"reviews": [], "a": {"x": [1, 2], "y": "é"}, "b": 1}
        self.assertEqual(hr.receipt_claim_sha256(receipt), hr.receipt_claim_sha256(reordered))
        self.assertNotEqual(hr.receipt_claim_sha256(receipt), hr.receipt_claim_sha256({**receipt, "b": 2}))

    def test_grandfather_entry_without_a_claim_sha256_is_rejected(self):
        self._place_alias()
        exit_code, output = self._validate_with({self.ALIAS_PATH: dict(self.ENTRY)})
        self.assertEqual(exit_code, 1, output)
        self.assertIn("entry has no lowercase hex 'claim_sha256'", output)
        self.assertIn("component_id 'widget-alias' is the manifests/stack.json id", output)

    def test_corrupt_grandfathered_file_gets_an_accurate_error(self):
        path = self.root / self.ALIAS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        grandfathered = self.GRANDFATHERED   # a corrupt file has no claim, so it cannot be exempt
        exit_code, output = self._validate_with(grandfathered)
        self.assertEqual(exit_code, 1, output)
        self.assertIn(f"{self.ALIAS_PATH}: listed in GRANDFATHERED_ALIAS_RECEIPTS but is not a parseable JSON "
                      "receipt (corrupt or unreadable)", output)
        self.assertNotIn("component_id None", output)
        self.assertNotIn("no longer a manifests/stack.json alias", output)

    def test_non_object_grandfathered_file_gets_an_accurate_error(self):
        errors = hr.alias_receipt_errors(self.root, {self.ALIAS_PATH: None}, {"widget-alias": ("widget-winner",)},
                                         {self.ALIAS_PATH: dict(self.ENTRY, claim_sha256="0" * 64)})
        self.assertEqual(errors, [])   # file absent in a tree without that host: not judged
        self._place_alias()
        errors = hr.alias_receipt_errors(self.root, {self.ALIAS_PATH: None}, {"widget-alias": ("widget-winner",)},
                                         self.GRANDFATHERED)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("has no string component_id (not a receipt object)", errors[0])

    def test_grandfathered_entry_naming_the_wrong_canonical_id_is_rejected(self):
        self._place_alias()
        wrong = {self.ALIAS_PATH: {**self.GRANDFATHERED[self.ALIAS_PATH], "canonical_component_id": "other"}}
        exit_code, output = self._validate_with(wrong)
        self.assertEqual(exit_code, 1, output)
        self.assertIn("names canonical id 'other'", output)

    def test_stale_grandfather_entry_for_a_missing_file_is_rejected(self):
        (self.root / self.ALIAS_PATH).parent.mkdir(parents=True)   # the tree carries that host's evidence
        exit_code, output = self._validate_with(self.GRANDFATHERED)
        self.assertEqual(exit_code, 1, output)
        self.assertIn("no longer exists", output)

    def test_grandfather_entry_for_a_host_the_tree_does_not_carry_is_not_judged(self):
        exit_code, output = self._validate_with(self.GRANDFATHERED)
        self.assertEqual(exit_code, 0, output)
        self.assertTrue(hr.grandfather_file_expected(REPO_ROOT, "evidence/hosts/absent-host-20260101/x.json"))
        self.assertFalse(hr.grandfather_file_expected(self.root, self.ALIAS_PATH))

    def test_stale_grandfather_entry_that_is_no_longer_an_alias_is_rejected(self):
        self._place_alias()
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(
            json.dumps({"layers": []}), encoding="utf-8")
        exit_code, output = self._validate_with(self.GRANDFATHERED)
        self.assertEqual(exit_code, 1, output)
        self.assertIn("no longer a manifests/stack.json alias", output)

    def test_the_real_grandfather_list_applies_in_any_tree_holding_those_files(self):
        # Another checkout or a copy of this one: the same paths are exempt whatever script validates it.
        aliases = {"alpaca-py": ("data-alpaca-py",), "duckdb": ("data-duckdb",),
                   "nautilus-trader": ("nautilustrader",)}
        recorded = {}
        for relative in hr.GRANDFATHERED_ALIAS_RECEIPTS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / relative, target)   # the exact recorded bytes
            recorded[relative] = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))["component_id"]
        self.assertEqual(hr.alias_receipt_errors(self.root, recorded, aliases, hr.GRANDFATHERED_ALIAS_RECEIPTS), [])
        self.assertEqual(hr.grandfathered_alias_paths(self.root), set(hr.GRANDFATHERED_ALIAS_RECEIPTS))
        # The default validate path applies the real list, which does not exempt this fixture's alias receipt.
        for relative in hr.GRANDFATHERED_ALIAS_RECEIPTS:
            shutil.rmtree((self.root / relative).parent, ignore_errors=True)
        self._place_alias()
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1, output)
        self.assertIn(self.ALIAS_PATH, output)
        self.assertNotIn("no longer exists", output)

    def test_every_real_grandfathered_receipt_is_a_live_alias_of_its_canonical_id(self):
        aliases = hr.winner_stack_aliases(REPO_ROOT)
        # The exact grandfathered set (path -> canonical id): adding or dropping an entry fails here.
        host_dir = "evidence/hosts/macos-m5pro-20260924/"
        self.assertEqual(
            {relative: entry["canonical_component_id"] for relative, entry in hr.GRANDFATHERED_ALIAS_RECEIPTS.items()},
            {f"{host_dir}macos-m5pro-20260924--alpaca-py--use--20260924.json": "data-alpaca-py",
             f"{host_dir}macos-m5pro-20260924--duckdb--use--20260924.json": "data-duckdb",
             f"{host_dir}macos-m5pro-20260924--nautilus-trader--use--20260924.json": "nautilustrader"})
        for relative, entry in hr.GRANDFATHERED_ALIAS_RECEIPTS.items():
            with self.subTest(relative=relative):
                receipt = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
                self.assertIn(entry["canonical_component_id"], aliases.get(receipt["component_id"], ()))
                self.assertEqual(entry["date"], "2026-09-24")
                self.assertTrue(entry["reason"])
                self.assertEqual(entry["claim_sha256"], hr.receipt_claim_sha256(receipt))
        self.assertEqual(hr.grandfathered_alias_paths(REPO_ROOT), set(hr.GRANDFATHERED_ALIAS_RECEIPTS))

    def test_every_real_alias_receipt_is_grandfathered_and_validate_accepts_the_tree(self):
        # A receipt recorded under a stack alias that is not grandfathered (for example one merged
        # from main after the refusal landed) must fail this test, not only the CI validate step.
        aliases = hr.winner_stack_aliases(REPO_ROOT)
        alias_receipts = set()
        for _host_dir, path in hr._iter_receipt_files(REPO_ROOT):
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(receipt, dict) and aliases.get(receipt.get("component_id")):
                alias_receipts.add(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual(alias_receipts, set(hr.GRANDFATHERED_ALIAS_RECEIPTS))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = hr.main(["validate"])
        self.assertEqual(exit_code, 0, out.getvalue())


class ReceiptAliasTableTests(unittest.TestCase):
    """host_receipts.receipt_alias_table_errors ties tools/sota-convergence/receipt-component-aliases.json
    to the repository-inferred winner_stack_aliases() in both directions."""

    ALIASES = {"duckdb": ("data-duckdb",), "alpaca-py": ("data-alpaca-py",)}
    WINNERS = {"data-duckdb", "data-alpaca-py", "nautilustrader"}
    ABSENT = {"alpaca-py": "sota manifest has its own id"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _errors(self, table, absent=None):
        path = self.root / hr.RECEIPT_ALIASES_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 1, "aliases": table}), encoding="utf-8")
        return hr.receipt_alias_table_errors(self.root, self.ALIASES, self.WINNERS,
                                             self.ABSENT if absent is None else absent)

    def test_consistent_tables_agree(self):
        self.assertEqual(self._errors({"duckdb": "data-duckdb", "pandas-x": "sota-only-id"}), [])

    def test_absent_table_is_not_compared(self):
        self.assertEqual(hr.receipt_alias_table_errors(self.root, self.ALIASES, self.WINNERS, self.ABSENT), [])

    def test_explicit_winner_target_the_repository_does_not_infer_is_an_error(self):
        errors = self._errors({"duckdb": "data-duckdb", "nautilus-trader": "nautilustrader"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("maps 'nautilus-trader' to landscape winner 'nautilustrader'", errors[0])

    def test_inferred_alias_missing_from_the_table_is_an_error(self):
        errors = self._errors({})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("'duckdb' is the manifests/stack.json alias of landscape winner(s) data-duckdb", errors[0])

    def test_wrong_target_for_an_inferred_alias_is_an_error(self):
        errors = self._errors({"duckdb": "some-other-id"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("maps 'duckdb' to 'some-other-id'", errors[0])

    def test_stale_exemption_is_an_error(self):
        errors = self._errors({"duckdb": "data-duckdb", "alpaca-py": "data-alpaca-py"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("lists 'alpaca-py', but it is in the table", errors[0])
        errors = self._errors({"duckdb": "data-duckdb"}, absent={**self.ABSENT, "gone": "reason"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("lists 'gone', but it is no longer an inferred alias", errors[0])

    def test_malformed_table_is_an_error(self):
        self.assertIn("must map", self._errors(["duckdb"])[0])

    def test_real_tables_agree(self):
        self.assertEqual(hr.receipt_alias_table_errors(
            REPO_ROOT, hr.winner_stack_aliases(REPO_ROOT), hr.landscape_component_ids(REPO_ROOT)), [])


class LayerRefsTests(unittest.TestCase):
    """record --layer-ref writes layer_refs; a use receipt of a component several layers catalogue must name at least
    one; validate checks the named layers; build_summary exposes the scope and which receipts are superseded."""

    WIDGET = "https://github.com/example/widget"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)
        stack = json.loads((self.root / "manifests" / "stack.json").read_text(encoding="utf-8"))
        stack["components"][0]["repository"] = self.WIDGET
        (self.root / "manifests" / "stack.json").write_text(json.dumps(stack), encoding="utf-8")
        # widget wins foundation/native-clients and is an alternative in foundation/workers.
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"layer_id": "native-clients", "winners": [{"component_id": "widget", "repository": self.WIDGET,
                                                        "pin": "1.0.0"}]},
            {"layer_id": "workers", "alternatives": [{"name": "Widget workers", "repository": self.WIDGET + ".git"}]},
            {"layer_id": "isolation", "winners": [], "alternatives": []},
        ]}), encoding="utf-8")

    def _record(self, *extra: str, stage: str = "use") -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = _run_cli(["record", "--root", str(self.root), "--host-id", "test-host-20260101",
                                  "--platform-id", "linux-wsl2-x86_64", "--os", "linux", "--architecture", "x86_64",
                                  "--component-id", "widget", "--stage", stage, "--evidence-class", "synthetic",
                                  "--cmd", "echo hi", *extra])
        return exit_code, buffer.getvalue()

    def _validate(self) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = hr.cmd_validate(argparse.Namespace(root=self.root))
        return exit_code, buffer.getvalue()

    def test_component_layers_join_winner_ids_and_repositories(self):
        self.assertEqual(hr.component_layers(self.root, "widget"), ["foundation/native-clients", "foundation/workers"])
        self.assertEqual(hr.component_layers(self.root, "unlisted"), [])

    def test_a_scoped_use_receipt_is_written_and_validates(self):
        exit_code, output = self._record("--layer-ref", "foundation/workers", "--layer-ref", "foundation/native-clients")
        self.assertEqual(exit_code, 0, output)
        receipt = json.loads((self.root / output.strip()).read_text(encoding="utf-8"))
        self.assertEqual(receipt["layer_refs"], [{"catalog": "foundation", "layer_id": "workers"},
                                                 {"catalog": "foundation", "layer_id": "native-clients"}])
        self.assertEqual(self._validate()[0], 0, self._validate()[1])
        entry = hr.build_summary(self.root)["components"]["widget"]["platforms"]["linux-wsl2-x86_64"]["receipts"][0]
        self.assertEqual(entry["layer_scope"], ["foundation/native-clients", "foundation/workers"])
        self.assertIsNone(entry["supersedes_path"])

    def test_an_unscoped_use_receipt_of_a_multi_layer_component_is_refused_before_running(self):
        exit_code, output = self._record("--cmd", "touch ran-anyway")
        self.assertEqual(exit_code, 2)
        self.assertIn("catalogued in 2 layers (foundation/native-clients, foundation/workers)", output)
        self.assertFalse((self.root / "ran-anyway").exists())
        self.assertFalse((self.root / "evidence" / "hosts" / "test-host-20260101").exists())

    def test_an_unscoped_install_receipt_is_still_accepted(self):
        exit_code, output = self._record(stage="install")
        self.assertEqual(exit_code, 0, output)
        self.assertNotIn("layer_refs", json.loads((self.root / output.strip()).read_text(encoding="utf-8")))

    def test_bad_layer_refs_are_refused(self):
        for refs, message in ((["foundation/isolation"], "names no layer that catalogues 'widget'"),
                              (["workers"], "must be CATALOG/LAYER_ID"),
                              (["foundation/workers", "foundation/workers"], "is given twice")):
            with self.subTest(refs=refs):
                exit_code, output = self._record(*[arg for ref in refs for arg in ("--layer-ref", ref)])
                self.assertEqual(exit_code, 2)
                self.assertIn(message, output)

    def test_validate_rejects_unknown_and_repeated_layers(self):
        exit_code, output = self._record("--layer-ref", "foundation/workers")
        self.assertEqual(exit_code, 0, output)
        path = self.root / output.strip()
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["layer_refs"] = [{"catalog": "foundation", "layer_id": "workers"},
                                 {"catalog": "foundation", "layer_id": "workers"},
                                 {"catalog": "us-equities", "layer_id": "no-such-layer"}]
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        hr.register_file(self.root, output.strip())
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertIn("layer_refs names 'foundation/workers' more than once", output)
        self.assertIn("layer_refs names 'us-equities/no-such-layer', which is not a layer", output)
        receipt["layer_refs"] = []
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        hr.register_file(self.root, str(path.relative_to(self.root)))
        self.assertIn("must have at least 1 item", self._validate()[1])

    def test_receipt_layer_scope_never_widens_a_malformed_scope(self):
        self.assertIsNone(hr.receipt_layer_scope({}))
        self.assertEqual(hr.receipt_layer_scope({"layer_refs": "foundation/workers"}), [])
        self.assertEqual(hr.receipt_layer_scope({"layer_refs": [{"catalog": "foundation"}, 3]}), [])

    def test_superseded_receipts_leave_the_reviewed_stage_list(self):
        exit_code, output = self._record("--layer-ref", "foundation/workers")
        self.assertEqual(exit_code, 0, output)
        first = output.strip()
        exit_code, output = self._record("--layer-ref", "foundation/workers", "--supersedes", Path(first).stem)
        self.assertEqual(exit_code, 0, output)
        second = output.strip()
        entries = {entry["path"]: entry for entry in
                   hr.build_summary(self.root)["components"]["widget"]["platforms"]["linux-wsl2-x86_64"]["receipts"]}
        self.assertEqual(entries[second]["supersedes_path"], first)
        self.assertIsNone(entries[first]["supersedes_path"])
        self.assertEqual(hr.superseded_paths(entries.values()), {first})

    def test_validate_rejects_a_forked_supersede_chain(self):
        # PR #321 verification: A-2 and A-3 both superseding A passed validate, and A-2's agree then outlived
        # A-3's needs_changes. record cannot write a fork (it names the latest generation); validate now refuses one.
        exit_code, output = self._record("--layer-ref", "foundation/workers")
        self.assertEqual(exit_code, 0, output)
        exit_code, output = self._record("--layer-ref", "foundation/workers", "--supersedes", Path(output.strip()).stem)
        self.assertEqual(exit_code, 0, output)
        second = self.root / output.strip()
        self.assertEqual(self._validate()[0], 0, self._validate()[1])
        fork = json.loads(second.read_text(encoding="utf-8"))
        fork["id"] = fork["id"][:-2] + "-3"
        forked = second.with_name(second.name.replace("-2.json", "-3.json"))
        forked.write_text(json.dumps(fork, indent=2) + "\n", encoding="utf-8")
        hr.register_file(self.root, forked.relative_to(self.root).as_posix())
        exit_code, output = self._validate()
        self.assertEqual(exit_code, 1)
        self.assertEqual(output.count("a supersede chain must stay linear"), 2, output)
        # The linear repair: A-3 supersedes A-2 instead.
        fork["supersedes"] = fork["id"][:-2] + "-2"
        forked.write_text(json.dumps(fork, indent=2) + "\n", encoding="utf-8")
        hr.register_file(self.root, forked.relative_to(self.root).as_posix())
        self.assertEqual(self._validate()[0], 0, self._validate()[1])

    def test_layer_refs_name_the_catalogs_the_matrix_joins(self):
        from scripts import component_matrix
        self.assertIs(component_matrix.LANDSCAPE_FILES, hr.LANDSCAPE_CATALOGS)
        layers = hr.landscape_layers(REPO_ROOT)
        self.assertIn("foundation/workers", layers)
        self.assertIn("us-equities/agents-models-workers", layers)


if __name__ == "__main__":
    unittest.main()
