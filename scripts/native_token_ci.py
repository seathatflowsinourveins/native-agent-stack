#!/usr/bin/env python3
"""Real, scoped native-tool fixtures; no providers, account reads, LLM or embedding models.

Only sanitized fixture outputs survive cleanup. --install uses upstream commands
in a new temporary prefix; omission reuses explicit installed executables. Every
measured tool, including an MCP server that MCPorter spawns, runs from its resolved
absolute path, never a PATH lookup, so --install exercises exactly the copy it
fetched; only plumbing (git, grep, curl, sha256sum, tar, npm and the Node runtime of
npm-installed tools) comes from PATH. Each fixture runs the pinned tool's own CLI or
MCP commands (upstream native operations) and this repository's checks assert on what
they return: local integration evidence of upstream native operations. The one
upstream test is `rtk verify --require-all`, which runs the inline filter tests built
into RTK's release binary. Discriminating inputs make RTK, MarkItDown, ast-grep, Repomix
and TOON each produce output that a passthrough or a plain-text tool would not (a compacted
long git log, converted HTML elements, a multi-line structural match, bodies dropped by
compression, a tabular encoding); each such check is also held against the baseline it must
differ from (git's own log, the raw and the tag-stripped HTML, a line regex, the uncompressed
pack, the JSON input).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PINS = {"rtk": "0.50.0", "qmd": "2.8.3", "repomix": "1.18.1", "toon": "4.1.1",
        "mcporter": "0.14.1", "markitdown": "0.1.8", "ast-grep": "0.45.3",
        "ccusage": "20.0.24", "codebase-memory-mcp": "0.11.0", "headroom": "0.37.0",
        "jcodemunch-mcp": "1.108.319"}
# npm-kind: id -> registry package name, installed exactly like the existing three.
PACKAGES = {"qmd": "@tobilu/qmd", "repomix": "repomix", "toon": "@toon-format/cli",
            "mcporter": "mcporter", "ast-grep": "@ast-grep/cli", "ccusage": "ccusage"}
# codebase-memory-mcp keeps its rendezvous socket at
# $CBM_RUNTIME_DIR/cbm-daemon-<euid>/cbm-<16 hex>.sock and refuses a path that does not
# fit a Unix socket address (108 bytes on Linux, including the terminating NUL).
CBM_SOCKET_NAME = "cbm-" + "0" * 16 + ".sock"
UNIX_SOCKET_PATH_MAX = 107
# GitHub-release-tarball kind: id -> (base URL template, asset filename, path to the
# binary inside the extracted tree). Verified the same way as rtk's existing pin:
# a freshly fetched checksums.txt naming the exact asset once (verify_archive).
GITHUB_RELEASES = {
    "rtk": {"base": "https://github.com/rtk-ai/rtk/releases/download/v{version}",
            "asset": "rtk-x86_64-unknown-linux-musl.tar.gz", "binary": "rtk"},
    "codebase-memory-mcp": {
        "base": "https://github.com/DeusData/codebase-memory-mcp/releases/download/v{version}",
        "asset": "codebase-memory-mcp-linux-amd64.tar.gz", "binary": "codebase-memory-mcp"},
}
# uv-tool kind: id -> PyPI distribution spec (differs from id for headroom's [mcp] extra).
UV_TOOLS = {"markitdown": "markitdown", "headroom": "headroom-ai[mcp]",
            "jcodemunch-mcp": "jcodemunch-mcp"}
# uv itself is plumbing, not one of the measured tools: pinned and hash-verified the
# same way as adoption/pins-linux-x86_64.json's own uv 0.12.17 entry, so uv-tool-kind
# installs never depend on whatever the runner happens to have on PATH.
UV_PIN = {"version": "0.12.17",
          "url": "https://github.com/astral-sh/uv/releases/download/0.12.17/uv-x86_64-unknown-linux-gnu.tar.gz",
          "sha256": "fa82fd8dde8e8eefdecada6aa0889666556cfceb690d06e0c3bca49eb3070a63"}
# Harness, workflow, pin manifest and fixture inputs whose bytes each receipt records.
SOURCE_FILES = ("scripts/native_token_ci.py", ".github/workflows/native-token-e2e.yml",
                "manifests/stack.json", "fixtures/rag-note.md", "fixtures/records.json",
                "fixtures/before.py", "fixtures/after.py", "fixtures/greeting.html",
                "fixtures/headroom-note.txt", "fixtures/headroom-records.json",
                "fixtures/ccusage-synthetic-claude/projects/native-ci-synthetic-project/synthetic-session.jsonl",
                "fixtures/ast_grep_calls.py", "fixtures/ast_grep_shell_calls.py",
                "fixtures/markitdown-multi-element.html")
# Frozen ast-grep input and outcome (1-based lines): the two real subprocess.run calls,
# one written with a space before its argument list, versus a plain-text grep for the
# call prefix, which finds the first call plus a comment and a string literal instead.
AST_GREP_FIXTURE = "fixtures/ast_grep_calls.py"
AST_GREP_CALL_LINES = [9, 13]
AST_GREP_TEXT_LINES = [9, 16, 17]
# A pattern no line-based search expresses: subprocess.run calls with a shell=True keyword argument
# anywhere in their argument list. Frozen outcome as 1-based [start, end] lines: the one-line call
# and the call spread over lines 12-16. The closest single-line regex instead finds the one-line
# call, a comment and a string (lines 8, 24, 31) and misses the spread-out call.
AST_GREP_SHELL_FIXTURE = "fixtures/ast_grep_shell_calls.py"
AST_GREP_SHELL_PATTERN = "subprocess.run($$$, shell=True, $$$)"
AST_GREP_SHELL_CALL_RANGES = [[8, 8], [12, 16]]
AST_GREP_SHELL_TEXT_REGEX = r"subprocess\.run\(.*shell=True"
AST_GREP_SHELL_TEXT_LINES = [8, 24, 31]
# RTK 0.50.0's `git log` filter (src/cmds/git/git_cmd.rs, run_log and filter_log_output) prints one
# `%h %s (%ar) <%an>` header per commit and at most three non-empty body lines, drops Signed-off-by
# and Co-authored-by trailers, ends a longer body with `[+N lines omitted]`, and without -N shows the
# ten newest commits. Each fixture commit has five body lines and both trailers.
RTK_LOG_COMMITS = 12
RTK_LOG_DEFAULT_LIMIT = 10
# MarkItDown input with one of each element its HTML converter turns into Markdown, plus a script,
# a style sheet and a comment whose text must not survive conversion. The markers are letters
# only: markdownify escapes Markdown characters such as `_`, so `NATIVE_CI_X` leaked into a
# paragraph came out as `NATIVE\_CI\_X` and a literal search missed it (a 2026-09-26 control).
MARKITDOWN_MULTI_ELEMENT = "fixtures/markitdown-multi-element.html"
MARKITDOWN_HIDDEN_TEXT = ("NativeCiScriptBody", "NativeCiStyleBody", "NativeCiHtmlComment")
# TOON 4.1.1 (its encoder is bundled in the CLI, no runtime dependency) writes fixtures/records.json,
# a uniform array of objects, as one tabular block: a header naming the length and fields, then rows.
TOON_TABULAR_RECORDS = "items[2]{name,enabled,count}:\n  alpha,true,2\n  beta,false,3"
# Headroom inputs. The records are a compact JSON array of objects, the input its SmartCrusher
# compresses (upstream README: "SmartCrusher — universal JSON: arrays of dicts"). The note is
# below compress()'s default min_tokens_to_compress (250), which Headroom stores unchanged.
HEADROOM_RECORDS = "fixtures/headroom-records.json"
HEADROOM_NOTE = "fixtures/headroom-note.txt"
# Frozen jCodeMunch source-recovery oracle: the identity, 1-based bounds and complete source of
# the function in fixtures/after.py, taken from the committed fixture, never from a response.
JCODEMUNCH_SYMBOL = {"id": "fixtures/after.py::greeting#function", "kind": "function", "name": "greeting",
                     "file": "fixtures/after.py", "line": 1, "end_line": 2}
JCODEMUNCH_SYMBOL_SOURCE = 'def greeting(name):\n    return "Hello, " + name + "!"'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def signal_group(process: subprocess.Popen, signum: int) -> None:
    """Signal a timed-out command's process group unless it has already finished.

    The group can finish between the timeout and the signal: Linux then reports ESRCH once it is
    reaped, and macOS reports EPERM while its members are unreaped zombies (XNU killpg1 skips
    them). EPERM while the leader still runs is a real refusal and is raised."""
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            raise


def verify_safe_tar_members(archive: Path) -> None:
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            path = Path(member.name)
            require(not path.is_absolute() and ".." not in path.parts
                    and (member.isfile() or member.isdir()), "Unsafe archive member")


def verify_archive(archive: Path, checksums: str) -> None:
    matches = [line.split()[0] for line in checksums.splitlines()
               if len(line.split()) == 2 and line.split()[1].lstrip("*") == archive.name]
    require(len(matches) == 1, "Publisher checksums must contain the exact asset once")
    require(re.fullmatch(r"[0-9a-fA-F]{64}", matches[0]) is not None,
            "Publisher checksum is not SHA-256")
    require(digest(archive.read_bytes()) == matches[0].lower(), "Archive checksum mismatch")
    verify_safe_tar_members(archive)


def verify_pack(xml: str, originals: dict[str, str]) -> None:
    files = ET.fromstring(xml).findall(".//file")
    require(len(files) == len(originals), "Pack has missing or extra files")
    actual = {item.attrib.get("path"): item.text or "" for item in files}
    require(set(actual) == set(originals), "Pack file selection differs from the explicit inputs")
    for path, content in originals.items():
        # XML wrapper newlines are formatting; every source character within them matters.
        require(actual[path].strip("\n") == content.strip("\n"),
                f"Packed source differs: {path}")


def verify_qmd_document(response: str, uri: str, docid: str, body: str) -> None:
    # Pinned `get --no-line-numbers` framing: canonical URI/docid, separator,
    # then the original body plus console.log's one terminating newline.
    canonical_uri = uri.partition("?")[0]
    require(re.fullmatch(r"#[0-9a-f]+", docid) is not None, "QMD search docid is malformed")
    expected = f"{canonical_uri}  {docid}\n---\n\n{body}\n"
    require(response == expected, "QMD document identity/body differs from source")


def verify_json_roundtrip(original: str, recovered: str) -> None:
    # Preserve JSON types, including bool versus int, while ignoring object key order.
    def canonical(value: str) -> str:
        return json.dumps(json.loads(value), sort_keys=True, ensure_ascii=False)
    require(canonical(original) == canonical(recovered), "Decoded JSON values/types differ")


def stdio_command(executable: str, *arguments: str) -> str:
    """Build one MCPorter --stdio value. MCPorter splits it like a POSIX shell, honoring
    quotes, and spawns the first word through the child PATH, so the resolved absolute
    executable is quoted in rather than left to a PATH lookup."""
    return " ".join(shlex.quote(part) for part in (executable, *arguments))


def require_cbm_socket_fits(runtime_parent: str) -> None:
    socket = f"{runtime_parent}/cbm-daemon-{os.geteuid()}/{CBM_SOCKET_NAME}"
    require(len(os.fsencode(socket)) <= UNIX_SOCKET_PATH_MAX,
            "codebase-memory-mcp rendezvous socket path exceeds the Unix socket address limit; "
            "set TMPDIR to a shorter directory")


def cbm_listed_total(stdout: str) -> int:
    """Read list_projects' `total: N` line; its CLI returns this listing as text only."""
    text = json.loads(stdout)["content"][0]["text"]
    totals = re.findall(r"^total: (0|[1-9][0-9]*)$", text, re.MULTILINE)
    require(len(totals) == 1, "codebase-memory-mcp list_projects returned no single total line")
    return int(totals[0])


