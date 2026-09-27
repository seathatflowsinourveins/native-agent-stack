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
from unittest import mock
from pathlib import Path

from scripts import component_matrix as cm
from scripts import host_receipts as hr

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _layer(layer_id="layer-a", *, verdict_status="recorded", agreement="same_winner",
           winners=None, alternatives=None, open_gaps=None, checked_at="2026-09-22", catalog="foundation") -> dict:
    layer = {
        "catalog": catalog,
        "layer_id": layer_id,
        "title": f"Title for {layer_id}",
        "verdict_status": verdict_status,
        "winners": winners or [],
        "alternatives": alternatives or [],
        "lanes": {"claude": {}, "codex": {}, "agreement": agreement},
        "open_gaps": open_gaps or [],
    }
    if checked_at is not None:  # scripts/landscape.py requires it on every verdict row
        layer["checked_at"] = checked_at
    return layer


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
             os_value: str | None = None, architecture: str | None = None, version="1.0.0",
             reviewer="reviewer-session", review_verdict="agree", observed_at="2026-09-22T01:00:00Z",
             qualified_models: list | None = None) -> dict:
    """A fully schema-shape-valid receipt (host_receipts.validate_receipt_shape must pass
    it with no errors): scripts/host_receipts.py's build_summary only lets a
    result=pass/native_proven/independently-reviewed receipt into
    independently_reviewed_native_proven_pass_stages (what the macOS flip rule reads) when
    it is also shape-valid, so a malformed test fixture would silently never satisfy it."""
    if os_value is None:
        os_value = "macos" if platform_id == "macos-arm64" else "linux"
    if architecture is None:
        architecture = "arm64" if platform_id == "macos-arm64" else "x86_64"
    recorder = {"identity_sha256": hr.identity_digest("recorder-session")}
    reviews = [{"kind": "self", "ref": "record", "verdict": "agree", "at_utc": observed_at, "reviewer": recorder}]
    if reviewed:
        reviews.append({
            "kind": "independent_session", "ref": "test-suite", "verdict": review_verdict,
            "at_utc": observed_at, "reviewer": {"identity_sha256": hr.identity_digest(reviewer)},
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
        "recorded_by": recorder,
        "component_id": component_id,
        "stage": stage,
        "commands": [{
            "cmd": "echo hi", "exit": 0, "duration_s": 0.01,
            "output_sha256": "98ea6e4f216f2fb4b69fff9b3a44842c38686ca685f3f55dc48c5d3fb1107be4",
            "output_excerpt": "hi",
        }],
        "tool_versions": {component_id: version},
        "observed_at_utc": observed_at,
        "result": result,
        "claim": "test claim",
        "limitations": ["test limitation"],
        "evidence_class": evidence_class,
        "reviews": reviews,
        **({"qualified_models": qualified_models} if qualified_models else {}),
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
            self.assertIn("platform_status.macos-arm64 declares 'accepted'", flip_violations[0])

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

    def test_receipt_for_an_old_pin_does_not_satisfy_flip_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner(macos="accepted", pin="1.1.0")])])
            _write_receipt(root, _receipt("widget", "macos-arm64", version="1.0.0"))
            _document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)
            self.assertIn("pin '1.1.0'", flip_violations[0])

    def test_same_identity_review_does_not_satisfy_flip_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner(macos="accepted")])])
            _write_receipt(root, _receipt("widget", "macos-arm64", reviewer="recorder-session"))
            _document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)

    def test_dissenting_review_vetoes_and_is_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner(macos="conditional")])])
            _write_receipt(root, _receipt("widget", "macos-arm64", review_verdict="needs_changes"))
            document, flip_violations = cm.build_document(root)
            self.assertEqual(len(flip_violations), 1)
            macos = document["rows"][0]["winners"][0]["platforms"]["macos-arm64"]
            self.assertEqual(macos["derived_status"], "not_established")
            self.assertEqual(macos["host_receipts"]["dissented"], 1)
            self.assertIn("dissented 1", cm.render_markdown(document))

    def test_conditional_macos_is_allowed_with_an_unreviewed_pin_bound_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner(macos="conditional")])])
            _write_receipt(root, _receipt("widget", "macos-arm64", reviewed=False))
            document, flip_violations = cm.build_document(root)
            self.assertEqual(flip_violations, [])
            self.assertEqual(document["rows"][0]["winners"][0]["platforms"]["macos-arm64"]["derived_status"],
                             "conditional")

    def test_markdown_shows_pass_and_fail_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner()])])
            _write_receipt(root, _receipt("widget", "linux-wsl2-x86_64", stage="use", result="fail", reviewed=False))
            document, _ = cm.build_document(root)
            self.assertIn("widget (accepted [0/1/0/0] / untested [0/0/0/0])", cm.render_markdown(document))

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


class AlternativeHostVerifiedTests(unittest.TestCase):
    """#164 review, item 2: an alternative is host_verified only on a reviewed use-stage pass, as a winner is
    accepted only on one (platform_status.ACCEPTING_STAGES)."""

    def _state(self, stages):
        summary = {"components": {"widget": {"platforms": {"linux-wsl2-x86_64": {"receipts": [
            {"path": f"evidence/hosts/h-20260922/{stage}.json", "stage": stage,
             "independently_reviewed_native_proven_pass": True, "layer_scope": None, "supersedes_path": None}
            for stage in stages]}}}}}
        return cm.build_alternative({"name": "Widget", "repository": "https://github.com/acme/widget"},
                                    cm.repository_to_component_id({"components": [
                                        {"id": "widget", "repository": "https://github.com/acme/widget"}]}),
                                    summary)["e2e_state"]

    def test_install_only_is_recorded_and_use_is_verified(self):
        self.assertEqual(self._state(["install"]), "receipts_recorded")
        self.assertEqual(self._state([]), "receipts_recorded")
        self.assertEqual(self._state(["install", "use"]), "host_verified")


