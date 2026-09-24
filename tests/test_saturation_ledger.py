"""Tests for scripts/saturation_ledger.py and .github/workflows/saturation-tracking.yml.

Three groups: the consecutive-clean arithmetic (pure ``derive`` fixtures), integrity (hash chain,
survivor-to-manifest binding, both votes with survival recomputed, usage registration) in a
synthetic fixture checkout, and separation (the ledger never writes research-state.json or any
verdict path). The committed ledger is checked against this checkout, and its seed is re-derived
from the retained files and compared byte for byte.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import saturation_ledger as sl  # noqa: E402

from tests.test_workflow_hardening import first_step, jobs, permission_blocks  # noqa: E402

REQ = "a" * 64
PLAT = "b" * 64
WORKFLOW = ROOT / ".github/workflows/saturation-tracking.yml"


# --------------------------------------------------------------------------- arithmetic


def layer(layer_id="alpha", *, votes="retained", survived=(), reopen=(), req=REQ, plat=PLAT, catalog="foundation"):
    return {"catalog": catalog, "layer_id": layer_id, "requirement_sha256": req, "platform_profiles_sha256": plat,
            "votes": votes, "proposed": [], "known": [], "new": [],
            "survived": [{"repo": repo} for repo in survived], "refuted": [],
            "reopen": [{"trigger": trigger, "ref": "fixture"} for trigger in reopen]}


def sweep(sweep_id, day, *layers, status="completed"):
    return {"sweep_id": sweep_id, "date": day, "status": status, "layers": list(layers) or [layer()]}


def ledger_of(*sweeps):
    return {"schema_version": 1, "policy": {"K": 3, "min_gap_days": 7}, "sweeps": list(sweeps)}


KEY = ("foundation", "alpha")


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return sl.main(argv)


class ArithmeticTests(unittest.TestCase):
    def state(self, *sweeps, current=None):
        return sl.derive(ledger_of(*sweeps), current)[KEY]

    def test_three_clean_sweeps_seven_days_apart_become_a_candidate(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"), sweep("s3", "2026-10-15"))
        self.assertEqual(entry["count"], 3)
        self.assertTrue(entry["saturation_candidate"])
        self.assertEqual(entry["counted_sweeps"], ["s1", "s2", "s3"])

    def test_two_clean_sweeps_are_not_a_candidate(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"))
        self.assertEqual(entry["count"], 2)
        self.assertFalse(entry["saturation_candidate"])

    def test_same_day_sweeps_count_once(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-01"), sweep("s3", "2026-10-01"))
        self.assertEqual(entry["count"], 1)
        self.assertFalse(entry["saturation_candidate"])

    def test_sweeps_closer_than_the_gap_neither_count_nor_reset(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-05"), sweep("s3", "2026-10-08"),
                           sweep("s4", "2026-10-15"))
        self.assertEqual(entry["counted_sweeps"], ["s1", "s3", "s4"])
        self.assertTrue(entry["saturation_candidate"])

    def test_a_stopped_run_neither_counts_nor_resets(self):
        stopped_with_survivor = sweep("x", "2026-10-09", layer(survived=["https://github.com/o/r"]), status="stopped")
        entry = self.state(sweep("s1", "2026-10-01"), stopped_with_survivor, sweep("s2", "2026-10-08"),
                           sweep("s3", "2026-10-15"))
        self.assertEqual(entry["count"], 3)
        self.assertTrue(entry["saturation_candidate"])
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                           sweep("x", "2026-10-15", status="stopped"))
        self.assertEqual(entry["count"], 2)
        self.assertFalse(entry["saturation_candidate"])

    def test_a_survivor_resets_the_count(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                           sweep("s3", "2026-10-15", layer(survived=["https://github.com/o/r"])),
                           sweep("s4", "2026-10-22"))
        self.assertEqual(entry["count"], 1)
        self.assertFalse(entry["saturation_candidate"])

    def test_a_reopen_entry_resets_the_count(self):
        for trigger in sl.REOPEN_TRIGGERS:
            with self.subTest(trigger=trigger):
                entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                                   sweep("s3", "2026-10-15", layer(reopen=[trigger])))
                self.assertEqual(entry["count"], 0)

    def test_a_changed_requirement_hash_resets_the_count(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                           sweep("s3", "2026-10-15", layer(req="c" * 64)))
        self.assertEqual(entry["count"], 1)
        self.assertEqual(entry["reset"][0]["trigger"], "requirement_changed")
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"), sweep("s3", "2026-10-15"),
                           current={"requirements": {KEY: "c" * 64}})
        self.assertEqual(entry["count"], 0)
        self.assertFalse(entry["saturation_candidate"])

    def test_a_new_platform_profile_resets_the_count(self):
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                           sweep("s3", "2026-10-15", layer(plat="d" * 64)))
        self.assertEqual(entry["count"], 1)
        entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"), sweep("s3", "2026-10-15"),
                           current={"platform_profiles_sha256": "d" * 64})
        self.assertEqual(entry["count"], 0)
        self.assertEqual(entry["current_triggers"][0]["trigger"], "platform_profile_changed")

    def test_pin_moved_or_stale_receipt_flags_reset_the_count(self):
        manifest = {"foundation": [{"layer": "alpha", "components": [{"id": "tool", "repository": "https://github.com/o/tool"}]}],
                    "trading": []}
        for flag, trigger in (("pin_moved", "pin_moved"), ("stale", "stale_receipt")):
            with self.subTest(flag=flag):
                staleness = {"rows": [{"platform_id": "linux", "component_id": "tool", "flags": [flag]}]}
                triggers, _ = sl.external_triggers(manifest, staleness, None)
                self.assertEqual(triggers[KEY][0]["trigger"], trigger)
                entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"), sweep("s3", "2026-10-15"),
                                   current={"triggers": triggers})
                self.assertEqual(entry["count"], 0)
                self.assertFalse(entry["saturation_candidate"])
        staleness = {"rows": [{"platform_id": "linux", "component_id": "tool", "flags": ["no_bound_receipt"]}]}
        self.assertEqual(sl.external_triggers(manifest, staleness, None)[0], {})

    def test_an_archived_renamed_or_relicensed_selection_is_a_reopen_trigger(self):
        before = {"foundation": [{"layer": "alpha", "components": [
            {"id": "tool", "repository": "https://github.com/o/tool",
             "upstream": {"license": "MIT", "archived": False, "renamed_to": None}}]}], "trading": []}
        for change in ({"archived": True}, {"renamed_to": "https://github.com/n/tool"}, {"license": "BUSL-1.1"}):
            with self.subTest(change=change):
                after = copy.deepcopy(before)
                after["foundation"][0]["components"][0]["upstream"].update(change)
                triggers, _ = sl.external_triggers(before, None, after)
                self.assertEqual(triggers[KEY][0]["trigger"], "selection_changed")
        self.assertEqual(sl.external_triggers(before, None, copy.deepcopy(before))[0], {})
        # A state the baseline already recorded is not a new trigger.
        standing = copy.deepcopy(before)
        standing["foundation"][0]["components"][0]["upstream"].update(archived=True, renamed_to="https://github.com/n/tool")
        self.assertEqual(sl.external_triggers(standing, None, copy.deepcopy(standing))[0], {})

    def test_votes_not_retained_is_never_clean(self):
        for votes in ("not_retained", "not_returned"):
            with self.subTest(votes=votes):
                entry = self.state(sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"),
                                   sweep("s3", "2026-10-15", layer(votes=votes)))
                self.assertEqual(entry["count"], 0)

    def test_layers_are_counted_independently(self):
        state = sl.derive(ledger_of(
            sweep("s1", "2026-10-01", layer(), layer("beta")),
            sweep("s2", "2026-10-08", layer(), layer("beta", survived=["https://github.com/o/r"])),
            sweep("s3", "2026-10-15", layer())))
        self.assertTrue(state[KEY]["saturation_candidate"])
        self.assertEqual(state[("foundation", "beta")]["count"], 0)


# --------------------------------------------------------------------------- fixture checkout


LANE = "fx-lane"
MANIFEST = "catalogs/sota-convergence/manifest-fx.json"
USAGE = "evidence/artifacts/fx/child-usage-complete.json"
USAGE_PARTIAL = "evidence/artifacts/fx/child-usage-partial.json"
VOTES = "evidence/artifacts/fx/votes.json"
REVIEW = "evidence/artifacts/fx/o-surv.json"
SURV, REF, OTHER = "https://github.com/o/surv", "https://github.com/o/ref", "https://github.com/o/other"
# The retained per-vote returns the fixture cites (one file, one object per vote).
VOTE_DATA = {
    "surv": {"facts": {"refuted": False}, "fit": {"refuted": False}},
    "ref": {"facts": {"refuted": False}, "fit": {"refuted": True}},
    "beta": {"facts": {"refuted": True}, "fit": {"refuted": True}},
}


def write(root: Path, relative: str, value) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1) + "\n", encoding="utf-8")


def register(root: Path) -> None:
    files = []
    for relative in (MANIFEST, USAGE, USAGE_PARTIAL, VOTES, REVIEW, "evidence/artifacts/fx/other-review.json"):
        raw = (root / relative).read_bytes()
        files.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    write(root, sl.EVIDENCE, {"schema_version": 1, "receipts": [], "files": sorted(files, key=lambda f: f["path"])})


def build_fixture(root: Path) -> None:
    write(root, sl.RESEARCH_STATE, {"schema_version": 1, "layers": [
        {"catalog": "foundation", "layer_id": "alpha", "status": "comparison_required",
         "next_action": "compare alpha", "decision_ref": "catalogs/landscape/foundation.json"},
        {"catalog": "us-equities", "layer_id": "beta", "status": "on_requirement_change",
         "next_action": "compare beta", "decision_ref": "catalogs/landscape/trading.json"}]})
    write(root, sl.ADOPTION, {"platform_profiles": [{"id": "linux-x86_64", "os": "linux"}]})

    def row(repo, survives):
        return {"repository": repo, "lane": LANE, "disposition": "targeted_candidate" if survives else "refuted",
                "adversarial_verification": {"survives": survives, "votes": [
                    {"lens": 0, "refuted": False}, {"lens": 1, "refuted": not survives}]}}

    write(root, MANIFEST, {
        "checked_at": "2026-10-01",
        "foundation": [{"layer": "alpha", "components": [{"id": "sel", "repository": "https://github.com/o/sel"}],
                        "alternatives_keep_but_compare": [{"repository": OTHER}],
                        "candidates": [row(SURV, True), row(REF, False)]}],
        "trading": [{"layer": "beta", "entries": [], "candidates": [row("https://github.com/o/beta", False)]}],
    })
    write(root, USAGE, {"child_usage": {"status": "complete"}})
    write(root, USAGE_PARTIAL, {"child_usage": {"status": "incomplete"}})
    write(root, VOTES, VOTE_DATA)
    write(root, REVIEW, {"repository": SURV, "layers": ["alpha"]})
    write(root, "evidence/artifacts/fx/other-review.json", {"repository": OTHER, "layers": ["alpha"]})
    register(root)
    write(root, sl.LEDGER, sl.dump(sl.empty_ledger()))


def vote(name, role):
    return {"vote": "refuted" if VOTE_DATA[name][role]["refuted"] else "not_refuted", "ref": f"{VOTES}#/{name}/{role}"}


def result(sweep_id="fx-1", day="2026-10-01", **overrides):
    value = {
        "sweep_id": sweep_id, "date": day, "workflow_run": f"wf_{sweep_id}", "status": "completed",
        "manifest_ref": MANIFEST, "lane": LANE, "prompts_sha256": "c" * 64, "usage_ref": USAGE,
        "lower_bound_usage": False,
        "layers": [
            {"catalog": "foundation", "layer_id": "alpha", "votes": "retained", "calls": {"web_search": 2},
             "proposed": [SURV, REF],
             "survived": [{"repo": SURV, "source_review": REVIEW, "facts": vote("surv", "facts"), "fit": vote("surv", "fit")}],
             "refuted": [{"repo": REF, "facts": vote("ref", "facts"), "fit": vote("ref", "fit")}],
             "reopen": []},
            {"catalog": "us-equities", "layer_id": "beta", "votes": "retained", "calls": None,
             "proposed": ["https://github.com/o/beta"], "survived": [],
             "refuted": [{"repo": "https://github.com/o/beta", "facts": vote("beta", "facts"), "fit": vote("beta", "fit")}],
             "reopen": []},
        ],
    }
    value.update(overrides)
    return value


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        build_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def ledger(self):
        return json.loads((self.root / sl.LEDGER).read_text(encoding="utf-8"))

    def appended(self, *results):
        ledger = self.ledger()
        for item in results:
            ledger = sl.append(self.root, ledger, item)
        return ledger

    def assertErrorMatches(self, ledger, pattern):
        errors = sl.check_ledger(self.root, ledger)
        self.assertTrue(any(re.search(pattern, error) for error in errors), errors)


class IntegrityTests(FixtureCase):
    def test_a_valid_sweep_appends_and_checks(self):
        ledger = self.appended(result())
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        record = ledger["sweeps"][0]
        self.assertEqual(record["prev_sha256"], sl.genesis_sha256(ledger))
        self.assertEqual(ledger["head_sha256"], sl.record_sha256(record))
        alpha = record["layers"][0]
        self.assertEqual(alpha["known"], [])
        self.assertEqual(alpha["new"], [SURV, REF])

    def test_editing_an_earlier_sweep_breaks_the_hash_chain(self):
        ledger = self.appended(result(), result("fx-2", "2026-10-08"))
        edited = copy.deepcopy(ledger)
        edited["sweeps"][0]["workflow_run"] = "wf_forged"
        self.assertErrorMatches(edited, r"sweeps\[1\]: prev_sha256 breaks the hash chain")

    def test_deleting_a_sweep_breaks_the_chain_or_the_head(self):
        ledger = self.appended(result(), result("fx-2", "2026-10-08"))
        first_removed = copy.deepcopy(ledger)
        del first_removed["sweeps"][0]
        self.assertErrorMatches(first_removed, r"prev_sha256 breaks the hash chain")
        last_removed = copy.deepcopy(ledger)
        del last_removed["sweeps"][-1]
        self.assertErrorMatches(last_removed, r"head_sha256 does not match")

    def test_changing_the_policy_breaks_the_chain(self):
        ledger = self.appended(result())
        ledger["policy"]["K"] = 1
        self.assertErrorMatches(ledger, r"prev_sha256 breaks the hash chain")

    def test_append_refuses_to_rewrite_history(self):
        ledger = self.appended(result())
        with self.assertRaisesRegex(sl.LedgerError, "already recorded"):
            sl.append(self.root, ledger, result())
        with self.assertRaisesRegex(sl.LedgerError, "computed field prev_sha256"):
            sl.append(self.root, ledger, result("fx-2", "2026-10-08", prev_sha256="0" * 64))
        broken = copy.deepcopy(ledger)
        broken["sweeps"][0]["date"] = "2026-09-30"
        with self.assertRaisesRegex(sl.LedgerError, "existing ledger does not check"):
            sl.append(self.root, broken, result("fx-2", "2026-10-08"))

    def test_a_rechained_rewrite_is_caught_against_the_base_commit(self):
        if shutil.which("git") is None:
            self.skipTest("git unavailable")
        ledger = self.appended(result(), result("fx-2", "2026-10-08"))
        (self.root / sl.LEDGER).write_text(sl.dump(ledger), encoding="utf-8")
        git = ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
        # A forger edits the first record and recomputes every hash: the chain is internally
        # consistent again, so only the comparison with the base commit catches it.
        forged = copy.deepcopy(ledger)
        forged["sweeps"][0]["workflow_run"] = "wf_forged"
        previous = sl.genesis_sha256(forged)
        for record in forged["sweeps"]:
            record["prev_sha256"] = previous
            previous = sl.record_sha256(record)
        forged["head_sha256"] = previous
        self.assertEqual(sl.check_ledger(self.root, forged), [])
        self.assertTrue(sl.check_append_only(self.root, forged, "HEAD"))
        extended = sl.append(self.root, ledger, result("fx-3", "2026-10-15"))
        self.assertEqual(sl.check_append_only(self.root, extended, "HEAD"), [])

    def test_survivor_must_bind_to_a_surviving_manifest_lane_row(self):
        ledger = self.appended(result())
        wrong_repo = copy.deepcopy(ledger)
        entry = wrong_repo["sweeps"][0]["layers"][0]["survived"][0]
        entry["repo"] = OTHER
        wrong_repo["sweeps"][0]["layers"][0]["proposed"] = [OTHER, REF]
        self.assertErrorMatches(sl_rechain(wrong_repo), r"survivor https://github.com/o/other has no fx-lane row")
        refuted_row = self.ledger()
        manifest = json.loads((self.root / MANIFEST).read_text())
        manifest["foundation"][0]["candidates"][0]["adversarial_verification"]["survives"] = False
        write(self.root, MANIFEST, manifest)
        register(self.root)
        with self.assertRaises(sl.LedgerError):
            sl.append(self.root, refuted_row, result(manifest_ref=MANIFEST))

    def test_survivor_needs_a_registered_source_review_of_the_same_repository(self):
        ledger = self.appended(result())
        missing = copy.deepcopy(ledger)
        missing["sweeps"][0]["layers"][0]["survived"][0]["source_review"] = "evidence/artifacts/fx/absent.json"
        self.assertErrorMatches(sl_rechain(missing), r"absent\.json does not exist")
        other = copy.deepcopy(ledger)
        other["sweeps"][0]["layers"][0]["survived"][0]["source_review"] = "evidence/artifacts/fx/other-review.json"
        self.assertErrorMatches(sl_rechain(other), r"reviews a different repository")
        write(self.root, "evidence/artifacts/fx/unregistered.json", {"repository": SURV, "layers": ["alpha"]})
        unregistered = copy.deepcopy(ledger)
        unregistered["sweeps"][0]["layers"][0]["survived"][0]["source_review"] = "evidence/artifacts/fx/unregistered.json"
        self.assertErrorMatches(sl_rechain(unregistered), r"is not registered")

    def test_both_votes_are_required(self):
        ledger = self.appended(result())
        for role in ("facts", "fit"):
            with self.subTest(role=role):
                missing = copy.deepcopy(ledger)
                del missing["sweeps"][0]["layers"][0]["refuted"][0][role]
                self.assertErrorMatches(sl_rechain(missing), rf"{role} vote required")

    def test_survival_is_recomputed_from_the_votes(self):
        ledger = self.appended(result())
        # Listed as survived, but a vote refutes it (and the vote file agrees).
        layer_ = copy.deepcopy(ledger)
        alpha = layer_["sweeps"][0]["layers"][0]
        alpha["survived"].append(dict(alpha["refuted"].pop(0), source_review=REVIEW))
        self.assertErrorMatches(sl_rechain(layer_), r"listed as survived but its votes give refuted")
        # A vote that disagrees with the retained return it cites.
        flipped = copy.deepcopy(ledger)
        flipped["sweeps"][0]["layers"][0]["refuted"][0]["fit"]["vote"] = "not_refuted"
        errors = sl.check_ledger(self.root, sl_rechain(flipped))
        self.assertTrue(any("disagrees with evidence/artifacts/fx/votes.json#/ref/fit" in e for e in errors), errors)
        self.assertTrue(any("listed as refuted but its votes give survived" in e for e in errors), errors)

    def test_a_completed_sweep_must_adjudicate_every_manifest_lane_row(self):
        ledger = self.appended(result())
        partial = copy.deepcopy(ledger)
        partial["sweeps"][0]["layers"][0]["refuted"] = []
        self.assertErrorMatches(sl_rechain(partial), r"must adjudicate every proposal")

    def test_completed_sweep_needs_registered_complete_usage(self):
        with self.assertRaisesRegex(sl.LedgerError, "complete usage"):
            sl.append(self.root, self.ledger(), result(usage_ref=USAGE_PARTIAL))
        with self.assertRaisesRegex(sl.LedgerError, "must not be a lower bound"):
            sl.append(self.root, self.ledger(), result(lower_bound_usage=True))
        write(self.root, "evidence/artifacts/fx/unregistered-usage.json", {"child_usage": {"status": "complete"}})
        with self.assertRaisesRegex(sl.LedgerError, "is not registered"):
            sl.append(self.root, self.ledger(), result(usage_ref="evidence/artifacts/fx/unregistered-usage.json"))
        ledger = self.appended(result())
        write(self.root, USAGE, {"child_usage": {"status": "complete"}, "edited": True})
        self.assertErrorMatches(ledger, r"differs from its manifests/evidence.json registration")

    def test_stopped_sweep_must_mark_lower_bound_usage(self):
        stopped = result(status="stopped", usage_ref=USAGE_PARTIAL, lower_bound_usage=False,
                         layers=[{"catalog": "foundation", "layer_id": "alpha", "votes": "not_returned",
                                  "votes_note": "stopped before any refuter returned", "calls": None,
                                  "proposed": [SURV], "survived": [], "refuted": [], "reopen": []}])
        with self.assertRaisesRegex(sl.LedgerError, "lower_bound_usage"):
            sl.append(self.root, self.ledger(), stopped)
        stopped["lower_bound_usage"] = True
        ledger = sl.append(self.root, self.ledger(), stopped)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        # The stopped run's proposals were never adjudicated, so they stay new in a later sweep.
        ledger = sl.append(self.root, ledger, result("fx-2", "2026-10-08"))
        self.assertEqual(ledger["sweeps"][1]["layers"][0]["new"], [SURV, REF])
        ledger = sl.append(self.root, ledger, result("fx-3", "2026-10-15"))
        self.assertEqual(ledger["sweeps"][2]["layers"][0]["known"], [SURV, REF])

    def test_not_retained_votes_need_a_note(self):
        missing_note = result()
        missing_note["layers"][1]["votes"] = "not_retained"
        with self.assertRaisesRegex(sl.LedgerError, "needs a votes_note"):
            sl.append(self.root, self.ledger(), missing_note)

    def test_command_line_append_check_and_report(self):
        path = self.root.parent / f"{self.root.name}-result.json"
        try:
            path.write_text(json.dumps(result()), encoding="utf-8")
            self.assertEqual(quiet_main(["--root", str(self.root), "--append", str(path)]), 0)
            self.assertEqual(quiet_main(["--root", str(self.root), "--check"]), 0)
            self.assertEqual(quiet_main(["--root", str(self.root), "--append", str(path)]), 2)
        finally:
            path.unlink(missing_ok=True)
        report = sl.build_report(self.root, self.ledger())
        self.assertIn("foundation/alpha", report["due"])
        self.assertEqual(report["saturation_candidates"], [])
        self.assertIn("Saturation tracking", sl.render_markdown(report))


def sl_rechain(ledger):
    """Recompute prev/head hashes so a test isolates the non-chain check it exercises."""
    ledger = copy.deepcopy(ledger)
    previous = sl.genesis_sha256(ledger)
    for record in ledger["sweeps"]:
        record["prev_sha256"] = previous
        previous = sl.record_sha256(record)
    ledger["head_sha256"] = previous
    return ledger


# --------------------------------------------------------------------------- separation


class SeparationTests(FixtureCase):
    def test_append_never_writes_research_state_or_verdict_paths(self):
        protected = {relative: (self.root / relative).read_bytes()
                     for relative in (sl.RESEARCH_STATE, sl.ADOPTION, sl.EVIDENCE, MANIFEST)}
        writes = []

        def hook(event, args):
            if event == "open" and recording and isinstance(args[0], (str, Path)):
                mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
                flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
                if any(ch in mode for ch in "wax+") or flags & 0o3:
                    writes.append(str(args[0]))

        recording = True
        sys.addaudithook(hook)
        try:
            path = self.root.parent / f"{self.root.name}-sep.json"
            path.write_text(json.dumps(result()), encoding="utf-8")
            writes.clear()
            self.assertEqual(quiet_main(["--root", str(self.root), "--append", str(path)]), 0)
        finally:
            recording = False
            path.unlink(missing_ok=True)
        ledger_dir = str((self.root / sl.LEDGER).parent.resolve())
        self.assertTrue(writes)
        for written in writes:
            self.assertTrue(str(Path(written).resolve()).startswith(ledger_dir), written)
        for relative, raw in protected.items():
            self.assertEqual((self.root / relative).read_bytes(), raw, relative)

    def test_the_writer_refuses_protected_paths(self):
        ledger = self.ledger()
        for relative in ("catalogs/landscape/ledger.json", "catalogs/sota-convergence/ledger.json",
                         "adoption/ledger.json", sl.RESEARCH_STATE):
            with self.subTest(path=relative):
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with self.assertRaises(sl.LedgerError):
                    sl.write_ledger(self.root, target, ledger)

    def test_new_files_are_outside_the_verdict_review_gate_trust_paths(self):
        import verdict_review_gate as gate
        owned = ["scripts/saturation_ledger.py", "tests/test_saturation_ledger.py", sl.LEDGER,
                 "catalogs/saturation/ledger.schema.json", "catalogs/saturation/README.md",
                 ".github/workflows/saturation-tracking.yml", "recipes/saturation-sweep.md"]
        for path in owned:
            self.assertNotIn(path, gate.TRUST_PATHS)
            for spec in gate.VERDICT_PATHSPECS:
                self.assertFalse(path.startswith(spec.rstrip("*")), (path, spec))
            for prefix, _ in gate.HEAD_DATA_BINDINGS:
                self.assertFalse(path.startswith(prefix), (path, prefix))

    def test_the_script_names_no_model_client(self):
        text = (ROOT / "scripts/saturation_ledger.py").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?i)\b(anthropic|openai)\b|claude\s+-p|\bcodex\s+(exec|review)")
        self.assertNotRegex(text, r"\b(urllib|requests|http\.client|socket)\b")


# --------------------------------------------------------------------------- repository ledger


class RepositoryLedgerTests(unittest.TestCase):
    def test_the_committed_ledger_checks(self):
        ledger = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))
        self.assertEqual(sl.check_ledger(ROOT, ledger), [])

    def test_the_seed_is_rederived_from_the_retained_files(self):
        ledger = sl.empty_ledger()
        for item in sl.derive_seed(ROOT):
            ledger = sl.append(ROOT, ledger, item)
        self.assertEqual(sl.dump(ledger), (ROOT / sl.LEDGER).read_text(encoding="utf-8"))

    def test_no_seed_layer_counts_as_clean(self):
        ledger = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))
        stopped, completed = ledger["sweeps"][:2]
        self.assertEqual((stopped["status"], stopped["lower_bound_usage"]), ("stopped", True))
        self.assertEqual((completed["status"], completed["lower_bound_usage"]), ("completed", False))
        self.assertTrue(all(layer["votes"] == "not_returned" for layer in stopped["layers"]))
        self.assertTrue(all(layer["votes"] == "not_retained" for layer in completed["layers"]))
        self.assertEqual(len(completed["layers"]), 32)
        survivors = [entry for layer in completed["layers"] for entry in layer["survived"]]
        self.assertEqual(len(survivors), 11)
        self.assertTrue(all(entry["source_review"] for entry in survivors))
        state = sl.derive(ledger)
        self.assertTrue(all(entry["count"] == 0 and not entry["saturation_candidate"] for entry in state.values()))

    def test_the_schema_matches_when_jsonschema_is_available(self):
        schema = json.loads((ROOT / "catalogs/saturation/ledger.schema.json").read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; scripts/saturation_ledger.py --check is the enforced check")
        ledger = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual([e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(ledger)], [])


# --------------------------------------------------------------------------- workflow


class WorkflowTests(unittest.TestCase):
    text = WORKFLOW.read_text(encoding="utf-8")

    def test_schedule_and_dry_run_dispatch(self):
        self.assertIn("- cron: '53 7 * * 1'", self.text)
        self.assertRegex(self.text, r"(?ms)workflow_dispatch:\n\s+inputs:\n\s+dry_run:\n.*?type: boolean\n\s+default: false")
        self.assertNotRegex(self.text, r"(?m)^\s+(pull_request_target|workflow_run|issue_comment):")

    def test_top_level_read_only_and_issues_write_only_on_the_final_job(self):
        blocks = permission_blocks(self.text)
        self.assertEqual(blocks[0], {"contents": "read"})
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read\n")
        self.assertEqual(len(blocks), 3)
        job_map = jobs(self.text)
        self.assertEqual(list(job_map), ["report", "issue"])
        self.assertEqual(permission_blocks(job_map["report"]), [{"contents": "read", "actions": "read"}])
        self.assertEqual(permission_blocks(job_map["issue"]), [{"issues": "write"}])
        self.assertEqual(self.text.count("issues: write"), 1)
        self.assertNotRegex(self.text, r"(?m)(contents|pull-requests|actions|id-token): write")
        self.assertIn("needs: report", job_map["issue"])
        self.assertNotIn("actions/checkout@", job_map["issue"])

    def test_every_job_starts_with_harden_runner(self):
        for job_id, job_text in jobs(self.text).items():
            step = first_step(job_text)
            self.assertIn("step-security/harden-runner@", step, job_id)
            self.assertIn("egress-policy: audit", step, job_id)

    def test_no_secret_beyond_the_job_token_and_no_model_invocation(self):
        self.assertNotIn("secrets.", self.text)
        expressions = re.findall(r"\$\{\{\s*(.*?)\s*\}\}", self.text)
        self.assertIn("github.token", expressions)
        self.assertEqual([e for e in expressions if "token" in e.lower() and e != "github.token"], [])
        run_text = "\n".join(re.findall(r"(?ms)run: \|\n(.*?)(?=\n      - |\n  [a-z]|\Z)", self.text))
        self.assertNotRegex(run_text, r"(?i)\b(claude|codex|anthropic|openai)\b")
        self.assertNotRegex(self.text, r"(?i)uses:\s*\S*(claude|anthropic|openai|codex)")

    def test_one_labelled_issue_is_upserted_and_dry_run_writes_nothing(self):
        job = jobs(self.text)["issue"]
        self.assertIn("gh issue list --label \"$label\" --state open", job)
        self.assertIn("gh issue edit", job)
        self.assertIn("gh issue create", job)
        self.assertIn("label='saturation-tracking'", job)
        dry = job.index('if [ "$DRY_RUN" = "true" ]')
        for write_command in ("gh issue create", "gh issue edit", "gh issue close", "gh label create"):
            self.assertGreater(job.index(write_command), dry, write_command)
        self.assertIn("DRY_RUN: ${{ inputs.dry_run && 'true' || 'false' }}", job)

    def test_the_report_job_checks_before_reporting(self):
        job = jobs(self.text)["report"]
        self.assertLess(job.index("saturation_ledger.py --check"), job.index("saturation_ledger.py --report"))
        self.assertIn("receipt_staleness.py --json", job)
        self.assertIn("gh run download", job)


if __name__ == "__main__":
    unittest.main()
