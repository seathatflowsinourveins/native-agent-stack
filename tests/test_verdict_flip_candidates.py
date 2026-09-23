"""Tests for scripts/verdict_flip_candidates.py: a read-only, report-only join over
scripts/platform_status.py. Every test builds its own temporary fixture root; nothing here
reads or writes the real repository tree except the smoke test against the actual checked-in
catalogs."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import host_receipts as hr
from scripts import verdict_flip_candidates as vfc

REPO_ROOT = Path(__file__).resolve().parents[1]
MAC_PROFILE = {"id": "macos-arm64", "os": "macos", "architecture": "arm64", "status": "drafted_not_accepted"}
LINUX_PROFILE = {"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64", "status": "accepted"}


def _winner(component_id="widget", *, linux="untested", macos="untested",
            evidence_class="native_proven", pin="1.0.0", evidence_refs=()):
    return {
        "component_id": component_id, "pin": pin, "evidence_class": evidence_class,
        "evidence_refs": list(evidence_refs),
        "platform_status": {"linux-wsl2-x86_64": linux, "macos-arm64": macos},
    }


def _layer(layer_id="layer-a", winners=None):
    return {"layer_id": layer_id, "title": f"Title for {layer_id}", "winners": winners or []}


class _Root:
    """Minimal fixture tree: adoption/manifest.json platform_profiles, both landscape files
    and a place to register host receipts, mirroring tests/test_platform_status.py's helper."""

    def __init__(self, root: Path):
        self.root = root
        (root / "adoption").mkdir(parents=True)
        (root / "adoption" / "host-receipt.schema.json").write_text(
            (REPO_ROOT / "adoption" / "host-receipt.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
        (root / "adoption" / "manifest.json").write_text(
            json.dumps({"platform_profiles": [MAC_PROFILE, LINUX_PROFILE]}), encoding="utf-8")
        (root / "manifests").mkdir()
        (root / "catalogs" / "landscape").mkdir(parents=True)
        self.registered: list[dict] = []
        self._write_evidence()
        self.count = 0
        self.set_layers("foundation", [])
        self.set_layers("us-equities", [])

    def _write_evidence(self):
        (self.root / "manifests" / "evidence.json").write_text(
            json.dumps({"schema_version": 1, "files": self.registered}), encoding="utf-8")

    def set_layers(self, catalog: str, layers: list[dict]) -> None:
        (self.root / "catalogs" / "landscape" / f"{catalog}.json").write_text(
            json.dumps({"schema_version": 2, "layers": layers}), encoding="utf-8")

    def receipt(self, component_id="widget", platform_id="macos-arm64", *, result="pass", stage="use",
                evidence_class="native_proven", version="1.0.0", second_machine=True,
                reviewer="other-session", verdict="agree", observed_at="2026-09-23T01:00:00Z"):
        self.count += 1
        mac = platform_id == "macos-arm64"
        host_id = f"host{self.count}-20260923"
        recorder = {"identity_sha256": hr.identity_digest(f"recorder-{self.count}")}
        reviews = [{"kind": "self", "ref": "record", "verdict": "agree", "at_utc": observed_at, "reviewer": recorder}]
        if reviewer is not None:
            reviews.append({"kind": "independent_session", "ref": "review", "verdict": verdict,
                            "at_utc": observed_at, "reviewer": {"identity_sha256": hr.identity_digest(reviewer)}})
        receipt_id = f"{host_id}--{component_id}--{stage}--20260923"
        receipt = {
            "schema_version": 1, "id": receipt_id, "kind": "host_acceptance",
            "host": {"host_id": host_id, "platform_id": platform_id,
                     "os": "macos" if mac else "linux", "architecture": "arm64" if mac else "x86_64",
                     "second_physical_machine": second_machine},
            "catalog_revision": "0" * 40, "recorded_by": recorder, "component_id": component_id, "stage": stage,
            "commands": [{"cmd": f"{component_id} --version", "exit": 0 if result == "pass" else 1,
                          "duration_s": 0.1, "output_sha256": "0" * 64, "output_excerpt": component_id}],
            "tool_versions": {component_id: version}, "observed_at_utc": observed_at, "result": result,
            "claim": "test", "limitations": ["test"], "evidence_class": evidence_class, "reviews": reviews,
        }
        path = self.root / "evidence" / "hosts" / host_id / f"{receipt_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path.relative_to(self.root).as_posix()


class FindCandidatesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = _Root(Path(tmp.name))

    def test_no_candidates_on_empty_catalogs(self):
        self.assertEqual(vfc.find_candidates(self.r.root), [])

    def test_qualifying_macos_receipt_with_declared_untested_is_a_candidate(self):
        # native_proven evidence_class alone is enough for platform_status.py to derive at
        # least "conditional" on linux-wsl2-x86_64 with no receipts at all (see its
        # docstring); declare linux "conditional" already so only the macOS row is a
        # candidate here, and assert on that row rather than the raw candidate count.
        self.r.receipt(platform_id="macos-arm64")
        self.r.set_layers("foundation", [_layer(winners=[_winner(macos="untested", linux="conditional")])])
        candidates = vfc.find_candidates(self.r.root)
        self.assertEqual([c["platform"] for c in candidates], ["macos-arm64"])
        row = candidates[0]
        self.assertEqual(row["catalog"], "foundation")
        self.assertEqual(row["platform"], "macos-arm64")
        self.assertEqual(row["declared_status"], "untested")
        self.assertEqual(row["derived_status"], "accepted")
        self.assertTrue(row["qualifying_receipts"])

    def test_already_accepted_declaration_is_not_a_candidate(self):
        self.r.receipt(platform_id="macos-arm64")
        self.r.set_layers("foundation", [_layer(winners=[_winner(macos="accepted", linux="untested")])])
        candidates = vfc.find_candidates(self.r.root)
        self.assertFalse(any(c["platform"] == "macos-arm64" for c in candidates))

    def test_weaker_declared_status_than_derived_but_still_below_is_a_candidate(self):
        # conditional (non-synthetic pass, no full acceptance conditions) declared as untested.
        self.r.receipt(platform_id="macos-arm64", reviewer=None)
        self.r.set_layers("foundation", [_layer(winners=[_winner(macos="untested", linux="untested")])])
        candidates = vfc.find_candidates(self.r.root)
        row = next(c for c in candidates if c["platform"] == "macos-arm64")
        self.assertEqual(row["derived_status"], "conditional")

    def test_linux_platform_is_also_covered_not_only_macos(self):
        # linux-wsl2-x86_64 is not in landscape.ENFORCED_PLATFORMS, so the component_matrix
        # flip rule never gates it; this report must still surface it.
        winner = _winner(linux="untested", macos="untested",
                         evidence_class="native_proven", evidence_refs=["evidence/hosts/marker.json"])
        self.r.registered.append({"path": "evidence/hosts/marker.json", "sha256": "0" * 64, "bytes": 2})
        (self.r.root / "evidence" / "hosts").mkdir(parents=True, exist_ok=True)
        (self.r.root / "evidence" / "hosts" / "marker.json").write_text("{}", encoding="utf-8")
        self.r._write_evidence()
        self.r.set_layers("us-equities", [_layer(winners=[winner])])
        candidates = vfc.find_candidates(self.r.root)
        self.assertTrue(any(c["platform"] == "linux-wsl2-x86_64" and c["catalog"] == "us-equities"
                            for c in candidates))

    def test_malformed_input_raises(self):
        (self.r.root / "catalogs" / "landscape" / "foundation.json").write_text("not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            vfc.find_candidates(self.r.root)


class MainCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = _Root(Path(tmp.name))

    def test_main_exits_zero_and_prints_json_even_with_candidates(self):
        self.r.receipt(platform_id="macos-arm64")
        self.r.set_layers("foundation", [_layer(winners=[_winner(macos="untested", linux="conditional")])])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = vfc.main(["--root", str(self.r.root)])
        self.assertEqual(exit_code, 0)
        document = json.loads(buffer.getvalue())
        self.assertEqual(document["candidate_count"], 1)
        self.assertIn("record_verdicts.py", document["flip_instructions"])

    def test_main_exits_zero_with_no_candidates(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = vfc.main(["--root", str(self.r.root)])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["candidate_count"], 0)

    def test_main_exits_nonzero_on_missing_root(self):
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            exit_code = vfc.main(["--root", str(self.r.root / "does-not-exist")])
        self.assertNotEqual(exit_code, 0)


class RealCatalogSmokeTest(unittest.TestCase):
    """This is native_proven for whatever the real catalogs currently declare, not a fixed
    assertion: it only checks the script runs clean (exit 0, valid JSON) against the actual
    checked-in landscape files, mirroring the pattern in test_hardware_profile.py."""

    def test_runs_clean_against_the_real_repository(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = vfc.main(["--root", str(REPO_ROOT)])
        self.assertEqual(exit_code, 0)
        document = json.loads(buffer.getvalue())
        self.assertIn("candidates", document)
        self.assertEqual(document["candidate_count"], len(document["candidates"]))


if __name__ == "__main__":
    unittest.main()