CODEX = "https://github.com/openai/codex"


class LayerScopeTests(unittest.TestCase):
    """GPT-6 cross-family review: a use receipt must verify only the rows whose role it exercised. Codex wins
    foundation/native-clients and foundation/agent-sdks and is the foundation/workers alternative "Codex native
    workers"; a read-only exec receipt (the native-clients role) must not verify that workers alternative, whose
    owned writing child and worktree it never exercises."""

    def _document(self, *receipts):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        layers = [
            _layer("native-clients", winners=[_winner("codex", repository=CODEX, linux="conditional")]),
            _layer("agent-sdks", winners=[_winner("codex", repository=CODEX, linux="conditional")]),
            _layer("workers", alternatives=[{"name": "Codex native workers", "repository": CODEX,
                                             "disposition": "conditional", "evidence_class": "native_proven"},
                                            {"name": "Widget", "repository": "https://github.com/example/widget",
                                             "disposition": "overlap", "evidence_class": "native_proven"}]),
        ]
        _init_root(root, layers)
        _write_json(root / "manifests" / "stack.json", {"schema_version": 1, "components": [
            {"id": "codex", "repository": CODEX, "version": "1.0.0"},
            {"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.0"}]})
        for receipt in receipts:
            _write_receipt(root, receipt)
        document, flip_violations = cm.build_document(root)
        self.assertEqual(flip_violations, [])
        rows = {row["layer_id"]: row for row in document["rows"]}
        return rows

    @staticmethod
    def _codex_use(*layers, **overrides):
        receipt = _receipt("codex", "linux-wsl2-x86_64", **overrides)
        if layers:
            receipt["layer_refs"] = [{"catalog": "foundation", "layer_id": layer} for layer in layers]
        return receipt

    @staticmethod
    def _winner_state(rows, layer):
        return rows[layer]["winners"][0]["platforms"]["linux-wsl2-x86_64"]["e2e_state"]

    @staticmethod
    def _alternative(rows, name):
        return next(alt for alt in rows["workers"]["alternatives"] if alt["name"] == name)

    def test_an_unscoped_use_receipt_does_not_verify_the_workers_alternative(self):
        rows = self._document(self._codex_use())
        # Unchanged for winners: the receipt was recorded against the codex id and pin both winner rows share.
        self.assertEqual(self._winner_state(rows, "native-clients"), "host_verified")
        self.assertEqual(self._winner_state(rows, "agent-sdks"), "host_verified")
        codex_workers = self._alternative(rows, "Codex native workers")
        self.assertEqual(codex_workers["e2e_state"], "receipts_recorded")
        self.assertTrue(codex_workers["layer_scope_needed"])

    def test_a_receipt_scoped_to_another_layer_verifies_only_that_layer(self):
        rows = self._document(self._codex_use("native-clients"))
        self.assertEqual(self._winner_state(rows, "native-clients"), "host_verified")
        self.assertEqual(self._winner_state(rows, "agent-sdks"), "conditional")
        codex_workers = self._alternative(rows, "Codex native workers")
        self.assertEqual(codex_workers["e2e_state"], "receipts_recorded")
        self.assertNotIn("layer_scope_needed", codex_workers)

    def test_a_receipt_scoped_to_the_workers_layer_verifies_the_alternative(self):
        rows = self._document(self._codex_use("workers"))
        self.assertEqual(self._alternative(rows, "Codex native workers")["e2e_state"], "host_verified")
        self.assertEqual(self._winner_state(rows, "native-clients"), "conditional")
        self.assertEqual(self._winner_state(rows, "agent-sdks"), "conditional")

    def test_an_unscoped_receipt_still_verifies_a_single_layer_alternative(self):
        rows = self._document(_receipt("widget", "linux-wsl2-x86_64"))
        widget = self._alternative(rows, "Widget")
        self.assertEqual(widget["e2e_state"], "host_verified")
        self.assertNotIn("layer_scope_needed", widget)

    def test_a_superseded_generation_verifies_nothing(self):
        # Generation 1 was agreed; generation 2 supersedes it and carries a standing needs_changes review.
        first = self._codex_use("workers")
        second = self._codex_use("workers", review_verdict="needs_changes", observed_at="2026-09-22T02:00:00Z")
        second["id"] = first["id"] + "-2"
        second["supersedes"] = first["id"]
        rows = self._document(first, second)
        self.assertEqual(self._alternative(rows, "Codex native workers")["e2e_state"], "receipts_recorded")
        # And the same for a winner: an agreed superseded receipt no longer makes it host_verified.
        first_unscoped, second_unscoped = self._codex_use(), self._codex_use(
            review_verdict="needs_changes", observed_at="2026-09-22T02:00:00Z")
        second_unscoped["id"] = first_unscoped["id"] + "-2"
        second_unscoped["supersedes"] = first_unscoped["id"]
        rows = self._document(first_unscoped, second_unscoped)
        self.assertEqual(self._winner_state(rows, "native-clients"), "conditional")

    def test_a_mismatched_supersedes_link_retires_nothing(self):
        first = self._codex_use("workers")
        other = _receipt("widget", "linux-wsl2-x86_64", review_verdict="needs_changes")
        other["supersedes"] = first["id"]   # another component's id: not a supersede chain
        rows = self._document(first, other)
        self.assertEqual(self._alternative(rows, "Codex native workers")["e2e_state"], "host_verified")


