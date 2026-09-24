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
# adjudicate put the repo root on sys.path.
from scripts.landscape import (  # noqa: E402
    SEALED_CANDIDATE_FIELDS, judge_adjudication, sealed_candidate_labels, sealed_candidates_sha256)

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


def writes_events(stub, events=None):
    """A run_codex_call stand-in that, like the real call, always leaves its events file (a stage that ran without
    one is flagged: independent review of #145, BIND-R4-3). ``events`` maps an events file name to what that call
    leaves in it (empty otherwise)."""
    def call(*args, **kwargs):
        path = Path(args[7])
        path.write_text((events or {}).get(path.name, ""), encoding="utf-8")
        return stub(*args, **kwargs)
    return call


def read_command_event(command):
    return json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": command}}) + "\n"


def quiet(function, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
        code = function(*args)
    return code, err.getvalue()


class AdjudicateFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        # The position index lives outside the work dir, under this state directory (never the real one in tests).
        # Never the developer's credential or state (independent review of #145, R4-REG-7): a fixture native Codex
        # home with a dummy auth.json, and run-scoped Codex homes under the fixture.
        (self.base / "native-codex").mkdir()
        (self.base / "native-codex" / "auth.json").write_text("{}", encoding="utf-8")
        state = mock.patch.dict(os.environ, {adjudicate.STATE_DIR_ENV: str(self.base / "state"),
                                             "CODEX_HOME": str(self.base / "native-codex"),
                                             adjudicate.codex_lane.CODEX_HOME_BASE_ENV: str(self.base / "codex-homes")})
        state.start()
        self.addCleanup(state.stop)
        # The fake codex reads its CODEX_FAKE_* settings; production children get only the allowlist (ISO-R5-2).
        prefixes = mock.patch.object(adjudicate.codex_lane, "CHILD_ENV_EXTRA_PREFIXES", ("CODEX_FAKE_",))
        prefixes.start()
        self.addCleanup(prefixes.stop)
        # claude-collect audits the workflow's agent transcripts (Codex review of #145 at 68e74f2c); a test that does
        # not pass its own gets clean transcripts for the inputs claude-args gave the workflow.
        real_collect = adjudicate.collect_claude
        def collect(work_dir, result, model, repo_override=None, transcripts=None):
            return real_collect(work_dir, result, model, repo_override,
                                transcripts if transcripts is not None else self.clean_transcripts())
        collect_patch = mock.patch.object(adjudicate, "collect_claude", collect)
        collect_patch.start()
        self.addCleanup(collect_patch.stop)
        self.real_collect_claude = real_collect
        self.work = self.base / "work"
        # blind-adjudicator refuses a repository root with fewer than four path components.
        self.repo = self.base / "hosts" / "blind" / "repo"
        self.repo.mkdir(parents=True)
        for sub in ("packets", "claude", "codex"):
            (self.work / sub).mkdir(parents=True)
        packet_path = self.work / "packets" / f"{NAME}.json"
        packet_path.write_text(json.dumps(PACKET), encoding="utf-8")
        self.sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        self.write_return("claude", "c1", refutation={"status": "unrefuted"}, final_source="proposal")
        self.write_return("codex", "c2")

    def rewrite_returns(self):
        """setUp's two returns again, recording the repository's current tree."""
        self.write_return("claude", "c1", refutation={"status": "unrefuted"}, final_source="proposal")
        self.write_return("codex", "c2")

    def write_return(self, lane, winner, name=NAME, sha=None, **extra):
        # A lane records the evidence tree it read; inputs binds each lane root to it (BIND-R4-9).
        extra.setdefault("provenance", {"x": "y", "repo_tree_sha256": adjudicate.tree_sha256(self.repo)})
        path = self.work / lane / f"{name}.json"
        path.write_text(json.dumps(lane_return(lane, winner, sha or self.sha, **extra)), encoding="utf-8")

    def inputs(self, *roots):
        argv = ["inputs", "--work-dir", str(self.work)]
        for root in roots or (self.repo,):
            argv += ["--lane-repo-root", str(root)]
        return quiet(adjudicate.main, argv)

    def judgment(self, lane, order, preferred_lane, refuted=False, model=None):
        family = adjudicate.FAMILIES[lane]
        entry = next(e for e in adjudicate.load_index(self.work)["layers"] if e["layer"] == NAME)
        claude_position = adjudicate.claude_position(entry, order)
        other = "B" if claude_position == "A" else "A"
        input_path = self.work / "adjudication-inputs" / f"{NAME}.{order}.json"
        record = adjudicate.judgment_record(
            family, NAME, order, input_path, self.sha,
            model or ("claude-opus-5-5" if lane == "claude" else "gpt-6-astra"), str(self.repo),
            {"preferred": claude_position if preferred_lane == "claude" else other, "why": WHY,
             "evidence_refs": [str(self.repo / "evidence/receipt.json")]},
            {"refuted": refuted, "reason": "The cited receipt exists and shows the run.", "evidence_refs": []},
            input_sha256=adjudicate.sha256_file(input_path) if input_path.is_file() else None,
            provenance=adjudicate.adjudication_provenance(repo=self.repo))
        if lane == "claude":
            # claude-collect records a clean, bound audit of the agents' transcripts (Codex review of #145 at 68e74f2c).
            directory = self.write_transcripts({f"{NAME}.{order}": input_path})
            record["audit_clean"] = True
            record["transcripts"] = {"dir": str(directory),
                                     "sha256": adjudicate.transcript_audit.transcripts_sha256(directory)}
        if lane == "codex":
            record["audit_clean"] = True  # the Codex runner records its calls' clean blind audit
            # ... and the events files it audited, by digest (independent review of #145, BIND-R4-6).
            events = self.work / "adjudication-judgments" / "codex" / "events"
            events.mkdir(parents=True, exist_ok=True)
            record["events"] = {}
            for stage in ("judge", "refute"):
                path = events / f"{NAME}.{order}.{stage}.jsonl"
                path.write_text("", encoding="utf-8")
                record["events"][stage] = {"path": str(path), "sha256": adjudicate.sha256_file(path)}
        adjudicate.write_json(self.work / "adjudication-judgments" / lane / f"{NAME}.{order}.json", record)

    def write_transcripts(self, inputs: dict, extra_reads=()) -> Path:
        """A workflow run's agent transcripts: one judge agent per input ("<name>.<order>" -> input path) whose
        prompt names its Input file line and which reads that input, plus ``extra_reads``."""
        directory = Path(tempfile.mkdtemp(dir=self.base))
        for index, (key, input_path) in enumerate(sorted(inputs.items())):
            calls = [{"type": "tool_use", "name": "Read", "input": {"file_path": str(input_path)}},
                     *({"type": "tool_use", "name": "Read", "input": {"file_path": str(path)}} for path in extra_reads),
                     {"type": "tool_use", "name": "StructuredOutput", "input": {}}]
            lines = [{"type": "user", "cwd": str(self.repo), "message": {"role": "user", "content":
                      f"Input file: {input_path}\nPacket file: x\nRepository root: {self.repo}"}},
                     {"type": "assistant", "cwd": str(self.repo), "message": {"role": "assistant", "content": calls}}]
            (directory / f"agent-{index:04d}.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines),
                                                                 encoding="utf-8")
        return directory

    def clean_transcripts(self) -> Path:
        """Clean transcripts for every input the current claude-args snapshot gave the workflow."""
        path = self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT
        snapshot = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        index = adjudicate.load_index(self.work)
        inputs = {f"{name}.{order}": input_path for name, order, input_path, _sha in adjudicate.pending_items(index)
                  if f"{name}.{order}" in (snapshot.get("inputs") or {})}
        return self.write_transcripts(inputs)

    def input_body(self, order="AB"):
        """The input with the Claude return as A, whichever position the index's secret map gave it (F3)."""
        body = json.loads((self.work / "adjudication-inputs" / f"{NAME}.{order}.json").read_text(encoding="utf-8"))
        entry = next(e for e in adjudicate.load_index(self.work)["layers"] if e["layer"] == NAME)
        return dict(body, A=body["B"], B=body["A"]) if adjudicate.claude_position(entry, order) == "B" else body

    def snapshot_packet(self, name=NAME, sha=None):
        """The immutable packet copy judges read (Codex review of #145, round 8)."""
        return self.work / adjudicate.PACKET_SNAPSHOTS_DIR / (sha or self.sha) / "packets" / f"{name}.json"

    def as_workflow(self, result):
        """``result`` as adjudication-lane.js returns it (Codex review of #145): the prompt and repo it read and
        each item's consumed input and packet paths, filled in where the test did not set them."""
        if not isinstance(result, dict):
            return result
        index = adjudicate.load_index(self.work)
        path = self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT
        snapshot = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        inputs = {(entry["layer"], order): input_path for entry in index.get("layers") or []
                  for order, input_path in (entry.get("inputs") or {}).items()}
        packets = adjudicate.packet_paths(index)
        out = dict(result)
        out.setdefault("prompt", adjudicate.PROMPT_PATH.read_text(encoding="utf-8"))
        out.setdefault("repo", snapshot.get("repo"))
        out["items"] = [{"path": inputs.get((item.get("name"), item.get("order"))),
                         "packet_path": packets.get(item.get("name")), **item} if isinstance(item, dict) else item
                        for item in result.get("items") or []]
        return out

    def snapshot_id(self):
        path = self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT
        return json.loads(path.read_text(encoding="utf-8")).get("snapshot_id") if path.is_file() else None

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
        index = json.loads((adjudicate.index_path(self.work)).read_text(encoding="utf-8"))
        entry = index["layers"][0]
        self.assertEqual(entry["agreement"], "disagree")
        self.assertEqual(entry["components"]["claude"], [["comp-one", "https://github.com/example/one"]])
        self.assertEqual(entry["components"]["codex"], [["comp-two", "https://github.com/example/two"]])
        ab = json.loads((self.work / "adjudication-inputs" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        ba = json.loads((self.work / "adjudication-inputs" / f"{NAME}.BA.json").read_text(encoding="utf-8"))
        self.assertEqual(ab["packet_sha256"], self.sha)
        self.assertEqual(ab["A"], ba["B"])
        self.assertEqual(ab["B"], ba["A"])
        # The Claude return (winner c1) sits where the index's secret claude_position says (F3).
        claude_side = adjudicate.claude_position(entry, "AB")
        codex_side = "B" if claude_side == "A" else "A"
        self.assertEqual(ab[claude_side]["winner_keys"], ["c1"])
        self.assertEqual(ab[codex_side]["winner_keys"], ["c2"])
        self.assertEqual(adjudicate.claude_position(entry, "BA"), codex_side)
        for side in (ab["A"], ab["B"]):
            self.assertEqual(set(side), set(adjudicate.SCRUB_KEEP))
            for key in ("lane", "model", "provenance", "refutation", "final_source", "packet_sha256",
                        "schema_version"):
                self.assertNotIn(key, side)

    def test_evidence_path_lists_are_reduced_to_sorted_bare_paths(self):
        """Round-2 review: Claude sources_read entries carried notes ("path (lines 60-104, prior round)")
        while Codex entries were bare paths, so the notes told the judge which lane wrote A."""
        claude_repo = self.base / "hosts" / "claude" / "export"
        claude_repo.mkdir(parents=True, exist_ok=True)  # the same (empty) tree as self.repo: both roots hold it
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
        code, _err = self.inputs(claude_repo, self.repo)
        self.assertEqual(code, 0)
        ab = self.input_body("AB")
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
        index = json.loads((adjudicate.index_path(self.work)).read_text(encoding="utf-8"))
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

    def test_a_judgment_of_an_older_input_does_not_count(self):
        # Codex review of #145: an old A/B preference must not be read against rebuilt returns.
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        ab = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        body = json.loads(ab.read_text(encoding="utf-8"))
        body["A"]["why_selected"] = body["A"]["why_selected"] + " (rebuilt)"
        ab.write_text(json.dumps(body), encoding="utf-8")
        data = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_text())
        self.assertEqual(adjudicate.usable_judgment(data, "anthropic", "AB", self.sha), "judged a different input")
        _code, _err, record = self.assemble()
        self.assertTrue(record is None or record["winner_lane"] is None, record)

    def test_a_refused_layer_loses_its_earlier_record(self):
        # Codex review of #145: a stale record in --out must not reach record_verdicts --adjudications.
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        code, _err, record = self.assemble()
        self.assertEqual((code, record["winner_lane"]), (0, "codex"))
        for lane in ("claude", "codex"):
            (self.work / "adjudication-judgments" / lane / f"{NAME}.BA.json").unlink()
        _code, _err, record = self.assemble()
        self.assertIsNone(record)

    def test_claude_collect_refuses_an_input_changed_after_claude_args(self):
        adjudicate.claude_args(self.work, self.repo)
        ab = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        ab.write_text(ab.read_text(encoding="utf-8").replace("}", " }", 1), encoding="utf-8")
        result = {"snapshot_id": self.snapshot_id(), "items": [{"name": NAME, "order": order, "packet_sha256": self.sha,
                             "judge": {"preferred": "B", "why": WHY, "evidence_refs": []},
                             "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}}
                            for order in adjudicate.ORDERS]}
        missing = dict(adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5"))
        self.assertIn("input changed after claude-args", missing[f"{NAME}.AB"])
        self.assertNotIn(f"{NAME}.BA", missing)

    def test_whitespace_in_a_root_or_work_dir_is_refused(self):
        self.assertIn("whitespace", adjudicate.root_issue("/srv/blind runs/lab/export"))
        self.assertIn("whitespace", adjudicate.refuse_work_dir_inside(self.base / "my work", self.repo))

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
                    "codex_lane_py_sha256": TOOL_DIR / "codex_lane.py",
                    "prompt_sha256": TOOL_DIR / "adjudication-prompt.md",
                    "judge_schema_sha256": TOOL_DIR / "adjudication-judge.schema.json",
                    "refute_schema_sha256": TOOL_DIR / "adjudication-refute.schema.json",
                    "workflow_sha256": TOOL_DIR / "adjudication-lane.js",
                    "adjudicator_role_sha256": adjudicate.VENDORED_ADJUDICATOR}
        self.assertEqual(record["provenance"], {**{key: hashlib.sha256(path.read_bytes()).hexdigest()
                                                   for key, path in expected.items()},
                                                "repo_tree_sha256": adjudicate.tree_sha256(self.repo)})
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
        result = {"snapshot_id": self.snapshot_id(), "items": [
            {"name": NAME, "order": "AB", "packet_sha256": self.sha,
             "judge": {"preferred": "B", "why": WHY, "evidence_refs": ["evidence/receipt.json"]},
             "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}},
            {"name": NAME, "order": "BA", "packet_sha256": self.sha, "judge": None, "refuter": None}]}
        result_path = self.base / "result.json"
        result_path.write_text(json.dumps(self.as_workflow(result)), encoding="utf-8")
        code, err = quiet(adjudicate.main, ["claude-collect", "--work-dir", str(self.work), "--result",
                                            str(result_path), "--model", "claude-opus-5-5",
                                            "--transcripts", str(self.clean_transcripts())])
        self.assertEqual(code, 1)
        self.assertIn("BA: missing", err)
        for order in adjudicate.ORDERS:
            self.judgment("codex", order, "codex")
        _code, _err, record = self.assemble()
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(record["missing_families"], ["anthropic"])
        self.assert_valid(record)
        code, err = quiet(adjudicate.main, ["claude-collect", "--work-dir", str(self.work), "--result",
                                            str(result_path), "--model", "unknown",
                                            "--transcripts", str(self.clean_transcripts())])
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

    def run_codex(self, repo=None, model="gpt-6-astra", effort=None, **env):
        with mock.patch.dict(os.environ, {**self.env, **env}):
            return quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(repo or self.repo),
                                           "--timeout", "30", "--model", model]
                         + (["--effort", effort] if effort else []))

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

    def test_resume_reruns_a_judgment_made_at_another_effort(self):
        # Codex re-review of #145: effort is recorded and a changed --effort reruns the judgment.
        self.assertEqual(self.run_codex(effort="high")[0], 0)
        first = len(self.calls())
        data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text())
        self.assertEqual(data["effort"], "high")
        self.assertEqual(self.run_codex(effort="high")[0], 0)
        self.assertEqual(len(self.calls()), first, "same effort: resumed, no new calls")
        self.assertEqual(self.run_codex(effort="medium")[0], 0)
        self.assertGreater(len(self.calls()), first, "a changed effort reruns the judgments")

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
        entry = next(e for e in adjudicate.load_index(self.work)["layers"] if e["layer"] == NAME)
        # The Claude family picks the codex return in both orders, wherever the secret map put it (F3).
        codex_side = {order: "B" if adjudicate.claude_position(entry, order) == "A" else "A" for order in adjudicate.ORDERS}
        result = {"snapshot_id": self.snapshot_id(), "items": [{"name": NAME, "order": order, "packet_sha256": self.sha,
                             "judge": {"preferred": codex_side[order], "why": WHY,
                                       "evidence_refs": ["evidence/receipt.json"]},
                             "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}}
                            for order in adjudicate.ORDERS]}
        adjudicate.claude_args(self.work, self.repo)
        result["snapshot_id"] = self.snapshot_id()
        missing = adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5")
        self.assertEqual(missing, [])
        code, _err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertIsNone(record["winner_lane"])
        self.assertEqual(self.assert_valid(record)["tally"], {"claude": 1, "codex": 3})
        self.assertIn("different lanes", record["why"])


class LeakTests(AdjudicateFixture):
    """Round-2 review: a judge or refuter that finds reviewer identity answers leak true; that judgment is
    missing (failure "leak"), never counted, and the layer's inputs are listed in a leaks file."""

    def setUp(self):
        super().setUp()
        self.inputs()

    def test_both_schemas_require_leak_and_leak_text(self):
        for schema in (adjudicate.JUDGE_SCHEMA, adjudicate.REFUTE_SCHEMA):
            data = json.loads(schema.read_text(encoding="utf-8"))
            self.assertEqual(data["properties"]["leak"], {"type": "boolean"})
            self.assertEqual(data["properties"]["leak_text"], {"type": "string"})
            self.assertEqual(set(data["required"]), set(data["properties"]), "Codex strict mode requires all")

    def test_the_prompt_gives_three_labelled_paths_and_a_leak_first_rule_for_both_roles(self):
        judge, refuter = adjudicate.split_prompt(adjudicate.PROMPT_PATH.read_text(encoding="utf-8"))
        input_path = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        for template in (judge, refuter):
            packet = adjudicate.packet_paths(adjudicate.load_index(self.work))[NAME]
            text = adjudicate.fill(template, input_path, self.repo, {"preferred": "A"}, packet)
            self.assertIn(f"Input file: {input_path}\n", text)
            self.assertIn(f"Packet file: {self.snapshot_packet()}\n", text)
            self.assertIn(f"Repository root: {self.repo}\n", text)
            self.assertLess(text.index("Leak check"), text.index("Blind rule"))
            for words in ("claude-opus", "o3", "not a leak", "as data"):
                self.assertIn(words, text)

    def test_a_leak_object_is_never_a_valid_judge_or_refuter(self):
        judge = {"preferred": "A", "why": WHY, "evidence_refs": [], "leak": True, "leak_text": "model: gpt-6"}
        self.assertIsNone(adjudicate.valid_judge(judge))
        self.assertIsNone(adjudicate.valid_refuter({"refuted": False, "reason": "x", "evidence_refs": [],
                                                    "leak": True, "leak_text": "opus"}))
        self.assertIsNotNone(adjudicate.valid_judge(dict(judge, leak=False, leak_text="")))

    def test_claude_leaks_at_either_stage_are_missing_and_listed(self):
        result = {"snapshot_id": self.snapshot_id(), "items": [
            {"name": NAME, "order": "AB", "packet_sha256": self.sha, "judge": None, "refuter": None,
             "leak": {"stage": "judge", "text": "\"lane\": \"claude\""}},
            {"name": NAME, "order": "BA", "packet_sha256": self.sha,
             "judge": {"preferred": "A", "why": WHY, "evidence_refs": []},
             "refuter": {"refuted": False, "reason": "leak", "evidence_refs": [], "leak": True,
                         "leak_text": "sonnet"}}]}
        adjudicate.claude_args(self.work, self.repo)
        result["snapshot_id"] = self.snapshot_id()
        missing = adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5")
        self.assertEqual(missing, [(f"{NAME}.AB", "leak"), (f"{NAME}.BA", "leak")])
        for order in adjudicate.ORDERS:
            data = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.{order}.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(adjudicate.usable_judgment(data, "anthropic", order, self.sha), "leak")
            self.assertIsNone(data["judge"])
        leaks = json.loads((self.work / "adjudication-judgments" / "claude" / "leaks.json").read_text(encoding="utf-8"))
        self.assertEqual([(e["order"], e["stage"], e["family"]) for e in leaks["leaks"]],
                         [("AB", "judge", "anthropic"), ("BA", "refuter", "anthropic")])
        self.assertEqual(set(leaks["leaks"][0]["inputs"]), {"AB", "BA"})
        self.assertEqual(leaks["leaks"][0]["input"], f"{NAME}.AB.json")
        self.assertEqual(leaks["leaks"][0]["input_sha256"], hashlib.sha256(
            (self.work / "adjudication-inputs" / f"{NAME}.AB.json").read_bytes()).hexdigest())
        for order in adjudicate.ORDERS:
            self.judgment("codex", order, "codex")
        code, err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIsNone(record, "no judgment of a leaked input counts, so no adjudication record is written")
        self.assertIn("leak recorded for the input", err)
        assembled = json.loads((self.work / "adjudication-leaks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(assembled["leaks"]), 2)
        # Basenames only (Codex review of #145): the work-dir layout is not retained.
        self.assertEqual(assembled["leaks"][0]["inputs"]["AB"], f"{NAME}.AB.json")
        self.assertEqual(assembled["split_layers"][0]["leaked_inputs"], [f"{NAME}.AB.json", f"{NAME}.BA.json"])
        self.assertIn("split: a leak is recorded", assembled["split_layers"][0]["reason"])

    def claude_result(self, leak_orders=()):
        items = []
        for order in adjudicate.ORDERS:
            item = {"name": NAME, "order": order, "packet_sha256": self.sha,
                    "judge": {"preferred": "A" if order == "AB" else "B", "why": WHY, "evidence_refs": []},
                    "refuter": {"refuted": False, "reason": "holds", "evidence_refs": []}}
            if order in leak_orders:
                item.update(judge=None, refuter=None, leak={"stage": "judge", "text": "gpt-6"})
            items.append(item)
        return {"snapshot_id": self.snapshot_id(), "items": items}

    def test_claude_judgments_are_audited_on_their_agents_transcripts(self):
        # Codex review of #145 at 68e74f2c: a Claude judge can Read the sibling lane returns; its transcript shows it.
        adjudicate.claude_args(self.work, self.repo)
        inputs = {f"{NAME}.{order}": str(self.work / "adjudication-inputs" / f"{NAME}.{order}.json")
                  for order in adjudicate.ORDERS}
        with self.assertRaisesRegex(ValueError, "--transcripts"):
            self.real_collect_claude(self.work, self.as_workflow(self.claude_result()), "claude-opus-5-5")
        sibling = self.work / "claude" / f"{NAME}.json"
        flagged = self.write_transcripts(inputs, extra_reads=[sibling])
        missing = self.real_collect_claude(self.work, self.as_workflow(self.claude_result()), "claude-opus-5-5",
                                           transcripts=flagged)
        self.assertEqual(sorted(reason for _stem, reason in missing), [adjudicate.AUDIT_FLAGGED] * 2)
        record = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual((record["audit_clean"], record["judge"]), (False, None))
        # A record edited to claim a clean audit is re-audited on the recorded transcripts and still does not count.
        record.update(audit_clean=True, failure=None, judge=self.claude_result()["items"][0]["judge"],
                      refuter=self.claude_result()["items"][0]["refuter"])
        entry = next(e for e in adjudicate.load_index(self.work)["layers"] if e["layer"] == NAME)
        self.assertEqual(adjudicate.claude_transcripts_issue(record, entry), adjudicate.AUDIT_FLAGGED)
        # Transcripts that cover one input only, or use another tool, flag too.
        partial = self.write_transcripts({f"{NAME}.AB": inputs[f"{NAME}.AB"]})
        self.assertEqual(adjudicate.transcript_audit.audit(partial, adjudicate.claude_audit_items(
            adjudicate.load_index(self.work), self.repo, inputs))["flagged_items"], [f"{NAME}.BA"])
        clean = self.write_transcripts(inputs)
        missing = self.real_collect_claude(self.work, self.as_workflow(self.claude_result()), "claude-opus-5-5",
                                           transcripts=clean)
        self.assertEqual(missing, [])
        record = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertIsNone(adjudicate.claude_transcripts_issue(record, entry))
        (clean / "agent-0000.jsonl").write_text("", encoding="utf-8")
        self.assertIn("changed", adjudicate.claude_transcripts_issue(record, entry))

    def test_a_duplicated_or_extra_claude_item_is_refused(self):
        # Codex review of #145 at 68e74f2c: an edited args or result could run several chains for one item and keep
        # one stochastic judgment.
        adjudicate.claude_args(self.work, self.repo)
        duplicated = self.claude_result()
        duplicated["items"].append(dict(duplicated["items"][0]))
        with self.assertRaisesRegex(ValueError, "more than once"):
            adjudicate.collect_claude(self.work, self.as_workflow(duplicated), "claude-opus-5-5")
        extra = self.claude_result()
        extra["items"].append(dict(extra["items"][0], name="foundation__other-layer"))
        with self.assertRaisesRegex(ValueError, "did not give it"):
            adjudicate.collect_claude(self.work, self.as_workflow(extra), "claude-opus-5-5")
        snapshot = json.loads((self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT)
                              .read_text(encoding="utf-8"))
        self.assertEqual(sorted(snapshot["items"]), [f"{NAME}.AB", f"{NAME}.BA"])

    def test_a_claude_leak_is_sticky_until_the_input_changes(self):
        """Round-2 review (adjudication round 3): a second claude-collect overwrote the leaked judgment with a
        counted one."""
        adjudicate.claude_args(self.work, self.repo)
        self.assertEqual(adjudicate.collect_claude(self.work, self.as_workflow(self.claude_result(("AB",))), "claude-opus-5-5"),
                         [(f"{NAME}.AB", "leak")])
        # Both orders hold the same returns, so a leak in AB suppresses BA too (Codex review of #145).
        self.assertEqual(adjudicate.claude_args(self.work, self.repo)["leaked"], [f"{NAME}.AB", f"{NAME}.BA"])
        self.assertEqual(adjudicate.claude_args(self.work, self.repo)["items"], [])
        # The workflow is rerun anyway and returns a clean judgment for the leaked input. claude-args left the
        # leaked AB out of its snapshot, so collect does not touch AB's leak record at all.
        self.assertEqual(adjudicate.collect_claude(self.work, self.as_workflow(self.claude_result()), "claude-opus-5-5"), [])
        data = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual((data["failure"], data["judge"]), ("leak", None))
        records = json.loads((self.work / "adjudication-judgments" / "claude" / "leaks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(records["leaks"]), 1, "the leak record survives the second run")
        for order in adjudicate.ORDERS:
            self.judgment("codex", order, "claude")
        # Even a judgment file edited to look clean does not count while the leak is recorded.
        self.judgment("claude", "AB", "claude")
        code, _err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        # Rebuilding the input with different content clears it.
        self.write_return("codex", "c2", why_selected="c2 has evidence in evidence/receipt.json and docs/b.md")
        self.inputs()
        self.assertEqual(adjudicate.claude_args(self.work, self.repo)["leaked"], [])


class RereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145: skipped layers, selective collection, stale leaks and effort on resume."""

    def setUp(self):
        super().setUp()
        self.inputs()

    def test_a_layer_skipped_by_inputs_loses_its_earlier_record(self):
        out = self.base / "adjudications"
        out.mkdir()
        (out / f"{NAME}.json").write_text("{}", encoding="utf-8")
        index_path = adjudicate.index_path(self.work)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["skipped"] = [{"layer": NAME, "reason": "host paths remain after scrubbing"}]
        index["layers"] = []
        index_path.write_text(json.dumps(index), encoding="utf-8")
        quiet(adjudicate.main, ["assemble", "--work-dir", str(self.work), "--out", str(out)])
        self.assertFalse((out / f"{NAME}.json").exists())

    def test_collect_touches_only_the_snapshotted_items(self):
        for order in adjudicate.ORDERS:
            self.judgment("claude", order, "claude")
        before = (self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_bytes()
        empty = {"inputs": {}, "repo": str(self.repo),
                 "provenance": {"prompt_sha256": adjudicate.sha256_file(adjudicate.PROMPT_PATH)}}
        empty_id = hashlib.sha256(json.dumps(empty, sort_keys=True).encode("utf-8")).hexdigest()
        adjudicate.write_json(self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT,
                              {**empty, "snapshot_id": empty_id})
        self.assertEqual(adjudicate.collect_claude(self.work, self.as_workflow({"snapshot_id": empty_id, "items": []}), "claude-opus-5-5"), [])
        self.assertEqual((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_bytes(), before)

    def test_a_leak_on_an_input_rebuilt_after_claude_args_is_discarded(self):
        adjudicate.claude_args(self.work, self.repo)
        ab = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        ab.write_text(ab.read_text(encoding="utf-8").replace("}", " }", 1), encoding="utf-8")
        result = {"snapshot_id": self.snapshot_id(), "items": [{"name": NAME, "order": "AB", "packet_sha256": self.sha, "leak": {"stage": "judge",
                             "text": "the Codex lane"}}]}
        adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5")
        self.assertEqual(adjudicate.recorded_leaks(self.work), set())


class SecondRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (second round)."""

    def test_a_layer_with_a_missing_return_is_skipped_and_purged(self):
        self.inputs()
        out = self.base / "adjudications"
        out.mkdir()
        (out / f"{NAME}.json").write_text("{}", encoding="utf-8")
        (self.work / "codex" / f"{NAME}.json").unlink()
        self.inputs()
        index = json.loads((adjudicate.index_path(self.work)).read_text(encoding="utf-8"))
        self.assertIn(NAME, [entry["layer"] for entry in index["skipped"]])
        quiet(adjudicate.main, ["assemble", "--work-dir", str(self.work), "--out", str(out)])
        self.assertFalse((out / f"{NAME}.json").exists())

    def test_paths_inside_backticks_are_scrubbed_and_caught(self):
        text = "cited `/home/example/lane-codex/evidence/x.json` in the review"
        self.assertNotIn("/home/example", adjudicate.scrub_text(text, str(self.work / "packets"), ()))
        self.assertTrue(adjudicate.unscrubbed_paths({"why": "left `/opt/lane/x.json` here"}))

    def test_roots_with_tokenizer_delimiters_are_refused(self):
        for root in ("/work/blind/lane(repo)/export", "/work/blind/lane's/export", "/work/blind/a;b/export"):
            self.assertIsNotNone(adjudicate.root_issue(root), root)
        self.assertIsNone(adjudicate.root_issue("/work/blind/lane-repo/export"))

    def test_judgments_under_different_provenance_refuse_the_layer(self):
        self.inputs()
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        path = self.work / "adjudication-judgments" / "codex" / f"{NAME}.BA.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["provenance"] = dict(data["provenance"], prompt_sha256="0" * 64)
        path.write_text(json.dumps(data), encoding="utf-8")
        code, err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        self.assertIn("different provenance", err)


class ThirdRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (third round)."""

    def test_parent_traversal_never_relativizes_into_a_sibling(self):
        root = str(self.repo)
        text = f"see {root}/../codex/return.json and ../codex/x.json"
        scrubbed = adjudicate.scrub_text(text, str(self.work / "packets"), (root,))
        self.assertNotIn("../", scrubbed)
        self.assertNotIn("codex/return.json", scrubbed)
        self.assertTrue(adjudicate.unscrubbed_paths({"why": "left ../codex/x.json"}))

    def test_claude_args_refuses_an_installed_role_other_than_the_vendored_one(self):
        self.inputs()
        edited = self.base / "blind-adjudicator.md"
        edited.write_text(adjudicate.VENDORED_ADJUDICATOR.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
        code, err = quiet(adjudicate.main, ["claude-args", "--work-dir", str(self.work), "--repo", str(self.repo), "--run-dir", str(self.repo),
                                            "--agent-file", str(edited)])
        self.assertEqual(code, 2)
        self.assertIn("is not the vendored", err)
        code, _err = quiet(adjudicate.main, ["claude-args", "--work-dir", str(self.work), "--repo", str(self.repo), "--run-dir", str(self.repo),
                                             "--agent-file", str(adjudicate.VENDORED_ADJUDICATOR)])
        self.assertEqual(code, 0)
        self.assertIn("adjudicator_role_sha256", adjudicate.adjudication_provenance())

    def test_a_claude_leak_binds_to_the_snapshot_hash(self):
        self.inputs()
        adjudicate.claude_args(self.work, self.repo)
        snapshot = json.loads((self.work / "adjudication-judgments" / "claude"
                               / adjudicate.CLAUDE_ARGS_SNAPSHOT).read_text(encoding="utf-8"))["inputs"]
        result = {"snapshot_id": self.snapshot_id(), "items": [{"name": NAME, "order": "AB", "packet_sha256": self.sha,
                             "leak": {"stage": "judge", "text": "the Codex lane"}}]}
        adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5")
        records = json.loads((self.work / "adjudication-judgments" / "claude" / "leaks.json").read_text())["leaks"]
        self.assertEqual([record["input_sha256"] for record in records], [snapshot[f"{NAME}.AB"]])


class FourthRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (fourth round): judgments bind to the prompt used and the evidence tree."""

    def test_provenance_names_the_prompt_used_and_the_evidence_tree(self):
        custom = self.base / "custom-prompt.md"
        custom.write_text(adjudicate.PROMPT_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        default = adjudicate.adjudication_provenance(repo=self.repo)
        self.assertNotEqual(adjudicate.adjudication_provenance(custom, self.repo)["prompt_sha256"],
                            default["prompt_sha256"])
        (self.repo / "new-receipt.json").write_text("{}", encoding="utf-8")
        self.assertNotEqual(adjudicate.adjudication_provenance(repo=self.repo)["repo_tree_sha256"],
                            default["repo_tree_sha256"])

    def test_judgments_against_another_evidence_tree_do_not_assemble_together(self):
        self.inputs()
        for order in adjudicate.ORDERS:
            self.judgment("claude", order, "codex")
        (self.repo / "new-receipt.json").write_text("{}", encoding="utf-8")
        for order in adjudicate.ORDERS:
            self.judgment("codex", order, "codex")
        code, err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        # Refused before the provenance comparison: the lane root changed after `inputs` (round 6, REG6-2).
        self.assertIn("changed after `inputs`", err)


class FifthRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (fifth round)."""

    def setUp(self):
        super().setUp()
        self.inputs()

    def test_a_result_from_another_claude_args_snapshot_is_refused(self):
        adjudicate.claude_args(self.work, self.repo)
        stale = self.snapshot_id()
        (self.repo / "new-receipt.json").write_text("{}", encoding="utf-8")
        adjudicate.claude_args(self.work, self.repo)
        self.assertNotEqual(stale, self.snapshot_id())
        with self.assertRaisesRegex(ValueError, "not the current claude-args snapshot"):
            adjudicate.collect_claude(self.work, self.as_workflow({"snapshot_id": stale, "items": []}), "claude-opus-5-5")

    def test_a_project_level_adjudicator_in_the_run_dir_must_be_the_vendored_one(self):
        run_dir = self.base / "hosts" / "blind" / "run"
        (run_dir / ".claude" / "agents").mkdir(parents=True)
        (run_dir / ".claude" / "agents" / "blind-adjudicator.md").write_text("broader\n", encoding="utf-8")
        code, err = quiet(adjudicate.main, ["claude-args", "--work-dir", str(self.work), "--repo", str(self.repo), "--run-dir", str(self.repo),
                                            "--agent-file", str(adjudicate.VENDORED_ADJUDICATOR),
                                            "--run-dir", str(run_dir)])
        self.assertEqual(code, 2)
        self.assertIn("is not the vendored", err)

    def test_a_retargeted_internal_symlink_changes_the_tree_digest(self):
        (self.repo / "a.json").write_text("{}", encoding="utf-8")
        (self.repo / "b.json").write_text("[]", encoding="utf-8")
        os.symlink("a.json", self.repo / "cited.json")
        before = adjudicate.tree_sha256(self.repo)
        (self.repo / "cited.json").unlink()
        os.symlink("b.json", self.repo / "cited.json")
        self.assertNotEqual(adjudicate.tree_sha256(self.repo), before)

    def test_a_packet_changed_after_inputs_is_refused(self):
        index = json.loads((adjudicate.index_path(self.work)).read_text(encoding="utf-8"))
        packet = Path(index["layers"][0]["packet_path"])
        packet.write_text(packet.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "packets changed after"):
            adjudicate.claude_args(self.work, self.repo)


class SixthRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (sixth round)."""

    def test_paths_after_html_delimiters_are_scrubbed_and_caught(self):
        text = "<code>/srv/blind/run/export/evidence/x.json</code>"
        self.assertNotIn("/srv/blind", adjudicate.scrub_text(text, str(self.work / "packets"), ()))
        self.assertTrue(adjudicate.unscrubbed_paths({"why": "<code>/opt/lane/x.json</code>"}))

    def test_claude_args_refuses_a_git_backed_repository(self):
        self.inputs()
        (self.repo / ".git").mkdir()
        code, err = quiet(adjudicate.main, ["claude-args", "--work-dir", str(self.work), "--repo", str(self.repo), "--run-dir", str(self.repo),
                                            "--agent-file", str(adjudicate.VENDORED_ADJUDICATOR)])
        self.assertEqual(code, 2)
        self.assertIn(".git", err)


class SeventhRereviewOf145Tests(AdjudicateFixture):
    """Codex re-review of #145 (seventh round)."""

    def setUp(self):
        super().setUp()
        self.inputs()

    def test_an_input_edited_after_inputs_is_refused(self):
        ab = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        ab.write_text(ab.read_text(encoding="utf-8").replace("}", " }", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inputs changed after"):
            adjudicate.claude_args(self.work, self.repo)

    def test_a_url_does_not_swallow_an_adjacent_host_path(self):
        text = '<a href="https://example.com/x">x</a>/home/example/private.json'
        self.assertNotIn("/home/example/private.json", adjudicate.scrub_text(text, str(self.work / "packets"), ()))
        self.assertTrue(adjudicate.unscrubbed_paths({"why": 'https://example.com/x">/opt/lane/private.json'}))

    def test_record_prose_is_scrubbed_before_it_is_written(self):
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "codex")
        path = self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["judge"]["why"] = data["judge"]["why"] + f" Checked {self.repo}/evidence/receipt.json directly."
        path.write_text(json.dumps(data), encoding="utf-8")
        code, _err, record = self.assemble()
        self.assertEqual(code, 0)
        self.assertNotIn(str(self.repo), record["why"])
        self.assertIn("evidence/receipt.json", record["why"])


class InputScrubTests(AdjudicateFixture):
    """Round-2 review (adjudication round 3): every real input tripped the leak rule, because inputs carried
    the packet's absolute path and left absolute paths outside the lane roots."""

    def test_inputs_carry_no_packet_path_and_no_host_path(self):
        packet = self.work / "packets" / f"{NAME}.json"
        self.write_return("claude", "c1", refutation={"status": "unrefuted"},
                          sources_read=[str(packet), f"{self.repo}/evidence/receipt.json (lines 1-9)"],
                          why_selected=f"c1: see {self.repo}/docs/a.md, /home/example/code/agent-lab/docs/tasks/t.md "
                                       "and <host-path>/SKILL.md (https://github.com/example/one).")
        self.write_return("codex", "c2", sources_read=["evidence/receipt.json", f"{packet}"],
                          limits=["could not read ~/notes/verdicts.md or $HOME/.codex/AGENTS.md"])
        code, err = self.inputs()
        self.assertEqual(code, 0, err)
        body = self.input_body()
        self.assertEqual(set(body), {"layer", "packet_sha256", "A", "B"})
        self.assertEqual(body["A"]["sources_read"], ["PACKET", "evidence/receipt.json"])
        self.assertEqual(body["A"]["why_selected"], "c1: see docs/a.md, <outside-path> "
                                                    "<outside-path> (https://github.com/example/one).")
        self.assertEqual(body["B"]["limits"], ["could not read <outside-path> <outside-path>"])
        self.assertEqual(adjudicate.unscrubbed_paths(body), [])
        self.assertNotIn(str(self.base), json.dumps(body))
        index = adjudicate.load_index(self.work)
        self.assertEqual(adjudicate.packet_paths(index)[NAME], str(self.snapshot_packet()))
        self.assertEqual(adjudicate.claude_args(self.work, self.repo)["items"][0]["packet_path"],
                         str(self.snapshot_packet()))

    def test_lane_repo_root_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            adjudicate.main(["inputs", "--work-dir", str(self.work)])
        self.assertEqual(raised.exception.code, 2)

    def test_inputs_refuse_to_write_a_layer_whose_host_path_survives_scrubbing(self):
        self.inputs()
        self.assertTrue((self.work / "adjudication-inputs" / f"{NAME}.AB.json").is_file())
        self.write_return("codex", "c2", limits=["see ~example/private/verdicts.md"])
        code, err = self.inputs()
        self.assertEqual(code, 1)
        self.assertIn("host paths remain after scrubbing: ~example/private/verdicts.md", err)
        self.assertFalse((self.work / "adjudication-inputs" / f"{NAME}.AB.json").exists(), "the stale input is removed")
        index = adjudicate.load_index(self.work)
        self.assertEqual(index["skipped"][0]["unscrubbed"], ["~example/private/verdicts.md"])
        self.assertEqual(adjudicate.pending_items(index), [])


class RootDepthTests(AdjudicateFixture):
    """Round-2 review (adjudication round 3): blind-adjudicator refuses shallow repository roots, so the Claude
    family alone would refuse while the Codex family judged."""

    def test_root_issue_matches_the_blind_adjudicator_rule(self):
        for bad in ("/", "/home", "/tmp", "/home/example", "/Users/example", "/root", "/tmp/a/b", "/srv/x/y",
                    "/a/../b/c/d", "/a/b/c/$HOME", "relative/a/b/c", str(Path.home())):
            self.assertIsNotNone(adjudicate.root_issue(bad), bad)
        for good in ("/tmp/a/b/c", "/home/example/code/export", str(self.repo)):
            self.assertIsNone(adjudicate.root_issue(good), good)

    def test_every_entry_point_refuses_a_shallow_root_with_exit_2(self):
        # The depth check is textual; a fixed two-component path stays shallow on every host (macOS temp
        # directories sit under /private/var/folders/..., deep enough to pass as <tmp>/export).
        shallow = Path("/srv/blind-export")
        code, err = self.inputs(shallow)
        self.assertEqual(code, 2)
        self.assertIn("path components", err)
        self.inputs()
        code, err = quiet(adjudicate.main, ["claude-args", "--work-dir", str(self.work), "--repo", str(shallow), "--run-dir", str(shallow)])
        self.assertEqual(code, 2)
        self.assertIn("blind-adjudicator refuses", err)
        code, err = quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", "/home",
                                            "--model", "gpt-6-astra"])
        self.assertEqual(code, 2)
        self.assertIn("/home", err)

    def test_a_work_dir_inside_the_repository_root_is_refused(self):
        # blind-adjudicator refuses an input or packet file inside the repository root.
        self.assertIsNotNone(adjudicate.refuse_work_dir_inside(self.repo / "work", self.repo))
        self.assertIsNone(adjudicate.refuse_work_dir_inside(self.work, self.repo))


class EighthRereviewOf145Tests(AdjudicateFixture):
    """Round-8 review of #145: judges read an immutable packet snapshot that is verified before and after
    judging, and a selective rebuild keeps every other layer in the index."""

    def second_layer(self):
        name = "foundation__other-layer"
        packet = dict(PACKET, layer_id="other-layer")
        path = self.work / "packets" / f"{name}.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_return("claude", "c1", name=name, sha=sha, refutation={"status": "unrefuted"},
                          final_source="proposal")
        self.write_return("codex", "c2", name=name, sha=sha)
        return name

    def test_judges_read_a_snapshot_that_edits_to_the_live_packet_do_not_reach(self):
        live = self.work / "packets" / f"{NAME}.json"
        original = live.read_bytes()
        self.inputs()
        live.write_text(json.dumps(dict(PACKET, requirement="edited after inputs")), encoding="utf-8")
        snapshot = self.snapshot_packet()
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertEqual(adjudicate.claude_args(self.work, self.repo)["items"][0]["packet_path"], str(snapshot))

    def test_a_tampered_snapshot_is_refused_by_claude_args_and_collect(self):
        self.inputs()
        args = adjudicate.claude_args(self.work, self.repo)
        self.snapshot_packet().write_text(json.dumps(dict(PACKET, requirement="tampered")), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "packets changed after `inputs`"):
            adjudicate.claude_args(self.work, self.repo)
        verdict = {"preferred": "A", "why": WHY, "evidence_refs": ["evidence/receipt.json"], "leak": False,
                   "leak_text": ""}
        refute = {"refuted": False, "reason": "The cited receipt exists and shows the run.", "evidence_refs": [],
                  "leak": False, "leak_text": ""}
        result = {"snapshot_id": args["snapshot_id"],
                  "items": [{"name": NAME, "order": order, "judge": verdict, "refuter": refute}
                            for order in adjudicate.ORDERS]}
        missing = adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", self.repo)
        self.assertEqual({reason for _, reason in missing}, {"the packet snapshot changed; rerun inputs"})

    def test_a_snapshot_changed_during_a_codex_call_voids_the_judgment(self):
        self.inputs()
        calls = []

        def changed_after_first_check(items):
            calls.append(items)
            return [] if len(calls) == 1 else [f"{item['name']}.{item['order']}" for item in items]

        judge = {"preferred": "A", "why": WHY, "evidence_refs": ["evidence/receipt.json"], "leak": False,
                 "leak_text": ""}
        refute = {"refuted": False, "reason": "The cited receipt exists and shows the run.", "evidence_refs": [],
                  "leak": False, "leak_text": ""}
        call = mock.Mock(side_effect=[(judge, "gpt-6-astra", [0], None, None),
                                      (refute, "gpt-6-astra", [0], None, None)])
        with mock.patch.object(adjudicate, "packets_changed", side_effect=changed_after_first_check), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(call)), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            code, _ = quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                              "--model", "gpt-6-astra", "--jobs", "1"])
        self.assertEqual(code, 1)
        records = [json.loads(path.read_text(encoding="utf-8")) for path in
                   (self.work / "adjudication-judgments" / "codex").glob(f"{NAME}.*.json")]
        self.assertTrue(records)
        voided = [record for record in records if record.get("failure") ==
                  "the packet snapshot changed during the call"]
        self.assertTrue(voided, records)
        for record in voided:
            self.assertIsNone(record.get("judge"))

    def test_a_selective_rebuild_keeps_other_layers_and_skips_a_selected_layer_whose_packet_is_gone(self):
        other = self.second_layer()
        self.inputs()
        self.assertEqual({entry["layer"] for entry in adjudicate.load_index(self.work)["layers"]}, {NAME, other})
        code, err = quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work), "--lane-repo-root",
                                            str(self.repo), "--layers", "native-clients"])
        self.assertEqual(code, 0, err)
        index = adjudicate.load_index(self.work)
        self.assertEqual({entry["layer"] for entry in index["layers"]}, {NAME, other})
        (self.work / "packets" / f"{other}.json").unlink()
        code, err = quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work), "--lane-repo-root",
                                            str(self.repo), "--layers", "other-layer"])
        self.assertEqual(code, 1, err)
        self.assertIn("skipped foundation__other-layer: the packet is missing", err)
        index = adjudicate.load_index(self.work)
        self.assertEqual([entry["layer"] for entry in index["layers"]], [NAME])
        self.assertEqual(index["skipped"], [{"layer": other, "reason": "the packet is missing"}])


