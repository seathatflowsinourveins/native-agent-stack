"""Regression cases use synthetic receipts, never private execution logs."""

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from scripts.validate import InvalidPublication, validate


class PublicationValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.receipt = {
            "schema_version": 1, "id": "sample", "kind": "native_cli_e2e",
            "component_ids": ["example"], "claim": "Fixture command exited zero.",
            "limitations": ["Synthetic fixture; not a live command run."],
            "data": {"exit_code": 0},
        }
        self.stack = {
            "schema_version": 1,
            "components": [{"id": "example", "version": "1.0.0", "profile": "core",
                            "commands": ["example --version"], "evidence_ids": ["sample"]}],
            "profiles": [{"id": "core", "component_ids": ["example"]}], "models": [],
        }
        self.evidence = {
            "schema_version": 1,
            "receipts": [{**{key: value for key, value in self.receipt.items()
                              if key not in {"schema_version", "data"}},
                          "path": "evidence/receipts/sample.json"}],
            "files": [],
        }
        self.write_json("evidence/receipts/sample.json", self.receipt)
        self.write("evidence/artifacts/output.txt", "example 1.0.0\n")
        for relative in ("evidence/receipts/sample.json", "evidence/artifacts/output.txt"):
            content = (self.root / relative).read_bytes()
            self.evidence["files"].append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        self.save()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_json(self, relative, content):
        self.write(relative, json.dumps(content, indent=2) + "\n")

    def save(self):
        self.write_json("manifests/stack.json", self.stack)
        self.write_json("manifests/evidence.json", self.evidence)

    def assert_invalid(self, fragment):
        with self.assertRaisesRegex(InvalidPublication, fragment):
            validate(self.root)

    def test_valid_bundle_reports_counts(self):
        self.assertEqual(validate(self.root), {"components": 1, "profiles": 1, "receipts": 1, "hashed_files": 2})

    def test_changed_artifact_fails_hash_even_when_length_unchanged(self):
        self.write("evidence/artifacts/output.txt", "example 9.0.0\n")
        self.assert_invalid("SHA-256 mismatch")

    def test_missing_receipt_fails(self):
        (self.root / "evidence/receipts/sample.json").unlink()
        self.assert_invalid("file missing")

    def test_unknown_receipt_reference_fails(self):
        self.stack["components"][0]["evidence_ids"] = ["absent"]
        self.save()
        self.assert_invalid("unknown evidence absent")

    def test_unhashed_evidence_fails(self):
        self.write("evidence/artifacts/extra.txt", "extra evidence")
        self.assert_invalid("not hash-listed")

    def test_traversal_and_absolute_paths_fail(self):
        for path in ("../outside.txt", "/etc/passwd", "evidence/../outside.txt", "evidence//output.txt", "C:\\temp\\output.txt"):
            with self.subTest(path=path):
                self.evidence["files"][1]["path"] = path
                self.save()
                self.assert_invalid("path must be canonical, relative")

    def test_symlink_file_and_parent_directory_fail(self):
        target = self.root / "target.txt"
        target.write_text("example 1.0.0\n", encoding="utf-8")
        artifact = self.root / "evidence/artifacts/output.txt"
        artifact.unlink()
        artifact.symlink_to(target)
        self.assert_invalid("symlinks are forbidden")
        artifact.unlink()
        artifact.parent.rmdir()
        artifact.parent.symlink_to(self.root, target_is_directory=True)
        self.assert_invalid("symlinks are forbidden")

    def test_duplicate_component_receipt_profile_and_hash_paths_fail(self):
        for field, target in (("components", self.stack), ("profiles", self.stack), ("receipts", self.evidence), ("files", self.evidence)):
            with self.subTest(field=field):
                target[field].append(dict(target[field][0]))
                self.save()
                self.assert_invalid("duplicate")
                target[field].pop()

    def test_profile_mismatch_fails(self):
        self.stack["components"][0]["profile"] = "optional"
        self.save()
        self.assert_invalid("profile membership mismatch")

    def test_receipt_payload_metadata_must_match_manifest(self):
        self.evidence["receipts"][0]["claim"] = "Different claim"
        self.save()
        self.assert_invalid("payload claim differs")

    def test_evidence_must_cover_referencing_component(self):
        self.evidence["receipts"][0]["component_ids"] = ["other"]
        self.save()
        self.assert_invalid("does not cover component")

    def test_historical_inventory_requires_scope_limitation(self):
        self.evidence["receipts"][0]["kind"] = "historical_inventory"
        self.save()
        self.assert_invalid("historical inventory needs explicit non-live limitation")

    def test_personal_paths_and_credentials_rejected_without_echoing(self):
        for content, expected in (("/" + "home" + "/private-person/project", "personal home path"),
                                  ("hf" + "_" + "x" * 32, "Hugging Face token"),
                                  ("ghp" + "_" + "y" * 36, "GitHub token"),
                                  ("C:" + "\\Users\\private-person\\project", "Windows user path")):
            with self.subTest(expected=expected):
                self.write("README.md", content)
                with self.assertRaises(InvalidPublication) as error:
                    validate(self.root)
                self.assertIn(expected, str(error.exception))
                self.assertNotIn(content, str(error.exception))

    def test_generic_variable_paths_are_allowed(self):
        self.write("README.md", 'Use "${HOME}/.codex" and "${PROJECT_ROOT}"; /dev/null is valid. Anonymized /home/example and /mnt/c/Users/example are permitted.')
        validate(self.root)

    def test_session_identifiers_rejected_even_when_glued_to_words(self):
        session_id = "-".join(("01234567", "89ab", "cdef", "0123", "456789abcdef"))
        for content in (session_id, "task" + session_id, "thread" + session_id.upper() + "suffix"):
            with self.subTest(content_style=content[:6]):
                self.write("README.md", content)
                with self.assertRaises(InvalidPublication) as error:
                    validate(self.root)
                self.assertIn("local session identifier", str(error.exception))
                self.assertNotIn(content, str(error.exception))

    def test_companion_task_handles_rejected_without_echoing(self):
        handle = "-".join(("task", "a" * 8, "b" * 6))
        for content in (handle, "backend" + handle.upper() + "completed"):
            with self.subTest(content_style=content[:6]):
                self.write("README.md", content)
                with self.assertRaises(InvalidPublication) as error:
                    validate(self.root)
                self.assertIn("local companion task handle", str(error.exception))
                self.assertNotIn(content, str(error.exception))

    def test_native_tool_and_source_only_references_are_valid(self):
        self.stack["components"][0]["commands"] = [
            {"tool": "find_symbol", "arguments": {"name": "example"}},
            {"skill_invocation": None, "source_only": True},
        ]
        self.save()
        validate(self.root)

    def test_malformed_reference_types_fail_cleanly(self):
        self.stack["models"] = [{"id": "example", "runtime": []}]
        self.evidence["receipts"][0]["component_ids"] = None
        self.save()
        self.assert_invalid("unknown runtime")

    def test_duplicate_json_keys_fail(self):
        self.write("manifests/stack.json", '{"schema_version": 1, "schema_version": 1}')
        self.assert_invalid("invalid JSON")

    def test_empty_command_and_boolean_byte_count_fail(self):
        self.stack["components"][0]["commands"] = [""]
        self.evidence["files"][0]["bytes"] = True
        self.save()
        self.assert_invalid("expected nonempty string")

    @staticmethod
    def png_fixture():
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
                + chunk(b"IEND", b""))

    def write_binary(self, relative, content, hashed=True):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if hashed:
            self.evidence["files"].append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        self.save()

    def test_hash_listed_structural_png_evidence_is_allowed(self):
        self.write_binary("evidence/artifacts/screenshot.png", self.png_fixture())
        self.assertEqual(validate(self.root)["hashed_files"], 3)

    def test_fake_corrupt_and_trailing_png_bytes_are_rejected(self):
        valid = self.png_fixture()
        for content in (b"not actually a PNG", valid[:8], valid[:40] + b"\x00" + valid[41:], valid + b"trailing"):
            with self.subTest(content_size=len(content)):
                self.write_binary("evidence/artifacts/screenshot.png", content)
                self.assert_invalid("invalid PNG structure or checksum")
                self.evidence["files"].pop()

    def test_unlisted_png_and_png_outside_evidence_are_rejected(self):
        self.write_binary("evidence/artifacts/screenshot.png", self.png_fixture(), hashed=False)
        self.assert_invalid("PNG must be a hash-listed evidence artifact")
        (self.root / "evidence/artifacts/screenshot.png").unlink()
        self.write_binary("screenshots/other.png", self.png_fixture())
        self.assert_invalid("PNG must be a hash-listed evidence artifact")

    def test_other_binary_formats_are_rejected_even_if_hash_listed(self):
        self.write_binary("evidence/artifacts/binary.dat", b"\xff\xfe\x00\x01")
        self.assert_invalid("cannot inspect as UTF-8")


if __name__ == "__main__":
    unittest.main()
