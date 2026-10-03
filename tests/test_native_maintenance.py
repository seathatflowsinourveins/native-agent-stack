"""Include bounded recipe regressions in normal CI; never start a model/service."""

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "blueprints/convergence-practice"


def _load(short, path):
    # Registered in sys.modules under a child name of this module before exec_module, as in
    # the importlib docs recipe "Importing a source file directly", so that pickle finds the
    # TestCase classes by module name: a spawned worker (unittest-parallel) that unpickles one
    # imports this module, whose import-time code registers the child, and the import system
    # then returns it from sys.modules (importlib._bootstrap._find_and_load_unlocked).
    name = f"{__name__}.{short}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Loaded at import time, not in load_tests: a spawned worker imports this module but never
# calls load_tests.
MODULES = tuple(_load(name, path) for name, path in (
    ("memory_patch_evidence_tests", ROOT / "mac-memory-patch/test_evidence.py"),
    ("application_portability_tests", ROOT / "application-delivery/test_portability.py"),
    ("wsl_transport_evidence_tests", ROOT / "wsl-transport-recovery/test_transport_evidence.py"),
))


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for module in MODULES:
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
