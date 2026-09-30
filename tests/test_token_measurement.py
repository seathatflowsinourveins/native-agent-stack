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
# The tree-sitter-bash install the kernel's lane reading needs (child-usage.mjs loadShellParser): CHILD_USAGE_SHELL_PARSER, else the
# ecosystem tools directory that shell-parser.pin.json names. Tests of lane counts skip, with this message, on a host without it.
PARSER_DIR = Path(os.environ.get("CHILD_USAGE_SHELL_PARSER") or Path.home() / ".local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1")
PARSER_INSTALLED = (PARSER_DIR / "package-lock.json").is_file()
NEEDS_PARSER = unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
# What a measured cli_lanes records about the parser (versions and the two wasm sha256 values, no path): shell-parser.pin.json.
PARSER_RECORD = {"versions": {"tree_sitter_bash": "0.25.1", "web_tree_sitter": "0.27.0"},
                 "wasm_sha256": {"tree_sitter_bash": "8292919c88a0f7d3fb31d0cd0253ca5a9531bc1ede82b0537f2c63dd8abe6a7a",
                                 "web_tree_sitter": "c03bccdc3b448a32848f5ae327e209c982bbb0840d43eec8bc2d5759544a1ed3"}}


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
    "ssh \"$(echo host)\" <<'EOF'\ncurl https://example.org\nEOF", "FOO=$(pwd) bash <<'EOF'\ncurl https://example.org\nEOF",
    "echo \"$(FOO=\"$(pwd)\" bash <<'EOF'\ncurl https://example.org\nEOF\n)\"",
    # A quote inside the substitution, two substitutions, and controls that already read correctly at f83f8367 (a backquote span,
    # a separator before the operator, a nested "$( )" that has its own heredoc).
    "FOO=\"$(echo \"a b\")\" bash <<'EOF'\ncurl https://example.org\nEOF", "ssh \"$(echo \"h o\")\" <<'EOF'\ncurl https://example.org\nEOF",
    "A=\"$(pwd)\" B=\"$(pwd)\" bash <<'EOF'\ncurl https://example.org\nEOF", "FOO=\"`pwd`\" bash <<'EOF'\ncurl https://example.org\nEOF",
    "x=\"$(cat <<'A'\nbody\nA\n)\" && bash <<'B'\ncurl https://example.org\nB",
    "echo \"$(echo \"$(pwd)\" | bash <<'EOF'\ncurl https://example.org\nEOF\n)\"",
]
# Limit (not a defect of the per-level cuts): a construct that runs over lines carries its command's head on an earlier line, so
# the heredoc operator after it has no reader on its own line. Real shells run curl once for each of these; the kernel reads the
# body as data, a possible fetch (fetch_mentions_unconfirmed 1, status incomplete), never a lost one.
R1_MULTILINE = [
    "x=\"$(cat <<'A'\nbody\nA\n)\" bash <<'B'\ncurl https://example.org\nB", "x=\"a\nb\" bash <<'EOF'\ncurl https://example.org\nEOF",
    "x='a\nb' bash <<'EOF'\ncurl https://example.org\nEOF", "x=\"$(cat <<'A'\nbody\nA\n) tail\" bash <<'B'\ncurl https://example.org\nB",
]
R1_DATA = [  # the reader is cat, so the body is data and curl never ran
    "FOO=\"$(pwd)\" cat <<'EOF'\ncurl https://example.org\nEOF", "FOO=\"$(echo \"a b\")\" cat <<'EOF'\ncurl https://example.org\nEOF",
    "echo \"$(cat <<'EOF'\ncurl https://example.org\nEOF\n)\"",
]
# The same two views for a heredoc body: with an unquoted delimiter the shell that reads the command line expands the body (each
# unescaped $( ) and backquote runs there, quotes are literal, a backslash escapes only $ ` \ and a newline) before the shell
# that reads the heredoc sees it (bash(1) Here Documents; POSIX.1-2024 XCU 2.7.4). Run under bash 5.2.21 and dash with stub curl:
# curl ran once for each of these commands, except HD_TWICE (twice) and HD_DATA (never: a quoted delimiter passes the body as is).
HD_ONCE = [
    "bash <<EOF\necho '$(curl https://example.org)'\nEOF", "sh <<EOF\necho '$(curl https://example.org)'\nEOF",
    "FOO=\"$(pwd)\" bash <<EOF\necho '$(curl https://example.org)'\nEOF", "ssh host <<EOF\necho '$(curl https://example.org)'\nEOF",
    "bash <<EOF\necho \\$(curl https://example.org)\nEOF", "bash <<EOF\n`curl https://example.org`\nEOF",
    "bash <<EOF\ncurl https://example.org\nEOF", "bash <<EOF\nx=$(curl https://example.org)\nEOF",
    "cat <<EOF\necho '$(curl https://example.org)'\nEOF", "bash <<EOF\n# $(curl https://example.org)\nEOF",
    "bash <<EOF\necho '$(curl \"https://example.org\")'\nEOF", "bash <<EOF\necho '$(echo a\ncurl https://example.org)'\nEOF",
    "bash <<EOF\necho \\\\$(curl https://example.org)\nEOF", "bash <<EOF\ncu\\\nrl https://example.org\nEOF",
    "bash <<-EOF\n\techo '$(curl https://example.org)'\n\tEOF", "bash <<EOF\necho '$(( $(curl https://example.org >/dev/null; echo 1) + 1 ))'\nEOF",
    "bash <<EOF\nbash -c \"echo '$(curl https://example.org)'\"\nEOF",
]
HD_TWICE = ["bash <<EOF\necho $(curl https://example.org/a); echo \\$(curl https://example.org/b)\nEOF"]
HD_DATA = ["bash <<'EOF'\necho '$(curl https://example.org)'\nEOF", "bash <<\"EOF\"\necho '$(curl https://example.org)'\nEOF"]
# A run string that follows an opening backquote is a run string: the anchor of a command name is the text start, a blank, ; & | (
# or a backquote (bash(1) Command Substitution, the `command` form). Run under bash 5.2.21 and dash with stub curl and wget (BQ_ONCE
# ran the stub once each; BQ_DATA never).
BQ_ONCE = [
    "echo `bash -c \"curl https://example.org\"`", "x=`ssh host \"wget https://example.org\"`", "echo `eval \"curl https://example.org\"`",
    "echo `bash -c 'curl https://example.org'`", "sh -c 'echo `bash -c \"curl https://example.org\"`'",
    "bash -c \"echo \\`bash -c 'curl https://example.org'\\`\"",
    "echo ` bash -c \"curl https://example.org\"`", "echo $(bash -c \"curl https://example.org\")",  # controls that read correctly already
]
BQ_DATA = ["echo `echo \"curl https://example.org\"`"]
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
EMPTY_CLI = {"status": "measured", "parser": PARSER_RECORD, "lanes": {}, "mcporter_downstream": {}, "excluded_version_help": {},
             "calls_with_lane_invocation": 0, "unresolved_programs": 0, "remote_invocations": 0, "parse_errors": 0}

# Result templates of calls that never ran (U2 item 7; M14). The Claude Code client writes them (observed on this host, not a documented
# schema; count-only: evidence/artifacts/pra-u2-differential-20260929/scans/call-states.json). Every observed row that did not run carries a
# toolDenialKind or a <tool_use_error> or user-rejection content, so the config and cancelled texts below are read by U1's rule only through
# the denial kind; the fixtures that omit it are the ones that fail first. The interrupt marker is written as a user text block after a
# user-rejection result (37 of 37), never as a result: its result form is the U2 design's binary constant, kept as not observed.
PERMISSION_TO_USE = "Permission to use Bash with command rm -rf build has been denied."
NOT_RUN = "Not run: the response that made this tool call was stopped by a safety classifier."
INTERRUPT_MARKER = "[Request interrupted by user for tool use]"
USER_REJECTION = ("The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the "
                  "new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.")
HOOK_DENIAL = "PreToolUse:Bash hook error: Blocked by a project hook"
PERMISSION_FOR = "Permission for this tool use was denied."
AUTOMODE_NO_VERDICT = ("The server-side auto mode classifier gave no verdict (error), so auto mode cannot determine the safety of Bash. "
                       "This is a transient failure of the check, not a judgment about the action.")


def said(key, blocks, timestamp="2026-09-26T01:00:00Z"):
    """An assistant row as the client writes it: a provider message id and its content blocks (PR-A item 6 reads final messages)."""
    return {"type": "assistant", "timestamp": timestamp, "message": {"id": key, "content": blocks}}


def rtk_rewrite(key, command, timestamp="2026-09-26T01:00:00Z"):
    """The PreToolUse:Bash hook row `rtk hook claude` writes when it rewrites the call `key` to `command`."""
    return {"type": "attachment", "timestamp": timestamp, "attachment": {
        "type": "hook_success", "hookName": "PreToolUse:Bash", "hookEvent": "PreToolUse", "toolUseID": key, "command": "rtk hook claude",
        "stdout": json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {"command": command}}})}}


# The empty M14 counters of rtk_parts.eligible_call_states (the per-server key set of call_states.by_server).
M14_ROW = {"attempted": 0, "executed": 0, "succeeded": 0, "failed": 0, "interrupted": 0, "rejected": 0, "invalid": 0,
           "cancelled_with_result": 0, "cancelled_or_unfinished": 0, "unknown": 0}


def lane_row(calls=1, carrier="bash", **counts):
    """One cli_lanes.lanes entry: `calls` calls with one invocation each, all on `carrier`, other counters zero."""
    row = {"calls": calls, "invocations": calls, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0,
           "unknown": 0, "interrupted": 0, "background": 0, "ambiguous": 0, "via_mcporter": 0,
           "by_carrier": {c: calls if c == carrier else 0 for c in CLI_CARRIERS}}
    row.update(counts)
    return row


def lane_calls(cli):
    """{lane: calls} of a measured cli_lanes (an unmeasured one has none)."""
    return {lane: row["calls"] for lane, row in (cli or {}).get("lanes", {}).items()}


def downstream_row(calls=1, **counts):
    """One cli_lanes.mcporter_downstream entry."""
    row = {"calls": calls, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0, "unknown": 0, "interrupted": 0}
    row.update(counts)
    return row


