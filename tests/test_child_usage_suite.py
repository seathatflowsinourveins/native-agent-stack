"""Runs examples/claude-native/workflows/test-child-usage.mjs, the synthetic-row suite of
child-usage.mjs (usage accounting and the per-child lanes object), so `python3 -m unittest` and the
CI step that runs it exercise that script. No provider call; not native evidence.

It also checks the evidence tooling of the U1 pivot (evidence/artifacts/pra-u1-differential-20260929) on synthetic inputs,
and that the decision record's first overturn condition quotes what counts.json measured."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "examples" / "claude-native" / "workflows" / "test-child-usage.mjs"
KERNEL = ROOT / "examples" / "claude-native" / "workflows" / "child-usage.mjs"
EVIDENCE = ROOT / "evidence" / "artifacts" / "pra-u1-differential-20260929"
DECISION = ROOT / "docs" / "decisions" / "2026-09-29-shell-command-parser.md"
PARSER_DIR = Path(os.environ.get("CHILD_USAGE_SHELL_PARSER") or Path.home() / ".local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1")


class ChildUsageNodeSuite(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_suite_passes(self):
        result = subprocess.run(["node", str(SUITE)], cwd=SUITE.parent, capture_output=True, text=True,
                                timeout=300, check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        summary = re.search(r"^SUMMARY passed=(\d+) failed=(\d+) total=(\d+)$", result.stdout, re.M)
        self.assertIsNotNone(summary, result.stdout[-2000:])
        self.assertEqual(summary.group(2), "0")
        self.assertGreater(int(summary.group(1)), 0)


# Synthetic shell texts (nothing from a host) with known shapes, in the order the expected counts below follow. tree-sitter-bash 0.25.1
# (pinned by integrity) reads each as noted; a pin update has to re-check them.
SHAPE_TEXTS = [
    "echo a; (( qmd status",                # a parse error; the lane word lies inside an ERROR node and no lane is read
    "echo a ) qmd status",                  # a parse error; the lane word lies outside its ERROR node and no lane is read
    "case x in a) qmd status;; esac esac",  # a parse error; the reading reads the lane from the valid part
    "cat <<2\nqmd status\n2>&1 x\n2",       # a heredoc the grammar ends early, with a lane word in its body; no error
    "bash -c 'qmd status;((('",            # the error is only in a script the reading read again (a shell string)
    "qmd status",                           # a lane invocation and no grammar limit
    "echo qmd",                             # a lane word only
    "ls -la",                               # neither
    "echo a ) echo qmd",                    # a parse error; the lane word follows plain words, so it is an argument whatever the tree makes of it
    'echo a ) ; echo "x; qmd"',             # a parse error; the lane word stands where a command name could, but the tree puts it in a string
]
# An unread lane word of a limit command is one of: no command slot (an argument), a slot the tree puts in data (a comment, heredoc body,
# string or assignment value), a slot anywhere else (an ERROR node included), or unplaced (the error is only in a script read again).
# The bound counts a limit command that reads a lane, is a heredoc ended early with a lane word, or holds an unplaced or slot-elsewhere word.
EXPECTED_SHAPES = {
    "commands": 10, "with_a_parse_error": 6, "with_a_lane_invocation": 2, "with_a_lane_word": 9, "lane_bearing_upper": 9,
    "grammar_limit": 7, "grammar_limit_with_a_lane_word": 7, "grammar_limit_lane_read": 1, "grammar_limit_lane_word_unread": 6,
    "grammar_limit_lane_word_in_an_error_node": 1, "grammar_limit_early_with_a_lane_word": 1,
    "grammar_limit_error_only_in_a_script_read_again": 1, "grammar_limit_error_only_in_a_script_read_again_lane_word": 1,
    "grammar_limit_unread_no_command_slot": 1, "grammar_limit_unread_slot_in_data": 2, "grammar_limit_unread_slot_elsewhere": 2,
    "grammar_limit_unread_unplaced": 1, "grammar_limit_lost_or_invented_upper": 5, "grammar_limit_scanner_reads_more": None,
    "grammar_limit_scanner_throws": None,
}
# 5 commands the limit can lose or invent a lane in, of 2 that read a lane: a threshold of 0.001 is one command.
EXPECTED_OVERTURN = {
    "threshold": 0.001, "threshold_commands": 1, "lane_bearing": 2, "lane_bearing_upper": 9, "lost_or_invented_upper_bound": 5,
    "rate_upper_bound": 2.5, "rate_lane_word_screen": 3.5, "met_by_the_upper_bound": True,
}


def transcript_row(command, timestamp):
    return json.dumps({"timestamp": timestamp, "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]}})


class PraU1EvidenceTooling(unittest.TestCase):
    def run_node(self, script, *args):
        done = subprocess.run(["node", str(EVIDENCE / script), *map(str, args)], capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        return json.loads(done.stdout)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    @unittest.skipUnless((PARSER_DIR / "package-lock.json").is_file(), "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_shape_counts_evaluate_the_first_overturn_condition(self):
        """Lane-bearing commands are counted without the parser (a lane word), and a grammar limit is bounded from the tree's own
        limits: a lane word inside an ERROR node, a heredoc ended early with a lane word, an error only in a script read again
        with a lane word, or a lane read from a tree with an error. --scanner adds the second reading's opinion."""
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus.json"
            corpus.write_text(json.dumps(SHAPE_TEXTS))
            scanner = Path(tmp) / "scanner.mjs"
            scanner.write_text("export const commandInvocations = () => [{ lane: 'qmd' }]\n")  # reads a qmd in every text
            throwing = Path(tmp) / "throwing.mjs"
            throwing.write_text("export const commandInvocations = () => { throw new Error('scanner failed') }\n")
            plain = self.run_node("shape-counts.mjs", "--kernel", KERNEL, "--inputs", corpus)
            crossed = self.run_node("shape-counts.mjs", "--kernel", KERNEL, "--inputs", corpus, "--scanner", scanner)
            failed = self.run_node("shape-counts.mjs", "--kernel", KERNEL, "--inputs", corpus, "--scanner", throwing)
        for key, want in EXPECTED_SHAPES.items():
            self.assertEqual(plain.get(key, "(missing)"), want, key)
        self.assertEqual(plain.get("overturn_1"), EXPECTED_OVERTURN)
        # the four counts of unread lane words partition the unread limit commands
        unread = [plain["grammar_limit_unread_" + k] for k in ("no_command_slot", "slot_in_data", "slot_elsewhere", "unplaced")]
        self.assertEqual(sum(unread), plain["grammar_limit_lane_word_unread"])
        # the scanner finds the qmd that the tree reading does not read in the six limit texts where it reads none
        self.assertEqual((crossed.get("grammar_limit_scanner_reads_more"), crossed.get("grammar_limit_scanner_throws")), (6, 0))
        # a scanner that throws is counted, not fatal, and reads nothing
        self.assertEqual((failed.get("grammar_limit_scanner_reads_more"), failed.get("grammar_limit_scanner_throws")), (0, 7))

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_identity_check_compares_whole_lane_records_of_two_kernels(self):
        """--fields lanes compares commandInvocations and measureTranscript(...).cli_lanes of two kernels, input by input: a
        difference in either, or an exception in either kernel, is counted and never hidden."""
        stub = "export const loadShellParser = async () => ({ ok: true })\nexport const executedText = () => 'x'\nexport const fetchKind = () => null\n"
        a = stub + "export const commandInvocations = (t) => [{ lane: t.length > 3 ? 'qmd' : null }]\nexport const measureTranscript = () => ({ cli_lanes: { calls: 1 } })\n"
        b = stub + ("export const commandInvocations = (t) => { if (t === 'boom') throw new Error('x'); return [{ lane: t === 'differ' ? 'toon' : t.length > 3 ? 'qmd' : null }] }\n"
                    "export const measureTranscript = (r) => ({ cli_lanes: { calls: r[0].message.content[0].input.command === 'cli' ? 2 : 1 } })\n")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mjs").write_text(a)
            (Path(tmp) / "b.mjs").write_text(b)
            inputs = Path(tmp) / "inputs.json"
            inputs.write_text(json.dumps(["same one", "differ", "boom", "ab", "cli"]))
            totals = self.run_node("m4-identity.mjs", "--a", Path(tmp) / "a.mjs", "--b", Path(tmp) / "b.mjs", "--inputs", inputs, "--fields", "lanes")
        # 'same one' and 'ab' agree; 'differ' differs in a lane, 'cli' only in cli_lanes; 'boom' throws in b
        self.assertEqual(totals, {"inputs": 5, "analysed": 5, "identical": 2, "different": 2, "a_throws": 0, "b_throws": 1})

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    @unittest.skipUnless((PARSER_DIR / "package-lock.json").is_file(), "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_identity_check_of_a_kernel_with_itself_finds_no_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp) / "inputs.json"
            inputs.write_text(json.dumps(SHAPE_TEXTS))
            totals = self.run_node("m4-identity.mjs", "--a", KERNEL, "--b", KERNEL, "--inputs", inputs, "--fields", "lanes")
        self.assertEqual(totals, {"inputs": 10, "analysed": 10, "identical": 10, "different": 0, "a_throws": 0, "b_throws": 0})

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_real_commands_reproduces_a_corpus_as_of_a_timestamp(self):
        """--until keeps the shell texts first seen at or before the instant, so a later run rebuilds the corpus of an earlier one."""
        rows = [transcript_row("echo first", "2026-09-29T07:00:00.000Z"), transcript_row("echo second", "2026-09-29T07:08:06.392Z"),
                transcript_row("echo third", "2026-09-29T07:08:08.754Z"), transcript_row("echo first", "2026-09-29T07:08:10.000Z")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            root.mkdir()
            (root / "session.jsonl").write_text("\n".join(rows) + "\n")
            out = Path(tmp) / "corpus.json"
            cut = self.run_node("real-commands.mjs", out, root, "--until", "2026-09-29T07:08:07Z")
            self.assertEqual(json.loads(out.read_text()), ["echo first", "echo second"])
            self.assertEqual((cut.get("until"), cut.get("distinct_shell_texts")), ("2026-09-29T07:08:07Z", 2))
            whole = self.run_node("real-commands.mjs", out, root)
            self.assertEqual(json.loads(out.read_text()), ["echo first", "echo second", "echo third"])
            self.assertEqual((whole.get("until"), whole.get("distinct_shell_texts")), (None, 3))


class DecisionRecordOverturnCondition(unittest.TestCase):
    def test_first_overturn_condition_quotes_the_measured_bound(self):
        """The record evaluates the condition from counts.json (shapes.overturn_1), not from the count of tree errors alone."""
        counts = json.loads((EVIDENCE / "counts.json").read_text())
        overturn = counts["shapes"].get("overturn_1")
        self.assertIsNotNone(overturn, "counts.json has no shapes.overturn_1: the condition was never evaluated")
        text = DECISION.read_text()
        section = text.split("## What would overturn it", 1)[1].split("\n## ", 1)[0]
        bound, denominator = overturn["lost_or_invented_upper_bound"], overturn["lane_bearing"]
        self.assertIn(f"an upper bound of {bound} of {denominator:,} lane-bearing commands ({overturn['rate_upper_bound'] * 100:.3f}%)", section)
        self.assertIn(f"a threshold of {overturn['threshold_commands']} commands", section)
        self.assertIn("**not met**" if not overturn["met_by_the_upper_bound"] else "**met**", section)
        shapes = counts["shapes"]
        self.assertIn(f"{shapes['grammar_limit_with_a_lane_word']} of the {shapes['grammar_limit']}", section)
        self.assertEqual(counts["corpus"]["distinct_shell_texts"], shapes["commands"])


if __name__ == "__main__":
    unittest.main()
