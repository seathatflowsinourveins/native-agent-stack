"""Synthetic artifact-integrity controls; these are not upstream or host acceptance."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
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
