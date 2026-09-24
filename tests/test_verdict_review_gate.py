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
from unittest import mock
from pathlib import Path

from scripts import landscape
from scripts import verdict_review_gate as gate

MANIFEST = "catalogs/landscape/manifest.json"
LEDGERS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
REGISTRY = "catalogs/sota-convergence/layer-verdict-waves.json"
RUN = "20260923"
SEALED = f"evidence/artifacts/layer-verdicts-{RUN}"
ANTHROPIC = {"name": "claude-opus-4-5", "family": "anthropic", "effort": "high"}
OPENAI = {"name": "gpt-5.2", "family": "openai", "effort": "high"}
# A --withhold-labels packet lists every policy label; its candidates' manifest fields are sealed in KEYS, which
# the wave retains as packet-keys.json (review of #145).
PACKET = {"catalog": "foundation", "layer_id": "beta", "candidates": [
    {"key": "c1", "repository": "https://github.com/example/one", "adopted": True},
    {"key": "c2", "repository": "https://github.com/example/two", "adopted": True},
], "withheld": landscape.withhold_policy_labels(None) + landscape.sealed_candidate_labels()}
KEYS = {"c1": {"component_id": "comp-one", "pin": "1.0"}, "c2": {"component_id": "comp-two"}}
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


def winner(component_id, linux="not_established", macos="untested", evidence_class="source_review",
           evidence_refs=(), pin=None):
    """The winner record_verdicts.build_winners writes: the packet pin, else "unpinned" (the fixture
    rows carry no v1 candidates unless a test adds them)."""
    key = next(key for key, fields in KEYS.items() if fields["component_id"] == component_id)
    candidate = next(c for c in PACKET["candidates"] if c["key"] == key)
    return {"component_id": component_id, "repository": candidate["repository"],
            "pin": pin or KEYS[key].get("pin") or "unpinned", "evidence_class": evidence_class,
            "why_selected": "fixture", "evidence_refs": list(evidence_refs), "recipe_ref": LEDGERS["foundation"],
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
        # retained packet name -> its packet-keys entry (lane_packets.py --keys-out, retained by record_verdicts.py)
        self.keys = {}
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
            keys_data = dump({"schema_version": 1, "packets": self.keys})
            self.write(f"{SEALED}/packet-keys.json", keys_data)
            self.register(f"{SEALED}/packet-keys.json")
            manifest["packet_keys_sha256"] = sha(keys_data)
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
               register_lanes=True, in_run_manifest=True, register_wave=True, status="recorded", packet=None,
               evidence_class="source_review", evidence_refs=(), linux="not_established", keys=None):
        """Seal a new-wave (20260923) row the way record_verdicts.py would, then add it to the ledger."""
        self.new_wave = True
        packet_bytes = dump(packet if packet is not None else PACKET)
        packet_name = f"foundation__{layer_id}.json"
        self.retained[packet_name] = sha(packet_bytes)
        self.keys[packet_name] = {"packet_sha256": sha(packet_bytes), "candidates": {
            candidate["key"]: (KEYS if keys is None else keys).get(candidate["key"], {})
            for candidate in (packet if packet is not None else PACKET).get("candidates") or []}}
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
                         "winner_evidence_class": evidence_class, "winner_evidence_refs": list(evidence_refs),
                         "why_selected": "fixture",
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
                   winners=winners if winners is not None else [
                       winner(COMPONENTS[key], linux=linux, evidence_class=evidence_class, evidence_refs=evidence_refs)
                       for key in chosen_keys],
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
        # The authorization is at the base (fourth review, G2): it landed in an earlier pull request.
        self.decision("# Single lane\n\nsingle-lane-authorization: foundation/beta\n")
        self.rebase()
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

    def refuting_votes_report(self, votes):
        judgments = [judgment(family, position) for family in ("anthropic", "openai") for position in ("A", "B")]
        judgments[3]["refuting_votes"] = votes
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication(judgments))
        return self.report()

    # Review of #135, round 2: false and 0.0 are == 0 in Python but are not a zero vote count.
    def test_adjudication_with_false_refuting_votes_fails(self):
        self.assertFails(self.refuting_votes_report(False), "a judgment carries refuting_votes False")

    def test_adjudication_with_float_refuting_votes_fails(self):
        self.assertFails(self.refuting_votes_report(0.0), "a judgment carries refuting_votes 0.0")

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
        self.rebase()
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

    # Review of #135, M1: every wave document holds all rows, and build_verdicts.py --check verifies a
    # wave that is no longer current only against its own rows and registry sha256. So the base's
    # newest wave is frozen outright once the head registers a newer one.
    NEWEST = {"catalogs": {"foundation": [{"layer_id": "alpha", "verdict_status": "pending_lanes"},
                                          {"layer_id": "beta", "verdict_status": "recorded", "winners": ["comp-one"]}]}}

    def test_base_newest_wave_rewritten_while_a_newer_wave_is_registered_fails(self):
        self.add_wave("20260923", dump(self.NEWEST))
        self.rebase()
        edited = json.loads(json.dumps(self.NEWEST))
        edited["catalogs"]["foundation"][0]["verdict_status"] = "recorded"
        self.add_wave("20260923", dump(edited))  # the registry sha256 follows the edited document
        self.add_wave("20260924", dump(self.NEWEST))
        report = self.report()
        self.assertFails(report, "the registry entry of wave 20260923, the base's newest, was changed or removed")
        self.assertIn("the wave document catalogs/sota-convergence/layer-verdicts-20260923.json of wave 20260923, the "
                      "base's newest, was rewritten while this change registers the newer wave(s) 20260924",
                      self.messages(report))

    def test_base_newest_wave_reformatted_while_a_newer_wave_is_registered_fails(self):
        self.add_wave("20260923", dump(self.NEWEST))
        self.rebase()
        self.add_wave("20260923", (json.dumps(self.NEWEST, indent=4) + "\n").encode())
        self.add_wave("20260924", dump(self.NEWEST))
        self.assertFails(self.report(), "a superseded wave's document is frozen byte for byte")

    def test_newer_wave_registered_without_touching_the_base_newest_passes(self):
        self.add_wave("20260923", dump(self.NEWEST))
        self.rebase()
        self.add_wave("20260924", dump(self.NEWEST))
        report = self.report()
        self.assertPasses(report)
        self.assertTrue(report["waves_changed"])

    # Review of #135, round 2: only the current wave is regenerated by build_verdicts.py --check, so a
    # wave registered first at the head must be the one current wave, newer than every base wave.
    def test_two_new_waves_in_one_change_fail(self):
        forged = json.loads(json.dumps(self.NEWEST))
        forged["catalogs"]["foundation"][0]["verdict_status"] = "recorded"
        self.add_wave("20260923", dump(forged))  # a forged document with its correct registry sha256
        self.add_wave("20260924", dump(self.NEWEST))
        report = self.report()
        self.assertFails(report, "this change registers 2 new waves (20260923, 20260924)")
        self.assertIn("the newly registered wave 20260923 is not the current wave", self.messages(report))

    def test_backdated_new_wave_fails(self):
        self.add_wave("20260923", dump(self.NEWEST))
        self.rebase()
        self.add_wave("20260915", dump(self.NEWEST))
        self.assertFails(self.report(), "the newly registered wave 20260915 is not the current wave (the head's "
                                        "newest is 20260923, the base's newest is 20260923)")
        # Backdated also when it is the head's newest because the base's newest was dropped (the
        # dropped wave itself is left to the other checks).
        self.assertIn("is not the current wave", self.messages({"violations": gate.new_wave_violations(
            {"20260922": {}, "20260923": {}}, {"20260922": {}, "20260922a": {}})}))

    def test_one_new_current_wave_passes(self):
        self.add_wave("20260923", dump(self.NEWEST))
        report = self.report()
        self.assertPasses(report)
        self.assertEqual(gate.new_wave_violations({"20260922": {}}, {"20260922": {}, "20260923": {}}), [])

    def test_unregistering_the_base_newest_wave_fails(self):
        # Round 2 builder note: with no newer wave the base's newest wave may change, not disappear.
        self.record()
        self.rebase()
        del self.waves[RUN]
        self.assertFails(self.report(), f"wave {RUN}, the base's newest, was removed from")

    def test_frozen_values_compare_type_strictly(self):
        # Review of #135, L5: 1, 1.0 and true are equal to Python's ==, not in a frozen document.
        self.add_wave("20260922", b'{"n": 1, "flag": true}\n')
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        for rewritten in (b'{"n": 1.0, "flag": true}\n', b'{"n": 1, "flag": 1}\n', b'{"n": true, "flag": true}\n'):
            with self.subTest(rewritten=rewritten):
                self.add_wave("20260922", rewritten)
                self.assertFails(self.report(), "the frozen wave document catalogs/sota-convergence/"
                                                "layer-verdicts-20260922.json was rewritten")
        self.assertFalse(gate.json_equivalent(b'{"a": 12}', b'{"a": 12.0}'))
        self.assertFalse(gate.registry_equivalent(b'{"waves": [{"n": 1}]}', b'{"waves": [{"n": true}]}'))
        self.assertTrue(gate.json_equivalent(b'{"a": 1, "b": [true]}', b'{"b": [true],\n "a": 1}'))
        row = {"winners": [], "lanes": {"agreement": "pending", "attempt": 1}}
        self.assertEqual(gate.change_kind(row, {**row, "lanes": {"agreement": "pending", "attempt": True}}), "changed")
        self.assertEqual(gate.change_kind(row, {**row, "lanes": {"attempt": 1, "agreement": "pending"}}), None)


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

    def test_derived_values_compare_type_strictly(self):
        # Review of #135, round 2: a value that only changes type (12 -> 12.0 or true) is == to the
        # derivation from the sealed returns in Python, but not in the published document.
        with mock.patch.dict(PROTOCOL, {"min_passes": 12}):
            row = self.record()
            self.rebase()
            sealed = dict(row["overturn_protocol"])
            for rewritten in (12.0, True):
                with self.subTest(rewritten=rewritten):
                    row["overturn_protocol"] = {**sealed, "min_passes": rewritten}
                    self.assertFails(self.report(), "overturn_protocol is not the one record_verdicts.py chooses")
            row["overturn_protocol"] = sealed
            self.assertPasses(self.report())

    def test_published_alternatives_compare_type_strictly(self):
        with mock.patch.dict(ALTERNATIVE, {"why_not_default": 1}):
            row = self.record()
            self.rebase()
            sealed = [dict(alternative) for alternative in row["alternatives"]]
            self.assertEqual(sealed[0]["why_not_default"], 1)
            for rewritten in (1.0, True):
                with self.subTest(rewritten=rewritten):
                    row["alternatives"] = [{**sealed[0], "why_not_default": rewritten}, *sealed[1:]]
                    self.assertFails(self.report(), "alternatives are not the ones record_verdicts.py derives")
            row["alternatives"] = sealed
            self.assertPasses(self.report())

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

    def test_sealed_candidate_keys_are_bound_by_the_run_manifest(self):
        # Review of #145 (F5): winners resolve through the wave's packet-keys document, never an unbound one.
        self.record()
        self.manifest_overrides["packet_keys_sha256"] = "0" * 64
        self.assertFails(self.report(), "packet-keys.json is not the run manifest's packet_keys_sha256")
        del self.manifest_overrides["packet_keys_sha256"]
        # Bound, but naming another component for the winning key: the row's winner no longer matches.
        self.keys["foundation__beta.json"]["candidates"]["c1"] = {"component_id": "comp-forged", "pin": "1.0"}
        report = self.report()
        self.assertEqual(report["status"], "failed", self.messages(report))
        self.assertIn("comp-forged", self.messages(report))

    def test_sha256sums_other_than_the_run_manifest_text_fails(self):
        self.record()
        path = self.root / f"{SEALED}/packets/SHA256SUMS"
        path.write_bytes(path.read_bytes() + f"{'c' * 64}  foundation__other.json\n".encode())
        self.assertFails(self.report(), "SHA256SUMS is not the run manifest's packets_sha256sums")

    def test_withheld_keys_in_the_sealed_packet_fail(self):
        for layer_id, packet, label in (
                # upstream itself is a sealed field (review of #145), so nested keys are placed under evidence.
                ("stars", {**PACKET, "candidates": [{**PACKET["candidates"][0], "evidence": {"stars": 5}},
                                                    PACKET["candidates"][1]]}, "candidates[].evidence.stars"),
                ("pushed", {**PACKET, "candidates": [{**PACKET["candidates"][0],
                                                      "evidence": {"meta": [{"pushed_at": "2026"}]}},
                                                     PACKET["candidates"][1]]}, "candidates[].evidence.meta[].pushed_at"),
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
        labels = landscape.withhold_policy_labels(None) + landscape.sealed_candidate_labels()
        self.assertEqual(gate.withheld_packet_keys({"checked_at": "x", "c": [{"checked_at": "y"}], "withheld": labels}),
                         ["c[].checked_at"])

    def test_the_gate_applies_the_landscape_validators_withheld_policy(self):
        # 2026-09-23: the gate kept its own copy of the policy, which lacked the top-level, disposition
        # and withheld[] checks; it now imports the base's scripts/landscape.withheld_packet_keys, so a
        # key the tooling owner adds (TOP_LEVEL_WITHHELD_KEYS) is enforced here without a gate change.
        self.assertIs(gate.withheld_packet_keys, landscape.withheld_packet_keys)
        missing = [label for label in PACKET["withheld"] if label != "candidates[].upstream.stars"]
        first = {**PACKET["candidates"][0]}
        for layer_id, packet, fragment in (
                ("decision", {**PACKET, "decision": "comp-one"}, "carries withheld keys ['decision']"),
                ("rationale", {**PACKET, "rationale": "why"}, "carries withheld keys ['rationale']"),
                ("choice", {**PACKET, "current_choice": "comp-one"}, "carries withheld keys ['current_choice']"),
                ("disposition", {**PACKET, "candidates": [{**first, "disposition": "adopted"}, PACKET["candidates"][1]]},
                 "carries withheld keys ['candidates[].disposition']"),
                ("review", {**PACKET, "candidates": [{**first, "review_status": "accepted"}, PACKET["candidates"][1]]},
                 "carries withheld keys ['candidates[].review_status']"),
                ("unlabelled", {**PACKET, "withheld": missing},
                 "carries withheld keys ['withheld[] lacks candidates[].upstream.stars']")):
            with self.subTest(layer_id):
                self.setUp()
                self.record(packet=packet)
                self.assertFails(self.report(), fragment)

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

    # #124's values at origin/claude/verdict-integrity-2-20260923 238c754 (scripts/landscape.py lines
    # 99-126), pinned so the comparison asserts something before #124 merges.
    TOOLING_OWNER_NAMES_238C754 = {
        "RETAINED_PACKETS_DIR": "packets",
        "SINGLE_LANE_DECISION_DIR": "docs/decisions/",
    }

    def test_names_match_the_tooling_owners_pinned_values(self):
        for name, value in self.TOOLING_OWNER_NAMES_238C754.items():
            self.assertEqual(getattr(gate, name), value, name)

    def test_names_match_the_tooling_owners_landscape_once_it_defines_them(self):
        from scripts import landscape
        defined = [name for name in self.TOOLING_OWNER_NAMES_238C754 if hasattr(landscape, name)]
        if not defined:
            self.skipTest("scripts/landscape.py defines none of #124's names yet (#124 unmerged); "
                          "test_names_match_the_tooling_owners_pinned_values pins them")
        for name in defined:
            self.assertEqual(getattr(gate, name), getattr(landscape, name), name)


class StatusDerivationTests(GateFixture):
    """Third review of #123, finding 1: verdict_status is the one record_verdicts.py writes for the
    sealed evidence, so a recorded verdict cannot be withdrawn by relabelling its row."""

    def withdraw(self, row, status, open_gaps=()):
        row.update(verdict_status=status, winners=[], alternatives=[], verdict_overturn_when="",
                   open_gaps=list(open_gaps))

    def test_agreeing_row_relabelled_pending_lanes_fails(self):
        row = self.record()
        self.rebase()
        self.withdraw(row, "pending_lanes")
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "changed")
        self.assertFails(report, "verdict_status is 'pending_lanes' but record_verdicts.py writes 'recorded'")

    def test_agreeing_row_relabelled_no_selection_fails(self):
        row = self.record()
        self.rebase()
        self.withdraw(row, "no_selection", ["withdrawn"])
        self.assertFails(self.report(), "a new-wave row cannot be 'no_selection'")

    def test_added_no_selection_row_fails(self):
        row = self.record(claude_keys=("c1",), codex_keys=("c2",), status="pending_lanes", winners=[])
        row.update(verdict_status="no_selection", open_gaps=["nothing fits"])
        self.assertFails(self.report(), "a new-wave row cannot be 'no_selection'")

    def test_adjudicated_disagreement_relabelled_pending_lanes_fails(self):
        row = self.record(claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        self.rebase()
        self.withdraw(row, "pending_lanes")
        self.assertFails(self.report(), "verdict_status is 'pending_lanes' but record_verdicts.py writes 'recorded'")

    def test_single_lane_row_relabelled_pending_lanes_fails_even_without_its_hash(self):
        self.decision("single-lane-authorization: foundation/beta\n")
        row = self.record(codex=False, single_lane=DECISION)
        self.rebase()
        self.withdraw(row, "pending_lanes")
        del row["lanes"]["single_lane_decision_sha256"]
        self.assertFails(self.report(), "verdict_status is 'pending_lanes' but record_verdicts.py writes 'recorded'")

    def test_unadjudicated_disagreement_pending_lanes_passes(self):
        self.record(claude_keys=("c1",), codex_keys=("c2",), status="pending_lanes", winners=[])
        self.assertPasses(self.report())

    def test_split_adjudication_pending_lanes_passes(self):
        judged = adjudication([judgment("anthropic", "A"), judgment("anthropic", "B"),
                               judgment("openai", "A", "codex"), judgment("openai", "B", "codex")], winner_lane=None)
        self.record(claude_keys=("c1",), codex_keys=("c2",), judged=judged, status="pending_lanes", winners=[])
        self.assertPasses(self.report())

    def test_single_lane_row_without_a_decision_pending_lanes_passes(self):
        self.record(codex=False, status="pending_lanes", winners=[])
        self.assertPasses(self.report())

    def test_recorded_row_with_no_remaining_alternative_fails(self):
        # Both lanes name only the winner as an alternative: record_verdicts.py defers the verdict.
        with mock.patch.dict(ALTERNATIVE, {"repository": PACKET["candidates"][0]["repository"]}):
            row = self.record()
            row["alternatives"] = []
            self.assertFails(self.report(), "verdict_status is 'recorded' but record_verdicts.py writes 'pending_lanes'")


class FailClosedTests(GateFixture):
    """Third review of #123, findings 3 and 4: git failures and duplicate JSON keys fail closed."""

    def test_git_failure_listing_changed_paths_is_a_read_error(self):
        for function in (gate.changed_verdict_paths, gate.changed_trust_paths):
            with self.assertRaises(gate.ReadError):
                function(self.root, "0" * 40)

    def test_stubbed_ls_files_failure_is_a_read_error_and_exits_2(self):
        real = gate.git

        def failing(root, *args, check=True):
            if args and args[0] == "ls-files":
                return subprocess.CompletedProcess(args, 128, b"", b"fatal: stubbed failure")
            return real(root, *args, check=check)

        with mock.patch.object(gate, "git", failing), contextlib.redirect_stdout(io.StringIO()) as output:
            code = gate.main(["--root", str(self.root), "--base", self.base])
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn("git ls-files failed", output.getvalue())

    def test_duplicate_keys_are_not_equivalent(self):
        self.assertTrue(gate.json_equivalent(b'{"a": 2}', b'{\n "a": 2\n}\n'))
        self.assertFalse(gate.json_equivalent(b'{"a": 2}', b'{"a": 1, "a": 2}'))
        self.assertFalse(gate.registry_equivalent(b'{"waves": []}', b'{"waves": [1], "waves": []}'))

    def test_frozen_wave_document_rewritten_with_an_earlier_duplicate_key_fails(self):
        self.add_wave("20260923", b'{"wave": "20260923"}\n')
        self.rebase()
        path = "catalogs/sota-convergence/layer-verdicts-20260922.json"
        self.write(path, b'{"wave": "rewritten", "wave": "20260922"}\n')
        self.waves["20260922"]["sha256"] = sha((self.root / path).read_bytes())
        report = self.report()
        self.assertFails(report, "the frozen wave document catalogs/sota-convergence/layer-verdicts-20260922.json "
                                 "was rewritten")
        self.assertIn(path, report["value_changed_paths"])

    def test_changed_paths_are_listed_nul_separated(self):
        # Review of #135, hardening: without -z git C-quotes a path with a newline or a non-ASCII byte
        # (and splitlines splits it), so the listed path would not be the file's.
        odd = ["catalogs/sota-convergence/tracked name\nwith \u00e9.json",
               "catalogs/sota-convergence/untracked name \u00e9.json"]
        self.write(odd[0], b"{}\n")
        self.rebase()
        self.write(odd[0], b'{"edited": true}\n')
        self.write(odd[1], b"{}\n")
        paths = gate.changed_verdict_paths(self.root, self.base)
        for path in odd:
            self.assertIn(path, paths)
        self.assertFalse([path for path in paths if path.startswith('"')], paths)
        report = self.report()
        self.assertIn(odd[0], report["value_changed_paths"])
        self.assertTrue(report["touched"])

    def test_ledger_with_a_duplicate_key_is_a_read_error(self):
        self.flush()
        data = (self.root / LEDGERS["foundation"]).read_bytes()
        self.write(LEDGERS["foundation"], data.replace(b'"schema_version": 2', b'"layers": [], "schema_version": 2', 1))
        with self.assertRaises(gate.ReadError):
            gate.evaluate(self.root, self.base, self.root, validators=lambda _root: [])


class SealedWinnerBindingTests(GateFixture):
    """Fourth review, G1: a winner's evidence_refs and pin are the sealed ones, and platform_status
    derives from receipts bound to the sealed pin and evidence_refs, never from the head winner's."""

    UNRELATED = "evidence/receipts/unrelated.json"

    def with_receipt(self, component_id, version):
        """Patch platform_status's context with one qualifying linux receipt for ``component_id`` at
        ``version`` (an independently reviewed native_proven install pass on a second machine), and
        write and register its file, so it is base-trusted when a rebase() follows (fifth review)."""
        real = gate.platform_evidence.load_context
        path = f"evidence/hosts/second-host/{component_id}.json"
        receipt = {"shape_ok": True, "platform_identity_ok": True, "component_version": version,
                   "evidence_class": "native_proven", "stage": "install", "result": "pass",
                   "second_physical_machine": True, "review_state": "agree", "host_id": "second-host",
                   "observed_at_utc": "2026-09-23T00:00:00Z", "path": path}
        self.write(path, dump({"component_id": component_id, "tool_versions": {component_id: version}}))
        self.register(path)

        def load(root):
            summary = {"components": {component_id: {"platforms": {"linux-wsl2-x86_64": {"receipts": [receipt]}}}}}
            return gate.platform_evidence.StatusContext(summary=summary, registered_paths=real(root).registered_paths)

        patcher = mock.patch.object(gate.platform_evidence, "load_context", load)
        patcher.start()
        self.addCleanup(patcher.stop)

    def unrelated_evidence(self):
        self.write(self.UNRELATED, b'{"unrelated": true}\n')
        self.register(self.UNRELATED)

    def test_forged_evidence_refs_raising_linux_to_accepted_fail(self):
        # native_proven with no registered ref derives linux 'conditional'; citing any registered
        # evidence/ file would derive 'accepted' from the head winner's own refs.
        self.unrelated_evidence()
        row = self.record(evidence_class="native_proven", linux="conditional")
        self.rebase()
        row["winners"][0]["evidence_refs"] = [self.UNRELATED]
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "changed")
        self.assertFails(report, f"winner comp-one: evidence_refs ['{self.UNRELATED}'] are not the sealed claude "
                                 "lane's winner_evidence_refs")
        self.assertIn("platform_status.linux-wsl2-x86_64 changed to 'accepted' but scripts/platform_status.py derives "
                      "'conditional'", self.messages(report))

    def test_sealed_evidence_refs_citing_registered_evidence_pass(self):
        # The cited evidence is at the base, registered with its sha256, before the row is recorded.
        self.unrelated_evidence()
        self.rebase()
        self.record(evidence_class="native_proven", evidence_refs=[self.UNRELATED], linux="accepted")
        self.assertPasses(self.report())

    def test_sealed_citation_to_evidence_added_with_the_row_fails(self):
        # Fifth review: the sealed citation resolves only because the same PR adds and registers the file.
        self.unrelated_evidence()
        self.record(evidence_class="native_proven", evidence_refs=[self.UNRELATED], linux="accepted")
        self.assertFails(self.report(), "platform_status.linux-wsl2-x86_64 changed to 'accepted', which the head's "
                                        "evidence derives, but only 'conditional'")

    def test_sealed_citation_absent_at_recording_added_later_cannot_raise_the_status(self):
        # Fifth review (G1 remainder): the sealed claude return cites evidence/new.json, which did not
        # exist when the row was recorded (record_verdicts.py dropped it, so the row's refs are []).
        # A PR adds and registers it, copies it into evidence_refs and raises linux to 'accepted':
        # build_winners at the head now writes that ref, and the head's registry registers it.
        new = "evidence/new.json"
        row = self.record(evidence_class="native_proven", evidence_refs=[new], linux="conditional")
        row["winners"][0]["evidence_refs"] = []
        self.rebase()
        self.write(new, b'{"new": true}\n')
        self.register(new)
        row["winners"][0]["evidence_refs"] = [new]
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "changed")
        self.assertFails(report, "changed to 'accepted', which the head's evidence derives, but only 'conditional'")
        self.assertIn(f"unregistered there: ['{new}']", self.messages(report))
        self.assertNotIn("are not the sealed claude lane's winner_evidence_refs", self.messages(report))

    def test_sealed_citation_whose_file_is_at_the_base_raises_the_status(self):
        # The positive twin: the file the sealed return cites is already at the base and registered.
        new = "evidence/new.json"
        self.write(new, b'{"new": true}\n')
        self.register(new)
        row = self.record(evidence_class="native_proven", evidence_refs=[new], linux="conditional")
        self.rebase()
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        self.assertPasses(self.report())

    def test_cited_evidence_rewritten_in_the_same_pull_request_cannot_raise_the_status(self):
        new = "evidence/new.json"
        self.write(new, b'{"new": true}\n')
        self.register(new)
        row = self.record(evidence_class="native_proven", evidence_refs=[new], linux="conditional")
        self.rebase()
        self.write(new, b'{"new": "rewritten"}\n')
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        self.assertFails(self.report(), "which the head's evidence derives, but only 'conditional'")

    def test_base_file_the_base_does_not_register_cannot_raise_the_status(self):
        new = "evidence/new.json"
        self.write(new, b'{"new": true}\n')
        row = self.record(evidence_class="native_proven", evidence_refs=[new], linux="conditional")
        self.rebase()
        self.register(new)
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        self.assertFails(self.report(), "which the head's evidence derives, but only 'conditional'")

    def test_pin_added_where_the_packet_has_none_fails(self):
        self.with_receipt("comp-two", "9.9")
        row = self.record(claude_keys=("c2",), codex_keys=("c2",))
        self.rebase()
        row["winners"][0].update(pin="9.9")
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertFails(report, "winner comp-two: pin '9.9' is not the one record_verdicts.py writes without a "
                                 "packet pin")
        self.assertIn("changed to 'accepted' but scripts/platform_status.py derives 'not_established'",
                      self.messages(report))

    def test_pin_added_with_a_matching_head_candidate_binds_no_receipt(self):
        # The head row's candidates carry the pin, so build_winners would write it; the base's row does
        # not, so it binds no receipt and the raised status fails.
        self.with_receipt("comp-two", "9.9")
        row = self.record(claude_keys=("c2",), codex_keys=("c2",))
        self.rebase()
        row["candidates"] = [{"repository": PACKET["candidates"][1]["repository"], "source_pin": "9.9"}]
        row["winners"][0].update(pin="9.9")
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertFails(report, "changed to 'accepted' but scripts/platform_status.py derives 'not_established'")
        self.assertIn("the sealed pin 'unpinned'", self.messages(report))
        # Sixth review: the fallback pin now comes from the base row's candidates, so a
        # candidates-only pin addition also fails the pin check and must land in its own PR.
        self.assertIn("pin '9.9' is not the one record_verdicts.py writes", self.messages(report))

    def test_pin_the_base_candidates_already_carry_binds_its_receipt(self):
        candidates = [{"repository": PACKET["candidates"][1]["repository"], "source_pin": "9.9"}]
        self.ledger["foundation"][0]["candidates"] = candidates
        self.with_receipt("comp-two", "9.9")
        self.rebase()
        del self.ledger["foundation"][0]
        row = self.record("alpha", claude_keys=("c2",), codex_keys=("c2",),
                          winners=[winner("comp-two", linux="accepted", pin="9.9")])
        row["candidates"] = candidates
        self.assertPasses(self.report())

    def test_candidates_pin_change_with_a_same_pr_receipt_keeping_the_status_fails(self):
        # Sixth review: the base row is accepted at pin 9.9 (a base receipt). The PR moves the head
        # row's candidates and winner to 9.10, adds a 9.10 receipt in the same PR and leaves the
        # declared status 'accepted' unchanged. The fallback pin comes from the base candidates, and
        # an unchanged status is re-derived because its pin changed.
        candidates = [{"repository": PACKET["candidates"][1]["repository"], "source_pin": "9.9"}]
        self.ledger["foundation"][0]["candidates"] = candidates
        self.with_receipt("comp-two", "9.9")
        self.rebase()
        del self.ledger["foundation"][0]
        row = self.record("alpha", claude_keys=("c2",), codex_keys=("c2",),
                          winners=[winner("comp-two", linux="accepted", pin="9.9")])
        row["candidates"] = candidates
        self.rebase()
        row["candidates"] = [{"repository": PACKET["candidates"][1]["repository"], "source_pin": "9.10"}]
        row["winners"][0].update(pin="9.10")
        self.with_receipt("comp-two", "9.10")
        report = self.report()
        self.assertEqual(report["status"], "failed", self.messages(report))
        self.assertIn("pin '9.10' is not", self.messages(report))

    def test_resealed_pin_behind_an_unchanged_accepted_status_is_rederived(self):
        # Sixth review: a re-recorded newest-wave row whose sealed packet moves comp-one from 1.0 to
        # 2.0 keeps the declared 'accepted' that a 1.0 receipt supported. The status is unchanged,
        # but its pin is not, so it is re-derived: no receipt is bound to 2.0.
        self.with_receipt("comp-one", "1.0")
        row = self.record(winners=[winner("comp-one", linux="accepted")])
        self.rebase()
        self.ledger["foundation"] = [r for r in self.ledger["foundation"] if r is not row]
        # The pin is a sealed candidate field (review of #145): the re-recorded wave's packet-keys moves it.
        self.record(keys={**KEYS, "c1": dict(KEYS["c1"], pin="2.0")},
                    winners=[winner("comp-one", linux="accepted", pin="2.0")])
        report = self.report()
        self.assertEqual(report["status"], "failed", self.messages(report))
        self.assertIn("derives 'not_established'", self.messages(report))
        self.assertIn("the sealed pin '2.0'", self.messages(report))

    def test_unchanged_status_with_changed_evidence_refs_is_rederived(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["evidence_refs"] = list(row["winners"][0].get("evidence_refs") or []) + ["evidence/forged.json"]
        report = self.report()
        self.assertEqual(report["status"], "failed", self.messages(report))

    def test_pin_changed_to_one_matching_an_unrelated_receipt_fails(self):
        self.with_receipt("comp-one", "3.0")
        row = self.record()
        self.rebase()
        row["winners"][0].update(pin="3.0")
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertFails(report, "winner comp-one: pin '3.0' is not the sealed packet's '1.0'")
        self.assertIn("derives 'not_established'", self.messages(report))
        self.assertIn("the sealed pin '1.0'", self.messages(report))

    def test_platform_only_upgrade_a_receipt_at_the_sealed_pin_supports_passes(self):
        row = self.record()
        self.with_receipt("comp-one", "1.0")
        self.rebase()
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "platform_status")
        self.assertPasses(report)

    def test_receipt_added_in_the_same_pull_request_cannot_raise_the_status(self):
        # Fifth review: the receipt lands with the status raise; it must be at the base first.
        row = self.record()
        self.rebase()
        self.with_receipt("comp-one", "1.0")
        row["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "accepted"
        report = self.report()
        self.assertEqual(report["changes"][0]["kind"], "platform_status")
        self.assertFails(report, "changed to 'accepted', which the head's evidence derives, but only "
                                 "'not_established'")
        self.assertIn("evidence/hosts/second-host/comp-one.json", self.messages(report))

    def test_winner_with_a_key_build_winners_does_not_write_fails(self):
        row = self.record()
        self.rebase()
        row["winners"][0]["accepted_by"] = "maintainer"
        self.assertFails(self.report(), "winner comp-one: carries ['accepted_by'], which record_verdicts.build_winners "
                                        "does not write")


class CanonicalIndexBindingTests(GateFixture):
    """Fourth review, G3: the canonical repository index is a head-side rule input of the derived
    alternatives and status, so a changed row must derive the same with the base's index."""

    def test_index_edit_that_empties_the_alternatives_cannot_withdraw_a_verdict(self):
        row = self.record()
        self.rebase()
        index = json.loads((self.root / INDEX).read_bytes())
        index["records"] = [record for record in index["records"] if record["repository"] != ALTERNATIVE["repository"]]
        self.write(INDEX, dump(index))
        row.update(verdict_status="pending_lanes", winners=[], alternatives=[], verdict_overturn_when="")
        self.assertFails(self.report(), "derives other alternatives for this row than the base's")

    def test_index_edit_that_does_not_change_the_row_passes(self):
        row = self.record()
        self.rebase()
        index = json.loads((self.root / INDEX).read_bytes())
        index["records"].append({"repository": "https://github.com/example/unrelated"})
        self.write(INDEX, dump(index))
        row["open_gaps"] = ["edited"]
        self.assertPasses(self.report())

    def test_the_gates_index_reader_matches_record_verdicts(self):
        import record_verdicts
        self.flush()
        self.assertEqual(gate.canonical_index(gate.Side(self.root)), record_verdicts.load_canonical_index(self.root))
        self.assertEqual(gate.canonical_index(gate.Side(self.root, self.base)),
                         record_verdicts.load_canonical_index(self.root))

    def test_platform_profiles_change_with_a_verdict_change_fails_the_trust_rule(self):
        self.write("adoption/manifest.json", dump({"platform_profiles": [{"id": "macos-arm64", "os": "darwin",
                                                                          "architecture": "arm64"}]}))
        self.rebase()
        self.write("adoption/manifest.json", dump({"platform_profiles": [{"id": "macos-arm64", "os": "linux",
                                                                          "architecture": "x86_64"}]}))
        self.record()
        report = self.report()
        self.assertFails(report, "also the gate's trust base (adoption/manifest.json#/platform_profiles)")
        self.assertEqual(report["rule_inputs_changed"], ["adoption/manifest.json#/platform_profiles"])

    def test_other_adoption_manifest_changes_are_data(self):
        self.write("adoption/manifest.json", dump({"platform_profiles": [], "components": []}))
        self.rebase()
        self.write("adoption/manifest.json", dump({"platform_profiles": [], "components": ["new"]}))
        self.record()
        self.assertPasses(self.report())


class SingleLaneBaseTests(GateFixture):
    """Fourth review, G2: a single-lane authorization is byte-identical at the base, so it cannot be
    added or edited in the pull request that adds the row it authorizes."""

    def test_authorization_added_in_the_same_pull_request_fails(self):
        self.decision("single-lane-authorization: foundation/beta\n")
        self.record(codex=False, single_lane=DECISION)
        report = self.report()
        self.assertFails(report, f"lanes.single_lane_decision '{DECISION}' is not at the base")
        self.assertIn("verdict_status is 'recorded' but record_verdicts.py writes 'pending_lanes'", self.messages(report))

    def test_authorization_edited_in_the_same_pull_request_fails(self):
        self.decision("single-lane-authorization: foundation/alpha\n")
        self.rebase()
        self.decision("single-lane-authorization: foundation/alpha\nsingle-lane-authorization: foundation/beta\n")
        self.record(codex=False, single_lane=DECISION)
        self.assertFails(self.report(), f"lanes.single_lane_decision '{DECISION}' differs from its base copy")

    def test_authorization_present_at_the_base_passes(self):
        self.decision("single-lane-authorization: foundation/beta\n")
        self.rebase()
        self.record(codex=False, single_lane=DECISION)
        self.assertPasses(self.report())


class BaseTreeReadTests(GateFixture):
    """Third review, finding 3 (re-checked): a failing base tree listing is a read error, not an absent file."""

    def test_directory_at_the_base_is_not_a_file(self):
        self.assertIsNone(gate.Side(self.root, self.base).read("catalogs/landscape"))
        self.assertIsNone(gate.Side(self.root, self.base).read("catalogs/landscape/absent.json"))
        self.assertIsNotNone(gate.Side(self.root, self.base).read(MANIFEST))

    def test_failing_ls_tree_is_a_read_error_and_exits_2(self):
        real = gate.git

        def failing(root, *args, check=True):
            if args and args[0] == "ls-tree":
                return subprocess.CompletedProcess(args, 128, b"", b"fatal: stubbed failure")
            return real(root, *args, check=check)

        with mock.patch.object(gate, "git", failing), contextlib.redirect_stdout(io.StringIO()) as output:
            code = gate.main(["--root", str(self.root), "--base", self.base])
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn("cannot list", output.getvalue())


class MergeBaseTests(GateFixture):
    """Fifth review (round-three low re-checked): merge_base falls back to the base only when git
    reports no common history, and any other git failure exits 2."""

    def test_git_failure_finding_the_merge_base_raises(self):
        real = gate.git

        def failing(root, *args, check=True):
            if args and args[0] == "merge-base":
                return subprocess.CompletedProcess(args, 128, b"", b"fatal: stubbed failure")
            return real(root, *args, check=check)

        with mock.patch.object(gate, "git", failing):
            with self.assertRaises(gate.RevisionError):
                gate.merge_base(self.root, self.base, self.base)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = gate.main(["--root", str(self.root), "--base", self.base])
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn("git merge-base", output.getvalue())

    def test_unrelated_history_compares_with_the_base_itself(self):
        self.git("checkout", "--quiet", "--orphan", "unrelated")
        self.git("commit", "--quiet", "--allow-empty", "-m", "unrelated root")
        unrelated = self.git("rev-parse", "HEAD")
        self.assertEqual(gate.merge_base(self.root, self.base, unrelated), self.base)


class SotaManifestFreezeTests(GateFixture):
    """Fifth review: a registered wave's SOTA manifest (the source of its published sota_components)
    is frozen, the newest wave's included."""

    NEWEST = f"catalogs/sota-convergence/manifest-{RUN}.json"

    def registered_wave(self):
        self.write(self.NEWEST, dump({"foundation": [{"id": "beta", "components": [{"pin": "1.0",
                                                                                    "review_status": "reviewed"}]}]}))
        row = self.record()
        self.rebase()
        return row

    def test_newest_wave_manifest_edited_fails(self):
        self.registered_wave()
        self.write(self.NEWEST, dump({"foundation": [{"id": "beta", "components": [{"pin": "1.0",
                                                                                    "review_status": "accepted"}]}]}))
        self.assertFails(self.report(), f"the SOTA manifest {self.NEWEST} registered by wave {RUN} was changed")

    def test_newest_wave_manifest_pointer_moved_fails(self):
        self.registered_wave()
        other = "catalogs/sota-convergence/manifest-other.json"
        self.write(other, b'{"foundation": []}\n')
        self.waves[RUN]["manifest"] = other
        self.assertFails(self.report(), f"the registered SOTA manifest of wave {RUN} moved from {self.NEWEST}")

    def test_grandfathered_wave_manifest_edited_fails(self):
        path = "catalogs/sota-convergence/manifest-20260922.json"
        self.write(path, b'{"foundation": []}\n')
        self.rebase()
        self.write(path, b'{"foundation": [{"id": "alpha"}]}\n')
        self.assertFails(self.report(), f"the SOTA manifest {path} registered by wave 20260922 was changed")

    def test_reformatted_newest_wave_manifest_passes(self):
        self.registered_wave()
        data = json.loads((self.root / self.NEWEST).read_bytes())
        self.write(self.NEWEST, json.dumps(data).encode())
        self.assertPasses(self.report())


class TrustPathDerivationTests(unittest.TestCase):
    """Review of #123, finding 4, and fourth review G3: TRUST_PATHS covers every repository module the
    gate and the validators import (transitively) and every head-side rule input they read, derived
    from the modules (an ast walk of the imports) and from what they actually open (a sys.addaudithook
    recording every read while the gate judges a fixture and the validators check this checkout)."""

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

    # Runs in a subprocess: an audit hook cannot be removed once added. It records every file opened
    # for reading under the data root and every module imported from the repository.
    READ_TRACER = r"""
import json, os, runpy, sys
repository, data_root, mode, *rest = sys.argv[1:]
repository, data_root = os.path.realpath(repository), os.path.realpath(data_root)
reads = set()

def hook(event, args):
    if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    flags = args[1] if len(args) > 1 else "r"
    if isinstance(flags, str) and any(char in flags for char in "wax+"):
        return
    if flags is None and len(args) > 2 and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
        return
    path = os.path.realpath(os.fsdecode(args[0]))
    if path.startswith(data_root + os.sep) and "__pycache__" not in path:
        reads.add(os.path.relpath(path, data_root))

sys.path[:0] = [repository, os.path.join(repository, "tools", "sota-convergence")]
sys.addaudithook(hook)
code = 0
if mode == "gate":
    from scripts import verdict_review_gate as gate
    report = gate.evaluate(data_root, rest[0], data_root, validators=None)
    code = report["violations"]
else:
    sys.path.insert(0, os.path.dirname(os.path.join(repository, mode)))
    sys.argv = [os.path.join(repository, mode), *rest]
    try:
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as error:
        code = error.code
modules = sorted({os.path.relpath(os.path.realpath(module.__file__), repository) for module in list(sys.modules.values())
                  if getattr(module, "__file__", None)
                  and os.path.realpath(module.__file__).startswith(repository + os.sep)})
print(json.dumps({"code": code, "reads": sorted(reads), "modules": modules}))
"""

    def trace(self, data_root, mode, *arguments):
        import sys
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        result = subprocess.run([sys.executable, "-c", self.READ_TRACER, str(self.ROOT), str(data_root), mode,
                                 *map(str, arguments)], capture_output=True, text=True, env=environment,
                                cwd=str(self.ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    @staticmethod
    def bound(path):
        return path in gate.TRUST_PATHS or any(path == prefix or path.startswith(prefix)
                                               for prefix, _why in gate.HEAD_DATA_BINDINGS)

    def test_every_head_side_file_the_gate_reads_is_a_trust_path_or_bound_verdict_data(self):
        # A fixture that reaches every RowCheck path: an agreeing row, an adjudicated disagreement and
        # an authorized single-lane row (its decision record at the base), with the rules' own inputs
        # absent so that their attempted reads are recorded too.
        fixture = GateFixture("setUp")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.decision("single-lane-authorization: foundation/delta\n")
        fixture.rebase()
        fixture.record("beta")
        fixture.record("gamma", claude_keys=("c1",), codex_keys=("c2",), judged=adjudication())
        fixture.record("delta", codex=False, single_lane=DECISION)
        fixture.assertPasses(fixture.report())
        traced = self.trace(fixture.root, "gate", fixture.base)
        self.assertEqual(traced["code"], [])
        unbound = sorted(path for path in traced["reads"] if not self.bound(path))
        self.assertEqual(unbound, [], "a head-side read that is neither a trust path nor bound verdict data")
        # Non-vacuous: the reads include the rule inputs each binding names.
        for path in (INDEX, DECISION, MANIFEST, f"{SEALED}/run-manifest.json", f"{SEALED}/packets/foundation__beta.json",
                     f"{SEALED}/adjudication/foundation-gamma-{RUN}.json", "manifests/evidence.json",
                     "adoption/manifest.json"):
            self.assertIn(path, traced["reads"])
        self.assertEqual(sorted(set(traced["modules"]) - set(gate.TRUST_PATHS)), [])

    def test_every_rule_input_the_validators_read_from_this_checkout_is_a_trust_path(self):
        # The validators can only add failures to the gate's own verdict, so their catalog data reads
        # are not rule inputs; their code, schemas and tool registries are.
        for script, *arguments in (("scripts/landscape.py", "--root", self.ROOT),
                                   ("tools/sota-convergence/build_verdicts.py", "--check", "--root", self.ROOT)):
            with self.subTest(script):
                traced = self.trace(self.ROOT, script, *arguments)
                self.assertEqual(traced["code"], 0, script)
                rules = sorted(path for path in traced["reads"] + traced["modules"] + [script]
                               if path.endswith((".py", ".schema.json")) and path.startswith(("scripts/", "tools/"))
                               or path.endswith(".schema.json")
                               or path.startswith(("tools/", ".github/")) and not path.endswith(".py"))
                self.assertTrue(rules)
                self.assertEqual(sorted(set(rules) - set(gate.TRUST_PATHS)), [], script)

    def test_rule_inputs_named_by_the_modules_are_trust_paths(self):
        from scripts import host_receipts, landscape
        import record_verdicts
        inputs = {landscape.LANE_PROVENANCE_REGISTRY, host_receipts.SCHEMA_RELATIVE_PATH,
                  Path(record_verdicts.SCHEMA_PATH).resolve().relative_to(self.ROOT).as_posix()}
        self.assertEqual(sorted(inputs - set(gate.TRUST_PATHS)), [])
        for path in gate.TRUST_PATHS:
            self.assertTrue((self.ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