class QualifiedModelsSurfacingTests(unittest.TestCase):
    """scripts/host_receipts.py record --qualified-model entries must surface per platform
    on the runtime component's winner row, and never affect the flip rule."""

    def test_qualified_model_surfaces_on_the_winner_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(component_id="vllm", linux="conditional", macos="untested")])
            _init_root(root, [layer])
            qm = [{"model_id": "Qwen/Qwen3-8B-AWQ", "revision": "abc123", "runtime": "vllm",
                  "runtime_version": "0.9.0", "bars": "20/20 tool calls, 4/5 tasks", "result": "pass"}]
            _write_receipt(root, _receipt("vllm", "linux-wsl2-x86_64", qualified_models=qm))

            document, flip_violations = cm.build_document(root)
            self.assertEqual(flip_violations, [])
            winner = document["rows"][0]["winners"][0]
            linux_qm = winner["platforms"]["linux-wsl2-x86_64"]["qualified_models"]
            self.assertEqual(len(linux_qm), 1)
            self.assertEqual(linux_qm[0]["model_id"], "Qwen/Qwen3-8B-AWQ")
            self.assertEqual(linux_qm[0]["runtime"], "vllm")
            self.assertEqual(linux_qm[0]["result"], "pass")
            self.assertIn("host_id", linux_qm[0])
            self.assertIn("receipt_path", linux_qm[0])
            # Never on the platform it was not recorded for.
            self.assertEqual(winner["platforms"]["macos-arm64"]["qualified_models"], [])

    def test_no_qualified_models_yields_empty_list_not_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(component_id="vllm")])
            _init_root(root, [layer])
            _write_receipt(root, _receipt("vllm", "linux-wsl2-x86_64"))
            document, _flip = cm.build_document(root)
            winner = document["rows"][0]["winners"][0]
            self.assertEqual(winner["platforms"]["linux-wsl2-x86_64"]["qualified_models"], [])

    def test_shape_invalid_receipt_never_surfaces_a_qualified_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer = _layer(winners=[_winner(component_id="vllm")])
            _init_root(root, [layer])
            qm = [{"model_id": "Qwen/Qwen3-8B-AWQ", "revision": "abc123", "runtime": "vllm",
                  "runtime_version": "0.9.0", "bars": "bars", "result": "pass"}]
            receipt = _receipt("vllm", "linux-wsl2-x86_64", qualified_models=qm)
            receipt["result"] = "not-a-known-result"  # shape-invalid: fails the schema's result enum
            _write_receipt(root, receipt)
            document, _flip = cm.build_document(root)
            winner = document["rows"][0]["winners"][0]
            self.assertEqual(winner["platforms"]["linux-wsl2-x86_64"]["qualified_models"], [])



