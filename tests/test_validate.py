"""Regression cases use synthetic receipts, never private execution logs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from scripts.validate import PRIVATE_CONTENT, InvalidPublication, scan_file_for_private_content, validate

ROOT = Path(__file__).resolve().parents[1]
VALIDATE_SCRIPT = ROOT / "scripts/validate.py"


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
        # files[] must be sorted by path on disk (scripts/validate.py now enforces
        # it); sort only the written copy so in-memory index/append/pop-based test
        # fixtures above are unaffected.
        ordered = {**self.evidence, "files": sorted(
            self.evidence["files"], key=lambda entry: entry.get("path", "") if isinstance(entry, dict) else "")}
        self.write_json("manifests/evidence.json", ordered)

    def assert_invalid(self, fragment):
        with self.assertRaisesRegex(InvalidPublication, fragment):
            validate(self.root)

    def test_valid_bundle_reports_counts(self):
        self.assertEqual(validate(self.root), {"components": 1, "profiles": 1, "receipts": 1, "hashed_files": 2})

    def test_registered_exact_vendor_document_uuid_examples_are_public_sources(self):
        folder = "evidence/artifacts/claude-federation-docs-20261010/"
        for name in ("platform.claude.com_wif-providers_github-actions.md",
                     "platform.claude.com_workload-identity-federation.md"):
            with self.subTest(snapshot=name):
                relative = folder + name
                raw = (ROOT / relative).read_bytes()
                self.write(relative, raw.decode())
                self.evidence["files"].append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                                               "bytes": len(raw)})
                self.save()
                try:
                    result = validate(self.root)
                except InvalidPublication as error:
                    self.fail(f"Exact registered public vendor snapshot was refused: {error}")
                self.assertEqual(result["hashed_files"], len(self.evidence["files"]))

    def test_vendor_uuid_exception_requires_exact_content_path_and_registration(self):
        # CPython v3.13.16 Lib/unittest/case.py:538 (subTest) and647-651
        # (run): setUp runs once per test method; subTest does not reset its
        # fixture. Each arm therefore owns a fresh publication directory.
        folder = "evidence/artifacts/claude-federation-docs-20261010/"
        for name in ("platform.claude.com_wif-providers_github-actions.md",
                     "platform.claude.com_workload-identity-federation.md"):
            relative = folder + name
            original = (ROOT / relative).read_bytes()
            for arm in ("changed-and-rehashed", "different-path", "unregistered", "wrong-registration-hash"):
                with self.subTest(snapshot=name, arm=arm), tempfile.TemporaryDirectory() as temporary:
                    # Copy only the untouched base publication. No earlier arm's
                    # vendor/copy file may supply this arm's expected UUID error.
                    fresh = Path(temporary) / "publication"
                    shutil.copytree(self.root, fresh)
                    target = "evidence/artifacts/another-document.md" if arm == "different-path" else relative
                    raw = original + b"\nchanged\n" if arm == "changed-and-rehashed" else original
                    path = fresh / target
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                    registry = fresh / "manifests/evidence.json"
                    evidence = json.loads(registry.read_text())
                    if arm != "unregistered":
                        digest = "0" * 64 if arm == "wrong-registration-hash" else hashlib.sha256(raw).hexdigest()
                        evidence["files"].append({"path": target, "sha256": digest, "bytes": len(raw)})
                        evidence["files"].sort(key=lambda entry: entry["path"])
                    registry.write_text(json.dumps(evidence, indent=2) + "\n")
                    with self.assertRaises(InvalidPublication) as refused:
                        validate(fresh)
                    self.assertIn(f"{target}: contains possible local session identifier", str(refused.exception))

    def test_public_uuid_source_exception_does_not_exempt_other_private_patterns(self):
        from scripts import validate as validator_module
        relative = ("evidence/artifacts/claude-federation-docs-20261010/"
                    "platform.claude.com_wif-providers_github-actions.md")
        # Synthetic text, never a real host path or session identifier.
        cases = [("/" + "home/fixture/file", "personal home path"),
                 ("gh" + "p_" + "x" * 36, "GitHub token")]
        for synthetic, label in cases:
            with self.subTest(pattern=label):
                public_example = "-".join(["0" * 8, "0" * 4, "0" * 4, "0" * 4, "0" * 12])
                content = public_example + "\n" + synthetic + "\n"
                raw = content.encode()
                digest = hashlib.sha256(raw).hexdigest()
                self.write(relative, content)
                self.evidence["files"] = self.evidence["files"][:2]
                self.evidence["files"].append({"path": relative, "sha256": digest, "bytes": len(raw)})
                self.save()
                with patch.dict(validator_module.PUBLIC_VENDOR_UUID_SNAPSHOTS, {relative: digest}):
                    self.assert_invalid(label)

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

    def test_unsorted_files_fail_and_name_the_normalizer(self):
        # The fixture's own build order (receipts/sample.json, then
        # artifacts/output.txt) is not path-sorted; write it directly,
        # bypassing the test harness's own sort-on-write (save()), to
        # exercise the validator's ordering rule.
        self.assertEqual([entry["path"] for entry in self.evidence["files"]],
                          ["evidence/receipts/sample.json", "evidence/artifacts/output.txt"])
        self.write_json("manifests/evidence.json", self.evidence)
        self.assert_invalid(r"files\[1\]: files\[\] must be sorted by path.*"
                             r"scripts/evidence_manifest\.py --write")

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
                                  ("tvly" + "-prod-" + "z" * 40, "Tavily token"),
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

    def test_encoded_home_paths_rejected_without_echoing(self):
        paths = (
            "/tmp/claude-1000/" + "-".join(("", "home", "alice", "code", "proj")) + "/<id>/scratchpad/",
            "~/.claude/projects/" + "-".join(("", "Users", "bob", "src", "app")) + "/",
            "-".join(("C", "", "Users", "carol", "repo")),
            "/tmp/claude-1000/" + "-".join(("", "home", "alice")) + "/<id>/",
            "~/.claude/projects/" + "-".join(("", "Users", "bob")) + "/",
            '"' + "-".join(("C", "", "Users", "carol")) + '"',
            "~/.claude/projects/" + "-".join(("", "mnt", "c", "Users", "carol", "repo")) + "/",
        )
        for index, content in enumerate(paths):
            with self.subTest(form=index):
                self.write("README.md", content)
                with self.assertRaises(InvalidPublication) as error:
                    validate(self.root)
                self.assertIn("encoded home path", str(error.exception))
                self.assertNotIn(content, str(error.exception))

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

    def test_git_ignored_untracked_hash_listed_file_fails_as_uncommittable(self):
        # A hash-listed file that Git ignores and does not track exists only in this
        # checkout: `git add -A` skips it silently, so a clean clone (CI) would miss it
        # while a local validation that only checks the disk still passes.
        self.init_git()
        self.write(".gitignore", "*.jsonl\n")
        name = "evidence/artifacts/events.jsonl"
        self.write_binary(name, b'{"event": "done"}\n')
        self.assert_invalid(f"{name}: hash-listed but ignored by Git and not tracked")
        with self.subTest(route="force-added"):
            self.git("add", "--force", "--", name)
            validate(self.root)
            self.git("rm", "--cached", "--quiet", "--", name)
        with self.subTest(route="narrow .gitignore exception"):
            self.write(".gitignore", "*.jsonl\n!evidence/artifacts/events.jsonl\n")
            validate(self.root)
        with self.subTest(route="missing file reports only the missing file"):
            self.write(".gitignore", "*.jsonl\n")
            (self.root / name).unlink()
            with self.assertRaises(InvalidPublication) as caught:
                validate(self.root)
            self.assertIn("file missing", str(caught.exception))
            self.assertNotIn("ignored by Git", str(caught.exception))

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


class EncodedHomePathTests(unittest.TestCase):
    def test_bare_homes_and_name_characters_match(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        for parts in (("", "home"), ("", "Users"), ("C", "", "Users")):
            for name in ("alice", "john.doe", "john-doe", "user99", "j_doe", "example.person"):
                slug = "-".join((*parts, name))
                for suffix in ("/", "\\", '"', "'", " ", "\t", "\n", "`", ")", "]", ""):
                    with self.subTest(root=parts, name=name, suffix=suffix):
                        self.assertIsNotNone(pattern.search(slug + suffix))

    def test_wsl_profiles_and_name_characters_match(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        for drive in ("c", "C", "d", "Z"):
            for name in ("alice", "john.doe", "john-doe", "user99", "j_doe", "example.person"):
                slug = "-".join(("", "mnt", drive, "Users", name))
                for suffix in ("-repo/", "/", "\\", '"', " ", "]", ""):
                    with self.subTest(drive=drive, name=name, suffix=suffix):
                        self.assertIsNotNone(pattern.search("~/.claude/projects/" + slug + suffix))

    def test_users_branches_ignore_case_and_home_stays_case_sensitive(self):
        # Review thread on #697: Windows (and default macOS) path components are case-insensitive.
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        # Slugs are joined at run time so this file never carries a literal that the rule flags.
        for parts in (("C", "", "USERS", "carol", "repo"), ("c", "", "users", "carol", "repo"),
                      ("C", "", "uSeRs", "carol/"), ("", "users", "bob", "src"), ("", "USERS", "bob/"),
                      ("", "mnt", "c", "USERS", "carol", "repo"), ("", "mnt", "C", "users", "carol/")):
            slug = "-".join(parts)
            with self.subTest(parts=parts):
                self.assertIsNotNone(pattern.search("~/.claude/projects/" + slug))
        for parts in (("", "HOME", "alice", "x"), ("", "Home", "alice/"), ("C", "", "USERS", "example", "repo"),
                      ("", "users", "example/")):
            slug = "-".join(parts)
            with self.subTest(parts=parts):
                self.assertIsNone(pattern.search("~/.claude/projects/" + slug))

    def test_bare_home_and_wsl_placeholders_and_invalid_forms_do_not_match(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        roots = (("", "home"), ("", "Users"), ("C", "", "Users"), ("", "mnt", "c", "Users"))
        for parts in roots:
            for name in ("<user>", "example", ""):
                slug = "-".join((*parts, name))
                for suffix in ("-repo/", "/", "\\", '"', "'", " ", "\t", "\n", "`", ")", "]", ""):
                    with self.subTest(root=parts, name=name, suffix=suffix):
                        self.assertIsNone(pattern.search(slug + suffix))
            for name in ("alice", "john.doe", "user99", "j_doe"):
                slug = "-".join((*parts, name))
                for suffix in (":", "=", "@", ">", "(", "{", ",", ";"):
                    with self.subTest(root=parts, name=name, invalid_suffix=suffix):
                        self.assertIsNone(pattern.search(slug + suffix))
        for drive in ("", "cd", "1", "_"):
            with self.subTest(invalid_drive=drive):
                self.assertIsNone(pattern.search("-".join(("", "mnt", drive, "Users", "alice", "repo"))))

    def test_example_prefix_names_keep_existing_matches(self):
        # Only the complete example placeholder is exempt; punctuation in a
        # real name must not make an existing match disappear.
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        for parts in (("", "home"), ("", "Users"), ("C", "", "Users")):
            for name in ("example.person", "example99", "example_user", "examples"):
                with self.subTest(root=parts, name=name):
                    self.assertIsNotNone(pattern.search("-".join((*parts, name, "repo"))))

    def test_posix_and_windows_forms_match(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        paths = (
            "/tmp/claude-1000/" + "-".join(("", "home", "alice", "code", "proj")) + "/<id>/scratchpad/",
            "~/.claude/projects/" + "-".join(("", "Users", "bob", "src", "app")) + "/",
            "-".join(("C", "", "Users", "carol", "repo")),
        )
        for index, content in enumerate(paths):
            with self.subTest(form=index):
                self.assertIsNotNone(pattern.search(content))

    def test_placeholders_examples_options_and_words_do_not_match(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        for content in (
            "-home-<user>-code", "-home-example-code", "--home-dir", "pre-home-run",
            "C--Users-example-x", "-Users-<user>-src", "-Users-example-src",
            "C--Users-<user>-repo", "-home-", "-Users-", "C--Users-",
        ):
            with self.subTest(content=content):
                self.assertIsNone(pattern.search(content))

    def test_encoded_path_boundary_is_required(self):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        paths = (
            "-".join(("", "home", "alice", "code")),
            "-".join(("", "Users", "bob", "src")),
            "-".join(("C", "", "Users", "carol", "repo")),
            "-".join(("", "home", "alice")),
            "-".join(("", "Users", "bob")),
            "-".join(("C", "", "Users", "carol")),
            "-".join(("", "mnt", "c", "Users", "carol", "repo")),
            "-".join(("", "mnt", "c", "Users", "carol")),
        )
        for index, content in enumerate(paths):
            for prefix in ("a", "Z", "0", "_", "-", "é", "９"):
                with self.subTest(form=index, prefix=prefix):
                    self.assertIsNone(pattern.search(prefix + content))
            for prefix in ("", "/", " ", "`", "("):
                with self.subTest(form=index, prefix=prefix):
                    self.assertIsNotNone(pattern.search(prefix + content))


class DirectCodegraphHomePrivacyProperties(unittest.TestCase):
    """Finite semantic domains for graph identifiers, independent of the regex.

    Every fixture is constructed at runtime from synthetic components so the
    publication validator does not encounter private-looking literals in this
    source. No host username, fixture exclusion or regex-derived generator is
    used. These are exhaustive properties over declared finite domains, using
    the repository's existing unittest runner without a new dependency.
    """

    from string import punctuation as PUNCTUATION

    NAME_CLASSES = (
        ("ascii", "fixtureagent"),
        ("dot", "fixture.agent"),
        ("underscore", "fixture_agent"),
        ("hyphen", "fixture-agent"),
        ("consecutive-hyphens", "fixture--agent"),
        ("trailing-hyphen", "fixtureagent-"),
        ("Lu", "fixtureÅagent"),
        ("Ll", "fixtureéagent"),
        ("Lt", "fixtureǅagent"),
        ("Lm", "fixtureʰagent"),
        ("Lo", "fixture中agent"),
        ("example-dot", "example.person"),
        ("example-underscore", "example_person"),
        ("example-plural", "examples"),
    )
    PLACEHOLDERS = ("<user>", "%u", "example")
    NON_PUNCTUATION_BOUNDARIES = ("", " ", "\t", "\n")
    FILE_SCAN_WRAPPERS = ("", '"', "`")
    property_cases_executed = 0

    @classmethod
    def setUpClass(cls):
        cls.property_cases_executed = 0

    @staticmethod
    def graph_id(name):
        return "-".join(("home", name, "code", "native", "agent", "stack"))

    @staticmethod
    def unicode_letters():
        for point in range(128, 0x110000):
            character = chr(point)
            if character.isalpha():
                yield character

    @classmethod
    def property_case_counts(cls):
        """Export deterministic domain sizes for the parent evidence marker."""
        import unicodedata

        categories = {}
        for character in cls.unicode_letters():
            category = unicodedata.category(character)
            categories[category] = categories.get(category, 0) + 1
        count = sum(categories.values())
        pairs = len(cls.PUNCTUATION) ** 2
        whitespace_pairs = len(cls.NON_PUNCTUATION_BOUNDARIES) ** 2
        counts = {
            "punctuation_pairs_per_name": pairs,
            "representative_name_classes": len(cls.NAME_CLASSES),
            "positive_punctuation": pairs * len(cls.NAME_CLASSES),
            "placeholder_punctuation": pairs * len(cls.PLACEHOLDERS),
            "positive_empty_whitespace": whitespace_pairs * len(cls.NAME_CLASSES),
            "placeholder_empty_whitespace": whitespace_pairs * len(cls.PLACEHOLDERS),
            "unicode_letter_names": count,
            "unicode_letter_left_neighbors": count,
            "ascii_alphanumeric_left_neighbors": 62,
            "scan_file_wrappers": len(cls.NAME_CLASSES) * len(cls.FILE_SCAN_WRAPPERS),
            "unicode_categories": categories,
            "unicode_version": unicodedata.unidata_version,
        }
        counts["property_cases"] = sum(counts[key] for key in (
            "positive_punctuation", "placeholder_punctuation", "positive_empty_whitespace",
            "placeholder_empty_whitespace", "unicode_letter_names",
            "unicode_letter_left_neighbors", "ascii_alphanumeric_left_neighbors",
            "scan_file_wrappers"))
        return counts

    def assert_semantic_domain(self, candidates, expected_private):
        pattern = dict(PRIVATE_CONTENT)["encoded home path"]
        checked = mismatches = 0
        for candidate in candidates:
            checked += 1
            mismatches += (pattern.search(candidate) is not None) != expected_private
        type(self).property_cases_executed += checked
        self.assertGreater(checked, 0, "property domain must be exercised")
        self.assertEqual(mismatches, 0, f"{mismatches} mismatches across {checked} semantic cases")

    @classmethod
    def wrapped_ids(cls, names, boundaries):
        for name in names:
            identifier = cls.graph_id(name)
            for left in boundaries:
                for right in boundaries:
                    yield left + identifier + right

    def test_every_punctuation_pair_preserves_private_name_classification(self):
        self.assertEqual(len(self.PUNCTUATION), 32)
        self.assert_semantic_domain(self.wrapped_ids(
            (name for _, name in self.NAME_CLASSES), self.PUNCTUATION), True)

    def test_every_punctuation_pair_preserves_placeholder_classification(self):
        self.assert_semantic_domain(self.wrapped_ids(self.PLACEHOLDERS, self.PUNCTUATION), False)

    def test_empty_and_whitespace_boundaries_preserve_private_classification(self):
        self.assert_semantic_domain(self.wrapped_ids(
            (name for _, name in self.NAME_CLASSES), self.NON_PUNCTUATION_BOUNDARIES), True)

    def test_empty_and_whitespace_boundaries_preserve_placeholder_classification(self):
        self.assert_semantic_domain(self.wrapped_ids(
            self.PLACEHOLDERS, self.NON_PUNCTUATION_BOUNDARIES), False)

    def test_all_non_ascii_unicode_letters_are_private_name_characters(self):
        self.assert_semantic_domain(
            ('"' + self.graph_id("fixture" + letter + "agent") + '"'
             for letter in self.unicode_letters()), True)

    def test_unicode_letter_left_neighbors_do_not_create_a_graph_boundary(self):
        identifier = self.graph_id("fixtureagent")
        self.assert_semantic_domain((letter + identifier for letter in self.unicode_letters()), False)

    def test_ascii_alphanumeric_left_neighbors_do_not_create_a_graph_boundary(self):
        from string import ascii_letters, digits

        identifier = self.graph_id("fixtureagent")
        self.assert_semantic_domain((letter + identifier for letter in ascii_letters + digits), False)

    def test_direct_file_scan_flags_bare_quotes_and_backticks_without_echoing_identifier(self):
        mismatches = 0
        with tempfile.TemporaryDirectory(prefix="codegraph-privacy-") as directory:
            target = Path(directory) / "synthetic.txt"
            for _, name in self.NAME_CLASSES:
                identifier = self.graph_id(name)
                for wrapper in self.FILE_SCAN_WRAPPERS:
                    target.write_text(wrapper + identifier + wrapper, encoding="utf-8")
                    findings = scan_file_for_private_content(target)
                    type(self).property_cases_executed += 1
                    mismatches += not any("encoded home path" in finding for finding in findings)
                    mismatches += any(identifier in finding for finding in findings)
        self.assertEqual(mismatches, 0, f"{mismatches} scan classification/redaction mismatches")


class ScanFileForPrivateContentTests(unittest.TestCase):
    """`scan_publication()` only walks git-tracked/listed paths; a generated,
    gitignored artifact built fresh right before publication (e.g.
    `docs/ecosystem/index.html` in `publish-catalog.yml`) needs its own
    direct scan. Covers `scan_file_for_private_content()` and the
    `--scan-file` CLI mode that wraps it."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_clean_file_reports_no_findings(self):
        path = self.write("explorer.html", "<html><body>hello</body></html>")
        self.assertEqual(scan_file_for_private_content(path), [])

    def test_personal_home_path_is_reported(self):
        # Built from parts (as the existing PRIVATE_CONTENT tests above do) so
        # this test's own source text, once committed, is not itself a
        # contiguous match for the pattern under test.
        path = self.write("explorer.html", "<html>/" + "home" + "/private-person/project</html>")
        findings = scan_file_for_private_content(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("personal home path", findings[0])

    def test_github_token_is_reported(self):
        token = "gh" + "p_" + "a" * 36
        path = self.write("explorer.html", f"<html>{token}</html>")
        findings = scan_file_for_private_content(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("GitHub token", findings[0])

    def test_missing_file_is_reported_not_raised(self):
        findings = scan_file_for_private_content(self.root / "missing.html")
        self.assertEqual(len(findings), 1)
        self.assertIn("cannot read file", findings[0])

    def test_non_utf8_bytes_are_still_scanned_as_latin1(self):
        secret = ("hf" + "_" + "a" * 32).encode()
        path = self.root / "explorer.html"
        # 0xFF is an invalid UTF-8 start byte (forces the latin-1 fallback);
        # 0x00 keeps a non-word byte before "hf_" so \b still matches under
        # latin-1 decoding (some high latin-1 bytes are themselves letters).
        path.write_bytes(b"\xff\x00" + secret)
        findings = scan_file_for_private_content(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("Hugging Face token", findings[0])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), *args],
            capture_output=True, text=True, check=False, cwd=str(ROOT),
            env={"PATH": os.environ.get("PATH", os.defpath),
                 "NATIVE_AGENT_HOST_NAMES_JSON": json.dumps(["fixture_" + "host_marker"])},
            timeout=150,
        )

    def test_cli_scan_file_passes_on_a_clean_file(self):
        path = self.write("explorer.html", "<html>nothing sensitive here</html>")
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report, {"status": "passed", "source": "synthetic",
                                  "scanned_files": 1, "matching_locations": 0})
        self.assertIn("synthetic sources", result.stderr)

    def test_cli_scan_file_fails_on_an_encoded_home_path_without_echoing_it(self):
        content = "-".join(("C", "", "Users", "carol", "repo"))
        path = self.write("explorer.html", f"<html>{content}</html>")
        findings = scan_file_for_private_content(path)
        self.assertEqual(findings, [f"{path}: contains possible encoded home path"])
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[0])["matching_locations"], 1)
        self.assertIn("explorer.html:1", result.stdout)
        self.assertNotIn(content, result.stdout + result.stderr)

    def test_cli_scan_file_fails_on_a_planted_secret_without_echoing_it(self):
        secret = ("sk-ant-" + "b" * 30)
        path = self.write("explorer.html", f"<html>{secret}</html>")
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[0])["matching_locations"], 1)
        self.assertIn("explorer.html:1", result.stdout)
        self.assertNotIn(secret, result.stdout)

    def test_cli_scan_file_does_not_require_git_tracking_or_root(self):
        # The whole point: an untracked/gitignored file outside any --root
        # publication enumeration must still be scannable directly.
        path = self.write("untracked-explorer.html", "<html>clean</html>")
        self.assertFalse((self.root / ".git").exists())
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_scan_file_supports_multiple_files(self):
        clean = self.write("a.html", "<html>clean</html>")
        secret = ("sk-ant-" + "c" * 30)
        dirty = self.write("b.html", f"<html>{secret}</html>")
        result = self.run_cli("--scan-file", str(clean), "--scan-file", str(dirty))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_cli_scan_file_refuses_a_bare_name_with_only_a_safe_locator(self):
        name = "fixture_" + "host_marker"
        path = self.write("explorer.html", "clean\n[" + name + "]\n")
        result = self.run_cli("--scan-file", str(path), "--scan-file", str(path))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ['{"matching_locations": 1, "scanned_files": 1, "source": "synthetic", "status": "failed"}',
                          "explorer.html:2"])
        self.assertNotIn(name, result.stdout + result.stderr)

    def test_cli_scan_file_refuses_an_unavailable_scanner_without_a_traceback(self):
        path = self.write("explorer.html", "clean\n")
        with patch.dict(os.environ, {"PATH": ""}):
            result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "error", "source": "synthetic", "scanned_files": 1})
        self.assertEqual(result.stderr,
                         "Host-name scan uses synthetic sources; this is not real-host acceptance.\n")

    def test_cli_scan_file_refuses_a_missing_input_without_its_absolute_path(self):
        path = self.root / "missing.html"
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "error", "source": "synthetic", "scanned_files": 1})
        self.assertNotIn(str(path), result.stdout + result.stderr)

    def test_cli_private_content_locator_uses_the_actual_original_line(self):
        content = "-".join(("C", "", "Users", "carol", "repo"))
        path = self.write("explorer.html", "clean\n<html>" + content + "</html>\n")
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ['{"matching_locations": 1, "scanned_files": 1, "source": "synthetic", "status": "failed"}',
                          "explorer.html:2"])
        self.assertNotIn(content, result.stdout + result.stderr)

    def test_cli_labels_repeated_matches_as_one_distinct_location(self):
        name = "fixture_" + "host_marker"
        path = self.write("explorer.html", name + "|" + name)
        result = self.run_cli("--scan-file", str(path))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout.splitlines()[0])
        self.assertEqual(report["matching_locations"], 1)
        self.assertNotIn("findings", report)
        self.assertEqual(report["source"], "synthetic")
        self.assertNotIn(name, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
