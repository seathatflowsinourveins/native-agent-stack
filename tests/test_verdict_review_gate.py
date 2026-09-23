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
    {"key": "c1", "component_id": "comp-one", "repository": "https://github.com/example/one", "adopted": True,
     "pin": "1.0"},
    {"key": "c2", "component_id": "comp-two", "repository": "https://github.com/example/two", "adopted": True},
]}
COMPONENTS = {"c1": "comp-one", "c2": "comp-two"}
DECISION = "docs/decisions/2026-09-23-single-lane.md"
INDEX = "catalogs/us-equities/decision-index.json"
ALTERNATIVE = {"name": "Alt", "repository": "https://github.com/example/alt", "disposition": "rejected",
               "why_not_default": "fixture alternative", "evidence_class": "source_review", "evidence_refs": []}
PROTOCOL = {"metric": "fixture metric", "arms": [], "fixture_paths": []}
# The gate's message, or the one scripts/landscape.run_manifest_row_issue reports first once the
# tooling owner's #124 binds the run manifest's adjudication there too.
MANIFEST_ADJUDICATION_MISMATCH = (r"is not the sealed adjudication lanes\.adjudication_sha256 names"
                                  r"|sealed adjudication of foundation/beta .* differs from the row's "
                                  r"lanes\.adjudication_sha256")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(value) -> bytes:
    return (json.dumps(value, indent=1, sort_keys=True) + "\n").encode()


