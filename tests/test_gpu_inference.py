"""Offline resource/patch guards; never load a model or contact a server."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "blueprints/convergence-practice/gpu-inference"
SPEC = importlib.util.spec_from_file_location("gpu_qualification", LANE / "qualify.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GPUInferenceGuards(unittest.TestCase):
    def test_frozen_prompt_and_original_oracle(self):
        plan = json.loads((LANE / "plan.json").read_text())
        MODULE.check_plan(plan)
        self.assertEqual(MODULE.digest(LANE / "prompt.txt"), plan["prompt_sha256"])
        for name, expected in plan["fixture_sha256"].items():
            self.assertEqual(MODULE.digest(LANE.parent / "native-worker/seed" / name), expected)

    def test_acceptance_preserves_original_trial_and_reviewed_source_identity(self):
        receipt = json.loads((LANE / "receipt.json").read_text())
        for name, expected in receipt["evidence"].items():
            self.assertEqual(MODULE.digest(LANE / name), expected)
        trial = json.loads((LANE / "trial.json").read_text())
        review = json.loads((LANE / "independent-review.json").read_text())
        self.assertEqual(trial["status"], "generated-awaiting-review")
        self.assertEqual(trial["candidate_sha256"], review["candidate_sha256"])
        self.assertEqual(review["candidate_sha256"], MODULE.digest(LANE / "accepted/planner.py"))
        self.assertIsNone(receipt["offload_evidence"]["observed_exact_layer_count"])
        self.assertFalse(receipt["savings_claim"])

    def test_profile_cannot_silently_exceed_partial_offload_budget(self):
        original = json.loads((LANE / "plan.json").read_text())
        for key, bad in [("gpu_layers", 65), ("minimum_free_mib", 1024),
                         ("parallel", 2), ("context", 262144), ("threads", True)]:
            with self.subTest(key=key):
                plan = copy.deepcopy(original)
                plan["profile"][key] = bad
                with self.assertRaises(ValueError):
                    MODULE.check_plan(plan)

    def test_generated_source_cannot_smuggle_external_or_top_level_execution(self):
        samples = ["import os\ndef order_tasks(d): return os.listdir()\n",
                   "def order_tasks(d): return __import__('os').listdir()\n",
                   "print('executed')\ndef order_tasks(d): return []\n",
                   "def order_tasks(d=open('secret')): return []\n",
                   "@print('decorator')\ndef order_tasks(d): return []\n",
                   "def order_tasks(d): return d.__class__.__mro__\n"]
        for source in samples:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    MODULE.candidate_source(json.dumps({"planner_py": source}))

    def test_extra_fields_or_non_source_payload_is_rejected(self):
        for value in [{"planner_py": "def order_tasks(d): return []", "run": "command"},
                      {"planner_py": None}, ["not a patch"]]:
            with self.assertRaises(ValueError):
                MODULE.candidate_source(json.dumps(value))

    def test_legitimate_patch_is_only_returned_as_text(self):
        source = '"""Planner."""\nimport heapq\ndef order_tasks(d):\n    return sorted(d)\n'
        self.assertEqual(MODULE.candidate_source(json.dumps({"planner_py": source})), source)
        # Passing these static checks intentionally does not certify semantic quality.

    def test_cleanup_tolerates_concurrent_process_exit(self):
        process = Mock(pid=123, returncode=0)
        process.poll.return_value = None
        with patch.object(MODULE.os, "killpg", side_effect=ProcessLookupError):
            self.assertEqual(MODULE.terminate_owned(process), [])
        process.wait.assert_called_once_with(timeout=5)

    def test_failed_final_telemetry_preserves_original_failure_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            lane = Path(temp)
            with patch.object(MODULE, "gpu_memory", side_effect=OSError("probe failed")):
                result = MODULE.run(lane, LANE / "plan.json", LANE / "prompt.txt", 18085)
            saved = json.loads((lane / "trial.json").read_text())
            self.assertEqual(saved, result)
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(saved["failure_type"], "FileNotFoundError")
            self.assertIsNone(saved["memory_after"])
            self.assertEqual(saved["telemetry_after_error"], "OSError")


if __name__ == "__main__":
    unittest.main()
