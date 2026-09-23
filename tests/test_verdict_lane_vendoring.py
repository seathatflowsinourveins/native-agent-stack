"""The Claude lane workflow is vendored into the catalog (2026-09-23 peer audit).

The layer-verdict Claude lane used to live only in agent-lab, unpinned, so a host
holding only this catalog could not reproduce it. The vendored bytes sit under
examples/claude-native/workflows/ and its SHA256SUMS (checked byte for byte by
validate.yml); record_verdicts.py accepts a new-wave Claude return only when its
provenance.workflow_sha256 matches that SHA256SUMS entry.
"""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "examples" / "claude-native" / "workflows"


def sums():
    result = {}
    for line in (WORKFLOWS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(None, 1)
        result[name.lstrip("*")] = digest
    return result


class VendoredLaneWorkflowTests(unittest.TestCase):
    def test_layer_verdict_lane_workflow_is_vendored_under_sha256sums(self):
        path = WORKFLOWS / "layer-verdict-lane.js"
        self.assertTrue(path.is_file(), "examples/claude-native/workflows/layer-verdict-lane.js must be vendored")
        self.assertEqual(sums().get("layer-verdict-lane.js"), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_the_vendored_lane_records_its_agent_lab_source_pin(self):
        pin = json.loads((WORKFLOWS / "vendored-lanes.json").read_text(encoding="utf-8"))
        entry = next(item for item in pin["files"] if item["path"] == "layer-verdict-lane.js")
        self.assertRegex(entry["agentlab_commit"], r"^[a-f0-9]{40}$")
        self.assertEqual(entry["source_path"], ".claude/workflows/layer-verdict-lane.js")
        self.assertEqual(entry["sha256"], sums()["layer-verdict-lane.js"])

    def test_the_lane_prompt_it_fills_is_the_catalog_copy(self):
        # lane-prompt.md was already in the catalog; codex_lane.py and the packets read it from there.
        self.assertTrue((ROOT / "tools" / "sota-convergence" / "lane-prompt.md").is_file())


if __name__ == "__main__":
    unittest.main()