def winner(component_id, linux="not_established", macos="untested"):
    repository = next(c["repository"] for c in PACKET["candidates"] if c["component_id"] == component_id)
    return {"component_id": component_id, "repository": repository, "pin": "1.0", "evidence_class": "source_review",
            "why_selected": "fixture", "evidence_refs": [], "recipe_ref": LEDGERS["foundation"],
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
        # retained packet name -> sha256 (the run manifest's retained_packets); layer ids whose row is
        # not bound to the run manifest (lanes.run_manifest_sha256 left out); a run-manifest override.
        self.retained, self.unbound, self.manifest_overrides = {}, set(), {}
        self.manifest = {"schema_version": 1, "catalogs": dict(LEDGERS), "sources": {"repository_index": INDEX}}
        self.write(INDEX, dump({"aliases": {}, "records": [
            {"repository": c["repository"]} for c in PACKET["candidates"]] + [{"repository": ALTERNATIVE["repository"]}]}))
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
        self.write(MANIFEST, dump(self.manifest))
        if self.new_wave:
            # The layout of #124's record_verdicts.run_manifest_document.
            manifest = {
                "schema_version": 1, "run_id": RUN, "sealed_base": SEALED,
                "packets_sha256sums": "".join(f"{digest}  {name}\n" for name, digest in sorted(self.retained.items())),
                "retained_packets": [{"name": name, "sha256": digest} for name, digest in sorted(self.retained.items())],
                "packets": [self.manifest_entries[key] for key in sorted(self.manifest_entries)], "rejections": []}
            manifest.update(self.manifest_overrides)
            data = dump(manifest)
            self.write(f"{SEALED}/run-manifest.json", data)
            self.register(f"{SEALED}/run-manifest.json")
            for row in self.ledger["foundation"]:
                if row["lanes"].get("sealed_base") == SEALED and row["layer_id"] not in self.unbound:
                    row["lanes"]["run_manifest_sha256"] = sha(data)
        for catalog, path in LEDGERS.items():
            self.write(path, dump({"schema_version": 2, "layers": self.ledger[catalog]}))
        self.write(REGISTRY, dump({"schema_version": 1, "waves": [self.waves[r] for r in sorted(self.waves)]}))
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
               register_lanes=True, in_run_manifest=True, register_wave=True, status="recorded", packet=None):
        """Seal a new-wave (20260923) row the way record_verdicts.py would, then add it to the ledger."""
        self.new_wave = True
        packet_bytes = dump(packet if packet is not None else PACKET)
        packet_name = f"foundation__{layer_id}.json"
        self.retained[packet_name] = sha(packet_bytes)
        if packets:
            self.write(f"{SEALED}/packets/{packet_name}", packet_bytes)
            self.write(f"{SEALED}/packets/SHA256SUMS", "".join(
                f"{digest}  {name}\n" for name, digest in sorted(self.retained.items())).encode())
        run_id = f"foundation-{layer_id}-{RUN}"
        lanes = {"sealed_base": SEALED, "claude": {"run_id": "", "sealed_sha256": ""},
                 "codex": {"run_id": "", "sealed_sha256": ""}}
        outcomes = {"claude": {"outcome": "missing"}, "codex": {"outcome": "missing"}}
        sealed = [("claude", claude_keys, ANTHROPIC, sha(packet_bytes))]
        if codex:
            sealed.append(("codex", codex_keys, codex_model, codex_packet or sha(packet_bytes)))
        for lane, keys, model, packet_sha in sealed:
            data = dump({"schema_version": 1, "lane": lane, "catalog": "foundation", "layer_id": layer_id,
                         "packet_sha256": packet_sha, "model": model, "winner_keys": list(keys),
                         "winner_evidence_class": "source_review", "why_selected": "fixture",
                         "overturn_when": f"{lane} overturn", "overturn_protocol": PROTOCOL,
                         "alternatives": [ALTERNATIVE]})
            path = f"{SEALED}/{lane}/{run_id}.json"
            self.write(path, data)
            if register_lanes:
                self.register(path)
            lanes[lane] = {"run_id": run_id, "sealed_sha256": sha(data)}
            outcomes[lane] = {"outcome": "sealed", **lanes[lane]}
        if agreement is None:
            agreement = ("same_winner" if set(claude_keys) == set(codex_keys) else "disagree") if codex else "codex_absent"
        lanes["agreement"] = agreement
        chosen_keys, chosen_lane = claude_keys, "claude"
        entry = {"catalog": "foundation", "layer_id": layer_id, "packet_sha256": sha(packet_bytes), "lanes": outcomes}
        if judged is not None:
            path = f"{SEALED}/adjudication/{run_id}.json"
            self.write(path, dump(judged))
            self.register(path)
            # #124 binds a sealed adjudication by the row and by the run manifest.
            lanes["adjudication_sha256"] = sha(dump(judged))
            entry["adjudication"] = {"outcome": "sealed", "sha256": sha(dump(judged))}
            if judged.get("winner_lane") == "codex":
                chosen_keys, chosen_lane = codex_keys, "codex"
        if single_lane is not None:
            lanes["single_lane_decision"] = single_lane
            if (self.root / single_lane).is_file():
                lanes["single_lane_decision_sha256"] = sha((self.root / single_lane).read_bytes())
        if in_run_manifest:
            self.manifest_entries[layer_id] = entry
        self.add_wave(RUN, b'{"wave": "20260923"}\n', register=register_wave)
        row = self.grandfathered_row(layer_id)
        recorded = status == "recorded"
        row.update(verdict_status=status, checked_at="2026-09-23", lanes=lanes,
                   winners=winners if winners is not None else [winner(COMPONENTS[key]) for key in chosen_keys],
                   alternatives=[{**ALTERNATIVE, "source": "lane:claude"}] if recorded else [],
                   verdict_overturn_when=f"{chosen_lane} overturn" if recorded else "",
                   overturn_protocol=PROTOCOL)
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

    def test_winner_evidence_class_edited_after_recording_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["evidence_class"] = "native_proven"
        self.assertFails(self.report(), "evidence_class 'native_proven' is not the claude lane's winner_evidence_class")

    def test_winner_why_selected_edited_after_recording_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["why_selected"] = "rewritten"
        self.assertFails(self.report(), "why_selected differs from the sealed claude lane return")

    def test_winner_pin_other_than_the_sealed_packet_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["pin"] = "2.0"
        self.assertFails(self.report(), "winner comp-one: pin '2.0' is not the sealed packet's '1.0'")

    def test_pending_row_carrying_winners_fails(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), status="pending_lanes")
        self.assertFails(self.report(), "a 'pending_lanes' row carries winners")

    def test_added_row_declaring_more_than_the_receipts_derive_fails(self):
        self.record(winners=[winner("comp-one", linux="accepted")])
        self.assertFails(self.report(), "platform_status.linux-wsl2-x86_64 changed to 'accepted'")

    def test_new_wave_row_without_sealed_packets_fails_closed(self):
        self.record(packets=False)
        self.assertFails(self.report(), "are absent, so the row's winners cannot be resolved from the packet both "
                                        "lanes judged; failing closed")

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