class NinthRereviewOf145Tests(AdjudicateFixture):
    """Round-9 review of #145: the evidence tree is re-verified after judging, the packet snapshots are audit
    roots, leak text is redacted, and host paths starting with any legal character are scrubbed."""

    JUDGE = {"preferred": "A", "why": WHY, "evidence_refs": ["evidence/receipt.json"], "leak": False, "leak_text": ""}
    REFUTE = {"refuted": False, "reason": "The cited receipt exists and shows the run.", "evidence_refs": [],
              "leak": False, "leak_text": ""}

    def run_codex(self, tree_values, events=None):
        # The launch digest, then the digest every later check sees (after each call and at the end of the run).
        launch, later = tree_values
        trees = iter([launch])
        call = mock.Mock(side_effect=[(self.JUDGE, "gpt-6-astra", [0], None, None),
                                      (self.REFUTE, "gpt-6-astra", [0], None, None)] * 2)
        with mock.patch.object(adjudicate, "tree_sha256", side_effect=lambda repo: next(trees, later)), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(call, events)), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            return quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                           "--model", "gpt-6-astra"])

    def test_a_tree_changed_during_the_codex_run_voids_every_judgment_of_the_run(self):
        self.inputs()
        code, err = self.run_codex(["a" * 64, "b" * 64])
        self.assertEqual(code, 1)
        self.assertIn(adjudicate.TREE_CHANGED, err)
        for order in adjudicate.ORDERS:
            record = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.{order}.json")
                                .read_text(encoding="utf-8"))
            self.assertEqual(record["failure"], adjudicate.TREE_CHANGED)
            self.assertIsNone(record["judge"])

    def test_an_unchanged_tree_keeps_the_judgments_and_the_snapshots_are_audit_roots(self):
        self.inputs()
        events = self.work / "adjudication-judgments" / "codex" / "events"
        events.mkdir(parents=True, exist_ok=True)
        (events / f"{NAME}.AB.judge.jsonl").write_text("", encoding="utf-8")
        code, err = self.run_codex(["a" * 64, "a" * 64])
        self.assertEqual(code, 0, err)
        audit = json.loads((self.work / "adjudication-judgments" / "codex" / "blind-audit.json")
                           .read_text(encoding="utf-8"))
        # Each call may read the repository, its own input and its packet snapshot only (F3): not the inputs
        # directory or the index.
        self.assertEqual(audit["allowed_roots"][f"{NAME}.AB.judge"],
                         [str(self.repo), str(self.work / "adjudication-inputs" / f"{NAME}.AB.json"),
                          str(self.snapshot_packet())])

    def test_claude_collect_refuses_judgments_when_the_tree_changed_after_claude_args(self):
        (self.repo / "evidence").mkdir()
        (self.repo / "evidence" / "receipt.json").write_text("{}", encoding="utf-8")
        self.rewrite_returns()  # the lanes read the tree with the receipt (BIND-R4-9)
        self.inputs()
        args = adjudicate.claude_args(self.work, self.repo)
        result = {"snapshot_id": args["snapshot_id"],
                  "items": [{"name": NAME, "order": order, "judge": self.JUDGE, "refuter": self.REFUTE}
                            for order in adjudicate.ORDERS]}
        (self.repo / "evidence" / "receipt.json").write_text('{"changed": true}', encoding="utf-8")
        missing = adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", self.repo)
        self.assertEqual({reason for _, reason in missing}, {adjudicate.TREE_CHANGED})
        (self.repo / "evidence" / "receipt.json").write_text("{}", encoding="utf-8")
        self.assertEqual(adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", self.repo), [])

    def test_leak_text_is_redacted_before_it_is_retained_or_printed(self):
        raw = "found /home/example/code/nas-wt-codex-blind/x.json, ~/notes and /évidence/private.json"
        self.assertEqual(adjudicate.redact_leak_text(raw),
                         "found <outside-path>, <outside-path> <outside-path>")
        self.inputs()
        index = adjudicate.load_index(self.work)
        input_path = self.work / "adjudication-inputs" / f"{NAME}.AB.json"
        with contextlib.redirect_stderr(io.StringIO()) as err:
            records = adjudicate.record_leaks(self.work / "leaks.json", index, [
                (NAME, "AB", input_path, {"family": "openai", "stage": "judge", "text": raw})])
        self.assertEqual(records[0]["text"], "found <outside-path>, <outside-path> <outside-path>")
        self.assertNotIn("/home/example", err.getvalue())
        self.assertNotIn("/home/example", (self.work / "leaks.json").read_text(encoding="utf-8"))

    def test_paths_starting_with_non_ascii_or_symbol_characters_are_scrubbed_and_caught(self):
        for path in ("/évidence/private.json", "/-private/codex.json", "/@host/path"):
            text = f"see {path} for details"
            self.assertEqual(adjudicate.scrub_text(text, str(self.work / "packets")),
                             "see <outside-path>", path)
            self.assertTrue(adjudicate.unscrubbed_paths([text]), path)
        for prose in ("a +/- 2% band", "and/or", "A / B", "3/4 of runs"):
            self.assertEqual(adjudicate.scrub_text(prose, str(self.work / "packets")), prose)
            self.assertEqual(adjudicate.unscrubbed_paths([prose]), [], prose)


class TenthRereviewOf145Tests(AdjudicateFixture):
    """Round-10 review of #145: collection is bound to the snapshotted repository, each Codex worker rechecks
    the indexed input, and an assembled adjudication names the lane returns it compared."""

    JUDGE = NinthRereviewOf145Tests.JUDGE
    REFUTE = NinthRereviewOf145Tests.REFUTE

    def test_claude_collect_refuses_another_repository(self):
        self.inputs()
        args = adjudicate.claude_args(self.work, self.repo)
        result = {"snapshot_id": args["snapshot_id"], "items": []}
        with self.assertRaisesRegex(ValueError, "is not the claude-args repository"):
            adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", "/")
        with self.assertRaisesRegex(ValueError, "is not the claude-args repository"):
            adjudicate.collect_claude(self.work, self.as_workflow(dict(result, repo=str(self.base))), "claude-opus-5-5")
        self.assertEqual(len(adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", str(self.repo))), 2)

    def run_codex_with_input_checks(self, check_results):
        checks = iter(check_results)
        call = mock.Mock(side_effect=[(self.JUDGE, "gpt-6-astra", [0], None, None),
                                      (self.REFUTE, "gpt-6-astra", [0], None, None)] * 2)
        real = adjudicate.inputs_changed

        def inputs_changed(index, stems):
            value = next(checks, None)
            return real(index, stems) if value is None else ([stems[0]] if value else [])

        with mock.patch.object(adjudicate, "inputs_changed", side_effect=inputs_changed), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(call)), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            code, err = quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                                "--model", "gpt-6-astra", "--jobs", "1"])
        return code, err, call

    def test_a_worker_never_judges_an_input_changed_after_scheduling(self):
        self.inputs()
        # scheduling AB, scheduling BA, then AB's worker start sees a change.
        code, err, call = self.run_codex_with_input_checks([False, False, True, False, False])
        self.assertEqual(code, 1)
        self.assertIn("the input changed after `inputs` built it", err)
        self.assertEqual(call.call_count, 2, "only the unchanged order is judged")

    def test_an_input_changed_during_the_call_voids_the_judgment(self):
        self.inputs()
        code, err, _call = self.run_codex_with_input_checks([False, False, False, True, False, False])
        self.assertEqual(code, 1)
        self.assertIn("the input changed during the call", err)

    def test_assemble_refuses_lane_returns_changed_after_inputs_and_names_the_ones_it_compared(self):
        self.inputs()
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude")
        code, err, record = self.assemble()
        self.assertEqual(code, 0, err)
        self.assertEqual(record["lane_returns_sha256"],
                         {lane: adjudicate.current_return_sha256(self.work / lane / f"{NAME}.json")
                          for lane in ("claude", "codex")})
        self.write_return("codex", "c2", limits=["rerun after inputs"])
        code, err, record = self.assemble()
        self.assertEqual(code, 1)
        self.assertIn("the codex lane return changed after `inputs`", err)
        self.assertIsNone(record)