class AliasReceiptTests(unittest.TestCase):
    """Receipts recorded under a manifests/stack.json id sharing the winner's repository are
    listed per winner x platform and never counted (status, counts, flip rule, e2e_state)."""

    def _root(self, root: Path, *, with_alias_receipt: bool, version="1.0.0") -> None:
        layer = _layer(winners=[_winner(component_id="widget-winner", macos="untested")])
        _init_root(root, [layer])
        _write_json(root / "manifests" / "stack.json", {"schema_version": 1, "components": [
            {"id": "widget", "repository": "https://github.com/Example/widget.git", "version": "1.0.0"}]})
        if with_alias_receipt:
            _write_receipt(root, _receipt("widget", "macos-arm64", version=version))

    @staticmethod
    def _without_alias_lists(document: dict) -> dict:
        document = json.loads(json.dumps(document))
        for row in document["rows"]:
            for winner in row["winners"]:
                for entry in winner["platforms"].values():
                    entry.pop("alias_receipts")
        return document

    def test_alias_receipt_is_listed_and_never_counted(self):
        with tempfile.TemporaryDirectory() as with_tmp, tempfile.TemporaryDirectory() as without_tmp:
            self._root(Path(with_tmp), with_alias_receipt=True)
            self._root(Path(without_tmp), with_alias_receipt=False)
            with_doc, with_flip = cm.build_document(Path(with_tmp))
            without_doc, without_flip = cm.build_document(Path(without_tmp))
            self.assertEqual(self._without_alias_lists(with_doc), self._without_alias_lists(without_doc))
            self.assertEqual(with_flip, without_flip)
            macos = with_doc["rows"][0]["winners"][0]["platforms"]["macos-arm64"]
            self.assertEqual(macos["derived_status"], "untested")
            self.assertEqual(macos["host_receipts"]["pass"], 0)
            self.assertEqual(macos["e2e_state"], "untested")
            [alias] = macos["alias_receipts"]
            self.assertEqual(alias["recorded_component_id"], "widget")
            self.assertEqual(alias["recorded_version"], "1.0.0")
            self.assertEqual((alias["evidence_class"], alias["stage"], alias["result"]), ("native_proven", "use", "pass"))
            self.assertIs(alias["binds"], False)
            self.assertIs(alias["version_matches_pin"], True)
            self.assertTrue(alias["path"].startswith("evidence/hosts/test-host-20260922/"))
            self.assertEqual(with_doc["rows"][0]["winners"][0]["platforms"]["linux-wsl2-x86_64"]["alias_receipts"], [])
            self.assertIn(alias["path"], cm.render_markdown(with_doc))
            self.assertIn("never counted", cm.render_markdown(with_doc))

    def test_alias_reason_names_a_version_that_is_not_the_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root(Path(tmp), with_alias_receipt=True, version="0.9.0")
            document, _flip = cm.build_document(Path(tmp))
            [alias] = document["rows"][0]["winners"][0]["platforms"]["macos-arm64"]["alias_receipts"]
            self.assertIs(alias["version_matches_pin"], False)
            self.assertIn("not the winner pin in full", alias["reason"])

    def test_no_alias_receipts_render_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root(Path(tmp), with_alias_receipt=False)
            document, _flip = cm.build_document(Path(tmp))
            markdown = cm.render_markdown(document)
            self.assertIn("## Alias receipts (listed, never counted)", markdown)
            self.assertNotIn("Listed:", markdown)
            self.assertIn("\n\nNone.\n", markdown)

    def test_alias_prose_is_derived_from_the_listed_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._root(root, with_alias_receipt=True)
            document, _flip = cm.build_document(root)
            [alias] = document["rows"][0]["winners"][0]["platforms"]["macos-arm64"]["alias_receipts"]
            self.assertEqual((alias["host_id"], alias["observed_at_utc"], alias["grandfathered"]),
                             ("test-host-20260922", "2026-09-22T01:00:00Z", False))
            markdown = cm.render_markdown(document)
            self.assertIn("Listed: 1 alias receipt(s) from host(s) `test-host-20260922`, observed 2026-09-22; "
                          "0 of 1 grandfathered.", markdown)
            self.assertNotIn("two Mac receipts", markdown)
            # Grandfathering that exact recorded claim (path and claim_sha256) is reflected in the entry and the prose.
            entry = {"canonical_component_id": "widget-winner", "date": "2026-09-22", "reason": "test",
                     "claim_sha256": hr.receipt_claim_sha256(
                         json.loads((root / alias["path"]).read_text(encoding="utf-8")))}
            with mock.patch.object(hr, "GRANDFATHERED_ALIAS_RECEIPTS", {alias["path"]: entry}):
                document, _flip = cm.build_document(root)
            [alias] = document["rows"][0]["winners"][0]["platforms"]["macos-arm64"]["alias_receipts"]
            self.assertIs(alias["grandfathered"], True)
            markdown = cm.render_markdown(document)
            self.assertIn("1 of 1 grandfathered.", markdown)
            self.assertIn("the pin in full; grandfathered)", markdown)

    def test_alias_summary_sentence_counts_hosts_and_dates(self):
        self.assertEqual(cm.alias_summary_sentence([]), "")
        sentence = cm.alias_summary_sentence([
            {"host_id": "b-20260102", "observed_at_utc": "2026-01-02T00:00:00Z", "grandfathered": True},
            {"host_id": "a-20260101", "observed_at_utc": "2026-01-01T00:00:00Z", "grandfathered": False},
            {"host_id": "a-20260101", "observed_at_utc": "2026-01-01T05:00:00Z"}])
        self.assertEqual(sentence, " Listed: 3 alias receipt(s) from host(s) `a-20260101`, `b-20260102`, "
                                   "observed 2026-01-01, 2026-01-02; 1 of 3 grandfathered.")

    def test_alias_summary_counts_a_multi_layer_winner_receipt_once(self):
        # The same winner selected in two layers lists its alias receipt under both rows,
        # but the summary sentence counts that receipt (and its grandfathering) once.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layers = [_layer(layer_id, winners=[_winner(component_id="widget-winner", macos="untested")])
                      for layer_id in ("layer-a", "layer-b")]
            _init_root(root, layers)
            _write_json(root / "manifests" / "stack.json", {"schema_version": 1, "components": [
                {"id": "widget", "repository": "https://github.com/Example/widget.git", "version": "1.0.0"}]})
            _write_receipt(root, _receipt("widget", "macos-arm64"))
            document, _flip = cm.build_document(root)
            paths = [alias["path"] for row in document["rows"] for winner in row["winners"]
                     for alias in winner["platforms"]["macos-arm64"]["alias_receipts"]]
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(set(paths)), 1)
            entry = {"canonical_component_id": "widget-winner", "date": "2026-09-22", "reason": "test",
                     "claim_sha256": hr.receipt_claim_sha256(json.loads((root / paths[0]).read_text(encoding="utf-8")))}
            with mock.patch.object(hr, "GRANDFATHERED_ALIAS_RECEIPTS", {paths[0]: entry}):
                document, _flip = cm.build_document(root)
            markdown = cm.render_markdown(document)
            self.assertIn("Listed: 1 alias receipt(s) from host(s) `test-host-20260922`, observed 2026-09-22; "
                          "1 of 1 grandfathered.", markdown)
            # The per-row listing keeps one line per row.
            self.assertEqual(markdown.count(paths[0]), 2)

    def test_repository_crosswalk_uses_the_shared_normalization(self):
        mapping = cm.repository_to_component_id({"components": [
            {"id": "widget", "repository": "https://github.com/Example/widget.git/"},
            # manifests/stack.json records some repositories as release URLs (rtk, shellcheck, difftastic)
            {"id": "gadget", "repository": "https://github.com/example/gadget/releases/tag/v1.0.0"}]})
        self.assertEqual(mapping, {"github.com/example/widget": "widget", "github.com/example/gadget": "gadget"})
        summary = {"components": {"widget": {"platforms": {"macos-arm64": {}}},
                                  "gadget": {"platforms": {"linux-wsl2-x86_64": {}}}}}
        for repository in ("https://github.com/example/widget", "https://github.com/example/gadget"):
            with self.subTest(repository=repository):
                built = cm.build_alternative({"repository": repository}, mapping, summary)
                self.assertEqual(built["e2e_state"], "receipts_recorded")


