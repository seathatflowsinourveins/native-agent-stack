"""Synthetic consistency tests; these never qualify native tool use or a host."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import host_receipts, organic_use
from scripts.validate import InvalidPublication, Validator


def proof(name="owner-analysis"):
    return {"ref": f"evidence/artifacts/organic-fixture/{name}.json", "sha256": "a" * 64}


def pending():
    pending_review = {"status": "pending", "ref": None, "sha256": None}
    return {
        "schema_version": 1, "protocol_id": "organic-e2e-v1-20261005", "amendment": "U1",
        "sources": [proof("protocol"), proof("amendment")],
        "records": [{
            "record_id": "serena-codex-native-pilot", "supersedes": None,
            "component_id": "serena", "layer_ids": ["foundation/code-navigation"],
            "component_pin": None,
            "client": {"id": "codex", "version": "0.160.0", "mode": "headless",
                       "model": None, "requested_effort": "max", "effective_effort": None,
                       "effective_tier": None, "route": None, "config_sha256": None},
            "platform_id": "linux-wsl2-x86_64", "arm": "native",
            "observed_at_utc": "2026-10-05T16:00:00Z",
            "task_scope": "ordinary navigation positives",
            "collection_scope": "terminal metadata only; exposure and joins unknown",
            "evidence_class": "source_review", "stage": "pilot", "state": "pending",
            "protocol_status": "UNKNOWN", "context_proof": None, "proofs": [proof("manifest")],
            "open_items": ["exposure and native telemetry joins remain unknown"],
            "phases": {"P1": None, "P2": None, "pooled": None},
            "runs": [{"run_id": "trial-1", "started_at_utc": "2026-10-05T15:00:00Z",
                      "ended_at_utc": "2026-10-05T15:01:00Z", "rc": 0}],
            "verdict": None,
            "qualification": {**pending_review, "rule": None,
                              "negative_control": copy.deepcopy(pending_review)},
            "review": copy.deepcopy(pending_review), "adjudication": copy.deepcopy(pending_review),
            "exclusion": None,
            "recheck": {"tool_pin": None, "client_version": "0.160.0",
                        "landscape": proof("landscape"), "sweep_id": None,
                        "sweep_date_utc": None, "max_age_days": 30},
        }],
    }


def metric(multiplier=1, *, eligible=4, uses=2, selections=3):
    cell = {
        "scope": "should_use", "provenance": proof("strata"),
        "interval_method": "wilson95", "interval_source": proof("owner-intervals"),
        "assigned": 8, "exposed": 6, "valid": 5, "eligible_exposed": eligible,
        # These categories are deliberately overlapping, not a sum partition.
        "unavailable": 5, "censored": 5, "telemetry_invalid": 5,
        "contamination_excluded": 5, "quota_deferred": 5,
        "uses": uses, "selections": selections,
        "oir": uses / eligible if eligible else None,
        "wilson95_low": 0.1 if eligible and uses else (0.0 if eligible else None),
        "wilson95_high": 0.9 if eligible else None,
        "selection_rate": selections / eligible if eligible else None,
    }
    for field in organic_use.COUNTS:
        cell[field] *= multiplier
    return cell


def completed(*, verdict=None, eligible=4, uses=2, selections=3):
    payload = pending()
    row = payload["records"][0]
    row.update(record_id="serena-codex-native-qualified", component_pin="v1.0.0",
               state="complete", stage="qualification", evidence_class="native_proven",
               protocol_status="SCREEN_PASS", context_proof=proof("frozen-context"), verdict=verdict)
    row["client"].update(model="fixture-model", effective_effort="max",
                         effective_tier="fixture-tier", route="fixture-route", config_sha256="b" * 64)
    row["recheck"]["tool_pin"] = row["component_pin"]
    row["phases"] = {phase: metric(2 if phase == "pooled" else 1,
                                 eligible=eligible, uses=uses, selections=selections)
                     for phase in organic_use.PHASES}
    row["qualification"] = {"status": "complete", "rule": "T6", **proof("qualification"),
                            "negative_control": {"status": "passed", **proof("negative-control")}}
    row["review"] = {"status": "reviewed", **proof("review")}
    row["adjudication"] = {"status": "adjudicated", **proof("adjudication")}
    return payload


def excluded():
    payload = completed(verdict="EXCLUDED", uses=0, selections=0)
    row = payload["records"][0]
    row["protocol_status"] = "SCREEN_NEVER"
    row["exclusion"] = {
        "rule_c": {**proof("rule-c"), "component_id": row["component_id"],
                   "task_scope": row["task_scope"]},
        "predicates": {
            "never_selected_full_run": {**proof("full-native-run"), "client_id": "codex",
                                        "arm": "native", "selections": 0},
            "overlap_with_selected": {**proof("overlap"), "client_id": "codex",
                                      "selected_cover_component_id": "jcodemunch",
                                      "task_scope": row["task_scope"]},
            "native_fix_rerun": {"client_id": "codex", "outcome": "unsuccessful",
                                "fix": proof("native-fix"), "rerun": proof("native-rerun")},
        },
        "overturn_conditions": {
            name: {"condition": name.replace("_", " "), "status": "pending", **proof("rule-c")}
            for name in ("later_organic_selection", "covering_tool_regression", "better_upstream_harness_ab")
        },
    }
    return payload


class OrganicPayloadTests(unittest.TestCase):
    def errors(self, payload):
        return organic_use.validate_payload(payload, component_ids={"serena", "jcodemunch"},
                                            receipt_component_ids={"serena", "jcodemunch"})

    def test_unknown_pilot_rc_zero_does_not_become_use(self):
        payload = pending()
        before = copy.deepcopy(payload)
        self.assertEqual(self.errors(payload), [])
        self.assertEqual(payload, before)
        self.assertTrue(all(value is None for value in payload["records"][0]["phases"].values()))
        self.assertIsNone(payload["records"][0]["verdict"])

    def test_schema_uses_only_the_existing_supported_subset(self):
        for node in host_receipts.schema_nodes(organic_use._schema()):
            unknown = set(node) - host_receipts.SCHEMA_SUPPORTED_KEYWORDS - host_receipts.SCHEMA_META_KEYWORDS
            self.assertEqual(unknown, set())

    def test_malformed_payloads_return_errors_without_semantic_crash(self):
        for value in (None, [], {}, {"schema_version": True}):
            with self.subTest(value=value):
                self.assertTrue(self.errors(value))

    def test_pilot_cannot_issue_any_final_verdict(self):
        for verdict in ("READY", "NOT-READY", "EXCLUDED"):
            payload = pending()
            payload["records"][0]["verdict"] = verdict
            self.assertTrue(any("pilot issues no verdicts" in message for message in self.errors(payload)))

    def test_pending_metrics_cannot_hide_unknowns_as_measured_zero(self):
        payload = pending()
        payload["records"][0]["phases"]["P1"] = metric(eligible=0, uses=0, selections=0)
        self.assertTrue(any("pending records require" in message for message in self.errors(payload)))

    def test_completed_declared_values_are_consistent_without_certifying_bounds(self):
        self.assertEqual(self.errors(completed(verdict="READY")), [])
        payload = completed()
        payload["records"][0]["phases"]["pooled"]["wilson95_low"] = 0.01
        self.assertEqual(self.errors(payload), [])  # No Wilson calculation or certification.

    def test_ready_rejects_env_local_checks_unknown_runtime_and_missing_t6(self):
        for field, value in (("arm", "env"), ("evidence_class", "local_integration"),
                             ("context_proof", None), ("protocol_status", "RATE_QUALIFIED_ON_SUITE")):
            payload = completed(verdict="READY")
            payload["records"][0][field] = value
            self.assertTrue(self.errors(payload), field)
        for field in ("model", "effective_effort", "effective_tier", "route", "config_sha256"):
            payload = completed(verdict="READY")
            payload["records"][0]["client"][field] = None
            self.assertTrue(self.errors(payload), field)
        payload = completed(verdict="READY")
        payload["records"][0]["qualification"]["rule"] = None
        self.assertTrue(self.errors(payload))

    def test_ready_needs_independent_review_adjudication_and_negative_control(self):
        for name in ("review", "adjudication"):
            payload = completed(verdict="READY")
            payload["records"][0][name] = {"status": "pending", "ref": None, "sha256": None}
            self.assertTrue(self.errors(payload))
        payload = completed(verdict="READY")
        payload["records"][0]["qualification"]["negative_control"]["status"] = "failed"
        self.assertTrue(self.errors(payload))

    def test_unknown_and_deferred_cannot_complete_qualification_or_issue_verdict(self):
        for status in ("UNKNOWN", "DEFERRED"):
            for verdict in (None, "NOT-READY"):
                with self.subTest(status=status, verdict=verdict):
                    payload = completed(verdict=verdict, eligible=0, uses=0, selections=0)
                    row = payload["records"][0]
                    row.update(protocol_status=status, context_proof=None)
                    row["qualification"]["rule"] = None
                    self.assertTrue(any("unresolved observations" in message
                                        for message in self.errors(payload)))

    def test_unknown_and_deferred_terminal_observations_remain_intermediate(self):
        for status in ("UNKNOWN", "DEFERRED"):
            with self.subTest(status=status):
                payload = completed(eligible=0, uses=0, selections=0)
                row = payload["records"][0]
                row.update(protocol_status=status, context_proof=None)
                row["qualification"] = copy.deepcopy(pending()["records"][0]["qualification"])
                self.assertEqual(self.errors(payload), [])

    def test_known_native_availability_failure_can_be_not_ready_without_use(self):
        # U1:61: an evidenced native availability defect is a known negative,
        # independently of READY's successful-use and negative-control gates.
        payload = completed(verdict="NOT-READY", eligible=0, uses=0, selections=0)
        row = payload["records"][0]
        row.update(protocol_status="UNAVAILABLE", context_proof=proof("native-availability-context"))
        row["qualification"].update(rule="U1:61", **proof("U1-native-unavailable-owner-proof"))
        row["qualification"]["negative_control"] = {
            "status": "pending", "ref": None, "sha256": None,
        }
        self.assertEqual(self.errors(payload), [])
        # The native callability probes need not invent organic-trial counts.
        row["phases"] = {phase: None for phase in organic_use.PHASES}
        self.assertEqual(self.errors(payload), [])
        for field, value in (("arm", "env"), ("evidence_class", "synthetic"),
                             ("context_proof", None)):
            with self.subTest(field=field):
                invalid = copy.deepcopy(payload)
                invalid["records"][0][field] = value
                self.assertTrue(self.errors(invalid))
        invalid = copy.deepcopy(payload)
        invalid["records"][0]["qualification"]["rule"] = None
        self.assertTrue(self.errors(invalid))

    def test_completed_availability_qualification_needs_native_proof_before_verdict(self):
        payload = completed(eligible=0, uses=0, selections=0)
        row = payload["records"][0]
        row.update(protocol_status="UNAVAILABLE", context_proof=proof("native-availability-context"))
        row["qualification"]["rule"] = "U1:61"
        row["phases"] = {phase: None for phase in organic_use.PHASES}
        self.assertEqual(self.errors(payload), [])
        for field, value in (("arm", "env"), ("evidence_class", "synthetic"),
                             ("context_proof", None)):
            with self.subTest(field=field):
                invalid = copy.deepcopy(payload)
                invalid["records"][0][field] = value
                self.assertTrue(any("U1:61 needs" in message for message in self.errors(invalid)))
        for field in ("ref", "sha256"):
            invalid = copy.deepcopy(payload)
            invalid["records"][0]["qualification"][field] = None
            self.assertTrue(self.errors(invalid))

    def test_native_availability_failure_rule_is_bound_to_its_client_and_criterion(self):
        for field, value in (("protocol_status", "SCREEN_NEVER"), ("client", "claude-code")):
            with self.subTest(field=field):
                payload = completed(verdict="NOT-READY", eligible=0, uses=0, selections=0)
                row = payload["records"][0]
                row["protocol_status"] = "UNAVAILABLE"
                row["qualification"]["rule"] = "U1:61"
                if field == "client":
                    row["client"]["id"] = value
                else:
                    row[field] = value
                self.assertTrue(any("U1:61 requires" in message for message in self.errors(payload)))

    def test_ready_uses_each_clients_applicable_t6_status(self):
        payload = completed(verdict="READY")
        payload["records"][0]["protocol_status"] = "ORGANIC_OBSERVED"
        self.assertTrue(self.errors(payload))
        payload["records"][0]["client"]["id"] = "claude-code"
        self.assertEqual(self.errors(payload), [])
        payload["records"][0]["protocol_status"] = "SCREEN_PASS"
        self.assertTrue(self.errors(payload))

    def test_rates_use_eligible_exposed_and_reject_nonfinite_or_inconsistent_declarations(self):
        for field, value in (("oir", 2 / 6), ("selection_rate", 3 / 6),
                             ("wilson95_low", float("nan")), ("wilson95_high", float("inf")),
                             ("wilson95_high", 1.01), ("eligible_exposed", 7), ("uses", True)):
            payload = completed()
            payload["records"][0]["phases"]["P1"][field] = value
            self.assertTrue(self.errors(payload), field)

    def test_zero_eligible_has_null_rates_and_does_not_establish_ready(self):
        self.assertEqual(self.errors(completed(eligible=0, uses=0, selections=0)), [])
        self.assertTrue(self.errors(completed(verdict="READY", eligible=0, uses=0, selections=0)))
        payload = completed(eligible=0, uses=0, selections=0)
        payload["records"][0]["phases"]["P1"]["oir"] = 0
        self.assertTrue(self.errors(payload))

    def test_pooled_counts_are_not_an_average_or_duplicate_snapshot(self):
        payload = completed()
        payload["records"][0]["phases"]["pooled"] = copy.deepcopy(payload["records"][0]["phases"]["P1"])
        self.assertTrue(any("disagrees with phase counts" in message for message in self.errors(payload)))

    def test_exclusion_requires_authority_same_client_cover_and_native_fix_rerun(self):
        self.assertEqual(self.errors(excluded()), [])
        for name in ("rule_c", "predicates", "overturn_conditions"):
            payload = excluded()
            del payload["records"][0]["exclusion"][name]
            self.assertTrue(self.errors(payload), name)
        payload = excluded()
        payload["records"][0]["exclusion"]["predicates"]["native_fix_rerun"]["client_id"] = "claude-code"
        self.assertTrue(self.errors(payload))
        payload = excluded()
        payload["records"][0]["exclusion"]["predicates"]["overlap_with_selected"]["task_scope"] = "other class"
        self.assertTrue(self.errors(payload))

    def test_selected_but_failed_and_unavailable_are_not_exclusions(self):
        payload = excluded()
        for phase in organic_use.PHASES:
            cell = payload["records"][0]["phases"][phase]
            cell["selections"] = 2 if phase == "pooled" else 1
            cell["selection_rate"] = 0.25
        self.assertTrue(self.errors(payload))
        payload = excluded()
        payload["records"][0]["protocol_status"] = "UNAVAILABLE"
        self.assertTrue(self.errors(payload))

    def test_exclusion_needs_native_observation_and_qualified_context(self):
        self.assertEqual(self.errors(excluded()), [])
        for field, value in (("evidence_class", "synthetic"),
                             ("evidence_class", "source_review"),
                             ("evidence_class", "local_integration"),
                             ("evidence_class", "measured_comparison"),
                             ("context_proof", None)):
            with self.subTest(field=field, value=value):
                payload = excluded()
                payload["records"][0][field] = value
                self.assertTrue(self.errors(payload))
        payload = excluded()
        payload["records"][0]["qualification"]["rule"] = None
        self.assertTrue(self.errors(payload))

    def test_canonical_id_receipt_scope_and_observation_identity_are_preserved(self):
        payload = pending()
        self.assertTrue(organic_use.validate_payload(payload, component_ids={"jcodemunch"}))
        self.assertTrue(organic_use.validate_payload(payload, receipt_component_ids={"jcodemunch"}))
        payload["records"].append(copy.deepcopy(payload["records"][0]))
        self.assertTrue(any("duplicate observation" in message for message in self.errors(payload)))

    def test_invalid_times_and_private_source_locators_fail_without_echoing_values(self):
        for field, value in (("ended_at_utc", "2026-10-05T14:59:00Z"),
                             ("started_at_utc", "2026-02-31T15:00:00Z")):
            payload = pending()
            payload["records"][0]["runs"][0][field] = value
            self.assertTrue(self.errors(payload))
        payload = pending()
        payload["sources"][0]["ref"] = str(Path(tempfile.gettempdir()) / "private-proof.json")
        messages = self.errors(payload)
        self.assertTrue(messages)
        self.assertFalse(any("private-proof.json" in message for message in messages))


class OrganicLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = "evidence/receipts/organic-fixture.json"
        self.detail = {
            "schema_version": 1, "id": "organic-fixture", "kind": "historical_inventory",
            "component_ids": ["serena"],
            "claim": "Historical pilot metadata, organic qualification pending",
            "limitations": ["Historical metadata only, not live acceptance"],
            "data": {"organic_use": pending()},
        }
        self.write()

    def write(self):
        path = self.root / self.relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(self.detail, indent=2) + "\n").encode()
        path.write_bytes(raw)
        manifests = self.root / "manifests"
        manifests.mkdir(exist_ok=True)
        entry = {key: self.detail[key] for key in ("id", "kind", "component_ids", "claim", "limitations")}
        entry["path"] = self.relative
        self.registry = {"schema_version": 1, "receipts": [entry], "files": [{
            "path": self.relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}]}
        (manifests / "evidence.json").write_text(json.dumps(self.registry), encoding="utf-8")
        stack = {"schema_version": 1, "components": [{"id": "serena", "version": "1.0.0",
                 "profile": "foundation", "commands": ["serena --help"], "evidence_ids": ["organic-fixture"]}],
                 "profiles": [{"id": "foundation", "component_ids": ["serena"]}], "models": []}
        (manifests / "stack.json").write_text(json.dumps(stack), encoding="utf-8")

    def test_projection_preserves_unknowns_identity_method_hash_and_does_not_mutate(self):
        rows = organic_use.load_records(self.root)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["component_id"], "serena")
        self.assertEqual(row["block_ref"], self.relative + "#/data/organic_use/records/0")
        self.assertEqual(row["receipt_sha256"], self.registry["files"][0]["sha256"])
        self.assertEqual(row["protocol_id"], self.detail["data"]["organic_use"]["protocol_id"])
        self.assertEqual(row["protocol_sources"], self.detail["data"]["organic_use"]["sources"])
        row["protocol_sources"][0]["sha256"] = "b" * 64
        self.assertEqual(self.detail["data"]["organic_use"]["sources"][0]["sha256"], "a" * 64)
        self.assertIsNone(row["verdict"])

    def test_absent_registry_unregistered_file_and_ordinary_receipt_do_not_project(self):
        (self.root / "manifests/evidence.json").unlink()
        self.assertEqual(organic_use.load_records(self.root), [])
        self.write()
        self.registry["receipts"] = []
        (self.root / "manifests/evidence.json").write_text(json.dumps(self.registry), encoding="utf-8")
        self.assertEqual(organic_use.load_records(self.root), [])
        self.detail["data"] = {"ordinary_inventory": {}}
        self.write()
        self.assertEqual(organic_use.load_records(self.root), [])

    def test_tampered_hash_malformed_block_metadata_and_scope_fail_closed(self):
        for alteration in ("hash", "payload", "metadata", "scope"):
            self.detail["data"]["organic_use"] = pending()
            self.write()
            if alteration == "hash":
                with (self.root / self.relative).open("a", encoding="utf-8") as stream:
                    stream.write(" ")
            elif alteration == "metadata":
                self.registry["receipts"][0]["claim"] = "different"
                (self.root / "manifests/evidence.json").write_text(json.dumps(self.registry), encoding="utf-8")
            elif alteration == "payload":
                self.detail["data"]["organic_use"] = None
                self.write()
            else:
                self.detail["data"]["organic_use"]["records"][0]["component_id"] = "jcodemunch"
                self.write()
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                organic_use.load_records(self.root)

    def test_existing_validator_rejects_optional_pilot_verdict(self):
        self.detail["data"]["organic_use"]["records"][0]["verdict"] = "READY"
        self.write()
        validator = Validator(self.root)
        with self.assertRaises(InvalidPublication):
            validator.validate()
        self.assertTrue(any("pilot issues no verdicts" in error for error in validator.errors))


class OrganicRecheckTests(unittest.TestCase):
    def test_unknown_bindings_are_not_matches_or_changes(self):
        row = pending()["records"][0]
        now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        self.assertEqual(organic_use.recheck(row, None, None, now), [])
        self.assertEqual(organic_use.recheck(row, "a-known-new-target", "0.160.0", now), [])

    def test_four_scoped_flags_age_window_end_and_exact_thirty_day_boundary(self):
        row = completed()["records"][0]
        boundary = datetime(2026, 11, 4, 16, tzinfo=timezone.utc)
        self.assertEqual(organic_use.recheck(row, "v1.0.0", "0.160.0", boundary), [])
        due = datetime(2026, 11, 4, 16, 0, 1, tzinfo=timezone.utc)
        self.assertEqual(organic_use.recheck(row, "v2.0.0", "0.161.0", due, True), [
            "organic_tool_version_changed", "organic_client_version_changed",
            "organic_landscape_reopened", "organic_age_limit"])


if __name__ == "__main__":
    unittest.main()