class EleventhRereviewOf145Tests(AdjudicateFixture):
    """Round-11 review of #145: Windows host paths are scrubbed, and inputs hashes the bytes it parsed."""

    def test_windows_host_paths_are_scrubbed_and_caught(self):
        for path in (r"C:\Users\example\private\result.json", r"\Users\example\private.json",
                     r"\\server\share\x.json", "C:/Users/example/y.json"):
            text = f"see {path} for details"
            self.assertEqual(adjudicate.scrub_text(text, str(self.work / "packets")),
                             "see <outside-path>", path)
            self.assertTrue(adjudicate.unscrubbed_paths([text]), path)
            self.assertNotIn("Users", adjudicate.redact_leak_text(text))
        for prose in ("Section C: done", r"a regex \d+ here", "and/or"):
            self.assertEqual(adjudicate.scrub_text(prose, str(self.work / "packets")), prose)

    def test_inputs_hash_the_lane_return_bytes_they_parsed(self):
        # The codex return is rewritten right after its first read, as a lane rerun racing `inputs` would.
        codex_path = self.work / "codex" / f"{NAME}.json"
        original = codex_path.read_bytes()
        rewritten = json.dumps(lane_return("codex", "c2", self.sha, limits=["rewritten"])).encode("utf-8")
        real_read_bytes, real_load_json = Path.read_bytes, adjudicate.load_json
        state = {"rewritten": False}

        def rewrite_after_first_read(path):
            if Path(path) == codex_path and not state["rewritten"]:
                state["rewritten"] = True
                codex_path.write_bytes(rewritten)

        def read_bytes(path):
            data = real_read_bytes(path)
            rewrite_after_first_read(path)
            return data

        def load_json(path):
            data = real_load_json(path)
            rewrite_after_first_read(path)
            return data

        with mock.patch.object(Path, "read_bytes", read_bytes), mock.patch.object(adjudicate, "load_json", load_json):
            self.inputs()
        index = adjudicate.load_index(self.work)
        self.assertEqual(index["layers"][0]["lane_returns_sha256"]["codex"],
                         adjudicate.sealed_form_sha256(json.loads(original)),
                         "the hash is of the bytes the inputs were built from")

