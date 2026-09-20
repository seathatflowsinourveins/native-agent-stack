"""Regression cases use synthetic receipts, never private execution logs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
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

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.root), *arguments],
                              check=True, capture_output=True)

    def init_git(self):
        self.git("init", "--quiet")
        self.write(".gitignore", "node_modules/\n.next/\n.runtime/\n__pycache__/\n.env\n")

    def test_git_ignores_nested_runtime_files_and_symlinks(self):
        self.init_git()
        for folder in ("node_modules", ".next", ".runtime", "__pycache__"):
            self.write_binary(f"project/{folder}/binary.dat", b"\xff\x00", hashed=False)
            self.write(f"project/{folder}/auth.json", "private local state")
            (self.root / f"project/{folder}/link").symlink_to(self.root)
        self.assertEqual(validate(self.root)["hashed_files"], 2)

    def test_git_tracked_ignored_private_text_is_still_scanned(self):
        self.init_git()
        for folder in ("node_modules", ".next", ".runtime", "__pycache__"):
            with self.subTest(folder=folder):
                name = f"project/{folder}/secret.txt"
                self.write(name, "ghp" + "_" + "x" * 36)
                self.git("add", "--force", "--", name)
                self.assert_invalid("GitHub token")
                self.git("rm", "--force", "--", name)

    def test_git_tracked_ignored_auth_file_and_symlink_fail(self):
        self.init_git()
        self.write(".env", "EXAMPLE=value")
        self.git("add", "--force", ".env")
        self.assert_invalid("private authentication/environment file")
        self.git("rm", "--force", ".env")
        path = self.root / "project/.runtime/link"
        path.parent.mkdir(parents=True)
        path.symlink_to(self.root / "manifests/stack.json")
        self.git("add", "--force", "--", str(path))
        self.assert_invalid("symlinks are forbidden")

    def test_git_untracked_nonignored_files_are_scanned(self):
        self.init_git()
        self.write("new/auth.json", "synthetic state")
        self.assert_invalid("private authentication/environment file")

    def test_git_ignored_hash_listed_evidence_is_always_scanned(self):
        self.init_git()
        self.write_binary("project/.runtime/secret.txt", ("hf" + "_" + "a" * 32).encode())
        self.assert_invalid("Hugging Face token")

    def test_git_ignored_required_manifests_are_always_scanned(self):
        self.init_git()
        self.write(".gitignore", "manifests/\n")
        self.evidence["private_note"] = "hf" + "_" + "a" * 32
        self.save()
        self.assert_invalid("manifests/evidence.json: contains possible Hugging Face token")

    def test_git_ignored_hash_listed_symlink_is_always_rejected(self):
        self.init_git()
        name = "project/.runtime/linked.txt"
        self.write_binary(name, b"example")
        path = self.root / name
        path.unlink()
        path.symlink_to(self.root / "evidence/artifacts/output.txt")
        self.assert_invalid("symlinks are forbidden")

    def test_git_ignored_unpublished_evidence_does_not_require_hash(self):
        self.init_git()
        self.write_binary("evidence/artifacts/.runtime/local.dat", b"\xff\x00", hashed=False)
        validate(self.root)

    def test_git_errors_never_fall_back_to_filesystem_success(self):
        self.init_git()
        for error in (OSError("unavailable"), subprocess.CalledProcessError(128, ["git"])):
            with self.subTest(error=type(error).__name__), patch("scripts.validate.subprocess.run", side_effect=error):
                self.assert_invalid("Git publication enumeration failed")
        (self.root / ".git/index").write_bytes(b"broken index")
        self.assert_invalid("Git publication enumeration failed")

    def test_git_other_root_or_truncated_listing_fails_closed(self):
        self.init_git()
        with patch("scripts.validate.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"/\n")):
            self.assert_invalid("Git publication enumeration failed")
        outputs = [subprocess.CompletedProcess([], 0, os.fsencode(self.root) + b"\n"),
                   subprocess.CompletedProcess([], 0, b"manifests/stack.json")]
        with patch("scripts.validate.subprocess.run", side_effect=outputs):
            self.assert_invalid("Git publication enumeration failed")

    def test_git_ignores_inherited_checkout_and_index_routing(self):
        self.init_git()
        self.write("secret.txt", "ghp" + "_" + "x" * 36)
        self.git("add", "secret.txt")
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "missing"),
                                     "GIT_INDEX_FILE": str(self.root / "empty-index")}):
            self.assert_invalid("GitHub token")

    def test_archive_scan_does_not_borrow_parent_repository_ignores(self):
        export = self.root / "export"
        export.mkdir()
        for name in ("manifests", "evidence"):
            shutil.move(str(self.root / name), export / name)
        self.init_git()
        self.root = export
        self.write("project/.runtime/secret.txt", "hf" + "_" + "a" * 32)
        self.assert_invalid("Hugging Face token")

    def test_archive_without_git_retains_binary_and_symlink_refusals(self):
        self.write_binary("project/node_modules/private.dat", b"\xff\x00", hashed=False)
        self.assert_invalid("cannot inspect as UTF-8")
        (self.root / "project/node_modules/private.dat").unlink()
        (self.root / "project/__pycache__").symlink_to(self.root, target_is_directory=True)
        self.assert_invalid("symlinks are forbidden")

    def test_hash_listed_convergence_png_is_allowed(self):
        self.write_binary("blueprints/convergence-practice/corpus/page.png", self.png_fixture())
        validate(self.root)

    @staticmethod
    def pdf_fixture(text=b"Synthetic PDF", extra=b""):
        stream = zlib.compress(b"BT /F1 12 Tf (" + text + b") Tj ET")
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>",
                   b"<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream"]
        output = b"%PDF-1.4\n%\xff\xfe\xfd\xfc\n" + extra
        offsets = []
        for number, content in enumerate(objects, 1):
            offsets.append(len(output))
            output += f"{number} 0 obj\n".encode() + content + b"\nendobj\n"
        xref = len(output)
        output += b"xref\n0 5\n0000000000 65535 f \n"
        output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
        return output + b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"

    def add_reviewed_pdf(self, relative="blueprints/convergence-practice/corpus/sample.pdf", *, raw=None, text=b"Synthetic PDF\n"):
        self.write_binary(relative + ".txt", text)
        self.write_binary(relative, self.pdf_fixture() if raw is None else raw)
        record = self.evidence["files"][-1]
        record["publication_review"] = {
            "source": "Synthetic test fixture", "license": "MIT",
            "reviewed_for_private_content": True, "reviewed_sha256": record["sha256"],
            "text_extraction_path": relative + ".txt", "text_extraction_method": "Synthetic fixture text",
        }
        self.save()
        return record

    def test_reviewed_hash_listed_pdf_is_allowed_in_both_artifact_roots(self):
        self.add_reviewed_pdf()
        self.add_reviewed_pdf("evidence/artifacts/sample.pdf")
        self.assertEqual(validate(self.root)["hashed_files"], 6)

    def test_pdf_requires_review_even_when_all_bytes_are_utf8(self):
        self.write_binary("evidence/artifacts/sample.pdf", b"%PDF-1.4\n%%EOF\n")
        self.assert_invalid("PDF requires recorded review and provenance")

    def test_unlisted_pdf_and_pdf_outside_allowed_roots_are_rejected(self):
        self.write_binary("evidence/artifacts/sample.pdf", self.pdf_fixture(), hashed=False)
        self.assert_invalid("PDF must be a hash-listed")
        (self.root / "evidence/artifacts/sample.pdf").unlink()
        self.add_reviewed_pdf("documents/sample.pdf")
        self.assert_invalid("PDF must be a hash-listed")

    def test_pdf_requires_provenance_review_digest_and_hashed_extraction(self):
        record = self.add_reviewed_pdf()
        review = dict(record["publication_review"])
        for field in review:
            with self.subTest(field=field):
                record["publication_review"] = {key: value for key, value in review.items() if key != field}
                self.save()
                self.assert_invalid("publication_review")
        record["publication_review"] = review
        self.evidence["files"] = [item for item in self.evidence["files"] if item["path"] != review["text_extraction_path"]]
        self.save()
        self.assert_invalid("text_extraction_path must name hash-listed")

    def test_pdf_extraction_hash_and_utf8_are_checked(self):
        record = self.add_reviewed_pdf()
        self.write(record["publication_review"]["text_extraction_path"], "Changed extraction")
        self.assert_invalid("SHA-256 mismatch")
        (self.root / record["publication_review"]["text_extraction_path"]).write_bytes(b"\xff\x00")
        self.assert_invalid("cannot inspect as UTF-8")

    def test_pdf_changed_bytes_need_a_new_review_even_after_rehashing(self):
        record = self.add_reviewed_pdf()
        updated = self.pdf_fixture(text=b"Changed PDF")
        (self.root / record["path"]).write_bytes(updated)
        record.update(sha256=hashlib.sha256(updated).hexdigest(), bytes=len(updated))
        self.save()
        self.assert_invalid("reviewed_sha256 must match PDF bytes")

    def test_pdf_ignored_extraction_text_is_still_scanned(self):
        self.init_git()
        record = self.add_reviewed_pdf()
        extraction = "project/.runtime/extracted.txt"
        self.write_binary(extraction, ("hf" + "_" + "a" * 32).encode())
        record["publication_review"]["text_extraction_path"] = extraction
        self.save()
        self.assert_invalid("extracted.txt: contains possible Hugging Face token")

    def test_pdf_raw_metadata_and_extracted_compressed_text_are_scanned(self):
        secret = ("hf" + "_" + "a" * 32).encode()
        self.add_reviewed_pdf(raw=self.pdf_fixture(extra=b"% " + secret + b"\n"))
        self.assert_invalid("Hugging Face token")
        self.evidence["files"] = self.evidence["files"][:2]
        self.add_reviewed_pdf(raw=self.pdf_fixture(text=secret), text=secret)
        self.assert_invalid("sample.pdf.txt: contains possible Hugging Face token")

    def test_pdf_fake_trailing_encrypted_incremental_and_bad_offset_are_rejected(self):
        valid = self.pdf_fixture()
        for raw in (b"not a PDF", valid + b"trailing", self.pdf_fixture(extra=b"% /Encrypt 5 0 R\n"),
                    self.pdf_fixture(extra=b"% /Prev 1\n"), valid + b"\n%%EOF\n",
                    valid.replace(b"startxref\n", b"startxref\n999999"),
                    valid.replace(b"startxref\n", b"startxref\n" + b"9" * 5000)):
            with self.subTest(size=len(raw)):
                self.evidence["files"] = self.evidence["files"][:2]
                self.add_reviewed_pdf(raw=raw)
                self.assert_invalid("unsupported PDF framing")


if __name__ == "__main__":
    unittest.main()
