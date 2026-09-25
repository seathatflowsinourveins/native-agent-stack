"""Check rejection paths that would otherwise allow misleading native receipts."""

import hashlib
from contextlib import ExitStack, redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_token_ci.py"
SPEC = importlib.util.spec_from_file_location("native_token_ci", SCRIPT)
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class NativeTokenCIContracts(unittest.TestCase):
    def test_unexpected_exception_and_interrupt_cannot_publish_passing_receipt(self):
        for failure in (TypeError("unexpected fixture shape"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "results"
                with ExitStack() as stack:
                    stack.enter_context(patch.object(sys, "argv", [str(SCRIPT), "--output", str(output)]))
                    stack.enter_context(patch.object(ci.shutil, "which", side_effect=lambda name: f"/stub/{name}"))
                    stack.enter_context(patch.object(ci.Run, "command", side_effect=lambda label, *_args, **_kw: ci.PINS[label.removeprefix("version-")]))
                    stack.enter_context(patch.object(ci, "rtk_fixture", side_effect=failure))
                    for name in ("qmd_fixture", "repomix_fixture", "toon_fixture"):
                        stack.enter_context(patch.object(ci, name))
                    stack.enter_context(redirect_stdout(io.StringIO()))
                    if isinstance(failure, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            ci.main()
                    else:
                        self.assertEqual(ci.main(), 1)
                result = json.loads((output / "receipt.json").read_text())
                self.assertEqual(result["status"], "failed")
                self.assertTrue(result["failures"])
                self.assertTrue(result["cleanup"]["owned_temporary_directory_absent"])

    def test_archive_requires_exact_asset_checksum_and_safe_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.tar.gz"
            for member_name in ("rtk", "../outside"):
                with tarfile.open(archive, "w:gz") as out:
                    member = tarfile.TarInfo(member_name)
                    member.size = 4
                    out.addfile(member, io.BytesIO(b"test"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                checksums = f"{digest}  {archive.name}\n"
                if member_name == "rtk":
                    ci.verify_archive(archive, checksums)
                    with self.assertRaisesRegex(AssertionError, "exact asset"):
                        ci.verify_archive(archive, f"{digest}  other.tar.gz\n")
                    with self.assertRaisesRegex(AssertionError, "checksum mismatch"):
                        ci.verify_archive(archive, f"{'0' * 64}  {archive.name}\n")
                else:
                    with self.assertRaisesRegex(AssertionError, "Unsafe archive"):
                        ci.verify_archive(archive, checksums)

    def test_pack_rejects_changed_or_extra_source(self):
        original = {"a.py": "def greeting():\n    return 19\n"}
        valid = '<files><file path="a.py">\ndef greeting():\n    return 19\n</file></files>'
        ci.verify_pack(valid, original)
        with self.assertRaisesRegex(AssertionError, "source differs"):
            ci.verify_pack(valid.replace("return 19", "return 20"), original)
        with self.assertRaisesRegex(AssertionError, "extra files"):
            ci.verify_pack(valid.replace("</files>", '<file path="secret.txt">extra</file></files>'), original)

    def test_qmd_rejects_truncated_wrong_or_extra_document_content(self):
        uri, body = "qmd://native-ci-docs/note.md", "# Public\nExact fact: 19.\n"
        valid = f"{uri}  #abcdef\n---\n\n{body}\n"
        ci.verify_qmd_document(valid, uri + "?index=native-ci-docs", "#abcdef", body)
        for response in (valid.replace(body, "# Public"),
                         valid.replace(uri, "qmd://other/note.md"),
                         valid + "extra content\n"):
            with self.assertRaises(AssertionError):
                ci.verify_qmd_document(response, uri, "#abcdef", body)

    def test_roundtrip_preserves_boolean_and_integer_types(self):
        ci.verify_json_roundtrip('{"a":true,"b":19}', '{"b":19,"a":true}')
        with self.assertRaisesRegex(AssertionError, "values/types differ"):
            ci.verify_json_roundtrip('{"a":true}', '{"a":1}')

    def test_timeout_retains_exit_and_scoped_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "private-test-value",
                                         "INDEX_PATH": "/unrelated/index.sqlite"}):
                run = ci.Run(output, work)
            self.assertNotIn("OPENAI_API_KEY", run.env)
            self.assertTrue(run.env["INDEX_PATH"].startswith(str(work)))
            self.assertEqual(run.env["HOME"], os.environ.get("HOME"))
            with self.assertRaisesRegex(AssertionError, "timed out"):
                run.command("timeout-fixture", [sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.05)
            result = json.loads((output / "receipt.json").read_text())
            self.assertTrue(result["commands"][0]["timed_out"])
            self.assertNotEqual(result["commands"][0]["exit_code"], 0)
            self.assertNotIn(str(work), json.dumps(result))
            self.assertNotIn("private-test-value", json.dumps(result))

    def test_timeout_signal_refused_by_an_exited_group_is_still_a_timeout(self):
        # The command can finish between the timeout and the signal; macOS then answers killpg with EPERM.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            run = ci.Run(output, work)
            refusal = PermissionError(errno.EPERM, "Operation not permitted")
            with patch.object(ci.os, "killpg", side_effect=refusal) as killpg, \
                    self.assertRaisesRegex(AssertionError, "timed out"):
                run.command("exited-group", [sys.executable, "-c", "import time; time.sleep(0.3)"], timeout=0.05)
            self.assertEqual([call.args[1] for call in killpg.call_args_list], [signal.SIGTERM])
            self.assertTrue(json.loads((output / "receipt.json").read_text())["commands"][0]["timed_out"])


if __name__ == "__main__":
    unittest.main()
