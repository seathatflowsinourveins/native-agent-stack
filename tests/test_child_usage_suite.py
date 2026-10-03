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


def bash_is_5_2() -> bool:
    """The real-shell probe documents its curl counts for bash 5.2 (Ubuntu 24.04 ships 5.2.21). macOS runners have bash 3.2
    (/bin/bash) or a newer Homebrew bash first on PATH, and one R3 fixture differs there (hosted run 36618373211, validate-macos),
    so the two real-shell tests below run only where `bash` is 5.2 and are skipped elsewhere with that reason."""
    exe = shutil.which("bash")
    if not exe:
        return False
    try:
        done = subprocess.run([exe, "-c", 'echo "${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]}"'], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.stdout.strip() == "5.2"


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
    @unittest.skipUnless((PARSER_DIR / "package-lock.json").is_file(), "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_shape_counts_report_the_largest_commands(self):
        """The maxima that bound the shapes whose parse is quadratic (a run of here-document operators or of array openers): the longest
        command, the most heredoc operators (a here-string <<< is not one) and the most `=(` in one command."""
        texts = ["a=(x y); b=(z)", "cat <<A <<B\nx\nA\ny\nB", "cat <<<word", "ls"]
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus.json"
            corpus.write_text(json.dumps(texts))
            shapes = self.run_node("shape-counts.mjs", "--kernel", KERNEL, "--inputs", corpus)
        self.assertEqual((shapes.get("longest_command_chars"), shapes.get("most_heredoc_operators_in_a_command"), shapes.get("most_array_openers_in_a_command")),
                         (max(len(t) for t in texts), 2, 2))

    def real_shells(self, *extra):
        done = subprocess.run(["python3", str(EVIDENCE / "m4-real-shells.py"), "--repo", str(ROOT), *extra], capture_output=True, text=True, timeout=600, check=False)
        return done, (json.loads(done.stdout) if done.stdout.strip().startswith("{") else None)

    @unittest.skipUnless(shutil.which("node") and bash_is_5_2() and shutil.which("dash"), "node, bash 5.2 (the documented counts) and dash are needed")
    def test_m4_fixtures_agree_with_real_bash_and_dash_and_the_kernel(self):
        """m4-real-shells.py runs every fixture of the M4 decisions (D7, R1, R3, heredoc expansion, backquote anchor) under real bash and dash with
        a stub curl: the stub must run as often as documented in both shells, and the kernel must call a fetch confirmed exactly when it ran."""
        done, report = self.real_shells()
        self.assertEqual(done.returncode, 0, done.stdout[-1500:] + done.stderr[-1500:])
        self.assertEqual((report["fixtures"], report["agree"], report["disagree"]), (75, 75, 0))
        self.assertEqual(sorted(report["groups"]), ["BQ_DATA", "BQ_ONCE", "D7_DATA", "D7_EXECUTED", "D7_INNER", "D7_TWICE", "HD_DATA", "HD_ONCE", "HD_TWICE",
                                                    "R1_DATA", "R1_EXECUTED", "R1_MULTILINE", "R3_EXECUTED"])
        self.assertNotIn("example.org", done.stdout)  # counts only: no command text

    @unittest.skipUnless(shutil.which("node") and bash_is_5_2() and shutil.which("dash"), "node, bash 5.2 (the documented counts) and dash are needed")
    def test_m4_real_shells_probe_fails_when_the_stub_curl_logs_nothing(self):
        """Negative control of the probe itself: with stubs that log nothing, the 67 fixtures that should run curl disagree and the exit is 1."""
        done, report = self.real_shells("--control", "silent-curl")
        self.assertEqual(done.returncode, 1, done.stdout[-1500:] + done.stderr[-1500:])
        self.assertEqual((report["fixtures"], report["disagree"], report["control"]), (75, 67, "silent-curl"))

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
    def test_scaling_times_commandinvocations_by_size_and_shape(self):
        """scaling.mjs prints, per shape, the length of the text and the best time at each size, and the largest growth from one size to the
        next where the earlier time is measurable; a run over the limit ends the shape."""
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "kernel.mjs"
            stub.write_text("export const commandInvocations = (text) => [{ lane: null, length: text.length }]\n"
                            "export const withShellTree = (text, visit) => visit({ hasError: text.length < 0 })\n")
            bare = Path(tmp) / "bare.mjs"
            bare.write_text("export const commandInvocations = (text) => []\n")  # no withShellTree: no parse-only series
            out = self.run_node("scaling.mjs", "--kernel", stub, "--sizes", "50,100,200", "--shapes", "words,comments", "--runs", "2")
            without = self.run_node("scaling.mjs", "--kernel", bare, "--sizes", "50,100", "--shapes", "words", "--runs", "1")
        self.assertEqual(out["sizes"], [50, 100, 200])
        self.assertEqual(sorted(out["shapes"]), ["comments", "words"])
        for name, shape in out["shapes"].items():
            self.assertEqual(len(shape["chars"]), 3, name)
            self.assertEqual(len(shape["ms"]), 3, name)
            self.assertTrue(all(isinstance(t, (int, float)) and t >= 0 for t in shape["ms"]), name)
            self.assertIn("max_ratio", shape)
            # the time of the parse alone (kernel.withShellTree with nothing to do), to tell a slow parse from a slow reading
            self.assertEqual(len(shape["parse_ms"]), 3, name)
            self.assertIn("parse_max_ratio", shape)
        self.assertIsNone(without["shapes"]["words"]["parse_ms"])
        self.assertEqual(out["shapes"]["comments"]["chars"], [100, 200, 400])  # '# c\n' x ceil(2n / 4)... = about 2n characters
        self.assertRegex(out["kernel_sha256"], r"^[0-9a-f]{12}$")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    @unittest.skipUnless((PARSER_DIR / "package-lock.json").is_file(), "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_update_round2_splices_the_new_sections_into_counts(self):
        """update-round2.py re-runs only the shape scan, the whole-record identity check against a baseline kernel, the scaling
        measurement and the totals of the differential, and writes them (with the corpus and its cutoff) into a copy of counts.json,
        leaving every other section alone. A re-run differential is compared with round 1's record of the same corpus."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            corpus = tmp / "real.json"
            corpus.write_text(json.dumps(SHAPE_TEXTS))
            scanner = tmp / "scanner.mjs"
            scanner.write_text("export const commandInvocations = () => [{ lane: 'qmd' }]\n")
            counts = tmp / "counts.json"
            same_as_before = {"inputs": 10, "bash_valid": None, "same": 2, "differ": 8, "old_throws": 0, "new_throws": 0, "new_program_outside_vocabulary": 0,
                              "old_program_outside_vocabulary": 0, "differ_new_parse_error": 5, "differ_kinds": {"lanes": 8}}
            recorded = {"real": {"differ": 113}, "synthetic": {**same_as_before, "distinct_witnesses": 5}, "changed": {**same_as_before, "same": 3}}
            counts.write_text(json.dumps({"kernels": {"new_sha256": "earlier"}, "differential": recorded}))
            done = subprocess.run(["python3", str(EVIDENCE / "update-round2.py"), "--repo", str(ROOT), "--scanner", str(scanner), "--baseline", str(KERNEL),
                                   "--work", str(tmp / "work"), "--real", str(corpus), "--real-until", "2026-09-29T07:08:07Z", "--until-reconstructed",
                                   "--identity", f"synthetic={corpus}",
                                   "--differential", f"synthetic={corpus}", f"changed={corpus}", f"unrecorded={corpus}",
                                   "--sizes", "50,100", "--counts", str(counts)], capture_output=True, text=True, timeout=300, check=False)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            out = json.loads(counts.read_text())
        self.assertEqual(out["differential"], recorded)  # every other section is left alone
        self.assertEqual(out["kernels"], {"new_sha256": "earlier"})
        self.assertEqual(out["corpus"], {"source": "real-commands.mjs", "until": "2026-09-29T07:08:07Z", "until_reconstructed": True, "distinct_shell_texts": 10})
        self.assertEqual(out["shapes"]["overturn_1"], EXPECTED_OVERTURN)
        self.assertEqual(out["shapes"]["grammar_limit_scanner_reads_more"], 6)
        identity = out["lanes_identity"]
        self.assertEqual(identity["baseline_sha256"], identity["kernel_sha256"])  # the baseline here is the kernel itself
        self.assertEqual(identity["corpora"], {"synthetic": {"inputs": 10, "analysed": 10, "identical": 10, "different": 0, "a_throws": 0, "b_throws": 0}})
        self.assertEqual(sorted(out["scaling"]), ["baseline", "kernel"])
        self.assertEqual(out["scaling"]["kernel"]["sizes"], [50, 100])
        # the stub scanner reads a qmd in every text, so the differential of the ten texts is 2 the same and 8 different (5 with a parse error);
        # it equals the round-1 record of "synthetic" (whose distinct_witnesses needs a reduction and is not compared), not that of "changed"
        rerun = out["differential_rerun"]
        self.assertEqual({k: v for k, v in rerun["synthetic"].items() if k != "equal_to_round1"}, same_as_before)
        self.assertEqual([rerun[k]["equal_to_round1"] for k in ("synthetic", "changed", "unrecorded")], [True, False, None])
        self.assertEqual(out["round2"]["sections"], ["corpus", "shapes", "lanes_identity", "scaling", "differential_rerun"])

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
        section = " ".join(text.split("## What would overturn it", 1)[1].split("\n## ", 1)[0].split())  # line wrapping does not matter
        bound, denominator = overturn["lost_or_invented_upper_bound"], overturn["lane_bearing"]
        self.assertIn(f"an upper bound of {bound} of {denominator:,} lane-bearing commands ({overturn['rate_upper_bound'] * 100:.3f}%)", section)
        self.assertIn(f"a threshold of {overturn['threshold_commands']} commands", section)
        self.assertIn("**not met**" if not overturn["met_by_the_upper_bound"] else "**met**", section)
        shapes = counts["shapes"]
        self.assertIn(f"{shapes['grammar_limit_with_a_lane_word']} of the {shapes['grammar_limit']}", section)
        self.assertEqual(counts["corpus"]["distinct_shell_texts"], shapes["commands"])


if __name__ == "__main__":
    unittest.main()
