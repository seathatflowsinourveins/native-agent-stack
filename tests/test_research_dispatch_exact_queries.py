"""Offline exact-query wiring/retention checks; no model or network acceptance.

Public search responses and caller resolution are synthetic fixtures. The
installed-DDGS checks only inspect metadata/source and call a pure native payload
builder, without opening a connection. All written evidence is temporary.
"""

import argparse
import contextlib
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "tools/research/dispatch"
HELPER = ROOT / "tools/research/exact_queries.py"


def load_source(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


exact = load_source("research_exact_queries", HELPER)


class ExactQueryFixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="exact-query-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scope_file = self.root / "scope.json"
        self.query_file = self.root / "queries.json"
        self.scope = {"active_fields": [
            {"layer_id": f"canonical-field-{index}", "modality": "skills" if index >= 32 else "repository"}
            for index in range(45)
        ]}
        self.packet = {"schema_version": 1, "fields": [
            {**field, "queries": [f"  exact Q{index}: café — \"upstream\"\n", f"second Q{index} site:example.org"]}
            for index, field in enumerate(self.scope["active_fields"])
        ]}
        self.scope_file.write_text(json.dumps(self.scope), encoding="utf-8")
        self.scope_sha = hashlib.sha256(self.scope_file.read_bytes()).hexdigest()
        self.write_queries()

    def write_queries(self):
        self.query_file.write_text(json.dumps(self.packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def validate(self):
        return exact.validate(self.query_file, self.scope_file, self.scope_sha)

    def file_record(self, path):
        raw = path.read_bytes()
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


class ApprovedQueryValidationTests(ExactQueryFixtures):
    def test_all_frozen_ids_and_ordered_utf8_query_bytes_are_preserved(self):
        self.packet["fields"].reverse()
        self.write_queries()
        raw, rows, scope_raw = self.validate()
        self.assertEqual(raw, self.query_file.read_bytes())
        self.assertEqual(scope_raw, self.scope_file.read_bytes())
        self.assertEqual(rows, self.packet["fields"])
        self.assertEqual(sum(len(row["queries"]) for row in rows), 90)
        self.assertTrue(rows[0]["queries"][0].startswith("  "))
        self.assertTrue(rows[0]["queries"][0].endswith("\n"))

    def test_two_to_three_queries_is_the_costed_contract(self):
        self.packet["fields"][0]["queries"].append("literal third query")
        self.write_queries()
        self.assertEqual(len(self.validate()[1][0]["queries"]), 3)
        for queries in [[], ["single"], ["1", "2", "3", "4"], [" ", "second"], [1, "second"], ["é" * 2049, "second"]]:
            with self.subTest(queries=str(queries)[:60]):
                self.packet["fields"][0]["queries"] = queries
                self.write_queries()
                with self.assertRaises(ValueError):
                    self.validate()

    def test_duplicate_unapproved_missing_and_extra_field_shapes_are_inverse_failures(self):
        original = json.loads(json.dumps(self.packet))
        mutations = [
            lambda: self.packet["fields"].__setitem__(1, dict(self.packet["fields"][0])),
            lambda: self.packet["fields"][0].__setitem__("layer_id", "not-approved"),
            lambda: self.packet["fields"].pop(),
            lambda: self.packet["fields"][0].__setitem__("rewritten_queries", []),
            lambda: self.packet.__setitem__("model", "not-a-selected-provider"),
            lambda: self.packet.__setitem__("schema_version", True),
            lambda: self.packet["fields"][0].__setitem__("modality", "skills"),
            lambda: self.packet["fields"][0].__setitem__("modality", "repositories"),
        ]
        for mutation in mutations:
            self.packet = json.loads(json.dumps(original))
            mutation()
            self.write_queries()
            with self.assertRaises(ValueError):
                self.validate()

    def test_scope_sha_and_canonical_ids_are_bound_before_retrieval(self):
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            exact.validate(self.query_file, self.scope_file, "0" * 64)
        self.scope["active_fields"][1] = dict(self.scope["active_fields"][0])
        self.scope_file.write_text(json.dumps(self.scope))
        self.scope_sha = exact.sha(self.scope_file.read_bytes())
        with self.assertRaisesRegex(ValueError, "unique IDs"):
            self.validate()

    def test_duplicate_json_keys_in_query_and_scope_are_ambiguous_inverse_failures(self):
        self.query_file.write_text(self.query_file.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON keys"):
            self.validate()
        self.write_queries()
        self.query_file.write_text(self.query_file.read_text().replace('"layer_id": "canonical-field-0"',
            '"layer_id": "canonical-field-0", "layer_id": "canonical-field-0"', 1))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON keys"):
            self.validate()
        self.write_queries()
        self.scope_file.write_text(self.scope_file.read_text().replace('"modality": "repository"',
            '"modality": "repository", "modality": "repository"', 1))
        self.scope_sha = exact.sha(self.scope_file.read_bytes())
        with self.assertRaisesRegex(ValueError, "Duplicate JSON keys"):
            self.validate()


class MechanicalRetentionTests(ExactQueryFixtures):
    def capture(self, client, top_k=0):
        directory = self.root / "capture"
        directory.mkdir()
        factory = mock.Mock(return_value=client)
        rows = [{"layer_id": "canonical-field-0", "modality": "repository",
                 "queries": ["  literal café Q\n", "literal second Q"]}]
        manifest = exact.capture(rows, directory, top_k, factory)
        records = [json.loads(Path(record["path"]).read_text()) for record in manifest["queries"]]
        return directory, manifest, records, factory

    def test_all_vendor_hits_rank_urls_full_snippets_and_exact_queries_are_retained(self):
        results = [{"href": f"https://example.org/{rank}", "title": str(rank), "body": "snippet" * 100}
                   for rank in range(7)]
        client = mock.Mock()
        client.text.return_value = results
        directory, manifest, records, factory = self.capture(client)
        self.assertEqual(manifest["search_calls"], 2)
        self.assertEqual(manifest["fetch_calls"], 0)
        self.assertEqual(manifest["provider_model_calls"], 0)
        self.assertIsNone(manifest["network_request_count"])
        self.assertEqual(client.text.call_args_list, [
            mock.call(query, region="wt-wt", safesearch="moderate", max_results=5, page=1, backend="duckduckgo")
            for query in ["  literal café Q\n", "literal second Q"]
        ])
        self.assertEqual(factory.call_args_list, [mock.call(timeout=15), mock.call(timeout=15)])
        client.extract.assert_not_called()
        for record in records:
            self.assertEqual(record["raw_vendor_results"], results)
            self.assertEqual([s["vendor_result_rank"] for s in record["sources"]], list(range(1, 8)))
            self.assertEqual(record["query_sha256"], exact.sha(record["query"].encode("utf-8")))
            self.assertEqual([s["url"] for s in record["sources"]], [hit["href"] for hit in results])
            self.assertTrue(record["started_at_utc"].endswith("Z"))
            self.assertTrue(record["ended_at_utc"].endswith("Z"))
        for artifact in manifest["queries"]:
            self.assertEqual(artifact["sha256"], exact.sha(Path(artifact["path"]).read_bytes()))
        self.assertTrue((directory / "progress.json").is_file())

    def test_only_explicit_top_k_is_extracted_and_raw_source_hashes_match(self):
        client = mock.Mock()
        client.text.return_value = [{"href": f"https://example.org/{rank}"} for rank in range(7)]
        client.extract.side_effect = lambda url, fmt: {"url": url, "content": "<html>raw source</html>"}
        _, manifest, records, _ = self.capture(client, top_k=1)
        self.assertEqual(manifest["fetch_calls"], 2)
        self.assertEqual(client.extract.call_args_list, [mock.call("https://example.org/0", fmt="text")] * 2)
        self.assertEqual(len(records[0]["sources"]), 7)
        source = records[0]["sources"][0]
        self.assertEqual(source["status"], "captured")
        self.assertEqual(source["raw"]["sha256"], exact.sha(Path(source["raw"]["path"]).read_bytes()))
        self.assertEqual(json.loads(Path(source["raw"]["path"]).read_text())["content"], "<html>raw source</html>")
        self.assertEqual(records[0]["sources"][1]["status"], "retained_not_fetched")

    def test_query_and_source_failures_are_separate_and_never_fallback_or_copy_exception_payload(self):
        client = mock.Mock()
        client.text.side_effect = [RuntimeError("fixture-private-header-value"), [{"href": "https://example.org/source"}]]
        client.extract.side_effect = TimeoutError("fixture-private-header-value")
        directory, manifest, records, _ = self.capture(client, top_k=1)
        self.assertEqual(manifest["search_calls"], 2)
        self.assertEqual(manifest["fetch_calls"], 1)
        self.assertEqual(manifest["error_count"], 2)
        self.assertEqual(records[0]["status"], "failed")
        self.assertEqual(records[0]["error_type"], "RuntimeError")
        self.assertEqual(records[1]["sources"][0]["error_type"], "TimeoutError")
        self.assertEqual(client.text.call_count, 2)
        self.assertNotIn("fixture-private-header-value", "".join(p.read_text() for p in directory.glob("*.json")))

    def test_empty_results_stay_empty_and_unfetched_without_inventing_candidates(self):
        client = mock.Mock()
        client.text.return_value = []
        _, manifest, records, _ = self.capture(client, top_k=5)
        self.assertEqual(manifest["empty_query_count"], 2)
        self.assertEqual(manifest["fetch_calls"], 0)
        self.assertEqual([record["status"] for record in records], ["empty", "empty"])
        self.assertEqual([record["raw_vendor_results"] for record in records], [[], []])

    def test_nonpublic_and_credentialed_url_forms_are_not_fetched(self):
        denied = ["http://127.0.0.1/", "http://[::1]/", "http://10.0.0.1/", "http://localhost/",
                  "http://127.1/", "http://0x7f.0.0.1/", "http://0177.0.0.1/", "http://127.0.0.1./", "http://localhost./",
                  "http://host.local/", "https://fixture-user:fixture-password@example.org/", "file:///tmp/source",
                  "http://[invalid/", None]
        for url in denied:
            with self.subTest(url=url):
                self.assertFalse(exact.public_url(url))
        client = mock.Mock()
        client.text.return_value = [{"href": "http://127.0.0.1/"}, {"href": "https://example.org/public"}]
        _, manifest, records, _ = self.capture(client, top_k=1)
        self.assertEqual(manifest["fetch_calls"], 0)
        client.extract.assert_not_called()
        self.assertEqual(records[0]["sources"][0]["status"], "refused_nonpublic_url_form")

    def test_numeric_url_aliases_are_retained_but_never_extracted(self):
        urls = ["http://127.1/", "http://0x7f.0.0.1/", "http://0177.0.0.1/", "http://127.0.0.1./", "http://localhost./"]
        client = mock.Mock()
        client.text.return_value = [{"href": url} for url in urls]
        _, manifest, records, _ = self.capture(client, top_k=5)
        client.extract.assert_not_called()
        self.assertEqual(manifest["fetch_calls"], 0)
        self.assertEqual([source["url"] for source in records[0]["sources"]], urls)
        self.assertEqual([source["status"] for source in records[0]["sources"]], ["refused_nonpublic_url_form"] * 5)


class ExactDispatchWiringTests(ExactQueryFixtures):
    def setUp(self):
        super().setUp()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.hcom = self.bin / "hcom"
        self.hcom.write_text(f"#!{sys.executable}\n" + textwrap.dedent("""
            import json, os, sys
            from pathlib import Path
            Path(os.environ["SYNTHETIC_FIXTURE_ROOT"]).joinpath("hcom-call.json").write_text(json.dumps(sys.argv[1:]))
            print(json.dumps({"name":"gala", "session_id":"synthetic-native-caller", "tool":"codex"}))
        """))
        self.hcom.chmod(0o755)
        self.env = {"PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "XDG_STATE_HOME": str(self.root / "state"), "SYNTHETIC_FIXTURE_ROOT": str(self.root)}

    def cli(self, *extra):
        return subprocess.run([sys.executable, str(DISPATCH), *extra], text=True, capture_output=True,
                              env=self.env, timeout=10)

    def exact_arguments(self):
        return ["--name", "gala", "--exact-queries-file", str(self.query_file),
                "--approved-scope-file", str(self.scope_file), "--approved-scope-sha256", self.scope_sha]

    def args(self, execute=True):
        return argparse.Namespace(name="gala", exact_queries_file=self.query_file, approved_scope_file=self.scope_file,
                                  approved_scope_sha256=self.scope_sha, mechanical_python=Path(sys.executable),
                                  fetch_top_k=1, execute=execute)

    def fake_identity(self, command, stdout, stderr, timeout):
        self.assertEqual(command, ["hcom", "list", "self", "--json", "--name", "gala"])
        stdout.write(json.dumps({"name": "gala", "session_id": "synthetic-native-caller", "tool": "codex"}).encode())
        return subprocess.CompletedProcess(command, 0)

    def completed_manifest(self, directory, errors=0):
        queries = [query for field in self.packet["fields"] for query in field["queries"]]
        records = []
        for index, query in enumerate(queries):
            record = {"query": query, "status": "failed" if index < errors else "returned"}
            if index < errors:
                record.update(error_type="TimeoutException", error_kind="native_timeout")
            records.append(exact.retained(directory / f"synthetic-query-{index}.json", record))
        return {"status": "captured_with_errors" if errors else "captured", "error_count": errors,
                "search_calls": len(queries), "fetch_calls": 0, "completed_query_count": len(queries),
                "empty_query_count": 0, "queries": records,
                "parsed_queries": {"sha256": exact.sha(self.query_file.read_bytes()), "bytes": self.query_file.stat().st_size}}

    def test_cli_defaults_to_validation_without_runtime_or_network(self):
        result = self.cli(*self.exact_arguments())
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt_path = Path(result.stdout.strip())
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["status"], "validated_no_network")
        self.assertEqual(receipt["logical_search_bound"], 90)
        self.assertEqual(receipt["source_fetch_bound"], 0)
        self.assertNotIn("native_exit_code", receipt)
        self.assertNotIn("runtime", receipt)
        self.assertEqual((receipt_path.parent / "frozen-queries.json").read_bytes(), self.query_file.read_bytes())
        self.assertEqual((receipt_path.parent / "frozen-scope.json").read_bytes(), self.scope_file.read_bytes())
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((self.root / "hcom-call.json").read_text()), ["list", "self", "--json", "--name", "gala"])

    def test_cli_rejects_wrong_scope_before_native_caller_or_worker(self):
        result = self.cli(*self.exact_arguments()[:-1], "0" * 64)
        self.assertEqual(result.returncode, 1)
        receipt = json.loads(Path(result.stdout.strip()).read_text())
        self.assertIn("SHA256 mismatch", receipt["error"])
        self.assertFalse((self.root / "hcom-call.json").exists())

    def test_mutation_before_frozen_file_record_cannot_replace_original_query_identity(self):
        original_raw = self.query_file.read_bytes()
        original_sha = exact.sha(original_raw)
        def mutated_record(path):
            if path.name == "frozen-queries.json":
                replacement = json.loads(path.read_bytes())
                replacement["fields"][0]["queries"].append("extra query inserted after validation")
                path.write_text(json.dumps(replacement), encoding="utf-8")
            return self.file_record(path)
        producer = mock.Mock()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run") as native:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), mutated_record, exact.utc, lambda: ({}, {}), producer)
        self.assertEqual(code, 1)
        native.assert_not_called()
        producer.assert_not_called()
        receipt = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["queries"]["sha256"], original_sha)
        self.assertEqual(receipt["queries"]["bytes"], len(original_raw))
        self.assertNotEqual(receipt["frozen_queries"]["sha256"], original_sha)
        self.assertIn("changed after validation", receipt["error"])
        self.assertNotIn("native_exit_code", receipt)

    def test_mechanical_args_cannot_select_or_silently_fallback_to_deerflow(self):
        for extra in [["--question", "question", "--execute"],
                      [*self.exact_arguments(), "--question", "question"],
                      ["--exact-queries-file", str(self.query_file), "--fetch-top-k", "6"],
                      ["--question", "question", "--fetch-top-k", "0"],
                      ["--question", "question", "--approved-scope-sha256", ""],
                      ["--question", "question", "--approved-scope-file", ""],
                      ["--question", "question", "--mechanical-python", ""],
                      ["--question", "question", "--fetch-top-k", "1"]]:
            with self.subTest(args=extra):
                result = self.cli(*extra)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.root / "hcom-call.json").exists())

    def test_execute_binds_owned_worker_frozen_inputs_and_restricts_environment(self):
        seen = {}
        def producer(launcher, question, directory, tools, *, command, env):
            self.assertIsNone(launcher)
            self.assertIsNone(question)
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(command[1], str(HELPER))
            self.assertEqual(env, {"PATH": os.defpath, "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"})
            self.assertEqual(Path(command[command.index("--worker-file") + 1]).read_bytes(), self.query_file.read_bytes())
            self.assertEqual(command[command.index("--query-sha256") + 1], exact.sha(self.query_file.read_bytes()))
            self.assertEqual(Path(command[command.index("--scope-file") + 1]).read_bytes(), self.scope_file.read_bytes())
            (directory / "producer.stdout").write_text("synthetic mechanical output")
            (directory / "producer.stderr").write_text("")
            exact.retained(directory / "manifest.json", self.completed_manifest(directory))
            seen["directory"] = directory
            return 0, None, None
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), producer)
        self.assertEqual(code, 0)
        receipt = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(receipt["status"], "captured")
        self.assertEqual(receipt["source_fetch_bound"], 90)
        self.assertEqual(receipt["worker_parsed_queries"]["sha256"], receipt["frozen_queries"]["sha256"])
        self.assertEqual(receipt["producer.stdout"]["sha256"], exact.sha((seen["directory"] / "producer.stdout").read_bytes()))

    def test_unresolved_identity_and_nonabsolute_runtime_never_start_retrieval(self):
        producer = mock.Mock()
        args = self.args()
        args.mechanical_python = Path("relative-python")
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(args, self.file_record, exact.utc, lambda: ({}, {}), producer)
        self.assertEqual(code, 1)
        self.assertIn("absolute installed", json.loads(Path(output.getvalue().strip()).read_text())["error"])
        producer.assert_not_called()
        def missing_identity(command, stdout, stderr, timeout):
            stdout.write(b'{}')
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=missing_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), producer)
        self.assertEqual(code, 1)
        self.assertIn("caller resolution failed", json.loads(Path(output.getvalue().strip()).read_text())["error"])
        producer.assert_not_called()

    def test_owned_cancellation_receipt_and_partial_outputs_remain_failed(self):
        def cancelled(launcher, question, directory, tools, **kwargs):
            (directory / "producer.stdout").write_text("synthetic partial output")
            (directory / "producer.stderr").write_text("synthetic cancellation")
            exact.retained(directory / "manifest.json", {"search_calls": 1, "fetch_calls": 0, "status": "failed"})
            exact.retained(directory / "progress.json", {"search_calls": 1, "fetch_calls": 0,
                                                       "inflight_operation": {"kind": "search", "outcome": "pending"}})
            return -15, 15, {"status": "retired", "method": "native procps --session/--sid"}
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), cancelled)
        self.assertEqual(code, 143)
        receipt = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["cancellation"]["status"], "retired")
        self.assertEqual(receipt["failure_kind"], "cancelled_or_terminated")
        self.assertIn("manifest", receipt)
        self.assertIn("producer.stdout", receipt)
        self.assertIn("progress", receipt)
        self.assertIn("unknown", receipt["interruption_boundary"])

    def test_successful_worker_without_matching_parsed_byte_witness_is_rejected(self):
        def wrong_witness(launcher, question, directory, tools, **kwargs):
            manifest = self.completed_manifest(directory)
            manifest["parsed_queries"]["sha256"] = "0" * 64
            exact.retained(directory / "manifest.json", manifest)
            return 0, None, None
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), wrong_witness)
        self.assertEqual(code, 1)
        receipt = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("parsed-query witness", receipt["error"])

    def test_finished_partial_capture_keeps_nonzero_exit_all_errors_and_verified_input_witness(self):
        def partial(launcher, question, directory, tools, **kwargs):
            manifest = self.completed_manifest(directory, errors=2)
            exact.retained(directory / "manifest.json", manifest)
            exact.retained(directory / "progress.json", manifest)
            return 1, None, None
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), partial)
        self.assertEqual(code, 1)
        receipt = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(receipt["status"], "captured_with_errors")
        self.assertEqual(receipt["capture_outcome"], "all_logical_queries_finished")
        self.assertEqual(receipt["native_exit_code"], 1)
        self.assertEqual(receipt["worker_parsed_queries"]["sha256"], receipt["queries"]["sha256"])
        self.assertEqual(receipt["capture_counts"]["completed_query_count"], 90)
        self.assertEqual(receipt["capture_counts"]["error_count"], 2)
        self.assertNotIn("failure_kind", receipt)
        manifest = json.loads(Path(receipt["manifest"]["path"]).read_text())
        self.assertEqual(len(manifest["queries"]), 90)
        for artifact in manifest["queries"][:2]:
            self.assertEqual(artifact["sha256"], exact.sha(Path(artifact["path"]).read_bytes()))
            record = json.loads(Path(artifact["path"]).read_text())
            self.assertEqual(record["error_type"], "TimeoutException")
            self.assertEqual(record["error_kind"], "native_timeout")
        self.assertIn("progress", receipt)

    def test_nonzero_partial_cannot_bypass_input_witness_or_all_query_progress(self):
        for failure in ["wrong_witness", "missing_progress"]:
            with self.subTest(failure=failure):
                def partial(launcher, question, directory, tools, **kwargs):
                    manifest = self.completed_manifest(directory, errors=2)
                    if failure == "wrong_witness":
                        manifest["parsed_queries"]["sha256"] = "0" * 64
                    else:
                        manifest["completed_query_count"] -= 1
                        manifest["queries"].pop()
                    exact.retained(directory / "manifest.json", manifest)
                    return 1, None, None
                with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(exact.subprocess, "run", side_effect=self.fake_identity):
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        code = exact.dispatch_exact(self.args(), self.file_record, exact.utc, lambda: ({}, {}), partial)
                self.assertEqual(code, 1)
                receipt = json.loads(Path(output.getvalue().strip()).read_text())
                self.assertEqual(receipt["status"], "failed")
                self.assertNotIn("capture_outcome", receipt)
                self.assertIn("manifest", receipt)
                self.assertIn("witness" if failure == "wrong_witness" else "counts", receipt["error"])