# ------------------------------------------------------------------------------ convergence by layer


def _manifest_row(component_id, *, repository=None, compared=True, behind=False, decision=None) -> dict:
    """A catalogs/sota-convergence/manifest-YYYYMMDD.json component (foundation) or entry (trading) row."""
    row = {"id": component_id, "repository": repository or f"https://github.com/example/{component_id}",
           "pin": "1.0.0", "pin_comparison": "compared" if compared else "not_compared",
           "pin_behind_upstream": behind if compared else None}
    if decision is not None:
        row["decision"] = decision
    return row


def _sweep_manifest(checked_at, *, foundation=None, trading=None) -> dict:
    return {"schema_version": 1, "id": "sota-convergence-" + checked_at.replace("-", ""), "checked_at": checked_at,
            "foundation": [{"layer": layer_id, "components": rows} for layer_id, rows in (foundation or {}).items()],
            "trading": [{"layer": layer_id, "entries": rows} for layer_id, rows in (trading or {}).items()]}


def _sweep(sweep_id, day, layers, *, status="completed") -> dict:
    """A catalogs/saturation/ledger.json sweep record, reduced to the fields the metric reads."""
    return {"sweep_id": sweep_id, "date": day, "status": status,
            "manifest_ref": "catalogs/sota-convergence/manifest-" + day.replace("-", "") + ".json",
            "layers": [{"catalog": catalog, "layer_id": layer_id} for catalog, layer_id in layers]}


EVERY_FIXTURE_LAYER = ([("foundation", layer_id) for layer_id in
                        ("f-current", "f-reopened", "f-none", "f-empty", "f-pending")]
                       + [("us-equities", layer_id) for layer_id in ("u-engines", "u-pending")])


def _convergence_root(root: Path) -> None:
    """Seven layers covering every layer_state, every factor value and every unresolved reason.

    foundation/f-current is recorded on 2026-09-26: a completed sweep the same day, a later completed sweep
    that covers another layer and a later stopped sweep all leave it confirmed_current. foundation/f-reopened
    (recorded 2026-09-22) is reopened by the completed sweeps of 2026-09-26 and 2026-09-27. f-none is a
    no_selection verdict, f-empty a recorded verdict without winners, f-pending and u-pending are
    pending_lanes, and us-equities/u-engines is recorded on 2026-09-26."""
    _init_root(root, [
        _layer("f-current", checked_at="2026-09-26", winners=[
            _winner("widget"), _winner("gadget", linux="untested"), _winner("relay", linux="untested")]),
        _layer("f-reopened", winners=[_winner("widget")]),
        _layer("f-none", verdict_status="no_selection"),
        _layer("f-empty"),
        _layer("f-pending", verdict_status="pending_lanes", agreement="disagree"),
    ])
    _write_json(root / "catalogs" / "landscape" / "us-equities.json", {
        "schema_version": 2, "checked_at": "2026-09-22", "scope": "test fixture", "layers": [
            _layer("u-engines", catalog="us-equities", checked_at="2026-09-26", winners=[
                _winner("nautilus-trader", repository="https://github.com/example/nautilus"),
                _winner("engine-x", repository="https://github.com/example/engine-x", linux="conditional"),
                _winner("data-tracker", repository="https://github.com/example/tracker")]),
            _layer("u-pending", catalog="us-equities", verdict_status="pending_lanes", agreement="disagree"),
        ]})
    _write_json(root / cm.STACK_FILE, {"schema_version": 1, "components": [
        {"id": component_id, "repository": "https://github.com/example/" + repository, "version": "1.0.0"}
        for component_id, repository in (("widget", "widget"), ("gadget", "gadget"), ("relay", "relay"),
                                         ("helper", "helper"), ("gizmo", "gizmo"), ("tool", "tool"),
                                         ("twin-a", "twin"), ("twin-b", "twin"), ("cli", "cli"))]})
    _write_json(root / "tools" / "sota-convergence" / "receipt-component-aliases.json", {"schema_version": 1, "aliases": {
        "gizmo": "data-gizmo", "nautilus-trader": "nautilustrader"}})
    # relay declares linux untested; its reviewed linux use receipt makes the matrix entry host_verified.
    _write_receipt(root, _receipt("relay", "linux-wsl2-x86_64"))
    manifests = root / "catalogs" / "sota-convergence"
    _write_json(manifests / "manifest-20260927.json", _sweep_manifest("2026-09-27", foundation={
        "f-current": [
            _manifest_row("widget"), _manifest_row("relay"), _manifest_row("gadget", behind=True),
            _manifest_row("helper", compared=False),
            _manifest_row("data-gizmo", repository="https://github.com/example/gizmo"),
            _manifest_row("forked-tool", repository="https://github.com/example/tool"),
            _manifest_row("twin", repository="https://github.com/example/twin"),
            _manifest_row("stranger")],
        "f-reopened": [
            _manifest_row("widget"),
            _manifest_row("cli-core", repository="https://github.com/example/cli"),
            _manifest_row("cli-plugin", repository="https://github.com/example/cli")],
        "f-none": [_manifest_row("helper")],
        "f-pending": [_manifest_row("widget")],
    }, trading={
        "u-engines": [
            _manifest_row("nautilustrader", repository="https://github.com/example/nautilus", decision="default"),
            _manifest_row("data-engine-x", repository="https://github.com/example/engine-x", decision="default"),
            _manifest_row("data-tracker", repository="https://github.com/example/tracker", decision="conditional"),
            _manifest_row("tracker", repository="https://github.com/example/tracker", compared=False,
                          decision="default"),
            _manifest_row("extra", behind=True, decision="default"),
            _manifest_row("maybe", decision="conditional"),
            _manifest_row("mystery")],
        "u-pending": [
            _manifest_row("alpaca-a", repository="https://github.com/example/alpaca", decision="default"),
            _manifest_row("alpaca-b", repository="https://github.com/example/alpaca", decision="default")],
    }))
    # Older by checked_at (one of them under the latest file name) and a file outside the manifest-YYYYMMDD
    # pattern: none of them may be read.
    stale = _sweep_manifest("2026-09-20", foundation={"f-current": [_manifest_row("widget", behind=True)]})
    _write_json(manifests / "manifest-20260920.json", stale)
    _write_json(manifests / "manifest-20261001.json", {**stale, "id": "misdated", "checked_at": "2026-09-19"})
    _write_json(manifests / "layer-verdicts-20261231.json", {**stale, "id": "not-a-manifest", "checked_at": "2026-12-31"})
    _write_json(root / "catalogs" / "saturation" / "ledger.json", {"schema_version": 1, "sweeps": [
        _sweep("sweep-0926", "2026-09-26", EVERY_FIXTURE_LAYER),
        _sweep("sweep-0927", "2026-09-27", [("foundation", "f-reopened")]),
        _sweep("sweep-0928-stopped", "2026-09-28", EVERY_FIXTURE_LAYER, status="stopped")]})


