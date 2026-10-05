"""Reject recursive checkout-copy destinations before test-package scratch is created."""

import os
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

if __package__:
    from .repository_copy import guarded_copytree
else:
    from repository_copy import guarded_copytree


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "tests/__init__.py"
PROBE = """
import runpy
import sys
import tempfile
from unittest.mock import patch

with patch.object(tempfile, "gettempdir", return_value=sys.argv[1]):
    if sys.argv[3] == "block":
        with patch.object(tempfile, "mkdtemp", side_effect=AssertionError("scratch creation reached")):
            runpy.run_path(sys.argv[2])
    else:
        runpy.run_path(sys.argv[2])
"""


class TempdirGuardTests(unittest.TestCase):
    def probe(self, tempdir, *, block_creation=True, environment=None):
        # Mock the effective (possibly cached) gettempdir() in a fresh process. No
        # scratch is actually created inside the checkout, even with the guard absent.
        return subprocess.run(
            [sys.executable, "-c", PROBE, str(tempdir), str(SETUP),
             "block" if block_creation else "allow"],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
        )

    def assert_rejected(self, tempdir):
        result = self.probe(tempdir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsafe test temporary directory", result.stderr)
        self.assertIn("TMPDIR must live", result.stderr)
        self.assertIn("outside the repository root", result.stderr)
        self.assertNotIn("scratch creation reached", result.stderr)

    def test_rejects_repository_root_and_descendants_before_creating_scratch(self):
        for path in (ROOT, ROOT / "tests", ROOT / "tests/../tests"):
            with self.subTest(path=path):
                self.assert_rejected(path)

    def test_rejects_an_external_symlink_into_the_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            link = Path(temporary) / "checkout-temp"
            link.symlink_to(ROOT / "tests", target_is_directory=True)
            self.assert_rejected(link)

    def test_accepts_an_external_tempdir_on_a_ci_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner_temp = Path(temporary) / "runner-temp"
            runner_temp.mkdir()
            environment = {**os.environ, "CI": "true", "RUNNER_TEMP": str(runner_temp)}
            result = self.probe(runner_temp, block_creation=False, environment=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(runner_temp.iterdir()), [])  # atexit cleaned the Git scratch

    def test_a_sibling_with_the_repository_name_prefix_is_allowed(self):
        sibling = ROOT.with_name(ROOT.name + "-temp")
        result = self.probe(sibling)
        # Reaching mkdtemp proves the guard allowed the sibling. The sentinel keeps
        # this test from creating a directory outside the builder's owned roots.
        self.assertIn("scratch creation reached", result.stderr)
        self.assertNotIn("Unsafe test temporary directory", result.stderr)


class RepositoryCopyCallSiteTests(unittest.TestCase):
    def test_top_level_discovery_copy_sites_reject_an_internal_destination(self):
        # Import the real module as discovery with -s tests does, without importing
        # tests/__init__.py. The copy sentinel prevents recursion in the red control.
        probe = """
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tests"))
module = importlib.import_module("test_catalog_freshness_propose")
assert "tests" not in sys.modules, "package guard unexpectedly ran"
for name in ("RebuildExplorerSubprocessTests", "TrackedExplorerSubprocessTests"):
    with patch.object(module.tempfile, "mkdtemp", return_value=str(root / "tests")), \
         patch.object(module.shutil, "copytree", side_effect=AssertionError("unguarded copy reached")) as copy:
        try:
            getattr(module, name).setUpClass()
        except ValueError as exc:
            assert "inside the source tree" in str(exc), str(exc)
        else:
            raise AssertionError("internal destination accepted")
        copy.assert_not_called()
print("both top-level copy sites refused before copying")
"""
        result = subprocess.run([sys.executable, "-c", probe, str(ROOT)], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("both top-level copy sites refused", result.stdout)

    def test_direct_root_copies_all_use_the_shared_guard(self):
        unguarded = []
        for path in (ROOT / "tests").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "copytree" and node.args
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id in {"ROOT", "REPO_ROOT", "REPOSITORY_ROOT"}):
                    unguarded.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        # tests/test_wsl_retrieval.py is a frozen evaluation input of the convergence record
        # blueprints/convergence-practice/wsl-retrieval/experiment.json (frozen_inputs.evaluation[2]); its ROOT is the WSL
        # retrieval fixture subtree, not the checkout, so its copies stay as frozen and are a recorded residual
        # (docs/decisions/2026-10-05-disk-headroom-enospc.md). Any other file must use the shared guard.
        exempt = {"tests/test_wsl_retrieval.py"}
        self.assertTrue(any(entry.split(":")[0] in exempt for entry in unguarded) or not exempt,
                        "a stale exemption: the frozen file no longer copies its subtree")
        remaining = [entry for entry in unguarded if entry.split(":")[0] not in exempt]
        self.assertEqual(remaining, [], "Unprotected root-tree copies: " + ", ".join(remaining))


class RepositoryCopyGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "keep").write_text("preserved\n")

    def test_rejects_source_itself_and_normalized_descendants_before_copying(self):
        for destination in (self.source, self.source / "scratch", self.source / "child/../scratch"):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(ValueError, "inside the source tree"):
                    guarded_copytree(self.source, destination, dirs_exist_ok=True)
                self.assertEqual(list(self.source.iterdir()), [self.source / "keep"])

    def test_rejects_an_external_symlink_destination_into_the_source(self):
        link = self.root / "outside-link"
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "inside the source tree"):
            guarded_copytree(self.source, link / "scratch")
        self.assertFalse((self.source / "scratch").exists())

    def test_safe_sibling_copy_preserves_native_copytree_options(self):
        (self.source / "ignore-me").write_text("ignored\n")
        destination = self.root / "source-scratch"
        destination.mkdir()
        import shutil
        result = guarded_copytree(self.source, destination, dirs_exist_ok=True,
                                  ignore=shutil.ignore_patterns("ignore-me"))
        self.assertEqual(result, destination.resolve())
        self.assertEqual((destination / "keep").read_text(), "preserved\n")
        self.assertFalse((destination / "ignore-me").exists())


if __name__ == "__main__":
    unittest.main()
