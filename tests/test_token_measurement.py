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


def shell_carriers(command):
    """The three shell-text carriers, their M4 carrier bucket and their curl/wget key."""
    return [("Bash", {"command": command}, "bash", "shell_fetch"),
            ("mcp__ctx__ctx_execute", {"language": "shell", "code": command}, "ctx", "ctx_sandbox_fetch"),
            ("mcp__ctx__ctx_batch_execute", {"commands": [{"command": command}]}, "ctx", "ctx_sandbox_fetch")]


# verify-fixup2 D1: heredoc openers whose stdin runs as a shell script. Sources: bash(1)
# OPTIONS/ARGUMENTS (GNU bash 5.2.21), POSIX.1-2024 sh OPTIONS/STDIN, OpenSSH ssh(1) 9.6p1.
EXECUTING_OPENERS = [
    "bash <<'EOF'", "bash <<'EOF' 2>&1 | tail -n 5", "bash <<'EOF' 2>&1", "bash <<'EOF' > log.txt",
    "bash <<'EOF' && echo done", "bash <<'EOF'; echo done", "timeout 60 bash <<'EOF' | tee out.log",
    "bash -euo pipefail <<'EOF'", "bash -o pipefail <<'EOF'", "bash -oe pipefail <<'EOF'",
    "bash +e <<'EOF'", "bash -O extglob <<'EOF'", "bash --norc <<'EOF'", "bash --login <<'EOF'",
    "bash --rcfile /dev/null <<'EOF'", "bash - <<'EOF'", "sh -e <<'EOF'", "dash -o nounset <<'EOF'",
    "ssh host <<'EOF'", "ssh -o StrictHostKeyChecking=no -p 22 user@host <<'EOF'",
    "ssh host bash -s <<'EOF'", "ssh host 'bash -s' <<'EOF'",
]
# Stdin never runs as source: -c or a script operand (a shell's `-` equals `--`), -n reads
# without executing, ssh -n/-N never read it, and a remote `cat` or a local `cat` keeps data.
IGNORED_OPENERS = [
    "bash -s -c 'echo x' <<'EOF'", "bash -n <<'EOF'", "bash -c cat <<'EOF'",
    "bash - script.sh <<'EOF'", "ssh -n host <<'EOF'", "ssh -N host <<'EOF'",
    "ssh host cat <<'EOF'", "ssh host 'cat > remote.sh' <<'EOF'", "cat <<'EOF' > run.sh",
]

# D7 (GPT-6 #8), R1 and R3 of the U1 pivot. Every command below was run on 2026-09-29 under GNU bash 5.2.21 and dash, with `env`
# cleared and PATH holding a stub curl that logs its calls (and a stub ssh that logs, then runs `sh` on its stdin: the remote
# login shell of OpenSSH ssh(1)); the comment on each list says how often the stub curl ran. Both shells agreed on every command.
# The outer shell expands a double-quoted string before the shell it starts sees it: a command substitution or backquote
# inside it runs there, whatever the inner shell then makes of the text (POSIX.1-2024 XCU 2.2.3 and 2.6.3).
D7_EXECUTED = [  # the outer shell runs the substitution: curl ran once
    "bash -c \"cat <<'EOF'\n$(curl https://example.org)\nEOF\"",  # GPT-6 #8, verbatim
    "bash -c \"cat <<'EOF'\nline\n$(curl https://example.org)\nEOF\"",
    "bash -c \"cat <<EOF\n$(curl https://example.org)\nEOF\"",  # an unquoted delimiter: still once, not once per view
    "bash -c \"echo '$(curl https://example.org)'\"", "bash -c \"# $(curl https://example.org)\"",
    "bash -c \"cat <<'EOF'\n`curl https://example.org`\nEOF\"", "sh -c \"cat <<'EOF'\n$(curl https://example.org)\nEOF\"",
    "eval \"echo '$(curl https://example.org)'\"", "ssh host \"cat <<'EOF'\n$(curl https://example.org)\nEOF\"",
    "bash -c \"echo ${UNSET_X:-$(curl https://example.org)}\"", "bash -c \"echo $(( $(curl https://example.org >/dev/null; echo 1) + 1 ))\"",
    "bash -c \"echo '$(curl \"https://example.org\")'\"", "bash -c \"echo \\\"$(curl https://example.org)\\\"\"",
]
D7_INNER = [  # the inner shell runs it (an escaped $ or backquote, or a single-quoted string that is not expanded): curl ran once
    "bash -c \"echo \\$(curl https://example.org)\"", "bash -c \"echo \\\"\\$(curl https://example.org)\\\"\"",
    "bash -c 'cat <<EOF\n$(curl https://example.org)\nEOF'", "bash -c 'echo \"$(curl https://example.org)\"'",
    "bash -c \"echo \\`curl https://example.org\\`\"",
]
D7_TWICE = [  # the outer shell runs one substitution and the inner shell another command or substitution: curl ran twice
    "bash -c \"x=$(curl https://example.org/a); curl https://example.org/b\"",
    "bash -c \"cat <<EOF\n$(curl https://example.org/a) \\$(curl https://example.org/b)\nEOF\"",
]
D7_DATA = [  # nothing runs curl: an escaped $ is data in a quoted heredoc, and a single-quoted string is not expanded
    "bash -c \"cat <<'EOF'\n\\$(curl https://example.org)\nEOF\"", "bash -c 'cat <<\"EOF\"\n$(curl https://example.org)\nEOF'",
]
# R1: a heredoc operator after a closed "$( )" in the same simple command still belongs to that command (curl ran once, except cat).
R1_EXECUTED = [
    "FOO=\"$(pwd)\" bash <<'EOF'\ncurl https://example.org\nEOF", "bash -s -- \"$(pwd)\" <<'EOF'\ncurl https://example.org\nEOF",
    "ssh \"$(echo host)\" <<'EOF'\ncurl https://example.org\nEOF", "x=\"$(cat <<'A'\nbody\nA\n)\" bash <<'B'\ncurl https://example.org\nB",
    "echo \"$(FOO=\"$(pwd)\" bash <<'EOF'\ncurl https://example.org\nEOF\n)\"", "FOO=$(pwd) bash <<'EOF'\ncurl https://example.org\nEOF",
]
R1_DATA = ["FOO=\"$(pwd)\" cat <<'EOF'\ncurl https://example.org\nEOF"]  # cat reads the body as data: curl never ran
# R3: an escaped blank, `;` or newline before a # is not a comment start, so the ) and the closing quote are found (curl ran once).
R3_EXECUTED = [
    'x="$(echo a\\ #b)"; curl https://example.org', 'x="$(echo a\\;#b)"; curl https://example.org',
    'x="$(echo a\\\n#b)"; curl https://example.org', 'x="$(echo a\\\\ #b\n)"; curl https://example.org',
    'x="$(echo a #b\n)"; curl https://example.org', 'echo a\\ #b; curl https://example.org',
]

