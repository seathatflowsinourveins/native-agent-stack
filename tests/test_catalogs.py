"""Offline catalog regressions use small synthetic records, not private evidence."""

from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_catalogs import BASE, CATALOG_FILES, InvalidCatalog, main, validate


class CatalogValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.header = {"schema_version": 1, "checked_at": "2026-09-19"}
        self.catalogs = []
        for index, path in enumerate(CATALOG_FILES):
            entry = {
                "id": f"repo-{index}", "repository": f"https://github.com/example/repo-{index}",
                "layers": ["research"], "role": "Offline catalog fixture",
                "decision": "conditional", "rationale": "Illustrates a separate capability.",
                "version_or_commit": "v1.0.0", "release_date": "2026-09-18T10:00:00Z",
                "license": "MIT", "us_equities_fit": "Research only.",
                "alpaca_fit": "No broker actions.", "evidence_level": "source_review",
                "evidence_refs": ["https://github.com/example/source"],
                "native_workflow": ["# Prospective: example --help"],
                "requirements": ["An operator-selected local runtime."],
                "limitations": ["Synthetic source review, not installed or executed."],
                "sources": ["https://github.com/example/source"],
            }
            self.catalogs.append({**self.header, "layer": Path(path).stem, "entries": [entry]})
        self.model = {
            "id": "example/model", "provider": "Example publisher", "role": "Embedding candidate",
            "decision": "conditional", "revision": "a" * 40,
            "release_evidence_date": None, "release_evidence_kind": "Release date unknown",
            "license": None, "task_fit": "Candidate retrieval model.",
            "limitations": ["Metadata does not prove local inference."],
            "evidence_level": "metadata_only", "evidence_refs": ["evidence/metadata.json"],
            "native_workflow": ["# Prospective: hf models info example/model"],
            "workflow_scope": "Metadata only; no weights or inference.",
            "sources": ["https://huggingface.co/example/model"],
        }
        self.models = {
            **self.header, "layer": "models", "recent_window": ["2026-06-21", "2026-09-19"],
            "scope": "Synthetic model records.", "entries": [self.model],
        }
        self.coverage = {
            **self.header,
            "stars": [
                {"repository": "https://github.com/example/repo-0", "disposition": "catalog_reviewed", "catalog_entry_ids": ["repo-0"]},
                {"repository": "https://github.com/example/unassessed", "disposition": "metadata_only_unassessed", "catalog_entry_ids": []},
                {"repository": "https://github.com/example/baseline", "disposition": "baseline_record", "catalog_entry_ids": []},
            ],
            "beyond_stars": [
                {"repository": f"https://github.com/example/repo-{index}", "catalog_entry_ids": [f"repo-{index}"]}
                for index in range(1, 4)
            ],
            "aliases": {},
        }
        self.manifest = {
            **self.header, "catalog_files": list(CATALOG_FILES),
            "model_file": f"{BASE}/models.json", "coverage_file": f"{BASE}/coverage.json",
            "star_audit_file": f"{BASE}/star-audit.json",
            "counts": {"repository_entries": 4, "unique_catalog_repositories": 4, "models": 1,
                       "public_stars": 3, "starred_catalog_repositories": 1, "beyond_star_catalog_repositories": 3},
        }
        self.write("manifests/stack.json", {"components": [{"repository": "https://github.com/example/baseline/releases/tag/v1"}]})
        self.write("evidence/metadata.json", {"schema_version": 1, "kind": "native_metadata_commands", "scope": "Metadata retrieval.", "commands": [{"exit_code": 0}]})
        self.write("evidence/receipt.json", {"schema_version": 1, "kind": "native_model_e2e", "claim": "Synthetic model fixture.", "data": {"exit_code": 0}})
        self.audit = {
            **self.header, "scope": "Synthetic overview decisions, not runtime proof.",
            "counts": {"public_stars": 3, "previously_covered": 0,
                       "new_source_dispositions": 3, "unassessed": 0,
                       "by_review_level": {"source_review": 3},
                       "by_review_depth": {"readme_license_overview": 3},
                       "by_decision": {"conditional": 3}},
            "entries": [{"repository": item["repository"], "review_level": "source_review",
                         "source_commit": "a" * 40, "review_depth": "readme_license_overview",
                         "decision": "conditional", "role": "Synthetic reference",
                         "catalog_entry_ids": item["catalog_entry_ids"], "evidence_refs": [],
                         "rationale": "Selected for this fixture.", "limitations": ["Not executed."],
                         "sources": [item["repository"]]} for item in self.coverage["stars"]],
        }
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.save()

    @property
    def entry(self):
        return self.catalogs[0]["entries"][0]

    def write(self, relative, data):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def save(self):
        for path, catalog in zip(CATALOG_FILES, self.catalogs):
            self.write(path, catalog)
        self.write(f"{BASE}/models.json", self.models)
        self.write(f"{BASE}/coverage.json", self.coverage)
        self.write(f"{BASE}/manifest.json", self.manifest)

    def assert_invalid(self, message):
        with self.assertRaisesRegex(InvalidCatalog, message):
            validate(self.root)

    def test_valid_counts_and_metadata_only_model(self):
        self.assertEqual(validate(self.root), self.manifest["counts"])

    def test_star_audit_missing_or_extra_identity_fails(self):
        self.audit["entries"].pop()
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assert_invalid("exactly the public-star snapshot")

    def test_star_audit_duplicate_identity_fails(self):
        self.audit["entries"].append(self.audit["entries"][0])
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assert_invalid("duplicate canonical")

    def test_star_source_review_needs_pin_and_depth(self):
        self.audit["entries"][0]["source_commit"] = "main"
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assert_invalid("pinned commit")

    def test_star_audit_cannot_label_source_review_native_proven(self):
        self.audit["entries"][0]["review_level"] = "native_proven"
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assert_invalid("review_level")

    def test_star_audit_rejects_inflated_review_depth_count(self):
        self.audit["counts"]["by_review_depth"] = {"deep_review": 3}
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assert_invalid("by_review_depth")

    def test_malformed_star_records_fail_with_catalog_error(self):
        self.coverage["stars"] = [None]
        self.save()
        self.assert_invalid("expected object")

    def test_star_audit_references_and_catalog_ids_are_checked(self):
        for field, value, message in (
            ("evidence_refs", ["../outside.json"], "path must be canonical"),
            ("catalog_entry_ids", ["nonexistent"], "catalog_entry_ids"),
            ("review_depth", "full_security_audit", "review_depth"),
        ):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.audit)
                altered["entries"][0][field] = value
                self.write(f"{BASE}/star-audit.json", altered)
                self.assert_invalid(message)

    def test_star_audit_counts_reject_boolean_and_float(self):
        for value in (False, 0.0):
            with self.subTest(value=value):
                self.audit["counts"]["unassessed"] = value
                self.write(f"{BASE}/star-audit.json", self.audit)
                self.assert_invalid("expected nonnegative integer")

    def test_missing_manifest_or_catalog_fails(self):
        for path in (f"{BASE}/manifest.json", CATALOG_FILES[2]):
            with self.subTest(path=path):
                (self.root / path).unlink()
                self.assert_invalid("file missing")
                self.save()

    def test_manifest_cannot_silently_omit_a_catalog(self):
        self.manifest["catalog_files"].pop()
        self.save()
        self.assert_invalid("all four repository catalogs")

    def test_duplicate_json_keys_fail(self):
        (self.root / f"{BASE}/manifest.json").write_text('{"schema_version": 1, "schema_version": 1}')
        self.assert_invalid("duplicate key")

    def test_invalid_schema_versions_and_layer_fail(self):
        for value in (2, True, "1"):
            with self.subTest(value=value):
                self.catalogs[0]["schema_version"] = value
                self.save()
                self.assert_invalid("schema_version must be 1")
        self.catalogs[0]["schema_version"] = 1
        self.catalogs[0]["layer"] = "other"
        self.save()
        self.assert_invalid("layer differs")

    def test_duplicate_ids_across_layers_and_models_fail(self):
        self.catalogs[1]["entries"][0]["id"] = self.entry["id"]
        self.save()
        self.assert_invalid("duplicate global id")
        self.catalogs[1]["entries"][0]["id"] = "repo-1"
        self.model["id"] = self.entry["id"]
        self.save()
        self.assert_invalid("duplicate global id")

    def test_same_repository_in_two_layers_is_allowed_and_counted_once(self):
        self.catalogs[1]["entries"][0]["repository"] = self.entry["repository"]
        self.coverage["stars"][0]["catalog_entry_ids"].append("repo-1")
        self.coverage["beyond_stars"].pop(0)
        self.manifest["counts"]["unique_catalog_repositories"] = 3
        self.manifest["counts"]["beyond_star_catalog_repositories"] = 2
        self.save()
        self.write(f"{BASE}/star-audit.json", self.audit)
        self.assertEqual(validate(self.root), self.manifest["counts"])

    def test_enums_and_meaningful_lists(self):
        for key, value in (("decision", "installed"), ("evidence_level", "passed"),
                           ("requirements", []), ("limitations", [" "]), ("layers", "research"),
                           ("sources", []), ("native_workflow", []), ("role", "")):
            with self.subTest(key=key):
                old = self.entry[key]
                self.entry[key] = value
                self.save()
                self.assert_invalid(key)
                self.entry[key] = old

    def test_excluded_model_can_have_no_proposed_execution(self):
        self.model["decision"] = "excluded"
        self.model["native_workflow"] = []
        self.save()
        validate(self.root)

    def test_release_dates_are_real_iso_dates_and_unknown_is_explicit(self):
        for value in ("2026-02-30", "09/19/2026", "2026-09-18T10:00:00", 0):
            with self.subTest(value=value):
                self.entry["release_date"] = value
                self.save()
                self.assert_invalid("release_date")
        self.entry["release_date"] = None
        self.save()
        validate(self.root)
        del self.entry["release_date"]
        self.save()
        self.assert_invalid("missing release_date")

    def test_catalog_dates_match_manifest(self):
        self.catalogs[2]["checked_at"] = "2026-09-18"
        self.save()
        self.assert_invalid("checked_at differs")

    def test_model_recent_window_order_and_revision(self):
        self.models["recent_window"].reverse()
        self.save()
        self.assert_invalid("recent_window ordering")
        self.models["recent_window"].reverse()
        self.model["revision"] = "main"
        self.save()
        self.assert_invalid("revision must be null")

    def test_optional_source_commit_is_validated_without_requiring_it(self):
        self.entry["source_commit"] = "not-a-sha"
        self.save()
        self.assert_invalid("source_commit")
        self.entry["source_commit"] = "a" * 40
        self.save()
        validate(self.root)

    def test_repository_urls_are_canonical_and_case_insensitive_for_joins(self):
        original = self.entry["repository"]
        for value in ("http://github.com/example/repo-0", original + "/", original + ".git",
                      original + "/tree/main", original + "?x=1", "https://github.com.evil/example/repo-0"):
            with self.subTest(value=value):
                self.entry["repository"] = value
                self.save()
                self.assert_invalid("repository")
        self.entry["repository"] = "https://github.com/Example/Repo-0"
        self.save()
        validate(self.root)

    def test_sources_require_https_without_embedded_credentials(self):
        for value in ("http://example.org/source", "https://user:password@example.org/source", "https://", "https://example.org/a b"):
            with self.subTest(value=value):
                self.entry["sources"] = [value]
                self.save()
                self.assert_invalid("HTTPS URL")

    def test_evidence_paths_reject_missing_traversal_absolute_and_symlinks(self):
        for value in ("missing.json", "../outside.json", "/etc/passwd", "evidence/../receipt.json",
                      "evidence//receipt.json", "C:\\private.json", "evidence/receipt.json#section"):
            with self.subTest(value=value):
                self.entry["evidence_refs"] = [value]
                self.save()
                self.assert_invalid("file missing|path must")
        target = self.root / "evidence/linked.json"
        target.symlink_to(self.root / "evidence/receipt.json")
        self.entry["evidence_refs"] = ["evidence/linked.json"]
        self.save()
        self.assert_invalid("symlinks are forbidden")
        target.unlink()
        target.parent.rename(self.root / "real-evidence")
        target.parent.symlink_to(self.root / "real-evidence", target_is_directory=True)
        self.entry["evidence_refs"] = ["evidence/receipt.json"]
        self.save()
        self.assert_invalid("symlinks are forbidden")

    def test_policy_or_metadata_json_is_not_native_evidence(self):
        self.entry["evidence_level"] = "native_proven"
        for record in ({"policy": "Use native tools."}, {"kind": "native_metadata_commands", "scope": "Metadata", "commands": [{}]},
                       {"schema_version": 1, "kind": "native_cli_e2e"}, {"kind": []}):
            with self.subTest(record=record):
                self.write("evidence/policy.json", record)
                self.entry["evidence_refs"] = ["evidence/policy.json"]
                self.save()
                self.assert_invalid("local execution receipt")

    def test_native_model_needs_model_execution_not_cli_or_metadata_receipt(self):
        self.model["evidence_level"] = "native_proven"
        self.model["evidence_refs"] = ["evidence/metadata.json"]
        self.save()
        self.assert_invalid("metadata is not inference proof")
        self.write("evidence/cli.json", {"schema_version": 1, "kind": "native_cli_e2e", "claim": "CLI help.", "data": {"exit_code": 0}})
        self.model["evidence_refs"] = ["evidence/cli.json"]
        self.save()
        self.assert_invalid("native_model_e2e")
        self.model["evidence_refs"] = ["evidence/receipt.json"]
        self.save()
        validate(self.root)

    def test_native_cli_receipt_can_declare_scope_inside_its_result(self):
        self.write("evidence/cli.json", {
            "schema_version": 1, "kind": "native_cli_e2e", "recorded_date": "2026-09-19",
            "result": {"scope": "Synthetic offline conversion.", "rows": 3},
            "command": "example convert fixture.json",
        })
        self.entry["evidence_level"] = "native_proven"
        self.entry["evidence_refs"] = ["evidence/cli.json"]
        self.save()
        validate(self.root)

    def test_native_receipt_scope_requires_meaningful_text(self):
        self.model["evidence_level"] = "native_proven"
        self.model["evidence_refs"] = ["evidence/malformed.json"]
        self.save()
        for field in ("claim", "scope", "task", "result.scope"):
            for value in ({"x": 1}, ["scope"], True, 1, "", "   ", None):
                with self.subTest(field=field, value=value):
                    record = {"schema_version": 1, "kind": "native_model_e2e", "data": {"exit_code": 0}}
                    if field == "result.scope":
                        record["result"] = {"scope": value}
                    else:
                        record[field] = value
                    self.write("evidence/malformed.json", record)
                    self.assert_invalid("native_model_e2e")

    def test_legacy_health_receipt_is_native_cli_evidence_only(self):
        self.write("evidence/health.json", {
            "checked_at_utc": "2026-09-19T00:00:00+00:00", "scope": "Anonymous health only.",
            "limits": ["No provider call."], "routes": [{"method": "GET", "authentication_supplied": False,
                "attempts": 1, "http_status": 200, "url": "http://127.0.0.1:10000/health"}],
        })
        self.entry["evidence_level"] = "native_proven"
        self.entry["evidence_refs"] = ["evidence/health.json"]
        self.save()
        validate(self.root)
        self.model["evidence_level"] = "native_proven"
        self.model["evidence_refs"] = ["evidence/health.json"]
        self.save()
        self.assert_invalid("native_model_e2e")

    def test_alias_chain_joins_without_double_counting(self):
        self.coverage["aliases"] = {"old/repo": "renamed/repo", "renamed/repo": "example/repo-0"}
        self.coverage["stars"][0]["repository"] = "https://github.com/old/repo"
        self.save()
        self.assertEqual(validate(self.root), self.manifest["counts"])

    def test_alias_cycles_and_noncanonical_names_fail(self):
        for aliases in ({"old/repo": "old/repo"}, {"old/repo": "new/repo", "new/repo": "old/repo"},
                        {"Old/repo": "new/repo"}, {"old/repo": ["new/repo"]}):
            with self.subTest(aliases=aliases):
                self.coverage["aliases"] = aliases
                self.save()
                self.assert_invalid("alias cycle|aliases must")

    def test_wrong_or_missing_join_ids_fail(self):
        for ids in (["repo-1"], [], ["repo-0", "unknown"], ["repo-0", "repo-0"]):
            with self.subTest(ids=ids):
                self.coverage["stars"][0]["catalog_entry_ids"] = ids
                self.save()
                self.assert_invalid("catalog_entry_ids")

    def test_star_disposition_cannot_claim_or_hide_catalog_review(self):
        self.coverage["stars"][0]["disposition"] = "metadata_only_unassessed"
        self.save()
        self.assert_invalid("disposition must match catalog membership")
        self.coverage["stars"][0]["disposition"] = "catalog_reviewed"
        self.coverage["stars"][1]["disposition"] = "catalog_reviewed"
        self.save()
        self.assert_invalid("disposition must match catalog membership")

    def test_baseline_disposition_requires_a_real_baseline_repository(self):
        self.coverage["stars"][1]["disposition"] = "baseline_record"
        self.save()
        self.assert_invalid("absent from manifests/stack.json")

    def test_coverage_must_partition_every_catalog_repository(self):
        original = copy.deepcopy(self.coverage)
        self.coverage["beyond_stars"].pop()
        self.save()
        self.assert_invalid("missing from coverage")
        self.coverage = original
        self.coverage["beyond_stars"].append({"repository": self.entry["repository"], "catalog_entry_ids": [self.entry["id"]]})
        self.save()
        self.assert_invalid("overlap")

    def test_duplicate_alias_and_case_stars_do_not_inflate_counts(self):
        self.coverage["aliases"] = {"old/repo": "example/repo-0"}
        self.coverage["stars"].append({"repository": "https://github.com/Old/Repo", "disposition": "catalog_reviewed", "catalog_entry_ids": ["repo-0"]})
        self.save()
        self.assert_invalid("duplicate canonical repository")

    def test_unknown_beyond_repository_is_not_counted(self):
        self.coverage["beyond_stars"].append({"repository": "https://github.com/example/other", "catalog_entry_ids": []})
        self.save()
        self.assert_invalid("beyond_stars must refer")

    def test_every_declared_count_is_recomputed_and_booleans_rejected(self):
        for key, actual in self.manifest["counts"].copy().items():
            with self.subTest(key=key):
                self.manifest["counts"][key] = actual + 1
                self.save()
                self.assert_invalid(f"counts.{key}")
                self.manifest["counts"][key] = actual
        self.manifest["counts"]["models"] = True
        self.save()
        self.assert_invalid("nonnegative integer")

    def test_cli_reports_success_and_missing_manifest_failure(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--root", str(self.root)]), 0)
        self.assertIn("source claims and native executions were not rerun", output.getvalue())
        (self.root / f"{BASE}/manifest.json").unlink()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--root", str(self.root)]), 1)


class Pr4CardsReconciliationTests(unittest.TestCase):
    """Content checks for the 2026-09-22 engine/broker card reconciliation (pr4-cards).

    These assert the actual repository files under catalogs/us-equities, not a
    synthetic fixture; they check card content only, not full-catalog schema
    validation (that path also needs coverage.json/star-audit.json, which this
    unit does not own -- see the task handoff for the exact blocking finding).
    """

    ROOT = Path(__file__).resolve().parents[1]

    def load(self, relative):
        return json.loads((self.ROOT / relative).read_text(encoding="utf-8"))

    def entry(self, data, entry_id):
        for item in data["entries"]:
            if item["id"] == entry_id:
                return item
        self.fail(f"entry {entry_id} not found")

    def test_nautilustrader_card_is_the_selected_destination_default(self):
        data = self.load(f"{BASE}/engines-strategies.json")
        nautilustrader = self.entry(data, "nautilustrader")
        self.assertEqual(nautilustrader["decision"], "default")
        self.assertEqual(nautilustrader["evidence_level"], "native_proven")
        self.assertIn("selected destination runtime", nautilustrader["role"])
        self.assertIn("2.0.0rc5", nautilustrader["version_or_commit"])
        self.assertEqual(nautilustrader.get("source_commit"), "1b0a49d2792a9432a3aca3fcb617ce7a630d905e")
        joined_limitations = " ".join(nautilustrader["limitations"])
        # Codex cross-family review of PR-4: the card must state the retained parity
        # state (a completed BLOCKED replay with four failed checks recorded in the
        # comparison summary), not "planned_not_executed", and never a per-check total
        # that is not retained in this repository. PR #67 (2026-09-22) retains the
        # verdict file itself on main, so the card now points there instead of the
        # former parity worktree.
        self.assertIn("reported_execution_blocked_review_incomplete", joined_limitations)
        self.assertIn("completed BLOCKED replay", joined_limitations)
        self.assertIn("four failed checks", joined_limitations)
        self.assertIn("blueprints/us-equities/engine-nautilus/spy-parity/verdict.json", joined_limitations)
        self.assertNotIn("parity worktree", joined_limitations)
        self.assertNotIn("planned_not_executed", joined_limitations)
        self.assertNotIn("25 pass / 4 fail", joined_limitations)
        self.assertNotIn("29 checks", joined_limitations)

        lean = self.entry(data, "lean")
        self.assertEqual(lean["decision"], "default")
        self.assertIn("frozen historical comparator", lean["role"])
        self.assertNotIn("shared strategy host", lean["role"])

    def test_new_broker_adapter_cards_exist_with_required_notes(self):
        data = self.load(f"{BASE}/engines-strategies.json")
        ibkr = self.entry(data, "nautilus-ibkr-adapter")
        self.assertEqual(ibkr["repository"], "https://github.com/nautechsystems/nautilus_trader")
        self.assertEqual(ibkr["decision"], "default")
        self.assertEqual(ibkr["evidence_level"], "source_review")
        self.assertIn("broker-adapter", ibkr["layers"])
        self.assertTrue(any("not_established" in item for item in ibkr["limitations"]))

        alpaca = self.entry(data, "adaptive-paper-alpaca-adapter")
        self.assertEqual(alpaca["repository"], "https://github.com/seathatflowsinourveins/native-agent-stack")
        self.assertEqual(alpaca["decision"], "default")
        self.assertEqual(alpaca["evidence_level"], "source_review")
        self.assertTrue(any("no live broker fills claimed" in item.lower() for item in alpaca["limitations"]))
        self.assertIn("blueprints/us-equities/adaptive-paper/receipt.json", alpaca["evidence_refs"])

    def test_engines_strategies_card_files_referenced_by_new_entries_exist(self):
        data = self.load(f"{BASE}/engines-strategies.json")
        for entry_id in ("nautilustrader", "nautilus-ibkr-adapter", "adaptive-paper-alpaca-adapter"):
            item = self.entry(data, entry_id)
            for ref in item.get("evidence_refs", []):
                if not ref.startswith("https://"):
                    self.assertTrue((self.ROOT / ref).is_file(), f"{entry_id}: missing local evidence {ref}")

    def test_agents_operations_grype_and_openbao_notes(self):
        data = self.load(f"{BASE}/agents-operations.json")
        grype = self.entry(data, "grype")
        # After the pr4-scan unit landed, the grype card records the executed scan
        # (evidence_level native_proven, limitations naming the 2026-09-22 database
        # snapshot) instead of the pending "scan receipt lands" note.
        self.assertEqual(grype["evidence_level"], "native_proven")
        self.assertTrue(any("2026-09-22 database" in item for item in grype["limitations"]))
        openbao = self.entry(data, "openbao")
        self.assertTrue(any("selected live-primary, unaccepted" in item for item in openbao["limitations"]))
        # Regression (fix round pr4-cards): "live-primary" is this catalog's own
        # designation, not something runtime-target.json declares. Any mention
        # of runtime-target.json alongside "live-primary" must say what the
        # file actually records instead of implying it names IBKR live-primary.
        for item in openbao["limitations"]:
            if "live-primary" in item and "runtime-target.json" in item:
                self.assertIn("not a 'live-primary' designation", item)

    def test_ibkr_live_primary_claim_does_not_misattribute_runtime_target(self):
        # Regression (fix round pr4-cards): runtime-target.json broker_boundaries
        # only records selected_path/local_broker_acceptance for IBKR; it never
        # uses the phrase "live-primary". Any card text combining both terms
        # must say so explicitly rather than implying runtime-target.json makes
        # that designation.
        runtime_target = self.load(f"{BASE}/runtime-target.json")
        self.assertNotIn("live-primary", json.dumps(runtime_target))
        data = self.load(f"{BASE}/engines-strategies.json")
        ibkr = self.entry(data, "nautilus-ibkr-adapter")
        if "live-primary" in ibkr["rationale"] and "runtime-target.json" in ibkr["rationale"]:
            self.assertIn("not a 'live-primary' designation", ibkr["rationale"])

    def test_nautilus_repository_cards_are_reflected_in_coverage_and_star_audit(self):
        # Regression (fix round pr4-cards): the coverage/star-audit records for
        # nautechsystems/nautilus_trader must list every catalog card id sharing
        # that repository (nautilustrader and nautilus-ibkr-adapter), and the new
        # adaptive-paper-alpaca-adapter repository must appear in coverage.
        coverage = self.load(f"{BASE}/coverage.json")
        star_audit = self.load(f"{BASE}/star-audit.json")
        nautilus_star = next(
            s for s in coverage["stars"]
            if s["repository"] == "https://github.com/nautechsystems/nautilus_trader"
        )
        self.assertEqual(
            set(nautilus_star["catalog_entry_ids"]),
            {"nautilustrader", "nautilus-ibkr-adapter"},
        )
        nautilus_audit_entry = next(
            e for e in star_audit["entries"]
            if e["repository"] == "https://github.com/nautechsystems/nautilus_trader"
        )
        self.assertEqual(
            set(nautilus_audit_entry["catalog_entry_ids"]),
            {"nautilustrader", "nautilus-ibkr-adapter"},
        )
        alpaca_adapter_repos = {
            entry["repository"]
            for entry in coverage.get("stars", []) + coverage.get("beyond_stars", [])
            if "adaptive-paper-alpaca-adapter" in entry.get("catalog_entry_ids", [])
        }
        self.assertEqual(
            alpaca_adapter_repos,
            {"https://github.com/seathatflowsinourveins/native-agent-stack"},
        )
        manifest = self.load(f"{BASE}/manifest.json")
        self.assertEqual(
            manifest["counts"]["beyond_star_catalog_repositories"],
            len(coverage["beyond_stars"]),
        )

    def test_manifest_repository_entry_counts_match_recomputation(self):
        manifest = self.load(f"{BASE}/manifest.json")
        repos = set()
        total = 0
        for name in ("foundation-memory", "agents-operations", "data-research", "engines-strategies"):
            data = self.load(f"{BASE}/{name}.json")
            for entry in data["entries"]:
                total += 1
                repos.add(entry["repository"].lower())
        self.assertEqual(manifest["counts"]["repository_entries"], total)
        self.assertEqual(manifest["counts"]["unique_catalog_repositories"], len(repos))

    def test_reconciliations_file_has_the_nine_new_entries(self):
        data = self.load("tools/sota-convergence/reconciliations-20260922.json")
        entries = data["reconciliations"]
        pairs = [(item["layer"], item["kind"]) for item in entries]
        for expected in (
            ("backtesting-engine", "card_reconciled"),
            ("execution-broker", "card_added"),
            ("market-data-reference", "stack_component_added"),
            ("security-supply-chain", "scan_recorded"),
            ("observability-hosting", "alert_rules_added"),
            ("security-supply-chain", "decision_recorded"),
            ("data-quality-orchestration", "gate_wired"),
            ("execution-broker", "gate_ladder_recorded"),
        ):
            self.assertIn(expected, pairs)
        self.assertEqual(pairs.count(("execution-broker", "card_added")), 2)
        new_kinds = {
            "card_reconciled", "card_added", "stack_component_added", "scan_recorded",
            "alert_rules_added", "decision_recorded", "gate_wired", "gate_ladder_recorded",
        }
        for item in entries:
            if item["kind"] in new_kinds:
                self.assertEqual(set(item), {"layer", "kind", "repository", "pin", "source", "note"})


if __name__ == "__main__":
    unittest.main()
