"""Synthetic-fixture tests for tools/sota-convergence/adjudicate.py and adjudication-lane.js.

No model is called: the Codex family runs against the env-driven fake ``codex`` in
tests/fixtures/codex-lane/bin (see tests/test_codex_lane.py), and the Claude family's workflow return is
a canned object fed to ``claude-collect``.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
FAKE_BIN = ROOT / "tests" / "fixtures" / "codex-lane" / "bin"
CHECK_SYNTAX = ROOT / "examples" / "claude-native" / "workflows" / "check-syntax.mjs"

spec = importlib.util.spec_from_file_location("adjudicate", TOOL_DIR / "adjudicate.py")
adjudicate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adjudicate)
from scripts.landscape import judge_adjudication  # noqa: E402  (adjudicate put the repo root on sys.path)

NAME = "foundation__native-clients"
WHY = "A cites evidence/receipt.json, which records a native execution; B cites only a README claim."
PACKET = {
    "catalog": "foundation", "layer_id": "native-clients", "requirement": "a native client",
    "candidates": [
        {"key": "c1", "component_id": "comp-one", "repository": "https://github.com/example/one", "adopted": True},
        {"key": "c2", "component_id": "comp-two", "repository": "https://github.com/example/two", "adopted": True},
    ],
}


def lane_return(lane, winner, packet_sha256, **extra):
    row = {
        "schema_version": 1, "lane": lane, "catalog": "foundation", "layer_id": "native-clients",
        "packet_sha256": packet_sha256, "model": {"name": "x", "effort": "high"},
        "provenance": {"x": "y"}, "winner_keys": [winner],
        "why_selected": f"{winner} has evidence in evidence/receipt.json", "winner_evidence_class": "native_proven",
        "winner_evidence_refs": ["evidence/receipt.json"], "alternatives": [], "challenger_preferred": None,
        "overturn_when": "python3 tests/x.py", "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "open_gaps": [], "sources_read": ["evidence/receipt.json"], "limits": [],
    }
    row.update(extra)
    return row


def quiet(function, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
        code = function(*args)
    return code, err.getvalue()


class AdjudicateFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.work = self.base / "work"
        self.repo = self.base / "repo"
        self.repo.mkdir()
        for sub in ("packets", "claude", "codex"):
            (self.work / sub).mkdir(parents=True)
        packet_path = self.work / "packets" / f"{NAME}.json"
        packet_path.write_text(json.dumps(PACKET), encoding="utf-8")
        self.sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        self.write_return("claude", "c1", refutation={"status": "unrefuted"}, final_source="proposal")
        self.write_return("codex", "c2")

    def write_return(self, lane, winner, name=NAME, sha=None, **extra):
        path = self.work / lane / f"{name}.json"
        path.write_text(json.dumps(lane_return(lane, winner, sha or self.sha, **extra)), encoding="utf-8")

    def inputs(self):
        return quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work)])

    def judgment(self, lane, order, preferred_lane, refuted=False, model=None):
        family = adjudicate.FAMILIES[lane]
        claude_position = adjudicate.CLAUDE_POSITION[order]
        other = "B" if claude_position == "A" else "A"
        record = adjudicate.judgment_record(
            family, NAME, order, self.work / "adjudication-inputs" / f"{NAME}.{order}.json", self.sha,
            model or ("claude-opus-5-5" if lane == "claude" else "gpt-6-astra"), str(self.repo),
            {"preferred": claude_position if preferred_lane == "claude" else other, "why": WHY,
             "evidence_refs": [str(self.repo / "evidence/receipt.json")]},
            {"refuted": refuted, "reason": "The cited receipt exists and shows the run.", "evidence_refs": []})
        adjudicate.write_json(self.work / "adjudication-judgments" / lane / f"{NAME}.{order}.json", record)

    def assemble(self):
        out = self.base / "adjudications"
        code, err = quiet(adjudicate.main, ["assemble", "--work-dir", str(self.work), "--out", str(out)])
        path = out / f"{NAME}.json"
        return code, err, (json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None)

    def assert_valid(self, record):
        issue, result = judge_adjudication(record, grandfathered=False, packet_sha256=self.sha)
        self.assertIsNone(issue)
        return result


class InputsTests(AdjudicateFixture):
    def test_disagreement_is_detected_and_both_returns_are_scrubbed(self):
        code, _err = self.inputs()
        self.assertEqual(code, 0)
        index = json.loads((self.work / "adjudication-inputs" / "index.json").read_text(encoding="utf-8"))
        entry = index["layers"][0]
        self.assertEqual(entry["agreement"], "disagree")
        self.assertEqual(entry["components"]["claude"], [["comp-one", "https://github.com/example/one"]])
        self.assertEqual(entry["components"]["codex"], [["comp-two", "https://github.com/example/two"]])
        ab = json.loads((self.work / "adjudication-inputs" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        ba = json.loads((self.work / "adjudication-inputs" / f"{NAME}.BA.json").read_text(encoding="utf-8"))
        self.assertEqual(ab["packet_sha256"], self.sha)
        self.assertEqual(ab["A"], ba["B"])
        self.assertEqual(ab["B"], ba["A"])
        self.assertEqual(ab["A"]["winner_keys"], ["c1"])
        self.assertEqual(ab["B"]["winner_keys"], ["c2"])
        for side in (ab["A"], ab["B"]):
            self.assertEqual(set(side), set(adjudicate.SCRUB_KEEP))
            for key in ("lane", "model", "provenance", "refutation", "final_source", "packet_sha256",
                        "schema_version"):
                self.assertNotIn(key, side)

    def test_evidence_path_lists_are_reduced_to_sorted_bare_paths(self):
        """Round-2 review: Claude sources_read entries carried notes ("path (lines 60-104, prior round)")
        while Codex entries were bare paths, so the notes told the judge which lane wrote A."""
        claude_repo = self.base / "claude-export"
        self.write_return(
            "claude", "c1", refutation={"status": "unrefuted"},
            sources_read=["evidence/receipt.json (lines 60-104, prior round)", f"{claude_repo}/docs/a.md#setup",
                          "docs/b.md:12-30", "evidence/receipt.json"],
            winner_evidence_refs=[f"{claude_repo}/evidence/receipt.json (native run)"],
            alternatives=[{"key": "c2", "evidence_refs": ["docs/b.md (README claim only)"]}],
            challenger_preferred={"key": "c2", "evidence_refs": ["tests/x.py (fixture)"]},
            overturn_protocol={"fixture_paths": ["tests/x.py (fixture)"], "metric": "", "arms": []})
        self.write_return("codex", "c2", sources_read=["docs/b.md", "docs/a.md#setup", "evidence/receipt.json"],
                          alternatives=[{"key": "c1", "evidence_refs": ["docs/b.md"]}],
                          challenger_preferred={"key": "c1", "evidence_refs": ["tests/x.py"]})
        code, _err = quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work),
                                             "--lane-repo-root", str(claude_repo)])
        self.assertEqual(code, 0)
        ab = json.loads((self.work / "adjudication-inputs" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        claude_side, codex_side = ab["A"], ab["B"]
        self.assertEqual(claude_side["sources_read"], ["docs/a.md#setup", "docs/b.md", "evidence/receipt.json"])
        self.assertEqual(claude_side["sources_read"], codex_side["sources_read"])
        self.assertEqual(claude_side["winner_evidence_refs"], ["evidence/receipt.json"])
        self.assertEqual(claude_side["alternatives"][0]["evidence_refs"], ["docs/b.md"])
        self.assertEqual(claude_side["challenger_preferred"]["evidence_refs"], ["tests/x.py"])
        self.assertEqual(claude_side["overturn_protocol"]["fixture_paths"], ["tests/x.py"])
        self.assertNotIn("prior round", json.dumps(ab))
        self.assertNotIn(str(claude_repo), json.dumps(ab))

    def test_agreeing_layer_writes_no_input(self):
        self.write_return("codex", "c1")
        self.inputs()
        index = json.loads((self.work / "adjudication-inputs" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["layers"][0]["agreement"], "agree")
        self.assertFalse((self.work / "adjudication-inputs" / f"{NAME}.AB.json").exists())

    def test_packet_mismatch_and_unparseable_return_are_skipped(self):
        self.write_return("codex", "c2", sha="0" * 64)
        code, err = self.inputs()
        self.assertEqual(code, 1)
        self.assertIn("packet_sha256", err)
        (self.work / "codex" / f"{NAME}.json").write_text("{nope", encoding="utf-8")
        code, err = self.inputs()
        self.assertEqual(code, 1)
        self.assertIn("does not parse", err)


class AssembleTests(AdjudicateFixture):
    def setUp(self):
        super().setUp()
        self.inputs()

    def test_four_agreeing_unrefuted_judgments_give_a_winner(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        code, _err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertEqual(record["winner_lane"], "codex")
        self.assertEqual(self.assert_valid(record)["winner_lane"], "codex")
        self.assertEqual(sorted((j["judge"]["family"], j["claude_position"]) for j in record["judgments"]),
                         [("anthropic", "A"), ("anthropic", "B"), ("openai", "A"), ("openai", "B")])
        self.assertTrue(all(j["stripped_packet_sha256"] == self.sha for j in record["judgments"]))
        self.assertEqual(record["evidence_refs"], ["evidence/receipt.json"])

    def test_single_family_is_a_split_naming_the_missing_family(self):
        for order in adjudicate.ORDERS:
            self.judgment("claude", order, "claude")
        code, err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(record["missing_families"], ["openai"])
        self.assertIn("missing openai", record["why"])
        self.assertIn("openai AB: no judgment file", err)
        self.assertIsNone(self.assert_valid(record)["winner_lane"])

    def test_one_refuted_judgment_makes_a_split(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude", refuted=(lane == "codex" and order == "BA"))
        code, _err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(self.assert_valid(record)["refuted"], 1)

    def test_disagreeing_judges_split(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, lane)
        _code, _err, record = self.assemble()
        self.assertIsNone(record["winner_lane"])
        self.assert_valid(record)

    def test_a_record_that_fails_validation_is_not_written(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude")
        with mock.patch.object(adjudicate, "judge_adjudication", return_value=("rejected", None)):
            code, err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        self.assertIn("not written: rejected", err)

    def test_unknown_model_judgments_are_left_out_so_the_record_is_a_split(self):
        # Before the round-2 fix these counted and the whole record failed validation.
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude", model="unknown" if lane == "codex" else None)
        code, err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(record["missing_families"], ["openai"])
        self.assertIn("does not match the openai pattern", err)
        self.assert_valid(record)

    def test_each_record_carries_the_provenance_of_its_code(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        _code, _err, record = self.assemble()
        expected = {"adjudicate_py_sha256": TOOL_DIR / "adjudicate.py",
                    "prompt_sha256": TOOL_DIR / "adjudication-prompt.md",
                    "judge_schema_sha256": TOOL_DIR / "adjudication-judge.schema.json",
                    "refute_schema_sha256": TOOL_DIR / "adjudication-refute.schema.json",
                    "workflow_sha256": TOOL_DIR / "adjudication-lane.js"}
        self.assertEqual(record["provenance"], {key: hashlib.sha256(path.read_bytes()).hexdigest()
                                                for key, path in expected.items()})
        self.assertEqual(self.assert_valid(record)["winner_lane"], "codex")

    def test_a_judgment_whose_model_misses_its_family_pattern_does_not_count(self):
        self.judgment("codex", "AB", "codex", model="unknown")
        data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertIn("does not match the openai pattern", adjudicate.usable_judgment(data, "openai", "AB", self.sha))
        data["model"] = "gpt-6-astra"
        self.assertIsNone(adjudicate.usable_judgment(data, "openai", "AB", self.sha))

    def test_claude_collect_records_a_lost_agent_as_missing(self):
        index_items = adjudicate.claude_args(self.work, self.repo)["items"]
        self.assertEqual([(i["name"], i["order"]) for i in index_items], [(NAME, "AB"), (NAME, "BA")])
        result = {"items": [
            {"name": NAME, "order": "AB", "packet_sha256": self.sha,
             "judge": {"preferred": "B", "why": WHY, "evidence_refs": ["evidence/receipt.json"]},
             "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}},
            {"name": NAME, "order": "BA", "packet_sha256": self.sha, "judge": None, "refuter": None}]}
        result_path = self.base / "result.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        code, err = quiet(adjudicate.main, ["claude-collect", "--work-dir", str(self.work), "--result",
                                            str(result_path), "--model", "claude-opus-5-5"])
        self.assertEqual(code, 1)
        self.assertIn("BA: missing", err)
        for order in adjudicate.ORDERS:
            self.judgment("codex", order, "codex")
        _code, _err, record = self.assemble()
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(record["missing_families"], ["anthropic"])
        self.assert_valid(record)
        code, err = quiet(adjudicate.main, ["claude-collect", "--work-dir", str(self.work), "--result",
                                            str(result_path), "--model", "unknown"])
        self.assertEqual(code, 2)


@unittest.skipUnless(os.access(FAKE_BIN / "codex", os.X_OK), "fake codex fixture is not executable")
class CodexTests(AdjudicateFixture):
    def setUp(self):
        super().setUp()
        self.inputs()
        self.argv_log = self.base / "argv.jsonl"
        return_file = self.base / "return.json"
        # One canned object serves both calls: the judge keeps its schema keys, the refuter its own.
        return_file.write_text(json.dumps({"preferred": "B", "why": WHY, "evidence_refs": ["evidence/receipt.json"],
                                           "refuted": False, "reason": "The receipt holds."}), encoding="utf-8")
        events = self.base / "events.jsonl"
        events.write_text(json.dumps({"type": "turn.completed", "model": "gpt-6-astra",
                                      "usage": {"input_tokens": 1}}) + "\n", encoding="utf-8")
        self.env = {"PATH": f"{FAKE_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CODEX_FAKE_ARGV_LOG": str(self.argv_log), "CODEX_FAKE_RETURN_FILE": str(return_file),
                    "CODEX_FAKE_EVENTS_FILE": str(events), "CODEX_FAKE_COUNTER_FILE": str(self.base / "count")}

    def run_codex(self, repo=None, model="gpt-6-astra", **env):
        with mock.patch.dict(os.environ, {**self.env, **env}):
            return quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(repo or self.repo),
                                           "--timeout", "30", "--model", model])

    def calls(self):
        return [json.loads(line) for line in self.argv_log.read_text(encoding="utf-8").splitlines()]

    def test_judge_and_refuter_run_isolated_per_order(self):
        code, err = self.run_codex()
        self.assertEqual(code, 0, err)
        calls = self.calls()
        self.assertEqual(len(calls), 4)
        isolation = list(adjudicate.codex_lane.ISOLATION_ARGS)
        for argv in calls:
            self.assertTrue(any(argv[i:i + len(isolation)] == isolation for i in range(len(argv))), argv)
            self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
            self.assertEqual(argv[argv.index("-C") + 1], str(self.repo))
            self.assertIn("--json", argv)
            self.assertIn("-o", argv)
        schemas = [Path(argv[argv.index("--output-schema") + 1]).name for argv in calls]
        self.assertEqual(sorted(schemas), ["adjudication-judge.codex-strict.schema.json"] * 2
                         + ["adjudication-refute.codex-strict.schema.json"] * 2)
        self.assertTrue(any("do not try to identify which lane" in argv[-1].lower() for argv in calls))
        for order in adjudicate.ORDERS:
            data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.{order}.json")
                              .read_text(encoding="utf-8"))
            self.assertIsNone(adjudicate.usable_judgment(data, "openai", order, self.sha))
            self.assertEqual(data["model"], "gpt-6-astra")
            self.assertEqual(data["exit_codes"], {"judge": [0], "refuter": [0]})
        # Resumable: a second run skips both valid judgments.
        self.run_codex()
        self.assertEqual(len(self.calls()), 4)

    def test_model_is_required_and_must_match_the_openai_pattern(self):
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                adjudicate.main(["codex", "--work-dir", str(self.work), "--repo", str(self.repo)])
        self.assertEqual(raised.exception.code, 2)
        for model in ("unknown", "claude-opus-5-5"):
            code, err = self.run_codex(model=model)
            self.assertEqual(code, 2)
            self.assertIn("openai pattern", err)
        self.assertFalse(self.argv_log.exists())

    def test_the_configured_model_is_recorded_over_the_event_stream_name(self):
        code, err = self.run_codex(model="gpt-6-codex")
        self.assertEqual(code, 0, err)
        for argv in self.calls():
            self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-codex")
        data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "gpt-6-codex")

    def test_resume_reruns_a_judgment_with_an_unknown_or_other_model(self):
        self.run_codex()
        self.assertEqual(len(self.calls()), 4)
        path = self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps({**data, "model": "unknown"}), encoding="utf-8")
        self.run_codex()
        self.assertEqual(len(self.calls()), 6, "the unknown-model judgment reruns (judge and refuter)")
        self.run_codex(model="gpt-6-codex")
        self.assertEqual(len(self.calls()), 10, "a different --model reruns both orders")

    def test_a_failed_call_is_retried_once(self):
        code, err = self.run_codex(CODEX_FAKE_FAIL_ATTEMPTS="1")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.calls()), 5)
        data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(data["exit_codes"]["judge"], [1, 0])

    def test_two_failures_leave_the_judgment_missing(self):
        code, err = self.run_codex(CODEX_FAKE_FAIL_ATTEMPTS="1,2")
        self.assertEqual(code, 1)
        self.assertIn("judge failed after retry", err)

    def test_repo_with_git_is_refused(self):
        (self.repo / ".git").mkdir()
        code, err = self.run_codex()
        self.assertEqual(code, 2)
        self.assertIn(".git", err)
        self.assertFalse(self.argv_log.exists())

    def test_a_position_biased_codex_judge_splits_the_layer(self):
        # The fake answers "B" in both orders: codex in AB, claude in BA, so counterbalancing exposes it.
        self.run_codex()
        result = {"items": [{"name": NAME, "order": order, "packet_sha256": self.sha,
                             "judge": {"preferred": "B" if order == "AB" else "A", "why": WHY,
                                       "evidence_refs": ["evidence/receipt.json"]},
                             "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}}
                            for order in adjudicate.ORDERS]}
        missing = adjudicate.collect_claude(self.work, result, "claude-opus-5-5")
        self.assertEqual(missing, [])
        code, _err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(self.assert_valid(record)["tally"], {"claude": 1, "codex": 3})
        self.assertIn("different lanes", record["why"])


class WorkflowSyntaxTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_adjudication_lane_passes_the_workflow_syntax_check(self):
        target = str(TOOL_DIR / "adjudication-lane.js")
        result = subprocess.run(["node", str(CHECK_SYNTAX), target], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_agent_call_binds_the_blind_reviewer_literals(self):
        source = (TOOL_DIR / "adjudication-lane.js").read_text(encoding="utf-8")
        calls = source.count("await agent(")
        self.assertEqual(calls, 2)
        self.assertEqual(source.count("agentType: 'blind-lane-reviewer', model: 'opus', effort: 'high', schema: "),
                         calls)
        self.assertIn("Do not try to identify which lane", source)


if __name__ == "__main__":
    unittest.main()