# CLI lanes (#381 AA-PLAN PR-A item 3; U1 design sections 2-5 and 7). The stack commands are the literal entries of
# manifests/stack.json at cf3fb72e: :1003 toon, :797 repomix, :579 markitdown, :762 qmd, :519 headroom, :629 an
# mcporter list, and :280 and :407 mcporter calls, the two seeds of the downstream alias map.
STACK_LANE_COMMANDS = {
    "toon": 'toon fixtures/records.json --stats -o "${OUTPUT_DIR}/records.toon"',
    "repomix": 'repomix --include fixtures/records.json,fixtures/example.sh --output "${OUTPUT_DIR}/repomix.xml"',
    "markitdown": "markitdown fixtures/greeting.html",
    "qmd": 'qmd --index "${QMD_INDEX}" search "automatic local code RAG Nemotron" -c "${QMD_COLLECTION}" -n 2 --json',
    "headroom": "headroom mcp serve --proxy-url http://127.0.0.1:1",
}
STACK_MCPORTER_LIST = 'mcporter --config "${MCPORTER_CONFIG}" list socraticode --brief --no-oauth'
STACK_MCPORTER_CALLS = {
    "codebase-memory": ('mcporter --config "${MCPORTER_CONFIG}" call codebase-memory.search_graph'
                        ' --args "${GRAPH_QUERY_ARGS}" --output json --no-oauth', "codebase-memory-mcp"),
    "context-mode": ("mcporter --config \"${MCPORTER_CONFIG}\" call context-mode.ctx_doctor --args '{}'"
                     " --output text --no-oauth", "context-mode"),
}
CLI_CARRIERS = ("bash", "rtk_proxy", "ctx", "nested")
EMPTY_CLI = {"lanes": {}, "mcporter_downstream": {}, "excluded_version_help": {}, "calls_with_lane_invocation": 0,
             "unresolved_programs": 0, "remote_invocations": 0}


def lane_row(calls=1, carrier="bash", **counts):
    """One cli_lanes.lanes entry: `calls` calls with one invocation each, all on `carrier`, other counters zero."""
    row = {"calls": calls, "invocations": calls, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0,
           "unknown": 0, "background": 0, "ambiguous": 0, "via_mcporter": 0,
           "by_carrier": {c: calls if c == carrier else 0 for c in CLI_CARRIERS}}
    row.update(counts)
    return row


def downstream_row(calls=1, **counts):
    """One cli_lanes.mcporter_downstream entry."""
    row = {"calls": calls, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0, "unknown": 0}
    row.update(counts)
    return row