class LedgerBindingTests(GateFixture):
    def test_manifest_pointing_at_a_decoy_ledger_fails_and_the_real_ledger_is_still_checked(self):
        # Review of #123, finding 1: a decoy copy of the ledger plus a manifest pointing at it must not
        # hide an unevidenced edit of the real ledger, which build_verdicts.py publishes.
        decoy = "catalogs/landscape/foundation-decoy.json"
        self.flush()
        self.manifest["catalogs"]["foundation"] = decoy
        row = self.grandfathered_row("beta")
        row["lanes"] = {"sealed_base": SEALED, "claude": {"run_id": "", "sealed_sha256": ""},
                        "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "same_winner"}
        row.update(verdict_status="recorded", winners=[winner("comp-one")])
        self.ledger["foundation"].append(row)
        self.write(decoy, (self.root / LEDGERS["foundation"]).read_bytes())  # decoy keeps the base rows
        report = self.report()
        self.assertFails(report, f"{MANIFEST}#/catalogs is")
        self.assertIn(f"foundation/beta@{RUN}", [change["row"] for change in report["changes"]])
        self.assertIn(f"wave {RUN}'s document is not registered", self.messages(report))

    def test_manifest_without_catalogs_fails(self):
        del self.manifest["catalogs"]
        self.assertFails(self.report(), f"{MANIFEST}#/catalogs is None")

    def test_malformed_base_wave_registry_exits_2(self):
        self.write(REGISTRY, b"{not json\n")
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", "malformed registry")
        broken = self.git("rev-parse", "HEAD")
        self.flush()
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", "repaired registry")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gate.main(["--root", str(self.root), "--base", broken])
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn(f"{REGISTRY} at {broken[:12]} is not JSON", output.getvalue())

    def test_malformed_head_ledger_fails_closed(self):
        self.flush()
        self.write(LEDGERS["foundation"], b"[truncated")
        with self.assertRaisesRegex(gate.ReadError, "foundation.json at the head is not JSON"):
            gate.evaluate(self.root, self.base, self.root, validators=lambda _root: [])


class TrustBaseTests(GateFixture):
    def test_verdict_row_change_with_a_rules_change_in_the_same_comparison_fails(self):
        self.write("scripts/landscape.py", b'GRANDFATHERED_RUN_IDS = frozenset({"20260922", "20260923"})\n')
        self.record()
        self.assertFails(self.report(), "also the gate's trust base (scripts/landscape.py)")

    def test_workflow_change_with_a_sealed_artifact_change_fails(self):
        self.record()
        self.rebase()
        self.write(".github/workflows/validate.yml", b"name: weakened\n")
        path = f"{SEALED}/codex/foundation-beta-{RUN}.json"
        (self.root / path).unlink()
        self.registered.discard(path)
        self.assertFails(self.report(), "also the gate's trust base (.github/workflows/validate.yml)")

    def test_rules_change_alone_passes(self):
        self.write("scripts/verdict_review_gate.py", b"# rules change on its own\n")
        report = self.report()
        self.assertPasses(report)
        self.assertEqual(report["trust_paths_changed"], ["scripts/verdict_review_gate.py"])

    def test_rules_change_with_a_non_verdict_ledger_edit_passes(self):
        self.write("scripts/landscape.py", b"# rules change\n")
        self.ledger["foundation"][0]["rationale"] = "edited prose, no verdict field"
        self.assertPasses(self.report())


class PublishedFieldTests(GateFixture):
    def test_winner_repository_other_than_the_packet_candidate_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["repository"] = "https://github.com/example/two"
        self.assertFails(self.report(), "winner comp-one: repository 'https://github.com/example/two' is not the "
                                        "sealed packet candidate's 'https://github.com/example/one'")

    def test_winner_recipe_ref_other_than_the_recorded_one_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["recipe_ref"] = "recipes/elsewhere.md"
        self.assertFails(self.report(), "winner comp-one: recipe_ref 'recipes/elsewhere.md' is not "
                                        f"'{LEDGERS['foundation']}'")

    def test_rewritten_alternative_fails(self):
        row = self.record()
        self.rebase()
        row["alternatives"][0]["why_not_default"] = "rewritten after recording"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "changed")
        self.assertFails(report, "alternatives are not the ones record_verdicts.py derives")

    def test_dropped_alternative_fails(self):
        row = self.record()
        self.rebase()
        row["alternatives"] = []
        self.assertFails(self.report(), "alternatives are not the ones record_verdicts.py derives")

    def test_rewritten_verdict_overturn_when_fails(self):
        row = self.record()
        self.rebase()
        row["verdict_overturn_when"] = "never"
        self.assertFails(self.report(), "verdict_overturn_when differs from the sealed claude lane return")

    def test_rewritten_overturn_protocol_fails(self):
        row = self.record()
        self.rebase()
        row["overturn_protocol"] = {"metric": "another"}
        self.assertFails(self.report(), "overturn_protocol is not the one record_verdicts.py chooses")

    def test_pending_row_publishing_alternatives_fails(self):
        row = self.record(claude_keys=("c1",), codex_keys=("c2",), status="pending_lanes", winners=[])
        row["alternatives"] = [{**ALTERNATIVE, "source": "lane:claude"}]
        self.assertFails(self.report(), "a 'pending_lanes' row carries alternatives or verdict_overturn_when")

    def test_open_gaps_change_is_a_verdict_change(self):
        row = self.record()
        self.rebase()
        row["open_gaps"] = ["edited"]
        report = self.report()
        self.assertEqual(report["changes"], [{"row": f"foundation/beta@{RUN}", "kind": "changed",
                                              "grandfathered": False}])
        self.assertPasses(report)  # re-checked against the sealed evidence; its text is not re-derived


