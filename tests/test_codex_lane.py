"""Synthetic-fixture tests for tools/sota-convergence/codex_lane.py.

No real ``codex`` binary is ever invoked. A fake ``codex`` script fixture
(``tests/fixtures/codex-lane/bin/codex``) is placed first on PATH for every
test in this module; it is env-var driven (see its own docstring) so each
test configures the exact behavior it needs -- argv recording, a canned
event stream, a canned ``-o`` return, chosen failing attempts, and an
optional sleep to exercise the timeout path. Modules are loaded by file path
(tools/sota-convergence is not a dotted-import package name), matching the
pattern already used by test_layer_verdicts.py.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "codex-lane"
FIXTURE_PROMPT = FIXTURE_DIR / "lane-prompt.md"
FIXTURE_SCHEMA = FIXTURE_DIR / "lane-return.schema.json"
FIXTURE_BIN = FIXTURE_DIR / "bin"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_lane = load_module("codex_lane", "codex_lane.py")


def canned_return(**overrides):
    row = {
        "schema_version": 1, "lane": "codex", "catalog": "foundation", "layer_id": "native-clients",
        "winner_keys": ["c1"],
        "why_selected": "c1 is the only adopted candidate with native execution evidence recorded in receipt.json.",
        "winner_evidence_class": "native_proven", "winner_evidence_refs": ["evidence/receipt.json"],
        "alternatives": [{
            "key": "c2", "name": "Other", "repository": "https://github.com/example/other",
            "disposition": "conditional",
            "why_not_default": "No native execution evidence was found for this candidate in the packet.",
            "evidence_class": "source_review", "evidence_refs": [],
        }],
        "challenger_preferred": None,
        "overturn_when": "python3 tests/fixtures/codex-lane/rerun.py improves the measured result",
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "open_gaps": [], "sources_read": ["evidence/receipt.json"], "limits": [],
    }
    row.update(overrides)
    return row


CANNED_EVENTS = "\n".join([
    json.dumps({"type": "thread.started", "thread_id": "fixture-thread"}),
    json.dumps({"type": "turn.started"}),
    json.dumps({"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "done"}}),
    json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 1234, "cached_input_tokens": 200, "cache_write_input_tokens": 0,
        "output_tokens": 56, "reasoning_output_tokens": 12,
    }, "model": "gpt-6-astra"}),
]) + "\n"


class CodexLaneFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.repo = base / "repo"
        self.work_dir = base / "work"
        self.repo.mkdir()
        self.work_dir.mkdir()
        (self.work_dir / "packets").mkdir()

        self._old_environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._old_environ)))
        os.environ["PATH"] = str(FIXTURE_BIN) + os.pathsep + os.environ.get("PATH", "")
        for key in list(os.environ):
            if key.startswith("CODEX_FAKE_"):
                os.environ.pop(key)

        self.argv_log = base / "argv.jsonl"
        self.counter_file = base / "counter.txt"
        self.events_file = base / "events.jsonl"
        self.return_file = base / "return.json"
        os.environ["CODEX_FAKE_ARGV_LOG"] = str(self.argv_log)
        os.environ["CODEX_FAKE_COUNTER_FILE"] = str(self.counter_file)
        os.environ["CODEX_FAKE_EVENTS_FILE"] = str(self.events_file)
        os.environ["CODEX_FAKE_RETURN_FILE"] = str(self.return_file)
        self.events_file.write_text(CANNED_EVENTS, encoding="utf-8")
        self.return_file.write_text(json.dumps(canned_return()), encoding="utf-8")

    def write_packet(self, catalog: str, layer_id: str, content=None) -> Path:
        path = self.work_dir / "packets" / f"{catalog}__{layer_id}.json"
        path.write_text(json.dumps(content or {"schema_version": 1, "catalog": catalog, "layer_id": layer_id}),
                         encoding="utf-8")
        return path

    def run_lane(self, extra_args=None):
        args = [
            "--work-dir", str(self.work_dir), "--repo", str(self.repo),
            "--prompt", str(FIXTURE_PROMPT), "--schema", str(FIXTURE_SCHEMA),
        ]
        args.extend(extra_args or [])
        return codex_lane.main(args)

    def argv_calls(self):
        if not self.argv_log.exists():
            return []
        return [json.loads(line) for line in self.argv_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def usage_rows(self):
        usage_path = self.work_dir / "codex" / "usage.jsonl"
        if not usage_path.exists():
            return []
        return [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def out_path(self, catalog: str, layer_id: str) -> Path:
        return self.work_dir / "codex" / f"{catalog}__{layer_id}.json"


class MissingCliTests(CodexLaneFixture):
    def test_a_missing_codex_cli_exits_2_with_a_message(self):
        self.write_packet("foundation", "native-clients")
        empty = self.work_dir / "empty-bin"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.run_lane()
        self.assertEqual(code, 2)
        self.assertIn("codex CLI is not on PATH", err.getvalue())
        self.assertFalse(self.argv_log.exists())


class CodexLaneTests(CodexLaneFixture):
    def test_dry_run_prints_command_and_writes_nothing(self):
        self.write_packet("foundation", "native-clients")
        import contextlib
        import io
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exit_code = self.run_lane(["--dry-run"])
        self.assertEqual(exit_code, 0)
        printed = captured.getvalue().strip()
        self.assertIn("codex exec", printed)
        self.assertIn("--sandbox", printed)
        self.assertIn("read-only", printed)
        self.assertIn("--skip-git-repo-check", printed)
        self.assertIn("--ephemeral", printed)
        self.assertIn("--output-schema", printed)
        self.assertIn("model_reasoning_effort=high", printed)
        # Nothing written: not even the codex/ directory.
        self.assertFalse((self.work_dir / "codex").exists())
        self.assertEqual(self.argv_calls(), [])

    def test_first_attempt_fails_then_retry_succeeds(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        os.environ["CODEX_FAKE_EXIT_CODE"] = "7"
        # The canned return omits packet_sha256 and model so both must be filled.
        self.return_file.write_text(json.dumps(canned_return(packet_sha256=None, model=None)), encoding="utf-8")

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry (two invocations)")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["attempt"], 1)
        self.assertEqual(rows[0]["exit_code"], 7)
        self.assertEqual(rows[1]["attempt"], 2)
        self.assertEqual(rows[1]["exit_code"], 0)
        # The second (successful) attempt's usage row carries the canned
        # token fields found in the event stream.
        self.assertEqual(rows[1]["input_tokens"], 1234)
        self.assertEqual(rows[1]["model"], "gpt-6-astra")

        out_path = self.out_path("foundation", "native-clients")
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")
        self.assertEqual(data["catalog"], "foundation")
        self.assertEqual(data["layer_id"], "native-clients")
        packet_path = self.work_dir / "packets" / "foundation__native-clients.json"
        import hashlib
        expected_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        self.assertEqual(data["packet_sha256"], expected_sha)
        self.assertEqual(data["model"], {"name": "gpt-6-astra", "effort": "high", "family": "openai"})

    def test_lane_forced_and_self_declared_model_replaced_by_the_event_stream_model(self):
        self.write_packet("foundation", "native-clients")
        # lane deliberately wrong and a self-declared model in the response text: the runner forces
        # lane and records the model it observed in the event stream, never the response's claim
        # (re-review 2026-09-23: a non-OpenAI provider answering "gpt-5" would otherwise be sealed).
        self.return_file.write_text(
            json.dumps(canned_return(lane="claude", model={"name": "gpt-5", "effort": "medium"})),
            encoding="utf-8")
        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")
        self.assertEqual(data["model"], {"name": "gpt-6-astra", "effort": "high", "family": "openai"})

    def test_configured_model_is_passed_to_codex_and_recorded(self):
        self.write_packet("foundation", "native-clients")
        self.return_file.write_text(json.dumps(canned_return(model={"name": "gpt-5", "effort": "low"})),
                                    encoding="utf-8")
        self.assertEqual(self.run_lane(["--model", "gpt-6-configured"]), 0)
        argv = self.argv_calls()[0]
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-configured")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"], {"name": "gpt-6-configured", "effort": "high", "family": "openai"})

    def test_without_an_observed_model_the_name_is_unknown_not_the_response_text(self):
        self.write_packet("foundation", "native-clients")
        self.events_file.write_text("\n".join(line for line in CANNED_EVENTS.splitlines()
                                              if '"model"' not in line) + "\n", encoding="utf-8")
        self.return_file.write_text(json.dumps(canned_return(model={"name": "gpt-5", "effort": "high"})),
                                    encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"]["name"], "unknown")
        self.assertEqual(self.argv_calls()[0].count("-m"), 0, "no -m without --model")

    def test_written_return_records_its_own_provenance_and_family(self):
        import hashlib
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"], {
            "codex_lane_py_sha256": hashlib.sha256((TOOL_DIR / "codex_lane.py").read_bytes()).hexdigest(),
            "prompt_sha256": hashlib.sha256(FIXTURE_PROMPT.read_bytes()).hexdigest(),
        })
        self.assertEqual(data["model"]["family"], "openai")
        self.assertEqual(data["model"]["name"], "gpt-6-astra")

    def test_a_self_declared_provenance_or_family_is_replaced_by_the_runner(self):
        self.write_packet("foundation", "native-clients")
        self.return_file.write_text(json.dumps(canned_return(
            model={"name": "gpt-6-astra", "effort": "high", "family": "anthropic"},
            provenance={"codex_lane_py_sha256": "0" * 64, "prompt_sha256": "0" * 64})), encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"]["family"], "openai")
        self.assertNotEqual(data["provenance"]["prompt_sha256"], "0" * 64)

    def test_resumable_skip_of_an_existing_valid_file(self):
        packet_path = self.write_packet("foundation", "native-clients")
        import hashlib
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        existing = canned_return(packet_sha256=packet_sha256,
                                 provenance=codex_lane.lane_provenance(FIXTURE_PROMPT),
                                 model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(existing, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        before = out_path.read_text(encoding="utf-8")

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.argv_calls(), [], "the fake codex must never be invoked for an already-valid layer")
        self.assertEqual(out_path.read_text(encoding="utf-8"), before)

    def test_a_return_from_older_lane_code_or_prompt_reruns_instead_of_being_skipped(self):
        """PR #141 review (P1): the skip ignored provenance, so a return from older lane code or an older
        prompt was skipped forever and then rejected by record_verdicts.py."""
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()
        stale = (None, {**current, "codex_lane_py_sha256": "1" * 64}, {**current, "prompt_sha256": "2" * 64})
        for index, provenance in enumerate(stale, start=1):
            existing = canned_return(packet_sha256=packet_sha256,
                                     model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})
            if provenance is not None:
                existing["provenance"] = provenance
            out_path.write_text(json.dumps(existing), encoding="utf-8")
            self.assertEqual(self.run_lane(), 0)
            self.assertEqual(len(self.argv_calls()), index, f"stale provenance {provenance} must rerun")
            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["provenance"], current)
        self.assertTrue(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                             packet_sha256, current))

    def test_a_return_with_an_unknown_or_other_model_reruns_instead_of_being_skipped(self):
        """Round-2 review: a return whose model.name is "unknown", or differs from --model, was skipped."""
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()

        def write(name):
            out_path.write_text(json.dumps(canned_return(
                packet_sha256=packet_sha256, provenance=current,
                model={"name": name, "effort": "high", "family": "openai"})), encoding="utf-8")

        write("unknown")
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), 1, "an unknown model reruns")
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["model"]["name"], "gpt-6-astra")
        write("gpt-6-astra")
        self.assertEqual(self.run_lane(["--model", "gpt-6-codex"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "a return from another model than --model reruns")
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["model"]["name"], "gpt-6-codex")
        self.assertEqual(self.run_lane(["--model", "gpt-6-codex"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "a return from the configured model is skipped")

    def test_timeout_handling_retries_once_then_fails(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SLEEP_SECONDS"] = "2"

        exit_code = self.run_lane(["--timeout", "1"])
        self.assertEqual(exit_code, 1, "both attempts time out, so the layer must be reported failed")

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the first timeout")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue(row["timed_out"])
            self.assertIsNone(row["exit_code"])

        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        # Review of catalog #122, finding 7: the failure and its reason reach record_verdicts.py's
        # run manifest through codex/failures.json instead of a bare "missing".
        failures_path = self.out_path("foundation", "native-clients").parent / "failures.json"
        failures = json.loads(failures_path.read_text(encoding="utf-8"))
        self.assertEqual(failures["failures"], [{"catalog": "foundation", "layer_id": "native-clients",
                                                 "reason": "failed after retry: timed out"}])

    def test_a_failed_rerun_removes_the_stale_return_for_an_older_packet(self):
        # Review of catalog #124 (codex_lane.py:482): a stale return rejected for an older packet
        # hash must not survive a failed rerun, or record_verdicts.py records `rejected`, not `failed`.
        self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        stale = self.out_path("foundation", "native-clients")
        stale.write_text(json.dumps(canned_return(packet_sha256="f" * 64), sort_keys=True, indent=1) + "\n",
                         encoding="utf-8")
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_EXIT_CODE"] = "7"
        self.assertEqual(self.run_lane(), 1)
        self.assertEqual(len(self.argv_calls()), 2, "the stale return must not be skipped as valid")
        self.assertFalse(stale.exists())
        failures = json.loads((codex_dir / "failures.json").read_text(encoding="utf-8"))
        self.assertEqual(failures["failures"], [{"catalog": "foundation", "layer_id": "native-clients",
                                                 "reason": "failed after retry: codex exec exited 7"}])

    def test_timed_out_attempt_keeps_its_partial_event_stream(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SLEEP_SECONDS"] = "3"
        os.environ["CODEX_FAKE_EMIT_BEFORE_SLEEP"] = "1"

        self.assertEqual(self.run_lane(["--timeout", "1"]), 1)
        events_path = self.work_dir / "codex" / "events" / "foundation__native-clients.jsonl"
        self.assertTrue(events_path.exists())
        captured = events_path.read_text(encoding="utf-8")
        first_event = CANNED_EVENTS.strip().splitlines()[0]
        self.assertIn(first_event, captured, "partial output of a timed-out attempt must be kept, not discarded")

    def test_layers_filter_only_runs_the_selected_layer(self):
        self.write_packet("foundation", "layer-a")
        self.write_packet("foundation", "layer-b")
        self.return_file.write_text(json.dumps(canned_return(layer_id="layer-a")), encoding="utf-8")

        exit_code = self.run_lane(["--layers", "layer-a"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(self.out_path("foundation", "layer-a").exists())
        self.assertFalse(self.out_path("foundation", "layer-b").exists())
        self.assertEqual(len(self.argv_calls()), 1)

    def test_stale_out_tmp_is_cleared_before_each_attempt(self):
        # A stale <catalog>__<layer>.out.tmp left behind by a prior killed
        # run (SIGKILL / Ctrl-C / OOM) must never be misread as *this*
        # attempt's own output; codex_lane.py must clear it before launching
        # the attempt, not only after detecting a failure.
        self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir(parents=True)
        tmp_out = codex_dir / "foundation__native-clients.out.tmp"
        stale_payload = canned_return(why_selected=(
            "STALE leftover from a killed prior run; this text must never be read as a real result."
        ))
        tmp_out.write_text(json.dumps(stale_payload), encoding="utf-8")

        # Attempt 1's fake codex exits 0 but never touches -o at all; a
        # correct implementation must not find the stale file still there
        # and treat it as attempt 1's own output.
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(self.argv_calls()), 2,
                          "attempt 1 must be treated as failed (stale file cleared first), forcing a retry")

        out_path = self.out_path("foundation", "native-clients")
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertNotIn("STALE", data["why_selected"], "the stale leftover out.tmp must never be read as a result")
        self.assertFalse(tmp_out.exists())

    def test_missing_output_file_retries_then_succeeds(self):
        # Attempt 1 exits 0 (a "successful" codex run) but never writes the
        # -o file at all; codex_lane.py must treat that as a failed attempt,
        # retry, and succeed on attempt 2's normal canned return.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the missing-output attempt")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["exit_code"], 0)
        self.assertEqual(rows[1]["exit_code"], 0)

        out_path = self.out_path("foundation", "native-clients")
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")

    def test_missing_output_file_both_attempts_fails(self):
        # Both attempts exit 0 but never write -o: the layer must be
        # reported failed, main() must return 1, and nothing must be
        # written for that layer (resumable: a later run retries it).
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1,2"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the first missing-output attempt")

        out_path = self.out_path("foundation", "native-clients")
        self.assertFalse(out_path.exists())
        tmp_out = self.work_dir / "codex" / "foundation__native-clients.out.tmp"
        self.assertFalse(tmp_out.exists(), "no stale out.tmp should be left behind")

    def test_unparseable_output_both_attempts_fails(self):
        # Both attempts exit 0 but write text that fails json.loads
        # (JSONDecodeError) to -o: same failed-layer contract as a missing
        # file.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_BAD_OUTPUT_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_BAD_OUTPUT_TEXT"] = "not json at all {{{"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(self.argv_calls()), 2)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        tmp_out = self.work_dir / "codex" / "foundation__native-clients.out.tmp"
        self.assertFalse(tmp_out.exists(), "the unparseable out.tmp must be cleaned up, not left behind")

    def test_non_dict_output_retries_then_fails(self):
        # Both attempts exit 0 and write *valid* JSON to -o, but it is not a
        # JSON object (a bare list here) -- must be rejected the same as
        # missing/unparseable output, not accepted because json.loads
        # succeeded.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_BAD_OUTPUT_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_BAD_OUTPUT_TEXT"] = json.dumps(["not", "a", "dict"])

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(self.argv_calls()), 2, "expected exactly one retry after a non-dict output attempt")
        self.assertFalse(self.out_path("foundation", "native-clients").exists())

    def test_usage_jsonl_rows_accumulate_across_layers(self):
        self.write_packet("foundation", "layer-a")
        self.write_packet("foundation", "layer-b")
        self.return_file.write_text(json.dumps(canned_return(layer_id="layer-a")), encoding="utf-8")
        # Both layers share the same canned return content object at the
        # filesystem level (the fake codex just copies bytes); layer_id
        # mismatches inside the payload are not validated by codex_lane.py
        # itself (that is record_verdicts.py's job), so this only exercises
        # that a usage row is appended per attempt per layer.
        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["layer"] for row in rows}, {"layer-a", "layer-b"})
        for row in rows:
            self.assertEqual(row["attempt"], 1)
            self.assertEqual(row["exit_code"], 0)



class StrictSchemaTests(CodexLaneFixture):
    def test_strict_copy_drops_keywords_codex_rejects_and_keeps_the_rest(self):
        schema = {"$schema": "x", "type": "object", "additionalProperties": False,
                  "properties": {"keys": {"type": "array", "uniqueItems": True, "minItems": 1,
                                          "items": {"type": "string", "pattern": "^c"}}},
                  "required": ["keys"]}
        strict = codex_lane.strict_output_schema(schema)
        self.assertNotIn("$schema", strict)
        self.assertNotIn("uniqueItems", strict["properties"]["keys"])
        self.assertEqual(strict["properties"]["keys"]["minItems"], 1)
        self.assertEqual(strict["properties"]["keys"]["items"]["pattern"], "^c")
        self.assertFalse(strict["additionalProperties"])

    def test_the_real_lane_schema_has_no_rejected_keyword_after_stripping(self):
        text = json.dumps(codex_lane.strict_output_schema(json.loads(codex_lane.DEFAULT_SCHEMA.read_text())))
        for keyword in codex_lane.STRICT_UNSUPPORTED_KEYWORDS:
            self.assertNotIn('"' + keyword + '"', text)

    def test_the_strict_schema_leaves_runner_owned_fields_to_the_runner(self):
        # provenance and model.family are written by codex_lane.py itself; Codex strict output
        # also requires every listed property to be required, so they are not asked of the model.
        strict = codex_lane.strict_output_schema(json.loads(codex_lane.DEFAULT_SCHEMA.read_text()))
        self.assertNotIn("provenance", strict["properties"])
        self.assertNotIn("family", strict["properties"]["model"]["properties"])
        # The Claude lane's refutation summary (review of catalog #122, finding 5) is never asked of Codex.
        self.assertIn("refutation", json.loads(codex_lane.DEFAULT_SCHEMA.read_text())["properties"])
        self.assertNotIn("refutation", strict["properties"])
        self.assertEqual(set(strict["properties"]), set(strict["required"]))
        self.assertEqual(set(strict["properties"]["model"]["properties"]), set(strict["properties"]["model"]["required"]))

    def test_codex_exec_receives_the_strict_schema(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        schema_arg = argv[argv.index("--output-schema") + 1]
        self.assertTrue(schema_arg.endswith("lane-return.codex-strict.schema.json"))
        self.assertTrue(Path(schema_arg).exists())

    def test_property_names_that_match_dropped_keywords_are_kept(self):
        schema = {"type": "object", "additionalProperties": False, "required": ["title", "description"],
                  "properties": {"title": {"type": "string", "description": "dropped"},
                                 "description": {"type": "string", "title": "dropped"}},
                  "$defs": {"$id": {"type": "string", "uniqueItems": True}}}
        strict = codex_lane.strict_output_schema(schema)
        self.assertEqual(strict["properties"], {"title": {"type": "string"}, "description": {"type": "string"}})
        self.assertEqual(strict["required"], ["title", "description"])
        self.assertEqual(strict["$defs"], {"$id": {"type": "string"}})

    def test_property_dependencies_keep_their_names(self):
        schema = {"type": "object", "dependentRequired": {"title": ["description"]},
                  "dependencies": {"title": ["$id"], "description": {"required": ["title"], "title": "dropped"}}}
        strict = codex_lane.strict_output_schema(schema)
        self.assertEqual(strict["dependentRequired"], {"title": ["description"]})
        self.assertEqual(strict["dependencies"], {"title": ["$id"], "description": {"required": ["title"]}})

    def test_instance_data_keywords_are_kept_verbatim(self):
        schema = {"type": "object", "const": {"title": "x"}, "default": {"description": "y"},
                  "enum": [{"$id": "z"}], "examples": [{"uniqueItems": True}]}
        strict = codex_lane.strict_output_schema(schema)
        for keyword in ("const", "default", "enum", "examples"):
            self.assertEqual(strict[keyword], schema[keyword])

    def test_dry_run_writes_no_strict_schema(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertFalse(any(self.work_dir.rglob("lane-return.codex-strict.schema.json")))


class PromptFillTests(CodexLaneFixture):
    """The prompt that reaches ``codex exec`` is lane-prompt.md with every
    placeholder filled: PACKET_PATH absolute, REPO_ROOT, LANE=codex."""

    def test_prompt_placeholders_are_filled_from_the_template(self):
        packet = self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        calls = self.argv_calls()
        self.assertEqual(len(calls), 1)
        prompt = calls[0][-1]
        self.assertIn(str(packet.resolve()), prompt, "PACKET_PATH must be the absolute packet path")
        self.assertIn(str(self.repo), prompt, "REPO_ROOT must be the --repo root")
        self.assertIn("You are the codex lane", prompt, "LANE must be filled with codex")
        for marker in ("{PACKET_PATH}", "{REPO_ROOT}", "{LANE}"):
            self.assertNotIn(marker, prompt)


class BlindIsolationTests(CodexLaneFixture):
    """2026-09-23 re-record: every lane child ignores the user config and runs without hooks, in a real run
    and in the dry run's printed commands alike."""

    def test_every_attempt_ignores_the_user_config_and_hooks(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        overrides = [argv[index + 1] for index, arg in enumerate(argv) if arg == "-c"]
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("features.hooks=false", overrides)
        self.assertIn("features.plugin_hooks=false", overrides)
        self.assertLess(argv.index("--ignore-user-config"), len(argv) - 1, "the flags precede the prompt")

    def test_the_dry_run_prints_the_same_flags(self):
        self.write_packet("foundation", "native-clients")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertIn("--ignore-user-config -c features.hooks=false -c features.plugin_hooks=false", out.getvalue())

    def test_native_web_search_is_off(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        self.assertIn('web_search="disabled"', [argv[index + 1] for index, arg in enumerate(argv) if arg == "-c"])

    def test_a_repository_with_git_history_is_refused_unless_allowed(self):
        self.write_packet("foundation", "native-clients")
        (self.repo / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("--export copy", err.getvalue())
        self.assertFalse(self.argv_log.exists())
        self.assertEqual(self.run_lane(["--allow-git-history"]), 0)

    def test_a_repository_inside_another_repository_is_refused(self):
        self.write_packet("foundation", "native-clients")
        (self.repo.parent / ".git").mkdir()
        nested = self.repo / "export"
        nested.mkdir()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(codex_lane.main(["--work-dir", str(self.work_dir), "--repo", str(nested),
                                              "--prompt", str(FIXTURE_PROMPT), "--schema", str(FIXTURE_SCHEMA)]), 2)
        self.assertFalse(self.argv_log.exists())

    def test_the_blind_audit_reports_what_a_child_reached_outside_the_boundary(self):
        self.write_packet("foundation", "native-clients")
        def done(item):
            return json.dumps({"type": "item.completed", "item": item})
        self.events_file.write_text("\n".join([
            done({"type": "command_execution", "command": f"/bin/bash -lc 'sed -n 1,40p {self.repo}/catalogs/x.json'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg -n verdict /home/example/code/agent-lab/docs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'git log -p -- catalogs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg -n verdict ~/code/agent-lab/docs/tasks'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'cat $HOME/code/agent-lab/docs/x.md'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg verdict ../../agent-lab/docs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'sqlite3 db.sqlite .dump'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'cd /; rg -l verdict home'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'sed -n 1,20p catalogs/landscape/foundation.json'"}),
            done({"type": "web_search", "query": "x"}),
            done({"type": "mcp_tool_call", "server": "s", "tool": "t"}),
        ]) + "\n" + CANNED_EVENTS, encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(), 0)
        audit = json.loads((self.work_dir / "codex" / "blind-audit.json").read_text(encoding="utf-8"))
        entry = audit["layers"]["foundation__native-clients"]
        self.assertEqual((entry["web_search"], entry["mcp_tool_calls"], entry["commands"]), (1, 1, 9))
        flagged = {item["command"]: item["reasons"] for item in entry["flagged_commands"]}
        self.assertEqual(len(flagged), 7, flagged)
        self.assertFalse(any("catalogs/landscape/foundation.json" in command for command in flagged), flagged)
        joined = " ".join(reason for reasons in flagged.values() for reason in reasons)
        for expected in ("home-relative path: ~/code/agent-lab/docs/tasks", "home-relative path: $HOME/code/agent-lab/docs/x.md",
                         "path climbs out of the working directory: ../../agent-lab/docs", "runs sqlite3",
                         "names the filesystem root /"):
            self.assertIn(expected, joined)
        self.assertTrue(any("path outside the repository and packets: /home/example/code/agent-lab/docs" in reason
                            for reasons in flagged.values() for reason in reasons))
        self.assertTrue(any("runs git" in reasons for reasons in flagged.values()))
        self.assertIn("blind audit flags 1 layer(s)", err.getvalue())

    def audit_paths(self, *commands):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text("".join(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n" for command in commands), encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo), str(self.work_dir / "packets")])
        return {item["command"]: [reason.split(": ", 1)[1] for reason in item["reasons"]
                                  if reason.startswith("path outside")]
                for item in report["flagged_commands"]}

    def test_only_a_segment_executable_under_a_system_prefix_is_exempt(self):
        """PR #141 review (P2): every /usr/ or /bin/ path was exempt, which hid data reads such as
        /bin/cat /usr/local/share/prior-verdict.json."""
        repo = self.repo
        flagged = self.audit_paths(
            "/bin/cat /usr/local/share/prior-verdict.json",
            "/bin/bash -lc '/usr/bin/sed -n 1,20p /usr/share/doc/verdicts.txt'",
            f"/bin/bash -lc 'cat {repo}/a.json | /usr/bin/head -5 && /usr/bin/python3 {repo}/x.py || /bin/true; /usr/bin/wc -l {repo}/b'",
            f"/bin/bash -lc 'rg -n x {repo} 2>/dev/null'",
            "/bin/bash -lc 'cat /bin/prior-verdicts'",
            "/bin/bash -lc \"ls /usr/local/lib/verdicts\"",
            "/bin/sh -c '/home/example/bin/tool --flag'",
            "/usr/bin/env python3 -c 'print(1)'",
        )
        self.assertEqual(flagged, {
            "/bin/cat /usr/local/share/prior-verdict.json": ["/usr/local/share/prior-verdict.json"],
            "/bin/bash -lc '/usr/bin/sed -n 1,20p /usr/share/doc/verdicts.txt'": ["/usr/share/doc/verdicts.txt"],
            "/bin/bash -lc 'cat /bin/prior-verdicts'": ["/bin/prior-verdicts"],
            "/bin/bash -lc \"ls /usr/local/lib/verdicts\"": ["/usr/local/lib/verdicts"],
            "/bin/sh -c '/home/example/bin/tool --flag'": ["/home/example/bin/tool"],
        })

    def audit_reasons(self, command):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo), str(self.work_dir / "packets")])
        return [reason for item in report["flagged_commands"] for reason in item["reasons"]]

    def test_round_two_audit_gaps_are_flagged(self):
        """Round-2 review: cd to an unnamed directory, non-HOME variable paths and a /usr/ executable outside
        the executable directories were not flagged."""
        expected = {
            "/bin/bash -lc 'cd'": "cd leaves for an unnamed directory: cd (home)",
            "cd": "cd leaves for an unnamed directory: cd (home)",
            "/bin/bash -lc 'cd -'": "cd leaves for an unnamed directory: cd -",
            "/bin/bash -lc 'cd ~ && rg verdict'": "cd leaves for an unnamed directory: cd ~",
            "/bin/bash -lc 'cd $OLDPWD'": "cd leaves for an unnamed directory: cd $OLDPWD",
            "/bin/bash -lc 'cd \"$OLDPWD\"; ls'": "cd leaves for an unnamed directory: cd $OLDPWD",
            "/bin/bash -lc 'cat $CODEX_HOME/AGENTS.md'": "variable path: $CODEX_HOME/AGENTS.md",
            "/bin/bash -lc 'ls ${XDG_DATA_HOME}/x'": "variable path: ${XDG_DATA_HOME}/x",
            "/bin/bash -lc '/usr/local/share/verdicts/show'":
                "path outside the repository and packets: /usr/local/share/verdicts/show",
            "/bin/bash -lc '/usr/lib/verdicts/show --all'":
                "path outside the repository and packets: /usr/lib/verdicts/show",
        }
        for command, reason in expected.items():
            self.assertIn(reason, self.audit_reasons(command), command)
        for command in ("/bin/bash -lc 'cd catalogs && ls'", "/usr/local/bin/rg -n x catalogs",
                        "/usr/sbin/tool x", "/sbin/tool x", "/bin/bash -lc 'for f in a b; do cat $f; done'"):
            self.assertEqual(self.audit_reasons(command), [], command)



class DocumentedCommandTests(unittest.TestCase):
    """PR #141 review (P2): the README's codex exec block omitted -c web_search="disabled"."""

    def test_the_readme_command_block_carries_every_isolation_argument(self):
        readme = (TOOL_DIR / "README.md").read_text(encoding="utf-8")
        blocks = [block for block in re.findall(r"```sh\n(.*?)```", readme, re.S) if block.startswith("codex exec")]
        self.assertEqual(len(blocks), 1, "exactly one documented codex exec command block")
        argv = shlex.split(blocks[0].replace("\\\n", " "))
        isolation = list(codex_lane.ISOLATION_ARGS)
        self.assertTrue(any(argv[index:index + len(isolation)] == isolation for index in range(len(argv))),
                        f"{argv} must contain {isolation} in order")
        docstring = shlex.split(codex_lane.__doc__.split("then run", 1)[1].split("capturing", 1)[0]
                                .replace("\\\n", " "))
        self.assertTrue(any(docstring[index:index + len(isolation)] == isolation for index in range(len(docstring))),
                        f"the module docstring {docstring} must contain {isolation} in order")


class EffortResumeTests(CodexLaneFixture):
    """Codex review of #145: a changed --effort reruns a layer instead of resuming it."""

    def test_a_return_made_at_another_effort_is_not_resumed(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "high"]), 0)
        first = len(self.argv_calls())
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "high"]), 0)
        self.assertEqual(len(self.argv_calls()), first)
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "medium"]), 0)
        self.assertGreater(len(self.argv_calls()), first)


if __name__ == "__main__":
    unittest.main()