class TwelfthRereviewOf145Tests(AdjudicateFixture):
    """Round-12 review of #145: the effective adjudicator role is snapshotted and rechecked, and a missing
    evidence repository is refused before its tree is hashed."""

    def test_claude_collect_refuses_judgments_when_the_loaded_role_changed_after_claude_args(self):
        self.inputs()
        role = self.base / "agents" / "blind-adjudicator.md"
        role.parent.mkdir()
        role.write_bytes(adjudicate.VENDORED_ADJUDICATOR.read_bytes())
        args = adjudicate.claude_args(self.work, self.repo, role_files=[role])
        result = {"snapshot_id": args["snapshot_id"],
                  "items": [{"name": NAME, "order": order, "judge": NinthRereviewOf145Tests.JUDGE,
                             "refuter": NinthRereviewOf145Tests.REFUTE} for order in adjudicate.ORDERS]}
        role.write_text(role.read_text(encoding="utf-8") + "\nextra rule\n", encoding="utf-8")
        missing = adjudicate.collect_claude(self.work, self.as_workflow(result), "claude-opus-5-5", str(self.repo))
        self.assertEqual({reason for _, reason in missing}, {adjudicate.ROLE_CHANGED})

    def test_a_missing_repository_is_refused_before_hashing(self):
        self.inputs()
        missing = self.base / "hosts" / "blind" / "gone"
        for argv in (["claude-args", "--work-dir", str(self.work), "--repo", str(missing), "--run-dir", str(missing),
                      "--agent-file", str(adjudicate.VENDORED_ADJUDICATOR)],
                     ["codex", "--work-dir", str(self.work), "--repo", str(missing), "--model", "gpt-6-astra"]):
            code, err = quiet(adjudicate.main, argv)
            self.assertEqual(code, 2, argv[0])
            self.assertIn("is not an existing directory", err)


