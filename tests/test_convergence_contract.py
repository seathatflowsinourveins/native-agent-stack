"""Synthetic evidence tests; never start a native client or execute record commands."""

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from scripts.validate_convergence import CONTRACT, REPO, validate_record


class ConvergenceContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifact = self.write("fixture.txt", b"abc")
        reference = (CONTRACT / "contract-reference.md").read_text(encoding="utf-8")
        self.record = json.loads(re.search(r"```json\n(.*?)\n```", reference, re.S).group(1))

    def write(self, path, raw):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}

    def result(self):
        self.write("record.json", json.dumps(self.record).encode())
        return validate_record(self.root, "record.json")

    def assert_invalid(self, fragment):
        result = self.result()
        self.assertFalse(result["valid"], result)
        self.assertIn(fragment, "\n".join(result["errors"]))

    def run_record(self, identifier="candidate-1", condition="candidate"):
        return {
            "id": identifier, "task": "patch-a", "role": "worker", "condition": condition,
            "attempt": 1, "command_index": 0, "evidence_class": "offline_artifact_check",
            "scope": "fixture only", "status": "passed", "exit_code": 0,
            "quality": {"semantic": True, "contract": True}, "artifacts": [copy.deepcopy(self.artifact)],
            "usage": {key: None for key in ("uncached_input", "cache_creation", "cache_read", "output", "reasoning_in_output", "total", "native_retries")},
        }

    def observed(self):
        self.record["status"] = "observed"
        self.record["observations"] = [self.run_record()]

    def savings(self):
        self.observed()
        self.record["observations"].insert(0, self.run_record("baseline-1", "baseline"))
        for index, run in enumerate(self.record["observations"]):
            run["usage"] = {"uncached_input": 50 if index == 0 else 10, "cache_creation": 5,
                            "cache_read": 20, "output": 10, "reasoning_in_output": 4,
                            "total": 85 if index == 0 else 45, "native_retries": 0}
        self.coverage()

    def coverage(self):
        identifiers = [run["id"] for run in self.record["observations"]]
        artifact = self.write("coverage.json", json.dumps({"run_ids": identifiers, "complete": True}).encode())
        self.record["usage_assessment"] = {"claim": "whole_task_token_savings", "coverage": "complete",
                                           "expected_run_ids": identifiers, "coverage_artifact": artifact}

    def test_documented_minimal_plan_is_valid_and_not_executed(self):
        self.record["commands"] = ["this command must never execute"]
        self.assertEqual(self.result(), {"valid": True, "errors": [], "observations": 0})

    def test_all_protocol_evidence_fields_are_required(self):
        original = copy.deepcopy(self.record)
        protocol = json.loads((CONTRACT / "protocol.json").read_text())
        for field in protocol["required_experiment_fields"]:
            with self.subTest(field=field):
                self.record = copy.deepcopy(original)
                del self.record[field]
                self.assert_invalid("missing required fields")

    def test_unknown_fields_do_not_echo_values_or_keys(self):
        self.record["DO_NOT_ECHO_SECRET_KEY"] = "DO_NOT_ECHO_SECRET_VALUE"
        result = self.result()
        self.assertFalse(result["valid"])
        self.assertNotIn("DO_NOT_ECHO", json.dumps(result))

    def test_boolean_counts_and_invalid_pins_rejected(self):
        self.observed()
        for field in ("attempt", "command_index", "exit_code"):
            with self.subTest(field=field):
                original = self.record["observations"][0][field]
                self.record["observations"][0][field] = True
                self.assert_invalid("invalid type")
                self.record["observations"][0][field] = original
        self.record["frozen_inputs"]["base_revision"] = "main"
        self.assert_invalid("invalid text format")

    def test_artifact_bytes_must_match_actual_hash(self):
        (self.root / "fixture.txt").write_bytes(b"abd")
        self.assert_invalid("SHA-256 mismatch")

    def test_artifact_path_boundaries(self):
        for path in ("/tmp/fixture.txt", "../fixture.txt", "a/../fixture.txt", "./fixture.txt",
                     "a//fixture.txt", "C:\\fixture.txt", ".git/config", "missing.txt"):
            with self.subTest(path=path):
                self.record["frozen_inputs"]["sources"][0]["path"] = path
                self.assert_invalid("canonical" if path != "missing.txt" else "file missing")

    def test_symlink_file_and_parent_refused_even_inside_root(self):
        (self.root / "linked.txt").symlink_to(self.root / "fixture.txt")
        (self.root / "linked-dir").symlink_to(self.root, target_is_directory=True)
        for path in ("linked.txt", "linked-dir/fixture.txt"):
            with self.subTest(path=path):
                self.record["frozen_inputs"]["sources"][0]["path"] = path
                self.assert_invalid("symlinks are forbidden")

    def test_record_path_itself_is_confined(self):
        self.result()
        for path in ("../record.json", str(self.root / "record.json")):
            self.assertFalse(validate_record(self.root, path)["valid"])
        (self.root / "alias.json").symlink_to(self.root / "record.json")
        self.assertIn("symlinks", " ".join(validate_record(self.root, "alias.json")["errors"]))

    def test_duplicate_json_and_malformed_shapes_fail_cleanly(self):
        for raw in (b'{"schema_version":1,"schema_version":1}', b'[]', b'{"observations":false}', b'NaN'):
            with self.subTest(raw=raw):
                self.write("record.json", raw)
                self.assertFalse(validate_record(self.root, "record.json")["valid"])

    def test_plans_cannot_contain_executed_or_adopted_claims(self):
        self.record["observations"] = [self.run_record()]
        self.assert_invalid("planned record")
        self.record["observations"] = []
        self.record["decision_and_scope"]["decision"] = "adopt_within_scope"
        self.assert_invalid("observed scoped qualification required")

    def test_observed_record_requires_actual_runs(self):
        self.record["status"] = "observed"
        self.assert_invalid("at least one run required")

    def test_scoped_execution_can_qualify_without_known_usage(self):
        self.observed()
        self.record["decision_and_scope"].update(decision="adopt_within_scope", qualification_run_ids=["candidate-1"])
        self.assertTrue(self.result()["valid"])
        self.assertTrue(all(value is None for value in self.record["observations"][0]["usage"].values()))

    def test_scope_baseline_discovery_or_unknown_quality_cannot_qualify(self):
        self.observed()
        self.record["decision_and_scope"].update(decision="adopt_within_scope", qualification_run_ids=["candidate-1"])
        original = copy.deepcopy(self.record["observations"][0])
        changes = ({"scope": "different host"}, {"condition": "baseline"},
                   {"evidence_class": "discovery"}, {"evidence_class": "pinned_source_review"},
                   {"quality": {"semantic": None, "contract": True}})
        for change in changes:
            with self.subTest(change=change):
                self.record["observations"][0] = original | change
                self.assert_invalid("successful candidate execution in exact scope required")

    def test_later_failed_or_skipped_candidate_invalidates_earlier_qualification(self):
        self.observed()
        self.record["decision_and_scope"].update(decision="adopt_within_scope", qualification_run_ids=["candidate-1"])
        later = self.run_record("candidate-2")
        later.update(attempt=2, status="failed", exit_code=1, quality={"semantic": False, "contract": False})
        self.record["observations"].append(later)
        self.record["failures_and_skips"] = [{"run_id": "candidate-2", "reason": "Later attempt failed."}]
        self.assert_invalid("latest candidate attempt in task/role/scope required")
        later.update(status="skipped", exit_code=None, quality={"semantic": None, "contract": None})
        self.record["failures_and_skips"][0]["reason"] = "Later attempt skipped."
        self.assert_invalid("latest candidate attempt in task/role/scope required")

    def test_later_success_can_qualify_with_earlier_failure_retained(self):
        self.observed()
        earlier = self.record["observations"][0]
        earlier.update(status="failed", exit_code=1, quality={"semantic": False, "contract": False})
        later = self.run_record("candidate-2")
        later["attempt"] = 2
        self.record["observations"].append(later)
        self.record["failures_and_skips"] = [{"run_id": "candidate-1", "reason": "Earlier attempt failed."}]
        self.record["decision_and_scope"].update(decision="adopt_within_scope", qualification_run_ids=["candidate-2"])
        self.assertTrue(self.result()["valid"])

    def test_failed_and_skipped_runs_are_preserved_exactly_once(self):
        self.observed()
        run = self.record["observations"][0]
        run.update(status="failed", exit_code=1, quality={"semantic": False, "contract": None})
        self.assert_invalid("every non-passed run exactly once")
        self.record["failures_and_skips"] = [{"run_id": run["id"], "reason": "Synthetic test failure."}]
        self.assertTrue(self.result()["valid"])
        self.record["failures_and_skips"].append(copy.deepcopy(self.record["failures_and_skips"][0]))
        self.assert_invalid("every non-passed run exactly once")

    def test_skips_cannot_claim_exits_or_quality(self):
        self.observed()
        run = self.record["observations"][0]
        run.update(status="skipped", exit_code=None, quality={"semantic": None, "contract": None})
        self.record["failures_and_skips"] = [{"run_id": run["id"], "reason": "Missing prerequisite."}]
        self.assertTrue(self.result()["valid"])
        run["exit_code"] = 0
        self.assert_invalid("skipped run cannot have exit")

    def test_zero_exit_does_not_override_failed_contract(self):
        self.observed()
        self.record["observations"][0]["quality"]["contract"] = False
        self.assert_invalid("passed run contradicts exit or quality")

    def test_runs_must_use_declared_tasks_roles_commands_and_unique_attempts(self):
        self.observed()
        original = copy.deepcopy(self.record["observations"][0])
        for change in ({"task": "unknown"}, {"role": "unknown"}, {"command_index": 1}):
            with self.subTest(change=change):
                self.record["observations"][0] = original | change
                self.assert_invalid("undeclared")
        self.record["observations"] = [original, copy.deepcopy(original)]
        self.assert_invalid("duplicate run ID")
        self.record["observations"][1]["id"] = "other"
        self.assert_invalid("duplicate task/role/condition attempt")

    def test_cache_and_reasoning_are_not_double_counted(self):
        self.savings()
        self.assertTrue(self.result()["valid"])
        usage = self.record["observations"][0]["usage"]
        usage["total"] += usage["reasoning_in_output"]
        self.assert_invalid("disjoint usage categories do not equal total")
        usage["total"] -= usage["reasoning_in_output"]
        usage["reasoning_in_output"] = usage["output"] + 1
        self.assert_invalid("reasoning exceeds inclusive output")

    def test_partial_or_unknown_usage_never_supports_savings(self):
        self.savings()
        for key in self.record["observations"][0]["usage"]:
            with self.subTest(key=key):
                original = self.record["observations"][0]["usage"][key]
                self.record["observations"][0]["usage"][key] = None
                self.assert_invalid("complete known usage")
                self.record["observations"][0]["usage"][key] = original
        self.record["usage_assessment"]["coverage"] = "partial"
        self.assert_invalid("complete matched task/role/condition coverage")

    def test_known_usage_subset_cannot_exceed_total_even_with_unknown_categories(self):
        self.observed()
        self.record["observations"][0]["usage"].update(cache_read=20, total=10)
        self.assert_invalid("known usage categories exceed total")

    def test_savings_require_execution_evidence_in_same_scope(self):
        self.savings()
        run = self.record["observations"][0]
        run["scope"] = "different task boundary"
        self.assert_invalid("scoped execution evidence required")
        run["scope"] = "fixture only"
        run["evidence_class"] = "pinned_source_review"
        self.assert_invalid("scoped execution evidence required")

    def test_uncovered_role_or_task_invalidates_whole_task_claim(self):
        self.savings()
        self.record["frozen_inputs"]["roles"].append("coordinator")
        self.assert_invalid("complete matched task/role/condition coverage")
        self.record["frozen_inputs"]["roles"].remove("coordinator")
        self.record["frozen_inputs"]["tasks"].append("patch-b")
        self.assert_invalid("complete matched task/role/condition coverage")

    def test_missing_attempt_and_changed_coverage_ledger_rejected(self):
        self.savings()
        self.record["observations"][0]["attempt"] = 2
        self.assert_invalid("consecutive attempt coverage")
        self.record["observations"][0]["attempt"] = 1
        self.record["usage_assessment"]["coverage_artifact"] = self.write("coverage.json", b'{"run_ids":[],"complete":true}')
        self.assert_invalid("coverage artifact disagrees")

    def test_coverage_must_list_every_attempt(self):
        self.savings()
        self.record["usage_assessment"]["expected_run_ids"].pop()
        self.assert_invalid("complete coverage needs every run")

    def test_cheaper_failed_or_ungraded_result_is_not_accepted_efficiency(self):
        self.savings()
        run = self.record["observations"][1]
        run["quality"]["semantic"] = None
        self.assert_invalid("every attempt needs passing quality")
        run.update(status="failed", exit_code=0, quality={"semantic": True, "contract": False})
        self.record["failures_and_skips"] = [{"run_id": run["id"], "reason": "Word limit failed."}]
        self.assert_invalid("every attempt needs passing quality")

    def test_equal_or_more_expensive_candidate_does_not_claim_savings(self):
        self.savings()
        self.record["observations"][1]["usage"] = copy.deepcopy(self.record["observations"][0]["usage"])
        self.assert_invalid("candidate total must be lower")

    def test_extra_passing_baseline_attempt_cannot_manufacture_savings(self):
        self.savings()
        baseline = copy.deepcopy(self.record["observations"][0])
        baseline.update(id="baseline-2", attempt=2)
        self.record["observations"].append(baseline)
        # Each baseline costs85; the sole candidate costs105. Summing the two
        # baseline attempts would incorrectly make the worse candidate look cheaper.
        self.record["observations"][1]["usage"].update(uncached_input=70, total=105)
        self.coverage()
        self.assert_invalid("equal passing attempt counts required per task and role")

    def test_matching_passing_attempt_counts_use_known_aggregate_sums(self):
        self.savings()
        second = copy.deepcopy(self.record["observations"])
        for run in second:
            run.update(id=f'{run["condition"]}-2', attempt=2)
        self.record["observations"].extend(second)
        self.coverage()
        self.assertEqual(sum(run["usage"]["total"] for run in self.record["observations"] if run["condition"] == "baseline"), 170)
        self.assertEqual(sum(run["usage"]["total"] for run in self.record["observations"] if run["condition"] == "candidate"), 90)
        self.assertTrue(self.result()["valid"])

    def test_cli_json_and_exit_status(self):
        self.result()
        command = [sys.executable, str(REPO / "scripts/validate_convergence.py"), "record.json", "--root", str(self.root), "--json"]
        passed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertTrue(json.loads(passed.stdout)["valid"])
        self.record["status"] = "observed"
        self.result()
        failed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(failed.returncode, 1)
        self.assertFalse(json.loads(failed.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
