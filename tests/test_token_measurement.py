"""PR-A synthetic transcript controls; no provider execution or savings claim.

Contract: #381 preregistration M3/M4/M5 and full-save plan §4.1 controls.
The public measurement export is shared by the two existing WP4 tools.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "examples/claude-native/workflows/child-usage.mjs"


def rtk_replay_supported():
    """Check the kernel's platform/self-reported-version prerequisite only.

    The kernel separately probes all five exclusions; neither check pins a build.
    """
    if sys.platform != "linux" or not shutil.which("rtk"):
        return False
    version = subprocess.run(["rtk", "--version"], text=True, capture_output=True, check=False)
    return version.returncode == 0 and bool(re.fullmatch(r"rtk 0\.50\.0\s*", version.stdout))


RTK_REPLAY_SUPPORTED = rtk_replay_supported()


def call(key, name, **inputs):
    return {"type": "assistant", "timestamp": "2026-09-26T01:00:00Z",
            "message": {"content": [{"type": "tool_use", "id": key, "name": name, "input": inputs}]}}


def result(key, content, error=False, timestamp="2026-09-26T01:00:01Z"):
    return {"type": "user", "timestamp": timestamp, "message": {"content": [
        {"type": "tool_result", "tool_use_id": key, "content": content, "is_error": error}]}}


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TokenMeasurement(unittest.TestCase):
    def measure(self, rows, *, env=None, **options):
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript} from "
                  + json.dumps(MODULE.as_uri()) + "; const x=JSON.parse(readFileSync(0,'utf8')); "
                  "process.stdout.write(JSON.stringify(measureTranscript(x.rows,x.options))); ")
        p = subprocess.run(["node", "--input-type=module", "-e", script],
                           input=json.dumps({"rows": rows, "options": options}),
                           text=True, capture_output=True, check=False, env=env)
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

    def test_text_blocks_have_the_same_utf8_size_as_string_results(self):
        text = 'é\n"' * 1280  # Exactly 5,120 bytes; JSON escapes would cross M3.
        rows = [call("bash", "Bash", command="cat f"), result("bash", text),
                call("ctx", "mcp__ctx__ctx_execute"),
                result("ctx", [{"type": "text", "text": text[:100]},
                               {"type": "text", "text": text[100:]}])]
        got = self.measure(rows)
        self.assertEqual(got["by_carrier"]["bash"]["bytes"], 5120)
        self.assertEqual(got["by_carrier"]["ctx"]["bytes"], 5120)
        self.assertEqual(got["m3"]["large_results"], 0)
        self.assertEqual(got["m5"]["large_results"], 0)
        block = {"type": "image", "data": "synthetic"}
        mixed = self.measure([call("c", "mcp__ctx__ctx_execute"), result("c", [
            {"type": "text", "text": "é"}, block])])
        self.assertEqual(mixed["m3"]["bytes"], 2 + len(json.dumps(block, separators=(",", ":")).encode()))

    def test_mixed_sidecar_records_validate_every_present_class(self):
        # #381 reviewed sidecars: a valid class cannot vouch for a malformed sibling.
        rows = [call("c", "Bash", command="rtk proxy check"), result("c", "x" * 6000)]
        good = {"exception": "exact_bytes_required_by_frozen_check", "proxy_purpose": "acceptance",
                "rtk_log_find": [{"part": 1, "disposition": "permitted"}], "witness": "frozen check"}
        accepted = self.measure(rows, exceptions={"c": good})
        self.assertEqual(accepted["invalid_exceptions"], 0)
        self.assertEqual(accepted["m3"]["bytes"], 0)
        self.assertEqual(accepted["proxy"]["acceptance"], 1)
        for field, invalid in [("exception", "typo"), ("exception", None),
                               ("proxy_purpose", "acceptence"), ("proxy_purpose", None),
                               ("rtk_log_find", None), ("rtk_log_find", []),
                               ("rtk_log_find", [{"part": 0, "disposition": "permitted"}]),
                               ("rtk_log_find", [{"part": 1, "disposition": "guess"}]),
                               ("rtk_log_find", good["rtk_log_find"] * 2)]:
            with self.subTest(field=field, invalid=invalid):
                got = self.measure(rows, exceptions={"c": {**good, field: invalid}})
                self.assertEqual(got["invalid_exceptions"], 1)
                self.assertEqual(got["m3"]["bytes"], 6000)
                self.assertEqual(got["proxy"]["unclassified"], 1)
        empty = self.measure(rows, exceptions={"c": {"witness": "no class"}})
        self.assertEqual(empty["invalid_exceptions"], 1)

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

    def test_m4_quoted_patterns_comments_and_written_scripts_are_not_fetches(self):
        commands = ['grep -n "fetch(" app.js', '# fetch(url) is slow',
                    'cat <<\'EOF\' > script.py\nrequests.get(u)\nEOF',
                    'grep "requests.get(u)" f', '# requests.get(u)',
                    'cat <<EOF > script.js\nfetch("https://example.org")\nEOF']
        for command in commands:
            for name, inputs in [
                ("Bash", {"command": command}),
                ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}),
                ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}),
            ]:
                with self.subTest(command=command, carrier=name):
                    got = self.measure([call("c", name, **inputs)])["m4"]
                    self.assertEqual(got["remote_fetches"], 0)
                    self.assertEqual(got["fetch_mentions_unconfirmed"], 1)
                    self.assertIsNone(got["routed_share"])
                    self.assertEqual(got["routed_share_lower_bound"], 0)
                    self.assertEqual(got["status"], "incomplete")
        for command in ["python3 -c 'import requests; requests.get(u)'",
                        'node -e \'fetch("https://example.org")\'',
                        "bash <<'EOF'\npython3 -c 'requests.get(u)'\nEOF"]:
            with self.subTest(command=command):
                self.assertEqual(self.measure([call("c", "Bash", command=command)])["m4"]["unclassifiable"], 1)

    def test_m4_interpreter_heredocs_and_quoted_code_stay_in_denominator(self):
        # context-mode v1.0.169 routing.mjs:228-229,787-797 strips heredocs;
        # #381 M4 must count the interpreter HTTP operations it cannot route.
        commands = ["python3 - <<'PY'\nrequests.get(u)\nPY",
                    'node <<\'EOF\'\nfetch("https://example.org")\nEOF',
                    "python3 -Bc 'requests.get(u)'",
                    "python3 -IBc 'requests.get(u)'",
                    "node -p 'fetch(u)'", "node --print 'fetch(u)'",
                    "nodejs -p 'fetch(u)'", "deno eval 'fetch(u)'",
                    "bun -e 'fetch(u)'", "bun --eval 'fetch(u)'"]
        for interpreter in ("python", "python3.13", "nodejs", "deno run -",
                            "bun run -", "ruby -", "perl -", "php"):
            commands.append(f"{interpreter} <<'EOF'\nfetch(u)\nEOF")
        for command in commands:
            for name, inputs in [
                ("Bash", {"command": command}),
                ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}),
                ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}),
            ]:
                with self.subTest(command=command, carrier=name):
                    rows = [call("routed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org"),
                            call("code", name, **inputs)]
                    got = self.measure(rows)["m4"]
                    self.assertEqual(got["unclassifiable"], 1)
                    self.assertEqual(got["remote_fetches"], 2)
                    self.assertEqual(got["routed_share"], .5)
                    self.assertEqual(got["fetch_mentions_unconfirmed"], 0)
                    self.assertEqual(got["routed_share_lower_bound"], .5)
                    self.assertEqual(got["unclassifiable_share"], .5)
                    self.assertEqual(got["status"], "incomplete")

    def test_m4_ignored_interpreter_stdin_is_data(self):
        # Python interface options, Node v24 CLI, POSIX sh STDIN: -c/-e or
        # a script operand executes that source, not the heredoc on stdin.
        invocations = ["python -c pass", "python3 -Bc pass", "python3 -m module",
                       "python3 script.py", "node -e 0", "node --eval=0",
                       "node -p 0", "node script.js", "bash -c :", "sh -c :",
                       "bash script.sh", "sh script.sh", "python3 -h"]
        commands = [f"{invocation} <<'EOF'\nrequests.get(u)\nEOF" for invocation in invocations]
        commands += ["python3 <<'EOF' -c pass\nrequests.get(u)\nEOF",
                     "node <<'EOF' -e 0\nfetch(u)\nEOF"]
        for command in commands:
            for name, inputs in [
                ("Bash", {"command": command}),
                ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}),
                ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}),
            ]:
                with self.subTest(command=command, carrier=name):
                    got = self.measure([call("code", name, **inputs)])["m4"]
                    self.assertEqual(got["remote_fetches"], 0)
                    self.assertEqual(got["unclassifiable"], 0)
                    self.assertEqual(got["fetch_mentions_unconfirmed"], 1)
                    self.assertEqual(got["routed_share_lower_bound"], 0)

    def test_m4_stdin_source_options_and_body_boundaries(self):
        commands = [("python3 -B - <<'PY'\nrequests.get(u)\nPY", 0),
                    ("bash -- <<'SH'\npython3 -c 'requests.get(u)'\nSH", 0),
                    ("node - <<'JS'\nfetch(u)\nJS", 0),
                    ("bash -s argument <<'SH'\npython3 -c 'requests.get(u)'\nSH", 0)]
        for body in ["python3 - <<'PY'\nx = 1 << bits\nrequests.get(u)\nPY",
                     "node <<'JS'\n// user's comment\nfetch(u)\nJS"]:
            commands.append((body + "\npython3 - <<'NEXT'\nrequests.get(v)\nNEXT"
                             + "\ncat <<'DATA'\nfetch(w)\nDATA", 2))
        for command, mentions in commands:
            for name, inputs in [
                ("Bash", {"command": command}),
                ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}),
                ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}),
            ]:
                with self.subTest(command=command, carrier=name):
                    got = self.measure([call("code", name, **inputs)])["m4"]
                    self.assertEqual(got["remote_fetches"], 1)
                    self.assertEqual(got["fetch_mentions_unconfirmed"], mentions)

    def test_m4_parser_omissions_reduce_gate_lower_bound_per_carrier(self):
        # #381 thresholds.M4 and context-mode v1.0.169 routing.mjs:788-795.
        # C1/C2 are verification's residual misses, not confirmed operations.
        commands = ["python3 - <<'PY'\nx = 1 << bits\nrequests.get(u)\nPY",
                    "node <<'JS'\n// user's comment\nfetch(u)\nJS"]
        for command in commands:
            for name, inputs, carrier in [
                ("Bash", {"command": command}, "bash"),
                ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}, "ctx"),
                ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}, "ctx"),
            ]:
                with self.subTest(command=command, carrier=name):
                    rows = [call("routed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org"),
                            call("code", name, **inputs)]
                    got = self.measure(rows)["m4"]
                    self.assertEqual(got["remote_fetches"], 1)
                    self.assertEqual(got["routed_share"], 1)
                    self.assertEqual(got["fetch_mentions_unconfirmed"], 1)
                    self.assertEqual(got["routed_share_lower_bound"], .5)
                    self.assertEqual(got["status"], "incomplete")
                    self.assertEqual(got["by_carrier"][carrier]["fetch_mentions_unconfirmed"], 1)

    def test_m4_possible_fetches_count_per_command_without_double_counting(self):
        rows = [call("routed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org"),
                call("batch", "mcp__ctx__ctx_batch_execute", commands=[
                    {"command": "python3 -c 'requests.get(u)' # requests.get(v)"},
                    {"command": "grep 'fetch(u); fetch(v)' script.js"}]),
                call("direct", "mcp__ctx__ctx_execute", language="javascript",
                     code="await fetch(u)")]
        got = self.measure(rows)["m4"]
        self.assertEqual(got["remote_fetches"], 3)
        self.assertEqual(got["unclassifiable"], 2)
        self.assertEqual(got["fetch_mentions_unconfirmed"], 3)
        self.assertEqual(got["routed_share"], .3333)
        self.assertEqual(got["routed_share_lower_bound"], .1667)
        self.assertEqual(got["by_carrier"]["ctx"]["fetch_mentions_unconfirmed"], 3)

    def test_m4_aggregate_recomputes_bounds_and_carrier_counts(self):
        # Aggregation sums counts, never actor percentages. Empty is N/A.
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript, aggregateMeasurements} from "
                  + json.dumps(MODULE.as_uri()) + "; const rows=JSON.parse(readFileSync(0,'utf8')); "
                  "process.stdout.write(JSON.stringify([aggregateMeasurements(rows.map(r=>measureTranscript(r))), "
                  "aggregateMeasurements([])]));")
        rows = [[call("routed", "mcp__ctx__ctx_fetch_and_index", requests=[
                    {"url": "https://example.org/a"}, {"url": "https://example.org/b"}])],
                [call("data", "Bash", command="rtk proxy grep 'fetch(u)' app.js")]]
        p = subprocess.run(["node", "--input-type=module", "-e", script],
                           input=json.dumps(rows), text=True, capture_output=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        got, empty = json.loads(p.stdout)
        self.assertEqual(got["m4"]["remote_fetches"], 2)
        self.assertEqual(got["m4"]["routed_share"], 1)
        self.assertEqual(got["m4"]["fetch_mentions_unconfirmed"], 1)
        self.assertEqual(got["m4"]["routed_share_lower_bound"], .6667)
        self.assertEqual(got["m4"]["by_carrier"]["rtk_proxy"]["fetch_mentions_unconfirmed"], 1)
        self.assertEqual(got["m4"]["by_carrier"]["ctx"]["routed_share_lower_bound"], 1)
        self.assertEqual(empty["m4"]["fetch_mentions_unconfirmed"], 0)
        self.assertIsNone(empty["m4"]["routed_share_lower_bound"])
        self.assertEqual(empty["m4"]["by_carrier"], {})
        self.assertEqual(empty["m4"]["status"], "not_applicable")

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

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
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

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
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

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
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
        self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 9)
        self.assertEqual(got["explicit_rtk_log_find_advisory"], 2)
        self.assertEqual(got["proxy_parts"], 1)
        # log/find still rewrite under the frozen FIVE exclusions; their
        # independent raw-exactness guard must not shrink M-R1's denominator.
        self.assertEqual(got["eligible_parts"], 5)
        self.assertEqual(got["observed_covered_parts"], 3)

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_rtk_quoted_greater_than_is_data_and_redirect_is_syntax(self):
        for command in ['rtk grep -n "=>" f', 'rtk rg "Vec<String>" src']:
            with self.subTest(command=command):
                got = self.measure([call("c", "Bash", command=command)], rtkCheck=True)["rtk_parts"]
                self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 0)
                self.assertEqual(got["eligible_parts"], 1)
                self.assertEqual(got["observed_covered_parts"], 1)
        got = self.measure([call("c", "Bash", command="rtk git status > out.txt")], rtkCheck=True)["rtk_parts"]
        self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 1)
        self.assertEqual(got["eligible_parts"], 0)
        # /dev/null is accepted by the native hook; the local guard cannot veto it.
        got = self.measure([call("c", "Bash", command="git status 2>/dev/null")], rtkCheck=True)["rtk_parts"]
        self.assertEqual(got["eligible_parts"], 1)

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_rtk_log_find_are_advisory_with_per_part_review(self):
        rows = [call("c", "Bash", command="rtk git log -3 && rtk find . -name x")]
        got = self.measure(rows, rtkCheck=True)["rtk_parts"]
        self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 0)
        self.assertEqual(got["explicit_rtk_log_find_advisory"], 2)
        self.assertEqual(got["log_find_unresolved_parts"], 2)
        self.assertEqual(got["eligible_parts"], 2)
        reviewed = self.measure(rows, rtkCheck=True, exceptions={"c": {
            "rtk_log_find": [{"part": 1, "disposition": "permitted"},
                             {"part": 2, "disposition": "requires_raw"}],
            "witness": "bounded history and independently checked path requirement"}})["rtk_parts"]
        self.assertEqual(reviewed["log_find_permitted_parts"], 1)
        self.assertEqual(reviewed["log_find_requires_raw_parts"], 1)
        self.assertEqual(reviewed["log_find_unresolved_parts"], 0)

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_rtk_proxy_parts_are_outside_eligible_population(self):
        for review in [{"proxy_purpose": "acceptance", "witness": "native check"},
                       {"exception": "exact_bytes_required_by_frozen_check", "witness": "check"}, {}]:
            with self.subTest(review=review):
                got = self.measure([call("c", "Bash", command="rtk proxy git diff --stat && rtk git status")],
                                   rtkCheck=True, exceptions={"c": review})["rtk_parts"]
                self.assertEqual(got["proxy_parts"], 1)
                self.assertEqual(got["eligible_parts"], 1)
                self.assertEqual(got["coverage"], 1)

    def test_unsupported_rtk_version_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "rtk"
            binary.write_text("#!/bin/sh\nprintf 'rtk 0.51.0\\n'\n")
            binary.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ.get("PATH", "")}
            got = self.measure([call("c", "Bash", command="git status")], env=env, rtkCheck=True)["rtk_parts"]
            self.assertEqual(got["status"], "unavailable")
            self.assertIsNone(got["coverage"])

    def test_rtk_replay_support_matches_kernel_platform_and_version(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(shutil, "which", return_value="rtk"):
            for output, code, expected in [("rtk 0.50.0\n", 0, True), ("rtk 0.51.0\n", 0, False),
                                           (" rtk 0.50.0\n", 0, False), ("rtk 0.50.0\n", 1, False)]:
                with self.subTest(output=output, code=code), mock.patch.object(subprocess, "run", return_value=
                        subprocess.CompletedProcess(["rtk", "--version"], code, output, "")):
                    self.assertEqual(rtk_replay_supported(), expected)
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertFalse(rtk_replay_supported())

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
            child.write_text(content + "\n")  # Different digest, same semantic rows.
            (root / "session.jsonl").write_text(content)
            review = root / "exceptions.json"
            review.write_text(json.dumps([{"transcript_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "tool_use_id": "c", "exception": "original_source_quoted_or_line_cited", "witness": "citation"},
                {"transcript_sha256": "0" * 64, "tool_use_id": "stale",
                 "exception": "original_source_quoted_or_line_cited", "witness": "stale citation"}]))
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory,
                                "--exceptions", str(review)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
            self.assertEqual(got["children_in_window"], 1)
            self.assertEqual(got["main_sessions_in_window"], 1)
            self.assertEqual(got["groups"]["all"]["measurement"]["m3"]["large_results"], 1)
            self.assertEqual(got["main"]["measurement"]["exceptions"]["original_source_quoted_or_line_cited"]["results"], 1)
            self.assertEqual(got["sidecar_records"], {"bound": 1, "unbound": 1})
            self.assertEqual(len(got["actors"]), 2)
            self.assertNotIn(directory, p.stdout)
            self.assertNotIn("tool_use_id", p.stdout.split('"limits"')[0])

    def test_sweep_keeps_legacy_skips_and_parse_errors_child_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child_dir = root / "session/subagents"
            child_dir.mkdir(parents=True)
            content = json.dumps(call("c", "Read"))
            (child_dir / "agent-child.jsonl").write_text(content + "\n{bad\n")
            (root / "session.jsonl").write_text(content + "\n{bad\n{bad\n")
            stale = [child_dir / "agent-old.jsonl", root / "old.jsonl", root / "older.jsonl"]
            for path in stale:
                path.write_text(content)
                os.utime(path, (0, 0))
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory,
                                "--since", "2026-09-26T00:00:00Z"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
            self.assertEqual(got["transcripts_found"], 2)
            self.assertEqual(got["transcripts_skipped_unmodified"], 1)
            self.assertEqual(got["parse_errors"], 1)
            self.assertEqual(got["main_transcripts_found"], 3)
            self.assertEqual(got["main_transcripts_skipped_unmodified"], 2)
            self.assertEqual(got["main_parse_errors"], 2)


if __name__ == "__main__":
    unittest.main()
