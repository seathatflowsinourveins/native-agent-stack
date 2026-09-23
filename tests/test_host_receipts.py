"""Tests for scripts/host_receipts.py: schema/code sync, fixture validation and a
recorder round trip. Never write evidence/hosts in the real repository tree from
these tests; everything mutating runs against a temporary copy."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

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


class ValidateFixtureTests(unittest.TestCase):
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


class RecorderRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_support_tree(self.root)

    def _run(self, argv: list[str]) -> int:
        args = hr.build_parser().parse_args(argv)
        return args.func(args)

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
            ])
        self.assertEqual(review_exit, 0, review_buffer.getvalue())

        receipt = json.loads((self.root / relative_path).read_text(encoding="utf-8"))
        kinds = [review["kind"] for review in receipt["reviews"]]
        self.assertEqual(kinds, ["self", "independent_session"])

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
            summary_exit = hr.cmd_summary(argparse.Namespace(root=self.root, json=True))
        self.assertEqual(summary_exit, 0)
        summary = json.loads(summary_buffer.getvalue())
        stage_counts = summary["components"]["widget"]["platforms"]["linux-wsl2-x86_64"]["stages"]["use"]
        self.assertEqual(stage_counts["pass"], 1)


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
                        architecture: str = "x86_64", platform_id: str = "linux-wsl2-x86_64") -> None:
        receipt = {
            "schema_version": 1,
            "id": "test-host-20260101--widget--use--20260101",
            "kind": "host_acceptance",
            "host": {
                "host_id": "test-host-20260101", "platform_id": platform_id, "os": os_value,
                "architecture": architecture, "second_physical_machine": second_physical_machine,
            },
            "catalog_revision": self.commit,
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
                {"kind": "independent_session", "ref": "another session", "verdict": "agree",
                 "at_utc": "2026-01-01T01:00:00Z"},
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

    def test_platform_profile_map_reads_adoption_manifest(self):
        profiles = hr.platform_profile_map(self.root)
        self.assertEqual(profiles["linux-wsl2-x86_64"], {"os": "linux", "architecture": "x86_64"})


if __name__ == "__main__":
    unittest.main()