class FrozenWorkerBoundaryTests(ExactQueryFixtures):
    def worker_arguments(self, query_sha):
        return ["--worker-file", str(self.query_file), "--query-sha256", query_sha,
                "--scope-file", str(self.scope_file), "--scope-sha256", self.scope_sha,
                "--out", str(self.root), "--fetch-top-k", "0"]

    def test_mutation_before_worker_read_is_rejected_without_native_retrieval(self):
        original_sha = exact.sha(self.query_file.read_bytes())
        self.packet["fields"][0]["queries"][0] = "different query after parent freezes and records it"
        self.write_queries()
        with mock.patch.object(exact, "native_ddgs") as native:
            code = exact.main(self.worker_arguments(original_sha))
        self.assertEqual(code, 1)
        native.assert_not_called()
        receipt = json.loads((self.root / "manifest.json").read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["search_calls"], 0)
        self.assertNotIn("parsed_queries", receipt)
        self.assertFalse((self.root / "progress.json").exists())

    def test_interrupt_after_one_returned_query_preserves_counts_and_unknown_inflight_search(self):
        client = mock.Mock()
        client.text.side_effect = [[{"href": "https://example.org/returned", "body": "complete first result"}], KeyboardInterrupt()]
        factory = mock.Mock(return_value=client)
        expected_sha = exact.sha(self.query_file.read_bytes())
        with mock.patch.object(exact, "native_ddgs", return_value=(factory, {"version": "synthetic-ddgs-fixture"})):
            code = exact.main(self.worker_arguments(expected_sha))
        self.assertEqual(code, 130)
        receipt = json.loads((self.root / "manifest.json").read_text())
        self.assertEqual(receipt["status"], "interrupted")
        self.assertEqual(receipt["parsed_queries"]["sha256"], expected_sha)
        self.assertEqual(receipt["parsed_queries"]["bytes"], self.query_file.stat().st_size)
        self.assertEqual(receipt["search_calls"], 2)
        self.assertEqual(receipt["completed_query_count"], 1)
        self.assertEqual(receipt["fetch_calls"], 0)
        self.assertEqual(receipt["inflight_operation"]["kind"], "search")
        self.assertEqual(receipt["inflight_operation"]["outcome"], "unknown")
        self.assertIn("unknown", receipt["interruption_boundary"])
        first = json.loads(Path(receipt["queries"][0]["path"]).read_text())
        self.assertEqual(first["raw_vendor_results"], [{"href": "https://example.org/returned", "body": "complete first result"}])
        second = json.loads(Path(receipt["queries"][1]["path"]).read_text())
        self.assertEqual(second["status"], "in_flight")
        progress = json.loads((self.root / "progress.json").read_text())
        self.assertEqual(progress["search_calls"], 2)
        self.assertEqual(progress["completed_query_count"], 1)
        self.assertEqual(client.text.call_count, 2)

    def test_sigterm_during_source_fetch_retains_returned_hits_and_started_attempt_counts(self):
        client = mock.Mock()
        client.text.return_value = [{"href": "https://example.org/one"}, {"href": "https://example.org/two"}]
        def terminated(url, fmt):
            signal.raise_signal(signal.SIGTERM)
        client.extract.side_effect = terminated
        args = self.worker_arguments(exact.sha(self.query_file.read_bytes()))
        args[-1] = "1"
        previous = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(exact, "native_ddgs", return_value=(mock.Mock(return_value=client), {"version": "synthetic-ddgs-fixture"})):
            code = exact.main(args)
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assertEqual(code, 143)
        receipt = json.loads((self.root / "manifest.json").read_text())
        self.assertEqual(receipt["status"], "interrupted")
        self.assertEqual(receipt["search_calls"], 1)
        self.assertEqual(receipt["fetch_calls"], 1)
        self.assertEqual(receipt["completed_query_count"], 0)
        self.assertEqual(receipt["interrupted_by_signal"], signal.SIGTERM)
        self.assertEqual(receipt["inflight_operation"]["kind"], "fetch")
        self.assertEqual(receipt["inflight_operation"]["outcome"], "unknown")
        record = json.loads(Path(receipt["queries"][0]["path"]).read_text())
        self.assertEqual(record["raw_vendor_results"], client.text.return_value)
        self.assertEqual(len(record["sources"]), 2)
        self.assertEqual(record["sources"][0]["status"], "in_flight")
        self.assertEqual(list(self.root.glob(".capture-*")), [])


