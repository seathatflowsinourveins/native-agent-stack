"""Synthetic-fixture tests for tools/sota-convergence/record_verdicts.py.

Builds a full landscape fixture root -- the same source files
scripts/landscape.py's build_landscape() needs (see tests/test_landscape.py) --
so every row record_verdicts.py writes is proven valid by the real row
validator, not a reimplementation of it. The packets and lane-return files it
consumes are built here directly (no network, no real catalogs, no
dependency on the sibling lane_packets.py unit) matching the packet/
lane-return shapes documented in the PR-5 lane contract.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.landscape import build_landscape

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


record_verdicts = load_module("record_verdicts", "record_verdicts.py")


def long_text(base: str, minimum: int) -> str:
    text = base
    while len(text) < minimum:
        text += " padded"
    return text


def repo(layer_id: str, suffix: str) -> str:
    return f"https://github.com/example/{layer_id}-{suffix}"


V1_CANDIDATES = [
    {"name": "Selected native tool", "repository": "https://github.com/example/selected",
     "disposition": "selected", "rationale": "Fits the requirement",
     "evidence_kind": "native_execution", "evidence_refs": ["receipt.json"]},
    {"name": "Historical alternative", "repository": "https://github.com/example/alternative",
     "disposition": "unqualified", "rationale": "Not tested on this host",
     "evidence_kind": "source_review", "evidence_refs": ["receipt.json"]},
]


def v2_row(catalog, layer_id, title, **overrides):
    row = {
        "catalog": catalog, "layer_id": layer_id, "title": title,
        "requirement": "Run the fixture requirement", "current_choice": "Selected native tool",
        "decision": "retain", "rationale": "Native execution evidence",
        "evidence_refs": ["receipt.json"], "limitations": ["One input"],
        "overturn_when": "A matched task improves quality",
        "candidates": [dict(candidate) for candidate in V1_CANDIDATES],
        "group": None,
        "verdict_status": "pending_lanes", "winners": [], "alternatives": [],
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "lanes": {"claude": {"run_id": "", "sealed_sha256": ""},
                  "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"},
        "open_gaps": [], "checked_at": "2026-09-21",
    }
    row.update(overrides)
    return row


def make_packet(catalog, layer_id, candidates):
    return {
        "schema_version": 1, "catalog": catalog, "layer_id": layer_id, "title": layer_id,
        "group": None if catalog == "foundation" else "data-domain",
        "checked_at": "2026-09-22", "requirement": "Requirement text",
        "limitations": ["One limitation"], "existing_overturn_when": "Existing text",
        "candidates": candidates, "sota_components_not_in_candidates": [],
        "enums": {"evidence_class": ["local_integration", "measured_comparison", "native_proven",
                                      "source_review", "synthetic"],
                  "disposition": ["conditional", "measured_tradeoff", "observed_failure", "out_of_scope",
                                  "overlap", "selected", "unqualified"]},
        "withheld": ["current_choice", "decision", "rationale", "candidates[].disposition",
                     "candidates[].rationale"],
        "rules": ["Judge from retained evidence."],
    }


def make_candidate(key, layer_id, suffix, *, adopted=True, component_id=None, pin="1.0", recipe_ref=None):
    return {
        "key": key, "name": f"{layer_id} {suffix}", "repository": repo(layer_id, suffix),
        "adopted": adopted, "evidence_kind": "native_execution", "evidence_refs": [],
        "component_id": component_id, "pin": pin, "upstream": {"latest": pin},
        "review_status": "confirmed_default", "pin_behind_upstream": False,
        "recipe_ref": recipe_ref, "decisions": [],
    }


def make_alternative(candidate, *, why_suffix="alt"):
    return {
        "key": candidate["key"], "name": candidate["name"], "repository": candidate["repository"],
        "disposition": "conditional",
        "why_not_default": long_text(f"Not selected for {candidate['name']} {why_suffix} on the evidence.", 30),
        "evidence_class": "source_review", "evidence_refs": [],
    }


def make_lane_return(lane, catalog, layer_id, packet_sha256, winner_keys, alternatives, **overrides):
    data = {
        "schema_version": 1, "lane": lane, "catalog": catalog, "layer_id": layer_id,
        "packet_sha256": packet_sha256,
        "model": {"name": "test-model", "effort": "high"},
        "winner_keys": winner_keys,
        "why_selected": long_text(f"{lane} selected this using native execution evidence in receipt.json "
                                  f"for {layer_id}.", 60),
        "winner_evidence_class": "native_proven",
        "winner_evidence_refs": ["receipt.json"],
        "alternatives": alternatives,
        "challenger_preferred": None,
        "overturn_when": f"See tests/test_record_verdicts.py for {layer_id}.",
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "open_gaps": [],
        "sources_read": [],
        "limits": [],
    }
    data.update(overrides)
    return data


class PacketWriter:
    """Writes packets/<catalog>__<layer_id>.json and packets/SHA256SUMS into a
    work_dir exactly the way lane_packets.py's own contract describes
    (deterministic json.dumps(sort_keys=True, indent=1) + newline; SHA256SUMS
    in sha256sum format), without depending on that sibling unit."""

    def __init__(self, work_dir: Path):
        self.packets_dir = work_dir / "packets"
        self.packets_dir.mkdir(parents=True, exist_ok=True)
        self.sums = []

    def write(self, catalog, layer_id, packet) -> str:
        filename = f"{catalog}__{layer_id}.json"
        text = json.dumps(packet, sort_keys=True, indent=1) + "\n"
        (self.packets_dir / filename).write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.sums.append(f"{digest}  {filename}")
        return digest

    def flush(self):
        (self.packets_dir / "SHA256SUMS").write_text("\n".join(self.sums) + "\n", encoding="utf-8")


def write_lane(work_dir: Path, lane: str, catalog: str, layer_id: str, data: dict):
    lane_dir = work_dir / lane
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / f"{catalog}__{layer_id}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


def counterbalanced(winner_lane, why="The retained receipt decides it.", evidence_refs=("receipt.json",),
                    picks=None):
    """An adjudication record with one judgment per presentation order. ``picks`` maps
    Claude's position (A or B) to the lane that judgment chose; by default both orders
    chose ``winner_lane``."""
    picks = picks or {"A": winner_lane, "B": winner_lane}
    judgments = []
    for claude_position, lane in picks.items():
        codex_position = "B" if claude_position == "A" else "A"
        judgments.append({"claude_position": claude_position,
                          "preferred_position": claude_position if lane == "claude" else codex_position,
                          "preferred_lane": lane, "refuting_votes": 0})
    return {"winner_lane": winner_lane, "why": why, "evidence_refs": list(evidence_refs), "judgments": judgments}


def write_adjudication(adjudications_dir: Path, catalog: str, layer_id: str, data: dict):
    adjudications_dir.mkdir(parents=True, exist_ok=True)
    (adjudications_dir / f"{catalog}__{layer_id}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


# Every foundation/us-equities layer_id exercised across the test methods
# below -- declared once so setUp can build a single landscape-validator-
# complete fixture root that covers all of them (each test method only
# writes packets/lane files for the layer(s) it actually exercises; every
# other declared layer simply stays "pending_lanes", which is already a
# valid v2 row).
FOUNDATION_LAYERS = [
    "same-winner-layer", "disagree-pending-layer", "disagree-adjudicated-layer",
    "codex-absent-layer", "rejected-codex-layer", "pin-fallback-layer", "pin-unpinned-layer",
    "challenger-layer", "protocol-layer", "codex-only-layer",
    "rejection-winnerkey-layer", "rejection-altmissing-layer", "rejection-whyequal-layer",
    "rejection-overturn-layer", "rejection-nonhttps-layer", "rejection-challenger-layer",
    "citation-layer", "review-adjudicated-layer", "review-badadj-layer", "review-sealed-layer",
    "review-packet-layer", "review-nosum-layer", "review-leak-layer", "review-sources-layer",
    "review-explorer-layer", "verify-noalt-layer", "verify-adjleak-layer", "verify-winalt-layer",
    "disagree-split-layer", "disagree-one-order-layer", "disagree-no-judgments-layer",
    "disagree-split-claimed-layer", "disagree-refuted-layer", "disagree-contradiction-layer",
    "disagree-missing-winner-layer", "disagree-bool-votes-layer", "disagree-judgments-object-layer",
]
US_EQUITIES_LAYERS = ["unindexed-alt-layer", "unindexed-pending-layer"]


class RecordVerdictsFixture(unittest.TestCase):
    def setUp(self):
        root_temp = tempfile.TemporaryDirectory()
        self.addCleanup(root_temp.cleanup)
        self.root = Path(root_temp.name).resolve()
        work_temp = tempfile.TemporaryDirectory()
        self.addCleanup(work_temp.cleanup)
        self.work_dir = Path(work_temp.name).resolve()
        self.packets = PacketWriter(self.work_dir)

        manifest = {
            "schema_version": 1, "checked_at": "2026-09-22", "source_base": "a" * 40,
            "scope": "Fixture selection", "status": "reviewed_baseline",
            "new_pc_scope": "New host acceptance required", "universal_superiority": "not_established",
            "rules": ["Execution is not superiority"],
            "catalogs": {"foundation": "catalogs/landscape/foundation.json",
                        "us-equities": "catalogs/landscape/us-equities.json"},
            "sources": {"foundation_manifest": "foundation-manifest.json",
                        "foundation_decisions": "decisions.json", "domain_manifest": "domain-manifest.json",
                        "trading_taxonomy": "taxonomy.json",
                        "repository_index": "index.json", "selected_manifest": "stack.json",
                        "freshness_snapshot": "freshness.json"},
        }
        foundation_rows = [v2_row("foundation", layer_id, layer_id) for layer_id in FOUNDATION_LAYERS]
        domain_rows = [v2_row("us-equities", layer_id, layer_id, group="data-domain")
                       for layer_id in US_EQUITIES_LAYERS]
        self.foundation_doc = {"schema_version": 2, "checked_at": "2026-09-22", "scope": "General",
                               "layers": foundation_rows}
        self.domain_doc = {"schema_version": 2, "checked_at": "2026-09-22", "scope": "General",
                           "layers": domain_rows}

        self.write("catalogs/landscape/manifest.json", manifest, at_landscape_manifest=True)
        self.write("catalogs/landscape/foundation.json", self.foundation_doc)
        self.write("catalogs/landscape/us-equities.json", self.domain_doc)
        self.write("foundation-manifest.json", {"layers": [{"id": layer_id} for layer_id in FOUNDATION_LAYERS]})
        self.write("domain-manifest.json", {"catalog_files": ["data.json"]})
        self.write("data.json", {"layer": "data-domain", "checked_at": "2026-09-19", "entries": [{
            "id": "old", "repository": "https://github.com/example/alternative", "role": "Old source candidate",
            "decision": "default", "rationale": "Historical reason", "evidence_level": "source_review",
            "version_or_commit": "v1", "limitations": ["Historical only"], "evidence_refs": ["receipt.json"]}]})
        self.write("taxonomy.json", {
            "foundation": [{"layer": layer_id, "components": []} for layer_id in FOUNDATION_LAYERS],
            "trading": [{"layer": layer_id, "entries": []} for layer_id in US_EQUITIES_LAYERS],
        })
        self.write("adoption/manifest.json", {"recipe_map": {}})
        indexed_repositories = {candidate["repository"] for candidate in V1_CANDIDATES}
        for layer_id in FOUNDATION_LAYERS + US_EQUITIES_LAYERS:
            indexed_repositories.add(repo(layer_id, "c1"))
            indexed_repositories.add(repo(layer_id, "c2"))
        self.write("index.json", {"aliases": {},
                   "records": [{"repository": url} for url in sorted(indexed_repositories)]})
        self.write("stack.json", {"components": [{"id": "selected", "version": "1",
                   "repository": "https://github.com/example/selected", "source_pin": "a" * 40}]})
        self.write("decisions.json", {"decisions": [{"review_status": "accepted_within_scope"}]})
        freshness = {"schema_version": 1, "scope": "Metadata only",
                    "components": [{"component_id": "selected", "selected_version": "1",
                                    "selected_repository_url": "https://github.com/example/selected",
                                    "selected_source_pin": "a" * 40}],
                    "stars": {"status": "checked", "repository_snapshot_count": 1,
                              "repositories": [{"repository": "https://github.com/example/selected"}],
                              "observed_identity_set_sha256":
                                  hashlib.sha256(b"https://github.com/example/selected").hexdigest()}}
        self.write("freshness.json", freshness)
        self.write("receipt.json", {"exit_code": 0, "scope": "A local fixture, not upstream E2E"})

    def write(self, path, value, at_landscape_manifest=False):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def load_row(self, catalog, layer_id):
        relative = record_verdicts.LEDGER_FILES[catalog]
        document = json.loads((self.root / relative).read_text(encoding="utf-8"))
        return next(row for row in document["layers"] if row["layer_id"] == layer_id)

    def run_main(self, *, write=True, check=False, adjudications=None, lane_roots=()):
        args = ["--root", str(self.root), "--work-dir", str(self.work_dir), "--checked-at", "2026-09-22"]
        for lane_root in lane_roots:
            args += ["--lane-repo-root", lane_root]
        args.append("--write" if write else "--check")
        if check:
            args.append("--check")
        if adjudications is not None:
            args += ["--adjudications", str(adjudications)]
        return record_verdicts.main(args)

    def build_packet_pair(self, catalog, layer_id, *, c1_component=None, c2_component=None):
        c1 = make_candidate("c1", layer_id, "c1", component_id=c1_component)
        c2 = make_candidate("c2", layer_id, "c2", component_id=c2_component)
        packet = make_packet(catalog, layer_id, [c1, c2])
        digest = self.packets.write(catalog, layer_id, packet)
        self.packets.flush()
        return c1, c2, digest


class SameWinnerTests(RecordVerdictsFixture):
    def test_same_winner_records_and_round_trips(self):
        catalog, layer_id = "foundation", "same-winner-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id,
                                                  c1_component="same-winner-component")
        alt = make_alternative(c2)
        for lane in ("claude", "codex"):
            write_lane(self.work_dir, lane, catalog, layer_id,
                       make_lane_return(lane, catalog, layer_id, digest, ["c1"], [alt]))

        original_row = self.load_row(catalog, layer_id)
        original_v1 = {key: original_row[key] for key in
                       ("requirement", "current_choice", "decision", "rationale", "candidates",
                        "limitations", "evidence_refs", "overturn_when")}

        exit_code = self.run_main(write=True)
        self.assertEqual(exit_code, 0)

        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual(len(row["winners"]), 1)
        winner = row["winners"][0]
        self.assertEqual(winner["component_id"], "same-winner-component")
        self.assertEqual(winner["repository"], c1["repository"])
        self.assertEqual(winner["pin"], "1.0")
        self.assertEqual(winner["recipe_ref"], "catalogs/landscape/foundation.json")
        self.assertEqual(winner["platform_status"], {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"})
        self.assertEqual(len(row["alternatives"]), 1)
        self.assertEqual(row["alternatives"][0]["repository"], c2["repository"])
        self.assertEqual(row["alternatives"][0]["source"], "lane:claude")
        self.assertEqual(row["lanes"]["agreement"], "same_winner")
        self.assertTrue(row["lanes"]["claude"]["sealed_sha256"])
        self.assertTrue(row["lanes"]["codex"]["sealed_sha256"])
        self.assertEqual(row["checked_at"], "2026-09-22")
        self.assertIn("tests/test_record_verdicts.py", row["verdict_overturn_when"])
        self.assertNotIn("tests/test_record_verdicts.py", row["overturn_when"])

        # v1 fields byte-identical (the row validator's "never modifies v1
        # fields" contract, checked directly here rather than only implied
        # by build_landscape() succeeding below).
        for key, value in original_v1.items():
            self.assertEqual(row[key], value, key)

        # The sealed evidence file's bytes hash to the recorded sealed_sha256.
        for lane in ("claude", "codex"):
            run_id = row["lanes"][lane]["run_id"]
            self.assertEqual(run_id, f"{catalog}-{layer_id}-20260922")
            sealed_path = self.root / record_verdicts.SEALED_BASE / lane / f"{run_id}.json"
            self.assertTrue(sealed_path.is_file())
            digest_actual = hashlib.sha256(sealed_path.read_bytes()).hexdigest()
            self.assertEqual(digest_actual, row["lanes"][lane]["sealed_sha256"])

        # Every written row passes the real layer-verdict schema v2 validator.
        build_landscape(self.root)

        # --check now exits 0 (idempotent) ...
        self.assertEqual(self.run_main(write=False, check=True), 0)
        # ... and a second --write changes nothing.
        before = (self.root / "catalogs/landscape/foundation.json").read_text(encoding="utf-8")
        self.assertEqual(self.run_main(write=True), 0)
        after = (self.root / "catalogs/landscape/foundation.json").read_text(encoding="utf-8")
        self.assertEqual(before, after)


class CodexAbsentTests(RecordVerdictsFixture):
    def test_codex_absent_records_from_claude_only(self):
        catalog, layer_id = "foundation", "codex-absent-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        alt = make_alternative(c2)
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [alt]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual(row["lanes"]["agreement"], "codex_absent")
        self.assertIn("codex lane absent for this layer", row["open_gaps"])
        self.assertEqual(row["lanes"]["codex"], {"run_id": "", "sealed_sha256": ""})
        self.assertTrue(row["lanes"]["claude"]["sealed_sha256"])
        build_landscape(self.root)


class DisagreeTests(RecordVerdictsFixture):
    def write_disagreeing_lanes(self, catalog, layer_id, digest, c1, c2):
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c2"], [make_alternative(c1)]))

    def test_disagree_without_adjudication_stays_pending(self):
        catalog, layer_id = "foundation", "disagree-pending-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        self.write_disagreeing_lanes(catalog, layer_id, digest, c1, c2)

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["alternatives"], [])
        self.assertEqual(row["lanes"]["agreement"], "disagree")
        self.assertTrue(row["lanes"]["claude"]["sealed_sha256"])
        self.assertTrue(row["lanes"]["codex"]["sealed_sha256"])
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("lanes disagreed"))
        # "<ids>" names winner component_ids (the same identity the
        # agreement check itself compares), not the opaque packet-local
        # candidate keys -- see the regression test in DisagreeTests for the
        # component_id-vs-key distinction.
        self.assertIn(f"claude=candidate:example-{layer_id}-c1", gap)
        self.assertIn(f"codex=candidate:example-{layer_id}-c2", gap)
        self.assertIn("adjudication pending", gap)
        build_landscape(self.root)

    def test_disagree_with_adjudication_records_from_adjudicated_lane(self):
        catalog, layer_id = "foundation", "disagree-adjudicated-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id,
                                                  c1_component="adjudicated-component")
        self.write_disagreeing_lanes(catalog, layer_id, digest, c1, c2)
        adjudications_dir = self.work_dir / "adjudications"
        write_adjudication(adjudications_dir, catalog, layer_id, counterbalanced(
            "claude", why="Claude's evidence was stronger on native execution."))

        self.assertEqual(self.run_main(write=True, adjudications=adjudications_dir), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual(row["winners"][0]["component_id"], "adjudicated-component")
        self.assertEqual(row["lanes"]["agreement"], "disagree")
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("lanes disagreed"))
        self.assertIn("adjudicated by", gap)
        run_id = row["lanes"]["claude"]["run_id"]
        adjudication_path = self.root / record_verdicts.SEALED_BASE / "adjudication" / f"{run_id}.json"
        self.assertTrue(adjudication_path.is_file())
        adjudication_data = json.loads(adjudication_path.read_text(encoding="utf-8"))
        self.assertEqual(adjudication_data["winner_lane"], "claude")
        self.assertIn(f"{record_verdicts.SEALED_BASE}/adjudication/{run_id}.json", gap)
        build_landscape(self.root)

    def test_split_counterbalanced_adjudication_is_sealed_and_stays_pending(self):
        catalog, layer_id = "foundation", "disagree-split-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        self.write_disagreeing_lanes(catalog, layer_id, digest, c1, c2)
        adjudications_dir = self.work_dir / "adjudications"
        # Each order chose whichever return was shown as A: a position effect, not evidence.
        write_adjudication(adjudications_dir, catalog, layer_id, counterbalanced(
            None, why="Every judgment followed the presentation order.",
            picks={"A": "claude", "B": "codex"}))

        self.assertEqual(self.run_main(write=True, adjudications=adjudications_dir), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("lanes disagreed"))
        self.assertIn("did not agree (claude 1, codex 1, 0 refuted", gap)
        self.assertNotIn("adjudication pending", gap)
        run_id = row["lanes"]["claude"]["run_id"]
        sealed = self.root / record_verdicts.SEALED_BASE / "adjudication" / f"{run_id}.json"
        self.assertTrue(sealed.is_file())
        self.assertIsNone(json.loads(sealed.read_text(encoding="utf-8"))["winner_lane"])
        self.assertIn(f"{record_verdicts.SEALED_BASE}/adjudication/{run_id}.json", gap)
        self.assertEqual(self.run_main(write=False, adjudications=adjudications_dir), 0)
        build_landscape(self.root)

    def assert_adjudication_rejected(self, layer_id, data, reason_fragment):
        catalog = "foundation"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        self.write_disagreeing_lanes(catalog, layer_id, digest, c1, c2)
        adjudications_dir = self.work_dir / "adjudications"
        write_adjudication(adjudications_dir, catalog, layer_id, data)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True, adjudications=adjudications_dir), 1)
        self.assertIn(f"{catalog}__{layer_id} [adjudication]", output.getvalue())
        self.assertIn(reason_fragment, output.getvalue())
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])

    def test_adjudication_from_one_presentation_order_is_rejected(self):
        data = counterbalanced("claude")
        data["judgments"] = [data["judgments"][0]]
        self.assert_adjudication_rejected("disagree-one-order-layer", data, "both presentation orders")

    def test_adjudication_without_judgments_is_rejected(self):
        data = counterbalanced("claude")
        del data["judgments"]
        self.assert_adjudication_rejected("disagree-no-judgments-layer", data, "both presentation orders")

    def test_winner_lane_over_a_split_is_rejected(self):
        data = counterbalanced("claude", picks={"A": "claude", "B": "codex"})
        self.assert_adjudication_rejected("disagree-split-claimed-layer", data, "must equal the lane")

    def test_winner_lane_over_a_refuted_judgment_is_rejected(self):
        data = counterbalanced("claude")
        data["judgments"][1]["refuting_votes"] = 1
        self.assert_adjudication_rejected("disagree-refuted-layer", data, "must equal the lane")

    def test_split_without_an_explicit_null_winner_lane_is_rejected(self):
        data = counterbalanced(None, picks={"A": "claude", "B": "codex"})
        del data["winner_lane"]
        self.assert_adjudication_rejected("disagree-missing-winner-layer", data, "winner_lane claude|codex|null")

    def test_boolean_refuting_votes_is_rejected(self):
        data = counterbalanced("claude")
        data["judgments"][0]["refuting_votes"] = False
        self.assert_adjudication_rejected("disagree-bool-votes-layer", data, "nonnegative integer refuting_votes")

    def test_judgments_that_are_not_a_list_are_rejected(self):
        data = counterbalanced("claude")
        data["judgments"] = {"A": data["judgments"][0]}
        self.assert_adjudication_rejected("disagree-judgments-object-layer", data, "both presentation orders")

    def test_judgment_lane_contradicting_its_positions_is_rejected(self):
        data = counterbalanced("claude")
        data["judgments"][0]["preferred_position"] = "B"
        self.assert_adjudication_rejected("disagree-contradiction-layer", data, "contradicts")


class RejectedLaneTests(RecordVerdictsFixture):
    def test_rejected_codex_lane_file_is_treated_as_absent(self):
        catalog, layer_id = "foundation", "rejected-codex-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))
        # A bad packet hash -- the codex file is well-formed otherwise.
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, "0" * 64, ["c1"], [make_alternative(c2)]))

        exit_code = self.run_main(write=True)
        self.assertEqual(exit_code, 1)
        row = self.load_row(catalog, layer_id)
        # Rejected codex file treated as absent -- the row still records from
        # Claude alone, exactly like the codex_absent case.
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual(row["lanes"]["agreement"], "codex_absent")
        self.assertEqual(row["lanes"]["codex"], {"run_id": "", "sealed_sha256": ""})
        build_landscape(self.root)


class UnindexedAlternativeTests(RecordVerdictsFixture):
    def test_unindexed_alternative_moves_to_open_gaps(self):
        catalog, layer_id = "us-equities", "unindexed-alt-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        unindexed = {"key": None, "name": "Unindexed alt", "disposition": "conditional",
                     "repository": "https://github.com/example/not-in-the-index",
                     "why_not_default": long_text("Not indexed in the canonical repository list.", 30),
                     "evidence_class": "source_review", "evidence_refs": []}
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"],
                                     [make_alternative(c2), unindexed]))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        alt_repositories = {alt["repository"] for alt in row["alternatives"]}
        self.assertNotIn("https://github.com/example/not-in-the-index", alt_repositories)
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("unindexed alternative"))
        self.assertIn("Unindexed alt", gap)
        self.assertIn("https://github.com/example/not-in-the-index", gap)
        build_landscape(self.root)

    def test_unindexed_alternative_still_surfaces_on_a_disagree_pending_row(self):
        # The rule must fire even when no verdict is recorded this run --
        # build_alternatives() used to run only inside the "recorded" branch,
        # silently dropping an unindexed alternative named on a
        # disagree-pending (or codex-only) row.
        catalog, layer_id = "us-equities", "unindexed-pending-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        unindexed = {"key": None, "name": "Pending unindexed alt", "disposition": "conditional",
                     "repository": "https://github.com/example/pending-not-in-the-index",
                     "why_not_default": long_text("Not indexed in the canonical repository list.", 30),
                     "evidence_class": "source_review", "evidence_refs": []}
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"],
                                     [make_alternative(c2), unindexed]))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c2"], [make_alternative(c1)]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        # Lanes disagree (c1 vs c2) so nothing is recorded this run ...
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["alternatives"], [])
        # ... but the unindexed alternative is still not silently lost.
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("unindexed alternative"))
        self.assertIn("Pending unindexed alt", gap)
        self.assertIn("https://github.com/example/pending-not-in-the-index", gap)
        build_landscape(self.root)


class PinFallbackTests(RecordVerdictsFixture):
    def test_winner_pin_falls_back_to_the_v1_candidate_source_pin(self):
        # The real v1 candidate schema never carries a "v1_pin" field; a pin
        # text, when a lane recorded one at all, lives under "source_pin"
        # (preferred) or "revision" -- see catalogs/landscape/{foundation,
        # us-equities}.json's actual field names.
        catalog, layer_id = "foundation", "pin-fallback-layer"
        relative = record_verdicts.LEDGER_FILES[catalog]
        path = self.root / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in document["layers"] if item["layer_id"] == layer_id)
        row["candidates"] = [
            {"name": "c1 candidate", "repository": repo(layer_id, "c1"), "disposition": "selected",
             "rationale": "Fits the requirement", "evidence_kind": "native_execution",
             "evidence_refs": ["receipt.json"], "source_pin": "d" * 40},
            {"name": "c2 candidate", "repository": repo(layer_id, "c2"), "disposition": "unqualified",
             "rationale": "Not tested on this host", "evidence_kind": "source_review",
             "evidence_refs": ["receipt.json"]},
        ]
        path.write_text(json.dumps(document), encoding="utf-8")

        c1 = make_candidate("c1", layer_id, "c1", pin=None)
        c2 = make_candidate("c2", layer_id, "c2", pin=None)
        packet = make_packet(catalog, layer_id, [c1, c2])
        digest = self.packets.write(catalog, layer_id, packet)
        self.packets.flush()
        alt = make_alternative(c2)
        for lane in ("claude", "codex"):
            write_lane(self.work_dir, lane, catalog, layer_id,
                       make_lane_return(lane, catalog, layer_id, digest, ["c1"], [alt]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["winners"][0]["pin"], "d" * 40)
        build_landscape(self.root)

    def test_winner_pin_falls_back_to_unpinned_with_no_manifest_or_v1_pin(self):
        # No manifest pin (packet candidate pin=None) and no matching v1
        # candidate carries source_pin/revision either -- "unpinned" is the
        # last resort, not silently substituted for a real value.
        catalog, layer_id = "foundation", "pin-unpinned-layer"
        c1 = make_candidate("c1", layer_id, "c1", pin=None)
        c2 = make_candidate("c2", layer_id, "c2", pin=None)
        packet = make_packet(catalog, layer_id, [c1, c2])
        digest = self.packets.write(catalog, layer_id, packet)
        self.packets.flush()
        alt = make_alternative(c2)
        for lane in ("claude", "codex"):
            write_lane(self.work_dir, lane, catalog, layer_id,
                       make_lane_return(lane, catalog, layer_id, digest, ["c1"], [alt]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["winners"][0]["pin"], "unpinned")
        build_landscape(self.root)


class ChallengerPreferredTests(RecordVerdictsFixture):
    def test_challenger_preferred_adds_an_open_gap(self):
        catalog, layer_id = "foundation", "challenger-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        challenger = {"key": None, "name": "Non-adopted challenger",
                      "repository": "https://github.com/example/challenger",
                      "why": "Looks stronger on unverified evidence.",
                      "required_comparison": "python3 tests/test_record_verdicts.py"}
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     challenger_preferred=challenger))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        gap = next(gap for gap in row["open_gaps"] if gap.startswith("lane claude prefers"))
        self.assertIn("Non-adopted challenger", gap)
        self.assertIn("https://github.com/example/challenger", gap)
        self.assertIn("python3 tests/test_record_verdicts.py", gap)
        build_landscape(self.root)


class OverturnProtocolTests(RecordVerdictsFixture):
    def test_claude_protocol_used_when_nonempty(self):
        catalog, layer_id = "foundation", "protocol-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        claude_protocol = {"fixture_paths": ["tests/fixtures/claude.json"], "metric": "accuracy", "arms": ["a", "b"]}
        codex_protocol = {"fixture_paths": ["tests/fixtures/codex.json"], "metric": "latency", "arms": ["c", "d"]}
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     overturn_protocol=claude_protocol))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     overturn_protocol=codex_protocol))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["overturn_protocol"], claude_protocol)
        build_landscape(self.root)

    def test_codex_protocol_used_when_claude_protocol_is_empty(self):
        catalog, layer_id = "foundation", "protocol-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        codex_protocol = {"fixture_paths": ["tests/fixtures/codex.json"], "metric": "latency", "arms": ["c", "d"]}
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     overturn_protocol=codex_protocol))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["overturn_protocol"], codex_protocol)
        build_landscape(self.root)


class SameWinnerCodexGapsTests(RecordVerdictsFixture):
    def test_same_winner_appends_codexs_open_gaps(self):
        catalog, layer_id = "foundation", "same-winner-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     open_gaps=["claude-only gap"]))
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)],
                                     open_gaps=["codex-only gap"]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertIn("claude-only gap", row["open_gaps"])
        self.assertIn("codex-only gap", row["open_gaps"])
        build_landscape(self.root)


class CodexOnlyTests(RecordVerdictsFixture):
    def test_codex_only_folds_into_pending_not_a_recorded_verdict(self):
        # The contract names only "Codex only -> no dedicated agreement
        # value"; record_verdicts.py's own reading folds it into the
        # "neither lane ran" pending state. No winner is ever recorded from a
        # single non-Claude lane, even though Codex's file is still sealed.
        catalog, layer_id = "foundation", "codex-only-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        write_lane(self.work_dir, "codex", catalog, layer_id,
                   make_lane_return("codex", catalog, layer_id, digest, ["c1"], [make_alternative(c2)]))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["alternatives"], [])
        self.assertEqual(row["lanes"]["agreement"], "pending")
        self.assertIn("claude lane absent for this layer", row["open_gaps"])
        self.assertEqual(row["lanes"]["claude"], {"run_id": "", "sealed_sha256": ""})
        self.assertTrue(row["lanes"]["codex"]["sealed_sha256"])
        build_landscape(self.root)


class CheckExitCodeTests(RecordVerdictsFixture):
    def test_check_exits_one_when_the_ledger_differs_from_the_recomputed_output(self):
        catalog, layer_id = "foundation", "same-winner-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        alt = make_alternative(c2)
        for lane in ("claude", "codex"):
            write_lane(self.work_dir, lane, catalog, layer_id,
                       make_lane_return(lane, catalog, layer_id, digest, ["c1"], [alt]))

        # No --write yet: the checked-in ledger is still all-pending, so
        # --check must recompute a real difference and exit 1 (only the
        # idempotent, already-converged half of --check was covered before).
        exit_code = self.run_main(write=False, check=True)
        self.assertEqual(exit_code, 1)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")  # --check never writes


class CliModeTests(unittest.TestCase):
    def test_write_and_check_together_is_rejected(self):
        with self.assertRaises(SystemExit):
            record_verdicts.parse_args(["--work-dir", "/tmp/does-not-matter", "--write", "--check"])

    def test_neither_write_nor_check_is_rejected(self):
        with self.assertRaises(SystemExit):
            record_verdicts.parse_args(["--work-dir", "/tmp/does-not-matter"])


class ValidateLaneReturnRuleTests(unittest.TestCase):
    """Direct unit coverage of the "rules beyond the JSON schema" in
    validate_lane_return: previously only the packet_sha256-mismatch rule was
    exercised end-to-end (RejectedLaneTests); the other five, plus the
    challenger_preferred.required_comparison marker rule, had none."""

    def setUp(self):
        work_temp = tempfile.TemporaryDirectory()
        self.addCleanup(work_temp.cleanup)
        self.work_dir = Path(work_temp.name).resolve()
        self.catalog, self.layer_id = "foundation", "rule-fixture-layer"
        self.c1 = make_candidate("c1", self.layer_id, "c1")
        self.c2 = make_candidate("c2", self.layer_id, "c2")
        self.c3 = make_candidate("c3", self.layer_id, "c3", adopted=False)
        self.candidates_by_key = {c["key"]: c for c in (self.c1, self.c2, self.c3)}
        packet = make_packet(self.catalog, self.layer_id, [self.c1, self.c2, self.c3])
        packet_text = json.dumps(packet, sort_keys=True, indent=1) + "\n"
        self.packet_sha256 = hashlib.sha256(packet_text.encode("utf-8")).hexdigest()
        self.packet_filename = f"{self.catalog}__{self.layer_id}.json"
        self.sha256sums = {self.packet_filename: self.packet_sha256}

    def validate(self, data):
        path = self.work_dir / "lane.json"
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return record_verdicts.validate_lane_return(
            path, lane="claude", catalog=self.catalog, layer_id=self.layer_id,
            candidates_by_key=self.candidates_by_key, packet_sha256sums=self.sha256sums,
            packet_filename=self.packet_filename)

    def base_return(self, **overrides):
        data = make_lane_return("claude", self.catalog, self.layer_id, self.packet_sha256,
                                 ["c1"], [make_alternative(self.c2)])
        data.update(overrides)
        return data

    def test_winner_key_not_an_adopted_candidate_is_rejected(self):
        data = self.base_return(winner_keys=["c3"])  # c3 exists in the packet but adopted=False
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("not an adopted packet candidate", str(ctx.exception))

    def test_adopted_non_winner_missing_from_alternatives_is_rejected(self):
        # c2 is adopted and not the winner, but never named in alternatives.
        stray = make_alternative(self.c3, why_suffix="stray")
        data = self.base_return(alternatives=[stray])
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("missing from alternatives", str(ctx.exception))

    def test_why_selected_equal_to_a_why_not_default_is_rejected(self):
        alt = make_alternative(self.c2)
        # why_selected requires >= 60 chars on its own; pad both alt and
        # override text identically so the equality check is what fails,
        # not the separate minimum-length rule.
        # It also cites receipt.json so the separate "names a cited path" rule passes.
        alt["why_not_default"] = long_text(alt["why_not_default"] + " See receipt.json.", 60)
        data = self.base_return(alternatives=[alt], why_selected=alt["why_not_default"])
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("must differ from every alternative's why_not_default", str(ctx.exception))

    def test_overturn_when_without_a_marker_is_rejected(self):
        data = self.base_return(overturn_when="Nothing here names a concrete check at all.")
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("overturn_when must name", str(ctx.exception))

    def test_non_https_alternative_repository_is_rejected(self):
        alt = make_alternative(self.c2)
        alt["repository"] = "git@github.com:example/alt.git"
        data = self.base_return(alternatives=[alt])
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("alternative repository must be an https URL", str(ctx.exception))

    def test_challenger_preferred_required_comparison_without_a_marker_is_rejected(self):
        data = self.base_return(challenger_preferred={
            "key": None, "name": "Challenger", "repository": "https://github.com/example/challenger",
            "why": "Might be better", "required_comparison": "just trust me, no path or command here"})
        with self.assertRaises(record_verdicts.LaneRejected) as ctx:
            self.validate(data)
        self.assertIn("challenger_preferred required_comparison must name", str(ctx.exception))


class CitationNormalizationTests(RecordVerdictsFixture):
    """Lane citations carry line anchors and commentary; the ledger row keeps the bare
    canonical repository path and the sealed lane return keeps the full citation."""

    def test_citation_path_strips_anchors_and_commentary(self):
        cases = {
            "docs/a.md:107-130": "docs/a.md",
            "catalogs/b.json#L564-L603 (decision id x)": "catalogs/b.json",
            "adoption/receipt.json lines 10-11, 14": "adoption/receipt.json",
            "evidence/c.json:1-21,84-105": "evidence/c.json",
            "blueprints/d/README.md": "blueprints/d/README.md",
            "https://github.com/acme/x (release notes)": "https://github.com/acme/x",
        }
        for citation, expected in cases.items():
            self.assertEqual(record_verdicts.citation_path(citation), expected, citation)

    def test_recorded_row_keeps_canonical_paths_and_counts_unresolved_citations(self):
        catalog, layer_id = "foundation", "citation-layer"
        c1, c2, digest = self.build_packet_pair(catalog, layer_id)
        alt = make_alternative(c2)
        alt["evidence_refs"] = ["receipt.json (why not default)"]
        self.write("manifests/evidence.json", {"files": []})
        citations = ["receipt.json:10-12", "receipt.json#L3 (anchored note)", "receipt.json lines 1-2",
                     "packets/foundation__citation-layer.json#candidates[c1]", "manifests/evidence.json#/files"]
        write_lane(self.work_dir, "claude", catalog, layer_id,
                   make_lane_return("claude", catalog, layer_id, digest, ["c1"], [alt],
                                    winner_evidence_refs=citations))

        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row(catalog, layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual(row["winners"][0]["evidence_refs"], ["receipt.json"])
        self.assertEqual(row["alternatives"][0]["evidence_refs"], ["receipt.json"])
        self.assertIn("2 lane citation(s) name no repository evidence file (an unresolved path or a generated "
                      "index); the full citations are kept in the sealed lane return", row["open_gaps"])
        sealed = json.loads((self.root / "evidence/artifacts/layer-verdicts-20260922/claude"
                             / f"{catalog}-{layer_id}-20260922.json").read_text(encoding="utf-8"))
        self.assertEqual(sealed["winner_evidence_refs"], citations)
        build_landscape(self.root)


class ReviewFindingTests(RecordVerdictsFixture):
    """Regression tests for the independent review of the PR-5 tooling."""

    def recorded(self, layer_id, **lane_overrides):
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"], [make_alternative(c2)],
                                    **lane_overrides))
        return c1, c2, digest

    def sealed_path(self, lane, layer_id):
        return (self.root / "evidence/artifacts/layer-verdicts-20260922" / lane
                / f"foundation-{layer_id}-20260922.json")

    def test_adjudicated_row_never_lists_its_winner_as_an_alternative(self):
        layer_id = "review-adjudicated-layer"
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"], [make_alternative(c2)]))
        write_lane(self.work_dir, "codex", "foundation", layer_id,
                   make_lane_return("codex", "foundation", layer_id, digest, ["c2"], [make_alternative(c1)]))
        adjudications = self.work_dir / "adjudications"
        adjudications.mkdir()
        (adjudications / f"foundation__{layer_id}.json").write_text(json.dumps(
            counterbalanced("claude", why="Claude cites the executed receipt.")),
            encoding="utf-8")
        self.assertEqual(self.run_main(write=True, adjudications=adjudications), 0)
        row = self.load_row("foundation", layer_id)
        self.assertEqual(row["verdict_status"], "recorded")
        self.assertEqual([w["repository"] for w in row["winners"]], [c1["repository"]])
        self.assertNotIn(c1["repository"], [a["repository"] for a in row["alternatives"]])
        build_landscape(self.root)

    def test_malformed_adjudication_is_reported_not_ignored(self):
        layer_id = "review-badadj-layer"
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"], [make_alternative(c2)]))
        write_lane(self.work_dir, "codex", "foundation", layer_id,
                   make_lane_return("codex", "foundation", layer_id, digest, ["c2"], [make_alternative(c1)]))
        adjudications = self.work_dir / "adjudications"
        adjudications.mkdir()
        (adjudications / f"foundation__{layer_id}.json").write_text('{"winner_lane": "nobody"}', encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True, adjudications=adjudications), 1)
        self.assertIn(f"foundation__{layer_id} [adjudication]", output.getvalue())
        self.assertEqual(self.load_row("foundation", layer_id)["verdict_status"], "pending_lanes")

    def test_check_detects_a_tampered_sealed_file_and_landscape_rejects_it(self):
        layer_id = "review-sealed-layer"
        self.recorded(layer_id)
        self.assertEqual(self.run_main(write=True), 0)
        self.assertEqual(self.run_main(write=False), 0)
        sealed = self.sealed_path("claude", layer_id)
        sealed.write_text(sealed.read_text(encoding="utf-8").replace("receipt.json", "receipt.jsonX", 1),
                          encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_main(write=False), 1)
        with self.assertRaisesRegex(ValueError, "sealed_sha256 does not match"):
            build_landscape(self.root)

    def test_tampered_packet_file_rejects_the_lane(self):
        layer_id = "review-packet-layer"
        self.recorded(layer_id)
        packet = self.work_dir / "packets" / f"foundation__{layer_id}.json"
        packet.write_text(packet.read_text(encoding="utf-8") + " ", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True), 1)
        self.assertIn("does not match packets/SHA256SUMS", output.getvalue())

    def test_missing_sha256sums_entry_rejects_the_lane(self):
        layer_id = "review-nosum-layer"
        self.recorded(layer_id)
        sums = self.work_dir / "packets" / "SHA256SUMS"
        sums.write_text("".join(line + "\n" for line in sums.read_text(encoding="utf-8").splitlines()
                                if not line.endswith(f"foundation__{layer_id}.json")), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True), 1)
        self.assertIn(f"packets/SHA256SUMS has no entry for foundation__{layer_id}.json", output.getvalue())

    def test_leak_marker_in_lane_prose_rejects_that_lane_without_aborting(self):
        layer_id = "review-leak-layer"
        self.recorded(layer_id, limits=["The APCA credential names were not read."])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True), 1)
        self.assertIn("sealing refused", output.getvalue())
        self.assertEqual(self.load_row("foundation", layer_id)["verdict_status"], "pending_lanes")

    def test_sources_read_are_made_repository_relative_before_sealing(self):
        layer_id = "review-sources-layer"
        self.recorded(layer_id, sources_read=["/home/example/checkout/receipt.json (lines 1-2)",
                                              "/home/example/other-repo/receipt.json",
                                              "/home/example/.claude/skills/x/SKILL.md"])
        self.assertEqual(self.run_main(write=True, lane_roots=["/home/example/checkout"]), 0)
        sealed = json.loads(self.sealed_path("claude", layer_id).read_text(encoding="utf-8"))
        self.assertEqual(sealed["sources_read"][0], "receipt.json (lines 1-2)")
        # A same-named file from another checkout is never attributed to this repository.
        self.assertNotEqual(sealed["sources_read"][1], "receipt.json")
        self.assertNotIn("/home/", json.dumps(sealed))
        # --check reproduces the sealed text only with the same lane roots.
        self.assertEqual(self.run_main(write=False, lane_roots=["/home/example/checkout"]), 0)

    def test_generated_explorer_citation_is_excluded(self):
        layer_id = "review-explorer-layer"
        (self.root / "docs/ecosystem").mkdir(parents=True, exist_ok=True)
        (self.root / "docs/ecosystem/index.html").write_text("<html></html>", encoding="utf-8")
        self.recorded(layer_id, winner_evidence_refs=["receipt.json", "docs/ecosystem/index.html#layers"])
        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row("foundation", layer_id)
        self.assertEqual(row["winners"][0]["evidence_refs"], ["receipt.json"])
        self.assertTrue(any("generated index" in gap for gap in row["open_gaps"]))


class VerificationFindingTests(RecordVerdictsFixture):
    """Branches the fix verification found untested."""

    def test_recorded_row_reduced_to_no_alternative_stays_pending(self):
        layer_id = "verify-noalt-layer"
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        # The adopted c2 is named by key (so the lane passes validation) with an unindexed
        # repository, so the only alternative is moved to open_gaps.
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"],
                                    [dict(make_alternative(c2), repository="https://github.com/unindexed/c2")]))
        self.assertEqual(self.run_main(write=True), 0)
        row = self.load_row("foundation", layer_id)
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertIn("no indexed alternative remains for this verdict; recording deferred", row["open_gaps"])
        build_landscape(self.root)

    def test_leak_in_adjudication_is_reported_not_raised(self):
        layer_id = "verify-adjleak-layer"
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"], [make_alternative(c2)]))
        write_lane(self.work_dir, "codex", "foundation", layer_id,
                   make_lane_return("codex", "foundation", layer_id, digest, ["c2"], [make_alternative(c1)]))
        adjudications = self.work_dir / "adjudications"
        adjudications.mkdir()
        (adjudications / f"foundation__{layer_id}.json").write_text(json.dumps(
            counterbalanced("claude", why="The APCA broker receipt decides it.", evidence_refs=())),
            encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_main(write=True, adjudications=adjudications), 1)
        self.assertIn(f"foundation__{layer_id} [adjudication]: sealing refused", output.getvalue())
        self.assertEqual(self.load_row("foundation", layer_id)["verdict_status"], "pending_lanes")

    def test_landscape_rejects_a_winner_listed_among_alternatives(self):
        layer_id = "verify-winalt-layer"
        c1, c2, _ = self.recorded_pair(layer_id)
        foundation = json.loads((self.root / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))
        row = next(r for r in foundation["layers"] if r["layer_id"] == layer_id)
        row["alternatives"].append(dict(row["alternatives"][0], repository=c1["repository"],
                                        why_not_default="A hand edit that names the winner as an alternative."))
        (self.root / "catalogs/landscape/foundation.json").write_text(json.dumps(foundation), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lists a winner repository among its alternatives"):
            build_landscape(self.root)

    def recorded_pair(self, layer_id):
        c1, c2, digest = self.build_packet_pair("foundation", layer_id)
        write_lane(self.work_dir, "claude", "foundation", layer_id,
                   make_lane_return("claude", "foundation", layer_id, digest, ["c1"], [make_alternative(c2)]))
        self.assertEqual(self.run_main(write=True), 0)
        return c1, c2, digest


class LaneSchemaRuleTests(unittest.TestCase):
    # Reuse the rule-test fixture without re-running its inherited tests.
    setUp = ValidateLaneReturnRuleTests.setUp
    validate = ValidateLaneReturnRuleTests.validate
    base_return = ValidateLaneReturnRuleTests.base_return

    def test_extra_top_level_property_is_rejected(self):
        with self.assertRaisesRegex(record_verdicts.LaneRejected, "outside the lane-return schema: surprise"):
            self.validate(self.base_return(surprise=True))

    def test_extra_alternative_property_is_rejected(self):
        alt = make_alternative(self.c2)
        alt["score"] = 9
        with self.assertRaisesRegex(record_verdicts.LaneRejected, "alternative has properties outside"):
            self.validate(self.base_return(alternatives=[alt]))

    def test_non_https_challenger_repository_is_rejected(self):
        data = self.base_return(challenger_preferred={
            "key": None, "name": "Challenger", "repository": "example/challenger",
            "why": "Might be better", "required_comparison": "python3 tests/test_x.py"})
        with self.assertRaisesRegex(record_verdicts.LaneRejected, "challenger_preferred repository must be an https"):
            self.validate(data)

    def test_why_selected_must_cite_an_evidence_path(self):
        data = self.base_return(why_selected="x" * 80)
        with self.assertRaisesRegex(record_verdicts.LaneRejected, "why_selected must cite at least one"):
            self.validate(data)

    def test_why_selected_may_cite_a_path_outside_its_own_refs(self):
        # The contract lets a lane leave evidence_refs empty rather than guess.
        data = self.base_return(winner_evidence_refs=[],
                                why_selected="Observed native execution recorded in blueprints/x/receipt.json " * 2)
        self.assertEqual(self.validate(data)["winner_evidence_refs"], [])


if __name__ == "__main__":
    unittest.main()
