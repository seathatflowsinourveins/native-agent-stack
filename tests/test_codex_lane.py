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
import importlib.util
import json
import os
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

    def test_lane_forced_and_existing_model_not_overwritten(self):
        self.write_packet("foundation", "native-clients")
        # lane deliberately wrong, model already fully set by the "model" --
        # codex_lane must force lane but must NOT clobber an already-usable model.
        self.return_file.write_text(
            json.dumps(canned_return(lane="claude", model={"name": "already-set", "effort": "medium"})),
            encoding="utf-8")
        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")
        # name and effort are kept; the runner adds the family it actually ran (codex exec is OpenAI's CLI).
        self.assertEqual(data["model"], {"name": "already-set", "effort": "medium", "family": "openai"})

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
        existing = canned_return(packet_sha256=packet_sha256)
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(existing, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        before = out_path.read_text(encoding="utf-8")

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.argv_calls(), [], "the fake codex must never be invoked for an already-valid layer")
        self.assertEqual(out_path.read_text(encoding="utf-8"), before)

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


if __name__ == "__main__":
    unittest.main()
