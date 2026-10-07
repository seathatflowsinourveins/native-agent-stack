"""Synthetic declarations test ownership; they establish no native acceptance.

Extend native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:
scripts/validate_foundation.py:50-63 and scripts/validate_catalogs.py:110-186.
JSON Schema's uniqueItems compares whole array values; projected repository
identity also needs the existing case/alias canonicalization:
https://json-schema.org/understanding-json-schema/reference/array#uniqueitems
"""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate import InvalidPublication, validate as validate_publication
from scripts.validate_catalogs import InvalidCatalog
from scripts.validate_foundation import (
    FINALIZED_SELECTION, MANIFEST, REPOSITORY_COVERAGE,
    SelectionEvidence, validate_finalized_selection, validate_foundation,
)
from tests import test_foundation_catalog as foundation_fixtures
from tests import test_validate as publication_fixtures


RESEARCH = "https://github.com/vendor/research"
SDK = "https://github.com/vendor/sdk"
ALTERNATIVE = "https://github.com/vendor/sdk-alternative"
EXCLUDED = "https://github.com/vendor/retired-sdk"
DECISION = "docs/decisions/2026-10-07-finalized-sota-catalog.md"


def slot(identifier, layer_id, role, repositories, references=()):
    return {
        "id": identifier, "layer_id": layer_id, "role": role,
        "purpose": f"One bounded {role} capability.",
        "repositories": repositories, "references": list(references),
    }


def selected(repository, selection="default"):
    return {"repository": repository, "selection": selection}


class FinalizedSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = {"finalized_selection_file": FINALIZED_SELECTION}
        self.coverage = {"aliases": {"old/sdk": "vendor/sdk"}}
        self.document = {
            "schema_version": 1, "status": "finalized",
            "decision_record": DECISION,
            "source_base_commit": "e28d0eec112527ac02659ac23753533b8ed39a73",
            "included_repositories": [RESEARCH, SDK, ALTERNATIVE, EXCLUDED],
            "limitations": ["Synthetic structural fixtures; no actual installation or adoption."],
            "slots": [
                slot("research-worker", "web-research", "research-worker",
                     [selected(RESEARCH)], [SDK, SDK]),
                {**slot("python-sdk", "agent-sdks", "agent-sdk", [
                    selected(SDK), selected(ALTERNATIVE, "alternative"),
                    selected(EXCLUDED, "excluded"),
                ], [RESEARCH]), "language": "python",
                 "supported_languages": ["python", "typescript"]},
            ],
        }
        self.write(DECISION, "# Synthetic decision record\n")
        self.prepare_sources()
        for value in self.document["slots"]:
            value["repositories"] = [self.contract(row["repository"], row["selection"]) for row in value["repositories"]]

    def prepare_sources(self):
        self.base_commit = "6fc39660d458824b7aaf0827d1c6d3ea0ae73453"
        self.release_commit = "a" * 40
        self.component_ids = {RESEARCH: "fixture-research", SDK: "fixture-sdk"}
        self.source_documents = {
            "manifests/landscape.json": {"schema_version": 1, "current_core_releases": [
                {"repo": repo.removeprefix("https://github.com/"), "tag_name": "v1.0.0",
                 "published_at": "2026-10-01T00:00:00Z", "prerelease": False,
                 "html_url": repo + "/releases/tag/v1.0.0", "source_commit": self.release_commit}
                for repo in (RESEARCH, SDK, ALTERNATIVE, EXCLUDED)]},
            "catalogs/us-equities/agents-operations.json": {"schema_version": 1, "entries": [
                {"repository": repo, "version_or_commit": "1.0.0", "evidence_level": "source_review"}
                for repo in (ALTERNATIVE, EXCLUDED)]},
            "catalogs/us-equities/decision-index.json": {"schema_version": 1, "records": [
                {"repository": repo, "references": [{"kind": "catalog_card",
                 "path": "catalogs/us-equities/agents-operations.json", "pointer": f"/entries/{index}",
                 "evidence_level": "source_review"}]} for index, repo in enumerate((ALTERNATIVE, EXCLUDED))]},
            "fixtures/comparison.json": {"frozen": "Synthetic comparison input"},
        }
        self.packet_path = "evidence/receipts/fixture-selection-evidence.json"
        self.packet = {"schema_version": 1, "id": "fixture-selection-evidence", "kind": "artifact_measurement",
                       "component_ids": list(self.component_ids.values()),
                       "claim": "Synthetic publication-contract inputs; no native acceptance.",
                       "limitations": ["Every observation is synthetic fixture data."],
                       "evidence_class": "synthetic", "data": {"proofs": {}, "organic": {}, "judgments": {},
                       "fields": {}, "audits": {}, "comparisons": {}, "exclusions": {
                           "retired": {"repository": EXCLUDED, "pin": "1.0.0", "component_ids": [],
                                       "evidence_class": "synthetic", "scope": "Dated fixture exclusion",
                                       "date": "2026-10-01", "reason": "Synthetic retired candidate",
                                       "overturn_conditions": ["A supported replacement meets the same fixture requirement."]}}}}
        self.source_documents[self.packet_path] = self.packet
        self.stack = {"schema_version": 1, "components": [
            {"id": cid, "repository": repo, "version": "1.0.0", "source_pin": self.release_commit,
             "profile": "core", "commands": ["fixture --help"], "evidence_ids": [self.packet["id"]]}
            for repo, cid in self.component_ids.items()], "profiles": [{"id": "core", "component_ids": list(self.component_ids.values())}],
            "models": []}

    def source_ref(self, path, pointer):
        raw = json.dumps(self.source_documents[path]).encode()
        return {"path": path, "pointer": pointer, "sha256": hashlib.sha256(raw).hexdigest(),
                "source_commit": self.base_commit}

    def evidence_ref(self, pointer, target):
        return {**self.source_ref(self.packet_path, pointer), "receipt_id": self.packet["id"],
                "evidence_class": target.get("evidence_class", "synthetic"), "scope": target["scope"]}

    def contract(self, repo, selection="default"):
        position = [RESEARCH, SDK, ALTERNATIVE, EXCLUDED].index(repo)
        unknown = lambda: {"status": "unknown", "reason": "No qualifying observation in this synthetic fixture.", "evidence_refs": []}
        result = {"repository": repo, "selection": selection, "component_ids": [self.component_ids[repo]] if repo in self.component_ids else [],
                  "adoption_status": "recommendation", "source": {"status": "recorded", "reason": None,
                  "vendor_official": True, "release_pin": "1.0.0", "commit": self.release_commit,
                  "release_date": "2026-10-01", "clean_release": True,
                  "release_ref": self.source_ref("manifests/landscape.json", f"/current_core_releases/{position}"),
                  "candidate_binding": None}, "evidence_classes": ["metadata_only"],
                  "install_smoke": [{"client": client, "integration": {
                      "status": "unknown", "reason": "Native integration not qualified.", "channel": None, "integration_path": None,
                      "vendor_ref": None, "readback_refs": [], "provenance_refs": []},
                      "installation": unknown(), "wiring": unknown(), "smoke": unknown()}
                                    for client in ("claude", "codex")],
                  "organic": [{"client": client, "arm": arm, "task_scope": None, **unknown(), **({"daily_report": {
                      "status": "unknown", "reason": "Owner working-day report/policy unavailable.", "policy_ref": None,
                      "report_ref": None}} if arm == "native" else {})}
                              for client in ("claude", "codex") for arm in ("native", "env")],
                  "refutations": [{"family": family, "role": role, "status": "unknown", "reason": "No original judgment returned.",
                                   "source_field_ref": None, "judgment_refs": [], "result": None}
                                  for family in ("claude", "gpt6") for role in ("facts", "fit")],
                  "audit": {"status": "unknown", "reason": "Audit unavailable.", "grade": None, "origin": None,
                            "date": None, "limitations": ["Owner audit is only a lead."], "lead_only": True, "evidence_refs": []},
                  "exclusion": None, "overturn": {"status": "unknown", "reason": "Comparison not run.", "fixture_ref": None,
                                                 "metric_ref": None, "arms": [], "trigger_ref": None}, "supersedes": []}
        if repo not in self.component_ids:
            index = [ALTERNATIVE, EXCLUDED].index(repo)
            result["source"]["candidate_binding"] = {
                "record_ref": self.source_ref("catalogs/us-equities/decision-index.json", f"/records/{index}"),
                "origin_ref": self.source_ref("catalogs/us-equities/agents-operations.json", f"/entries/{index}")}
            result["evidence_classes"].append("source_review")
        if selection == "excluded":
            target = self.packet["data"]["exclusions"]["retired"]
            result["exclusion"] = {key: copy.deepcopy(target[key]) for key in ("date", "reason", "overturn_conditions")}
            result["exclusion"]["evidence_refs"] = [self.evidence_ref("/data/exclusions/retired", target)]
            result["evidence_classes"].append("synthetic")
        return result

    def registry(self):
        return {"schema_version": 1, "receipts": [{**{key: self.packet[key] for key in
                ("id", "kind", "component_ids", "claim", "limitations")}, "path": self.packet_path}],
                "files": sorted([{"path": path, "sha256": hashlib.sha256(json.dumps(value).encode()).hexdigest(),
                                  "bytes": len(json.dumps(value).encode())} for path, value in self.source_documents.items()],
                                 key=lambda row: row["path"])}

    def refresh_refs(self):
        def walk(value):
            if isinstance(value, dict):
                if "path" in value and "pointer" in value and "source_commit" in value and value["path"] in self.source_documents:
                    value["sha256"] = self.source_ref(value["path"], value["pointer"])["sha256"]
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.document)

    def copy_sources_to(self, fixture):
        for path, value in self.source_documents.items():
            target = fixture.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")
        stack_path = fixture.root / "manifests/stack.json"
        stack = json.loads(stack_path.read_text())
        stack["components"].extend(copy.deepcopy(self.stack["components"]))
        for component in stack["components"]:
            component["profile"] = "core"
        if "profiles" in stack:
            stack["profiles"][0]["component_ids"].extend(component["id"] for component in self.stack["components"])
        registry = json.loads((fixture.root / "manifests/evidence.json").read_text())
        additional = self.registry()
        registry["receipts"].extend(additional["receipts"])
        registry["files"] = sorted(registry.get("files", []) + additional["files"], key=lambda row: row["path"])
        for path, value in (("manifests/stack.json", stack), ("manifests/evidence.json", registry)):
            fixture.write_json(path, value) if hasattr(fixture, "write_json") else fixture.write(path, value)
        return {"components": len(stack["components"]), "profiles": len(stack.get("profiles", [])),
                "receipts": len(registry["receipts"]), "hashed_files": len(registry["files"])}

    def default_row(self):
        return self.document["slots"][0]["repositories"][0]

    def add_smoke(self, *, client="claude", stage="smoke", evidence_class="synthetic"):
        row, slot = self.default_row(), self.document["slots"][0]
        key = client + "-" + stage
        target = {"repository": row["repository"], "pin": "1.0.0", "component_ids": row["component_ids"],
                  "evidence_class": evidence_class, "scope": "One synthetic consuming-client operation",
                  "client": client, "stage": stage, "role": slot["role"], "layer_id": slot["layer_id"],
                  "result": "pass", "observed_at_utc": "2026-10-06T00:00:00Z", "commands": [
                      {"exit": 0, "output_excerpt": "Synthetic structural fixture output.", "output_sha256": "b" * 64}]}
        self.packet["data"]["proofs"][key] = target
        carrier = next(value for value in row["install_smoke"] if value["client"] == client)
        field = "installation" if stage == "install" else stage
        carrier[field] = {"status": "recorded", "reason": None,
                          "evidence_refs": [self.evidence_ref("/data/proofs/" + key, target)]}
        if evidence_class not in row["evidence_classes"]:
            row["evidence_classes"].append(evidence_class)
        self.refresh_refs()
        return carrier[field]["evidence_refs"][0], target

    def add_refuters(self):
        from scripts.saturation_ledger import v2_field_sha256
        row, slot = self.default_row(), self.document["slots"][0]
        member = {"candidate_key": "foundation/web-research/fixture-research", "repository": RESEARCH}
        source = {"contract_version": 2, "catalog": "foundation", "layer_id": slot["layer_id"],
                  "requirement_sha256": "c" * 64, "platform_profiles_sha256": "d" * 64,
                  "eligible_field": [member], "requirement": {"selection": {
                      "repository": RESEARCH, "pin": "1.0.0", "commit": self.release_commit, "role": slot["role"]}}}
        from scripts.saturation_ledger import canonical
        source["requirement_sha256"] = hashlib.sha256(canonical(source["requirement"])).hexdigest()
        source["field_sha256"] = v2_field_sha256(source)
        self.packet["data"]["fields"]["research"] = source
        for carrier in row["refutations"]:
            family, role = carrier["family"], carrier["role"]
            refs, results = [], []
            for seed in (1, 2):
                jid = family + "-" + role + "-" + str(seed)
                vote = {"candidate_key": member["candidate_key"], "repository": RESEARCH,
                        "evidence_key": member["candidate_key"], "status": "credible", "criterion": None,
                        "fact": "Synthetic source identity", "confidence": 0.9,
                        "reasoning": "Synthetic fixture of an original returned judgment.",
                        "refs": [RESEARCH], "requirement_fit": "Bounded fixture requirement"}
                self.packet["data"]["judgments"][jid] = {
                    "contract_version": 2, "layer_id": slot["layer_id"], "role": role,
                    "votes": [vote], "skills_used": [], "judgment": {
                        "judgment_id": jid, "order_seed": seed, "family": family,
                        "model_route_requested": "fixture", "model_route_actual": None,
                        "source_field_sha256": source["field_sha256"],
                        "provider_sampling_seed_requested": None, "provider_sampling_seed_actual": None,
                        "provider_sampling_seed_status": "unknown"}}
                refs.append(self.source_ref(self.packet_path, "/data/judgments/" + jid))
                results.append({"judgment_id": jid, "status": "credible", "criterion": None})
            carrier.update(status="recorded", reason=None, source_field_ref=self.source_ref(self.packet_path, "/data/fields/research"),
                           judgment_refs=refs, result=results)
        row["evidence_classes"].append("synthetic")
        self.refresh_refs()

    def external_evidence_ref(self, path, target):
        artifacts = self.packet["data"].setdefault("artifacts", [])
        if {"path": path} not in artifacts:
            artifacts.append({"path": path})
        return {**self.source_ref(path, ""), "receipt_id": self.packet["id"],
                "evidence_class": target["evidence_class"], "scope": target["scope"]}

    def wiring_chain(self, *, instruction_path=False):
        """Source-declared prototype, never real deployment or owner qualification."""
        row, slot = self.default_row(), self.document["slots"][0]
        slot["task_scope"] = "One source-retrieval fixture"
        self.add_refuters()
        for cid, repo in (("claude-code", "https://github.com/anthropics/claude-code"),
                         ("codex", "https://github.com/openai/codex")):
            self.stack["components"].append({"id": cid, "repository": repo, "version": "1.0.0", "source_pin": "e" * 40, "profile": "core",
                                             "commands": ["fixture-client --help"], "evidence_ids": [self.packet["id"]]})
            self.stack["profiles"][0]["component_ids"].append(cid)
            self.packet["component_ids"].append(cid)
        self.packet["data"]["vendors"] = {}
        self.packet["data"]["readbacks"] = {}
        for client in ("claude", "codex"):
            integration_path = "vendor-instructions" if instruction_path else "vendor-hook-install"
            vendor = {"kind": "vendor_client_integration", "repository": RESEARCH, "component_pin": "1.0.0",
                      "source_commit": self.release_commit, "client": client, "client_version": "1.0.0",
                      "role": slot["role"], "layer_id": slot["layer_id"], "channel": "hook",
                      "integration_path": integration_path, "registration_surface": "client-native-registration",
                      "registration_names": ["fixture-native-hook"], "native_operations": ["bounded-source-query"],
                      "required_provenance": [], "documentation": {"repository": RESEARCH, "commit": self.release_commit,
                      "path": "README.md", "start_line": 10, "end_line": 12,
                      "url": RESEARCH + "/blob/" + self.release_commit + "/README.md#L10-L12"}}
            readback = {"kind": "native_integration_readback", "repository": RESEARCH, "pin": "1.0.0",
                        "component_ids": row["component_ids"], "evidence_class": "native_proven", "scope": "Names-only native readback",
                        "client": client, "client_version": "1.0.0", "role": slot["role"], "layer_id": slot["layer_id"],
                        "channel": "hook", "integration_path": integration_path, "registration_surface": vendor["registration_surface"],
                        "names": ["fixture-native-hook"], "names_only": True, "completed_at_utc": "2026-10-06T09:00:00Z"}
            self.packet["data"]["vendors"][client] = vendor
            self.packet["data"]["readbacks"][client] = readback
            consumer = next(value for value in row["install_smoke"] if value["client"] == client)
            consumer["integration"] = {"status": "recorded", "reason": None, "channel": "hook", "integration_path": integration_path,
                                       "vendor_ref": self.source_ref(self.packet_path, "/data/vendors/" + client),
                                       "readback_refs": [self.evidence_ref("/data/readbacks/" + client, readback)], "provenance_refs": []}
            for stage in ("install", "wiring", "smoke"):
                _, target = self.add_smoke(client=client, stage=stage, evidence_class="native_proven")
                target.update(client_version="1.0.0", channel="hook", observed_at_utc={
                    "install": "2026-10-06T08:00:00Z", "wiring": "2026-10-06T08:30:00Z",
                    "smoke": "2026-10-06T10:00:00Z"}[stage])
                target["commands"][0]["cmd"] = "fixture native operation"
                if stage == "smoke":
                    context = {"kind": "native_session_context", "repository": RESEARCH, "pin": "1.0.0",
                               "component_ids": row["component_ids"], "evidence_class": "native_proven", "scope": "Fresh task context",
                               "client": client, "client_version": "1.0.0", "role": slot["role"], "layer_id": slot["layer_id"],
                               "task_scope": slot["task_scope"], "channel": "hook", "session_digest": ("1" if client == "claude" else "2") * 64,
                               "launched_at_utc": "2026-10-06T09:30:00Z", "fresh_session": True,
                               "task_prompt_named_tool": False, "extra_task_harness_named_tool": False,
                               "prompt_sha256": "3" * 64, "harness_sha256": "4" * 64}
                    path = f"evidence/artifacts/fresh-context-{client}.json"
                    self.source_documents[path] = context
                    target["context_proof_ref"] = self.external_evidence_ref(path, context)
                    from scripts.saturation_ledger import canonical
                    execution = {"kind": "native_integration_execution", "repository": RESEARCH, "pin": "1.0.0",
                                 "component_ids": row["component_ids"], "evidence_class": "native_proven", "scope": "Original native path execution",
                                 "client": client, "client_version": "1.0.0", "role": slot["role"], "layer_id": slot["layer_id"],
                                 "task_scope": slot["task_scope"], "channel": "hook", "integration_path": integration_path,
                                 "registration_name": "fixture-native-hook", "native_operation": "bounded-source-query",
                                 "session_digest": context["session_digest"], "completed_at_utc": "2026-10-06T09:45:00Z",
                                 "command_sha256": hashlib.sha256(canonical(target["commands"])).hexdigest(), "output_sha256": "b" * 64}
                    event_path = f"evidence/artifacts/native-execution-{client}.json"
                    self.source_documents[event_path] = execution
                    target["native_execution_ref"] = self.external_evidence_ref(event_path, execution)
        self.owner_records = []
        self.packet["data"]["organic_use"] = {"records": []}
        for client in ("claude", "codex"):
            index = len(self.owner_records)
            record = {"component_id": row["component_ids"][0], "component_pin": "1.0.0", "task_scope": slot["task_scope"],
                      "client": {"id": "claude-code" if client == "claude" else client}, "arm": "native",
                      "layer_ids": [slot["layer_id"]], "evidence_class": "native_proven", "verdict": "READY"}
            self.packet["data"]["organic_use"]["records"].append(record)
            pointer = f"/data/organic_use/records/{index}"
            self.owner_records.append({**record, "block_ref": self.packet_path + "#" + pointer})
            cell = next(cell for cell in row["organic"] if cell["client"] == client and cell["arm"] == "native")
            cell.update(status="recorded", reason=None, task_scope=slot["task_scope"], evidence_refs=[
                self.evidence_ref(pointer, {**record, "scope": slot["task_scope"]})])
            policy_path = f"evidence/artifacts/day-policy-{client}.json"
            counter_path = f"evidence/artifacts/day-counter-{client}.json"
            report_path = f"evidence/artifacts/day-report-{client}.json"
            # The fixture owner declares these endpoints. The checker contains
            # no universal 8h/24h interpretation of 'one working day'.
            window = {"since": "2026-10-06T13:00:00Z", "until": "2026-10-06T21:00:00Z"}
            counter_type = "hook_execution_complete" if client == "claude" else "codex_hooks_run_total"
            common = {"repository": RESEARCH, "component_pin": "1.0.0", "client": client, "client_version": "1.0.0",
                      "role": slot["role"], "layer_id": slot["layer_id"], "task_scope": slot["task_scope"],
                      "channel": "hook", "counter_type": counter_type, "window": window}
            definition_path = f"evidence/artifacts/day-definition-{client}.json"
            definition = {"kind": "owner_working_day_definition", "owner": "fixture-owner", "period": "one_working_day",
                          "definition_id": "fixture-booked-day", "time_zone": "America/New_York", "working_date": "2026-10-06",
                          "local_since": "2026-10-06T09:00:00-04:00", "local_until": "2026-10-06T17:00:00-04:00",
                          "window": copy.deepcopy(window)}
            self.source_documents[definition_path] = definition
            definition_ref = self.source_ref(definition_path, "")
            qualification_path = f"evidence/artifacts/day-definition-qualification-{client}.json"
            qualification = {**common, "pin": "1.0.0", "component_ids": row["component_ids"], "scope": "Qualified fixture day definition",
                             "kind": "working_day_definition_qualification", "owner": "fixture-owner", "result": "accepted",
                             "evidence_class": "source_review", "definition_ref": definition_ref, "qualified_at_utc": "2026-10-06T12:00:00Z"}
            self.source_documents[qualification_path] = qualification
            invoke_map_path = f"evidence/artifacts/invoke-map-{client}.json"
            emitter_path = f"evidence/artifacts/native-emitter-{client}.json"
            client_repo = "https://github.com/anthropics/claude-code" if client == "claude" else "https://github.com/openai/codex"
            self.source_documents[emitter_path] = {"kind": "native_counter_source", "client": client, "client_version": "1.0.0",
                "channel": "hook", "counter_type": counter_type, "event_kind": "hook_execution", "documentation": {
                    "repository": client_repo, "commit": "e" * 40, "path": "README.md", "start_line": 20, "end_line": 20,
                    "url": client_repo + "/blob/" + "e" * 40 + "/README.md#L20"}}
            self.source_documents[invoke_map_path] = {**{k: v for k, v in common.items() if k != "window"},
                "kind": "owner_native_invoke_map", "owner": "fixture-owner", "counter_source_ref": self.source_ref(emitter_path, "")}
            self.source_documents[policy_path] = {**common, "kind": "native_tool_working_day_policy", "owner": "fixture-owner",
                "period": "one_working_day", "definition_ref": definition_ref,
                "definition_qualification_ref": self.external_evidence_ref(qualification_path, qualification),
                "invoke_map_ref": self.source_ref(invoke_map_path, "")}
            self.source_documents[counter_path] = {**common, "kind": "native_channel_counter", "organic_invocations": 3,
                                                   "requested": False, "smoke_harness": False,
                "excluded_smoke_sessions": ["1" * 64, "2" * 64], "component_ids": row["component_ids"], "scope": "Original native counters",
                "evidence_class": "local_integration", "event_kind": "hook_execution"}
            policy_ref = self.source_ref(policy_path, "")
            coverage_path = f"evidence/artifacts/day-coverage-{client}.json"
            coverage = {**common, "kind": "owner_working_day_coverage", "owner": "fixture-owner", "pin": "1.0.0",
                        "component_ids": row["component_ids"], "scope": "Original qualified-day coverage", "evidence_class": "local_integration",
                        "policy_ref": policy_ref, "definition_ref": definition_ref, "observed_until": window["until"]}
            self.source_documents[coverage_path] = coverage
            report = {**{key: value for key, value in common.items() if key != "component_pin"},
                      "kind": "native_tool_daily_invoke_report", "owner": "fixture-owner", "pin": "1.0.0",
                      "component_ids": row["component_ids"], "evidence_class": "local_integration", "scope": "Source-declared daily native counters",
                      "generated_at": "2026-10-06T21:01:00Z", "observed_until": "2026-10-06T21:00:00Z",
                      "policy_ref": policy_ref, "organic_invocations": 3, "directed_smoke_invocations": 2,
                      "unknown_invocations": 0, "result": "observed", "source_refs": [self.source_ref(counter_path, "")]}
            report["source_refs"] = [self.external_evidence_ref(counter_path, self.source_documents[counter_path])]
            report["coverage_ref"] = self.external_evidence_ref(coverage_path, coverage)
            self.source_documents[report_path] = report
            cell["daily_report"] = {"status": "recorded", "reason": None, "policy_ref": policy_ref,
                                    "report_ref": self.external_evidence_ref(report_path, report)}
        row["evidence_classes"] = ["metadata_only", "synthetic", "native_proven", "local_integration", "source_review"]
        row["adoption_status"] = "adopted"
        self.refresh_chain()

    def refresh_chain(self):
        # Context/policy/counter artifacts are separate from the report holding
        # their hashes: no self-referential source digest is constructed.
        for client in ("claude", "codex"):
            path = f"evidence/artifacts/day-report-{client}.json"
            if path not in self.source_documents:
                continue
            report = self.source_documents[path]
            policy_path = f"evidence/artifacts/day-policy-{client}.json"
            policy = self.source_documents[policy_path]
            definition_path = f"evidence/artifacts/day-definition-{client}.json"
            qualification_path = f"evidence/artifacts/day-definition-qualification-{client}.json"
            qualification = self.source_documents[qualification_path]
            qualification["definition_ref"] = self.source_ref(definition_path, "")
            policy["definition_ref"] = self.source_ref(definition_path, "")
            policy["definition_qualification_ref"] = self.external_evidence_ref(qualification_path, qualification)
            invoke_map_path = f"evidence/artifacts/invoke-map-{client}.json"
            self.source_documents[invoke_map_path]["counter_source_ref"] = self.source_ref(f"evidence/artifacts/native-emitter-{client}.json", "")
            policy["invoke_map_ref"] = self.source_ref(invoke_map_path, "")
            report["policy_ref"] = self.source_ref(f"evidence/artifacts/day-policy-{client}.json", "")
            counter_path = f"evidence/artifacts/day-counter-{client}.json"
            report["source_refs"] = [self.external_evidence_ref(counter_path, self.source_documents[counter_path])]
            coverage_path = f"evidence/artifacts/day-coverage-{client}.json"
            coverage = self.source_documents[coverage_path]
            coverage["policy_ref"] = report["policy_ref"]
            coverage["definition_ref"] = policy["definition_ref"]
            report["coverage_ref"] = self.external_evidence_ref(coverage_path, coverage)
            context_path = f"evidence/artifacts/fresh-context-{client}.json"
            target = self.packet["data"]["proofs"][client + "-smoke"]
            target["context_proof_ref"] = self.external_evidence_ref(context_path, self.source_documents[context_path])
            event_path = f"evidence/artifacts/native-execution-{client}.json"
            target["native_execution_ref"] = self.external_evidence_ref(event_path, self.source_documents[event_path])
        self.refresh_refs()

    def chain_check(self):
        with patch.object(SelectionEvidence, "qualified_organic_records", return_value=self.owner_records):
            return self.check()

    def chain_invalid(self, fragment):
        with patch.object(SelectionEvidence, "qualified_organic_records", return_value=self.owner_records):
            self.assert_invalid(fragment)

    def test_adoption_requires_complete_native_chain_with_owner_declared_day(self):
        self.wiring_chain()
        self.assertEqual(self.chain_check()["repositories"], 4)
        self.default_row()["organic"][0]["daily_report"].update(status="unknown", reason="Owner day not complete.", policy_ref=None, report_ref=None)
        self.chain_invalid("adoption requires both clients")

    def test_vendor_instruction_path_needs_full_native_chain_and_names_only_readback(self):
        self.wiring_chain(instruction_path=True)
        self.assertEqual(self.chain_check()["repositories"], 4)
        self.packet["data"]["readbacks"]["claude"]["names"] = []
        self.refresh_chain()
        self.chain_invalid("expected nonempty array")

    def test_missing_vendor_path_and_readback_values_do_not_establish_wiring(self):
        self.wiring_chain()
        vendor = self.packet["data"]["vendors"]["claude"]
        vendor["integration_path"] = "other-native-route"
        self.refresh_chain()
        self.chain_invalid("vendor integration pin/path/channel mismatch")
        vendor["integration_path"] = "vendor-hook-install"
        self.packet["data"]["readbacks"]["claude"]["names_only"] = False
        self.refresh_chain()
        self.chain_invalid("native readback must carry names only")

    def test_stale_tool_pin_or_client_version_cannot_qualify_native_integration(self):
        self.wiring_chain()
        vendor = self.packet["data"]["vendors"]["claude"]
        for key, value, fragment in (("component_pin", "0.9.0", "selected repository/pin mismatch"),
                                     ("client_version", "0.9.0", "consuming client version mismatch")):
            original = vendor[key]
            vendor[key] = value
            self.refresh_chain()
            self.chain_invalid(fragment)
            vendor[key] = original

    def test_reused_or_tool_named_task_context_cannot_supply_fresh_smoke(self):
        self.wiring_chain()
        context = self.source_documents["evidence/artifacts/fresh-context-claude.json"]
        for key, value, fragment in (("fresh_session", False, "fresh consuming-client session"),
                                     ("task_prompt_named_tool", True, "must not name the tool"),
                                     ("extra_task_harness_named_tool", True, "must not name the tool")):
            original = context[key]
            context[key] = value
            self.refresh_chain()
            self.chain_invalid(fragment)
            context[key] = original

    def test_hook_integration_cannot_use_mcp_only_counter_report(self):
        self.wiring_chain()
        counter = self.source_documents["evidence/artifacts/day-counter-claude.json"]
        counter["channel"] = "mcp"
        counter["counter_type"] = "mcp_tool_result"
        self.refresh_chain()
        self.chain_invalid("raw counter uses wrong native channel")

    def test_zero_unknown_and_short_snapshot_daily_results_cannot_adopt(self):
        self.wiring_chain()
        counter = self.source_documents["evidence/artifacts/day-counter-claude.json"]
        report = self.source_documents["evidence/artifacts/day-report-claude.json"]
        for count, result in ((0, "defect"), (None, "unknown")):
            counter["organic_invocations"] = report["organic_invocations"] = count
            report["result"] = result
            self.refresh_chain()
            self.chain_invalid("adoption requires both clients")
        counter["organic_invocations"] = report["organic_invocations"] = 3
        report["result"] = "observed"
        report["window"] = {"since": "2026-10-06T19:00:00Z", "until": "2026-10-06T21:00:00Z"}
        self.refresh_chain()
        self.chain_invalid("complete source-declared working-day window")

    def test_report_creation_timestamp_does_not_prove_window_completion(self):
        self.wiring_chain()
        report = self.source_documents["evidence/artifacts/day-report-claude.json"]
        report["observed_until"] = "2026-10-06T20:00:00Z"
        self.refresh_chain()
        self.chain_invalid("creation does not establish completion")

    def test_daily_window_before_smoke_and_directed_smoke_counts_reject(self):
        self.wiring_chain()
        policy = self.source_documents["evidence/artifacts/day-policy-claude.json"]
        policy["window"]["since"] = "2026-10-06T09:00:00Z"
        definition = self.source_documents["evidence/artifacts/day-definition-claude.json"]
        definition["window"]["since"] = "2026-10-06T09:00:00Z"
        definition["local_since"] = "2026-10-06T05:00:00-04:00"
        self.source_documents["evidence/artifacts/day-definition-qualification-claude.json"]["qualified_at_utc"] = "2026-10-06T08:00:00Z"
        self.refresh_chain()
        self.chain_invalid("daily window must follow both clients")
        policy["window"]["since"] = "2026-10-06T13:00:00Z"
        definition["window"]["since"] = "2026-10-06T13:00:00Z"
        definition["local_since"] = "2026-10-06T09:00:00-04:00"
        self.source_documents["evidence/artifacts/day-counter-claude.json"]["requested"] = True
        self.refresh_chain()
        self.chain_invalid("cannot masquerade as organic daily use")

    def test_synthetic_fresh_context_and_bool_only_day_claim_cannot_adopt(self):
        self.wiring_chain()
        context = self.source_documents["evidence/artifacts/fresh-context-claude.json"]
        context["evidence_class"] = "synthetic"
        self.refresh_chain()
        self.chain_invalid("adoption requires both clients")
        context["evidence_class"] = "native_proven"
        policy = self.source_documents["evidence/artifacts/day-policy-claude.json"]
        del policy["window"]
        policy["working_day_complete"] = True
        self.refresh_chain()
        self.chain_invalid("unknown fields")

    def test_unrelated_registration_names_cannot_prove_vendor_wiring(self):
        self.wiring_chain()
        self.packet["data"]["readbacks"]["claude"]["names"] = ["unrelated-hook"]
        self.refresh_chain()
        self.chain_invalid("vendor-required registration identities")

    def test_version_only_smoke_cannot_borrow_original_native_path_event(self):
        self.wiring_chain()
        self.packet["data"]["proofs"]["claude-smoke"]["commands"][0]["cmd"] = "fixture --version"
        self.refresh_chain()
        self.chain_invalid("native path execution proof differs from actual returned smoke")

    def test_relabelled_two_hour_window_cannot_override_original_qualified_day(self):
        self.wiring_chain()
        for name in ("day-policy", "day-counter", "day-report"):
            self.source_documents[f"evidence/artifacts/{name}-claude.json"]["window"] = {
                "since": "2026-10-06T19:00:00Z", "until": "2026-10-06T21:00:00Z"}
        self.refresh_chain()
        self.chain_invalid("original owner's working-day definition")

    def test_mutually_relabelled_mcp_metric_cannot_override_original_invoke_map(self):
        self.wiring_chain()
        for name in ("day-policy", "day-counter", "day-report"):
            self.source_documents[f"evidence/artifacts/{name}-claude.json"]["counter_type"] = "mcp_tool_result"
        self.refresh_chain()
        self.chain_invalid("original owner invoke-map")

    def test_synthetic_raw_counters_cannot_qualify_local_daily_report(self):
        self.wiring_chain()
        self.source_documents["evidence/artifacts/day-counter-claude.json"]["evidence_class"] = "synthetic"
        self.refresh_chain()
        self.chain_invalid("adoption requires both clients")

    def test_local_state_install_wiring_readbacks_keep_class_and_can_prove_state(self):
        self.wiring_chain()
        for client in ("claude", "codex"):
            readback = self.packet["data"]["readbacks"][client]
            readback["evidence_class"] = "local_integration"
            carrier = next(value for value in self.default_row()["install_smoke"] if value["client"] == client)
            carrier["integration"]["readback_refs"][0]["evidence_class"] = "local_integration"
            for stage, field in (("install", "installation"), ("wiring", "wiring")):
                self.packet["data"]["proofs"][client + "-" + stage]["evidence_class"] = "local_integration"
                carrier[field]["evidence_refs"][0]["evidence_class"] = "local_integration"
        self.refresh_chain()
        self.assertEqual(self.chain_check()["repositories"], 4)

    def test_smoke_must_follow_original_installation_and_wiring_completion(self):
        self.wiring_chain()
        self.packet["data"]["proofs"]["claude-install"]["observed_at_utc"] = "2026-10-06T12:00:00Z"
        self.refresh_chain()
        self.chain_invalid("installation/wiring must complete before native readback")

    def test_synthetic_definition_qualification_cannot_qualify_a_native_day(self):
        self.wiring_chain()
        self.source_documents["evidence/artifacts/day-definition-qualification-claude.json"]["evidence_class"] = "synthetic"
        self.refresh_chain()
        self.chain_invalid("working-day qualification origin cannot be synthetic")

    def test_emitter_full_commit_and_url_must_match_known_client_source_pin(self):
        self.wiring_chain()
        doc = self.source_documents["evidence/artifacts/native-emitter-codex.json"]["documentation"]
        doc["commit"] = "f" * 40
        doc["url"] = doc["repository"] + "/blob/" + doc["commit"] + "/README.md#L20"
        self.refresh_chain()
        self.chain_invalid("documentation commit differs from the canonical client source pin")

    def test_unmapped_client_source_pin_keeps_daily_evidence_nonadopted(self):
        self.wiring_chain()
        component = next(component for component in self.stack["components"] if component["id"] == "codex")
        del component["source_pin"]
        self.chain_invalid("adoption requires both clients")
        self.default_row()["adoption_status"] = "recommendation"
        self.assertEqual(self.chain_check()["repositories"], 4)

    def test_all_declared_carrier_fields_are_required_and_typos_reject(self):
        row = self.default_row()
        carriers = [self.document, self.document["slots"][0], row, row["source"], row["install_smoke"][0],
                    row["install_smoke"][0]["smoke"], row["organic"][0], row["refutations"][0], row["audit"],
                    row["overturn"], row["source"]["release_ref"],
                    self.document["slots"][1]["repositories"][2]["exclusion"]]
        optional = {"language", "supported_languages"}
        for carrier in carriers:
            for key in list(carrier):
                if key in optional:
                    continue
                with self.subTest(field=key, carrier_keys=sorted(carrier)):
                    value = carrier.pop(key)
                    try:
                        self.assert_invalid("missing fields|expected nonempty text|expected one of")
                    finally:
                        carrier[key] = value
            carrier["misspelled_contract_field"] = True
            try:
                self.assert_invalid("unknown fields")
            finally:
                del carrier["misspelled_contract_field"]

    def test_component_repository_version_and_source_pin_are_bound(self):
        component = self.stack["components"][0]
        for key, value, fragment in (("repository", SDK, "component repository"),
                                     ("version", "2.0.0", "component pin"),
                                     ("source_pin", "e" * 40, "component source commit")):
            with self.subTest(key=key):
                original = component[key]
                component[key] = value
                try:
                    self.assert_invalid(fragment)
                finally:
                    component[key] = original

    def test_selected_release_pin_commit_date_and_clean_flag_are_bound(self):
        source = self.default_row()["source"]
        for key, value, fragment in (("release_pin", "2.0.0", "selected release pin"),
                                     ("commit", "e" * 40, "selected release commit"),
                                     ("release_date", "2026-10-02", "selected release date"),
                                     ("clean_release", False, "clean-release declaration")):
            with self.subTest(key=key):
                original = source[key]
                source[key] = value
                try:
                    self.assert_invalid(fragment)
                finally:
                    source[key] = original
        source.update(status="unknown", reason="Official release not verified.")
        self.assert_invalid("default requires known official selected release")

    def test_snapshot_release_joins_actual_tag_commit_without_using_commit_date(self):
        target = copy.deepcopy(self.source_documents["manifests/landscape.json"]["current_core_releases"][0])
        del target["source_commit"]
        path = "catalogs/landscape/upstream-snapshot.json"
        component = {"repository": RESEARCH, "latest_stable_release": target,
                     "latest_release_source": {"ref": "v1.0.0", "sha": self.release_commit},
                     "selected_pin_source": {"sha": self.release_commit, "committed_at": "2026-09-30T00:00:00Z"}}
        self.source_documents[path] = {"schema_version": 1, "components": [component]}
        self.default_row()["source"]["release_ref"] = self.source_ref(path, "/components/0/latest_stable_release")
        self.assertEqual(self.check()["repositories"], 4)
        component["latest_release_source"]["ref"] = "v2.0.0"
        self.refresh_refs()
        self.assert_invalid("latest-release commit source names a different tag")

    def test_candidate_can_defer_release_without_becoming_installed(self):
        row = self.document["slots"][1]["repositories"][1]
        row["source"].update(status="deferred", reason="Release API metadata not retained.", vendor_official=None,
                            release_ref=None, release_date=None, clean_release=None)
        row["evidence_classes"] = ["source_review"]
        self.assertEqual(self.check()["repositories"], 4)
        self.assertEqual(row["component_ids"], [])

    def test_candidate_binding_and_origin_cannot_be_unrelated_or_star_only(self):
        candidate = self.source_documents["catalogs/us-equities/decision-index.json"]["records"][0]
        candidate["repository"] = SDK
        self.refresh_refs()
        self.assert_invalid("candidate repository mismatch")
        candidate["repository"] = ALTERNATIVE
        candidate["references"][0]["kind"] = "public_star"
        self.refresh_refs()
        self.assert_invalid("not public-star-only discovery")

    def test_unknown_or_misbound_registered_receipt_and_pointer_reject(self):
        ref, _ = self.add_smoke()
        for key, value, fragment in (("receipt_id", "not-registered", "unknown registered receipt ID"),
                                     ("pointer", "/data/no-such-object", "does not resolve"),
                                     ("sha256", "e" * 64, "reference hash differs"),
                                     ("scope", "Other scope", "evidence scope differs"),
                                     ("evidence_class", "native_proven", "evidence class differs")):
            with self.subTest(key=key):
                original = ref[key]
                ref[key] = value
                try:
                    self.assert_invalid(fragment)
                finally:
                    ref[key] = original

    def test_unrelated_registered_child_artifact_cannot_borrow_parent_coverage(self):
        ref, target = self.add_smoke()
        path = "evidence/artifacts/unrelated-child.json"
        self.source_documents[path] = {"target": copy.deepcopy(target)}
        ref.update(self.source_ref(path, "/target"))
        self.assert_invalid("artifact is not a declared child")
        self.packet["data"]["artifacts"] = [{"path": path}]
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)
        self.source_documents[path]["target"]["component_ids"] = ["fixture-sdk"]
        self.refresh_refs()
        self.assert_invalid("pointed source does not cover selected components")

    def test_native_operation_keeps_client_role_layer_stage_pin_and_completion(self):
        _, target = self.add_smoke()
        for key, value, fragment in (("client", "codex", "consumer client/stage"),
                                     ("stage", "install", "consumer client/stage"),
                                     ("role", "other-role", "functional role/layer"),
                                     ("layer_id", "workers", "functional role/layer"),
                                     ("pin", "2.0.0", "pointed source pin")):
            with self.subTest(key=key):
                original = target[key]
                target[key] = value
                self.refresh_refs()
                try:
                    self.assert_invalid(fragment)
                finally:
                    target[key] = original
                    self.refresh_refs()
        target["commands"][0]["exit"] = 1
        self.refresh_refs()
        self.assert_invalid("passed evidence contains a failed command")
        target["result"] = "fail"
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)

    def test_synthetic_smoke_cannot_supply_adoption_or_self_asserted_classes(self):
        self.add_smoke()
        row = self.default_row()
        row["evidence_classes"].append("native_proven")
        self.assert_invalid("evidence classes must equal resolved canonical classes")
        row["evidence_classes"].remove("native_proven")
        row["adoption_status"] = "adopted"
        self.assert_invalid("adoption requires both clients")

    def test_undated_or_unbound_exclusion_rejects(self):
        value = self.document["slots"][1]["repositories"][2]["exclusion"]
        value["date"] = None
        self.assert_invalid("expected nonempty text")
        value["date"] = "2026-10-02"
        self.assert_invalid("exclusion differs from dated canonical evidence")

    def test_four_family_role_carriers_need_original_bound_judgments(self):
        self.add_refuters()
        self.assertEqual(self.check()["repositories"], 4)
        carrier = self.default_row()["refutations"][0]
        carrier["judgment_refs"].pop()
        carrier["result"].pop()
        self.assert_invalid("recorded refuter lacks canonical replicated judgments")

    def test_refuter_source_field_repository_family_and_result_mismatch_reject(self):
        self.add_refuters()
        doc = self.packet["data"]["judgments"]["claude-facts-1"]
        doc["judgment"]["source_field_sha256"] = "e" * 64
        self.refresh_refs()
        self.assert_invalid("malformed/unbound canonical refuter")
        doc["judgment"]["source_field_sha256"] = self.packet["data"]["fields"]["research"]["field_sha256"]
        doc["judgment"]["family"] = "gpt6"
        self.refresh_refs()
        self.assert_invalid("refuter role/family mismatch")
        doc["judgment"]["family"] = "claude"
        self.default_row()["refutations"][0]["result"][0]["status"] = "not_credible"
        self.refresh_refs()
        self.assert_invalid("refuter result differs from original")

    def test_old_pin_or_other_role_refuters_cannot_qualify_current_selection(self):
        from scripts.saturation_ledger import canonical, v2_field_sha256
        self.add_refuters()
        source = self.packet["data"]["fields"]["research"]
        for key, value in (("pin", "0.9.0"), ("role", "other-worker")):
            with self.subTest(key=key):
                original = source["requirement"]["selection"][key]
                source["requirement"]["selection"][key] = value
                source["requirement_sha256"] = hashlib.sha256(canonical(source["requirement"])).hexdigest()
                source["field_sha256"] = v2_field_sha256(source)
                for doc in self.packet["data"]["judgments"].values():
                    doc["judgment"]["source_field_sha256"] = source["field_sha256"]
                self.refresh_refs()
                self.assert_invalid("reviewed input selected pin/commit/functional role mismatch")
                for carrier in self.default_row()["refutations"]:
                    carrier["status"] = "observed"
                self.assertEqual(self.check()["repositories"], 4)
                for carrier in self.default_row()["refutations"]:
                    carrier["status"] = "recorded"
                source["requirement"]["selection"][key] = original

    def test_real_host_envelope_shape_is_preserved_as_unqualified_observation(self):
        row = self.default_row()
        cid = row["component_ids"][0]
        target = {"schema_version": 1, "id": "fixture-host-20261006--fixture-research--use--20261006",
                  "kind": "host_acceptance", "component_id": cid, "stage": "use",
                  "host": {"host_id": "fixture-host-20261006", "platform_id": "linux", "os": "linux",
                           "architecture": "x86_64", "second_physical_machine": False},
                  "catalog_revision": self.base_commit, "tool_versions": {cid: "1.0.0"},
                  "observed_at_utc": "2026-10-06T00:00:00Z", "result": "pass",
                  "claim": "Synthetic host-shaped operation; no consuming-client qualification.",
                  "limitations": ["Synthetic fixture; no real host acceptance."], "evidence_class": "synthetic",
                  "commands": [{"cmd": "fixture operation", "exit": 0, "duration_s": 0.1,
                                "output_excerpt": "Synthetic original host output", "output_sha256": "b" * 64}], "reviews": []}
        path = "evidence/hosts/fixture-host-20261006/fixture-use.json"
        self.source_documents[path] = target
        ref = {**self.source_ref(path, ""), "receipt_id": target["id"], "evidence_class": "synthetic", "scope": target["claim"]}
        row["install_smoke"][0]["smoke"] = {"status": "observed", "reason": None, "evidence_refs": [ref]}
        row["evidence_classes"].append("synthetic")
        self.assertEqual(self.check()["repositories"], 4)
        self.assertNotIn("repository", target)
        self.assertNotIn("pin", target)
        command = target["commands"][0]
        for actual, expected in ((1, 1), (0, 1)):
            with self.subTest(actual_exit=actual, expected_exit=expected):
                command.update(exit=actual, expected_exit=expected)
                ref.update(self.source_ref(path, ""))
                if actual == expected:
                    self.assertEqual(self.check()["repositories"], 4)
                else:
                    self.assert_invalid("passed evidence contains a failed command")
        command.update(exit=0, expected_exit=True)
        ref.update(self.source_ref(path, ""))
        self.assert_invalid("expected exit code must be an integer")
        del command["expected_exit"]
        ref.update(self.source_ref(path, ""))
        row["install_smoke"][0]["smoke"]["status"] = "recorded"
        self.assert_invalid("consumer client/stage scope mismatch")

    def test_organic_owner_shape_joins_task_scope_and_preserves_missing_owner(self):
        row, slot = self.default_row(), self.document["slots"][0]
        slot["task_scope"] = "One source-retrieval fixture"
        # Canonical #750 properties: component_pin, task_scope, client.id and
        # layer_ids; the owner schema deliberately has no repository/pin/role.
        target = {"component_id": row["component_ids"][0], "component_pin": "1.0.0",
                  "task_scope": slot["task_scope"], "client": {"id": "claude-code"}, "arm": "native",
                  "layer_ids": [slot["layer_id"]], "evidence_class": "synthetic", "verdict": None}
        self.packet["data"]["organic_use"] = {"records": [target]}
        cell = next(cell for cell in row["organic"] if cell["client"] == "claude" and cell["arm"] == "native")
        cell.update(status="observed", reason=None, task_scope=slot["task_scope"], evidence_refs=[
            self.evidence_ref("/data/organic_use/records/0", {**target, "scope": target["task_scope"]})])
        row["evidence_classes"].append("synthetic")
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)
        cell["status"] = "recorded"
        self.assert_invalid("canonical organic owner/validator is unavailable")

    def test_audit_grade_is_dated_bound_and_never_native_acceptance(self):
        row = self.default_row()
        target = {"repository": RESEARCH, "pin": "1.0.0", "component_ids": row["component_ids"],
                  "evidence_class": "synthetic", "scope": "Owner audit lead", "grade": "A",
                  "origin": "Synthetic owner audit", "date": "2026-10-01",
                  "limitations": ["Lead only; neither refutation nor execution."], "lead_only": True}
        self.packet["data"]["audits"]["research"] = target
        row["audit"] = {"status": "recorded", "reason": None,
                        **{key: copy.deepcopy(target[key]) for key in ("grade", "origin", "date", "limitations", "lead_only")},
                        "evidence_refs": [self.evidence_ref("/data/audits/research", target)]}
        row["evidence_classes"].append("synthetic")
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)
        row["audit"]["lead_only"] = False
        self.assert_invalid("audit grade is a lead only")
        row["audit"]["lead_only"] = True
        row["audit"]["grade"] = "B"
        self.assert_invalid("audit differs from its canonical source")

    def test_overturn_comparison_binds_fixture_metric_arms_and_trigger(self):
        row = self.default_row()
        fixture = self.source_documents["fixtures/comparison.json"]
        comparison = {"fixture": {"path": "fixtures/comparison.json", "sha256": hashlib.sha256(json.dumps(fixture).encode()).hexdigest()},
                      "metric": {"name": "quality", "direction": "maximize"},
                      "arms": [{"repository": RESEARCH, "pin": "1.0.0"}, {"repository": ALTERNATIVE, "pin": "1.0.0"}],
                      "trigger": {"metric": "quality", "operator": "gt", "threshold": 0.95}}
        self.packet["data"]["comparisons"]["research"] = comparison
        row["overturn"] = {"status": "recorded", "reason": None,
                           "fixture_ref": self.source_ref(self.packet_path, "/data/comparisons/research/fixture"),
                           "metric_ref": self.source_ref(self.packet_path, "/data/comparisons/research/metric"),
                           "arms": [{**arm, "source_ref": self.source_ref(self.packet_path, f"/data/comparisons/research/arms/{index}")}
                                    for index, arm in enumerate(comparison["arms"])],
                           "trigger_ref": self.source_ref(self.packet_path, "/data/comparisons/research/trigger")}
        row["evidence_classes"].append("synthetic")
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)
        comparison["trigger"]["metric"] = "latency"
        self.refresh_refs()
        self.assert_invalid("comparison trigger metric mismatch")

    def test_prior_pin_failures_remain_valid_supersession_evidence(self):
        row = self.default_row()
        scope = "One prior fixture operation"
        prior = {"role": self.document["slots"][0]["role"], "repository": RESEARCH, "pin": "0.9.0",
                 "commit": "9" * 40, "component_ids": row["component_ids"], "checked_at": "2026-09-01", "scope": scope}
        retained = {"repository": RESEARCH, "pin": "0.9.0", "component_ids": row["component_ids"],
                    "evidence_class": "synthetic", "scope": scope, "result": "fail"}
        self.packet["data"]["prior_decision"] = prior
        self.packet["data"]["prior_failure"] = retained
        row["supersedes"] = [{"date": "2026-09-01", "scope": scope, "reason": "Retain original failed condition.",
                             "decision_ref": self.source_ref(self.packet_path, "/data/prior_decision"),
                             "receipt_refs": [self.evidence_ref("/data/prior_failure", retained)]}]
        row["evidence_classes"].append("synthetic")
        self.refresh_refs()
        self.assertEqual(self.check()["repositories"], 4)
        retained["pin"] = "0.8.0"
        self.refresh_refs()
        self.assert_invalid("pointed source pin mismatch")
        retained["pin"] = "0.9.0"
        row["supersedes"][0]["scope"] = "Wrong prior scope"
        self.refresh_refs()
        self.assert_invalid("supersession scope differs from prior canonical decision")

    def write(self, relative, value):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = value if isinstance(value, str) else json.dumps(value)
        target.write_text(content, encoding="utf-8")

    def save(self):
        self.write(MANIFEST, self.manifest)
        self.write(REPOSITORY_COVERAGE, self.coverage)
        self.write(FINALIZED_SELECTION, self.document)
        for path, value in self.source_documents.items():
            self.write(path, value)
        self.write("manifests/stack.json", self.stack)
        self.write("manifests/evidence.json", self.registry())

    def check(self):
        self.save()
        return validate_finalized_selection(self.root)

    def assert_invalid(self, fragment):
        with self.assertRaisesRegex(InvalidCatalog, fragment):
            self.check()

    def test_valid_final_includes_alternatives_exclusions_and_repeated_references(self):
        self.assertEqual(self.check(), {"status": "finalized", "slots": 2, "repositories": 4})
        del self.document["slots"][1]["supported_languages"]
        self.assertEqual(self.check()["repositories"], 4)

    def test_valid_pending_has_no_selections_or_claimed_census(self):
        self.document["status"] = "pending_synthesis"
        self.document["included_repositories"] = None
        for row in self.document["slots"]:
            row["repositories"] = []
        self.assertEqual(self.check(), {"status": "pending_synthesis", "slots": 2, "repositories": None})

    def test_legacy_manifest_does_not_opt_into_the_new_selection_contract(self):
        self.assertIsNone(validate_finalized_selection(self.root, {}))

    def test_pending_cannot_carry_any_selection_or_nonnull_census(self):
        original = copy.deepcopy(self.document)
        for selection in ("default", "alternative", "excluded"):
            with self.subTest(selection=selection):
                self.document = copy.deepcopy(original)
                self.document["status"] = "pending_synthesis"
                self.document["included_repositories"] = None
                self.document["slots"][0]["repositories"] = [selected(RESEARCH, selection)]
                self.assert_invalid("pending synthesis cannot declare repository selections")
        self.document["included_repositories"] = []
        self.assert_invalid("repository census null")

    def test_missing_and_multiple_defaults_fail(self):
        self.document["slots"][0]["repositories"][0]["selection"] = "alternative"
        self.assert_invalid("exactly one default")
        self.document["slots"][0]["repositories"][0]["selection"] = "default"
        self.document["slots"][1]["repositories"][1]["selection"] = "default"
        self.assert_invalid("exactly one default")

    def test_unknown_repository_selection_cannot_count_as_a_default(self):
        self.document["slots"][0]["repositories"][0]["selection"] = "candidate"
        self.assert_invalid("expected one of alternative, default, excluded")

    def test_duplicate_slot_ids_fail(self):
        self.document["slots"][1]["id"] = "research-worker"
        self.assert_invalid("duplicate ID research-worker")

    def test_repository_cannot_be_owned_twice_within_or_across_slots(self):
        for target_slot in (0, 1):
            with self.subTest(target_slot=target_slot):
                self.document["slots"][target_slot]["repositories"].append(selected(RESEARCH, "alternative"))
                self.assert_invalid("already owned by slot research-worker")
                self.document["slots"][target_slot]["repositories"].pop()

    def test_census_must_be_complete_and_independently_declared(self):
        self.document["included_repositories"].append("https://github.com/vendor/unowned")
        self.assert_invalid(r"unowned=\['vendor/unowned'\]")
        self.document["included_repositories"].pop()
        self.document["included_repositories"].remove(ALTERNATIVE)
        self.assert_invalid(r"outside_census=\['vendor/sdk-alternative'\]")
        del self.document["included_repositories"]
        self.assert_invalid("missing fields")

    def test_case_and_alias_collisions_fail_in_both_ownership_and_census(self):
        for spelling in ("https://github.com/Vendor/SDK", "https://github.com/old/sdk"):
            with self.subTest(spelling=spelling, declaration="ownership"):
                duplicate = copy.deepcopy(self.document["slots"][1]["repositories"][0])
                duplicate.update(repository=spelling, selection="alternative")
                self.document["slots"][0]["repositories"].append(duplicate)
                self.assert_invalid("already owned by slot")
                self.document["slots"][0]["repositories"].pop()
            with self.subTest(spelling=spelling, declaration="census"):
                self.document["included_repositories"].append(spelling)
                self.assert_invalid("duplicate canonical repository vendor/sdk")
                self.document["included_repositories"].pop()

    def test_alias_reference_resolves_without_becoming_another_owner(self):
        self.document["slots"][0]["references"].append("https://github.com/old/sdk")
        self.assertEqual(self.check()["repositories"], 4)

    def test_reference_outside_the_final_census_fails(self):
        self.document["slots"][0]["references"].append("https://github.com/vendor/unknown")
        self.assert_invalid("reference outside included repository census")

    def test_duplicate_json_keys_remain_rejected(self):
        self.save()
        self.write(FINALIZED_SELECTION, '{"schema_version": 1, "status": "finalized", "status": "pending_synthesis"}')
        with self.assertRaisesRegex(InvalidCatalog, "duplicate key status"):
            validate_finalized_selection(self.root)

    def test_nonobject_document_roots_raise_invalid_catalog(self):
        self.save()
        for value in (None, False, 0, "scalar", [], [{}]):
            with self.subTest(value=value):
                self.write(FINALIZED_SELECTION, json.dumps(value))
                with self.assertRaisesRegex(InvalidCatalog, "expected object"):
                    validate_finalized_selection(self.root)

    def test_noncanonical_repository_urls_fail(self):
        for value in ("http://github.com/vendor/research", "https://github.com/vendor/research.git",
                      "https://github.com/vendor/research.GIT", "https://github.com/vendor/research.GiT",
                      "https://github.com/vendor/research?view=1", "https://github.com/vendor/research#readme",
                      "https://github.com/vendor/research/issues"):
            with self.subTest(value=value):
                self.document["included_repositories"][0] = value
                self.assert_invalid("HTTPS URL|canonical https")

    def test_malformed_document_and_slot_stages_fail(self):
        original = copy.deepcopy(self.document)
        mutations = [
            ("schema_version", True, "schema_version must be 1"),
            ("status", "accepted", "expected one of"),
            ("source_base_commit", "e28d0eec", "full lowercase Git commit SHA"),
            ("included_repositories", None, "expected nonempty array"),
            ("slots", [], "expected nonempty array"),
            ("slots", ["bad-slot"], "expected object"),
        ]
        for key, value, fragment in mutations:
            with self.subTest(field=key, value=value):
                self.document = copy.deepcopy(original)
                self.document[key] = value
                self.assert_invalid(fragment)
        for key, value, fragment in [
            ("layer_id", "unknown", "expected one of"),
            ("role", "", "expected nonempty text"),
            ("purpose", None, "expected nonempty text"),
            ("language", None, "expected nonempty text"),
            ("supported_languages", [], "expected nonempty array"),
            ("supported_languages", ["python", "python"], "duplicate values"),
            ("supported_languages", [None], "expected nonempty text"),
            ("repositories", [False], "expected object"),
            ("references", {}, "expected array"),
        ]:
            with self.subTest(slot_field=key, value=value):
                self.document = copy.deepcopy(original)
                self.document["slots"][0][key] = value
                self.assert_invalid(fragment)

    def test_projection_and_decision_paths_keep_existing_confinement_checks(self):
        self.manifest["finalized_selection_file"] = "../selection.json"
        self.assert_invalid("canonical selection file")
        self.manifest["finalized_selection_file"] = FINALIZED_SELECTION
        self.document["decision_record"] = "../decision.md"
        self.assert_invalid("canonical, relative and confined")

    def test_existing_foundation_validator_reaches_the_opt_in_guard(self):
        fixture = foundation_fixtures.FoundationCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.manifest["finalized_selection_file"] = FINALIZED_SELECTION
        fixture.write(MANIFEST, fixture.manifest)
        fixture.write("catalogs/foundation/decisions.json", fixture.decisions)
        fixture.write(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, {})
        fixture.write(FINALIZED_SELECTION, self.document)
        self.copy_sources_to(fixture)
        self.assertEqual(validate_foundation(fixture.root)["layers"], 20)
        self.document["slots"][0]["repositories"] = []
        fixture.write(FINALIZED_SELECTION, self.document)
        with self.assertRaisesRegex(InvalidCatalog, "exactly one default"):
            validate_foundation(fixture.root)

    def test_direct_script_uses_its_own_modules_with_a_foreign_scripts_package(self):
        self.write("scripts/__init__.py", "")
        self.write("scripts/validate_foundation.py", 'raise RuntimeError("foreign validator imported")\n')
        fixture = publication_fixtures.PublicationValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write_json(MANIFEST, self.manifest)
        fixture.write_json(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, "# Synthetic decision\n")
        fixture.write_json(FINALIZED_SELECTION, self.document)
        self.copy_sources_to(fixture)
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        arguments = [sys.executable, str(script), "--root", str(fixture.root)]
        environment = {"PYTHONPATH": str(self.root), "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(arguments, cwd=self.root, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[0])["status"], "passed")
        self.document["slots"][0]["repositories"] = []
        fixture.write_json(FINALIZED_SELECTION, self.document)
        result = subprocess.run(arguments, cwd=self.root, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("exactly one default", result.stdout)

    def test_cold_file_spec_import_exposes_private_patterns_without_catalog_imports(self):
        # Upstream source-file loading recipe, with no repository on sys.path:
        # https://docs.python.org/3.13/library/importlib.html#importing-a-source-file-directly
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        code = """import importlib.util, sys
spec = importlib.util.spec_from_file_location('standalone_publication', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.PRIVATE_CONTENT
assert not any(name == 'validate_foundation' or name.endswith('.validate_foundation') for name in sys.modules)
print('private-patterns:', len(module.PRIVATE_CONTENT))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-I", "-c", code, str(script)], cwd=self.root,
            env={"PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("private-patterns:", result.stdout)

    def test_publication_validator_reaches_guard_and_retains_legacy_counts(self):
        fixture = publication_fixtures.PublicationValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write_json(MANIFEST, self.manifest)
        fixture.write_json(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, "# Synthetic decision\n")
        fixture.write_json(FINALIZED_SELECTION, self.document)
        counts = self.copy_sources_to(fixture)
        self.assertEqual(validate_publication(fixture.root), counts)
        self.document["slots"][0]["repositories"] = []
        fixture.write_json(FINALIZED_SELECTION, self.document)
        with self.assertRaisesRegex(InvalidPublication, "exactly one default"):
            validate_publication(fixture.root)


if __name__ == "__main__":
    unittest.main()