class ConvergenceByLayerTests(unittest.TestCase):
    """The convergence-by-layer metric frozen on 2026-09-27: layer_state, the in-use denominator, the three
    true/false/unknown factors, the comparability columns, the unresolved list and the summary."""

    def _document(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        _convergence_root(root)
        document, flip_violations = cm.build_document(root)
        self.assertEqual(flip_violations, [])
        return root, document

    @staticmethod
    def _rows(document):
        return {(row["catalog"], row["layer_id"]): row["convergence"] for row in document["rows"]}

    @staticmethod
    def _factors(convergence):
        return {name: (counts["true"], counts["false"], counts["unknown"])
                for name, counts in convergence["factors"].items()}

    @staticmethod
    def _counts(convergence):
        return tuple(convergence[key] for key in ("in_use", "converged", "all_rows", "recorded_winner_rows"))

    def test_every_layer_state(self):
        _root, document = self._document()
        rows = self._rows(document)
        self.assertEqual({key: value["layer_state"] for key, value in rows.items()}, {
            # A same-day completed sweep is not "after"; the later completed sweep covers another layer; the
            # later sweep that does cover it stopped.
            ("foundation", "f-current"): "confirmed_current",
            ("foundation", "f-empty"): "no_selection",       # recorded, no winners
            ("foundation", "f-none"): "no_selection",        # verdict_status no_selection
            ("foundation", "f-pending"): "pending_lanes",
            ("foundation", "f-reopened"): "recorded_reopened",
            ("us-equities", "u-engines"): "confirmed_current",
            ("us-equities", "u-pending"): "pending_lanes",
        })
        self.assertEqual(rows[("foundation", "f-reopened")]["reopened_by"], [
            {"sweep_id": "sweep-0926", "date": "2026-09-26"}, {"sweep_id": "sweep-0927", "date": "2026-09-27"}])
        self.assertEqual(rows[("foundation", "f-current")]["reopened_by"], [])
        self.assertEqual(rows[("foundation", "f-current")]["verdict_checked_at"], "2026-09-26")
        self.assertEqual(document["summary"]["convergence"]["layer_states"], {
            "confirmed_current": 2, "no_selection": 2, "pending_lanes": 2, "recorded_reopened": 1})

    def test_foundation_factors_counts_and_unresolved_rows(self):
        _root, document = self._document()
        current = self._rows(document)[("foundation", "f-current")]
        self.assertEqual(self._counts(current), (6, 2, 8, 3))
        self.assertEqual(self._factors(current), {
            "verdict_winner": (3, 3, 0), "pin_current": (4, 1, 1), "host_e2e": (2, 1, 3)})
        self.assertEqual(current["unresolved"], [
            {"id": "stranger", "repository": "https://github.com/example/stranger",
             "reason": "no manifests/stack.json id, alias or repository match"},
            {"id": "twin", "repository": "https://github.com/example/twin",
             "reason": "ambiguous repository: manifests/stack.json ids twin-a, twin-b"}])
        components = {component["id"]: component for component in current["components"]}
        self.assertEqual([component["id"] for component in current["components"]],
                         ["data-gizmo", "forked-tool", "gadget", "helper", "relay", "widget"])
        self.assertEqual({key: (value["resolved_by"], value["adopted_as"]) for key, value in components.items()}, {
            "data-gizmo": ("alias", "gizmo"), "forked-tool": ("repository", "tool"), "gadget": ("id", "gadget"),
            "helper": ("id", "helper"), "relay": ("id", "relay"), "widget": ("id", "widget")})
        self.assertEqual({key: (value["verdict_winner"], value["pin_current"], value["host_e2e"], value["converged"])
                          for key, value in components.items()}, {
            "widget": ("true", "true", "true", True),           # declared linux accepted
            "relay": ("true", "true", "true", True),            # host_verified by its reviewed use receipt
            "gadget": ("true", "false", "false", False),        # behind upstream; linux untested
            "helper": ("false", "unknown", "unknown", False),   # not compared; no winner entry in this layer
            "data-gizmo": ("false", "true", "unknown", False),
            "forked-tool": ("false", "true", "unknown", False)})
        reopened = self._rows(document)[("foundation", "f-reopened")]
        # Every factor is true, but completed sweeps dated after the verdict reopened it.
        self.assertEqual(self._counts(reopened), (1, 0, 3, 1))
        self.assertEqual(self._factors(reopened), {
            "verdict_winner": (1, 0, 0), "pin_current": (1, 0, 0), "host_e2e": (1, 0, 0)})
        self.assertIs(reopened["components"][0]["converged"], False)
        # One stack id uses the repository, but so do two sweep-manifest ids (tools/sota-convergence/
        # lane_packets.py receipts_for): a repository match cannot tell them apart.
        self.assertEqual([(row["id"], row["reason"]) for row in reopened["unresolved"]], [
            ("cli-core", "ambiguous repository: manifests/stack.json ids cli; also sweep-manifest ids cli-plugin"),
            ("cli-plugin", "ambiguous repository: manifests/stack.json ids cli; also sweep-manifest ids cli-core")])

    def test_no_selection_and_pending_layers(self):
        rows = self._rows(self._document()[1])
        none, empty, pending = (rows[("foundation", layer_id)] for layer_id in ("f-none", "f-empty", "f-pending"))
        self.assertEqual(self._counts(none), (1, 0, 1, 0))
        self.assertEqual(self._factors(none), {
            "verdict_winner": (0, 1, 0), "pin_current": (1, 0, 0), "host_e2e": (0, 0, 1)})
        self.assertEqual(self._counts(empty), (0, 0, 0, 0))
        self.assertEqual(empty["unresolved"], [])
        self.assertEqual(self._factors(empty), {name: (0, 0, 0) for name in ("verdict_winner", "pin_current", "host_e2e")})
        # No recorded verdict exists yet: whether the component wins is unknown, not false.
        self.assertEqual(self._counts(pending), (1, 0, 1, 0))
        self.assertEqual(self._factors(pending), {
            "verdict_winner": (0, 0, 1), "pin_current": (1, 0, 0), "host_e2e": (0, 0, 1)})
        us_pending = rows[("us-equities", "u-pending")]
        self.assertEqual(self._counts(us_pending), (2, 0, 2, 0))
        self.assertEqual(self._factors(us_pending), {
            "verdict_winner": (0, 0, 2), "pin_current": (2, 0, 0), "host_e2e": (0, 0, 2)})

    def test_us_equities_in_use_is_the_default_decision_and_winners_match_by_id_alias_or_repository(self):
        engines = self._rows(self._document()[1])[("us-equities", "u-engines")]
        self.assertEqual(self._counts(engines), (4, 1, 7, 4))
        self.assertEqual(self._factors(engines), {
            "verdict_winner": (3, 1, 0), "pin_current": (2, 1, 1), "host_e2e": (2, 1, 1)})
        self.assertEqual({component["id"]: (component["resolved_by"], component["adopted_as"],
                                            component["winner_match"], component["winner_ids"],
                                            component["verdict_winner"], component["pin_current"],
                                            component["host_e2e"], component["converged"])
                          for component in engines["components"]}, {
            "nautilustrader": ("decision", None, "alias", ["nautilus-trader"], "true", "true", "true", True),
            "data-engine-x": ("decision", None, "repository", ["engine-x"], "true", "true", "false", False),
            "tracker": ("decision", None, "repository", ["data-tracker"], "true", "unknown", "true", False),
            "extra": ("decision", None, None, [], "false", "false", "unknown", False)})
        # The comparability column counts winner rows whether or not they are in use (data-tracker is
        # conditional) and whether or not a later sweep reopened the verdict.
        self.assertEqual(engines["winner_rows"], [
            {"id": "data-engine-x", "matched_by": "repository", "winner_ids": ["engine-x"]},
            {"id": "data-tracker", "matched_by": "id", "winner_ids": ["data-tracker"]},
            {"id": "nautilustrader", "matched_by": "alias", "winner_ids": ["nautilus-trader"]},
            {"id": "tracker", "matched_by": "repository", "winner_ids": ["data-tracker"]}])
        self.assertEqual(engines["unresolved"], [{"id": "mystery", "repository": "https://github.com/example/mystery",
                                                  "reason": "no default or conditional decision"}])

    def test_summary_totals_newest_manifest_verdict_dates_and_invoke(self):
        _root, document = self._document()
        block = document["summary"]["convergence"]
        self.assertEqual(block["newest_manifest"], {"path": "catalogs/sota-convergence/manifest-20260927.json",
                                                    "id": "sota-convergence-20260927", "checked_at": "2026-09-27"})
        self.assertEqual(block["newest_verdict_checked_at"], {"foundation": "2026-09-26", "us-equities": "2026-09-26"})
        self.assertEqual(block["catalogs"], {
            "foundation": {"layers": 5, "in_use": 9, "converged": 2, "share": 0.2222, "unresolved": 4},
            "us-equities": {"layers": 2, "in_use": 6, "converged": 1, "share": 0.1667, "unresolved": 1}})
        self.assertEqual(block["overall"], {"layers": 7, "in_use": 15, "converged": 3, "share": 0.2, "unresolved": 5})
        self.assertEqual(block["sources"]["completed_sweeps"], [
            {"sweep_id": "sweep-0926", "date": "2026-09-26", "layers": 7,
             "manifest_ref": "catalogs/sota-convergence/manifest-20260926.json"},
            {"sweep_id": "sweep-0927", "date": "2026-09-27", "layers": 1,
             "manifest_ref": "catalogs/sota-convergence/manifest-20260927.json"}])
        self.assertEqual(block["sources"]["host_e2e_platform"], "linux-wsl2-x86_64")
        self.assertEqual(block["frozen_at"], "2026-09-27")
        self.assertEqual([item["term"] for item in block["definitions"]], [
            "layer_state", "in_use", "verdict_winner", "pin_current", "host_e2e", "converged",
            "all_rows", "recorded_winner_rows", "unresolved", "invoke"])
        for row in document["rows"]:
            with self.subTest(layer=row["layer_id"]):
                self.assertIsNone(row["convergence"]["invoke"])
                self.assertEqual(row["convergence"]["invoke_reason"], "no post-fix invoke receipt yet")
                for counts in row["convergence"]["factors"].values():
                    self.assertEqual(sum(counts.values()), row["convergence"]["in_use"])

    def test_absent_inputs_give_an_empty_denominator_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner()]),
                              _layer("layer-b", verdict_status="pending_lanes", agreement="disagree")])
            document, _flip = cm.build_document(root)
            rows = self._rows(document)
            self.assertEqual(rows[("foundation", "layer-a")]["layer_state"], "confirmed_current")
            self.assertEqual(self._counts(rows[("foundation", "layer-a")]), (0, 0, 0, 0))
            block = document["summary"]["convergence"]
            self.assertIsNone(block["newest_manifest"])
            self.assertEqual(block["sources"]["completed_sweeps"], [])
            self.assertEqual(block["overall"], {"layers": 2, "in_use": 0, "converged": 0, "share": None, "unresolved": 0})
            self.assertEqual(block["catalogs"]["us-equities"],
                             {"layers": 0, "in_use": 0, "converged": 0, "share": None, "unresolved": 0})
            self.assertEqual(block["newest_verdict_checked_at"], {"foundation": "2026-09-22", "us-equities": None})
            self.assertIn("## Convergence by layer", cm.render_markdown(document))

    def test_an_undated_verdict_is_never_confirmed_current_under_a_covering_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_root(root, [_layer(winners=[_winner()], checked_at=None),
                              _layer("layer-b", winners=[_winner()], checked_at=None)])
            _write_json(root / "catalogs" / "saturation" / "ledger.json", {"schema_version": 1, "sweeps": [
                _sweep("sweep-a", "2026-09-23", [("foundation", "layer-a")])]})
            rows = self._rows(cm.build_document(root)[0])
            self.assertEqual((rows[("foundation", "layer-a")]["layer_state"],
                              rows[("foundation", "layer-a")]["verdict_checked_at"]), ("recorded_reopened", None))
            self.assertEqual(rows[("foundation", "layer-b")]["layer_state"], "confirmed_current")

    def test_markdown_renders_the_convergence_table_from_the_json(self):
        _root, document = self._document()
        markdown = cm.render_markdown(document)
        self.assertLess(markdown.index("## Needs independent review"), markdown.index("## Convergence by layer"))
        section = markdown.split("## Convergence by layer", 1)[1].split("## How to update this page", 1)[0]
        for expected in (
            "| `foundation/f-current` | confirmed_current | 2026-09-26 | - | 6 | 2 | 3/3/0 | 4/1/1 | 2/1/3 | 8 | 3 "
            "| `stranger`, `twin` | null |",
            "| `foundation/f-reopened` | recorded_reopened | 2026-09-22 | `sweep-0926`, `sweep-0927` | 1 | 0 | 1/0/0 "
            "| 1/0/0 | 1/0/0 | 3 | 1 | `cli-core`, `cli-plugin` | null |",
            "| `us-equities/u-pending` | pending_lanes | 2026-09-22 | - | 2 | 0 | 0/0/2 | 2/0/0 | 0/0/2 | 2 | 0 | - "
            "| null |",
            "| foundation | 5 | 2 / 9 | 0.2222 | 4 |",
            "| us-equities | 2 | 1 / 6 | 0.1667 | 1 |",
            "| overall | 7 | 3 / 15 | 0.2 | 5 |",
            "Layer states: confirmed_current 2, no_selection 2, pending_lanes 2, recorded_reopened 1.",
            "`catalogs/sota-convergence/manifest-20260927.json` (`sota-convergence-20260927`, checked_at 2026-09-27)",
            "`sweep-0926` (2026-09-26), `sweep-0927` (2026-09-27)",
            "- `us-equities/u-engines` `mystery`: no default or conditional decision",
            "- `foundation/f-current` `twin`: ambiguous repository: manifests/stack.json ids twin-a, twin-b",
        ):
            self.assertIn(expected, section)
        for item in document["summary"]["convergence"]["definitions"]:
            self.assertIn(f"- **{item['term']}**: {item['definition']}", section)

    def test_check_detects_a_later_completed_sweep_and_write_is_deterministic(self):
        root, _document = self._document()
        for mode in ("--write", "--check"):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(cm.main(["--root", str(root), mode]), 0, buffer.getvalue())
        written = (root / cm.OUTPUT_JSON).read_bytes()
        self.assertEqual(cm.serialize(cm.build_document(root)[0]).encode("utf-8"), written)
        ledger_path = root / "catalogs" / "saturation" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["sweeps"].append(_sweep("sweep-0929", "2026-09-29", [("foundation", "f-current")]))
        _write_json(ledger_path, ledger)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cm.main(["--root", str(root), "--check"]), 1)
        self.assertIn("JSON differs from the generated output", buffer.getvalue())
        current = self._rows(cm.build_document(root)[0])[("foundation", "f-current")]
        self.assertEqual((current["layer_state"], current["converged"]), ("recorded_reopened", 0))


if __name__ == "__main__":
    unittest.main()