def rtk_inline_tests_passed(stdout: str) -> bool:
    """`rtk verify` prints one `P/T tests passed` line for RTK's built-in filter tests."""
    totals = re.findall(r"^([0-9]+)/([0-9]+) tests passed$", stdout, re.MULTILINE)
    return len(totals) == 1 and totals[0][0] == totals[0][1] and int(totals[0][1]) > 0


def headroom_compressed(result: dict, original: str) -> bool:
    """headroom_compress really compressed: a retrieval hash, a changed text, fewer tokens by the
    reported saving and a SmartCrusher route, not `router:noop` or a passthrough."""
    before, after = result.get("original_tokens"), result.get("compressed_tokens")
    return (bool(result.get("hash")) and isinstance(result.get("compressed"), str)
            and result["compressed"] != original and type(before) is int and type(after) is int
            and 0 < after < before and result.get("tokens_saved") == before - after
            and any(str(route).startswith("router:smart_crusher:") for route in result.get("transforms") or []))


def jcodemunch_symbol_exact(response: dict) -> bool:
    """get_symbol_source returned the frozen symbol: its identity, bounds and complete source."""
    return (all(response.get(key) == value for key, value in JCODEMUNCH_SYMBOL.items())
            and response.get("source") == JCODEMUNCH_SYMBOL_SOURCE)


def jcodemunch_index_file(repo: str) -> str:
    """Name of the SQLite index jcodemunch-mcp 1.108.319 writes for an `owner/name` repo id:
    storage/sqlite_store.py `_db_path` is `{base_path}/{owner}-{name}.db`, each part
    sanitized by `_safe_repo_component` (characters outside [A-Za-z0-9._-] become one
    hyphen, outer hyphens stripped). The harness never writes this file itself."""
    parts = repo.split("/")
    require(len(parts) == 2, "jcodemunch repo id is not owner/name")
    safe = [re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9._-]", "-", part)).strip("-") for part in parts]
    require(all(part not in {"", ".", ".."} for part in safe), "jcodemunch repo id has an empty part")
    return f"{safe[0]}-{safe[1]}.db"


def rtk_log_message(number: int) -> str:
    """Message of long-log fixture commit `number`: a subject, five body lines and two trailers."""
    details = "".join(f"Detail {line} of change {number:03d}: public synthetic text.\n" for line in range(1, 6))
    return (f"CI_LOG_{number:03d} synthetic change\n\n{details}\n"
            "Signed-off-by: Native CI Fixture <ci@example.invalid>\n"
            "Co-authored-by: Native CI Fixture <ci@example.invalid>\n")


def rtk_compacted_log(output: str, newest: int, count: int) -> bool:
    """`output` is exactly RTK's compact log of fixture commits newest, newest - 1, ... (`count` of
    them): each commit's header, its first three body lines and `[+2 lines omitted]`, nothing else.
    The abbreviated hash and the relative date are the only parts left open."""
    blocks = [rf"[0-9a-f]{{7,40}} CI_LOG_{number:03d} synthetic change \([^()\n]+\) <Native CI Fixture>"
              + "".join(rf"\n  Detail {line} of change {number:03d}: public synthetic text\." for line in (1, 2, 3))
              + r"\n  \[\+2 lines omitted\]" for number in range(newest, newest - count, -1)]
    return re.fullmatch("\n".join(blocks) + "\n", output) is not None


def rtk_ledger_delta(before: dict, after: dict) -> dict[str, int]:
    """Change in the `rtk gain --format json` summary counters between two readings."""
    return {key: after["summary"][key] - before["summary"][key]
            for key in ("total_commands", "total_input", "total_output", "total_saved")}


