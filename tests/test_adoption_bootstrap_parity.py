"""Lock the shared bootstrap helpers to the macOS reference implementation."""

import unittest

from tests.test_adoption_bootstrap import ROOT, SCRIPT_PATH, shell_functions


class BootstrapParityTests(unittest.TestCase):
    def test_common_helpers_are_byte_identical(self):
        linux = SCRIPT_PATH.read_text()
        macos = (ROOT / "adoption/bootstrap-macos.sh").read_text()
        for name in ("verify_sha256", "fetch", "canonical_path", "prune_old_version", "npm_package_name"):
            with self.subTest(function=name):
                self.assertEqual(shell_functions(linux, name), shell_functions(macos, name))

    def test_install_npm_is_identical_apart_from_comment_lines(self):
        def executable_lines(text):
            return "".join(line for line in shell_functions(text, "install_npm").splitlines(keepends=True)
                           if not line.lstrip().startswith("#"))

        self.assertEqual(executable_lines(SCRIPT_PATH.read_text()),
                         executable_lines((ROOT / "adoption/bootstrap-macos.sh").read_text()))
