"""PR-A synthetic transcript controls; no provider execution or savings claim.

Contract: #381 preregistration M3/M4/M5 and full-save plan §4.1 controls.
The public measurement export is shared by the two existing WP4 tools.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "examples/claude-native/workflows/child-usage.mjs"


def call(key, name, **inputs):
    return {"type": "assistant", "timestamp": "2026-09-26T01:00:00Z",
            "message": {"content": [{"type": "tool_use", "id": key, "name": name, "input": inputs}]}}


def result(key, content, error=False, timestamp="2026-09-26T01:00:01Z"):
    return {"type": "user", "timestamp": timestamp, "message": {"content": [
        {"type": "tool_result", "tool_use_id": key, "content": content, "is_error": error}]}}


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TokenMeasurement(unittest.TestCase):
    def measure(self, rows, **options):
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript} from "
                  + json.dumps(MODULE.as_uri()) + "; const x=JSON.parse(readFileSync(0,'utf8')); "
                  "process.stdout.write(JSON.stringify(measureTranscript(x.rows,x.options))); ")
        p = subprocess.run(["node", "--input-type=module", "-e", script],
                           input=json.dumps({"rows": rows, "options": options}),
                           text=True, capture_output=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_all_carriers_utf8_thresholds_dedup_and_proxy_are_in_m3(self):
        specs = [("Bash", {"command": "ls"}), ("Bash", {"command": "rtk proxy ls"}),
                 ("WebFetch", {}), ("Read", {}), ("Grep", {}), ("Glob", {}),
                 ("mcp__context_mode__ctx_execute", {}), ("mcp__other__query", {})]
        rows = []
        for i, (name, args) in enumerate(specs):
            rows += [call(str(i), name, **args), result(str(i), "é" * 2561)]
        rows += [rows[0], rows[1], call("edge", "Read"), result("edge", "x" * 5120)]
        got = self.measure(rows)
        self.assertEqual(got["m3"]["results"], 9)
        self.assertEqual(got["m3"]["large_results"], 8)
        self.assertEqual(got["m3"]["bytes"], 46096)
        self.assertEqual(got["m3"]["large_bytes"], 40976)
        self.assertEqual(got["m3"]["max_bytes"], 5122)
        self.assertEqual(got["by_carrier"]["rtk_proxy"]["large_results"], 1)
        self.assertEqual(got["by_carrier"]["grep_glob"]["results"], 2)
        self.assertEqual(got["m5"]["results"], 1)

    def test_exceptions_require_later_success_or_reviewed_witness(self):
        rows = [call("read", "Read", file_path="a.py"), result("read", "a" * 6000),
                call("failed", "Read", file_path="b.py"), result("failed", "b" * 6000),
                call("edit", "Edit", file_path="a.py"), result("edit", "ok"),
                call("badedit", "Edit", file_path="b.py"), result("badedit", "failed", True),
                call("source", "WebFetch"), result("source", "c" * 6000),
                call("exact", "Bash", command="rtk proxy check"), result("exact", "d" * 6000)]
        got = self.measure(rows, exceptions={
            "source": {"exception": "original_source_quoted_or_line_cited", "witness": "reviewed citation"},
            "exact": {"exception": "exact_bytes_required_by_frozen_check", "witness": "frozen check"}})
        self.assertEqual(got["m3"]["large_results"], 1)
        self.assertEqual(got["exceptions"]["read_of_subsequently_edited_file"]["large_results"], 1)
        self.assertEqual(got["exceptions"]["exact_bytes_required_by_frozen_check"]["bytes"], 6000)
        self.assertEqual(got["by_carrier"]["read"]["bytes"], 12000)
        # An unsupported label or a bare claim never silently removes bytes.
        invalid = self.measure(rows, exceptions={"exact": {"exception": "exact_bytes_required_by_frozen_check"}})
        self.assertEqual(invalid["m3"]["large_results"], 3)
        self.assertEqual(invalid["invalid_exceptions"], 1)

    def test_m5_one_enormous_result_among_small_ones_fails_byte_and_max_guards(self):
        rows = []
        for i in range(20):
            rows += [call(str(i), "mcp__context_mode__ctx_search"),
                     result(str(i), "x" * (25000 if i == 0 else 10))]
        got = self.measure(rows, exceptions={"0": {
            "exception": "exact_bytes_required_by_frozen_check", "witness": "check"}})
        self.assertEqual(got["m5"]["large_result_share"], .05)
        self.assertGreater(got["m5"]["large_byte_share"], .99)
        self.assertEqual(got["m5"]["max_bytes"], 25000)
        self.assertEqual(got["m3"]["large_results"], 0)

    def test_result_windows_count_once_and_do_not_use_a_future_edit(self):
        rows = [call("read", "Read", file_path="a"), result("read", "x" * 6000),
                call("edit", "Edit", file_path="a"),
                result("edit", "ok", timestamp="2026-09-26T02:00:00Z")]
        got = self.measure(rows, window={"since": 1790384401000, "until": 1790388000000})
        self.assertEqual(got["m3"]["large_results"], 1)

    def test_m4_nineteen_nested_fetches_do_not_report_one_hundred_percent(self):
        rows = [call("indexed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org")]
        rows += [call(str(i), "mcp__ctx__ctx_execute", language="shell",
                      code="curl https://example.org/page") for i in range(19)]
        got = self.measure(rows)["m4"]
        self.assertEqual(got["ctx_sandbox_fetch"], 19)
        self.assertEqual(got["remote_fetches"], 20)
        self.assertEqual(got["routed_share"], .05)

    def test_m4_operations_batches_loopback_and_unknown_http_libraries(self):
        rows = [call("batch", "mcp__ctx__ctx_batch_execute", commands=[
                    {"command": "curl https://example.org/a; wget https://example.org/b"},
                    {"command": "curl http://127.0.0.1:8000/health"},
                    {"command": "echo 'curl https://example.org'"}]),
                call("indexed", "mcp__ctx__ctx_fetch_and_index", requests=[
                    {"url": "https://example.org/a"}, {"url": "https://example.org/b"}]),
                call("unknown", "mcp__ctx__ctx_execute", language="javascript",
                     code="await fetch(url); await fetch(other);"),
                call("library", "Bash", command="python3 -c 'import requests; requests.get(url)'"),
                call("proxy", "Bash", command="rtk proxy curl https://example.org/a")]
        got = self.measure(rows)["m4"]
        self.assertEqual(got["ctx_sandbox_fetch"], 2)
        self.assertEqual(got["loopback"], 1)
        self.assertEqual(got["unclassifiable"], 3)
        self.assertEqual(got["remote_fetches"], 8)
        self.assertEqual(got["routed_share"], .25)
        self.assertEqual(got["status"], "incomplete")

    def test_m4_shell_fetches_inside_javascript_and_python_ctx_code(self):
        rows = [call("js", "mcp__ctx__ctx_execute", language="javascript",
                     code='const p = execSync("curl https://example.org/a");'),
                call("py", "mcp__ctx__ctx_execute", language="python",
                     code='subprocess.run(["curl", "https://example.org/b"])'),
                call("string", "mcp__ctx__ctx_execute", language="javascript",
                     code='const example = "curl https://example.org";')]
        got = self.measure(rows)["m4"]
        self.assertEqual(got["ctx_sandbox_fetch"], 2)
        self.assertEqual(got["remote_fetches"], 2)

    def test_hook_context_is_inserted_only_by_additional_context_rows(self):
        def hook(kind, name, **rest):
            return {"type": "attachment", "timestamp": "2026-09-26T01:00:00Z", "attachment": {
                "type": kind, "hookEvent": name.split(":")[0], "hookName": name, **rest}}
        rows = [hook("hook_success", "SubagentStart:reviewer", stdout=json.dumps({"hookSpecificOutput": {
                    "additionalContext": "claimed only"}})),
                hook("hook_additional_context", "PreToolUse:Read", content=["routing without marker"]),
                hook("hook_additional_context", "PreToolUse:Grep", content=["tip"]),
                hook("hook_additional_context", "SessionStart", content=["<context_window_protection>"])]
        got = self.measure(rows)["hook_context"]
        self.assertEqual(got["inserted"], 3)
        self.assertEqual(got["claimed"], 1)
        self.assertEqual(got["with_marker"], 1)
        self.assertEqual(got["by_hook"]["PreToolUse:Read"], 1)

    def test_mcp_attempt_result_states_and_unclassified_proxy_are_explicit(self):
        rows = [call("ok", "mcp__qmd__search"), result("ok", "[]"),
                call("error", "mcp__qmd__get"), result("error", "failed", True),
                call("unfinished", "mcp__qmd__get"),
                call("raw", "Bash", command="rtk proxy test -f a"), result("raw", "ok")]
        got = self.measure(rows)
        self.assertEqual(got["mcp_states"]["qmd"], {"attempted": 3, "succeeded": 1, "failed": 1, "unfinished": 1})
        self.assertEqual(got["proxy"]["unclassified"], 1)
        accepted = self.measure(rows, exceptions={"raw": {"proxy_purpose": "acceptance", "witness": "frozen check"}})
        self.assertEqual(accepted["proxy"]["acceptance_or_exception_share"], 1)
        self.assertEqual(accepted["m3"]["results"], 3)

    def test_missing_result_content_is_unknown_and_not_four_null_bytes(self):
        missing = result("c", None)
        del missing["message"]["content"][0]["content"]
        got = self.measure([call("c", "Read"), missing])
        self.assertEqual(got["unknown_result_bytes"], 1)
        self.assertFalse(got["bytes_complete"])
        self.assertEqual(got["m3"]["bytes"], 0)

    def test_streamed_message_usage_partitions_across_adjacent_windows(self):
        def msg(output, time):
            return {"type": "assistant", "timestamp": time, "message": {"id": "same",
                "model": "claude-opus-5-5", "usage": {"input_tokens": 10, "output_tokens": output,
                "cache_read_input_tokens": 20, "cache_creation_input_tokens": 3}}}
        rows = [msg(2, "2026-09-26T01:00:00Z"), msg(7, "2026-09-26T02:00:00Z")]
        from datetime import datetime
        split = datetime.fromisoformat("2026-09-26T01:30:00+00:00").timestamp() * 1000
        early = self.measure(rows, window={"since": 0, "until": split})["usage"]["totals"]
        late = self.measure(rows, window={"since": split, "until": split + 86400000})["usage"]["totals"]
        self.assertEqual(early["input_tokens"] + late["input_tokens"], 10)
        self.assertEqual(early["output_tokens"] + late["output_tokens"], 7)

    @unittest.skipUnless(shutil.which("rtk"), "RTK v0.50.0 required")
    def test_rtk_native_replay_parts_and_call_controls(self):
        controls = [
            ("git status && gh pr view 1 | head -n 5", 2, 1, 0),
            ("gh pr view 1 | head -n 5", 1, 0, 0),
            ("git status && gh pr view 1", 2, 2, 1),
            ("git status && ls -la | wc -l", 1, 1, 1)]
        for command, eligible, replayed, all_covered in controls:
            with self.subTest(command=command):
                got = self.measure([call("a", "Bash", command=command)], rtkCheck=True)["rtk_parts"]
                self.assertEqual(got["status"], "measured")
                self.assertEqual(got["eligible_parts"], eligible)
                self.assertEqual(got["replayed_covered_parts"], replayed)
                self.assertEqual(got["replayed_all_covered_calls"], all_covered)
                # Replay proves potential routing, never what actually executed.
                self.assertEqual(got["observed_covered_parts"], 0)

    @unittest.skipUnless(shutil.which("rtk"), "RTK v0.50.0 required")
    def test_whole_call_substitution_does_not_hide_eligible_prefix(self):
        got = self.measure([call("c", "Bash", command='git status && printf "%s" "$(date)"')], rtkCheck=True)["rtk_parts"]
        self.assertEqual(got["eligible_parts"], 1)
        self.assertEqual(got["replayed_covered_parts"], 0)

    def test_failed_read_is_not_an_original_source_exception(self):
        rows = [call("r", "Read", file_path="a"), result("r", "x" * 6000, True),
                call("e", "Edit", file_path="a"), result("e", "ok")]
        self.assertEqual(self.measure(rows)["m3"]["large_results"], 1)

    def test_m4_proxy_gh_api_is_unknown_and_in_denominator(self):
        rows = [call("indexed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org")]
        rows += [call(str(i), "Bash", command="rtk proxy gh api repos/example/repo") for i in range(19)]
        got = self.measure(rows)["m4"]
        self.assertEqual(got["remote_fetches"], 20)
        self.assertEqual(got["status"], "incomplete")
        self.assertEqual(got["routed_share"], .05)

    @unittest.skipUnless(shutil.which("rtk"), "RTK v0.50.0 required")
    def test_rtk_explicit_exclusions_proxy_and_quoted_operators(self):
        commands = ["rtk jq . a.json", "rtk git -C . show HEAD:a", "rtk git branch -a",
                    "rtk diff a b", "rtk git log", "rtk find missing", "rtk cd .",
                    "rtk proxy git show HEAD:a", "git status > output.txt",
                    "gh pr view 1 --json title", "git status && rtk git status",
                    "git status && printf 'a|b; c'", "git status | tail -f",
                    "rtk head -c 5 file", 'rtk tail -n 5 "$FILE"',
                    "rtk gh pr view 1 --json title", "rtk /usr/bin/git status"]
        got = self.measure([call(str(i), "Bash", command=c) for i,c in enumerate(commands)],
                           rtkCheck=True)["rtk_parts"]
        self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 11)
        self.assertEqual(got["proxy_parts"], 1)
        # log/find still rewrite under the frozen FIVE exclusions; their
        # independent raw-exactness guard must not shrink M-R1's denominator.
        self.assertEqual(got["eligible_parts"], 5)
        self.assertEqual(got["observed_covered_parts"], 3)

    def test_usage_dedup_routes_partial_counters_and_completion(self):
        def message(key, output, **kw):
            return {"type": "assistant", "timestamp": "2026-09-26T01:00:00Z", "effort": "max",
                    "message": {"id": key, "model": "claude-opus-5-5", "usage": {
                        "input_tokens": 4, "output_tokens": output, "cache_creation_input_tokens": 7,
                        "cache_read_input_tokens": 10}, **kw}}
        got = self.measure([message("first", 1), message("first", 5), message("second", 3)])
        self.assertEqual(got["usage"]["totals"], {"input_tokens": 8, "output_tokens": 8,
                          "cache_creation_input_tokens": 14, "cache_read_input_tokens": 20})
        self.assertTrue(got["usage"]["complete"])
        self.assertEqual(len(got["usage"]["messages"]), 2)
        self.assertNotIn("first", json.dumps(got["usage"]))
        self.assertEqual(got["usage"]["messages"][0]["effort"], "max")
        partial = self.measure([message("partial", 1, usage={"input_tokens": 4})])["usage"]
        self.assertFalse(partial["complete"])
        self.assertIsNone(partial["totals"]["output_tokens"])

    def test_sweep_reports_children_and_main_separately_with_digest_bound_exceptions(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "session/subagents/agent-child.jsonl"
            child.parent.mkdir(parents=True)
            rows = [call("c", "WebFetch", url="https://example.org"), result("c", "x" * 6000)]
            content = "\n".join(json.dumps(r) for r in rows)
            child.write_text(content)
            (root / "session.jsonl").write_text(content)
            review = root / "exceptions.json"
            review.write_text(json.dumps([{"transcript_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "tool_use_id": "c", "exception": "original_source_quoted_or_line_cited", "witness": "citation"}]))
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory,
                                "--exceptions", str(review)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
            self.assertEqual(got["children_in_window"], 1)
            self.assertEqual(got["main_sessions_in_window"], 1)
            self.assertEqual(got["groups"]["all"]["measurement"]["m3"]["large_results"], 0)
            self.assertEqual(got["main"]["measurement"]["exceptions"]["original_source_quoted_or_line_cited"]["results"], 1)
            self.assertEqual(len(got["actors"]), 2)
            self.assertNotIn(directory, p.stdout)
            self.assertNotIn("tool_use_id", p.stdout.split('"limits"')[0])


if __name__ == "__main__":
    unittest.main()
