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
import time
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
# The suite does not depend on the PATH this host's login shell ends up with (independent review of #206, R2-3): a new
# PC with npm globals in /usr/local/bin would otherwise refuse every blind fixture run. The real probe is tested below.
REAL_LOGIN_SHELL_PATH = codex_lane.login_shell_path
_SHELL_PATH = mock.patch.object(codex_lane, "login_shell_path", return_value=codex_lane.BLIND_CHILD_PATH)


def setUpModule():
    _SHELL_PATH.start()


def tearDownModule():
    _SHELL_PATH.stop()


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
        # A blind export sits at least four directories deep (codex_lane.root_issue, independent review of #145).
        self.repo = base / "hosts" / "blind" / "repo"
        self.work_dir = base / "work"
        self.repo.mkdir(parents=True)
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
        # Never the developer's credential or state (independent review of #145, R4-REG-7): a fixture native
        # Codex home with a dummy auth.json, and run-scoped homes under the fixture.
        self.native_codex = base / "native-codex"
        self.native_codex.mkdir()
        (self.native_codex / "auth.json").write_text("{}", encoding="utf-8")
        os.environ["CODEX_HOME"] = str(self.native_codex)
        os.environ[codex_lane.CODEX_HOME_BASE_ENV] = str(base / "codex-homes")
        self.addCleanup(setattr, codex_lane, "CHILD_CODEX_HOME", None)
        # A stop signal in one test never leaks into the next (round 7), nor a held in-use lock.
        codex_lane.STOP.clear()
        self.addCleanup(codex_lane.STOP.clear)
        self.addCleanup(lambda: codex_lane.IN_USE_HANDLE and codex_lane.release_codex_home(None))
        # The fake codex reads its CODEX_FAKE_* settings; production children get only the allowlist (ISO-R5-2).
        prefixes = mock.patch.object(codex_lane, "CHILD_ENV_EXTRA_PREFIXES", ("CODEX_FAKE_",))
        prefixes.start()
        self.addCleanup(prefixes.stop)

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
            "repo_tree_sha256": codex_lane.tree_sha256(self.repo),
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
                                 provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
                                 model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(existing, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        # A blind return is resumed only with its clean retained events (round 7, REG7-1).
        (codex_dir / "events").mkdir()
        (codex_dir / "events" / "foundation__native-clients.jsonl").write_text(CANNED_EVENTS, encoding="utf-8")
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
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
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
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
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

    def test_a_layers_rerun_keeps_the_failures_of_unselected_layers(self):
        # Codex review of #145 at a4dfd99e: a --layers rerun replaced failures.json with its own subset.
        self.write_packet("foundation", "native-clients")
        self.write_packet("foundation", "workers")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        (codex_dir / "failures.json").write_text(json.dumps({"lane": "codex", "failures": [
            {"catalog": "foundation", "layer_id": "workers", "reason": "failed after retry: timed out"},
            {"catalog": "foundation", "layer_id": "native-clients", "reason": "failed after retry: timed out"}]}),
            encoding="utf-8")
        self.assertEqual(self.run_lane(["--layers", "native-clients"]), 0)
        failures = json.loads((codex_dir / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual(failures, [{"catalog": "foundation", "layer_id": "workers",
                                     "reason": "failed after retry: timed out"}])

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
            # A flagged blind layer is void (Codex review of #145 at a516c477): exit 1, return set aside.
            self.assertEqual(self.run_lane(), 1)
        self.assertFalse((self.work_dir / "codex" / "foundation__native-clients.json").exists())
        self.assertTrue((self.work_dir / "codex" / "foundation__native-clients.json.audit-flagged").exists())
        failures = json.loads((self.work_dir / "codex" / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertIn("blind audit flagged", failures[0]["reason"])
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



class BlindPathAndPrecisionTests(CodexLaneFixture):
    """2026-09-24 re-record: 15 of 32 blind layers were voided with no read outside the export. Retrieval-CLI names were
    search terms or Python list items, a quoted '/' joined path parts, and Path.cwd()/ref and 'https://' read as
    absolute paths. A blind child's PATH now resolves no retrieval CLI (enforced, and refused otherwise), so the audit
    stops looking for their names; the root and path rules skip those Python forms."""

    def reasons(self, command, tools=codex_lane.AUDIT_TOOLS):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo), str(self.work_dir / "packets")], tools)
        return [reason for item in report["flagged_commands"] for reason in item["reasons"]]

    def test_the_voided_re_record_commands_are_clean(self):
        for command in (
                "/bin/bash -lc \"rg -n -i 'qmd|original|body| get |context.hub' evidence/receipts\"",
                "/bin/bash -lc \"rg --files fixtures | rg -i 'rag|socraticode|qdrant'\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfor t in ['serena','ast-grep','mcporter','ai-memory']: print(t)\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\ndef walk(v,p=''):\n for k,x in v.items(): walk(x,p+'/'+k)\n "
                "for i,x in enumerate(v): walk(x, p + '/' + str(i))\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfrom pathlib import Path\nfor ref in refs: print(Path.cwd()/ref)\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfor ref in refs:\n if not ref.startswith('https://'): print(ref)\nPY\"",
                "/bin/bash -lc \"rg -n 'https://github.com/org/repo' catalogs\""):
            with self.subTest(command=command):
                self.assertEqual(self.reasons(command), [])

    def test_real_reaches_still_flag(self):
        expected = {
            "/bin/bash -lc 'ls /'": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"import os; print(os.listdir('/'))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 - <<'PY'\nimport os\nprint(os.listdir('/'))\nPY\"": "names the filesystem root /",
            "/bin/bash -lc 'git log -p'": "runs git",
            "/bin/bash -lc 'curl -s https://example.invalid/x'": "runs curl",
            "/bin/bash -lc 'cat /home/example/.codex/AGENTS.md'":
                "path outside the repository and packets: /home/example/.codex/AGENTS.md",
            "/bin/bash -lc \"python3 -c \\\"print(open('/home/example/notes.md').read())\\\"\"":
                "path outside the repository and packets: /home/example/notes.md",
            "/bin/bash -lc 'cat https:/etc/passwd'": "path outside the repository and packets: /etc/passwd",
            "/bin/bash -lc 'cat x:/etc/passwd'": "path outside the repository and packets: /etc/passwd",
            "/bin/bash -lc '/home/example/.local/share/codex-ecosystem/bin/qmd search verdict'":
                "path outside the repository and packets: /home/example/.local/share/codex-ecosystem/bin/qmd",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))

    def test_a_non_blind_run_still_looks_for_retrieval_cli_names(self):
        extended = codex_lane.AUDIT_TOOLS + codex_lane.BLIND_UNRESOLVABLE
        self.assertIn("runs qmd", self.reasons("/bin/bash -lc 'qmd search verdict'", extended))
        self.assertIn("runs codex", self.reasons("/bin/bash -lc 'codex exec --search x'", extended))
        self.assertEqual(self.reasons("/bin/bash -lc 'qmd search verdict'"), [])

    def test_a_blind_child_gets_the_system_path_and_the_callers_codex(self):
        env = codex_lane.child_env(self.work_dir / "home-probe")
        self.assertEqual(env["PATH"], codex_lane.BLIND_CHILD_PATH)
        self.assertEqual(codex_lane.child_executable("codex"), shutil.which("codex"))
        self.assertEqual(codex_lane.child_executable("/opt/x/codex"), "/opt/x/codex")

    def test_a_path_that_resolves_a_retrieval_cli_is_refused(self):
        bin_dir = self.work_dir / "sysbin"
        bin_dir.mkdir()
        self.assertIsNone(codex_lane.blind_path_issue(str(bin_dir)))
        (bin_dir / "qmd").write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertIsNone(codex_lane.blind_path_issue(str(bin_dir)), "a file that is not executable resolves nothing")
        (bin_dir / "qmd").chmod(0o755)
        (bin_dir / "codex").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
        issue = codex_lane.blind_path_issue(str(bin_dir))
        self.assertIn(f"qmd ({bin_dir / 'qmd'})", issue)
        self.assertIn(f"codex ({bin_dir / 'codex'})", issue)
        # The default measures what the login shell adds, and refuses when it cannot.
        with mock.patch.object(codex_lane, "login_shell_path", return_value=str(bin_dir)):
            self.assertIn("qmd", codex_lane.blind_path_issue())
        with mock.patch.object(codex_lane, "login_shell_path", side_effect=codex_lane.PathUnmeasured("`/bin/sh -c` exited 2")):
            self.assertIn("could not be measured (`/bin/sh -c` exited 2)", codex_lane.blind_path_issue())

    def test_a_non_blind_lane_reports_a_retrieval_cli_and_a_blind_one_does_not(self):
        self.write_packet("foundation", "native-clients")
        command = json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "/bin/bash -lc 'qmd search verdict'"}})
        self.events_file.write_text(command + "\n" + CANNED_EVENTS, encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(["--allow-git-history"]), 0)
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        reasons = [r for item in audit["layers"]["foundation__native-clients"]["flagged_commands"] for r in item["reasons"]]
        self.assertIn("runs qmd", reasons)
        # The same events in a blind run: qmd cannot resolve on the child's PATH, so the name is not flagged.
        (self.work_dir / "codex" / "foundation__native-clients.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(), 0)
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(audit["layers"]["foundation__native-clients"]["flagged_commands"], [])

    def test_an_env_style_launcher_runs_with_the_callers_interpreter(self):
        # Codex review of #206 (P1): npm's codex is `#!/usr/bin/env node`, and a blind child's PATH has no node.
        bin_dir = self.work_dir / "npm-bin"
        bin_dir.mkdir()
        (bin_dir / "fakenode").write_text("#!/bin/sh\nexec python3 \"$@\"\n", encoding="utf-8")
        body = (FIXTURE_BIN / "codex").read_text(encoding="utf-8").split("\n", 1)[1]
        (bin_dir / "codex").write_text("#!/usr/bin/env fakenode\n" + body, encoding="utf-8")
        for name in ("fakenode", "codex"):
            (bin_dir / name).chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}):
            self.assertEqual(codex_lane.blind_child_argv(["codex", "exec", "x"]),
                             [str(bin_dir / "fakenode"), str(bin_dir / "codex"), "exec", "x"])
            self.write_packet("foundation", "native-clients")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.run_lane(), 0)
        self.assertTrue((self.work_dir / "codex" / "foundation__native-clients.json").is_file())
        # `env -S` with interpreter arguments, an absolute shebang, a binary, and an interpreter nobody resolves.
        (bin_dir / "s").write_text("#!/usr/bin/env -S fakenode -u -S\n", encoding="utf-8")
        (bin_dir / "a").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "b").write_bytes(b"\x7fELF\x02\x01")
        (bin_dir / "u").write_text("#!/usr/bin/env no-such-interpreter\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            self.assertEqual(codex_lane.blind_child_argv([str(bin_dir / "s"), "x"]),
                             [str(bin_dir / "fakenode"), "-u", "-S", str(bin_dir / "s"), "x"])
            for name in ("a", "b", "u"):
                self.assertEqual(codex_lane.blind_child_argv([str(bin_dir / name), "x"]), [str(bin_dir / name), "x"])
            self.assertEqual(codex_lane.blind_child_argv(["missing-cli", "x"]), ["missing-cli", "x"])

    def test_a_cli_run_by_absolute_path_and_a_file_url_still_flag(self):
        # Codex review of #206 (P2 x2): /usr/local/bin/qmd is an exempt system executable token, and file:// is local.
        repo = self.repo
        expected = {
            "/bin/bash -lc '/usr/local/bin/qmd search verdict'": "runs qmd by path: /usr/local/bin/qmd",
            "/usr/local/bin/mcporter call x": "runs mcporter by path: /usr/local/bin/mcporter",
            "/bin/bash -lc 'cat https: //etc/passwd'": "path outside the repository and packets: //etc/passwd",
            "/bin/bash -lc \"python3 -c \\\"import subprocess; subprocess.run(['/opt/tools/serena'])\\\"\"":
                "runs serena by path: /opt/tools/serena",
            "/bin/bash -lc \"python3 -c \\\"import urllib.request as u; u.urlopen('file:///etc/os-release')\\\"\"":
                "path outside the repository and packets: ///etc/os-release",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))
        for command in (f"/bin/bash -lc 'rg -n x {repo}/docs/qmd'", "/bin/bash -lc 'rg -n ssh://host/x docs'",
                        "/bin/bash -lc \"rg -n 'https://github.com/tobi/qmd' catalogs\"",
                        "/bin/bash -lc \"rg -n 'qmd://docs/verdict|s3://bucket/key|attachment://x/y' catalogs\"",
                        # Wave 20260924 re-record: a Python URL test and an rg regex fragment voided two layers.
                        "/bin/bash -lc \"python3 - <<'PY'\nfor ref in refs:\n print(ref, 'EXTERNAL' if '://' in ref else ref)\nPY\"",
                        "/bin/bash -lc \"rg --files tests | rg '(test_adaptive_paper_(recovery|safety)\\\\.py$|/runner.py$)'\"",
                        "/bin/bash -lc \"rg -n 'https://example.invalid/tools/serena/' catalogs\"",
                        "/bin/bash -lc \"rg -n 'wss://host/x|sftp://h/y' docs\""):
            with self.subTest(command=command):
                self.assertEqual(self.reasons(command), [])

    def test_independent_review_of_206_reaches_still_flag(self):
        # C2: a '/' joined on one side only builds an absolute path; C1: file:/// and https:/// are no network authority.
        expected = {
            "/bin/bash -lc \"python3 -c \\\"print(open('/'+'etc/passwd').read())\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"x = 'etc' ; print(open('/' + x))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"print(open(''+'/'+'etc/passwd').read())\\\"\"": "names the filesystem root /",
            "/bin/bash -lc 'python3 - <<\"PY\"\nprint(open(\"/\"+\"etc\"))\nPY'": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"x='a'; print(open(x+'/'+'etc'))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"x='etc'; print(open(''+'/'+x))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc 'cat https:///etc/passwd'": "path outside the repository and packets: ///etc/passwd",
            "/bin/bash -lc \"cat /etc/passwd$''\"": "path outside the repository and packets: /etc/passwd$",
            "/bin/bash -lc \"rg -n '/runner.py$' x\"": "path outside the repository and packets: /runner.py$",
            "/bin/bash -lc 'cat ://x'": "path outside the repository and packets: //x",
            "/bin/bash -lc 'ls //'": "path outside the repository and packets: //",
            "/bin/bash -lc 'rg -n \"://|file\" docs'": "path outside the repository and packets: //",
            "/bin/bash -lc \"python3 -c \\\"print(':'+'//etc')\\\"\"": "path outside the repository and packets: //etc",
            "/bin/bash -lc \"python3 -c \\\"import urllib.request as u; u.urlopen('FILE://localhost/etc/passwd')\\\"\"":
                "path outside the repository and packets: //localhost/etc/passwd",
            "/bin/bash -lc 'unzip -p jar:file:///etc/x.jar'": "path outside the repository and packets: ///etc/x.jar",
            "/bin/bash -lc \"python3 -c \\\"print('http+unix://%2Frun%2Fuser%2F1000%2Fx.sock/v1')\\\"\"":
                "path outside the repository and packets: //%2Frun%2Fuser%2F1000%2Fx.sock/v1",
            "/bin/bash -lc \"python3 -c \\\"print('local://etc/passwd')\\\"\"": "path outside the repository and packets: //etc/passwd",
            "/bin/bash -lc '/bin/sh -c file:///usr/local/bin/qmd; /usr/local/bin/qmd x'":
                "runs qmd by path: /usr/local/bin/qmd",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))

    def test_the_measured_path_covers_a_shell_without_path_and_ignores_profile_output(self):
        # C3: subprocess.run(..., shell=True, env={}) starts /bin/sh with its compiled default PATH (/usr/local/bin);
        # C5: a profile that prints something must not turn it into a directory.
        calls = []

        def run(argv, env=None, **_kwargs):
            calls.append((argv, env))
            noise = "profile says hi\n" if "-lc" in argv else ""
            measured = "/login/bin" if "-lc" in argv else ("/sh/default" if argv[0] == "/bin/sh" else "/shell/default")
            return subprocess.CompletedProcess(argv, 0, noise + "\n" + codex_lane.PATH_SENTINEL + measured, "")

        with mock.patch.object(codex_lane.subprocess, "run", side_effect=run):
            measured = REAL_LOGIN_SHELL_PATH()
        self.assertEqual(measured.split(os.pathsep),
                         [*os.defpath.split(os.pathsep), "/login/bin", "/sh/default", "/shell/default"])
        self.assertEqual([env for _argv, env in calls][1:], [{}, {}])
        self.assertEqual(calls[0][1]["PATH"], codex_lane.BLIND_CHILD_PATH)
        self.assertEqual(calls[1][0][0], "/bin/sh")
        failing = lambda argv, env=None, **_kwargs: subprocess.CompletedProcess(argv, 0, "no sentinel", "profile broke")
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=failing):
            with self.assertRaisesRegex(codex_lane.PathUnmeasured, "without printing its PATH: profile broke"):
                REAL_LOGIN_SHELL_PATH()
        # R2-4: a probe that raises is named, and so is non-UTF-8 profile output, which no longer escapes.
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=subprocess.TimeoutExpired("sh", 30)):
            with self.assertRaisesRegex(codex_lane.PathUnmeasured, "timed out"):
                REAL_LOGIN_SHELL_PATH()
        self.assertIn("/usr/bin", REAL_LOGIN_SHELL_PATH().split(os.pathsep))
        # A login shell whose profile prints bytes that are not UTF-8 is still measured (R2-4).
        noisy = self.work_dir / "noisy-shell"
        noisy.write_bytes(b'#!/bin/sh\nprintf "\\377\\376 profile noise\\n"\nexec /bin/sh "$@"\n')
        noisy.chmod(0o755)
        import pwd
        with mock.patch.object(pwd, "getpwuid", return_value=mock.Mock(pw_shell=str(noisy))):
            self.assertIn("/usr/bin", REAL_LOGIN_SHELL_PATH().split(os.pathsep))

    def test_a_shell_script_codex_launcher_is_refused_up_front(self):
        # Independent review of #206, R2-2: pnpm's cmd-shim runs `exec node ...` by name, which exits 127 in a blind child.
        bin_dir = self.work_dir / "shim-bin"
        bin_dir.mkdir()
        (bin_dir / "codex").write_text('#!/bin/sh\nexec node "$0.js" "$@"\n', encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}):
            self.assertIn("is a shell-script launcher (/bin/sh)", codex_lane.codex_launch_issue())
            self.write_packet("foundation", "native-clients")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("shell-script launcher", err.getvalue())
        self.assertFalse(self.argv_log.exists() and self.argv_log.read_text(encoding="utf-8").strip())
        # An env-style shell launcher (asdf's shims) is a shell-script launcher too.
        (bin_dir / "asdf-codex").write_text('#!/usr/bin/env bash\nexec asdf exec codex "$@"\n', encoding="utf-8")
        (bin_dir / "asdf-codex").chmod(0o755)
        self.assertIn("shell-script launcher (bash)", codex_lane.codex_launch_issue(str(bin_dir / "asdf-codex")))
        (bin_dir / "s-codex").write_text('#!/usr/bin/env -S bash -e\n', encoding="utf-8")
        (bin_dir / "s-codex").chmod(0o755)
        self.assertIn("shell-script launcher (bash -e)", codex_lane.codex_launch_issue(str(bin_dir / "s-codex")))
        # The fixture's env-style launcher, a missing codex and a binary are not refused.
        self.assertIsNone(codex_lane.codex_launch_issue())
        self.assertIsNone(codex_lane.codex_launch_issue("no-such-codex"))
        (bin_dir / "native").write_bytes(b"\x7fELF\x02\x01")
        (bin_dir / "native").chmod(0o755)
        self.assertIsNone(codex_lane.codex_launch_issue(str(bin_dir / "native")))

    def test_a_failed_childs_stderr_reaches_the_console_not_the_record(self):
        # Independent review of #206, R2-2: "codex exec exited 127" alone did not say why.
        self.write_packet("foundation", "native-clients")
        failed = {"exit_code": 127, "stdout": "", "timed_out": False, "stopped": False, "elapsed": 0.1,
                  "stderr": "Reading additional input from stdin...\n/usr/bin/env: 'node': No such file or directory\n"}
        err = io.StringIO()
        with mock.patch.object(codex_lane, "run_attempt", return_value=failed), contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(), 1)
        self.assertIn("codex exec exited 127: /usr/bin/env: 'node': No such file or directory", err.getvalue())
        self.assertNotIn("Reading additional input", err.getvalue())
        failures = json.loads((self.work_dir / "codex" / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual(failures[0]["reason"], "failed after retry: codex exec exited 127")

    def test_a_blind_run_is_refused_when_the_child_path_resolves_one(self):
        self.write_packet("foundation", "native-clients")
        with mock.patch.object(codex_lane, "blind_path_issue", return_value="a blind child's PATH resolves qmd"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("resolves qmd", err.getvalue())
        self.assertFalse(self.argv_log.exists() and self.argv_log.read_text(encoding="utf-8").strip())


class InterruptionTests(CodexLaneFixture):
    """Independent review of #145, round 7 (REG7-1, ISO-R7-1..4): an interrupted or resumed blind run never keeps a
    flagged layer, a stop writes no return and starts no retry, and one work dir runs once whatever the base."""

    FLAGGED = json.dumps({"type": "item.completed", "item": {
        "type": "command_execution", "command": "/bin/bash -lc 'cat /home/example/.state/verdicts.json'"}}) + "\n"

    def flagged_events(self) -> Path:
        path = self.work_dir.parent / "flagged-events.jsonl"
        path.write_text(CANNED_EVENTS + "\n" + self.FLAGGED, encoding="utf-8")
        return path

    def test_an_interrupted_run_and_its_resume_never_keep_a_flagged_layer(self):
        self.write_packet("foundation", "a-layer")
        self.write_packet("foundation", "b-layer")
        os.environ["CODEX_FAKE_EVENTS_MAP"] = json.dumps({"foundation__a-layer": str(self.flagged_events())})
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__b-layer"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane()
        codex_dir = self.work_dir / "codex"
        # The flagged layer was audited before any write; the stopped one wrote nothing.
        self.assertFalse((codex_dir / "foundation__a-layer.json").exists())
        self.assertTrue((codex_dir / "foundation__a-layer.json.audit-flagged").exists())
        self.assertFalse((codex_dir / "foundation__b-layer.json").exists())
        audit = json.loads((codex_dir / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        self.assertTrue(audit["layers"]["foundation__a-layer"]["flagged_commands"])
        os.environ.pop("CODEX_FAKE_TERM_PARENT_MATCH")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(), 1)
        self.assertFalse((codex_dir / "foundation__a-layer.json").exists())
        self.assertTrue((codex_dir / "foundation__b-layer.json").exists())

    def test_a_resume_reaudits_a_kept_return(self):
        packet_path = self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        (codex_dir / "events").mkdir(parents=True)
        out_path = codex_dir / "foundation__native-clients.json"
        events_path = codex_dir / "events" / "foundation__native-clients.jsonl"
        for events in (self.FLAGGED, None):
            with self.subTest(events="flagged" if events else "missing"):
                self.argv_log.unlink(missing_ok=True)
                out_path.write_text(json.dumps(canned_return(
                    packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                    provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
                    model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
                if events:
                    events_path.write_text(events, encoding="utf-8")
                else:
                    events_path.unlink(missing_ok=True)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.run_lane(["--model", "gpt-6-astra", "--effort", "high"])
                self.assertEqual(len(self.argv_calls()), 1, "a kept return with flagged or missing events reruns")

    def test_an_interrupted_rerun_never_leaves_a_countable_old_return(self):
        # Round 8, NEW-1: the rerun truncated the events and was interrupted, leaving the old return beside an empty,
        # clean-looking stream that the next resume counted.
        packet_path = self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        (codex_dir / "events").mkdir(parents=True)
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(canned_return(
            packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
            model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
        events_path = codex_dir / "events" / "foundation__native-clients.jsonl"
        events_path.write_text(self.FLAGGED, encoding="utf-8")
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__native-clients"
        os.environ["CODEX_FAKE_TERM_SLEEP"] = "30"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane(["--model", "gpt-6-astra", "--effort", "high"])
        self.assertFalse(out_path.exists(), "the rerun removed the old return before rewriting its events")
        # And a kept return beside an empty stream is never counted.
        out_path.write_text(json.dumps(canned_return(
            packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
            model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
        events_path.write_text("", encoding="utf-8")
        self.assertFalse(codex_lane.existing_output_is_valid(
            out_path, "foundation", "native-clients", hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            audit_roots=[str(self.repo)]))

    def test_a_stop_with_jobs_2_writes_no_return_and_starts_no_retry(self):
        self.write_packet("foundation", "a-layer")
        self.write_packet("foundation", "b-layer")
        os.environ["CODEX_FAKE_SLEEP_MAP"] = json.dumps({"foundation__a-layer": 30})
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__b-layer"
        os.environ["CODEX_FAKE_TERM_SLEEP"] = "30"
        started = time.monotonic()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane(["--jobs", "2"])
        self.assertLess(time.monotonic() - started, 20)
        # Each layer's child ran at most once: no retry starts after a stop, and a layer whose child had not started
        # when the stop came never starts one.
        calls = [" ".join(call) for call in self.argv_calls()]
        for layer in ("foundation__a-layer", "foundation__b-layer"):
            self.assertLessEqual(sum(layer in call for call in calls), 1, layer)
        self.assertEqual(sum("foundation__b-layer" in call for call in calls), 1)
        self.assertEqual(sorted(p.name for p in (self.work_dir / "codex").glob("*__*.json")), [])
        # The run home's link is gone and no child is left holding it.
        homes = sorted(codex_lane.codex_home_base().glob(codex_lane.codex_home_prefix(self.work_dir) + "-*"))
        self.assertTrue(homes)
        self.assertFalse(any((home / "auth.json").is_symlink() for home in homes))
        self.assertFalse(any(codex_lane.home_in_use(home) for home in homes))

    def test_one_work_dir_runs_once_whatever_the_homes_base(self):
        self.write_packet("foundation", "native-clients")
        with codex_lane.exclusive_run_lock(codex_lane.work_run_lock(self.work_dir)):
            os.environ[codex_lane.CODEX_HOME_BASE_ENV] = str(self.work_dir.parent / "other-base")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("another run holds", err.getvalue())
        self.assertEqual(self.argv_calls(), [])


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


class EvidenceTreeProvenanceTests(CodexLaneFixture):
    """Round-9 review of #145: a return is bound to the evidence tree it read."""

    def test_a_resume_against_another_export_reruns(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        first = len(self.argv_calls())
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), first, "same tree: resumed")
        (self.repo / "evidence.json").write_text('{"other": "export"}', encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        self.assertGreater(len(self.argv_calls()), first, "another tree: rerun")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["repo_tree_sha256"], codex_lane.tree_sha256(self.repo))

    def test_a_tree_changed_during_the_run_sets_the_returns_aside(self):
        self.write_packet("foundation", "native-clients")
        trees = iter(["a" * 64, "b" * 64])
        with mock.patch.object(codex_lane, "tree_sha256", side_effect=lambda repo, *rest, **named: next(trees)), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 1)
        out_path = self.out_path("foundation", "native-clients")
        self.assertFalse(out_path.exists())
        self.assertTrue(out_path.with_name(out_path.name + ".tree-changed").is_file())
        self.assertIn("the evidence tree changed during the run", err.getvalue())


class EscapingSymlinkTreeTests(CodexLaneFixture):
    """Codex review of #145: content behind a symlink leaving the tree could change under an unchanged digest."""

    def test_the_tree_digest_refuses_a_symlink_leaving_the_repository(self):
        (self.repo / "inner.md").write_text("x", encoding="utf-8")
        os.symlink("inner.md", self.repo / "inner-link.md")
        codex_lane.tree_sha256(self.repo)
        os.symlink("/etc/hostname", self.repo / "outside-link")
        with self.assertRaises(ValueError):
            codex_lane.tree_sha256(self.repo)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("symlink leaving it", err.getvalue())
        # A deliberately non-blind run (--allow-git-history) hashes such a link's text instead (re-review L2).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)
        (self.repo / "outside-link").unlink()
        os.symlink("loop-b", self.repo / "loop-a")
        os.symlink("loop-a", self.repo / "loop-b")
        with self.assertRaisesRegex(ValueError, "symlink loop"):  # on 3.12 and 3.13 alike (delta review D1)
            codex_lane.tree_sha256(self.repo)
        # A non-blind run hashes a loop by its link text on 3.12 too, where resolve() raises (round 4, R4-REG-4).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)
        os.symlink("missing-target", self.repo / "dangling")
        (self.repo / "loop-a").unlink()
        (self.repo / "loop-b").unlink()
        self.assertIsInstance(codex_lane.tree_sha256(self.repo), str)  # a dangling internal link is hashed
        (self.repo / "dangling").unlink()
        os.symlink("loop-b", self.repo / "loop-a")
        os.symlink("loop-a", self.repo / "loop-b")
        (self.repo / "loop-a").unlink()
        (self.repo / "loop-b").unlink()
        os.mkfifo(self.repo / "pipe")
        with self.assertRaisesRegex(ValueError, "non-regular entry"):
            codex_lane.tree_sha256(self.repo)
        # A non-blind run tolerates git's fsmonitor socket and similar entries (delta review L3).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)


class IsolatedCodexHomeTests(CodexLaneFixture):
    """2026-09-24 blindness: --ignore-user-config does not skip $CODEX_HOME/AGENTS.md, so blind children run
    with a fresh run-scoped CODEX_HOME that links, never copies, the native auth.json, an empty HOME and only an
    allowlisted environment."""

    def homes(self):
        base = codex_lane.codex_home_base()
        return sorted(base.glob(codex_lane.codex_home_prefix(self.work_dir) + "-*")) if base.is_dir() else []

    def test_the_home_links_the_native_auth_and_children_get_only_the_allowlisted_environment(self):
        (self.native_codex / "AGENTS.md").write_text("# global instructions naming tools", encoding="utf-8")
        home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertEqual(home.parent, codex_lane.codex_home_base())
        # Outside the work dir, which holds both lanes' returns (BIND-R4-7).
        self.assertNotIn(self.work_dir.resolve(), home.parents)
        self.assertTrue((home / "auth.json").is_symlink())
        self.assertEqual(os.readlink(home / "auth.json"), str(self.native_codex / "auth.json"))
        self.assertFalse((home / "AGENTS.md").exists())
        self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")
        seen = {}

        def fake_popen(cmd, **kwargs):
            seen.update(kwargs)
            return mock.Mock(returncode=0, communicate=mock.Mock(return_value=("", "")), poll=mock.Mock(return_value=0))

        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SSE_PORT": "1", "ALPACA_API_KEY_ID": "x", "LANG": "C.UTF-8"}), \
                mock.patch.object(codex_lane, "CHILD_CODEX_HOME", home), \
                mock.patch.object(codex_lane.subprocess, "Popen", side_effect=fake_popen):
            codex_lane.run_attempt(["codex", "exec"], 5)
        # The run home's in-use lock rides along to the child (round 7, ISO-R7-2).
        self.assertEqual(seen["pass_fds"], (codex_lane.IN_USE_HANDLE.fileno(),))
        env = seen["env"]
        self.assertEqual(env["CODEX_HOME"], str(home))
        # Review of #145: user Agent Skills under $HOME/.agents/skills name adopted tools; the child's HOME is empty.
        self.assertEqual(env["HOME"], str(home / "home"))
        self.assertEqual(list((home / "home").iterdir()), [])
        # Round 5, ISO-R5-2 and ISO-R5-3: no coordinator or broker variable, no stdin.
        self.assertNotIn("CLAUDE_CODE_SSE_PORT", env)
        self.assertNotIn("ALPACA_API_KEY_ID", env)
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertIs(seen["stdin"], subprocess.DEVNULL)

    def test_each_run_gets_a_fresh_home_and_a_dry_run_writes_none(self):
        # Codex review of #145: a leftover AGENTS.md would be loaded; round 5, INT-R5-2: nothing is ever removed to
        # make a home. A dry run writes nothing but prints each child's environment (OPS-4, N7).
        first = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        (first / "AGENTS.md").write_text("# leftover instructions", encoding="utf-8")
        second = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertNotEqual(first, second)
        self.assertFalse((second / "AGENTS.md").exists())
        self.assertTrue((first / "AGENTS.md").exists())  # never removed
        for home in self.homes():
            shutil.rmtree(home)
        self.write_packet("foundation", "native-clients")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertEqual(self.homes(), [])
        self.assertIn("env -i", out.getvalue())
        self.assertIn("CODEX_HOME=" + str(codex_lane.codex_home_base()), out.getvalue())
        self.assertIn("fresh", err.getvalue())

    def test_a_blind_run_uses_a_home_and_removes_the_credential_link_after(self):
        env_log = self.work_dir.parent / "env.jsonl"
        os.environ["CODEX_FAKE_ENV_LOG"] = str(env_log)
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        seen = [json.loads(line) for line in env_log.read_text(encoding="utf-8").splitlines()]
        [home] = self.homes()
        self.assertEqual(seen, [{"CODEX_HOME": str(home), "HOME": str(home / "home"), "auth_link": True}])
        self.assertFalse((home / "auth.json").is_symlink())
        self.assertIsNone(codex_lane.CHILD_CODEX_HOME)

    def test_a_base_overlapping_the_native_home_is_refused_and_nothing_is_removed(self):
        # Round 5, INT-R5-2: with the native home at, inside or around the run homes' base, nothing is created
        # and nothing is removed.
        (self.native_codex / "config.toml").write_text("model = 'x'", encoding="utf-8")
        for base in (self.native_codex, self.native_codex / "runs", self.native_codex.parent):
            with self.subTest(base=str(base)), mock.patch.dict(os.environ, {codex_lane.CODEX_HOME_BASE_ENV: str(base)}):
                with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "overlap"):
                    codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertEqual(sorted(p.name for p in self.native_codex.iterdir()), ["auth.json", "config.toml"])
        self.assertFalse((self.native_codex / "runs").exists())

    def test_a_base_inside_the_work_dir_or_without_a_credential_is_refused(self):
        with mock.patch.dict(os.environ, {codex_lane.CODEX_HOME_BASE_ENV: str(self.work_dir / "homes")}):
            with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "overlaps"):
                codex_lane.isolated_codex_home(self.work_dir, self.repo)
        (self.native_codex / "auth.json").unlink()
        for key in ("CODEX_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "no native Codex credential"):
            codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("codex login", err.getvalue())
        self.assertFalse((self.work_dir / "codex" / "foundation__native-clients.json").exists())

    def test_an_api_key_never_reaches_a_child(self):
        # Round 6, ISO-R6-4: the model's shell inherits the child's variables, so a blind child gets no key; an API key
        # alone does not satisfy the credential check.
        with mock.patch.dict(os.environ, {"CODEX_API_KEY": "k", "OPENAI_API_KEY": "o"}):
            home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
            (home / "auth.json").unlink()
            self.assertFalse({"CODEX_API_KEY", "OPENAI_API_KEY"} & set(codex_lane.child_env(home)))
            (self.native_codex / "auth.json").unlink()
            self.assertIn("codex login --with-api-key", codex_lane.codex_home_issue(self.work_dir, self.repo))

    def test_round6_isolation_details(self):
        # Round 6: a fresh TMPDIR (REG6-3), no API key forwarded (ISO-R6-4), stale links swept under the
        # shared lock (ISO-R6-1), proxy credentials redacted in printed output (ISO-R6-5).
        home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        env = codex_lane.child_env(home)
        self.assertEqual(env["TMPDIR"], str(home / "tmp"))
        self.assertEqual(list((home / "tmp").iterdir()), [])
        (home / "auth.json").unlink()
        with mock.patch.dict(os.environ, {"CODEX_API_KEY": "k", "OPENAI_API_KEY": "o"}):
            env = codex_lane.child_env(home)
        self.assertEqual((env.get("CODEX_API_KEY"), env.get("OPENAI_API_KEY")), (None, None))
        stale = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertTrue((stale / "auth.json").is_symlink())
        # A live holder of the in-use lock (a child of a killed run) keeps its link (round 7, ISO-R7-2) ...
        codex_lane.sweep_stale_links(self.work_dir)
        self.assertTrue((stale / "auth.json").is_symlink())
        # ... and once no process holds it, the next run's sweep removes it.
        codex_lane.IN_USE_HANDLE.close()
        codex_lane.IN_USE_HANDLE = None
        codex_lane.sweep_stale_links(self.work_dir)
        self.assertFalse((stale / "auth.json").is_symlink())
        self.assertTrue((self.native_codex / "auth.json").is_file())
        self.assertEqual(codex_lane.redact_userinfo("http://user:secret@proxy:3128"), "http://***@proxy:3128")
        # Round 7, ISO-R7-6: scheme-less, and a password holding '@'.
        self.assertEqual(codex_lane.redact_userinfo("user:pass@proxy:3128"), "***@proxy:3128")
        self.assertEqual(codex_lane.redact_userinfo("socks5h://user:p@ss@proxy:1080"), "socks5h://***@proxy:1080")
        self.assertEqual(codex_lane.redact_userinfo("/usr/bin:/bin"), "/usr/bin:/bin")
        self.assertEqual(codex_lane.codex_home_lock(self.work_dir).parent, codex_lane.codex_home_base())
        # Round 7, ISO-R7-8: the homes' base is private.
        self.assertEqual(oct(codex_lane.codex_home_base().stat().st_mode & 0o777), "0o700")

    def test_the_audit_reads_the_raw_command_text(self):
        # Round 8, REG8-1: a narrower reading of what bash expands hid reads; the raw text is matched. REG8-3: the
        # bare word CODEX_HOME in a search is benign, reading the environment is not.
        events = self.work_dir / "active-events.jsonl"
        commands = {"/bin/bash -lc \"rg -n CODEX_HOME docs\"": False,
                    "/bin/bash -lc \"rg -n 'CODEX_HOME' docs\"": False,
                    "/bin/bash -lc 'cat $(dirname x)/y'": True,
                    "/bin/bash -lc \"echo \\\"it's\\\" $(pwd)\"": True,
                    "/bin/bash -lc \"cat <<EOF\n$(cat evidence/x)\nEOF\"": True,
                    "/bin/bash -c \"sh -c 'ls $CODEX_HOME'\"": True,
                    "/bin/bash -lc 'printenv CODEX_HOME | xargs dirname'": True,
                    "/bin/bash -lc 'env | grep HOME'": True,
                    "/bin/bash -lc 'rg -l winner ${TMPDIR}'": True,
                    # A known low (REG7-3): a literal backtick in a single-quoted pattern is voided too.
                    "/bin/bash -lc \"rg -n '`component_id`' docs\"": True}
        for command, flagged in commands.items():
            events.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
            report = codex_lane.blind_audit(events, [str(self.repo)])
            self.assertEqual(bool(report["flagged_commands"]), flagged, command)

    def test_round7_a_proxy_with_credentials_is_refused_for_a_blind_run(self):
        # ISO-R7-5: every child variable reaches the model's shell.
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://user:secret@proxy.example:3128"}):
            issue = codex_lane.codex_home_issue(self.work_dir, self.repo)
        self.assertIn("carries credentials", issue)
        self.assertNotIn("secret", issue)
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy.example:3128", "NO_PROXY": "a@b"}):
            self.assertIsNone(codex_lane.codex_home_issue(self.work_dir, self.repo))

    def test_a_dry_run_refuses_a_home_it_could_not_set_up(self):
        # Round 6, ISO-R6-5: the refusals run before the dry run and create nothing.
        (self.native_codex / "auth.json").unlink()
        for key in ("CODEX_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_lane(["--dry-run"]), 2)
        self.assertIn("codex login", err.getvalue())
        self.assertFalse(codex_lane.codex_home_base().exists())

    def test_the_codex_home_and_command_substitution_are_flagged(self):
        # Round 6, ISO-R6-2.
        events = self.work_dir / "home-events.jsonl"
        events.write_text("".join(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n"
            for command in ("ls $CODEX_HOME", "cat $(dirname x)/y", "cat `pwd`/y", "rg -l winner ${TMPDIR}",
                            "cp -r $SSL_CERT_DIR .")), encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo)])
        reasons = " ".join(reason for item in report["flagged_commands"] for reason in item["reasons"])
        self.assertIn("names the Codex home", reasons)
        self.assertEqual(reasons.count("command substitution"), 2)
        self.assertEqual(reasons.count("inherited directory variable"), 2)  # REG6-3
        self.assertEqual(len(report["flagged_commands"]), 5)

    def test_a_work_dir_inside_a_repository_is_refused(self):
        # Independent review of #145, round 4, OPS-6: the recipe's rule, enforced.
        (self.work_dir / ".git").mkdir()
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("is inside the git repository", err.getvalue())

    def test_parameter_expansion_is_flagged(self):
        # Independent review of #145, BIND-R4-7: ${...} builds a path the event does not show.
        events = self.work_dir / "expansion.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "bash -lc 'cat \"${CODEX_HOME%/*}/x.json\"'"}}) + "\n",
            encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo)])
        self.assertTrue(any("parameter expansion" in reason for item in report["flagged_commands"]
                            for reason in item["reasons"]), report)


class ExactProvenanceResumeTests(CodexLaneFixture):
    """Round-8 review of #145: resume needs the recorded provenance to equal the current one exactly; a return
    carrying an extra or changed provenance field is not resumed."""

    def test_a_return_with_an_extra_provenance_field_reruns(self):
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()
        existing = canned_return(packet_sha256=packet_sha256, provenance={**current, "extra": "1" * 64},
                                 model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})
        out_path.write_text(json.dumps(existing), encoding="utf-8")
        self.assertFalse(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                              packet_sha256, current))
        existing["provenance"] = current
        out_path.write_text(json.dumps(existing), encoding="utf-8")
        self.assertTrue(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                             packet_sha256, current))


if __name__ == "__main__":
    unittest.main()
