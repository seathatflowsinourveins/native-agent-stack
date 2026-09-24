"""Tests for scripts/platform_status.py: the one rule landscape.py, component_matrix.py and
record_verdicts.py use to derive a winner's per-platform status from host receipts. Each
test builds receipts in a temporary root and derives the summary with the real
host_receipts.build_summary, so the rule is exercised end to end."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import host_receipts as hr
from scripts import platform_status as ps

REPO_ROOT = Path(__file__).resolve().parents[1]
MAC_PROFILE = {"id": "macos-arm64", "os": "macos", "architecture": "arm64", "status": "drafted_not_accepted"}
LINUX_PROFILE = {"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64", "status": "accepted"}


def _winner(*, pin="1.0.0", evidence_class="native_proven", evidence_refs=()):
    return {"component_id": "widget", "pin": pin, "evidence_class": evidence_class,
            "evidence_refs": list(evidence_refs)}


class _Root:
    def __init__(self, root: Path):
        self.root = root
        (root / "adoption").mkdir(parents=True)
        (root / "adoption" / "host-receipt.schema.json").write_text(
            (REPO_ROOT / "adoption" / "host-receipt.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
        (root / "adoption" / "manifest.json").write_text(
            json.dumps({"platform_profiles": [MAC_PROFILE, LINUX_PROFILE]}), encoding="utf-8")
        (root / "manifests").mkdir()
        self.registered: list[dict] = []
        self._write_evidence()
        self.count = 0

    def _write_evidence(self):
        (self.root / "manifests" / "evidence.json").write_text(
            json.dumps({"schema_version": 1, "files": self.registered}), encoding="utf-8")

    def register(self, path: str):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
        self.registered.append({"path": path, "sha256": "0" * 64, "bytes": 2})
        self._write_evidence()

    def receipt(self, platform_id="macos-arm64", *, result="pass", stage="use", evidence_class="native_proven",
                version="1.0.0", second_machine=True, reviewer="other-session", verdict="agree",
                observed_at="2026-09-23T01:00:00Z", os_value=None, architecture=None, host=None):
        self.count += 1
        mac = platform_id == "macos-arm64"
        host_id = f"{host or 'host' + str(self.count)}-20260923"
        recorder = {"identity_sha256": hr.identity_digest(f"recorder-{self.count}")}
        reviews = [{"kind": "self", "ref": "record", "verdict": "agree", "at_utc": observed_at, "reviewer": recorder}]
        if reviewer is not None:
            reviews.append({"kind": "independent_session", "ref": "review", "verdict": verdict,
                            "at_utc": observed_at, "reviewer": {"identity_sha256": hr.identity_digest(reviewer)}})
        receipt_id = f"{host_id}--widget--{stage}--20260923"
        if (self.root / "evidence" / "hosts" / host_id / f"{receipt_id}.json").exists():
            receipt_id = f"{host_id}--widget--{stage}--20260924"
            observed_at = "2026-09-24" + observed_at[10:]
            for review in reviews:
                review["at_utc"] = observed_at
        receipt = {
            "schema_version": 1, "id": receipt_id, "kind": "host_acceptance",
            "host": {"host_id": host_id, "platform_id": platform_id,
                     "os": os_value or ("macos" if mac else "linux"),
                     "architecture": architecture or ("arm64" if mac else "x86_64"),
                     "second_physical_machine": second_machine},
            "catalog_revision": "0" * 40, "recorded_by": recorder, "component_id": "widget", "stage": stage,
            "commands": [{"cmd": "widget --version", "exit": 0 if result == "pass" else 1, "duration_s": 0.1,
                          "output_sha256": "0" * 64, "output_excerpt": "widget"}],
            "tool_versions": {"widget": version}, "observed_at_utc": observed_at, "result": result,
            "claim": "test", "limitations": ["test"], "evidence_class": evidence_class, "reviews": reviews,
        }
        path = self.root / "evidence" / "hosts" / host_id / f"{receipt_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path.relative_to(self.root).as_posix()

    def status(self, platform_id="macos-arm64", **winner):
        return ps.platform_status(platform_id, _winner(**winner), ps.load_context(self.root))


class PlatformStatusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = _Root(Path(tmp.name))

    # ---------------------------------------------------------------- macOS
    def test_macos_untested_without_receipts(self):
        self.assertEqual(self.r.status().status, "untested")

    def test_macos_accepted_with_a_qualifying_pass(self):
        path = self.r.receipt()
        derived = self.r.status()
        self.assertEqual((derived.status, derived.receipt_refs), ("accepted", (path,)))

    def test_macos_conditional_without_independent_review(self):
        self.r.receipt(reviewer=None)
        self.assertEqual(self.r.status().status, "conditional")

    def test_same_identity_review_is_not_independent(self):
        self.r.receipt(reviewer="recorder-1")
        self.assertEqual(self.r.status().status, "conditional")

    def test_macos_not_accepted_without_second_machine_or_on_wrong_stage_or_class(self):
        self.r.receipt(second_machine=False)
        self.r.receipt(stage="restart")
        self.r.receipt(evidence_class="local_integration")
        self.assertEqual(self.r.status().status, "conditional")

    def test_platform_identity_mismatch_does_not_bind(self):
        self.r.receipt(os_value="linux", architecture="x86_64")
        self.assertEqual(self.r.status().status, "untested")

    def test_old_pin_receipts_are_retired(self):
        self.r.receipt(version="0.9.0")
        self.assertEqual(self.r.status().status, "untested")
        self.assertEqual(self.r.status(pin="0.9.0").status, "accepted")

    def test_pin_normalization_binds_v_prefix_and_sha_prefix(self):
        self.r.receipt(version="v1.0.0")
        self.assertEqual(self.r.status(pin="1.0.0").status, "accepted")
        full_sha = "985ef30ad3ac774218c5ac516b4cb0aa2655730f"
        self.assertTrue(ps.pin_matches("985ef30", full_sha))
        self.assertFalse(ps.pin_matches("985ef", full_sha))
        self.assertFalse(ps.pin_matches("985ef30 with documented remediation", full_sha))
        self.assertFalse(ps.pin_matches("unpinned", "unpinned"))
        self.assertFalse(ps.pin_matches(None, "1.0.0"))
        self.assertFalse(ps.pin_matches("1.2", "1.2.9"))
        # Re-review: an all-digit date is not a commit abbreviation of a longer number.
        self.assertFalse(ps.pin_matches("2026092", "20260921"))
        self.assertFalse(ps.pin_matches("985ef30", "985ef30ad3ac"))

    def test_multi_part_pins_must_match_in_full(self):
        # Review of #117 finding 2: only the first token used to be compared, so any
        # "CLI ..." version matched this us-equities pin.
        pin = "CLI rust-v0.155.1; Python openai-codex 0.154.0"
        self.assertFalse(ps.pin_matches("CLI rust-v0.999.0", pin))
        self.assertFalse(ps.pin_matches("cli", pin))
        self.assertTrue(ps.pin_matches("cli  rust-v0.155.1;  python openai-codex v0.154.0", pin))
        self.assertTrue(ps.pin_matches("1.2.9; WalkForward source c99fcf7", "1.2.9; walkforward source c99fcf7"))

    def test_standing_dissent_vetoes_acceptance_and_conditional(self):
        self.r.receipt(verdict="needs_changes")
        self.assertEqual(self.r.status().status, "not_established")

    def test_a_later_qualifying_fail_supersedes_a_pass(self):
        self.r.receipt(observed_at="2026-09-23T01:00:00Z")
        self.r.receipt(result="fail", observed_at="2026-09-23T02:00:00Z")
        derived = self.r.status()
        self.assertEqual(derived.status, "conditional")
        self.assertIn("failed", derived.reason)

    def test_a_later_pass_on_the_failing_host_restores_acceptance(self):
        self.r.receipt(result="fail", host="mac-a", observed_at="2026-09-23T01:00:00Z")
        self.r.receipt(host="mac-b", observed_at="2026-09-23T02:00:00Z")
        self.assertEqual(self.r.status().status, "conditional")  # mac-a's latest is still a fail
        self.r.receipt(host="mac-a", observed_at="2026-09-23T03:00:00Z")
        self.assertEqual(self.r.status().status, "accepted")

    def test_an_unreviewed_native_fail_blocks_acceptance(self):
        # Review of #117 finding 5: a fail supersedes whatever its review state.
        self.r.receipt(host="mac-a", observed_at="2026-09-23T01:00:00Z")
        self.r.receipt(result="fail", host="mac-a", reviewer=None, observed_at="2026-09-23T02:00:00Z")
        self.assertEqual(self.r.status().status, "conditional")

    def test_a_later_partial_or_not_runnable_does_not_clear_a_fail(self):
        self.r.receipt(host="mac-b", observed_at="2026-09-23T00:30:00Z")
        self.r.receipt(result="fail", host="mac-a", observed_at="2026-09-23T01:00:00Z")
        self.r.receipt(result="not_runnable", host="mac-a", observed_at="2026-09-23T02:00:00Z")
        self.assertEqual(self.r.status().status, "conditional")

    def test_a_reviewed_install_pass_alone_is_conditional_on_either_platform(self):
        # 2026-09-24 decision: a version-only install receipt proves the binary resolves, not that the component
        # works; accepted needs a reviewed use-stage pass.
        # On Linux a source_review winner reaches the receipt route (a native winner has its own routes).
        for platform_id, winner in (("macos-arm64", {}), ("linux-wsl2-x86_64", {"evidence_class": "source_review"})):
            with self.subTest(platform_id):
                self.setUp()
                self.r.receipt(platform_id, stage="install", host="box-a")
                derived = self.r.status(platform_id, **winner)
                self.assertEqual(derived.status, "conditional")
                self.assertIn("use-stage pass", derived.reason)
                self.r.receipt(platform_id, stage="use", host="box-b")
                self.assertEqual(self.r.status(platform_id, **winner).status, "accepted")

    def test_a_reviewed_install_pass_never_lowers_a_winner_accepted_by_registered_evidence(self):
        # Review of #164: the install-only cap ran ahead of the Linux winner-level route and demoted it, for both
        # native classes (Codex cross-family lane).
        for evidence_class in ("native_proven", "measured_comparison"):
            with self.subTest(evidence_class):
                self.setUp()
                self.r.register("evidence/receipts/widget.json")
                winner = {"evidence_refs": ["evidence/receipts/widget.json"], "evidence_class": evidence_class}
                self.assertEqual(self.r.status("linux-wsl2-x86_64", **winner).status, "accepted")
                self.r.receipt("linux-wsl2-x86_64", stage="install", host="box-a")
                self.assertEqual(self.r.status("linux-wsl2-x86_64", **winner).status, "accepted")

    def test_a_use_fail_is_not_hidden_by_a_later_install_pass(self):
        self.r.receipt(result="fail", stage="use", host="mac-a", observed_at="2026-09-23T01:00:00Z")
        self.r.receipt(stage="install", host="mac-a", observed_at="2026-09-23T02:00:00Z")
        self.assertEqual(self.r.status().status, "conditional")

    def test_macos_conditional_needs_a_second_machine_and_a_non_synthetic_pass(self):
        # Review of #117 finding 6: a Linux box could record a synthetic macos-arm64 receipt.
        self.r.receipt(evidence_class="synthetic", reviewer=None)
        self.r.receipt(second_machine=False, reviewer=None)
        self.assertEqual(self.r.status().status, "not_established")

    def test_macos_not_established_when_only_failures(self):
        self.r.receipt(result="fail", reviewer=None)
        self.assertEqual(self.r.status().status, "not_established")

    # ---------------------------------------------------------------- Linux
    def test_linux_native_winner_with_registered_evidence_is_accepted(self):
        self.r.register("evidence/receipts/widget.json")
        derived = self.r.status("linux-wsl2-x86_64", evidence_refs=["evidence/receipts/widget.json", "docs/x.md"])
        self.assertEqual((derived.status, derived.receipt_refs), ("accepted", ("evidence/receipts/widget.json",)))

    def test_linux_native_winner_without_registered_evidence_is_conditional(self):
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_refs=["docs/x.md"]).status, "conditional")
        (self.r.root / "evidence" / "receipts").mkdir(parents=True)
        (self.r.root / "evidence" / "receipts" / "unregistered.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.r.status("linux-wsl2-x86_64",
                                       evidence_refs=["evidence/receipts/unregistered.json"]).status, "conditional")

    def test_linux_source_review_is_not_established_until_a_pin_bound_pass(self):
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_class="source_review").status,
                         "not_established")
        self.r.receipt("linux-wsl2-x86_64", reviewer=None, evidence_class="local_integration")
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_class="source_review").status, "conditional")

    def test_linux_qualifying_receipt_accepts_a_source_review_winner(self):
        self.r.receipt("linux-wsl2-x86_64")
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_class="source_review").status, "accepted")

    def test_linux_qualifying_fail_caps_a_lane_accepted_winner(self):
        self.r.register("evidence/receipts/widget.json")
        self.r.receipt("linux-wsl2-x86_64", result="fail")
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_refs=["evidence/receipts/widget.json"]).status,
                         "conditional")

    # ------------------------------------------------------ declared ceiling
    def test_declared_status_may_not_outrank_the_derived_one(self):
        context = ps.load_context(self.r.root)
        error = ps.declared_status_error("macos-arm64", "accepted", _winner(), context)
        self.assertIn("supports at most 'untested'", error)
        self.assertIsNone(ps.declared_status_error("macos-arm64", "untested", _winner(), context))
        self.assertIsNone(ps.declared_status_error("macos-arm64", "not_established", _winner(), context))
        self.assertIsNotNone(ps.declared_status_error("macos-arm64", "bogus", _winner(), context))

    def test_weaker_declared_status_is_allowed_after_new_evidence(self):
        self.r.receipt()
        context = ps.load_context(self.r.root)
        for declared in ("untested", "conditional", "accepted"):
            self.assertIsNone(ps.declared_status_error("macos-arm64", declared, _winner(), context))

    def test_linux_synthetic_receipt_does_not_raise_a_source_review_winner(self):
        self.r.receipt("linux-wsl2-x86_64", evidence_class="synthetic", reviewer=None)
        self.assertEqual(self.r.status("linux-wsl2-x86_64", evidence_class="source_review").status,
                         "not_established")

    def test_unknown_platform_is_an_error(self):
        with self.assertRaises(ValueError):
            self.r.status("windows-x86_64")


if __name__ == "__main__":
    unittest.main()


class RecorderHandoffContractTests(unittest.TestCase):
    """The interface agent-lab-17's record_verdicts.py imports (agreed 2026-09-23). If this
    changes, that recorder breaks: change both together."""

    def test_signature(self):
        self.assertEqual(list(inspect.signature(ps.platform_status).parameters), ["platform_id", "winner", "context"])
        self.assertEqual(list(inspect.signature(ps.load_context).parameters), ["root"])
        self.assertEqual(list(inspect.signature(ps.declared_status_error).parameters),
                         ["platform_id", "declared", "winner", "context"])
        self.assertEqual(ps.PlatformStatus._fields, ("status", "reason", "receipt_refs"))
        self.assertEqual(set(ps.STATUS_RANK), {"untested", "not_established", "conditional", "accepted"})

    def test_importable_the_way_record_verdicts_sets_up_its_path(self):
        # record_verdicts.py puts tools/sota-convergence and the repository root on sys.path.
        code = (
            "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; "
            "from scripts.platform_status import load_context, platform_status; "
            "import json; from pathlib import Path; root = Path(sys.argv[2]); "
            "winner = json.loads((root / 'catalogs/landscape/foundation.json').read_text())['layers'][0]['winners'][0]; "
            "print(platform_status('macos-arm64', winner, load_context(root)).status)"
        )
        result = subprocess.run([sys.executable, "-c", code, str(REPO_ROOT / "tools" / "sota-convergence"),
                                 str(REPO_ROOT)], capture_output=True, text=True, cwd=REPO_ROOT / "tools", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(result.stdout.strip(), ps.STATUS_RANK)
