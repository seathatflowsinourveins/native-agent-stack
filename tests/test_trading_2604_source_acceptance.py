"""Run the runtime acceptance source heredoc against offline synthetic fixtures.

Only /source path resolution and Git observations are faked. The actual heredoc
uses real files, the repository source-map format and hashlib; no acceptance
shell, installer, runtime imports, network or broker code runs.
"""

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "blueprints/us-equities/runtime-2604"
SOURCE_DIRECTORY = "blueprints/us-equities/adaptive-paper"


class Trading2604SourceAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        acceptance = (BUNDLE / "accept-trading-2604.sh").read_text()
        cls.commit = re.search(
            r"^readonly adapter_commit=([0-9a-f]{40})$", acceptance, re.M
        )[1]
        # The production shell supplies a fixed digest, never an environment override.
        match = re.search(
            r'^check alpaca_adapter_source "\$python" -I - "\$adapter_commit" '
            r'"([0-9a-f]{64})" <<\'PY\'\n(.*?)^PY$',
            acceptance,
            re.M | re.S,
        )
        if match is None:
            raise AssertionError("source acceptance heredoc with a fixed adapter digest is missing")
        cls.source_check = compile(match[2], "accept-trading-2604.sh:alpaca_adapter_source", "exec")

    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        self.source = Path(fixture.name)
        self.directory = self.source / SOURCE_DIRECTORY
        self.directory.mkdir(parents=True)
        for name in ("native_adapter.py", "runner.py", "safety.py"):
            (self.directory / name).write_text(f"# synthetic {name}\n", encoding="utf-8")
        self.adapter_digest = hashlib.sha256(
            (self.directory / "native_adapter.py").read_bytes()
        ).hexdigest()
        self.write_source_map()

    def write_source_map(self):
        hashes = {
            path.relative_to(self.source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.directory.glob("*.py")
        }
        (self.directory / "source-hashes.json").write_text(json.dumps(hashes), encoding="utf-8")

    def run_source_check(self, head=None, status=""):
        def source_path(path):
            self.assertEqual(path, "/source")
            return self.source

        def git_output(argv, *, text):
            self.assertTrue(text)
            self.assertEqual(argv[:3], ["/usr/bin/git", "-C", "/source"])
            if argv[3:] == ["rev-parse", "HEAD"]:
                return (self.commit if head is None else head) + "\n"
            self.assertEqual(argv[3:], ["status", "--porcelain"])
            return status

        with (
            patch("pathlib.Path", side_effect=source_path),
            patch("subprocess.check_output", side_effect=git_output),
            patch.object(sys, "argv", ["-", self.commit, self.adapter_digest]),
        ):
            exec(self.source_check, {})

    def test_every_staged_python_file_passes_with_matching_map(self):
        self.run_source_check()

    def test_tampered_non_adapter_module_is_refused(self):
        (self.directory / "runner.py").write_text("# tampered runner\n", encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "source hash differs: .*runner.py"):
            self.run_source_check()

    def test_unregistered_staged_python_file_is_refused(self):
        (self.directory / "recovery.py").write_text("# unregistered recovery\n", encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "source is not registered: .*recovery.py"):
            self.run_source_check()

    def test_native_adapter_pin_is_required_even_with_a_matching_map(self):
        (self.directory / "native_adapter.py").write_text("# different adapter\n", encoding="utf-8")
        self.write_source_map()
        with self.assertRaisesRegex(AssertionError, "Native adapter source hash differs"):
            self.run_source_check()

    def test_source_commit_must_match_the_pin(self):
        with self.assertRaises(AssertionError):
            self.run_source_check(head="0" * 40)

    def test_dirty_checkout_is_refused_before_source_acceptance(self):
        with self.assertRaisesRegex(AssertionError, "Adapter source has local changes"):
            self.run_source_check(status=f" M {SOURCE_DIRECTORY}/safety.py\n")


if __name__ == "__main__":
    unittest.main()
