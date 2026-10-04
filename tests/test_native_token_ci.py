"""Check rejection paths that would otherwise allow misleading native receipts."""

import ast
from copy import deepcopy
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
                    later = stack.enter_context(patch.object(ci, "rtk_long_log_fixture"))
                    for name in ("qmd_fixture", "repomix_fixture", "toon_fixture", "markitdown_fixture",
                                "markitdown_multi_element_fixture", "ast_grep_fixture", "ast_grep_shell_fixture",
                                "ccusage_fixture", "codebase_memory_mcp_fixture",
                                "headroom_fixture", "jcodemunch_mcp_fixture", "rtk_hook_check_fixture",
                                "rtk_exactness_fixture", "context_mode_fixture", "serena_fixture",
                                "ai_memory_fixture", "context_hub_fixture", "agentsview_fixture"):
                        stack.enter_context(patch.object(ci, name))
                    stack.enter_context(redirect_stdout(io.StringIO()))
                    if isinstance(failure, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            ci.main()
                    else:
                        self.assertEqual(ci.main(), 1)
                        # A tool's later fixture still runs after its first one fails.
                        self.assertEqual(later.call_count, 1)
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

            with patch.object(run, "command", side_effect=download), patch.object(ci, "verify_archive"), \
                    patch.object(ci, "verify_adoption_archive"):
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
            shared = {"CBM_CACHE_DIR": "/shared/cbm", "CBM_RUNTIME_DIR": "/shared/rt",
                      "HEADROOM_WORKSPACE_DIR": "/shared/headroom", "MCPORTER_CONFIG": "/shared/mcporter.json",
                      "CONTEXT_MODE_DIR": "/shared/context-mode", "SERENA_HOME": "/shared/serena",
                      "AI_MEMORY_DATA_DIR": "/shared/ai-memory", "CHUB_DIR": "/shared/chub",
                      "AGENTSVIEW_DATA_DIR": "/shared/agentsview", "AGENTSVIEW_TELEMETRY_ENABLED": "1",
                      "CHUB_TELEMETRY": "1", "AI_MEMORY_EMBEDDING_PROVIDER": "local"}
            with patch.dict(os.environ, shared):
                run = ci.Run(output, work)
            for key in ("CBM_CACHE_DIR", "CBM_RUNTIME_DIR", "HEADROOM_WORKSPACE_DIR", "HEADROOM_CONFIG_DIR",
                        "CODE_INDEX_PATH", "MCPORTER_DAEMON_DIR", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR",
                        "CONTEXT_MODE_DIR", "SERENA_HOME", "AI_MEMORY_DATA_DIR", "CHUB_DIR", "AGENTSVIEW_DATA_DIR"):
                self.assertTrue(run.env[key].startswith(str(work) + os.sep), key)
            # Telemetry and model choices are the harness's own, never inherited; the context-hub
            # control arm depends on no CHUB_TELEMETRY in the run environment.
            self.assertEqual((run.env["AGENTSVIEW_TELEMETRY_ENABLED"], run.env["AI_MEMORY_EMBEDDING_PROVIDER"]),
                             ("0", "none"))
            self.assertNotIn("CHUB_TELEMETRY", run.env)
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

    def test_clean_redacts_uuid_text(self):
        # Source: scripts/validate.py:PRIVATE_CONTENT, including case and embedded matches.
        # Assemble fabricated identifiers so the test source contains no private-content match.
        identifier = "-".join(("a1b2c3d4", "e5f6", "4a7b", "8c9d", "e0f1a2b3c4d5"))
        cases = (
            ("bare", identifier, "<UUID>"),
            ("uppercase", identifier.upper(), "<UUID>"),
            ("sentence", f"warning: device {identifier} unavailable", "warning: device <UUID> unavailable"),
            ("word-embedded", f"prefix{identifier}suffix", "prefix<UUID>suffix"),
            ("store-path", f"wiki/{identifier}/{identifier.upper()}/notes/sample.md",
             "wiki/<UUID>/<UUID>/notes/sample.md"),
        )
        with tempfile.TemporaryDirectory() as directory:
            run = self._new_run(Path(directory))
            for label, value, expected in cases:
                with self.subTest(case=label):
                    self.assertEqual(run.clean(value), expected)

    def test_clean_redacts_personal_home_paths(self):
        # Source: scripts/validate.py:PRIVATE_CONTENT; construct synthetic home paths at runtime.
        with tempfile.TemporaryDirectory() as directory:
            run = self._new_run(Path(directory))
            for base in ("home", "Users"):
                for username in ("someuser", "me", "exampleuser"):
                    personal_home = "/".join(("", base, username))
                    with self.subTest(base=base, username=username, case="bare"):
                        self.assertEqual(run.clean(personal_home), "<HOME-EXAMPLE>")
                    with self.subTest(base=base, username=username, case="help-example"):
                        self.assertEqual(run.clean(f"example option: {personal_home}/notes.txt"),
                                         "example option: <HOME-EXAMPLE>notes.txt")

    def test_clean_preserves_public_examples_and_normal_text(self):
        # Source: scripts/validate.py:PRIVATE_CONTENT's literal example-segment exemption.
        values = (
            "/home/example/notes.txt", "/home/example",
            "/Users/example/notes.txt", "/Users/example",
            "ordinary text: abcdef0123456789 deadbeef /home /Users",
            "short groups: abcd-1234-5678-9abc-def0",
        )
        with tempfile.TemporaryDirectory() as directory:
            run = self._new_run(Path(directory))
            for value in values:
                with self.subTest(value=value):
                    self.assertEqual(run.clean(value), value)

    def test_clean_preserves_literal_path_replacements(self):
        # Source: Run.clean's existing literal substitutions, longest source first.
        with tempfile.TemporaryDirectory() as directory:
            run = self._new_run(Path(directory))
            run.tools["probe"] = str(run.work / "bin" / "probe")
            for value, expected in (
                (str(run.work), "<WORK>"),
                (str(ci.ROOT), "<CHECKOUT>"),
                (str(run.output), "<RESULTS>"),
                (run.tools["probe"], "<TOOL:probe>"),
            ):
                with self.subTest(placeholder=expected):
                    self.assertEqual(run.clean(value), expected)

    def test_clean_applies_literals_before_private_patterns(self):
        # Source: Run.clean's literal contract and scripts/validate.py:PRIVATE_CONTENT.
        identifier = "-".join(("a1b2c3d4", "e5f6", "4a7b", "8c9d", "e0f1a2b3c4d5"))
        native_home = "/".join(("", "home", "someuser"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / identifier
            root.mkdir()
            run = self._new_run(root)
            with patch.dict(os.environ, {"HOME": native_home}):
                self.assertEqual(
                    run.clean(f"{run.work}/file.txt {native_home}/notes.txt {identifier}"),
                    "<WORK>/file.txt <NATIVE_HOME>/notes.txt <UUID>",
                )

    def test_observe_redacts_uuid_shaped_filenames_a_tool_generates(self):
        # Source: Run.observe's own docstring (added alongside the Run.clean fix above) and the
        # real hosted-CI artifact of run 36283215966, whose state_observations["ai-memory-store"]
        # listed real ai-memory-generated paths with UUID components before this fix -- observe()
        # never routed its relative-path listing through clean(), so the redaction the fixture
        # above proves for clean() itself never reached this call site.
        fabricated_id = "-".join(("f1e2d3c4", "b5a6", "4c7d", "8e9f", "a0b1c2d3e4f5"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, work = root / "result", root / "work"
            output.mkdir()
            work.mkdir()
            run = ci.Run(output, work)
            store = work / "data/tool-store"
            (store / "wiki" / fabricated_id / "notes").mkdir(parents=True)
            (store / "wiki" / fabricated_id / "notes" / "page.md").write_text("body\n")
            found = run.observe("fixture-store", store)
        self.assertNotIn(fabricated_id, "\n".join(found))
        self.assertIn("wiki/<UUID>/notes/page.md", found)
        self.assertIn("wiki/<UUID>/", found)
        self.assertIn("wiki/<UUID>/notes/", found)
        self.assertEqual(run.report["state_observations"]["fixture-store"], found)

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

    # Discriminating inputs: each check below must reject what a passthrough or plain-text tool returns.

    @staticmethod
    def _rtk_compact(numbers, trailers=False):
        """RTK 0.50.0's documented git log compaction applied to the fixture messages, written
        independently of the harness's regex: header, first three non-empty non-trailer body lines,
        then `[+N lines omitted]`."""
        blocks = []
        for number in numbers:
            subject, _, body = ci.rtk_log_message(number).partition("\n\n")
            kept = [line for line in body.splitlines() if line
                    and (trailers or not line.startswith(("Signed-off-by:", "Co-authored-by:")))]
            block = [f"{number:07x} {subject} (3 seconds ago) <Native CI Fixture>"]
            block += [f"  {line}" for line in kept[:3]] + [f"  [+{len(kept) - 3} lines omitted]"]
            blocks.append("\n".join(block))
        return "\n".join(blocks) + "\n"

    @staticmethod
    def _raw_git_log(numbers):
        return "\n".join(f"commit {number:040x}\nAuthor: Native CI Fixture <ci@example.invalid>\n"
                         f"Date:   Sat Sep 26 16:00:00 2026 +0000\n\n"
                         + "".join(f"    {line}\n" if line else "\n" for line in ci.rtk_log_message(number).splitlines())
                         for number in numbers)

    def _run_rtk_long_log(self, root: Path, outputs=None, gains=None):
        """Run the long-log fixture against stand-in outputs. `outputs` replaces commands' stdout by
        label; `gains` replaces the three (commands, input, output, saved) ledger readings."""
        newest = ci.RTK_LOG_COMMITS - 1
        every, window = range(newest, -1, -1), range(newest, newest - ci.RTK_LOG_DEFAULT_LIMIT, -1)
        raw = self._raw_git_log(every)
        outputs = {"git-long-log-baseline": raw, "rtk-long-git-log": self._rtk_compact(every),
                   "rtk-long-proxy-git-log": raw, "rtk-long-default-git-log": self._rtk_compact(window),
                   **(outputs or {})}
        gains = iter(gains or [(0, 0, 0, 0), (1, 1284, 720, 564), (2, 2934, 2370, 564)])
        run = self._new_run(root)
        run.tools["rtk"] = "/stub/rtk"

        def command(label, argv, *_args, **_kwargs):
            if label.startswith("rtk-long-gain-"):
                commands, used, emitted, saved = next(gains)
                return json.dumps({"summary": {"total_commands": commands, "total_input": used,
                                               "total_output": emitted, "total_saved": saved}})
            return outputs.get(label, "")

        with patch.object(run, "command", side_effect=command):
            ci.rtk_long_log_fixture(run)
        return run

    def test_rtk_long_log_checks_need_compaction_a_default_window_and_a_filter_only_saving(self):
        newest = ci.RTK_LOG_COMMITS - 1
        every = range(newest, -1, -1)
        # The harness regex agrees with the documented rule and rejects raw git output.
        self.assertTrue(ci.rtk_compacted_log(self._rtk_compact(every), newest, ci.RTK_LOG_COMMITS))
        self.assertFalse(ci.rtk_compacted_log(self._raw_git_log(every), newest, ci.RTK_LOG_COMMITS))
        with tempfile.TemporaryDirectory() as directory:
            run = self._run_rtk_long_log(Path(directory))
        self.assertTrue(all(check["passed"] for check in run.report["checks"]))
        self.assertEqual(len(run.report["checks"]), 6)
        self.assertGreater(run.report["rtk_long_log"]["raw_bytes"], run.report["rtk_long_log"]["rtk_bytes"])
        raw, compact = self._raw_git_log(every), self._rtk_compact(every)
        for name, replace, failing in (
                ("filter returned git's own output", {"outputs": {"rtk-long-git-log": raw}},
                 "rtk-long-log-compacts-every-commit"),
                ("trailers kept", {"outputs": {"rtk-long-git-log": self._rtk_compact(every, trailers=True)}},
                 "rtk-long-log-compacts-every-commit"),
                ("one commit missing", {"outputs": {"rtk-long-git-log": self._rtk_compact(range(newest, 0, -1))}},
                 "rtk-long-log-compacts-every-commit"),
                ("proxy returned the compact form", {"outputs": {"rtk-long-proxy-git-log": compact}},
                 "rtk-long-log-proxy-exact-stdout"),
                ("filtered call not in the ledger", {"gains": [(0, 0, 0, 0), (0, 0, 0, 0), (1, 1650, 1650, 0)]},
                 "rtk-long-log-ledger-records-the-filter-saving"),
                ("proxy recorded a saving", {"gains": [(0, 0, 0, 0), (1, 1284, 720, 564), (2, 2934, 2000, 934)]},
                 "rtk-long-log-ledger-records-no-proxy-saving"),
                ("default showed every commit", {"outputs": {"rtk-long-default-git-log": compact}},
                 "rtk-long-log-default-window-ten-newest-commits")):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                    self._run_rtk_long_log(Path(directory), **replace)

    MARKITDOWN_EXPECTED = (
        "# Release checklist\n\nRun the **pinned** tools with *scoped* state and read the "
        "[upgrade guide](https://example.invalid/guide) first.\n\n## Pinned tools\n\n"
        "| Tool | Version | Check |\n| --- | --- | --- |\n| rtk | 0.50.0 | inline filter tests |\n"
        "| markitdown | 0.1.8 | structure oracle |\n| ast-grep | 0.45.3 | call-site oracle |\n\n### Steps\n\n"
        "1. Install into a fresh prefix\n2. Run each fixture\n3. Keep only sanitized output\n\n"
        "* Record every command\n  + including failures\n* Never read account state\n\n"
        "> Evidence is not authority.\n\n```\nrtk git log -20\nmarkitdown page.html\n```\n\n"
        "Tom & Jerry use `--offline` mode.\n\n![Pipeline diagram](diagram.png)\n")

    def test_markitdown_element_checks_accept_markdownify_spellings_and_reject_html(self):
        html = (ci.ROOT / ci.MARKITDOWN_MULTI_ELEMENT).read_text()
        self.assertTrue(all(ci.markdown_elements(self.MARKITDOWN_EXPECTED).values()))
        other_spellings = (self.MARKITDOWN_EXPECTED.replace("* Record", "- Record").replace("  + including", "    - including")
                           .replace("*scoped*", "_scoped_")
                           .replace("```\nrtk git log -20\nmarkitdown page.html\n```",
                                    "    rtk git log -20\n    markitdown page.html"))
        self.assertTrue(all(ci.markdown_elements(other_spellings).values()))
        for baseline in (html, ci.tag_stripped_text(html)):
            self.assertFalse(any(ci.markdown_elements(baseline).values()))
            self.assertTrue(any(text in baseline for text in ci.MARKITDOWN_HIDDEN_TEXT))
        without_table = "\n".join(line for line in self.MARKITDOWN_EXPECTED.splitlines() if not line.startswith("|"))
        self.assertEqual([key for key, value in ci.markdown_elements(without_table).items() if not value], ["table"])

    def _run_markitdown_multi_element(self, root: Path, markdown: str | None):
        """The fixture with a stand-in converter that writes `markdown`, or copies the HTML when None."""
        run = self._new_run(root)
        run.tools["markitdown"] = "/stub/markitdown"

        def command(label, argv, *_args, **_kwargs):
            target = Path(argv[argv.index("-o") + 1])
            target.write_text(Path(argv[1]).read_text() if markdown is None else markdown)
            return ""

        with patch.object(run, "command", side_effect=command):
            ci.markitdown_multi_element_fixture(run)
        return run

    def test_markitdown_multi_element_fixture_rejects_passthrough_and_leaked_script_text(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self._run_markitdown_multi_element(Path(directory), self.MARKITDOWN_EXPECTED)
        self.assertTrue(all(check["passed"] for check in run.report["checks"]))
        for name, markdown, failing in (
                ("HTML copied through", None, "markitdown-multi-element-structure-converted"),
                ("script text kept", self.MARKITDOWN_EXPECTED + "\nvar marker = \"NativeCiScriptBody\";\n",
                 "markitdown-script-style-and-comment-text-dropped"),
                # markdownify escapes Markdown characters in text it keeps; the check reads through that.
                ("comment text kept with an escape", self.MARKITDOWN_EXPECTED + "\nNativeCi\\HtmlComment\n",
                 "markitdown-script-style-and-comment-text-dropped")):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                    self._run_markitdown_multi_element(Path(directory), markdown)

    def test_ast_grep_shell_outcome_is_frozen_and_structural(self):
        # The oracle comes from Python's own parser and a regex over the frozen fixture's lines.
        source = (ci.ROOT / ci.AST_GREP_SHELL_FIXTURE).read_text()
        calls = sorted([node.lineno, node.end_lineno] for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.Call) and ast.unparse(node.func) == "subprocess.run"
                       and any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant)
                               and keyword.value.value is True for keyword in node.keywords))
        every = sorted([node.lineno, node.end_lineno] for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.Call) and ast.unparse(node.func) == "subprocess.run")
        text = [number for number, line in enumerate(source.splitlines(), 1)
                if re.search(ci.AST_GREP_SHELL_TEXT_REGEX, line)]
        self.assertEqual(calls, ci.AST_GREP_SHELL_CALL_RANGES)
        self.assertEqual(text, ci.AST_GREP_SHELL_TEXT_LINES)
        self.assertTrue(any(end > start for start, end in calls), "one match must span several lines")

        def outputs(ranges):
            def command(label, argv, *_args, **_kwargs):
                seen.append(argv)
                if label == "ast-grep-shell-true-calls":
                    return json.dumps([{"file": ci.AST_GREP_SHELL_FIXTURE,
                                        "range": {"start": {"line": start - 1}, "end": {"line": end - 1}}}
                                       for start, end in ranges])
                return "".join(f"{line}:subprocess.run(\n" for line in ci.AST_GREP_SHELL_TEXT_LINES)
            return command

        for name, ranges, passes in (("structural matches", calls, True),
                                     ("the regex's lines", [[line, line] for line in text], False),
                                     ("every subprocess.run call", every, False)):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["ast-grep"] = "/stub/ast-grep"
                seen = []
                with patch.object(run, "command", side_effect=outputs(ranges)):
                    if passes:
                        ci.ast_grep_shell_fixture(run)
                    else:
                        with self.assertRaisesRegex(AssertionError, "^ast-grep-shell-true-calls-match-across-lines$"):
                            ci.ast_grep_shell_fixture(run)
                self.assertTrue(all(ci.AST_GREP_SHELL_FIXTURE in argv for argv in seen))

    @staticmethod
    def _pack(files: dict) -> str:
        from xml.sax.saxutils import escape
        return "<repomix><files>" + "".join(f'<file path="{path}">\n{escape(text)}\n</file>'
                                            for path, text in files.items()) + "</files></repomix>"

    def test_repomix_compress_check_rejects_an_uncompressed_pack(self):
        originals = {name: (ci.ROOT / "fixtures" / name).read_text() for name in ("before.py", "after.py")}
        signatures = {name: "def greeting(name)" for name in originals}
        for name, structure, passes in (("signatures only", signatures, True), ("uncompressed", originals, False)):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["repomix"] = "/stub/repomix"

                def command(label, argv, *_args, _structure=structure, **_kwargs):
                    packed = originals if label == "repomix-selected-originals" else _structure
                    Path(argv[argv.index("--output") + 1]).write_text(self._pack(packed))
                    return ""

                with patch.object(run, "command", side_effect=command):
                    if passes:
                        ci.repomix_fixture(run)
                    else:
                        with self.assertRaisesRegex(AssertionError, "^repomix-compress-keeps-signatures-drops-bodies$"):
                            ci.repomix_fixture(run)
                # The earlier structural check passes either way: it could not tell the two apart.
                self.assertIn({"label": "repomix-structural-output-only", "passed": True}, run.report["checks"])

    def test_toon_tabular_check_rejects_copied_json_and_another_delimiter(self):
        # The stand-in decoder always returns the records, isolating the tabular check. The real TOON
        # 4.1.1 decoder reads a copied JSON file as one key and a string, so the round trip rejects
        # that case first; a pipe-delimited block round-trips and only the tabular check rejects it.
        records = (ci.ROOT / "fixtures/records.json").read_text()
        piped = "items[2|]{name|enabled|count}:\n  alpha|true|2\n  beta|false|3\n"
        for name, encoded, passes in (("tabular", ci.TOON_TABULAR_RECORDS + "\n", True),
                                      ("JSON copied through", records, False), ("pipe delimiter", piped, False)):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["toon"] = "/stub/toon"

                def command(label, argv, *_args, _encoded=encoded, **_kwargs):
                    if "-o" in argv:
                        output = Path(argv[argv.index("-o") + 1])
                        output.write_text(_encoded if label == "toon-encode-statistics" else records)
                    return ""

                with patch.object(run, "command", side_effect=command):
                    if passes:
                        ci.toon_fixture(run)
                    else:
                        with self.assertRaisesRegex(AssertionError, "^toon-tabular-encoding-smaller-than-json$"):
                            ci.toon_fixture(run)


    def test_rtk_hook_check_fixture_discriminates_exclusions_and_partial_rewrites(self):
        # RTK 0.50.0: rtk_hook_check_fixture/hook_decision, recipes/README.md:143-160,
        # fixtures/rtk-hook-exclusions.toml, and full-save/PLAN.md section 4.1.
        probes = (
            ("git show HEAD:x | tail -n 5", None, "rtk git show HEAD:x | tail -n 5"),
            ("git -C . show --no-color HEAD:x | tail -n 5", None,
             "rtk git -C . show --no-color HEAD:x | tail -n 5"),
            ("diff a.txt missing.txt", None, "rtk diff a.txt missing.txt"),
            ("git -C repo show HEAD:x", None, "rtk git -C repo show HEAD:x"),
            ("git --git-dir /r/.git show HEAD:x", None, "rtk git --git-dir /r/.git show HEAD:x"),
            ("git --work-tree /w branch -a", None, "rtk git --work-tree /w branch -a"),
            ("git branch -a", None, "rtk git branch -a"),
            ("git -C . branch", None, "rtk git -C . branch"),
            ("git show HEAD~1", "rtk git show HEAD~1", "rtk git show HEAD~1"),
            ("git show --stat HEAD", "rtk git show --stat HEAD", "rtk git show --stat HEAD"),
            ("git --git-dir /r/.git status", "rtk git --git-dir /r/.git status", "rtk git --git-dir /r/.git status"),
            ("git push origin branch", "rtk git push origin branch", "rtk git push origin branch"),
            ('git commit -m "update branch docs"', 'rtk git commit -m "update branch docs"',
             'rtk git commit -m "update branch docs"'),
            ("jq -r .x f.json", None, "rtk jq -r .x f.json"),
            ("git status && jq .", "rtk git status && jq .", "rtk git status && rtk jq ."),
            ("git status && gh pr view 1 | head -n 5", "rtk git status && gh pr view 1 | head -n 5",
             "rtk git status && gh pr view 1 | head -n 5"),
            ("gh pr view 1 | head -n 5", None, None),
            ("git status && gh pr view 1", "rtk git status && rtk gh pr view 1", "rtk git status && rtk gh pr view 1"),
            ("git status && ls -la | wc -l", "rtk git status && ls -la | wc -l", "rtk git status && ls -la | wc -l"),
        )
        self.assertEqual(ci.RTK_HOOK_PROBES, probes)
        self.assertEqual(ci.RTK_HOOK_NEGATIVE_CONTROLS, tuple(probe[0] for probe in probes[-4:]))
        labels = (
            "rtk-hook-five-exclusions-answer-every-probe-as-recorded",
            "rtk-hook-jq-excluded-and-the-git-part-beside-it-rewritten",
            "rtk-hook-negative-controls-rewrite-only-eligible-parts",
            "rtk-hook-defaults-rewrite-every-form-the-exclusions-keep-native",
        )
        recorded = {"five-exclusions": {probe: excluded for probe, excluded, _default in probes},
                    "defaults": {probe: default for probe, _excluded, default in probes}}
        variants = [("recorded", recorded, None),
                    ("passthrough", {arm: dict.fromkeys(answers) for arm, answers in recorded.items()}, labels[0]),
                    ("ignored exclusions", {"five-exclusions": recorded["defaults"],
                                            "defaults": recorded["defaults"]}, labels[0]),
                    ("defaults unchanged", {"five-exclusions": recorded["five-exclusions"],
                                            "defaults": recorded["five-exclusions"]}, labels[3])]
        for probe, wrong, failing in (
                ("jq -r .x f.json", "rtk jq -r .x f.json", labels[1]),
                ("git status && jq .", None, labels[1]),
                ("git status && gh pr view 1 | head -n 5", "rtk git status && rtk gh pr view 1 | head -n 5", labels[2]),
                ("gh pr view 1 | head -n 5", "rtk gh pr view 1 | head -n 5", labels[2]),
                ("git status && gh pr view 1", "rtk git status && gh pr view 1", labels[2]),
                ("git status && ls -la | wc -l", "rtk git status && rtk ls -la | wc -l", labels[2])):
            answers = deepcopy(recorded)
            answers["five-exclusions"][probe] = wrong
            variants.append((probe, answers, failing))

        for name, answers, failing in variants:
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["rtk"] = "/stub/rtk"

                def command(label, argv, *_args, **kwargs):
                    arm, number = label.removeprefix("rtk-hook-check-").rsplit("-", 1)
                    probe = probes[int(number) - 1][0]
                    self.assertEqual(argv, ["/stub/rtk", "hook", "check", "--agent", "claude", probe])
                    self.assertEqual(Path(kwargs["env"]["XDG_CONFIG_HOME"]).name, arm)
                    rewritten = answers[arm][probe]
                    stdout = "" if rewritten is None else rewritten + "\n"
                    run.report["commands"].append({"label": label, "stdout": stdout,
                                                   "exit_code": 1 if rewritten is None else 0,
                                                   "stderr": "[rtk] No hook installed\n" + (
                                                       f"No rewrite for: {probe}\n" if rewritten is None else "")})
                    return stdout

                original_check = run.check

                def check(label, condition):
                    # The aggregate fails before its two redundant subchecks. Observe its real
                    # failure, then continue to exercise the selected subcheck's real assertion.
                    if label == labels[0] and failing in labels[1:3]:
                        with self.assertRaisesRegex(AssertionError, f"^{label}$"):
                            original_check(label, condition)
                    else:
                        original_check(label, condition)

                with patch.object(run, "command", side_effect=command), patch.object(run, "check", side_effect=check):
                    if failing is None:
                        ci.rtk_hook_check_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.rtk_hook_check_fixture(run)
                self.assertEqual(len(run.report["commands"]), 2 * len(probes))

    @staticmethod
    def _rtk_exactness_cases():
        # Synthetic native/0.51.0/proxy arms; diff status follows upstream bf23cff.
        # Remaining outcomes come from the 0.50.0 rtk_exactness_fixture predicates;
        # the committed port cites full-save/rtk/exactness.sh (2026-09-26 scratch, not committed).
        blob = "".join(f"line {number:05d} abcdefghijklmnopqrstuvwxyz0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
                       for number in range(1, 401))
        subjects = ["post", "merge feature", "feat", *[f"c{number}" for number in range(12, -1, -1)]]
        native_log = "".join(f"commit {number:040x}\n    {subject}\n\n" for number, subject in enumerate(subjects))
        rtk_log = "".join(f"{number:07x} {subject}\n" for number, subject in enumerate(
            [subject for subject in subjects if subject != "merge feature"][:10]))
        rows = [f"{number} item-{number:03d} " + (
            "long " + "x" * 150 + f" {number}" if number % 9 == 0 else f"short {number}")
                for number in range(1, 61)]
        jq = "\n".join([row if len(row) <= 120 else row[:117] + "..." for row in rows[:40]] + [
            "... (20 lines truncated)", "[full output: rtk recall abc123]"]) + "\n"
        diff = "2c2\n< beta\n---\n> gamma\n"
        grep = "src/deep/pkg/f1.txt\nsrc/deep/pkg/f2.txt\nsrc/deep/pkg/f3.txt\n"
        cases = {}
        for case, native_exit, native_stdout, rtk_exit, rtk_stdout in (
                ("t1-git-show-blob", 0, blob, 0, "".join(blob.splitlines(keepends=True)[:100]) +
                 "... (+300 lines) [see remaining: rtk proxy git show HEAD:big.txt]\n"),
                ("t1b-git-c-show-blob", 0, blob, 0, "".join(blob.splitlines(keepends=True)[:100]) +
                 "... (+300 lines) [see remaining: rtk proxy git -C . show HEAD:big.txt]\n"),
                ("t2-diff-missing-file", 2, "", 2, ""),
                ("t2b-diff-two-files", 1, diff, 1, diff),
                ("t3-git-branch-all", 0, "+ feature\n* main\n  remotes/origin/feature\n  remotes/origin/main\n",
                 0, "  remote-only (1):\n    feature\n"),
                ("t4-git-log", 0, native_log, 0, rtk_log),
                ("t4b-git-log-subjects", 0, "\n".join(subjects) + "\n", 0,
                 "\n".join(subject for subject in subjects if subject != "merge feature") + "\n"),
                ("t5-find-missing-dir", 1, "", 0, ""),
                ("t6-grep-file-list", 0, grep, 0, grep),
                ("t7-jq-rows", 0, "\n".join(rows) + "\n", 0, jq)):
            native = {"exit": native_exit, "stdout": native_stdout}
            cases[case] = {"native": native, "rtk": {"exit": rtk_exit, "stdout": rtk_stdout}, "proxy": dict(native)}
        return cases, blob

    def test_rtk_exactness_checks_reject_passthrough_and_broken_recovery(self):
        # Mock-free check of the eight exactness outcomes; v0.51.0 diff status repair is included.
        labels = (
            "rtk-exactness-git-show-blob-window-changes-its-tail",
            "rtk-exactness-diff-missing-file-preserves-native-exit-code",
            "rtk-exactness-branch-list-misreports-a-worktree-branch-as-remote-only",
            "rtk-exactness-log-caps-at-ten-commits-and-drops-the-merge",
            "rtk-exactness-find-on-a-missing-directory-masks-the-exit-code",
            "rtk-exactness-jq-truncates-rows-and-width",
            "rtk-exactness-controls-diff-and-grep-unchanged",
            "rtk-exactness-proxy-restores-native-output-and-exit",
        )
        cases, blob = self._rtk_exactness_cases()
        self.assertEqual(len(cases), 10)
        self.assertEqual(ci.rtk_exactness_checks(cases, blob), dict.fromkeys(labels, True))
        variants = []
        for case, failing in (
                ("t1-git-show-blob", labels[0]), ("t1b-git-c-show-blob", labels[0]),
                ("t3-git-branch-all", labels[2]),
                ("t4-git-log", labels[3]), ("t4b-git-log-subjects", labels[3]),
                ("t5-find-missing-dir", labels[4]), ("t7-jq-rows", labels[5])):
            variants.append((case, "rtk", dict(cases[case]["native"]), failing))
        # Upstream v0.51.0 tests/diff_byte_accuracy_test.rs: missing_operand_exits_two_and_names_the_failed_path.
        # Reject the former exit=1 result and a broken native control.
        variants.append(("t2-diff-missing-file", "rtk", {"exit": 1, "stdout": ""}, labels[1]))
        variants.append(("t2-diff-missing-file", "native", {"exit": 1, "stdout": ""}, labels[1]))
        for case in ("t1-git-show-blob", "t1b-git-c-show-blob"):
            variants.append((case, "rtk", {"exit": 0, "stdout": ""}, labels[0]))
        for case in ("t2b-diff-two-files", "t6-grep-file-list"):
            for field, wrong in (("stdout", "lost output\n"), ("exit", 42)):
                variants.append((case, "rtk", {**cases[case]["rtk"], field: wrong}, labels[6]))
        for case in cases:
            for field, wrong in (("stdout", "lost output\n"), ("exit", 42)):
                variants.append((case, "proxy", {**cases[case]["proxy"], field: wrong}, labels[7]))
        for case, arm, wrong, failing in variants:
            with self.subTest(case=case, arm=arm, response=wrong):
                changed = deepcopy(cases)
                changed[case][arm] = wrong
                if arm == "native":
                    changed[case]["proxy"] = dict(wrong)
                checks = ci.rtk_exactness_checks(changed, blob)
                self.assertEqual(checks, {label: label != failing for label in labels})
                # The fixture feeds these exact booleans and labels to Run.check -> require.
                with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                    ci.require(checks[failing], failing)

    def test_rtk_exact_rows_exercises_the_jq_line_and_width_limits(self):
        # rtk_exact_rows and rtk 0.50.0 src/filters/jq.toml: max_lines=40, width=120.
        rows = ci.rtk_exact_rows()
        self.assertEqual(len(rows), 60)
        self.assertEqual([row["id"] for row in rows], list(range(1, 61)))
        self.assertEqual([row["name"] for row in rows], [f"item-{number:03d}" for number in range(1, 61)])
        self.assertEqual([row["id"] for row in rows if len(row["note"]) > 120], [9, 18, 27, 36, 45, 54])
        cases, blob = self._rtk_exactness_cases()
        failing = "rtk-exactness-jq-truncates-rows-and-width"
        for name, input_rows, passes in (
                ("sixty with wide ninth rows", rows, True),
                ("line limit never reached", rows[:40], False),
                ("width limit never reached", [{**row, "note": "short"} for row in rows], False)):
            with self.subTest(rows=name):
                changed = deepcopy(cases)
                native = {"exit": 0, "stdout": "".join(f"{row['id']} {row['name']} {row['note']}\n" for row in input_rows)}
                changed["t7-jq-rows"]["native"] = native
                changed["t7-jq-rows"]["proxy"] = dict(native)
                checks = ci.rtk_exactness_checks(changed, blob)
                self.assertEqual(checks[failing], passes)
                if not passes:
                    with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                        ci.require(checks[failing], failing)

    def test_rtk_exactness_fixture_dispatches_native_rtk_and_proxy_arms(self):
        # rtk_exactness_fixture's git-fixture/three-arm protocol; all commands, including Git
        # setup, are intercepted at Run.command. The pure predicate test above supplies the oracle.
        for name, failing in (
                ("recorded", None),
                ("git show unchanged", "rtk-exactness-git-show-blob-window-changes-its-tail"),
                ("git show empty", "rtk-exactness-git-show-blob-window-changes-its-tail"),
                ("proxy loses exit", "rtk-exactness-proxy-restores-native-output-and-exit")):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["rtk"] = "/stub/rtk"
                cases, blob = self._rtk_exactness_cases()
                if name == "git show unchanged":
                    cases["t1-git-show-blob"]["rtk"] = dict(cases["t1-git-show-blob"]["native"])
                if name == "git show empty":
                    cases["t1-git-show-blob"]["rtk"]["stdout"] = ""
                if name == "proxy loses exit":
                    cases["t2-diff-missing-file"]["proxy"]["exit"] = 0
                arms = []

                def command(label, argv, *_args, **kwargs):
                    if label.startswith("rtk-exactness-git-"):
                        self.assertEqual(argv[0], "git")
                        return ""
                    case, arm = label.removeprefix("rtk-exactness-").rsplit("-", 1)
                    self.assertIn(case, cases)
                    self.assertIn(arm, ("native", "rtk", "proxy"))
                    self.assertIsNone(kwargs["nonzero"])
                    prefix = {"native": [], "rtk": ["/stub/rtk"], "proxy": ["/stub/rtk", "proxy"]}[arm]
                    self.assertEqual(argv[:len(prefix)], prefix)
                    self.assertIn(argv[len(prefix)], ("git", "diff", "find", "grep", "jq"))
                    arms.append((case, arm))
                    result = cases[case][arm]
                    run.report["commands"].append({"label": label, "exit_code": result["exit"],
                                                   "stdout": result["stdout"], "stderr": ""})
                    return result["stdout"]

                with patch.object(run, "command", side_effect=command):
                    if failing is None:
                        ci.rtk_exactness_fixture(run)
                        self.assertEqual(run.report["checks"], [
                            {"label": label, "passed": passed} for label, passed in ci.rtk_exactness_checks(cases, blob).items()])
                        self.assertTrue(all(check["passed"] for check in run.report["checks"]))
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.rtk_exactness_fixture(run)
                self.assertEqual(arms, [(case, arm) for case in cases for arm in ("native", "rtk", "proxy")])
                self.assertEqual(set(run.report["rtk_exactness"]), set(cases))


    def test_context_mode_fixture_requires_indexing_exact_small_output_and_scoped_state(self):
        # context_mode_fixture/context_mode_indexed/context_mode_small_answer: npm 1.0.169's
        # doctor and ctx_execute contracts, with fixtures/context-mode-build.log as passthrough.
        raw_bytes = (ci.ROOT / ci.CONTEXT_MODE_LOG).read_bytes()
        raw = raw_bytes.decode()
        indexed = ('Indexed 12 sections from "execute:shell" into knowledge base.\n'
                   '1 section matched "amberquartz verdict" (3 lines):\n'
                   'amberquartz verdict: 19\n')
        labels = (
            "context-mode-ctx-doctor-reports-the-pin-a-working-server-and-fts5",
            "context-mode-ctx-doctor-storage-under-context-mode-dir",
            "context-mode-ctx-execute-indexes-a-large-output-instead-of-returning-it",
            "context-mode-ctx-execute-returns-a-small-output-exactly",
            "context-mode-index-inside-run",
        )
        self.assertTrue(ci.context_mode_indexed(indexed, raw))
        self.assertFalse(ci.context_mode_indexed(raw, raw))
        self.assertEqual(ci.context_mode_small_answer("printf hi", "hi"), "```shell\nprintf hi\n```\n\nhi")
        for name, failing in (
                ("recorded", None), ("wrong version", labels[0]), ("no server", labels[0]),
                ("no fts5", labels[0]), ("wrong sessions storage", labels[1]), ("wrong content storage", labels[1]),
                ("passthrough", labels[2]), ("no index announcement", labels[2]), ("no intent match", labels[2]),
                ("large answer", labels[2]), ("ten repeated lines", labels[2]),
                ("small output unfenced", labels[3]), ("small output truncated", labels[3]),
                ("no index file", labels[4])):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools.update({"mcporter": "/stub/mcporter", "context-mode": "/stub/context-mode"})
                storage = Path(run.env["CONTEXT_MODE_DIR"])

                def command(label, argv, *_args, **kwargs):
                    self.assertEqual(argv[0], "/stub/mcporter")
                    self.assertEqual(kwargs["env"], {"CLAUDE_CONFIG_DIR": None})
                    args = json.loads(argv[argv.index("--args") + 1])
                    if label == "context-mode-ctx-doctor":
                        doctor = [f"[OK] Version: v{ci.PINS['context-mode']}", "[OK] Server test: PASS",
                                  "[OK] FTS5 / SQLite: PASS", "[FAIL] Hooks: client plugin not installed"]
                        doctor.extend(f"[OK] Storage {kind}: {storage / kind} (via CONTEXT_MODE_DIR)"
                                      for kind in ("sessions", "content"))
                        if name == "wrong version":
                            doctor[0] = "[OK] Version: v0.0.0"
                        if name == "no server":
                            doctor[1] = "[FAIL] Server test: FAIL"
                        if name == "no fts5":
                            doctor[2] = "[FAIL] FTS5 / SQLite: FAIL"
                        for index, kind in ((4, "sessions"), (5, "content")):
                            if name == f"wrong {kind} storage":
                                doctor[index] = f"[OK] Storage {kind}: elsewhere (via CONTEXT_MODE_DIR)"
                        return "\n".join(doctor) + "\n"
                    if label == "context-mode-ctx-execute-large-output-with-intent":
                        self.assertEqual(args["intent"], "amberquartz verdict")
                        if name != "no index file":
                            index = storage / "content/build.db"
                            index.parent.mkdir(parents=True, exist_ok=True)
                            index.write_bytes(b"synthetic index")
                        answer = {
                            "passthrough": raw,
                            "no index announcement": indexed.replace("Indexed 12 sections", "Read 12 sections"),
                            "no intent match": indexed.replace("1 section matched", "0 sections matched"),
                            "large answer": indexed + "x" * len(raw),
                            "ten repeated lines": indexed + "\n".join(raw.splitlines()[:10]),
                        }.get(name, indexed)
                        return json.dumps({"content": [{"type": "text", "text": answer}]})
                    if label == "context-mode-ctx-execute-small-output":
                        output = f"{hashlib.sha256(raw_bytes).hexdigest()}\n{raw.count(chr(10))}\n"
                        answer = f"```shell\n{args['code']}\n```\n\n{output}"
                        if name == "small output unfenced":
                            answer = output
                        if name == "small output truncated":
                            answer = answer[:-1]
                        return json.dumps({"content": [{"type": "text", "text": answer}]})
                    self.fail(f"unexpected command: {label}")

                with patch.object(run, "command", side_effect=command):
                    if failing is None:
                        ci.context_mode_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                        self.assertEqual(run.report["context_mode_doctor_failures"],
                                         ["[FAIL] Hooks: client plugin not installed"])
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.context_mode_fixture(run)

    def test_serena_verified_native_preimages_require_exact_tool_schemas(self):
        # Exact independently observed native responses from the immutable upstream pin.
        # This replay exercises our parity gate; it is not a new server run or upstream test.
        evidence = SCRIPT.parents[1] / "evidence/artifacts/token-profile-completion-20260930/serena-no-project"
        transcripts = {context: (evidence / f"{context}.stdout.txt").read_bytes().splitlines(keepends=True)
                       for context in ("claude-code", "codex")}
        frozen_hashes = {"claude-code": "d2e22bcef4d45e867ca580dae8f50ad5738d31f4b348531ea1a88844994b5083",
                         "codex": "2fe0460cd748ae5df612496585404a47f282ad90747a94d3c17a1149ee0f194f"}
        for context, lines in transcripts.items():
            self.assertEqual(len(lines), 2)
            self.assertEqual(hashlib.sha256(lines[0]).hexdigest(), ci.SERENA_INITIALIZE_SHA256)
            self.assertEqual(hashlib.sha256(lines[1]).hexdigest(), frozen_hashes[context])
        for target in (None, "claude-code", "codex"):
            with self.subTest(changed_schema=target), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["serena"] = "/stub/serena"
                answers = deepcopy(transcripts)
                if target is not None:
                    response = json.loads(answers[target][1])
                    tools = response["result"]["tools"]
                    self.assertEqual(tools[0]["inputSchema"]["properties"]["needle"]["type"], "string")
                    tools[0]["inputSchema"]["properties"]["needle"]["type"] = "integer"
                    answers[target][1] = (json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
                    self.assertEqual(ci.serena_tool_names(answers[target][1]), ci.serena_tool_names(transcripts[target][1]))
                    self.assertNotEqual(hashlib.sha256(answers[target][1]).hexdigest(), frozen_hashes[target])

                def server(_run, _label, argv, _requests, **kwargs):
                    context = argv[argv.index("--context") + 1]
                    home = Path(kwargs["env"]["SERENA_HOME"])
                    home.mkdir(parents=True, exist_ok=True)
                    (home / "serena_config.yml").write_text("web_dashboard: false\n")
                    return answers[context]

                with patch.object(ci, "mcp_stdio_session", side_effect=server):
                    if target is None:
                        ci.serena_fixture(run)
                        self.assertTrue(all(check["passed"] for check in run.report["checks"]))
                        self.assertEqual(len(run.report["checks"]), 4)
                    else:
                        with self.assertRaisesRegex(AssertionError, "^serena-tools-list-byte-parity-with-the-pinned-install$"):
                            ci.serena_fixture(run)
                        self.assertEqual(run.report["checks"][-1],
                                         {"label": "serena-tools-list-byte-parity-with-the-pinned-install", "passed": False})

    def test_serena_fixture_requires_exact_response_bytes_context_tools_and_scoped_state(self):
        # serena_fixture and its frozen response/context comments at c6fbd1c5932df2494ffa0020af5a9fbe80b82143.
        # This synthetic test uses test-scoped hashes with the real digest/parser/checks; it is
        # not pinned-server evidence. The retained native preimages are covered separately above.
        labels = (
            "serena-initialize-byte-parity-with-the-pinned-install",
            "serena-tools-list-byte-parity-with-the-pinned-install",
            "serena-contexts-serve-their-own-tool-sets",
            "serena-state-inside-run",
        )
        frozen_initialize = "5277f280d5eeb79d76c620b8676144aab4d33b83dd1d89c7c222a853c676e494"
        frozen_tools = {"claude-code": "d2e22bcef4d45e867ca580dae8f50ad5738d31f4b348531ea1a88844994b5083",
                        "codex": "2fe0460cd748ae5df612496585404a47f282ad90747a94d3c17a1149ee0f194f"}
        self.assertEqual(ci.SERENA_INITIALIZE_SHA256, frozen_initialize)
        self.assertEqual(ci.SERENA_TOOLS_LIST_SHA256, frozen_tools)
        self.assertEqual(ci.SERENA_CONTEXT_ONLY_TOOLS, {"claude-code": "replace_content", "codex": "search_for_pattern"})

        def reply(number, result):
            return (json.dumps({"jsonrpc": "2.0", "id": number, "result": result}, separators=(",", ":")) + "\n").encode()

        def tools_reply(names):
            return reply(2, {"tools": [{"name": name, "description": "Synthetic tool",
                                       "inputSchema": {"type": "object", "properties": {}}} for name in names]})

        initialize = reply(1, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                               "serverInfo": {"name": "Serena", "version": "2.0.0.dev0"}})
        transcripts = {"claude-code": [initialize, tools_reply(["find_symbol", "replace_content"])],
                       "codex": [initialize, tools_reply(["find_symbol", "search_for_pattern"])]}
        initialize_hash = hashlib.sha256(initialize).hexdigest()
        tools_hashes = {context: hashlib.sha256(lines[1]).hexdigest() for context, lines in transcripts.items()}
        self.assertNotEqual(initialize_hash, frozen_initialize)
        variants = [("synthetic contracts", None, None), ("synthetic bytes against frozen hashes", None, labels[0]),
                    ("same context", None, labels[2]), ("exclusive tools in both contexts", None, labels[2]),
                    ("exclusive tools in neither context", None, labels[2])]
        for context in transcripts:
            variants.extend([("initialize byte changed", context, labels[0]),
                             ("tools byte changed", context, labels[1]),
                             ("missing config", context, labels[3])])
        for name, target, failing in variants:
            with self.subTest(response=name, context=target), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["serena"] = "/stub/serena"
                answers = deepcopy(transcripts)
                expected_tools = tools_hashes
                if name == "initialize byte changed":
                    answers[target][0] = initialize[:-1] + b" \n"  # Same JSON, different bytes.
                if name == "tools byte changed":
                    answers[target][1] = answers[target][1][:-1]  # The terminating newline counts.
                if name == "same context":
                    answers["codex"][1] = answers["claude-code"][1]
                if name == "exclusive tools in both contexts":
                    answers["codex"][1] = tools_reply(["find_symbol", "replace_content", "search_for_pattern"])
                if name == "exclusive tools in neither context":
                    answers["claude-code"][1] = tools_reply(["find_symbol"])
                    answers["codex"][1] = tools_reply(["find_symbol", "get_symbols_overview"])
                if failing == labels[2]:
                    # Admit these synthetic bytes at the parity gate so the independent context
                    # predicate is reached, rather than stopping at the earlier hash check.
                    expected_tools = {context: hashlib.sha256(lines[1]).hexdigest() for context, lines in answers.items()}
                seen = []

                def server(_run, label, argv, requests, *_args, **kwargs):
                    self.assertIs(_run, run)
                    context = argv[argv.index("--context") + 1]
                    self.assertEqual(label, f"serena-{context}-initialize-and-tools-list")
                    self.assertEqual(argv, ["/stub/serena", "start-mcp-server", "--context", context,
                                            "--enable-web-dashboard", "false",
                                            "--open-web-dashboard", "false"])
                    self.assertEqual(requests, [("tools/list", {})])
                    home = Path(kwargs["env"]["SERENA_HOME"])
                    self.assertEqual(home, run.work / f"data/serena-{context}")
                    self.assertEqual(kwargs["cwd"], run.work / "serena-no-project")
                    home.mkdir(parents=True, exist_ok=True)
                    if name != "missing config" or context != target:
                        (home / "serena_config.yml").write_text("web_dashboard: false\n")
                    seen.append(context)
                    return answers[context]

                with ExitStack() as patches:
                    patches.enter_context(patch.object(ci, "mcp_stdio_session", side_effect=server))
                    if name != "synthetic bytes against frozen hashes":
                        patches.enter_context(patch.object(ci, "SERENA_INITIALIZE_SHA256", initialize_hash))
                        patches.enter_context(patch.object(ci, "SERENA_TOOLS_LIST_SHA256", expected_tools))
                    if failing is None:
                        ci.serena_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                        self.assertEqual({context: parity["tools"] for context, parity in run.report["serena_parity"].items()},
                                         {"claude-code": ["find_symbol", "replace_content"],
                                          "codex": ["find_symbol", "search_for_pattern"]})
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.serena_fixture(run)
                self.assertEqual(seen, ["claude-code", "codex"])
                self.assertEqual(ci.SERENA_INITIALIZE_SHA256, frozen_initialize)
                self.assertEqual(ci.SERENA_TOOLS_LIST_SHA256, frozen_tools)

    def test_ai_memory_fixture_requires_selective_persistent_exact_pages_without_a_model(self):
        # ai_memory_fixture's 2.4.1 write/new-process-query/read contract and mcp_tool_json's
        # single JSON text result. State files are real; neither MCP nor CLI launches a process.
        labels = (
            "ai-memory-query-selects-only-the-marker-page",
            "ai-memory-nonsense-query-finds-nothing",
            "ai-memory-read-page-returns-the-exact-body-from-a-new-process",
            "ai-memory-store-inside-run-without-a-model",
        )
        marker, decoy = ci.AI_MEMORY_PAGES
        for name, failing in (
                ("recorded", None), ("no marker", labels[0]), ("wrong marker path", labels[0]),
                ("decoy returned too", labels[0]), ("unhighlighted snippet", labels[0]),
                ("nonsense hit", labels[1]), ("nonsense extra field", labels[1]),
                ("wrong read path", labels[2]), ("truncated body", labels[2]),
                ("missing database", labels[3]), ("missing page file", labels[3]),
                ("downloaded model", labels[3]), ("vector log absent", labels[3])):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["ai-memory"] = "/stub/ai-memory"
                store = Path(run.env["AI_MEMORY_DATA_DIR"])
                sessions = []

                def command(label, argv, *_args, **_kwargs):
                    self.assertEqual(label, "ai-memory-init-disposable-store")
                    self.assertEqual(argv, ["/stub/ai-memory", "init", "--data-dir", str(store)])
                    if name != "missing database":
                        db = store / "db/memory.sqlite"
                        db.parent.mkdir(parents=True, exist_ok=True)
                        db.write_bytes(b"synthetic database")
                    (store / "models").mkdir(parents=True, exist_ok=True)
                    if name == "downloaded model":
                        (store / "models/embedding.bin").write_bytes(b"unexpected model")
                    run.report["commands"].append({"label": label, "exit_code": 0, "stdout": "", "stderr": ""})
                    return ""

                def reply(number, value):
                    result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
                    return (json.dumps({"jsonrpc": "2.0", "id": number, "result": result}) + "\n").encode()

                def server(_run, label, argv, requests, *_args, **_kwargs):
                    self.assertIs(_run, run)
                    self.assertIn("--no-watcher", argv)
                    self.assertEqual(argv[argv.index("--data-dir") + 1], str(store))
                    sessions.append(label)
                    run.report["commands"].append({"label": label, "exit_code": 0, "stdout": "",
                                                   "stderr": "" if name == "vector log absent" else "vector search disabled\n"})
                    initialize = b'{"jsonrpc":"2.0","id":1,"result":{}}\n'
                    self.assertTrue(all(method == "tools/call" for method, _params in requests))
                    if label == "ai-memory-write-marker-and-decoy-pages":
                        self.assertEqual([params["name"] for _method, params in requests], ["memory_write_page"] * 2)
                        self.assertEqual([params["arguments"] for _method, params in requests],
                                         [{**ci.AI_MEMORY_SCOPE, **page} for page in ci.AI_MEMORY_PAGES])
                        for page in ci.AI_MEMORY_PAGES:
                            if name == "missing page file" and page == marker:
                                continue
                            path = store / "workspaces/native-ci/projects/fixture" / page["path"]
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(page["body"])
                        return [initialize, reply(2, {"path": marker["path"]}), reply(3, {"path": decoy["path"]})]
                    self.assertEqual(label, "ai-memory-query-and-read-from-a-new-process")
                    self.assertEqual([params["name"] for _method, params in requests],
                                     ["memory_query", "memory_query", "memory_read_page"])
                    self.assertEqual([params["arguments"] for _method, params in requests], [
                        {**ci.AI_MEMORY_SCOPE, "query": ci.AI_MEMORY_MARKER},
                        {**ci.AI_MEMORY_SCOPE, "query": "zzznativecimissing"},
                        {**ci.AI_MEMORY_SCOPE, "path": marker["path"]}])
                    hit = {"path": marker["path"], "snippet": "The <mark>amberquartz</mark> fixture keeps 19 entries."}
                    found, absent, page = {"hits": [hit]}, {"hits": []}, dict(marker)
                    if name == "no marker":
                        found["hits"] = []
                    if name == "wrong marker path":
                        hit["path"] = decoy["path"]
                    if name == "decoy returned too":
                        found["hits"].append({"path": decoy["path"], "snippet": "decoy"})
                    if name == "unhighlighted snippet":
                        hit["snippet"] = marker["body"]
                    if name == "nonsense hit":
                        absent["hits"] = [hit]
                    if name == "nonsense extra field":
                        absent["total"] = 0
                    if name == "wrong read path":
                        page["path"] = decoy["path"]
                    if name == "truncated body":
                        page["body"] = marker["body"][:-1]
                    return [initialize, reply(2, found), reply(3, absent), reply(4, page)]

                with patch.object(run, "command", side_effect=command), patch.object(ci, "mcp_stdio_session", side_effect=server):
                    if failing is None:
                        ci.ai_memory_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.ai_memory_fixture(run)
                self.assertEqual(sessions, ["ai-memory-write-marker-and-decoy-pages",
                                            "ai-memory-query-and-read-from-a-new-process"])


    def test_context_hub_fixture_discriminates_config_opt_out_from_offline_control(self):
        # context_hub_fixture: context-hub 0.1.4 src/lib/config.js, telemetry.js and identity.js
        # write client_id before a telemetry request; offline identity files distinguish the arms.
        labels = (
            "context-hub-registry-cached-without-client-id",
            "context-hub-opt-out-search-offline-returns-results",
            "context-hub-config-opt-out-writes-no-client-id",
            "context-hub-control-without-config-writes-client-id",
        )
        for name, failing in (
                ("recorded", None), ("no registry", labels[0]), ("warm client id", labels[0]),
                ("empty results", labels[1]), ("wrong result prefix", labels[1]),
                ("opt-out ignored", labels[2]), ("control also opts out", labels[3])):
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["context-hub"] = "/stub/chub"
                issued = []

                def command(label, argv, *_args, **kwargs):
                    issued.append(label)
                    stdout, exit_code = "", 0
                    if label == "context-hub-update-registry-telemetry-off":
                        self.assertEqual(argv, ["/stub/chub", "update"])
                        self.assertEqual(kwargs["env"]["CHUB_TELEMETRY"], "0")
                        self.assertEqual(kwargs["env"]["CHUB_FEEDBACK"], "0")
                        warm = Path(kwargs["env"]["CHUB_DIR"])
                        self.assertEqual((warm / "config.yaml").read_text(), "telemetry: false\nfeedback: false\n")
                        if name != "no registry":
                            registry = warm / "sources/default/registry.json"
                            registry.parent.mkdir(parents=True)
                            registry.write_text('{"results": [{"id": "stripe/api"}]}\n')
                        if name == "warm client id":
                            (warm / "client_id").write_text("synthetic-client\n")
                    elif label == "network-namespace-available":
                        self.assertEqual(argv, ["unshare", "-rn", "true"])
                    elif label in {"context-hub-offline-search-with-config-opt-out",
                                   "context-hub-offline-search-control-without-config"}:
                        folder = Path(kwargs["env"]["CHUB_DIR"])
                        opted = label == "context-hub-offline-search-with-config-opt-out"
                        self.assertEqual(argv[:3], ["unshare", "-rn", "timeout"])
                        self.assertEqual(argv[4:], ["/stub/chub", "search", "stripe", "--json"])
                        self.assertEqual(set(kwargs["env"]), {"CHUB_DIR"})
                        self.assertTrue((folder / "sources/default/registry.json").is_file())
                        self.assertEqual((folder / "config.yaml").exists(), opted)
                        if opted:
                            self.assertEqual((folder / "config.yaml").read_text(), "telemetry: false\nfeedback: false\n")
                            results = [{"id": "stripe/api"}]
                            if name == "empty results":
                                results = []
                            if name == "wrong result prefix":
                                results = [{"id": "striped/api"}]
                            stdout = json.dumps({"results": results})
                            if name == "opt-out ignored":
                                (folder / "client_id").write_text("synthetic-client\n")
                        else:
                            self.assertIsNone(kwargs["nonzero"])
                            if name != "control also opts out":
                                (folder / "client_id").write_text("synthetic-client\n")
                            exit_code = 124  # Offline control can time out after identity.js writes.
                    else:
                        self.fail(f"unexpected command: {label}")
                    run.report["commands"].append({"label": label, "exit_code": exit_code, "stdout": stdout,
                                                   "stderr": "", "elapsed_seconds": 0.01})
                    return stdout

                with patch.object(run, "command", side_effect=command):
                    if failing is None:
                        ci.context_hub_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                        self.assertEqual(run.report["context_hub_offline"], {
                            "config-opt-out": {"exit_code": 0, "elapsed_seconds": 0.01},
                            "control-without-config": {"exit_code": 124, "elapsed_seconds": 0.01}})
                        self.assertEqual(issued, ["context-hub-update-registry-telemetry-off", "network-namespace-available",
                                                  "context-hub-offline-search-with-config-opt-out",
                                                  "context-hub-offline-search-control-without-config"])
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.context_hub_fixture(run)

    def test_agentsview_fixture_requires_the_pinned_build_documented_commands_and_no_state(self):
        # agentsview_fixture: kenn-io/agentsview 0.43.0 --version/--help recipe contract.
        labels = (
            "agentsview-version-names-the-pin-and-its-build-commit",
            "agentsview-help-documents-the-recipe-commands",
            "agentsview-version-and-help-write-no-state",
        )
        version = f"agentsview v{ci.PINS['agentsview']} (commit {'a' * 40}, built 2026-09-26T00:00:00Z)\n"
        help_lines = ["  session search  Search sessions", "  session list  List sessions", "  usage daily  Daily usage",
                      "  AGENTSVIEW_DATA_DIR  State directory"]
        variants = [("recorded", version, help_lines, None),
                    ("wrong tag", version.replace(f"v{ci.PINS['agentsview']}", "v0.0.0"), help_lines, labels[0]),
                    ("no commit clause", f"agentsview v{ci.PINS['agentsview']}\n", help_lines, labels[0]),
                    ("short commit", version.replace("a" * 40, "a" * 7), help_lines, labels[0]),
                    ("missing state directory", version, help_lines[:-1], labels[1]),
                    ("writes data", version, help_lines, labels[2]), ("writes home", version, help_lines, labels[2])]
        for command in ci.AGENTSVIEW_COMMANDS:
            variants.append((f"missing {command}", version, [line for line in help_lines if command not in line], labels[1]))
        for name, version_answer, help_answer, failing in variants:
            with self.subTest(response=name), tempfile.TemporaryDirectory() as directory:
                run = self._new_run(Path(directory))
                run.tools["agentsview"] = "/stub/agentsview"
                seen = []

                def command(label, argv, *_args, **kwargs):
                    seen.append(label)
                    self.assertEqual(run.env["AGENTSVIEW_TELEMETRY_ENABLED"], "0")
                    home = Path(kwargs["env"]["HOME"])
                    self.assertEqual(home, run.work / "agentsview-home")
                    if label == "agentsview-version-telemetry-off":
                        self.assertEqual(argv, ["/stub/agentsview", "--version"])
                        return version_answer
                    if label == "agentsview-help-telemetry-off":
                        self.assertEqual(argv, ["/stub/agentsview", "--help"])
                        if name in {"writes data", "writes home"}:
                            folder = Path(run.env["AGENTSVIEW_DATA_DIR"]) if name == "writes data" else home
                            folder.mkdir(parents=True, exist_ok=True)
                            (folder / "unexpected-state").write_text("state\n")
                        return "\n".join(help_answer) + "\n"
                    self.fail(f"unexpected command: {label}")

                with patch.object(run, "command", side_effect=command):
                    if failing is None:
                        ci.agentsview_fixture(run)
                        self.assertEqual(run.report["checks"], [{"label": label, "passed": True} for label in labels])
                    else:
                        with self.assertRaisesRegex(AssertionError, f"^{failing}$"):
                            ci.agentsview_fixture(run)
                self.assertEqual(seen, ["agentsview-version-telemetry-off", "agentsview-help-telemetry-off"])


if __name__ == "__main__":
    unittest.main()