class ThirteenthRereviewOf145Tests(AdjudicateFixture):
    """Round-13 review of #145: whitespace-bearing host paths are scrubbed whole, and an edited claude-args
    snapshot is refused."""

    def test_glued_segments_and_url_fields_do_not_carry_host_paths(self):
        # Codex review of #145: "/home/example,private/x" and "https://x;local=/home/..." kept private suffixes.
        packets = str(self.work / "packets")
        self.assertEqual(adjudicate.scrub_text("see /home/example,private/result.json", packets), "see <outside-path>")
        scrubbed = adjudicate.scrub_text("source=https://example.com;local=/home/example/private.json", packets)
        self.assertNotIn("private.json", scrubbed)
        self.assertIn("https://example.com", scrubbed)
        self.assertNotIn("example,private", adjudicate.redact_leak_text("at /home/example,private/result.json"))

    def test_host_paths_with_spaces_leave_no_suffix(self):
        packets = str(self.work / "packets")
        for text, expected in (("see /home/example user/private.json now", "see <outside-path>"),
                               (r"at C:\Users\Example User\private.json", "at <outside-path>"),
                               ("~/My Docs/x.json and more", "<outside-path>"),
                               ("/home/example/a b/c d/e.json end", "<outside-path>"),
                               ("see /srv/My Project/private key now", "see <outside-path>"),
                               (r"at C:\Users\example user\private key, then", "at <outside-path>, then"),
                               ("see /home/example user/private.json. Next sentence.",
                                "see <outside-path>. Next sentence."),
                               # A next sentence holding a / separator may continue a spaced path, so it goes too
                               # (independent review of #145, round 4, R4-REG-5): privacy over prose.
                               ("/srv/x/y is missing. c2 wins because docs/b.md shows it.", "<outside-path>."),
                               ("/srv/x/y is missing. c2 wins on the receipt.",
                                "<outside-path>. c2 wins on the receipt.")):
            self.assertEqual(adjudicate.scrub_text(text, packets), expected, text)
            self.assertEqual(adjudicate.redact_leak_text(text), expected, text)
        self.assertEqual(adjudicate.scrub_text("evidence/a.json and plain words", packets),
                         "evidence/a.json and plain words")

    def test_an_edited_snapshot_is_refused_even_with_its_old_snapshot_id(self):
        self.inputs()
        args = adjudicate.claude_args(self.work, self.repo)
        path = self.work / "adjudication-judgments" / "claude" / adjudicate.CLAUDE_ARGS_SNAPSHOT
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        snapshot["inputs"] = {key: "0" * 64 for key in snapshot["inputs"]}
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not hash to its snapshot_id"):
            adjudicate.collect_claude(self.work, self.as_workflow({"snapshot_id": args["snapshot_id"], "items": []}),
                                      "claude-opus-5-5", str(self.repo))


