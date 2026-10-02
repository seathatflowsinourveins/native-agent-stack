"""Local regression oracle for the published Claude SDK Quickstart fixture.

Source: https://code.claude.com/docs/en/agent-sdk/quickstart (2026-10-02).
The fixture is upstream documentation; these four tests are local integration
checks, not the SDK's upstream tests or an agent evaluation harness.
"""

import importlib.util
import os
from pathlib import Path
import unittest


CANDIDATE = Path(
    os.environ.get("NATIVE_SDK_CANDIDATE", str(Path(__file__).with_name("utils.py")))
).resolve(strict=True)
SPEC = importlib.util.spec_from_file_location("sdk_candidate_utils", CANDIDATE)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load candidate: {CANDIDATE}")
UTILS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UTILS)


class QuickstartContract(unittest.TestCase):
    def test_empty_average_does_not_crash(self):
        UTILS.calculate_average([])

    def test_null_user_does_not_crash(self):
        UTILS.get_user_name(None)

    def test_average_preserves_normal_result(self):
        self.assertEqual(UTILS.calculate_average([2, 4, 6]), 4)

    def test_name_preserves_normal_result(self):
        self.assertEqual(UTILS.get_user_name({"name": "Alice"}), "ALICE")
