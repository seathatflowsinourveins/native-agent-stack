"""Contract tests for scripts/catalog_index.py, the ranked catalog index
(docs/decisions/2026-09-29-catalog-index-ranking.md).

Every test except the last builds its own fixture repository: the two verdict ledgers, a committed component
evidence matrix that mirrors them, a decision index that scripts/catalog_decisions.py generates from its base
sources, the stack, the evidence manifest and the landscape manifest. Fixture repositories are made up; only
test_the_committed_repository_index_is_current reads the real tree. Tests are numbered as in the build spec.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import catalog_decisions as cd
from scripts import catalog_index as ci
from scripts import component_matrix as cm
from scripts import host_receipts as hr
from scripts import new_host_grand_list as grand_list

REPO_ROOT = Path(__file__).resolve().parents[1]
LINUX, MACOS = "linux-wsl2-x86_64", "macos-arm64"
FOUNDATION_LEDGER, TRADING_LEDGER = "catalogs/landscape/foundation.json", "catalogs/landscape/us-equities.json"
CARD_FILES = ("foundation-memory", "agents-operations", "data-research", "engines-strategies")
SEQUENCE = ("python3 scripts/component_matrix.py --write, python3 scripts/new_host_grand_list.py --write, "
            "python3 scripts/catalog_index.py --write, then python3 scripts/validate.py")
PENDING_NOTE = ("No recorded verdict: every entry is a historical candidate card; the order is candidate-card "
                "evidence only, not a selection.")


def _write_json(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _github(name: str) -> str:
    return "https://github.com/" + name


def W(name, component_id=None, *, repository=None, evidence_class="native_proven", declared="accepted",
      derived="accepted", host_verified=False, macos="untested", passes=1, fails=0, reviewed_passes=None,
      pin="1.0.0", pin_current="true", latest="2026-09-20T00:00:00Z", evidence_refs=()):
    """A recorded winner as the matrix states it on linux-wsl2-x86_64: ``declared`` is the ledger's catalog status,
    ``derived`` what scripts/platform_status.py derives, ``host_verified`` the matrix's e2e_state host_verified."""
    return {"role": "winner", "name": name, "repository": repository or _github(name),
            "component_id": component_id or name.split("/")[1], "pin": pin, "evidence_class": evidence_class,
            "declared": declared, "derived": derived, "host_verified": host_verified, "macos": macos,
            "passes": passes, "fails": fails,
            "reviewed_passes": (1 if host_verified else 0) if reviewed_passes is None else reviewed_passes,
            "pin_current": pin_current, "latest": latest, "evidence_refs": list(evidence_refs)}


def A(name, *, repository=None, disposition="conditional", evidence_class="source_review", e2e_state="not_run"):
    """A verdict alternative as the matrix states it."""
    return {"role": "alternative", "name": name, "repository": repository or _github(name),
            "disposition": disposition, "evidence_class": evidence_class, "e2e_state": e2e_state}


def C(name, *, repository=None, disposition="unqualified", evidence_kind="source_review",
      evidence_refs=("https://example.org/review",)):
    """A historical candidate card of the ledger layer."""
    return {"role": "candidate", "name": name, "repository": repository or _github(name),
            "disposition": disposition, "evidence_kind": evidence_kind, "evidence_refs": list(evidence_refs)}


def _receipts(passes, fails, reviewed, latest):
    return {"pass": passes, "fail": fails, "independently_reviewed_pass": reviewed,
            "independently_reviewed_fail": 0, "dissented": 0, "latest": latest}


class Tree:
    """A fixture repository holding every input scripts/catalog_index.py reads."""

    def __init__(self, root: Path):
        self.root = root
        self.layers: list[dict] = []
        self.aliases: dict[str, str] = {}
        self.extra_repositories: set[str] = set()
        self.outside_universe: set[str] = set()
        self.stack: list[dict] = []
        self.cards: dict[str, list[dict]] = {}
        self.receipts: list[dict] = []
        self.convergence_records: list[str] = []
        self.files: dict[str, object] = {}

    def layer(self, layer_id, *records, catalog="foundation", verdict_status="recorded", reopened=False,
              metric="task success on the frozen fixture", decision="retain", title=None):
        self.layers.append({"layer_id": layer_id, "catalog": catalog, "records": list(records),
                            "verdict_status": verdict_status, "reopened": reopened, "metric": metric,
                            "decision": decision, "title": title or f"Title {layer_id}"})
        return self

    def universe(self) -> set[str]:
        names = set()
        values = [record["repository"] for layer in self.layers for record in layer["records"]]
        values += [_github(component["repository"]) for component in self.stack]
        values += [_github(name) for name in self.extra_repositories]
        for value in values:
            try:
                names.add(cd.canonical(cd.identity(value), self.aliases))
            except cd.InvalidDecisionIndex:
                continue
        return names - self.outside_universe

    @staticmethod
    def ledger_layer(layer: dict) -> dict:
        pending = layer["verdict_status"] == "pending_lanes"
        records = layer["records"]
        return {
            "catalog": layer["catalog"], "layer_id": layer["layer_id"], "title": layer["title"],
            "requirement": "fixture requirement", "decision": layer["decision"], "checked_at": "2026-09-22",
            "verdict_status": layer["verdict_status"],
            "lanes": {"claude": {}, "codex": {}, "agreement": "pending" if pending else "same_winner"},
            "winners": [{"component_id": r["component_id"], "repository": r["repository"], "pin": r["pin"],
                         "evidence_class": r["evidence_class"], "why_selected": "fixture",
                         "evidence_refs": r["evidence_refs"],
                         "platform_status": {LINUX: r["declared"], MACOS: "untested"}}
                        for r in records if r["role"] == "winner"],
            "alternatives": [{"name": r["name"], "repository": r["repository"], "disposition": r["disposition"],
                              "evidence_class": r["evidence_class"], "why_not_default": "fixture",
                              "evidence_refs": [], "source": "star"}
                             for r in records if r["role"] == "alternative"],
            "candidates": [{"name": r["name"], "repository": r["repository"], "disposition": r["disposition"],
                            "evidence_kind": r["evidence_kind"], "rationale": "fixture",
                            "evidence_refs": r["evidence_refs"]}
                           for r in records if r["role"] == "candidate"],
            "overturn_protocol": {"metric": layer["metric"], "arms": [], "fixture_paths": []},
            "open_gaps": [],
        }

    @staticmethod
    def matrix_winner(r: dict) -> dict:
        return {"component_id": r["component_id"], "repository": r["repository"], "pin": r["pin"],
                "evidence_class": r["evidence_class"], "lifecycle_stages": [],
                "platforms": {
                    LINUX: {"catalog_status": r["declared"], "derived_status": r["derived"],
                            "derived_reason": "fixture",
                            "e2e_state": "host_verified" if r["host_verified"] else r["declared"],
                            "host_receipts": _receipts(r["passes"], r["fails"], r["reviewed_passes"], r["latest"]),
                            "qualified_models": [], "alias_receipts": []},
                    MACOS: {"catalog_status": "untested", "derived_status": r["macos"], "derived_reason": "fixture",
                            "e2e_state": "untested", "host_receipts": _receipts(0, 0, 0, None),
                            "qualified_models": [], "alias_receipts": []}}}

    @classmethod
    def matrix_row(cls, layer: dict) -> dict:
        pending = layer["verdict_status"] == "pending_lanes"
        state = "pending_lanes" if pending else "recorded_reopened" if layer["reopened"] else "confirmed_current"
        winners = [r for r in layer["records"] if r["role"] == "winner"]
        return {
            "catalog": layer["catalog"], "layer_id": layer["layer_id"], "title": layer["title"],
            "verdict_status": layer["verdict_status"],
            "independent_review": "pending_lanes" if pending else "dual_lane_same_winner",
            "adjudication_ref": None, "open_executable_now_gaps": 0, "open_gaps": 3,
            "winners": [cls.matrix_winner(r) for r in winners],
            "alternatives": [{"name": r["name"], "repository": r["repository"], "disposition": r["disposition"],
                              "evidence_class": r["evidence_class"], "e2e_state": r["e2e_state"]}
                             for r in layer["records"] if r["role"] == "alternative"],
            "convergence": {
                "layer_state": state, "verdict_checked_at": "2026-09-22",
                "reopened_by": [{"sweep_id": "sweep-0926", "date": "2026-09-26"}] if layer["reopened"] else [],
                "components": [{"id": r["component_id"], "winner_ids": [r["component_id"]],
                                "pin_current": r["pin_current"]} for r in winners if r["pin_current"] is not None]},
        }

    def write(self) -> None:
        root = self.root
        names = self.universe()
        _write_json(root / "catalogs/us-equities/coverage.json", {
            "schema_version": 1, "aliases": self.aliases,
            "stars": [{"repository": name} for name in sorted(names)]})
        _write_json(root / "catalogs/us-equities/star-audit.json", {"schema_version": 1, "entries": []})
        for stem in CARD_FILES:
            _write_json(root / f"catalogs/us-equities/{stem}.json",
                        {"schema_version": 1, "entries": self.cards.get(stem, [])})
        _write_json(root / "manifests/candidates.json", {"schema_version": 1, "candidates": []})
        _write_json(root / "adoption/research.json", {"schema_version": 1, "candidates": []})
        if not (root / "catalogs/us-equities/manifest.json").exists():
            _write_json(root / "catalogs/us-equities/manifest.json", {"schema_version": 1})
        _write_json(root / "manifests/stack.json", {"schema_version": 1, "components": [
            {"id": c["id"], "repository": _github(c["repository"]), "profile": c.get("profile", "core"),
             "version": "1.0.0"} for c in self.stack], "profiles": [], "models": []})
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = cd.main(["--root", str(root), "--write"])
        if code != 0:
            raise AssertionError("fixture decision index: " + printed.getvalue())
        for catalog, ledger in (("foundation", FOUNDATION_LEDGER), ("us-equities", TRADING_LEDGER)):
            _write_json(root / ledger, {"schema_version": 2, "checked_at": "2026-09-22", "scope": "fixture",
                                        "layers": [self.ledger_layer(layer) for layer in self.layers
                                                   if layer["catalog"] == catalog]})
        rows = sorted((self.matrix_row(layer) for layer in self.layers),
                      key=lambda row: (row["catalog"], row["layer_id"]))
        _write_json(root / cm.OUTPUT_JSON, {
            "schema_version": 1, "checked_at": "2026-09-27", "scope": "fixture", "rows": rows,
            "summary": {"convergence": {"newest_manifest": {
                "path": "catalogs/sota-convergence/manifest-20260926.json", "id": "fixture",
                "checked_at": "2026-09-26"}}}})
        _write_json(root / "manifests/evidence.json", {
            "schema_version": 1, "receipts": self.receipts, "files": [],
            "convergence_records": self.convergence_records})
        _write_json(root / "catalogs/landscape/manifest.json", {
            "schema_version": 1, "universal_superiority": "not_established",
            "sources": {"trading_taxonomy": "catalogs/sota-convergence/manifest-20260922.json",
                        "repository_index": cd.INDEX}})
        _write_json(root / "catalogs/saturation/ledger.json", {"schema_version": 1, "sweeps": []})
        for relative, document in self.files.items():
            _write_json(root / relative, document)


class IndexCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tree = Tree(self.root)

    def build(self):
        """Write the fixture and build the index document in memory."""
        self.tree.write()
        return self.rebuild()

    def rebuild(self):
        with mock.patch.object(ci, "EXPECTED_LAYER_COUNT", len(self.tree.layers)):
            return ci.build_document(self.root)

    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(ci, "EXPECTED_LAYER_COUNT", len(self.tree.layers)), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = ci.main(["--root", str(self.root), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def edit(self, relative, change):
        path = self.root / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        change(document)
        _write_json(path, document)

    def layer(self, document, ref):
        found = [layer for layer in document.get("layers", []) if layer.get("ref") == ref]
        self.assertEqual(len(found), 1, f"layer {ref} is not in the index exactly once")
        return found[0]

    def placement(self, document, layer_ref, entity):
        found = [p for p in self.layer(document, layer_ref).get("placements", []) if p.get("entity") == entity]
        self.assertEqual(len(found), 1, f"{entity} is not ranked in {layer_ref} exactly once")
        return found[0]

    def entity(self, document, ref):
        found = [entity for entity in document.get("entities", []) if entity.get("ref") == ref]
        self.assertEqual(len(found), 1, f"entity {ref} is not listed exactly once")
        return found[0]

    @staticmethod
    def items(document, item_type):
        return [item for item in document.get("status_items", []) if item.get("type") == item_type]

    def ranks(self, document):
        """(layer, entity) -> (position, shared, sort_key) for every ranked placement."""
        ranks = {(layer["ref"], p["entity"]): (p.get("position"), p.get("shared"), p.get("sort_key"))
                 for layer in document.get("layers", []) for p in layer.get("placements", [])}
        self.assertTrue(ranks, "the index ranks nothing")
        return ranks


class IdentityTests(IndexCase):
    def test_alias_and_release_url_resolve_to_one_entity(self):  # 1
        self.tree.aliases = {"old-owner/tool": "new-owner/tool"}
        self.tree.layer("l1",
                        W("new-owner/tool", "tool",
                          repository="https://github.com/new-owner/tool/releases/tag/v1.0.0"),
                        A("example/alt"),
                        C("old-owner/tool", repository="https://github.com/Old-Owner/tool", disposition="selected"))
        document = self.build()
        layer = self.layer(document, "layer:foundation/l1")
        entities = [p["entity"] for p in layer["placements"]]
        self.assertEqual(entities.count("repo:new-owner/tool"), 1, entities)
        self.assertNotIn("repo:old-owner/tool", entities)
        placement = self.placement(document, "layer:foundation/l1", "repo:new-owner/tool")
        self.assertEqual(placement["role"], "winner")
        self.assertEqual(sorted(record["pointer"] for record in placement["role_records"]),
                         ["/layers/0/candidates/0", "/layers/0/winners/0"])
        self.assertIn("old-owner/tool", self.entity(document, "repo:new-owner/tool")["aliases"])
        self.assertNotIn("repo:old-owner/tool", [entity["ref"] for entity in document["entities"]])

    def test_unresolvable_identity_is_listed_with_reason_never_dropped(self):  # 2
        self.tree.outside_universe = {"gone/missing"}
        self.tree.layer("l1", W("example/win"), A("example/alt"),
                        C("gone/missing"), C("group/project", repository="https://gitlab.com/group/project"))
        document = self.build()
        unresolved = {(item["path"], item["pointer"]): item["reason"] for item in document.get("unresolved", [])}
        self.assertEqual(sorted(unresolved), [(FOUNDATION_LEDGER, "/layers/0/candidates/0"),
                                              (FOUNDATION_LEDGER, "/layers/0/candidates/1")])
        self.assertTrue(all(isinstance(reason, str) and reason.strip() for reason in unresolved.values()))
        self.assertEqual(len(self.items(document, "identity/unresolved")), 2)
        layer = self.layer(document, "layer:foundation/l1")
        self.assertEqual(layer["counts"]["records"], 4)
        self.assertEqual(layer["counts"]["unresolved_records"], 2)
        self.assertEqual(layer["counts"]["placements"], 2)

    def test_one_placement_per_layer_and_entity_keeps_all_role_records(self):  # 3
        self.tree.layer("l1", W("example/tool", "tool"), A("example/other"),
                        C("example/tool", disposition="selected"), C("example/other", disposition="conditional"))
        document = self.build()
        layer = self.layer(document, "layer:foundation/l1")
        self.assertEqual(sorted(p["entity"] for p in layer["placements"]),
                         ["repo:example/other", "repo:example/tool"])
        tool = self.placement(document, "layer:foundation/l1", "repo:example/tool")
        self.assertEqual(tool["role"], "winner")
        self.assertEqual(sorted((r["role"], r["pointer"], r["disposition"]) for r in tool["role_records"]),
                         [("candidate", "/layers/0/candidates/0", "selected"), ("winner", "/layers/0/winners/0", None)])
        other = self.placement(document, "layer:foundation/l1", "repo:example/other")
        self.assertEqual(other["role"], "alternative")
        self.assertEqual(sorted((r["role"], r["disposition"]) for r in other["role_records"]),
                         [("alternative", "conditional"), ("candidate", "conditional")])

    def test_components_never_merged_by_repository(self):  # 4
        # The shape of one repository that carries two stack ids (a CLI and its SDK), each the winner of its own layer.
        self.tree.stack = [{"id": "alpha", "repository": "example/alpha", "profile": "core"},
                           {"id": "alpha-sdk", "repository": "example/alpha", "profile": "supporting"}]
        self.tree.receipts = [
            {"id": "sdk-receipt", "kind": "native_cli_e2e", "component_ids": ["alpha-sdk"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/sdk.json"},
            {"id": "cli-receipt", "kind": "native_cli_e2e", "component_ids": ["alpha"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/cli.json"}]
        self.tree.layer("clients", W("example/alpha", "alpha"), A("example/beta"))
        self.tree.layer("sdks", W("example/alpha", "alpha-sdk"), A("example/gamma"))
        document = self.build()
        entity = self.entity(document, "repo:example/alpha")
        self.assertEqual(entity["component_ids"], ["alpha", "alpha-sdk"])
        self.assertEqual(entity["stack_profiles"], ["core", "supporting"])
        self.assertEqual(entity["receipts"]["ids"], ["cli-receipt", "sdk-receipt"])
        self.assertEqual(self.placement(document, "layer:foundation/clients", "repo:example/alpha")["component_id"],
                         "alpha")
        self.assertEqual(self.placement(document, "layer:foundation/sdks", "repo:example/alpha")["component_id"],
                         "alpha-sdk")
        multiple = self.items(document, "identity/multiple-component-ids")
        self.assertEqual([item["refs"][0] for item in multiple], ["repo:example/alpha"])
        self.assertEqual(self.items(document, "identity/component-id-conflict"), [])
        self.assertEqual(document["counts"]["conservation"]["receipts"],
                         {"attached": 2, "listed": 2, "unattached": 0})


class PartitionTests(IndexCase):
    def test_out_of_scope_goes_outside_and_observed_failure_goes_to_caution(self):  # 5
        self.tree.layer("l1", W("example/win"), A("example/oos", disposition="out_of_scope"),
                        C("example/failed", disposition="observed_failure", evidence_kind="native_execution",
                          evidence_refs=("evidence/artifacts/run/result.json",)),
                        C("example/card-oos", disposition="out_of_scope"),
                        C("example/ok", disposition="conditional"))
        document = self.build()
        layer = self.layer(document, "layer:foundation/l1")
        self.assertEqual(sorted(p["entity"] for p in layer["placements"]), ["repo:example/ok", "repo:example/win"])
        self.assertEqual([(entry["entity"], entry["reason"]) for entry in layer["outside_ranking"]],
                         [("repo:example/card-oos", "out_of_scope"), ("repo:example/oos", "out_of_scope")])
        self.assertEqual([(entry["entity"], entry["reason"]) for entry in layer["caution"]],
                         [("repo:example/failed", "observed_failure")])
        for entry in layer["outside_ranking"] + layer["caution"]:
            self.assertNotIn("position", entry)
        self.assertEqual((document["counts"]["placements"]["ranked"],
                          document["counts"]["placements"]["outside_ranking"],
                          document["counts"]["placements"]["caution"]), (2, 2, 1))

    def test_pending_lanes_layer_ranks_candidates_on_evidence_only_with_banner(self):  # 6
        self.tree.layer("pending", C("example/exec", disposition="selected", evidence_kind="native_execution"),
                        C("example/review", disposition="conditional"),
                        C("example/mixed", evidence_kind="mixed", evidence_refs=("blueprints/x/result.json",)),
                        catalog="us-equities", verdict_status="pending_lanes")
        document = self.build()
        layer = self.layer(document, "layer:us-equities/pending")
        self.assertEqual(layer["banner"]["note"], PENDING_NOTE)
        self.assertEqual(layer["banner"]["layer_state"], "pending_lanes")
        self.assertEqual({p["role"] for p in layer["placements"]}, {"candidate"})
        self.assertEqual({p["sort_key"][0] for p in layer["placements"]}, {2})
        self.assertEqual([(p["entity"], p["position"], p["shared"]) for p in layer["placements"]],
                         [("repo:example/exec", 1, True), ("repo:example/mixed", 1, True),
                          ("repo:example/review", 3, False)])
        no_verdict = self.items(document, "role/selected-card-no-verdict")
        self.assertEqual([item["refs"] for item in no_verdict], [["layer:us-equities/pending", "repo:example/exec"]])
        self.assertEqual(self.items(document, "role/selected-card-not-winner"), [])


class KeyOrderTests(IndexCase):
    def test_recorded_winner_precedes_stronger_evidence_alternative(self):  # 7
        self.tree.layer("l1", W("example/win", evidence_class="source_review", declared="not_established",
                                derived="not_established"),
                        A("example/strong", evidence_class="native_proven", e2e_state="host_verified"))
        document = self.build()
        winner = self.placement(document, "layer:foundation/l1", "repo:example/win")
        strong = self.placement(document, "layer:foundation/l1", "repo:example/strong")
        self.assertEqual((winner["position"], strong["position"]), (1, 2))
        self.assertLess(winner["sort_key"], strong["sort_key"])
        below = self.items(document, "evidence/winner-tier-below-alternative")
        self.assertEqual(len(below), 1)
        self.assertIn("evidence/winner-tier-below-alternative", winner["flags"])

    def test_evidence_tier_mapping(self):  # 8
        for field, recorded, tier in (("evidence_class", "native_proven", "A"),
                                      ("evidence_class", "measured_comparison", "A"),
                                      ("evidence_class", "local_integration", "B"),
                                      ("evidence_class", "synthetic", "B"),
                                      ("evidence_class", "source_review", "C"),
                                      ("evidence_kind", "native_execution", "A"),
                                      ("evidence_kind", "measured_comparison", "A"),
                                      ("evidence_kind", "source_review", "C"),
                                      ("evidence_kind", "requirement_fit", "U")):
            with self.subTest(field=field, recorded=recorded):
                self.assertEqual(ci.evidence_tier(field, recorded), tier)
        self.assertEqual(ci.evidence_tier("evidence_kind", "mixed", True), "A")
        self.assertEqual(ci.evidence_tier("evidence_kind", "mixed", False), "C")
        self.assertTrue(ci.has_retained_local_result(["evidence/artifacts/run/result.json"]))
        self.assertTrue(ci.has_retained_local_result(["https://example.org/a", "logs/run.log"]))
        self.assertTrue(ci.has_retained_local_result(["notes/output.txt"]))
        self.assertFalse(ci.has_retained_local_result(["https://example.org/result.json"]))
        self.assertFalse(ci.has_retained_local_result(["docs/review.md"]))
        with self.assertRaises(ci.InvalidIndex):
            ci.evidence_tier("evidence_kind", "vibes")
        self.tree.layer("l1", W("example/win"), A("example/alt"),
                        C("example/fit", evidence_kind="requirement_fit"),
                        C("example/mixed-kept", evidence_kind="mixed", evidence_refs=("evidence/r/result.json",)),
                        C("example/mixed-remote", evidence_kind="mixed",
                          evidence_refs=("https://example.org/result.json",)))
        document = self.build()
        fit = self.placement(document, "layer:foundation/l1", "repo:example/fit")
        self.assertEqual(fit["evidence"]["tier"], "U")
        self.assertIn("evidence/unmapped-kind", fit["flags"])
        kept = self.placement(document, "layer:foundation/l1", "repo:example/mixed-kept")
        remote = self.placement(document, "layer:foundation/l1", "repo:example/mixed-remote")
        self.assertEqual((kept["evidence"]["tier"], remote["evidence"]["tier"]), ("A", "C"))
        self.assertIn("evidence/mixed-kind", kept["flags"])
        self.assertIn("evidence/mixed-kind", remote["flags"])
        self.assertLess(kept["position"], remote["position"])
        self.assertLess(remote["position"], fit["position"])

    def test_verification_reads_derived_not_declared_status(self):  # 9
        self.tree.layer("l1", W("example/claims", declared="accepted", derived="conditional"),
                        W("example/plain", declared="conditional", derived="conditional"), A("example/alt"))
        self.tree.layer("l2", W("example/hosted", declared="conditional", derived="accepted", host_verified=True),
                        W("example/routed", declared="conditional", derived="accepted"), A("example/other"))
        document = self.build()
        claims = self.placement(document, "layer:foundation/l1", "repo:example/claims")
        plain = self.placement(document, "layer:foundation/l1", "repo:example/plain")
        self.assertEqual((claims["verification"]["state"], claims["verification"]["level"]), ("conditional", 2))
        self.assertEqual(claims["verification"]["declared"], "accepted")
        self.assertEqual((claims["position"], plain["position"]), (1, 1))
        declared = self.items(document, "status/declared-above-derived")
        self.assertEqual([item["refs"] for item in declared], [["layer:foundation/l1", "repo:example/claims"]])
        hosted = self.placement(document, "layer:foundation/l2", "repo:example/hosted")
        routed = self.placement(document, "layer:foundation/l2", "repo:example/routed")
        self.assertEqual((hosted["verification"]["level"], routed["verification"]["level"]), (0, 1))
        self.assertEqual((hosted["position"], routed["position"]), (1, 2))

    def test_receipts_recorded_does_not_raise_an_alternative(self):  # 10
        self.tree.layer("l1", W("example/win"),
                        A("example/recorded", evidence_class="native_proven", e2e_state="receipts_recorded"),
                        A("example/none", evidence_class="native_proven", e2e_state="not_run"),
                        A("example/verified", evidence_class="native_proven", e2e_state="host_verified"))
        document = self.build()
        layer_ref = "layer:foundation/l1"
        recorded = self.placement(document, layer_ref, "repo:example/recorded")
        none = self.placement(document, layer_ref, "repo:example/none")
        verified = self.placement(document, layer_ref, "repo:example/verified")
        self.assertEqual((verified["position"], recorded["position"], none["position"]), (2, 3, 3))
        self.assertTrue(recorded["shared"] and none["shared"])
        self.assertEqual(recorded["sort_key"], none["sort_key"])
        self.assertIn("verification/joined-by-repository", recorded["flags"])
        self.assertNotIn("verification/joined-by-repository", none["flags"])

    def test_class_precedes_verification_and_inversion_is_flagged(self):  # 11
        self.tree.layer("l1", W("example/win"),
                        A("example/class-a", evidence_class="native_proven", e2e_state="not_run"),
                        A("example/verified-c", evidence_class="source_review", e2e_state="host_verified"))
        document = self.build()
        class_a = self.placement(document, "layer:foundation/l1", "repo:example/class-a")
        verified_c = self.placement(document, "layer:foundation/l1", "repo:example/verified-c")
        self.assertEqual((class_a["position"], verified_c["position"]), (2, 3))
        inversions = self.items(document, "evidence/class-verification-inversion")
        self.assertEqual([sorted(item["refs"]) for item in inversions],
                         [["layer:foundation/l1", "repo:example/class-a", "repo:example/verified-c"]])
        self.assertIn("evidence/class-verification-inversion", class_a["flags"])
        self.assertIn("evidence/class-verification-inversion", verified_c["flags"])
        metrics = document["counts"]["overturn_metrics"]
        self.assertEqual(metrics["class_vs_verification_flipped_pairs"], 1)
        self.assertEqual(metrics["class_vs_verification_flipped_winner_pairs"], 0)

    def test_positions_are_competition_ranks(self):  # 12
        self.assertEqual(ci.positions([[0, 0, 0, 0], [0, 0, 0, 0], [1, 0, 0, 0]]),
                         [(1, True), (1, True), (3, False)])
        self.assertEqual(ci.positions([[2, 1, 0, 0], [0, 0, 0, 0], [2, 1, 0, 0], [1, 0, 1, 0]]),
                         [(3, True), (1, False), (3, True), (2, False)])
        self.tree.layer("l1", W("example/win"), A("example/zeta"), A("example/beta"), C("example/card"))
        document = self.build()
        layer = self.layer(document, "layer:foundation/l1")
        self.assertEqual([(p["entity"], p["position"], p["shared"]) for p in layer["placements"]],
                         [("repo:example/win", 1, False), ("repo:example/beta", 2, True),
                          ("repo:example/zeta", 2, True), ("repo:example/card", 4, False)])

    def test_popularity_and_recency_never_reorder(self):  # 13
        # Three tied pairs (two winners, two alternatives, two card-only candidates). Every never-sort field gets a
        # distinct value in each pair, the "better" one on the entity that sorts later, so a tiebreak on any one of
        # them, in either direction, unshares the pair (and a better-first tiebreak also swaps its display order).
        # Repair round, review item 6: the values were identical across records before, which no tiebreak can split.
        layer_ref = "layer:foundation/l1"
        self.tree.layer("l1", W("example/current", declared="conditional", derived="conditional", pin_current="true"),
                        W("example/behind", declared="conditional", derived="conditional", pin_current="false"),
                        A("example/alt-one"), A("example/alt-two"), C("example/card-one"), C("example/card-two"))
        document = self.build()
        before = self.ranks(document)
        order = [p["entity"] for p in self.layer(document, layer_ref)["placements"]]
        pairs = (("example/behind", "example/current"), ("example/alt-one", "example/alt-two"),
                 ("example/card-one", "example/card-two"))
        self.assertEqual(order, ["repo:" + name for pair in pairs for name in pair])
        for pair, position in zip(pairs, (1, 3, 5)):
            for name in pair:
                self.assertEqual(before[(layer_ref, "repo:" + name)][:2], (position, True))
        worse = {"stars": 10, "review_status": "unreviewed", "votes": 1, "confidence": "low",
                 "pin_behind_upstream": True, "priority": 2, "archived": True, "latest": "2020-01-01T00:00:00Z"}
        better = {"stars": 10 ** 6, "review_status": "reviewed", "votes": 99, "confidence": "high",
                  "pin_behind_upstream": False, "priority": 1, "archived": False, "latest": "2030-01-01T00:00:00Z"}
        self.assertEqual(set(worse), set(better))
        self.assertTrue(all(worse[field] != better[field] for field in worse))
        planted = {_github(earlier): worse for earlier, _later in pairs}
        planted.update({_github(later): better for _earlier, later in pairs})

        def plant(record):
            record.update(planted[record["repository"]])

        def matrix_values(matrix):
            for row in matrix["rows"]:
                for component in row["convergence"]["components"]:
                    component["pin_current"] = {"true": "false", "false": "true"}[component["pin_current"]]
                for winner in row["winners"]:
                    plant(winner)
                    winner["pin"] = "9.9.9-" + winner["component_id"]
                    winner["platforms"][LINUX]["host_receipts"]["latest"] = planted[winner["repository"]]["latest"]
                for alternative in row["alternatives"]:
                    plant(alternative)

        def ledger_values(ledger):
            for layer in ledger["layers"]:
                for record in layer["winners"] + layer["alternatives"] + layer["candidates"]:
                    plant(record)

        def stars(coverage):
            for entry in coverage["stars"]:
                entry["stars"] = planted.get(_github(entry["repository"]), worse)["stars"]

        self.edit(cm.OUTPUT_JSON, matrix_values)
        self.edit(FOUNDATION_LEDGER, ledger_values)
        self.edit("catalogs/us-equities/coverage.json", stars)
        after_document = self.rebuild()
        self.assertEqual(self.ranks(after_document), before)
        self.assertEqual([p["entity"] for p in self.layer(after_document, layer_ref)["placements"]], order)
        self.assertEqual(self.placement(after_document, layer_ref, "repo:example/behind")
                         ["freshness"]["pin_current"], "true")


class MeasurementTests(IndexCase):
    LAYER, METRIC = "layer:foundation/l1", "task success on the frozen fixture"

    def measurement(self, entity, *, interval=None, outcome=None, verified=True, fixtures=("f" * 64,), major=1,
                    value=1.0):
        return {"layer": self.LAYER, "entity": entity, "metric": self.METRIC, "benchmark": "fixture-bench",
                "benchmark_major_version": major, "fixture_sha256": list(fixtures), "host_profile": "linux-wsl2",
                "pins": {"harness": "1.0.0"}, "direction": "higher_is_better", "verified": verified,
                "value": value, "interval": interval, "outcome": outcome}

    def split(self, *measurements):
        return {entity: (result["rank"], result["group"] is not None)
                for entity, result in ci.measured_split(["repo:x/a", "repo:x/b"], list(measurements),
                                                        layer=self.LAYER, metric=self.METRIC).items()}

    def test_measurement_splits_only_a_whole_tie_class_in_one_verified_group(self):  # 14
        a, b = "repo:x/a", "repo:x/b"
        cases = {
            "disjoint": ([self.measurement(a, interval=[10, 12]), self.measurement(b, interval=[1, 3])],
                         {a: (0, True), b: (1, True)}),
            "overlapping": ([self.measurement(a, interval=[5, 10]), self.measurement(b, interval=[8, 12])],
                            {a: (0, True), b: (0, True)}),
            "exact_pass_fail": ([self.measurement(a, outcome="fail"), self.measurement(b, outcome="pass")],
                                {a: (1, True), b: (0, True)}),
            "partial": ([self.measurement(a, interval=[10, 12])], {a: (0, False), b: (0, False)}),
            "different_sha": ([self.measurement(a, interval=[10, 12]),
                               self.measurement(b, interval=[1, 3], fixtures=("e" * 64,))],
                              {a: (0, False), b: (0, False)}),
            "different_major_version": ([self.measurement(a, interval=[10, 12]),
                                         self.measurement(b, interval=[1, 3], major=2)],
                                        {a: (0, False), b: (0, False)}),
            "unverified": ([self.measurement(a, interval=[10, 12]),
                            self.measurement(b, interval=[1, 3], verified=False)],
                           {a: (0, False), b: (0, False)}),
        }
        for name, (measurements, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.split(*measurements), expected)

        # End to end: two tied alternatives split only when both hold a verified result in one group.
        self.tree.files["catalogs/foundation/bench-fixture.json"] = {"results": [{"value": 0.9}, {"value": 0.2}]}
        self.tree.layer("l1", W("example/win"), A("example/fast"), A("example/slow"), metric=self.METRIC)
        results = [dict(self.measurement("repo:example/fast", interval=[0.85, 0.95], value=0.9),
                        source={"path": "catalogs/foundation/bench-fixture.json", "pointer": "/results/0/value"}),
                   dict(self.measurement("repo:example/slow", interval=[0.1, 0.3], value=0.2),
                        source={"path": "catalogs/foundation/bench-fixture.json", "pointer": "/results/1/value"})]
        with mock.patch.object(ci, "load_measurements", return_value=copy.deepcopy(results)):
            document = self.build()
        fast = self.placement(document, self.LAYER, "repo:example/fast")
        slow = self.placement(document, self.LAYER, "repo:example/slow")
        self.assertEqual((fast["position"], slow["position"]), (2, 3))
        self.assertEqual((fast["sort_key"][3], slow["sort_key"][3]), (0, 1))
        self.assertIsNotNone(fast["measured"]["group"])
        with mock.patch.object(ci, "load_measurements", return_value=copy.deepcopy(results[:1])):
            document = self.rebuild()
        self.assertEqual([self.placement(document, self.LAYER, entity)["position"]
                          for entity in ("repo:example/fast", "repo:example/slow")], [2, 2])
        tampered = copy.deepcopy(results)
        tampered[1]["value"] = 0.5  # no longer the number at its pointer
        with mock.patch.object(ci, "load_measurements", return_value=tampered), \
                self.assertRaisesRegex(ci.InvalidIndex, "F8"):
            self.rebuild()

    def test_order_is_a_total_preorder(self):  # 15
        rng = random.Random(20260929)
        states = {"winner": ["host_verified", "accepted", "conditional", "not_established", "untested"],
                  "alternative": ["host_verified", "receipts_recorded", "not_run"], "candidate": ["not_applicable"]}
        values = {"evidence_class": ["native_proven", "measured_comparison", "local_integration", "synthetic",
                                     "source_review"],
                  "evidence_kind": ["native_execution", "measured_comparison", "source_review", "requirement_fit",
                                    "mixed"]}
        for trial in range(300):
            placements = []
            for number in range(rng.randint(2, 9)):
                role = rng.choice(["winner", "alternative", "candidate"])
                field = "evidence_kind" if role == "candidate" else "evidence_class"
                placements.append({"entity": f"repo:fixture/p{number}", "role": role,
                                   "evidence": {"field": field, "recorded": rng.choice(values[field]),
                                                "retained_local_result": rng.random() < 0.5},
                                   "verification": {"state": rng.choice(states[role])}})
            measurements = []
            for placement in placements:
                if rng.random() < 0.7:
                    low = rng.uniform(0, 10)
                    measurements.append(dict(self.measurement(placement["entity"],
                                                              interval=[low, low + rng.uniform(0, 3)],
                                                              verified=rng.random() < 0.85,
                                                              major=rng.choice([1, 1, 2]))))
            ranked = ci.rank_layer(copy.deepcopy(placements), measurements, layer=self.LAYER, metric=self.METRIC)
            with self.subTest(trial=trial):
                for placement in ranked:
                    self.assertIn("position", placement)
                    self.assertIn("sort_key", placement)
                for p in ranked:
                    for q in ranked:
                        self.assertEqual(p["position"] < q["position"], p["sort_key"] < q["sort_key"])
                        self.assertEqual(p["position"] == q["position"], p["sort_key"] == q["sort_key"])
                        for r in ranked:
                            if p["sort_key"] <= q["sort_key"] <= r["sort_key"]:
                                self.assertLessEqual(p["position"], r["position"])
                classes: dict[tuple, list[dict]] = {}
                for placement in ranked:
                    classes.setdefault(tuple(placement["sort_key"][:3]), []).append(placement)
                verified = {(m["entity"], ci.comparability_key(m)) for m in measurements if m["verified"]}
                for members in classes.values():
                    if any(member["sort_key"][3] for member in members):
                        groups = {member["measured"]["group"] for member in members}
                        self.assertEqual(len(groups), 1)
                        group = groups.pop()
                        self.assertIsNotNone(group)
                        for member in members:
                            self.assertIn((member["entity"], group), verified)


class ConflictAndShapeTests(IndexCase):
    def test_conflicts_become_status_items_not_role_changes(self):  # 16
        self.tree.layer("l1", W("example/win"), A("example/alt"),
                        C("example/win", disposition="unqualified"), C("example/alt", disposition="selected"),
                        C("example/card", disposition="selected"))
        document = self.build()
        layer_ref = "layer:foundation/l1"
        self.assertEqual([(entity, self.placement(document, layer_ref, "repo:example/" + entity)["role"])
                          for entity in ("win", "alt", "card")],
                         [("win", "winner"), ("alt", "alternative"), ("card", "candidate")])
        not_selected = self.items(document, "role/winner-card-not-selected")
        self.assertEqual([item["refs"] for item in not_selected], [[layer_ref, "repo:example/win"]])
        self.assertEqual(not_selected[0]["level"], "warning")
        not_winner = self.items(document, "role/selected-card-not-winner")
        self.assertEqual(sorted(item["refs"][1] for item in not_winner), ["repo:example/alt", "repo:example/card"])
        self.assertIn("role/selected-card-not-winner",
                      self.placement(document, layer_ref, "repo:example/alt")["flags"])
        win = self.placement(document, layer_ref, "repo:example/win")
        self.assertIn(("candidate", "unqualified"), [(r["role"], r["disposition"]) for r in win["role_records"]])

    def test_duplicate_role_records_are_flagged_never_merged_silently(self):  # 38 (repair round, review item 5)
        # Two winner component ids of one repository in one layer (scripts/landscape.py forbids only a duplicate
        # component_id), and two alternatives of one repository (no uniqueness check there): the first record by
        # path and pointer governs the placement, and each duplicate is a status item, never dropped.
        self.tree.layer("l1", W("example/tool", "tool"), W("example/tool", "tool-sdk", declared="conditional",
                                                         derived="conditional"),
                        A("example/alt", disposition="conditional"), A("example/alt", disposition="overlap"),
                        C("example/card"))
        document = self.build()
        layer_ref = "layer:foundation/l1"
        duplicates = self.items(document, "role/duplicate-role-record")
        self.assertEqual(
            [item["refs"] for item in duplicates],
            [[layer_ref, "repo:example/alt", FOUNDATION_LEDGER + "#/layers/0/alternatives/0",
              FOUNDATION_LEDGER + "#/layers/0/alternatives/1"],
             [layer_ref, "repo:example/tool", FOUNDATION_LEDGER + "#/layers/0/winners/0",
              FOUNDATION_LEDGER + "#/layers/0/winners/1"]])
        self.assertEqual({item["level"] for item in duplicates}, {"warning"})
        tool = self.placement(document, layer_ref, "repo:example/tool")
        self.assertEqual((tool["role"], tool["component_id"]), ("winner", "tool"))
        self.assertEqual(sorted((r["role"], r["pointer"]) for r in tool["role_records"]),
                         [("winner", "/layers/0/winners/0"), ("winner", "/layers/0/winners/1")])
        self.assertIn("role/duplicate-role-record", tool["flags"])
        self.assertIn("tool-sdk", duplicates[1]["message"])
        alt = self.placement(document, layer_ref, "repo:example/alt")
        self.assertEqual(sorted((r["pointer"], r["disposition"]) for r in alt["role_records"]),
                         [("/layers/0/alternatives/0", "conditional"), ("/layers/0/alternatives/1", "overlap")])
        self.assertIn("role/duplicate-role-record", alt["flags"])
        self.assertNotIn("role/duplicate-role-record", self.placement(document, layer_ref, "repo:example/card")["flags"])
        self.assertEqual(self.entity(document, "repo:example/tool")["component_ids"], ["tool", "tool-sdk"])
        self.assertEqual(document["counts"]["status_items"]["role/duplicate-role-record"], 2)

    def test_no_blended_or_weighted_field_is_emitted(self):  # 17
        self.tree.layer("l1", W("example/win"), A("example/alt"), C("example/card"))
        document = self.build()
        self.assertTrue(document.get("layers"))
        banned = {"score", "scores", "weight", "weights", "weighted", "total", "totals", "composite"}
        found = []

        def walk(node, pointer):
            if isinstance(node, dict):
                for key, value in node.items():
                    if set(key.lower().split("_")) & banned and pointer + "/" + key != "/rule/blended_score":
                        found.append(pointer + "/" + key)
                    walk(value, pointer + "/" + key)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{pointer}/{index}")

        walk(document, "")
        self.assertEqual(found, [])
        self.assertIs(document["rule"]["blended_score"], False)
        planted = copy.deepcopy(document)
        planted["layers"][0]["placements"][0]["score"] = 1
        with self.assertRaisesRegex(ci.InvalidIndex, "F6"):
            ci.check_document(planted)
        blended = copy.deepcopy(document)
        blended["rule"]["blended_score"] = True
        with self.assertRaisesRegex(ci.InvalidIndex, "F6"):
            ci.check_document(blended)

    def test_no_winners_key_and_landscape_winners_unchanged(self):  # 18
        self.tree.layer("l1", W("example/win"), A("example/alt"), C("example/card"))
        self.tree.write()
        before = hr.landscape_winners(self.root)
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.root / ci.OUTPUT_JSON).is_file(), "--write wrote no index")
        written = json.loads((self.root / ci.OUTPUT_JSON).read_text(encoding="utf-8"))
        self.assertEqual(len(written["layers"]), 1)
        self.assertEqual(hr.landscape_winners(self.root), before)
        self.assertEqual(hr.landscape_component_ids(self.root), {"win"})
        keys = []

        def walk(node):
            if isinstance(node, dict):
                keys.extend(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(written)
        self.assertNotIn("winners", keys)
        planted = copy.deepcopy(written)
        planted["layers"][0]["winners"] = []
        with self.assertRaisesRegex(ci.InvalidIndex, "F14"):
            ci.check_document(planted)


class ConservationTests(IndexCase):
    def test_conservation_counts(self):  # 19
        self.tree.stack = [{"id": "win", "repository": "example/win"}]
        self.tree.receipts = [
            {"id": "attached", "kind": "native_cli_e2e", "component_ids": ["win"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/a.json"},
            {"id": "by-winner-id", "kind": "artifact_measurement", "component_ids": ["other-win"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/b.json"},
            {"id": "ghost", "kind": "native_cli_e2e", "component_ids": ["no-such-component"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/c.json"}]
        self.tree.convergence_records = ["blueprints/one/experiment.json", "blueprints/two/experiment.json"]
        self.tree.extra_repositories = {"example/unplaced"}
        self.tree.layer("l1", W("example/win"), A("example/alt"), A("example/oos", disposition="out_of_scope"),
                        C("example/win", disposition="selected"), C("example/card"))
        self.tree.layer("u1", W("example/other", "other-win"), A("example/alt"), catalog="us-equities")
        document = self.build()
        for layer in document["layers"]:
            with self.subTest(layer=layer["ref"]):
                spec = next(item for item in self.tree.layers
                            if f"layer:{item['catalog']}/{item['layer_id']}" == layer["ref"])
                entities = {cd.canonical(cd.identity(record["repository"]), {}) for record in spec["records"]}
                placed = len(layer["placements"]) + len(layer["outside_ranking"]) + len(layer["caution"])
                self.assertEqual(placed, len(entities))
                self.assertEqual(layer["counts"]["placements"], len(entities))
                self.assertEqual(layer["counts"]["records"], len(spec["records"]))
        index = json.loads((self.root / cd.INDEX).read_text(encoding="utf-8"))
        self.assertEqual(len(document["entities"]), len(index["records"]))
        attached = {receipt for entity in document["entities"] for receipt in entity["receipts"]["ids"]}
        unattached = [item["id"] for item in document["evidence"]["receipts_unattached"]]
        self.assertEqual(sorted(attached), ["attached", "by-winner-id"])
        self.assertEqual(unattached, ["ghost"])
        self.assertEqual(len(attached) + len(unattached), len(self.tree.receipts))
        self.assertEqual([item["path"] for item in document["evidence"]["experiments"]],
                         sorted(self.tree.convergence_records))
        self.assertTrue(all(item["joined"] is False for item in document["evidence"]["experiments"]))
        listed = sorted({path.relative_to(self.root).as_posix() for pattern in ("catalogs/**/*.json",)
                         for path in self.root.glob(pattern)}
                        | {path.relative_to(self.root).as_posix() for path in self.root.glob("manifests/*.json")})
        self.assertEqual([item["path"] for item in document["coverage"]["catalog_files"]], listed)
        conservation = document["counts"]["conservation"]
        self.assertEqual(conservation["receipts"], {"attached": 2, "listed": 3, "unattached": 1})
        self.assertEqual(conservation["experiments"], {"convergence_records": 2, "listed": 2})
        self.assertEqual(conservation["entities"], conservation["decision_index_records"])

    def test_role_record_pointers_resolve_and_read_set_equals_inputs(self):  # 20
        self.tree.aliases = {"old-owner/tool": "new-owner/tool"}
        self.tree.layer("l1", W("new-owner/tool", "tool"), A("example/alt"),
                        C("old-owner/tool", repository="https://github.com/old-owner/tool", disposition="selected"),
                        C("example/card"), C("example/oos", disposition="out_of_scope"))
        self.tree.layer("pending", C("example/pending"), catalog="us-equities", verdict_status="pending_lanes")
        self.tree.write()
        loaded = []
        original = cd.load

        def recording(root, relative):
            loaded.append(relative)
            return original(root, relative)

        with mock.patch.object(cd, "load", recording):
            document = self.rebuild()
        aliases = cd.aliases_for(self.root)
        checked = 0
        for layer in document["layers"]:
            for entry in layer["placements"] + layer["outside_ranking"] + layer["caution"]:
                for record in entry["role_records"]:
                    source = json.loads((self.root / record["path"]).read_text(encoding="utf-8"))
                    target = cd.pointer(source, record["pointer"])
                    self.assertEqual("repo:" + cd.canonical(cd.identity(target["repository"]), aliases),
                                     entry["entity"], record)
                    self.assertEqual(target.get("disposition"), record["disposition"])
                    checked += 1
                matrix_record = entry.get("matrix_record")
                if matrix_record:
                    source = json.loads((self.root / matrix_record["path"]).read_text(encoding="utf-8"))
                    target = cd.pointer(source, matrix_record["pointer"])
                    self.assertEqual("repo:" + cd.canonical(cd.identity(target["repository"]), aliases),
                                     entry["entity"])
        self.assertEqual(checked, 6)
        declared = {item["path"] for item in document["inputs"]}
        listing = {item["path"] for item in document["coverage"]["catalog_files"]}
        self.assertIn(ci.LISTING_INPUT, declared)
        self.assertEqual(set(loaded), (declared - {ci.LISTING_INPUT}) | listing)
        self.assertTrue(all(path.startswith(("catalogs/", "manifests/")) for path in loaded), loaded)

    def test_only_receipts_and_convergence_records_are_read_from_evidence(self):  # 21
        self.tree.stack = [{"id": "win", "repository": "example/win"}]
        self.tree.receipts = [{"id": "first", "kind": "native_cli_e2e", "component_ids": ["win"],
                               "claim": "fixture", "limitations": [], "path": "evidence/receipts/a.json"}]
        self.tree.layer("l1", W("example/win"), A("example/alt"))
        baseline = ci.serialize(self.build())

        def add_files(evidence):
            evidence["files"] = [{"path": "evidence/receipts/a.json", "sha256": "0" * 64, "bytes": 1},
                                 {"path": ci.OUTPUT_JSON, "sha256": "1" * 64, "bytes": 2}]

        self.edit("manifests/evidence.json", add_files)
        self.assertEqual(ci.serialize(self.rebuild()), baseline)

        def add_receipt(evidence):
            evidence["receipts"].append({"id": "second", "kind": "native_cli_e2e", "component_ids": ["win"],
                                         "claim": "fixture", "limitations": [], "path": "evidence/receipts/b.json"})

        self.edit("manifests/evidence.json", add_receipt)
        self.assertNotEqual(ci.serialize(self.rebuild()), baseline)
        self.edit("manifests/evidence.json", lambda evidence: evidence["receipts"].pop())
        self.assertEqual(ci.serialize(self.rebuild()), baseline)
        self.edit("manifests/evidence.json",
                  lambda evidence: evidence["convergence_records"].append("blueprints/x/experiment.json"))
        self.assertNotEqual(ci.serialize(self.rebuild()), baseline)

    def test_catalog_file_add_or_remove_changes_coverage_but_an_edit_does_not(self):  # 22
        self.tree.files["catalogs/foundation/notes.json"] = {"schema_version": 1, "notes": ["first"]}
        self.tree.layer("l1", W("example/win"), A("example/alt"))
        baseline = ci.serialize(self.build())
        added = self.root / "catalogs/foundation/added.json"
        _write_json(added, {"schema_version": 1, "entries": []})
        document = self.rebuild()
        self.assertIn({"path": "catalogs/foundation/added.json", "reached_as": "not_reached"},
                      document["coverage"]["catalog_files"])
        self.assertNotEqual(ci.serialize(document), baseline)
        added.unlink()
        self.assertEqual(ci.serialize(self.rebuild()), baseline)
        self.edit("catalogs/foundation/notes.json", lambda notes: notes["notes"].append("second, edited"))
        self.assertEqual(ci.serialize(self.rebuild()), baseline)


class CheckAndWriteTests(IndexCase):
    def test_check_fails_on_stale_output_and_names_the_sequence(self):  # 23
        self.tree.stack = [{"id": "win", "repository": "example/win"}]
        self.tree.layer("l1", W("example/win"), A("example/alt"))
        self.tree.write()
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1, err)
        self.assertIn("stale or missing: " + ci.OUTPUT_JSON, err)
        self.assertIn(SEQUENCE, err)
        self.assertIn("receipts[] and convergence_records[]", err)
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        code, out, err = self.run_main("--check")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "checked")
        self.edit("manifests/evidence.json", lambda evidence: evidence["receipts"].append(
            {"id": "late", "kind": "native_cli_e2e", "component_ids": ["win"], "claim": "fixture",
             "limitations": [], "path": "evidence/receipts/late.json"}))
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1, err)
        self.assertIn(SEQUENCE, err)
        self.edit("manifests/evidence.json", lambda evidence: evidence["receipts"].pop())
        self.assertEqual(self.run_main("--check")[0], 0)
        (self.root / ci.OUTPUT_JSON).write_text("{}\n", encoding="utf-8")
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1, err)
        self.assertIn("stale or missing: " + ci.OUTPUT_JSON, err)

    def test_write_register_check_fixed_point_and_idempotent_second_write(self):  # 24
        self.tree.layer("l1", W("example/win"), A("example/alt"))
        self.tree.write()
        code, out, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "written")
        first = (self.root / ci.OUTPUT_JSON).read_bytes()
        evidence_after_first = (self.root / "manifests/evidence.json").read_bytes()
        registered = {item["path"]: item for item in json.loads(evidence_after_first)["files"]}
        self.assertEqual(registered[ci.OUTPUT_JSON],
                         {"path": ci.OUTPUT_JSON, "sha256": hashlib.sha256(first).hexdigest(), "bytes": len(first)})
        self.assertNotIn(ci.OUTPUT_JSON, [item["path"] for item in json.loads(first)["coverage"]["catalog_files"]])
        self.assertEqual(self.run_main("--check")[0], 0)
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        self.assertEqual((self.root / ci.OUTPUT_JSON).read_bytes(), first)
        self.assertEqual((self.root / "manifests/evidence.json").read_bytes(), evidence_after_first)
        self.assertEqual(self.run_main("--check")[0], 0)

    RUNNER = ("import sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[3])\n"
              "from scripts import catalog_index as ci\nci.EXPECTED_LAYER_COUNT = int(sys.argv[2])\n"
              "sys.stdout.write(ci.serialize(ci.build_document(Path(sys.argv[1]))))\n")

    def test_two_process_hash_seed_determinism_and_no_clock(self):  # 25
        self.tree.stack = [{"id": f"tool-{number:02d}", "repository": "example/tool"} for number in range(12)]
        self.tree.receipts = [{"id": f"receipt-{number:02d}", "kind": "native_cli_e2e",
                               "component_ids": [f"tool-{number:02d}"], "claim": "fixture", "limitations": [],
                               "path": f"evidence/receipts/{number}.json"} for number in range(12)]
        self.tree.files.update({f"catalogs/foundation/extra-{number:02d}.json": {"n": number}
                                for number in range(12)})
        self.tree.layer("l1", W("example/tool", "tool-00"), *[A(f"example/alt-{number:02d}") for number in range(8)],
                        *[C(f"example/card-{number:02d}") for number in range(8)])
        self.tree.layer("u1", W("example/other"), A("example/tool"), catalog="us-equities")
        self.tree.write()
        outputs = []
        for seed in ("1", "2"):
            result = subprocess.run(
                [sys.executable, "-c", self.RUNNER, str(self.root), str(len(self.tree.layers)), str(REPO_ROOT)],
                env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, timeout=120,
                check=False)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            outputs.append(result.stdout)
        self.assertEqual(len(json.loads(outputs[0])["layers"]), 2)
        self.assertEqual(outputs[0], outputs[1])
        source = (REPO_ROOT / "scripts" / "catalog_index.py").read_text(encoding="utf-8")
        clock = {"now", "today", "utcnow", "time", "time_ns", "monotonic", "perf_counter", "localtime", "gmtime"}
        tree = ast.parse(source)
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names} | {node.module.split(".")[0] for node in ast.walk(tree)
                                                  if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imported & {"time", "datetime", "random", "uuid", "subprocess"}, imported)
        self.assertEqual([node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr in clock],
                         [])
        self.assertEqual(ci.RULE["frozen_at"], ci.FROZEN_AT)

    def test_output_over_the_secret_scan_cap_is_refused(self):  # 26
        # The layer title is copied into the index once, so it inflates the output directly.
        self.tree.layer("l1", W("example/win"), A("example/alt"), title="Layer " + "x" * 2_100_000)
        self.tree.write()
        evidence = (self.root / "manifests/evidence.json").read_bytes()
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 1, err)
        self.assertIn("F10", err)
        self.assertFalse((self.root / ci.OUTPUT_JSON).exists())
        self.assertEqual((self.root / "manifests/evidence.json").read_bytes(), evidence)
        self.tree.layers[0]["title"] = "Layer " + "x" * 1_600_000
        self.tree.write()
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        self.assertIn("warning", err)
        self.assertLess((self.root / ci.OUTPUT_JSON).stat().st_size, ci.SIZE_LIMIT_BYTES)

    def test_private_content_aborts_before_writing(self):  # 27
        planted = "/" + "home" + "/planted-account/notes"  # assembled at run time: this file holds no such path
        self.tree.layer("l1", W("example/win"), A("example/alt"), title="Layer kept in " + planted)
        self.tree.write()
        evidence = (self.root / "manifests/evidence.json").read_bytes()
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 1, err)
        self.assertIn("F11", err)
        self.assertIn("personal home path", err)
        self.assertFalse((self.root / ci.OUTPUT_JSON).exists())
        self.assertEqual((self.root / "manifests/evidence.json").read_bytes(), evidence)

    def test_unknown_enum_value_fails_closed(self):  # 28
        def matrix_winner(field, value):
            def change(matrix):
                matrix["rows"][0]["winners"][0]["platforms"][LINUX][field] = value
            return cm.OUTPUT_JSON, change

        def matrix_row(change_row):
            def change(matrix):
                change_row(matrix["rows"][0])
            return cm.OUTPUT_JSON, change

        def card(field, value):
            def change(ledger):
                ledger["layers"][0]["candidates"][0][field] = value
            return FOUNDATION_LEDGER, change

        cases = {
            "winner evidence_class": matrix_row(lambda row: row["winners"][0].update(evidence_class="vibes")),
            "winner derived_status": matrix_winner("derived_status", "vibes"),
            "winner catalog_status": matrix_winner("catalog_status", "vibes"),
            "alternative e2e_state": matrix_row(lambda row: row["alternatives"][0].update(e2e_state="vibes")),
            "alternative disposition": matrix_row(lambda row: row["alternatives"][0].update(disposition="vibes")),
            "layer_state": matrix_row(lambda row: row["convergence"].update(layer_state="vibes")),
            "independent_review": matrix_row(lambda row: row.update(independent_review="vibes")),
            "pin_current": matrix_row(lambda row: row["convergence"]["components"][0].update(pin_current="maybe")),
            "card evidence_kind": card("evidence_kind", "vibes"),
            "card disposition": card("disposition", "vibes"),
        }
        self.tree.layer("l1", W("example/win"), A("example/alt"), C("example/card"))
        self.tree.write()
        for name, (relative, change) in cases.items():
            with self.subTest(case=name):
                original = (self.root / relative).read_text(encoding="utf-8")
                self.edit(relative, change)
                try:
                    with self.assertRaisesRegex(ci.InvalidIndex, "F13"):
                        self.rebuild()
                    code, _, err = self.run_main("--write")
                    self.assertEqual(code, 1, err)
                    self.assertFalse((self.root / ci.OUTPUT_JSON).exists())
                finally:
                    (self.root / relative).write_text(original, encoding="utf-8")

    def test_write_leaves_other_generator_outputs_unchanged(self):  # 29
        self.tree.layer("l1", W("example/alpha", "alpha"), A("example/beta"), C("example/gamma"))
        self.tree.layer("u1", W("example/delta", "delta"), A("example/epsilon"), catalog="us-equities")
        self.tree.write()
        root = self.root
        # The matrix, the grand list and the decision index here come from their own generators, so their
        # --check runs are meaningful.
        schema = "adoption/host-receipt.schema.json"
        (root / schema).write_text((REPO_ROOT / schema).read_text(encoding="utf-8"), encoding="utf-8")
        (root / "evidence" / "hosts").mkdir(parents=True, exist_ok=True)
        (root / "docs").mkdir(exist_ok=True)
        _write_json(root / grand_list.MANIFEST, {"schema_version": 1, "checked_at": "2026-09-23"})
        _write_json(root / "adoption/manifest.json", {"profiles": [], "recipe_map": {}})
        for relative in grand_list.PIN_FILES.values():
            _write_json(root / relative, {})
        _write_json(root / "adoption/hardware-profiles.json", {"hosts": []})
        quiet = contextlib.ExitStack()
        quiet.enter_context(contextlib.redirect_stdout(io.StringIO()))
        quiet.enter_context(contextlib.redirect_stderr(io.StringIO()))
        with quiet:
            self.assertEqual(cm.main(["--root", str(root), "--write"]), 0)
            with mock.patch.object(grand_list, "ROOT", root):
                self.assertEqual(grand_list.main(["--write"]), 0)
        outputs = (cm.OUTPUT_JSON, cm.OUTPUT_MD, grand_list.OUT_JSON, grand_list.OUT_MD, cd.INDEX)
        before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}
        code, _, err = self.run_main("--write")
        self.assertEqual(code, 0, err)
        self.assertTrue((root / ci.OUTPUT_JSON).is_file(), "--write wrote no index")
        self.assertEqual(len(json.loads((root / ci.OUTPUT_JSON).read_text(encoding="utf-8"))["layers"]), 2)
        self.assertEqual({path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}, before)
        quiet = contextlib.ExitStack()
        quiet.enter_context(contextlib.redirect_stdout(io.StringIO()))
        quiet.enter_context(contextlib.redirect_stderr(io.StringIO()))
        with quiet:
            self.assertEqual(cm.main(["--root", str(root), "--check"]), 0)
            with mock.patch.object(grand_list, "ROOT", root):
                self.assertEqual(grand_list.main(["--check"]), 0)
            self.assertEqual(cd.main(["--root", str(root), "--check"]), 0)
        self.assertEqual(self.run_main("--check")[0], 0)


class RepositoryIndexTests(unittest.TestCase):
    def test_the_committed_repository_index_is_current(self):  # 30
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = ci.main(["--root", str(REPO_ROOT), "--check"])
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertTrue((REPO_ROOT / ci.OUTPUT_JSON).is_file(), "no committed index")
        text = (REPO_ROOT / ci.OUTPUT_JSON).read_text(encoding="utf-8")
        document = json.loads(text)
        self.assertEqual(len(document["layers"]), 32)
        self.assertEqual(document["rule"], ci.RULE)
        self.assertEqual(document["universal_superiority"], "not_established")
        # The index names Sourcegraph repositories, so the secret scan would read a bare 40-hex commit id as a leak.
        self.assertIsNone(re.search(r"\b[0-9a-f]{40}\b", text))


if __name__ == "__main__":
    unittest.main()