class FourteenthRereviewOf145Tests(AdjudicateFixture):
    """Round-14 review of #145: collection verifies what the workflow consumed, leaks of invalidated runs are
    discarded, a deleted input is a missing judgment, and spaced final segments are scrubbed whole."""

    def result(self, **item_overrides):
        args = adjudicate.claude_args(self.work, self.repo)
        items = [{"name": NAME, "order": order, "packet_sha256": self.sha, "judge": NinthRereviewOf145Tests.JUDGE,
                  "refuter": NinthRereviewOf145Tests.REFUTE, **item_overrides} for order in adjudicate.ORDERS]
        return self.as_workflow({"snapshot_id": args["snapshot_id"], "items": items})

    def test_other_consumed_arguments_are_refused(self):
        self.inputs()
        other = self.base / "elsewhere" / f"{NAME}.AB.json"
        missing = adjudicate.collect_claude(self.work, self.result(path=str(other)), "claude-opus-5-5")
        self.assertEqual({reason for _, reason in missing},
                         {"the workflow judged other input or packet paths than claude-args gave it"})
        for change, message in (({"prompt": "edited prompt <!-- refuter -->"}, "prompt is not the one"),
                                ({"repo": None}, "repo is not the claude-args repository")):
            with self.assertRaisesRegex(ValueError, message):
                adjudicate.collect_claude(self.work, {**self.result(), **change}, "claude-opus-5-5")

    def test_a_leak_from_an_invalidated_run_is_not_recorded(self):
        (self.repo / "evidence").mkdir()
        (self.repo / "evidence" / "receipt.json").write_text("{}", encoding="utf-8")
        self.rewrite_returns()  # the lanes read the tree with the receipt (BIND-R4-9)
        self.inputs()
        result = self.result(judge=None, refuter=None, leak={"stage": "judge", "text": "provenance: x"})
        (self.repo / "evidence" / "receipt.json").write_text('{"changed": true}', encoding="utf-8")
        missing = adjudicate.collect_claude(self.work, result, "claude-opus-5-5")
        self.assertEqual({reason for _, reason in missing}, {adjudicate.TREE_CHANGED})
        self.assertEqual(adjudicate.recorded_leaks(self.work), set())

    def test_a_deleted_input_is_a_missing_judgment_not_a_traceback(self):
        self.inputs()
        result = self.result()
        (self.work / "adjudication-inputs" / f"{NAME}.BA.json").unlink()
        missing = dict(adjudicate.collect_claude(self.work, result, "claude-opus-5-5"))
        self.assertEqual(missing[f"{NAME}.BA"], "the input changed after claude-args; rerun claude-args")

    def test_spaced_final_segments_are_scrubbed_whole(self):
        packets = str(self.work / "packets")
        for text in ("see /srv/My Project/private key.json now", r"see C:\Users\example user\private file.json now"):
            self.assertEqual(adjudicate.scrub_text(text, packets), "see <outside-path>", text)
            self.assertEqual(adjudicate.redact_leak_text(text), "see <outside-path>", text)

    def test_the_workflow_echoes_what_it_consumed(self):
        source = (TOOL_DIR / "adjudication-lane.js").read_text(encoding="utf-8")
        self.assertIn("path: i.path, packet_path: i.packet_path", source)
        self.assertEqual(source.count("...echo(i)"), 5)
        self.assertIn("prompt: PROMPT", source)


