"""Synthetic-fixture tests for tools/sota-convergence/claude_lane.py (2026-09-23 peer audit).

The Claude lane workflow returns its layers without writing files; claude_lane.py is the step
that writes <work-dir>/claude/<catalog>__<layer_id>.json with the runner-owned model.family and
provenance a new-wave return needs, refusing workflow bytes that are uncommitted or not vendored.
"""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.landscape import lane_model_issue, lane_provenance_issue

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "examples" / "claude-native" / "workflows" / "layer-verdict-lane.js"


def load_module():
    spec = importlib.util.spec_from_file_location("claude_lane", ROOT / "tools" / "sota-convergence" / "claude_lane.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claude_lane = load_module()


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class ClaudeLaneWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.agentlab = self.tmp / "agent-lab"
        workflow = self.agentlab / ".claude" / "workflows" / "layer-verdict-lane.js"
        workflow.parent.mkdir(parents=True)
        shutil.copyfile(VENDORED, workflow)
        self.workflow = workflow
        git(self.agentlab, "init", "-q")
        git(self.agentlab, "add", ".")
        git(self.agentlab, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "lane")
        self.work = self.tmp / "work"
        final = {"schema_version": 1, "lane": "claude", "catalog": "foundation", "layer_id": "l1",
                 "packet_sha256": "0" * 64, "model": {"name": "opus", "effort": "high"}}
        self.unrefuted = {"status": "unrefuted", "final_source": "proposal", "proposal_status": "unrefuted",
                          "revision_status": None, "votes": [
                              {"lens": "evidence", "round": "proposal", "refuted": False, "reason": "Paths hold."},
                              {"lens": "challenger", "round": "proposal", "refuted": False, "reason": "No rival."}]}
        refuted = {"status": "refuted", "final_source": None, "proposal_status": "refuted", "revision_status": None,
                   "votes": [{"lens": "evidence", "round": "proposal", "refuted": True, "reason": "A cited path is missing."},
                             {"lens": "challenger", "round": "proposal", "refuted": None, "reason": "no vote returned"}]}
        self.result = self.tmp / "result.json"
        self.result.write_text(json.dumps({
            "lane": "claude", "layers": [
                {"catalog": "foundation", "layer_id": "l1", "final": final, "refutation": self.unrefuted},
                {"catalog": "foundation", "layer_id": "l2", "proposal": {"x": 1}, "final": None,
                 "refutation": refuted}],
            "lost": ["us-equities/l3"]}), encoding="utf-8")

    def run_main(self, *extra):
        return claude_lane.main(["--result", str(self.result), "--work-dir", str(self.work),
                                 "--agentlab-root", str(self.agentlab), *extra])

    def test_written_return_carries_family_and_vendored_provenance(self):
        self.assertEqual(self.run_main("--resolved-model", "claude-opus-5-5"), 0)
        data = json.loads((self.work / "claude" / "foundation__l1.json").read_text(encoding="utf-8"))
        self.assertEqual(data["model"], {"name": "claude-opus-5-5", "effort": "high", "family": "anthropic"})
        self.assertIsNone(lane_model_issue("claude", data["model"]))
        self.assertIsNone(lane_provenance_issue("claude", data["provenance"]))
        self.assertEqual(data["provenance"]["workflow_path"], ".claude/workflows/layer-verdict-lane.js")
        self.assertEqual(data["provenance"]["workflow_sha256"], claude_lane.vendored_sums()["layer-verdict-lane.js"])
        self.assertFalse((self.work / "claude" / "foundation__l2.json").exists())

    def test_the_refutation_summary_is_copied_and_layers_without_a_final_are_listed_as_failures(self):
        # Review of catalog #122, findings 5 and 7: the lane's votes were dropped, and a layer without
        # a final (refuted, unknown or lost) was recorded as a bare "missing".
        self.assertEqual(self.run_main(), 0)
        data = json.loads((self.work / "claude" / "foundation__l1.json").read_text(encoding="utf-8"))
        self.assertEqual(data["refutation"], self.unrefuted)
        failures = json.loads((self.work / "claude" / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual([(item["catalog"], item["layer_id"]) for item in failures],
                         [("foundation", "l2"), ("us-equities", "l3")])
        self.assertIn("refutation status refuted", failures[0]["reason"])
        self.assertIn("A cited path is missing.", failures[0]["reason"])
        self.assertIn("lost", failures[1]["reason"])

    def test_a_prior_return_is_removed_when_its_layer_now_fails_or_is_lost(self):
        # Review of catalog #124 (claude_lane.py:148): a valid return from an earlier run must not
        # survive a later run whose final is null or whose packet is lost, or record_verdicts.py
        # would seal the stale return.
        out_dir = self.work / "claude"
        out_dir.mkdir(parents=True)
        stale = {"schema_version": 1, "lane": "claude", "note": "earlier run"}
        for name in ("foundation__l2.json", "us-equities__l3.json"):
            (out_dir / name).write_text(json.dumps(stale), encoding="utf-8")
        self.assertEqual(self.run_main(), 0)
        self.assertFalse((out_dir / "foundation__l2.json").exists())
        self.assertFalse((out_dir / "us-equities__l3.json").exists())
        self.assertTrue((out_dir / "foundation__l1.json").exists())
        failures = json.loads((out_dir / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual(len(failures), 2)

    def test_uncommitted_or_unvendored_workflow_bytes_are_refused(self):
        with self.workflow.open("a", encoding="utf-8") as handle:
            handle.write("// local edit\n")
        self.assertEqual(self.run_main(), 2)
        git(self.agentlab, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qam", "edit")
        self.assertEqual(self.run_main(), 2)
        self.assertFalse((self.work / "claude").exists())


if __name__ == "__main__":
    unittest.main()
