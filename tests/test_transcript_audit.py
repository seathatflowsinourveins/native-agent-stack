"""Tests for tools/sota-convergence/transcript_audit.py: the blind audit of a Claude workflow run's agent transcripts
(Codex review of #145 at 68e74f2c), including the evasion and fail-closed cases the round-9 review targets."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("transcript_audit", ROOT / "tools/sota-convergence/transcript_audit.py")
transcript_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transcript_audit)

RESULT = {"layers": [{"layer_id": "layer"}]}


class TranscriptAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.export = self.base / "hosts" / "blind" / "export"
        (self.export / "evidence").mkdir(parents=True)
        (self.export / "evidence" / "receipt.json").write_text("{}", encoding="utf-8")
        self.packet = self.base / "work" / "packets" / "foundation__layer.json"
        self.packet.parent.mkdir(parents=True)
        self.packet.write_text("{}", encoding="utf-8")
        self.session = self.base / "projects" / "slug" / "session-1"
        self.run = self.session / "subagents" / "workflows" / "wf_1"
        self.run.mkdir(parents=True)
        self.items = {"foundation__layer": {"marker": str(self.packet), "roots": [str(self.export), str(self.packet)]}}
        self.agents = []

    def agent(self, name, calls, prompt=None, cwd="export", raw_tail=None, parts=None):
        """One agent transcript: its prompt, then an assistant message with ``calls`` [(tool, input)] (or ``parts``)."""
        cwd = str(self.export) if cwd == "export" else cwd
        content = parts if parts is not None else [{"type": "tool_use", "name": tool, "input": inputs}
                                                   for tool, inputs in calls]
        lines = [{"type": "user", "message": {"role": "user", "content": prompt or f"Read the packet at {self.packet}"}},
                 {"type": "assistant", "message": {"role": "assistant", "content": content}}]
        if cwd is not None:
            for line in lines:
                line["cwd"] = cwd
        text = "".join(json.dumps(line) + "\n" for line in lines) + (raw_tail or "")
        (self.run / f"agent-{name}.jsonl").write_text(text, encoding="utf-8")
        self.agents.append(name)
        self.record()

    def record(self, **change):
        (self.session / "workflows").mkdir(exist_ok=True)
        record = {"status": "completed", "result": RESULT,
                  "workflowProgress": [{"type": "workflow_agent", "agentId": agent} for agent in self.agents]}
        record.update(change)
        (self.session / "workflows" / "wf_1.json").write_text(json.dumps(record), encoding="utf-8")

    def flagged(self, **kwargs):
        kwargs.setdefault("export", self.export)
        kwargs.setdefault("result", RESULT)
        return transcript_audit.audit(self.run, self.items, **kwargs)["flagged_items"]

    def fresh(self):
        for path in self.run.glob("agent-*.jsonl"):
            path.unlink()
        self.agents = []

    def assert_flags(self, calls, **agent_kwargs):
        self.fresh()
        self.agent("a", calls, **agent_kwargs)
        self.assertEqual(self.flagged(), ["foundation__layer"], calls)

    def test_reads_inside_the_item_roots_are_clean(self):
        self.agent("a", [("Read", {"file_path": str(self.packet)}), ("Read", {"file_path": "evidence/receipt.json"}),
                         ("Read", {"file_path": "evidence/../evidence/receipt.json"}),
                         ("Glob", {"pattern": "docs/**/*.md"}), ("Grep", {"pattern": "winner", "glob": "*.md"}),
                         ("StructuredOutput", {})])
        # Two agents on one item (a judge and its refuter) are both audited.
        self.agent("b", [("Grep", {"pattern": "x", "path": str(self.export / "evidence")})])
        report = transcript_audit.audit(self.run, self.items, export=self.export, result=RESULT)
        self.assertEqual(report["flagged_items"], [])
        self.assertEqual(report["items"]["foundation__layer"]["agents"], 2)

    def test_globs_and_greps_that_reach_outside_flag(self):
        for call in [("Glob", {"pattern": "../**/*.json"}),
                     ("Glob", {"pattern": "docs/**/../../../work/*.json"}),
                     ("Glob", {"pattern": str(self.base / "work") + "/*/*.json"}),
                     ("Glob", {"pattern": "*.json", "path": str(self.base / "work")}),
                     ("Grep", {"pattern": "x", "path": str(self.base)}),
                     ("Grep", {"pattern": "x", "glob": "../*.json"}),
                     ("Grep", {"pattern": "x", "glob": str(self.base) + "/**"})]:
            with self.subTest(call=call):
                self.assert_flags([call])

    def test_reads_that_resolve_outside_flag(self):
        outside = self.base / "work" / "codex" / "foundation__layer.json"
        outside.parent.mkdir(parents=True)
        outside.write_text("{}", encoding="utf-8")
        (self.export / "evidence" / "link.json").symlink_to(outside)
        for call in [("Read", {"file_path": str(outside)}),
                     ("Read", {"file_path": "../../../work/codex/foundation__layer.json"}),
                     ("Read", {"file_path": "evidence/link.json"}),
                     ("Read", {"file_path": str(self.export) + "/../../../work/codex/foundation__layer.json"})]:
            with self.subTest(call=call):
                self.assert_flags([call])
        upper = str(self.export).upper()
        if not os.path.exists(upper):  # a case-sensitive filesystem: a case variant is another path
            self.assert_flags([("Read", {"file_path": upper + "/evidence/receipt.json"})])

    def test_tools_and_calls_the_audit_does_not_model_flag(self):
        for calls in [[("Bash", {"command": "ls"})], [("mcp__memory__query", {"q": "winner"})],
                      [("WebFetch", {"url": "https://example.invalid"})], [("Agent", {"prompt": "x"})],
                      [(None, {})], [({"name": "Read"}, {})], [("Read", "not an object")], [("Read", {})]]:
            with self.subTest(calls=calls):
                self.assert_flags(calls)
        # A server-side tool (web search) is a call too, whatever its content type.
        self.assert_flags([], parts=[{"type": "server_tool_use", "name": "web_search", "input": {"query": "x"}}])

    def test_unreadable_unbound_and_unserved_transcripts_flag(self):
        # A transcript cut off mid-JSON.
        self.assert_flags([("Read", {"file_path": str(self.packet)})],
                          raw_tail='{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Re')
        # No recorded working directory for a relative read, or another working directory than the export.
        self.assert_flags([("Read", {"file_path": "evidence/receipt.json"})], cwd=None)
        self.assert_flags([("Read", {"file_path": str(self.packet)})], cwd=str(self.base))
        # A prompt naming two items.
        other = dict(self.items, other={"marker": "OTHER-MARKER", "roots": [str(self.export)]})
        self.fresh()
        self.agent("a", [("Read", {"file_path": str(self.packet)})], prompt=f"{self.packet} and OTHER-MARKER")
        self.assertEqual(transcript_audit.audit(self.run, other, export=self.export, result=RESULT)["flagged_items"],
                         ["foundation__layer", "other"])
        # An item no agent served.
        self.fresh()
        self.agent("a", [("Read", {"file_path": str(self.packet)})])
        self.assertEqual(transcript_audit.audit(self.run, dict(self.items, unserved={
            "marker": "NOBODY", "roots": []}), export=self.export, result=RESULT)["flagged_items"], ["unserved"])

    def test_run_level_problems_flag_every_item(self):
        self.agent("a", [("Read", {"file_path": str(self.packet)})])
        self.assertEqual(self.flagged(), [])
        checks = [({"status": "running"}, "did not complete"), ({"result": {"layers": []}}, "another result"),
                  ({"workflowProgress": [{"type": "workflow_agent", "agentId": "a"},
                                         {"type": "workflow_agent", "agentId": "b"}]}, "missing")]
        for change, reason in checks:
            with self.subTest(reason=reason):
                self.record(**change)
                report = transcript_audit.audit(self.run, self.items, export=self.export, result=RESULT)
                self.assertEqual(report["flagged_items"], ["foundation__layer"])
                self.assertIn(reason, report["run_issue"])
        self.record()
        # A nested agent transcript the run record does not list.
        nested = self.run / "nested"
        nested.mkdir()
        (nested / "agent-z.jsonl").write_text("", encoding="utf-8")
        self.assertIn("extra", transcript_audit.audit(self.run, self.items)["run_issue"])
        (nested / "agent-z.jsonl").unlink()
        # A flagged agent naming no item flags every item.
        self.agent("b", [("Read", {"file_path": "/etc/hostname"})], prompt="an orchestration step")
        report = transcript_audit.audit(self.run, self.items, export=self.export, result=RESULT)
        self.assertEqual(report["flagged_items"], ["foundation__layer"])
        self.assertEqual(len(report["unmapped_flagged"]), 1)
        # Without its run record the transcripts are not one run's.
        (self.session / "workflows" / "wf_1.json").unlink()
        self.assertIn("no workflow run record", transcript_audit.audit(self.run, self.items)["run_issue"])

    def test_an_agent_naming_another_audits_item_is_skipped_only_with_its_prefix(self):
        self.agent("a", [("Read", {"file_path": str(self.packet)})])
        self.agent("b", [("Read", {"file_path": "/elsewhere/other.json"})], prompt="Input file: /elsewhere/other.json")
        self.assertEqual(self.flagged(), ["foundation__layer"])
        self.assertEqual(self.flagged(marker_prefix="Input file: "), [])

    def test_the_digest_binds_the_transcripts_and_the_run_record(self):
        self.agent("a", [])
        before = transcript_audit.transcripts_sha256(self.run)
        self.record(extra=1)
        after_record = transcript_audit.transcripts_sha256(self.run)
        self.assertNotEqual(before, after_record)
        self.agent("b", [])
        self.assertNotEqual(after_record, transcript_audit.transcripts_sha256(self.run))

    def test_locate_finds_the_one_workflow_run_of_a_session(self):
        projects = self.base / "p"
        run = projects / transcript_audit.project_slug(self.export) / "s1" / "subagents" / "workflows" / "wf_1"
        run.mkdir(parents=True)
        self.assertEqual(transcript_audit.workflow_transcript_dir(self.export, "s1", projects), run)
        (run.parent / "wf_2").mkdir()
        with self.assertRaisesRegex(ValueError, "found 2"):
            transcript_audit.workflow_transcript_dir(self.export, "s1", projects)
        with self.assertRaisesRegex(ValueError, "not a session id"):
            transcript_audit.workflow_transcript_dir(self.export, "../s1", projects)
        self.assertEqual(transcript_audit.project_slug("/home/example/code/agent-lab"), "-home-example-code-agent-lab")


if __name__ == "__main__":
    unittest.main()