class IndependentReviewOf145Tests(AdjudicateFixture):
    """Independent review of #145: the A/B family map is a per-layer secret kept outside the inputs directory
    (F3), a judgment counts only for this index's input (M3), and claude-args names where the workflow runs (M4)."""

    def test_the_family_position_is_a_per_layer_secret_outside_the_inputs_directory(self):
        with mock.patch.object(adjudicate.secrets, "choice", return_value="B"):
            self.inputs()
        self.assertFalse((self.work / "adjudication-inputs" / "index.json").exists())
        self.assertFalse((self.work / adjudicate.INDEX_NAME).exists())
        self.assertFalse(adjudicate.index_path(self.work).is_relative_to(self.work))
        entry = adjudicate.load_index(self.work)["layers"][0]
        self.assertEqual(entry["claude_position"], {"AB": "B", "BA": "A"})
        ab = json.loads((self.work / "adjudication-inputs" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual(ab["A"]["winner_keys"], ["c2"], "the Codex return is A when the secret says so")
        self.assertNotIn("Claude return", (TOOL_DIR / "adjudication-prompt.md").read_text(encoding="utf-8"))

    def test_a_judgment_of_another_directorys_input_does_not_count(self):
        self.inputs()
        entry = adjudicate.load_index(self.work)["layers"][0]
        self.judgment("claude", "AB", "claude")
        data = json.loads((self.work / "adjudication-judgments" / "claude" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertIsNone(adjudicate.usable_judgment(data, "anthropic", "AB", self.sha, entry=entry))
        copied_input = self.base / "other-work" / "adjudication-inputs" / f"{NAME}.AB.json"
        copied_input.parent.mkdir(parents=True)
        copied_input.write_bytes(Path(data["input_path"]).read_bytes())
        moved = dict(data, input_path=str(copied_input))
        self.assertEqual(adjudicate.usable_judgment(moved, "anthropic", "AB", self.sha, entry=entry),
                         "judged an input this index did not build")

    def test_claude_args_requires_run_dir(self):
        self.inputs()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            adjudicate.main(["claude-args", "--work-dir", str(self.work), "--repo", str(self.repo)])
        self.assertEqual(raised.exception.code, 2)


class RereviewR2Tests(unittest.TestCase):
    def test_the_bound_form_is_the_one_record_verdicts_seals(self):
        # Re-review R2: sources_read under a lane root are relativized before sealing; the binding must match.
        import record_verdicts
        data = {"schema_version": 1, "sources_read": ["/x/hosts/blind/export/README.md (intro)"], "why_selected": "w"}
        roots = ("/x/hosts/blind/export",)
        sealed = record_verdicts.sealed_text(record_verdicts.with_relative_sources(data, adjudicate.REPO_ROOT, roots))
        self.assertEqual(adjudicate.sealed_form_sha256(data, roots), hashlib.sha256(sealed.encode("utf-8")).hexdigest())


class SixteenthRereviewOf145Tests(AdjudicateFixture):
    """Codex review of #145 at a2434e2e: the index cannot flip a winner, and a flagged Codex audit voids the
    judgment."""

    JUDGE = NinthRereviewOf145Tests.JUDGE
    REFUTE = NinthRereviewOf145Tests.REFUTE

    def test_an_edited_position_map_does_not_flip_the_winner(self):
        self.inputs()
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude")
        code, err, record = self.assemble()
        self.assertEqual(code, 0, err)
        self.assertEqual(record["winner_lane"], "claude")
        path = adjudicate.index_path(self.work)
        index = json.loads(path.read_text(encoding="utf-8"))
        flip = {"A": "B", "B": "A"}
        index["layers"][0]["claude_position"] = {order: flip[pos] for order, pos in index["layers"][0]["claude_position"].items()}
        path.write_text(json.dumps(index), encoding="utf-8")
        code, err, record = self.assemble()
        self.assertIn("does not match the input contents", err)
        self.assertIsNone(record)

    def test_collect_has_nothing_to_do_when_no_layer_disagrees(self):
        # Re-review: with no disagreeing layer the workflow returns an argument issue without a snapshot_id.
        (self.work / "codex" / f"{NAME}.json").write_text(
            (self.work / "claude" / f"{NAME}.json").read_text(encoding="utf-8").replace('"lane": "claude"', '"lane": "codex"'),
            encoding="utf-8")
        self.write_return("codex", "c1")
        self.inputs()
        adjudicate.claude_args(self.work, self.repo)
        self.assertEqual(adjudicate.collect_claude(self.work, {"status": "incomplete", "argument_issues": ["items"]},
                                                   "claude-opus-5-5"), [])

    def test_a_leak_from_a_voided_codex_call_is_not_recorded(self):
        # Codex review of #145 at 3d0943cc: a leak from a call the audit voids must not become sticky.
        self.inputs()
        events = self.work / "adjudication-judgments" / "codex" / "events"
        events.mkdir(parents=True, exist_ok=True)
        leak_answer = (None, "gpt-6-astra", [0], None, "provenance: codex_lane_py_sha256")
        clean = [(self.JUDGE, "gpt-6-astra", [0], None, None), (self.REFUTE, "gpt-6-astra", [0], None, None)]
        call = mock.Mock(side_effect=[leak_answer] + clean)
        flagged = {f"{NAME}.AB.judge.jsonl": read_command_event(f"cat {adjudicate.index_path(self.work)}")}
        with mock.patch.object(adjudicate, "tree_sha256", return_value="a" * 64), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(call, flagged)), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                    "--model", "gpt-6-astra", "--jobs", "1"])
        self.assertEqual(adjudicate.recorded_leaks(self.work), set())

    def test_a_deleted_input_is_a_failure_not_a_traceback(self):
        self.inputs()
        real = adjudicate.inputs_changed
        calls = []

        def inputs_changed(index, stems):
            # Both scheduling checks pass; the AB input disappears right after them, before its worker starts.
            calls.append(stems)
            if len(calls) <= 2:
                if len(calls) == 2:
                    (self.work / "adjudication-inputs" / f"{NAME}.AB.json").unlink()
                return []
            return real(index, stems)

        with mock.patch.object(adjudicate, "inputs_changed", side_effect=inputs_changed), \
                mock.patch.object(adjudicate, "tree_sha256", return_value="a" * 64), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(mock.Mock(side_effect=[
                    (self.JUDGE, "gpt-6-astra", [0], None, None), (self.REFUTE, "gpt-6-astra", [0], None, None)] * 2))), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            code, err = quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                                "--model", "gpt-6-astra", "--jobs", "1"])
        self.assertEqual(code, 1)
        self.assertIn("the input changed after `inputs` built it", err)

    def test_a_resumed_codex_judgment_without_a_clean_audit_does_not_count(self):
        # Binding re-review N2: an interrupted run could leave a flagged call's record counted.
        self.inputs()
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude")
        path = self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.pop("audit_clean")
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(adjudicate.usable_judgment(record, "openai", "AB", self.sha),
                         "no clean blind audit recorded for this judgment")
        code, err, result = self.assemble()
        self.assertIsNone(result["winner_lane"])
        self.assertIn("openai", result["missing_families"])

    def test_a_flagged_codex_audit_voids_the_judgment(self):
        self.inputs()
        events = self.work / "adjudication-judgments" / "codex" / "events"
        events.mkdir(parents=True, exist_ok=True)
        index_file = adjudicate.index_path(self.work)
        code, err = NinthRereviewOf145Tests.run_codex(
            self, ["a" * 64, "a" * 64], {f"{NAME}.AB.judge.jsonl": read_command_event(f"cat {index_file}")})
        self.assertEqual(code, 1)
        self.assertIn(adjudicate.AUDIT_FLAGGED, err)
        record = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual(record["failure"], adjudicate.AUDIT_FLAGGED)
        self.assertIsNone(record["judge"])


@unittest.skipUnless(os.access(FAKE_BIN / "codex", os.X_OK), "fake codex fixture is not executable")
class CodexLeakTests(AdjudicateFixture):
    def setUp(self):
        super().setUp()
        self.inputs()
        self.argv_log = self.base / "argv.jsonl"
        self.return_file = self.base / "return.json"
        events = self.base / "events.jsonl"
        events.write_text(json.dumps({"type": "turn.completed", "model": "gpt-6-astra"}) + "\n", encoding="utf-8")
        self.env = {"PATH": f"{FAKE_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CODEX_FAKE_ARGV_LOG": str(self.argv_log), "CODEX_FAKE_RETURN_FILE": str(self.return_file),
                    "CODEX_FAKE_EVENTS_FILE": str(events), "CODEX_FAKE_COUNTER_FILE": str(self.base / "count")}

    def run_codex(self):
        with mock.patch.dict(os.environ, self.env):
            return quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                           "--timeout", "30", "--model", "gpt-6-astra"])

    def test_a_codex_judge_leak_is_missing_listed_and_not_retried(self):
        self.return_file.write_text(json.dumps({"preferred": "A", "why": "leak", "evidence_refs": [], "leak": True,
                                                "leak_text": "provenance: codex_lane_py_sha256"}), encoding="utf-8")
        code, err = self.run_codex()
        self.assertEqual(code, 1)
        calls = [json.loads(line) for line in self.argv_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(calls), 2, "one judge call per order: no retry and no refuter after a leak")
        self.assertIn(f"Packet file: {self.snapshot_packet()}\n", calls[0][-1])
        for order in adjudicate.ORDERS:
            data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.{order}.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(data["failure"], "leak")
            self.assertEqual(data["leak"], {"stage": "judge", "text": "provenance: codex_lane_py_sha256"})
            self.assertEqual(adjudicate.usable_judgment(data, "openai", order, self.sha), "leak")
        leaks = json.loads((self.work / "adjudication-judgments" / "codex" / "leaks.json").read_text(encoding="utf-8"))
        self.assertEqual([(e["family"], e["order"]) for e in leaks["leaks"]], [("openai", "AB"), ("openai", "BA")])
        self.assertIn("LEAK openai", err)

    def test_a_codex_leak_is_sticky_until_inputs_rebuild_the_file(self):
        """Round-2 review (adjudication round 3): a rerun erased the leak and counted the new judgment."""
        self.return_file.write_text(json.dumps({"preferred": "A", "why": "leak", "evidence_refs": [], "leak": True,
                                                "leak_text": "gpt-6"}), encoding="utf-8")
        self.run_codex()
        self.return_file.write_text(json.dumps({"preferred": "B", "why": WHY, "evidence_refs": [], "leak": False,
                                                "leak_text": "", "refuted": False, "reason": "holds"}),
                                    encoding="utf-8")
        code, err = self.run_codex()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.argv_log.read_text(encoding="utf-8").splitlines()), 2, "a leaked input is not rerun")
        self.assertIn("leak recorded for this input", err)
        for order in adjudicate.ORDERS:
            self.judgment("claude", order, "codex")
        code, _err, record = self.assemble()
        self.assertEqual((code, record), (1, None))
        split = json.loads((self.work / "adjudication-leaks.json").read_text(encoding="utf-8"))["split_layers"]
        self.assertEqual([entry["layer"] for entry in split], [NAME])
        # A rebuilt input with different content is judged again.
        self.write_return("claude", "c1", refutation={"status": "unrefuted"}, why_selected="c1 is native: evidence/receipt.json")
        self.inputs()
        code, err = self.run_codex()
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.argv_log.read_text(encoding="utf-8").splitlines()), 6)

    def test_a_codex_refuter_leak_drops_the_judgment(self):
        judge = {"preferred": "B", "why": WHY, "evidence_refs": ["evidence/receipt.json"]}
        answers = iter([(judge, "gpt-6-astra", [0], None, None), (None, "gpt-6-astra", [0], "leak", "gpt-6")] * 2)
        with mock.patch.object(adjudicate, "run_codex_call", writes_events(lambda *a, **k: next(answers))), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/bin/codex"):
            code, _err = self.run_codex()
        self.assertEqual(code, 1)
        data = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual((data["failure"], data["judge"], data["leak"]["stage"]), ("leak", None, "refuter"))


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
        self.assertEqual(source.count("agentType: 'blind-adjudicator', model: 'opus', effort: 'max', schema: "),
                         calls)
        self.assertNotIn("blind-lane-reviewer", source)
        for key in ("leak", "leak_text"):
            self.assertIn(key, source)
        self.assertIn("Do not try to identify which lane", source)


class SealedPacketKeysTests(AdjudicateFixture):
    """Review of #145 (F5): a --withhold-labels packet seals its candidates' manifest fields (their presence alone
    marked the catalog's current default); inputs restores them from --packet-keys to compare winner component
    sets as record_verdicts.py does, and refuses the layer without them."""

    def seal_packet(self, same_repository=False):
        packet = json.loads(json.dumps(PACKET))
        if same_repository:
            # Two manifest entries can share one repository (lane_packets.manifest_layer_candidates).
            packet["candidates"][1]["repository"] = packet["candidates"][0]["repository"]
        sealed = {candidate["key"]: {field: candidate.pop(field) for field in SEALED_CANDIDATE_FIELDS if field in candidate}
                  for candidate in packet["candidates"]}
        packet["withheld"] = sealed_candidate_labels()
        packet["sealed_candidates_sha256"] = sealed_candidates_sha256(sealed)
        path = self.work / "packets" / f"{NAME}.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        self.sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_return("claude", "c1", refutation={"status": "unrefuted"}, final_source="proposal")
        self.write_return("codex", "c2")
        keys = self.base / "keys" / "packet-keys.json"
        keys.parent.mkdir()
        keys.write_text(json.dumps({"schema_version": 1, "packets": {
            f"{NAME}.json": {"packet_sha256": self.sha, "candidates": sealed}}}), encoding="utf-8")
        return keys

    def index(self):
        return json.loads(adjudicate.index_path(self.work).read_text(encoding="utf-8"))

    def test_a_sealed_packet_needs_its_keys(self):
        self.seal_packet()
        self.assertEqual(self.inputs()[0], 1, "a skipped layer fails inputs")
        skipped = self.index()["skipped"]
        self.assertEqual([item["layer"] for item in skipped], [NAME])
        self.assertIn("pass --packet-keys", skipped[0]["reason"])
        self.assertFalse((self.work / "adjudication-inputs" / f"{NAME}.AB.json").exists())

    def test_the_keys_restore_component_ids_even_for_a_shared_repository(self):
        keys = self.seal_packet(same_repository=True)
        code, _err = quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work), "--lane-repo-root", str(self.repo),
                                             "--packet-keys", str(keys)])
        self.assertEqual(code, 0)
        entry = self.index()["layers"][0]
        # Without the keys both winners fall back to candidate:example-one and would compare as agreeing.
        self.assertEqual(entry["agreement"], "disagree")
        self.assertEqual(entry["components"]["claude"], [["comp-one", "https://github.com/example/one"]])
        self.assertEqual(entry["components"]["codex"], [["comp-two", "https://github.com/example/one"]])
        # Judges read the sealed packet, never the restored fields.
        self.assertNotIn("comp-one", self.snapshot_packet().read_text(encoding="utf-8"))

    def test_keys_for_other_packet_bytes_are_refused(self):
        keys = self.seal_packet()
        document = json.loads(keys.read_text(encoding="utf-8"))
        document["packets"][f"{NAME}.json"]["packet_sha256"] = "0" * 64
        keys.write_text(json.dumps(document), encoding="utf-8")
        quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work), "--lane-repo-root", str(self.repo),
                                "--packet-keys", str(keys)])
        self.assertIn("names packet_sha256", self.index()["skipped"][0]["reason"])


