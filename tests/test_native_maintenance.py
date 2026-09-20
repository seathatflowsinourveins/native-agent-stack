"""Include bounded recipe regressions in normal CI; never start a model/service."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "blueprints/convergence-practice"


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, path in (
        ("memory_patch_evidence_tests", ROOT / "mac-memory-patch/test_evidence.py"),
        ("application_portability_tests", ROOT / "application-delivery/test_portability.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
