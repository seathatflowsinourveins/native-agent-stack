"""Local integration with synthetic receipts/temp files; never a live Codex canary."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "examples/codex-native/currency/currency.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CodexCurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex-currency-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_root = self.root / "state"
        self.state = self.state_root / "runs/fixture-run"
        self.state.mkdir(parents=True)
        self.releases = self.root / "releases"
        self.previous = self.releases / "0.161.0-x86_64-unknown-linux-musl/bin/codex"
        self.candidate = self.releases / "0.162.0-x86_64-unknown-linux-musl/bin/codex"
        for binary, version in [(self.previous, "0.161.0"), (self.candidate, "0.162.0")]:
            binary.parent.mkdir(parents=True)
            binary.write_text(f"#!/bin/sh\nprintf '%s\\n' 'codex-cli {version}'\n")
            binary.chmod(0o755)
        self.launcher = self.root / "codex-launcher"
        self.launcher.write_text(f"#!/bin/bash\n# identity fixture\nexec '{self.previous}' \"$@\"\n")
        self.launcher.chmod(0o750)
        self.original = self.launcher.read_bytes()
        backup = self.state / "launcher-before"
        backup.write_bytes(self.original)
        backup.chmod(0o750)
        self.resource = self.candidate.parent.parent / "codex-resources/bwrap"
        self.resource.parent.mkdir()
        self.resource.write_text("Fixture resource bytes")
        self.resource.chmod(0o755)
        self.members = ["bin/", "bin/codex", "codex-resources/", "codex-resources/bwrap"]
        self.provenance = self.state_root / "stages/0.162.0"
        self.provenance.mkdir(parents=True)
        (self.provenance / "archive-members.txt").write_text("\n".join(self.members) + "\n")
        manifest = ""
        for member in self.members:
            path = self.candidate.parent.parent / member
            mode_type = subprocess.check_output(["stat", "-c", "%a:%F", "--", str(path)],
                                                text=True, env=dict(os.environ, LC_ALL="C"))
            manifest += member + "\t" + mode_type
            if path.is_file():
                manifest += digest(path) + "\n"
        (self.provenance / "package-state.native").write_text(manifest)
        self.notes = self.provenance / "release-notes.md"
        self.notes.write_text("Fixture release notes")
        self.transaction = {
            "tag": "rust-v0.162.0",
            "version": "0.162.0",
            "previous_version": "0.161.0",
            "previous": str(self.previous),
            "candidate": str(self.candidate),
            "binary_sha256": digest(self.candidate),
            "package_sha256": digest(self.provenance / "package-state.native"),
            "launcher_sha256": digest(self.launcher),
        }
        (self.state / "transaction.json").write_text(json.dumps(self.transaction))
        self.evidence = self.state / "synthetic-evidence.txt"
        self.evidence.write_text("Constructed fixture; no native model/MCP/provider run.\n")
        counters = {
            "tool_calls": 2,
            "tool_counts": {"native_read": 1, "mcp_read": 1},
            "native_errors": 0, "mcp_errors": 0, "provider_errors": 0, "retries": 0,
        }
        self.receipt = {
            # Intentional fixture of the accepted payload shape; test classification remains synthetic.
            "evidence_class": "native_proven", "version": "0.162.0", "previous_version": "0.161.0",
            "release_review": {"tag": "rust-v0.162.0", "reviewer": "fixture coordinator",
                               "source": "https://github.com/openai/codex/releases/tag/rust-v0.162.0",
                               "install_documentation": "https://developers.openai.com/codex/cli",
                               "notes_sha256": digest(self.notes), "approved_for_canary": True,
                               "declared_breaking_items": [], "compatibility_items": []},
            "lanes": [
                {
                    "lane": lane, "thread": f"fixture-{lane}", "was_parked": True,
                    "selected_executable": str(self.candidate),
                    "queued_task": "fixture of a queued task receipt", "queued_task_complete": True,
                    "tools_smoke": [{"tool": f"tool-{i}", "ok": True} for i in range(7)],
                    "baseline": dict(counters, version="0.161.0", turn="fixture-baseline"),
                    "current": dict(counters, version="0.162.0", turn="fixture-current",
                                    binary_sha256=digest(self.candidate)),
                    "evidence": [{"path": str(self.evidence), "sha256": digest(self.evidence)}],
                }
                for lane in ["canary-one", "canary-two"]
            ],
        }
        self.source_receipt = self.root / "fixture-receipt.json"
        self.adapter = self.root / "fixture-adapter"
        self.adapter.write_text('#!/bin/sh\ncp "$FIXTURE_RECEIPT" "$3"\n')
        self.adapter.chmod(0o755)
        self.protected = self.state / "protected-window"
        self.record = self.state / "currency.md"
        self.env = dict(os.environ, CURRENCY_STATE=str(self.state_root), CURRENCY_RUN="fixture-run",
                        CURRENCY_RELEASES=str(self.releases), CURRENCY_LAUNCHER=str(self.launcher),
                        CURRENCY_PROTECTED=str(self.protected), CURRENCY_RECORD=str(self.record),
                        CURRENCY_CANARY=str(self.adapter), FIXTURE_RECEIPT=str(self.source_receipt))

    def run_phase(self, phase, receipt=None):
        self.source_receipt.write_text(json.dumps(self.receipt if receipt is None else receipt))
        return subprocess.run(["bash", str(SCRIPT), phase], env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

    def approve(self):
        result = self.run_phase("canary")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_protected_window_refuses_before_network_and_after_canary(self):
        self.protected.touch()
        self.assertEqual(self.run_phase("stage").returncode, 75)
        self.assertEqual(self.launcher.read_bytes(), self.original)
        self.protected.unlink()
        self.approve()
        self.protected.touch()
        self.assertEqual(self.run_phase("promote").returncode, 75)
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_valid_receipts_promote_next_launch_then_rollback_exact_bytes_and_mode(self):
        self.approve()
        result = self.run_phase("promote")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.candidate), self.launcher.read_text())
        self.assertTrue(self.previous.exists())
        result = self.run_phase("rollback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launcher.read_bytes(), self.original)
        self.assertEqual(self.launcher.stat().st_mode & 0o777, 0o750)

    def test_failed_canary_retains_previous_default(self):
        self.adapter.write_text("#!/bin/sh\nexit 9\n")
        self.assertEqual(self.run_phase("canary").returncode, 9)
        self.assertEqual(self.run_phase("rollback").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)
        self.assertIn("previous-retained", self.record.read_text())

    def test_invalid_canary_contracts_refuse(self):
        for mutation in [
            lambda r: r["lanes"][1].update(lane="canary-one"),
            lambda r: r["lanes"][0]["tools_smoke"].pop(),
            lambda r: r["lanes"][0]["current"].update(provider_errors=1),
            lambda r: r["lanes"][0]["baseline"].update(tool_calls=None),
            lambda r: r["lanes"][0].update(selected_executable=str(self.previous)),
            lambda r: r["lanes"][0].update(lane="paper-open-e2e"),
            lambda r: r["lanes"][0].update(was_parked=False),
            lambda r: r["lanes"][0].update(queued_task_complete=False),
            lambda r: r["release_review"].update(approved_for_canary=False),
            lambda r: r["lanes"][0]["current"].update(mcp_errors=1),
        ]:
            receipt = copy.deepcopy(self.receipt)
            mutation(receipt)
            with self.subTest(receipt=receipt["lanes"][0]["lane"]):
                self.assertNotEqual(self.run_phase("canary", receipt).returncode, 0)
                self.assertFalse((self.state / "canary-approved.json").exists())
                self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_idle_baseline_and_source_explained_guard_are_allowed(self):
        receipt = copy.deepcopy(self.receipt)
        lane = receipt["lanes"][0]
        lane["baseline"].update(tool_calls=0, tool_counts={})
        lane["current"].update(mcp_errors=1)
        lane["error_dispositions"] = [{"category": "mcp", "count": 1, "candidate_caused": False,
                                      "explanation": "Synthetic fixture of an independently sourced guard",
                                      "source": "https://github.com/mksglu/context-mode/issues/852",
                                      "failure_text_sha256": digest(self.evidence)}]
        result = self.run_phase("canary", receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_phase("promote").returncode, 0)

    def test_evidence_tamper_refuses_canary(self):
        self.evidence.write_text("Changed fixture evidence")
        self.assertNotEqual(self.run_phase("canary").returncode, 0)
        self.assertFalse((self.state / "canary-approved.json").exists())

    def test_evidence_changed_after_approval_refuses_promotion(self):
        self.approve()
        self.evidence.write_text("Changed after approval")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_failed_retry_revokes_earlier_canary_approval(self):
        self.approve()
        self.adapter.write_text("#!/bin/sh\nexit 9\n")
        self.assertEqual(self.run_phase("canary").returncode, 9)
        self.assertFalse((self.state / "canary-approved.json").exists())
        self.assertNotEqual(self.run_phase("promote").returncode, 0)

    def test_new_run_cannot_rollback_an_earlier_accepted_run(self):
        self.approve()
        self.assertEqual(self.run_phase("promote").returncode, 0)
        accepted = self.launcher.read_bytes()
        self.env["CURRENCY_RUN"] = "new-run"
        self.assertEqual(self.run_phase("rollback").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), accepted)

    def test_verified_stage_provenance_is_reused_across_runs(self):
        asset = self.provenance / "codex-package-x86_64-unknown-linux-musl.tar.gz"
        subprocess.run(["tar", "-czf", str(asset), "-C", str(self.candidate.parent.parent),
                        "bin", "codex-resources"], check=True, timeout=10)
        (self.provenance / "stage-archive.sha256").write_text(f"{digest(asset)}  {asset}\n")
        (self.provenance / "stage-binary.sha256").write_text(f"{digest(self.candidate)}  {self.candidate}\n")
        latest = self.root / "fixture-latest.json"
        latest.write_text(json.dumps({"draft": False, "prerelease": False, "tag_name": "rust-v0.162.0",
                                      "body": "Fixture release notes", "assets": [
                                          {"name": asset.name, "digest": "sha256:" + digest(asset)}]}))
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text('#!/bin/sh\ncat "$FIXTURE_LATEST"\n')
        fake_gh.chmod(0o755)
        self.env.update(PATH=str(fake_bin) + os.pathsep + self.env["PATH"],
                        FIXTURE_LATEST=str(latest), CURRENCY_RUN="retry-run")
        result = self.run_phase("stage")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.state_root / "runs/retry-run/transaction.json").is_file())
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_native_execcondition_refusal_is_recorded(self):
        self.protected.touch()
        self.assertEqual(self.run_phase("condition").returncode, 1)
        self.assertIn("REFUSED protected-window-present", self.record.read_text())

    def test_receipt_and_transaction_changes_refuse_promotion(self):
        self.approve()
        p = self.state / "canary.json"
        p.write_text(p.read_text() + " ")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)
        self.approve()
        p = self.state / "transaction.json"
        p.write_text(p.read_text() + " ")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)

    def test_candidate_change_refuses_promotion(self):
        self.approve()
        self.candidate.write_text("Changed candidate fixture")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_runtime_resource_bytes_and_permissions_are_bound(self):
        self.approve()
        self.resource.write_text("Changed resource bytes")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.resource.write_text("Fixture resource bytes")
        self.resource.chmod(0o777)
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_release_notes_changed_after_review_refuse_promotion(self):
        self.approve()
        self.notes.write_text("Changed release notes")
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.launcher.read_bytes(), self.original)

    def test_evidence_parent_escape_and_symlink_refuse(self):
        outside = self.root / "outside-evidence.txt"
        outside.write_text("Outside fixture")
        alias = self.state / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        for path in [str(self.state / "../../outside-evidence.txt"), str(alias / outside.name)]:
            receipt = copy.deepcopy(self.receipt)
            receipt["lanes"][0]["evidence"] = [{"path": path, "sha256": digest(outside)}]
            self.assertNotEqual(self.run_phase("canary", receipt).returncode, 0)
            self.assertFalse((self.state / "canary-approved.json").exists())

    def test_protected_window_also_refuses_a_restore(self):
        self.approve()
        self.assertEqual(self.run_phase("promote").returncode, 0)
        selected = self.launcher.read_bytes()
        self.protected.touch()
        self.assertEqual(self.run_phase("rollback").returncode, 75)
        self.assertEqual(self.launcher.read_bytes(), selected)

    def test_foreign_launcher_change_is_preserved(self):
        self.approve()
        self.launcher.write_text("#!/bin/sh\n# changed by another owner\n")
        changed = self.launcher.read_bytes()
        self.assertNotEqual(self.run_phase("promote").returncode, 0)
        self.assertEqual(self.run_phase("rollback").returncode, 2)
        self.assertEqual(self.launcher.read_bytes(), changed)

    def test_broken_symlink_marker_also_refuses(self):
        self.protected.symlink_to(self.state / "missing-marker-target")
        self.assertEqual(self.run_phase("stage").returncode, 75)
        self.assertEqual(self.launcher.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
