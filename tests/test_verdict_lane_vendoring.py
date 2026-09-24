"""The Claude lane workflow is vendored into the catalog (2026-09-23 peer audit).

The layer-verdict Claude lane used to live only in agent-lab, unpinned, so a host
holding only this catalog could not reproduce it. The vendored bytes sit under
examples/claude-native/workflows/ and its SHA256SUMS (checked byte for byte by
validate.yml); record_verdicts.py accepts a new-wave Claude return only when its
provenance.workflow_sha256 matches that SHA256SUMS entry.
"""
import hashlib
import importlib.util
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


TOOLS = ROOT / "tools" / "sota-convergence"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LaneProvenanceRegistryTests(unittest.TestCase):
    """Review finding: provenance was format-checked only (the Codex hashes were never compared
    with codex_lane.py / lane-prompt.md, the Claude hash was looked up by basename, and CI never
    re-checked either). tools/sota-convergence/lane-provenance.json is the append-only list both
    record_verdicts.py and scripts/landscape.py check against; it must cover the current bytes."""

    def registry(self):
        return json.loads((TOOLS / "lane-provenance.json").read_text(encoding="utf-8"))

    def test_the_current_codex_lane_code_is_registered(self):
        current = {"codex_lane_py_sha256": sha256(TOOLS / "codex_lane.py"),
                   "prompt_sha256": sha256(TOOLS / "lane-prompt.md")}
        listed = [{key: entry[key] for key in current} for entry in self.registry()["codex"]]
        self.assertIn(current, listed, "append the current codex_lane.py/lane-prompt.md hashes to "
                                       "tools/sota-convergence/lane-provenance.json")

    def test_the_vendored_lane_echoes_what_the_collector_requires(self):
        """Re-review R1: claude_lane.py requires the result's prompt and launch, so the vendored workflow must
        return both and refuse a promptless real run (agent-lab #42 and #45)."""
        source = (ROOT / "examples" / "claude-native" / "workflows" / "layer-verdict-lane.js").read_text(encoding="utf-8")
        self.assertIn("return { lane: 'claude', launch: LAUNCH, prompt: PROMPT,", source)
        self.assertIn("packet_sha256: p.sha256, packet_path: p.path,", source)
        self.assertIn("prompt must be the lane-prompt.md text when packets are given", source)
        self.assertIn("launch must be an object whose repo equals repo", source)

    def test_the_current_adjudication_code_is_registered(self):
        """Independent review of #145, M2: record_verdicts.py and scripts/landscape.py refuse a new-wave
        adjudication whose code is not listed, so the current adjudicate.py, prompt, schemas, workflow and
        vendored blind-adjudicator role must be (append an entry whenever one of them changes)."""
        spec = importlib.util.spec_from_file_location("adjudicate_for_registry", TOOLS / "adjudicate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        provenance = module.adjudication_provenance()
        keys = ("adjudicate_py_sha256", "prompt_sha256", "judge_schema_sha256", "refute_schema_sha256",
                "workflow_sha256", "adjudicator_role_sha256")
        self.assertTrue(any(all(entry.get(key) == provenance[key] for key in keys)
                            for entry in self.registry().get("adjudication") or []),
                        "append the current adjudication provenance to tools/sota-convergence/lane-provenance.json")

    def test_every_vendored_lane_workflow_is_registered_under_its_source_and_vendored_paths(self):
        pin = json.loads((WORKFLOWS / "vendored-lanes.json").read_text(encoding="utf-8"))
        claude = self.registry()["claude"]
        for item in pin["files"]:
            vendored = f"examples/claude-native/workflows/{item['path']}"
            for workflow_path in (item["source_path"], vendored):
                self.assertIn({"workflow_path": workflow_path, "vendored_path": vendored,
                               "workflow_sha256": sums()[item["path"]]},
                              [{key: entry[key] for key in ("workflow_path", "vendored_path", "workflow_sha256")}
                               for entry in claude])

    def test_registry_entries_are_well_formed_and_unique(self):
        registry = self.registry()
        # agent_sha256 (the blind-lane-reviewer role hash) is part of the Claude key from 2026-09-23; entries
        # registered before it simply lack it (the registry is append-only).
        for lane, fields in (("claude", ("workflow_path", "workflow_sha256", "agent_sha256")),
                             ("codex", ("codex_lane_py_sha256", "prompt_sha256"))):
            keys = [tuple(entry.get(field) for field in fields) for entry in registry[lane]]
            self.assertEqual(len(keys), len(set(keys)), lane)
            for entry in registry[lane]:
                for field in fields:
                    if field.endswith("sha256") and field in entry:
                        self.assertRegex(entry[field], r"^[a-f0-9]{64}$")

    def test_the_blind_roles_are_in_the_maintained_adoption_source(self):
        # Codex review of #145: tools/adoption/install_claude_profile.py installs adoption/agents/claude/*.md,
        # so a fresh host gets exactly the vendored blind roles.
        for role in ("blind-lane-reviewer", "blind-adjudicator"):
            self.assertEqual((ROOT / "adoption/agents/claude" / f"{role}.md").read_bytes(),
                             (ROOT / "examples/claude-native/agents" / f"{role}.md").read_bytes(), role)

    def test_the_vendored_lane_role_is_registered(self):
        agent = hashlib.sha256((ROOT / "examples/claude-native/agents/blind-lane-reviewer.md").read_bytes()).hexdigest()
        self.assertIn(agent, [entry.get("agent_sha256") for entry in self.registry()["claude"]])


if __name__ == "__main__":
    unittest.main()
