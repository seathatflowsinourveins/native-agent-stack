"""study/runtime.lock: the pinned runtime, its requirements file and the version refusal."""
import json
import unittest
from pathlib import Path

from core import guards

STUDY = Path(__file__).resolve().parents[1]
LOCK = json.loads((STUDY / "runtime.lock").read_text())


class Runtime(unittest.TestCase):
    def test_lock_and_requirements_agree(self):
        reqs = {}
        for line in (STUDY / LOCK["requirements_file"]).read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                name, ver = line.split("==")
                reqs[name.replace("-", "_").lower()] = ver
        lock = {k.replace("-", "_").lower(): v for k, v in LOCK["packages"].items()}
        self.assertEqual(reqs, lock)

    def test_tests_run_under_the_pinned_runtime(self):
        guards.check_runtime(LOCK)

    def test_a_different_version_is_refused(self):
        v = guards.runtime_versions()
        v["duckdb"] = "0.0.1"
        with self.assertRaises(guards.Refused):
            guards.check_runtime(LOCK, v)
        v = guards.runtime_versions()
        v["python"] = "3.12.3"
        with self.assertRaises(guards.Refused):
            guards.check_runtime(LOCK, v)

    def test_protocol_names_the_lock_and_test_command(self):
        proto = json.loads((STUDY.parent / "protocol-core-draft.json").read_text())
        sc = proto["run_discipline"]["study_code"]
        self.assertEqual(sc["runtime_lock"], "blueprints/us-equities/mover-v3/study/runtime.lock")
        self.assertEqual(sc["test_command"], LOCK["test_command"])
        self.assertIsNone(sc["tree"])
        self.assertEqual(proto["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(proto["frozen_before_outcomes"], False)


if __name__ == "__main__":
    unittest.main()
