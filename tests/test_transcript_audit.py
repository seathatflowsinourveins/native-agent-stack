"""Tests for tools/sota-convergence/transcript_audit.py: the blind audit of a Claude workflow run's agent transcripts
(Codex review of #145 at 68e74f2c)."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("transcript_audit", ROOT / "tools/sota-convergence/transcript_audit.py")
transcript_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transcript_audit)


class TranscriptAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.export = self.base / "hosts" / "blind" / "export"
        self.export.mkdir(parents=True)
        self.packet = self.base / "work" / "packets" / "foundation__layer.json"
        self.transcripts = self.base / "transcripts"
        self.transcripts.mkdir()
        self.items = {"foundation__layer": {"marker": str(self.packet), "roots": [str(self.export), str(self.packet)]}}

    def agent(self, name, prompt, calls):
        lines = [{"type": "user", "cwd": str(self.export), "message": {"role": "user", "content": prompt}},
                 {"type": "assistant", "cwd": str(self.export), "message": {"role": "assistant", "content": [
                     {"type": "tool_use", "name": tool, "input": inputs} for tool, inputs in calls]}}]
        (self.transcripts / f"agent-{name}.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines),
                                                              encoding="utf-8")

    def test_reads_inside_the_item_roots_are_clean(self):
        self.agent("a", f"Read the packet at {self.packet}", [
            ("Read", {"file_path": str(self.packet)}), ("Read", {"file_path": "evidence/receipt.json"}),
            ("Glob", {"pattern": "docs/**/*.md"}), ("Grep", {"pattern": "winner"}), ("StructuredOutput", {})])
        report = transcript_audit.audit(self.transcripts, self.items)
        self.assertEqual(report["flagged_items"], [])
        self.assertEqual(report["items"]["foundation__layer"]["agents"], 1)

    def test_reads_outside_other_tools_and_climbing_patterns_flag(self):
        cases = [("Read", {"file_path": str(self.base / "work" / "codex" / "foundation__layer.json")}),
                 ("Glob", {"pattern": str(self.base / "work") + "/*/*.json"}),
                 ("Glob", {"pattern": "../../*.json"}),
                 ("Grep", {"pattern": "x", "path": str(self.base)}),
                 ("Bash", {"command": "ls"})]
        for index, call in enumerate(cases):
            with self.subTest(call=call):
                for path in self.transcripts.glob("*.jsonl"):
                    path.unlink()
                self.agent(str(index), f"Read the packet at {self.packet}", [call])
                self.assertEqual(transcript_audit.audit(self.transcripts, self.items)["flagged_items"],
                                 ["foundation__layer"])

    def test_an_unserved_item_or_a_flagged_unmapped_agent_flags(self):
        self.assertEqual(transcript_audit.audit(self.transcripts, self.items)["flagged_items"], ["foundation__layer"])
        self.agent("a", f"Read the packet at {self.packet}", [("Read", {"file_path": str(self.packet)})])
        self.agent("b", "an orchestration step", [("Read", {"file_path": "/etc/hostname"})])
        report = transcript_audit.audit(self.transcripts, self.items)
        self.assertEqual(report["flagged_items"], ["foundation__layer"])
        self.assertEqual(len(report["unmapped_flagged"]), 1)
        # An agent that names another item's marker belongs to an audit outside this one.
        (self.transcripts / "agent-b.jsonl").unlink()
        self.agent("c", "Input file: /elsewhere/other.json", [("Read", {"file_path": "/elsewhere/other.json"})])
        self.assertEqual(transcript_audit.audit(self.transcripts, self.items, marker_prefix="Input file: ")
                         ["flagged_items"], [])

    def test_the_digest_binds_every_transcript(self):
        self.agent("a", str(self.packet), [])
        before = transcript_audit.transcripts_sha256(self.transcripts)
        self.agent("b", str(self.packet), [])
        self.assertNotEqual(before, transcript_audit.transcripts_sha256(self.transcripts))


    def test_locate_finds_the_one_workflow_run_of_a_session(self):
        projects = self.base / "projects"
        run = projects / transcript_audit.project_slug(self.export) / "s1" / "subagents" / "workflows" / "wf_1"
        run.mkdir(parents=True)
        self.assertEqual(transcript_audit.workflow_transcript_dir(self.export, "s1", projects), run)
        (run.parent / "wf_2").mkdir()
        with self.assertRaisesRegex(ValueError, "found 2"):
            transcript_audit.workflow_transcript_dir(self.export, "s1", projects)
        self.assertEqual(transcript_audit.project_slug("/home/example/code/agent-lab"), "-home-example-code-agent-lab")

if __name__ == "__main__":
    unittest.main()