def proxy_row(calls=1, prefix_rule_calls=0, **counts):
    """measurement.proxy for `calls` unreviewed rtk proxy calls with one invocation each."""
    row = {"calls": calls, "acceptance": 0, "exception": 0, "unclassified": calls, "invocations": calls, "nested": 0,
           "in_ctx_code": 0, "prefix_rule_calls": prefix_rule_calls, "rule": "command_position",
           "acceptance_or_exception_share": 0 if calls else None}
    row.update(counts)
    return row


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TokenMeasurement(unittest.TestCase):
    def measure(self, rows, *, env=None, parser=True, **options):
        """measureTranscript over `rows`. With parser=True (the default) the kernel's loadShellParser() is awaited first, as its CLI and
        the Codex bridge do; on a host with no install, or with CHILD_USAGE_SHELL_PARSER in `env` naming none, cli_lanes says so."""
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript, loadShellParser} from "
                  + json.dumps(MODULE.as_uri()) + "; const x=JSON.parse(readFileSync(0,'utf8')); "
                  + ("await loadShellParser(); " if parser else "")
                  + "process.stdout.write(JSON.stringify(measureTranscript(x.rows,x.options))); ")
        p = subprocess.run(["node", "--input-type=module", "-e", script],
                           input=json.dumps({"rows": rows, "options": options}),
                           text=True, capture_output=True, check=False, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def exports(self, expression, value, *, env=None, parser=True):
        """Evaluate `expression` (awaited) over the module's exports (`cu`) and the JSON input (`x`), after awaiting loadShellParser()
        unless parser=False."""
        script = ("import {readFileSync} from 'node:fs'; import * as cu from " + json.dumps(MODULE.as_uri())
                  + "; const x=JSON.parse(readFileSync(0,'utf8')); " + ("await cu.loadShellParser(); " if parser else "")
                  + "process.stdout.write(JSON.stringify(await (" + expression + ")));")
        p = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(value),
                           text=True, capture_output=True, check=False, env=env)
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

    @NEEDS_PARSER
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

    def test_m4_r1_limit_a_heredoc_after_a_construct_that_runs_over_lines_is_a_possible_fetch(self):
        # Pinned limit: the reader of an operator is read from its own line, so a command that begins on an earlier line (inside a
        # quote or "$( )" that runs over lines) leaves its heredoc without one. Real shells run curl once for each command.
        for command, name, _, key, m4 in self.carrier_m4(R1_MULTILINE):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
                self.assertEqual(m4["status"], "incomplete")

    @NEEDS_PARSER
    def test_cli_lanes_read_the_heredoc_a_shell_reads_after_a_closed_double_quoted_substitution(self):
        got = self.lanes_of(["FOO=\"$(pwd)\" bash <<'EOF'\nqmd search x\nEOF"])
        self.assertEqual((got[0][0]["lanes"].get("qmd") or {}).get("calls"), 1)

    def test_m4_unquoted_heredoc_body_a_shell_reads_is_expanded_by_the_outer_shell_first(self):
        # D7 for a heredoc: the substitutions of an unquoted-delimiter body run in the outer shell whatever its quotes say, and the
        # reader sees the expanded text (with its own escapes: an escaped $( ) is the reader's). A substitution both views could
        # see counts once, and a quoted delimiter expands nothing.
        for command, name, _, key, m4 in self.carrier_m4(HD_ONCE):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
                self.assertEqual(m4["status"], "measured")
        for command, name, _, key, m4 in self.carrier_m4(HD_TWICE):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 2)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        for command, name, _, key, m4 in self.carrier_m4(HD_DATA):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 1)
        commands = HD_ONCE + HD_TWICE + HD_DATA
        self.assertEqual(self.exports("x.map(cu.fetchKind)", commands),
                         ["fetch"] * (len(commands) - len(HD_DATA)) + [None] * len(HD_DATA))

    def test_m4_a_run_string_after_an_opening_backquote_is_run(self):
        # The run-string detector anchored at the text start, a blank, ; & | or ( but not at a backquote, so bash -c "curl u" inside
        # `...` read as double-quoted data: the fetch was lost, and the raw detector (which anchors curl itself, not the quote) did not
        # count a possible fetch either.
        for command, name, _, key, m4 in self.carrier_m4(BQ_ONCE):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        for command, name, _, key, m4 in self.carrier_m4(BQ_DATA):
            with self.subTest(command=command, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["remote_fetches"], 0)
        commands = BQ_ONCE + BQ_DATA
        self.assertEqual(self.exports("x.map(cu.fetchKind)", commands), ["fetch"] * len(BQ_ONCE) + [None] * len(BQ_DATA))

    def test_m4_a_run_keyword_beyond_the_tail_window_is_unclassifiable_not_lost(self):
        # D8 work budget: scanQuotes reads the last 512 characters of the text built so far (never the whole rope, which made a long
        # script quadratic). The brief's fallback for input past a budget is "marks the command unclassifiable for M4", not a silent
        # miss: an ssh option word (`-oProxyCommand=...`) long enough to push `ssh` out of the window, in a text past 1,024
        # characters, counts one unclassifiable operation instead of reading its "curl u" as data with no mention at all.
        def command(n, after=""):
            return "ssh -oProxyCommand=" + "y" * n + " host \"curl https://example.org\"" + after
        for n in (100, 400, 700):  # inside the window, or before the text has grown past 1,024 characters: read as before
            for _, name, _, key, m4 in self.carrier_m4([command(n)]):
                with self.subTest(option=n, carrier=name):
                    self.assertEqual(m4[key], 1)
                    self.assertEqual(m4["unclassifiable"], 0)
        for _, name, _, key, m4 in self.carrier_m4([command(1500)]):
            with self.subTest(option=1500, carrier=name):
                self.assertEqual(m4[key], 0)
                self.assertEqual(m4["unclassifiable"], 1)
                self.assertEqual(m4["remote_fetches"], 1)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)
        # Counted once for the command, and only for the command that held the keyword: a later command is read on its own.
        for _, name, _, key, m4 in self.carrier_m4([command(1500, "; echo \"hi\"; echo \"there\"")]):
            with self.subTest(option="1500 then more commands", carrier=name):
                self.assertEqual(m4["unclassifiable"], 1)
        # A long command with no run keyword in it is no miss, however many quotes it holds.
        for _, name, _, key, m4 in self.carrier_m4(["printf '%s' " + "a " * 1500 + "\"x\" 'y'; echo \"z\""]):
            with self.subTest(command="long printf", carrier=name):
                self.assertEqual(m4["unclassifiable"], 0)
                self.assertEqual(m4["fetch_mentions_unconfirmed"], 0)

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

    @NEEDS_PARSER
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

    @NEEDS_PARSER
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

    @NEEDS_PARSER
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

    @NEEDS_PARSER
    def test_cli_lanes_mcporter_calls_count_for_the_downstream_server(self):
        # openclaw/mcporter@93e0916c (v0.14.1): global flags (cli-factory.ts:19), command inference
        # (command-inference.ts:10-95), call parsing (call-arguments.ts:79-233), target resolution (call-command.ts:114-173,
        # 309-348). An HTTP selector or ad-hoc stdio command has no config name: it reads (http) or (stdio), never a host. U1 pivot
        # D5: only the stack's own servers (manifests/stack.json:280, :407, :629, :966 and the coordinator's closed set) are emitted
        # by name; any other server reads (other), so `linear` below is (other) while the same selector forms name `socraticode`.
        cases = {"mcporter call linear.create_comment --issue-id X": "(other)",
                 "mcporter call 'linear.create_comment(issueId: \"LNR-123\", body: \"Hi\")'": "(other)",
                 "mcporter 'context7.resolve-library-id(\"React hooks docs\", \"react\")'": "(other)",
                 "mcporter call --server linear --tool create_comment": "(other)",
                 "mcporter call linear create_comment": "(other)",
                 "mcporter call create_comment server=linear": "(other)",
                 # The first positional is the selector even with '=' (call-arguments.ts:170-172), so this names a
                 # server "server=linear", which is not name-shaped.
                 "mcporter call server=linear tool=create_comment": "(other)",
                 "npx mcporter call https://mcp.context7.com/mcp.resolve-library-id": "(http)",
                 "mcporter call \"npx -y chrome-devtools-mcp@latest\" list_pages": "(stdio)",
                 "mcporter --config c.json --log-level debug call x.y --timeout 5000 --output json -- --literal": "(other)",
                 # the same selector forms with a server of the stack read by name
                 "mcporter call socraticode.create_comment --issue-id X": "socraticode",
                 "mcporter call 'socraticode.create_comment(issueId: \"LNR-123\", body: \"Hi\")'": "socraticode",
                 "mcporter 'socraticode.resolve(\"React hooks docs\", \"react\")'": "socraticode",
                 "mcporter call --server socraticode --tool create_comment": "socraticode",
                 "mcporter call socraticode create_comment": "socraticode",
                 "mcporter call create_comment server=socraticode": "socraticode",
                 "mcporter --config c.json --log-level debug call socraticode.y --timeout 5000 --output json -- --literal": "socraticode"}
        for (command, server), (cli, _) in zip(cases.items(), self.lanes_of(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli, {**EMPTY_CLI, "mcporter_downstream": {server: downstream_row(succeeded=1)}})
                self.assertNotIn("context7.com", json.dumps(cli))

    @NEEDS_PARSER
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

    @NEEDS_PARSER
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

    @NEEDS_PARSER
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

    @NEEDS_PARSER
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

    # ---- U1 pivot D11: the findings of the two reviews of the scanner-based reading (3cb7c4f6) that concern command position. Inputs of the
    # GPT-6 review are verbatim (a `\n` there is a real newline). Every expected value below is what real bash 5.2 (and dash where the
    # syntax is POSIX) does with the same text under stub executables: tests/test_command_position_oracle.py runs these inputs against them.
    def tally(self, commands, **kwargs):
        """[({lane: calls}, measurement.proxy, cli_lanes)] of each command as one successful call."""
        return [(lane_calls(cli), proxy, cli) for cli, proxy in self.lanes_of(commands, **kwargs)]

    @NEEDS_PARSER
    def test_a_shell_string_is_a_script_only_where_a_shell_reads_it(self):
        # GPT-6 #1. bash(1) OPTIONS and ARGUMENTS: the script of -c is the first operand after the options (an option may follow -c);
        # everything after it is $0 and the positional parameters; -n and -D read without running; `--` and `-` end the options,
        # so a -c after them names a file; a shell string an echo prints is data.
        cases = {"echo bash -c 'qmd search x'": {}, "bash -c ':' qmd search x": {}, "bash -n -c 'qmd search x'": {},
                 "bash -nc 'qmd search x'": {}, "bash -cn 'qmd search x'": {}, "bash -D -c 'qmd search x'": {}, "sh -n -c 'qmd search x'": {},
                 "bash -- -c 'qmd search x'": {}, "bash - -c 'qmd search x'": {},
                 "bash -ec 'qmd search x'": {"qmd": 1}, "bash -c -e 'qmd search x'": {"qmd": 1}, "bash -o pipefail -c 'qmd search x'": {"qmd": 1},
                 "bash -O extglob -c 'qmd search x'": {"qmd": 1}, "bash +e -c 'qmd search x'": {"qmd": 1},
                 "bash --norc -c 'qmd search x'": {"qmd": 1}, "bash --rcfile /dev/null -c 'qmd search x'": {"qmd": 1},
                 "bash -c 'qmd status \"$0\"' toon": {"qmd": 1}, "sh -c 'qmd search x'": {"qmd": 1}, "dash -c 'qmd search x'": {"qmd": 1},
                 # a string with an expansion is still a script: the shell that expands it runs the substitution and reads the rest
                 'bash -c "qmd get $HOME"': {"qmd": 1}, 'bash -c "cd $(pwd) && qmd get x"': {"qmd": 1}, 'bash -c "qmd get \\$HOME"': {"qmd": 1}}
        for (command, want), (lanes, _, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)

    @NEEDS_PARSER
    def test_array_elements_are_words_not_commands(self):
        # GPT-6 #2 (verbatim `a=( qmd )`): an array assignment runs nothing, but a substitution inside it does.
        cases = {"a=( qmd )": {}, "tools=(qmd toon)": {}, "declare -a x=(qmd toon)": {}, "a=( $(qmd list) )": {"qmd": 1}}
        for (command, want), (lanes, _, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)

    @NEEDS_PARSER
    def test_double_quotes_keep_a_backslash_unless_it_precedes_a_special_character(self):
        # GPT-6 #3. bash(1) QUOTING: inside double quotes a backslash keeps its meaning except before $, `, ", \ or newline, so
        # "--he\lp" is not --help, "q\md" is not qmd and "pro\xy" is not proxy; unquoted, a backslash quotes the next character (q\md is qmd).
        cases = {'qmd "--he\\lp"': ({"qmd": 1}, {}), 'qmd "--help"': ({}, {"qmd": 1}), '"q\\md" status': ({}, {}), "q\\md status": ({"qmd": 1}, {}),
                 '"qmd" status': ({"qmd": 1}, {}), 'q""md status': ({"qmd": 1}, {}), 'rtk "pro\\xy" echo ok': ({}, {}),
                 'rtk "proxy" qmd status': ({"rtk_proxy": 1, "qmd": 1}, {})}
        for (command, (lanes, excluded)), (got, proxy, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(got, lanes)
                self.assertEqual(cli["excluded_version_help"], excluded)
                self.assertEqual(proxy["calls"], int("rtk_proxy" in lanes))

    @NEEDS_PARSER
    def test_any_word_is_a_heredoc_delimiter(self):
        # GPT-6 #4 (verbatim). bash(1) Here Documents: the delimiter is any word (a hyphen or digits included); the body of a heredoc
        # that a non-shell reads is data, and one a shell reads is its script.
        cases = {"cat <<'END-JSON'\nrtk proxy qmd status\nEND-JSON": {}, "cat <<123\nqmd status\n123": {},
                 "bash <<'END-X'\nqmd status\nEND-X": {"qmd": 1}, "bash <<123\nqmd status\n123": {"qmd": 1},
                 "bash <<-EOF\n\tqmd status\n\tEOF": {"qmd": 1}, "cat <<\\EOF\n$(qmd a)\nEOF": {}, 'cat <<"EOF"\n$(qmd a)\nEOF': {},
                 "cat <<EOF\n$(qmd a)\nEOF": {"qmd": 1}, "cat <<EOF\nx \\$(qmd a)\nEOF": {}}
        for (command, want), (lanes, proxy, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)
                self.assertEqual(proxy["calls"], 0)

    @NEEDS_PARSER
    def test_the_shell_that_reads_a_heredoc_is_found_through_wrappers_and_lists(self):
        # GPT-6 #5 (verbatim first two). The heredoc is the standard input of the command it follows: past env, timeout, nice, nohup,
        # stdbuf and rtk proxy (rtk-ai/rtk@1d87b8e7 src/main.rs:3060-3066 spawns the child without touching its stdin), the last
        # command of a list, pipeline or negation. A file operand (unless -s) or -c gives the shell its script elsewhere, and a
        # descriptor other than 0 is not standard input.
        body = "\nqmd status\nEOF"
        cases = {"env -u UNUSED bash <<'EOF'" + body: {"qmd": 1}, "timeout -k 1 5 bash <<'EOF'" + body: {"qmd": 1},
                 "nice -n 5 bash <<'EOF'" + body: {"qmd": 1}, "nohup bash <<'EOF'" + body: {"qmd": 1}, "stdbuf -oL bash <<'EOF'" + body: {"qmd": 1},
                 "rtk proxy bash <<'EOF'" + body: {"rtk_proxy": 1, "qmd": 1},
                 "true && bash <<'EOF'" + body: {"qmd": 1}, "echo x | bash <<'EOF'" + body: {"qmd": 1}, "! bash <<'EOF'" + body: {"qmd": 1},
                 "bash -s <<'EOF'" + body: {"qmd": 1}, "bash - <<'EOF'" + body: {"qmd": 1}, "bash -s /dev/null <<'EOF'" + body: {"qmd": 1},
                 "bash /dev/null <<'EOF'" + body: {}, "bash -c 'cat' <<'EOF'" + body: {}, "bash 3<<'EOF'" + body: {},
                 "bash > /dev/null <<'EOF'" + body: {"qmd": 1}, "bash <<'EOF' > /dev/null" + body: {"qmd": 1},
                 "bash <<'EOF' && toon after" + body: {"qmd": 1, "toon": 1}, "bash <<< 'qmd status'": {"qmd": 1}, "cat <<< 'qmd status'": {},
                 "bash -c 'cat' <<< 'qmd status'": {}}
        for (command, want), (lanes, _, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)

    @NEEDS_PARSER
    def test_a_substitution_inside_an_arithmetic_expansion_runs(self):
        # GPT-6 #6 (verbatim `echo $(( $(qmd count) + 1 ))`): bash runs the substitution before it evaluates the expression.
        cases = {"echo $(( $(qmd count) + 1 ))": {"qmd": 1}, 'echo "$(( $(qmd count) + 1 ))"': {"qmd": 1},
                 "x=$(( $(qmd a) + $(toon b) ))": {"qmd": 1, "toon": 1}, "echo $(( 1 + 2 ))": {}}
        for (command, want), (lanes, _, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)

    @NEEDS_PARSER
    def test_rtk_proxy_runs_its_argument_without_a_shell(self):
        # GPT-6 #7 (verbatim `rtk proxy command qmd status`): rtk resolves the program on PATH and spawns it (src/main.rs:3060-3066,
        # src/core/utils.rs:615-632): `command` and `exec` are shell builtins, so nothing runs after them (installed rtk 0.50.0:
        # `rtk proxy command true` fails with "Failed to execute command"). env is an executable, so it runs its utility.
        cases = {"rtk proxy command qmd status": {"rtk_proxy": 1}, "rtk proxy exec qmd status": {"rtk_proxy": 1},
                 "rtk proxy env qmd status": {"rtk_proxy": 1, "qmd": 1}, "rtk proxy qmd status": {"rtk_proxy": 1, "qmd": 1},
                 "rtk proxy 'qmd status'": {"rtk_proxy": 1, "qmd": 1}, "rtk proxy bash -c 'qmd status'": {"rtk_proxy": 1, "qmd": 1},
                 "rtk --ultra-compact proxy qmd status": {"rtk_proxy": 1, "qmd": 1}, "rtk proxy": {"rtk_proxy": 1}}
        for (command, want), (lanes, proxy, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)
                self.assertEqual(proxy["calls"], 1)

    @NEEDS_PARSER
    def test_a_proxied_program_named_by_an_expansion_is_unresolved(self):
        # Claude review R5: rtk splits one argument only after the shell has expanded it, so `rtk proxy "$QMD search x"` runs a
        # program this reading cannot name: an unresolved program, never a lane.
        cases = {'rtk proxy "$QMD search x"': 1, 'rtk proxy "$(which qmd) search x"': 1, "rtk proxy '$QMD search x'": 0, "rtk proxy qmd search $X": 0}
        for (command, unresolved), (lanes, proxy, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(cli["unresolved_programs"], unresolved)
                self.assertEqual(proxy["calls"], 1)
                if unresolved:
                    self.assertNotIn("qmd", lanes)

    @NEEDS_PARSER
    def test_function_bodies_are_commands_and_parentheses_outside_command_position_are_not(self):
        # Claude review R4: a function body counts where it is defined (documented), whatever the header syntax; a function name, an
        # array, a case pattern and the regular expression of [[ =~ ]] are words.
        cases = {"function f { qmd get a; }": {"qmd": 1}, "f() ( qmd get a )": {"qmd": 1}, "f() { qmd get a; }": {"qmd": 1},
                 "qmd() { :; }": {}, "[[ $t =~ ^(qmd|toon)$ ]]": {}, "case x in qmd) : ;; toon|repomix) : ;; esac": {},
                 "case x in x) qmd get a ;; esac": {"qmd": 1}, "if qmd status; then toon a; fi": {"qmd": 1, "toon": 1},
                 "while qmd status; do :; done": {"qmd": 1}, "for f in qmd toon; do echo $f; done": {}}
        for (command, want), (lanes, _, _) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)

    @NEEDS_PARSER
    def test_parse_errors_are_counted_by_call_and_the_valid_parts_still_count(self):
        # U1 pivot D2: a tree with an error still yields the invocations of its valid parts; the error is counted once per call (not
        # per node), and nodes under an ERROR node are skipped.
        cases = {"qmd get a; echo \"unterminated": ({"qmd": 1}, 1), "qmd get a; ; toon b": ({"qmd": 1, "toon": 1}, 1),
                 "if then fi; qmd get": ({}, 1), "qmd get a": ({"qmd": 1}, 0), "qmd get a; ; ; toon b": ({"qmd": 1, "toon": 1}, 1)}
        for (command, (lanes, errors)), (got, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(got, lanes)
                self.assertEqual(cli["parse_errors"], errors)

    @NEEDS_PARSER
    def test_a_command_the_grammar_joined_to_the_previous_one_is_read_on_its_own(self):
        # tree-sitter-bash 0.25.1 reads what follows a command as more of its arguments after an unquoted `==` or `=~` (an ERROR on the
        # `;`, `&&` or `|`, or none at all after a newline) and after a redirection that follows a here-document operator (an ERROR on
        # the `|` or `;`). Measured on this host's real commands: 732 of 136,361 with no error, 163 more with one. A separator ERROR
        # or an unescaped newline inside one command's words is a boundary (bash(1) SHELL GRAMMAR), so the words after it are read as a
        # command of their own; parse_errors still counts the calls whose tree has an ERROR. The inputs are the recovery probes of the
        # oracle, whose expected lanes are what real bash ran.
        cases = {"echo ==; qmd get a": ({"qmd": 1}, 1), "echo ==\nqmd get a": ({"qmd": 1}, 0), "echo == | toon f": ({"toon": 1}, 1),
                 "echo == && qmd get a": ({"qmd": 1}, 1), "echo =~; qmd get a": ({"qmd": 1}, 1), "echo ==; qmd a; toon b": ({"qmd": 1, "toon": 1}, 1),
                 "cat <<'EOF' 2>&1 | qmd index x\nbody\nEOF": ({"qmd": 1}, 1), "cat <<'EOF' > out; qmd get a\nbody\nEOF": ({"qmd": 1}, 1),
                 "bash <<'EOF' 2>&1 | qmd index x\nqmd status\nEOF": ({"qmd": 1}, 1),
                 'echo "$M" | tr " " "\\n" | grep -c . \nstart=$(date +%s)\nTMPDIR=/x rtk proxy python3 -m unittest $M > run.txt 2>&1\nrc=$?':
                 ({"rtk_proxy": 1}, 0),
                 # a line that begins with a backslash reaches the grammar as a word that starts with the newline, and as the first line of a
                 # heredoc body it leaves the body node without that line
                 "{ timeout 5 repomix\n\\markitdown --flag; }": ({"repomix": 1, "markitdown": 1}, 0), "cd /x; toon f\n\\qmd get a": ({"toon": 1, "qmd": 1}, 0),
                 "! timeout -k 1 5 bash <<'END-2'\n\\markitdown a.json\nEND-2\n:": ({"markitdown": 1}, 0),
                 "bash <<'E'\n\\qmd status\nrtk proxy toon f\nE": ({"qmd": 1, "rtk_proxy": 1, "toon": 1}, 0),
                 "for i in a; do bash <<< 'nice -n 5 codebase-memory-mcp'\n\\markitdown search; done": ({"codebase-memory-mcp": 1, "markitdown": 1}, 0),
                 # an escaped $ inside backquotes starts a substitution (POSIX.1-2024 XCU 2.6.3); the grammar reads it as an ERROR and the kernel
                 # reads the unescaped body
                 "echo `echo \\$(qmd a)`": ({"qmd": 1}, 1),
                 # an ordinary continuation and a comment are not boundaries
                 "qmd get a \\\n  b": ({"qmd": 1}, 0), "qmd get a # toon b\n": ({"qmd": 1}, 0)}
        for (command, (lanes, errors)), (got, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(got, lanes)
                self.assertEqual(cli["parse_errors"], errors)

    @NEEDS_PARSER
    def test_the_classes_the_oracle_found_read_as_real_bash_runs_them(self):
        # U1 pivot, stage c: four classes the oracle generators (tests/test_command_position_oracle.py, seeds beyond the committed ones)
        # found against the AST reading, each measured on this host's real commands before it was fixed (136,361 distinct commands, count-only:
        # a command named `!` 0; a backquoted body with a backslash before $, ` or \ 0; words folded into a redirection 500, one of them
        # naming a lane; `time` before an assignment or `!` 12). Every expected value is the run of real bash 5.2 under stub executables
        # (the same inputs are probes of the oracle); (lanes by call, excluded --version/--help by lane).
        cases = {
            # 1. `!` is a reserved word wherever a pipeline may begin, twice in bash (bash(1) SHELL GRAMMAR); the grammar reads the second as a
            # command name, also after a line it joined to an array assignment. A quoted or escaped `!` is a program name.
            "! ! qmd status": ({"qmd": 1}, {}), "! ! ! qmd status": ({"qmd": 1}, {}), "'!' qmd status": ({}, {}), "\\! qmd status": ({}, {}),
            "! ! A=1 qmd status": ({"qmd": 1}, {}), "! A=1 qmd status": ({"qmd": 1}, {}), "! ! A=$(toon x) qmd": ({"toon": 1, "qmd": 1}, {}),
            "nohup markitdown | bash -n -c 'qmd x' | a=( $(nice -n 5 markitdown) )\n! rtk proxy 'markitdown v1' || :": ({"markitdown": 1, "rtk_proxy": 1}, {}),
            "time ! qmd status || :": ({"qmd": 1}, {}), "time -p ! qmd status || :": ({"qmd": 1}, {}), "! time qmd status || :": ({"qmd": 1}, {}),
            # 2. A backquoted body is unescaped before it is parsed (POSIX.1-2024 XCU 2.6.3): \` nests a substitution, \$ starts one, \\ is data.
            "echo `echo \\`qmd a\\``": ({"qmd": 1}, {}), 'echo "`echo \\`qmd a\\``"': ({"qmd": 1}, {}),
            "echo `echo \\`echo \\\\\\`qmd a\\\\\\`\\``": ({"qmd": 1}, {}),
            "echo `echo \\\\; qmd b`": ({}, {}), "echo `echo \\a; qmd b`": ({"qmd": 1}, {}), "echo `qmd a`": ({"qmd": 1}, {}),
            # 3. Every word after a redirection's target is an argument of the command (tree-sitter-bash reads them as more targets).
            "time 2>&1 toon": ({"toon": 1}, {}), "time >/dev/null toon get": ({"toon": 1}, {}), "nice 2>&1 qmd": ({"qmd": 1}, {}),
            "env A=1 >/dev/null qmd get": ({"qmd": 1}, {}), "env >/dev/null A=1 qmd get": ({"qmd": 1}, {}), "timeout 5 2>/dev/null qmd status": ({"qmd": 1}, {}),
            "nohup 2>&1 >/dev/null qmd a": ({"qmd": 1}, {}), "nice < /dev/null qmd status": ({"qmd": 1}, {}), "echo a | xargs 2>/dev/null qmd get": ({"qmd": 1}, {}),
            "rtk proxy 2>&1 qmd get": ({"rtk_proxy": 1, "qmd": 1}, {}), "sh 2>&1 -c 'qmd get'": ({"qmd": 1}, {}), "bash >/dev/null -c 'qmd get'": ({"qmd": 1}, {}),
            "qmd get > /dev/null --help": ({}, {"qmd": 1}), "time > /dev/null qmd --version": ({}, {"qmd": 1}),
            "time -p 2>&1 headroom | context-mode --help": ({"headroom": 1}, {"context-mode": 1}),
            "echo hi >/dev/null qmd get": ({}, {}), "echo a > /dev/null b; qmd get": ({"qmd": 1}, {}), "cat /dev/null > /dev/null qmd | toon x": ({"toon": 1}, {}),
            # 4. `time` is a reserved word, so an assignment may follow it (bash(1) SHELL GRAMMAR, Pipelines).
            "time A=1 qmd get": ({"qmd": 1}, {}), "time -p A=1 B=2 qmd get": ({"qmd": 1}, {}), "time A=$(toon x) qmd": ({"toon": 1, "qmd": 1}, {})}
        for (command, (lanes, excluded)), (got, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(got, lanes)
                self.assertEqual(cli["excluded_version_help"], excluded)
                self.assertEqual(cli["parse_errors"], 0)

    @NEEDS_PARSER
    def test_a_shell_builtin_after_a_real_wrapper_runs_nothing(self):
        # env, nice, nohup, stdbuf, timeout, xargs and sudo are executables, and the builtin exec replaces the shell with one: they run
        # their command with execvp, which finds no shell builtin (`env eval x`: "No such file or directory"), so a lane after such a
        # builtin is not run. `command` and `time` are the shell's own and pass a builtin on. Expected lanes are the runs of real bash
        # 5.2 under stub executables; the same inputs are probes of the oracle. After `rtk proxy` the same rule already held (GPT-6 7).
        cases = {"env eval 'qmd status'": {}, "env command qmd status": {}, "env exec qmd status": {}, "nohup eval qmd status": {},
                 "timeout 5 command qmd status": {}, "nice -n 5 exec qmd status": {}, "stdbuf -oL eval qmd status": {},
                 "echo a | xargs command qmd get": {}, "exec eval qmd status": {}, "env -u X timeout 5 nice eval qmd status": {},
                 "command eval 'qmd status'": {"qmd": 1}, "command command qmd status": {"qmd": 1}, "time eval 'qmd status'": {"qmd": 1},
                 "env bash -c 'eval qmd status'": {"qmd": 1}, "env timeout 5 nice qmd status": {"qmd": 1}, "env qmd status": {"qmd": 1},
                 "exec qmd status": {"qmd": 1}}
        for (command, want), (lanes, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)
                self.assertEqual(cli["parse_errors"], 0)

    @NEEDS_PARSER
    def test_a_word_the_grammar_cut_after_an_assignment_is_one_word(self):
        # tree-sitter-bash 0.25.1 cuts the value of an assignment at the second `$` of `a=$x/$y-$z` and reads the tail, glued to the
        # assignment with no blank, as the command's name (its arguments become the name's arguments), so `a=$x/$y-$z qmd get` lost the
        # lane and counted an unresolved program (93 of 136,361 real commands hold such a cut word, none with a lane word after it; count-only).
        # A name with no blank before it belongs to the assignment's word. Expected lanes are the runs of real bash 5.2 under stubs.
        cases = {"a=$HOME/$X-$Y qmd get": {"qmd": 1}, "a=$HOME/$X.$Y toon f.json": {"toon": 1}, "A=$HOME/$X-$Y rtk proxy toon f": {"rtk_proxy": 1, "toon": 1},
                 "A=1 B=$HOME/$X-$Y markitdown a.json": {"markitdown": 1}, "a=$HOME/$X-$Y": {}, "for i in a; do out=$HOME/$X-$Y; done": {},
                 "for i in a; do out=$HOME/$X-$Y; done; qmd get": {"qmd": 1}, "a=$HOME/$X-z qmd get": {"qmd": 1}, "a=$HOME/$Xz qmd get": {"qmd": 1},
                 # inside the command's own words two argument nodes with no blank between them are one word
                 "env A=$HOME/$X-$Y qmd get": {"qmd": 1}, "nohup env A=$HOME/$X-$Y toon f": {"toon": 1},
                 "rtk proxy env A=$HOME/$X.$Y qmd get": {"rtk_proxy": 1, "qmd": 1}, "echo x=$HOME/$X-$Y; qmd get": {"qmd": 1}}
        for (command, want), (lanes, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)
                self.assertEqual(cli["parse_errors"], 0)
                self.assertEqual(cli["unresolved_programs"], 0)

    @NEEDS_PARSER
    def test_a_cut_word_does_not_hide_an_exclusion_flag(self):
        # The word after a cut is still a word: `--help` after `--out=$x/$y-$z` excludes the call (the flags are the lane's own words).
        cases = {"qmd get --out=$HOME/$X-$Y --help": ({}, {"qmd": 1}), "qmd get --out=$HOME/$X-$Y": ({"qmd": 1}, {})}
        for (command, (lanes, excluded)), (got, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(got, lanes)
                self.assertEqual(cli["excluded_version_help"], excluded)

    @NEEDS_PARSER
    def test_a_heredoc_with_no_delimiter_line_is_closed_by_the_end_of_the_text(self):
        # bash runs a here-document whose delimiter line is missing, with a warning, and its body is everything after the operator's line;
        # tree-sitter-bash 0.25.1 puts that body in an ERROR and its words among the commands of the operator's line, or drops it when the
        # text ends with a newline. The kernel appends the missing delimiter line before it reads (none of 15,128 real commands with a
        # here-document lacks one; the oracle's fuzz inputs do). Expected lanes are the runs of real bash 5.2 under stub executables.
        cases = {"bash <<EOF\nqmd status": {"qmd": 1}, "bash <<'EOF'\nqmd status\nrtk proxy toon f": {"qmd": 1, "rtk_proxy": 1, "toon": 1},
                 "bash <<'EOF'\nqmd status\n": {"qmd": 1}, "bash <<-EOF\n\tqmd status": {"qmd": 1}, "cat <<EOF\nqmd status": {},
                 "cat <<EOF\n$(toon a)": {"toon": 1}, "cat <<'EOF'\n$(toon a)": {},
                 # the first body line reads as a second operator until the first heredoc is closed: one delimiter is appended at a time
                 "cat <<EOF\n<<-EOF\\$cat": {},
                 "bash <<EOF && toon x\nqmd status": {"qmd": 1, "toon": 1}, "env -u X bash <<'END-1'\nqmd status": {"qmd": 1}}
        for (command, want), (lanes, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(lanes, want)
                self.assertEqual(cli["parse_errors"], 0)
                self.assertEqual(cli["unresolved_programs"], 0)

    @NEEDS_PARSER
    def test_a_name_is_emitted_only_from_the_closed_vocabulary(self):
        # GPT-6 #10 and U1 pivot D5: a mcporter server key is one of the stack's own servers or (other), (http), (stdio) or
        # (unresolved); a string that only looks like a name (an id, a host) never reaches the output.
        vocabulary = ["codebase-memory", "context-mode", "jcodemunch", "serena", "socraticode", "qmd", "headroom", "ai-memory"]
        cases = {"mcporter call call_PRIVATE.search": "(other)", "mcporter call --server private-host tool": "(other)",
                 "mcporter call my-private-host.example.search": "(other)", "mcporter call linear.create_comment": "(other)",
                 "mcporter call --server 'toolu_01AbCdEf' tool": "(other)"}
        cases.update({"mcporter call %s.tool" % name: name for name in vocabulary})
        for (command, key), (_, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                self.assertEqual(sorted(cli["mcporter_downstream"]), [key])
                for text in ("call_PRIVATE", "private-host", "toolu_01AbCdEf"):
                    self.assertNotIn(text, json.dumps(cli))

    @NEEDS_PARSER
    def test_mcporter_reads_a_version_token_as_the_command_and_a_help_token_anywhere(self):
        # Claude review R6, checked against openclaw/mcporter@93e0916c (v0.14.1): runCli takes the first word after the global flags
        # as the command and answers isHelpToken (--help, -h, help) or isVersionToken (--version, -v, -V) only for it (src/cli.ts
        # 137-145); each command then calls consumeHelpTokens on its whole argument list, and consumeMatchingTokens (src/cli/flag-utils.ts
        # 34-41) neither stops at `--` nor looks at anything but the token, so --help anywhere prints help. A version token after
        # the command is an ordinary (unknown) call flag: a call.
        call = "mcporter call codebase-memory.search_graph"
        cases = {"mcporter --version": ("excluded", "mcporter"), "mcporter -V": ("excluded", "mcporter"), "mcporter -v": ("excluded", "mcporter"),
                 call + " --version": ("call", "codebase-memory"), call + " -V": ("call", "codebase-memory"),
                 call + " --help": ("excluded", "mcporter"), call + " -h": ("excluded", "mcporter"), call + " -- --help": ("excluded", "mcporter"),
                 "mcporter help": ("excluded", "mcporter"), "mcporter list --help": ("excluded", "mcporter")}
        for (command, (kind, name)), (_, _, cli) in zip(cases.items(), self.tally(list(cases))):
            with self.subTest(command=command):
                if kind == "excluded":
                    self.assertEqual((cli["excluded_version_help"], cli["mcporter_downstream"]), ({name: 1}, {}))
                else:
                    self.assertEqual((cli["excluded_version_help"], sorted(cli["mcporter_downstream"])), ({}, [name]))

    @NEEDS_PARSER
    def test_not_executed_calls_are_read_where_the_client_records_them(self):
        # Claude review R7, observed on this host's Claude Code transcripts (122,648 Bash results, count-only): the user's rejection
        # opens the result CONTENT ("The user doesn't want to proceed with this tool use", 25 rows, whose toolUseResult is
        # "User rejected tool use"), and every client denial (permission-rule 750, user-rejected 46, cancelled 1, automode-unavailable 1)
        # carries a row-level toolDenialKind. A host hook's own refusal text (209 rows opening "This agent is isolated") carries none
        # and is left as a failed call (open: its meaning is the hook's, not the client's). No result of the shapes below was an
        # interrupted run: toolUseResult.interrupted was false in all 25,506 object results, so that state is a synthetic fixture.
        def answer(content, **row):
            return {**result("a", content, True), **row}

        classifier = ("The server-side auto mode classifier gave no verdict (error), so auto mode cannot determine the safety of Bash. "
                      "This is a transient failure of the check, not a judgment about the action.")
        rejected = "The user doesn't want to proceed with this tool use. The tool use was rejected."
        cases = {"rejection in the content": (answer(rejected, toolUseResult="Error: something else"), {"failed": 1, "not_executed": 1}),
                 "toolDenialKind permission-rule": (answer("blocked by a rule", toolDenialKind="permission-rule", toolUseResult="Error: blocked"),
                                                    {"failed": 1, "not_executed": 1}),
                 "toolDenialKind user-rejected": (answer("no", toolDenialKind="user-rejected"), {"failed": 1, "not_executed": 1}),
                 "toolDenialKind cancelled": (answer("no", toolDenialKind="cancelled"), {"failed": 1, "not_executed": 1}),
                 "classifier without a verdict": (answer(classifier, toolDenialKind="automode-unavailable", toolUseResult="Error: " + classifier),
                                                  {"failed": 1, "not_executed": 1}),
                 "classifier text alone": (answer(classifier), {"failed": 1, "not_executed": 1}),
                 "host hook text": (answer("This agent is isolated in the worktree /w, but this command runs rtk with a git command",
                                           toolUseResult="Error: This agent is isolated in the worktree /w"), {"failed": 1}),
                 "a failed command": (answer("Exit code 1\nboom", toolUseResult="Error: Exit code 1\nboom"), {"failed": 1}),
                 "interrupted": ({**result("a", "partial"), "toolUseResult": {"stdout": "partial", "stderr": "", "interrupted": True}},
                                 {"interrupted": 1}),
                 "not interrupted": ({**result("a", "ok"), "toolUseResult": {"stdout": "ok", "stderr": "", "interrupted": False}}, {"succeeded": 1})}
        got = self.exports("x.map((rows) => cu.measureTranscript(rows).cli_lanes ?? null)",
                           [[call("a", "Bash", command="qmd search x"), row] for row, _ in cases.values()])
        counters = ["succeeded", "failed", "not_executed", "unfinished", "unknown", "background", "interrupted"]
        for (name, (_, want)), cli in zip(cases.items(), got):
            with self.subTest(state=name):
                row = (cli or {}).get("lanes", {}).get("qmd", {})
                self.assertEqual({k: row.get(k, 0) for k in counters}, {k: want.get(k, 0) for k in counters})

    @NEEDS_PARSER
    def test_call_state_reads_each_not_executed_template_in_both_fields_and_names_its_cause(self):
        """U2 item 7, the callState extension the review's dependency finding asks for: the config and cancelled templates (U1 reads them
        only through toolDenialKind), each template read at the start of the result content and of the toolUseResult string (after
        'Error: '), and the exported callState and notExecuted accessor. The cause is the first match of: a template's own cause unless it
        is 'other', the toolDenialKind (permission-rule config, user-rejected user, cancelled cancelled, anything else other), the
        template's 'other', and a native declined state. Hook denials carry toolDenialKind permission-rule on this host (817 of 817), so the
        text decides before the denial kind. Cases marked (control) already read not-executed at ebcca292; the others fail there."""
        def answer(content, error=True, **row):
            return {**result("a", content, error), **row}

        bash = call("a", "Bash", command="qmd search x")
        declined = call("a", "Bash", command="qmd search x")
        declined["message"]["content"][0]["native_status"] = "declined"
        native_declined = answer("exec command rejected by user")
        native_declined["message"]["content"][0]["native_state"] = "declined"
        cases = {  # name: (call row, result row or None, (state, not_executed, cause))
            "config: 'Permission to use' in the content, no denial kind": (
                bash, answer(PERMISSION_TO_USE, toolUseResult="Error: " + PERMISSION_TO_USE), ("failed", True, "config")),
            "config: 'Permission to use' only in the toolUseResult": (
                bash, answer("denied", toolUseResult="Error: " + PERMISSION_TO_USE), ("failed", True, "config")),
            "config: with its observed denial kind (control)": (
                bash, answer(PERMISSION_TO_USE, toolDenialKind="permission-rule", toolUseResult="Error: " + PERMISSION_TO_USE),
                ("failed", True, "config")),
            "cancelled: 'Not run: the response ...', no denial kind": (
                bash, answer(NOT_RUN, toolUseResult="Error: " + NOT_RUN), ("failed", True, "cancelled")),
            "cancelled: with its observed denial kind (control)": (
                bash, answer(NOT_RUN, toolDenialKind="cancelled", toolUseResult=NOT_RUN), ("failed", True, "cancelled")),
            "cancelled: the interrupt marker as a result (the design's constant, not observed as a result)": (
                bash, answer(INTERRUPT_MARKER), ("failed", True, "cancelled")),
            "cancelled: <tool_use_error>Cancelled (control)": (
                bash, answer("<tool_use_error>Cancelled: Claude ended the conversation</tool_use_error>"), ("failed", True, "cancelled")),
            "cancelled: <tool_use_error>Error: Streaming fallback (control)": (
                bash, answer("<tool_use_error>Error: Streaming fallback - tool execution discarded</tool_use_error>"),
                ("failed", True, "cancelled")),
            "invalid: another <tool_use_error> (control)": (
                bash, answer("<tool_use_error>InputValidationError: command: Required</tool_use_error>"), ("failed", True, "invalid")),
            "user: the rejection content with 'User rejected tool use' (control)": (
                bash, answer(USER_REJECTION, toolUseResult="User rejected tool use"), ("failed", True, "user")),
            "user: the rejection content with toolUseResult 'Error: ' + content (control)": (
                bash, answer(USER_REJECTION, toolUseResult="Error: " + USER_REJECTION), ("failed", True, "user")),
            "user: the rejection only in the toolUseResult": (
                bash, answer("no", toolUseResult="Error: " + USER_REJECTION), ("failed", True, "user")),
            "user: denial kind user-rejected with another text (control)": (
                bash, answer("Cannot call mcp__x__y while in plan mode.", toolDenialKind="user-rejected",
                             toolUseResult="Error: Cannot call mcp__x__y while in plan mode."), ("failed", True, "user")),
            "hook: the text decides over its observed denial kind permission-rule (control)": (
                bash, answer(HOOK_DENIAL, toolDenialKind="permission-rule", toolUseResult="Error: " + HOOK_DENIAL), ("failed", True, "hook")),
            "other: 'Permission for' in a toolUseResult 'Error: ' + text (control)": (
                bash, answer(PERMISSION_FOR, toolUseResult="Error: " + PERMISSION_FOR), ("failed", True, "other")),
            "other: 'Permission for' in a bare toolUseResult (control)": (
                bash, answer(PERMISSION_FOR, toolUseResult=PERMISSION_FOR), ("failed", True, "other")),
            "other: 'Permission for' only in the content": (bash, answer(PERMISSION_FOR), ("failed", True, "other")),
            "config: the denial kind permission-rule decides over the generic 'Permission for' text (control)": (
                bash, answer("Permission for this command was denied by a built-in rule.", toolDenialKind="permission-rule",
                             toolUseResult="Error: Permission for this command was denied by a built-in rule."), ("failed", True, "config")),
            "other: the classifier text with denial kind automode-unavailable (control)": (
                bash, answer(AUTOMODE_NO_VERDICT, toolDenialKind="automode-unavailable", toolUseResult="Error: " + AUTOMODE_NO_VERDICT),
                ("failed", True, "other")),
            "other: a denial kind this reading does not know (control)": (
                bash, answer("no", toolDenialKind="some-new-kind"), ("failed", True, "other")),
            "declined: a Codex call with no result (control)": (declined, None, ("failed", True, "declined")),
            "declined: a Codex result with native state declined (control)": (bash, native_declined, ("failed", True, "declined")),
            "failed: the command's own exit (control)": (
                bash, answer("Exit code 1\nboom", toolUseResult="Error: Exit code 1\nboom"), ("failed", False, None)),
            "failed: a host hook's own refusal text (control)": (
                bash, answer("This agent is isolated in the worktree /w", toolUseResult="Error: This agent is isolated in the worktree /w"),
                ("failed", False, None)),
            "succeeded: a template in a result that is not an error is data (control)": (
                bash, answer(PERMISSION_TO_USE, error=False), ("succeeded", False, None)),
            "unfinished: no result (control)": (bash, None, ("unfinished", False, None)),
        }
        rows = [[c, r] for c, r, _ in cases.values()]
        # The rows as cli_lanes reads them: qmd's not_executed counter, a value U1's rule already gives at ebcca292.
        lanes = self.exports("x.map(([c, r]) => (cu.measureTranscript(r ? [c, r] : [c]).cli_lanes?.lanes?.qmd ?? {}).not_executed ?? 0)", rows)
        for (name, (_, _, want)), not_executed in zip(cases.items(), lanes):
            with self.subTest(case=name, view="cli_lanes not_executed"):
                self.assertEqual(not_executed, int(want[1]))
        # The exported reading: callState(call, result) and notExecuted(call, result), with the result a tool_result block and its row.
        got = self.exports("x.map(([c, r]) => { const call = c.message.content[0], result = r ? { ...r.message.content[0], row: r } : null;"
                           " const s = cu.callState(call, result); return [s.state, s.not_executed === true, s.cause ?? null,"
                           " cu.notExecuted(call, result)] })", rows)
        for (name, (_, _, want)), state in zip(cases.items(), got):
            with self.subTest(case=name, view="callState"):
                self.assertEqual(tuple(state[:3]), want)
                self.assertEqual(state[3], want[1])  # the accessor is the flag
                self.assertEqual(state[2] is not None, want[1])  # a cause exactly when the call did not run

    @staticmethod
    def m14_rows(session=None, agent=None):
        """The M14 fixtures: U2 design 4.6 with the review's corrections (every not-executed fixture states is_error and its exact
        toolUseResult; a call that has a result is never 'no result') and the shapes of scans/call-states.json. Codex calls are
        bridge-normalized rows, which carry no sessionId or agentId. Returns (rows, {call number: (state, cause)})."""
        ident = {k: v for k, v in (("sessionId", session), ("agentId", agent)) if v}

        def c(n, name, **inputs):
            return {**call("toolu_m14_%02d" % n, name, **inputs), **ident}

        def r(n, content, error=True, **row):
            return {**result("toolu_m14_%02d" % n, content, error), **ident, **row}

        def codex(n, **fields):
            row = call("toolu_m14_%02d" % n, "Bash", command="qmd search x")
            row["message"]["content"][0].update(fields)
            return row

        unknown = result("toolu_m14_18", "Chunk ID: 1\nOutput:\nx")
        unknown["message"]["content"][0]["native_state"] = "unknown"
        marker = {"type": "user", "timestamp": "2026-09-26T01:00:02Z", **ident,
                  "message": {"role": "user", "content": [{"type": "text", "text": INTERRUPT_MARKER}]}}
        rows = [
            c(1, "Bash", command="ls"), r(1, "a\nb", False),
            c(2, "Bash", command="false"), r(2, "Exit code 1", toolUseResult="Error: Exit code 1"),
            c(3, "Bash", command="rm -rf build"), r(3, HOOK_DENIAL, toolDenialKind="permission-rule", toolUseResult="Error: " + HOOK_DENIAL),
            c(4, "Bash", command="rm -rf build"), r(4, PERMISSION_TO_USE, toolUseResult="Error: " + PERMISSION_TO_USE),
            c(5, "Edit", file_path="a.py"), r(5, USER_REJECTION, toolDenialKind="user-rejected", toolUseResult="User rejected tool use"),
            c(6, "Edit", file_path="a.py"), r(6, USER_REJECTION, toolUseResult="Error: " + USER_REJECTION),
            c(7, "Read"), r(7, "<tool_use_error>InputValidationError: Read failed due to the following issue:\n"
                               "The required parameter `file_path` is missing</tool_use_error>",
                            toolUseResult="InputValidationError: [file_path: Required]"),
            c(8, "mcp__qmd__search", query="x"), r(8, "<tool_use_error>Error: No such tool available: mcp__qmd__search</tool_use_error>",
                                                  toolUseResult="Error: No such tool available: mcp__qmd__search"),
            c(9, "Bash", command="sleep 1"), r(9, "<tool_use_error>Cancelled: Claude ended the conversation</tool_use_error>",
                                               toolUseResult="Cancelled: Claude ended the conversation"),
            c(10, "Grep", pattern="x"),
            c(11, "Bash", command="sleep 60", run_in_background=True),
            r(11, "Command running in background with ID: bg1", False, toolUseResult={"backgroundTaskId": "bg1"}),
            c(12, "mcp__plugin_context-mode_context-mode__ctx_execute", language="shell", code="ls"),
            r(12, USER_REJECTION, toolDenialKind="user-rejected", toolUseResult="User rejected tool use"),
            codex(13, native_status="declined"),
            c(14, "Bash", command="make"), r(14, USER_REJECTION, toolDenialKind="user-rejected", toolUseResult="User rejected tool use"), marker,
            c(15, "Bash", command="make"), r(15, NOT_RUN, toolUseResult="Error: " + NOT_RUN),
            c(16, "Bash", command="make"), r(16, INTERRUPT_MARKER),
            c(17, "Bash", command="make"), r(17, "partial", False, toolUseResult={"stdout": "partial", "stderr": "", "interrupted": True}),
            codex(18), unknown,
            c(19, "Bash", command="make"),
            r(19, AUTOMODE_NO_VERDICT, toolDenialKind="automode-unavailable", toolUseResult="Error: " + AUTOMODE_NO_VERDICT),
            codex(20, native_status="completed", sandbox=True),
        ]
        want = {1: ("succeeded", None), 2: ("failed", None), 3: ("rejected", "hook"), 4: ("rejected", "config"), 5: ("rejected", "user"),
                6: ("rejected", "user"), 7: ("invalid", "invalid"), 8: ("invalid", "invalid"), 9: ("cancelled_with_result", "cancelled"),
                10: ("cancelled_or_unfinished", None), 11: ("succeeded", None), 12: ("rejected", "user"), 13: ("rejected", "declined"),
                14: ("rejected", "user"), 15: ("cancelled_with_result", "cancelled"), 16: ("cancelled_with_result", "cancelled"),
                17: ("interrupted", None), 18: ("unknown", None), 19: ("rejected", "other"), 20: ("succeeded", None)}
        return rows, want

    M14_SERVER_KEYS = ("attempted", "executed", "succeeded", "failed", "interrupted", "rejected", "invalid", "cancelled_with_result",
                       "cancelled_or_unfinished", "unknown")

    def m14_server_row(self, **counts):
        return {**dict.fromkeys(self.M14_SERVER_KEYS, 0), **counts}

    def assert_m14_invariants(self, states):
        """attempted = executed + rejected + invalid + cancelled_with_result + cancelled_or_unfinished + unknown, per actor and per server;
        executed = succeeded + failed + interrupted; the rejection sources add up to rejected."""
        for label, row in [("actor", states), *states["by_server"].items()]:
            with self.subTest(invariant=label):
                self.assertEqual(row["attempted"], row["executed"] + row["rejected"] + row["invalid"] + row["cancelled_with_result"]
                                 + row["cancelled_or_unfinished"] + row["unknown"])
                self.assertEqual(row["executed"], row["succeeded"] + row["failed"] + row["interrupted"])
        self.assertEqual(sum(states["rejected_by_source"].values()), states["rejected"])

    def test_m14_call_states_one_vocabulary(self):
        """PR-A item 7 (U2 design 4.2-4.7 with the review's corrections). call_states projects U1's callState onto the sealed M14 names
        (E2E README.md M14 row; preregistration.json thresholds.M14.criteria.states): a call that has a transcript result is executed
        (succeeded, failed or interrupted), rejected (by source, in the OTel tool_decision vocabulary), invalid or cancelled_with_result,
        never 'no result'; cancelled_or_unfinished is the sealed state, the calls with no result. decided is null: transcripts cannot
        observe the Loki tool_decision event. mcp_states keeps its #432 reading, and calls_without_result its published meaning: the
        calls with no result, the cancelled_or_unfinished ones plus the ones a native status decided (call 13 here)."""
        rows, want = self.m14_rows()
        got = self.measure(rows)
        self.assertEqual(got.get("call_states"), {
            "attempted": 20, "decided": None, "executed": 5, "succeeded": 3, "failed": 1, "interrupted": 1, "rejected": 8,
            "rejected_by_source": {"config": 1, "hook": 1, "user": 4, "other": 1, "declined": 1}, "invalid": 2, "cancelled_with_result": 3,
            "cancelled_or_unfinished": 1, "unknown": 1, "background": 1, "sandbox": 1,
            "by_server": {"qmd": self.m14_server_row(attempted=1, invalid=1),
                          "plugin_context-mode_context-mode": self.m14_server_row(attempted=1, rejected=1)}})
        self.assert_m14_invariants(got["call_states"])
        # The #432 legacy view, unchanged (a result's is_error, else the native status); it counts the same attempts per server.
        self.assertEqual(got["mcp_states"], {"qmd": {"attempted": 1, "succeeded": 0, "failed": 1, "unfinished": 0},
                                             "plugin_context-mode_context-mode": {"attempted": 1, "succeeded": 0, "failed": 1, "unfinished": 0}})
        for server, row in got["mcp_states"].items():
            self.assertEqual(row["attempted"], got["call_states"]["by_server"][server]["attempted"])
        # calls_without_result: calls 10 (no status: cancelled_or_unfinished) and 13 (declined, a native status decided it); 20 is nested.
        self.assertEqual(got["calls_without_result"], 2)
        # The per-call projection, exported for the ledger and its consumers.
        states = self.exports("x.map((rows) => { const call = rows[0].message.content[0], r = rows[1] && rows[1].message.content.find("
                              "(b) => b.type === 'tool_result'); const m = cu.m14State(call, r ? { ...r, row: rows[1] } : null);"
                              " return [m.state, m.cause, m.executed] })",
                              [[rows[i], rows[i + 1] if i + 1 < len(rows) and rows[i + 1]["type"] == "user"
                                and rows[i + 1]["message"]["content"][0].get("type") == "tool_result" else None]
                               for i in range(len(rows)) if rows[i]["type"] == "assistant"])
        executed = {"succeeded", "failed", "interrupted"}
        for n, state in zip(sorted(want), states):
            with self.subTest(call=n):
                self.assertEqual(tuple(state), (*want[n], want[n][0] in executed))

    def test_m14_call_states_aggregate_and_window(self):
        """aggregateMeasurements sums call_states and by_server (decided stays null); a call counts in the window of its tool_use row."""
        rows, _ = self.m14_rows()
        agg = self.exports("(() => { const a = cu.measureTranscript(x.rows), b = cu.measureTranscript(x.rows); "
                           "return cu.aggregateMeasurements([a, b]).call_states })()", {"rows": rows})
        self.assertEqual((agg["attempted"], agg["decided"], agg["rejected"], agg["rejected_by_source"]["user"], agg["background"]),
                         (40, None, 16, 8, 2))
        self.assertEqual(agg["by_server"]["qmd"], self.m14_server_row(attempted=2, invalid=2))
        self.assert_m14_invariants(agg)
        empty = self.exports("cu.aggregateMeasurements([]).call_states", {})
        self.assertEqual((empty["attempted"], empty["decided"], empty["by_server"]), (0, None, {}))
        early = [{**r, "timestamp": "2026-09-26T00:00:00Z"} if r.get("type") == "assistant" and "toolu_m14_01" in json.dumps(r) else r
                 for r in rows]
        windowed = self.exports("cu.measureTranscript(x.rows, { window: { since: Date.parse('2026-09-26T00:30:00Z'), until: Infinity } })"
                                ".call_states", {"rows": early})
        self.assertEqual((windowed["attempted"], windowed["succeeded"]), (19, 2))

    def test_call_ledger_records_every_attempted_call_privately(self):
        """AA:319, the per-child list of tool_use_ids with each call's state (scope item 7), keyed by (session_id, tool_use_id) as the M14
        row requires. session_id and owner come from the call's row: owner is its agentId, 'main' for a row with a sessionId and no
        agentId, and null for a row with neither (a Codex bridge row: U3 supplies conversation.id and the owner kind)."""
        rows, want = self.m14_rows(session="sess-fixture-1", agent="agent-fixture-1")
        ledger = self.exports("cu.callLedger(x.rows)", {"rows": rows})
        self.assertEqual(len(ledger), 20)
        by_id = {r["tool_use_id"]: r for r in ledger}
        for n, (state, cause) in want.items():
            with self.subTest(call=n):
                record = by_id["toolu_m14_%02d" % n]
                self.assertEqual((record["state"], record["cause"]), (state, cause))
                codex = n in (13, 18, 20)
                self.assertEqual((record["session_id"], record["owner"]),
                                 (None, None) if codex else ("sess-fixture-1", "agent-fixture-1"))
        self.assertEqual(sorted(by_id["toolu_m14_12"]), ["background", "cause", "code_mode", "m15_class", "native_status", "owner",
                                                          "sandbox", "server", "session_id", "state", "tool", "tool_use_id"])
        self.assertEqual((by_id["toolu_m14_12"]["server"], by_id["toolu_m14_12"]["tool"], by_id["toolu_m14_12"]["m15_class"]),
                         ("plugin_context-mode_context-mode", "mcp__plugin_context-mode_context-mode__ctx_execute", "rejected"))
        self.assertEqual((by_id["toolu_m14_13"]["native_status"], by_id["toolu_m14_20"]["sandbox"], by_id["toolu_m14_11"]["background"]),
                         ("declined", True, True))
        self.assertIsNone(by_id["toolu_m14_01"]["m15_class"])
        main_rows, _ = self.m14_rows(session="sess-fixture-2")
        self.assertEqual(self.exports("cu.callLedger(x.rows)[0].owner", {"rows": main_rows}), "main")
        # Nothing of the ledger reaches the published measurement.
        published = json.dumps(self.measure(rows))
        for secret in ("toolu_m14", "sess-fixture-1", "agent-fixture-1"):
            self.assertNotIn(secret, published)

    def ledger_sweep_root(self, directory):
        """A sweep root with one child transcript of the M14 fixtures and one main session transcript."""
        root = Path(directory) / "root"
        child = root / "session-a/subagents/agent-child.jsonl"
        child.parent.mkdir(parents=True)
        rows, _ = self.m14_rows(session="sess-fixture-1", agent="agent-fixture-1")
        child.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        main_rows = [{**call("toolu_main_01", "Bash", command="ls"), "sessionId": "sess-fixture-1"},
                     {**result("toolu_main_01", "a"), "sessionId": "sess-fixture-1"}]
        (root / "session-a.jsonl").write_text("\n".join(json.dumps(r) for r in main_rows) + "\n")
        return root

    def test_call_ledger_cli_writes_a_private_file_and_stdout_stays_id_free(self):
        """--call-ledger PATH (U2 design 4.5, with the review's corrections): JSONL, one record per attempted call, created with mode 0600
        and never over an existing file; the sweep adds the published actor ordinal. Stdout stays free of every call id, session id and
        agent id and of the directory, and no ledger is written without the flag."""
        with tempfile.TemporaryDirectory() as directory:
            root = self.ledger_sweep_root(directory)
            ledger = Path(directory) / "private/calls.jsonl"
            ledger.parent.mkdir()
            plain = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", str(root)], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertEqual(sorted(p.name for p in ledger.parent.iterdir()), [])
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", str(root), "--call-ledger", str(ledger)],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout, plain.stdout)
            self.assertEqual(oct(ledger.stat().st_mode & 0o777), "0o600")
            records = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual(len(records), 21)
            got = json.loads(p.stdout)
            ordinals = {a["actor"]: a["ordinal"] for a in got["actors"]}
            self.assertEqual({r["actor_ordinal"] for r in records if r["owner"] == "main"}, {ordinals["main"]})
            self.assertEqual({r["actor_ordinal"] for r in records if r["owner"] == "agent-fixture-1"}, {ordinals["child"]})
            self.assertEqual(got["groups"]["all"]["measurement"]["call_states"]["attempted"], 20)
            for secret in ("toolu_m14", "toolu_main", "sess-fixture-1", "agent-fixture-1", directory):
                self.assertNotIn(secret, p.stdout)

    def test_call_ledger_cli_refusals_write_nothing(self):
        """Exit 2 and nothing written, before any output, for: a path inside this repository or inside any git work tree (the ledger holds
        ids; skill_usage.py write_out's precedent, widened to every work tree), an existing file (create-only, so an existing file's mode
        never stands for 0600: the review's finding on the precedent at mkdtemp), a missing directory, and the flag given twice."""
        with tempfile.TemporaryDirectory() as directory:
            root = self.ledger_sweep_root(directory)
            other = Path(directory) / "other-checkout"
            (other / ".git").mkdir(parents=True)
            (other / "sub").mkdir()
            existing = Path(directory) / "existing.jsonl"
            existing.write_text("keep\n")
            existing.chmod(0o644)
            inside = ROOT / "calls-refused.jsonl"
            # Control: a new file in a directory outside every work tree is written, so the refusals below are not an unknown option.
            accepted = Path(directory) / "accepted.jsonl"
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", str(root), "--call-ledger", str(accepted)],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(accepted.is_file())
            cases = {"inside this repository": [str(inside)], "inside another work tree": [str(other / "sub/calls.jsonl")],
                     "an existing file": [str(existing)], "a missing directory": [str(Path(directory) / "absent/calls.jsonl")],
                     "given twice": [str(Path(directory) / "a.jsonl"), "--call-ledger", str(Path(directory) / "b.jsonl")]}
            for name, args in cases.items():
                with self.subTest(case=name):
                    p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", str(root), "--call-ledger", *args],
                                       capture_output=True, text=True)
                    self.assertEqual((p.returncode, p.stdout), (2, ""))
                    self.assertIn("--call-ledger", p.stderr)
                    self.assertNotIn("unknown option", p.stderr)
            self.assertFalse(inside.exists())
            self.assertFalse((other / "sub/calls.jsonl").exists())
            self.assertEqual((existing.read_text(), oct(existing.stat().st_mode & 0o777)), ("keep\n", "0o644"))
            self.assertFalse((Path(directory) / "a.jsonl").exists())

    def test_call_ledger_run_mode_labels_attempts_and_run_stdout_has_no_call_or_session_ids(self):
        """Run mode: each record carries the child's journal label and whether its attempt was superseded. The review's run-mode contract:
        stdout holds agent ids and the transcript directory by design, but no tool_use_id and no sessionId value."""
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "wf_run"
            run.mkdir()
            rows, _ = self.m14_rows(session="sess-fixture-1", agent="a1")
            usage = {"type": "assistant", "timestamp": "2026-09-26T01:00:03Z", "sessionId": "sess-fixture-1", "agentId": "a1",
                     "effort": "max", "message": {"id": "m1", "model": "claude-opus-5-5", "usage": {
                         "input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}
            (run / "agent-a1.jsonl").write_text("\n".join(json.dumps(r) for r in rows + [usage]) + "\n")
            (run / "agent-a1.meta.json").write_text(json.dumps({"model": "opus", "agentType": "workflow"}))
            (run / "journal.jsonl").write_text("\n".join(json.dumps(e) for e in [
                {"type": "started", "agentId": "a1", "label": "inventory", "key": "k1"},
                {"type": "result", "agentId": "a1", "result": {"answer": "done"}}]) + "\n")
            ledger = Path(directory) / "run-calls.jsonl"
            p = subprocess.run(["node", str(MODULE), str(run), "--call-ledger", str(ledger)], capture_output=True, text=True)
            self.assertIn(p.returncode, (0, 1), p.stderr)
            records = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual(len(records), 20)
            self.assertEqual({(r["label"], r["superseded"]) for r in records}, {("inventory", False)})
            self.assertEqual(oct(ledger.stat().st_mode & 0o777), "0o600")
            for secret in ("toolu_m14", "sess-fixture-1"):
                self.assertNotIn(secret, p.stdout)
            self.assertEqual(json.loads(p.stdout)["children"][0]["lanes"]["measurement"]["call_states"]["attempted"], 20)

    @classmethod
    def m15_rows(cls):
        """M15 fixtures in the exact shapes context-mode v1.0.169 returns (src/server.ts, tag commit 442f1eb6; exit-classify.ts), the Claude
        Code client's MCP texts (observed on this host, count-only) and the Codex approval denial (openai/codex rust-v0.157.1
        core/src/mcp_tool_call.rs:1612). Returns (rows, the expected m15.by_server)."""
        ctx = "mcp__plugin_context-mode_context-mode__"
        rows, count = [], [0]

        def add(name, inputs, content=None, error=True, fields=None, **row):
            count[0] += 1
            key = "toolu_m15_%03d" % count[0]
            rows.append({"type": "assistant", "timestamp": "2026-09-26T01:00:00Z", "message": {"content": [
                {"type": "tool_use", "id": key, "name": name, "input": inputs, **(fields or {})}]}})
            if content is not None:
                rows.append({**result(key, content, error), **({"toolUseResult": "Error: " + content} if error else {}), **row})

        def echo(language, code, path=None):
            return cls.ctx_echo(language, code, path)

        warning = "⚠️ context-mode v1.0.169 outdated → v1.0.170 available. Upgrade: /ctx-upgrade\n\n"
        outside = ('File access blocked: "/abs/outside/app.log" resolves outside the project root (/abs/project). context-mode confines '
                   "ctx_execute_file to the workspace so it cannot be used to bypass the host's sandbox/permission controls (issue #852). "
                   'To intentionally process a file outside the project, add a host allow rule, e.g. "permissions": { "allow": '
                   '["Read(/abs/outside/app.log)"] } in your settings.')
        # Infrastructure: boundary (echo-free, server.ts:1196-1201, returned at :2118-2119 before the echo at :2145), timeouts, modules.
        add(ctx + "ctx_execute_file", {"path": "/abs/outside/app.log", "language": "shell", "code": "wc -l \"$FILE_PATH\""}, outside)
        add(ctx + "ctx_execute_file", {"path": "/abs/outside/app.log", "language": "shell", "code": "cat x"}, warning + outside)
        add(ctx + "ctx_execute", {"language": "python", "code": "import time\ntime.sleep(9)"},
            echo("python", "import time\ntime.sleep(9)") + "Execution timed out after 5000ms\n\nstderr:\n")
        add(ctx + "ctx_execute", {"language": "shell", "code": "sleep 9"},
            warning + echo("shell", "sleep 9") + "Execution timed out after 3000ms\n\nstderr:\n")
        add(ctx + "ctx_execute_file", {"path": "/abs/project/big.log", "language": "python", "code": "print(len(FILE_CONTENT))"},
            echo("python", "print(len(FILE_CONTENT))", "/abs/project/big.log") + "Timed out processing /abs/project/big.log after 30000ms")
        add(ctx + "ctx_batch_execute", {"commands": [{"label": "a", "command": "sleep 90"}], "queries": ["x"]},
            "Batch timed out after 60000ms. No output captured.")
        add(ctx + "ctx_execute", {"language": "shell", "code": "sleep 400"},
            'MCP server "plugin:context-mode:context-mode" tool "ctx_execute" sent no response or progress for 300s; aborting. If this '
            'server is configured in your MCP settings, set a per-server "timeout" (ms) to allow longer silent runs for just this '
            "server; otherwise set CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT (ms).")
        add(ctx + "ctx_execute", {"language": "python", "code": "import numpy"},
            echo("python", "import numpy") + "Exit code: 1\n\nstdout:\n\n\nstderr:\nTraceback (most recent call last):\n"
            "  File \"/abs/project/x.py\", line 1, in <module>\n    import numpy\nModuleNotFoundError: No module named 'numpy'\n")
        add(ctx + "ctx_execute", {"language": "javascript", "code": "require('left-pad')"},
            echo("javascript", "require('left-pad')") + "Exit code: 1\n\nstdout:\n\n\nstderr:\nError: Cannot find module 'left-pad'\n"
            "Require stack:\n- /abs/project/x.js\n")
        # Excluded: the invoked command's own non-zero exit, including the hazard whose echoed code holds every pattern text.
        add(ctx + "ctx_execute", {"language": "shell", "code": "grep x f"},
            echo("shell", "grep x f") + "Exit code: 2\n\nstdout:\n\n\nstderr:\ngrep: f: No such file or directory")
        hazard = "echo '```'; echo 'Execution timed out after 1ms'; echo ModuleNotFoundError; exit 3"
        add(ctx + "ctx_execute", {"language": "shell", "code": hazard},
            echo("shell", hazard) + "Exit code: 3\n\nstdout:\n```\nExecution timed out after 1ms\nModuleNotFoundError\n\nstderr:\n")
        # Unknown between excluded and module: a non-zero exit whose output was indexed, both labels (server.ts:1887, :1897, :2167, :2177).
        add(ctx + "ctx_execute", {"language": "shell", "code": "npm test", "intent": "failing tests"},
            echo("shell", "npm test") + 'Indexed 4 sections from "execute:shell:error" into knowledge base.\n2 sections matched "failing '
            'tests" (400 lines, 24.1KB):\n\n  - FAIL: x\n\nUse ctx_search(queries: [...]) to retrieve full content of any section.')
        add(ctx + "ctx_execute_file", {"path": "/abs/project/build.log", "language": "shell", "code": "cat \"$FILE_PATH\"; exit 1"},
            echo("shell", "cat \"$FILE_PATH\"; exit 1", "/abs/project/build.log") + 'Indexed 2 sections from "file:/abs/project/build.log:'
            'error" into knowledge base.\nNo sections matched intent "errors failures exceptions" in 900-line output (140.2KB).\n\n'
            "Use ctx_search(queries: [...]) to explore the indexed content.")
        # Success: the partial-output timeout note is not an error (server.ts:1863).
        add(ctx + "ctx_execute", {"language": "shell", "code": "tail -f x"},
            echo("shell", "tail -f x") + "partial\n\n_(timed out after 5000ms — partial output shown above)_", error=False)
        # Known classes outside the six: the server's deny firewall, remote fetches (single and an all-failed batch) and search throttling.
        add(ctx + "ctx_execute", {"language": "shell", "code": "rm -rf /"}, "Command blocked by security policy: matches deny pattern Bash(rm -rf *)")
        add(ctx + "ctx_execute_file", {"path": "/abs/project/.env", "language": "shell", "code": "cat x"},
            "File access blocked by security policy: path matches Read deny pattern Read(./.env)")
        add(ctx + "ctx_fetch_and_index", {"url": "https://example.org/x"}, "Failed to fetch https://example.org/x: HTTP 404")
        add(ctx + "ctx_fetch_and_index", {"requests": [{"url": "https://example.org/a"}, {"url": "https://example.org/b"}]},
            "fetched 2 c=2 cap=2/16cpu. ok=0 cache=0 err=2. 0 sections 0.0KB.\n\n- [err]   https://example.org/a: HTTP 404\n"
            '- [err]   https://example.org/b: HTTP 500\n\nctx_search(queries: [...], source: "<label>") for full content.')
        add(ctx + "ctx_search", {"queries": ["x"]}, "BLOCKED: 9 search calls in 12s. You're flooding context. STOP making individual search "
            "calls. Use ctx_batch_execute(commands, queries) for your next research step.")
        # Not executed (M14): no MCP error at all.
        add(ctx + "ctx_execute", {"language": "shell", "code": "ls"}, USER_REJECTION, toolDenialKind="user-rejected",
            toolUseResult="User rejected tool use")
        add(ctx + "ctx_search", {"queries": ["x"]}, "<tool_use_error>InputValidationError: mcp__plugin_context-mode_context-mode__ctx_search "
            "was called with input that could not be parsed</tool_use_error>")
        # New classes (no cm-audit row; a new class counts as our misuse until reproduced on upstream-recommended config).
        add(ctx + "ctx_execute", {"language": "python", "code": "print(1)"}, "Runtime error: spawn python3 ENOENT")
        add(ctx + "ctx_search", {"queries": ["x"]}, "Knowledge base is empty — no content has been indexed yet.\n\nctx_search is a follow-up tool.")
        add(ctx + "ctx_index", {"content": "x", "source": "y"}, "context-mode session directory is not writable: /abs/state/sessions\n"
            "Set CONTEXT_MODE_DIR to a writable directory.")
        add(ctx + "ctx_execute", {"language": "shell"}, 'MCP error -32602: Input validation error: Invalid arguments for tool ctx_execute: '
            '[\n  {\n    "code": "invalid_type"\n  }\n]')
        add(ctx + "ctx_index", {"content": "x"}, "Something unexpected happened")
        # Not read: an echo that differs from the call's code, and a call with no result.
        add(ctx + "ctx_execute", {"language": "shell", "code": "ls"}, "```shell\nls -la\n```\n\nExit code: 2\n\nstdout:\n\n\nstderr:\nls: x")
        add(ctx + "ctx_execute", {"language": "shell", "code": "sleep 1"})
        for _ in range(72):
            add(ctx + "ctx_execute", {"language": "shell", "code": "ls"}, echo("shell", "ls") + "a\nb\n", error=False)
        # Other servers: the client's connection texts, a server's own error, the Codex approval denial, and a call with no result.
        for i in range(8):
            add("mcp__qmd__search", {"query": "q%d" % i}, "[]", error=False)
        add("mcp__qmd__search", {"query": "q"}, 'MCP server "qmd" is not connected')
        add("mcp__qmd__search", {"query": "q"}, 'workspace "private-space" not found')
        add("mcp__ai-memory__memory_query", {"query": "q"}, "MCP tool call requires approval, but approval policy is never")
        add("mcp__linear__list_issues", {}, "Connection closed")
        add("mcp__linear__list_issues", {}, "[]", error=False)
        for i in range(49):
            add("mcp__serena__find_symbol", {"name": "f%d" % i}, "[]", error=False)
        add("mcp__serena__find_symbol", {"name": "g"})
        add("mcp__context_mode__ctx_execute_file", {"path": "/abs/outside/app.log", "language": "shell", "code": "cat x"}, outside,
            fields={"root_mismatch": True})

        def row(attempted, succeeded, classes, infrastructure, new, unknowns, unassigned, rate, lower, upper, over, sensitive, classified,
                is_ctx=False):
            return {"attempted": attempted, "succeeded": succeeded, "ctx": is_ctx, "classes": classes, "infrastructure_errors": infrastructure,
                    "new_class_errors": new, "unknowns": unknowns, "unassigned_errors": unassigned, "rate": rate, "rate_lower_bound": lower,
                    "rate_upper_bound": upper, "over_threshold": over, "threshold_sensitive": sensitive, "every_error_classified": classified}

        want = {  # unassigned: policy_deny, remote_fetch, search_throttle, rejected, invalid (7 on the ctx server); graded on the ceiling
            "plugin_context-mode_context-mode": row(100, 73, {
                "boundary": 2, "timeout": 5, "module": 2, "invoked_command_exit": 2, "invoked_command_exit_indexed": 2, "policy_deny": 2,
                "remote_fetch": 2, "search_throttle": 1, "rejected": 1, "invalid": 1, "server_error": 1, "usage_error": 1,
                "storage_directory": 1, "invalid_arguments": 1, "unmatched": 1, "echo_mismatch": 1, "outcome_unknown": 1},
                9, 5, 4, 7, 0.18, 0.14, 0.25, True, False, False, True),
            "qmd": row(10, 8, {"connection": 1, "unmatched": 1}, 1, 1, 0, 0, 0.2, 0.2, 0.2, True, False, False),
            "ai-memory": row(1, 0, {"approval": 1}, 1, 0, 0, 0, 1, 1, 1, True, False, True),
            "linear": row(2, 1, {"connection": 1}, 1, 0, 0, 0, 0.5, 0.5, 0.5, True, False, True),
            "serena": row(50, 49, {"outcome_unknown": 1}, 0, 0, 1, 0, 0.02, 0, 0.02, True, True, True),
            "context_mode": row(1, 0, {"binding": 1}, 1, 0, 0, 0, 1, 1, 1, True, False, True, True),
        }
        return rows, want

    def test_m15_infrastructure_error_classes(self):
        """Protocol M15 (E2E README.md M15 row; preregistration.json thresholds.M15), one class per attempted MCP call, per server. The
        anchored templates context-mode returns before it builds the code echo (boundary, the deny firewall, Runtime error, storage and
        usage errors) are tested on the raw text first; the echo is required, and stripped, only for ctx_execute and ctx_execute_file
        outputs after execution (the review's high finding), and the outdated-version notice trackResponse may put first (server.ts:892-896)
        is stripped before both. rate_upper_bound, the graded rate until Amendment 4 assigns the classes outside the named groups (U2 design
        5.3; binding decisions: the harder-to-pass reading), counts every call that neither succeeded nor ended in the invoked command's own
        exit, and over_threshold is its verdict by counts; unassigned_errors is its residual after the named groups. rate counts the six
        infrastructure classes, every new class (named, or unmatched text: 'a new class counts as our misuse until reproduced') and every
        call whose class or outcome cannot be established (binding decision B2: an unknown is not a success); rate_lower_bound counts the
        unknowns as successes; threshold_sensitive marks a server whose rate_lower_bound and rate_upper_bound fall on different sides of
        0.01; every_error_classified is the criterion classify_every_ctx_error."""
        rows, want = self.m15_rows()
        got = self.measure(rows).get("m15")
        self.assertEqual(got, {"threshold": 0.01, "by_server": want})
        per_call = self.exports("cu.callLedger(x.rows).filter((r) => r.server).map((r) => r.m15_class)", {"rows": rows})
        self.assertEqual(per_call[:4], ["boundary", "boundary", "timeout", "timeout"])
        for server, r in got["by_server"].items():  # the ceiling is the named groups plus the residual, on every server
            with self.subTest(server=server):
                self.assertEqual(r["infrastructure_errors"] + r["new_class_errors"] + r["unknowns"] + r["unassigned_errors"],
                                 r["attempted"] - r["succeeded"] - r["classes"].get("invoked_command_exit", 0))

    def m15_server_rows(self, cases, attempted):
        """Each case's classes as the one server of an aggregated measurement with `attempted` calls, the rest successes:
        [rate, rate_lower_bound, rate_upper_bound, over_threshold, threshold_sensitive, unassigned_errors] per case."""
        rows = [call("q", "mcp__qmd__search", query="x"), result("q", "[]")]
        return self.exports("x.cases.map((classes) => { const m = cu.measureTranscript(x.rows); m.m15.by_server = { qmd: { attempted: x.n,"
                            " succeeded: x.n - Object.values(classes).reduce((a, b) => a + b, 0), ctx: false, classes } };"
                            " const r = cu.aggregateMeasurements([m]).m15.by_server.qmd;"
                            " return [r.rate, r.rate_lower_bound, r.rate_upper_bound, r.over_threshold, r.threshold_sensitive, r.unassigned_errors] })",
                            {"rows": rows, "cases": cases, "n": attempted})

    def test_m15_threshold_comparison_uses_counts_not_the_rounded_rate(self):
        """rate is rounded to four places, as every kernel share is, so a server just over the 0.01 threshold can print as 0.01: 202 of
        20,100 calls is 1.005%. over_threshold and threshold_sensitive (binding decision B2) therefore compare the counts: errors * 100 >
        attempted, with the graded ceiling's count for over_threshold."""
        cases = {  # classes of one server with 20,100 attempts:
            # (rate, rate_lower_bound, rate_upper_bound, over_threshold, threshold_sensitive, unassigned_errors)
            "over by counts, 0.01 when rounded; lower bound under": ({"connection": 190, "outcome_unknown": 12}, (0.01, 0.0095, 0.01, True, True, 0)),
            "exactly at the threshold is not over it": ({"connection": 190, "outcome_unknown": 11}, (0.01, 0.0095, 0.01, False, False, 0)),
            "both bounds over": ({"connection": 202}, (0.01, 0.01, 0.01, True, False, 0)),
            "only the ceiling crosses: an unassigned class counts in the graded rate": (
                {"connection": 100, "outcome_unknown": 50, "rejected": 52}, (0.0075, 0.005, 0.01, True, True, 52)),
            "the invoked command's own exit stays out of every rate": ({"invoked_command_exit": 5000, "connection": 100}, (0.005, 0.005, 0.005, False, False, 0)),
        }
        got = self.m15_server_rows([classes for classes, _ in cases.values()], 20100)
        for (name, (_, want)), row in zip(cases.items(), got):
            with self.subTest(case=name):
                self.assertEqual(tuple(row), want)

    def test_m15_grades_the_ceiling_until_amendment_4_assigns_the_classes(self):
        """The review's high finding: a server every call of which fails with a class outside the named groups must not pass the 0.01
        threshold. The U2 design (5.3: 'Grading reads rate_upper_bound until a dated amendment assigns the other classes') and the binding
        decisions ('the harder-to-pass reading applies') grade on the ceiling, every attempted call that neither succeeded nor ended in the
        invoked command's own exit (the frozen M15 row excludes only that exit). The client's own text for a tool it does not have (the
        M14 fixture above; 6 MCP results on this host, scans/call-states.json) is an invalid call; on the kernel before this fix (b2dd1eb7)
        it read rate 0, rate_lower_bound 0 and threshold_sensitive false, and only rate_upper_bound 1."""
        missing = "No such tool available: mcp__qmd__search"
        rows = []
        for i in range(5):
            rows += [call("nt%d" % i, "mcp__qmd__search", query="q%d" % i),
                     {**result("nt%d" % i, "<tool_use_error>Error: " + missing + "</tool_use_error>", True), "toolUseResult": "Error: " + missing}]
        got = self.measure(rows)["m15"]["by_server"]["qmd"]
        self.assertEqual(got, {"attempted": 5, "succeeded": 0, "ctx": False, "classes": {"invalid": 5}, "infrastructure_errors": 0,
                               "new_class_errors": 0, "unknowns": 0, "unassigned_errors": 5, "rate": 0, "rate_lower_bound": 0,
                               "rate_upper_bound": 1, "over_threshold": True, "threshold_sensitive": True, "every_error_classified": True})

    def test_m15_every_class_outside_the_named_groups_counts_in_the_ceiling(self):
        """Each class outside the named groups alone, 2 of 100 calls, is over the threshold on the ceiling; so is a class no list names (a
        template added later), since the ceiling is a residual; the invoked command's own exit is the one exclusion (the frozen M15 row)."""
        unassigned = ["policy_deny", "remote_fetch", "search_throttle", "rejected", "invalid", "cancelled_with_result", "a_later_class"]
        got = self.m15_server_rows([{k: 2} for k in unassigned] + [{"invoked_command_exit": 50}], 100)
        for name, row in zip(unassigned + ["invoked_command_exit"], got):
            with self.subTest(case=name):
                self.assertEqual(tuple(row), (0, 0, 0, False, False, 0) if name == "invoked_command_exit" else (0, 0, 0.02, True, True, 2))

    def test_m15_aggregate_recomputes_rates_and_sweep_output_is_id_free(self):
        """aggregateMeasurements sums each server's attempts and classes over actors and computes the rates again; the sweep prints class
        names and counts only: no path, URL, module name, server-side text or id from the results."""
        rows, want = self.m15_rows()
        cut = next(i for i, r in enumerate(rows) if r["type"] == "assistant" and "toolu_m15_050" in json.dumps(r))
        agg = self.exports("cu.aggregateMeasurements([cu.measureTranscript(x.a), cu.measureTranscript(x.b)]).m15",
                           {"a": rows[:cut], "b": rows[cut:]})
        self.assertEqual(agg, {"threshold": 0.01, "by_server": want})
        self.assertEqual(self.exports("cu.aggregateMeasurements([]).m15", {}), {"threshold": 0.01, "by_server": {}})
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "session/subagents/agent-child.jsonl"
            child.parent.mkdir(parents=True)
            child.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["groups"]["all"]["measurement"]["m15"]["by_server"]["qmd"], want["qmd"])
            for secret in ("/abs", "example.org", "numpy", "left-pad", "private-space", "ENOENT", "CONTEXT_MODE_DIR", "ctx-upgrade",
                           "plugin:context-mode:context-mode", "toolu_m15", directory):
                self.assertNotIn(secret, p.stdout)

    @NEEDS_PARSER
    def test_cli_lanes_aggregate_sums_counters_and_counts_actors_with_success(self):
        script = ("import {readFileSync} from 'node:fs'; import {measureTranscript, aggregateMeasurements, loadShellParser} from "
                  + json.dumps(MODULE.as_uri()) + "; const rows=JSON.parse(readFileSync(0,'utf8')); await loadShellParser(); "
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
            "mcporter_downstream": {"(other)": downstream_row(succeeded=1)}})
        self.assertEqual(got["proxy"], proxy_row(calls=0, in_ctx_code=1))
        self.assertEqual(empty.get("cli_lanes"), {"status": "not_measured"})  # an aggregate of no measurements has no lane counts

    @NEEDS_PARSER
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
            self.assertEqual(sorted(cli.get("mcporter_downstream", {})), ["(http)", "(other)"])
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

    # Item 1 (PR-A): injected context from every hook event. Rows in the shapes this host's 2.1.283/2.1.284 transcripts carry (count-only scan,
    # evidence/artifacts/pra-u2-differential-20260929): a PreToolUse insertion is named PreToolUse:<tool> and follows the hook_success row of
    # the same (toolUseID, hookName); SessionStart and SubagentStart insertions carry a plain hookName and one or two content entries.
    HOOK_MARKER = "<context_window_protection>"

    @staticmethod
    def hook(kind, name, event=None, **rest):
        return {"type": "attachment", "timestamp": "2026-09-26T01:00:00Z", "attachment": {
            "type": kind, "hookName": name, "hookEvent": event or name.split(":")[0], **rest}}

    @classmethod
    def hook_rows(cls):
        hook, marker = cls.hook, cls.HOOK_MARKER
        def claim(text, event):
            return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})
        return {
            "A": hook("hook_success", "SessionStart:startup", toolUseID="s1", stdout=claim("a", "SessionStart")),
            "B": hook("hook_success", "SessionStart:startup", toolUseID="s2", stdout=claim("b " + marker, "SessionStart")),
            "C": hook("hook_additional_context", "SessionStart", toolUseID="SessionStart", content=["a", "b " + marker]),
            "D": hook("hook_success", "PreToolUse:Read", toolUseID="toolu_r", stdout=claim("tip", "PreToolUse")),
            "E": hook("hook_additional_context", "PreToolUse:Read", toolUseID="toolu_r", content=["tip"]),
            "F": hook("hook_success", "SubagentStart:general-purpose", toolUseID="start", stdout=claim("lanes", "SubagentStart")),
            "G": hook("hook_additional_context", "SubagentStart", toolUseID="rnd", content=["lanes"]),
            "H": hook("hook_additional_context", "PostToolUse:Bash", toolUseID="toolu_b", content=["post"]),
            "I": hook("hook_additional_context", "UserPromptSubmit", content=["ups"]),
            "J": hook("hook_success", "PreToolUse:Grep", toolUseID="toolu_g", stdout=claim("claimed only", "PreToolUse")),
            # Plain stdout reaches context only on UserPromptSubmit, UserPromptExpansion, SessionStart and PostModelSwitch; stdout that does not
            # both start with { and end with } is plain text, a JSON array included (code.claude.com/docs/en/hooks, "Exit code 0").
            "K": hook("hook_success", "UserPromptSubmit", stdout="plain text context"),
            "K2": hook("hook_success", "PreToolUse:Bash", toolUseID="toolu_p", stdout="plain on a tool event goes to the debug log"),
            "K3": hook("hook_success", "SessionStart:resume", stdout="[1, 2]"),
            "K4": hook("hook_success", "UserPromptSubmit", stdout='{"unterminated": 1'),
            "K5": hook("hook_success", "UserPromptSubmit", stdout=json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}})),
            "K6": hook("hook_success", "UserPromptSubmit", stdout="{not json}"),
            "L": hook("hook_non_blocking_error", "PostToolUse:Bash", toolUseID="toolu_b"),
            "L2": hook("hook_system_message", "PostToolUse:Bash", toolUseID="toolu_b"),
            "M": hook("hook_additional_context", "PreToolUse:mcp__srv__" + "y" * 70, toolUseID="toolu_m", content=["t"]),
        }

    def test_hook_context_rows_blocks_and_claims_by_event(self):
        """inserted counts hook_additional_context rows (the unit of M12: README.md M12 row), inserted_blocks their content entries, both
        per hookEvent; a hook_success claim is never an insertion; other hook_* rows are counted apart, descriptively."""
        rows = self.hook_rows()
        got = self.measure([rows[k] for k in "A B C D E F G H I J K K2 K3 K4 K5 K6 L L2 M".split()])["hook_context"]
        # must-stay controls: the #432 counters, the same at the base
        self.assertEqual((got["inserted"], got["claimed"], got["with_marker"]), (6, 5, 1))
        self.assertEqual(got["by_event"], {"SessionStart": 1, "PreToolUse": 2, "SubagentStart": 1, "PostToolUse": 1, "UserPromptSubmit": 1})
        # a hook name SAFE_KEY drops (over 80 characters) keeps its event and MCP server; the base counts it under (other)
        self.assertEqual(got["by_hook"], {"SessionStart": 1, "PreToolUse:Read": 1, "SubagentStart": 1, "PostToolUse:Bash": 1,
                                          "UserPromptSubmit": 1, "PreToolUse:mcp__srv": 1})
        self.assertEqual(got.get("hook_names_folded"), 1)
        self.assertEqual(got.get("inserted_blocks"), 7)
        self.assertEqual(got.get("blocks_by_event"), {"SessionStart": 2, "PreToolUse": 2, "SubagentStart": 1, "PostToolUse": 1, "UserPromptSubmit": 1})
        self.assertEqual(got.get("claimed_by_event"), {"SessionStart": 2, "PreToolUse": 2, "SubagentStart": 1})
        self.assertEqual(got.get("claimed_plain_stdout"), {"UserPromptSubmit": 2, "SessionStart": 1})
        self.assertEqual(got.get("other_hook_rows"), {"hook_non_blocking_error": 1, "hook_system_message": 1})

    def test_hook_context_negatives_and_the_m12_positive_control(self):
        rows = self.hook_rows()
        def measured(keys):
            return self.measure([rows[k] for k in keys.split()])["hook_context"]
        for keys, want in [
                ("J", {"inserted": 0, "inserted_blocks": 0, "claimed": 1}),  # stdout only: a claim, never an insertion
                ("D E", {"inserted": 1, "inserted_blocks": 1, "claimed": 1}),  # sibling rows: the hook_success row beside an insertion adds none
                ("E G H", {"inserted": 3, "inserted_blocks": 3, "with_marker": 0})]:  # absent marker: rows still count
            with self.subTest(rows=keys):
                got = measured(keys)
                self.assertEqual({k: got.get(k) for k in want}, want)
        # M12's positive control reads this key (README.md M12 row): it must stay exactly as it is
        self.assertEqual(measured("E")["by_hook"], {"PreToolUse:Read": 1})
        # only an over-long <Event>:mcp__<server>__<tool> name with a hook-event-shaped prefix and a name-shaped server folds; the rest stay (other)
        hook = self.hook
        long_rows = [rows["M"], hook("hook_additional_context", "PreToolUse:" + "z" * 90, content=["t"]),
                     hook("hook_additional_context", "pre tool use:mcp__srv__" + "y" * 70, event="PreToolUse", content=["t"]),
                     hook("hook_additional_context", "PostToolUse:mcp__bad server__" + "y" * 70, content=["t"])]
        got = self.measure(long_rows)["hook_context"]
        self.assertEqual((got["by_hook"], got.get("hook_names_folded")), ({"PreToolUse:mcp__srv": 1, "(other)": 3}, 1))

    def test_hook_context_of_a_sibling_child_counts_only_in_its_own_actor(self):
        rows = self.hook_rows()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "session/subagents"
            base.mkdir(parents=True)
            (base / "agent-inserted.jsonl").write_text(json.dumps(rows["E"]) + "\n")
            (base / "agent-claimed.jsonl").write_text(json.dumps(rows["D"]) + "\n")
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
        hooks = got["groups"]["all"]["measurement"]["hook_context"]
        self.assertEqual((hooks["inserted"], hooks["claimed"]), (1, 1))  # control
        self.assertEqual(hooks.get("actors_with_insertion"), 1)
        self.assertEqual(sorted(a["measurement"]["hook_context"]["inserted"] for a in got["actors"]), [0, 1])  # control

    def test_loaded_not_called_counts_references_and_actors(self):
        """Item 5: measurement.loaded counts the tool references of ToolSearch results per MCP server whether or not the actor called it;
        loaded_not_called keeps the #432 unit (references of servers the actor attempted no call on inside the window); the aggregate adds
        the historical baseline row's unit, actors per server (RUNBOOK.md 'Loaded, never called': children loading each named server)."""
        def ref(tool):
            return {"type": "tool_reference", "tool_name": tool}
        a = [call("s", "ToolSearch", query="select:x"), result("s", [ref("mcp__serena__find_symbol"), ref("mcp__serena__find_referencing_symbols"),
                                                                     ref("mcp__qmd__query"), ref("Read")]),
             call("q", "mcp__qmd__query"), result("q", "ok")]
        c = [call("s", "ToolSearch", query="select:y"), result("s", [ref("mcp__serena__find_symbol")]),
             call("f", "mcp__serena__find_symbol"), result("f", "ok")]
        each, agg = self.exports("(() => { const ms = x.map((r) => cu.measureTranscript(r)); return [ms, cu.aggregateMeasurements(ms)] })()", [a, a, c])
        self.assertEqual(each[0]["loaded_not_called"], {"serena": 2})  # control: references, as at #432
        self.assertEqual(each[0].get("loaded"), {"serena": 2, "qmd": 1})  # a built-in tool reference (Read) is no server
        self.assertEqual(each[2].get("loaded"), {"serena": 1})
        self.assertEqual(agg["loaded_not_called"], {"serena": 4})  # control
        self.assertEqual(agg.get("loaded"), {"serena": 5, "qmd": 2})
        self.assertEqual(agg.get("loaded_actors"), {"serena": 3, "qmd": 2})
        self.assertEqual(agg.get("loaded_not_called_actors"), {"serena": 2})
        # the window: a call before since does not make a load inside it a call, and a result at or after until adds nothing
        from datetime import datetime
        def ms(clock):
            return datetime.fromisoformat("2026-09-26T" + clock + "+00:00").timestamp() * 1000
        def at(row, clock):
            return {**row, "timestamp": "2026-09-26T" + clock + "Z"}
        rows = [at(call("f", "mcp__serena__find_symbol"), "01:00:00"), result("f", "ok", timestamp="2026-09-26T01:00:01Z"),
                at(call("s", "ToolSearch"), "02:00:00"), result("s", [ref("mcp__serena__find_symbol")], timestamp="2026-09-26T02:00:01Z"),
                at(call("t", "ToolSearch"), "02:40:00"), result("t", [ref("mcp__qmd__query")], timestamp="2026-09-26T02:40:01Z")]
        got = self.measure(rows, window={"since": ms("01:30:00"), "until": ms("02:30:00")})
        self.assertEqual(got["loaded_not_called"], {"serena": 1})  # control
        self.assertEqual(got.get("loaded"), {"serena": 1})

    # Item 4: JSON and uniform-tabular shapes of results over 5,120 B. P is a JSON array of 200 flat records.
    P = [{"id": i, "name": "n%d" % i, "ok": True} for i in range(200)]

    @staticmethod
    def ctx_echo(language, code, path=None):
        """context-mode v1.0.169 src/server.ts:1511-1527 (buildExecuteEcho): the code clipped at 2,000 characters, fenced, before stdout."""
        clip = code if len(code) <= 2000 else code[:2000] + "\n… (truncated)"
        return ("path=" + path + "\n" if path else "") + "```" + language + "\n" + clip + "\n```\n\n"

    @staticmethod
    def cat_n(text):
        """The Read tool's cat -n form: a right-aligned line number and a tab before every line."""
        return "\n".join("%6d\t%s" % (i, line) for i, line in enumerate(text.split("\n"), 1))

    def test_large_json_and_uniform_tabular_by_carrier(self):
        """A result over RESULT_LIMIT is JSON when its payload, trimmed, opens with [ or { and parses; uniform_keys when it (or the one value of
        a one-key object) is an array of at least five objects with the same non-empty key set; uniform_flat when every value is also null,
        a boolean, a number or a string (TOON v4.1.1 packages/toon/README.md:199, 'identical fields with primitive values'). The payload is
        the text after the carrier's own wrapper: the ctx_execute(_file) code echo, or the Read tool's cat -n line numbers. A result this
        reading cannot inspect (a non-text block, an echo or a line number it cannot find) counts in large_shape_unknown, never as 0."""
        p = json.dumps(self.P)
        nested = json.dumps([{"id": i, "meta": {"x": 1}} for i in range(200)])
        padded = json.dumps([{"id": i, "pad": "x" * 1500} for i in range(4)])
        ragged = json.dumps([{"id": i, "name": "n%d" % i, ("a" if i % 2 else "b"): 1} for i in range(200)])
        small = json.dumps(self.P[:6])
        long_code = "echo " + "x" * 2500
        half = len(self.ctx_echo("shell", "cat a.json") + p) // 2
        echoed = self.ctx_echo("shell", "cat a.json") + p
        specs = [
            ("r1", "Bash", {"command": "cat a.json"}, p),
            ("r2", "Bash", {"command": "cat b.json"}, json.dumps({"items": self.P})),
            ("r3", "Bash", {"command": "cat c.json"}, nested),
            ("r4", "Bash", {"command": "cat d.json"}, padded),
            ("r5", "Bash", {"command": "cat e.json"}, ragged),
            ("r6", "Bash", {"command": "cat f.txt"}, "not json " * 700),
            ("r7", "Bash", {"command": "cat g.json"}, small),
            ("r8", "Bash", {"command": "rtk proxy cat a.json"}, p),
            ("r9", "mcp__ctx__ctx_execute", {"language": "shell", "code": "cat a.json"},
             [{"type": "text", "text": echoed[:half]}, {"type": "text", "text": echoed[half:]}]),
            ("r10", "mcp__ctx__ctx_execute", {"language": "shell", "code": "cat a.json"},
             [{"type": "text", "text": self.ctx_echo("shell", "cat a.json") + p}, {"type": "image", "source": {"type": "base64", "data": "AAAA"}}]),
            ("r11", "mcp__ctx__ctx_execute", {"language": "shell", "code": "cat a.json"}, self.ctx_echo("shell", "cat b.json") + p),
            ("r12", "Read", {"file_path": "a.json"}, self.cat_n(json.dumps(self.P, indent=1))),
            ("r13", "Read", {"file_path": "b.json"}, self.cat_n(json.dumps(self.P, indent=1)) + "\n(more lines not shown)"),
            ("r14", "mcp__ctx__ctx_execute_file", {"path": "a.json", "language": "python", "code": "print(open(FILE).read())"},
             [{"type": "text", "text": self.ctx_echo("python", "print(open(FILE).read())", "a.json") + p}]),
            ("r15", "mcp__ctx__ctx_execute", {"language": "shell", "code": long_code}, [{"type": "text", "text": self.ctx_echo("shell", long_code) + p}]),
            ("r16", "mcp__qmd__query", {}, [{"type": "text", "text": p}]),
        ]
        rows = []
        for key, name, inputs, content in specs:
            rows += [call(key, name, **inputs), result(key, content)]
        got = self.measure(rows)
        shape = lambda sizes: tuple(sizes.get(k) for k in ("large_json", "large_uniform_keys", "large_uniform_flat", "large_shape_unknown"))
        self.assertEqual(got["m3"]["large_results"], 15)  # control: r7 alone is under the limit
        self.assertEqual(shape(got["by_carrier"]["bash"]), (5, 3, 2, 0))
        self.assertEqual(shape(got["by_carrier"]["rtk_proxy"]), (1, 1, 1, 0))
        self.assertEqual(shape(got["by_carrier"]["ctx"]), (3, 3, 3, 2))
        self.assertEqual(shape(got["by_carrier"]["read"]), (1, 1, 1, 1))
        self.assertEqual(shape(got["by_carrier"]["other_mcp"]), (1, 1, 1, 0))
        self.assertEqual(shape(got["m3"]), (11, 9, 8, 3))
        self.assertEqual(shape(got["m5"]), (3, 3, 3, 2))
        # the aggregate sums the counters of every sizes object
        agg = self.exports("cu.aggregateMeasurements([cu.measureTranscript(x), cu.measureTranscript(x)])", rows)
        self.assertEqual(shape(agg["m3"]), (22, 18, 16, 6))
        self.assertEqual(shape(agg["by_carrier"]["ctx"]), (6, 6, 6, 4))

    def test_section_one_per_actor_figures_survive_aggregation(self):
        """The AA §1 figures that exist only per actor (scope extract, baseline derivation order): children with any MCP call, children with
        an MCP call that is not a ctx_ tool, per-server loaded-never-called children (test above), and the per-child distribution of shell/web
        results over 5 KB (bash, rtk_proxy and webfetch carriers; tokenStats nearest rank). actors_with_ctx_results is M5's population
        ('All B children using ctx', README.md M5 row)."""
        big = "x" * 6000
        x = [call("b1", "Bash", command="cat a"), result("b1", big), call("b2", "Bash", command="cat b"), result("b2", big),
             call("b3", "Bash", command="rtk proxy cat c"), result("b3", big), call("w", "WebFetch", url="https://example.org"), result("w", big),
             call("q", "mcp__qmd__query"), result("q", "ok"), call("e", "mcp__ctx__ctx_execute", language="shell", code="ls"), result("e", "ok")]
        y = [call("e", "mcp__ctx__ctx_execute", language="shell", code="ls"), result("e", "ok")]
        z = [call("l", "Bash", command="ls"), result("l", "a")]
        agg = self.exports("cu.aggregateMeasurements(x.map((r) => cu.measureTranscript(r)))", [x, y, z])
        self.assertEqual(agg["m3_large_results_per_actor"], {"n": 3, "min": 0, "p10": 0, "median": 0, "p90": 4, "max": 4})  # control
        self.assertEqual(agg.get("shell_web_large_results_per_actor"), {"n": 3, "min": 0, "p10": 0, "median": 0, "p90": 4, "max": 4})
        self.assertEqual((agg.get("actors_with_mcp_call"), agg.get("actors_with_non_ctx_mcp_call"), agg.get("actors_with_ctx_results")), (2, 1, 2))

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

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_rtk_parts_join_eligible_calls_to_their_m14_state(self):
        """U2 design 7.3/7.4 and binding decision B5: M1's rtk-claude success signal per child-task is a Bash call with an eligible part
        observed covered whose M14 state is succeeded (observed_covered_succeeded_calls); eligible_call_states gives every such call's
        state. The call is `git status && git log -3`, which the rtk hook rewrote to `rtk git status && rtk git log -3`."""
        command, rewritten = "git status && git log -3", "rtk git status && rtk git log -3"
        base = [call("c", "Bash", command=command), rtk_rewrite("c", rewritten)]
        cases = {"ok": (base + [result("c", "On branch main")], "succeeded", 1),
                 "exit 128": (base + [result("c", "Exit code 128\nfatal: not a git repository", True)], "failed", 0),
                 "hook rejection": (base + [result("c", HOOK_DENIAL, True)], "rejected", 0),
                 "no result": (base, "cancelled_or_unfinished", 0)}
        for name, (rows, state, succeeded) in cases.items():
            with self.subTest(case=name):
                got = self.measure(rows, rtkCheck=True)["rtk_parts"]
                self.assertEqual((got["eligible_parts"], got["observed_covered_parts"], got["eligible_calls"]), (2, 2, 1))
                executed = 1 if state in ("succeeded", "failed") else 0
                self.assertEqual(got["eligible_call_states"], {**M14_ROW, "attempted": 1, "executed": executed, state: 1})
                self.assertEqual(got["observed_covered_succeeded_calls"], succeeded)
        # Covered in replay only (no hook row): eligible and succeeded, but nothing observed covered, so no M1 success.
        got = self.measure([call("c", "Bash", command=command), result("c", "ok")], rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["replayed_covered_parts"], got["observed_covered_parts"], got["observed_covered_succeeded_calls"]), (2, 0, 0))
        self.assertEqual(got["eligible_call_states"]["succeeded"], 1)
        # An rtk proxy part is outside the eligible population, so the call is no opportunity at all.
        got = self.measure([call("c", "Bash", command="rtk proxy git diff --stat"), result("c", "ok")], rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["proxy_parts"], got["eligible_calls"], got["observed_covered_succeeded_calls"]), (1, 0, 0))
        self.assertEqual(got["eligible_call_states"], M14_ROW)
        # The aggregate sums the states and the numerator.
        rows = [base + [result("c", "ok")], base + [result("c", HOOK_DENIAL, True)]]
        agg = self.exports("cu.aggregateMeasurements(x.map((rows) => cu.measureTranscript(rows, { rtkCheck: true }))).rtk_parts", rows)
        self.assertEqual(agg["eligible_call_states"], {**M14_ROW, "attempted": 2, "executed": 1, "succeeded": 1, "rejected": 1})
        self.assertEqual(agg["observed_covered_succeeded_calls"], 1)

    # Binding decision B8: the M-R1 part splitter reads shell text with U1's frame machine (step(): quotes, escapes, comments, $(( )) and
    # (( )), "$( )" and backquote frames, and the redirection forms of the control-operator characters), and a here-document body is data
    # (bash(1) Here Documents; POSIX.1-2024 XCU 2.7.4). A top-level body lies between two parts and belongs to neither part's text; a body
    # inside a part stays in its text and is masked in its syntax.
    B8_PARTS = {
        "cat > notes.txt <<'EOF'\nline; with && ops | \"quote\nEOF\ngit status": [["cat > notes.txt <<'EOF'", "\n"], ["git status", ""]],
        "git commit -m \"$(cat <<'EOF'\nmsg; x && y\nEOF\n)\" && git status": [["git commit -m \"$(cat <<'EOF'\nmsg; x && y\nEOF\n)\"", "&&"], ["git status", ""]],
        "echo $((1 + 2)) && git status": [["echo $((1 + 2))", "&&"], ["git status", ""]],
        "(( n = 1 << 2 )); git status": [["(( n = 1 << 2 ))", ";"], ["git status", ""]],
        "git status # a; b\ngit log -3": [["git status # a; b", "\n"], ["git log -3", ""]],
        "git status &> /dev/null; git log -3": [["git status &> /dev/null", ";"], ["git log -3", ""]],
        "git status >| out.txt": [["git status >| out.txt", ""]],
        "cat <<A <<B\na;\nA\nb|\nB\ngit status": [["cat <<A <<B", "\n"], ["git status", ""]],
        "cat <<-EOF\n\tbody;\n\tEOF\ngit status": [["cat <<-EOF", "\n"], ["git status", ""]],
        "cat <<'END-JSON'\n{\"a\": \"b;c\"}\nEND-JSON\ngit status": [["cat <<'END-JSON'", "\n"], ["git status", ""]],
        "cat <<EOF\nno delimiter line; git status": [["cat <<EOF", "\n"]],
        "git log --format='%h <<EOF' && git status": [["git log --format='%h <<EOF'", "&&"], ["git status", ""]],
        "x=$(printf '%s' \"a;b\") && git status": [["x=$(printf '%s' \"a;b\")", "&&"], ["git status", ""]],
        "echo `git status; ls` && git log -3": [["echo `git status; ls`", "&&"], ["git log -3", ""]],
        "git status |& tail -n 5": [["git status", "|"], ["tail -n 5", ""]],
        "git status 2>&1 | head": [["git status 2>&1", "|"], ["head", ""]],
        "{ git status; git log -3; } && ls": [["{ git status; git log -3; }", "&&"], ["ls", ""]],
        "cat <<EOF | grep x && git status\nbody\nEOF\nls": [["cat <<EOF", "|"], ["grep x", "&&"], ["git status", "\n"], ["ls", ""]],
        "sleep 1 & git status": [["sleep 1", "&"], ["git status", ""]],
        "echo \"a\\\"b\" ; git status": [["echo \"a\\\"b\"", ";"], ["git status", ""]],
        # A body begins at a newline of its operator's frame depth or shallower. Run under GNU bash 5.2.21 and dash on 2026-09-29: the first
        # printed body-line (a newline inside "$( )" does not begin the outer body), the second x=[echo visible] with bash's warning
        # "command substitution: 1 unterminated here-document" (a body the substitution leaves open is read after the enclosing line).
        "cat <<'EOF' && x=$(echo a\necho b)\nbody-line\nEOF\necho after": [["cat <<'EOF'", "&&"], ["x=$(echo a\necho b)", "\n"], ["echo after", ""]],
        "x=$(cat <<EOF)\necho visible\nEOF\necho after": [["x=$(cat <<EOF)", "\n"], ["echo after", ""]],
    }
    # Text these rules cannot read: an open quote, a ) with no ( before it, an open $( and a << with no delimiter word.
    B8_UNPARSED = ["git status && echo \"unterminated", "git status )", "echo $(git status", "cat <<\ngit status", "git status && cat <<"]

    def test_b8_shell_parts_read_heredocs_arithmetic_and_comments(self):
        got = self.exports("x.map((c) => { const p = cu.shellParts(c); return p && p.map((q) => [q.text, q.op]) })", list(self.B8_PARTS))
        for (command, want), parts in zip(self.B8_PARTS.items(), got):
            with self.subTest(command=command):
                self.assertEqual(parts, want)
        got = self.exports("x.map((c) => cu.shellParts(c))", self.B8_UNPARSED)
        for command, parts in zip(self.B8_UNPARSED, got):
            with self.subTest(command=command):
                self.assertIsNone(parts)
        # The syntax view masks data: a > in a heredoc body inside a part, in a comment or in $(( )) is no redirection; one outside is.
        got = self.exports("x.map((c) => cu.shellParts(c).map((q) => q.syntax))", [
            "x=$(cat <<'EOF'\na > b\nEOF\n) && git status > out.txt", "git status # > f", "echo $((2 > 1)) && git status"])
        self.assertNotIn(">", got[0][0])
        self.assertIn("> out.txt", got[0][1])
        self.assertNotIn(">", got[1][0])
        self.assertNotIn(">", got[2][0])

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_b8_heredoc_and_arithmetic_calls_are_classified_not_unknown(self):
        """rtk v0.50.0 rewrites no command that holds a here-document or $(( (src/discover/registry.rs rewrite_command_precompiled, tag
        commit 1d87b8e7), so such a call runs raw: its parts are classified, and an eligible part in it is not covered. At the base these
        calls were unknown (shellParts refused any << or $(( ), which hid every eligible part they held."""
        cases = {"cat > notes.txt <<'EOF'\nline; with && ops\nEOF\ngit status": 1,
                 "git commit -m \"$(cat <<'EOF'\nmsg; x\nEOF\n)\" && git status": 1,
                 "echo $((1 + 2)) && git status": 1}
        for command, eligible in cases.items():
            with self.subTest(command=command):
                got = self.measure([call("c", "Bash", command=command), result("c", "ok")], rtkCheck=True)["rtk_parts"]
                self.assertEqual((got["calls"], got["unknown_calls"], got["eligible_parts"], got["ineligible_parts"]), (1, 0, eligible, 1))
                self.assertEqual((got["observed_covered_parts"], got["replayed_covered_parts"]), (0, 0))
                self.assertEqual((got["status"], got["unknown_call_share"]), ("measured", 0))
        # A genuinely unparsable call stays unknown and is counted once however many parts it has.
        got = self.measure([call("c", "Bash", command="git status && git log -3 && echo \"unterminated")], rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["calls"], got["unknown_calls"], got["eligible_parts"], got["unknown_call_share"]), (1, 1, 0, 1))
        self.assertEqual(got["status"], "incomplete")

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_b8_an_unknown_call_counts_once_and_leaves_the_eligible_denominators(self):
        """B8: a call whose parts cannot all be classified is one unknown call and adds no eligible, ineligible, observed or replayed part.
        A stub rtk (the real binary for everything else) fails the standalone check of two parts of one call."""
        real = shutil.which("rtk")
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "rtk"
            # The kernel runs `rtk hook check --agent claude <command>`, so the command is the fifth argument.
            stub.write_text("#!/bin/sh\nif [ \"$1\" = hook ] && { [ \"$5\" = 'echo boom1' ] || [ \"$5\" = 'echo boom2' ]; }; then\n"
                            "  echo 'simulated failure' >&2; exit 3\nfi\nexec " + json.dumps(real) + " \"$@\"\n")
            stub.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ.get("PATH", "")}
            got = self.measure([call("c", "Bash", command="git status && echo boom1 && echo boom2"), result("c", "ok")],
                               env=env, rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["calls"], got["unknown_calls"]), (1, 1))
        self.assertEqual((got["eligible_parts"], got["ineligible_parts"], got["eligible_calls"], got["replayed_covered_parts"]), (0, 0, 0, 0))
        self.assertEqual(got["eligible_call_states"], M14_ROW)

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_b8_explicit_rtk_counts_even_when_replay_cannot_classify_the_call(self):
        """M-R3/M6c's zero counter reads the command's own parts, so a call that M-R1 cannot classify (here the hook's rewrite has fewer
        parts than the command) still shows an explicit rtk on an excluded command. At the base such a call counted nothing."""
        rows = [call("c", "Bash", command="rtk jq . a.json && git status"), rtk_rewrite("c", "rtk jq . a.json"), result("c", "ok")]
        got = self.measure(rows, rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["unknown_calls"], got["eligible_parts"]), (1, 0))
        self.assertEqual(got["explicit_rtk_on_excluded_or_sensitive"], 1)

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "Linux and RTK v0.50.0 required")
    def test_b8_status_is_incomplete_only_when_unknown_calls_exceed_five_percent_of_calls(self):
        """B8: M-R1 is not evaluable (status incomplete) when unknown calls exceed 5% of calls, and is evaluated on parsed parts otherwise.
        The comparison uses the integer counts (unknown * 20 > calls), and an aggregate applies it to its summed counts, not to its actors'
        statuses."""
        good = [[call("g%d" % i, "Bash", command="git status"), result("g%d" % i, "ok")] for i in range(19)]
        bad = [call("u", "Bash", command="echo \"open"), result("u", "x")]
        one = [row for rows in good for row in rows] + bad
        got = self.measure(one, rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["calls"], got["unknown_calls"], got["status"]), (20, 1, "measured"))
        self.assertEqual(got["unknown_call_share"], .05)
        two = [row for rows in good[:18] for row in rows] + bad + [call("v", "Bash", command="echo 'open"), result("v", "x")]
        got = self.measure(two, rtkCheck=True)["rtk_parts"]
        self.assertEqual((got["calls"], got["unknown_calls"], got["status"]), (20, 2, "incomplete"))
        self.assertEqual(got["unknown_call_share"], .1)
        agg = self.exports("cu.aggregateMeasurements(x.map((rows) => cu.measureTranscript(rows, { rtkCheck: true })))",
                           [bad, [row for rows in good for row in rows]])
        self.assertEqual((agg["rtk_parts"]["calls"], agg["rtk_parts"]["unknown_calls"], agg["rtk_parts"]["status"]), (20, 1, "measured"))
        self.assertEqual(agg["rtk_parts"]["unknown_call_share"], .05)
        alone = self.measure(bad, rtkCheck=True)["rtk_parts"]
        self.assertEqual(alone["status"], "incomplete")

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

    # PR-A item 6 on the transcript side (U2 design 6.2, amended by the count-only scans in evidence/artifacts/pra-u2-differential-20260929/
    # scans: final-returns, task-notifications and task-stop). A background task is a Bash backgroundTaskId, a Monitor or Workflow taskId,
    # or an async Agent's agentId; it ends with a <task-notification> whose <status> is completed, failed, killed or stopped, or with a
    # TaskStop result that names it; a Monitor event notification has no status and ends nothing.
    @staticmethod
    def final_rows(final_text, *, notify=None, ids="task-secret-1"):
        rows = [said("msg-1", [{"type": "tool_use", "id": "toolu_bg_1", "name": "Bash", "input": {"command": "sleep 9", "run_in_background": True}}]),
                {"type": "user", "timestamp": "2026-09-26T01:00:01Z", "toolUseResult": {"backgroundTaskId": ids},
                 "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_bg_1", "content": "Command running in background", "is_error": False}]}}]
        if notify:
            rows.append({"type": "user", "timestamp": "2026-09-26T01:00:02Z", "message": {"content":
                         "<task-notification>\n<task-id>%s</task-id>\n<status>%s</status>\n<summary>s</summary>\n</task-notification>" % (ids, notify)}})
        rows.append(said("msg-2", [{"type": "text", "text": final_text}], "2026-09-26T01:00:03Z"))
        return rows

    def test_final_return_reads_the_final_message_and_the_actors_background_tasks(self):
        none = {"final": None, "empty_text": None, "wait_notice": None, "background_started": None, "background_pending": None,
                "background_pending_with_events": None}
        cases = {"a wait notice with a task still running": (self.final_rows("Waiting for monitor"),
                     {"status": "measured", "final": "text", "empty_text": 0, "wait_notice": 1, "background_started": 1, "background_pending": 1,
                      "background_pending_with_events": 0}),
                 "an empty final text after the task completed": (self.final_rows("  ", notify="completed"),
                     {"status": "measured", "final": "text", "empty_text": 1, "wait_notice": 0, "background_started": 1, "background_pending": 0,
                      "background_pending_with_events": 0}),
                 "an answer after the task failed": (self.final_rows("The build failed at step 3.", notify="failed"),
                     {"status": "measured", "final": "text", "empty_text": 0, "wait_notice": 0, "background_started": 1, "background_pending": 0,
                      "background_pending_with_events": 0}),
                 # The Codex bridge's rows (and these helpers) carry no provider message id: no final message to read, not a zero.
                 "rows without a provider message": ([call("c", "Bash", command="ls"), result("c", "a")], {"status": "not_applicable", **none})}
        for name, (rows, want) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.measure(rows)["final_return"], want)
        # An actor with a row at or after until ran past the window end: its final return lies outside the window (the review's finding on
        # the sweep: measureTranscript itself records it, since the sweep aggregates measurements only).
        from datetime import datetime
        cut = datetime.fromisoformat("2026-09-26T01:00:02+00:00").timestamp() * 1000
        got = self.measure(self.final_rows("Done."), window={"since": 0, "until": cut})["final_return"]
        self.assertEqual(got, {"status": "unobserved", **none})

    def test_final_return_aggregate_counts_actors_and_the_sweep_stays_id_free(self):
        runs = [self.final_rows("Waiting for monitor"), self.final_rows("Done.", notify="completed"),
                self.final_rows("Done.", notify="stopped") + [said("msg-3", [{"type": "tool_use", "id": "toolu_x", "name": "StructuredOutput", "input": {}}],
                                                                    "2026-09-26T01:00:04Z")],
                [call("c", "Bash", command="ls"), result("c", "a")]]
        agg = self.exports("cu.aggregateMeasurements(x.map((rows) => cu.measureTranscript(rows))).final_return ?? null", runs)
        self.assertEqual(agg, {"measured": 3, "not_applicable": 1, "unobserved": 0, "by_final": {"text": 2, "tool_use": 1, "other": 0},
                               "empty_text": 0, "wait_notice": 1, "background_started": 3, "background_pending": 1,
                               "background_pending_with_events": 0, "actors_with_background_pending": 1})
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "root/session-a/subagents/agent-child.jsonl"
            child.parent.mkdir(parents=True)
            child.write_text("\n".join(json.dumps(r) for r in self.final_rows("Waiting for monitor")) + "\n")
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", str(Path(directory) / "root")], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            got = json.loads(p.stdout)
            self.assertEqual(got["groups"]["all"]["measurement"]["final_return"]["wait_notice"], 1)
            self.assertEqual(got["actors"][0]["measurement"]["final_return"]["background_pending"], 1)
            for secret in ("task-secret-1", "toolu_bg_1", "msg-1", "Waiting for monitor", directory):
                self.assertNotIn(secret, p.stdout)

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

    # Binding decision B9 and U2 correction 1: per-child usage reads usage.iterations[] of assistant messages. The shapes follow a count-only
    # scan of this host's transcripts (evidence/artifacts/pra-u2-differential-20260929) and the beta Messages API reference (BetaIterationsUsage):
    # `message` entries are the executor's and the top-level counters are their sum; an `advisor_message` entry carries its own model and is
    # never in the top-level counters (advisor tool doc, "Usage and billing"); on a row with several iterations the top-level cache_creation
    # object holds the first iteration's split, while each entry's own split adds up to its combined counter.
    @staticmethod
    def iteration(kind, i, o, cr, cc, split=None, model=None):
        it = {"type": kind, "input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc}
        if split is not None:
            it["cache_creation"] = {"ephemeral_5m_input_tokens": split[0], "ephemeral_1h_input_tokens": split[1]}
        if model is not None:
            it["model"] = model
        return it

    @staticmethod
    def usage_row(key, usage, content=None, timestamp="2026-09-26T01:00:00Z", model="claude-opus-5-5"):
        return {"type": "assistant", "timestamp": timestamp, "effort": "max",
                "message": {"id": key, "model": model, "usage": usage, **({"content": content} if content is not None else {})}}

    @staticmethod
    def advisor_blocks(key, result="advisor_redacted_result"):
        call = {"type": "server_tool_use", "id": key, "name": "advisor", "input": {}}
        if result is None:
            return [call]
        content = {"type": result, "encrypted_content": "opaque"} if result != "advisor_tool_result_error" else {"type": result, "error_code": "overloaded"}
        return [call, {"type": "advisor_tool_result", "tool_use_id": key, "content": content}]

    def advisor_usage(self, advisor_model="claude-fable-5-1"):
        """Executor iterations 100/10/0/50 (5m 50) and 150/20/100/60 (1h 60) around an advisor sub-inference 200/300/7/40 (1h 40); the
        top-level cache_creation object is the first iteration's split, as observed on 3,706 of 3,706 multi-iteration rows here."""
        it = self.iteration
        return {"input_tokens": 250, "output_tokens": 30, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 110,
                "cache_creation": {"ephemeral_5m_input_tokens": 50, "ephemeral_1h_input_tokens": 0},
                "speed": "standard", "service_tier": "standard", "inference_geo": "not_available",
                "iterations": [it("message", 100, 10, 0, 50, (50, 0)), it("advisor_message", 200, 300, 7, 40, (0, 40), model=advisor_model),
                               it("message", 150, 20, 100, 60, (0, 60))]}

    def test_usage_advisor_iterations_tier_fields_and_split(self):
        it, row = self.iteration, self.usage_row
        rows = [
            row("m1", {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 20, "cache_creation_input_tokens": 30,
                       "cache_creation": {"ephemeral_5m_input_tokens": 10, "ephemeral_1h_input_tokens": 20},
                       "speed": "standard", "service_tier": "standard", "inference_geo": "not_available",
                       "iterations": [it("message", 10, 5, 20, 30, (10, 20))]}),
            row("m2", {"input_tokens": 4, "output_tokens": 2, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 7}),  # combined only
            row("m3", {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                       "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                       "speed": "fast", "service_tier": "standard", "inference_geo": "global", "iterations": [it("message", 1, 1, 0, 0, (0, 0))]}),
            row("m4", {"input_tokens": 6, "output_tokens": 2, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 3,
                       "cache_creation": {"ephemeral_5m_input_tokens": 3, "ephemeral_1h_input_tokens": 0},
                       "speed": "standard", "service_tier": "priority", "inference_geo": "us"}),
            row("m5", self.advisor_usage(), content=self.advisor_blocks("srv1")),
        ]
        usage = self.measure(rows)["usage"]
        # controls: the combined counters and the deduplication by message id are unchanged
        self.assertEqual(usage["totals"], {"input_tokens": 271, "output_tokens": 40, "cache_read_input_tokens": 120, "cache_creation_input_tokens": 150})
        self.assertEqual([m["usage"]["cache_creation_input_tokens"] for m in usage["messages"]], [30, 7, 0, 3, 110])
        fields = ("cache_creation_5m", "cache_creation_1h", "speed", "service_tier", "inference_geo")
        self.assertEqual([tuple(m.get(k) for k in fields) for m in usage["messages"]], [
            (10, 20, "standard", "standard", "not_available"),
            (None, None, None, None, None),  # a record without the fields reads null, never 0
            (0, 0, "fast", "standard", "global"),
            (3, 0, "standard", "priority", "us"),
            (50, 60, "standard", "standard", "not_available")])  # the executor iterations' own splits, not the top-level object (50, 0)
        self.assertEqual(usage.get("advisor_iterations"), [{
            "message_ordinal": 5, "model": "claude-fable-5-1",
            "usage": {"input_tokens": 200, "output_tokens": 300, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 40},
            "cache_creation_5m": 0, "cache_creation_1h": 40, "speed": None, "service_tier": None, "inference_geo": None}])
        self.assertEqual(usage.get("advisor_totals"), {"input_tokens": 200, "output_tokens": 300, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 40})
        self.assertEqual(usage.get("totals_including_advisor"), {"input_tokens": 471, "output_tokens": 340, "cache_read_input_tokens": 127, "cache_creation_input_tokens": 190})
        self.assertTrue(usage["complete"])
        self.assertEqual(usage.get("iteration_issues"), {"unread_entries": {}, "inconsistent_messages": 0, "advisor_results_without_usage": 0,
                                                          "advisor_calls_without_result": 0})

    def test_usage_iterations_streamed_rows_and_adjacent_windows(self):
        """Streamed rows of one message id carry the iterations on the last rows only (observed: every multi-row id with iterations has them
        on its last rows): the counted row, the one with the largest counters, holds them. An advisor iteration counts in the window of the
        first row that carries it, so adjacent windows add up."""
        it, row = self.iteration, self.usage_row
        early = {"input_tokens": 100, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 50,
                 "cache_creation": {"ephemeral_5m_input_tokens": 50, "ephemeral_1h_input_tokens": 0}}
        streamed = [row("adv", early, content=self.advisor_blocks("srv1", result=None)),
                    row("adv", self.advisor_usage(), content=self.advisor_blocks("srv1")[1:])]
        got = self.measure(streamed)["usage"]
        self.assertEqual((len(got["messages"]), got["messages"][0]["usage"]["output_tokens"]), (1, 30))  # control
        self.assertEqual([a["model"] for a in got.get("advisor_iterations", [])], ["claude-fable-5-1"])
        self.assertTrue(got["complete"])
        from datetime import datetime
        split = datetime.fromisoformat("2026-09-26T01:30:00+00:00").timestamp() * 1000
        rows = [row("w", early, content=self.advisor_blocks("srv1", result=None), timestamp="2026-09-26T01:00:00Z"),
                row("w", self.advisor_usage(), content=self.advisor_blocks("srv1")[1:], timestamp="2026-09-26T02:00:00Z"),
                row("v", self.advisor_usage("claude-opus-5-5"), content=self.advisor_blocks("srv2"), timestamp="2026-09-26T01:00:00Z"),
                row("v", self.advisor_usage("claude-opus-5-5"), timestamp="2026-09-26T02:00:00Z")]
        a = self.measure(rows, window={"since": 0, "until": split})["usage"]
        b = self.measure(rows, window={"since": split, "until": split + 86400000})["usage"]
        self.assertEqual(a["totals"]["output_tokens"] + b["totals"]["output_tokens"], 60)  # control: counters partition
        self.assertEqual(([x["model"] for x in a.get("advisor_iterations", [])], [x["model"] for x in b.get("advisor_iterations", [])]),
                         (["claude-opus-5-5"], ["claude-fable-5-1"]))
        self.assertEqual(b["messages"][0]["cache_creation_5m"], 0)  # 50 at the late row less 50 at the early one
        self.assertEqual(b["messages"][0]["cache_creation_1h"], 60)
        # a window that ends between an advisor call and its result reads a call without a result, so the earlier window's usage is
        # incomplete (only an actor with a row at or after until, the sweep's ran_past_window_end, can show it); the later window is complete
        self.assertEqual((a["complete"], (a.get("iteration_issues") or {}).get("advisor_calls_without_result"), b["complete"]), (False, 1, True))

    def test_usage_is_incomplete_when_iterations_cannot_be_read(self):
        """usage.complete is false when a message carries iterations this reading cannot read or account for (B9), each reason counted
        in iteration_issues; an empty list, an advisor error result and the fields of a plain message keep it complete."""
        it, row = self.iteration, self.usage_row
        def top(i, o, cr, cc, iterations=None):
            u = {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc,
                 "cache_creation": {"ephemeral_5m_input_tokens": cc, "ephemeral_1h_input_tokens": 0}}
            if iterations is not None:
                u["iterations"] = iterations
            return u
        issues = {"unread_entries": {}, "inconsistent_messages": 0, "advisor_results_without_usage": 0, "advisor_calls_without_result": 0}
        cases = [
            ("an empty iterations list: the top level stands (4,211 rows here)", [row("e", top(5, 1, 0, 2, []))], True, issues),
            ("an advisor error result has no sub-inference usage", [row("x", top(5, 3, 0, 0, [it("message", 2, 1, 0, 0), it("message", 3, 2, 0, 0)]),
                                                                       content=self.advisor_blocks("srvx", "advisor_tool_result_error"))], True, issues),
            ("top-level counters that are not the sum of the message entries (1 message here)",
             [row("z", top(0, 0, 0, 0, [it("message", 9, 3, 0, 4, (4, 0))]))], False, {**issues, "inconsistent_messages": 1}),
            ("a fallback-served turn: the declined hop's message entry is outside the top level",
             [row("f", top(3, 1, 0, 0, [it("message", 5, 2, 0, 0, model="claude-opus-5-5"), it("fallback_message", 3, 1, 0, 0, model="claude-opus-4-8")]),
                  model="claude-opus-4-8")], False, {**issues, "unread_entries": {"fallback_message": 1}}),
            ("a compaction entry is not in the top level", [row("c", top(3, 1, 0, 0, [it("compaction", 50, 9, 0, 0), it("message", 3, 1, 0, 0)]))],
             False, {**issues, "unread_entries": {"compaction": 1}}),
            ("an entry that is not an object", [row("n", top(3, 1, 0, 0, [7, it("message", 3, 1, 0, 0)]))], False, {**issues, "unread_entries": {"(not_an_object)": 1}}),
            ("a message entry without a numeric counter", [row("s", top(3, 1, 0, 0, [{**it("message", 3, 1, 0, 0), "output_tokens": "1"}]))],
             False, {**issues, "unread_entries": {"message": 1}}),
            ("a successful advisor result without its advisor_message entry (105 message ids here)",
             [row("a", top(5, 1, 0, 0), content=self.advisor_blocks("srva"))], False, {**issues, "advisor_results_without_usage": 1}),
            ("an advisor call without a result: the sub-inference may have run (47 message ids here)",
             [row("b", top(3, 1, 0, 0, [it("message", 3, 1, 0, 0)]), content=self.advisor_blocks("srvb", result=None))],
             False, {**issues, "advisor_calls_without_result": 1}),
        ]
        for name, rows, complete, want in cases:
            with self.subTest(case=name):
                got = self.measure(rows)["usage"]
                self.assertEqual((got["complete"], got.get("iteration_issues")), (complete, want))
        # an advisor entry without a model cannot be priced
        got = self.measure([row("m", self.advisor_usage(), content=self.advisor_blocks("srvm"))])["usage"]
        self.assertTrue(got["complete"])  # control for the case below
        unnamed = self.advisor_usage()
        del unnamed["iterations"][1]["model"]
        got = self.measure([row("m", unnamed, content=self.advisor_blocks("srvm"))])["usage"]
        self.assertEqual((got["complete"], [a["model"] for a in got.get("advisor_iterations", [])]), (False, ["(unresolved)"]))

    def test_usage_iterations_output_is_id_free(self):
        """Must-stay control, added after the implementation (not failing-first): the sweep's stdout carries the advisor iteration it read
        but neither the message id nor the advisor call id (server tool ids) of the transcript."""
        rows = [self.usage_row("msg_private_adv", self.advisor_usage(), content=self.advisor_blocks("srvtoolu_private_1"))]
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "session/subagents/agent-child.jsonl"
            child.parent.mkdir(parents=True)
            child.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            p = subprocess.run(["node", str(MODULE), "--lanes-sweep", "--root", directory], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
        got = json.loads(p.stdout)
        self.assertEqual(len(got["actors"][0]["measurement"]["usage"]["advisor_iterations"]), 1)
        self.assertEqual(got["groups"]["all"]["measurement"]["usage"]["advisor_iteration_count"], 1)
        for secret in ["msg_private_adv", "srvtoolu_private_1", directory]:
            self.assertNotIn(secret, p.stdout)

    def test_usage_aggregate_sums_advisor_totals_and_iteration_issues(self):
        it, row = self.iteration, self.usage_row
        ok = [row("m5", self.advisor_usage(), content=self.advisor_blocks("srv1"))]
        unread = [row("c", {"input_tokens": 3, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                            "iterations": [it("compaction", 50, 9, 0, 0), it("message", 3, 1, 0, 0)]})]
        agg = self.exports("cu.aggregateMeasurements(x.map((r) => cu.measureTranscript(r)))", [ok, ok, unread])["usage"]
        self.assertEqual((agg["complete"], agg["totals"]["input_tokens"]), (False, 503))  # control: 250 + 250 + 3
        self.assertEqual(agg.get("advisor_totals"), {"input_tokens": 400, "output_tokens": 600, "cache_read_input_tokens": 14, "cache_creation_input_tokens": 80})
        self.assertEqual(agg.get("totals_including_advisor"), {"input_tokens": 903, "output_tokens": 661, "cache_read_input_tokens": 214, "cache_creation_input_tokens": 300})
        self.assertEqual(agg.get("advisor_iteration_count"), 2)
        self.assertEqual(agg.get("iteration_issues"), {"unread_entries": {"compaction": 1}, "inconsistent_messages": 0, "advisor_results_without_usage": 0,
                                                        "advisor_calls_without_result": 0})

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
