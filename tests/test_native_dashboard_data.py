"""Offline guards for the local metadata adapter, not native E2E acceptance."""
import copy
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_dashboard_data", ROOT / "observability/native-data/snapshot.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
RENDER_SPEC = importlib.util.spec_from_file_location("native_dashboard_render", ROOT / "observability/native-data/render.py")
R = importlib.util.module_from_spec(RENDER_SPEC)
RENDER_SPEC.loader.exec_module(R)

# Native schemas observed with RTK 0.49.0 / ai-memory 2.3.2 / QMD 2.8.3.
# Counts are examples; no private path, provider configuration or corpus text.
RTK = b'{"summary":{"total_commands":245,"total_input":736134,"total_output":731933,"total_saved":4370,"avg_savings_pct":0.5936419184550639,"total_time_ms":129921,"avg_time_ms":530}}'
MEMORY = b'{"counts":{"pages_latest":50,"pages_all":140,"sessions":69,"observations":30035},"providers":{"secret":"DO_NOT_PUBLISH"}}'
QMD = b'''QMD Status
Documents
  Total:    67 files indexed
  Vectors:  0 embedded
  Pending:  67 need embedding (run 'qmd embed')
Collections
  selected-collection (qmd://selected-collection/)
    Pattern:  **/*.md
    Files:    67 (updated 14m ago)
'''