def moved_row(layer_id, run_id):
    """A grandfathered-shaped row whose lanes name wave ``run_id`` (no sealed evidence behind it)."""
    row = GateFixture.grandfathered_row(layer_id)
    row["lanes"]["sealed_base"] = f"evidence/artifacts/layer-verdicts-{run_id}"
    return row


class RowContinuityTests(GateFixture):
    """Review of #123, finding 1: rollback, deletion and moves between waves."""

    def test_rollback_of_a_new_wave_row_to_its_20260922_content_fails(self):
        self.record()
        self.rebase()
        self.ledger["foundation"][1] = self.grandfathered_row("beta")
        report = self.report()
        self.assertFails(report, f"the row moves from wave {RUN} back to the grandfathered wave 20260922")
        self.assertEqual([change["grandfathered"] for change in report["changes"]], [True])

    def test_deleted_grandfathered_row_fails(self):
        del self.ledger["foundation"][0]
        report = self.report()
        self.assertFails(report, "the row present at the base is missing at the head")
        self.assertEqual(report["removed"], ["foundation/alpha@20260922"])

    def test_deleted_new_wave_row_fails(self):
        self.record()
        self.rebase()
        del self.ledger["foundation"][1]
        self.assertFails(self.report(), "the row present at the base is missing at the head")

    def test_downgrade_to_an_older_non_grandfathered_wave_fails(self):
        for run_id in ("20260923", "20260924"):
            self.add_wave(run_id, f'{{"wave": "{run_id}"}}\n'.encode())
        self.ledger["foundation"][0] = moved_row("alpha", "20260924")
        self.rebase()
        self.ledger["foundation"][0] = moved_row("alpha", "20260923")
        self.assertFails(self.report(), "the row moves from wave 20260924 to the older wave 20260923")

    def test_move_to_an_unregistered_wave_fails(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        self.ledger["foundation"][0] = moved_row("alpha", "20260925")
        report = self.report()
        self.assertFails(report, "the row moves from wave 20260922 to wave 20260925, which is not the newest "
                                 "registered wave (20260923)")
        self.assertIn("wave 20260925's document is not registered", self.messages(report))

    def test_move_to_a_registered_wave_other_than_the_newest_fails(self):
        for run_id in ("20260923", "20260924"):
            self.add_wave(run_id, f'{{"wave": "{run_id}"}}\n'.encode())
        self.rebase()
        self.ledger["foundation"][0] = moved_row("alpha", "20260923")
        self.assertFails(self.report(), "which is not the newest registered wave (20260924)")

    def test_move_to_the_newest_wave_needs_the_full_new_wave_evidence(self):
        self.ledger["foundation"][0] = moved_row("alpha", RUN)
        self.add_wave(RUN, b'{"wave": "20260923"}\n')
        report = self.report()
        self.assertFails(report, f"the run manifest {SEALED}/run-manifest.json is missing")
        self.assertNotIn("moves from wave", self.messages(report))

    def test_move_to_the_newest_wave_with_the_full_evidence_passes(self):
        del self.ledger["foundation"][0]
        self.record("alpha")
        self.assertPasses(self.report())

    def test_two_rows_for_one_layer_fail(self):
        self.record()
        self.rebase()
        self.ledger["foundation"].append(self.grandfathered_row("beta"))
        self.assertFails(self.report(), "the head ledger holds 2 rows for this layer")


class SemanticComparisonTests(GateFixture):
    """Review of #123, finding 3: a pure formatting change of a generated document is not a value change."""

    def reformat(self, path):
        data = json.loads((self.root / path).read_bytes())
        self.write(path, (json.dumps(data, indent=4) + "\n").encode())
        return sha((self.root / path).read_bytes())

    def test_reformatted_frozen_wave_document_with_its_registry_sha256_passes(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        path = "catalogs/sota-convergence/layer-verdicts-20260922.json"
        self.waves["20260922"]["sha256"] = self.reformat(path)
        report = self.report()
        self.assertPasses(report)
        self.assertFalse(report["waves_changed"])
        self.assertIn(path, report["changed_paths"])
        self.assertNotIn(path, report["value_changed_paths"])

    def test_reformatted_frozen_wave_document_with_a_stale_registry_sha256_fails(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        self.reformat("catalogs/sota-convergence/layer-verdicts-20260922.json")
        self.assertFails(self.report(), "the frozen wave 20260922's registry sha256")

    def test_generator_format_change_with_regenerated_documents_passes_the_trust_rule(self):
        row = self.record()
        self.rebase()
        self.write("tools/sota-convergence/build_verdicts.py", b"# new output format\n")
        self.waves[RUN]["sha256"] = self.reformat(f"catalogs/sota-convergence/layer-verdicts-{RUN}.json")
        self.flush()
        self.reformat(LEDGERS["foundation"])
        calls = []
        report = gate.evaluate(self.root, self.base, self.root, validators=lambda root: calls.append(root) or [])
        self.assertPasses(report)
        self.assertEqual((report["changes"], report["waves_changed"]), ([], False))
        self.assertEqual(calls, [self.root])  # build_verdicts.py --check still decides the reformat
        self.assertEqual(row["verdict_status"], "recorded")

    def test_generator_change_with_a_changed_wave_value_still_fails_the_trust_rule(self):
        self.record()
        self.rebase()
        self.write("tools/sota-convergence/build_verdicts.py", b"# new output format\n")
        self.add_wave(RUN, b'{"wave": "20260923", "edited": true}\n')
        self.assertFails(self.report(), "also the gate's trust base (tools/sota-convergence/build_verdicts.py)")

    def test_changed_row_value_is_a_change_whatever_the_formatting(self):
        row = self.record()
        self.rebase()
        row["verdict_overturn_when"] = "never"
        self.flush()
        self.reformat(LEDGERS["foundation"])
        report = gate.evaluate(self.root, self.base, self.root, validators=lambda _root: [])
        self.assertFails(report, "verdict_overturn_when differs from the sealed claude lane return")


class ToolingAlignmentTests(GateFixture):
    """#124's names and bindings: packets through the run manifest, withheld keys, lane sha256 fields."""

    def test_packet_not_listed_in_the_run_manifest_fails(self):
        # The packet file sits at the conventional name, but the run manifest does not retain it:
        # the packet is resolved through the manifest, not through an assumed file name.
        self.record()
        self.manifest_overrides["retained_packets"] = [{"name": "foundation__beta.json", "sha256": "6" * 64}]
        self.assertFails(self.report(), "is not listed in the run manifest's retained_packets")

    def test_retained_packet_name_that_is_not_a_plain_file_name_fails(self):
        self.record()
        self.manifest_overrides["retained_packets"] = [{"name": "../foundation__beta.json",
                                                        "sha256": sha(dump(PACKET))}]
        self.assertFails(self.report(), "is not a plain .json file name")

    def test_run_manifest_without_retained_packets_fails(self):
        self.record()
        self.manifest_overrides["retained_packets"] = None
        self.assertFails(self.report(), "the run manifest has no retained_packets list")

    def test_packet_other_than_the_run_manifest_packet_sha256_fails(self):
        self.record()
        self.write(f"{SEALED}/packets/foundation__beta.json", dump({**PACKET, "extra": 1}))
        self.assertFails(self.report(), "is not the run manifest's packet_sha256")

    def test_sha256sums_other_than_the_run_manifest_text_fails(self):
        self.record()
        path = self.root / f"{SEALED}/packets/SHA256SUMS"
        path.write_bytes(path.read_bytes() + f"{'c' * 64}  foundation__other.json\n".encode())
        self.assertFails(self.report(), "SHA256SUMS is not the run manifest's packets_sha256sums")

    def test_withheld_keys_in_the_sealed_packet_fail(self):
        for layer_id, packet, label in (
                ("stars", {**PACKET, "candidates": [{**PACKET["candidates"][0], "upstream": {"stars": 5}},
                                                    PACKET["candidates"][1]]}, "candidates[].upstream.stars"),
                ("pushed", {**PACKET, "candidates": [{**PACKET["candidates"][0],
                                                      "upstream": {"meta": [{"pushed_at": "2026"}]}},
                                                     PACKET["candidates"][1]]}, "candidates[].upstream.meta[].pushed_at"),
                ("latest", {**PACKET, "latest": "2.0"}, "latest"),
                ("prerelease", {**PACKET, "candidates": [{**PACKET["candidates"][0], "prerelease": True},
                                                         PACKET["candidates"][1]]}, "candidates[].prerelease"),
                ("behind", {**PACKET, "candidates": [{**PACKET["candidates"][0], "pin_behind_upstream": True},
                                                     PACKET["candidates"][1]]}, "candidates[].pin_behind_upstream"),
                ("newcomer", {**PACKET, "sota": {"newcomer": True}}, "sota.newcomer"),
                ("forks", {**PACKET, "forks": 3, "watchers": 2}, "forks")):
            with self.subTest(layer_id):
                self.setUp()
                self.record(packet=packet)
                self.assertFails(self.report(), f"carries withheld keys ['{label}'"
                                 if layer_id != "forks" else "carries withheld keys ['forks', 'watchers']")

    def test_packet_own_checked_at_is_not_withheld(self):
        self.record(packet={**PACKET, "checked_at": "2026-09-23"})
        self.assertPasses(self.report())
        self.assertEqual(gate.withheld_packet_keys({"checked_at": "x", "c": [{"checked_at": "y"}]}), ["c[].checked_at"])

    def test_missing_run_manifest_sha256_fails(self):
        self.record()
        self.unbound.add("beta")
        self.assertFails(self.report(), "lanes.run_manifest_sha256 is absent")

    def test_wrong_run_manifest_sha256_fails(self):
        row = self.record()
        self.unbound.add("beta")
        row["lanes"]["run_manifest_sha256"] = "b" * 64
        self.assertFails(self.report(), f"lanes.run_manifest_sha256 {'b' * 64} is not the sha256 of {SEALED}/run-manifest.json")

    def test_disagree_row_without_adjudication_sha256_fails(self):
        row = self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        del row["lanes"]["adjudication_sha256"]
        self.assertFails(self.report(), "lanes.adjudication_sha256 is absent")

    def test_wrong_adjudication_sha256_fails(self):
        row = self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        row["lanes"]["adjudication_sha256"] = "9" * 64
        report = self.report()
        self.assertFails(report, f"lanes.adjudication_sha256 {'9' * 64} is not the sha256 of {SEALED}/adjudication/")
        self.assertRegex(self.messages(report), MANIFEST_ADJUDICATION_MISMATCH)

    def test_run_manifest_adjudication_other_than_the_row_fails(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        self.manifest_entries["beta"]["adjudication"] = {"outcome": "sealed", "sha256": "8" * 64}
        report = self.report()
        self.assertEqual(report["status"], "failed", report)
        self.assertRegex(self.messages(report), MANIFEST_ADJUDICATION_MISMATCH)

    def test_adjudication_sha256_on_an_agreeing_row_fails(self):
        row = self.record()
        row["lanes"]["adjudication_sha256"] = "7" * 64
        self.assertFails(self.report(), "lanes.adjudication_sha256 is only meaningful on a disagree row")

    def test_single_lane_row_without_decision_sha256_fails(self):
        self.decision("single-lane-authorization: foundation/beta\n")
        row = self.record(codex=False, single_lane=DECISION)
        del row["lanes"]["single_lane_decision_sha256"]
        self.assertFails(self.report(), "lanes.single_lane_decision_sha256 is absent")

    def test_names_match_the_tooling_owners_landscape_once_it_defines_them(self):
        from scripts import landscape
        for name in ("RETAINED_PACKETS_DIR", "POPULARITY_RECENCY_FIELDS", "POPULARITY_TOKENS",
                     "UPSTREAM_RELEASE_FIELDS", "COPY_WITHHELD_FIELDS", "WITHHELD_KEY_TOKENS", "PACKET_OWN_KEYS",
                     "SINGLE_LANE_DECISION_DIR"):
            if hasattr(landscape, name):
                self.assertEqual(getattr(gate, name), getattr(landscape, name), name)


class TrustPathDerivationTests(unittest.TestCase):
    """Review of #123, finding 4: TRUST_PATHS covers every repository module the gate and the validators
    import (transitively) and the rule inputs they read, derived from the modules themselves."""

    ROOT = Path(gate.__file__).resolve().parents[1]
    ENTRY_POINTS = ("scripts/verdict_review_gate.py", "scripts/landscape.py", "scripts/platform_status.py",
                    "scripts/host_receipts.py", "tools/sota-convergence/build_verdicts.py",
                    "tools/sota-convergence/record_verdicts.py")

    def local_imports(self, relative):
        import ast
        tree = ast.parse((self.ROOT / relative).read_text(encoding="utf-8"))
        here = Path(relative).parent
        found = set()
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = here.joinpath(*(node.module or "").split(".")) if node.module else here
                    names = [str(base).replace("/", ".")] + [f"{base}.{alias.name}".replace("/", ".")
                                                             for alias in node.names]
                else:
                    names = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
            for name in names:
                parts = name.split(".")
                for directory in (Path("."), here, Path("tools/sota-convergence")):
                    candidate = directory.joinpath(*parts).with_suffix(".py")
                    if (self.ROOT / candidate).is_file():
                        found.add(candidate.as_posix())
        return found

    def test_every_imported_repository_module_is_a_trust_path(self):
        seen, queue = set(), list(self.ENTRY_POINTS)
        while queue:
            relative = queue.pop()
            if relative in seen:
                continue
            seen.add(relative)
            queue.extend(self.local_imports(relative) - seen)
        self.assertIn("scripts/validate.py", seen)  # scripts/host_receipts.py imports it
        self.assertEqual(sorted(seen - set(gate.TRUST_PATHS)), [])

    def test_rule_inputs_the_modules_read_are_trust_paths(self):
        from scripts import host_receipts, landscape
        import record_verdicts
        inputs = {landscape.LANE_PROVENANCE_REGISTRY, host_receipts.SCHEMA_RELATIVE_PATH,
                  Path(record_verdicts.SCHEMA_PATH).resolve().relative_to(self.ROOT).as_posix()}
        self.assertEqual(sorted(inputs - set(gate.TRUST_PATHS)), [])
        self.assertIn("tools/sota-convergence/lane-provenance.json", gate.TRUST_PATHS)
        for path in gate.TRUST_PATHS:
            self.assertTrue((self.ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