class CallBindingRound4Tests(AdjudicateFixture):
    """Independent review of #145, round 4: each Codex call is audited on its own stages only (BIND-R4-3) and a
    clean call's leak is persisted when the call ends, so an interrupted run keeps it (BIND-R4-4)."""

    LEAK = (None, "gpt-6-astra", [0], None, "provenance: codex_lane_py_sha256")
    JUDGE = NinthRereviewOf145Tests.JUDGE
    REFUTE = NinthRereviewOf145Tests.REFUTE

    def run_judges(self, answers, events=None, jobs="1"):
        with mock.patch.object(adjudicate, "tree_sha256", return_value="a" * 64), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(mock.Mock(side_effect=answers), events)), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            return quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                           "--model", "gpt-6-astra", "--jobs", jobs])

    def test_a_stale_refuter_events_file_does_not_void_a_clean_judge_leak(self):
        self.inputs()
        events = self.work / "adjudication-judgments" / "codex" / "events"
        events.mkdir(parents=True)
        # An earlier run's refuter read the index; this run's judge reports a leak, so no refuter runs.
        (events / f"{NAME}.AB.refute.jsonl").write_text(read_command_event(f"cat {adjudicate.index_path(self.work)}"),
                                                         encoding="utf-8")
        self.run_judges([self.LEAK, self.LEAK])
        self.assertFalse((events / f"{NAME}.AB.refute.jsonl").exists())
        record = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertTrue(record["audit_clean"])
        self.assertEqual(record["failure"], adjudicate.LEAK)
        self.assertIn(f"{NAME}.AB.json", {name for name, _sha in adjudicate.recorded_leaks(self.work)})

    def test_an_interrupted_run_keeps_the_leak_of_a_finished_call(self):
        self.inputs()
        with self.assertRaises(RuntimeError):
            self.run_judges([self.LEAK, RuntimeError("killed")])
        self.assertIn(f"{NAME}.AB.json", {name for name, _sha in adjudicate.recorded_leaks(self.work)})

    def test_a_tree_change_seen_after_a_call_voids_it_at_once(self):
        self.inputs()
        trees = iter(["a" * 64])
        with mock.patch.object(adjudicate, "tree_sha256", side_effect=lambda repo: next(trees, "b" * 64)), \
                mock.patch.object(adjudicate, "run_codex_call", writes_events(mock.Mock(side_effect=[
                    (self.JUDGE, "gpt-6-astra", [0], None, None), (self.REFUTE, "gpt-6-astra", [0], None, None),
                    RuntimeError("killed")]))), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            with self.assertRaises(RuntimeError):
                quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                        "--model", "gpt-6-astra", "--jobs", "1"])
        record = json.loads((self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json").read_text(encoding="utf-8"))
        self.assertEqual(record["failure"], adjudicate.TREE_CHANGED)
        self.assertIsNone(record["judge"])

    def test_a_second_run_on_the_same_work_dir_is_refused(self):
        # BIND-R4-5: two runs would recreate each other's Codex home and interleave events files.
        self.inputs()
        lock = adjudicate.codex_lane.codex_home_lock(self.work)  # shared with codex_lane (round 6, ISO-R6-1)
        with adjudicate.codex_lane.exclusive_run_lock(lock):
            code, err = self.run_judges([(self.JUDGE, "gpt-6-astra", [0], None, None)])
        self.assertEqual(code, 2)
        self.assertIn("another run holds", err)

    def test_a_work_dir_inside_a_repository_is_refused(self):
        # Codex review of #145 at a4dfd99e: the judges would see an unsanitized checkout through the input paths.
        repo_parent = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, repo_parent)
        (repo_parent / ".git").mkdir()
        issue = adjudicate.refuse_work_dir_inside(repo_parent / "state" / "work", self.repo)
        self.assertIn("inside the git repository", issue)
        self.assertIsNone(adjudicate.refuse_work_dir_inside(self.work, self.repo))

    def test_a_second_run_with_another_homes_base_is_refused(self):
        # Round 7, REG7-2/ISO-R7-4: the work dir's own lock, whatever NAS_CODEX_HOME_DIR says.
        self.inputs()
        with adjudicate.codex_lane.exclusive_run_lock(adjudicate.codex_lane.work_run_lock(self.work)):
            with mock.patch.dict(os.environ, {adjudicate.codex_lane.CODEX_HOME_BASE_ENV: str(self.work.parent / "b2")}):
                code, err = self.run_judges([(self.JUDGE, "gpt-6-astra", [0], None, None)])
        self.assertEqual(code, 2)
        self.assertIn("another run holds", err)

    def test_a_stop_writes_no_record_and_starts_no_refute_stage(self):
        # Round 7, ISO-R7-3: after a stop signal no refute stage starts and the judged call leaves no record.
        self.inputs()
        self.addCleanup(adjudicate.codex_lane.STOP.clear)

        def judge_then_stop(*_args, **_kwargs):
            adjudicate.codex_lane.STOP.set()
            return self.JUDGE, "gpt-6-astra", [0], None, None

        call = mock.Mock(side_effect=judge_then_stop)
        with mock.patch.object(adjudicate, "run_codex_call", call), \
                mock.patch.object(adjudicate.shutil, "which", return_value="/usr/bin/codex"):
            quiet(adjudicate.main, ["codex", "--work-dir", str(self.work), "--repo", str(self.repo),
                                    "--model", "gpt-6-astra", "--jobs", "1"])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(sorted((self.work / "adjudication-judgments" / "codex").glob("*.AB.json")), [])

    def test_an_edited_record_over_flagged_events_does_not_count(self):
        # BIND-R4-6: audit_clean is re-checked against the recorded events, so editing a record cannot count a
        # judgment whose calls read outside their input.
        self.inputs()
        for lane in ("claude", "codex"):
            for order in adjudicate.ORDERS:
                self.judgment(lane, order, "claude")
        events = self.work / "adjudication-judgments" / "codex" / "events" / f"{NAME}.AB.judge.jsonl"
        events.write_text(read_command_event(f"cat {adjudicate.index_path(self.work)}"), encoding="utf-8")
        record_path = self.work / "adjudication-judgments" / "codex" / f"{NAME}.AB.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["events"]["judge"]["sha256"] = adjudicate.sha256_file(events)
        adjudicate.write_json(record_path, record)
        entry = next(e for e in adjudicate.load_index(self.work)["layers"] if e["layer"] == NAME)
        self.assertEqual(adjudicate.usable_judgment(record, "openai", "AB", self.sha, entry=entry),
                         adjudicate.AUDIT_FLAGGED)
        record["events"]["judge"]["sha256"] = "0" * 64
        self.assertIn("missing or changed", adjudicate.usable_judgment(record, "openai", "AB", self.sha, entry=entry))

    def test_inputs_bind_each_lane_root_to_the_returns_tree(self):
        # BIND-R4-9: another checkout named as a lane root would have its paths relativized as the export's.
        other = self.base / "hosts" / "blind" / "other"
        other.mkdir(parents=True)
        (other / "x.json").write_text("{}", encoding="utf-8")
        code, _err = self.inputs(self.repo, other)
        self.assertEqual(code, 1)
        skipped = json.loads(adjudicate.index_path(self.work).read_text(encoding="utf-8"))["skipped"]
        self.assertIn("does not hold", skipped[0]["reason"])
        code, err = quiet(adjudicate.main, ["inputs", "--work-dir", str(self.work), "--lane-repo-root",
                                            str(other / ".." / "repo")])
        self.assertEqual(code, 2)
        self.assertIn("contains ..", err)

    def test_the_run_provenance_names_codex_lane(self):
        # BIND-R4-2: codex_lane.py builds, isolates and audits the Codex judges.
        provenance = adjudicate.adjudication_provenance()
        self.assertEqual(provenance["codex_lane_py_sha256"],
                         hashlib.sha256((TOOL_DIR / "codex_lane.py").read_bytes()).hexdigest())


class ScrubRound4Tests(unittest.TestCase):
    """Independent review of #145, round 4, R4-REG-5: a sentence end inside a spaced host path, and a name glued by
    a comma, left words of the path."""

    def test_no_path_word_survives(self):
        cases = {
            "read /srv/Acme Inc. Secret Project/plan.md for the numbers": "read <outside-path>",
            "/Users/example/Docs/Q3 plan: acquisition target Foo/notes.txt then decide": "<outside-path>",
            "C:\\Users\\Example User\\Board deck v2. Layoffs list\\a.pptx is cited": "<outside-path>",
            "see /home/example/private,key.json now": "see <outside-path>",
            "cite /home/example/a.json, then b": "cite <outside-path>, then b",
            "read /srv/x/plan.md now. The next sentence stays.": "read <outside-path>. The next sentence stays.",
        }
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(adjudicate.redact_leak_text(text), expected)
                self.assertEqual(adjudicate.unscrubbed_paths([adjudicate.redact_leak_text(text)]), [])


class ScrubRound5Tests(unittest.TestCase):
    """Round 5: a glued segment naming a file under a lane root is repository evidence and stays, and stops the
    clause absorption (R5-REG-5); a host path after a URL-closing "|" is scrubbed (R5-REG-6)."""

    def test_glued_repository_evidence_stays_and_host_paths_go(self):
        root = Path(tempfile.mkdtemp()) / "srv" / "state" / "blind" / "export"
        self.addCleanup(shutil.rmtree, root.parents[3])
        for relative in ("docs/b.md", "docs/c.md", "evidence/receipts/r.json"):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text("x", encoding="utf-8")
        cases = {
            "see /home/example/x.json,docs/b.md and evidence/c.json": "see <outside-path>,docs/b.md and evidence/c.json",
            "read /home/example/a.json;evidence/receipts/r.json for the numbers":
                "read <outside-path>;evidence/receipts/r.json for the numbers",
            '{"from":"/home/example/a.json","to":"docs/b.md"}': '{"from":"<outside-path>","to":"docs/b.md"}',
            f"{root}/docs/a.md,/home/example/b.json,docs/c.md": "docs/a.md,<outside-path>,docs/c.md",
            "source=https://example.com|/home/example/private/notes.md": "source=https://example.com|<outside-path>",
            "/home/example,private/result.json": "<outside-path>",
            # Codex review at a516c477: a final segment glued on without a later separator.
            "/home/example,private.json": "<outside-path>",
            # Round 6, REG6-5: the whole glued chain is walked, past a kept repository file.
            "see /home/example/x.json,docs/b.md,private.json now": "see <outside-path>,docs/b.md now",
            "C:\\Users\\example,private.json": "<outside-path>",
        }
        # Round 6, REG6-1: an over-long glued segment is not a repository file, and nothing raises.
        long_segment = "/home/example/a.json," + "x" * 300 + ".json"
        self.assertEqual(adjudicate.scrub_text(long_segment, "/nonexistent", (str(root),)), "<outside-path>")
        for text, expected in cases.items():
            with self.subTest(text):
                out = adjudicate.scrub_text(text, "/nonexistent", (str(root),))
                self.assertEqual(out, expected)
                self.assertEqual(adjudicate.unscrubbed_paths([out]), [])


if __name__ == "__main__":
    unittest.main()
