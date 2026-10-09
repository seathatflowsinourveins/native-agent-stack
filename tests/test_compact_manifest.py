"""Synthetic artifact-integrity controls; these are not upstream or host acceptance."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import csv
import os

TOOL = Path(__file__).resolve().parents[1] / "tools/sota-convergence/compact_manifest.py"
SPEC = importlib.util.spec_from_file_location("compact_manifest", TOOL)
compact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compact)


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def pin(repository, value="a" * 40, subject="implementation"):
    return {"kind": "commit", "version_or_commit": value, "repository_or_source": repository, "subject": subject}


@unittest.skipUnless(shutil.which("zstd"), "supported native zstd prerequisite is unavailable")
class CompactManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.capture = raw({"kind": "synthetic-source-review", "scope": "documentation only; no test executed"})
        self.files = {"captures/source.json": self.capture, "captures/README.md": b"# synthetic awesome list\n"}
        self.rows = [self.row(f"example/project-{i}") for i in range(368)]
        census = raw({"rows": [{"entry_id": str(i), "repository_or_entry": "example/project-0", "slot": "native-clients"} for i in (0, 1)]})
        self.files["captures/list-census.json"] = census
        occurrences = [{"occurrence_id": f"awesome:entry:{i}", "repository_or_entry": "example/project-0", "slot": "native-clients",
                        "qualification": {}, "capture_sha256": digest(census), "archive_member": "captures/list-census.json", "pointer": f"/rows/{i}"} for i in (0, 1)]
        self.rows[0]["source_refs"] = [{"occurrence_id": item["occurrence_id"], "sha256": item["capture_sha256"],
                                        "archive_member": item["archive_member"], "pointer": item["pointer"]} for item in occurrences]
        self.coverage = {"schema_version": 1, "status": "FROZEN", "expected_keys": [self.row_key(row) for row in self.rows],
                         "starred_identities": [row["repository_or_entry"] for row in self.rows], "omissions": [],
                         "list_populations": [{"source_repository": "example/awesome", "pin": pin("example/awesome", "b" * 40, "source-entry"),
                             "path": "README.md", "capture_sha256": digest(self.files["captures/README.md"]), "archive_member": "captures/README.md",
                             "parser": "synthetic-retained-census-v1", "expected_occurrences": occurrences}]}
        self.add_authority_witnesses()

    def witness(self, name, value):
        member = "captures/" + name + ".json"
        data = raw(value)
        self.files[member] = data
        return {"archive_member": member, "sha256": digest(data), "pointer": ""}

    def add_authority_witnesses(self):
        population = self.coverage["list_populations"][0]
        source = {name: deepcopy(population[name]) for name in ("source_repository", "pin", "path", "capture_sha256")}
        population["source_witness"] = self.witness("source-receipt", source)
        population["census_witness"] = self.witness("frozen-list-census", {"status": "FROZEN", "expected_occurrences": deepcopy(population["expected_occurrences"])})
        population_fact = {name: deepcopy(population[name]) for name in ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser")}
        self.coverage["source_inventory_witness"] = self.witness("source-inventory", {"status": "FROZEN", "starred_identities": deepcopy(self.coverage["starred_identities"]), "list_populations": [population_fact]})
        fields = [{"slot": slot, "catalog": "foundation"} for slot in ["native-clients", "workers", *[f"field-{i}" for i in range(43)]]]
        self.coverage["field_inventory_witness"] = self.witness("field-inventory", {"status": "FROZEN", "fields": fields})
        self.coverage["star_inventory_witness"] = self.witness("original-star-census", [{"full_name": value} for value in self.coverage["starred_identities"]])

    def row(self, repository):
        p = pin(repository)
        return {"repository_or_entry": repository, "slot": "native-clients", "disposition": "WATCH", "evidence_class": "SOURCE-REVIEW",
                "pin": p, "primary_sources": [{"locator": f"https://github.com/{repository}/blob/{p['version_or_commit']}/README.md", "pin": p, "subject": "pinned implementation README"}],
                "capture_sha256": digest(self.capture), "archive_member": "captures/source.json", "owner_lane": "synthetic-controls", "refresh_date": "2026-10-08"}

    @staticmethod
    def row_key(row):
        return {key: deepcopy(row[key]) for key in ("repository_or_entry", "slot", "qualification") if key in row}

    def archive(self, extra=()):
        files = {"compact/rows.json": raw(self.rows), "compact/coverage.json": raw(self.coverage), **self.files}
        tar_path, asset = self.directory / "capture.tar", self.directory / "capture.tar.zst"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as archive:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            for member, data in extra:
                archive.addfile(member, io.BytesIO(data) if data is not None else None)
        with asset.open("wb") as output:
            subprocess.run(["zstd", "--quiet", "--stdout", str(tar_path)], stdout=output, stderr=subprocess.PIPE, check=True)
        return asset

    def build(self):
        return compact.build_manifest(self.archive(), "v2026.10.08")

    def closure_build(self):
        return compact.build_manifest(self.archive(), "v2026.10.08", profile=compact.START_CLOSURE_PROFILE)

    def closure_pending(self, *, pin_residue=False, locator_residue=False):
        row = self.rows[0]
        row["disposition"] = "PENDING"
        row["pending"] = {"provisional_disposition": "WATCH", "measurement": "verify retained primary bytes and exact upstream pin", "owner": "synthetic-controls"}
        row["closure"] = {}
        if pin_residue:
            row["pin"] = None
            row["primary_sources"][0]["pin"] = None
            row["closure"]["pending_pin"] = {"reason_code": "no-body", "measurement": "capture upstream repository file and locate its blob in a commit tree"}
        if locator_residue:
            row["primary_sources"][0]["locator"] = "UNKNOWN"
            row["closure"]["pending_locator"] = {"reason_code": "unsupported-transport", "measurement": "establish the source repository file locator from primary evidence"}

    def closure_counted(self):
        population = self.coverage["list_populations"][0]
        population["expected_occurrences"].pop()
        self.rows[0]["source_refs"].pop()
        population["counted"] = {"physical_entries": 3, "typed_source_ids": 3, "groups": 2, "duplicates_removed": 1,
                                 "overlap_stars": 1, "overlap_fields": 0, "promoted_entries": 1,
                                 "promotion_rule": "promote a claimed retained decision row; count all other physical entries",
                                 "unpromoted_ids": self.witness("unpromoted-list-ids", ["awesome:entry:1", "awesome:entry:2"])}
        population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(population["expected_occurrences"]), "counted": deepcopy(population["counted"])})

    def closure_physical_aliases(self):
        row = self.native_entry()
        raw_id = "example/awesome:README.md:2"
        physical = {"occurrence_id": raw_id, "original_ledger_input_id": raw_id, "source_repository": "example/awesome", "source_path": "README.md",
                    "source_line": 2, "source_pin": "b" * 40, "source_content_sha256": row["capture_sha256"], "archive_member": row["archive_member"],
                    "linked_targets": [{"label": "Candidate", "repository": "example/project-0", "url": "https://github.com/example/project-0"},
                                       {"label": "Another candidate on the same line", "repository": "example/project-1", "url": "https://github.com/example/project-1"}]}
        physical_ref = self.witness("original-physical-receipt", {"occurrences": [physical]}) | {"pointer": "/occurrences/0"}
        canonical_member = row["source_entry_witness"]["archive_member"]
        mappings = [{"occurrence_id": raw_id, "repository_or_entry": row["repository_or_entry"], "slot": row["slot"],
                     "archive_member": canonical_member, "capture_sha256": digest(self.files[canonical_member]), "pointer": "line:2"}]
        original_aliases = []
        for ordinal, prefix in enumerate(("list-screen:", "second-explicit-alias:")):
            member = "captures/alias-representation-" + str(ordinal) + ".json"
            self.files[member] = raw({"entry": {"entry": row["repository_or_entry"], "slot": row["slot"], "source_line": 2}})
            record = {"occurrence_id": prefix + raw_id, "source_line": 2, "entry": row["repository_or_entry"], "slot": row["slot"],
                      "archive_member": member, "capture_sha256": digest(self.files[member]), "pointer": "/entry", "kind": "awesome-list", "ordinal": None}
            original_aliases.append(record)
            mappings.append({name: record[name] for name in ("occurrence_id", "slot", "archive_member", "capture_sha256", "pointer")} |
                            {"repository_or_entry": row["repository_or_entry"], "physical_occurrence_id": raw_id})
        platform = {"collection": [{"source_repository": "example/awesome", "pin": "b" * 40, "file": "README.md", "occurrences": original_aliases}]}
        platform_ref = self.witness("original-alias-receipt", platform)
        aliases = []
        for ordinal, record in enumerate(original_aliases):
            aliases.append({name: record[name] for name in ("occurrence_id", "archive_member", "capture_sha256", "pointer")} |
                           {"physical_occurrence_id": raw_id, "original_id": raw_id, "source_repository": "example/awesome", "path": "README.md", "line": 2,
                            "physical_witness": physical_ref, "alias_collection_witness": platform_ref | {"pointer": "/collection/0"},
                            "alias_occurrence_witness": platform_ref | {"pointer": "/collection/0/occurrences/" + str(ordinal)}})
        row["source_refs"] = [{"occurrence_id": item["occurrence_id"], "archive_member": item["archive_member"], "sha256": item["capture_sha256"], "pointer": item["pointer"]} for item in mappings]
        population = self.coverage["list_populations"][0]
        population.update(archive_member=row["archive_member"], capture_sha256=row["capture_sha256"], expected_occurrences=mappings)
        self.add_authority_witnesses()
        alias_document = {"status": "FROZEN", "aliases": aliases}
        population["counted"] = {"physical_entries": 1, "typed_source_ids": 1, "groups": 1, "duplicates_removed": 0, "overlap_stars": 1, "overlap_fields": 0,
                                 "promoted_entries": 1, "promotion_rule": "retain original literal references; count physical source entries once",
                                 "unpromoted_ids": self.witness("unpromoted-list-ids", []), "alias_witness": self.witness("physical-alias-map", alias_document)}
        population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(mappings), "counted": deepcopy(population["counted"])})
        return alias_document

    def closure_omission(self, code="source-primary-qualification-unresolved"):
        omission = {"code": code, "count": 1, "cc_disposition_id": "CC-item-212958Z",
                    "follow_up_id": compact.OMISSION_FOLLOW_UPS[code], "resolution": "retain the measured residue in the declared follow-up"}
        self.coverage["omissions"].append(omission)
        return omission

    def residue_case(self, code):
        """Actual malformed source inputs, without a generated residue waiver."""
        row = self.rows[0]
        if code in {"foreign-primary-pin-scope-unqualified", "original-source-entry-identity-unbound"}:
            row["pin"] = pin("example/awesome", "b" * 40, "source-entry")
            row["primary_sources"] = [{"pin": row["pin"], "locator": "example/awesome@" + "b" * 40 + ":README.md", "subject": "source entry"}]
            if code == "original-source-entry-identity-unbound":
                row.update(decision_scope="source-entry-screen", candidate_implementation_status="UNESTABLISHED", source_pointer="")
        elif code == "unsupported-json-pointer-capture":
            self.files["captures/non-json.md"] = b"# Original Markdown\n"
            row["source_refs"].append({"archive_member": "captures/non-json.md", "sha256": digest(self.files["captures/non-json.md"]), "pointer": "/entry"})
        elif code == "unbound-field-selector":
            row = self.rows[1]
            row["slot"] = "unbound-selector"
        elif code == "original-list-occurrence-scope-unverified":
            census = json.loads(self.files["captures/list-census.json"])
            census["rows"][0].pop("slot")
            self.files["captures/list-census.json"] = raw(census)
            for occurrence in self.coverage["list_populations"][0]["expected_occurrences"]:
                occurrence["capture_sha256"] = digest(self.files["captures/list-census.json"])
            for ref in row["source_refs"]:
                ref["sha256"] = digest(self.files["captures/list-census.json"])
            self.add_authority_witnesses()
        else:
            original_star = deepcopy(row)
            row = deepcopy(self.native_skill())
            self.rows[0] = original_star
            self.rows.append(row)
            field_ref = self.coverage["field_inventory_witness"]
            fields = json.loads(self.files[field_ref["archive_member"]])
            fields["fields"][-1]["slot"] = row["slot"]
            self.coverage["field_inventory_witness"] = self.witness("field-inventory", fields)
            if code == "native-skill-entry-witness-unverified":
                row["source_pointer"] = "/proposed/99"
        self.coverage["expected_keys"] = [self.row_key(item) for item in self.rows]
        return row

    def test_each_blocker_class_default_action_and_non_action_profile_counts(self):
        for code in compact.RESIDUE_BUCKETS:
            with self.subTest(code=code):
                case = CompactManifestTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                row = case.residue_case(code)
                strict, _ = case.build()
                self.assertIn(code, {item["code"] for item in strict["validation"]["blockers"]})
                closure, _ = case.closure_build()
                self.assertNotIn(code, {item["code"] for item in closure["validation"]["blockers"]})
                self.assertGreater(closure["counts"]["residue_by_class"][code], 0)
                per_class = Counter()
                per_bucket = Counter()
                for output in closure["rows"]:
                    for item in output.get("closure", {}).get("residue", []):
                        per_class[item["reason_code"]] += item["count"]
                        per_bucket[item["bucket"]] += item["count"]
                        self.assertNotIn(output["disposition"], compact.ACTION_CLASSES)
                for reason in compact.RESIDUE_BUCKETS:
                    self.assertEqual(closure["counts"]["residue_by_class"][reason], per_class[reason])
                for bucket in {"PENDING-PIN", "PENDING-LOCATOR", "origin-unresolved", "counted-inventory", "G5-F1"}:
                    self.assertEqual(closure["counts"]["residue_by_bucket"][bucket], per_bucket[bucket])
                self.assertEqual(closure["counts"]["f1"], per_class["unbound-field-selector"])
                self.assertEqual(closure["counts"]["f2"], per_class["skill-entry-primary-bytes-unestablished"] + per_class["native-skill-entry-witness-unverified"])
                if code == "original-source-entry-identity-unbound":
                    self.assertEqual(next(r for r in closure["rows"] if r["slot"] == row["slot"] and r["repository_or_entry"] == compact.canonical(row["repository_or_entry"]))["origin_pointer"], "unresolved")
                row["disposition"] = "TRIAL"
                row.pop("pending", None)
                action, _ = case.closure_build()
                # Native skill entries additionally fail their existing PENDING-only guard.
                expected = "native-skill-entry-witness-unverified" if "skill-entry" in code else code
                self.assertIn(expected, {item["code"] for item in action["validation"]["blockers"]})
                action_row = next(r for r in action["rows"] if compact.decision_key(r) == compact.decision_key(row))
                self.assertFalse(action_row.get("closure", {}).get("residue"))

    def test_skill_primary_body_miss_at_both_append_sites_is_counted(self):
        self.native_skill("d" * 64)
        blockers = []
        index = {name: {"sha256": digest(body), "bytes": len(body)} for name, body in self.files.items()}
        compact.validate_native_skill_entry(self.rows[0], index, self.files, {}, blockers, compact.START_CLOSURE_PROFILE)
        self.assertFalse(blockers)
        self.assertEqual(self.rows[0]["closure"]["residue"][0]["reason_code"], "skill-entry-primary-bytes-unestablished")

    def test_declared_residue_never_waives_action_or_survives_repaired_input(self):
        self.residue_case("foreign-primary-pin-scope-unqualified")
        manifest, _ = self.closure_build()
        output = next(r for r in manifest["rows"] if r["repository_or_entry"] == compact.canonical(self.rows[0]["repository_or_entry"]))
        self.rows[0]["closure"] = deepcopy(output["closure"])
        self.rows[0]["disposition"] = "TRIAL"
        with self.assertRaisesRegex(compact.CompactError, "residue can never"):
            self.closure_build()
        self.rows[0]["disposition"] = "WATCH"
        self.rows[0]["pin"] = pin("example/project-0")
        self.rows[0]["primary_sources"] = self.row("example/project-0")["primary_sources"]
        repaired, _ = self.closure_build()
        self.assertEqual(repaired["counts"]["residue_by_class"]["foreign-primary-pin-scope-unqualified"], 0)

    def test_refreshed_bound_origin_survives_old_source_identity_residue(self):
        row = self.residue_case("original-source-entry-identity-unbound")
        prior, _ = self.closure_build()
        row["closure"] = deepcopy(next(r for r in prior["rows"] if compact.decision_key(r) == compact.decision_key(row))["closure"])
        row["pin"] = pin("example/project-0")
        row["primary_sources"] = self.row("example/project-0")["primary_sources"]
        row["origin_pointer"] = self.witness("refreshed-original-origin", {"rows": [{"repository_or_entry": "example/project-0", "slot": "native-clients"}]}) | {"pointer": "/rows/0"}
        refreshed, _ = self.closure_build()
        self.assertEqual(refreshed["validation"]["status"], "PASS")
        self.assertEqual(refreshed["counts"]["origin_pointer_bound"], 1)
        self.assertEqual(refreshed["counts"]["origin_unresolved"], 0)

    def test_global_f3_requires_exact_declared_count_hash_and_keeps_action_ids(self):
        extra = deepcopy(self.rows[0]["source_refs"][0])
        extra["occurrence_id"] = "outside-declared-union:1"
        self.rows[0]["source_refs"].append(extra)
        strict, _ = self.build()
        self.assertIn("occurrences-outside-declared-union", {item["code"] for item in strict["validation"]["blockers"]})
        unapproved, _ = self.closure_build()
        self.assertIn("occurrences-outside-declared-union", {item["code"] for item in unapproved["validation"]["blockers"]})
        omission = self.closure_omission("occurrences-outside-declared-union")
        omission.update(cc_disposition_id="G5-F3", occurrence_ids_sha256=digest(compact.json_text([extra["occurrence_id"]], indent=2).encode()))
        for disposition in ("WATCH", "TRIAL"):
            self.rows[0]["disposition"] = disposition
            manifest, _ = self.closure_build()
            self.assertEqual(manifest["validation"]["status"], "PASS")
            self.assertEqual(manifest["counts"]["f3"], 1)
            self.assertEqual(manifest["coverage"]["outside_declared_union"]["occurrence_ids"], [extra["occurrence_id"]])
            self.assertFalse(self.rows[0].get("closure", {}).get("residue"))
        omission["count"] = 2
        with self.assertRaisesRegex(compact.CompactError, "count/hash"):
            self.closure_build()
        omission["count"] = 1
        omission["occurrence_ids_sha256"] = "d" * 64
        with self.assertRaisesRegex(compact.CompactError, "count/hash"):
            self.closure_build()
        self.rows[0]["source_refs"].pop()
        with self.assertRaisesRegex(compact.CompactError, "count/hash"):
            self.closure_build()
        self.coverage["omissions"].append(deepcopy(omission))
        with self.assertRaisesRegex(compact.CompactError, "duplicate G5-F3"):
            self.closure_build()

    def scoped_occurrence(self):
        population = self.coverage["list_populations"][0]
        body = b"# Pinned list\n## Declared section\n- [Candidate](https://github.com/example/project-0)\n## Next section\n"
        self.files[population["archive_member"]] = body
        population["capture_sha256"] = digest(body)
        census = json.loads(self.files["captures/list-census.json"])
        original = {"source_repository": "example/awesome", "source_pin": "b" * 40, "source_path": "README.md",
                    "source_content_sha256": digest(body), "source_line": 3, "entry_text": body.decode().splitlines()[2],
                    "source_heading": "Pinned list / Declared section"}
        census["rows"][0] = original
        self.files["captures/list-census.json"] = raw(census)
        for occurrence in population["expected_occurrences"]:
            occurrence["capture_sha256"] = digest(self.files["captures/list-census.json"])
        for ref in self.rows[0]["source_refs"]:
            ref["sha256"] = digest(self.files["captures/list-census.json"])
        self.add_authority_witnesses()
        proof = {name: deepcopy(population[name]) for name in compact.POPULATION_FACTS}
        proof.update(section_heading="## Declared section", section_start=2, section_end=3,
                     section_sha256=digest(b"".join(body.splitlines(keepends=True)[1:3])), line_sha256=digest(body.splitlines(keepends=True)[2]),
                     boundary_witness=self.witness("declared-boundary", original),
                     slot_witness=self.witness("declared-slot", {"repository": "example/project-0", "layer_ids": "native-clients", "source_pin": "b" * 40,
                                                               "input_id": "list-screen:example/awesome:README.md:3"}),
                     field_witness=self.witness("declared-field", {"catalog": "foundation", "slot": "native-clients"}),
                     commit_witness=self.witness("primary-commit", {"sha": "b" * 40, "commit": {"tree": {"sha": "c" * 40}}}),
                     tree_witness=self.witness("primary-tree", {"sha": "c" * 40, "truncated": False,
                         "tree": [{"path": "README.md", "type": "blob", "sha": hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()}]}))
        population["expected_occurrences"][0]["scope_witness"] = self.witness("scope-proof", proof)
        self.add_authority_witnesses()
        self.rows[0]["disposition"] = "TRIAL"
        return proof

    def test_action_list_scope_binds_primary_section_pin_blob_and_declared_selector(self):
        proof = self.scoped_occurrence()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["counted_inventory"], 0)
        for changed in ({"section_end": 4}, {"section_start": 4}, {"capture_sha256": "d" * 64}, {"line_sha256": "d" * 64}):
            with self.subTest(changed=changed):
                altered = proof | changed
                self.coverage["list_populations"][0]["expected_occurrences"][0]["scope_witness"] = self.witness("scope-proof", altered)
                self.add_authority_witnesses()
                failed, _ = self.closure_build()
                self.assertIn("original-list-occurrence-scope-unverified", {b["code"] for b in failed["validation"]["blockers"]})
        proof["slot_witness"] = self.witness("declared-slot", {"repository": "example/project-0", "layer_ids": "workers", "source_pin": "b" * 40,
                                                               "input_id": "list-screen:example/awesome:README.md:3"})
        self.coverage["list_populations"][0]["expected_occurrences"][0]["scope_witness"] = self.witness("scope-proof", proof)
        self.add_authority_witnesses()
        failed, _ = self.closure_build()
        self.assertIn("original-list-occurrence-scope-unverified", {b["code"] for b in failed["validation"]["blockers"]})

    def test_action_list_scope_hash_mismatch_remains_a_byte_integrity_error(self):
        self.scoped_occurrence()
        self.coverage["list_populations"][0]["expected_occurrences"][0]["scope_witness"]["sha256"] = "d" * 64
        self.add_authority_witnesses()
        with self.assertRaisesRegex(compact.CompactError, "capture"):
            self.closure_build()

    def closure_missing_list(self):
        omission = self.closure_omission("missing-list-capture")
        omission.update({"source_repository": "example/missing-list", "pin": pin("example/missing-list", "c" * 40, "source-entry"),
                         "path": "README.md", "capture_sha256": "d" * 64, "archive_member": "captures/missing-list.md", "parser": "measured-source-list-v1", "count": 7})
        inventory = json.loads(self.files[self.coverage["source_inventory_witness"]["archive_member"]])
        inventory["list_populations"].append({name: omission[name] for name in compact.POPULATION_FACTS})
        self.coverage["source_inventory_witness"] = self.witness("source-inventory", inventory)

    def closure_disagreement(self):
        self.closure_pending()
        row = self.rows[0]
        source = row["primary_sources"][0]
        source["locator"] = f"https://github.com/example/wrong-repository/blob/{source['pin']['version_or_commit']}/README.md"
        row["closure"]["pending_locator"] = {"reason_code": "source-disagreement", "measurement": "capture the original repository README and settle which recorded source identity is correct"}
        row["closure"]["disagreements"] = [{"id": "locator-source-1", "kind": "source-repository", "status": "PENDING",
                                                 "recorded_locator": source["locator"], "recorded_repository": source["pin"]["repository_or_source"],
                                                 "recorded_pin": deepcopy(source["pin"]), "resolution": "retain unresolved original claims",
                                                 "explanation": "the captured locator and declared repository disagree", "measurement": "verify the original primary README",
                                                 "evidence_refs": []}]

    def closure_conflict(self):
        self.closure_pending()
        row = self.rows[0]
        row["pending"]["measurement"] = "settle the contradictory same-slot primary evidence and execution claims"
        row["choices"] = [{"disposition": "TRIAL", "source_refs": deepcopy(row["source_refs"]), "qualification": {"catalog": "foundation"}},
                          {"disposition": "WATCH", "source_refs": deepcopy(row["source_refs"]), "qualification": {"catalog": "foundation", "role": "worker"}}]
        row["closure"]["pending_conflict"] = {"provisional_disposition": row["pending"]["provisional_disposition"], "measurement": row["pending"]["measurement"],
                                              "action_side_row_ids": ["original113:example/project-0:native-clients:TRIAL"]}

    def closure_relaxation(self, rule):
        if rule == "pending-pin":
            self.closure_pending(pin_residue=True)
        elif rule == "pending-locator":
            self.closure_pending(locator_residue=True)
        elif rule == "counted-inventory":
            self.closure_counted()
        elif rule == "typed-list-omission":
            self.closure_omission("complete-typed-list-populations-not-frozen")
        elif rule == "source-qualification-omission":
            self.closure_omission()
        elif rule == "missing-list-capture":
            self.closure_missing_list()
        elif rule == "pending-disagreement":
            self.closure_disagreement()
        elif rule == "pending-conflict":
            self.closure_conflict()
        elif rule == "origin-unresolved":
            self.rows[0]["disposition"] = "TRIAL"
            self.rows[0]["origin_pointer"] = "unresolved"
        else:
            self.fail("unknown relaxation fixture")

    def test_closure_each_relaxed_rule_still_fails_the_strict_default(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for rule in ("pending-pin", "pending-locator", "counted-inventory", "typed-list-omission", "source-qualification-omission", "missing-list-capture", "pending-disagreement", "pending-conflict", "origin-unresolved"):
            with self.subTest(rule=rule):
                self.rows, self.files, self.coverage = deepcopy(original)
                self.closure_relaxation(rule)
                asset = self.archive()
                try:
                    default, _ = compact.build_manifest(asset, "v2026.10.08")
                except compact.CompactError:
                    pass
                else:
                    self.assertEqual(default["validation"]["status"], "BLOCKED")
                closure, _ = compact.build_manifest(asset, "v2026.10.08", profile=compact.START_CLOSURE_PROFILE)
                self.assertEqual(closure["validation"]["status"], "PASS", closure["validation"]["blockers"])
                self.assertEqual(closure["validation"]["profile"], "start-closure/1")

    def test_closure_each_relaxation_keeps_action_hash_locator_and_omission_guards(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for rule in ("pending-pin", "pending-locator", "counted-inventory", "typed-list-omission", "source-qualification-omission", "missing-list-capture", "pending-disagreement", "pending-conflict", "origin-unresolved"):
            for defect in ("null-action-row-pin", "null-action-primary-pin", "capture-hash", "unsafe-locator", "undispositioned-omission"):
                with self.subTest(rule=rule, defect=defect):
                    self.rows, self.files, self.coverage = deepcopy(original)
                    self.closure_relaxation(rule)
                    target = self.rows[2]
                    if defect.startswith("null-action"):
                        target["disposition"] = "TRIAL"
                        if defect == "null-action-row-pin":
                            target["pin"] = None
                        else:
                            target["primary_sources"][0]["pin"] = None
                    elif defect == "capture-hash":
                        target["capture_sha256"] = "e" * 64
                    elif defect == "unsafe-locator":
                        target["primary_sources"][0]["locator"] = "file:/tmp/unsafe-primary"
                    else:
                        self.closure_omission()["cc_disposition_id"] = ""
                    try:
                        manifest, _ = self.closure_build()
                    except compact.CompactError:
                        pass
                    else:
                        self.assertEqual(manifest["validation"]["status"], "BLOCKED")

    def test_closure_both_pending_flags_remain_independent_and_require_measurements(self):
        self.closure_pending(pin_residue=True, locator_residue=True)
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["pending_pin"], 1)
        self.assertEqual(manifest["counts"]["pending_locator"], 1)
        face = manifest["validation"]["nonblocking_counts"]
        self.assertEqual(face["pending_pin_by_reason"], {"no-body": 1})
        self.assertEqual(face["pending_pin_items_by_reason"], {"no-body": 2})
        self.assertEqual(face["pending_locator_items_by_reason"], {"unsupported-transport": 1})
        self.assertEqual(face["pending_locator_by_reason"], {"unsupported-transport": 1})
        for flag in ("pending_pin", "pending_locator"):
            with self.subTest(flag=flag):
                saved = self.rows[0]["closure"][flag].pop("measurement")
                with self.assertRaises(compact.CompactError):
                    self.closure_build()
                self.rows[0]["closure"][flag]["measurement"] = saved

    def test_closure_pending_residue_cannot_be_relabelled_as_an_action(self):
        for flag in ("pending_pin", "pending_locator"):
            with self.subTest(flag=flag):
                self.closure_pending(pin_residue=flag == "pending_pin", locator_residue=flag == "pending_locator")
                self.rows[0]["disposition"] = "TRIAL"
                self.rows[0].pop("pending")
                with self.assertRaises(compact.CompactError):
                    self.closure_build()

    def test_closure_conflict_is_counted_in_full_reads_with_original_choices_and_claim_ids(self):
        self.closure_conflict()
        self.rows[1]["disposition"] = "TRIAL"
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["action_rows"], 1)
        self.assertEqual(manifest["counts"]["pending_conflict"], 1)
        self.assertEqual(manifest["counts"]["action_read_rows"], 2)
        self.assertEqual(manifest["validation"]["nonblocking_counts"]["pending_conflict_rows"], 1)
        conflict_row = next(row for row in manifest["rows"] if "pending_conflict" in row.get("closure", {}))
        self.assertEqual(conflict_row["disposition"], "PENDING")
        self.assertEqual(conflict_row["choices"], self.rows[0]["choices"])
        self.assertEqual(conflict_row["closure"]["pending_conflict"]["action_side_row_ids"], ["original113:example/project-0:native-clients:TRIAL"])

    def test_closure_conflict_must_be_pending_and_keep_actual_same_slot_action_choices(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for defect in ("action", "provisional-action", "measurement", "no-action-side", "duplicate-action-side", "single-choice", "no-action-choice", "scope-split", "missing-choice-source"):
            with self.subTest(defect=defect):
                self.rows, self.files, self.coverage = deepcopy(original)
                self.closure_conflict()
                row = self.rows[0]
                conflict = row["closure"]["pending_conflict"]
                if defect == "action":
                    row["disposition"] = "TRIAL"
                    row.pop("pending")
                elif defect == "provisional-action":
                    conflict["provisional_disposition"] = row["pending"]["provisional_disposition"] = "TRIAL"
                elif defect == "measurement":
                    conflict["measurement"] = "a different measurement"
                elif defect == "no-action-side":
                    conflict["action_side_row_ids"] = []
                elif defect == "duplicate-action-side":
                    conflict["action_side_row_ids"] *= 2
                elif defect == "single-choice":
                    row["choices"].pop()
                elif defect == "no-action-choice":
                    row["choices"][0]["disposition"] = "REJECT"
                elif defect == "scope-split":
                    row["choices"][0]["qualification"]["slot"] = "workers"
                else:
                    row["choices"][0]["source_refs"] = []
                with self.assertRaises(compact.CompactError):
                    self.closure_build()

    def test_closure_conflict_can_retain_separate_pin_and_locator_residue_counts(self):
        self.closure_conflict()
        row = self.rows[0]
        row["pin"] = row["primary_sources"][0]["pin"] = None
        row["primary_sources"][0]["locator"] = "UNKNOWN"
        row["closure"].update(pending_pin={"reason_code": "no-body", "measurement": "capture the exact original source bytes"},
                              pending_locator={"reason_code": "unsupported-transport", "measurement": "establish the exact original primary locator"})
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["pending_conflict"], 1)
        self.assertEqual(manifest["counts"]["pending_pin"], 1)
        self.assertEqual(manifest["counts"]["pending_locator"], 1)
        self.assertEqual(manifest["counts"]["action_read_rows"], 1)

    def test_closure_unresolved_origin_preserves_evidenced_action_and_visible_count(self):
        self.rows[0]["disposition"] = "TRIAL"
        self.rows[0]["origin_pointer"] = "unresolved"
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["action_rows"], 1)
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved"], 1)
        self.assertEqual(manifest["validation"]["nonblocking_counts"]["origin_pointer_unresolved_action_rows"], 1)
        action = next(row for row in manifest["rows"] if row["disposition"] == "TRIAL")
        self.assertEqual(action["origin_pointer"], "unresolved")
        self.rows[0]["primary_sources"][0]["pin"] = None
        with self.assertRaises(compact.CompactError):
            self.closure_build()
        self.rows[0]["primary_sources"][0]["pin"] = self.rows[0]["pin"]
        self.rows[0]["disposition"] = "ADOPT-NOW"
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def test_closure_bound_origin_requires_original_repository_slot_hash_and_selector(self):
        self.rows[0]["disposition"] = "TRIAL"
        original = {"rows": [{"repository_or_entry": "example/project-0", "slot": "native-clients", "disposition": "TRIAL"}]}
        self.rows[0]["origin_pointer"] = self.witness("original-action-origin", original) | {"pointer": "/rows/0", "source_id": "original113:example/project-0:native-clients:TRIAL"}
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["origin_pointer_bound"], 1)
        for value in ("example/project-1", "example/project-0"):
            original["rows"][0]["repository_or_entry"] = value
            original["rows"][0]["slot"] = "native-clients" if value.endswith("1") else "workers"
            self.rows[0]["origin_pointer"] = self.witness("original-action-origin", original) | {"pointer": "/rows/0"}
            manifest, _ = self.closure_build()
            self.assertTrue(any(item["code"] == "origin-pointer-repository-slot-unbound" for item in manifest["validation"]["blockers"]))
        self.rows[0]["origin_pointer"]["pointer"] = "/missing"
        manifest, _ = self.closure_build()
        self.assertTrue(any(item["code"] == "unresolved-capture-pointer" for item in manifest["validation"]["blockers"]))
        self.rows[0]["origin_pointer"]["sha256"] = "e" * 64
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def closure_origin_claim(self):
        row = self.rows[0]
        row["disposition"] = "TRIAL"
        row["origin_pointer"] = "unresolved"
        row["origin_claim_ids"] = ["original113:shared-action-claim"]
        claim = {"row_id": row["origin_claim_ids"][0], "repository": "example/project-0", "slots": ["native-clients"],
                 "original_disposition": "TRIAL", "source_lane": "synthetic-original-lane"}
        row["source_refs"].append(self.witness("original-origin-claims", {"rows": [claim]}) | {"pointer": "/rows/0"})
        return claim

    def test_closure_one_original_origin_claim_counts_once_across_two_qualified_rows(self):
        self.closure_origin_claim()
        second = deepcopy(self.rows[0])
        second["qualification"] = {"role": "worker"}
        second["source_refs"] = [ref for ref in second["source_refs"] if "occurrence_id" not in ref]
        self.rows.append(second)
        self.coverage["expected_keys"].append(self.row_key(second))
        with self.assertRaises(compact.CompactError):
            self.build()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS", manifest["validation"]["blockers"])
        self.assertEqual(manifest["counts"]["action_rows"], 2)
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved"], 1)
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved_rows"], 2)
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved_claims"], 1)
        self.assertIn("distinct hash-bound original", manifest["coverage"]["count_units"]["origin_pointer_unresolved"])
        self.rows[1]["origin_pointer"] = "unresolved"
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved"], 2)
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved_rows"], 3)

    def test_closure_origin_claim_ids_require_exact_original_id_hash_repository_slot_and_unresolved(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for defect in ("id", "hash", "repository", "slot", "selector", "no-unresolved", "duplicate-id"):
            with self.subTest(defect=defect):
                self.rows, self.files, self.coverage = deepcopy(original)
                claim = self.closure_origin_claim()
                row = self.rows[0]
                if defect == "id":
                    row["origin_claim_ids"] = ["invented-claim-id"]
                elif defect == "hash":
                    row["source_refs"][-1]["sha256"] = "e" * 64
                elif defect in {"repository", "slot"}:
                    if defect == "repository":
                        claim["repository"] = "example/project-1"
                    else:
                        claim["slots"] = ["workers"]
                    row["source_refs"][-1] = self.witness("original-origin-claims", {"rows": [claim]}) | {"pointer": "/rows/0"}
                elif defect == "selector":
                    row["source_refs"][-1]["pointer"] = "/missing"
                elif defect == "no-unresolved":
                    row.pop("origin_pointer")
                else:
                    row["origin_claim_ids"] *= 2
                try:
                    manifest, _ = self.closure_build()
                except compact.CompactError:
                    pass
                else:
                    self.assertEqual(manifest["validation"]["status"], "BLOCKED")

    def test_closure_origin_claim_metadata_slots_compatibility_does_not_change_source_claim(self):
        claim = self.closure_origin_claim()
        claim["metadata"] = {"slots": claim.pop("slots")}
        self.rows[0]["source_refs"][-1] = self.witness("original-origin-claims", {"rows": [claim]}) | {"pointer": "/rows/0"}
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["origin_pointer_unresolved"], 1)

    def test_closure_missing_residue_declaration_and_unsafe_null_pin_locator_still_block(self):
        self.closure_pending(pin_residue=True)
        self.rows[0].pop("closure")
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "BLOCKED")
        self.rows[0]["closure"] = {"pending_pin": {"reason_code": "no-body", "measurement": "capture exact source file"}}
        for locator in ("https://user:secret@github.com/example/repo/blob/" + "a" * 40 + "/README.md", "https://github.com/example/repo/blob/main/README.md", "/tmp/primary", "github://example/repo",
                        "example/project-0@" + "a" * 40 + ":../../unsafe", "javascript:bad@" + "a" * 40 + ":README.md"):
            with self.subTest(locator=locator):
                self.rows[0]["primary_sources"][0]["locator"] = locator
                with self.assertRaises(compact.CompactError):
                    self.closure_build()

    def test_closure_counted_inventory_keeps_promoted_bijection_and_hash_bound_untyped_ids(self):
        self.closure_counted()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["counts"]["retained_occurrences"], 1)
        self.assertEqual(manifest["counts"]["unpromoted_list_occurrences"], 2)
        self.rows[0]["source_refs"].clear()
        manifest, _ = self.closure_build()
        self.assertTrue(any(item["code"] == "unretained-list-occurrence" for item in manifest["validation"]["blockers"]))
        population = self.coverage["list_populations"][0]
        population["counted"]["unpromoted_ids"]["sha256"] = "e" * 64
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def test_closure_counted_id_overlap_and_census_drift_fail(self):
        self.closure_counted()
        population = self.coverage["list_populations"][0]
        population["counted"]["unpromoted_ids"] = self.witness("unpromoted-list-ids", ["awesome:entry:0", "awesome:entry:2"])
        population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(population["expected_occurrences"]), "counted": deepcopy(population["counted"])})
        with self.assertRaises(compact.CompactError):
            self.closure_build()
        population["counted"]["unpromoted_ids"] = self.witness("unpromoted-list-ids", ["awesome:entry:1", "awesome:entry:2"])
        manifest, _ = self.closure_build()
        self.assertTrue(any(item["code"] == "original-list-census-unfrozen-or-mismatched" for item in manifest["validation"]["blockers"]))

    def test_closure_counted_physical_entry_can_have_multiple_exact_retained_mappings(self):
        row = self.native_entry()
        member = row["source_entry_witness"]["archive_member"]
        occurrence = {"occurrence_id": "example/awesome:README.md:2", "repository_or_entry": row["repository_or_entry"], "slot": row["slot"],
                      "archive_member": member, "capture_sha256": digest(self.files[member]), "pointer": "line:2"}
        ref = {"occurrence_id": occurrence["occurrence_id"], "archive_member": member, "sha256": occurrence["capture_sha256"], "pointer": "line:2"}
        row["source_refs"] = [ref]
        second = deepcopy(row)
        second["qualification"] = {"role": "worker"}
        self.rows.append(second)
        self.coverage["expected_keys"].append(self.row_key(second))
        population = self.coverage["list_populations"][0]
        population.update(archive_member=row["archive_member"], capture_sha256=row["capture_sha256"],
                          expected_occurrences=[occurrence, occurrence | {"qualification": second["qualification"]}])
        population["counted"] = {"physical_entries": 2, "typed_source_ids": 1, "groups": 1, "duplicates_removed": 0, "overlap_stars": 1, "overlap_fields": 0,
                                 "promoted_entries": 1, "promotion_rule": "retain both literal roles for the same physical entry",
                                 "unpromoted_ids": self.witness("unpromoted-list-ids", ["example/awesome:README.md:3"])}
        self.add_authority_witnesses()
        population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(population["expected_occurrences"]), "counted": deepcopy(population["counted"])})
        with self.assertRaisesRegex(compact.CompactError, "duplicate retained occurrence_id"):
            self.build()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS", manifest["validation"]["blockers"])
        self.assertEqual(manifest["counts"]["expected_occurrences"], 1)
        self.assertEqual(manifest["counts"]["retained_occurrences"], 1)
        self.assertEqual(manifest["counts"]["promoted_mappings"], 2)
        self.assertEqual(manifest["counts"]["retained_mappings"], 2)
        second["source_refs"][0]["pointer"] = "line:1"
        manifest, _ = self.closure_build()
        self.assertTrue(any(item["code"] == "unretained-list-occurrence" for item in manifest["validation"]["blockers"]))

    def test_closure_two_receipt_proven_aliases_and_original_count_one_physical_entry(self):
        self.closure_physical_aliases()
        with self.assertRaises(compact.CompactError):
            self.build()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "PASS", manifest["validation"]["blockers"])
        self.assertEqual(manifest["counts"]["expected_occurrences"], 1)
        self.assertEqual(manifest["counts"]["retained_occurrences"], 1)
        self.assertEqual(manifest["counts"]["literal_promoted_occurrences"], 3)
        self.assertEqual(manifest["counts"]["promoted_mappings"], 3)
        self.assertEqual(manifest["counts"]["physical_aliases"], 2)
        self.rows[0]["source_refs"].pop()
        manifest, _ = self.closure_build()
        self.assertTrue(any(item["code"] == "unretained-list-occurrence" for item in manifest["validation"]["blockers"]))

    def test_closure_physical_alias_missing_or_hash_mismatched_original_receipt_blocks(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for defect in ("missing-alias-map", "map-hash", "physical-hash", "platform-hash", "outside-collection"):
            with self.subTest(defect=defect):
                self.rows, self.files, self.coverage = deepcopy(original)
                aliases = self.closure_physical_aliases()
                population = self.coverage["list_populations"][0]
                if defect == "missing-alias-map":
                    population["counted"].pop("alias_witness")
                elif defect == "map-hash":
                    population["counted"]["alias_witness"]["sha256"] = "e" * 64
                else:
                    alias = aliases["aliases"][0]
                    if defect == "physical-hash":
                        alias["physical_witness"]["sha256"] = "e" * 64
                    elif defect == "platform-hash":
                        alias["alias_occurrence_witness"]["sha256"] = "e" * 64
                    else:
                        alias["alias_occurrence_witness"]["pointer"] = "/collection/0"
                    population["counted"]["alias_witness"] = self.witness("physical-alias-map", aliases)
                population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(population["expected_occurrences"]), "counted": deepcopy(population["counted"])})
                with self.assertRaises(compact.CompactError):
                    self.closure_build()

    def test_closure_physical_alias_wrong_source_line_candidate_slot_and_count_block(self):
        original = deepcopy((self.rows, self.files, self.coverage))
        for defect in ("source-line", "candidate", "slot", "double-count", "unpromoted-collision"):
            with self.subTest(defect=defect):
                self.rows, self.files, self.coverage = deepcopy(original)
                aliases = self.closure_physical_aliases()
                population = self.coverage["list_populations"][0]
                occurrence = population["expected_occurrences"][1]
                if defect == "source-line":
                    aliases["aliases"][0]["line"] = 3
                    population["counted"]["alias_witness"] = self.witness("physical-alias-map", aliases)
                elif defect == "candidate":
                    occurrence["repository_or_entry"] = "example/project-2"
                elif defect == "slot":
                    occurrence["slot"] = "workers"
                elif defect == "double-count":
                    population["counted"]["promoted_entries"] = 3
                    population["counted"]["physical_entries"] = 3
                else:
                    population["counted"]["physical_entries"] = 2
                    population["counted"]["unpromoted_ids"] = self.witness("unpromoted-list-ids", ["example/awesome:README.md:2"])
                population["census_witness"] = self.witness("counted-list-census", {"status": "COUNTED", "expected_occurrences": deepcopy(population["expected_occurrences"]), "counted": deepcopy(population["counted"])})
                with self.assertRaises(compact.CompactError):
                    self.closure_build()

    def test_closure_omission_followup_and_missing_source_reference_are_not_guessed(self):
        omission = self.closure_omission()
        omission["follow_up_id"] = "G5-F1"
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["status"], "BLOCKED")
        self.coverage["omissions"].clear()
        self.closure_missing_list()
        omission = self.coverage["omissions"][0]
        omission.pop("source_repository")
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def test_closure_disagreements_are_visible_and_unrelated_notes_do_not_waive_detection(self):
        self.closure_disagreement()
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["validation"]["nonblocking_counts"]["pending_disagreements"], 1)
        self.assertEqual(manifest["validation"]["disagreements"][0]["recorded_repository"], "example/project-0")
        self.rows[0]["closure"]["disagreements"][0]["recorded_locator"] += "?different=1"
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def test_closure_cli_requires_explicit_profile_and_profile_schemas_preserve_default_hashes(self):
        self.closure_pending(pin_residue=True)
        asset = self.archive()
        manifest_path = self.directory / "profile-manifest.json"
        args = ["--asset", str(asset), "--manifest", str(manifest_path), "--profile", "start-closure/1"]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(compact.main([*args, "--write"]), 0)
            self.assertEqual(compact.main([*args, "--check"]), 0)
            self.assertEqual(compact.main(["--asset", str(asset), "--manifest", str(manifest_path), "--check"]), 2)
        result = json.loads(manifest_path.read_bytes())
        self.assertTrue(result["row_schema"]["path"].endswith("compact-decision-start-closure-1.json"))
        self.assertTrue(result["coverage_schema"]["path"].endswith("compact-coverage-start-closure-1.json"))
        self.assertEqual(digest(compact.SCHEMA.read_bytes())[:8], "716f69bb")
        self.assertEqual(digest(compact.COVERAGE_SCHEMA.read_bytes())[:8], "ca1be75e")

    def test_closure_document_inventory_counts_two_hash_bound_artifacts(self):
        docs = []
        for name in ("architecture-index", "refresh-procedure"):
            member = "documents/" + name + ".md"
            self.files[member] = ("# synthetic " + name + "\n").encode()
            docs.append({"path": "docs/g5-" + name + ".md", "archive_member": member, "sha256": digest(self.files[member])})
        self.coverage["document_inventory_witness"] = self.witness("document-inventory", {"status": "FROZEN", "documents": docs})
        manifest, _ = self.closure_build()
        self.assertEqual(manifest["counts"]["documents"], 2)
        with self.assertRaises(compact.CompactError):
            self.build()
        docs[0]["sha256"] = "e" * 64
        self.coverage["document_inventory_witness"] = self.witness("document-inventory", {"status": "FROZEN", "documents": docs})
        with self.assertRaises(compact.CompactError):
            self.closure_build()

    def assertBlocked(self, code):
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "BLOCKED")
        self.assertTrue(any(code in item["code"] for item in manifest["validation"]["blockers"]))

    def test_asset_only_check_rebuilds_after_local_producers_are_removed(self):
        asset = self.archive()
        manifest_path = self.directory / "manifest.json"
        args = ["--asset", str(asset), "--manifest", str(manifest_path)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(compact.main([*args, "--write"]), 0)
            first = manifest_path.read_bytes()
            self.rows.clear()
            self.files.clear()
            self.assertEqual(compact.main([*args, "--check"]), 0)
        self.assertEqual(manifest_path.read_bytes(), first)
        result = json.loads(first)
        self.assertEqual(result["counts"]["represented_stars"], 368)
        self.assertEqual(result["counts"]["retained_occurrences"], 2)
        self.assertNotIn(str(self.directory), first.decode())

    def test_repeat_rows_witnesses_are_joined_and_never_replace_asset(self):
        asset = self.archive()
        paths = [self.directory / "part-a.json", self.directory / "part-b.json"]
        paths[0].write_bytes(raw(self.rows[:184]))
        paths[1].write_bytes(raw(self.rows[184:]))
        expected, _ = compact.build_manifest(asset, "v2026.10.08", paths)
        self.assertEqual(expected["counts"]["rows"], 368)
        changed = deepcopy(self.rows[:184])
        changed[0]["disposition"] = "TRIAL"
        paths[0].write_bytes(raw(changed))
        with self.assertRaises(compact.CompactError):
            compact.build_manifest(asset, "v2026.10.08", paths)

    def test_canonical_identity_duplicates_reject_without_arbitration(self):
        row = deepcopy(self.rows[0])
        row["repository_or_entry"] = "https://github.com/EXAMPLE/PROJECT-0.git"
        self.rows.append(row)
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_distinct_literal_roles_and_slots_remain_distinct(self):
        for role, slot in (("worker", "workers"), ("SDK", "workers")):
            row = deepcopy(self.rows[0])
            row.pop("source_refs")
            row.update(slot=slot, qualification={"catalog": "foundation", "role": role})
            self.rows.append(row)
            self.coverage["expected_keys"].append(self.row_key(row))
        manifest, _ = self.build()
        self.assertEqual(manifest["counts"]["rows"], 370)
        self.assertEqual(manifest["counts"]["by_slot"]["workers"], 2)
        self.assertEqual(manifest["validation"]["status"], "PASS")

    def test_duplicate_archive_members_reject_even_identical_bytes(self):
        info = tarfile.TarInfo("captures/source.json")
        info.size = len(self.capture)
        with self.assertRaises(compact.CompactError):
            compact.build_manifest(self.archive([(info, self.capture)]), "v2026.10.08")

    def test_unsafe_archive_names_never_extract_or_pass(self):
        for name in ("../escape", "/absolute", "./captures/ambiguous", "captures//ambiguous", "captures\\ambiguous", ".git/config"):
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.size = 1
                with self.assertRaises(compact.CompactError):
                    compact.build_manifest(self.archive([(info, b"x")]), "v2026.10.08")

    def test_archive_symlinks_hardlinks_and_devices_are_rejected(self):
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE):
            with self.subTest(type=member_type):
                info = tarfile.TarInfo("captures/unsupported")
                info.type = member_type
                info.linkname = "captures/source.json"
                with self.assertRaises(compact.CompactError):
                    compact.build_manifest(self.archive([(info, None)]), "v2026.10.08")

    def test_mismatched_capture_hash_fails(self):
        self.rows[0]["capture_sha256"] = "f" * 64
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_unknown_pins_write_blocked_metadata_and_fail_green_check(self):
        self.rows[0]["pin"] = None
        self.rows[0]["primary_sources"][0]["pin"] = None
        asset = self.archive()
        args = ["--asset", str(asset), "--manifest", str(self.directory / "blocked.json")]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(compact.main([*args, "--write"]), 1)
            self.assertEqual(compact.main([*args, "--check"]), 1)

    def test_floating_ref_and_capture_sha_substitution_fail(self):
        for value in ("main", "master", "latest", "a" * 64):
            with self.subTest(pin=value):
                self.rows[0]["pin"] = pin("example/project-0", value)
                with self.assertRaises(compact.CompactError):
                    self.build()

    def test_floating_or_wrong_primary_ref_fails(self):
        for ref in ("main", "master", "b" * 40):
            with self.subTest(ref=ref):
                self.rows[0]["primary_sources"][0]["locator"] = f"https://github.com/example/project-0/blob/{ref}/README.md"
                with self.assertRaises(compact.CompactError):
                    self.build()

    def test_homepage_or_unversioned_docs_cannot_claim_a_commit(self):
        self.rows[0]["primary_sources"][0]["locator"] = "https://github.com/example/project-0"
        self.assertBlocked("unestablished-pinned-primary-locator")
        self.rows[0]["primary_sources"][0]["locator"] = "https://docs.example.com/current"
        self.assertBlocked("unestablished-pinned-primary-locator")

    def test_same_commit_from_a_different_primary_repo_rejects(self):
        self.rows[0]["primary_sources"][0]["locator"] = "https://github.com/another/source/blob/" + "a" * 40 + "/README.md"
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_repo_at_pin_and_raw_github_primary_locators_bind_exactly(self):
        for locator in ("example/project-0@" + "a" * 40 + ":README.md:12", "https://raw.githubusercontent.com/example/project-0/" + "a" * 40 + "/README.md"):
            self.rows[0]["primary_sources"][0]["locator"] = locator
            manifest, _ = self.build()
            self.assertEqual(manifest["validation"]["status"], "PASS")

    def test_source_list_pin_cannot_substitute_for_repository_implementation(self):
        self.rows[0]["pin"] = pin("example/awesome", "b" * 40, "source-entry")
        self.rows[0]["primary_sources"] = [{"locator": "example/awesome@" + "b" * 40 + ":README.md", "pin": self.rows[0]["pin"], "subject": "source entry only"}]
        self.assertBlocked("foreign-primary-pin-scope-unqualified")

    def test_scoped_foreign_source_entry_pin_can_prove_only_list_presence(self):
        row = self.rows[0]
        row.update(pin=pin("example/awesome", "b" * 40, "source-entry"), decision_scope="source-entry-screen", candidate_implementation_status="UNESTABLISHED",
                   archive_member="captures/list-census.json", capture_sha256=digest(self.files["captures/list-census.json"]), source_pointer="/rows/0")
        row["primary_sources"] = [{"locator": "example/awesome@" + "b" * 40 + ":README.md", "pin": row["pin"], "subject": "original list entry, not candidate implementation"}]
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["candidate_implementation_unestablished"], 1)
        row["decision_scope"] = "implementation-merit"
        self.assertBlocked("foreign-primary-pin-scope-unqualified")

    def test_foreign_entry_pin_with_wrong_original_candidate_is_blocked(self):
        row = self.rows[1]
        row.update(pin=pin("example/awesome", "b" * 40, "source-entry"), decision_scope="source-entry-screen", candidate_implementation_status="UNESTABLISHED",
                   archive_member="captures/list-census.json", capture_sha256=digest(self.files["captures/list-census.json"]), source_pointer="/rows/0")
        row["primary_sources"] = [{"locator": "example/awesome@" + "b" * 40 + ":README.md", "pin": row["pin"], "subject": "original list entry"}]
        self.assertBlocked("original-source-entry-identity-unbound")

    def test_repository_reference_artifact_pins_are_kept_as_reference(self):
        reference = pin("example/project-0", subject="reference")
        self.rows[0]["pin"] = reference
        self.rows[0]["primary_sources"][0]["pin"] = reference
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["rows"][0]["pin"]["subject"], "reference")
        self.rows[0]["disposition"] = "ADOPT-NOW"
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_unknown_scope_and_unknown_primary_remain_explicit_blockers(self):
        self.rows[0]["slot"] = "UNKNOWN"
        self.rows[0]["qualification"] = {"slot": "workers, native-clients"}
        self.coverage["expected_keys"][0] = self.row_key(self.rows[0])
        for occurrence in self.coverage["list_populations"][0]["expected_occurrences"]:
            occurrence.update(slot="UNKNOWN", qualification={"slot": "workers, native-clients"})
        self.rows[0]["primary_sources"] = [{"locator": "UNKNOWN", "pin": None, "subject": "primary-source-not-established"}]
        self.rows[0]["pin"] = None
        self.assertBlocked("unknown-field-scope")

    def test_pending_measurement_is_open_without_missing_coverage(self):
        self.rows[0].update(disposition="PENDING", pending={"provisional_disposition": "WATCH", "measurement": "One named upstream comparison at this pin", "owner": "assigned-owner", "status": "NOT-RUN"})
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["pending_measurements"], 1)
        self.rows[0]["pending"]["provisional_disposition"] = "ADOPT-NOW"
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_reject_requires_named_searched_source(self):
        self.rows[0]["disposition"] = "REJECT"
        with self.assertRaises(compact.CompactError):
            self.build()
        self.rows[0]["searched"] = "Pinned README and vendor release entry"
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")

    def test_source_only_can_never_establish_native_adoption(self):
        self.rows[0]["disposition"] = "ADOPT-NOW"
        with self.assertRaises(compact.CompactError):
            self.build()
        self.rows[0].update(disposition="WATCH", evidence_class="RECORDED-LIVE-ACCEPTANCE")
        with self.assertRaises(compact.CompactError):
            self.build()

    def acceptance(self):
        row = self.rows[0]
        row.update(disposition="ADOPT-NOW", evidence_class="RECORDED-LIVE-ACCEPTANCE")
        receipt = {**self.row_key(row), "pin": row["pin"], "evidence_class": row["evidence_class"], "executed": True,
                   "status": "PASS", "exit_code": 0, "command": "synthetic recorded vendor acceptance command", "evidence_scope": "synthetic receipt consistency fixture",
                   "vendor_install": {"executed": True, "status": "PASS", "command": "synthetic vendor installation"},
                   "check": {"executed": True, "status": "PASS", "command": "synthetic vendor check"},
                   "inverse": {"command": "synthetic vendor cleanup"},
                   "native_clients": [{"client": name, "executed": True, "status": "PASS"} for name in ("claude", "codex")]}
        self.bind_receipt(receipt)
        return receipt

    def bind_receipt(self, receipt):
        capture = raw({"receipts": [receipt]})
        self.files["captures/native-receipt.json"] = capture
        self.rows[0]["acceptance_witness"] = {"archive_member": "captures/native-receipt.json", "sha256": digest(capture), "pointer": "/receipts/0"}

    def test_recorded_acceptance_requires_exact_executed_both_client_witness(self):
        receipt = self.acceptance()
        manifest, _ = self.build()
        self.assertEqual(manifest["counts"]["by_disposition"]["ADOPT-NOW"], 1)
        for mutate in (lambda r: r.update(executed=False), lambda r: r.update(exit_code=1), lambda r: r.update(slot="workers"),
                       lambda r: r.update(qualification={"role": "different"}), lambda r: r.update(native_clients=r["native_clients"][:1]),
                       lambda r: r["vendor_install"].update(executed=False)):
            changed = deepcopy(receipt)
            mutate(changed)
            self.bind_receipt(changed)
            with self.assertRaises(compact.CompactError):
                self.build()

    def test_receipt_pointer_must_resolve_and_cannot_point_at_projected_metadata(self):
        self.acceptance()
        self.rows[0]["acceptance_witness"]["pointer"] = "/receipts/9"
        with self.assertRaises(compact.CompactError):
            self.build()
        self.rows[0]["acceptance_witness"].update(archive_member="compact/rows.json", sha256=digest(raw(self.rows)))
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_missing_extra_or_duplicated_census_rows_are_not_green(self):
        self.coverage["expected_keys"].pop()
        self.assertBlocked("row-census-mismatch")
        self.coverage["expected_keys"].append(self.row_key(self.rows[-1]))
        self.coverage["expected_keys"].append(self.row_key(self.rows[-1]))
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_exact_368_star_census_and_explicit_out_of_scope_are_required(self):
        self.coverage["starred_identities"].append("example/not-dispositioned")
        self.assertBlocked("undispositioned-stars")
        self.coverage["starred_identities"].pop()
        self.rows[-1]["disposition"] = "OUT-OF-SCOPE"
        manifest, _ = self.build()
        self.assertEqual(manifest["counts"]["represented_stars"], 368)

    def test_unfrozen_union_omissions_or_empty_population_census_block(self):
        self.coverage["status"] = "INCOMPLETE"
        self.assertBlocked("complete-list-union-not-frozen")
        self.coverage["status"] = "FROZEN"
        self.coverage["omissions"] = ["One named producer inventory is not frozen"]
        self.assertBlocked("declared-omissions")
        self.coverage["omissions"] = []
        self.coverage["list_populations"] = []
        self.assertBlocked("no-mined-list-population-census")

    def test_deduplicated_decision_retains_each_physical_list_occurrence(self):
        self.rows[0]["source_refs"].pop()
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "BLOCKED")
        self.assertEqual(manifest["counts"]["expected_occurrences"], 2)
        self.assertEqual(manifest["counts"]["retained_occurrences"], 1)
        self.assertEqual(manifest["validation"]["blockers"][0]["code"], "unretained-list-occurrence")

    def test_false_occurrence_pointer_or_identity_never_matches_by_hash_alone(self):
        self.rows[0]["source_refs"][1]["pointer"] = "/wrong-row"
        self.assertBlocked("unretained-list-occurrence")

    def test_identical_fake_pointer_on_census_and_row_is_not_original_evidence(self):
        self.rows[0]["source_refs"][1]["pointer"] = "/wrong-row"
        self.coverage["list_populations"][0]["expected_occurrences"][1]["pointer"] = "/wrong-row"
        self.add_authority_witnesses()
        self.assertBlocked("unresolved-capture-pointer")

    def test_paired_projected_identity_cannot_overwrite_original_entry_scope(self):
        occurrence = self.coverage["list_populations"][0]["expected_occurrences"][1]
        occurrence["slot"] = "workers"
        moved = deepcopy(self.rows[0])
        moved["slot"] = "workers"
        moved["source_refs"] = [self.rows[0]["source_refs"].pop()]
        self.rows.append(moved)
        self.coverage["expected_keys"].append(self.row_key(moved))
        self.add_authority_witnesses()
        self.assertBlocked("original-list-occurrence-identity-scope-mismatch")

    def test_zero_projected_population_cannot_drop_original_frozen_census(self):
        self.coverage["list_populations"][0]["expected_occurrences"] = []
        self.rows[0]["source_refs"] = []
        self.assertBlocked("original-list-census-unfrozen-or-mismatched")

    def test_missing_original_inventory_and_foreign_population_pin_are_not_green(self):
        self.coverage.pop("source_inventory_witness")
        self.assertBlocked("frozen-source-inventory-witness-missing")
        self.coverage["list_populations"][0]["pin"] = pin("another/awesome", "b" * 40, "source-entry")
        with self.assertRaises(compact.CompactError):
            self.build()

    def test_368_substituted_star_identities_cannot_replace_original_census(self):
        self.rows[-1] = self.row("example/substituted-star")
        self.coverage["expected_keys"][-1] = self.row_key(self.rows[-1])
        self.coverage["starred_identities"][-1] = "example/substituted-star"
        self.assertBlocked("original-star-census-unbound-or-mismatched")

    def test_unknown_star_wrapper_cannot_bypass_original_census_binding(self):
        for unsupported in ({}, {"unrecognized": []}, False):
            with self.subTest(wrapper=unsupported):
                self.coverage["star_inventory_witness"] = self.witness("unsupported-star-census", unsupported)
                self.assertBlocked("unsupported-original-star-inventory")

    def test_null_authority_or_occurrence_selection_is_always_blocked(self):
        for name in ("source_inventory_witness", "field_inventory_witness"):
            with self.subTest(witness=name):
                original = self.coverage[name]
                self.coverage[name] = self.witness("null-authority", None)
                self.assertBlocked("null-capture-selection")
                self.coverage[name] = original
        population = self.coverage["list_populations"][0]
        for name in ("source_witness", "census_witness"):
            with self.subTest(witness=name):
                original = population[name]
                population[name] = self.witness("null-population", None)
                self.assertBlocked("null-capture-selection")
                population[name] = original

    def test_unbound_source_refs_and_uninventoried_field_selectors_are_blocked(self):
        self.rows[0]["source_refs"].append({"sha256": "f" * 64, "pointer": "/unknown"})
        self.assertBlocked("unbound-source-reference")
        self.rows[1]["slot"] = "invented-valid-kebab-selector"
        self.coverage["expected_keys"][1] = self.row_key(self.rows[1])
        self.assertBlocked("unbound-field-selector")

    def test_decoder_byte_and_metadata_bounds_cover_hidden_tar_headers(self):
        reader = compact.BoundedReader(io.BytesIO(b"x" * 10))
        reader.read_bytes = compact.UNPACKED_LIMIT - 4
        with self.assertRaises(compact.CompactError):
            reader.read(5)
        header = tarfile.TarInfo("hidden-pax")
        header.type = tarfile.XHDTYPE
        header.size = 2 * 1024**2
        with self.assertRaises(compact.CompactError):
            compact.BoundedTarInfo.frombuf(header.tobuf(), "utf-8", "strict")

    def test_manifest_asset_and_release_bindings_cannot_be_edited(self):
        asset = self.archive()
        manifest, original = compact.build_manifest(asset, "v2026.10.08")
        path = self.directory / "manifest.json"
        manifest["asset"]["sha256"] = "f" * 64
        path.write_bytes(raw(manifest))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(compact.main(["--asset", str(asset), "--manifest", str(path), "--check"]), 2)
        with self.assertRaises(compact.CompactError):
            compact.build_manifest(asset, "v2026.10.09")
        _, rebuilt = compact.build_manifest(asset, "v2026.10.08")
        self.assertEqual(rebuilt, original)

    def test_duplicate_json_keys_reject_without_last_write_wins(self):
        with self.assertRaises(compact.CompactError):
            compact.load(b'{"rows": [], "rows": []}')

    def native_entry(self):
        """A bounded synthetic native-format witness, not an upstream mining replay."""
        repository = "example/project-0"
        markdown = b"# Pinned list\n- [Candidate](https://github.com/example/project-0)\n"
        self.files["captures/native-list.md"] = markdown
        values = {name: "" for name in compact.NATIVE_LIST_HEADER}
        values.update(input_id="example/awesome:README.md:2", source_kind="awesome-list", source_repository="example/awesome", source_pin="b" * 40,
                      source_path="README.md", source_line="2", source_content_sha256=digest(markdown), linked_repository=repository,
                      linked_targets_json=json.dumps([{"url": "https://github.com/EXAMPLE/project-0", "repository": repository}]),
                      layer_fit="native-clients", relevant_slot="true", disposition="WATCH", verification_status="SOURCE-LIST-SCOPE-CHECKED; LINKED-CODE-UNVERIFIED")
        self.native_values = values
        self.bind_native_tsv()
        row = self.rows[0]
        row.update(pin=pin("example/awesome", "b" * 40, "source-entry"), decision_scope="source-entry-screen", candidate_implementation_status="UNESTABLISHED",
                   archive_member="captures/native-list.md", capture_sha256=digest(markdown),
                   source_entry_witness={"archive_member": "captures/native-list-screen.tsv", "sha256": digest(self.files["captures/native-list-screen.tsv"]), "pointer": "line:2"})
        row["primary_sources"] = [{"locator": "example/awesome@" + "b" * 40 + ":README.md:2", "pin": row["pin"], "subject": "original pinned list entry, not implementation acceptance"}]
        return row

    def bind_native_tsv(self):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(compact.NATIVE_LIST_HEADER)
        writer.writerow([self.native_values[name] for name in compact.NATIVE_LIST_HEADER])
        self.files["captures/native-list-screen.tsv"] = stream.getvalue().encode()
        if "source_entry_witness" in self.rows[0]:
            self.rows[0]["source_entry_witness"]["sha256"] = digest(self.files["captures/native-list-screen.tsv"])

    def test_native_original_tsv_binds_pinned_markdown_repository_and_literal_slot(self):
        row = self.native_entry()
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")
        self.assertEqual(manifest["counts"]["candidate_implementation_unestablished"], 1)
        row["source_entry_witness"]["pointer"] = "#L2"
        row["primary_sources"][0]["locator"] = "https://github.com/example/awesome/blob/" + "b" * 40 + "/README.md#L2"
        manifest, _ = self.build()
        self.assertEqual(manifest["validation"]["status"], "PASS")

    def test_native_tsv_source_metadata_mismatches_are_blocked(self):
        row = self.native_entry()
        original = deepcopy(self.native_values)
        for name, value in (("layer_fit", "workers"), ("source_pin", "c" * 40), ("source_repository", "another/awesome"),
                            ("source_path", "Different.md"), ("source_line", "3"), ("source_content_sha256", "d" * 64),
                            ("linked_repository", "another/project"), ("input_id", "wrong-id")):
            with self.subTest(field=name):
                self.native_values = {**original, name: value}
                self.bind_native_tsv()
                self.assertBlocked("native-source-entry-witness-unverified")
        self.native_values = original
        self.bind_native_tsv()
        row["qualification"] = {"slot": "workers"}
        self.coverage["expected_keys"][0] = self.row_key(row)
        self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_rejects_ambiguous_physical_lines_header_and_width(self):
        row = self.native_entry()
        valid = self.files["captures/native-list-screen.tsv"]
        for data in (valid.replace(b"input_id", b"renamed_id", 1), valid.rstrip(b"\n") + b"\textra\n",
                     valid.replace(b"example/awesome:README.md:2", b'"example/awesome:\nREADME.md:2"', 1)):
            with self.subTest(data_sha=digest(data)):
                self.files["captures/native-list-screen.tsv"] = data
                row["source_entry_witness"]["sha256"] = digest(data)
                self.assertBlocked("native-source-entry-witness-unverified")
        self.files["captures/native-list-screen.tsv"] = valid
        row["source_entry_witness"]["sha256"] = digest(valid)
        for locator in ("line:1", "line:3"):
            row["source_entry_witness"]["pointer"] = locator
            self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_generated_json_wrapper_is_not_an_original_entry(self):
        row = self.native_entry()
        wrapper = raw({"rows": [self.native_values]})
        self.files["captures/native-list-screen.tsv"] = wrapper
        row["source_entry_witness"]["sha256"] = digest(wrapper)
        row["source_entry_witness"]["pointer"] = "line:1"
        self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_candidate_link_is_exact_without_domain_query_or_path_guesses(self):
        row = self.native_entry()
        for link in ("https://github.example.com/example/project-0", "https://github.com/example/project-0?x=1", "https://github.com/example/project-0/tree/main",
                     "https://github.com/another/project", "https://github.com/example/project-0#readme"):
            with self.subTest(link=link):
                markdown = ("# Pinned list\n- [Candidate](" + link + ")\n").encode()
                self.files["captures/native-list.md"] = markdown
                row["capture_sha256"] = digest(markdown)
                self.native_values["source_content_sha256"] = digest(markdown)
                self.bind_native_tsv()
                self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_href_rejects_dot_segments_and_invalid_github_owners(self):
        for href in ("https://github.com/example/.", "https://github.com/example/..", "https://github.com/-owner/repository"):
            with self.subTest(href=href):
                with self.assertRaises(compact.CompactError):
                    compact.github_repository_href(href)

    def test_native_tsv_link_metadata_must_match_primary_markdown_href(self):
        self.native_entry()
        for target in ({"url": "https://github.com/another/project", "repository": "example/project-0"},
                       {"url": "https://github.com/example/project-0", "repository": "another/project"},
                       {"url": "https://github.com/example/project-0?x=1", "repository": "example/project-0"}):
            self.native_values["linked_targets_json"] = json.dumps([target])
            self.bind_native_tsv()
            self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_markdown_line_number_uses_physical_newlines_only(self):
        row = self.native_entry()
        markdown = "# Pinned list\u2028- [Candidate](https://github.com/example/project-0)\n".encode()
        self.files["captures/native-list.md"] = markdown
        row["capture_sha256"] = digest(markdown)
        self.native_values["source_content_sha256"] = digest(markdown)
        self.bind_native_tsv()
        self.assertBlocked("native-source-entry-witness-unverified")

    def test_native_tsv_source_entry_cannot_promote_implementation_merit_or_execution(self):
        row = self.native_entry()
        row["decision_scope"] = "implementation-merit"
        self.assertBlocked("native-source-entry-witness-scope-unqualified")
        row["disposition"] = "ADOPT-NOW"
        with self.assertRaises(compact.CompactError):
            self.build()

    def native_skill(self, skill_hash=None):
        schema = json.loads(compact.NATIVE_SKILLS_SCHEMA.read_bytes())
        entry = "Example/SkillRepo@safe-skill"
        proposal = {"skill_ref": entry, "source_id": "synthetic-native-schema-control", "lifecycle_task": "mcp-build", "pin": "a" * 40,
                    "skill_md_sha256": skill_hash, "license": "MIT", "source": "synthetic original native-role fixture",
                    "description_chars": 10, "model_invocable": True, "codex_implicit": True, "replaces": None,
                    "proposed_label": "keep_but_compare", "demonstrated_gap": "No native acceptance; source-binding fixture only.",
                    "evidence": ["https://github.com/Example/SkillRepo/blob/" + "a" * 40 + "/skills/safe-skill/SKILL.md"],
                    "upstream_now": {name: None for name in schema["properties"]["proposed"]["items"]["properties"]["upstream_now"]["required"]},
                    "comparison_that_would_overturn": "promptfoo maintained comparison; NOT RUN"}
        self.skill_doc = {"calls": {}, "layer_id": "skills-mcp-build", "notes": [], "proposed": [proposal], "skills_used": []}
        self.files["captures/native-skills-discovery.json"] = raw(self.skill_doc)
        p = pin("Example/SkillRepo")
        self.rows[0].update(repository_or_entry=entry, slot="skills-mcp-build", disposition="PENDING", evidence_class="DOCUMENTARY", pin=p,
                            primary_sources=[{"locator": "https://github.com/Example/SkillRepo/tree/" + "a" * 40, "pin": p, "subject": "native containing repository, exact SKILL bytes unestablished"}],
                            capture_sha256=digest(self.files["captures/native-skills-discovery.json"]), archive_member="captures/native-skills-discovery.json",
                            source_pointer="/proposed/0", pending={"provisional_disposition": "WATCH", "measurement": "Verify original pinned SKILL body then a maintained comparison", "owner": "assigned-owner"})
        self.rows[0].pop("source_refs", None)
        return self.rows[0]

    def skill_check(self):
        row = self.rows[0]
        index = {member: {"sha256": digest(data), "bytes": len(data)} for member, data in self.files.items()}
        blockers = [{"code": code} for code in compact.validate_row(row, index)]
        compact.validate_native_skill_entry(row, index, self.files, {}, blockers)
        return blockers

    def rebind_skill_doc(self):
        data = raw(self.skill_doc)
        self.files["captures/native-skills-discovery.json"] = data
        self.rows[0]["capture_sha256"] = digest(data)

    def test_native_composite_skill_parent_pin_remains_valid_but_null_skill_body_blocks(self):
        row = self.native_skill()
        blockers = self.skill_check()
        self.assertEqual([b["code"] for b in blockers], ["skill-entry-primary-bytes-unestablished"])
        self.assertEqual(compact.canonical(row["repository_or_entry"]), "example/skillrepo@safe-skill")

    def test_native_skill_wrong_name_task_pin_and_wrapper_never_bind(self):
        self.native_skill()
        original = deepcopy(self.skill_doc)
        for mutate in (lambda d: d["proposed"][0].update(skill_ref="Example/SkillRepo@another-skill"),
                       lambda d: d["proposed"][0].update(lifecycle_task="debug"),
                       lambda d: d.update(layer_id="skills-debug"),
                       lambda d: d["proposed"][0].update(pin="b" * 40),
                       lambda d: d.update(generated_row_wrapper=True)):
            self.skill_doc = deepcopy(original)
            mutate(self.skill_doc)
            self.rebind_skill_doc()
            self.assertTrue(any(b["code"] == "native-skill-entry-witness-unverified" for b in self.skill_check()))

    def test_native_skill_hash_requires_actual_pinned_skill_body_not_metadata(self):
        body = b"---\nname: safe-skill\ndescription: synthetic fixture\n---\n# Instructions\n"
        row = self.native_skill(digest(body))
        self.assertEqual(self.skill_check()[0]["code"], "skill-entry-primary-bytes-unestablished")
        self.files["captures/SKILL.md"] = body
        row["primary_sources"] = [{"locator": self.skill_doc["proposed"][0]["evidence"][0], "pin": row["pin"], "subject": "original pinned SKILL.md bytes",
                                   "archive_member": "captures/SKILL.md", "capture_sha256": digest(body)}]
        self.assertEqual(self.skill_check(), [])
        for wrong_path in ("skills/other-skill/SKILL.md", "skills/safe-skill/README.md"):
            row["primary_sources"][0]["locator"] = "https://github.com/Example/SkillRepo/blob/" + "a" * 40 + "/" + wrong_path
            self.assertEqual(self.skill_check()[0]["code"], "skill-entry-primary-bytes-unestablished")
        for metadata in (raw({"skill_ref": row["repository_or_entry"], "declared_source": "SKILL.md"}),
                         b'\xef\xbb\xbf{"declared_source":"SKILL.md"}', b"true", b"null", b'"receipt string"', b"42"):
            with self.subTest(metadata_sha=digest(metadata)):
                self.files["captures/SKILL.md"] = metadata
                self.skill_doc["proposed"][0]["skill_md_sha256"] = digest(metadata)
                self.rebind_skill_doc()
                row["primary_sources"][0].update(locator=self.skill_doc["proposed"][0]["evidence"][0], capture_sha256=digest(metadata))
                self.assertEqual(self.skill_check()[0]["code"], "skill-entry-primary-bytes-unestablished")

    def test_native_skill_containing_repo_and_pending_scope_are_strict(self):
        row = self.native_skill()
        row["pin"]["repository_or_source"] = "another/repository"
        with self.assertRaises(compact.CompactError):
            self.skill_check()
        row["pin"]["repository_or_source"] = "Example/SkillRepo"
        row.pop("pending")
        row["disposition"] = "WATCH"
        self.assertTrue(any(b["code"] == "skill-entry-source-scope-unqualified" for b in self.skill_check()))

    @unittest.skipUnless(os.environ.get("G5_NATIVE_SKILL_ORIGINAL"), "immutable original native-skills capture is not supplied")
    def test_actual_native_mcp_migration_entry_retains_parent_pin_and_null_body_hold(self):
        source = Path(os.environ["G5_NATIVE_SKILL_ORIGINAL"]).read_bytes()
        self.assertEqual(digest(source), "487ac7ed4da2742ac6db3d2a9a4c4505387dc03efdfc8678a846d9f51a6875c9")
        original = json.loads(source)
        proposal = original["proposed"][1]
        self.assertEqual(proposal["skill_ref"], "AlpayC/mcp-migration-check@mcp-migration")
        row = self.native_skill()
        p = pin("AlpayC/mcp-migration-check", proposal["pin"])
        self.files["captures/native-skills-discovery.json"] = source
        row.update(repository_or_entry=proposal["skill_ref"], pin=p, capture_sha256=digest(source), source_pointer="/proposed/1",
                   primary_sources=[{"locator": "https://github.com/AlpayC/mcp-migration-check/tree/" + proposal["pin"], "pin": p, "subject": "original containing repository pin"}])
        self.assertEqual(self.skill_check(), [{"code": "skill-entry-primary-bytes-unestablished", "source": "alpayc/mcp-migration-check@mcp-migration:skills-mcp-build"}])

    @unittest.skipUnless(os.environ.get("G5_NATIVE_ENTRY_EXAMPLES"), "immutable external native-example packet is not supplied")
    def test_three_immutable_native_trading_examples_without_mining_replay(self):
        example_path = Path(os.environ["G5_NATIVE_ENTRY_EXAMPLES"])
        packet = example_path.read_bytes()
        self.assertEqual(digest(packet), "0addb266fbcc32969e67fd3117d41f531879826809787fcb9ca02f9a24fc13d4")
        examples = json.loads(packet)["examples"]
        base = example_path.parent.parent
        for example in examples:
            with self.subTest(repository=example["repository_or_entry"]):
                tsv, primary = example["original_native_tsv"], example["original_primary_list"]
                captures = {}
                for member, expected in ((tsv["archive_member"], tsv["sha256"]), (primary["archive_member"], primary["capture_sha256"])):
                    local = base / member.removeprefix("g5-fields-b/")
                    captured = local.read_bytes()
                    self.assertEqual(digest(captured), expected)
                    captures[member] = captured
                p = pin(primary["repository"], primary["pin"], "source-entry")
                row = {"repository_or_entry": example["repository_or_entry"], "slot": example["qualification"]["slot"],
                       "qualification": example["qualification"], "disposition": "WATCH", "evidence_class": "SOURCE-REVIEW", "pin": p,
                       "primary_sources": [{"locator": primary["repository"] + "@" + primary["pin"] + ":" + primary["path"] + ":" + str(primary["line"]), "pin": p, "subject": "original pinned list entry"}],
                       "capture_sha256": primary["capture_sha256"], "archive_member": primary["archive_member"], "owner_lane": "g5-fields-b",
                       "refresh_date": "2026-10-08", "decision_scope": "source-entry-screen", "candidate_implementation_status": "UNESTABLISHED",
                       "source_entry_witness": {"archive_member": tsv["archive_member"], "sha256": tsv["sha256"], "pointer": "line:" + str(tsv["line"])}}
                index = {member: {"sha256": digest(value), "bytes": len(value)} for member, value in captures.items()}
                self.assertEqual(compact.validate_row(row, index), [])
                blockers, cache = [], {}
                result = compact.validate_native_source_entry(row, index, captures, cache, blockers)
                self.assertEqual(result, example["literal_dispatch_matches"])
                self.assertEqual(bool(blockers), not example["literal_dispatch_matches"])
                if not result:
                    self.assertIn("layer_fit differs", blockers[0]["reason"])


if __name__ == "__main__":
    unittest.main()
