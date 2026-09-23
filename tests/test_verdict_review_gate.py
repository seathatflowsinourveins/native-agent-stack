"""Synthetic-fixture tests for scripts/verdict_review_gate.py (the required verdict-review-gate check).

Each test builds a throwaway git repository holding only the files the gate reads: the landscape
manifest and ledgers, the wave registry and documents, manifests/evidence.json and a wave's sealed
lane returns, packet, adjudication and run manifest. The base is committed; the head is the working
tree. The repository validators (scripts/landscape.py, build_verdicts.py --check) need the full
catalog, so these tests pass a stub and check the gate's own rules; CI runs the real validators.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import verdict_review_gate as gate

MANIFEST = "catalogs/landscape/manifest.json"
LEDGERS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
REGISTRY = "catalogs/sota-convergence/layer-verdict-waves.json"
RUN = "20260923"
SEALED = f"evidence/artifacts/layer-verdicts-{RUN}"
ANTHROPIC = {"name": "claude-opus-4-5", "family": "anthropic", "effort": "high"}
OPENAI = {"name": "gpt-5.2", "family": "openai", "effort": "high"}
PACKET = {"catalog": "foundation", "layer_id": "beta", "candidates": [
    {"key": "c1", "component_id": "comp-one", "repository": "https://github.com/example/one", "adopted": True},
    {"key": "c2", "component_id": "comp-two", "repository": "https://github.com/example/two", "adopted": True},
]}
COMPONENTS = {"c1": "comp-one", "c2": "comp-two"}
DECISION = "docs/decisions/2026-09-23-single-lane.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(value) -> bytes:
    return (json.dumps(value, indent=1, sort_keys=True) + "\n").encode()


def winner(component_id, linux="not_established", macos="untested"):
    return {"component_id": component_id, "repository": None, "pin": "1.0", "evidence_class": "source_review",
            "why_selected": "fixture", "evidence_refs": [], "recipe_ref": "recipes/README.md",
            "platform_status": {"linux-wsl2-x86_64": linux, "macos-arm64": macos}}


def judgment(family, claude_position, preferred_lane="claude", refuting_votes=0, packet=None):
    other = "B" if claude_position == "A" else "A"
    return {"judge": {"model": ANTHROPIC["name"] if family == "anthropic" else OPENAI["name"], "family": family},
            "claude_position": claude_position,
            "preferred_position": claude_position if preferred_lane == "claude" else other,
            "preferred_lane": preferred_lane, "refuting_votes": refuting_votes,
            "stripped_packet_sha256": packet or sha(dump(PACKET))}


def adjudication(judgments=None, winner_lane="claude"):
    judgments = judgments if judgments is not None else [
        judgment(family, position) for family in ("anthropic", "openai") for position in ("A", "B")]
    return {"winner_lane": winner_lane, "why": "fixture adjudication", "evidence_refs": [], "judgments": judgments}


class GateFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.git("init", "--quiet", "--initial-branch=main")
        self.registered, self.registered_overrides = set(), {}
        self.manifest_entries, self.new_wave = {}, False
        self.write(MANIFEST, dump({"schema_version": 1, "catalogs": LEDGERS}))
        self.ledger = {"foundation": [self.grandfathered_row("alpha")], "us-equities": []}
        self.waves = {}
        self.add_wave("20260922", b'{"wave": "20260922"}\n')
        self.base = self.commit("base")

    # -- repository helpers -------------------------------------------------------------------
    def git(self, *args):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=fixture",
                               "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
                              env=environment, check=True, capture_output=True, text=True).stdout.strip()

    def write(self, path, data: bytes):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def register(self, path):
        self.registered.add(path)

    def add_wave(self, run_id, document: bytes, register=True):
        path = f"catalogs/sota-convergence/layer-verdicts-{run_id}.json"
        self.write(path, document)
        if register:
            self.waves[run_id] = {"run_id": run_id, "path": path, "checked_at": "2026-09-23",
                                  "manifest": f"catalogs/sota-convergence/manifest-{run_id}.json",
                                  "sha256": sha(document)}

    def flush(self):
        for catalog, path in LEDGERS.items():
            self.write(path, dump({"schema_version": 2, "layers": self.ledger[catalog]}))
        self.write(REGISTRY, dump({"schema_version": 1, "waves": [self.waves[r] for r in sorted(self.waves)]}))
        if self.new_wave:
            self.write(f"{SEALED}/run-manifest.json", dump({
                "schema_version": 1, "run_id": RUN, "sealed_base": SEALED,
                "packets_sha256sums": f"{sha(dump(PACKET))}  foundation__beta.json\n",
                "packets": [self.manifest_entries[key] for key in sorted(self.manifest_entries)], "rejections": []}))
            self.register(f"{SEALED}/run-manifest.json")
        files = []
        for path in sorted(self.registered):
            data = (self.root / path).read_bytes()
            files.append({"path": path, "sha256": self.registered_overrides.get(path, sha(data)), "bytes": len(data)})
        self.write("manifests/evidence.json", dump({"schema_version": 1, "files": files}))

    def commit(self, message):
        self.flush()
        self.git("add", "-A")
        self.git("commit", "--quiet", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def rebase(self):
        """Commit the current state as the comparison base."""
        self.base = self.commit("new base")

    def report(self, validators=None):
        self.flush()
        return gate.evaluate(self.root, self.base, self.root, validators=validators or (lambda _root: []))

    def messages(self, report):
        return "\n".join(violation["message"] for violation in report["violations"])

    def assertFails(self, report, fragment):
        self.assertEqual(report["status"], "failed", report)
        self.assertIn(fragment, self.messages(report))

    def assertPasses(self, report):
        self.assertEqual(report["violations"], [], self.messages(report))
        self.assertEqual(report["status"], "passed")

    # -- row builders -------------------------------------------------------------------------
    @staticmethod
    def grandfathered_row(layer_id):
        return {"catalog": "foundation", "layer_id": layer_id, "verdict_status": "pending_lanes", "winners": [],
                "alternatives": [], "open_gaps": [], "checked_at": "2026-09-22",
                "lanes": {"claude": {"run_id": "", "sealed_sha256": ""}, "codex": {"run_id": "", "sealed_sha256": ""},
                          "agreement": "pending"}}

    def record(self, layer_id="beta", *, claude_keys=("c1",), codex_keys=("c1",), codex=True, codex_model=OPENAI,
               codex_packet=None, agreement=None, winners=None, judged=None, packets=True, single_lane=None,
               register_lanes=True, in_run_manifest=True, register_wave=True, status="recorded"):
        """Seal a new-wave (20260923) row the way record_verdicts.py would, then add it to the ledger."""
        self.new_wave = True
        packet_bytes = dump(PACKET)
        if packets:
            self.write(f"{SEALED}/packets/foundation__{layer_id}.json", packet_bytes)
            self.write(f"{SEALED}/packets/SHA256SUMS", f"{sha(packet_bytes)}  foundation__{layer_id}.json\n".encode())
        run_id = f"foundation-{layer_id}-{RUN}"
        lanes = {"sealed_base": SEALED, "claude": {"run_id": "", "sealed_sha256": ""},
                 "codex": {"run_id": "", "sealed_sha256": ""}}
        outcomes = {"claude": {"outcome": "missing"}, "codex": {"outcome": "missing"}}
        sealed = [("claude", claude_keys, ANTHROPIC, sha(packet_bytes))]
        if codex:
            sealed.append(("codex", codex_keys, codex_model, codex_packet or sha(packet_bytes)))
        for lane, keys, model, packet_sha in sealed:
            data = dump({"schema_version": 1, "lane": lane, "catalog": "foundation", "layer_id": layer_id,
                         "packet_sha256": packet_sha, "model": model, "winner_keys": list(keys)})
            path = f"{SEALED}/{lane}/{run_id}.json"
            self.write(path, data)
            if register_lanes:
                self.register(path)
            lanes[lane] = {"run_id": run_id, "sealed_sha256": sha(data)}
            outcomes[lane] = {"outcome": "sealed", **lanes[lane]}
        if agreement is None:
            agreement = ("same_winner" if set(claude_keys) == set(codex_keys) else "disagree") if codex else "codex_absent"
        lanes["agreement"] = agreement
        chosen_keys = claude_keys
        if judged is not None:
            path = f"{SEALED}/adjudication/{run_id}.json"
            self.write(path, dump(judged))
            self.register(path)
            chosen_keys = claude_keys if judged.get("winner_lane") != "codex" else codex_keys
        if single_lane is not None:
            lanes["single_lane_decision"] = single_lane
        if in_run_manifest:
            self.manifest_entries[layer_id] = {"catalog": "foundation", "layer_id": layer_id,
                                               "packet_sha256": sha(packet_bytes), "lanes": outcomes}
        self.add_wave(RUN, b'{"wave": "20260923"}\n', register=register_wave)
        row = self.grandfathered_row(layer_id)
        row.update(verdict_status=status, checked_at="2026-09-23", lanes=lanes,
                   winners=winners if winners is not None else [winner(COMPONENTS[key]) for key in chosen_keys])
        self.ledger["foundation"].append(row)
        return row

    def decision(self, text, path=DECISION):
        self.write(path, text.encode())
        return path


class NoChangeAndGrandfatheredTests(GateFixture):
    def test_no_verdict_change_passes_with_one_line(self):
        self.write("README.md", b"unrelated change\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gate.main(["--root", str(self.root), "--base", self.base])
        self.assertEqual(code, 0)
        self.assertRegex(output.getvalue().strip(), r"^verdict-review-gate: no verdict rows changed \(base [0-9a-f]{12}\)$")

    def test_head_revision_is_checked_in_a_temporary_worktree(self):
        self.commit("unrelated")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gate.main(["--root", str(self.root), "--base", self.base, "--head", "HEAD"])
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn("no verdict rows changed", output.getvalue())
        self.assertNotIn("verdict-review-gate-", self.git("worktree", "list"))

    def test_unresolvable_base_exits_2(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(["--root", str(self.root), "--base", "no-such-revision"]), 2)

    def test_grandfathered_row_change_is_reported_and_passes(self):
        self.ledger["foundation"][0]["verdict_status"] = "no_selection"
        report = self.report()
        self.assertPasses(report)
        self.assertEqual(report["changes"], [{"row": "foundation/alpha@20260922", "kind": "changed",
                                              "grandfathered": True}])

    def test_sealed_artifact_change_without_a_row_change_runs_the_validators(self):
        self.record()
        self.rebase()
        path = f"{SEALED}/codex/foundation-beta-{RUN}.json"
        (self.root / path).unlink()
        self.registered.discard(path)
        calls = []
        report = self.report(validators=lambda root: calls.append(root) or [])
        self.assertEqual(report["changes"], [])
        self.assertIn(path, report["changed_paths"])
        self.assertEqual(calls, [self.root])

    def test_lane_run_id_naming_a_new_wave_is_not_grandfathered(self):
        row = self.ledger["foundation"][0]
        row["lanes"]["claude"] = {"run_id": f"foundation-alpha-{RUN}", "sealed_sha256": "0" * 64}
        report = self.report()
        self.assertFalse(report["changes"][0]["grandfathered"])
        self.assertFails(report, "lanes.sealed_base")

    def test_repository_validators_run_when_a_row_changes_and_their_failure_fails_the_gate(self):
        calls = []

        def failing(root):
            calls.append(root)
            return [{"row": "repository", "message": "scripts/landscape.py failed (exit 1)"}]

        self.assertPasses(self.report(validators=lambda root: calls.append(root) or []))
        self.assertEqual(calls, [])  # nothing changed yet: the validators are not needed
        self.record()
        self.assertFails(self.report(validators=failing), "scripts/landscape.py failed")
        self.assertEqual(calls, [self.root])


class EvidencedRowTests(GateFixture):
    def test_fully_evidenced_agreeing_row_passes(self):
        self.record()
        report = self.report()
        self.assertPasses(report)
        self.assertEqual(report["changes"], [{"row": f"foundation/beta@{RUN}", "kind": "added", "grandfathered": False}])

    def test_disagreeing_row_with_both_family_both_order_adjudication_passes(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        self.assertPasses(self.report())

    def test_disagreeing_row_adjudicated_for_codex_records_the_codex_winners(self):
        judged = adjudication([judgment(family, position, "codex") for family in ("anthropic", "openai")
                               for position in ("A", "B")], winner_lane="codex")
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=judged)
        self.assertPasses(self.report())

    def test_third_family_judge_is_not_required(self):
        # Two lane families in both orders suffice; no third family judged this row.
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        self.assertPasses(self.report())

    def test_single_lane_row_with_its_own_authorization_line_passes(self):
        self.decision("# Single lane\n\nsingle-lane-authorization: foundation/beta\n")
        self.record(codex=False, single_lane=DECISION)
        self.assertPasses(self.report())


class MissingEvidenceTests(GateFixture):
    def test_changed_row_with_no_lane_files_fails(self):
        self.record()
        for lane in ("claude", "codex"):
            (self.root / f"{SEALED}/{lane}/foundation-beta-{RUN}.json").unlink()
        self.registered -= {f"{SEALED}/{lane}/foundation-beta-{RUN}.json" for lane in ("claude", "codex")}
        report = self.report()
        self.assertFails(report, f"the sealed claude lane return {SEALED}/claude/foundation-beta-{RUN}.json is missing")
        self.assertIn("the sealed codex lane return", self.messages(report))

    def test_same_family_lane_pair_fails(self):
        self.record(codex_model=dict(ANTHROPIC))
        self.assertFails(self.report(), "both lane returns come from the same model family 'anthropic'")

    def test_disagree_row_without_adjudication_fails(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",))
        self.assertFails(self.report(), f"the disagree row's sealed adjudication {SEALED}/adjudication/"
                                        f"foundation-beta-{RUN}.json is missing")

    def test_adjudication_missing_one_presentation_order_fails(self):
        judged = adjudication([judgment("anthropic", "A"), judgment("anthropic", "B"), judgment("openai", "A")])
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=judged)
        self.assertFails(self.report(), "both lane families in both presentation orders; missing: openai")

    def test_adjudication_missing_one_family_fails(self):
        judged = adjudication([judgment("anthropic", "A"), judgment("anthropic", "B")])
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=judged)
        self.assertFails(self.report(), "missing: openai")

    def test_adjudication_with_a_refuting_vote_fails(self):
        judgments = [judgment(family, position) for family in ("anthropic", "openai") for position in ("A", "B")]
        judgments[3]["refuting_votes"] = 1
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication(judgments))
        self.assertFails(self.report(), "a judgment carries refuting_votes 1")

    def test_stale_sealed_sha256_fails(self):
        self.record()
        path = f"{SEALED}/claude/foundation-beta-{RUN}.json"
        (self.root / path).write_bytes((self.root / path).read_bytes().replace(b'"high"', b'"xhigh"'))
        self.assertFails(self.report(), f"lanes.claude.sealed_sha256 {self.ledger['foundation'][1]['lanes']['claude']['sealed_sha256']} is stale")

    def test_lane_file_not_registered_in_the_evidence_manifest_fails(self):
        self.record(register_lanes=False)
        self.assertFails(self.report(), f"the sealed claude lane return {SEALED}/claude/foundation-beta-{RUN}.json "
                                        "is not registered in manifests/evidence.json")

    def test_lane_file_registered_with_another_sha256_fails(self):
        self.record()
        self.registered_overrides[f"{SEALED}/codex/foundation-beta-{RUN}.json"] = "f" * 64
        self.assertFails(self.report(), "manifests/evidence.json registers sha256 " + "f" * 64)

    def test_new_wave_row_missing_from_its_run_manifest_fails(self):
        self.record(in_run_manifest=False)
        self.assertFails(self.report(), f"foundation/beta must appear exactly once in the run manifest of wave {RUN}")

    def test_unregistered_run_manifest_fails(self):
        self.record()
        # flush() always registers the run manifest; drop it from the written evidence manifest.
        self.flush()
        gate_files = json.loads((self.root / "manifests/evidence.json").read_text())
        gate_files["files"] = [f for f in gate_files["files"] if f["path"] != f"{SEALED}/run-manifest.json"]
        self.write("manifests/evidence.json", dump(gate_files))
        report = gate.evaluate(self.root, self.base, self.root, validators=lambda _root: [])
        self.assertFails(report, f"the run manifest {SEALED}/run-manifest.json is not registered")

    def test_unregistered_wave_document_fails(self):
        self.record(register_wave=False)
        self.assertFails(self.report(), f"wave {RUN}'s document is not registered in {REGISTRY}")

    def test_declared_platform_status_upgrade_without_a_receipt_fails(self):
        self.record()
        self.rebase()
        self.ledger["foundation"][1]["winners"][0]["platform_status"]["macos-arm64"] = "accepted"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "platform_status")
        self.assertFails(report, "platform_status.macos-arm64 changed to 'accepted' but scripts/platform_status.py "
                                 "derives 'untested'")

    def test_platform_status_change_the_receipts_derive_passes(self):
        self.record(winners=[winner("comp-one", linux="conditional")])
        self.rebase()
        self.ledger["foundation"][1]["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "not_established"
        self.assertPasses(self.report())


class RecomputedAgreementTests(GateFixture):
    def test_relabelled_disagree_row_recorded_as_same_winner_fails(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), agreement="same_winner")
        self.assertFails(self.report(), "lanes.agreement is 'same_winner' but the sealed lane returns recompute to "
                                        "'disagree'")

    def test_lanes_with_different_packet_sha256_fail(self):
        self.record(codex_packet="e" * 64)
        self.assertFails(self.report(), "the sealed lane returns judged different packets")

    def test_swapped_winners_with_sealed_packets_fail(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication(), winners=[winner("comp-two")])
        self.assertFails(self.report(), "row winners ['comp-two'] are not the claude lane's winner_keys resolved "
                                        "through the sealed packet (['comp-one'])")

    def test_new_wave_row_without_sealed_packets_fails_closed(self):
        self.record(packets=False)
        self.assertFails(self.report(), "failing closed until review finding 6")

    def test_packet_not_listed_in_its_sha256sums_fails(self):
        self.record()
        self.write(f"{SEALED}/packets/SHA256SUMS", f"{'d' * 64}  foundation__beta.json\n".encode())
        self.assertFails(self.report(), "is not the one")


class SingleLaneTests(GateFixture):
    def test_decision_file_that_is_the_wave_document_fails(self):
        self.record(codex=False, single_lane=f"catalogs/sota-convergence/layer-verdicts-{RUN}.json")
        self.assertFails(self.report(), "is a wave document, run manifest or sealed verdict artifact")

    def test_decision_file_that_is_the_run_manifest_fails(self):
        self.record(codex=False, single_lane=f"{SEALED}/run-manifest.json")
        self.assertFails(self.report(), "is a wave document, run manifest or sealed verdict artifact")

    def test_decision_file_outside_docs_decisions_fails(self):
        path = self.decision("single-lane-authorization: foundation/beta\n", "docs/2026-09-23-single-lane.md")
        self.record(codex=False, single_lane=path)
        self.assertFails(self.report(), "must be a file under docs/decisions/")

    def test_missing_authorization_line_fails(self):
        self.decision("# Single lane\n\nThis record names beta but authorizes nothing.\n")
        self.record(codex=False, single_lane=DECISION)
        self.assertFails(self.report(), "has no line 'single-lane-authorization: foundation/beta'")

    def test_authorization_line_for_another_row_fails(self):
        self.decision("single-lane-authorization: foundation/alpha\n")
        self.record(codex=False, single_lane=DECISION)
        self.assertFails(self.report(), "has no line 'single-lane-authorization: foundation/beta'")

    def test_stored_decision_sha256_must_match(self):
        self.decision("single-lane-authorization: foundation/beta\n")
        row = self.record(codex=False, single_lane=DECISION)
        row["lanes"][gate.SINGLE_LANE_DECISION_SHA256_FIELD] = "a" * 64
        self.assertFails(self.report(), f"lanes.{gate.SINGLE_LANE_DECISION_SHA256_FIELD} " + "a" * 64)
        row["lanes"][gate.SINGLE_LANE_DECISION_SHA256_FIELD] = sha((self.root / DECISION).read_bytes())
        self.assertPasses(self.report())


class WaveFreezeTests(GateFixture):
    def test_rewritten_earlier_wave_entry_fails(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.add_wave("20260924", b'{"wave": "20260924"}\n')
        self.rebase()
        self.add_wave("20260923", b'{"wave": "20260923", "rewritten": true}\n')
        report = self.report()
        self.assertFails(report, "the frozen registry entry of wave 20260923")
        self.assertIn("the frozen wave document catalogs/sota-convergence/layer-verdicts-20260923.json was rewritten",
                      self.messages(report))

    def test_newest_wave_may_change(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        self.add_wave("20260923", b'{"wave": "20260923", "regenerated": true}\n')
        self.assertPasses(self.report())

    def test_grandfathered_wave_is_frozen_even_when_newest(self):
        self.add_wave("20260922", b'{"wave": "20260922", "rewritten": true}\n')
        self.assertFails(self.report(), "the frozen registry entry of wave 20260922")


if __name__ == "__main__":
    unittest.main()