def markdown_elements(text: str) -> dict[str, bool]:
    """Which elements of MARKITDOWN_MULTI_ELEMENT `text` holds as Markdown. The bullet, emphasis and
    code-block spellings that markdownify can emit are all accepted; HTML markup never is."""
    lines = [item.rstrip() for item in text.splitlines()]

    def line(pattern: str) -> bool:
        return any(re.fullmatch(pattern, item) for item in lines)

    def row(*cells: str) -> str:
        return r"\|\s*" + r"\s*\|\s*".join(re.escape(cell) for cell in cells) + r"\s*\|"

    fences = [index for index, item in enumerate(lines) if re.fullmatch(r"(?:```|~~~)\S*", item)]
    code = ["rtk git log -20", "markitdown page.html"]
    return {
        "headings": line(r"# Release checklist") and line(r"## Pinned tools") and line(r"### Steps"),
        "table": (line(row("Tool", "Version", "Check")) and line(r"\|(?:\s*:?-{3,}:?\s*\|){3}")
                  and line(row("rtk", "0.50.0", "inline filter tests"))
                  and line(row("markitdown", "0.1.8", "structure oracle"))
                  and line(row("ast-grep", "0.45.3", "call-site oracle"))),
        "ordered_list": (line(r"1\. Install into a fresh prefix") and line(r"2\. Run each fixture")
                         and line(r"3\. Keep only sanitized output")),
        "nested_list": (line(r"[*+-] Record every command") and line(r" {2,}[*+-] including failures")
                        and line(r"[*+-] Never read account state")),
        "link": "[upgrade guide](https://example.invalid/guide)" in text,
        "emphasis": "**pinned**" in text and re.search(r"(?<![*_])[*_]scoped[*_](?![*_])", text) is not None,
        "blockquote": line(r"> Evidence is not authority\."),
        "code_block": ((len(fences) >= 2 and lines[fences[0] + 1:fences[1]] == code)
                       or all(line(" {4}" + re.escape(item)) for item in code)),
        "inline_code_and_entity": "Tom & Jerry use `--offline` mode." in text,
        "image": "![Pipeline diagram](diagram.png)" in text,
    }


class _TextOnly(HTMLParser):
    """Collects every text node of a document: the output of plain tag stripping."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def tag_stripped_text(html: str) -> str:
    parser = _TextOnly()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def pack_file_texts(xml: str) -> dict[str, str]:
    """Each packed file's text in a Repomix XML pack, keyed by its path."""
    return {item.attrib.get("path"): item.text or "" for item in ET.fromstring(xml).findall(".//file")}


