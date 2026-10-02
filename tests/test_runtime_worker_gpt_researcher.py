"""Offline recipe contracts; not upstream or live-provider acceptance.

Oracle: user runtime-worker brief (2026-09-27), and GPT Researcher v3.7.0
config/variables/default.py, utils/llm.py, mcp/client.py. No framework install.
"""

import json
import copy
import asyncio
from contextlib import asynccontextmanager
import hashlib
from contextlib import closing, nullcontext
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/gpt-researcher"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # These CLI recipes use sibling imports. Keep each fixture's native import
    # environment isolated when all worker families share one unittest process.
    with patch.dict(sys.modules), patch.object(sys, "path", [str(path.parent), *sys.path]):
        for key, value in list(sys.modules.items()):
            location = getattr(value, "__file__", None)
            if location and Path(location).is_relative_to(ROOT / "blueprints/runtime-workers") \
                    and not Path(location).is_relative_to(RECIPE):
                del sys.modules[key]
        spec.loader.exec_module(module)
    return module


class RuntimeWorkerGPTResearcherTests(unittest.TestCase):
    def test_dispatch_supervisor_pass_failure_timeout_busy_and_malformed_report(self):
        dispatch = load("gptr_dispatch", RECIPE / "dispatch.py")
        import fcntl
        for native_exit, report_ok, usage_ok, expected in ((0, True, True, 0), (7, False, False, 10),
                                                         (124, False, False, 30), (0, False, True, 30),
                                                         (0, True, False, 30)):
            with self.subTest(native_exit=native_exit, expected=expected), tempfile.TemporaryDirectory() as tmp:
                state = Path(tmp)
                run = state / "runs/control"
                run.mkdir(parents=True)
                job = {"mode": "cli", "routes": dispatch.select_routes({}), "prefix": str(state / "prefix"),
                       "report_type": "research_report", "engines_db_verified": False}
                (run / "job.json").write_text(json.dumps(job))
                def native(argv, *, cwd, env, stdout, stderr, **kwargs):
                    self.assertEqual(argv[:4], ["timeout", "--signal=TERM", "--kill-after=20s", "1800s"])
                    self.assertEqual(env["HOME"], str(run / "home"))
                    self.assertNotIn("PRIVATE_API_KEY", env)
                    self.assertNotIn("PYTHONPATH", env)
                    self.assertEqual(len(kwargs.get("pass_fds", ())), 1)
                    if report_ok:
                        (run / "outputs").mkdir()
                        synthetic_id = "-".join("a" * n for n in (8, 4, 4, 4, 12))
                        (run / "outputs/report.md").write_text('---\ntask_id: "' + synthetic_id + '"\nsources_count: 1\ntotal_cost_usd: 0.0\n---\nNative report\n')
                        stdout.write("Report written to 'outputs/report.md'\n")
                    return SimpleNamespace(returncode=native_exit)
                usage = {"worker": {"status": "observed" if usage_ok else "unavailable", "rows": [{"status": 200}],
                                     "effort": {"non_max_returned_reasoning": 0}}}
                with patch.object(dispatch, "preflight"), patch.object(dispatch.subprocess, "run", side_effect=native), \
                     patch.object(dispatch, "phase_usage", return_value=usage), \
                     patch.dict(os.environ, {"PRIVATE_API_KEY": "synthetic", "PYTHONPATH": "untrusted"}):
                    result = dispatch.supervise(run)
                self.assertEqual(result["exit_code"], expected)
                self.assertEqual(json.loads((run / "dispatch-result.json").read_text()), result)
                self.assertEqual(dispatch.poll(run), result)
                self.assertTrue((run / "receipt.json").exists())
                with (state / "worker.lock").open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with patch.object(dispatch, "preflight") as check:
                        busy = dispatch.supervise(run)
                    self.assertEqual(busy["exit_code"], 75)
                    check.assert_not_called()

    def test_dispatch_setup_errors_have_persistent_results_and_no_ambiguous_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "GPTR_STATE_ROOT": str(root / "state"), "PYTHONDONTWRITEBYTECODE": "1"}
            command = ["bash", str(RECIPE / "dispatch.sh"), "start", "--run-id", "bad-query", "--arm", "control"]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 20)
            parsed = json.loads(result.stdout)
            self.assertEqual(parsed["exit_class"], "setup_failure")
            self.assertTrue((root / "state" / parsed["result"]).is_file())
            self.assertTrue((root / "state" / parsed["receipt"]).is_file())
            syntax = subprocess.run(command + ["--unknown"], env=env, capture_output=True, text=True)
            self.assertEqual(syntax.returncode, 20)
            self.assertEqual(json.loads(syntax.stdout)["exit_class"], "setup_failure")

    def test_usage_does_not_call_partial_correlations_complete(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rows.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE call_logs(timestamp,path,status,model,reasoning_effort_requested,reasoning_effort_upstream,tokens_in,tokens_cache_read,tokens_reasoning,correlation_id)")
                con.execute("INSERT INTO call_logs VALUES('2026-09-27T00:00:01Z','/v1/responses',200,'gpt-6-astra-max',NULL,NULL,3,0,0,'one')")
                con.commit()
            result = receipt.gateway_rows(db, "2026-09-27T00:00:00Z", "2026-09-27T00:00:02Z",
                                          "cx/gpt-6-astra-max", correlation_ids={"one", "delayed-or-missing"})
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["missing_correlation_count"], 1)

    def test_evidence_requires_a_successful_gateway_row_and_preserves_compression_snapshots(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        observed = {"status": "observed", "rows": [{"status": 503}], "effort": {"non_max_returned_reasoning": 0}}
        self.assertFalse(receipt.gateway_evidence_complete(observed))
        observed["rows"][0]["status"] = 200
        self.assertTrue(receipt.gateway_evidence_complete(observed))
        observed["effort"]["non_max_returned_reasoning"] = 1
        self.assertFalse(receipt.gateway_evidence_complete(observed))
        before = {"status": "observed", "totalRequests": 2, "totalTokensSaved": 3}
        after = {"status": "observed", "totalRequests": 3, "totalTokensSaved": 7}
        delta = receipt.compression_delta(before, after)
        self.assertEqual(delta["before"], before)
        self.assertEqual(delta["after"], after)
        self.assertEqual(receipt.compression_delta(after, before)["status"], "counter_reset")

    def test_e2e_persists_disjoint_phases_and_uses_dispatch_handle(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            runner = load("gptr_run", RECIPE / "e2e/run.py")
        finally:
            sys.path.pop(0)
        async def native(args, output):
            output.update(report="Report", framework_version="0.16.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = ["run.py", "--run-dir", tmp, "--prefix", tmp, "--host-file", str(root / "host.json"),
                    "--model", "sharedgw/gpt-6-astra-max", "--base-url", "http://127.0.0.1:20129/v1",
                    "--judge-model", "cx/gpt-6-astra-max"]
            cwd = Path.cwd()
            try:
                with patch.object(sys, "argv", args), patch.object(runner, "run", side_effect=native), \
                     patch.object(runner, "compression_snapshot", create=True, return_value={"status": "observed", "totalRequests": 0, "totalTokensSaved": 0}), \
                     patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
                    self.assertEqual(runner.main(), 0)
            finally:
                os.chdir(cwd)
            phases = json.loads((root / "phases.json").read_text())
            self.assertLessEqual(phases["worker_started"], phases["worker_ended"])
            self.assertLessEqual(phases["worker_ended"], phases["judge_started"])
            self.assertLessEqual(phases["judge_started"], phases["judge_ended"])
            execution = json.loads((root / "execution.json").read_text())
            self.assertEqual(execution["framework_version"], "0.16.0")
            self.assertFalse((root / "receipt.json").exists())  # observer runs outside worker HOME
            env = {**os.environ, "GPTR_STATE_ROOT": str(root / "state"), "GPTR_PREFIX": str(root / "absent"),
                   "GPTR_RUN_ID": "e2e-failure", "RUNTIME_WORKER_ARM": "engines-on", "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(["bash", str(RECIPE / "run-e2e.sh")], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 20, result.stderr)
            self.assertEqual(json.loads(result.stdout)["receipt"], "runs/e2e-failure/receipt.json")

    def test_dispatch_start_wait_result_preserves_setup_failure_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            query = root / "query.txt"
            query.write_text("Research public Python documentation")
            env = {**os.environ, "GPTR_STATE_ROOT": str(root / "state"), "GPTR_PREFIX": str(root / "absent"),
                   "PYTHONDONTWRITEBYTECODE": "1"}
            base = ["bash", str(RECIPE / "dispatch.sh")]
            started = subprocess.run(base + ["start", "--run-id", "offline-setup", "--arm", "engines-on", "--query-file", str(query)],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(started.returncode, 0, started.stderr)
            handle = json.loads(started.stdout)
            self.assertEqual(handle["result"], "runs/offline-setup/dispatch-result.json")
            self.assertTrue((root / "state/runs/offline-setup/status.json").exists())
            waited = subprocess.run(base + ["wait", "--run-id", "offline-setup", "--timeout", "5"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(waited.returncode, 20, waited.stdout + waited.stderr)
            result = json.loads(waited.stdout)
            self.assertEqual(result["exit_class"], "setup_failure")
            self.assertEqual(result["arm"], "engines-on")
            self.assertEqual(result["receipt"], "runs/offline-setup/receipt.json")
            fetched = subprocess.run(base + ["result", "--run-id", "offline-setup"], env=env, capture_output=True, text=True)
            self.assertEqual(json.loads(fetched.stdout), result)
            self.assertEqual(fetched.returncode, 20)

    def test_dispatch_result_classes_do_not_invent_a_quality_threshold(self):
        dispatch = load("gptr_dispatch", RECIPE / "dispatch.py")
        self.assertEqual(dispatch.classify(0, True, True), ("pass", 0))
        self.assertEqual(dispatch.classify(0, True, False), ("incomplete_evidence", 30))
        self.assertEqual(dispatch.classify(0, False, True), ("incomplete_evidence", 30))
        self.assertEqual(dispatch.classify(7, False, False), ("negative_verdict", 10))
        self.assertEqual(dispatch.classify(124, False, False), ("incomplete_evidence", 30))
        # Scalar DRB-II scores are not inputs to classification.

    def test_cli_dispatch_runs_unchanged_native_main_with_guarded_transport(self):
        cli = load("gptr_cli_runner", RECIPE / "cli_runner.py")
        received = []
        async def native_main(args):
            received.append(args)
        @asynccontextmanager
        async def clients(_self):
            yield
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("query")
        parser.add_argument("--report_type")
        parser.add_argument("--tone")
        parser.add_argument("--no-pdf", action="store_true")
        parser.add_argument("--no-docx", action="store_true")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = {"base_url": "http://127.0.0.1:20129/v1", "model": "sharedgw/gpt-6-astra-max"}
            cwd = Path.cwd()
            try:
                with patch.object(cli.runpy, "run_path", return_value={"cli": parser, "main": native_main}) as run_path, \
                     patch.object(cli.GatewayTransport, "worker_clients", clients), patch.dict(os.environ):
                    asyncio.run(cli.execute_cli(root, root, route, "A query", "research_report"))
                    self.assertEqual(os.environ["RETRIEVER"], "duckduckgo")
                    self.assertEqual(os.environ["ALLOW_PRIVATE_URLS"], "false")
                    self.assertEqual(run_path.call_args.kwargs["run_name"], "gptr_native_cli")
                    self.assertTrue(run_path.call_args.args[0].endswith("0957c301ed06c2a5857b834358c7227c739041d4/cli.py"))
            finally:
                os.chdir(cwd)
            self.assertEqual(received[0].query, "A query")
            self.assertTrue(received[0].no_pdf and received[0].no_docx)
            cfg = json.loads((root / "config.json").read_text())
            self.assertEqual(cfg["MCP_SERVERS"], [])
            self.assertEqual(cfg["LLM_KWARGS"]["reasoning_effort"], "max")
            self.assertEqual(cfg["LLM_KWARGS"]["extra_body"]["reasoning"], {"effort": "max"})

    def test_receipt_records_separate_entry_gateways_phases_and_header_names(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        calls = []
        def rows(database, started, ended, model, **kwargs):
            calls.append((str(database), started, ended, model))
            return {"status": "observed", "rows": [], "effort": {"non_max_returned_reasoning": 0}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "result.json").write_text('{"report":"Report"}')
            routes = {"arm": "engines-on", "worker": {"base_url": "http://127.0.0.1:20129/v1", "model": "sharedgw/gpt-6-astra-max"},
                      "judge": {"base_url": "http://127.0.0.1:20128/v1", "model": "cx/gpt-6-astra-max"}}
            phases = {"worker_started": "2026-09-27T00:00:00Z", "worker_ended": "2026-09-27T00:01:00Z",
                      "judge_started": "2026-09-27T00:01:01Z", "judge_ended": "2026-09-27T00:02:00Z"}
            with patch.object(receipt, "gateway_rows", side_effect=rows):
                result = receipt.write_receipt(root, phases["worker_started"], phases["judge_ended"], routes["worker"]["model"],
                                               "0.16.0", routes=routes, phases=phases, engines_verified=True)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0][0].endswith("omniroute-fw/storage.sqlite"))
            self.assertTrue(calls[1][0].endswith("omniroute/storage.sqlite"))
            self.assertEqual(calls[0][1:3], (phases["worker_started"], phases["worker_ended"]))
            self.assertEqual(calls[1][1:3], (phases["judge_started"], phases["judge_ended"]))
            self.assertEqual(result["arm"], "engines-on")
            self.assertIn("x-omniroute-compression", result["routes"]["worker"]["header_names"])
            self.assertNotIn("allow-lossy", json.dumps(result))
            self.assertNotIn("x-omniroute-compression", result["routes"]["judge"]["header_names"])

    def test_gateway_captures_response_correlations_privately_for_worker_and_judge(self):
        gateway = load("gptr_gateway", RECIPE / "gateway.py")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "correlations.jsonl"
            transport = gateway.GatewayTransport("worker", correlation_log=path)
            response = SimpleNamespace(headers={"X-Correlation-Id": "private-correlation"})
            transport.response_hook(response)
            asyncio.run(transport.async_response_hook(response))
            transport.grader_post(lambda *a, **k: response)(gateway.CHAT_URL, json={"model": "cx/gpt-6-astra-max"})
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([e["correlation_id"] for e in events if e["event"] == "response"],
                             ["private-correlation"] * 3)

    def test_usage_filters_by_phase_model_path_and_correlation_without_retaining_ids(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "synthetic.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE call_logs(timestamp TEXT,path TEXT,status INTEGER,model TEXT,"
                            "reasoning_effort_requested TEXT,reasoning_effort_upstream TEXT,tokens_in INTEGER,"
                            "tokens_cache_read INTEGER,tokens_reasoning INTEGER,correlation_id TEXT)")
                for seconds, model, path, tokens, effort, correlation in (
                    (1, "gpt-6-astra-max", "/v1/responses", 20, "max", "ours"),
                    (2, "gpt-6-astra-max", "/v1/responses", 0, None, "no-reasoning"),
                    (3, "gpt-6-astra-max", "/v1/responses", 5, "high", "other-caller"),
                    (4, "claude", "/v1/responses", 20, "max", "other-model"),
                    (5, "gpt-6-astra-max", "/secret", 20, "max", "other-path"),
                    (6, "gpt-6-astra-max", "/v1/chat/completions", 20, "max", "judge")):
                    con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (f"2026-09-27T00:00:0{seconds}Z", path, 200, model, effort, effort, 100, 50, tokens, correlation))
                con.commit()
            before = db.read_bytes()
            rows = receipt.gateway_rows(db, "2026-09-27T00:00:00Z", "2026-09-27T00:00:06Z",
                                        "sharedgw/gpt-6-astra-max", correlation_ids={"ours", "no-reasoning"})
            self.assertEqual(len(rows["rows"]), 2)
            self.assertEqual(rows["effort"]["without_returned_reasoning"], 1)
            self.assertEqual(rows["effort"]["non_max_returned_reasoning"], 0)
            self.assertEqual(rows["attribution"], "correlation_id")
            self.assertNotIn("correlation_id", rows["rows"][0])
            self.assertNotIn("ours", json.dumps(rows))
            fallback = receipt.gateway_rows(db, "2026-09-27T00:00:00Z", "2026-09-27T00:00:06Z", "sharedgw/gpt-6-astra-max")
            self.assertEqual(len(fallback["rows"]), 3)
            self.assertEqual(fallback["effort"]["non_max_returned_reasoning"], 1)
            self.assertIn("time window", fallback["attribution"])
            self.assertEqual(before, db.read_bytes())
            self.assertEqual(receipt.gateway_database(root, "control", False), root / ".local/share/omniroute/storage.sqlite")
            with self.assertRaises(ValueError):
                receipt.gateway_database(root, "engines-on", False)
            self.assertEqual(receipt.gateway_database(root, "engines-on", True), root / ".local/share/omniroute-fw/storage.sqlite")
            self.assertEqual(receipt.compression_delta({"status": "observed", "totalRequests": 3, "totalTokensSaved": 8},
                                                     {"status": "observed", "totalRequests": 5, "totalTokensSaved": 20})["delta"],
                             {"totalRequests": 2, "totalTokensSaved": 12})
            self.assertEqual(receipt.compression_delta({"status": "unavailable"}, {"status": "observed"})["status"], "unavailable")

    def test_read_grade_checks_native_csv_controls_and_artifact_bindings(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        task = {"idx": 12, "content": {"task": "Control", "rubric": {
            "info_recall": ["Fact"], "analysis": ["Analysis"], "presentation": ["Presentation"]}}}
        pin = json.loads((RECIPE / "pins.json").read_text())["grader"]["commit"]
        for score in (1, 0, -1):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                row = {"model": "gptr", "idx": 12, "result": {"task": "Control", "scores": {
                    dim: {item: {"score": score, "reason": "Control", "evidence": ""} for item in items}
                    for dim, items in task["content"]["rubric"].items()}}}
                (root / "drb-result.jsonl").write_text(json.dumps(row) + "\n")
                (root / "report.md").write_text("Report")
                (root / "result.json").write_text('{"report":"Report"}')
                (root / "frozen-reports/gptr").mkdir(parents=True)
                (root / "frozen-reports/gptr/idx-12.md").write_text("Report")
                summary = {"commit": pin, "idx": 12, "judge_model": "cx/gpt-6-astra-max",
                           "raw_result_sha256": hashlib.sha256((root / "drb-result.jsonl").read_bytes()).hexdigest(),
                           "report_sha256": hashlib.sha256(b"Report").hexdigest(), "metric_artifacts": {}}
                # Exact CSV layout: DRB-II@b38f360 aggregate_scores.py:249-289.
                for suffix in ("inforecall", "analysis", "presentation", "total", "blocked"):
                    value = int(score == -1) if suffix == "blocked" else max(0, score)
                    path = root / f"scores_{suffix}.csv"
                    path.write_text(f"idx,language,theme,gptr,avg\n12,en,test,{value},{value}\navg,,,{value},{value}\n")
                    summary["metric_artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                summary_path = root / "grade-summary.json"
                summary_path.write_text(json.dumps(summary))
                with patch.object(grader, "load_task", return_value=(task, b"frozen")):
                    grade = grader.read_grade(root)
                    self.assertEqual(grade["metrics_from_upstream_csv"]["total"], max(0, score))
                    self.assertEqual(grade["metrics_from_upstream_csv"]["blocked"], int(score == -1))
                    path = root / "scores_total.csv"
                    original = path.read_bytes()
                    for cells in ("avg,,,0,0\n", "12,en,test,0,0\n13,en,test,0,0\n", "12,en,test,,0\n",
                                  "12,en,test,nonsense,0\n", "12,en,test,nan,0\n", "12,en,test,inf,0\n"):
                        path.write_text("idx,language,theme,gptr,avg\n" + cells)
                        summary["metric_artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                        summary_path.write_text(json.dumps(summary))
                        with self.subTest(cells=cells), self.assertRaises(ValueError):
                            grader.read_grade(root)
                    path.write_bytes(original)
                    with self.assertRaises(ValueError):
                        grader.read_grade(root)  # changed CSV hash
                    summary["metric_artifacts"][path.name] = hashlib.sha256(original).hexdigest()
                    summary["report_sha256"] = "0" * 64
                    summary_path.write_text(json.dumps(summary))
                    with self.assertRaises(ValueError):
                        grader.read_grade(root)

    def test_judge_uses_documented_batch_budget_and_separate_session(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        task = {"idx": 12, "prompt": "Prompt", "content": {"task": "Task", "rubric": {
            "info_recall": ["Fact"], "analysis": ["Analysis"], "presentation": ["Presentation"]}}}
        native_calls, sessions = [], []
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "tasks-and-rubrics.jsonl").write_bytes(b"frozen\n")
            (run_dir / "frozen-reports/gptr").mkdir(parents=True)
            (run_dir / "frozen-reports/gptr/idx-12.md").write_text("Report")
            (run_dir / "report.md").write_text("Report")
            (run_dir / "config.json").write_text(json.dumps({"LLM_KWARGS": {
                "default_headers": {"x-omniroute-session": "worker-session"}}}))
            def native(path, **kwargs):
                native_calls.append((sys.argv[:], dict(grader.os.environ)))
                if path.endswith("run_evaluation.py"):
                    row = {"model": "gptr", "idx": 12, "result": {"task": "Task", "scores": {
                        dim: {item: {"score": 0, "reason": "Control", "evidence": ""} for item in items}
                        for dim, items in task["content"]["rubric"].items()}}}
                    (run_dir / "drb-result.jsonl").write_text(json.dumps(row) + "\n")
                else:
                    for suffix in ("inforecall", "analysis", "presentation", "total", "blocked"):
                        (run_dir / f"scores_{suffix}.csv").write_text("idx,language,theme,gptr,avg\n12,en,test,0,0\navg,,,0,0\n")
            original_transport = grader.GatewayTransport
            def transport(session, **kwargs):
                sessions.append(session)
                return original_transport(session, **kwargs)
            import os
            cwd = Path.cwd()
            try:
                with patch.object(grader, "verified_source", return_value=run_dir), \
                     patch.object(grader, "load_task", return_value=(task, b"frozen\n")), \
                     patch.object(grader.runpy, "run_path", side_effect=native), \
                     patch.object(grader, "GatewayTransport", side_effect=transport), \
                     patch.dict(sys.modules, {"gpt_client": SimpleNamespace(requests=SimpleNamespace(post=lambda *a, **k: None))}), \
                     patch.dict(os.environ), patch.object(sys, "argv", ["grader.py", "--prefix", tmp,
                           "--run-dir", tmp, "--model", "cx/gpt-6-astra-max"]):
                    self.assertEqual(grader.main(), 0)
            finally:
                os.chdir(cwd)
            argv, env = native_calls[0]
            self.assertEqual(env["OPENAI_MAX_OUTPUT_TOKENS"], "32768")
            self.assertEqual(env["OPENAI_REASONING_EFFORT"], "max")
            self.assertEqual(argv[argv.index("--chunk_size") + 1], "50")
            self.assertEqual(argv[argv.index("--max_retries") + 1], "5")
            self.assertNotEqual(sessions, ["worker-session"])

    def test_worker_uses_native_retry_without_websocket_and_arm_config(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            runner = load("gptr_run", RECIPE / "e2e/run.py")
        finally:
            sys.path.pop(0)
        constructed = []
        class Researcher:
            def __init__(self, **kwargs):
                constructed.append(kwargs)
            async def conduct_research(self):
                pass
            async def write_report(self, **kwargs):
                return "Native report"
            def get_research_sources(self):
                return []
        class Manager:
            def __init__(self, configs):
                self.configs = configs
            async def get_all_tools(self):
                return [SimpleNamespace(name=n) for n in ("query", "get", "ctx_index", "memory_query")]
            async def close_client(self):
                pass
        @asynccontextmanager
        async def clients(_self):
            yield
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "grader-venv/bin").mkdir(parents=True)
            (root / "grader-venv/bin/python").touch()
            (root / "installation-pins.json").write_bytes((RECIPE / "pins.json").read_bytes())
            args = SimpleNamespace(host_file=root / "host.json", prefix=root, run_dir=root,
                                   model="sharedgw/gpt-6-astra-max", base_url="http://127.0.0.1:20129/v1")
            modules = {"gpt_researcher": SimpleNamespace(GPTResearcher=Researcher),
                       "gpt_researcher.mcp.client": SimpleNamespace(MCPClientManager=Manager)}
            with patch.dict(sys.modules, modules), patch.object(runner, "load_host", return_value={}), \
                 patch.object(runner.importlib.metadata, "version", return_value="0.16.0"), \
                 patch.object(runner, "verified_source", return_value=root), \
                 patch.object(runner, "load_task", return_value=({"idx": 12, "prompt": "Original prompt"}, b"{}\n")), \
                 patch.object(runner.GatewayTransport, "worker_clients", clients), patch.dict(runner.os.environ):
                asyncio.run(runner.run(args, {}))
            self.assertIsNone(constructed[0].get("websocket"))
            cfg = json.loads((root / "config.json").read_text())
            self.assertEqual(cfg["LLM_KWARGS"]["base_url"], args.base_url)
            self.assertEqual(cfg["LLM_KWARGS"]["reasoning_effort"], "max")
            self.assertEqual(cfg["LLM_KWARGS"]["default_headers"]["x-omniroute-compression"], "allow-lossy")
            for config in constructed[0]["mcp_configs"]:
                self.assertIn("--run-dir", config["args"])

    def test_grader_install_refuses_builds_and_retains_upstream_lock(self):
        # Source oracle: uv sync --help; DRB-II@b38f360 pyproject.toml:1-12.
        command = next(line for line in (RECIPE / "install.sh").read_text().splitlines()
                       if "uv sync --locked" in line)
        for flag in ("--locked", "--no-build", "--no-install-project"):
            self.assertIn(flag, command)

    def test_model_cannot_execute_fetch_or_index_host_files(self):
        proxy = load("gptr_proxy", RECIPE / "mcp_proxy.py")
        for name in ("ctx_execute", "ctx_execute_file", "ctx_batch_execute", "ctx_fetch_and_index"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                proxy.scope_arguments("context-mode", name, {"url": "http://127.0.0.1:49474/mcp"}, {})
        for args in ({"path": "/etc/passwd"}, {"content": "ok", "path": "/etc/passwd"},
                     {"content": "ok", "followSymlinks": True}, {"content": 42}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                proxy.scope_arguments("context-mode", "ctx_index", args, {})
        self.assertEqual(proxy.scope_arguments("context-mode", "ctx_index",
                         {"content": "Public source text", "source": "research"}, {}),
                         {"content": "Public source text", "source": "research"})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp).resolve()  # server_config resolves it; macOS temp dirs sit under a /var symlink
            host = {"ECO_ROOT": "/opt/tools", "HOST_PATH": "/usr/bin", "WORKER_CWD": "/private/checkout"}
            cfg = proxy.server_config("context-mode", host, run_dir)
            self.assertEqual(cfg["cwd"], str(run_dir / "mcp-work"))
            self.assertEqual(cfg["env"]["CONTEXT_MODE_PROJECT_DIR"], cfg["cwd"])
            self.assertEqual(cfg["env"]["CONTEXT_MODE_DIR"], str(run_dir / "context-mode"))
            self.assertEqual(cfg["env"]["HOME"], str(run_dir / "home"))
            self.assertNotIn("/private/checkout", json.dumps(cfg))

    def test_arm_routes_are_explicit_and_judge_stays_on_control(self):
        gateway = load("gptr_gateway", RECIPE / "gateway.py")
        control = gateway.select_routes({})
        engines = gateway.select_routes({"RUNTIME_WORKER_ARM": "engines-on"})
        self.assertEqual(control["worker"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(control["worker"]["model"], "cx/gpt-6-astra-max")
        self.assertEqual(engines["worker"]["base_url"], "http://127.0.0.1:20129/v1")
        self.assertEqual(engines["worker"]["model"], "sharedgw/gpt-6-astra-max")
        self.assertEqual(engines["judge"], control["judge"])
        for selection in (control, engines):
            route = selection["worker"]
            transport = gateway.GatewayTransport("conversation", **route)
            request = SimpleNamespace(url=route["base_url"] + "/responses", headers={},
                                      content=json.dumps({"model": route["model"]}).encode())
            transport.request_hook(request)
            self.assertEqual("x-omniroute-compression" in request.headers, selection["arm"] == "engines-on")
            if selection["arm"] == "engines-on":
                self.assertEqual(request.headers["x-omniroute-compression"], "allow-lossy")
            request.url = control["judge"]["base_url"] + "/responses" if selection["arm"] == "engines-on" else "https://example.invalid/responses"
            with self.assertRaises(ValueError):
                transport.request_hook(request)
        self.assertEqual(gateway.select_routes({"GPTR_MODEL": "cx/gpt-6-sol-medium"})["worker"]["model"],
                         "cx/gpt-6-sol-medium")
        for model in ("cx/gpt-6.1-sol", "cx/gpt-6.1-sol-max"):
            with self.subTest(model=model):
                selection = gateway.select_routes({"GPTR_MODEL": model})
                self.assertEqual(selection["worker"]["model"], model)
                self.assertEqual(selection["judge"], control["judge"])
                config = gateway.render_config({"LLM_KWARGS": {}}, selection["worker"], "conversation")
                for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
                    self.assertEqual(config[role], "openai:" + model)
                self.assertEqual(config["LLM_KWARGS"]["reasoning_effort"], "max")
                transport = gateway.GatewayTransport("conversation", **selection["worker"])
                payload = {"model": model, "reasoning_effort": "max"}
                request = SimpleNamespace(url=selection["worker"]["base_url"] + "/responses", headers={},
                                          content=json.dumps(payload).encode())
                transport.request_hook(request)
                self.assertEqual(json.loads(request.content), payload)
                self.assertNotIn("x-omniroute-compression", request.headers)
        for env in ({"RUNTIME_WORKER_ARM": "other"}, {"GPTR_MODEL": "sharedgw/cx/gpt-6-astra-max"},
                    {"GPTR_MODEL": "sharedgw/gpt-6-astra-max"},
                    {"RUNTIME_WORKER_ARM": "engines-on", "GPTR_MODEL": "cx/gpt-6-astra-max"},
                     {"GPTR_JUDGE_BASE_URL": "http://127.0.0.1:20129/v1"},
                     {"GPTR_BASE_URL": "https://example.invalid/v1"},
                     {"GPTR_MODEL": "cx/gpt-6-unknown-max"},
                     {"GPTR_MODEL": "cx/gpt-6.1-sol-unknown"},
                     {"GPTR_MODEL": "claude-opus-5-5"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                gateway.select_routes(env)

    def test_nested_max_survives_worker_client_configuration_and_oracle_controls(self):
        gateway = load("gptr_nested_max", RECIPE / "gateway.py")

        class Provider:
            @classmethod
            def from_provider(cls, provider, **kwargs):
                return kwargs

        def assert_nested_max(fields):
            self.assertEqual(fields.get("extra_body", {}).get("reasoning"), {"effort": "max"})

        clients = SimpleNamespace(Client=lambda **kwargs: nullcontext(object()),
                                  AsyncClient=lambda **kwargs: nullcontext(object()))
        for model in ("cx/gpt-6.1-sol", "cx/gpt-6.1-sol-max"):
            with self.subTest(model=model):
                route = gateway.select_routes({"GPTR_MODEL": model})["worker"]
                config = gateway.render_config({"LLM_KWARGS": {}}, route, "conversation")
                assert_nested_max(config["LLM_KWARGS"])
                transport = gateway.GatewayTransport("conversation", **route)

                async def construct():
                    async with transport.worker_clients():
                        return Provider.from_provider("openai", model=model, **config["LLM_KWARGS"])

                with patch.dict(sys.modules, {
                    "httpx": clients,
                    "gpt_researcher.llm_provider.generic.base": SimpleNamespace(GenericLLMProvider=Provider),
                }):
                    fields = asyncio.run(construct())
                assert_nested_max(fields)
                self.assertEqual(fields["model"], model)
                self.assertEqual(fields["reasoning_effort"], "max")
                self.assertEqual(fields["base_url"], "http://127.0.0.1:20128/v1")
                self.assertNotIn("x-omniroute-compression", fields["default_headers"])
                for bad_body in (None, {}, {"reasoning": {}}, {"reasoning": {"effort": "high"}},
                                 {"reasoning": {"effort": "xhigh"}}):
                    invalid = dict(fields)
                    if bad_body is None:
                        invalid.pop("extra_body")
                    else:
                        invalid["extra_body"] = bad_body
                    with self.subTest(bad_body=bad_body), self.assertRaises(AssertionError):
                        assert_nested_max(invalid)

    def test_recipe_contract_and_empty_result(self):
        for name in ("README.md", "install.sh", "run-e2e.sh", "config.template.json",
                     "mcp-policy.json", "pins.json", "e2e/check.py", "e2e/task.json",
                     "e2e/receipt.py", "requirements.lock"):
            self.assertTrue((RECIPE / name).is_file(), name)
        cfg = json.loads((RECIPE / "config.template.json").read_text())
        self.assertEqual(cfg["LLM_KWARGS"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(cfg["LLM_KWARGS"]["api_key"], "local-loopback")
        self.assertIsNone(cfg["LLM_KWARGS"]["temperature"])
        self.assertTrue(cfg["LLM_KWARGS"]["use_responses_api"])
        self.assertEqual(cfg["CONTEXT_FILTER"], "keyword")
        self.assertEqual(cfg["RETRIEVER"], "duckduckgo")
        for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
            self.assertEqual(cfg[role], "openai:${GPTR_MODEL}")
        runner = (RECIPE / "run-e2e.sh").read_text()
        self.assertIn('dispatch.py" run --mode e2e', runner)
        self.assertIn("set -euo pipefail", runner)
        installer = (RECIPE / "install.sh").read_text()
        self.assertIn("set -euo pipefail", installer)
        self.assertIn("--require-hashes", installer)
        policy = json.loads((RECIPE / "mcp-policy.json").read_text())
        self.assertTrue({"ctx_upgrade", "ctx_purge", "ctx_execute", "ctx_execute_file", "ctx_batch_execute",
                         "ctx_fetch_and_index"} <= set(policy["servers"]["context-mode"]["disabled_tools"]))
        self.assertEqual(policy["servers"]["ai-memory"]["enabled_tools"],
                         ["memory_query", "memory_read_page", "memory_recent",
                          "memory_status", "memory_briefing"])
        self.assertEqual(policy["servers"]["socraticode"]["enabled_tools"],
                         ["codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"])
        self.assertEqual(policy["servers"]["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(policy["servers"]["headroom"]["enabled_tools"],
                         ["headroom_compress", "headroom_retrieve", "headroom_stats"])
        self.assertEqual(policy["servers"]["qmd"]["collections"],
                         ["foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog"])
        # A policy file alone is not enforcement; direct unfiltered MCP is disabled.
        self.assertEqual(cfg["MCP_SERVERS"], [])
        self.assertFalse(policy["direct_servers_enabled"])
        for path in RECIPE.rglob("*"):
            if ".research" in path.parts:
                continue
            if path.is_file() and path.suffix in {".sh", ".py", ".json", ".toml"}:
                data = path.read_text()
                self.assertNotIn("0.0.0.0", data, str(path))
                self.assertNotRegex(data, r"sk-[A-Za-z0-9]{20,}", str(path))
                self.assertNotRegex(data, r"(?i)reasoning_effort[\"']?\s*[:=]\s*[\"']auto", str(path))
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.json"
            result.write_text("{}")
            checked = subprocess.run([sys.executable, str(RECIPE / "e2e/check.py"), str(result)],
                                     capture_output=True, text=True)
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            sanity = json.loads(checked.stdout)
            self.assertFalse(sanity["ready_for_grading"])
            self.assertNotIn("passed", sanity)
            self.assertIn("empty_report", sanity["errors"])

    def test_report_transport_controls_do_not_grade_content(self):
        checker = load("gptr_check", RECIPE / "e2e/check.py")
        # A valid report and an obviously wrong report both reach the UPSTREAM
        # grader unchanged. Transport success must never become a quality pass.
        for report in ("# Report\nAn evidence-bearing answer.\n", "The moon is cheese.\n"):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as tmp:
                result = {"report": report}
                self.assertTrue(checker.check(result)["ready_for_grading"])
                self.assertNotIn("passed", checker.check(result))
                destination = Path(tmp) / "idx-12.md"
                checker.export_report(result, destination)
                self.assertEqual(destination.read_bytes(), report.encode("utf-8"))
        for result in ({}, {"report": " \n"}, {"report": None}, {"report": 7}, [], None):
            with self.subTest(result=result):
                self.assertFalse(checker.check(result)["ready_for_grading"])

    def test_graded_report_binding_rejects_replaced_and_mismatched_exports(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        report = b"Original worker report\n"
        expected = hashlib.sha256(report).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            exported = run_dir / "frozen-reports/gptr/idx-12.md"
            exported.parent.mkdir(parents=True)
            (run_dir / "report.md").write_bytes(report)
            exported.write_bytes(report)
            self.assertEqual(grader.read_report(run_dir, 12, expected), report)
            exported.write_bytes(b"Changed report\n")
            with self.assertRaises(ValueError):
                grader.read_report(run_dir, 12, expected)
            (run_dir / "report.md").write_bytes(b"Changed report\n")
            with self.assertRaises(ValueError):
                grader.read_report(run_dir, 12, expected)

    def test_upstream_grade_controls_preserve_scores_and_reject_malformed_output(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        task = {"idx": 12, "content": {"task": "Frozen control", "rubric": {
            "info_recall": ["Fact"], "analysis": ["Analysis"], "presentation": ["Presentation"]}}}
        for score in (1, 0, -1):
            row = {"model": "gptr", "idx": 12, "result": {"task": "Frozen control", "scores": {
                dimension: {item: {"score": score, "reason": "Control", "evidence": ""}}
                for dimension, (item,) in task["content"]["rubric"].items()}}}
            with self.subTest(score=score):
                self.assertEqual(grader.validate_grade([row], task), row["result"])
                self.assertNotIn("passed", grader.validate_grade([row], task))
        for bad in ([], [row, row], [{"model": "gptr", "idx": 12, "result": {"error": "batch failed"}}],
                    [{**row, "idx": 13}], [{**row, "model": "wrong-arm"}], [None]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                grader.validate_grade(bad, task)
        for replacement in ({"score": 2}, {"score": True}, {"score": 1, "reason": [], "evidence": ""}):
            bad = copy.deepcopy(row)
            bad["result"]["scores"]["info_recall"]["Fact"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                grader.validate_grade([bad], task)
        bad = copy.deepcopy(row)
        bad["result"]["scores"]["analysis"] = {}
        with self.assertRaises(ValueError):
            grader.validate_grade([bad], task)

    def test_gateway_transport_headers_and_strict_schema_controls(self):
        gateway = load("gptr_gateway", RECIPE / "gateway.py")
        transport = gateway.GatewayTransport("fixed-conversation")
        payload = {"model": "cx/gpt-6-astra-max", "messages": [{"role": "user", "content": "Grade"}]}
        first = transport.headers(payload)
        second = transport.headers(payload)
        self.assertEqual(first["x-omniroute-session"], "fixed-conversation")
        self.assertEqual(second["x-omniroute-session"], first["x-omniroute-session"])
        self.assertNotEqual(first["Idempotency-Key"], second["Idempotency-Key"])
        # Public wire schema is copied from the upstream DRB-II prompt.
        strict = {**payload, "response_format": gateway.DRB_RESPONSE_FORMAT}
        self.assertTrue(transport.headers(strict))
        bad_schema = copy.deepcopy(strict)
        del bad_schema["response_format"]["json_schema"]["schema"]["properties"]["results"]["items"]["additionalProperties"]
        for bad in ({**payload, "model": "claude-opus-5-5"},
                    {**payload, "model": "openai/gpt-5"},
                    {**payload, "temperature": 0.1},
                    {**payload, "temperature": float("nan")},
                    {**payload, "response_format": {"type": "json_object"}}, bad_schema):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                transport.headers(bad)
        self.assertTrue(transport.headers({**payload, "tools": [{"type": "function"}]}))
        calls = []
        def sender(url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(headers={}, text="native response")
        post = transport.grader_post(sender)
        self.assertEqual(post(gateway.CHAT_URL, headers={"Authorization": "Bearer local-loopback"},
                              json=payload, timeout=600, stream=False).text, "native response")
        self.assertEqual(calls[0][1]["json"]["messages"], payload["messages"])
        self.assertEqual(calls[0][1]["json"]["response_format"], gateway.DRB_RESPONSE_FORMAT)
        self.assertNotIn("temperature", calls[0][1]["json"])
        self.assertIn("Idempotency-Key", calls[0][1]["headers"])
        with self.assertRaises(ValueError):
            post("https://example.invalid/v1/chat/completions", json=payload)

    def test_frozen_task_rejects_changed_bytes_and_recipe_wires_native_grader(self):
        grader = load("gptr_grader", RECIPE / "e2e/grader.py")
        data = b'{"idx":12,"prompt":"Frozen upstream prompt","content":{"task":"Frozen"}}\n'
        selection = {"idx": 12, "row_sha256": hashlib.sha256(data).hexdigest(),
                     "prompt_sha256": hashlib.sha256(b"Frozen upstream prompt").hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tasks_and_rubrics.jsonl"
            source.write_bytes(data)
            task, row = grader.load_task(source, selection)
            self.assertEqual(task["prompt"], "Frozen upstream prompt")
            self.assertEqual(row, data)
            source.write_bytes(data.replace(b"Frozen", b"Changed"))
            with self.assertRaises(ValueError):
                grader.load_task(source, selection)
            source.write_bytes(data + data)
            with self.assertRaises(ValueError):
                grader.load_task(source, selection)
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(pins["grader"]["commit"], "b38f360603db9531b102aef8c166cedb8509b6f6")
        self.assertEqual(pins["grader"]["runner_up_commit"], "852f4022d1f98fb707222e395405136e8f0e8d52")
        self.assertIn("uv sync --locked", (RECIPE / "install.sh").read_text())
        runner = (RECIPE / "run-e2e.sh").read_text()
        gateway = load("gptr_gateway", RECIPE / "gateway.py")
        self.assertEqual(gateway.select_routes({})["judge"]["model"], "cx/gpt-6-astra-max")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", runner)
        native = (RECIPE / "e2e/run.py").read_text()
        self.assertIn("worker_clients()", native)
        self.assertIn("grader-venv/bin/python", native)

    def test_mcp_policy_enforces_calls_and_collection_arguments(self):
        proxy = load("gptr_proxy", RECIPE / "mcp_proxy.py")
        host = {"MEMORY_PROJECT": "synthetic-project", "MEMORY_WORKSPACE": "synthetic-workspace"}
        for server, tool in [("context-mode", "ctx_upgrade"), ("context-mode", "ctx_purge"),
                             ("ai-memory", "memory_write_page"), ("qmd", "multi_get"),
                             ("socraticode", "codebase_search")]:
            with self.subTest(server=server, tool=tool), self.assertRaises(ValueError):
                proxy.scope_arguments(server, tool, {}, host)
        args = proxy.scope_arguments("qmd", "query", {"query": "token practice", "limit": 100}, host)
        self.assertEqual(args["collections"], ["foundation-docs", "foundation-adoption",
                                               "us-equities-foundation", "us-equities-catalog"])
        self.assertEqual(args["searches"], [{"type": "lex", "query": "token practice"}])
        self.assertFalse(args["rerank"])
        self.assertEqual(args["limit"], 5)
        with self.assertRaises(ValueError):
            proxy.scope_arguments("qmd", "query", {"query": "x", "collections": ["private"]}, host)
        for file in ["#abc123", "/etc/passwd", "qmd://private/doc.md", "qmd://foundation-docs/../x",
                     "qmd://foundation-docs/%2e%2e/x", "qmd://foundation-docs/*"]:
            with self.subTest(file=file), self.assertRaises(ValueError):
                proxy.scope_arguments("qmd", "get", {"file": file}, host)
        self.assertEqual(proxy.scope_arguments("qmd", "get",
                         {"file": "qmd://foundation-docs/token-practice.md", "maxLines": 900}, host)["maxLines"], 120)
        self.assertEqual(proxy.scope_arguments("ai-memory", "memory_query", {"project": "other"}, host)["project"],
                         "synthetic-project")
        scoped = proxy.scope_arguments("ai-memory", "memory_query",
                                       {"workspace": "other", "global": True, "scopes": [{"project": "other"}]}, host)
        self.assertEqual(scoped["workspace"], "synthetic-workspace")
        self.assertFalse(scoped["global"])
        self.assertFalse(scoped["answer"])
        self.assertNotIn("scopes", scoped)

    def test_gateway_reader_uses_only_authorized_columns_and_is_read_only(self):
        # Import the public receipt helper without installing either runtime.
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "synthetic.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE call_logs(timestamp TEXT,path TEXT,status INTEGER,model TEXT,"
                            "reasoning_effort_requested TEXT,reasoning_effort_upstream TEXT,tokens_in INTEGER,"
                            "tokens_cache_read INTEGER,tokens_reasoning INTEGER,correlation_id TEXT)")
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:01Z", "/v1/responses", 200, "cx/gpt-6-astra-max", None, "max", 123, 100, 20, "private"))
                con.execute("INSERT INTO call_logs VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("2026-09-27T17:20:02Z", "/private/path", 500, "synthetic@example.invalid", None, None, None, None, None, "other"))
                con.commit()
            before = db.read_bytes()
            rows = receipt.gateway_rows(db, "2026-09-27T17:20:00Z", "2026-09-27T17:20:03Z", "cx/gpt-6-astra-max")
            self.assertEqual(rows["status"], "observed")
            self.assertEqual(rows["rows"][0]["tokens_cache_read"], 100)
            self.assertEqual(len(rows["rows"]), 1)  # unrelated rows are excluded
            self.assertEqual(set(rows["rows"][0]), set(receipt.COLUMNS))
            self.assertEqual(before, db.read_bytes())
            absent = Path(tmp) / "absent.sqlite"
            self.assertEqual(receipt.gateway_rows(absent, "x", "y", "cx/gpt-6-astra-max")["status"], "unavailable")
            self.assertFalse(absent.exists())

    def test_receipt_cannot_promote_report_sanity_to_quality_verdict(self):
        sys.path.insert(0, str(RECIPE / "e2e"))
        try:
            receipt = load("gptr_receipt", RECIPE / "e2e/receipt.py")
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "result.json").write_text('{"report":"A complete-looking but ungraded report"}')
            result = receipt.write_receipt(run_dir, "2026-09-27T00:00:00Z", "2026-09-27T00:01:00Z",
                                           "cx/gpt-6-astra-max", "0.16.0", database=run_dir / "absent.sqlite")
            self.assertNotIn("passed", result)
            self.assertFalse(result["execution_complete"])
            self.assertEqual(result["evaluation"]["status"], "unavailable_or_malformed")
            self.assertTrue(result["report_sanity"]["ready_for_grading"])
            self.assertEqual(result["skills"]["listed_at_start"], [])
            self.assertEqual(result["skills"]["activation_events"], [])
            (run_dir / "result.json").write_text('{"report":')
            interrupted = receipt.write_receipt(run_dir, "2026-09-27T00:00:00Z", "2026-09-27T00:01:00Z",
                                                 "cx/gpt-6-astra-max", None, database=run_dir / "absent.sqlite")
            self.assertFalse(interrupted["execution_complete"])

    def test_skills_lifecycle_and_no_listener_recipe(self):
        readme = (RECIPE / "README.md").read_text()
        for value in ("tools/adoption/install_skills.py", "--manifest blueprints/runtime-workers/skills/manifest.json",
                      '--project-dir "$worker_workspace" --agent universal', "pending the skills-program PR",
                      "127.0.0.1:3730-3799", "rw-gpt-researcher-",
                      "com.native-agent-stack.owner=gpt6-omniroute-framework-integration"):
            self.assertIn(value, readme)
        # This SDK/stdio recipe allocates no Docker resources or listener ports.
        for name in ("install.sh", "run-e2e.sh", "run-upstream-tests.sh"):
            source = (RECIPE / name).read_text()
            self.assertNotIn("docker ", source)
            self.assertNotRegex(source, r"(?:127\.0\.0\.1|localhost):(?:37[12]\d|543[3-9]|38[01]\d)\b")


if __name__ == "__main__":
    unittest.main()
