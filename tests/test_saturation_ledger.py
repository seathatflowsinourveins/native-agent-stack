"""Tests for scripts/saturation_ledger.py and .github/workflows/saturation-tracking.yml.

Three groups: the consecutive-clean arithmetic (pure ``derive`` fixtures), integrity (hash chain,
survivor-to-manifest binding, both votes with survival recomputed, retained returns, usage
registration) in a synthetic fixture checkout, and separation (the ledger never writes
research-state.json or any verdict path). The committed ledger is checked against this checkout
and against the ledger at the merge base, and its seed records are re-derived from the retained
files; their requirement and platform-profile hashes are recomputed at the commits they cite.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
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


def layer(layer_id="alpha", *, votes="retained", survived=(), reopen=(), req=REQ, plat=PLAT, catalog="foundation",
          discovery=True):
    value = {"catalog": catalog, "layer_id": layer_id, "requirement_sha256": req, "platform_profiles_sha256": plat,
             "votes": votes, "proposed": [], "known": [], "new": [],
             "survived": [{"repo": repo} for repo in survived], "refuted": [],
             "reopen": [{"trigger": trigger, "ref": "fixture"} for trigger in reopen]}
    if discovery:
        value["discovery_ref"] = f"returns.json#/discovery/{layer_id}"
    return value


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

    def test_a_receipt_flag_holds_the_count_only_while_it_stands_until_a_sweep_records_it(self):
        clean = (sweep("s1", "2026-10-01"), sweep("s2", "2026-10-08"), sweep("s3", "2026-10-15"))
        flagged = {"triggers": {KEY: [{"trigger": "pin_moved", "ref": "receipt_staleness:linux/tool"}]}}
        self.assertEqual(self.state(*clean, current=flagged)["count"], 0)
        # The report reads receipt flags from today's files: once the flag clears, nothing in the
        # ledger remembers it ...
        self.assertTrue(self.state(*clean)["saturation_candidate"])
        # ... so the next sweep records it as a reopen entry, which is a durable reset.
        recorded = sweep("s4", "2026-10-22", layer(reopen=["pin_moved"]))
        entry = self.state(*clean, recorded)
        self.assertEqual(entry["count"], 0)
        self.assertFalse(entry["saturation_candidate"])
        entry = self.state(*clean, recorded, sweep("s5", "2026-10-29"))
        self.assertEqual(entry["count"], 1)

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
        # A selection removed from the rebuilt catalog, or moved to another layer, changes the layer.
        removed = copy.deepcopy(before)
        removed["foundation"][0]["components"] = []
        triggers, _ = sl.external_triggers(before, None, removed)
        self.assertEqual(triggers[KEY], [{"trigger": "selection_changed", "ref": "catalog-freshness:tool (removed from layer)"}])
        moved = copy.deepcopy(removed)
        moved["foundation"].append({"layer": "beta", "components": copy.deepcopy(before["foundation"][0]["components"])})
        triggers, _ = sl.external_triggers(before, None, moved)
        self.assertEqual(list(triggers), [KEY])
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

    def test_retained_votes_without_a_discovery_return_are_never_clean(self):
        entry = self.state(sweep("s1", "2026-10-01", layer(discovery=False)),
                           sweep("s2", "2026-10-08", layer(discovery=False)),
                           sweep("s3", "2026-10-15", layer(discovery=False)))
        self.assertEqual(entry["count"], 0)
        self.assertEqual(entry["reset"][0]["trigger"], "no_discovery_return")

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
RETURNS = "evidence/artifacts/fx/returns.json"
REVIEW = "evidence/artifacts/fx/o-surv.json"
SURV, REF, OTHER = "https://github.com/o/surv", "https://github.com/o/ref", "https://github.com/o/other"
BETA = "https://github.com/o/beta"
# One run per sweep: each sweep_id has its own dated manifest, usage output and returns file.
SWEEP_DAYS = {"fx-1": "2026-10-01", "fx-2": "2026-10-08", "fx-3": "2026-10-15"}


def paths(sweep_id):
    """(manifest_ref, usage_ref, returns_ref) of a fixture sweep; fx-1 uses the named constants."""
    if sweep_id == "fx-1":
        return MANIFEST, USAGE, RETURNS
    return (f"catalogs/sota-convergence/manifest-{sweep_id}.json", f"evidence/artifacts/fx/child-usage-wf_{sweep_id}.json",
            f"evidence/artifacts/fx/{sweep_id}/returns.json")


def usage_of(workflow_run, children, status="complete"):
    return {"child_usage": {"transcript_dir": f"<session-transcripts>/subagents/workflows/{workflow_run}",
                            "status": status, "children": children}}


# Every discovery worker, and both refuters of each layer the fixture sweeps propose in.
COMPLETE_CHILDREN = [{"label": f"{role}:{layer_id}", "complete": True}
                     for layer_id in ("alpha", "beta", "gamma") for role in ("discover", "refute-facts", "refute-fit")]
# The retained lane returns the fixture cites: one discovery return per layer and one object per vote.
RETURN_DATA = {
    "discovery": {
        "alpha": {"catalog": "foundation", "layer_id": "alpha", "proposed": [SURV, REF]},
        "beta": {"catalog": "us-equities", "layer_id": "beta", "proposed": [BETA]},
        "gamma": {"catalog": "foundation", "layer_id": "gamma", "proposed": []},
        "gamma-nonempty": {"catalog": "foundation", "layer_id": "gamma", "proposed": [OTHER]},
    },
    "votes": {
        "surv": {"facts": {"role": "facts", "repository": SURV, "refuted": False},
                 "fit": {"role": "fit", "repository": SURV, "refuted": False}},
        "ref": {"facts": {"role": "facts", "repository": REF, "refuted": False},
                "fit": {"role": "fit", "repository": REF, "refuted": True}},
        "beta": {"facts": {"role": "facts", "repository": BETA, "refuted": True},
                 "fit": {"role": "fit", "repository": BETA, "refuted": True}},
    },
}


def write(root: Path, relative: str, value) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1) + "\n", encoding="utf-8")


def register(root: Path, *extra: str) -> None:
    files = []
    fixture = sorted(path.relative_to(root).as_posix() for folder in ("catalogs/sota-convergence", "evidence/artifacts/fx")
                     for path in (root / folder).rglob("*.json"))
    for relative in [*fixture, *extra]:
        raw = (root / relative).read_bytes()
        files.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    write(root, sl.EVIDENCE, {"schema_version": 1, "receipts": [], "files": sorted(files, key=lambda f: f["path"])})


def build_fixture(root: Path) -> None:
    write(root, sl.RESEARCH_STATE, {"schema_version": 1, "layers": [
        {"catalog": "foundation", "layer_id": "alpha", "status": "comparison_required",
         "next_action": "compare alpha", "decision_ref": "catalogs/landscape/foundation.json"},
        {"catalog": "us-equities", "layer_id": "beta", "status": "on_requirement_change",
         "next_action": "compare beta", "decision_ref": "catalogs/landscape/trading.json"},
        {"catalog": "foundation", "layer_id": "gamma", "status": "comparison_required",
         "next_action": "compare gamma", "decision_ref": "catalogs/landscape/foundation.json"}]})
    write(root, sl.ADOPTION, {"platform_profiles": [{"id": "linux-x86_64", "os": "linux"}]})

    def row(repo, survives):
        return {"repository": repo, "lane": LANE, "disposition": "targeted_candidate" if survives else "refuted",
                "adversarial_verification": {"survives": survives, "votes": [
                    {"lens": 0, "refuted": False}, {"lens": 1, "refuted": not survives}]}}

    manifest = {
        "checked_at": "2026-10-01",
        "foundation": [{"layer": "alpha", "components": [{"id": "sel", "repository": "https://github.com/o/sel"}],
                        "alternatives_keep_but_compare": [{"repository": OTHER}],
                        "candidates": [row(SURV, True), row(REF, False)]},
                       {"layer": "gamma", "components": [], "candidates": []}],
        "trading": [{"layer": "beta", "entries": [], "candidates": [row(BETA, False)]}],
    }
    # The scope frozen before each run (--scope), retained with every discovery return.
    scope = sl.scope_hashes(root)
    returns = copy.deepcopy(RETURN_DATA)
    for item in returns["discovery"].values():
        item.update(requirement_sha256=scope["requirement_sha256"][f"{item['catalog']}/{item['layer_id']}"],
                    platform_profiles_sha256=scope["platform_profiles_sha256"])
    for sweep_id, day in SWEEP_DAYS.items():
        manifest_ref, usage_ref, returns_ref = paths(sweep_id)
        write(root, manifest_ref, dict(manifest, checked_at=day))
        write(root, usage_ref, usage_of(f"wf_{sweep_id}", COMPLETE_CHILDREN))
        write(root, returns_ref, dict(returns, workflow_run=f"wf_{sweep_id}"))
    write(root, USAGE_PARTIAL, usage_of("wf_fx-stopped", [
        {"label": "discover:alpha", "complete": True}, {"label": "discover:beta", "complete": False}], "incomplete"))
    write(root, REVIEW, {"repository": SURV, "layers": ["alpha"]})
    write(root, "evidence/artifacts/fx/other-review.json", {"repository": OTHER, "layers": ["alpha"]})
    register(root)
    write(root, sl.LEDGER, sl.dump(sl.empty_ledger()))


def vote(name, role, returns=RETURNS):
    return {"vote": "refuted" if RETURN_DATA["votes"][name][role]["refuted"] else "not_refuted",
            "ref": f"{returns}#/votes/{name}/{role}"}


def result(sweep_id="fx-1", day="2026-10-01", **overrides):
    manifest_ref, usage_ref, returns = paths(sweep_id)
    value = {
        "sweep_id": sweep_id, "date": day, "workflow_run": f"wf_{sweep_id}", "status": "completed",
        "manifest_ref": manifest_ref, "lane": LANE, "prompts_sha256": "c" * 64, "usage_ref": usage_ref,
        "lower_bound_usage": False, "returns_ref": returns,
        "layers": [
            {"catalog": "foundation", "layer_id": "alpha", "votes": "retained",
             "discovery_ref": f"{returns}#/discovery/alpha", "calls": {"web_search": 2},
             "proposed": [SURV, REF],
             "survived": [{"repo": SURV, "source_review": REVIEW, "facts": vote("surv", "facts", returns),
                           "fit": vote("surv", "fit", returns)}],
             "refuted": [{"repo": REF, "facts": vote("ref", "facts", returns), "fit": vote("ref", "fit", returns)}],
             "reopen": []},
            {"catalog": "us-equities", "layer_id": "beta", "votes": "retained",
             "discovery_ref": f"{returns}#/discovery/beta", "calls": None,
             "proposed": [BETA], "survived": [],
             "refuted": [{"repo": BETA, "facts": vote("beta", "facts", returns), "fit": vote("beta", "fit", returns)}],
             "reopen": []},
        ],
    }
    value.update(overrides)
    return value


def stopped_result(**overrides):
    """A stopped run of its own (wf_fx-stopped): partial usage, one layer, no returns file."""
    value = result(sweep_id="fx-stopped", status="stopped", manifest_ref=MANIFEST, usage_ref=USAGE_PARTIAL,
                   lower_bound_usage=True,
                   lost_workers=["discover:beta"],
                   layers=[{"catalog": "foundation", "layer_id": "alpha", "votes": "not_returned",
                            "votes_note": "stopped before any refuter returned", "calls": None,
                            "proposed": [SURV], "survived": [], "refuted": [], "reopen": []}])
    del value["returns_ref"]
    value.update(overrides)
    return value


def gamma(discovery="gamma", proposed=(), returns=RETURNS):
    value = {"catalog": "foundation", "layer_id": "gamma", "votes": "retained", "calls": None,
             "proposed": list(proposed), "survived": [], "refuted": [], "reopen": []}
    if discovery is not None:
        value["discovery_ref"] = f"{returns}#/discovery/{discovery}"
    return value


def lens_layer(refs):
    """alpha recorded with votes not_retained and the manifest's lens votes, refs overridable."""
    def lens_votes(row, lens_refuted):
        return [{"lens": lens, "vote": "refuted" if refuted else "not_refuted",
                 "ref": refs.get((row, lens), f"{MANIFEST}#/foundation/0/candidates/{row}/adversarial_verification/votes/{lens}")}
                for lens, refuted in enumerate(lens_refuted)]
    return {"catalog": "foundation", "layer_id": "alpha", "votes": "not_retained",
            "votes_note": "per-vote returns not retained", "calls": None, "proposed": [SURV, REF],
            "survived": [{"repo": SURV, "source_review": REVIEW, "lens_votes": lens_votes(0, (False, False))}],
            "refuted": [{"repo": REF, "lens_votes": lens_votes(1, (False, True))}], "reopen": []}


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
        forged["sweeps"][0]["notes"] = ["forged after review"]
        previous = sl.genesis_sha256(forged)
        for record in forged["sweeps"]:
            record["prev_sha256"] = previous
            previous = sl.record_sha256(record)
        forged["head_sha256"] = previous
        self.assertEqual(sl.check_ledger(self.root, forged), [])
        self.assertTrue(sl.check_append_only(self.root, forged, "HEAD"))
        extended = sl.append(self.root, ledger, result("fx-3", "2026-10-15"))
        self.assertEqual(sl.check_append_only(self.root, extended, "HEAD"), [])
        # An unknown base is an error, not "no ledger yet" ...
        self.assertEqual(sl.check_append_only(self.root, forged, "no-such-ref-xyz"),
                         ["append-only: no-such-ref-xyz is not a commit in this checkout"])
        self.assertEqual(quiet_main(["--root", str(self.root), "--check", "--base", "no-such-ref-xyz"]), 1)
        # ... while a valid commit without the ledger file is.
        (self.root / sl.LEDGER).unlink()
        subprocess.run([*git, "commit", "-q", "-am", "no ledger"], check=True)
        self.assertEqual(sl.check_append_only(self.root, forged, "HEAD"), [])

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
        # A review of the right repository must still name this layer in a layers list.
        for name, layers in (("no-layers", None), ("string-layers", "alpha"), ("other-layer", ["beta"])):
            with self.subTest(layers=layers):
                relative = f"evidence/artifacts/fx/review-{name}.json"
                write(self.root, relative, {"repository": SURV} | ({} if layers is None else {"layers": layers}))
                register(self.root)
                bound = copy.deepcopy(ledger)
                bound["sweeps"][0]["layers"][0]["survived"][0]["source_review"] = relative
                self.assertErrorMatches(sl_rechain(bound), r"does not name layer alpha in its layers list")

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
        self.assertTrue(any("disagrees with evidence/artifacts/fx/returns.json#/votes/ref/fit" in e for e in errors), errors)
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
        stopped = stopped_result(lower_bound_usage=False)
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

    def test_a_retained_layer_needs_its_retained_discovery_return(self):
        # An empty retained layer is evidence only through its discovery return.
        with self.assertRaisesRegex(sl.LedgerError, "needs a discovery_ref"):
            sl.append(self.root, self.ledger(), result(layers=[gamma(discovery=None)]))
        with self.assertRaisesRegex(sl.LedgerError, "does not equal the retained discovery return"):
            sl.append(self.root, self.ledger(), result(layers=[gamma("gamma-nonempty")]))
        with self.assertRaisesRegex(sl.LedgerError, "is not the discovery return of foundation/gamma"):
            sl.append(self.root, self.ledger(), result(layers=[gamma("alpha")]))
        with self.assertRaisesRegex(sl.LedgerError, "needs the sweep's returns_ref"):
            without = result(layers=[gamma()])
            del without["returns_ref"]
            sl.append(self.root, self.ledger(), without)
        ledger = self.appended(*(result(sweep_id, day, layers=[gamma(returns=paths(sweep_id)[2])])
                                 for sweep_id, day in SWEEP_DAYS.items()))
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        self.assertTrue(sl.derive(ledger)[("foundation", "gamma")]["saturation_candidate"])
        # The reviewer's case: retained, empty, and no discovery return, three times.
        stripped = copy.deepcopy(ledger)
        for record in stripped["sweeps"]:
            del record["layers"][0]["discovery_ref"]
        stripped = sl_rechain(stripped)
        self.assertErrorMatches(stripped, r"needs a discovery_ref")
        self.assertFalse(sl.derive(stripped)[("foundation", "gamma")]["saturation_candidate"])

    def test_retained_vote_refs_point_at_a_matching_vote_in_the_returns_file(self):
        ledger = self.appended(result())
        cases = {
            "pointer-less file": (REVIEW, r"needs a #/json/pointer"),
            "pointer-less returns file": (RETURNS, r"needs a #/json/pointer"),
            "usage file": (f"{USAGE}#/child_usage", r"must point into evidence/artifacts/fx/returns\.json"),
            "manifest": (f"{MANIFEST}#/foundation/0", r"must point into evidence/artifacts/fx/returns\.json"),
            "other role": (f"{RETURNS}#/votes/ref/fit", r"is not a facts vote"),
            "other repository": (f"{RETURNS}#/votes/surv/facts", r"is a vote on a different repository"),
            "unresolved": (f"{RETURNS}#/votes/ref/nope", r"does not resolve"),
        }
        for name, (ref, pattern) in cases.items():
            with self.subTest(case=name):
                edited = copy.deepcopy(ledger)
                edited["sweeps"][0]["layers"][0]["refuted"][0]["facts"]["ref"] = ref
                self.assertErrorMatches(sl_rechain(edited), pattern)
        for field in (MANIFEST, USAGE):
            with self.subTest(returns_ref=field):
                with self.assertRaisesRegex(sl.LedgerError, "must be the retained lane returns"):
                    sl.append(self.root, self.ledger(), result(returns_ref=field))

    def test_lens_votes_point_at_this_layers_lane_row_for_the_repository(self):
        ledger = self.appended(result(layers=[lens_layer({})]))
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        cases = {
            "pointer-less": (MANIFEST, r"needs a #/json/pointer"),
            "other file": (f"{RETURNS}#/votes/surv/facts", r"must point into catalogs/sota-convergence/manifest-fx\.json"),
            "other candidate": (f"{MANIFEST}#/foundation/0/candidates/1/adversarial_verification/votes/0",
                                r"is a vote on a different candidate row"),
            "other layer": (f"{MANIFEST}#/trading/0/candidates/0/adversarial_verification/votes/0",
                            r"is not a vote of this layer's manifest row"),
            "other lens": (f"{MANIFEST}#/foundation/0/candidates/0/adversarial_verification/votes/1", r"is not lens 0"),
        }
        for name, (ref, pattern) in cases.items():
            with self.subTest(case=name):
                with self.assertRaisesRegex(sl.LedgerError, pattern):
                    sl.append(self.root, self.ledger(), result(layers=[lens_layer({(0, 0): ref})]))

    def test_a_date_must_be_a_calendar_date(self):
        with self.assertRaisesRegex(sl.LedgerError, "calendar date"):
            sl.append(self.root, self.ledger(), result(day="2026-02-30"))
        ledger = self.appended(result())
        ledger["sweeps"][0]["date"] = "2026-02-30"
        self.assertErrorMatches(sl_rechain(ledger), r"date must be a calendar date")

    def test_lost_workers_name_incomplete_children_of_the_usage_output(self):
        stopped = stopped_result()
        self.assertEqual(sl.check_ledger(self.root, sl.append(self.root, self.ledger(), stopped)), [])
        for lost in (["discover:alpha"], ["discover:gone"]):
            with self.subTest(lost=lost):
                with self.assertRaisesRegex(sl.LedgerError, "is not an incomplete child"):
                    sl.append(self.root, self.ledger(), dict(stopped, lost_workers=lost))

    def test_lost_workers_must_list_every_incomplete_child(self):
        # Omitting lost_workers, or listing fewer than never returned, understates the lost work.
        omitted = stopped_result()
        del omitted["lost_workers"]
        for value in (omitted, stopped_result(lost_workers=[])):
            with self.subTest(lost_workers=value.get("lost_workers")):
                with self.assertRaisesRegex(sl.LedgerError, r"lost_workers omits incomplete children.*discover:beta"):
                    sl.append(self.root, self.ledger(), value)

    def test_a_completed_sweep_needs_every_discovery_and_refuter_worker(self):
        # Complete usage with no children says nothing about which workers ran.
        empty = "evidence/artifacts/fx/child-usage-empty.json"
        write(self.root, empty, usage_of("wf_fx-1", []))
        register(self.root)
        with self.assertRaisesRegex(sl.LedgerError, r"needs a completed discover:alpha child"):
            sl.append(self.root, self.ledger(), result(usage_ref=empty))
        # A layer with proposals also needs both refuters; a layer without them only discovery.
        partial = "evidence/artifacts/fx/child-usage-no-fit.json"
        write(self.root, partial, usage_of("wf_fx-1", [c for c in COMPLETE_CHILDREN if c["label"] != "refute-fit:beta"]))
        register(self.root)
        with self.assertRaisesRegex(sl.LedgerError, r"needs a completed refute-fit:beta child"):
            sl.append(self.root, self.ledger(), result(usage_ref=partial))
        discover_only = "evidence/artifacts/fx/child-usage-gamma.json"
        write(self.root, discover_only, usage_of("wf_fx-1", [{"label": "discover:gamma", "complete": True}]))
        register(self.root)
        self.assertEqual(sl.check_ledger(self.root, self.appended(result(usage_ref=discover_only, layers=[gamma()]))), [])

    def test_replayed_run_evidence_is_not_a_new_sweep(self):
        ledger = self.appended(result())
        replay = result()
        replay["sweep_id"] = "fx-replay"
        with self.assertRaisesRegex(sl.LedgerError, r"usage_ref .* is already recorded by fx-1"):
            sl.append(self.root, ledger, replay)
        errors = sl.check_ledger(self.root, sl_rechain(dict(ledger, sweeps=[*ledger["sweeps"], dict(
            ledger["sweeps"][0], sweep_id="fx-replay")])))
        for field in ("workflow_run", "usage_ref", "usage_sha256", "returns_ref", "returns_sha256",
                      "manifest_ref\\+lane", "manifest_sha256\\+lane"):
            self.assertTrue(any(re.search(rf"sweeps\[1\]: {field} .* already recorded by fx-1", e) for e in errors),
                            (field, errors))
        # workflow_run is the run the usage output measured, not a free string.
        with self.assertRaisesRegex(sl.LedgerError, r"workflow_run wf_other is not the run"):
            sl.append(self.root, self.ledger(), result(workflow_run="wf_other"))
        # A stopped run may share the manifest it used as its baseline with the completed run.
        self.assertEqual(sl.check_ledger(self.root, self.appended(stopped_result(), result())), [])

    def test_a_completed_sweep_is_dated_by_its_manifest(self):
        with self.assertRaisesRegex(sl.LedgerError, r"date 2026-10-09 must equal .*manifest-fx-2\.json#/checked_at"):
            sl.append(self.root, self.ledger(), result("fx-2", "2026-10-09"))
        # Back-dating to satisfy the gap rule fails the same way.
        ledger = self.appended(result())
        with self.assertRaisesRegex(sl.LedgerError, r"must equal"):
            sl.append(self.root, ledger, result("fx-2", "2026-10-01"))

    def test_the_record_carries_the_scope_frozen_before_the_run(self):
        frozen = sl.scope_hashes(self.root)
        # The layer's requirement changes after the sweep froze its scope, before --append.
        state = json.loads((self.root / sl.RESEARCH_STATE).read_text())
        state["layers"][0]["next_action"] = "compare alpha against a new requirement"
        write(self.root, sl.RESEARCH_STATE, state)
        changed = sl.scope_hashes(self.root)["requirement_sha256"]["foundation/alpha"]
        ledger = self.appended(result())
        alpha = ledger["sweeps"][0]["layers"][0]
        self.assertEqual(alpha["requirement_sha256"], frozen["requirement_sha256"]["foundation/alpha"])
        self.assertNotEqual(alpha["requirement_sha256"], changed)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        # The change stands as a current trigger instead of being absorbed into the record.
        report = sl.build_report(self.root, ledger)
        self.assertEqual(report["current_reopen_triggers"]["foundation/alpha"][0]["trigger"], "requirement_changed")
        # A record that claims today's hash for a sweep that evaluated the frozen scope fails.
        claimed = copy.deepcopy(ledger)
        claimed["sweeps"][0]["layers"][0]["requirement_sha256"] = changed
        self.assertErrorMatches(sl_rechain(claimed), r"requirement_sha256 differs from the frozen scope")
        self.assertEqual(json.loads(self.cli_output(["--scope"]))["requirement_sha256"]["foundation/alpha"], changed)

    def test_a_discovery_return_without_frozen_scope_does_not_check(self):
        returns = json.loads((self.root / RETURNS).read_text())
        for item in returns["discovery"].values():
            del item["requirement_sha256"], item["platform_profiles_sha256"]
        write(self.root, RETURNS, returns)
        register(self.root)
        with self.assertRaisesRegex(sl.LedgerError, r"platform_profiles_sha256 differs from the frozen scope"):
            sl.append(self.root, self.ledger(), result())

    def cli_output(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sl.main(["--root", str(self.root), *argv]), 0)
        return out.getvalue()

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
        self.assertEqual(report["inputs"]["freshness"], "not available")

    def test_a_partial_freshness_input_is_reported_as_partial(self):
        manifest = json.loads((self.root / MANIFEST).read_text())
        ledger = self.appended(result())
        cases = ((None, "partial"), ({"errors": 0, "partial_errors": 2}, "partial"),
                 ({"errors": 1, "partial_errors": 0}, "partial"), ({"errors": "0"}, "partial"),
                 ({"errors": 0, "partial_errors": 0}, "read"))
        for status, expected in cases:
            with self.subTest(status=status):
                report = sl.build_report(self.root, ledger, None, manifest, status)
                self.assertEqual(report["inputs"]["freshness"], expected)
                self.assertEqual(any("catalog-freshness input partial" in n for n in report["notes"]),
                                 expected == "partial")
                self.assertIn(f"catalog-freshness manifest {expected}", sl.render_markdown(report))


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

    # The requirement and platform-profile hashes are computed from the research-state and adoption
    # files at append time. They legitimately differ from today's files after a landscape edit, so
    # the seed comparison leaves them out and recomputes them at the commits the README cites.
    SEED_HASH_COMMITS = ("9eac1f9", "0465141", "4a4c8a2")

    @staticmethod
    def without_append_time_hashes(record):
        record = copy.deepcopy(record)
        record.pop("prev_sha256", None)  # the chain itself is verified by --check
        for layer_ in record["layers"]:
            layer_.pop("requirement_sha256", None)
            layer_.pop("platform_profiles_sha256", None)
        return record

    def test_the_seed_records_are_rederived_from_the_retained_files(self):
        committed = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))
        self.assertEqual(committed["policy"], sl.empty_ledger()["policy"])
        ledger = sl.empty_ledger()
        for item in sl.derive_seed(ROOT):
            ledger = sl.append(ROOT, ledger, item)
        seed = ledger["sweeps"]
        self.assertEqual(seed[0]["prev_sha256"], committed["sweeps"][0]["prev_sha256"])
        self.assertEqual([self.without_append_time_hashes(record) for record in seed],
                         [self.without_append_time_hashes(record) for record in committed["sweeps"][:len(seed)]])

    def test_the_seed_hashes_match_the_files_at_the_commits_they_cite(self):
        committed = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))["sweeps"][:2]
        checked = 0
        for commit in self.SEED_HASH_COMMITS:
            files = {}
            for relative in (sl.RESEARCH_STATE, sl.ADOPTION):
                shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{relative}"],
                                       capture_output=True, text=True, check=False)
                if shown.returncode != 0:
                    break
                files[relative] = json.loads(shown.stdout)
            if len(files) != 2:
                continue  # a shallow or partial clone lacks the commit
            rows = {(row.get("catalog"), row.get("layer_id")): row for row in files[sl.RESEARCH_STATE]["layers"]}
            profiles = sl.platform_profiles_sha256(files[sl.ADOPTION])
            for record in committed:
                for layer_ in record["layers"]:
                    key = (layer_["catalog"], layer_["layer_id"])
                    with self.subTest(commit=commit, layer=key):
                        self.assertEqual(layer_["requirement_sha256"], sl.requirement_sha256(rows[key]))
                        self.assertEqual(layer_["platform_profiles_sha256"], profiles)
            checked += 1
        if not checked:
            self.skipTest("none of the cited commits is in this clone")

    def test_the_ledger_extends_the_one_at_the_merge_base(self):
        """Append-only across commits: the ledger at the merge base with the target branch must be
        an unchanged prefix of this one, which catches a rewrite that recomputes every hash. In a
        pull_request run (GITHUB_BASE_REF set) with full history the base must resolve."""
        if shutil.which("git") is None:
            self.skipTest("git unavailable")
        target = f"origin/{os.environ.get('GITHUB_BASE_REF') or 'main'}"
        git = ["git", "-C", str(ROOT)]
        shallow = subprocess.run([*git, "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True, check=False).stdout.strip() == "true"
        base = subprocess.run([*git, "merge-base", "HEAD", target], capture_output=True, text=True, check=False)
        if base.returncode != 0:
            if os.environ.get("GITHUB_BASE_REF") and not shallow:
                self.fail(f"cannot find the merge base with {target}: {base.stderr.strip()}")
            self.skipTest(f"no merge base with {target} in this clone")
        ledger = json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8"))
        self.assertEqual(sl.check_append_only(ROOT, ledger, base.stdout.strip()), [])

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
        # The stopped attempt's provenance: its date comes from the superseding run's manifest, and
        # its eight in-flight children are lost workers without a layer entry.
        self.assertEqual(len(stopped["lost_workers"]), 8)
        self.assertTrue(any("no date of its own" in note for note in stopped["notes"]))
        self.assertFalse({label.split(":", 1)[1] for label in stopped["lost_workers"]}
                         & {layer["layer_id"] for layer in stopped["layers"]})

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
        self.assertEqual(len(blocks), 4)
        job_map = jobs(self.text)
        self.assertEqual(list(job_map), ["report", "plan", "issue"])
        self.assertEqual(permission_blocks(job_map["report"]), [{"contents": "read", "actions": "read"}])
        self.assertEqual(permission_blocks(job_map["plan"]), [{"issues": "read"}])
        self.assertEqual(permission_blocks(job_map["issue"]), [{"issues": "write"}])
        self.assertEqual(self.text.count("issues: write"), 1)
        self.assertNotRegex(self.text, r"(?m)(contents|pull-requests|actions|id-token): write")
        for job_id in ("plan", "issue"):
            self.assertIn("needs: report", job_map[job_id])
            self.assertNotIn("actions/checkout@", job_map[job_id])
        # A dry run never mints the write token: the write job is skipped and the plan job reads.
        self.assertIn("    if: ${{ !inputs.dry_run }}\n", job_map["issue"])
        self.assertIn("    if: ${{ inputs.dry_run }}\n", job_map["plan"])

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
        job_map = jobs(self.text)
        job = job_map["issue"]
        self.assertIn("gh issue list --label \"$label\" --state open", job)
        self.assertIn("gh issue edit", job)
        self.assertIn("gh issue create", job)
        self.assertIn("label='saturation-tracking'", job)
        plan = job_map["plan"]
        self.assertIn("gh issue list --label \"$label\" --state open", plan)
        self.assertIn("label='saturation-tracking'", plan)
        for write_command in ("gh issue create", "gh issue edit", "gh issue close", "gh label create"):
            self.assertNotIn(write_command, plan)
            self.assertNotIn(write_command, job_map["report"])
        self.assertNotIn("DRY_RUN", self.text)

    def test_the_report_job_checks_before_reporting(self):
        job = jobs(self.text)["report"]
        self.assertLess(job.index("saturation_ledger.py --check"), job.index("saturation_ledger.py --report"))
        self.assertIn("receipt_staleness.py --json", job)
        self.assertIn("gh run download", job)
        # Only scheduled freshness runs (no max_repos bound), with their error counts.
        self.assertIn("--event schedule", job)
        self.assertIn("--freshness-status", job)
        # The unit tests run in validate.yml; running them here would block the report.
        self.assertNotIn("unittest", job)


if __name__ == "__main__":
    unittest.main()