class Run:
    def __init__(self, output: Path, work: Path):
        self.output, self.work = output, work
        self.tools: dict[str, str] = {}
        # main() overrides this from --install; direct construction (e.g. tests) defaults to
        # resolving dependencies (mcporter) from PATH rather than installing a fresh copy.
        self.fresh_install = False
        # First failure to provide MCPorter, repeated to every later fixture that needs it.
        self.mcporter_error: str | None = None
        self.report = {
            "schema_version": 1, "kind": "native_cli_e2e", "evidence_class": "local_integration",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "pins": PINS, "status": "running", "commands": [], "checks": [],
            "failures": [], "artifacts": {},
            "scope": "Fresh Linux fixture state; selected upstream CLIs, no native model task",
            "limits": ["Not a new-PC, native Codex/Claude, GPU or provider acceptance",
                       "Local integration evidence of upstream native operations: each fixture runs the pinned "
                       "tool's own CLI or MCP commands and this repository's checks assert on their output; the "
                       "one upstream test is rtk verify --require-all (RTK's inline filter tests, built into its "
                       "release binary)",
                       "No LLM or embedding model: MarkItDown runs the ONNX file-type classifier bundled in its "
                       "magika dependency, and Headroom's token counter downloads tiktoken's o200k_base "
                       "vocabulary into TMPDIR at run time",
                       "Top-level package pins only: npm and uv tool (PyPI) dependencies resolve at "
                       "installation without a lockfile or pinned hashes; the uv archive is the only "
                       "download checked against a hash pinned in this harness",
                       "RTK counters are fixture-local estimates, not provider savings",
                       "ccusage reads a committed synthetic usage log, not account history",
                       "No token-saving requirement: fidelity may need the larger representation",
                       "Retained text replaces local paths; raw byte hashes precede sanitization"],
        }
        # A fresh allowlist excludes tokens, provider routing and inherited tool-state overrides.
        self.env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
        self.env.update({
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "TERM": "dumb",
            "CI": "true", "NO_COLOR": "1", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
            "XDG_CONFIG_HOME": str(work / "config"), "XDG_CACHE_HOME": str(work / "cache"),
            "XDG_DATA_HOME": str(work / "data"), "XDG_STATE_HOME": str(work / "state"),
            "TMPDIR": str(work / "tmp"), "RTK_DB_PATH": str(work / "data/rtk/history.db"),
            "RTK_TELEMETRY_DISABLED": "1",
            "QMD_CONFIG_DIR": str(work / "config/qmd"), "QMD_FORCE_CPU": "1",
            "INDEX_PATH": str(work / "cache/qmd/native-ci-docs.sqlite"),
            "NODE_LLAMA_CPP_SKIP_DOWNLOAD": "true",
            "NPM_CONFIG_CACHE": str(work / "npm-cache"),
            "NPM_CONFIG_USERCONFIG": str(work / "empty.npmrc"),
            "NPM_CONFIG_GLOBALCONFIG": str(work / "empty-global.npmrc"),
            "MCP_AUTO_OPEN_ENABLED": "false",
            # UV_TOOL_BIN_DIR stays off PATH: commands use the absolute paths install() returns.
            "UV_TOOL_DIR": str(work / "data/uv-tools"), "UV_TOOL_BIN_DIR": str(work / "install/uv-tools-bin"),
            # State these tools otherwise keep under the preserved native HOME, or, for
            # codebase-memory-mcp's rendezvous, in the account-wide /tmp/cbm-daemon-<uid>,
            # moved into this run's directory with each tool's documented setting.
            "HEADROOM_OFFLINE": "1", "DO_NOT_TRACK": "1",
            "HEADROOM_WORKSPACE_DIR": str(work / "data/headroom"),
            "HEADROOM_CONFIG_DIR": str(work / "config/headroom"),
            "JCODEMUNCH_SHARE_SAVINGS": "0", "CODE_INDEX_PATH": str(work / "cache/jcodemunch"),
            "CBM_CACHE_DIR": str(work / "cache/codebase-memory-mcp"), "CBM_RUNTIME_DIR": str(work / "cbm"),
            "MCPORTER_DAEMON_DIR": str(work / "mcp"),
            "CLAUDE_CONFIG_DIR": str(ROOT / "fixtures/ccusage-synthetic-claude"),
        })
        for folder in ("config", "cache/qmd", "cache/jcodemunch", "data/rtk", "data/uv-tools",
                       "data/headroom", "config/headroom", "config/mcporter",
                       "state", "tmp", "config/qmd", "install", "install/uv-tools-bin"):
            (work / folder).mkdir(parents=True, exist_ok=True)
        for private in ("cbm", "cache/codebase-memory-mcp", "mcp"):
            (work / private).mkdir(mode=0o700, parents=True, exist_ok=True)
        (work / "empty.npmrc").write_text("")
        (work / "empty-global.npmrc").write_text("")
        # An explicit MCPorter config is the only layer it reads; `imports: []` stops it from
        # reading editor/client MCP configs, which it otherwise imports by default.
        self.mcporter_config = work / "config/mcporter/mcporter.json"
        self.mcporter_config.write_text(json.dumps({"mcpServers": {}, "imports": []}) + "\n")
        self.report["state_observations"] = {}
        self.report["environment"] = {key: self.clean(value) for key, value in self.env.items()
                                      if key not in {"HOME", "PATH"}}
        self.report["native_home_preserved"] = self.env.get("HOME") == os.environ.get("HOME")
        # {path, sha256} objects, not a map keyed by path: a key such as
        # "scripts/native_token_ci.py" beside a 64-hex value is the keyed-credential shape
        # gitleaks' generic-api-key rule reports ("token" in the key), and receipts are
        # committed as evidence under the repository's secret scan.
        self.report["source_files"] = [{"path": name, "sha256": digest((ROOT / name).read_bytes())}
                                       for name in SOURCE_FILES]
        self.flush()

    def clean(self, value: str) -> str:
        replacements = [(str(self.work), "<WORK>"), (str(ROOT), "<CHECKOUT>"),
                        (str(self.output), "<RESULTS>")]
        replacements += [(path, f"<TOOL:{name}>") for name, path in self.tools.items()]
        if os.environ.get("HOME"):
            replacements.append((os.environ["HOME"], "<NATIVE_HOME>"))
        for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            value = value.replace(source, target)
        return value

    def flush(self) -> None:
        (self.output / "receipt.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def command(self, label: str, argv: list[str], cwd: Path | None = None,
                nonzero: bool = False, timeout: int = 90) -> str:
        start = time.monotonic()
        timed_out = False
        process = subprocess.Popen(argv, cwd=cwd or self.work, env=self.env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            signal_group(process, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                signal_group(process, signal.SIGKILL)
                stdout, stderr = process.communicate()
        entry = {"label": label, "argv": [self.clean(arg) for arg in argv],
                 "cwd": self.clean(str(cwd or self.work)), "exit_code": process.returncode,
                 "expected_exit": "nonzero" if nonzero else "zero", "timed_out": timed_out,
                 "elapsed_seconds": round(time.monotonic() - start, 3),
                 "stdout_raw_sha256": digest(stdout), "stderr_raw_sha256": digest(stderr),
                 "stdout": self.clean(stdout.decode("utf-8", errors="replace")),
                 "stderr": self.clean(stderr.decode("utf-8", errors="replace"))}
        self.report["commands"].append(entry)
        self.flush()
        require(not timed_out, f"{label}: timed out")
        require((process.returncode != 0) if nonzero else (process.returncode == 0),
                f"{label}: unexpected exit {process.returncode}")
        return stdout.decode("utf-8")

    def check(self, label: str, condition: bool) -> None:
        self.report["checks"].append({"label": label, "passed": bool(condition)})
        self.flush()
        require(condition, label)

    def artifact(self, name: str, source: Path) -> None:
        raw = source.read_bytes()
        public = self.clean(raw.decode("utf-8")).encode()
        (self.output / name).write_bytes(public)
        self.report["artifacts"][name] = {"raw_sha256": digest(raw),
                                           "retained_sha256": digest(public)}

    def install(self, name: str) -> str:
        prefix = self.work / "install" / name
        prefix.mkdir()
        if name in PACKAGES:
            self.command(f"install-{name}", ["npm", "install", "--global", "--prefix",
                         str(prefix), "--registry=https://registry.npmjs.org", "--no-audit",
                         "--no-fund", f"{PACKAGES[name]}@{PINS[name]}"], timeout=360)
            self.command(f"installed-metadata-{name}", ["npm", "list", "--global", "--prefix",
                         str(prefix), "--depth=0", "--json"])
            return str(prefix / "bin" / name)
        if name in GITHUB_RELEASES:
            release = GITHUB_RELEASES[name]
            asset, base = release["asset"], release["base"].format(version=PINS[name])
            for filename in (asset, "checksums.txt"):
                self.command(f"download-{name}-{filename}", ["curl", "--disable", "--fail", "--silent",
                             "--show-error", "--location", "--output", str(prefix / filename),
                             f"{base}/{filename}"])
            archive = prefix / asset
            checksums = (prefix / "checksums.txt").read_text()
            verify_archive(archive, checksums)
            # One key per tool; "rtk_archive_sha256" is also what retained reproductions read
            # (evidence/artifacts/sota-refresh-20260925/rtk/native_token_ci_rtk_only.py).
            self.report[f"{name.replace('-', '_')}_archive_sha256"] = digest(archive.read_bytes())
            self.command(f"{name}-publisher-checksum", ["sha256sum", "--check", "--ignore-missing",
                                                        "checksums.txt"], cwd=prefix)
            self.command(f"{name}-archive-members", ["tar", "-tf", asset], cwd=prefix)
            self.command(f"{name}-extract", ["tar", "-xf", asset], cwd=prefix)
            return str(prefix / release["binary"])
        if name in UV_TOOLS:
            uv = self.ensure_uv()
            self.command(f"install-{name}", [uv, "tool", "install", "--python", "3.13",
                         f"{UV_TOOLS[name]}=={PINS[name]}"], timeout=360)
            self.command(f"installed-metadata-{name}", [uv, "tool", "list"])
            return str(Path(self.env["UV_TOOL_BIN_DIR"]) / name)
        raise AssertionError(f"No install method registered for {name}")

    def ensure_uv(self) -> str:
        """Fetch the pinned upstream uv binary once per run; uv-tool-kind installs then use it.

        uv is plumbing to reach markitdown/headroom/jcodemunch-mcp, not one of the measured
        tools, so it is verified the same way adoption/bootstrap-linux.sh's own fetch() does:
        compare the download against this pin's own recorded sha256 (already independently
        matched against astral-sh/uv's release in adoption/pins-linux-x86_64.json) via a real
        sha256sum invocation, rather than re-fetching a release sidecar for a dependency."""
        if "uv" in self.tools:
            return self.tools["uv"]
        prefix = self.work / "install" / "_uv"
        prefix.mkdir()
        archive = prefix / "uv.tar.gz"
        self.command("download-uv", ["curl", "--disable", "--fail", "--silent", "--show-error",
                     "--location", "--output", str(archive), UV_PIN["url"]])
        (prefix / "uv.tar.gz.sha256").write_text(f"{UV_PIN['sha256']}  uv.tar.gz\n")
        self.command("uv-pinned-checksum", ["sha256sum", "--check", "--strict", "uv.tar.gz.sha256"],
                     cwd=prefix)
        verify_safe_tar_members(archive)
        self.command("uv-extract", ["tar", "-xf", "uv.tar.gz"], cwd=prefix)
        uv = prefix / "uv-x86_64-unknown-linux-gnu" / "uv"
        require(uv.is_file() and os.access(uv, os.X_OK), "uv archive is missing its uv executable")
        self.tools["uv"] = str(uv)
        return self.tools["uv"]

    def observe(self, label: str, directory: Path) -> list[str]:
        """Record what a tool wrote under a redirected state directory (directories end in /)."""
        found = sorted(path.relative_to(directory).as_posix() + ("/" if path.is_dir() else "")
                       for path in directory.rglob("*"))
        self.report["state_observations"][label] = found
        self.flush()
        return found


def rtk_fixture(run: Run) -> None:
    repo = run.work / "git-fixture"
    repo.mkdir()
    run.command("git-init", ["git", "init", "--quiet"], repo)
    for key, value in (("user.name", "Native CI Fixture"), ("user.email", "ci@example.invalid")):
        run.command(f"git-{key}", ["git", "config", key, value], repo)
    for number, message in enumerate(("CI_BASELINE_FIXED", "CI_FOLLOWUP_FIXED")):
        (repo / "selected.txt").write_text(f"public fixture revision {number}\n")
        run.command(f"git-add-{number}", ["git", "add", "selected.txt"], repo)
        run.command(f"git-commit-{number}", ["git", "commit", "--quiet", "-m", message], repo)
    tool = run.tools["rtk"]
    before = json.loads(run.command("rtk-gain-before", [tool, "gain", "--format", "json"], repo))
    run.check("rtk-fixture-ledger-starts-empty", before["summary"]["total_commands"] == 0)
    baseline = run.command("git-log-baseline", ["git", "log", "-2"], repo)
    compact = run.command("rtk-git-log", [tool, "git", "log", "-2"], repo)
    run.check("rtk-preserves-both-commit-subjects",
              all(message in compact for message in ("CI_BASELINE_FIXED", "CI_FOLLOWUP_FIXED")))
    recovered = run.command("rtk-raw-recovery", [tool, "proxy", "git", "log", "-2"], repo)
    run.check("rtk-proxy-exact-stdout", recovered == baseline)
    run.command("rtk-upstream-error", [tool, "proxy", "git", "rev-parse", "--verify",
                                     "refs/heads/ci-missing-ref"], repo, nonzero=True)
    after = json.loads(run.command("rtk-gain-after", [tool, "gain", "--format", "json"], repo))
    run.check("rtk-retained-fixture-database", Path(run.env["RTK_DB_PATH"]).is_file())
    run.check("rtk-native-statistics-returned", isinstance(after, dict) and bool(after))
    run.check("rtk-three-command-counter-increment", after["summary"]["total_commands"] == 3)
    # Upstream tests, unlike the checks above: `rtk verify` runs the inline tests of RTK's built-in
    # TOML filters, compiled into the release binary, and --require-all (its CI mode) also fails
    # when a filter has none. Its hook-integrity step reads $CLAUDE_CONFIG_DIR, here the committed
    # fixture directory, finds no hook and skips, so no client configuration is consulted.
    verify = run.command("rtk-verify-inline-filter-tests", [tool, "verify", "--require-all"], repo)
    run.check("rtk-upstream-inline-filter-tests-pass", rtk_inline_tests_passed(verify))


def rtk_long_log_fixture(run: Run) -> None:
    """RTK's git log filter on a history long enough to differ from git's own output: every commit
    compacted, a smaller output than raw git, the default ten-commit window, an exact proxy
    passthrough, and a ledger saving recorded for the filtered call only."""
    repo, messages = run.work / "git-long-fixture", run.work / "git-long-messages"
    repo.mkdir()
    messages.mkdir()
    run.command("git-long-init", ["git", "init", "--quiet"], repo)
    for key, value in (("user.name", "Native CI Fixture"), ("user.email", "ci@example.invalid")):
        run.command(f"git-long-{key}", ["git", "config", key, value], repo)
    for number in range(RTK_LOG_COMMITS):
        message = messages / f"{number:03d}.txt"
        message.write_text(rtk_log_message(number))
        run.command(f"git-long-commit-{number:03d}", ["git", "commit", "--quiet", "--allow-empty",
                                                     "--file", str(message)], repo)
    tool, count, newest = run.tools["rtk"], f"-{RTK_LOG_COMMITS}", RTK_LOG_COMMITS - 1
    raw = run.command("git-long-log-baseline", ["git", "log", count], repo)
    before = json.loads(run.command("rtk-long-gain-before", [tool, "gain", "--format", "json"], repo))
    compact = run.command("rtk-long-git-log", [tool, "git", "log", count], repo)
    filtered = json.loads(run.command("rtk-long-gain-after-filter", [tool, "gain", "--format", "json"], repo))
    proxied = run.command("rtk-long-proxy-git-log", [tool, "proxy", "git", "log", count], repo)
    after = json.loads(run.command("rtk-long-gain-after-proxy", [tool, "gain", "--format", "json"], repo))
    default = run.command("rtk-long-default-git-log", [tool, "git", "log"], repo)
    saving, passthrough = rtk_ledger_delta(before, filtered), rtk_ledger_delta(filtered, after)
    run.report["rtk_long_log"] = {"commits": RTK_LOG_COMMITS, "raw_bytes": len(raw.encode()),
                                  "rtk_bytes": len(compact.encode()), "default_bytes": len(default.encode()),
                                  "ledger_filter_delta": saving, "ledger_proxy_delta": passthrough}
    run.flush()
    run.check("rtk-long-log-compacts-every-commit", rtk_compacted_log(compact, newest, RTK_LOG_COMMITS))
    run.check("rtk-long-log-raw-baseline-rejected-and-larger",
              not rtk_compacted_log(raw, newest, RTK_LOG_COMMITS) and len(compact.encode()) < len(raw.encode()))
    run.check("rtk-long-log-proxy-exact-stdout", proxied == raw)
    run.check("rtk-long-log-ledger-records-the-filter-saving",
              saving["total_commands"] == 1 and saving["total_saved"] > 0
              and saving["total_saved"] == saving["total_input"] - saving["total_output"])
    run.check("rtk-long-log-ledger-records-no-proxy-saving",
              passthrough["total_commands"] == 1 and passthrough["total_saved"] == 0
              and passthrough["total_input"] == passthrough["total_output"])
    run.check("rtk-long-log-default-window-ten-newest-commits",
              rtk_compacted_log(default, newest, RTK_LOG_DEFAULT_LIMIT))


def qmd_fixture(run: Run) -> None:
    docs = run.work / "docs-fixture"
    docs.mkdir()
    original = (ROOT / "fixtures/rag-note.md").read_text()
    source = docs / "rag-note.md"
    source.write_text(original)
    cli = [run.tools["qmd"], "--index", "native-ci-docs"]
    run.command("qmd-collection-add", cli + ["collection", "add", str(docs), "--name",
                                           "native-ci-docs", "--mask", "*.md"])
    found = json.loads(run.command("qmd-bm25-search", cli + ["search", "Nemotron", "-c",
                                        "native-ci-docs", "-n", "1", "--json"]))
    require(isinstance(found, list) and len(found) == 1, "QMD search must return one fixture")
    uri = found[0]["file"]
    run.check("qmd-returned-fixture-uri",
              uri == "qmd://native-ci-docs/rag-note.md?index=native-ci-docs")
    first = run.command("qmd-get-fresh-process", cli + ["get", uri, "--no-line-numbers"])
    verify_qmd_document(first, uri, found[0]["docid"], original)
    run.check("qmd-reopened-exact-document-content", True)
    updated = original + "\nAmberquartz persistence marker: 19.\n"
    source.write_text(updated)
    run.command("qmd-update", cli + ["update"])
    found = json.loads(run.command("qmd-search-updated-document", cli + ["search", "Amberquartz",
                                      "-c", "native-ci-docs", "-n", "1", "--json"]))
    run.check("qmd-updated-search-source", len(found) == 1 and found[0]["file"] == uri)
    fresh = run.command("qmd-get-updated-fresh-process", cli + ["get", uri, "--no-line-numbers"])
    verify_qmd_document(fresh, uri, found[0]["docid"], updated)
    run.check("qmd-update-content-fidelity", True)
    run.command("qmd-status", cli + ["status"])
    run.command("qmd-remove-owned-collection", cli + ["collection", "remove", "native-ci-docs"])
    run.check("qmd-no-model-files", not any(run.work.rglob("*.gguf")))
    run.artifact("qmd-input.md", source)


def repomix_fixture(run: Run) -> None:
    inputs = run.work / "pack-fixture"
    inputs.mkdir()
    originals = {}
    for name in ("before.py", "after.py"):
        originals[name] = (ROOT / "fixtures" / name).read_text()
        (inputs / name).write_text(originals[name])
    (inputs / "unselected.txt").write_text("DO_NOT_PACK_CI_UNSELECTED\n")
    config = run.work / "repomix.config.json"
    config.write_text("{}\n")
    packed = run.work / "selected.xml"
    base = [run.tools["repomix"], str(inputs), "--config", str(config), "--include",
            "before.py,after.py", "--style", "xml", "--parsable-style",
            "--token-count-encoding", "o200k_base", "--no-file-summary", "--no-directory-structure"]
    run.command("repomix-selected-originals", base + ["--output", str(packed)])
    verify_pack(packed.read_text(), originals)
    run.check("repomix-source-fidelity-and-selection", True)
    run.artifact("repomix-originals.xml", packed)
    compressed = run.work / "selected-compressed.xml"
    run.command("repomix-selected-structure", base + ["--compress", "--output", str(compressed)])
    content = compressed.read_text()
    run.check("repomix-structural-output-only", all(name in content for name in originals)
              and "greeting" in content and "DO_NOT_PACK_CI_UNSELECTED" not in content)
    # The check above also passes on an uncompressed pack: compression must keep each signature and
    # drop the function body that the exact originals pack above still holds.
    structure = pack_file_texts(content)
    run.check("repomix-compress-keeps-signatures-drops-bodies",
              set(structure) == set(originals)
              and all("def greeting(name)" in text and "return" not in text for text in structure.values())
              and all("return" in text for text in originals.values()))
    run.artifact("repomix-structure.xml", compressed)


def toon_fixture(run: Run) -> None:
    source = run.work / "records.json"
    source.write_bytes((ROOT / "fixtures/records.json").read_bytes())
    encoded, recovered = run.work / "records.toon", run.work / "recovered.json"
    cli = run.tools["toon"]
    run.command("toon-encode-statistics", [cli, str(source), "--stats", "-o", str(encoded)])
    run.command("toon-strict-decode", [cli, str(encoded), "--decode", "--strict", "-o", str(recovered)])
    verify_json_roundtrip(source.read_text(), recovered.read_text())
    run.check("toon-exact-json-value-roundtrip", True)
    # Any valid TOON encoding round-trips (another delimiter, or the expanded list form), while a copied
    # JSON file decodes to a different value; the compact tabular block, smaller than the JSON, is the
    # form TOON is used for.
    tabular = encoded.read_text()
    run.check("toon-tabular-encoding-smaller-than-json",
              tabular.rstrip("\n") == TOON_TABULAR_RECORDS and len(tabular.encode()) < len(source.read_bytes()))
    malformed = run.work / "malformed.toon"
    malformed.write_text("items[2]{name,count}:\n  alpha,1\n")
    run.command("toon-rejects-truncated-array", [cli, str(malformed), "--decode", "--strict"], nonzero=True)
    run.artifact("records.toon", encoded)
    run.artifact("records.recovered.json", recovered)


def markitdown_fixture(run: Run) -> None:
    binary = run.tools["markitdown"]
    converted = run.work / "greeting.md"
    run.command("markitdown-html-fixture", [binary, str(ROOT / "fixtures/greeting.html"),
                "-o", str(converted)])
    run.check("markitdown-html-heading-present", "# Local browser command check" in converted.read_text())
    run.artifact("markitdown-greeting.md", converted)
    plain_text = "Native CI markitdown passthrough fixture line one.\nLine two stays unchanged.\n"
    plain_source = run.work / "markitdown-plain.txt"
    plain_source.write_text(plain_text)
    passthrough = run.work / "markitdown-plain-converted.txt"
    run.command("markitdown-txt-passthrough", [binary, str(plain_source), "-o", str(passthrough)])
    run.check("markitdown-txt-passthrough-unchanged",
              passthrough.read_text().rstrip("\n") == plain_text.rstrip("\n"))


def markitdown_multi_element_fixture(run: Run) -> None:
    """MarkItDown's HTML converter on a page with one of each common element. Every element check
    must hold on the converted Markdown and fail on the raw HTML and on its plain tag-stripped text."""
    source = ROOT / MARKITDOWN_MULTI_ELEMENT
    converted = run.work / "markitdown-multi-element.md"
    run.command("markitdown-multi-element-html", [run.tools["markitdown"], str(source), "-o", str(converted)])
    markdown, html = converted.read_text(), source.read_text()
    stripped = tag_stripped_text(html)
    found = markdown_elements(markdown)
    baselines = {"raw_html": markdown_elements(html), "tag_stripped_text": markdown_elements(stripped)}
    run.report["markitdown_multi_element"] = {"converted": found, **baselines}
    run.flush()
    run.check("markitdown-multi-element-structure-converted", all(found.values()))
    # Searched with Markdown backslash escapes removed as well, so an escaped leak still counts.
    unescaped = re.sub(r"\\(.)", r"\1", markdown)
    run.check("markitdown-script-style-and-comment-text-dropped",
              not any(text in candidate for text in MARKITDOWN_HIDDEN_TEXT for candidate in (markdown, unescaped)))
    run.check("markitdown-element-checks-reject-raw-and-tag-stripped-html",
              not any(value for baseline in baselines.values() for value in baseline.values())
              and all(any(text in candidate for text in MARKITDOWN_HIDDEN_TEXT) for candidate in (html, stripped)))
    run.artifact("markitdown-multi-element.md", converted)


def ast_grep_fixture(run: Run) -> None:
    # A frozen fixture, not the live scripts/ tree: its outcome cannot drift with unrelated
    # scripts, and it separates a structural match from a textual one. ast-grep must return
    # exactly the two real calls, including the one spelled `subprocess.run (`, which a text
    # search misses; grep's text baseline must find the first call plus the comment and
    # string decoys, which are not calls.
    binary = run.tools["ast-grep"]
    matches = json.loads(run.command("ast-grep-fixture-subprocess-run", [binary, "run", "--lang", "python",
                         "--pattern", "subprocess.run($$$ARGS)", AST_GREP_FIXTURE, "--json=compact"],
                         cwd=ROOT))
    text = run.command("ast-grep-text-baseline-grep", ["grep", "-n", "-o", r"subprocess\.run(",
                       AST_GREP_FIXTURE], cwd=ROOT)
    text_lines = [int(line.split(":", 1)[0]) for line in text.splitlines() if line]
    # ast-grep's JSON range lines are 0-based.
    call_lines = sorted(match["range"]["start"]["line"] + 1 for match in matches)
    run.check("ast-grep-matches-only-the-real-calls-in-fixture",
              {match["file"] for match in matches} == {AST_GREP_FIXTURE}
              and call_lines == AST_GREP_CALL_LINES and text_lines == AST_GREP_TEXT_LINES)
    # ast-grep exits 1 (not 0) on zero matches, matching grep/ripgrep convention; it still
    # prints the empty JSON array.
    none = json.loads(run.command("ast-grep-negative-control", [binary, "run", "--lang", "python",
                      "--pattern", "zzz_native_ci_nonexistent_call($$$ARGS)", AST_GREP_FIXTURE,
                      "--json=compact"], cwd=ROOT, nonzero=True))
    run.check("ast-grep-negative-control-zero-matches", none == [])


def ast_grep_shell_fixture(run: Run) -> None:
    """A structural pattern no line-based search expresses: calls that pass a shell=True keyword
    argument, one spread over five lines, against the closest single-line regex."""
    matches = json.loads(run.command("ast-grep-shell-true-calls", [run.tools["ast-grep"], "run", "--lang",
                         "python", "--pattern", AST_GREP_SHELL_PATTERN, AST_GREP_SHELL_FIXTURE,
                         "--json=compact"], cwd=ROOT))
    text = run.command("ast-grep-shell-text-baseline-grep", ["grep", "-n", "-E", AST_GREP_SHELL_TEXT_REGEX,
                       AST_GREP_SHELL_FIXTURE], cwd=ROOT)
    text_lines = [int(line.split(":", 1)[0]) for line in text.splitlines() if line]
    # ast-grep's JSON range lines are 0-based.
    ranges = sorted([match["range"]["start"]["line"] + 1, match["range"]["end"]["line"] + 1] for match in matches)
    run.check("ast-grep-shell-true-calls-match-across-lines",
              {match["file"] for match in matches} == {AST_GREP_SHELL_FIXTURE}
              and ranges == AST_GREP_SHELL_CALL_RANGES and text_lines == AST_GREP_SHELL_TEXT_LINES)


def ccusage_fixture(run: Run) -> None:
    binary = run.tools["ccusage"]
    report = json.loads(run.command("ccusage-claude-daily-synthetic-fixture",
                        [binary, "claude", "daily", "--json", "--offline", "--timezone", "UTC"]))
    require(len(report["daily"]) == 2, "ccusage must report both synthetic fixture days")
    totals = report["totals"]
    run.check("ccusage-synthetic-fixture-token-totals",
              totals["inputTokens"] == 1900 and totals["outputTokens"] == 380
              and totals["totalTokens"] == 2430)
    run.check("ccusage-synthetic-fixture-cost-total", abs(totals["totalCost"] - 0.0328) < 1e-9)


def codebase_memory_mcp_fixture(run: Run) -> None:
    # Every codebase-memory-mcp process, the one-shot `cli` and its index worker included,
    # coordinates through one per-account rendezvous (default /tmp/cbm-daemon-<uid>) and keeps
    # indexes and settings in ~/.cache/codebase-memory-mcp. On a host whose MCP clients already
    # run CBM, the defaults join that live rendezvous and store. The documented CBM_RUNTIME_DIR
    # and CBM_CACHE_DIR (upstream docs/CONFIGURATION.md) move both into this run's directory.
    binary = run.tools["codebase-memory-mcp"]
    cache, runtime = Path(run.env["CBM_CACHE_DIR"]), Path(run.env["CBM_RUNTIME_DIR"])
    require_cbm_socket_fits(str(runtime))
    project = "native-ci-codebase-memory-fixture"
    repo = run.work / "codebase-memory-fixture"
    repo.mkdir()
    for name in ("before.py", "after.py"):
        (repo / name).write_text((ROOT / "fixtures" / name).read_text())

    def cli(label: str, *arguments: str) -> str:
        return run.command(label, [binary, "cli", "--json", *arguments])

    run.command("codebase-memory-mcp-config-set-ui-disabled", [binary, "config", "set", "ui_enabled", "false"])
    disabled = run.command("codebase-memory-mcp-config-get-ui-disabled", [binary, "config", "get", "ui_enabled"])
    run.check("codebase-memory-mcp-ui-disabled", disabled.strip() == "false")
    settings = set(run.observe("codebase-memory-mcp-cache-after-config", cache))
    run.check("codebase-memory-mcp-settings-and-rendezvous-inside-run",
              bool(settings & {"_config.db", "config.json"})
              and (runtime / f"cbm-daemon-{os.geteuid()}").is_dir())
    indexed = json.loads(cli("codebase-memory-mcp-index-repository", "index_repository", "--repo-path",
                             str(repo), "--name", project, "--mode", "full"))["structuredContent"]
    run.check("codebase-memory-mcp-indexed-status", indexed["status"] == "indexed" and indexed["nodes"] > 0)
    listed = cli("codebase-memory-mcp-list-projects-after-index", "list_projects")
    run.check("codebase-memory-mcp-lists-only-the-fixture-project",
              cbm_listed_total(listed) == 1 and project in listed)
    found = json.loads(cli("codebase-memory-mcp-search-code-greeting", "search_code", "--project", project,
                           "--pattern", "greeting", "--format", "json"))["structuredContent"]
    run.check("codebase-memory-mcp-search-found-both-fixture-files",
              found["total_results"] == 2 and {row[2] for row in found["rows"]} == {"after.py", "before.py"})
    absent = json.loads(cli("codebase-memory-mcp-search-code-negative-control", "search_code", "--project",
                            project, "--pattern", "zzz_native_ci_nonexistent_symbol",
                            "--format", "json"))["structuredContent"]
    run.check("codebase-memory-mcp-negative-control-zero-results", absent["total_results"] == 0)
    deleted = json.loads(cli("codebase-memory-mcp-delete-project", "delete_project",
                             "--project", project))["structuredContent"]
    run.check("codebase-memory-mcp-project-deleted", deleted["status"] == "deleted")
    listing = cli("codebase-memory-mcp-list-projects-after-cleanup", "list_projects")
    run.check("codebase-memory-mcp-no-leaked-projects", cbm_listed_total(listing) == 0)
    run.observe("codebase-memory-mcp-cache-after-cleanup", cache)
    run.observe("codebase-memory-mcp-rendezvous", runtime)


def ensure_mcporter(run: Run) -> str:
    """Install (or resolve) the MCPorter bridge once per run; headroom and jcodemunch-mcp
    reach their own upstream MCP tool surfaces through it. It has no fixture of its own,
    but it is pinned and version-checked the same way."""
    if "mcporter" in run.tools:
        return run.tools["mcporter"]
    # A later fixture must report the first failure's real cause: retrying would repeat a
    # pin mismatch, or, after a failed --install, stop at install()'s existing prefix.
    require(run.mcporter_error is None, f"MCPorter unavailable after an earlier failure: {run.mcporter_error}")
    try:
        binary = run.install("mcporter") if run.fresh_install else shutil.which("mcporter")
        require(bool(binary), "Missing native executable: mcporter")
        version = run.command("version-mcporter", [str(binary), "--version"])
        require(re.search(rf"(?<![\d.]){re.escape(PINS['mcporter'])}(?![\d.])", version) is not None,
                "Installed mcporter differs from its manifest pin")
    except Exception as error:
        run.mcporter_error = f"{type(error).__name__}: {error}"
        raise
    # Only cache a version-checked binary: an earlier fixture's failed pin check must not
    # leave a mismatched mcporter memoized for a later fixture (headroom, jcodemunch-mcp)
    # to silently reuse without its own check.
    run.tools["mcporter"] = str(binary)
    return run.tools["mcporter"]


def mcporter_stdio_call(run: Run, label: str, server: str, name: str, tool: str, args: dict,
                        env_keys: tuple[str, ...], timeout_ms: int, timeout: int = 90,
                        extra_env: dict[str, str] | None = None) -> dict:
    """One ad-hoc MCPorter call. The server's state settings are also passed with --env so
    they do not depend on MCPorter's environment inheritance."""
    settings = {**{key: run.env[key] for key in env_keys}, **(extra_env or {})}
    state = [flag for key, value in settings.items() for flag in ("--env", f"{key}={value}")]
    return json.loads(run.command(label, [ensure_mcporter(run), "--config", str(run.mcporter_config),
                                          "call", "--stdio", server, *state, "--name", name,
                                          "--tool", tool, "--args", json.dumps(args), "--output", "json",
                                          "--no-oauth", "--timeout", str(timeout_ms)], timeout=timeout))


def headroom_fixture(run: Run) -> None:
    ensure_mcporter(run)
    workspace = Path(run.env["HEADROOM_WORKSPACE_DIR"])
    server = stdio_command(run.tools["headroom"], "mcp", "serve", "--proxy-url", "http://127.0.0.1:1")
    records = (ROOT / HEADROOM_RECORDS).read_text()
    note = (ROOT / HEADROOM_NOTE).read_text()

    def call(label: str, tool: str, args: dict) -> dict:
        # Headroom's workspace (default ~/.headroom) holds its compression store, session
        # stats and savings ledger; HEADROOM_WORKSPACE_DIR/HEADROOM_CONFIG_DIR move them.
        return mcporter_stdio_call(run, label, server, "headroom-native-ci", tool, args,
                                   ("HEADROOM_WORKSPACE_DIR", "HEADROOM_CONFIG_DIR", "HEADROOM_OFFLINE",
                                    "DO_NOT_TRACK"), 20000)

    compressed = call("headroom-compress-json-records", "headroom_compress", {"content": records})
    run.check("headroom-compress-json-records-saves-tokens", headroom_compressed(compressed, records))
    # Each call starts a new server process, so this round trip also crosses processes.
    retrieved = call("headroom-retrieve-json-records", "headroom_retrieve", {"hash": compressed["hash"]})
    run.check("headroom-retrieve-exact-original-records", retrieved.get("original_content") == records)
    # The in-run negative control for the saving check: short content stays unchanged, but stored.
    short = call("headroom-compress-short-note", "headroom_compress", {"content": note})
    run.check("headroom-short-note-stored-unchanged", short.get("compressed") == note
              and short.get("tokens_saved") == 0 and bool(short.get("hash")))
    negative = call("headroom-retrieve-bogus-hash", "headroom_retrieve", {"hash": "0" * 24})
    run.check("headroom-bogus-hash-reports-error", "error" in negative)
    run.check("headroom-compression-store-inside-run",
              "ccr_store.db" in run.observe("headroom-workspace", workspace))
    # Headroom counts tokens with tiktoken's o200k_base vocabulary, which tiktoken downloads into
    # its cache under TMPDIR on first use; recorded, not checked.
    run.observe("headroom-tiktoken-cache", Path(run.env["TMPDIR"]) / "data-gym-cache")


def jcodemunch_mcp_fixture(run: Run) -> None:
    ensure_mcporter(run)
    index_path = Path(run.env["CODE_INDEX_PATH"])
    # share_savings defaults to true; config.jsonc is the documented, non-deprecated setting
    # and the JCODEMUNCH_SHARE_SAVINGS environment fallback stays set as well.
    (index_path / "config.jsonc").write_text(json.dumps({"share_savings": False}) + "\n")
    # jcodemunch-mcp 1.108.319's savings/perf helpers fall back to ~/.code-index when a caller
    # passes no base path, whatever CODE_INDEX_PATH says (a local run observed that directory
    # being created), so this server alone gets a HOME inside the run; the result is recorded.
    # The name avoids a "/home/<name>" shape, which the publication scan treats as personal.
    server_home = run.work / "jcodemunch-mcp-home"
    server_home.mkdir(mode=0o700, parents=True)
    server = stdio_command(run.tools["jcodemunch-mcp"])

    def order(label: str, payload: dict) -> dict:
        return mcporter_stdio_call(run, label, server, "jcodemunch-native-ci", "order", payload,
                                   ("CODE_INDEX_PATH", "JCODEMUNCH_SHARE_SAVINGS"), 60000,
                                   extra_env={"HOME": str(server_home)})

    indexed = order("jcodemunch-index-folder", {"action": "index_folder", "args": {
        "path": str(ROOT / "fixtures"), "use_ai_summaries": False,
        "extra_ignore_patterns": ["*.json", "*.jsonl", "*.md", "*.html", "*.txt", "**/__pycache__/**"],
        "follow_symlinks": False, "context_providers": False}, "allow_state_change": True})
    require(indexed.get("success") is True, "jcodemunch index_folder did not report success")
    run.check("jcodemunch-indexed-fixtures-symbols", indexed.get("symbol_count", 0) >= 2)
    repo = indexed["repo"]
    # The repository's own index file, which only jcodemunch-mcp writes, must be under
    # CODE_INDEX_PATH and absent from the server HOME's ~/.code-index fallback. A non-empty
    # directory alone proves nothing: the harness itself wrote config.jsonc there.
    index_file = jcodemunch_index_file(repo)
    run.check("jcodemunch-index-inside-run",
              index_file in run.observe("jcodemunch-mcp-index", index_path)
              and not any(server_home.rglob(index_file)))

    found = order("jcodemunch-search-symbols-greeting", {"action": "search_symbols",
                  "args": {"repo": repo, "query": "greeting", "kind": "function", "max_results": 5}})
    search_text = found["content"][0]["text"]
    symbol_ids = [line.split(",")[1] for line in search_text.splitlines() if line.startswith("s,")]
    require(JCODEMUNCH_SYMBOL["id"] in symbol_ids, "jcodemunch did not return the after.py greeting symbol")

    source = order("jcodemunch-get-symbol-source", {"action": "get_symbol_source",
                   "args": {"repo": repo, "symbol_id": JCODEMUNCH_SYMBOL["id"]}})
    # Compared with the frozen oracle, never with the bounds the response itself reports: an
    # empty or partial source must not pass with matching wrong bounds.
    run.check("jcodemunch-get-symbol-source-exact-content", jcodemunch_symbol_exact(source))

    absent = order("jcodemunch-search-symbols-negative-control", {"action": "search_symbols",
                   "args": {"repo": repo, "query": "zzz_native_ci_nonexistent_symbol",
                            "kind": "function", "max_results": 5}})
    # jcodemunch-mcp 1.108.319 answers in its compact MUNCH text only when that is at least
    # 15% smaller than the JSON (encoding/__init__.py encode_response, encoding/gate.py
    # DEFAULT_THRESHOLD); otherwise it sends JSON text. MCPorter 0.14.1's `--output json`
    # prints JSON text as the parsed object and other text inside the raw result's content
    # list. Every local run got the JSON for this zero-result search (the upstream encoder's
    # MUNCH form of a zero-result response is larger than its JSON); both shapes are accepted.
    if "content" in absent:
        run.check("jcodemunch-negative-control-zero-results", "result_count=0" in absent["content"][0]["text"])
    else:
        run.check("jcodemunch-negative-control-zero-results", absent.get("result_count") == 0)
    run.observe("jcodemunch-mcp-server-home", server_home)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New sanitized result directory")
    parser.add_argument("--install", action="store_true", help="Install pinned tools into a fresh owned prefix")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="native-token-ci-") as directory:
        run = Run(output, Path(directory))
        run.report["installation"] = "fresh-upstream-prefix" if args.install else "existing-executables"
        run.fresh_install = args.install
        completed = False
        try:
            components = {row["id"]: row for row in json.loads((ROOT / "manifests/stack.json").read_text())["components"]}
            for name, version in PINS.items():
                require(components[name]["version"] == version, f"Manifest pin changed: {name}")
            # Built here, not at import, so a test's patch of a fixture function takes effect.
            for name, fixtures in (("rtk", (rtk_fixture, rtk_long_log_fixture)), ("qmd", (qmd_fixture,)),
                                   ("repomix", (repomix_fixture,)), ("toon", (toon_fixture,)),
                                   ("markitdown", (markitdown_fixture, markitdown_multi_element_fixture)),
                                   ("ast-grep", (ast_grep_fixture, ast_grep_shell_fixture)),
                                   ("ccusage", (ccusage_fixture,)),
                                   ("codebase-memory-mcp", (codebase_memory_mcp_fixture,)),
                                   ("headroom", (headroom_fixture,)),
                                   ("jcodemunch-mcp", (jcodemunch_mcp_fixture,))):
                try:
                    binary = run.install(name) if args.install else shutil.which(name)
                    require(bool(binary), f"Missing native executable: {name}")
                    run.tools[name] = str(binary)
                    version = run.command(f"version-{name}", [str(binary), "--version"])
                    require(re.search(rf"(?<![\d.]){re.escape(PINS[name])}(?![\d.])", version) is not None,
                            f"Installed {name} differs from its manifest pin")
                    for fixture in fixtures:
                        # Each fixture checks its own input, so one failure does not skip the next.
                        try:
                            fixture(run)
                        except Exception as error:
                            run.report["failures"].append({"component": name, "error": run.clean(str(error))})
                            run.flush()
                except Exception as error:
                    run.report["failures"].append({"component": name, "error": run.clean(str(error))})
                    run.flush()
            completed = True
        except Exception as error:
            run.report["failures"].append({"component": "harness", "error": run.clean(str(error))})
        finally:
            if not completed and not run.report["failures"]:
                run.report["failures"].append({"component": "harness", "error": "Execution interrupted before completion"})
            work = run.work
            if (work / "mcp").is_dir():
                # Ad-hoc stdio servers are not keep-alive, so no MCPorter daemon should start here.
                run.observe("mcporter-daemon-dir", work / "mcp")
            # Only this newly created TemporaryDirectory is removed; no shared state or install.
            try:
                shutil.rmtree(work)
            except OSError as error:
                run.report["failures"].append({"component": "cleanup", "error": run.clean(str(error))})
            run.report["cleanup"] = {"owned_temporary_directory_absent": not work.exists(),
                                     "retained_output_exists": output.is_dir()}
            run.report["execution_completed"] = completed
            run.report["status"] = "passed" if completed and not run.report["failures"] else "failed"
            run.flush()
    print(json.dumps({"status": run.report["status"], "commands": len(run.report["commands"]),
                      "checks": len(run.report["checks"]), "failures": run.report["failures"],
                      "cleanup": run.report["cleanup"]}))
    return 0 if run.report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
