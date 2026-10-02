"""Local contract checks; fixtures are synthetic and prove no runtime quality."""

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("qualification"), "qualification module absent")
        import qualification
        self.q = qualification
        self.temp = tempfile.TemporaryDirectory(prefix="native-qualification-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = self.root / "source.md"
        self.doc.write_text("Synthetic authoritative fact: project.color = blue.\n")
        self.digest = self.q.sha256_file(self.doc)
        self.source = dict(source_id="source-1", path="source.md", sha256=self.digest,
                           scenario_id="scenario-1", split="dev", recorded_at="2026-01-01T00:00:00Z",
                           available_from="2026-01-01T00:00:00Z", effective_at="2026-01-01T00:00:00Z",
                           effective_until=None, authority="canonical", supersedes=[],
                           supported_facts={"project.color": "blue"}, supports_abstention=[])
        self.case = dict(case_id="case-1", scenario_id="scenario-1", split="dev", category="temporal",
                         input="What is the project color?", query_time="2026-02-01T00:00:00Z",
                         source_ids=["source-1"], expected=dict(answer_type="answer",
                         required_facts=[dict(fact_id="project.color", value="blue", source_ids=["source-1"])],
                         forbidden_facts=[], citation_source_ids=["source-1"], abstention_reason=None),
                         provenance=dict(synthetic=True, authored_by="test", exposure="development"))
        self.record = dict(case_id="case-1", arm="hindsight", mode="tuned_pipeline", split="dev",
                           answer=dict(answer_type="answer", facts={"project.color": "blue"},
                                       as_of=self.case["query_time"], abstention_reason=None),
                           citations=[dict(fact_id="project.color", source_id="source-1", source_sha256=self.digest)],
                           evidence=dict(path="source.md", sha256=self.digest, kind="native_transcript"),
                           runtime=dict(actual=True, client="codex", model="test-native-label",
                                        model_family="test-family", version="test-version", run_id="test-native-run",
                                        started_at="2026-03-01T00:00:00Z", completed_at="2026-03-01T00:00:01Z",
                                        corpus_freeze_id="freeze-1", pipeline_config_sha256="a" * 64,
                                        holdout_exposed=False))

    def score(self, record=None, source=None):
        return self.q.score_record(self.case, {"source-1": source or self.source}, record or self.record)

    def inputs(self, records=None, cases=None, sources=None):
        paths = []
        for name, data, jsonl in (("cases.jsonl", cases or [self.case], True),
                                  ("sources.json", sources or [self.source], False),
                                  ("results.jsonl", records if records is not None else [self.record], True)):
            path = self.root / name
            path.write_text("\n".join(json.dumps(row) for row in data) if jsonl else json.dumps(data))
            paths.append(path)
        manifest_path = self.root / "corpus-manifest.json"
        manifest_path.write_text(json.dumps({"corpus_freeze_id": "freeze-1", "splits": {"dev": {
            "cases_sha256": self.q.sha256_file(paths[0]), "sources_registry_sha256": self.q.sha256_file(paths[1]),
            "case_count": len(cases or [self.case]), "source_count": len(sources or [self.source])}}}))
        return self.q.load_inputs(*paths, arm="hindsight", mode="tuned_pipeline", split="dev", freeze_id="freeze-1",
                                  corpus_manifest=manifest_path, manifest_sha256=self.q.sha256_file(manifest_path))

    def test_mutated_case_bytes_cannot_reuse_frozen_manifest(self):
        self.inputs()
        cases_path = self.root / "cases.jsonl"
        changed = {**self.case, "input": "Changed input after freeze"}
        cases_path.write_text(json.dumps(changed))
        manifest_path = self.root / "corpus-manifest.json"
        with self.assertRaisesRegex(ValueError, "frozen corpus manifest"):
            self.q.load_inputs(cases_path, self.root / "sources.json", self.root / "results.jsonl",
                               arm="hindsight", mode="tuned_pipeline", split="dev", freeze_id="freeze-1",
                               corpus_manifest=manifest_path, manifest_sha256=self.q.sha256_file(manifest_path))

    def test_exact_facts_and_attributed_citations_pass(self):
        self.assertEqual(self.score()["score"], 1)

    def test_fluent_false_claim_and_extra_claim_fail(self):
        record = copy.deepcopy(self.record)
        record["answer"]["facts"]["project.color"] = "not blue; official color is red"
        self.assertEqual(self.score(record)["score"], 0)
        record = copy.deepcopy(self.record)
        record["answer"]["facts"]["invented.claim"] = "blue"
        self.assertEqual(self.score(record)["score"], 0)

    def test_fabricated_or_wrong_fact_citation_fails(self):
        record = copy.deepcopy(self.record)
        record["citations"][0]["source_id"] = "invented-source"
        self.assertEqual(self.score(record)["score"], 0)
        source = copy.deepcopy(self.source)
        source["supported_facts"]["project.color"] = "red"
        self.assertEqual(self.score(source=source)["score"], 0)

    def test_multisource_fact_requires_each_source_and_scalar_types_are_exact(self):
        source2 = {**self.source, "source_id": "source-2"}
        self.case["source_ids"].append("source-2")
        self.case["expected"]["citation_source_ids"].append("source-2")
        self.case["expected"]["required_facts"][0]["source_ids"].append("source-2")
        sources = {"source-1": self.source, "source-2": source2}
        self.assertEqual(self.q.score_record(self.case, sources, self.record)["score"], 0)
        self.record["citations"].append({**self.record["citations"][0], "source_id": "source-2"})
        self.assertEqual(self.q.score_record(self.case, sources, self.record)["score"], 1)
        self.case["expected"]["required_facts"][0]["value"] = 1
        for source in sources.values():
            source["supported_facts"]["project.color"] = 1
        self.record["answer"]["facts"]["project.color"] = True
        self.assertEqual(self.q.score_record(self.case, sources, self.record)["score"], 0)

    def test_unavailable_expired_source_and_wrong_answer_date_fail(self):
        for field, value in (("available_from", "2027-01-01T00:00:00Z"),
                             ("effective_until", "2026-01-31T00:00:00Z")):
            source = copy.deepcopy(self.source)
            source[field] = value
            self.assertEqual(self.score(source=source)["score"], 0)
        record = copy.deepcopy(self.record)
        record["answer"]["as_of"] = "2026-01-01T00:00:00Z"
        self.assertEqual(self.score(record)["score"], 0)

    def test_missing_duplicate_and_mismatched_result_cases_rejected(self):
        for rows in ([], [self.record, self.record]):
            with self.assertRaises(ValueError):
                self.inputs(records=rows)
        record = copy.deepcopy(self.record)
        record["case_id"] = "other-case"
        with self.assertRaises(ValueError):
            self.inputs(records=[record])
        record = copy.deepcopy(self.record)
        record["arm"] = "ai_memory"
        with self.assertRaises(ValueError):
            self.inputs(records=[record])

    def test_source_hash_or_split_mismatch_rejected(self):
        source = copy.deepcopy(self.source)
        source["sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            self.inputs(sources=[source])
        source = copy.deepcopy(self.source)
        source["split"] = "holdout"
        with self.assertRaises(ValueError):
            self.inputs(sources=[source])

    def test_missing_provenance_rejected_and_absent_accounting_preserved_null(self):
        record = copy.deepcopy(self.record)
        record.pop("evidence")
        with self.assertRaises(ValueError):
            self.inputs(records=[record])
        data = self.inputs()
        self.assertIsNone(data[0]["record"]["runtime"]["accounting"]["input_tokens"])
        self.assertIsNone(data[0]["record"]["runtime"]["accounting"]["cost_usd"])

    def test_synthetic_runtime_rejected_by_native_task(self):
        record = copy.deepcopy(self.record)
        record["runtime"]["actual"] = False
        record["runtime"]["client"] = "synthetic"
        record["evidence"]["kind"] = "synthetic_fixture"
        with self.assertRaises(ValueError):
            self.inputs(records=[record])

    def rows(self, gain=True, n=60):
        rows = []
        for index in range(n):
            for arm in ("native_files", "ai_memory", "hindsight"):
                rows.append(dict(case_id=f"holdout-{index}", category=f"category-{index % 6}", split="holdout",
                                 arm=arm, mode="tuned_pipeline", score=int(arm == "hindsight" and gain),
                                 runtime={**self.record["runtime"], "pipeline_config_sha256": hashlib.sha256(arm.encode()).hexdigest()},
                                 freeze={"manifest_sha256": "d" * 64, "parent_manifest_sha256": None}))
        return rows

    def test_paired_stratified_macro_bootstrap_and_ties(self):
        result = self.q.paired_comparison(self.rows(), baseline="ai_memory", candidate="hindsight",
                                          mode="tuned_pipeline", iterations=200)
        self.assertEqual(result["gain"], 1)
        self.assertEqual(result["ci95"], [1, 1])
        tie = self.q.paired_comparison(self.rows(gain=False), baseline="ai_memory", candidate="hindsight",
                                       mode="tuned_pipeline", iterations=200)
        self.assertEqual(tie["gain"], 0)
        self.assertFalse(tie["decision_pass"])
        missing = self.rows()[:-1]
        with self.assertRaises(ValueError):
            self.q.paired_comparison(missing, baseline="ai_memory", candidate="hindsight", mode="tuned_pipeline")

    def test_perfect_quality_without_operational_evidence_cannot_promote(self):
        decision = self.q.promotion_decision(self.rows(), {}, freeze_id="freeze-1", manifest_sha256="d" * 64, iterations=200)
        self.assertFalse(decision["promote"])
        self.assertIn("operational", " ".join(decision["reasons"]))

    def test_holdout_exposure_and_invalid_extension_fail_closed(self):
        rows = self.rows()
        rows[0]["runtime"]["holdout_exposed"] = True
        decision = self.q.promotion_decision(rows, {}, freeze_id="freeze-1", manifest_sha256="d" * 64, iterations=200)
        self.assertFalse(decision["promote"])
        self.assertIn("exposed", " ".join(decision["reasons"]))
        with self.assertRaises(ValueError):
            self.q.promotion_decision(self.rows(n=120), {}, freeze_id="freeze-1", manifest_sha256="d" * 64, look="extension", iterations=200)

    def synthetic_gate_contracts(self):
        """Invented receipts for validator checks only, never native acceptance."""
        gates = {}
        for name in self.q.OPERATIONAL_GATES:
            identities = [f"synthetic-observation-{i}" for i in range(20)]
            common = dict(passed=True, actual_native=True, arm="hindsight", observed_ids=identities,
                          corpus_freeze_id="freeze-1")
            receipt = dict(**common, gate=name, evidence_class="native_operation",
                           checks=[dict(name="synthetic-contract-only", expected=True, observed=True, passed=True)],
                           discriminating_control=dict(expected_failure=True, observed_failure=True, observed_id="synthetic-control"),
                           blinded=True, model_families=["synthetic-family-a", "synthetic-family-b"],
                           restored_components=["database", "external_configuration", "wiki"],
                           clients=["codex", "claude"], completed_sessions=20, restarts=2,
                           p95_ms=100, budget_ms=500, sample_count=20)
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(receipt))
            digest = self.q.sha256_file(path)
            observer = dict(verified=True, observer_id="synthetic-observer", gate=name,
                            receipt_sha256=digest, native_family_provenance_verified=True)
            observer_path = self.root / f"{name}-observer.json"
            observer_path.write_text(json.dumps(observer))
            gates[name] = dict(**common, evidence=dict(path=path.name, sha256=digest),
                               independent_verification=dict(verified=True, evidence=dict(
                                   path=observer_path.name, sha256=self.q.sha256_file(observer_path))))
        return gates

    def test_gate_contract_requires_matching_receipt_and_independent_observer(self):
        gates = self.synthetic_gate_contracts()
        decision = self.q.promotion_decision(self.rows(), gates, freeze_id="freeze-1", manifest_sha256="d" * 64,
                                             evidence_root=self.root, iterations=200)
        self.assertTrue(decision["promote"])  # Schema consistency only; fixture is not native evidence.
        gates["backup_restore"]["independent_verification"]["verified"] = False
        decision = self.q.promotion_decision(self.rows(), gates, freeze_id="freeze-1", manifest_sha256="d" * 64,
                                             evidence_root=self.root, iterations=200)
        self.assertFalse(decision["promote"])
        self.assertFalse(decision["gates"]["backup_restore"])
        gates = self.synthetic_gate_contracts()
        gates["scope_isolation"]["observed_ids"] = ["synthetic-observation-0"] * 20
        self.assertFalse(self.q._gate_evidence("scope_isolation", gates["scope_isolation"], "freeze-1", self.root))

    def test_single_extension_keeps_config_freeze_and_original_case_set(self):
        initial = self.rows(gain=False)
        for row in initial:
            if row["arm"] == "hindsight" and row["case_id"] == "holdout-0":
                row["score"] = 1
        previous = self.q.promotion_decision(initial, {}, freeze_id="freeze-1", manifest_sha256="d" * 64, iterations=2000)
        self.assertTrue(previous["extension_eligible"])
        extension = initial + self.rows(n=120)[180:]
        for row in extension[180:]:
            row["freeze"] = {"manifest_sha256": "e" * 64, "parent_manifest_sha256": "d" * 64}
        decision = self.q.promotion_decision(extension, {}, freeze_id="freeze-1", manifest_sha256="e" * 64, look="extension",
                                             previous=previous, iterations=200)
        self.assertTrue(decision["extension_used"])
        self.assertFalse(decision["extension_eligible"])
        extension[-1]["runtime"]["pipeline_config_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            self.q.promotion_decision(extension, {}, freeze_id="freeze-1", manifest_sha256="e" * 64, look="extension", previous=previous)

    def test_native_file_conditional_recommendation_reports_third_contrast(self):
        rows = self.rows(gain=False)
        for row in rows:
            row["score"] = int(row["arm"] == "native_files")
        decision = self.q.promotion_decision(rows, {}, freeze_id="freeze-1", manifest_sha256="d" * 64, iterations=200)
        self.assertEqual(len(decision["comparisons"]), 3)
        self.assertTrue(decision["native_file_answer_recommendation"])
        self.assertFalse(decision["production_promotion"])


if __name__ == "__main__":
    unittest.main()