def proxy_row(calls=1, prefix_rule_calls=0, **counts):
    """measurement.proxy for `calls` unreviewed rtk proxy calls with one invocation each."""
    row = {"calls": calls, "acceptance": 0, "exception": 0, "unclassified": calls, "invocations": calls, "nested": 0,
           "in_ctx_code": 0, "prefix_rule_calls": prefix_rule_calls, "acceptance_or_exception_share": 0 if calls else None}
    row.update(counts)
    return row


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

    def exports(self, expression, value):
        """Evaluate `expression` (awaited) over the module's exports (`cu`) and the JSON input (`x`)."""
        script = ("import {readFileSync} from 'node:fs'; import * as cu from " + json.dumps(MODULE.as_uri())
                  + "; const x=JSON.parse(readFileSync(0,'utf8')); process.stdout.write(JSON.stringify(await ("
                  + expression + ")));")
        p = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(value),
                           text=True, capture_output=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def lanes_of(self, commands, *, name="Bash"):
        """[measurement.cli_lanes, measurement.proxy] of each command as one successful call, in one node process."""
        runs = []
        for command in commands:
            inputs = {"command": command} if name == "Bash" else {"language": "shell", "code": command}
            runs.append([call("c", name, **inputs), result("c", "ok")])
        return self.exports("x.map((rows) => { const m = cu.measureTranscript(rows); return [m.cli_lanes ?? null, m.proxy] })", runs)

    def carrier_m4(self, commands, routed=False):
        """M4 for each command on each shell carrier, optionally beside one routed fetch."""
        runs = [(command, *spec) for command in commands for spec in shell_carriers(command)]
        prefix = [call("routed", "mcp__ctx__ctx_fetch_and_index", url="https://example.org")] if routed else []
        got = self.exports("x.map((rows) => cu.measureTranscript(rows).m4)",
                           [prefix + [call("c", name, **inputs)] for _, name, inputs, _, _ in runs])
        return [(command, name, carrier, key, m4) for (command, name, _, carrier, key), m4 in zip(runs, got)]

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

    def test_m4_heredoc_resolves_its_whole_simple_command_on_every_carrier(self):
        # verify-fixup2 D1: pipes, lists and redirections after the heredoc token, shell
        # options with names or long forms, and ssh do not turn an executed body into data.
        commands = [opener + "\ncurl -s https://example.org\nEOF" for opener in EXECUTING_OPENERS]
        for command, name, _, key, m4 in self.carrier_m4(commands):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["unclassifiable"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        # An interpreter heredoc keeps its confirmed HTTP operation behind the same suffixes.
        commands = [opener + "\nfetch(u)\nEOF" for opener in
                    ["python3 - <<'EOF' | tail -n 5", "python3 - <<'EOF' 2>&1", "node <<'EOF' > out.txt"]]
        for command, name, _, _, m4 in self.carrier_m4(commands):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4["unclassifiable"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)

    def test_m4_unexecuted_heredoc_curl_wget_and_gh_api_stay_possible_fetches(self):
        # Recommendation 6 of verify-fixup2: raw curl/wget/gh api matches that executed-text
        # analysis does not confirm lower the gate's bound, like HTTP_SCRIPT matches.
        commands = [opener + "\ncurl -s https://example.org\nEOF" for opener in IGNORED_OPENERS]
        commands += ["cat <<'EOF' > fetch.sh\nwget -q https://example.org\nEOF",
                     "cat <<'EOF' > api.sh\ngh api repos/example/repo\nEOF",
                     "cat <<'EOF' > api.sh\nrtk proxy gh api repos/example/repo\nEOF"]
        for command, name, carrier, _, m4 in self.carrier_m4(commands, routed=True):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["routed_share"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
                self.assertEqual(m4["routed_share_lower_bound"], .5)
                self.assertEqual(m4["status"], "incomplete")
                self.assertEqual(m4["by_carrier"][carrier]["fetch_mentions_unconfirmed"], 1)

    def test_m4_heredoc_openers_respect_quotes_comments_and_arithmetic(self):
        # bash(1) QUOTING, COMMENTS and ARITHMETIC EVALUATION: a << inside quotes, in a comment
        # or in $(( )) opens no heredoc, so later lines are not swallowed; a heredoc inside a
        # quoted string that a shell runs is left to the quoted-string recursion.
        cases = [("bash -c \"python3 - <<'PY'\nrequests.get(u)\nPY\"\ncurl https://example.org", 1),
                 ('echo "a << b"\ncurl https://example.org', 0),
                 ("ls # see <<EOF\ncurl https://example.org", 0),
                 ("echo $(( 1 << bits ))\ncurl https://example.org", 0)]
        expected = dict(cases)
        for command, name, _, key, m4 in self.carrier_m4(list(expected)):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["unclassifiable"], expected[command])
                self.assertEqual(m4["remote_fetches"], 1 + expected[command])
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)

    def test_m4_confirmations_trace_back_to_raw_offsets(self):
        # verify-fixup2 D3: an executed-text match confirms only the raw match at its own raw
        # offset. Matches created by backslash-newline joins or by a quoted string a shell runs
        # cannot offset a raw miss; a join that creates a command position is counted once.
        cases = {"python3 - <<'EOF'\nr = requests.get \\\n    (u)\nx = 1 << bits\nrequests.get(v)\nEOF": (1, 0, 1),
                 "python3 - <<'EOF'\nr = requests.get\\\n(u)\nx = 1 << bits\nrequests.get(v)\nEOF": (1, 0, 1),
                 "bash -c 'curl https://example.org/a'\ncat <<'EOF' > b.sh\ncurl https://example.org/b\nEOF": (0, 1, 1),
                 "echo a; \\\ncurl https://example.org": (0, 1, 0)}
        for command, name, _, key, m4 in self.carrier_m4(list(cases)):
            http, shell, mentions = cases[command]
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4["unclassifiable"], http)
                self.assertEqual(m4[key], shell)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], mentions)

    def test_fetch_kind_and_legacy_lane_follow_the_heredoc_resolution(self):
        # Workflows README "Usage accounting": heredoc bodies count under ssh or a shell
        # heredoc (the legacy lanes.fetch.bash_curl_wget counter uses fetchKind).
        executing = [opener + "\ncurl -s https://example.org\nEOF" for opener in EXECUTING_OPENERS]
        executing.append("bash -c \"python3 - <<'PY'\nrequests.get(u)\nPY\"\ncurl https://example.org")
        ignored = [opener + "\ncurl -s https://example.org\nEOF" for opener in IGNORED_OPENERS]
        kinds = self.exports("x.map(cu.fetchKind)", executing + ignored)
        for command, kind in zip(executing + ignored, kinds):
            with self.subTest(command=command):
                self.assertEqual(kind, "fetch" if command in executing else None)
        rows = [call(str(i), "Bash", command=c) for i, c in enumerate(executing + ignored)]
        self.assertEqual(self.exports("cu.childLanes(x).fetch.bash_curl_wget", rows), len(executing))

    # N1, the #432 fixup3 residual: openers() did not track "$(" inside double quotes, and a quoted
    # string that a shell runs was added without its own heredoc resolution. POSIX.1-2024 XCU 2.6.3
    # (Command Substitution): inside double quotes the text between "$(" and the matching ")" is
    # tokenized recursively, so its heredoc is the inner command's data unless that command reads
    # stdin as source. GNU bash 5.2.21 and dash print these bodies as data. The probe bytes are
    # reconstructions of the verifier's shapes, which were not retained.
    def test_m4_n1_heredoc_in_double_quoted_substitution_or_run_string_is_data(self):
        body = "\n\ncurl -s https://example.org\nEOF\n)\""
        curl = ["git commit -m \"$(cat <<'EOF'\nSubject line" + body,  # p1
                "git commit -m \"$(cat <<'EOF'\nfix: don't retry" + body,
                "git commit -m \"$(cat <<'EOF'\nfix: handle \"quoted\" input" + body,
                "git commit -m \"$(cat <<'EOF'\nfix(scope): keep (a) and (b)" + body,
                "git commit -m \"$(cat <<'EOF'\nfix(ui): don't \"break\" it" + body,
                "bash -c 'cat <<EOF > x.sh\ncurl https://example.org\nEOF'",  # p3
                "bash -c \"cat <<EOF > x.sh\ncurl https://example.org\nEOF\""]
        for command, name, _, key, m4 in self.carrier_m4(curl):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
                self.assertEqual(m4["status"], "incomplete")
        gh = "gh pr create --title t --body \"$(cat <<'EOF'\n## Summary\ngh api repos/example/repo\nEOF\n)\""  # p2
        for command, name, _, _, m4 in self.carrier_m4([gh]):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4["unclassifiable"], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
        for command, kind in zip(curl + [gh], self.exports("x.map(cu.fetchKind)", curl + [gh])):
            with self.subTest(command=command):
                self.assertIsNone(kind)

    def test_m4_n1_executed_substitutions_and_run_strings_stay_confirmed(self):
        # Must-stay controls: a curl the substitution runs, a shell heredoc inside "$( )", an escaped
        # substitution in a double-quoted run string, and the command after a heredoc inside "$( )",
        # which resolving one heredoc twice would swallow as body. In the last case the outer shell
        # resolves the heredoc before `bash -c` reads the string (bash 5.2.21 and dash probe).
        executed = ["x=\"$(curl -s https://example.org)\"",
                    "echo \"$(bash <<'EOF'\ncurl https://example.org\nEOF\n)\"",
                    "bash -c \"echo \\\"\\$(curl https://example.org)\\\"\"",
                    "x=\"$(cat <<'EOF'\nbody\nEOF\ncurl https://example.org)\"",
                    "bash -c \"x=$(cat <<'EOF'\nbody\nEOF\n)\ncurl https://example.org\""]
        for command, name, _, key, m4 in self.carrier_m4(executed):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        data = ["x=$(cat <<'EOF'\ncurl -s https://example.org\nEOF\n)",
                "git commit -m \"$(cat <<'EOF'\nSubject (scope)\n\ncurl -s https://example.org\nEOF\n)\""]
        for command, name, _, key, m4 in self.carrier_m4(data):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
        self.assertEqual(self.exports("x.map(cu.fetchKind)", executed + data),
                         ["fetch"] * len(executed) + [None] * len(data))

    def test_m4_n1_quotes_inside_double_quoted_substitution_do_not_end_it(self):
        # POSIX.1-2024 XCU 2.6.3: quotes inside "$( )" belong to the substitution, so the commands after
        # them still run (bash 5.2.21 and dash print both words of "$(echo "a" && echo b)").
        command = "echo \"$(echo \"a\" && curl https://example.org)\""
        for _, name, _, key, m4 in self.carrier_m4([command]):
            with self.subTest(carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        self.assertEqual(self.exports("x.map(cu.fetchKind)", [command]), ["fetch"])

    def test_m4_n1_run_string_is_analyzed_as_the_inner_shells_input(self):
        # A string that a shell runs is that shell's input. In a double-quoted word the outer shell
        # removes the backslash before $ ` " \ and newline (POSIX.1-2024 XCU 2.2.3), so an escaped
        # quote stays a quote for the inner shell, and a string the inner shell runs in turn is
        # analyzed as well (bash 5.2.21 and dash: `bash -c "echo \"a; echo x\""` prints one line).
        quoted = "bash -c \"echo \\\"a; curl https://example.org\\\"\""
        for _, name, _, key, m4 in self.carrier_m4([quoted]):
            with self.subTest(command=quoted, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
        # Before the fix the nested curl was in neither count, so it could not lower the bound.
        nested = "ssh host 'bash -c \"curl https://example.org\"'"
        for _, name, _, key, m4 in self.carrier_m4([nested]):
            with self.subTest(command=nested, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        self.assertEqual(self.exports("x.map(cu.fetchKind)", [quoted, nested]), [None, "fetch"])

    def test_m4_d7_outer_shell_substitutions_in_a_double_quoted_run_string_are_executed(self):
        # D7 (GPT-6 #8): N1 read a double-quoted run string only as the inner shell's input, so a substitution the outer
        # shell runs was lost whenever the inner shell read it as data (a quoted heredoc, single quotes, a comment). Two views:
        # the substitutions the outer shell runs, and the inner shell's parse of the string it receives. The count is the
        # number of times the stub curl ran, so a substitution both views could see counts once.
        for command, name, _, key, m4 in self.carrier_m4(D7_EXECUTED + D7_INNER):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
                self.assertEqual(m4["status"], "measured")
        for command, name, _, key, m4 in self.carrier_m4(D7_TWICE):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 2)
                self.assertEqual(m4["remote_fetches"], 2)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        for command, name, _, key, m4 in self.carrier_m4(D7_DATA):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
                self.assertEqual(m4["status"], "incomplete")
        commands = D7_EXECUTED + D7_INNER + D7_TWICE + D7_DATA
        self.assertEqual(self.exports("x.map(cu.fetchKind)", commands),
                         ["fetch"] * (len(commands) - len(D7_DATA)) + [None] * len(D7_DATA))

    def test_cli_lanes_count_a_lane_the_outer_shell_runs_through_a_double_quoted_run_string(self):
        # D7 with qmd in place of curl (GPT-6 #8): the outer shell runs the substitution, so it is one qmd call.
        got = self.lanes_of(["bash -c \"cat <<'EOF'\n$(qmd search x)\nEOF\""])
        cli = got[0][0]
        self.assertEqual((cli["lanes"].get("qmd") or {}).get("calls"), 1)
        self.assertEqual((cli["lanes"].get("qmd") or {}).get("invocations"), 1)

    def test_m4_r1_a_heredoc_after_a_closed_double_quoted_substitution_keeps_its_reader(self):
        # R1 (Claude review of 3cb7c4f6): the cuts a "$( )" inside double quotes added bounded every heredoc of the line,
        # so the opener's command started at the closing quote, its reader read as empty and a shell-read body became data.
        # Each opener is bounded by the cuts of its own command level (M4 as at cf3fb72e: curl ran once).
        for command, name, _, key, m4 in self.carrier_m4(R1_EXECUTED):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        for command, name, _, key, m4 in self.carrier_m4(R1_DATA):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
        self.assertEqual(self.exports("x.map(cu.fetchKind)", R1_EXECUTED + R1_DATA),
                         ["fetch"] * len(R1_EXECUTED) + [None] * len(R1_DATA))
        # An interpreter that reads the heredoc keeps its confirmed HTTP operation behind the same "$( )" (inlineHttp mode).
        interpreters = ["python3 - \"$(pwd)\" <<'EOF'\nfetch(u)\nEOF", "FOO=\"$(pwd)\" node <<'EOF'\nfetch(u)\nEOF"]
        for command, name, _, _, m4 in self.carrier_m4(interpreters):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4["unclassifiable"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)

    def test_cli_lanes_read_the_heredoc_a_shell_reads_after_a_closed_double_quoted_substitution(self):
        got = self.lanes_of(["FOO=\"$(pwd)\" bash <<'EOF'\nqmd search x\nEOF"])
        self.assertEqual((got[0][0]["lanes"].get("qmd") or {}).get("calls"), 1)

    def test_m4_r3_an_escaped_metacharacter_before_a_hash_is_not_a_comment_start(self):
        # R3 (Claude review): in a $( ) frame a # after an escaped blank, `;` or newline was read as a comment, so the ) and
        # the closing quote ran on to the end of the command and the `; curl` after them fell inside double-quoted data.
        # bash(1) COMMENTS: only a word beginning with # (after an unquoted blank or metacharacter) starts a comment.
        for command, name, _, key, m4 in self.carrier_m4(R3_EXECUTED):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        self.assertEqual(self.exports("x.map(cu.fetchKind)", R3_EXECUTED), ["fetch"] * len(R3_EXECUTED))

    def test_cli_lanes_count_stack_commands_in_command_position(self):
        # #381 AA-PLAN PR-A item 3: a lane executable in command position is a lane call. An mcporter list counts for
        # mcporter; an mcporter call counts for its downstream server and reaches a lane only through the alias map.
        lanes = list(STACK_LANE_COMMANDS.items())
        calls = list(STACK_MCPORTER_CALLS.items())
        got = self.lanes_of([c for _, c in lanes] + [STACK_MCPORTER_LIST] + [c for _, (c, _) in calls])
        for (lane, command), (cli, _) in zip(lanes, got):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "lanes": {lane: lane_row(succeeded=1)}, "calls_with_lane_invocation": 1})
        self.assertEqual(got[len(lanes)][0], {**EMPTY_CLI, "lanes": {"mcporter": lane_row(succeeded=1)},
                                              "calls_with_lane_invocation": 1})
        for (server, (command, alias)), (cli, _) in zip(calls, got[len(lanes) + 1:]):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "lanes": {alias: lane_row(succeeded=1, via_mcporter=1)},
                                       "mcporter_downstream": {server: downstream_row(succeeded=1)},
                                       "calls_with_lane_invocation": 1})

    def test_cli_lanes_follow_wrappers_compound_commands_and_substitutions(self):
        # POSIX.1-2024 XCU 2.9.1 (Rule 7 assignments), 2.9.2-2.9.4 (pipelines, lists, compound commands), 2.6.3 (command
        # substitution) and the timeout, env, nice, command, time and xargs synopses; GNU coreutils 9.4 stdbuf; sudo
        # 1.9.15p5. More than one simple command makes the call ambiguous: its one state covers every command.
        cases = {"timeout -k 5 60 qmd search x": ("qmd", 0), "env -u X markitdown f.pdf": ("markitdown", 0),
                 "env -C d repomix": ("repomix", 0), "nice -n 10 repomix": ("repomix", 0),
                 "sudo -u u ai-memory status": ("ai-memory", 0), "command qmd status": ("qmd", 0),
                 "time -p toon f.json": ("toon", 0), "stdbuf -oL qmd search x": ("qmd", 0),
                 "find . -print0 | xargs -0 -n1 markitdown": ("markitdown", 1),
                 'for f in *.pdf; do markitdown "$f"; done': ("markitdown", 1),
                 "if qmd status; then :; fi": ("qmd", 1), "(cd d && qmd status)": ("qmd", 1),
                 "{ qmd get a; }": ("qmd", 0), "! qmd search x": ("qmd", 0), "x=$(qmd get a)": ("qmd", 1),
                 'echo "$(qmd get a)"': ("qmd", 1), "echo `qmd get a`": ("qmd", 1),
                 "bash -c 'qmd search x'": ("qmd", 1), "bash <<'EOF'\nqmd search x\nEOF": ("qmd", 1),
                 "cat <<EOF\n$(qmd get a)\nEOF": ("qmd", 1)}
        for (command, (lane, ambiguous)), (cli, _) in zip(cases.items(), self.lanes_of(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "lanes": {lane: lane_row(succeeded=1, ambiguous=ambiguous)},
                                       "calls_with_lane_invocation": 1})

    def test_cli_lanes_runners_and_direct_calls(self):
        # Executables: toon, repomix, @tobilu/qmd, mcporter and context-mode package bins; markitdown, headroom,
        # jcodemunch-mcp and serena console scripts; the codebase-memory-mcp and ai-memory binaries (U1 sources S5-S16).
        # Runners map their npm or PyPI package to the lane; `--from` names the executable itself.
        cases = {"npx -y repomix --mcp": "repomix", "npx repomix@latest": "repomix", "npx @toon-format/cli f.json": "toon",
                 "bunx @tobilu/qmd search x": "qmd", "uvx jcodemunch-mcp": "jcodemunch-mcp", "serena init": "serena",
                 "context-mode doctor": "context-mode", "codebase-memory-mcp cli search_graph '{}'": "codebase-memory-mcp",
                 "/usr/local/bin/qmd search x": "qmd", "ai-memory status": "ai-memory",
                 "uvx --from serena-agent serena start-mcp-server": "serena", "pipx run headroom-ai": "headroom",
                 "python3 -m markitdown f.pdf": "markitdown", "serena-agent start": "serena"}
        for (command, lane), (cli, _) in zip(cases.items(), self.lanes_of(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "lanes": {lane: lane_row(succeeded=1)}, "calls_with_lane_invocation": 1})

    def test_cli_lanes_mcporter_calls_count_for_the_downstream_server(self):
        # openclaw/mcporter@93e0916c (v0.14.1): global flags (cli-factory.ts:19), command inference
        # (command-inference.ts:10-95), call parsing (call-arguments.ts:79-233), target resolution (call-command.ts:114-173,
        # 309-348). An HTTP selector or ad-hoc stdio command has no config name: it reads (http) or (stdio), never a host.
        cases = {"mcporter call linear.create_comment --issue-id X": "linear",
                 "mcporter call 'linear.create_comment(issueId: \"LNR-123\", body: \"Hi\")'": "linear",
                 "mcporter 'context7.resolve-library-id(\"React hooks docs\", \"react\")'": "context7",
                 "mcporter call --server linear --tool create_comment": "linear",
                 "mcporter call linear create_comment": "linear",
                 "mcporter call create_comment server=linear": "linear",
                 # The first positional is the selector even with '=' (call-arguments.ts:170-172), so this names a
                 # server "server=linear", which is not name-shaped.
                 "mcporter call server=linear tool=create_comment": "(other)",
                 "npx mcporter call https://mcp.context7.com/mcp.resolve-library-id": "(http)",
                 "mcporter call \"npx -y chrome-devtools-mcp@latest\" list_pages": "(stdio)",
                 "mcporter --config c.json --log-level debug call x.y --timeout 5000 --output json -- --literal": "x"}
        for (command, server), (cli, _) in zip(cases.items(), self.lanes_of(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "mcporter_downstream": {server: downstream_row(succeeded=1)}})
                self.assertNotIn("context7.com", json.dumps(cli))

    def test_cli_lanes_ignore_data_lookups_registrations_and_near_names(self):
        negatives = ["command -v qmd", "type qmd", "which qmd", "hash qmd", "grep -n qmd notes.md",
                     'git commit -m "use toon"', "echo 'rtk proxy ls'", 'echo "rtk proxy pytest"',
                     'git log --grep="rtk proxy"', "# qmd search x", "cat ~/.qmd/index.sqlite", "ls toon/", "qmdx",
                     "my-repomix", "git commit -m \"$(cat <<'EOF'\nqmd search x\nEOF\n)\"",
                     "cat <<EOF > run.sh\nrtk proxy pytest\nEOF",
                     "claude mcp add context-mode -- npx -y context-mode",  # context-mode README:117 registers only
                     "codex mcp add qmd -- qmd mcp", "rtk git status",  # stack.json:826, an rtk filter
                     "gcm chat", "serena-hooks pre-tool"]  # lane-membership decisions: not lane executables
        for command, (cli, proxy) in zip(negatives, self.lanes_of(negatives)):
            with self.subTest(command=command):
                self.assertEqual(cli, EMPTY_CLI)
                self.assertEqual(proxy.get("calls"), 0)

    def test_cli_lanes_version_help_remote_and_unresolved_programs(self):
        # --version and --help among a lane's own words (before `--`; for rtk proxy, rtk's words before the proxied
        # program) are counted apart, per lane; mcporter's pinned help/version tokens and clap's rtk -V/-h as well.
        cases = {"qmd --version": {"excluded_version_help": {"qmd": 1}},
                 "toon --help": {"excluded_version_help": {"toon": 1}},
                 "ai-memory --version": {"excluded_version_help": {"ai-memory": 1}},  # stack.json:101
                 "mcporter --version": {"excluded_version_help": {"mcporter": 1}},
                 "rtk --version": {"excluded_version_help": {"rtk_proxy": 1}},
                 "ssh host 'qmd search x'": {"remote_invocations": 1},
                 "$QMD search x": {"unresolved_programs": 1},
                 "qmd search -- --help": {"lanes": {"qmd": lane_row(succeeded=1)}, "calls_with_lane_invocation": 1},
                 "rtk proxy qmd --version": {"lanes": {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1)},
                                             "excluded_version_help": {"qmd": 1}, "calls_with_lane_invocation": 1}}
        for (command, fields), (cli, proxy) in zip(cases.items(), self.lanes_of(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, **fields})
                self.assertEqual(proxy.get("calls"), 1 if command.startswith("rtk proxy") else 0)

    def test_cli_lane_states_follow_the_call_result(self):
        # AA-PLAN: "Successful" means the tool_result is not an error (Messages API is_error). An error that never ran
        # is also not_executed: content "<tool_use_error>", or a toolUseResult naming a PreToolUse hook denial, a
        # permission denial or a user rejection (strings observed on clients 2.1.282-2.1.283, not a documented schema).
        def bash(key, command="qmd search x", **inputs):
            return call(key, "Bash", command=command, **inputs)

        def answer(key, content="ok", error=False, **row):
            return {**result(key, content, error), **row}

        declined = bash("a")
        declined["message"]["content"][0]["native_status"] = "declined"
        unknown = answer("a", "Chunk ID: 1\nOutput:\nx")
        unknown["message"]["content"][0]["native_state"] = "unknown"
        ctx = answer("a")
        del ctx["message"]["content"][0]["is_error"]
        cases = {"exit": ([bash("a"), answer("a", "Exit code 1\nboom", True, toolUseResult="Error: Exit code 1\nboom")],
                          lane_row(failed=1)),
                 "tool_use_error": ([bash("a"), answer("a", "<tool_use_error>Error: blocked</tool_use_error>", True,
                                                       toolUseResult="Error: blocked")], lane_row(failed=1, not_executed=1)),
                 "hook": ([bash("a"), answer("a", "PreToolUse:Bash hook error: denied", True,
                                             toolUseResult="Error: PreToolUse:Bash hook error: denied")],
                          lane_row(failed=1, not_executed=1)),
                 "permission": ([bash("a"), answer("a", "Permission for this command was denied", True,
                                                   toolUseResult="Error: Permission for this command was denied")],
                                lane_row(failed=1, not_executed=1)),
                 "rejected": ([bash("a"), answer("a", "The user doesn't want to proceed with this tool use.", True,
                                                 toolUseResult="User rejected tool use")], lane_row(failed=1, not_executed=1)),
                 "no result": ([bash("a")], lane_row(unfinished=1)),
                 "declined": ([declined], lane_row(failed=1, not_executed=1)),
                 "succeeded": ([bash("a"), answer("a", toolUseResult={"stdout": "ok", "stderr": "", "interrupted": False})],
                               lane_row(succeeded=1)),
                 "background": ([bash("a", run_in_background=True), answer("a", "started", toolUseResult={"backgroundTaskId": "b1"})],
                                lane_row(succeeded=1, background=1)),
                 "ambiguous": ([bash("a", "qmd search x || true"), answer("a")], lane_row(succeeded=1, ambiguous=1)),
                 "unknown": ([bash("a"), unknown], lane_row(unknown=1)),
                 "ctx": ([call("a", "mcp__ctx__ctx_execute", language="shell", code="qmd search x"), ctx],
                         lane_row(carrier="ctx", succeeded=1))}
        got = self.exports("x.map((rows) => cu.measureTranscript(rows).cli_lanes ?? null)", [rows for rows, _ in cases.values()])
        for (name, (_, row)), cli in zip(cases.items(), got):
            with self.subTest(state=name):
                self.assertEqual((cli or {}).get("lanes"), {"qmd": row})
                self.assertNotIn("b1", json.dumps(cli))

    def test_rtk_proxy_population_follows_command_position(self):
        # rtk-ai/rtk@1d87b8e7 src/main.rs:68-90 (-v/--verbose, --ultra-compact, --skip-env before the subcommand) and
        # :3008-3042 (proxy's arguments; one spaced argument is shell-split, and no shell runs it). The prefix rule is
        # kept as prefix_rule_calls for comparison with earlier receipts.
        proxied = {"cd repo && rtk proxy pytest -q": (0, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1, ambiguous=1)}),
                   "FOO=1 rtk proxy pytest": (0, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1)}),
                   "rtk proxy qmd search x": (1, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1),
                                                  "qmd": lane_row(carrier="rtk_proxy", succeeded=1)}),
                   "rtk proxy 'qmd search x'": (1, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1),
                                                    "qmd": lane_row(carrier="rtk_proxy", succeeded=1)}),
                   "rtk --ultra-compact proxy pytest": (0, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1)}),
                   "rtk -v proxy pytest": (0, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1)}),
                   'sh -c "rtk proxy pytest"': (0, {"rtk_proxy": lane_row(carrier="rtk_proxy", succeeded=1, ambiguous=1)})}
        for (command, (prefix, lanes)), (cli, proxy) in zip(proxied.items(), self.lanes_of(list(proxied))):
            with self.subTest(command=command):
                self.assertEqual(proxy, proxy_row(prefix_rule_calls=prefix))
                self.assertEqual((cli or {}).get("lanes"), lanes)
        # Newly counted calls stay unclassified until a digest-bound review classifies them (M6).
        reviewed = self.measure([call("c", "Bash", command="cd repo && rtk proxy pytest -q"), result("c", "ok")],
                                exceptions={"c": {"proxy_purpose": "acceptance", "witness": "frozen check"}})
        self.assertEqual(reviewed["proxy"], proxy_row(acceptance=1, unclassified=0, acceptance_or_exception_share=1))
        # M3 by_carrier.rtk_proxy and m4.by_carrier follow the same rule.
        got = self.measure([call("m3", "Bash", command="cd repo && rtk proxy pytest -q"), result("m3", "x" * 6000),
                            call("m4", "Bash", command="cd repo && rtk proxy curl -s https://example.org")])
        self.assertEqual(got["by_carrier"].get("rtk_proxy", {}).get("large_results"), 1)
        self.assertEqual(got["m4"]["by_carrier"].get("rtk_proxy", {}).get("shell_fetch"), 1)
        self.assertEqual(sorted(got["m4"]["by_carrier"]), ["rtk_proxy"])
        # rtk proxy in ctx shell code is reported apart and stays outside M6; a sandbox-nested Codex call stays inside.
        nested = call("n", "Bash", command="rtk proxy pytest")
        nested["message"]["content"][0]["sandbox"] = True
        got = self.measure([call("x", "mcp__ctx__ctx_execute", language="shell", code="rtk proxy pytest"), result("x", "ok"),
                            nested, result("n", "ok")])
        self.assertEqual(got["proxy"], proxy_row(prefix_rule_calls=1, nested=1, in_ctx_code=1))
        both = lane_row(calls=2, succeeded=2)
        both["by_carrier"] = {"bash": 0, "rtk_proxy": 0, "ctx": 1, "nested": 1}
        self.assertEqual((got.get("cli_lanes") or {}).get("lanes"), {"rtk_proxy": both})

    def test_cli_lanes_aggregate_sums_counters_and_counts_actors_with_success(self):
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript, aggregateMeasurements} from "
                  + json.dumps(MODULE.as_uri()) + "; const rows=JSON.parse(readFileSync(0,'utf8')); "
                  "process.stdout.write(JSON.stringify([aggregateMeasurements(rows.map(r=>measureTranscript(r))), "
                  "aggregateMeasurements([])]));")
        actors = [[call("a", "Bash", command="qmd search x"), result("a", "ok"),
                   call("b", "Bash", command="mcporter call linear.create_comment --issue-id X"), result("b", "ok")],
                  [call("c", "Bash", command="qmd get a"), result("c", "Exit code 1", True),
                   call("d", "mcp__ctx__ctx_execute", language="shell", code="rtk proxy pytest"), result("d", "ok"),
                   call("e", "Bash", command="qmd --version"), result("e", "2.8.3")]]
        p = subprocess.run(["node", "--input-type=module", "-e", script],
                           input=json.dumps(actors), text=True, capture_output=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        got, empty = json.loads(p.stdout)
        self.assertEqual(got.get("cli_lanes"), {
            **EMPTY_CLI, "calls_with_lane_invocation": 3, "excluded_version_help": {"qmd": 1},
            "lanes": {"qmd": {**lane_row(calls=2, succeeded=1, failed=1), "actors_with_success": 1},
                      "rtk_proxy": {**lane_row(carrier="ctx", succeeded=1), "actors_with_success": 1}},
            "mcporter_downstream": {"linear": downstream_row(succeeded=1)}})
        self.assertEqual(got["proxy"], proxy_row(calls=0, in_ctx_code=1))
        self.assertEqual(empty.get("cli_lanes"), EMPTY_CLI)

    def test_sweep_cli_lanes_and_proxy_are_id_free(self):
        # Output is names and counts: no directory, tool_use_id, host, URL, path or command text from the fixture.
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "session/subagents/agent-child.jsonl"
            child.parent.mkdir(parents=True)
            commands = ["npx mcporter call https://mcp.context7.com/mcp.resolve-library-id",
                        "ssh buildhost.example.net 'qmd search \"private query\"'", 'qmd search "private query"',
                        "cd /srv/private-repo && rtk proxy pytest -q", "mcporter call --server linear --tool create_comment"]
            rows = []
            for i, command in enumerate(commands):
                rows += [call("toolu_private_%d" % i, "Bash", command=command), result("toolu_private_%d" % i, "ok")]
            child.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
            cli = got["groups"]["all"]["measurement"].get("cli_lanes") or {}
            self.assertEqual(sorted(cli.get("lanes", {})), ["qmd", "rtk_proxy"])
            self.assertEqual(sorted(cli.get("mcporter_downstream", {})), ["(http)", "linear"])
            self.assertEqual(cli.get("remote_invocations"), 1)
            self.assertEqual(got["actors"][0]["measurement"]["proxy"].get("invocations"), 1)
            for secret in [directory, "toolu_private", "context7", "buildhost", "example.net", "private query",
                           "private-repo", "/srv"]:
                self.assertNotIn(secret, p.stdout)
            self.assertNotIn("tool_use_id", p.stdout.split('"limits"')[0])
            self.assertIn("cli_lanes", got["limits"])

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