class InstalledDDGSContractTests(unittest.TestCase):
    def test_native_version_and_source_changes_refuse_before_client_import(self):
        distribution = mock.Mock(version="changed")
        with mock.patch.object(exact.importlib.metadata, "distribution", return_value=distribution):
            with self.assertRaisesRegex(ValueError, "version changed"):
                exact.native_ddgs()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "public-source.py"
            path.write_text("changed source")
            distribution.version = exact.DDGS_VERSION
            distribution.locate_file.return_value = path
            with mock.patch.object(exact.importlib.metadata, "distribution", return_value=distribution):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    exact.native_ddgs()

    def test_installed_upstream_payload_preserves_literal_query_without_network(self):
        try:
            version = importlib.metadata.version("ddgs")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("installed DDGS is unavailable; source-contract check requires native runtime")
        if version != exact.DDGS_VERSION:
            self.skipTest("installed DDGS version differs from the qualified source")
        _, record = exact.native_ddgs()
        self.assertEqual(record["version"], "9.16.0")
        from ddgs.engines.duckduckgo import Duckduckgo
        engine = object.__new__(Duckduckgo)
        query = "  literal café — \"query\"\n"
        payload = engine.build_payload(query, region="wt-wt", safesearch="moderate", timelimit=None, page=1)
        self.assertEqual(payload, {"q": query, "b": "", "l": "wt-wt"})

    def test_installed_native_empty_engine_exception_is_retained_separately_from_transport_timeout(self):
        try:
            version = importlib.metadata.version("ddgs")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("native DDGS empty-engine check requires the installed runtime")
        if version != exact.DDGS_VERSION:
            self.skipTest("installed DDGS version differs from the qualified source")
        exact.native_ddgs()
        from ddgs.ddgs import DDGS
        from ddgs.exceptions import DDGSException, TimeoutException
        class EmptyEngine:
            provider = "synthetic-no-network"
            name = "synthetic-empty-engine"
            def search(self, query, **kwargs):
                return []
        with mock.patch.dict(os.environ, {}, clear=True):
            client = DDGS(timeout=15)
        with mock.patch.object(DDGS, "_get_engines", return_value=[EmptyEngine()]):
            with self.assertRaises(DDGSException) as raised:
                client.text("literal no-network empty-engine query", max_results=5, page=1, backend="duckduckgo")
            self.assertEqual(raised.exception.args, ("No results found.",))
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                rows = [{"layer_id": "synthetic-canonical-field", "modality": "repository",
                         "queries": ["literal no-network empty-engine query"]}]
                manifest = exact.capture(rows, directory, 0, lambda timeout: client)
                record = json.loads(Path(manifest["queries"][0]["path"]).read_text())
                self.assertEqual(manifest["completed_query_count"], 1)
                self.assertEqual(manifest["error_count"], 1)
                self.assertEqual(manifest["empty_query_count"], 1)
                self.assertEqual(manifest["fetch_calls"], 0)
                self.assertEqual(record["status"], "empty_native_exception")
                self.assertEqual(record["error_kind"], "native_no_results")
                self.assertEqual(record["error_type"], "DDGSException")
                self.assertNotIn("raw_vendor_results", record)
                self.assertEqual(record["sources"], [])
        self.assertEqual(exact.native_error_kind(TimeoutException("fixture-private-header-text")), "native_timeout")
        self.assertEqual(exact.native_error_kind(DDGSException("fixture-private-header-text")), "retrieval_failure")


if __name__ == "__main__":
    unittest.main()
