"""A7 and A3 routing of tools/sota-convergence/gap_crosswalk.py: a synthetic fixture, and the retained 92bb279 inputs
read offline. Nothing here calls TypeSafe.

The rules come from section 3.1 of the design report "Jev and TypeSafe: typed judgments for the foundation and
north-star R&D" (2026-10-03, revision r1, sha256 6fdd8bc2). A7: a pair that no reviewer saw gets no final decision
(`screened_out`), and a gap with candidate pairs but no reviewed pair gets the gap status `screened_out`, not `open`.
A3: a pair whose gap text contains a digit always goes to review.

CrosswalkRoutingTests builds one fixture twice with build(): as a new crosswalk, which takes the new rule, and as the
retained 92bb279 crosswalk, which keeps the 2026-09-23 rule. The second build is the negative control: the A7 and A3
checks must fail on it. The tool at ecea28654 has only the 2026-09-23 rule, so its build fails the A7 and A3 tests.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/sota-convergence/gap_crosswalk.py"
LEDGER = ROOT / "catalogs/landscape/gap-crosswalk-92bb279.json"
EVID = ROOT / "evidence/artifacts/gap-crosswalk-92bb279"

NEW_ID, FROZEN_ID = "gap-crosswalk-synthetic", "gap-crosswalk-92bb279"
NEW_RULE = "a7-screened-out-a3-digit-review-20261003"
LAYER = "quality-evaluation"  # gap_crosswalk.OWNERS names an owner for it
R0, R1 = "receipts/r0.json", "receipts/r1.json"
GAPS = ["No native comparison against an alternative was run.",  # no digit
        "The check needs a rerun on 2 hosts.",                      # a digit
        "No upstream test was rerun.",                              # no digit, and no pair passes the screen
        "No check on a second surface was run."]                    # no digit; its reviewed pair does not address it
# (gap index, receipt) -> (P(settles), P(partially)); the tool's THRESHOLD is 0.3, so only (0, R1) and (3, R0) pass
# the screen.
SCREEN = {(0, R0): (0.05, 0.05), (0, R1): (0.2, 0.4), (1, R0): (0.05, 0.05), (1, R1): (0.05, 0.1),
          (2, R0): (0.05, 0.05), (2, R1): (0.1, 0.1), (3, R0): (0.1, 0.3), (3, R1): (0.05, 0.05)}
# Reviews: the queued pairs of gaps 0 and 3, and both pairs of gap 1. Gap 0's first pair, both pairs of gap 2 and gap
# 3's second pair have none.
REVIEWS = {(0, R1): "partially", (1, R0): "not_addressed", (1, R1): "settles", (3, R0): "not_addressed"}


def load_tool():
    spec = importlib.util.spec_from_file_location("gap_crosswalk_routing_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def choice(settles: float, partially: float) -> dict:
    probabilities = {"settles": settles, "partially": partially, "not_addressed": round(1 - settles - partially, 4)}
    return {"type": "choice", "choice": max(probabilities, key=probabilities.get), "probabilities": probabilities}


def run_build(crosswalk_id: str, reviews: dict = REVIEWS) -> tuple[dict, str]:
    """Build the fixture as crosswalk `crosswalk_id` in a scratch root; return the ledger document and the page."""
    tool = load_tool()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for receipt in (R0, R1):
            write(root / receipt, {"id": Path(receipt).stem, "purpose": "fixture", "result": "fixture",
                                   "limitations": [], "evidence_class": "synthetic_fixture"})
        write(root / "ledger.json", {"receipts": [{"path": receipt, "gap_refs": [{"layer_id": LAYER}],
                                                   "layer_ids": [LAYER]} for receipt in (R0, R1)]})
        judgments = []
        for index, text in enumerate(GAPS):
            body = tool.request_body(root, {"layer": LAYER, "gap": text, "receipts": [R0, R1]})
            answers = {f"addr_r{k}": choice(*SCREEN[(index, receipt)]) for k, receipt in enumerate((R0, R1))}
            answers["blocker"] = {"type": "choice", "choice": "executable_now", "confidence": 0.5,
                                  "probabilities": {"executable_now": 0.5, "catalog_edit": 0.5}}
            judgments.append({"catalog": "foundation", "layer": LAYER, "index": index, "receipts": [R0, R1],
                              "gap_sha256": tool.hashlib.sha256(text.encode()).hexdigest(),
                              "state_sha256": tool.hashlib.sha256(body["state"].encode()).hexdigest(),
                              "answers": answers})
        evid = root / "evid"
        write(evid / "typesafe-current.json", judgments)
        write(evid / "typesafe-eval.json", [])
        write(evid / "eval-score.json", {"threshold_p_addressed": {str(tool.THRESHOLD): {"tp": 1, "fn": 0, "fp": 0, "tn": 1}},
                                         "blocker_agreement": {"agree": 1, "total": 1}})
        gaps = [{"index": index, "category": "executable_now", "category_reason": "fixture", "next_check": None,
                 "pairs": [{"receipt": receipt, "decision": decision, "reason": "fixture"}
                           for (gap, receipt), decision in reviews.items() if gap == index]}
                for index in range(len(GAPS))]
        checks = [{"layer_id": LAYER, "index": gap, "receipt": receipt, "verdict": "agree", "evidence": "fixture",
                   "corrected_decision": decision} for (gap, receipt), decision in reviews.items()
                  if decision != "not_addressed"]
        write(evid / "review-results.json", {"results": [{"review": {"layers": [{"layer_id": LAYER, "gaps": gaps}]},
                                                          "verify": {"checks": checks}}]})
        (root / "out").mkdir()
        tool.LEDGER, tool.EVID, tool.OUT, tool.DOC = "ledger.json", "evid", "out/crosswalk.json", "out/crosswalk.md"
        tool.CURRENT_REV, tool.CROSSWALK_ID = "0" * 40, crosswalk_id
        sources = {"foundation": {"layers": [{"layer_id": LAYER, "open_gaps": GAPS}]}, "us-equities": {"layers": []}}

        def git_show(command, *args, **kwargs):  # build() reads the source rows with `git show REV:path`
            return json.dumps(sources[command[-1].rsplit("/", 1)[1].removesuffix(".json")]).encode()

        with contextlib.chdir(root), mock.patch.object(tool.subprocess, "check_output", side_effect=git_show), \
                contextlib.redirect_stdout(io.StringIO()):
            tool.build(argparse.Namespace(check=False))
        return (json.loads((root / "out/crosswalk.json").read_text(encoding="utf-8")),
                (root / "out/crosswalk.md").read_text(encoding="utf-8"))


def pairs(doc: dict) -> dict:
    return {(gap["index"], entry["receipt"]): entry for layer in doc["layers"] for gap in layer["gaps"]
            for entry in gap["receipts"]}


def gaps(doc: dict) -> dict:
    return {gap["index"]: gap for layer in doc["layers"] for gap in layer["gaps"]}


class CrosswalkRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new = run_build(NEW_ID)
        cls.frozen = run_build(FROZEN_ID)

    def check_a7(self, doc: dict, page: str) -> None:
        entry = pairs(doc)[(0, R0)]
        self.assertEqual((entry["queued"], entry["review_decision"]), (False, None))
        self.assertEqual(entry["final_decision"], "screened_out", "a pair no reviewer saw has no final decision")
        self.assertEqual(gaps(doc)[0]["status"], "advanced_by_receipt", "only the reviewed pair sets the status")
        self.assertEqual(doc["method"].get("routing", {}).get("id"), NEW_RULE, "the document names its rule")
        self.assertIn("`screened_out`", page)

    def check_a7_gap_status(self, doc: dict, page: str) -> None:
        self.assertEqual(gaps(doc)[2]["status"], "screened_out", "a gap with no reviewed pair is not read as open")
        self.assertEqual(gaps(doc)[3]["status"], "open", "a gap whose reviewed pair does not address it stays open")
        self.assertIn("| screened_out | 1 |", page)

    def check_a3(self, doc: dict) -> None:
        for receipt in (R0, R1):
            entry = pairs(doc)[(1, receipt)]
            self.assertEqual((entry["queued"], entry.get("review_route")), (True, "digit_in_gap"), receipt)
        self.assertEqual(gaps(doc)[1]["status"], "settled_by_receipt")

    def check_a3_refusal(self, crosswalk_id: str) -> None:
        without = {key: value for key, value in REVIEWS.items() if key != (1, R0)}
        with self.assertRaises(SystemExit) as raised:
            run_build(crosswalk_id, without)
        self.assertEqual(str(raised.exception.code), f"queued pair not reviewed: {LAYER}[1] {R0}")

    def test_a7_a_pair_no_reviewer_saw_has_no_final_decision(self):
        self.check_a7(*self.new)

    def test_a7_a_gap_with_no_reviewed_pair_is_not_open(self):
        self.check_a7_gap_status(*self.new)

    def test_a3_a_gap_with_a_digit_sends_every_pair_to_review(self):
        self.check_a3(self.new[0])
        self.check_a3_refusal(NEW_ID)

    def test_negative_control_the_2026_09_23_rule_fails_both_checks(self):
        doc, page = self.frozen
        self.assertEqual(pairs(doc)[(0, R0)]["final_decision"], "not_addressed", "the screen closed the pair")
        self.assertFalse(pairs(doc)[(1, R0)]["queued"], "the digit did not send the pair to review")
        self.assertEqual(gaps(doc)[2]["status"], "open", "a gap with no reviewed pair reads as open")
        self.assertNotIn("routing", doc["method"])
        self.assertFalse(any("review_route" in entry for entry in pairs(doc).values()))
        for name, check in (("A7", lambda: self.check_a7(doc, page)),
                            ("A7 gap status", lambda: self.check_a7_gap_status(doc, page)),
                            ("A3", lambda: self.check_a3(doc)),
                            ("A3 refusal", lambda: self.check_a3_refusal(FROZEN_ID))):
            with self.subTest(check=name), self.assertRaises(AssertionError):
                check()


class RetainedLedgerRoutingTests(unittest.TestCase):
    """The retained 92bb279 judgments and reviews under each rule. The 2026-09-23 rule reproduces every recorded
    pair entry. The new rule gives no unreviewed pair a final decision and refuses exactly the unreviewed pairs whose
    gap text contains a digit, so re-recording that ledger under it first needs their reviews."""

    def test_each_rule_on_the_retained_inputs(self):
        tool = load_tool()
        pair_entry, frozen_rule, routing_error = tool.pair_entry, tool.ROUTING_20260923, tool.RoutingError
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        judged = {(r["catalog"], r["layer"], r["index"]): r
                  for r in tool.load_judgments(EVID / "typesafe-current.json")}
        review, verify = {}, {}
        for group in json.loads((EVID / "review-results.json").read_text(encoding="utf-8"))["results"]:
            for layer in group["review"]["layers"]:
                for gap in layer["gaps"]:
                    review[(layer["layer_id"], gap["index"])] = gap
            for check in (group.get("verify") or {}).get("checks", []):
                verify[(check["layer_id"], check["index"], check["receipt"])] = check
        unreviewed = refused = screened = 0
        for layer in doc["layers"]:
            for gap in layer["gaps"]:
                judgment = judged[(layer["catalog"], layer["layer_id"], gap["index"])]
                reviewed = {pair["receipt"]: pair for pair in review[(layer["layer_id"], gap["index"])]["pairs"]}
                for k, recorded in enumerate(gap["receipts"]):
                    receipt = recorded["receipt"]
                    args = (receipt, judgment["answers"][f"addr_r{k}"], gap["text"], reviewed.get(receipt),
                            verify.get((layer["layer_id"], gap["index"], receipt)))
                    with self.subTest(layer=layer["layer_id"], gap=gap["index"], receipt=receipt):
                        self.assertEqual(pair_entry(*args, routing=frozen_rule), recorded)
                        unreviewed += recorded["review_decision"] is None
                        try:
                            entry = pair_entry(*args)
                        except routing_error:
                            refused += 1
                            self.assertIsNone(recorded["review_decision"])
                            self.assertRegex(gap["text"], re.compile(r"\d"))
                            continue
                        if entry["review_decision"] is None:
                            self.assertEqual(entry["final_decision"], "screened_out")
                            self.assertNotRegex(gap["text"], re.compile(r"\d"))
                            screened += 1
        self.assertGreater(unreviewed, 0)
        self.assertEqual(refused + screened, unreviewed)


if __name__ == "__main__":
    unittest.main()
