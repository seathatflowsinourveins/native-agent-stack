#!/usr/bin/env python3
"""Validate FOUNDATION capability references offline, without replaying receipts.

Pins, original claims and lifecycle stage evidence stay in their canonical files.
This checks consistency of the selection, never the truth of a prose assertion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

if __package__:
    from .validate_catalogs import (
        InvalidCatalog, SHA, Validator, dated, enum, https, object_value,
        repository, require, sequence, strings, text,
    )
else:
    from validate_catalogs import (
        InvalidCatalog, SHA, Validator, dated, enum, https, object_value,
        repository, require, sequence, strings, text,
    )


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "catalogs/foundation/manifest.json"
DECISIONS = "catalogs/foundation/decisions.json"
FINALIZED_SELECTION = "catalogs/foundation/finalized-sota-catalog.json"
REPOSITORY_COVERAGE = "catalogs/us-equities/coverage.json"
SOURCES = {
    "components": "manifests/stack.json",
    "evidence": "manifests/evidence.json",
    "lifecycle": "blueprints/token-native-focus/saturation-audit.json",
    "shared_research_inventory": "catalogs/us-equities/decision-index.json",
}
LAYERS = {
    "native-clients", "instructions-skills", "workers", "isolation", "code-navigation",
    "document-retrieval", "semantic-rag", "durable-memory", "web-research",
    "token-efficiency", "quality-evaluation", "ci-supply-chain", "scheduling-supervision",
    "hosting-services", "recovery-portability", "observation-inference",
    "agent-sdks", "mcp-surfaces", "secrets-credentials", "git-github-automation",
}
STAGES = {"install", "use", "persistence", "restart", "cleanup", "recovery"}
STATUSES = {
    "accepted_within_scope", "observed_installed", "partial_acceptance",
    "documented_not_replayed", "not_established", "not_applicable",
}
EXECUTION = {"native_model_e2e", "native_cli_e2e", "artifact_measurement"}


def fields(value, expected, label, *, optional=frozenset()):
    object_value(value, label)
    unknown = value.keys() - expected - optional
    require(not unknown, label, f"unknown fields: {sorted(unknown)}")
    require(not expected - value.keys(), label, f"missing fields: {sorted(expected - value.keys())}")


def indexed(rows, key, label):
    result = {}
    for row in sequence(rows, label):
        object_value(row, label)
        identifier = text(row.get(key), f"{label}.{key}")
        require(identifier not in result, label, f"duplicate ID {identifier}")
        result[identifier] = row
    return result


def source_paths(values, validator, label):
    for path in strings(values, label):
        validator.path(path, label)


class SelectionEvidence:
    """Join projection declarations to canonical, registered source objects.

    Sources at native-agent-stack@6fc39660d458824b7aaf0827d1c6d3ea0ae73453:
    host_receipts.py:204-232,547-574,698-728 (pins/repositories/registration);
    saturation_ledger.py:414-516,538-555 (retained v2 judgments/RFC 6901);
    catalog_decisions.py:178-203 (candidate identities and typed source rows).
    This verifies recorded consistency, not the truth of external observations.
    """

    ROW_FIELDS = {"repository", "selection", "component_ids", "adoption_status", "source",
                  "evidence_classes", "install_smoke", "organic", "refutations", "audit",
                  "exclusion", "overturn", "supersedes"}
    REF_FIELDS = {"path", "pointer", "sha256", "source_commit"}
    EVIDENCE_REF_FIELDS = REF_FIELDS | {"receipt_id", "evidence_class", "scope"}
    CLASSES = {"metadata_only", "source_review", "native_proven", "local_integration", "synthetic"}
    HEX64 = re.compile(r"[0-9a-f]{64}\Z")

    def __init__(self, validator, identity, decision_date):
        if __package__:
            from . import host_receipts, saturation_ledger
        else:
            import host_receipts
            import saturation_ledger
        self.host = host_receipts
        self.saturation = saturation_ledger
        self.validator, self.identity, self.decision_date = validator, identity, decision_date
        self.components = indexed(validator.load(SOURCES["components"]).get("components"), "id", "components")
        registry = validator.load(SOURCES["evidence"])
        self.files = indexed(registry.get("files"), "path", "evidence.files")
        self.receipts = indexed(registry.get("receipts"), "id", "evidence.receipts")
        self.documents = {}
        self.classes = set()

    def document(self, path, label):
        require(path in self.files, label, "source file is not registered")
        entry = self.files[path]
        raw = self.validator.path(path, label).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(entry.get("sha256") == digest, label, "registered source hash differs from actual bytes")
        if path not in self.documents:
            self.documents[path] = self.validator.load(path)
        return self.documents[path], digest

    def reference(self, ref, label, *, evidence=False, binding=None):
        fields(ref, self.EVIDENCE_REF_FIELDS if evidence else self.REF_FIELDS, label)
        require(bool(self.HEX64.fullmatch(text(ref["sha256"], label + ".sha256"))), label, "expected SHA256")
        require(bool(SHA.fullmatch(text(ref["source_commit"], label + ".source_commit"))), label,
                "expected full source commit")
        pointer = ref["pointer"]
        require(isinstance(pointer, str) and (pointer == "" or pointer.startswith("/"))
                and not re.search(r"~(?![01])", pointer), label, "invalid RFC 6901 JSON pointer")
        document, digest = self.document(ref["path"], label)
        require(ref["sha256"] == digest, label, "reference hash differs from registered source")
        try:
            target = document
            for token in pointer.split("/")[1:]:
                if isinstance(target, list):
                    require(bool(re.fullmatch(r"0|[1-9][0-9]*", token)), label, "noncanonical array index")
                target = self.saturation.resolve_pointer(target, "/" + token)
        except self.saturation.LedgerError as error:
            raise InvalidCatalog(f"{label}: {error}") from error
        if not evidence:
            if document.get("evidence_class") is not None:
                self.classes.add(enum(document["evidence_class"], self.CLASSES, label + ".source_class"))
            return target
        object_value(target, label + ".target")
        receipt_id = text(ref["receipt_id"], label + ".receipt_id")
        if receipt_id in self.receipts:
            registered = self.receipts[receipt_id]
            parent, _ = self.document(registered.get("path"), label + ".receipt")
            for key in ("id", "kind", "component_ids", "claim", "limitations"):
                require(parent.get(key) == registered.get(key), label, "receipt registry metadata mismatch")
            if registered["path"] != ref["path"]:
                artifacts = parent.get("artifacts", parent.get("data", {}).get("artifacts", []))
                require(isinstance(artifacts, list), label, "receipt has no declared child artifacts")
                paths = {item.get("path") if isinstance(item, dict) else item
                         for item in artifacts if isinstance(item, (str, dict))}
                require(ref["path"] in paths, label, "artifact is not a declared child of this receipt")
            covered = registered["component_ids"]
        else:
            # Native host receipts are registered in files[], not all in receipts[].
            require(document.get("id") == receipt_id and document.get("kind") == "host_acceptance",
                    label, "unknown registered receipt ID")
            parent, covered = document, [document.get("component_id")]
        level = target.get("evidence_class", document.get("evidence_class"))
        if level is None and parent.get("kind") == "upstream_provenance":
            level = "metadata_only"
        enum(ref["evidence_class"], self.CLASSES, label + ".evidence_class")
        require(level == ref["evidence_class"], label, "evidence class differs from canonical source")
        scope = target.get("scope", target.get("task_scope", target.get("claim")))
        require(text(ref["scope"], label + ".scope") == scope, label, "evidence scope differs from canonical source")
        components = self.row["component_ids"] if binding is None else binding["component_ids"]
        wanted_repo = self.repo if binding is None else self.identity(binding["repository"], label)
        wanted_pin, wanted_commit = (self.pin, self.commit) if binding is None else (binding["pin"], binding.get("commit"))
        require(set(components) <= set(covered), label, "receipt does not cover selected components")
        target_components = target.get("component_ids", [target.get("component_id")])
        require(isinstance(target_components, list), label, "source component scope must be declared")
        require(not components or set(components) <= set(target_components),
                label, "pointed source does not cover selected components")
        repo = target.get("repository")
        pin = target.get("component_pin", target.get("pin"))
        host_envelope = target.get("kind") == "host_acceptance"
        organic_record = bool(re.fullmatch(r"/data/organic_use/records/(0|[1-9][0-9]*)", pointer))
        if repo is None and (host_envelope or organic_record):
            cid = target.get("component_id")
            require(cid in self.components and cid in components, label, "unknown canonical source component")
            normalized = self.host.normalize_repository(self.components[cid].get("repository"))
            require(normalized is not None, label, "source component has no repository identity")
            repo = "https://" + normalized
            if host_envelope:
                pin = self.host.recorded_version(target)
        require(repo is not None and self.identity(repo, label) == wanted_repo, label, "pointed repository scope mismatch")
        if wanted_pin is not None or wanted_commit is not None:
            require(self.host.pin_matches(pin, wanted_pin) or self.host.pin_matches(pin, wanted_commit),
                    label, "pointed source pin mismatch")
        self.classes.add(level)
        return target

    @staticmethod
    def disposition(value, label, *, observed=False):
        choices = {"unknown", "deferred", "recorded"} | ({"observed"} if observed else set())
        status = enum(value["status"], choices, label + ".status")
        if status in {"unknown", "deferred"}:
            text(value["reason"], label + ".reason")
        else:
            require(value["reason"] is None, label, "resolved evidence must keep reason null")
        return status

    def source(self, value, label):
        fields(value, {"status", "reason", "vendor_official", "release_pin", "commit", "release_date", "clean_release",
                       "release_ref", "candidate_binding"}, label)
        status = self.disposition(value, label)
        self.pin, self.commit = value["release_pin"], value["commit"]
        if self.pin is not None:
            text(self.pin, label + ".release_pin")
        if self.commit is not None:
            require(bool(SHA.fullmatch(text(self.commit, label + ".commit"))), label, "release commit must be full SHA")
        if status != "recorded":
            require(self.row["selection"] != "default", label, "default requires known official selected release")
            require(value["release_ref"] is None and value["release_date"] is None
                    and value["clean_release"] is None and value["vendor_official"] is None,
                    label, "deferred release cannot claim official/dated/clean metadata")
        else:
            require(value["vendor_official"] is True and self.pin is not None and self.commit is not None,
                    label, "official selected release identity must be explicit")
            release_date = dated(value["release_date"], label + ".release_date")
            self.release_metadata(value, label, release_date)
        self.component_binding(value, label)

    def release_metadata(self, value, label, release_date):
        require(value["clean_release"] is None or type(value["clean_release"]) is bool,
                label, "clean_release must be boolean or explicitly unknown")
        ref = value["release_ref"]
        target = object_value(self.reference(ref, label + ".release_ref"), label + ".release")
        path = ref["path"]
        require(path in {"manifests/landscape.json", "catalogs/landscape/upstream-snapshot.json"},
                label, "release proof must use the canonical release metadata carrier")
        if path == "manifests/landscape.json":
            require(ref["pointer"].startswith(("/current_core_releases/", "/additional_supply_chain_candidates/")),
                    label, "release pointer must select a concrete release row")
            actual_repo = "https://github.com/" + text(target.get("repo"), label + ".repo")
        else:
            require(ref["pointer"].endswith("/latest_stable_release"), label,
                    "snapshot release pointer must name latest_stable_release, not commit metadata")
            component_pointer = ref["pointer"].rsplit("/", 1)[0]
            document, _ = self.document(path, label)
            component = self.saturation.resolve_pointer(document, component_pointer)
            actual_repo = component.get("repository")
        require(self.identity(actual_repo, label) == self.repo, label, "release repository mismatch")
        tag = target.get("tag_name", target.get("version"))
        require(self.host.pin_matches(tag, self.pin), label, "selected release pin mismatch")
        release_commit = target.get("source_commit")
        if path == "catalogs/landscape/upstream-snapshot.json":
            release_source = object_value(component.get("latest_release_source"), label + ".latest_release_source")
            require(release_source.get("ref") == tag, label, "latest-release commit source names a different tag")
            release_commit = release_source.get("sha")
        require(release_commit == self.commit, label, "selected release commit mismatch")
        require(dated(target.get("published_at"), label + ".published_at", timestamp=True) == release_date,
                label, "selected release date mismatch")
        url = target.get("html_url", target.get("url"))
        https(url, label + ".release_url")
        require(url == f"https://github.com/{actual_repo.removeprefix('https://github.com/')}/releases/tag/{tag}",
                label, "release URL does not bind the official repository and selected tag")
        clean = (target["prerelease"] is False and target.get("draft", False) is False) \
            if type(target.get("prerelease")) is bool else None
        require(value["clean_release"] is clean, label, "clean-release declaration differs from release metadata")
        if self.row["selection"] == "default":
            require(clean is True, label, "default requires a clean release")
        self.classes.add("metadata_only")

    def component_binding(self, value, label):
        for cid in self.row["component_ids"]:
            require(cid in self.components, label, "unknown canonical component ID")
            component = self.components[cid]
            normalized = self.host.normalize_repository(component.get("repository"))
            require(normalized is not None and self.validator.canonical(normalized.removeprefix("github.com/")) == self.repo,
                    label, "component repository differs from selected repository")
            require(self.host.pin_matches(component.get("version"), self.pin)
                    or self.host.pin_matches(component.get("version"), self.commit), label, "component pin mismatch")
            if component.get("source_pin") is not None:
                require(component["source_pin"] == self.commit, label, "component source commit mismatch")
        binding = value["candidate_binding"]
        if self.row["component_ids"]:
            require(binding is None, label, "installed component binding cannot imply a separate candidate")
        else:
            fields(binding, {"record_ref", "origin_ref"}, label + ".candidate_binding")
            record_ref = binding["record_ref"]
            fields(record_ref, self.REF_FIELDS, label + ".candidate.record_ref")
            require(record_ref["path"] == "catalogs/us-equities/decision-index.json"
                    and re.fullmatch(r"/records/(0|[1-9][0-9]*)", record_ref["pointer"]),
                    label, "candidate must bind a canonical research record")
            candidate = object_value(self.reference(record_ref, label + ".candidate"), label)
            require(self.identity(candidate.get("repository"), label) == self.repo, label, "candidate repository mismatch")
            origin_ref = binding["origin_ref"]
            fields(origin_ref, self.REF_FIELDS, label + ".candidate.origin_ref")
            origins = sequence(candidate.get("references"), label + ".candidate.references")
            matches = [origin for origin in origins if isinstance(origin, dict)
                       and origin.get("path") == origin_ref["path"] and origin.get("pointer") == origin_ref["pointer"]]
            require(len(matches) == 1 and matches[0].get("kind") != "public_star", label,
                    "candidate source must be a retained typed origin, not public-star-only discovery")
            origin = object_value(self.reference(origin_ref, label + ".origin"), label)
            require(self.identity(origin.get("repository"), label) == self.repo, label, "candidate origin repository mismatch")
            if origin.get("version_or_commit") is not None and self.pin is not None:
                require(self.host.pin_matches(origin["version_or_commit"], self.pin)
                        or self.host.pin_matches(origin["version_or_commit"], self.commit), label,
                        "candidate origin source pin mismatch")
            self.classes.add("source_review" if origin.get("evidence_level", origin.get("review_level")) == "source_review"
                             else "metadata_only")

    def proof(self, value, label, client, stage):
        fields(value, {"status", "reason", "evidence_refs"}, label)
        status = self.disposition(value, label, observed=True)
        refs = sequence(value["evidence_refs"], label + ".evidence_refs", nonempty=status in {"recorded", "observed"})
        require(status in {"recorded", "observed"} or not refs, label, "unknown/deferred evidence cannot contain completed proof")
        targets = []
        for ref in refs:
            target = self.reference(ref, label, evidence=True)
            if status == "recorded":
                require(target.get("client") == client and target.get("stage") == stage,
                        label, "consumer client/stage scope mismatch")
                require(target.get("role") == self.slot["role"] and target.get("layer_id") == self.slot["layer_id"],
                        label, "functional role/layer scope mismatch")
            else:
                for key, expected in (("client", client), ("role", self.slot["role"]), ("layer_id", self.slot["layer_id"])):
                    require(target.get(key) is None or target[key] == expected, label,
                            "observed evidence has a conflicting known consumer/functional scope")
            enum(target.get("result"), {"pass", "fail", "partial"}, label + ".result")
            dated(target.get("observed_at_utc"), label + ".observed_at_utc", timestamp=True)
            commands = sequence(target.get("commands"), label + ".commands")
            for command in commands:
                object_value(command, label + ".command")
                require(type(command.get("exit")) is int, label, "native command must retain its exit code")
                require(type(command.get("expected_exit", 0)) is int, label,
                        "expected exit code must be an integer")
                text(command.get("output_excerpt"), label + ".output_excerpt")
                require(bool(self.HEX64.fullmatch(text(command.get("output_sha256"), label))), label,
                        "native command must retain its output hash")
            require(target["result"] != "pass" or all(c["exit"] == c.get("expected_exit", 0) for c in commands), label,
                    "passed evidence contains a failed command")
            targets.append((target, ref["evidence_class"]))
        return status == "recorded" and bool(targets) and all(target["result"] == "pass" and level == "native_proven"
                                     for target, level in targets)

    def organic(self, value, label):
        fields(value, {"client", "arm", "task_scope", "status", "reason", "evidence_refs"}, label)
        status = self.disposition(value, label, observed=True)
        refs = sequence(value["evidence_refs"], label + ".evidence_refs", nonempty=status in {"recorded", "observed"})
        require(status not in {"unknown", "deferred"} or not refs, label, "unresolved organic evidence needs empty refs")
        if status in {"unknown", "deferred"}:
            require(value["task_scope"] is None, label, "unresolved organic scope must stay null")
        passed = False
        for ref in refs:
            target = self.reference(ref, label, evidence=True)
            actual_client = target.get("client")
            actual_client = actual_client.get("id") if isinstance(actual_client, dict) else actual_client
            actual_client = "claude" if actual_client == "claude-code" else actual_client
            require(actual_client == value["client"] and target.get("arm") == value["arm"], label,
                    "organic client/arm scope mismatch")
            require(text(value["task_scope"], label + ".task_scope") == self.slot.get("task_scope")
                    == target.get("task_scope") and self.slot["layer_id"] in target.get("layer_ids", []),
                    label, "organic functional role/layer scope mismatch")
            if status == "observed":
                require(target.get("verdict") is None,
                        label, "unqualified observations cannot claim native qualification")
                continue
            owner_path = Path(__file__).with_name("organic_use.py")
            require(owner_path.is_file(), label, "canonical organic owner/validator is unavailable")
            if __package__:
                from . import organic_use
            else:
                import organic_use
            require(Path(organic_use.__file__).resolve() == owner_path.resolve(), label, "organic owner source mismatch")
            records = organic_use.load_records(self.validator.root)
            match = [record for record in records if record.get("block_ref") == ref["path"] + "#" + ref["pointer"]]
            require(len(match) == 1, label, "organic reference is outside the canonical owner's carrier")
            passed = passed or (match[0].get("verdict") == "READY" and ref["evidence_class"] == "native_proven")
        return status == "recorded" and passed

    def refutations(self, rows, label):
        required = {(family, role) for family in ("claude", "gpt6") for role in ("facts", "fit")}
        seen, documents, results, fields_by_role = set(), {"facts": [], "fit": []}, {}, {}
        judgment_ids = set()
        for value in sequence(rows, label):
            fields(value, {"family", "role", "status", "reason", "source_field_ref", "judgment_refs", "result"}, label)
            key = (enum(value["family"], {"claude", "gpt6"}, label), enum(value["role"], {"facts", "fit"}, label))
            require(key not in seen, label, "duplicate family/role refuter")
            seen.add(key)
            status = self.disposition(value, label, observed=True)
            if status in {"unknown", "deferred"}:
                require(value["source_field_ref"] is None and value["judgment_refs"] == [] and value["result"] is None,
                        label, "unresolved refuter cannot claim completed judgments")
                continue
            source = object_value(self.reference(value["source_field_ref"], label + ".source_field"), label)
            require(source.get("catalog") == "foundation" and source.get("layer_id") == self.slot["layer_id"],
                    label, "refuter frozen field scope mismatch")
            try:
                require(self.saturation.v2_field_sha256(source) == source.get("field_sha256"), label,
                        "refuter frozen field hash mismatch")
            except (KeyError, TypeError) as error:
                raise InvalidCatalog(f"{label}: malformed frozen source field") from error
            if key[1] in fields_by_role:
                require(source == fields_by_role[key[1]], label, "families cite different frozen source fields")
            fields_by_role[key[1]] = source
            if status == "recorded":
                requirement = object_value(source.get("requirement"), label + ".requirement")
                require(hashlib.sha256(self.saturation.canonical(requirement)).hexdigest() == source.get("requirement_sha256"),
                        label, "reviewed requirement hash does not bind its original input")
                scope = object_value(requirement.get("selection"), label + ".selection_scope")
                fields(scope, {"repository", "pin", "commit", "role"}, label + ".selection_scope")
                require(self.identity(scope["repository"], label) == self.repo and self.host.pin_matches(scope["pin"], self.pin)
                        and scope["commit"] == self.commit and scope["role"] == self.slot["role"], label,
                        "reviewed input selected pin/commit/functional role mismatch")
            matching = [member for member in sequence(source.get("eligible_field"), label)
                        if isinstance(member, dict) and self.identity(member.get("repository"), label) == self.repo]
            require(len(matching) == 1, label, "repository is outside frozen refuter field")
            member = matching[0]
            result = []
            for ref in sequence(value["judgment_refs"], label):
                doc = object_value(self.reference(ref, label + ".judgment"), label)
                judgment = object_value(doc.get("judgment"), label + ".judgment.identity")
                require(doc.get("role") == key[1] and judgment.get("family") == key[0], label, "refuter role/family mismatch")
                jid = text(judgment.get("judgment_id"), label)
                require(jid not in judgment_ids, label, "refuter judgment identity reused")
                judgment_ids.add(jid)
                votes = [vote for vote in sequence(doc.get("votes"), label)
                         if isinstance(vote, dict) and vote.get("candidate_key") == member.get("candidate_key")]
                require(len(votes) == 1, label, "refuter needs exactly one retained candidate vote")
                result.append({"judgment_id": jid, "status": votes[0].get("status"), "criterion": votes[0].get("criterion")})
                documents[key[1]].append(doc)
            require(value["result"] == result, label, "refuter result differs from original retained judgments")
            results[key] = (member, source, status)
            if not any(self.documents[ref["path"]].get("evidence_class") is not None for ref in value["judgment_refs"]):
                self.classes.add("source_review")
        require(seen == required, label, "exactly four family/role refuter carriers required")
        for role, docs in documents.items():
            if not docs:
                continue
            member, source, _ = next(results[key] for key in results if key[1] == role)
            screen = self.saturation.v2_screen(role, docs, member, source)
            require(not any(reason in {"malformed_or_unbound_judgment", "overlapping_judgment_ids", "outside_source_field"}
                            for reason in screen["pending_reasons"]), label, "malformed/unbound canonical refuter judgment")
            for family in ("claude", "gpt6"):
                if (family, role) in results:
                    require(f"{family}:incomplete_replication" not in screen["pending_reasons"],
                            label, "recorded refuter lacks canonical replicated judgments")
        return all((family, role) in results and results[(family, role)][2] == "recorded" for family, role in required) and all(
            self.saturation.v2_screen(role, docs, results[("claude", role)][0], results[("claude", role)][1])["status"] == "credible"
            for role, docs in documents.items())

    def audit(self, value, label):
        fields(value, {"status", "reason", "grade", "origin", "date", "limitations", "lead_only", "evidence_refs"}, label)
        require(value["lead_only"] is True, label, "audit grade is a lead only")
        strings(value["limitations"], label + ".limitations")
        status = self.disposition(value, label)
        if status != "recorded":
            require(value["grade"] is None and value["origin"] is None and value["date"] is None
                    and value["evidence_refs"] == [], label, "unresolved audit cannot assert a grade")
            return
        text(value["grade"], label + ".grade")
        text(value["origin"], label + ".origin")
        dated(value["date"], label + ".date")
        for ref in sequence(value["evidence_refs"], label):
            target = self.reference(ref, label, evidence=True)
            require(ref["evidence_class"] in {"source_review", "metadata_only", "synthetic"}, label,
                    "audit lead cannot establish native acceptance")
            for key in ("grade", "origin", "date", "limitations", "lead_only"):
                require(target.get(key) == value[key], label, "audit differs from its canonical source")

    def overturn(self, value, label):
        fields(value, {"status", "reason", "fixture_ref", "metric_ref", "arms", "trigger_ref"}, label)
        status = self.disposition(value, label)
        if status != "recorded":
            require(value["fixture_ref"] is None and value["metric_ref"] is None
                    and value["trigger_ref"] is None and value["arms"] == [], label,
                    "unresolved comparison cannot claim measured arms or trigger")
            return
        fixture = object_value(self.reference(value["fixture_ref"], label), label)
        fields(fixture, {"path", "sha256"}, label + ".fixture")
        raw = self.validator.path(fixture["path"], label).read_bytes()
        require(fixture["path"] in self.files and self.files[fixture["path"]].get("sha256") == fixture["sha256"]
                == hashlib.sha256(raw).hexdigest(), label, "comparison fixture is not hash-bound")
        metric = object_value(self.reference(value["metric_ref"], label), label)
        fields(metric, {"name", "direction"}, label + ".metric")
        text(metric["name"], label)
        enum(metric["direction"], {"minimize", "maximize"}, label)
        identities = set()
        for arm in sequence(value["arms"], label):
            fields(arm, {"repository", "pin", "source_ref"}, label + ".arm")
            target = object_value(self.reference(arm["source_ref"], label), label)
            name, pin = self.identity(arm["repository"], label), text(arm["pin"], label)
            require(self.identity(target.get("repository"), label) == name
                    and self.host.pin_matches(target.get("pin"), pin), label, "comparison arm binding mismatch")
            require((name, pin) not in identities, label, "duplicate comparison arm")
            identities.add((name, pin))
        require(len(identities) >= 2 and any(name == self.repo and self.host.pin_matches(pin, self.pin)
                                           for name, pin in identities), label, "comparison needs selected pin and challenger arms")
        trigger = object_value(self.reference(value["trigger_ref"], label), label)
        fields(trigger, {"metric", "operator", "threshold"}, label + ".trigger")
        require(trigger["metric"] == metric["name"], label, "comparison trigger metric mismatch")
        enum(trigger["operator"], {"gt", "gte", "lt", "lte"}, label)
        require(type(trigger["threshold"]) in (int, float) and math.isfinite(trigger["threshold"]),
                label, "comparison trigger needs finite numeric threshold")

    def row_check(self, row, slot, label):
        fields(row, self.ROW_FIELDS, label)
        self.row, self.slot = row, slot
        self.repo = self.identity(row["repository"], label)
        self.classes = set()
        strings(row["component_ids"], label + ".component_ids", nonempty=False)
        enum(row["adoption_status"], {"recommendation", "adopted"}, label)
        require(row["selection"] == "default" or row["adoption_status"] == "recommendation", label,
                "alternatives/exclusions cannot assert adoption")
        self.source(row["source"], label + ".source")
        clients, operations = set(), []
        for client in sequence(row["install_smoke"], label):
            fields(client, {"client", "installation", "wiring", "smoke"}, label)
            name = enum(client["client"], {"claude", "codex"}, label)
            require(name not in clients, label, "duplicate consuming client")
            clients.add(name)
            operations.extend(self.proof(client[field], label + "." + field, name, stage)
                              for field, stage in (("installation", "install"), ("wiring", "wiring"), ("smoke", "smoke")))
        require(clients == {"claude", "codex"}, label, "both consuming client carriers required")
        cells, native = set(), {}
        for cell in sequence(row["organic"], label):
            key = (enum(cell.get("client"), {"claude", "codex"}, label), enum(cell.get("arm"), {"native", "env"}, label))
            require(key not in cells, label, "duplicate organic client/arm")
            cells.add(key)
            passed = self.organic(cell, label + ".organic")
            if key[1] == "native":
                native[key[0]] = passed
        require(cells == {(c, a) for c in ("claude", "codex") for a in ("native", "env")}, label,
                "all four organic client/arm dispositions required")
        refuted = self.refutations(row["refutations"], label + ".refutations")
        self.audit(row["audit"], label + ".audit")
        self.overturn(row["overturn"], label + ".overturn")
        if row["selection"] == "excluded":
            value = row["exclusion"]
            fields(value, {"date", "reason", "overturn_conditions", "evidence_refs"}, label + ".exclusion")
            dated(value["date"], label)
            text(value["reason"], label)
            strings(value["overturn_conditions"], label)
            for ref in sequence(value["evidence_refs"], label):
                target = self.reference(ref, label + ".exclusion", evidence=True)
                for key in ("date", "reason", "overturn_conditions"):
                    require(target.get(key) == value[key], label, "exclusion differs from dated canonical evidence")
        else:
            require(row["exclusion"] is None, label, "only excluded repository may carry exclusion")
        for previous in sequence(row["supersedes"], label + ".supersedes", nonempty=False):
            fields(previous, {"date", "scope", "reason", "decision_ref", "receipt_refs"}, label + ".supersedes")
            require(dated(previous["date"], label) < self.decision_date, label, "supersession must be strictly earlier")
            text(previous["scope"], label)
            text(previous["reason"], label)
            target = object_value(self.reference(previous["decision_ref"], label), label)
            require(target.get("role", target.get("capability_key")) == slot["role"]
                    and target.get("component_ids") == row["component_ids"]
                    and target.get("checked_at", target.get("date")) == previous["date"], label,
                    "supersession changes prior capability/components/date scope")
            require(previous["scope"] == target.get("scope", target.get("evidence_scope")), label,
                    "supersession scope differs from prior canonical decision")
            prior = {"repository": target.get("repository"), "pin": target.get("pin"),
                     "commit": target.get("commit"), "component_ids": target.get("component_ids")}
            text(prior["repository"], label + ".prior.repository")
            text(prior["pin"], label + ".prior.pin")
            for ref in sequence(previous["receipt_refs"], label):
                retained = self.reference(ref, label, evidence=True, binding=prior)
                require(retained.get("scope", retained.get("claim")) == previous["scope"], label,
                        "retained prior receipt differs from superseded scope")
        declared = strings(row["evidence_classes"], label + ".evidence_classes")
        require(set(declared) == self.classes, label, "evidence classes must equal resolved canonical classes")
        if row["adoption_status"] == "adopted":
            require(bool(row["component_ids"]) and all(operations) and all(native.values()) and refuted, label,
                    "adoption requires both clients' installation/wiring/native smoke and canonical native organic qualification")


def validate_finalized_selection(root: Path, manifest=None) -> dict | None:
    """Check the explicit selection projection, leaving research overlap valid.

    Reuse native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:
    scripts/validate_catalogs.py:110-127,156-186 and this file:56-63.
    Those readers retain duplicate-key rejection through object_pairs_hook:
    https://docs.python.org/3/library/json.html#json.load
    The census is a separate declaration, never generated from the slot rows.
    """
    validator = Validator(root)
    if manifest is None:
        manifest = validator.load(MANIFEST)
    object_value(manifest, MANIFEST)
    if "finalized_selection_file" not in manifest:
        return None
    require(manifest["finalized_selection_file"] == FINALIZED_SELECTION,
            MANIFEST, "finalized_selection_file must name the canonical selection file")
    document = validator.load(FINALIZED_SELECTION)
    fields(document, {"schema_version", "status", "decision_record", "source_base_commit",
                      "included_repositories", "slots", "limitations"}, FINALIZED_SELECTION)
    strings(document["limitations"], FINALIZED_SELECTION + ".limitations")
    require(type(document.get("schema_version")) is int
            and document["schema_version"] == 1,
            FINALIZED_SELECTION, "schema_version must be 1")
    status = enum(document.get("status"), {"pending_synthesis", "finalized"},
                  f"{FINALIZED_SELECTION}.status")
    validator.path(document.get("decision_record"), "finalized_selection.decision_record")
    base = text(document.get("source_base_commit"), "finalized_selection.source_base_commit")
    require(bool(SHA.fullmatch(base)), "finalized_selection.source_base_commit",
            "expected full lowercase Git commit SHA")
    validator.read_aliases(validator.load(REPOSITORY_COVERAGE))

    def identity(value, label):
        name = repository(value, label)
        # The source reader checks .git before lowercasing; keep this projection
        # canonical for mixed-case suffixes without changing legacy research.
        require(not name.endswith(".git"), label,
                "expected canonical https://github.com/owner/repo URL")
        return validator.canonical(name)

    require("included_repositories" in document, FINALIZED_SELECTION,
            "missing included_repositories census")
    census = set()
    if status == "pending_synthesis":
        require(document["included_repositories"] is None, FINALIZED_SELECTION,
                "pending synthesis must keep the repository census null")
    else:
        for value in sequence(document["included_repositories"], "included_repositories"):
            name = identity(value, "included_repositories")
            require(name not in census, "included_repositories",
                    f"duplicate canonical repository {name}")
            census.add(name)

    slots = indexed(document.get("slots"), "id", "finalized_selection.slots")
    evidence = SelectionEvidence(validator, identity, dated(Path(document["decision_record"]).name[:10], "decision date")) \
        if status == "finalized" else None
    owners = {}
    references = set()
    for identifier, slot in slots.items():
        fields(slot, {"id", "layer_id", "role", "purpose", "repositories", "references"}, identifier,
               optional={"language", "supported_languages", "task_scope"})
        enum(slot.get("layer_id"), LAYERS, f"{identifier}.layer_id")
        for key in ("role", "purpose"):
            text(slot.get(key), f"{identifier}.{key}")
        if "language" in slot:
            text(slot["language"], f"{identifier}.language")
        if "supported_languages" in slot:
            strings(slot["supported_languages"], f"{identifier}.supported_languages")
        if "task_scope" in slot:
            text(slot["task_scope"], f"{identifier}.task_scope")
        rows = sequence(slot.get("repositories"), f"{identifier}.repositories", nonempty=False)
        if status == "pending_synthesis":
            require(not rows, identifier,
                    "pending synthesis cannot declare repository selections")
        defaults = 0
        for row in rows:
            object_value(row, f"{identifier}.repositories")
            name = identity(row.get("repository"), f"{identifier}.repository")
            selection = enum(row.get("selection"), {"default", "alternative", "excluded"},
                             f"{identifier}.selection")
            require(name not in owners, identifier,
                    f"canonical repository {name} already owned by slot {owners.get(name)}")
            owners[name] = identifier
            defaults += selection == "default"
            evidence.row_check(row, slot, identifier + ".repositories")
        if status == "finalized":
            require(defaults == 1, identifier, "exactly one default repository required")
        # References are links, not ownership declarations; repetition is allowed.
        for value in sequence(slot.get("references"), f"{identifier}.references", nonempty=False):
            references.add(identity(value, f"{identifier}.references"))
    if status == "finalized":
        require(set(owners) == census, FINALIZED_SELECTION,
                "repository ownership must exactly equal the independent census; "
                f"unowned={sorted(census - owners.keys())}, "
                f"outside_census={sorted(owners.keys() - census)}")
        require(references <= census, FINALIZED_SELECTION,
                f"reference outside included repository census: {sorted(references - census)}")
    return {"status": status, "slots": len(slots),
            "repositories": len(owners) if status == "finalized" else None}


def validate_foundation(root: Path) -> dict:
    validator = Validator(root)
    manifest = validator.load(MANIFEST)
    fields(manifest, {"schema_version", "catalog_id", "checked_at", "scope", "limitations",
                      "canonical_sources", "decisions_file", "layers", "domain_boundary", "top_gaps", "open_gates"},
           MANIFEST, optional={"finalized_selection_file"})
    validator.header(manifest, MANIFEST)
    require(manifest["catalog_id"] == "foundation", MANIFEST, "catalog_id must be foundation")
    text(manifest["scope"], "manifest.scope")
    strings(manifest["limitations"], "manifest.limitations")
    require(manifest["canonical_sources"] == SOURCES, "canonical_sources", "use canonical sources without copying pins or receipts")
    require(manifest["decisions_file"] == DECISIONS, "decisions_file", "use the FOUNDATION decisions file")
    for path in SOURCES.values():
        validator.path(path, "canonical_sources")
    components = indexed(validator.load(SOURCES["components"]).get("components"), "id", "components")
    receipts = indexed(validator.load(SOURCES["evidence"]).get("receipts"), "id", "receipts")
    lifecycle = indexed(validator.load(SOURCES["lifecycle"]).get("components"), "component_id", "lifecycle")

    layers = indexed(manifest["layers"], "id", "layers")
    require(set(layers) == LAYERS, "layers", "must contain exactly the 20 required layers")
    for identifier, layer in layers.items():
        fields(layer, {"id", "title", "purpose", "selection", "activation", "lifecycle_scope", "next_gap"}, identifier)
        for key, value in layer.items():
            text(value, f"{identifier}.{key}")

    domain = {}
    for row in sequence(manifest["domain_boundary"], "domain_boundary", nonempty=False):
        fields(row, {"component_id", "catalog", "scope"}, "domain_boundary")
        identifier = text(row["component_id"], "domain_boundary.component_id")
        require(identifier in components, "domain_boundary", f"unknown component {identifier}")
        require(identifier not in domain, "domain_boundary", "duplicate component")
        validator.path(row["catalog"], "domain_boundary.catalog")
        text(row["scope"], "domain_boundary.scope")
        domain[identifier] = row

    gaps = indexed(manifest["top_gaps"], "id", "top_gaps")
    priorities = []
    for gap in gaps.values():
        fields(gap, {"id", "priority", "status", "scope", "next_action", "source_paths"}, "top_gaps")
        require(type(gap["priority"]) is int, "top_gaps.priority", "expected integer priority")
        priorities.append(gap["priority"])
        enum(gap["status"], {"open", "partial", "addressed_in_catalog", "accepted_within_scope"}, "top_gaps.status")
        text(gap["scope"], "top_gaps.scope")
        text(gap["next_action"], "top_gaps.next_action")
        source_paths(gap["source_paths"], validator, "top_gaps.source_paths")
    require(sorted(priorities) == [1, 2, 3], "top_gaps", "exactly three ranked gaps required")
    gate_ids, gap_ids = set(), set()
    for gate in sequence(manifest["open_gates"], "open_gates", nonempty=False):
        fields(gate, {"id", "gap_id"}, "open_gates")
        gate_id = text(gate["id"], "open_gates.id")
        gap_id = text(gate["gap_id"], "open_gates.gap_id")
        require(gate_id not in gate_ids and gap_id not in gap_ids, "open_gates", "duplicate gate or gap")
        require(gap_id in gaps, "open_gates", "unknown gap")
        gate_ids.add(gate_id)
        gap_ids.add(gap_id)
    require(gap_ids == {identifier for identifier, gap in gaps.items() if gap["status"] in {"open", "partial"}},
            "open_gates", "must reference exactly the unfinished gaps")

    document = validator.load(DECISIONS)
    fields(document, {"schema_version", "checked_at", "scope", "decisions"}, DECISIONS)
    validator.header(document, DECISIONS, manifest["checked_at"])
    text(document["scope"], "decisions.scope")
    decisions = indexed(document["decisions"], "id", "decisions")
    used_layers, used_components, used_receipts, candidates = set(), set(), set(), set()
    for identifier, row in decisions.items():
        fields(row, {"id", "capability", "capability_key", "checked_at", "layer_ids", "selection", "review_status",
                     "activation", "component_ids", "candidate", "evidence_ids", "evidence_scope", "limitations",
                     "source_paths", "next_gap", "lifecycle", "supersedes"}, identifier)
        for key in ("capability", "capability_key", "activation", "evidence_scope", "next_gap"):
            text(row[key], f"{identifier}.{key}")
        checked = dated(row["checked_at"], f"{identifier}.checked_at")
        require(checked <= dated(manifest["checked_at"], "manifest.checked_at"), identifier, "decision date exceeds manifest")
        layer_ids = strings(row["layer_ids"], f"{identifier}.layer_ids")
        require(set(layer_ids) <= LAYERS, identifier, "unknown layer")
        used_layers.update(layer_ids)
        enum(row["selection"], {"default", "conditional", "optional", "trial", "candidate"}, f"{identifier}.selection")
        enum(row["review_status"], {"accepted_within_scope", "partial_acceptance", "source_review", "discovery", "not_established"},
             f"{identifier}.review_status")
        component_ids = strings(row["component_ids"], f"{identifier}.component_ids", nonempty=False)
        require(set(component_ids) <= components.keys(), identifier, "unknown component")
        require(not set(component_ids) & domain.keys(), identifier, "component belongs to domain boundary")
        evidence_ids = strings(row["evidence_ids"], f"{identifier}.evidence_ids", nonempty=False)
        require(set(evidence_ids) <= receipts.keys(), identifier, "unknown evidence")
        strings(row["limitations"], f"{identifier}.limitations")
        source_paths(row["source_paths"], validator, f"{identifier}.source_paths")

        candidate = row["candidate"]
        if row["selection"] == "candidate":
            fields(candidate, {"id", "repository"}, f"{identifier}.candidate")
            candidate_id = text(candidate["id"], f"{identifier}.candidate.id")
            require(candidate_id not in candidates and candidate_id not in components, identifier, "candidate identity duplicates adopted component or candidate")
            https(candidate["repository"], f"{identifier}.candidate.repository")
            require(not component_ids and not evidence_ids and row["review_status"] in {"discovery", "source_review", "not_established"},
                    identifier, "candidate cannot assert adopted components or native acceptance")
            candidates.add(candidate_id)
        else:
            require(candidate is None and bool(component_ids), identifier, "selected capability needs component IDs, not a candidate")
            require(bool(evidence_ids), identifier, "selected capability needs evidence references")

        bound_components = set()
        for evidence_id in evidence_ids:
            receipt = receipts[evidence_id]
            validator.path(receipt.get("path"), f"{identifier}.evidence.{evidence_id}")
            receipt_components = set(strings(receipt.get("component_ids"), f"{evidence_id}.component_ids"))
            overlap = set(component_ids) & receipt_components
            require(bool(overlap), identifier, f"unrelated evidence {evidence_id}")
            bound_components.update(overlap)
            text(receipt.get("claim"), f"{evidence_id}.claim")
            strings(receipt.get("limitations"), f"{evidence_id}.limitations")
        require(set(component_ids) <= bound_components, identifier, "component without related evidence")
        if row["review_status"] == "accepted_within_scope":
            require(any(receipts[evidence_id].get("kind") in EXECUTION for evidence_id in evidence_ids),
                    identifier, "native acceptance requires execution evidence, not inventory alone")

        stages = row["lifecycle"]
        fields(stages, {"source_path", "scope", "unknown", "stage_refs"}, f"{identifier}.lifecycle")
        require(stages["source_path"] == SOURCES["lifecycle"], identifier, "use canonical lifecycle source")
        text(stages["scope"], f"{identifier}.lifecycle.scope")
        text(stages["unknown"], f"{identifier}.lifecycle.unknown")
        seen_stages = set()
        for stage in sequence(stages["stage_refs"], f"{identifier}.stage_refs", nonempty=bool(component_ids)):
            fields(stage, {"component_id", "stage", "status"}, f"{identifier}.stage_refs")
            require(stage["component_id"] in component_ids and stage["component_id"] in lifecycle,
                    identifier, "invalid lifecycle component")
            enum(stage["stage"], STAGES, f"{identifier}.lifecycle stage")
            enum(stage["status"], STATUSES, f"{identifier}.lifecycle status")
            key = (stage["component_id"], stage["stage"])
            require(key not in seen_stages, identifier, "duplicate lifecycle stage")
            seen_stages.add(key)
            canonical = object_value(lifecycle[stage["component_id"]].get("lifecycle_stages"), "canonical lifecycle")
            native_stage = object_value(canonical.get(stage["stage"]), "canonical lifecycle stage")
            require(stage["status"] == native_stage.get("status"), identifier, "lifecycle status differs from canonical scoped evidence")
            text(native_stage.get("scope"), "canonical lifecycle scope")
            for path in strings(native_stage.get("evidence_refs"), "canonical lifecycle evidence", nonempty=False):
                validator.path(path, "canonical lifecycle evidence")
        require(set(component_ids) <= {key[0] for key in seen_stages}, identifier, "component missing lifecycle reference")
        if row["review_status"] == "accepted_within_scope":
            accepted_components = {stage["component_id"] for stage in stages["stage_refs"]
                                   if stage["status"] == "accepted_within_scope"}
            require(set(component_ids) <= accepted_components, identifier,
                    "capability acceptance requires a canonical accepted stage for each component")
        if candidate is not None:
            require(not seen_stages, identifier, "candidate lifecycle must remain pending")
        used_components.update(component_ids)
        used_receipts.update(evidence_ids)

    require(used_layers == LAYERS, "decisions", "every required layer needs a capability or explicit pending decision")
    for identifier, row in decisions.items():
        targets = set()
        for supersession in sequence(row["supersedes"], f"{identifier}.supersedes", nonempty=False):
            fields(supersession, {"decision_id", "scope", "reason"}, f"{identifier}.supersedes")
            target = text(supersession["decision_id"], f"{identifier}.supersedes.decision_id")
            require(target in decisions, identifier, "unknown superseded decision")
            require(target != identifier and target not in targets, identifier, "self or duplicate supersession")
            targets.add(target)
            text(supersession["scope"], f"{identifier}.supersedes.scope")
            text(supersession["reason"], f"{identifier}.supersedes.reason")
            previous = decisions[target]
            require(previous["capability_key"] == row["capability_key"]
                    and set(previous["component_ids"]) == set(row["component_ids"])
                    and previous["candidate"] == row["candidate"], identifier, "supersession must retain the same capability and component scope")
            require(dated(previous["checked_at"], "superseded date") < dated(row["checked_at"], "decision date"),
                    identifier, "superseded decision must be earlier; cycles forbidden")

    validate_finalized_selection(root, manifest)
    return {"layers": len(layers), "decisions": len(decisions), "foundation_components": len(used_components),
            "domain_components": len(domain), "evidence_receipts": len(used_receipts), "candidates": len(candidates)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        counts = validate_foundation(args.root)
        report = {"ok": True, "counts": counts, "errors": []}
    except (InvalidCatalog, OSError, UnicodeError, ValueError) as error:
        report = {"ok": False, "counts": {}, "errors": [str(error)]}
    if args.as_json:
        print(json.dumps(report, indent=2))
    elif report["ok"]:
        print("FOUNDATION catalog valid: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    else:
        print("FOUNDATION catalog invalid: " + "; ".join(report["errors"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