class NativeDataTests(unittest.TestCase):
    def config(self):
        return json.loads((ROOT / "observability/native-data/config.example.json").read_text())

    def report(self, now):
        return {"generated_at": M.utc(now), "native": [{"tool": tool, "scope": scope,
                "latest": {"observed_at": M.utc(now), "success": True,
                           "metrics": {"saved": 12, "session_estimated_saved": 3, "raw": {"updated_at": now * 1000}}}}
                for tool, scope in M.REPORT_SCOPES]}

    def test_native_rtk_value_is_not_recomputed_net_difference(self):
        r = M.rtk_metrics(RTK)
        self.assertEqual(r["estimated_saved"], 4370)
        self.assertNotEqual(r["estimated_saved"], r["input_tokens"] - r["output_tokens"])

    def test_native_memory_excludes_provider_configuration(self):
        self.assertEqual(M.memory_metrics(MEMORY)["pages_all"], 140)
        self.assertNotIn("DO_NOT_PUBLISH", json.dumps(M.memory_metrics(MEMORY)))

    def memory_status_with_embedding(self):
        # Synthetic adapter fixture using the native 2.3.2 status schema. This
        # verifies projection/privacy, not the model, corpus or retrieval E2E.
        doc = json.loads(MEMORY)
        doc["providers"].update(
            embedding={"status": "ok", "provider": "local", "model": "all-MiniLM-L6-v2", "dim": 384,
                       "endpoint": "DO_NOT_PUBLISH", "error": "DO_NOT_PUBLISH", "api_key": "DO_NOT_PUBLISH"},
            llm={"status": "disabled", "model": "DO_NOT_PUBLISH", "endpoint": "DO_NOT_PUBLISH"})
        doc["derived"] = {"embedding_rows": 50, "latest_pages_missing_embeddings": 0,
                          "embed_failures_unresolved": 0, "error": "DO_NOT_PUBLISH"}
        return doc

    def test_memory_embedding_projection_keeps_only_reviewed_metadata(self):
        result = M.memory_metrics(json.dumps(self.memory_status_with_embedding()))
        expected = {"embedding_status": "ok", "embedding_provider": "local",
                    "embedding_model": "all-MiniLM-L6-v2", "embedding_dimensions": 384,
                    "llm_status": "disabled", "embedding_rows": 50,
                    "latest_pages_missing_embeddings": 0, "embed_failures_unresolved": 0}
        self.assertEqual({key: result[key] for key in expected}, expected)
        self.assertEqual(result["value"], 50)
        self.assertNotIn("DO_NOT_PUBLISH", json.dumps(result))
        self.assertNotIn("providers", result)
        self.assertNotIn("error", result)
        row = M.base_row("ai-memory", "memory inventory", "native inventory", "status --json",
                         "database-wide", 10000, "memory")
        row.update(result)
        self.assertNotIn("DO_NOT_PUBLISH", json.dumps(M.loki_payload([row], 123)))

    def test_memory_preserves_reported_incomplete_counts(self):
        doc = self.memory_status_with_embedding()
        doc["derived"].update(embedding_rows=140, latest_pages_missing_embeddings=3,
                              embed_failures_unresolved=2)
        result = M.memory_metrics(json.dumps(doc))
        self.assertEqual(result["embedding_rows"], 140)
        self.assertEqual(result["latest_pages_missing_embeddings"], 3)
        self.assertEqual(result["embed_failures_unresolved"], 2)
        self.assertEqual(result["value"], 50)

    def test_memory_missing_optional_fields_are_unavailable_not_zero(self):
        result = M.memory_metrics(MEMORY)
        for key in ("embedding_status", "embedding_provider", "embedding_model", "llm_status"):
            self.assertEqual(result[key], "unavailable")
        for key in ("embedding_dimensions", "embedding_rows", "latest_pages_missing_embeddings", "embed_failures_unresolved"):
            self.assertIsNone(result[key])
        self.assertEqual(result["value"], 50)

    def test_memory_rejects_unreviewed_modes_without_dropping_inventory(self):
        for section, key in (("embedding", "status"), ("embedding", "provider"),
                             ("embedding", "model"), ("llm", "status")):
            for value in ("DO_NOT_PUBLISH", {"private": "DO_NOT_PUBLISH"}, ["ok"], None, True):
                doc = self.memory_status_with_embedding()
                doc["providers"][section][key] = value
                with self.subTest(section=section, key=key, value=value):
                    result = M.memory_metrics(json.dumps(doc))
                    self.assertEqual(result[section + "_" + key], "unavailable")
                    self.assertEqual(result["value"], 50)
                    self.assertNotIn("DO_NOT_PUBLISH", json.dumps(result))

    def test_memory_bounds_optional_numbers_without_fabricated_zero(self):
        for key in ("embedding_rows", "latest_pages_missing_embeddings", "embed_failures_unresolved"):
            for value in (-1, 1.5, True, "0", None, {}, 2 ** 53, 10 ** 400):
                doc = self.memory_status_with_embedding()
                doc["derived"][key] = value
                with self.subTest(key=key, value=value):
                    result = M.memory_metrics(json.dumps(doc))
                    self.assertIsNone(result[key])
                    self.assertEqual(result["embedding_status"], "ok")
                    self.assertEqual(result["value"], 50)
        for value in (0, -1, 65537, 1.5, True, "384", None):
            doc = self.memory_status_with_embedding()
            doc["providers"]["embedding"]["dim"] = value
            with self.subTest(dimension=value):
                self.assertIsNone(M.memory_metrics(json.dumps(doc))["embedding_dimensions"])

    def test_memory_malformed_optional_sections_keep_inventory_available(self):
        for key in ("providers", "derived"):
            for value in (None, [], "DO_NOT_PUBLISH", 0):
                doc = self.memory_status_with_embedding()
                doc[key] = value
                with self.subTest(key=key, value=value):
                    result = M.memory_metrics(json.dumps(doc))
                    self.assertEqual(result["value"], 50)
                    self.assertNotIn("DO_NOT_PUBLISH", json.dumps(result))
        for key in ("embedding", "llm"):
            doc = self.memory_status_with_embedding()
            doc["providers"][key] = ["DO_NOT_PUBLISH"]
            self.assertEqual(M.memory_metrics(json.dumps(doc))[key + "_status"], "unavailable")

    def test_memory_dashboard_shows_native_completeness_and_disabled_llm(self):
        panel = next(panel for panel in R.dashboard()["panels"] if panel["id"] == 13)
        fields = next(t for t in panel["transformations"] if t["id"] == "filterFieldsByName")["options"]["include"]["names"]
        required = {"state", "embedding_status", "embedding_provider", "embedding_rows",
                    "latest_pages_missing_embeddings", "embed_failures_unresolved", "llm_status"}
        self.assertTrue(required <= set(fields))
        rename = next(t for t in panel["transformations"] if t["id"] == "organize")["options"]["renameByName"]
        self.assertTrue(required <= rename.keys())
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "—")
        self.assertEqual(panel["targets"][0]["expr"], R.latest("memory", "ai-memory"))
        failed = M.base_row("ai-memory", "memory inventory", "native inventory", "status --json",
                            "database-wide", 10000, "memory")
        visible_failed = {key: value for key, value in failed.items() if key in fields}
        self.assertEqual(visible_failed, {"state": "unknown"})

    def test_qmd_collection_selection_and_bm25_zero(self):
        r = M.qmd_metrics(QMD, "selected-collection")
        self.assertEqual(r["collection_files"], 67)
        self.assertEqual(r["index_vectors"], 0)
        with self.assertRaises(ValueError):
            M.qmd_metrics(QMD, "unselected")
        with self.assertRaises(ValueError):
            M.qmd_metrics(QMD + QMD, "selected-collection")

    def test_qdrant_uses_points_not_vector_count(self):
        r = M.qdrant_metrics(b'{"status":"ok","result":{"status":"green","points_count":201,"segments_count":2,"vectors_count":402,"payload":"SECRET"}}')
        self.assertEqual(r["value"], 201)
        self.assertNotIn("SECRET", json.dumps(r))

    def test_invalid_measurements_rejected(self):
        for value in (-1, float("nan"), float("inf"), True, "5", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                M.number(value)
        with self.assertRaises(ValueError):
            M.strict_json('{"count":NaN}')
        with self.assertRaises(ValueError):
            M.count(1.5)

    def test_failed_latest_never_falls_back_to_previous_success(self):
        report = self.report(10000)
        report["native"][0]["latest_success"] = copy.deepcopy(report["native"][0]["latest"])
        report["native"][0]["latest"]["success"] = False
        row = M.report_rows(report, 10000, 60, 10000)[0]
        self.assertEqual(row["state"], "unknown")
        self.assertNotIn("value", row)
        self.assertNotIn("estimated_saved", row)

    def test_capture_does_not_refresh_old_native_source(self):
        report = self.report(10000)
        report["native"][0]["latest"]["metrics"]["raw"]["updated_at"] = 1000 * 1000
        row = M.report_rows(report, 10000, 60, 10000)[0]
        self.assertEqual(row["state"], "stale")
        self.assertEqual(row["source_unix"], 1000)
        self.assertEqual(row["source_capture_unix"], 10000)

    def test_missing_future_or_ambiguous_source_becomes_unknown(self):
        for mutate in (lambda r: r["native"][0]["latest"]["metrics"]["raw"].clear(),
                       lambda r: r["native"][0]["latest"]["metrics"]["raw"].update(updated_at=9999999999999),
                       lambda r: r["native"].append(copy.deepcopy(r["native"][0]))):
            report = self.report(10000)
            mutate(report)
            row = M.report_rows(report, 10000, 60, 10000)[0]
            self.assertEqual(row["state"], "unknown")
            self.assertNotIn("value", row)

    def test_report_projection_drops_arbitrary_strings_and_dollars(self):
        report = self.report(10000)
        report["native"][0]["latest"]["metrics"].update(boundary="SECRET", kind="SECRET", dollars=8)
        report["coverage_matrix"] = [dict(id="ai-memory", role="SECRET", latest_pass={"status":"SECRET"}), dict(id="SECRET")]
        rows = M.report_rows(report, 10000, 60, 10000) + M.coverage_rows(report, 10000)
        self.assertNotIn("SECRET", json.dumps(rows))
        self.assertNotIn("dollars", json.dumps(rows))
        self.assertEqual(rows[-1]["state"], "historical")

    def test_config_rejects_remote_redirect_like_and_unscoped_targets(self):
        for url in ("http://example.com:6333", "http://127.0.0.1:6333/path", "http://127.0.0.1:6333?x=1", "http://x@127.0.0.1:6333", "http://127.0.0.1:99999"):
            c = self.config(); c["qdrant"] = {"url": url, "collection": "selected"}
            with self.subTest(url=url), self.assertRaises(ValueError):
                M.validate_config(c)
        c = self.config(); c["loki_url"] = "http://127.0.0.1:6333/"
        with self.assertRaises(ValueError):
            M.validate_config(c)
        c = self.config(); del c["ai_memory"]["workspace"]
        with self.assertRaises(ValueError):
            M.validate_config(c)

    def test_original_audit_and_newer_receipts_have_distinct_meanings(self):
        report = self.report(10000)
        receipt = dict(id="native-later", path="evidence/receipts/native-later.json",
                       component_ids=["agentsview"], claim="PRIVATE CONTENT")
        report["coverage_matrix"] = [dict(id="agentsview", latest_pass={"status": "Not executed in this pass"},
                                         canonical_receipts=[receipt, receipt, {"id": "PRIVATE CONTENT"}])]
        row = M.coverage_rows(report, 10000)[0]
        self.assertEqual(row["coverage_status"], "not_run_in_original_audit")
        self.assertEqual(row["canonical_receipt_count"], 1)
        self.assertEqual(row["timestamp_basis"], "token_report_generated_at")
        self.assertNotIn("PRIVATE CONTENT", json.dumps(row))
        for malformed in (7, "agentsview-unrelated", ["agentsview", 7]):
            report["coverage_matrix"][0]["canonical_receipts"] = [dict(receipt, component_ids=malformed)]
            self.assertEqual(M.coverage_rows(report, 10000)[0]["canonical_receipt_count"], 0)
        report["coverage_matrix"][0]["latest_pass"] = {"status": "Failed local check"}
        self.assertEqual(M.coverage_rows(report, 10000)[0]["coverage_status"], "original_audit_has_record")

    def test_http_disables_proxies_and_redirects(self):
        self.assertIsNone(M.NoRedirect().redirect_request(None, None, 302, None, None, "http://example.com"))
        with patch.object(M.urllib.request, "build_opener") as mocked:
            response = mocked.return_value.open.return_value
            response.read.return_value = b""; response.status = 204
            self.assertEqual(M.request(M.LOKI, b"{}"), (204, b""))
            self.assertEqual(mocked.call_args.args[0].proxies, {})

    def test_command_launch_failure_retains_attempt_and_empty_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            r = M.Recorder(Path(directory), 1)
            self.assertIsNone(r.command("launch", ["/nonexistent/native-tool"], directory))
            rec = r.records[0]
            self.assertEqual(rec["error"], "FileNotFoundError")
            self.assertIsNone(rec["exit_code"])
            self.assertEqual(rec["stdout"]["bytes"], 0)
            self.assertEqual(stat.S_IMODE((Path(directory)/"launch.stdout").stat().st_mode), 0o600)

    def test_nonzero_and_timeout_preserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            r = M.Recorder(Path(directory), 0.1)
            for name, script, error in (("nonzero", "import sys; print('partial',flush=True); print('diagnostic',file=sys.stderr); sys.exit(4)", "nonzero_exit"),
                                        ("timeout", "import time; print('partial',flush=True); time.sleep(30)", "TimeoutError")):
                self.assertIsNone(r.command(name, [sys.executable, "-c", script], directory))
                self.assertEqual(r.records[-1]["error"], error)
                self.assertEqual((Path(directory)/(name+".stdout")).read_bytes(), b"partial\n")

    def test_private_state_rejects_symlink_and_shared_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"state"; path.mkdir(mode=0o755)
            with self.assertRaises(ValueError):
                M.private_dir(path)
            path.chmod(0o700); link=Path(directory)/"link"; link.symlink_to(path, target_is_directory=True)
            with self.assertRaises(ValueError):
                M.private_dir(link)

    def test_output_limit_is_explicit_and_retains_only_bounded_prefix(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(M, "LIMIT", 32):
            r = M.Recorder(Path(directory), 1)
            self.assertIsNone(r.command("overflow", [sys.executable, "-c", "print('x'*100)"], directory))
            self.assertEqual(r.records[-1]["error"], "OverflowError")
            self.assertEqual(r.records[-1]["stdout"]["bytes"], 32)

    def test_an_exited_group_that_refuses_the_kill_is_treated_as_gone(self):
        # The overflow child usually exits before the kill; macOS then answers killpg with EPERM.
        refusal = PermissionError(errno.EPERM, "Operation not permitted")
        with tempfile.TemporaryDirectory() as directory, patch.object(M, "LIMIT", 32), \
                patch.object(M.os, "killpg", side_effect=refusal) as killpg:
            r = M.Recorder(Path(directory), 1)
            self.assertIsNone(r.command("overflow", [sys.executable, "-c", "print('x'*100)"], directory))
        killpg.assert_called_once()
        self.assertEqual((r.records[-1]["error"], r.records[-1]["exit_code"]), ("OverflowError", 0))

    @unittest.skipUnless(sys.platform in ("darwin", "linux") and hasattr(os, "waitid"), "needs os.waitid")
    def test_the_kernel_answer_for_signalling_an_exited_unreaped_group(self):
        # The premise of the handler: macOS refuses with EPERM (XNU killpg1 skips zombies), Linux signals.
        process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        try:
            os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
            try:
                os.killpg(process.pid, signal.SIGKILL)
                outcome = "signalled"
            except PermissionError:
                outcome = "EPERM"
        finally:
            process.wait()
        self.assertEqual(outcome, {"darwin": "EPERM", "linux": "signalled"}[sys.platform])

    def test_complete_generation_unknown_supersedes_prior_values(self):
        with tempfile.TemporaryDirectory() as directory:
            c = M.validate_config(self.config()); c["project"] = directory
            c["token_report"] = str(Path(directory)/"missing.json")
            class FakeRecorder:
                records = []
                def command(self, name, argv, cwd):
                    self.records.append({"completed_at": M.utc(time.time())})
                    return {"rtk-global": RTK, "rtk-project": None, "ai-memory": MEMORY, "qmd": QMD}[name]
            now = time.time(); snapshot = M.collect(c, FakeRecorder(), now)
            rows = snapshot["rows"]
            self.assertEqual(len({r["entity_id"] for r in rows}), len(rows))
            self.assertTrue(all(r["observed_unix"] == now for r in rows))
            self.assertEqual(rows[1]["state"], "unknown")
            self.assertNotIn("value", rows[1])
            self.assertEqual(rows[-1]["unknown_count"], 6)
            payload = M.loki_payload(rows, 123)
            self.assertTrue(all(set(s["stream"]) == {"service_name", "record_kind"} for s in payload["streams"]))
            self.assertNotIn(directory, json.dumps(payload))
            self.assertNotIn("DO_NOT_PUBLISH", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
