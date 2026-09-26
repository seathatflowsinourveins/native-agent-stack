"""Check rejection paths that would otherwise allow misleading native receipts."""

import ast
import hashlib
from contextlib import ExitStack, redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_token_ci.py"
SPEC = importlib.util.spec_from_file_location("native_token_ci", SCRIPT)
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)
# A JSON line whose key looks like a file path and whose value is a 64-hex digest: the shape
# gitleaks' generic-api-key rule reports when the path holds a keyword such as "token", and
# which .gitleaks.toml exempts only for listed files (tests/test_gitleaks_config.py).
PATH_KEYED_DIGEST = re.compile(r'^\s*"[^"]*[./][^"]*":\s*"[0-9a-f]{64}",?\s*$', re.MULTILINE)
EVIDENCE = SCRIPT.parents[1] / "evidence/artifacts/native-token-ci-extension-20260926"


class Stop(Exception):
    """Ends a fixture at a chosen command so a test can inspect what it had checked."""


class NativeTokenCIContracts(unittest.TestCase):
    def test_unexpected_exception_and_interrupt_cannot_publish_passing_receipt(self):
        for failure in (TypeError("unexpected fixture shape"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "results"
                with ExitStack() as stack:
                    stack.enter_context(patch.object(sys, "argv", [str(SCRIPT), "--output", str(output)]))
                    stack.enter_context(patch.object(ci.shutil, "which", side_effect=lambda name: f"/stub/{name}"))
                    stack.enter_context(patch.object(ci.Run, "command", side_effect=lambda label, *_args, **_kw: ci.PINS[label.removeprefix("version-")]))
                    stack.enter_context(patch.object(ci, "rtk_fixture", side_effect=failure))
                    for name in ("qmd_fixture", "repomix_fixture", "toon_fixture", "markitdown_fixture",
                                "ast_grep_fixture", "ccusage_fixture", "codebase_memory_mcp_fixture",
                                "headroom_fixture", "jcodemunch_mcp_fixture"):
                        stack.enter_context(patch.object(ci, name))
                    stack.enter_context(redirect_stdout(io.StringIO()))
                    if isinstance(failure, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            ci.main()
                    else:
                        self.assertEqual(ci.main(), 1)
                result = json.loads((output / "receipt.json").read_text())
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["evidence_class"], "local_integration")
                self.assertTrue(result["failures"])
                self.assertTrue(result["cleanup"]["owned_temporary_directory_absent"])

    def test_archive_requires_exact_asset_checksum_and_safe_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.tar.gz"
            for member_name in ("rtk", "../outside"):
                with tarfile.open(archive, "w:gz") as out:
                    member = tarfile.TarInfo(member_name)
                    member.size = 4
                    out.addfile(member, io.BytesIO(b"test"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                checksums = f"{digest}  {archive.name}\n"
                if member_name == "rtk":
                    ci.verify_archive(archive, checksums)
                    with self.assertRaisesRegex(AssertionError, "exact asset"):
                        ci.verify_archive(archive, f"{digest}  other.tar.gz\n")
                    with self.assertRaisesRegex(AssertionError, "checksum mismatch"):
                        ci.verify_archive(archive, f"{'0' * 64}  {archive.name}\n")
                else:
                    with self.assertRaisesRegex(AssertionError, "Unsafe archive"):
                        ci.verify_archive(archive, checksums)

    def test_release_archive_hash_keeps_the_key_retained_reproductions_read(self):
        # evidence/artifacts/sota-refresh-20260925/rtk/native_token_ci_rtk_only.py reads
        # report["rtk_archive_sha256"]; each release-tarball tool keeps its own such key.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            run = ci.Run(output, work)

            def download(label, argv, *_args, **_kwargs):
                if label.startswith("download-"):
                    Path(argv[argv.index("--output") + 1]).write_bytes(label.encode())
                return ""

            with patch.object(run, "command", side_effect=download), patch.object(ci, "verify_archive"):
                for name in ("rtk", "codebase-memory-mcp"):
                    run.install(name)
            for name, key in (("rtk", "rtk_archive_sha256"),
                              ("codebase-memory-mcp", "codebase_memory_mcp_archive_sha256")):
                asset = ci.GITHUB_RELEASES[name]["asset"]
                self.assertEqual(run.report[key], hashlib.sha256(f"download-{name}-{asset}".encode()).hexdigest())

    def test_pack_rejects_changed_or_extra_source(self):
        original = {"a.py": "def greeting():\n    return 19\n"}
        valid = '<files><file path="a.py">\ndef greeting():\n    return 19\n</file></files>'
        ci.verify_pack(valid, original)
        with self.assertRaisesRegex(AssertionError, "source differs"):
            ci.verify_pack(valid.replace("return 19", "return 20"), original)
        with self.assertRaisesRegex(AssertionError, "extra files"):
            ci.verify_pack(valid.replace("</files>", '<file path="secret.txt">extra</file></files>'), original)

    def test_qmd_rejects_truncated_wrong_or_extra_document_content(self):
        uri, body = "qmd://native-ci-docs/note.md", "# Public\nExact fact: 19.\n"
        valid = f"{uri}  #abcdef\n---\n\n{body}\n"
        ci.verify_qmd_document(valid, uri + "?index=native-ci-docs", "#abcdef", body)
        for response in (valid.replace(body, "# Public"),
                         valid.replace(uri, "qmd://other/note.md"),
                         valid + "extra content\n"):
            with self.assertRaises(AssertionError):
                ci.verify_qmd_document(response, uri, "#abcdef", body)

    def test_roundtrip_preserves_boolean_and_integer_types(self):
        ci.verify_json_roundtrip('{"a":true,"b":19}', '{"b":19,"a":true}')
        with self.assertRaisesRegex(AssertionError, "values/types differ"):
            ci.verify_json_roundtrip('{"a":true}', '{"a":1}')

    @staticmethod
    def _executable(path: Path) -> None:
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)

    def _run_with_installed_mcp_tools(self, root: Path):
        """A Run whose headroom and jcodemunch-mcp come from install(), where --install puts them."""
        output, work = root / "result", root / "work"
        output.mkdir()
        work.mkdir()
        run = ci.Run(output, work)
        with patch.object(run, "command"), patch.object(run, "ensure_uv", return_value="/stub/uv"):
            fresh = {name: run.install(name) for name in ("headroom", "jcodemunch-mcp")}
        for path in fresh.values():
            self._executable(Path(path))
        run.tools.update(fresh, mcporter="/stub/mcporter")
        return run, fresh

    def _first_mcporter_calls(self, run):
        """Run each MCP fixture up to its first MCPorter call; return those argument vectors."""
        class Spawned(Exception):
            pass
        calls = []

        def first_call(label, argv, *_args, **_kwargs):
            calls.append(argv)
            raise Spawned(label)

        with patch.object(run, "command", side_effect=first_call):
            for fixture in (ci.headroom_fixture, ci.jcodemunch_mcp_fixture):
                with self.assertRaises(Spawned):
                    fixture(run)
        return calls

    def test_mcp_fixtures_spawn_the_copy_install_just_placed_not_a_path_lookup(self):
        # --install places headroom and jcodemunch-mcp in UV_TOOL_BIN_DIR, which is not on the
        # child PATH. MCPorter splits --stdio like a POSIX shell and spawns its first word through
        # the child PATH, so a bare name finds nothing on a fresh runner and an unverified ambient
        # copy on a developer host. The decoys below stand in for that ambient copy.
        with tempfile.TemporaryDirectory() as directory:
            run, fresh = self._run_with_installed_mcp_tools(Path(directory))
            ambient = Path(directory) / "ambient-bin"
            ambient.mkdir()
            for name in fresh:
                self._executable(ambient / name)
            run.env["PATH"] = str(ambient)
            spawned = []
            for argv in self._first_mcporter_calls(run):
                word = shlex.split(argv[argv.index("--stdio") + 1])[0]
                spawned.append(word if os.path.isabs(word) else shutil.which(word, path=run.env["PATH"]))
            self.assertEqual(spawned, [fresh["headroom"], fresh["jcodemunch-mcp"]])
            self.assertTrue(all(path.startswith(run.env["UV_TOOL_BIN_DIR"]) for path in spawned))

    def test_retained_mcp_command_lines_pass_the_publication_scan(self):
        # A sanitized receipt can be committed as evidence, where scripts/validate.py rejects
        # personal-path shapes such as /home/<name>; run-owned paths must not take that shape.
        spec = importlib.util.spec_from_file_location("validate", SCRIPT.parent / "validate.py")
        validate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validate)
        with tempfile.TemporaryDirectory() as directory:
            run, _fresh = self._run_with_installed_mcp_tools(Path(directory))
            retained = json.dumps([[run.clean(arg) for arg in argv] for argv in self._first_mcporter_calls(run)])
        self.assertIn("HOME=<WORK>/", retained)
        for description, pattern in validate.PRIVATE_CONTENT:
            self.assertIsNone(pattern.search(retained), description)

    def test_tool_state_and_rendezvous_stay_inside_the_owned_work_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            with patch.dict(os.environ, {"CBM_CACHE_DIR": "/shared/cbm", "CBM_RUNTIME_DIR": "/shared/rt",
                                         "HEADROOM_WORKSPACE_DIR": "/shared/headroom",
                                         "MCPORTER_CONFIG": "/shared/mcporter.json"}):
                run = ci.Run(output, work)
            for key in ("CBM_CACHE_DIR", "CBM_RUNTIME_DIR", "HEADROOM_WORKSPACE_DIR", "HEADROOM_CONFIG_DIR",
                        "CODE_INDEX_PATH", "MCPORTER_DAEMON_DIR", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR"):
                self.assertTrue(run.env[key].startswith(str(work) + os.sep), key)
            self.assertNotIn("MCPORTER_CONFIG", run.env)
            config = json.loads(run.mcporter_config.read_text())
            self.assertEqual(config, {"mcpServers": {}, "imports": []})
            self.assertTrue(run.mcporter_config.is_relative_to(work))

    def test_codebase_memory_listing_total_is_parsed_not_substring_matched(self):
        def listing(text):
            return json.dumps({"content": [{"type": "text", "text": text}], "isError": False})
        self.assertEqual(ci.cbm_listed_total(listing("projects: 0  (cols: name root_path branch)\n"
                                                     "total: 0\nreturned: 0\n")), 0)
        self.assertEqual(ci.cbm_listed_total(listing("projects: 1\nfixture  /w/r  main\ntotal: 1\n")), 1)
        for text in ("projects: 0\n", "total: 01\n", "subtotal: 0\n"):
            with self.subTest(text=text), self.assertRaisesRegex(AssertionError, "total"):
                ci.cbm_listed_total(listing(text))

    def test_receipt_lists_source_hashes_as_path_and_digest_objects(self):
        # Receipts are committed evidence under the repository's gitleaks config; a map keyed by
        # "scripts/native_token_ci.py" with a 64-hex value is reported as a generic API key.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            ci.Run(output, work)
            text = (output / "receipt.json").read_text()
        self.assertIsNone(PATH_KEYED_DIGEST.search(text), "receipt keeps a path-keyed digest line")
        listed = json.loads(text)["source_files"]
        self.assertEqual([entry["path"] for entry in listed], list(ci.SOURCE_FILES))
        for entry in listed:
            self.assertEqual(set(entry), {"path", "sha256"})
            self.assertEqual(entry["sha256"], hashlib.sha256((ci.ROOT / entry["path"]).read_bytes()).hexdigest())

    def test_committed_receipts_differ_from_their_originals_only_in_source_hash_shape(self):
        # The two pre-polish receipts were reshaped from harness output that keyed source hashes by
        # path; undoing that one change must reproduce the recorded private originals exactly.
        runs = json.loads((EVIDENCE / "runs.json").read_text())
        reshaped = runs["pre_polish_runs"]["runs"]
        self.assertEqual(len(reshaped), 2)
        for run in reshaped:
            committed = (EVIDENCE / run["receipt"]).read_bytes()
            self.assertEqual(hashlib.sha256(committed).hexdigest(), run["receipt_sha256"])
            report = json.loads(committed)
            original = {}
            for key, value in report.items():
                if key == "source_files":
                    original["source_sha256"] = {entry["path"]: entry["sha256"] for entry in value}
                else:
                    original[key] = value
            restored = (json.dumps(original, indent=2) + "\n").encode()
            self.assertEqual(hashlib.sha256(restored).hexdigest(), run["private_original_sha256"])
        # The final harness writes the list itself, so its receipts are committed unchanged.
        for run in runs["final_runs"]["runs"]:
            committed = (EVIDENCE / run["receipt"]).read_bytes()
            self.assertEqual(hashlib.sha256(committed).hexdigest(), run["receipt_sha256"])
            self.assertNotIn("source_sha256", json.loads(committed))

    def test_no_committed_evidence_json_keys_a_digest_by_path(self):
        # Every JSON file in the run record is committed under the repository's secret scan.
        scanned = sorted(EVIDENCE.glob("*.json"))
        self.assertTrue(scanned)
        for path in scanned:
            with self.subTest(path=path.name):
                self.assertIsNone(PATH_KEYED_DIGEST.search(path.read_text()))

    def test_limits_name_every_unlocked_installer(self):
        # npm and uv tool installs both resolve their dependencies at installation time.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            limits = ci.Run(output, work).report["limits"]
        unlocked = [limit for limit in limits if "resolve at installation" in limit]
        self.assertEqual(len(unlocked), 1)
        self.assertIn("npm", unlocked[0])
        self.assertIn("uv tool (PyPI)", unlocked[0])

    def _run_jcodemunch_until_search(self, root: Path, writes_index_under: str):
        """Run the jCodeMunch fixture with a stand-in server that places the repository index
        under CODE_INDEX_PATH ("index"), under the server HOME's ~/.code-index ("home") or
        nowhere ("none"), then stop at the first search."""
        output, work = root / "result", root / "work"
        output.mkdir()
        work.mkdir()
        run = ci.Run(output, work)
        run.tools.update({"mcporter": "/stub/mcporter", "jcodemunch-mcp": "/stub/jcodemunch-mcp"})

        def server(_run, label, *_args, extra_env=None, **_kwargs):
            if label != "jcodemunch-index-folder":
                raise Stop(label)
            places = {"index": Path(run.env["CODE_INDEX_PATH"]),
                      "home": Path(extra_env["HOME"]) / ".code-index"}
            if writes_index_under in places:
                places[writes_index_under].mkdir(parents=True, exist_ok=True)
                (places[writes_index_under] / "local-fixture-repo.db").write_bytes(b"index")
            return {"success": True, "symbol_count": 3, "repo": "local/fixture-repo"}

        with patch.object(ci, "mcporter_stdio_call", side_effect=server):
            ci.jcodemunch_mcp_fixture(run)
        return run

    def test_jcodemunch_index_check_needs_the_index_file_jcodemunch_writes(self):
        # The harness writes config.jsonc into CODE_INDEX_PATH itself, so a non-empty directory
        # would pass even if jCodeMunch ignored the setting and indexed under ~/.code-index.
        for place in ("home", "none"):
            with self.subTest(index_written_under=place), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(AssertionError, "^jcodemunch-index-inside-run$"):
                    self._run_jcodemunch_until_search(Path(directory), place)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(Stop):
            self._run_jcodemunch_until_search(Path(directory), "index")
        self.assertEqual(ci.jcodemunch_index_file("local/wt-ws2b-f056036f"), "local-wt-ws2b-f056036f.db")
        self.assertEqual(ci.jcodemunch_index_file("local/my repo!"), "local-my-repo.db")
        with self.assertRaisesRegex(AssertionError, "owner/name"):
            ci.jcodemunch_index_file("no-owner")

    def test_later_fixture_reports_the_first_mcporter_failure(self):
        # After a failed --install of MCPorter for Headroom, jCodeMunch must report that cause,
        # not "[Errno 17] File exists" from install() finding the prefix already created.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            run = ci.Run(output, work)
            run.fresh_install = True

            def npm(label, *_args, **_kwargs):
                if label == "install-mcporter":
                    raise AssertionError("install-mcporter: unexpected exit 1")
                return ""

            with patch.object(run, "command", side_effect=npm):
                with self.assertRaisesRegex(AssertionError, "^install-mcporter: unexpected exit 1$"):
                    ci.ensure_mcporter(run)
                with self.assertRaisesRegex(AssertionError, "earlier failure.*install-mcporter: unexpected exit 1"):
                    ci.ensure_mcporter(run)
            self.assertNotIn("mcporter", run.tools)

    def test_ast_grep_outcome_is_frozen_and_structural(self):
        # The oracle comes from Python's own parser and a plain text scan of the frozen fixture,
        # independently of ast-grep: the real calls and the textual matches must differ.
        source = (ci.ROOT / ci.AST_GREP_FIXTURE).read_text()
        calls = sorted(node.lineno for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.Call) and ast.unparse(node.func) == "subprocess.run")
        text = [number for number, line in enumerate(source.splitlines(), 1) if "subprocess.run(" in line]
        self.assertEqual(calls, ci.AST_GREP_CALL_LINES)
        self.assertEqual(text, ci.AST_GREP_TEXT_LINES)
        self.assertNotEqual(calls, text)

        def outputs(structural_lines):
            def command(label, argv, *_args, **_kwargs):
                seen.append(argv)
                if label == "ast-grep-fixture-subprocess-run":
                    return json.dumps([{"file": ci.AST_GREP_FIXTURE, "range": {"start": {"line": line - 1}}}
                                       for line in structural_lines])
                if label == "ast-grep-text-baseline-grep":
                    return "".join(f"{line}:subprocess.run(\n" for line in ci.AST_GREP_TEXT_LINES)
                return "[]"
            return command

        for structural_lines, passes in ((ci.AST_GREP_CALL_LINES, True), (ci.AST_GREP_TEXT_LINES, False)):
            with self.subTest(structural_lines=structural_lines), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output, work = root / "result", root / "work"
                output.mkdir()
                work.mkdir()
                run = ci.Run(output, work)
                run.tools["ast-grep"] = "/stub/ast-grep"
                seen = []
                with patch.object(run, "command", side_effect=outputs(structural_lines)):
                    if passes:
                        ci.ast_grep_fixture(run)
                    else:
                        with self.assertRaisesRegex(AssertionError, "real-calls"):
                            ci.ast_grep_fixture(run)
                # Only the frozen fixture is read, never the live scripts/ tree.
                self.assertTrue(all(ci.AST_GREP_FIXTURE in argv and not any("scripts" in arg for arg in argv)
                                    for argv in seen))

    @staticmethod
    def _new_run(root: Path):
        output, work = root / "result", root / "work"
        output.mkdir()
        work.mkdir()
        return ci.Run(output, work)

    def test_rtk_fixture_runs_the_upstream_inline_filter_tests(self):
        # `rtk verify --require-all` runs the inline tests of RTK's built-in TOML filters, which ship
        # in its release binary: upstream tests, unlike the harness's own checks. A failed or empty
        # upstream result must fail the fixture.
        log = "commit 1\n    CI_FOLLOWUP_FIXED\ncommit 0\n    CI_BASELINE_FIXED\n"

        def rtk(verify_stdout):
            def command(label, argv, *_args, **_kwargs):
                issued.append(argv)
                if label.startswith("rtk-gain-"):
                    Path(run.env["RTK_DB_PATH"]).write_bytes(b"ledger")
                    return json.dumps({"summary": {"total_commands": 0 if label.endswith("before") else 3}})
                if label == "rtk-verify-inline-filter-tests":
                    return verify_stdout
                return log if label in {"git-log-baseline", "rtk-git-log", "rtk-raw-recovery"} else ""
            return command

        for verify_stdout, passes in (("SKIP  RTK hook not installed\n154/154 tests passed\n", True),
                                      ("153/154 tests passed\n", False), ("No inline tests found.\n", False),
                                      ("0/0 tests passed\n", False)):
            with self.subTest(verify_stdout=verify_stdout), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["rtk"] = "/stub/rtk"
                issued = []
                with patch.object(run, "command", side_effect=rtk(verify_stdout)):
                    if passes:
                        ci.rtk_fixture(run)
                    else:
                        with self.assertRaisesRegex(AssertionError, "^rtk-upstream-inline-filter-tests-pass$"):
                            ci.rtk_fixture(run)
                self.assertIn(["/stub/rtk", "verify", "--require-all"], issued)

    def _run_headroom(self, root: Path, compress_records: dict, retrieved: str | None = None):
        """Run the Headroom fixture against a stand-in MCP server that answers the records input with
        `compress_records`, the short note unchanged, and retrieval with `retrieved` (default: the
        stored original)."""
        run = self._new_run(root)
        run.tools.update({"mcporter": "/stub/mcporter", "headroom": "/stub/headroom"})
        records = (ci.ROOT / "fixtures/headroom-records.json").read_text()
        note = (ci.ROOT / "fixtures/headroom-note.txt").read_text()
        stored = {}

        def server(_run, label, _server, _name, tool, args, *_args, **_kwargs):
            if tool == "headroom_compress":
                Path(run.env["HEADROOM_WORKSPACE_DIR"], "ccr_store.db").write_bytes(b"store")
                answer = (dict(compress_records) if args["content"] == records else
                          {"compressed": args["content"], "original_tokens": 49, "compressed_tokens": 49,
                           "tokens_saved": 0, "transforms": ["router:noop"]})
                answer["hash"] = f"{len(stored) + 1:024x}"  # never the all-zero bogus hash
                stored[answer["hash"]] = args["content"]
                return answer
            if args["hash"] in stored:
                return {"hash": args["hash"], "original_content": stored[args["hash"]] if retrieved is None else retrieved}
            return {"error": "Content not found.", "hash": args["hash"]}

        with patch.object(ci, "mcporter_stdio_call", side_effect=server):
            ci.headroom_fixture(run)
        return run, records, note

    def test_headroom_fixture_requires_a_real_saving_and_exact_recovery(self):
        # Every earlier run returned the input unchanged ("router:noop", 0 tokens saved), which stored
        # and retrieved content but never exercised compression. The records input must shrink.
        records = (ci.ROOT / "fixtures/headroom-records.json").read_text()
        saved = {"compressed": "[24]{id:int,latency_ms:int}\n1,17\n", "original_tokens": 826, "compressed_tokens": 511,
                 "tokens_saved": 315, "savings_percent": 38.1, "transforms": ["router:smart_crusher:0.42"]}
        unchanged = {"compressed": records, "original_tokens": 826, "compressed_tokens": 826, "tokens_saved": 0,
                     "savings_percent": 0, "transforms": ["router:noop"]}
        passthrough = {"compressed": records, "original_tokens": 0, "compressed_tokens": 0, "tokens_saved": 0,
                       "savings_percent": 0, "transforms": []}
        with tempfile.TemporaryDirectory() as directory:
            run, _records, _note = self._run_headroom(Path(directory), saved)
        self.assertTrue(all(check["passed"] for check in run.report["checks"]))
        for name, response, retrieved, failing in (
                ("router:noop", unchanged, None, "headroom-compress-json-records-saves-tokens"),
                ("optimize=False passthrough", passthrough, None, "headroom-compress-json-records-saves-tokens"),
                ("wrong saving arithmetic", {**saved, "tokens_saved": 1}, None,
                 "headroom-compress-json-records-saves-tokens"),
                ("partial recovery", saved, records[:-2], "headroom-retrieve-exact-original-records")):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                    self._run_headroom(Path(directory), response, retrieved)

    def _run_jcodemunch_with_source(self, root: Path, source_response: dict):
        run = self._new_run(root)
        run.tools.update({"mcporter": "/stub/mcporter", "jcodemunch-mcp": "/stub/jcodemunch-mcp"})
        search = ("#MUNCH/1 tool=search_symbols enc=ss1\n\nresult_count=2\n\n"
                  "s,fixtures/after.py::greeting#function,greeting,function,fixtures/after.py,1,,def greeting(name),\n"
                  "s,fixtures/before.py::greeting#function,greeting,function,fixtures/before.py,1,,def greeting(name),\n")

        def server(_run, label, *_args, **_kwargs):
            if label == "jcodemunch-index-folder":
                (Path(run.env["CODE_INDEX_PATH"]) / "local-fixture-repo.db").write_bytes(b"index")
                return {"success": True, "symbol_count": 2, "repo": "local/fixture-repo"}
            if label == "jcodemunch-search-symbols-greeting":
                return {"content": [{"type": "text", "text": search}], "isError": False}
            if label == "jcodemunch-get-symbol-source":
                return source_response
            return {"result_count": 0, "results": []}

        with patch.object(ci, "mcporter_stdio_call", side_effect=server):
            ci.jcodemunch_mcp_fixture(run)

    def test_jcodemunch_source_check_rejects_empty_partial_or_other_symbols(self):
        # The oracle must not come from the bounds a response reports: with that, an empty source at
        # line=end_line=999, or the body line alone at line=end_line=2, compared equal.
        source = 'def greeting(name):\n    return "Hello, " + name + "!"'
        exact = {"id": "fixtures/after.py::greeting#function", "kind": "function", "name": "greeting",
                 "file": "fixtures/after.py", "line": 1, "end_line": 2, "signature": "def greeting(name)",
                 "source": source}
        with tempfile.TemporaryDirectory() as directory:
            self._run_jcodemunch_with_source(Path(directory), exact)
        for name, response in (("empty source at line=end_line=999", {**exact, "line": 999, "end_line": 999, "source": ""}),
                               ("body only at line=end_line=2", {**exact, "line": 2, "end_line": 2,
                                                                 "source": source.splitlines()[1]}),
                               ("complete source, wrong bounds", {**exact, "end_line": 3}),
                               ("another symbol", {**exact, "id": "fixtures/before.py::greeting#function",
                                                   "file": "fixtures/before.py"})):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(AssertionError, "^jcodemunch-get-symbol-source-exact-content$"):
                    self._run_jcodemunch_with_source(Path(directory), response)
        # The frozen oracle agrees with Python's own parser over the committed fixture.
        text = (ci.ROOT / "fixtures/after.py").read_text()
        [function] = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)]
        self.assertEqual({key: exact[key] for key in ci.JCODEMUNCH_SYMBOL}, ci.JCODEMUNCH_SYMBOL)
        self.assertEqual((function.name, function.lineno, function.end_lineno),
                         (ci.JCODEMUNCH_SYMBOL["name"], ci.JCODEMUNCH_SYMBOL["line"], ci.JCODEMUNCH_SYMBOL["end_line"]))
        self.assertEqual(ast.get_source_segment(text, function), ci.JCODEMUNCH_SYMBOL_SOURCE)

    def test_controls_driver_never_gives_a_tool_the_callers_home(self):
        # Run as documented (`controls_driver.py --output DIR`), the driver must not let a control that
        # removes a tool's state setting fall back to the caller's real HOME (~/.headroom).
        spec = importlib.util.spec_from_file_location("controls_driver", EVIDENCE / "controls_driver.py")
        driver = importlib.util.module_from_spec(spec)
        with patch.object(sys, "dont_write_bytecode", True):  # no __pycache__ inside the evidence directory
            spec.loader.exec_module(driver)
        seen = []

        def command(run, label, argv, *_args, **_kwargs):
            seen.append((label, run.env.get("HOME"), "HEADROOM_WORKSPACE_DIR" in run.env, list(argv)))
            raise Stop(label)

        def install(setup):
            setup.tools.update({name: f"/stub/{name}" for name in
                                ("mcporter", "rtk", "headroom", "jcodemunch-mcp", "ccusage", "markitdown")})

        with tempfile.TemporaryDirectory() as directory:
            caller_home = Path(directory) / "caller-home"
            caller_home.mkdir()
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, {"HOME": str(caller_home)}))
                stack.enter_context(patch.object(driver.ci.Run, "command", command))
                stack.enter_context(patch.object(driver, "install_tools", install))
                stack.enter_context(patch.object(sys, "argv", ["controls_driver.py", "--output",
                                                               str(Path(directory) / "controls")]))
                stack.enter_context(redirect_stdout(io.StringIO()))
                driver.main()
            self.assertEqual(sorted(caller_home.iterdir()), [])
        workspace_removed = [entry for entry in seen if entry[0].startswith("headroom-") and not entry[2]]
        self.assertTrue(workspace_removed, "no Headroom call ran without HEADROOM_WORKSPACE_DIR")
        for label, home, _workspace, argv in seen:
            with self.subTest(label=label):
                self.assertFalse(Path(home).is_relative_to(caller_home), home)
                self.assertTrue(Path(home).is_relative_to(tempfile.gettempdir()), home)
                self.assertFalse(any(arg == f"HOME={caller_home}" for arg in argv))

    def test_codebase_memory_comparison_is_reproducible_from_the_retained_pre_polish_source(self):
        # runs.json claims the codebase-memory-mcp fixture and every Run method it uses are unchanged
        # since the pre-polish runs; it keeps each definition's digest and the pre-polish source.
        comparison = json.loads((EVIDENCE / "runs.json").read_text())["codebase_memory_fixture_unchanged"]
        retained = EVIDENCE / comparison["pre_polish_harness"]["path"]
        self.assertEqual(hashlib.sha256(retained.read_bytes()).hexdigest(), comparison["pre_polish_harness"]["sha256"])

        recorded = {entry["definition"]: entry for entry in comparison["digests"]}

        def digests(source: str) -> dict:
            found = {}
            for node in ast.parse(source).body:
                nodes = [(f"Run.{item.name}", item) for item in node.body if isinstance(item, ast.FunctionDef)] \
                    if isinstance(node, ast.ClassDef) and node.name == "Run" else []
                name = getattr(node, "name", None) or (node.targets[0].id if isinstance(node, ast.Assign)
                                                        and isinstance(node.targets[0], ast.Name) else None)
                for key, item in nodes + [(name, node)]:
                    if key in recorded:
                        found[key] = hashlib.sha256(ast.get_source_segment(source, item).encode()).hexdigest()
            return found

        self.assertIn("codebase_memory_mcp_fixture", recorded)
        self.assertEqual(digests(retained.read_text()),
                         {name: entry["pre_polish_sha256"] for name, entry in recorded.items()})
        self.assertEqual(sorted(comparison["identical"]),
                         sorted(name for name, entry in recorded.items()
                                if entry["pre_polish_sha256"] == entry["final_sha256"]))
        self.assertEqual(sorted(comparison["changed"]),
                         sorted(name for name in recorded if name not in comparison["identical"]))
        for run in json.loads((EVIDENCE / "runs.json").read_text())["pre_polish_runs"]["runs"]:
            receipt = json.loads((EVIDENCE / run["receipt"]).read_text())
            harness = next(entry["sha256"] for entry in receipt["source_files"] if entry["path"] == "scripts/native_token_ci.py")
            self.assertEqual(harness, comparison["pre_polish_harness"]["sha256"])

    def test_codebase_memory_rendezvous_socket_must_fit_the_unix_address(self):
        ci.require_cbm_socket_fits("/tmp/native-token-ci-abcdefgh/cbm")
        with self.assertRaisesRegex(AssertionError, "TMPDIR"):
            ci.require_cbm_socket_fits("/tmp/" + "x" * 80 + "/cbm")

    def test_timeout_retains_exit_and_scoped_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "private-test-value",
                                         "INDEX_PATH": "/unrelated/index.sqlite"}):
                run = ci.Run(output, work)
            self.assertNotIn("OPENAI_API_KEY", run.env)
            self.assertTrue(run.env["INDEX_PATH"].startswith(str(work)))
            self.assertEqual(run.env["HOME"], os.environ.get("HOME"))
            with self.assertRaisesRegex(AssertionError, "timed out"):
                run.command("timeout-fixture", [sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.05)
            result = json.loads((output / "receipt.json").read_text())
            self.assertTrue(result["commands"][0]["timed_out"])
            self.assertNotEqual(result["commands"][0]["exit_code"], 0)
            self.assertNotIn(str(work), json.dumps(result))
            self.assertNotIn("private-test-value", json.dumps(result))

    @unittest.skipUnless(hasattr(os, "waitid"), "needs os.waitid")
    def test_timeout_signal_refused_by_an_exited_group_is_still_a_timeout(self):
        # The command can finish between the timeout and the signal; macOS then answers killpg with EPERM.
        def refuse_once_exited(pgid, signum):
            os.waitid(os.P_PID, pgid, os.WEXITED | os.WNOWAIT)  # exited but not reaped
            raise PermissionError(errno.EPERM, "Operation not permitted")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            run = ci.Run(output, work)
            with patch.object(ci.os, "killpg", side_effect=refuse_once_exited) as killpg, \
                    self.assertRaisesRegex(AssertionError, "timed out"):
                run.command("exited-group", [sys.executable, "-c", "import time; time.sleep(0.3)"], timeout=0.05)
            self.assertEqual([call.args[1] for call in killpg.call_args_list], [signal.SIGTERM])
            self.assertTrue(json.loads((output / "receipt.json").read_text())["commands"][0]["timed_out"])

    def test_signal_group_raises_a_refusal_while_the_leader_runs(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            with patch.object(ci.os, "killpg", side_effect=PermissionError(errno.EPERM, "Operation not permitted")):
                with self.assertRaises(PermissionError):
                    ci.signal_group(process, signal.SIGTERM)
        finally:
            process.kill()
            process.wait()


if __name__ == "__main__":
    unittest.main()
