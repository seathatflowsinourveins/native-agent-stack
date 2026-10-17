"""Native runtime profiles: live-port binding and generated tool fences.

The source of the endpoint is the repository's new-WSL client-config record;
the CC's 2026-10-12 measurement corroborates that record, without a network test.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import importlib.util
import argparse
from unittest import mock
import io
import shutil
import signal
import contextlib
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles
import runtime_acceptance as acceptance


WORKER = ROOT / "tools/claude-review-worker/worker.py"


class StrictHostConsumerTests(unittest.TestCase):
    def host(self, root):
        path = root / "host.json"
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        values.update(WSL_DISTRO_NAME="FixtureDistro", AI_MEMORY_URL="127.0.0.1:39374",
                      NS_PORT_OTEL_HTTP="31318", NS_PORT_GATEWAY="41128")
        path.write_text(json.dumps(values))
        return path

    def test_wsl_mcp_uses_the_explicit_complete_host_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(self.host(root))}):
                servers = profiles.render_wsl_mcp(root, root / "ecosystem")
            # ai-memory 3.1.0's bridge, session-less for these clients (install_mcp.rs:181-185 and 214-225 at 11ca7c5b).
            self.assertEqual(servers["ai-memory"]["args"],
                             ["mcp-bridge", "--no-session-id", "--server-url", "http://127.0.0.1:39374/mcp"])
            self.assertNotIn("url", servers["ai-memory"])

    def test_runtime_telemetry_uses_the_same_host_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(self.host(root))}):
                values = profiles.profile_environment("pi-gpt", root)
            self.assertEqual(values["OTEL_EXPORTER_OTLP_ENDPOINT"], "http://127.0.0.1:31318")
            self.assertEqual(values["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"], "http://127.0.0.1:31318/v1/logs")

    def test_provider_resolves_the_current_explicit_host_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(self.host(root))}):
                provider = profiles.opencode_provider("gpt")
                pi_provider = profiles.pi_models("gpt")
            self.assertEqual(provider["omniroute"]["options"]["baseURL"], "http://127.0.0.1:41128/v1")
            self.assertEqual(pi_provider["providers"]["omniroute"]["baseUrl"], "http://127.0.0.1:41128/v1")

    def test_wsl_mcp_refuses_missing_explicit_host_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": ""}):
                with self.assertRaisesRegex(profiles.ProfileError, "NS2604_HOST_FILE"):
                    profiles.render_wsl_mcp(root, root)

    def test_runtime_acceptance_uses_current_host_values_for_direct_and_credential_wrapped_checks(self):
        for profile in ("pi-gpt", "pi-claude"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                state = Path(tmp)
                root = state / profile
                root.mkdir()
                (root / "profile.json").write_text(json.dumps({"pi_bin": "/fixture/pi", "mcp_server_names": ["context-mode"]}))
                args = argparse.Namespace(state_root=state, workspace=state, out=state / "receipts",
                                          role_scope=None, tokenizer_python=Path(sys.executable))
                calls = []
                def native(command, **kwargs):
                    calls.append((command, kwargs))
                    return 0, json.dumps({"servers": []}) if "mcp" in command else "{}"
                with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(self.host(state))}), \
                        mock.patch.object(acceptance, "native", side_effect=native), \
                        mock.patch.object(acceptance, "choose_slot", return_value="fixture-slot"), \
                        mock.patch.object(acceptance, "discovered", return_value=[]), \
                        mock.patch.object(acceptance, "skill_integrity", return_value={"managed_pass": True}), \
                        redirect_stdout(io.StringIO()):
                    acceptance.check(args, profile)
                self.assertTrue(calls)
                wanted = "http://127.0.0.1:31318"
                if profile == "pi-gpt":
                    self.assertEqual(calls[0][1]["env"]["OTEL_EXPORTER_OTLP_ENDPOINT"], wanted)
                else:
                    self.assertIn("OTEL_EXPORTER_OTLP_ENDPOINT=" + wanted, calls[0][0])


def pi_events(handle, *, error=None, tokens=0, cost=0):
    """Pi --mode json events for one assistant turn: refused with `error` ("<status> <body>"), or completed."""
    message = {"role": "assistant", "content": [] if error else [{"type": "text", "text": "fixture"}],
               "usage": {"input": tokens, "output": 0, "totalTokens": tokens, "cost": {"total": cost}},
               "stopReason": "error" if error else "stop"}
    if error:
        message["errorMessage"] = error
    for kind in ("message_start", "message_end"):
        handle.write(json.dumps({"type": kind, "message": message}) + "\n")


CREDIT_400 = '400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API."}}'
# The refusal inside a response already streaming (measured 2026-10-15 ~04:06Z, request id replaced): no status prefix,
# and the refused message itself was billed.
CREDIT_STREAM = ('{"type":"error","error":{"details":null,"type":"invalid_request_error","message":"Your credit balance '
                 'is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},'
                 '"request_id":"req_fixture"}             ')


class PiLaunchFixture:
    """A pi-claude print launch against fixture slots, shared by the fill-first and mid-run failover tests."""

    def worker(self):
        spec = importlib.util.spec_from_file_location("fill_first_test_worker", WORKER)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # its dataclasses resolve their module through sys.modules
        spec.loader.exec_module(mod)
        return mod

    def launch(self, slot_outcomes, health_rows=None, ends=None, ledger=None, raises=None, sessions=True,
               resume=None, state=None, sigterm=None, raw=None):
        """A pi-claude print launch whose runtime writes, per slot, its turns: "ok" (a completed turn), a refusal text
        (refused before billed output) or (refusal, tokens) (refused after billed output), one turn or a list; then
        ends with status `ends[slot]` (0 when absent; "watchdog" raises the outer subprocess timeout); a slot in
        `raises` raises OSError. Like pi, it keeps a <time>_<id>.jsonl session file for a --session-id unless
        `sessions` is false. `resume(state, root)` returns a receipt path for --resume; `state` reuses a directory; a
        slot in `sigterm` sends SIGTERM to this process after its turns; `raw[slot]` is written as bytes. Returns (exit,
        receipt, runtime calls); the runtime commands, cwds, ledger rows, CC record and cleanup calls are kept on
        self."""
        real_module = profiles.module
        rows = health_rows or {}

        class Health:
            @staticmethod
            def health(selected, run=None):
                return [rows.get(slot, {"id": slot, "state": "stored", "validity": "valid"}) for slot in selected]

        calls = []
        with contextlib.ExitStack() as stack:
            state = state or Path(stack.enter_context(tempfile.TemporaryDirectory(dir="/var/tmp")))
            root, workspace = state / "pi-claude", state / "worktree"
            root.mkdir(exist_ok=True); workspace.mkdir(exist_ok=True)
            (root / "profile.json").write_text(json.dumps({"status": "trial", "pi_bin": "/fixture/pi",
                                                          "model": "fixture", "effort": "high", "roles": {}}))
            args = argparse.Namespace(profile="pi-claude", state_root=state, repository=state,
                                      role=None, print=True, prompt="fixture", timeout_seconds=1,
                                      ledger=ledger if ledger is not None else state / "ledger.jsonl",
                                      resume=resume(state, root) if resume else None)
            self.commands, self.cwds = [], []

            def runtime(command, **kwargs):
                if command[0] == "timeout":
                    slot = next(s for s in self.worker().DEFAULT_KEYS if s in command)
                    calls.append(slot)
                    self.commands.append(command)
                    self.cwds.append(kwargs["cwd"])
                    if slot in (raises or ()):
                        raise OSError("fixture")
                    if slot in (raw or {}):
                        Path(kwargs["stdout"].name).write_bytes(raw[slot])
                        return subprocess.CompletedProcess(command, 0)
                    if sessions and "--session-id" in command:
                        (root / "sessions").mkdir(exist_ok=True)
                        (root / "sessions" / ("fixture_" + command[command.index("--session-id") + 1] + ".jsonl")).touch()
                    turns = slot_outcomes.get(slot, "ok")
                    for turn in [turns] if isinstance(turns, (str, tuple)) else turns:
                        if turn == "inflight":
                            # A response that started streaming and never ended: no message_end, no usage reported.
                            partial = {"role": "assistant", "content": [], "stopReason": "stop",
                                       "usage": {"input": 9, "output": 3, "totalTokens": 12, "cost": {"total": 0.01}}}
                            for kind in ("message_start", "message_update"):
                                kwargs["stdout"].write(json.dumps({"type": kind, "message": partial}) + "\n")
                        elif turn == "ok":
                            pi_events(kwargs["stdout"], tokens=12, cost=0.5)
                        elif isinstance(turn, tuple):
                            pi_events(kwargs["stdout"], error=turn[0], tokens=turn[1], cost=0.25)
                        else:
                            pi_events(kwargs["stdout"], error=turn)
                    if slot in (sigterm or ()):
                        kwargs["stdout"].flush()
                        os.kill(os.getpid(), signal.SIGTERM)
                    end = (ends or {}).get(slot, 0)
                    if end == "watchdog":
                        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                    return subprocess.CompletedProcess(command, end)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(profiles, "module", side_effect=lambda name, path: Health if "key_health" in name
                                   else real_module(name, path)), \
                    mock.patch.object(profiles, "fresh_worktree", return_value=workspace) as worktree, \
                    mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture"), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-14T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}) as cleanup, \
                    redirect_stdout(io.StringIO()) as out:
                try:
                    code = profiles.launch(args)
                finally:
                    self.cleanup_calls, self.worktree_calls = cleanup.call_count, worktree.call_count
                    path = Path(args.ledger)
                    self.ledger_rows = ([json.loads(line) if line.startswith("{") else line
                                         for line in path.read_text().splitlines()] if path.is_file() else None)
            printed = json.loads(out.getvalue().strip().splitlines()[-1])
            self.receipt_path = Path(printed["receipt"])
            receipt = json.loads(self.receipt_path.read_text())
            self.record = Path(printed["record"]).read_text()
        return code, receipt, calls


class FillFirstSlotTests(PiLaunchFixture, unittest.TestCase):
    """ns-run's Anthropic slot choice (the command center's incident of 2026-10-14, 01:01:52Z): a researcher run on
    anthropic-api-4 was refused for exhausted credit because the profile chose by a no-token check, from a stale 4/3/2
    list, and never moved on. The order is the review worker's DEFAULT_KEYS, the no-token check only screens out an
    invalid or forbidden key, and a first call refused as credit-exhausted (the worker's classifier) moves the run to the
    next slot."""

    def test_an_exhausted_key_that_reports_valid_is_not_chosen_as_final(self):
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: CREDIT_400})
        self.assertEqual(calls, [order[0], order[1]])
        self.assertEqual(receipt["credential_loader_id"], order[1])
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], [order[0]])
        self.assertEqual(receipt["inference"]["usage"]["total_tokens"], 12)

    def test_every_exhausted_slot_is_passed_over_in_order(self):
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: CREDIT_400, order[1]: CREDIT_400.replace("400 ", "402 ", 1)})
        self.assertEqual(calls, [order[0], order[1], order[2]])
        self.assertEqual(receipt["credential_loader_id"], order[2])

    def test_the_last_exhausted_slot_is_recorded_when_no_slot_follows(self):
        # With no successor the last refused run's receipt stands, and it still names its own slot as refused.
        order = list(self.worker().DEFAULT_KEYS)
        code, receipt, calls = self.launch({slot: CREDIT_400 for slot in order})
        self.assertEqual(calls, order)
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], order)
        self.assertEqual(receipt["credential_loader_id"], order[-1])
        only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
        code, receipt, calls = self.launch({order[0]: CREDIT_400}, only_first)
        self.assertEqual(calls, [order[0]])
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], [order[0]])

    def test_a_timed_out_or_signalled_attempt_never_moves_to_another_slot(self):
        # A credit refusal already flushed to the log authorizes nothing once the attempt itself was cut short: the
        # outer watchdog, timeout's 124 and 137, the credential runner's 128+N, a signal on the direct child.
        order = self.worker().DEFAULT_KEYS
        for end, status in (("watchdog", 124), (124, 124), (137, 137), (143, 143), (-15, -15)):
            with self.subTest(end=end):
                code, receipt, calls = self.launch({order[0]: CREDIT_400}, ends={order[0]: end})
                self.assertEqual(calls, [order[0]])
                self.assertEqual((code, receipt["runtime_exit_code"]), (status, status))
                self.assertEqual(receipt["credential_loader_id"], order[0])
                self.assertEqual(receipt["credit_refused_slots"], [])
        # A native refusal that ended on its own still moves on: Pi exits 0, OpenCode 1.
        for end in (0, 1):
            with self.subTest(end=end):
                code, receipt, calls = self.launch({order[0]: CREDIT_400}, ends={order[0]: end})
                self.assertEqual(calls, [order[0], order[1]])

    def test_any_other_refusal_ends_the_run_on_its_slot(self):
        order = self.worker().DEFAULT_KEYS
        for refusal in ('401 {"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}',
                        '429 {"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}',
                        '400 {"type":"error","error":{"type":"invalid_request_error","message":"prompt is too long"}}'):
            with self.subTest(refusal=refusal[:3]):
                code, receipt, calls = self.launch({order[0]: refusal})
                self.assertEqual(calls, [order[0]])
                self.assertEqual(receipt["credit_refused_slots"], [])

    def test_the_no_token_check_screens_out_only_invalid_or_forbidden_keys(self):
        order = self.worker().DEFAULT_KEYS
        rows = {order[0]: {"id": order[0], "state": "stored", "validity": "invalid"},
                order[1]: {"id": order[1], "state": "missing"},
                order[2]: {"id": order[2], "state": "stored", "validity": "forbidden"},
                order[3]: {"id": order[3], "state": "stored", "validity": "rate_limited"}}
        code, receipt, calls = self.launch({}, rows)
        self.assertEqual(calls, [order[3]])

    def test_the_order_is_the_review_worker_default_keys(self):
        # One fill-first order for every Anthropic Console consumer: ns-run follows the review worker's DEFAULT_KEYS.
        self.assertEqual(profiles.fill_first_order(), tuple(self.worker().DEFAULT_KEYS))

    def test_first_call_refusal_reads_pi_and_opencode_events(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            with log.open("w") as handle:
                pi_events(handle, error=CREDIT_400)
            self.assertTrue(profiles.credit_refused(log, "pi"))
            with log.open("w") as handle:
                pi_events(handle, tokens=5)
            self.assertFalse(profiles.credit_refused(log, "pi"))
            for error, expected in (({"name": "APIError", "data": {"statusCode": 402, "message": "billing"}}, True),
                                    ({"message": CREDIT_400[4:]}, True),
                                    ({"name": "APIError", "data": {"statusCode": 401, "message": "invalid x-api-key"}}, False)):
                with self.subTest(error=str(error)[:40]):
                    log.write_text(json.dumps({"type": "error", "error": error}) + "\n")
                    self.assertEqual(profiles.credit_refused(log, "opencode"), expected)
            log.write_text(json.dumps({"type": "step_finish", "part": {"tokens": {"total": 3}}}) + "\n"
                           + json.dumps({"type": "error", "error": {"data": {"statusCode": 402}}}) + "\n")
            self.assertFalse(profiles.credit_refused(log, "opencode"))


class MidRunFailoverTests(PiLaunchFixture, unittest.TestCase):
    """A slot whose credit runs out MID-RUN (the command center's ruling of 2026-10-15, after two pi-claude researcher
    arms died at ~04:06Z when anthropic-api-3 ran out, losing $5.44 and $2.85 of billed work): the run continues the
    same pi session on the next funded slot, or stops resumable when none follows; every attempt is debited and settled
    in the API spend ledger under its slot id."""

    @staticmethod
    def session_and_prompt(command):
        at = command.index("--session-id")
        return command[at + 1], command[at + 2:]

    def test_credit_running_out_mid_run_continues_the_same_session_on_the_next_slot(self):
        order = self.worker().DEFAULT_KEYS
        for refusal in (CREDIT_STREAM, CREDIT_400):
            with self.subTest(refusal=refusal[:4]):
                code, receipt, calls = self.launch({order[0]: ["ok", (refusal, 186948)]})
                self.assertEqual((code, calls), (0, [order[0], order[1]]))
                (first, brief), (second, cont) = map(self.session_and_prompt, self.commands)
                self.assertEqual(first, second)
                self.assertEqual((brief, cont), (["fixture"], [profiles.CONTINUE_PROMPT]))
                self.assertEqual(receipt["resume"], {"status": "resumed", "reason": "credit_exhausted_mid_run",
                                                     "session_id": first, "from": order[0], "to": order[1],
                                                     "final_outcome": "ended"})
                self.assertEqual([a["outcome"] for a in receipt["attempts"]], ["credit_exhausted_mid_run", "ended"])
                self.assertEqual(receipt["credit_refused_slots"], [])
                self.assertEqual(receipt["credential_loader_id"], order[1])
                # The receipt holds the whole run: the failed attempt's billed usage stays in it.
                self.assertEqual(receipt["inference"]["usage"]["total_tokens"], 12 + 186948 + 12)
                self.assertEqual(receipt["inference"]["native_cost_usd"], 1.25)
                self.assertEqual(self.cleanup_calls, 1)

    def test_billed_work_without_a_session_file_stops_and_never_resends_the_brief(self):
        # The CC's P1 at e3dcee9d: the brief is never sent again onto a worktree that may hold the run's edits.
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_400, 40)]}, sessions=False)
        self.assertEqual((code, calls), (1, [order[0]]))
        self.assertEqual(receipt["resume"]["status"], "stopped_no_session")
        self.assertEqual(self.cleanup_calls, 0)
        # The CC's F3: no switch row for a failover that never happened.
        self.assertEqual([row["kind"] for row in self.ledger_rows], ["debit", "settle"])
        # The local review's P2 at 5bea71f9: with no slot left either, the stop is still not called resumable.
        only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
        code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_400, 40)]}, only_first, sessions=False)
        self.assertEqual((code, calls, receipt["resume"]["status"]), (1, [order[0]], "stopped_no_session"))

    def opencode_launch(self, events, status):
        """An opencode-claude print launch whose one attempt writes `events` and exits `status`. Returns (exit, receipt,
        ledger rows, runtime calls, choose_slot calls, cleanup calls)."""
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            root = state / "opencode-claude" / "roles/reviewer"
            root.mkdir(parents=True)
            workspace = state / "worktree"; workspace.mkdir()
            (root / "profile.json").write_text(json.dumps({"status": "trial", "model": "fixture", "effort": "high",
                "opencode_bin": "/fixture/opencode", "roles": {"evidence-reviewer": {"tools": ["read"]}}}))
            config = root / "config/opencode/opencode.json"
            config.parent.mkdir(parents=True); config.write_text('{"agent":{}}')
            calls = []

            def runtime(command, **kwargs):
                if command[0] == "timeout":
                    calls.append(command)
                    for event in events:
                        kwargs["stdout"].write(json.dumps(event) + "\n")
                    return subprocess.CompletedProcess(command, status)
                return subprocess.CompletedProcess(command, 0)
            args = argparse.Namespace(profile="opencode-claude", state_root=state, repository=state,
                                      role="evidence-reviewer", print=True, prompt="fixture", timeout_seconds=1,
                                      ledger=state / "ledger.jsonl")
            with mock.patch.dict(os.environ, {"PWD": str(state)}), \
                    mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                    mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture"), \
                    mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4") as choose, \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-15T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}) as cleanup, \
                    redirect_stdout(io.StringIO()) as out:
                code = profiles.launch(args)
            receipt = json.loads(Path(json.loads(out.getvalue().strip().splitlines()[-1])["receipt"]).read_text())
            rows = [json.loads(line) for line in (state / "ledger.jsonl").read_text().splitlines()]
        return code, receipt, rows, calls, choose.call_count, cleanup.call_count

    def test_an_ordinary_error_inside_a_response_settles_as_unknown_spend(self):
        # The GPT read and the local review at 64f41af3/5bea71f9: a step that started and never finished, ended by a
        # non-credit API error (OpenCode exits 1: anomalyco/opencode@53d1eabb run.ts:842), left its usage unreported;
        # it was settled as known spend because the outcome was "ended".
        step = {"type": "step_finish", "sessionID": "ses_fixture1", "part": {"tokens": {"total": 9}, "cost": 0.5}}
        start = {"type": "step_start", "sessionID": "ses_fixture1", "part": {}}
        error = {"type": "error", "sessionID": "ses_fixture1",
                 "error": {"name": "APIError", "data": {"statusCode": 500, "message": "overloaded"}}}
        code, receipt, rows, calls, chosen, cleaned = self.opencode_launch([step, start, error], 1)
        settle = rows[-1]
        self.assertEqual((settle["outcome"], settle["attempt_outcome"], settle["actual_usd"],
                          settle["measured_lower_bound_usd"]), ("unknown", "ended", profiles.ATTEMPT_RESERVE_USD, 0.5))
        self.assertFalse(receipt["attempts"][0]["spend_known"])
        # Finished before the error: the measured amount is the whole cost.
        code, receipt, rows, calls, chosen, cleaned = self.opencode_launch([step, error], 1)
        self.assertEqual((rows[-1]["outcome"], rows[-1]["actual_usd"]), ("ended", 0.5))
        self.assertTrue(receipt["attempts"][0]["spend_known"])

    def test_opencode_mid_run_exhaustion_stops_on_its_slot_and_is_not_called_resumable(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            root = state / "opencode-claude" / "roles/reviewer"
            root.mkdir(parents=True)
            workspace = state / "worktree"; workspace.mkdir()
            (root / "profile.json").write_text(json.dumps({"status": "trial", "model": "fixture", "effort": "high",
                "opencode_bin": "/fixture/opencode", "roles": {"evidence-reviewer": {"tools": ["read"]}}}))
            config = root / "config/opencode/opencode.json"
            config.parent.mkdir(parents=True); config.write_text('{"agent":{}}')
            calls = []

            def runtime(command, **kwargs):
                if command[0] == "timeout":
                    calls.append(command)
                    kwargs["stdout"].write(json.dumps({"type": "step_finish", "sessionID": "ses_fixture1",
                                                       "part": {"tokens": {"total": 9}, "cost": 0.5}}) + "\n")
                    kwargs["stdout"].write(json.dumps({"type": "error", "sessionID": "ses_fixture1", "error": {
                        "name": "APIError", "data": {"statusCode": 402, "message": "billing"}}}) + "\n")
                    return subprocess.CompletedProcess(command, 1)
                return subprocess.CompletedProcess(command, 0)
            args = argparse.Namespace(profile="opencode-claude", state_root=state, repository=state,
                                      role="evidence-reviewer", print=True, prompt="fixture", timeout_seconds=1,
                                      ledger=state / "ledger.jsonl")
            with mock.patch.dict(os.environ, {"PWD": str(state)}), \
                    mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                    mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture"), \
                    mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4") as choose, \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-15T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}) as cleanup, \
                    redirect_stdout(io.StringIO()) as out:
                code = profiles.launch(args)
            receipt = json.loads(Path(json.loads(out.getvalue().strip().splitlines()[-1])["receipt"]).read_text())
            rows = [json.loads(line) for line in (state / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual((code, len(calls), choose.call_count, cleanup.call_count), (1, 1, 1, 0))
        self.assertEqual({k: receipt["resume"][k] for k in ("status", "session_id", "credential_loader_id")},
                         {"status": "stopped_not_resumable", "session_id": "ses_fixture1",
                          "credential_loader_id": "anthropic-api-4"})
        self.assertEqual([(row["kind"], row["key"], row.get("actual_usd"), row.get("outcome")) for row in rows],
                         [("debit", "anthropic-api-4", None, None),
                          ("settle", "anthropic-api-4", 0.5, "credit_exhausted_mid_run")])

    def test_a_resumed_session_is_never_restarted_from_the_brief(self):
        # The local review's P1 at e3dcee9d: credit runs out mid-run on the first slot, then the next slot refuses the
        # continuation's FIRST call. The session still holds the billed work, so the run continues it on a third slot.
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)], order[1]: CREDIT_400})
        self.assertEqual((code, calls), (0, [order[0], order[1], order[2]]))
        sessions, prompts = zip(*map(self.session_and_prompt, self.commands))
        self.assertEqual(len(set(sessions)), 1)
        self.assertEqual(list(prompts), [["fixture"], [profiles.CONTINUE_PROMPT], [profiles.CONTINUE_PROMPT]])
        self.assertEqual({k: receipt["resume"][k] for k in ("status", "from", "to", "final_outcome")},
                         {"status": "resumed", "from": order[0], "to": order[2], "final_outcome": "ended"})
        self.assertEqual([row["reason"] for row in self.ledger_rows if row["kind"] == "switch"],
                         ["credit_exhausted (mid_run)", "credit_exhausted (first_call)"])
        # With no third slot, the run stops resumable instead of ending 0 on a refused continuation.
        two = {slot: {"id": slot, "state": "missing"} for slot in order[2:]}
        code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)], order[1]: CREDIT_400}, two)
        self.assertEqual((code, calls), (75, [order[0], order[1]]))
        self.assertEqual({k: receipt["resume"][k] for k in ("status", "from", "credential_loader_id")},
                         {"status": "stopped_resumable", "from": order[0], "credential_loader_id": order[1]})
        self.assertEqual(self.cleanup_calls, 0)

    def test_an_attempt_cut_short_inside_a_response_settles_as_unknown_spend(self):
        # The local review's P2 at e3dcee9d: killed while a paid response streams, the attempt reported no usage for
        # it; settling the measured amount would publish an under-count as actual spend.
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: ["ok", "inflight"]}, ends={order[0]: 137})
        settle = [row for row in self.ledger_rows if row["kind"] == "settle"][-1]
        self.assertEqual((settle["outcome"], settle["attempt_outcome"]), ("unknown", "cut_short"))
        self.assertEqual((settle["actual_usd"], settle["measured_lower_bound_usd"]),
                         (profiles.ATTEMPT_RESERVE_USD, 0.5))
        self.assertFalse(receipt["attempts"][0]["spend_known"])
        # Cut short between responses, the measured amount is the whole cost.
        code, receipt, calls = self.launch({order[0]: ["ok"]}, ends={order[0]: 137})
        settle = [row for row in self.ledger_rows if row["kind"] == "settle"][-1]
        self.assertEqual((settle["outcome"], settle["actual_usd"]), ("cut_short", 0.5))
        self.assertTrue(receipt["attempts"][0]["spend_known"])

    def test_resume_continues_a_stopped_run_in_its_kept_worktree_and_session(self):
        # The CC's P2 at e3dcee9d: exit 75 must have a consumer. --resume <receipt> continues the same pi session in
        # the kept worktree (pi resolves a session per cwd: session-manager.ts:1874-1886), then cleans it up.
        order = self.worker().DEFAULT_KEYS
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
            code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)]}, only_first, state=state)
            self.assertEqual(code, 75)
            session, stopped = receipt["resume"]["session_id"], self.receipt_path
            kept = Path(receipt["resume"]["retained_worktree"])
            fake = {"workspace": kept, "session_id": session, "receipt_run": stopped.parent.name, "from": order[0]}
            with mock.patch.object(profiles, "resumable_receipt", return_value=fake) as check:
                code, receipt, calls = self.launch({}, resume=lambda state, root: stopped, state=state)
            self.assertEqual(check.call_args.args[0], stopped)
        self.assertEqual((code, calls, self.worktree_calls, self.cleanup_calls), (0, [order[0]], 0, 1))
        self.assertEqual(self.cwds, [kept])
        self.assertEqual(self.session_and_prompt(self.commands[0]), (session, [profiles.CONTINUE_PROMPT]))
        self.assertEqual({k: receipt["resume"][k] for k in ("status", "reason", "session_id", "final_outcome")},
                         {"status": "resumed", "reason": "resumed_from_receipt", "session_id": session,
                          "final_outcome": "ended"})
        self.assertEqual(receipt["resumed_from"], stopped.parent.name)

    def test_resume_refuses_anything_but_a_resumable_stop_of_this_profile(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory) / "pi-claude"
            (root / "runs" / "r1").mkdir(parents=True)
            receipt = root / "runs" / "r1" / "receipt.json"
            outside = Path(directory) / "receipt.json"
            for document, path, why in (
                    ({"profile": "pi-claude", "role": None, "resume": {"status": "resumed"}}, receipt, "resumable stop"),
                    ({"profile": "pi-gpt", "role": None, "resume": {"status": "stopped_resumable"}}, receipt,
                     "resumable stop"),
                    ({"profile": "pi-claude", "role": None, "resume": {"status": "stopped_resumable"}}, outside, "runs"),
                    ({"profile": "pi-claude", "role": None, "resume": {"status": "stopped_resumable",
                      "retained_worktree": directory, "session_id": "x"}}, receipt, "worktree")):
                with self.subTest(why=why, path=path.name):
                    path.write_text(json.dumps(document))
                    with self.assertRaisesRegex(profiles.ProfileError, "resume refused"):
                        profiles.resumable_receipt(path, root, Path(directory), "pi-claude", None)

    def test_resume_accepts_a_kept_ns_run_worktree_of_this_repository(self):
        # The positive control on real git: the kept worktree must share the repository's common dir and sit on an
        # ns-run branch of this profile, and the session file must exist.
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            base = Path(directory)
            repository, kept, root = base / "repo", base / "kept", base / "pi-claude"
            git = lambda *argv: subprocess.run(["git", *argv], check=True, capture_output=True)
            git("init", "-q", "-b", "main", str(repository))
            git("-C", str(repository), "-c", "user.name=fixture", "-c", "user.email=fixture@users.noreply.github.com",
                "commit", "-q", "--allow-empty", "-m", "base")
            git("-C", str(repository), "worktree", "add", "-q", "-b", "runtime/pi-claude-0123456789ab", str(kept))
            (root / "runs" / "r1").mkdir(parents=True)
            (root / "sessions").mkdir()
            (root / "sessions" / "2026-10-15T00-00-00-000Z_feedface.jsonl").write_text("{}\n")
            receipt = root / "runs" / "r1" / "receipt.json"
            stop = {"status": "stopped_resumable", "retained_worktree": str(kept), "session_id": "feedface",
                    "credential_loader_id": "anthropic-api-4", "from": "anthropic-api-4"}
            receipt.write_text(json.dumps({"profile": "pi-claude", "role": None, "resume": stop}))
            found = profiles.resumable_receipt(receipt, root, repository, "pi-claude", None)
            self.assertEqual((found["workspace"], found["session_id"], found["receipt_run"]), (kept, "feedface", "r1"))
            for change, why in (({"session_id": "missing"}, "session"),):
                receipt.write_text(json.dumps({"profile": "pi-claude", "role": None, "resume": {**stop, **change}}))
                with self.subTest(why=why), self.assertRaisesRegex(profiles.ProfileError, "resume refused"):
                    profiles.resumable_receipt(receipt, root, repository, "pi-claude", None)
            # The CC's F4: a receipt that was resumed once is refused.
            receipt.write_text(json.dumps({"profile": "pi-claude", "role": None, "resume": stop}))
            (receipt.parent / "resumed-by.json").write_text("{}\n")
            with self.assertRaisesRegex(profiles.ProfileError, "already resumed"):
                profiles.resumable_receipt(receipt, root, repository, "pi-claude", None)
            (receipt.parent / "resumed-by.json").unlink()
            git("-C", str(kept), "switch", "-q", "-c", "other")
            receipt.write_text(json.dumps({"profile": "pi-claude", "role": None, "resume": stop}))
            with self.assertRaisesRegex(profiles.ProfileError, "worktree"):
                profiles.resumable_receipt(receipt, root, repository, "pi-claude", None)

    def test_the_run_command_takes_resume_without_a_brief_and_needs_one_without_it(self):
        with mock.patch.object(profiles, "launch", return_value=0) as launched:
            self.assertEqual(profiles.main(["run", "--state-root", "/x", "--repository", "/x", "--resume",
                                            "/x/runs/r1/receipt.json", "pi-claude", "researcher"]), 0)
        args = launched.call_args.args[0]
        self.assertEqual((args.prompt, args.resume, args.role, args.print),
                         (None, Path("/x/runs/r1/receipt.json"), "stack-researcher", True))
        with mock.patch.object(profiles, "launch", return_value=0) as launched, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(profiles.main(["run", "--state-root", "/x", "--repository", "/x", "pi-claude",
                                            "researcher"]), 2)
        launched.assert_not_called()

    def test_a_receipt_is_resumed_only_once(self):
        # The CC's F4 at 5bea71f9: the first --resume claims the receipt, so a second one refuses.
        order = self.worker().DEFAULT_KEYS
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
            code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)]}, only_first, state=state)
            stopped = self.receipt_path
            fake = {"workspace": Path(receipt["resume"]["retained_worktree"]), "session_id": receipt["resume"]["session_id"],
                    "receipt_run": stopped.parent.name, "from": order[0]}
            with mock.patch.object(profiles, "resumable_receipt", return_value=fake):
                code, receipt, calls = self.launch({}, resume=lambda state, root: stopped, state=state)
                self.assertEqual(code, 0)
                self.assertTrue((stopped.parent / "resumed-by.json").is_file())
                with self.assertRaisesRegex(profiles.ProfileError, "already resumed"):
                    self.launch({}, resume=lambda state, root: stopped, state=state)

    def test_a_failed_resume_preflight_leaves_the_receipt_resumable(self):
        # The local review's P2 at 64f41af3: with every slot unusable, --resume starts no attempt; it must not consume
        # the receipt, so a retry once a slot is usable continues it.
        order = self.worker().DEFAULT_KEYS
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
            code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)]}, only_first, state=state)
            stopped = self.receipt_path
            fake = {"workspace": Path(receipt["resume"]["retained_worktree"]), "session_id": receipt["resume"]["session_id"],
                    "receipt_run": stopped.parent.name, "from": order[0]}
            none_usable = {slot: {"id": slot, "state": "missing"} for slot in order}
            with mock.patch.object(profiles, "resumable_receipt", return_value=fake):
                with self.assertRaisesRegex(profiles.ProfileError, "no usable"):
                    self.launch({}, none_usable, resume=lambda state, root: stopped, state=state)
                self.assertFalse((stopped.parent / "resumed-by.json").exists())
                code, receipt, calls = self.launch({}, resume=lambda state, root: stopped, state=state)
            self.assertEqual((code, calls), (0, [order[0]]))
            self.assertTrue((stopped.parent / "resumed-by.json").is_file())

    def test_no_ledger_row_carries_an_absolute_path(self):
        # The CC's F1 at 5bea71f9: ledger rows are quoted into public records; no value may be a private path.
        order = self.worker().DEFAULT_KEYS
        values = []

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                values.append(value)
        self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)]})
        for row in self.ledger_rows:
            walk(row)
        home = str(Path.home())
        offending = [value for value in values if value.startswith("/") or value.startswith(home) or "/home/" in value]
        self.assertEqual(offending, [])
        self.assertTrue(any(row.get("detail", {}).get("run_dir") for row in self.ledger_rows))

    def test_a_malformed_ledger_is_refused_as_unreadable(self):
        # The CC's F2 at 5bea71f9: the worker's LedgerError must be caught as the class its Ledger raised.
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            ledger = Path(directory) / "ledger.jsonl"
            ledger.write_text("not json\n")
            with self.assertRaisesRegex(profiles.ProfileError, "unreadable"):
                self.launch({}, ledger=ledger)
            self.assertEqual((self.commands, self.worktree_calls), ([], 0))

    def test_sigterm_during_an_attempt_settles_it_before_ns_run_ends(self):
        # The CC's P3: a terminated ns-run must not leave its debit open.
        order = self.worker().DEFAULT_KEYS
        before = signal.getsignal(signal.SIGTERM)  # a test runner may have its own
        with self.assertRaises(SystemExit) as stop:
            self.launch({order[0]: ["ok", "inflight"]}, sigterm={order[0]})
        self.assertEqual(stop.exception.code, 128 + signal.SIGTERM)
        self.assertEqual([(row["kind"], row.get("outcome")) for row in self.ledger_rows],
                         [("debit", None), ("settle", "unknown")])
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_an_orphaned_debit_is_settled_as_unknown_by_the_next_launch(self):
        # The CC's P3: SIGKILL runs no handler, so the next launch settles a debit whose ns-run process is gone.
        order = self.worker().DEFAULT_KEYS
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            ledger = state / "ledger.jsonl"
            (state / "pi-claude/runs/r0").mkdir(parents=True)
            with (state / "pi-claude/runs/r0/events.jsonl").open("w") as handle:
                pi_events(handle, tokens=3, cost=0.75)
            live = {"pid": os.getpid(), "pid_start": profiles.process_start(os.getpid()), "run_dir": "pi-claude/runs/r0"}
            gone = {"pid": os.getpid(), "pid_start": "-1", "run_dir": "pi-claude/runs/r0", "runtime": "pi"}
            ledger.write_text("".join(json.dumps({"kind": "debit", "key": order[1], "workload": "NSRUN", "ref": ref,
                                                  "max_usd": 25.0, "detail": detail}) + "\n"
                                      for ref, detail in (("NSRUN:live", live), ("NSRUN:gone", gone))))
            self.launch({}, ledger=ledger, state=state)
        settled = {row["ref"]: row for row in self.ledger_rows if row["kind"] == "settle"}
        self.assertNotIn("NSRUN:live", settled)
        self.assertEqual((settled["NSRUN:gone"]["outcome"], settled["NSRUN:gone"]["actual_usd"],
                          settled["NSRUN:gone"]["measured_lower_bound_usd"]), ("unknown", 25.0, 0.75))

    def test_an_unreadable_log_or_null_usage_never_skips_the_settle(self):
        # The CC's P3: the settle sits in a finally that a decode error or a null usage cannot skip.
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({}, raw={order[0]: b"\xff\xfe not utf-8\n"})
        self.assertEqual([(row["kind"], row.get("outcome")) for row in self.ledger_rows],
                         [("debit", None), ("settle", "unknown")])
        self.assertEqual(code, 2)  # the CC's F5: a run whose log cannot be read never reports success
        null = json.dumps({"type": "message_end", "message": {"role": "assistant", "usage": None, "content": [],
                                                              "stopReason": "stop"}}).encode() + b"\n"
        code, receipt, calls = self.launch({}, raw={order[0]: null})
        self.assertEqual([(row["kind"], row.get("outcome"), row.get("actual_usd")) for row in self.ledger_rows],
                         [("debit", None, None), ("settle", "ended", 0.0)])

    def test_an_empty_or_homeless_ledger_is_refused_and_nothing_is_created(self):
        # The CC's P3: --ledger "" would name the current directory; a missing directory would hide the spend.
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                profiles.parser().parse_args(["run", "--state-root", "/x", "--repository", "/x", "--ledger", "",
                                              "pi-claude", "researcher", "brief.md"])
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            homeless = Path(directory) / "missing" / "ledger.jsonl"
            with self.assertRaisesRegex(profiles.ProfileError, "directory missing"):
                self.launch({}, ledger=homeless)
            self.assertFalse(homeless.parent.exists())
            self.assertEqual((self.commands, self.worktree_calls), ([], 0))

    def test_a_first_call_refusal_starts_a_fresh_session_with_the_brief(self):
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: CREDIT_400})
        (first, brief), (second, again) = map(self.session_and_prompt, self.commands)
        self.assertNotEqual(first, second)
        self.assertEqual((brief, again), (["fixture"], ["fixture"]))
        self.assertIsNone(receipt["resume"])
        self.assertEqual([a["outcome"] for a in receipt["attempts"]], ["first_call_refused", "ended"])

    def test_mid_run_exhaustion_with_no_funded_slot_left_stops_resumable(self):
        order = self.worker().DEFAULT_KEYS
        only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
        code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_STREAM, 40)]}, only_first)
        self.assertEqual((code, calls), (75, [order[0]]))
        session, _ = self.session_and_prompt(self.commands[0])
        self.assertEqual({k: receipt["resume"][k] for k in ("status", "session_id", "credential_loader_id")},
                         {"status": "stopped_resumable", "session_id": session, "credential_loader_id": order[0]})
        self.assertTrue(receipt["resume"]["retained_worktree"])
        self.assertEqual(self.cleanup_calls, 0)  # the session's worktree is kept for the resume
        self.assertIn("Stopped resumable", self.record)
        self.assertNotIn("No completed assistant text.", self.record)

    def test_a_cut_short_attempt_never_continues_even_after_a_mid_run_refusal(self):
        order = self.worker().DEFAULT_KEYS
        for end in ("watchdog", 124, 137, -15):
            with self.subTest(end=end):
                code, receipt, calls = self.launch({order[0]: ["ok", (CREDIT_400, 40)]}, ends={order[0]: end})
                self.assertEqual(calls, [order[0]])
                self.assertIsNone(receipt["resume"])
                self.assertEqual(receipt["attempts"][0]["outcome"], "cut_short")

    def test_any_other_mid_run_refusal_ends_the_run_on_its_slot(self):
        order = self.worker().DEFAULT_KEYS
        rate = '429 {"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}'
        code, receipt, calls = self.launch({order[0]: ["ok", (rate, 40)]})
        self.assertEqual(calls, [order[0]])
        self.assertIsNone(receipt["resume"])

    def test_mid_run_refusal_reads_both_pi_shapes_and_opencode(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            for turns, expected in ((["ok", (CREDIT_STREAM, 9)], True), (["ok", CREDIT_400], True),
                                    ([(CREDIT_STREAM, 9)], True), ([CREDIT_400], False), (["ok"], False),
                                    ([(CREDIT_STREAM, 9), "ok"], False)):
                with self.subTest(turns=[t if isinstance(t, str) and t == "ok" else "refused" for t in turns]):
                    with log.open("w") as handle:
                        for turn in turns:
                            if turn == "ok":
                                pi_events(handle, tokens=5)
                            elif isinstance(turn, tuple):
                                pi_events(handle, error=turn[0], tokens=turn[1])
                            else:
                                pi_events(handle, error=turn)
                    self.assertEqual(profiles.credit_exhausted_mid_run(log, "pi"), expected)
            step = json.dumps({"type": "step_finish", "part": {"tokens": {"total": 3}}}) + "\n"
            refused = json.dumps({"type": "error", "error": {"data": {"statusCode": 402}}}) + "\n"
            for text, expected, outcome in ((step + refused, True, "credit_exhausted_mid_run"),
                                            (refused, False, "first_call_refused"),
                                            (step + refused + step, False, "ended")):
                with self.subTest(opencode=expected):
                    log.write_text(text)
                    self.assertEqual(profiles.credit_exhausted_mid_run(log, "opencode"), expected)
                    self.assertEqual(profiles.attempt_outcome(log, "opencode", "claude", 1), outcome)

    def test_each_attempt_is_debited_and_settled_under_its_slot_with_a_switch_on_failover(self):
        order = self.worker().DEFAULT_KEYS
        self.launch({order[0]: ["ok", (CREDIT_STREAM, 186948)]})
        rows = self.ledger_rows
        self.assertEqual([row["kind"] for row in rows], ["debit", "settle", "switch", "debit", "settle"])
        debit, settle, switch, _, last = rows
        self.assertEqual((debit["key"], settle["key"], last["key"]), (order[0], order[0], order[1]))
        self.assertEqual((debit["workload"], debit["max_usd"]), ("NSRUN", profiles.ATTEMPT_RESERVE_USD))
        self.assertEqual(settle["ref"], debit["ref"])
        self.assertEqual((settle["actual_usd"], settle["requests"], settle["outcome"]),
                         (0.75, 2, "credit_exhausted_mid_run"))
        self.assertEqual(settle["tokens"], {"fixture": {"input": 12 + 186948, "output": 0, "cache_read": 0,
                                                        "cache_write": 0}})
        self.assertEqual((last["actual_usd"], last["outcome"]), (0.5, "ended"))
        self.assertEqual((switch["from"], switch["to"], switch["reason"]),
                         (order[0], order[1], "credit_exhausted (mid_run)"))
        # A row names the slot, never a key value or the variable that carries it.
        text = json.dumps(rows)
        self.assertNotIn("ANTHROPIC_API_KEY", text)
        self.assertNotRegex(text, r"sk-ant-")
        self.launch({order[0]: CREDIT_400})
        self.assertEqual(self.ledger_rows[2]["reason"], "credit_exhausted (first_call)")
        self.assertEqual(self.ledger_rows[1]["actual_usd"], 0)

    def test_an_attempt_that_raises_is_still_settled(self):
        order = self.worker().DEFAULT_KEYS
        with self.assertRaises(OSError):
            self.launch({}, raises={order[0]})
        self.assertEqual([(row["kind"], row.get("outcome")) for row in self.ledger_rows],
                         [("debit", None), ("settle", "error")])

    def test_no_ledger_or_an_unwritable_one_refuses_before_any_key_is_loaded(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            blocker = Path(directory) / "file"
            blocker.write_text("")
            for ledger in ("", blocker / "ledger.jsonl"):
                with self.subTest(ledger=str(ledger)[-12:]):
                    with self.assertRaisesRegex(profiles.ProfileError, "ledger"):
                        self.launch({}, ledger=ledger)
                    self.assertEqual((self.commands, self.worktree_calls), ([], 0))


class GatewayPortBindingTests(unittest.TestCase):
    def test_omniroute_template_matches_new_wsl_gateway_record(self):
        source = ROOT / "adoption/new-wsl/client-config-map.json"
        records = json.loads(source.read_text())["entries"]
        records = [row for row in records if row.get("owner") == "OmniRoute"
                   and "gateway listens on 21128" in row.get("source", "")]
        self.assertEqual(len(records), 1, "the recorded live gateway must have one source")
        rendered = tomllib.loads((ROOT / "adoption/templates/codex.omniroute.config.toml").read_text())
        self.assertEqual(rendered["model_providers"]["omniroute"]["base_url"],
                         "http://127.0.0.1:21128/v1")


class RuntimeInvokeTrackerTests(unittest.TestCase):
    def test_pi_completed_skill_and_mcp_calls_reach_existing_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "pi.jsonl"
            records = [
                {"type": "session", "id": "fixture-pi-session"},
                {"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "read",
                 "args": {"path": "/fixture/.agents/skills/codebase-design/SKILL.md"}},
                {"type": "tool_execution_end", "toolCallId": "call-1", "toolName": "read",
                 "isError": False},
                {"type": "tool_execution_start", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "args": {}},
                {"type": "tool_execution_end", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "isError": False},
            ]
            log.write_text("\n".join(json.dumps(row) for row in records) + "\n")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools/skill-usage/skill_usage.py"),
                 "--runtime-log", "pi", str(log), "--json"],
                cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            measured = json.loads(result.stdout)["runtimes"]["pi"]
            self.assertEqual(measured["sessions_measured"], 1)
            self.assertEqual(measured["successful_skill_uses"], {"codebase-design": 1})
            self.assertEqual(measured["successful_mcp_calls"], {"headroom": 1})
            self.assertNotIn("/fixture/", result.stdout)


class NativeProfileGenerationTests(unittest.TestCase):
    def setUp(self):
        # Renderer/command contracts use controlled fixture binaries. Actual
        # absent/wrong/native version admission is covered without this stub
        # by test_runtime_profile_readiness and the installed-CLI module.
        self.version_patch = mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture-version")
        self.version_patch.start()
        self.addCleanup(self.version_patch.stop)
    def test_escaping_links_are_refused_in_worktree_and_selected_vendor_roots(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            workspace, vendor, primary = [root / name for name in ("worktree", "vendor", "primary")]
            for path in (workspace, vendor, primary):
                path.mkdir()
            outside = primary / "private.txt"; outside.write_text("synthetic outside")
            owned = workspace / "owned.txt"; owned.write_text("synthetic owned")
            (workspace / "safe.txt").symlink_to(owned)
            profiles.check_read_links([workspace, vendor])
            for base, target in ((workspace, outside), (workspace, primary), (vendor, outside)):
                with self.subTest(base=base.name, directory=target.is_dir()):
                    alias = base / "escape"
                    alias.symlink_to(target, target_is_directory=target.is_dir())
                    with self.assertRaisesRegex(profiles.ProfileError, "escaping or unresolved read link"):
                        profiles.check_read_links([workspace, vendor])
                    alias.unlink()
            cyclic=workspace/'cycle';cyclic.symlink_to(cyclic)
            with self.assertRaises(profiles.ProfileError):profiles.check_read_links([workspace,vendor])
            cyclic.unlink()
            (workspace / "broken").symlink_to(primary / "missing")
            with self.assertRaises(profiles.ProfileError):
                profiles.check_read_links([workspace, vendor])

    def test_opencode_launch_binds_vendor_session_directory_on_both_routes(self):
        for route in ("gpt", "claude"):
            for headless in (True, False):
                with self.subTest(route=route, headless=headless), tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
                    state = Path(directory)
                    profile = "opencode-" + route
                    root = state / profile / "roles/reviewer"
                    root.mkdir(parents=True)
                    workspace = state / "worktree"; workspace.mkdir()
                    (root / "profile.json").write_text(json.dumps({"status": "trial", "model": "fixture",
                        "effort": "high", "opencode_bin": "/fixture/opencode",
                        "roles": {"evidence-reviewer": {"tools": ["read"]}}}))
                    config = root / "config/opencode/opencode.json"
                    config.parent.mkdir(parents=True); config.write_text('{"agent":{}}')
                    observed = []
                    def runtime(command, **kwargs):
                        if "/fixture/opencode" in command or command[0] in ("script", sys.executable, "timeout"):
                            observed.append((command, kwargs))
                        if command[0] == "/fixture/opencode" and "session" in command:
                            kwargs["stdout"].write("[]")
                        return subprocess.CompletedProcess(command, 0)
                    args = argparse.Namespace(profile=profile, state_root=state, repository=state,
                        role="evidence-reviewer", print=headless, prompt="fixture", timeout_seconds=1,
                        ledger=state / "ledger.jsonl")
                    with mock.patch.dict(os.environ, {"PWD": str(state / "primary"),
                                                       "OPENCODE_DISABLE_PROJECT_CONFIG": "1"}), \
                            mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                            mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                            mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4"), \
                            mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                            mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                            mock.patch.object(profiles, "utc", return_value="2026-10-12T00:00:00Z"), \
                            mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}), \
                            redirect_stdout(io.StringIO()):
                        self.assertEqual(profiles.launch(args), 0)
                    command, kwargs = observed[0]
                    self.assertEqual(kwargs["cwd"], workspace)
                    if route == "claude":
                        self.assertIn("PWD=" + str(workspace), command)
                        self.assertIn("OPENCODE_DISABLE_PROJECT_CONFIG=1", command)
                    else:
                        self.assertEqual(kwargs["env"]["PWD"], str(workspace))
                        self.assertEqual(kwargs["env"]["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
                    if headless:
                        start = command.index("/fixture/opencode")
                        self.assertEqual(command[start + 1:start + 4], ["run", "--dir", str(workspace)])

    def test_selected_vendor_skills_read_with_pinned_native_permission_evaluator(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("native Node permission evaluator unavailable")
        # The exact vendor functions are a test fixture, never deployed by the
        # profile. Source paths/pin are in the fixture header. Node24 matches
        # the installed client; do not replace native last-match semantics.
        javascript = r'''
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { stripTypeScriptTypes } = require('node:module');
let input = '';
process.stdin.on('data', value => input += value);
process.stdin.on('end', () => {
  const data = JSON.parse(input);
  const ts = fs.readFileSync(data.fixture, 'utf8').replaceAll('export ', '');
  const native = new Function('os', stripTypeScriptTypes(ts, {mode:'strip'})
    + '; const Wildcard={match}; return {evaluate,fromConfig,merge,sanitize,disabled};')(os);
  const packageRoot = path.join(data.root, 'cache/opencode/packages', native.sanitize(data.plugin), 'node_modules/superpowers');
  const outputs = {};
  for (const [name, agent] of Object.entries(data.config.agent)) {
    if (!agent.permission) continue;
    const rules = native.merge(native.fromConfig({'*':'allow',external_directory:{'*':'ask',[path.join(packageRoot,'skills/*')]:'allow'}}), native.fromConfig(agent.permission));
    outputs[name] = {
      selected: native.evaluate('external_directory',path.join(packageRoot,'skills/verification-before-completion/*'),rules).action,
      unselected: native.evaluate('external_directory',path.join(packageRoot,'skills/test-driven-development/*'),rules).action,
      unrelated: native.evaluate('external_directory',path.join(data.home,'unrelated/*'),rules).action,
      canonical: native.evaluate('external_directory',path.join(data.home,'.agents/skills/find-skills/*'),rules).action,
      nativeSkill: native.evaluate('skill','verification-before-completion',rules).action,
      unrelatedSkill: native.evaluate('skill','unrelated-unknown-skill',rules).action,
      skillHidden: native.disabled(['skill'],rules).has('skill'),
      // skill/index.ts:310-314 uses precisely this native evaluate filter.
      listed: data.inventory.filter(skill=>native.evaluate('skill',skill,rules).action!=='deny').sort(),
    };
  }
  console.log(JSON.stringify(outputs));
});
'''
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            servers = {"context-mode": {"type": "stdio", "command": "/fixture/mcp"}}
            with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                    mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                profiles.render("opencode-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state,
                                role_scope="reviewer")
            role_root = state / "opencode-gpt/roles/reviewer"
            config = json.loads((role_root / "config/opencode/opencode.json").read_text())
            payload = {"config": config, "root": str(role_root), "home": str(state),
                       "plugin": "superpowers@git+https://github.com/obra/superpowers.git#" + profiles.SUPERPOWERS,
                       "fixture": str(ROOT / "tests/fixtures/opencode-permission-53d1eabb.ts")}
            managed = {s["name"] for s in json.loads((ROOT / "adoption/skills/manifest.json").read_text())["skills"]
                       if s.get("status") != "held" and not s.get("native_plugin")
                       and s.get("agents") != ["claude-code"]}
            payload["inventory"] = sorted(managed | set(profiles.SUPERPOWERS_SKILLS)
                                           | {"context-mode", "unrelated-unknown-skill"})
            result = subprocess.run([node, "-e", javascript], input=json.dumps(payload), text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs = json.loads(result.stdout)
            self.assertEqual(set(outputs), set(profiles.ROLES))
            for role, outcome in outputs.items():
                with self.subTest(role=role):
                    selected_role = role in {"evidence-reviewer", "security-reviewer"}
                    self.assertFalse(outcome.pop("skillHidden"))
                    expected = managed | {"using-superpowers"}
                    for role_name, skills in profiles.ROLE_SCOPES.values():
                        if role_name == role:
                            expected |= set(skills)
                    if role == "isolated-builder":
                        expected.add("context-mode")
                    self.assertEqual(outcome.pop("listed"), sorted(expected))
                    self.assertEqual(outcome, {"selected": "allow" if selected_role else "deny",
                        "unselected": "allow" if role == "isolated-builder" else "deny", "unrelated": "deny",
                        "canonical": "deny", "nativeSkill": "allow" if selected_role else "deny",
                        "unrelatedSkill": "deny"})

    def test_run_permissions_deny_primary_checkout_reads_with_pinned_evaluator(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("native Node permission evaluator unavailable")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            base = Path(directory)
            root, worktree = base / "profile", base / "worktree"
            root.mkdir(); worktree.mkdir()
            vendor = root / "vendor/selected"
            config = {"agent": {"evidence-reviewer": {"permission": {
                "*": "deny", "read": {"*": "allow", "mcp:*": "deny"},
                "external_directory": {"*": "deny", str(vendor) + "/*": "allow"},
                "skill": {"*": "deny", "verification-before-completion": "allow"},
            }}}}
            path = root / "config/opencode/opencode.json"
            path.parent.mkdir(parents=True); path.write_text(json.dumps(config))
            overlay = profiles.worktree_permissions(root, worktree)
            javascript = r'''
const fs=require('node:fs'), os=require('node:os'), path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
let input=''; process.stdin.on('data',x=>input+=x); process.stdin.on('end',()=>{
 const data=JSON.parse(input);
 const ts=fs.readFileSync(data.fixture,'utf8').replaceAll('export ','');
 const native=new Function('os',stripTypeScriptTypes(ts,{mode:'strip'})+';const Wildcard={match};return {fromConfig,merge,evaluate};')(os);
 const rules=native.merge(native.fromConfig(data.overlay.permission),native.fromConfig(data.overlay.agent['evidence-reviewer'].permission));
 const out={};
 for (const [name,target] of Object.entries(data.targets)) {
  out[name]={read:native.evaluate('read',path.relative(data.worktree,target),rules).action,
    external:native.evaluate('external_directory',path.dirname(target)+'/*',rules).action};
 }
 console.log(JSON.stringify(out));
});'''
            payload = {"overlay": overlay, "worktree": str(worktree),
                "fixture": str(ROOT / "tests/fixtures/opencode-permission-53d1eabb.ts"),
                "targets": {"owned": str(worktree / "scripts/check.py"),
                    "primary": str(base / "primary/scripts/check.py"),
                    "vendor": str(vendor / "SKILL.md"),
                    "other_vendor": str(root / "vendor/unselected/SKILL.md"),
                    "outside": str(base / "unrelated/SKILL.md")}}
            result = subprocess.run([node, "-e", javascript], input=json.dumps(payload), text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                "owned": {"read": "allow", "external": "allow"},
                "primary": {"read": "deny", "external": "deny"},
                "vendor": {"read": "allow", "external": "allow"},
                "other_vendor": {"read": "deny", "external": "deny"},
                "outside": {"read": "deny", "external": "deny"}})

    def test_clean_worktree_removed_and_dirty_or_active_worktree_retained(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            repository = Path(directory) / "repo"
            repository.mkdir()
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "-c", "user.name=Fixture",
                            "-c", "user.email=fixture@users.noreply.github.com", "commit", "-q",
                            "--allow-empty", "-m", "fixture"], check=True)
            for state in ("clean", "dirty", "active"):
                worktree = Path(directory) / state
                subprocess.run(["git", "-C", str(repository), "worktree", "add", "--detach",
                                str(worktree)], check=True, capture_output=True)
                if state == "dirty":
                    (worktree / "keep.txt").write_text("fixture")
                with mock.patch.object(profiles, "active_worktree", return_value=state == "active"):
                    result = profiles.cleanup_worktree(repository, worktree)
                self.assertEqual(result["status"], "removed" if state == "clean" else "retained_" + state)
                self.assertEqual(worktree.exists(), state != "clean")
                if state == "dirty":
                    self.assertEqual(result["dirty_entries"], 1)
                    self.assertNotIn("keep.txt", json.dumps(result))

    def test_print_launch_cleans_only_after_usage_and_handoff_receipts(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            root, workspace = state / "pi-gpt", state / "worktree"
            root.mkdir(); workspace.mkdir()
            (root / "profile.json").write_text(json.dumps({"status": "trial", "pi_bin": "/fixture/pi",
                "model": "fixture", "effort": "high", "roles": {}}))
            args = argparse.Namespace(profile="pi-gpt", state_root=state, repository=state,
                role=None, print=True, prompt="fixture", timeout_seconds=1)
            def runtime(command, **kwargs):
                self.assertEqual(kwargs["cwd"], workspace)
                return subprocess.CompletedProcess(command, 0)
            def cleanup(repository, worktree):
                self.assertEqual(worktree, workspace)
                runs = list((root / "runs").iterdir())
                self.assertEqual(len(runs), 1)
                for name in ("invocations.json", "receipt.json", "CC-RECORD.md"):
                    self.assertTrue((runs[0] / name).is_file(), name)
                return {"status": "removed", "exit_code": 0}
            with mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-12T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", side_effect=cleanup) as removed, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args), 0)
                removed.assert_called_once()
            self.assertEqual(json.loads(next((root / "runs").glob("*/worktree-cleanup.json")).read_text())["status"], "removed")

    def test_valid_native_json_strings_with_unicode_line_separators_keep_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            event = {"type": "message_end", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "first\u2028second\u2029third"}],
                     "usage": {"input": 5, "output": 2, "totalTokens": 7, "cost": {"total": 0.01}}}}
            log.write_text(json.dumps(event, ensure_ascii=False) + "\n")
            measured = profiles.inference_facts(log, "pi")
            self.assertEqual(measured["completed_native_steps"], 1)
            self.assertEqual(measured["usage"]["total_tokens"], 7)
            self.assertEqual(measured["native_cost_usd"], 0.01)

    def test_pi_mcp_exit_zero_does_not_accept_absent_or_disabled_mandatory_server(self):
        for servers in [[], [{"name": "context-mode", "state": "disabled", "tools": []}]]:
            with self.subTest(servers=servers), tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                root = state / "pi-gpt"
                root.mkdir()
                (root / "profile.json").write_text(json.dumps({"pi_bin": "/fixture/pi",
                    "mcp_server_names": ["context-mode"]}))
                args = argparse.Namespace(state_root=state, workspace=state, out=state / "receipts",
                                          role_scope=None, tokenizer_python=Path(sys.executable))

                def native(command, **kwargs):
                    if "mcp" in command:
                        return 0, json.dumps({"servers": servers})
                    return 0, "{}"

                with mock.patch.object(acceptance, "native", side_effect=native), \
                        mock.patch.object(acceptance, "discovered", return_value=[]), \
                        mock.patch.object(acceptance, "skill_integrity", return_value={"managed_pass": True}), \
                        redirect_stdout(io.StringIO()):
                    self.assertFalse(acceptance.check(args, "pi-gpt"))
                receipt = json.loads((args.out / "pi-gpt.discovery.json").read_text())
                self.assertFalse(receipt["mcp"]["all_connected"])

    def test_interactive_claude_opencode_collector_uses_profile_xdg_after_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            role = state / "opencode-claude/roles/builder"
            role.mkdir(parents=True)
            (role / "profile.json").write_text(json.dumps({
                "status": "trial", "model": "fixture", "effort": "xhigh",
                "opencode_bin": "/fixture/opencode", "roles": {"isolated-builder": {"tools": []}},
            }))
            config = role / "config/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"agent":{}}')
            expected = {"XDG_STATE_HOME": str(role / "state"), "XDG_DATA_HOME": str(role / "data"),
                        "OPENCODE_CONFIG_DIR": str(role / "config")}
            observed = []

            def run(command, **kwargs):
                if command[0] == "/fixture/opencode":
                    observed.append(kwargs["env"])
                    kwargs["stdout"].write("[]")
                return subprocess.CompletedProcess(command, 0)

            args = argparse.Namespace(profile="opencode-claude", state_root=state, repository=state,
                                      role="isolated-builder", print=False, prompt=None)
            with mock.patch.object(profiles, "fresh_worktree", return_value=state), \
                    mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}), \
                    mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4"), \
                    mock.patch.object(profiles, "profile_environment", return_value=expected), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=run), redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args), 0)
            self.assertEqual(len(observed), 1)
            for name, value in expected.items():
                self.assertEqual(observed[0].get(name), value, name)
            self.assertEqual(observed[0]["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
            self.assertEqual(observed[0]["PWD"], str(state))
            self.assertEqual(json.loads(observed[0]["OPENCODE_CONFIG_CONTENT"])["permission"]["read"]["../*"], "deny")

    def test_read_only_vendor_skill_loader_is_explicitly_narrowed_per_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            servers = {"context-mode": {"type": "stdio", "command": "/fixture/mcp"}}
            with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                    mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                profiles.render("opencode-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state,
                                role_scope="auditor")
            config = json.loads((state / "opencode-gpt/roles/auditor/config/opencode/opencode.json").read_text())
            # CC09:55Z B1 supersedes the no-Skill expectation: this native
            # helper is a read-only loader and drives skill discoverability.
            for name in profiles.ROLES:
                permissions = config["agent"][name]["permission"]
                self.assertEqual(permissions["skill"]["*"], "deny", name)
                self.assertEqual(permissions["skill"]["find-skills"], "allow", name)
                self.assertNotIn("unrelated-unknown-skill", permissions["skill"])
            self.assertEqual(config["agent"]["security-reviewer"]["permission"]["skill"]["systematic-debugging"], "allow")
            self.assertNotIn("systematic-debugging", config["agent"]["source-scout"]["permission"]["skill"])

    def test_token_layer_is_private_on_both_runtimes_and_claude_prompt_fallback_disabled(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            for profile in profiles.PROFILES:
                env = profiles.profile_environment(profile, state, "reviewer")
                root = state / profile / "roles/reviewer"
                for variable in ("CLAUDE_CONFIG_DIR", "CONTEXT_MODE_DIR", "CONTEXT_MODE_DATA_DIR"):
                    self.assertTrue(Path(env[variable]).is_relative_to(root), variable)
                if profile.startswith("opencode"):
                    self.assertEqual(env["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"], "1")

    def test_both_canonical_role_preloads_use_native_files_without_copying_skill_text(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            for profile in ("pi-gpt", "opencode-gpt"):
                servers = {"context-mode": {"type": "stdio", "command": "/fixture/node"}}
                with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                        mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                        mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                            "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                        mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as installs:
                    profiles.render(profile, state=state, home=state, eco_root=state, templates=[],
                                    pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state)
                    npm = [call.args[0] for call in installs.call_args_list if call.args[0][0] == "npm"]
                    self.assertEqual(npm[0][1], "install")
                    self.assertIn("--ignore-scripts", npm[0])
                    self.assertEqual(npm[1][1], "rebuild")
                    self.assertEqual(npm[1][-1], "better-sqlite3")
                root = state / profile
                meta = json.loads((root / "profile.json").read_text())
                security = meta["roles"]["security-reviewer"]["preloads"]
                builder = meta["roles"]["isolated-builder"]["preloads"]
                self.assertEqual(security[0]["path"], str(state / ".agents/skills/security-best-practices/SKILL.md"))
                self.assertEqual(builder[0]["path"], str(profiles.context_mode_package(root) / "skills/context-mode/SKILL.md"))
                if profile.startswith("opencode"):
                    config = json.loads((root / "config/opencode/opencode.json").read_text())
                    for role, preloads in [("security-reviewer", security), ("isolated-builder", builder)]:
                        self.assertIn("{file:" + preloads[0]["path"] + "}", config["agent"][role]["prompt"])
                        self.assertEqual(config["agent"][role]["permission"]["skill"][preloads[0]["name"]], "allow")
                context = (json.loads((root / "agent/mcp.json").read_text())["mcpServers"]["context-mode"]
                           if profile.startswith("pi") else config["mcp"]["context-mode"])
                environment = context.get("env", context.get("environment"))
                self.assertTrue(Path(environment["HOME"]).is_relative_to(root))
                self.assertEqual(environment["CONTEXT_MODE_PLATFORM"], profile.split("-")[0])

    def test_native_mcp_failed_or_absent_status_is_not_connected_despite_exit_zero(self):
        output = "│ ✓ serena connected\n│ ✗ socraticode failed\n"
        states = acceptance.opencode_statuses(output, ["serena", "socraticode", "context-mode"])
        self.assertEqual(states, {"serena": "connected", "socraticode": "failed", "context-mode": "unverified"})

    def test_mcp_conversion_preserves_transport_environment_and_arguments(self):
        servers = {
            "stdio-fixture": {"type": "stdio", "command": "/tool with spaces", "args": ["--one", "two words"],
                              "env": {"PUBLIC_OPTION": "value"}},
            "remote-fixture": {"type": "http", "url": "http://127.0.0.1:19999/mcp"},
        }
        converted = profiles.opencode_mcp(servers)
        self.assertEqual(converted["stdio-fixture"]["command"], ["/tool with spaces", "--one", "two words"])
        self.assertEqual(converted["stdio-fixture"]["environment"], {"PUBLIC_OPTION": "value"})
        self.assertEqual(converted["remote-fixture"]["type"], "remote")
        self.assertFalse(converted["remote-fixture"]["oauth"])

    def test_roles_cannot_gain_shell_write_or_mcp_wildcards(self):
        metadata, _ = profiles.role_source("evidence-reviewer")
        for runtime in ["pi", "opencode"]:
            tools, omitted = profiles.granted_tools(metadata, runtime)
            self.assertNotIn("bash", tools)
            self.assertNotIn("edit", tools)
            self.assertNotIn("write", tools)
            self.assertNotIn("mcp__*", tools)
            self.assertNotIn("*", tools)
            self.assertTrue(any("serena" in tool for tool in tools))
        metadata, _ = profiles.role_source("source-scout")
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["bash", "find", "grep", "read"])

    def test_native_tool_identity_preserves_vendor_hyphens_and_role_patterns(self):
        metadata = {"tools": "mcp__ai-memory__memory_query, mcp__serena__find_*"}
        tools, _ = profiles.granted_tools(metadata, "opencode")
        self.assertEqual(tools, ["ai-memory_memory_query", "serena_find_*"])
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["mcp__ai_memory__memory_query", "mcp__serena__find_*"])

    def test_profile_destinations_refuse_symlink_and_protected_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to(root / "target", target_is_directory=True)
            with self.assertRaises(profiles.ProfileError):
                profiles.owned_destination(root / "link/nested")
        with self.assertRaises(profiles.ProfileError):
            profiles.owned_destination(Path.home() / ".codex/never")

    def test_ns_run_accepts_named_launcher_profile(self):
        args = profiles.parser().parse_args(["run", "--state-root", "/fixture",
                                            "--repository", "/fixture", "ns-pi-gpt", "builder", "brief.md"])
        self.assertEqual(args.profile, "pi-gpt")

    def test_xdg_profile_path_reaches_selected_python_without_host_shim_config(self):
        with tempfile.TemporaryDirectory() as directory:
            env = profiles.profile_environment("opencode-gpt", Path(directory))
            expected = str(Path(sys.executable).resolve().parent)
            self.assertEqual(env["PATH"].split(os.pathsep)[0], expected)
            self.assertTrue(env["XDG_STATE_HOME"].startswith(directory))
            self.assertEqual(env["OTEL_EXPORTER_OTLP_ENDPOINT"], "http://127.0.0.1:21318")

    def test_existing_profile_is_preserved_and_token_layer_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            destination = state / "pi-gpt"
            destination.mkdir()
            (destination / "owner-file").write_text("keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.render("pi-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state)
            self.assertEqual((destination / "owner-file").read_text(), "keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.canonical_servers(state, state, [])

    def test_secret_is_environment_reference_not_stored_value(self):
        provider = profiles.opencode_provider("claude")
        self.assertEqual(provider["anthropic"]["options"]["apiKey"], "{env:ANTHROPIC_API_KEY}")
        self.assertNotIn("apiKey", json.dumps(profiles.pi_models("claude")))

    def test_windows_fragments_are_new_profiles_not_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(home=root, state_root=root / "state", repository=ROOT,
                                      fragment=root / "Fragments/native-stack/runtimes.json")
            profiles.install_launchers(args)
            fragment = json.loads(args.fragment.read_text())
            self.assertEqual(len(fragment["profiles"]), 4)
            self.assertTrue(all("updates" not in item for item in fragment["profiles"]))
            self.assertTrue(all("wsl.exe" in item["commandline"] for item in fragment["profiles"]))
            self.assertFalse((root / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
