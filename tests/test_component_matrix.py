"""Tests for scripts/component_matrix.py: classification, the macOS-acceptance
flip rule and --check freshness. Every test builds its own temporary fixture
root; nothing here reads or writes the real repository tree except the two
tests that exercise --check against the actual checked-in outputs."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import component_matrix as cm

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _layer(layer_id="layer-a", *, verdict_status="recorded", agreement="same_winner",
           winners=None, alternatives=None, open_gaps=None) -> dict:
    return {
        "catalog": "foundation",
        "layer_id": layer_id,
        "title": f"Title for {layer_id}",
        "verdict_status": verdict_status,
        "winners": winners or [],
        "alternatives": alternatives or [],
        "lanes": {"claude": {}, "codex": {}, "agreement": agreement},
        "open_gaps": open_gaps or [],
    }


def _winner(component_id="widget", *, linux="accepted", macos="untested",
            repository="https://github.com/example/widget", pin="1.0.0",
            evidence_class="native_proven") -> dict:
    return {
        "component_id": component_id,
        "repository": repository,
        "pin": pin,
        "evidence_class": evidence_class,
        "platform_status": {"linux-wsl2-x86_64": linux, "macos-arm64": macos},
    }


def _init_root(root: Path, layers: list[dict], *, catalog_file="foundation.json") -> None:
    (root / "catalogs" / "landscape").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "hosts").mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    # component_matrix.py's --write/--check paths call host_receipts.build_summary(), which
    # now loads adoption/host-receipt.schema.json directly (single source of truth for
    # validate_receipt_shape); every fixture root needs a real copy of it.
    (root / "adoption").mkdir(parents=True, exist_ok=True)
    (root / "adoption" / "host-receipt.schema.json").write_text(
        (REPO_ROOT / "adoption" / "host-receipt.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    _write_json(root / "catalogs" / "landscape" / catalog_file, {
        "schema_version": 2, "checked_at": "2026-09-22", "scope": "test fixture", "layers": layers,
    })
    # component_matrix.py --write self-registers its two outputs in manifests/evidence.json;
    # a real repository checkout always has this file.
    _write_json(root / "manifests" / "evidence.json", {"schema_version": 1, "receipts": [], "files": []})


def _receipt(component_id: str, platform_id: str, *, stage="use", result="pass",
             evidence_class="native_proven", reviewed=True, second_physical_machine=True,
             os_value: str | None = None, architecture: str | None = None) -> dict:
    """A fully schema-shape-valid receipt (host_receipts.validate_receipt_shape must pass
    it with no errors): scripts/host_receipts.py's build_summary only lets a
    result=pass/native_proven/independently-reviewed receipt into
    independently_reviewed_native_proven_pass_stages (what the macOS flip rule reads) when
    it is also shape-valid, so a malformed test fixture would silently never satisfy it."""
    if os_value is None:
        os_value = "macos" if platform_id == "macos-arm64" else "linux"
    if architecture is None:
        architecture = "arm64" if platform_id == "macos-arm64" else "x86_64"
    reviews = [{"kind": "self", "ref": "record", "verdict": "agree", "at_utc": "2026-09-22T00:00:00Z"}]
    if reviewed:
        reviews.append({
            "kind": "independent_session", "ref": "test-suite", "verdict": "agree",
            "at_utc": "2026-09-22T01:00:00Z",
        })
    return {
        "schema_version": 1,
        "id": f"test-host-20260922--{component_id}--{stage}--20260922",
        "kind": "host_acceptance",
        "host": {
            "host_id": "test-host-20260922", "platform_id": platform_id, "os": os_value,
            "architecture": architecture, "second_physical_machine": second_physical_machine,
        },
        "catalog_revision": "0" * 40,
        "component_id": component_id,
        "stage": stage,
        "commands": [{
            "cmd": "echo hi", "exit": 0, "duration_s": 0.01,
            "output_sha256": "98ea6e4f216f2fb4b69fff9b3a44842c38686ca685f3f55dc48c5d3fb1107be4",
            "output_excerpt": "hi",
        }],
        "tool_versions": {},
        "observed_at_utc": "2026-09-22T01:00:00Z",
        "result": result,
        "claim": "test claim",
        "limitations": ["test limitation"],
        "evidence_class": evidence_class,
        "reviews": reviews,
    }


def _write_receipt(root: Path, receipt: dict) -> None:
    host_id = receipt["host"]["host_id"]
    path = root / "evidence" / "hosts" / host_id / f"{receipt['id']}.json"
    _write_json(path, receipt)


class ClassificationTests(unittest.TestCase):
    def test_dual_lane_same_winner(self):
        layer = _layer(verdict_status="recorded", agreement="same_winner")
        self.assertEqual(cm.classify_independent_review(layer), "dual_lane_same_winner")

    def test_dual_lane_adjudicated(self):
        layer = _layer(verdict_status="recorded", agreement="disagree")
        self.assertEqual(cm.classify_independent_review(layer), "dual_lane_adjudicated")

    def test_pending_lanes_overrides_agreement(self):
        # A disagreement whose adjudication did not resolve stays pending_lanes
        # even though lanes.agreement is still "disagree".
        layer = _layer(verdict_status="pending_lanes", agreement="disagree")
        self.assertEqual(cm.classify_independent_review(layer), "pending_lanes")

    def test_single_lane_when_no_second_lane(self):
        layer = _layer(verdict_status="recorded", agreement="codex_absent")
        self.assertEqual(cm.classify_independent_review(layer), "single_lane")

    def test_adjudication_ref_detected_by_path_existence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = cm.ADJUDICATION_TEMPLATE.format(catalog="foundation", layer_id="layer-a")
            _write_json(root / candidate, {"result": "did not agree"})
            layer = _layer(verdict_status="pending_lanes", agreement="disagree")
            ref = cm.find_adjudication_ref(root, "foundation", "layer-a", layer)
            self.assertEqual(ref, candidate)

    def test_adjudication_ref_detected_by_open_gaps_mention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = cm.ADJUDICATION_TEMPLATE.format(catalog="foundation", layer_id="layer-a")
            layer = _layer(
                verdict_status="pending_lanes", agreement="disagree",
                open_gaps=[f"lanes disagreed; the counterbalanced adjudication did not agree ({candidate})"],
            )
            ref = cm.find_adjudication_ref(root, "foundation", "layer-a", layer)
            self.assertEqual(ref, candidate)

    def test_adjudication_ref_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(verdict_status="recorded", agreement="same_winner")
            ref = cm.find_adjudication_ref(root, "foundation", "layer-a", layer)
            self.assertIsNone(ref)


class GapCountTests(unittest.TestCase):
    def test_counts_only_open_executable_now(self):
        doc = {
            "layers": [
                {
                    "catalog": "foundation", "layer_id": "layer-a",
                    "gaps": [
                        {"status": "open", "category": "executable_now"},
                        {"status": "open", "category": "executable_now"},
                        {"status": "open", "category": "not_actionable"},
                        {"status": "advanced_by_receipt", "category": "executable_now"},
                    ],
                },
            ],
        }
        counts = cm.gap_counts_by_layer(doc)
        self.assertEqual(counts[("foundation", "layer-a")], 2)

    def test_absent_document_yields_empty_map(self):
        self.assertEqual(cm.gap_counts_by_layer(None), {})


class FlipRuleTests(unittest.TestCase):
    def test_macos_accepted_without_receipt_fails_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])

            document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)
            self.assertIn("macos-arm64=accepted", flip_violations[0])

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = cm.main(["--root", str(root), "--check"])
            self.assertEqual(exit_code, 1, buffer.getvalue())
            self.assertIn("flip-rule violation", buffer.getvalue())

    def test_macos_accepted_with_reviewed_native_proven_receipt_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])
            _write_receipt(root, _receipt("widget", "macos-arm64", stage="use"))

            document, flip_violations = cm.build_document(root)
            self.assertEqual(flip_violations, [])

            winner_row = document["rows"][0]["winners"][0]
            self.assertEqual(winner_row["platforms"]["macos-arm64"]["e2e_state"], "host_verified")

            write_buffer = io.StringIO()
            with contextlib.redirect_stdout(write_buffer):
                write_exit = cm.main(["--root", str(root), "--write"])
            self.assertEqual(write_exit, 0, write_buffer.getvalue())

            check_buffer = io.StringIO()
            with contextlib.redirect_stdout(check_buffer):
                check_exit = cm.main(["--root", str(root), "--check"])
            self.assertEqual(check_exit, 0, check_buffer.getvalue())

    def test_wrong_stage_receipt_does_not_satisfy_flip_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])
            # "restart" is not "use" or "install"; the flip rule stays unsatisfied.
            _write_receipt(root, _receipt("widget", "macos-arm64", stage="restart"))

            _document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)

    def test_unreviewed_receipt_does_not_satisfy_flip_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])
            _write_receipt(root, _receipt("widget", "macos-arm64", stage="use", reviewed=False))

            _document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)

    def test_receipt_without_second_physical_machine_does_not_satisfy_flip_rule(self):
        # The described bypass: a recorder runs `record --platform-id macos-arm64` and
        # `review --kind human --verdict agree` on any single host, with
        # second_physical_machine left at its default (false). That alone must not flip
        # the winner's macos-arm64 e2e_state to host_verified.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])
            _write_receipt(root, _receipt("widget", "macos-arm64", stage="use", second_physical_machine=False))

            document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)
            winner_row = document["rows"][0]["winners"][0]
            self.assertEqual(winner_row["platforms"]["macos-arm64"]["e2e_state"], "accepted")

    def test_receipt_with_mismatched_os_architecture_does_not_satisfy_flip_rule(self):
        # A WSL host self-declaring host.os/architecture for macos-arm64 while
        # adoption/manifest.json records that platform as macos/arm64 must not flip it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="accepted")])
            _init_root(root, [layer])
            (root / "adoption").mkdir(parents=True, exist_ok=True)
            _write_json(root / "adoption" / "manifest.json", {
                "schema_version": 1,
                "platform_profiles": [
                    {"id": "macos-arm64", "os": "macos", "architecture": "arm64", "status": "drafted_not_accepted"},
                ],
            })
            _write_receipt(root, _receipt(
                "widget", "macos-arm64", stage="use", second_physical_machine=True,
                os_value="linux", architecture="x86_64",
            ))

            document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)
            winner_row = document["rows"][0]["winners"][0]
            self.assertEqual(winner_row["platforms"]["macos-arm64"]["e2e_state"], "accepted")

    def test_non_accepted_macos_status_never_flips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(macos="untested")])
            _init_root(root, [layer])

            _document, flip_violations = cm.build_document(root)
            self.assertEqual(flip_violations, [])


class CheckFreshnessTests(unittest.TestCase):
    def test_check_fails_when_no_outputs_written_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer()])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = cm.main(["--root", str(root), "--check"])
            self.assertEqual(exit_code, 1)
            self.assertIn("differs from the generated output", buffer.getvalue())

    def test_check_passes_immediately_after_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner()])])
            write_buffer = io.StringIO()
            with contextlib.redirect_stdout(write_buffer):
                write_exit = cm.main(["--root", str(root), "--write"])
            self.assertEqual(write_exit, 0, write_buffer.getvalue())

            check_buffer = io.StringIO()
            with contextlib.redirect_stdout(check_buffer):
                check_exit = cm.main(["--root", str(root), "--check"])
            self.assertEqual(check_exit, 0, check_buffer.getvalue())

    def test_check_fails_after_hand_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner()])])
            with contextlib.redirect_stdout(io.StringIO()):
                cm.main(["--root", str(root), "--write"])
            (root / cm.OUTPUT_MD).write_text("hand-edited, stale\n", encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = cm.main(["--root", str(root), "--check"])
            self.assertEqual(exit_code, 1, buffer.getvalue())

    def test_real_repository_outputs_are_current(self):
        # Guards against forgetting to rerun --write after editing the generator
        # or a real input file (landscape/decisions/gap-crosswalk/stack).
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = cm.main(["--root", str(REPO_ROOT), "--check"])
        self.assertEqual(exit_code, 0, buffer.getvalue())


class AlternativeAndDecisionJoinTests(unittest.TestCase):
    def test_alternative_defaults_to_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(alternatives=[{
                "name": "Unreviewed Thing", "repository": "https://github.com/example/unreviewed",
                "disposition": "unqualified", "evidence_class": "source_review",
            }])
            _init_root(root, [layer])
            document, _flip = cm.build_document(root)
            self.assertEqual(document["rows"][0]["alternatives"][0]["e2e_state"], "not_run")

    def test_lifecycle_stages_join_from_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(component_id="widget")])
            _init_root(root, [layer])
            _write_json(root / cm.DECISIONS_FILE, {
                "schema_version": 1, "decisions": [
                    {
                        "id": "widget-decision",
                        "lifecycle": {"stage_refs": [
                            {"component_id": "widget", "stage": "use", "status": "accepted_within_scope"},
                        ]},
                    },
                ],
            })
            document, _flip = cm.build_document(root)
            self.assertEqual(
                document["rows"][0]["winners"][0]["lifecycle_stages"],
                [{"stage": "use", "status": "accepted_within_scope"}],
            )

    def test_gap_crosswalk_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer()])
            document, _flip = cm.build_document(root)
            self.assertIsNone(document["rows"][0]["open_executable_now_gaps"])


if __name__ == "__main__":
    unittest.main()
