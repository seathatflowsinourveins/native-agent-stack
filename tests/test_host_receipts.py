"""Tests for scripts/host_receipts.py: schema/code sync, fixture validation and a
recorder round trip. Never write evidence/hosts in the real repository tree from
these tests; everything mutating runs against a temporary copy."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
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


if __name__ == "__main__":
    unittest.main()
