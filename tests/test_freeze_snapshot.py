"""Tests for tools/token-e2e/freeze_snapshot.py against a synthetic host: no real account, service, path or user.

The host is a temporary directory tree (a git checkout, a home directory, fake `claude`, `codex`, `rtk`, `node`,
`python3`, `qmd` and `systemctl` executables on a temporary PATH, canned repo scripts and a loopback HTTP server), so the
suite runs anywhere. The canned outputs copy the shapes observed on a real host on 2026-09-29 (claude 2.1.284, qmd 2.8.3,
systemd 255, scripts/adoption_status.py and scripts/codex_quota.py at the repository base), with synthetic values.

Two evidence classes stay apart. These are integration checks of our glue against fixtures, not upstream acceptance and
not a measurement of any host. `MutationControlTests` writes a mutant of the tool for each property (one that leaks the
environment, one blind to each item class, one that fails on informational changes, and so on), runs the real test that
checks that property against the mutant in a subprocess and requires that test to fail. The tool under test is
`FREEZE_SNAPSHOT_TOOL` when that names a file, so the same tests run against a mutant; `FREEZE_MUTANT_DIR` keeps the
mutant files and each one's exit code and failing assertion.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import hashlib
import http.server
import importlib
import json
import os
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import tests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOL = ROOT / "tools" / "token-e2e" / "freeze_snapshot.py"
TOOL = Path(os.environ.get("FREEZE_SNAPSHOT_TOOL") or DEFAULT_TOOL)
REAL_GIT = shutil.which("git") or "git"

ROLES = ("stack-verifier", "isolated-builder", "source-scout", "stack-researcher", "evidence-reviewer")
COPIES = ("adoption", "examples", "project", "user")
BLOCKS = ("token-lanes-block.md", "token-lanes-block.builder.md", "token-lanes-block.researcher.md",
          "token-lanes-block.reviewer.md", "token-lanes-block.scout.md", "token-lanes-block.verifier.md")
HOOK = "token-lanes-subagent-start.py"
SEALED = "evidence/artifacts/token-adoption-e2e-20260926"
UNITS = ("ecosystem-otelcol", "ecosystem-loki", "ecosystem-prometheus", "ecosystem-grafana", "omniroute",
         "omniroute-fw", "hindsight-live", "cognee-live", "ai-memory")
NO_CONFIG_UNITS = ("omniroute", "omniroute-fw", "hindsight-live")
NOT_FOUND_UNITS = ("cognee-live", "ai-memory")
FAMILIES = ("repo.carrier.", "repo.capability_gate.", "hooks.installed.", "claude.mcp.", "claude.wiring.",
            "codex.wiring.", "tools.pinned.", "tools.parser.file.")
GLYPH_OK, GLYPH_FAILED, GLYPH_AUTH = "✔", "✘", "!"

# Shapes copied from real output (paths, names and numbers are synthetic).
MCP_LIST = (
    "Checking MCP server health…\n\n"
    "plugin:fixture-plugin:fixture-plugin: {home}/tools/node {home}/sources/start.mjs - ✔ Connected\n"
    "ai-memory: http://127.0.0.1:49474/mcp (HTTP) - ✔ Connected\n"
    "serena: {home}/bin/serena start-mcp-server --transport stdio --project-from-cwd - ✔ Connected\n"
    "qmd: {home}/bin/qmd --index fixture-index mcp - ✔ Connected\n"
    "\nMCP config diagnostics ⚠\n\n"
    "For help configuring MCP servers, see: https://code.claude.com/docs/en/mcp\n\n"
    "[Contains warnings] Local config (private to you in this project)\n"
    "Location: {home}/.claude.json [project: {repo}/a - b]\n"
    " └ [Warning] [socraticode] mcpServers.socraticode: Leading or trailing whitespace in: env.PREFIX\n")
QMD_STATUS = (
    "QMD Status\n\nIndex: {home}/.cache/qmd/fixture-index.sqlite\nSize:  27.6 MB\n\nDocuments\n"
    "  Total:    288 files indexed\n  Vectors:  3284 embedded\n"
    "  Orphaned: 952 embedding chunks (29%) — run 'qmd cleanup'\n"
    "  Pending:  15 need embedding (run 'qmd embed')\n  Updated:  3m ago\n\n"
    "AST Chunking\n  Status:   active\n\nCollections\n  fixture-docs (qmd://fixture-docs/)\n"
    "    Pattern:  **/*.md\n    Files:    23 (updated 5h ago)\n\n"
    "Models\n  Embedding:   https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF\n")
QMD_STATUS_ZERO = QMD_STATUS.replace("  Orphaned: 952 embedding chunks (29%) — run 'qmd cleanup'\n", "").replace(
    "  Pending:  15 need embedding (run 'qmd embed')\n", "")
CODEX_QUOTA = {
    "used_percent": 95, "window_minutes": 10080, "resets_at_utc": "2026-10-04T00:35Z", "plan_type": "pro",
    "secondary": None, "limit_id": "codex", "rate_limit_reached_type": None, "ordinary_usage_allowed": True,
    "reset_credits_available": 1, "buckets": {}, "checked_at_utc": "2026-09-29T06:15:05Z"}
CLAUDE_RESETS = {"five_hour": 1790672400, "seven_day": 1790791200}
CLAUDE_P_ARRAY = [
    {"type": "system", "subtype": "init", "model": "claude-haiku-4-5-20251001"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "OK"}]}},
    {"type": "rate_limit_event", "rate_limit_info": {
        "status": "allowed_warning", "resetsAt": 1790791200, "rateLimitType": "seven_day", "utilization": 0.78,
        "isUsingOverage": False, "surpassedThreshold": 0.75,
        "unifiedWindows": {"five_hour": {"utilization": 0.52, "resetsAt": 1790672400},
                           "seven_day": {"utilization": 0.78, "resetsAt": 1790791200}}}},
    {"type": "result", "subtype": "success", "is_error": False, "result": "OK"}]
CLAUDE_P_PLAIN = {"type": "result", "subtype": "success", "is_error": False, "result": "OK"}
ADOPTION_WIRING = {
    "schema_version": 1, "status": "prerequisites_present",
    "client_wiring": {
        "claude": {"rtk_hook": True, "ai_memory_hook_events": 8, "context_mode_plugin_enabled": True,
                   "subagent_spawn_depth_1": True, "workflow_concurrency_set": True, "effort_level_env_unset": True,
                   "agent_teams_opt_in": 1},
        "project": {"settings_depth_and_concurrency": True,
                    "codex_mcp_servers_present": {"serena": False, "socraticode": False, "ai-memory": False}},
        "codex": {"rtk_instructions": True, "context_mode_plugin_enabled": True,
                  "mcp_servers_present": {"serena": True, "socraticode": True, "ai-memory": True},
                  "hooks_feature_enabled": True, "ai_memory_hook_events": 7, "ai_memory_hook_events_trusted": 7},
        "complete": True}}
ADOPTION_PINS = {
    "schema_version": 1, "status": "prerequisites_present",
    "profiles": [{"id": "token-efficiency", "pinned_versions": [
        {"id": "codex", "pinned_version": "0.157.1", "checked": True, "matches_pin": True},
        {"id": "claude-code", "pinned_version": "2.1.284", "checked": True, "matches_pin": True},
        {"id": "context-mode", "pinned_version": "1.0.169", "checked": False, "matches_pin": None}]}],
    "pinned_versions_match": True}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def utc_minute(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def words_in(text: str, word: str) -> bool:
    """True when `word` occurs delimited by non-alphanumeric characters (a user or host name, not a substring)."""
    start = 0
    while True:
        found = text.find(word, start)
        if found < 0:
            return False
        before = text[found - 1] if found else " "
        after = text[found + len(word)] if found + len(word) < len(text) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = found + 1


def find_leaks(texts: dict[str, str], forbidden: dict[str, str], words: dict[str, str]) -> list[str]:
    """The (output, forbidden value) pairs that leak. `forbidden` are substrings, `words` are whole words."""
    leaks = []
    for where, text in texts.items():
        for label, value in forbidden.items():
            if value and value in text:
                leaks.append(f"{where}: {label}")
        for label, value in words.items():
            if len(value) >= 4 and words_in(text, value):
                leaks.append(f"{where}: {label}")
    return leaks


OWNER_PREFIXES = ("repo.", "roles.", "hooks.", "claude.", "codex.", "wiring.", "tools.", "services.", "gateways.", "extra.",
                  "capacity.", "time.")


def expand_braces(pattern: str) -> list[str]:
    """`a.{b, c}.d` -> [`a.b.d`, `a.c.d`]; every brace group multiplies the list."""
    found = re.search(r"\{([^{}]*)\}", pattern)
    if not found:
        return [pattern]
    out: list[str] = []
    for option in found.group(1).split(","):
        out += expand_braces(pattern[:found.start()] + option.strip() + pattern[found.end():])
    return out


def pattern_regex(pattern: str) -> str:
    """`<name>` matches one or more characters and a `*` any run; everything else is literal."""
    out, index = [], 0
    while index < len(pattern):
        if pattern[index] == "<":
            index = pattern.index(">", index) + 1
            out.append(".+")
        elif pattern[index] == "*":
            index += 1
            out.append(".*")
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return "".join(out)


def blind_patch(owner: str) -> tuple[str, str]:
    """A mutant patch that replaces one collector by a constant one, so the class cannot see any change."""
    anchor = f'    ("{owner}", collect_{owner}),\n'
    constant = (f'    ("{owner}", lambda ctx: [make_item(s.id, s.cls, OK, "blind", s.method) for s in ctx.specs '
                f'if s.owner == "{owner}" and not s.id.endswith("*")]),\n')
    return anchor, constant


class Loopback(http.server.ThreadingHTTPServer):
    """A loopback HTTP server that serves `routes` ({path: (status, body, headers)}) and records each request."""

    daemon_threads = True

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.server.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
            status, body, headers = self.server.routes.get(self.path, (404, {"error": "not found"}, {}))
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    def __init__(self):
        self.routes: dict[str, tuple] = {}
        self.seen: list[dict] = []
        super().__init__(("127.0.0.1", 0), self.Handler)
        self.closed = False
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def close(self):
        if not self.closed:
            self.closed = True
            self.shutdown()
            self.server_close()


FAKE_CLAUDE = """#!/bin/sh
d="$(dirname "$0")/data"
echo "${FREEZE_PLANTED_MARKER:-}" >&2
case "$1" in
--version) cat "$d/claude.version" ;;
mcp) [ "$2" = "list" ] && cat "$d/claude.mcp" ;;
-p)
  echo "$*" > "$d/claude.p.argv"
  pwd > "$d/claude.p.cwd"
  { if [ -n "${OTEL_RESOURCE_ATTRIBUTES+x}" ]; then echo otel_set; else echo otel_unset; fi
    if [ -n "${RTK_DB_PATH+x}" ]; then echo rtk_set; else echo rtk_unset; fi; } > "$d/claude.p.env"
  case " $* " in
  *" --verbose "*) cat "$d/claude.p.verbose.json" ;;
  *) cat "$d/claude.p.plain.json" ;;
  esac ;;
esac
exit 0
"""
FAKE_VERSION_TOOL = """#!/bin/sh
d="$(dirname "$0")/data"
echo "${FREEZE_PLANTED_MARKER:-}" >&2
if [ "$1" = "--version" ]; then
  cat "$d/NAME.version"
  [ -f "$d/NAME.exit" ] && exit "$(cat "$d/NAME.exit")"
  exit 0
fi
exit 64
"""
FAKE_QMD = """#!/bin/sh
d="$(dirname "$0")/data"
echo "$*" >> "$d/qmd.log"
if [ "$1" = "--index" ] && [ "$3" = "status" ]; then cat "$d/qmd.status"; exit 0; fi
exit 64
"""
FAKE_SYSTEMCTL = """#!/bin/sh
d="$(dirname "$0")/data"
echo "$*" >> "$d/systemctl.log"
if [ "$1" != "--user" ] || [ "$2" != "show" ]; then echo unsupported >&2; exit 1; fi
unit="$3"; shift 3
want=""
while [ $# -gt 0 ]; do
  case "$1" in -p) want="$want $2"; shift 2 ;; *) shift ;; esac
done
f="$d/unit-$unit.txt"
[ -f "$f" ] || f="$d/unit-notfound.txt"
awk -F= -v want="$want" 'BEGIN{n=split(want,a," ");for(i=1;i<=n;i++)w[a[i]]=1} ($1 in w){print}' "$f"
"""
FAKE_GIT = """#!/bin/sh
d="$(dirname "$0")/data"
echo "$*" >> "$d/git.log"
exec "REAL_GIT" "$@"
"""


class FakeHost:
    """A complete synthetic host. `root` holds home/, repo/ (a git checkout), bin/ (fakes and their data) and out/."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.home, self.repo, self.bin = self.root / "home", self.root / "repo", self.root / "bin"
        self.sysbin, self.data, self.out, self.tmp = self.root / "sysbin", self.bin / "data", self.root / "out", self.root / "tmp"
        for folder in (self.home, self.repo, self.data, self.sysbin, self.tmp):
            folder.mkdir(parents=True, exist_ok=True)
        self.user = "freezefakeuser"
        self.settings_marker = "zz-settings-secret-91c3e07a5d2f48"
        self.unit_marker = "zz-unit-secret-5b2e8d1f7a3c60"
        self.credential_marker = "zz-credential-secret-c40d9e12b7a865"
        for name in ("cat", "dirname", "awk", "sleep"):
            found = shutil.which(name)
            if found:
                os.symlink(found, self.sysbin / name)
        self._build_home()
        self._build_repo()
        self._build_fakes()
        self.git("init", "-q", "-b", "main")
        self.commit_all("fixture")
        self.write(self.repo / ".claude" / "settings.local.json", json.dumps({"env": {}}))

    # ----------------------------------------------------------------- files
    def write(self, path: Path, text: str | bytes, mode: int | None = None) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        if mode is not None:
            path.chmod(mode)
        return path

    def append_byte(self, path: Path) -> None:
        with open(path, "ab") as handle:
            handle.write(b"\n")

    def _build_home(self) -> None:
        home = self.home
        settings = {"advisorModel": "opus", "effortLevel": "xhigh", "model": "sonnet",
                    "modelSettings": {"opus": {"effort": "xhigh"}},
                    "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1", "CLAUDE_CODE_SUBAGENT_MODEL": "opus",
                            "PATH": "/fake/bin:/fake/other", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
                            "SETTINGS_SECRET_LOOKING": self.settings_marker}}
        self.write(home / ".claude" / "settings.json", json.dumps(settings, indent=2))
        self.write(home / ".claude" / "CLAUDE.md", "user instructions v1\n")
        self.write(home / ".claude" / "RTK.md", "rtk instructions v1\n")
        for role in ROLES:
            self.write(home / ".claude" / "agents" / f"{role}.md", f"role body {role}\n")
        for name in (*BLOCKS, HOOK, "secret_path_guard.py", "effort-default-guard.py"):
            self.write(home / ".claude" / "hooks" / name, f"installed {name} v1\n")
        self.write(home / ".claude" / "hooks" / "effort-default-guard.py.bak-20260929", "old backup\n")
        for name in ("config.toml", "stack-worker.config.toml", "AGENTS.md", "RTK.md"):
            self.write(home / ".codex" / name, f"codex {name} v1\n")
        self.write(home / ".config" / "rtk" / "config.toml", "rtk config v1\n")
        observability = home / ".config" / "ecosystem-observability"
        for name, text in (("collector.yaml", "receivers: {}\n"), ("loki.yaml", "auth_enabled: false\n"),
                           ("prometheus.yml", "global: {}\n"), ("grafana.ini", "[server]\n")):
            self.write(observability / name, text)
        self.write(home / ".local" / "share" / "codex-ecosystem" / "bin" / "claude",
                   "#!/bin/sh\nexec claude-real \"$@\"\n", 0o755)
        versions = home / ".local" / "share" / "claude" / "versions"
        self.write(versions / "2.1.284", b"fake claude binary bytes")
        (home / ".local" / "bin").mkdir(parents=True, exist_ok=True)
        os.symlink(versions / "2.1.284", home / ".local" / "bin" / "claude")
        package = home / ".local" / "share" / "native-token-report" / "tokenizer" / "node_modules" / "gpt-tokenizer"
        self.write(package / "package.json", json.dumps({"name": "gpt-tokenizer", "version": "3.4.0"}))
        self.write(package / "cjs" / "encoding" / "o200k_base.js", "module.exports = 'encoding';\n")
        self.write(package / "cjs" / "bpeRanks" / "o200k_base.js", "module.exports = 'ranks';\n")
        self.parser_dir = home / ".local" / "share" / "codex-ecosystem" / "tools" / "tree-sitter-bash-0.25.1"
        self.parser_files = {"node_modules/tree-sitter-bash/package.json": "bash package v1\n",
                             "node_modules/tree-sitter-bash/tree-sitter-bash.wasm": "bash wasm v1\n",
                             "node_modules/web-tree-sitter/web-tree-sitter.wasm": "web wasm v1\n"}
        for relative, text in self.parser_files.items():
            self.write(self.parser_dir / relative, text)
        (home / ".claude.json").write_text(json.dumps({"credential": self.credential_marker}), encoding="utf-8")
        (home / ".claude" / ".credentials.json").write_text(self.credential_marker, encoding="utf-8")
        (home / ".codex" / "auth.json").write_text(self.credential_marker, encoding="utf-8")

    def _build_repo(self) -> None:
        repo = self.repo
        for name in ("preregistration.json", "token-e2e-run.mjs", "RUNBOOK.md", "fixtures/table.json",
                     "fixtures/events.jsonl"):
            self.write(repo / SEALED / name, f"sealed {name} v1\n")
        for name in (*BLOCKS, HOOK):
            self.write(repo / "adoption" / "hooks" / "claude" / name, f"installed {name} v1\n")
        for role in ROLES:
            for folder in ("adoption/agents/claude", "examples/claude-native/agents", ".claude/agents"):
                self.write(repo / folder / f"{role}.md", f"role body {role}\n")
        self.write(repo / ".claude" / "settings.json", json.dumps({"effortLevel": "xhigh", "env": {
            "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"}}, indent=2))
        for name in ("README.md", "run_gate.py", "assertions.js", "codex-profile-exec", "briefs/m13.md"):
            self.write(repo / "tools" / "capability-gate" / name, f"gate {name} v1\n")
        for name in ("child-usage.mjs", "SHA256SUMS"):
            self.write(repo / "examples" / "claude-native" / "workflows" / name, f"workflow {name} v1\n")
        pin = {"schema_version": 1, "files": {k: sha256_bytes(v.encode()) for k, v in self.parser_files.items()},
               "install": {"default_directory": ".local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1"}}
        self.write(repo / "examples" / "claude-native" / "workflows" / "shell-parser.pin.json", json.dumps(pin, indent=2))
        self.write(repo / "tools" / "skill-usage" / "skill_usage.py", "skill usage v1\n")
        for name in ("token_manifest.py", "test_token_manifest.py", "token_manifest.html.in", "token_manifest.full.html.in"):
            self.write(repo / "tools" / "token-report" / name, f"token report {name} v1\n")
        self.set_repo_scripts(ADOPTION_WIRING, ADOPTION_PINS, CODEX_QUOTA)

    def set_repo_scripts(self, wiring: dict, pins: dict, quota: dict) -> None:
        adoption = ("import json, sys\nargs = sys.argv[1:]\nassert '--json' in args, args\n"
                    f"WIRING = json.loads({json.dumps(json.dumps(wiring))})\n"
                    f"PINS = json.loads({json.dumps(json.dumps(pins))})\n"
                    "if '--pinned-versions' in args:\n    print(json.dumps(PINS))\n"
                    "elif '--client-wiring' in args:\n    print(json.dumps(WIRING))\n"
                    "else:\n    sys.exit(2)\n")
        self.write(self.repo / "scripts" / "adoption_status.py", adoption)
        self.write(self.repo / "scripts" / "codex_quota.py",
                   "import json, sys\nassert '--json' in sys.argv[1:]\n"
                   f"print(json.dumps(json.loads({json.dumps(json.dumps(quota))})))\n")

    # ----------------------------------------------------------------- fakes
    def _build_fakes(self) -> None:
        home, repo = str(self.home), str(self.repo)
        self.fake_text("claude.version", "2.1.284 (Claude Code)\n")
        self.fake_text("claude.mcp", MCP_LIST.format(home=home, repo=repo))
        self.fake_text("claude.p.verbose.json", json.dumps(CLAUDE_P_ARRAY))
        self.fake_text("claude.p.plain.json", json.dumps(CLAUDE_P_PLAIN))
        self.fake_text("codex.version", "codex-cli 0.157.1\n")
        self.fake_text("rtk.version", "rtk 0.50.0\n")
        self.fake_text("node.version", "v24.21.0\n")
        self.fake_text("python3.version", "Python 3.13.15\n")
        self.fake_text("qmd.status", QMD_STATUS.format(home=home))
        self.fake_text("unit-notfound.txt", "LoadState=not-found\nActiveState=inactive\nSubState=dead\nMainPID=0\n"
                                             "NRestarts=0\nId=fixture.service\n")
        observability = f"{home}/.config/ecosystem-observability"
        units = {"ecosystem-otelcol": ("otelcol", f"--config=file:{observability}/collector.yaml"),
                 "ecosystem-loki": ("loki", f"-config.file={observability}/loki.yaml"),
                 "ecosystem-prometheus": ("prometheus", f"--config.file={observability}/prometheus.yml "
                                          "--storage.tsdb.path=/data --web.listen-address=127.0.0.1:9090"),
                 "ecosystem-grafana": ("grafana", f"--homepath=/opt/grafana --config={observability}/grafana.ini"),
                 "omniroute": ("node", "/opt/omniroute/server.js --port 20128 --no-open --no-tray"),
                 "omniroute-fw": ("node", "/opt/omniroute/server.js --port 20129 --no-open --no-tray"),
                 "hindsight-live": ("uv", "run -i hindsight serve --port 3710")}
        for index, (unit, (binary, arguments)) in enumerate(units.items(), start=1):
            self.set_unit(unit, main_pid=1000 + index, exec_start=f"/usr/bin/{binary} {arguments}")
        self.write(self.bin / "claude", FAKE_CLAUDE, 0o755)
        for name in ("codex", "rtk", "node", "python3"):
            self.write(self.bin / name, FAKE_VERSION_TOOL.replace("NAME", name), 0o755)
        self.write(self.bin / "qmd", FAKE_QMD, 0o755)
        self.write(self.bin / "systemctl", FAKE_SYSTEMCTL, 0o755)
        self.write(self.bin / "git", FAKE_GIT.replace("REAL_GIT", REAL_GIT), 0o755)

    def fake_text(self, name: str, text: str) -> None:
        self.write(self.data / name, text)

    def set_unit(self, unit: str, *, main_pid: int, exec_start: str, active: str = "active", restarts: int = 0) -> None:
        self.fake_text(f"unit-{unit}.txt",
                       f"MainPID={main_pid}\nNRestarts={restarts}\nId={unit}.service\nLoadState=loaded\n"
                       f"ActiveState={active}\nSubState=running\nEnvironment=UNIT_SECRET={self.unit_marker}\n"
                       f"ExecStart={{ path=/usr/bin/x ; argv[]={exec_start} ; ignore_errors=no ; start_time=[n/a] ; "
                       "stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n")

    # ------------------------------------------------------------------- git
    def git(self, *args: str) -> str:
        done = subprocess.run([REAL_GIT, "-C", str(self.repo), *args], env=tests.hermetic_git_environment(),
                              capture_output=True, text=True, check=True)
        return done.stdout

    def commit_all(self, message: str) -> str:
        self.git("add", "-A")
        self.git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    # ------------------------------------------------------------ invocation
    def env(self, **extra: str) -> dict[str, str]:
        """A small, deterministic environment: only what the fixture needs, so a leaked value is one we planted."""
        base = dict(tests.HERMETIC_GIT_ENVIRONMENT)
        base.update({"HOME": str(self.home), "PATH": f"{self.bin}{os.pathsep}{self.sysbin}", "USER": self.user,
                     "LOGNAME": self.user, "TMPDIR": str(self.tmp), "LANG": "C"})
        base.update(extra)
        return base

    def run(self, tool: Path, *args: str, env: dict | None = None, cwd: Path | None = None,
            timeout: int = 180) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-B", str(tool), *args], env=env if env is not None else self.env(),
                              cwd=str(cwd or self.root), capture_output=True, text=True, timeout=timeout)

    def capture(self, tool: Path, label: str, *extra: str, env: dict | None = None, out: Path | None = None,
                probe: bool = True, timeout: int = 180) -> "Capture":
        folder = out or self.out
        args = ["capture", "--label", label, "--out", str(folder), "--repo", str(self.repo), "--platform", "linux"]
        if not probe:
            args.append("--no-usage-probe")
        proc = self.run(tool, *args, *extra, env=env, timeout=timeout)
        return Capture(proc, folder / f"freeze-{label}.json", folder / f"freeze-{label}.sanitized.json")


class Capture:
    """The result of one `capture`: the process and the two files. An unknown id is an assertion, not a KeyError."""

    def __init__(self, proc: subprocess.CompletedProcess, full: Path, sanitized: Path):
        self.proc, self.full, self.sanitized = proc, full, sanitized

    def items(self, which: str = "sanitized") -> dict[str, dict]:
        path = self.sanitized if which == "sanitized" else self.full
        if not path.exists():
            raise AssertionError(f"{path.name} was not written; exit {self.proc.returncode}: {self.proc.stderr[-300:]}")
        return {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))["items"]}

    def item(self, item_id: str, which: str = "sanitized") -> dict:
        items = self.items(which)
        if item_id not in items:
            raise AssertionError(f"item {item_id!r} is not in the {which} capture ({len(items)} items)")
        return items[item_id]

    def value(self, item_id: str, which: str = "sanitized"):
        return self.item(item_id, which)["value"]

    def status(self, item_id: str, which: str = "sanitized") -> str:
        return self.item(item_id, which)["status"]


class HostCase(unittest.TestCase):
    """A test with a fresh FakeHost per test."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="freeze-test-", dir=os.environ.get("TMPDIR") or None)
        self.addCleanup(shutil.rmtree, self.tempdir, True)
        self.host = FakeHost(Path(self.tempdir))
        self.tool = TOOL

    def capture(self, label: str, *extra: str, **kwargs) -> Capture:
        result = self.host.capture(self.tool, label, *extra, **kwargs)
        self.assertEqual(result.proc.returncode, 0, result.proc.stdout + result.proc.stderr)
        return result

    def compare(self, first: Capture, second: Capture, *extra: str) -> subprocess.CompletedProcess:
        return self.host.run(self.tool, "compare", str(first.sanitized), str(second.sanitized), *extra)

    def check(self, capture: Capture, expected: Path, *extra: str) -> subprocess.CompletedProcess:
        return self.host.run(self.tool, "check", str(capture.sanitized), "--expected", str(expected), *extra)

    @staticmethod
    def kinds(proc: subprocess.CompletedProcess) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ("DRIFT", "MISSING", "ERROR", "INFO", "PASS", "FAIL", "NOTE"):
                found.setdefault(parts[0], []).append(parts[1].rstrip(":"))
        return found

    def assert_drift(self, first: Capture, second: Capture, expected: list[str], kind: str = "DRIFT") -> None:
        proc = self.compare(first, second)
        self.assertEqual(sorted(self.kinds(proc).get(kind, [])), sorted(expected), proc.stdout)
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def expect_refused(self, capture: Capture, *needles: str) -> None:
        combined = capture.proc.stdout + capture.proc.stderr
        self.assertEqual(capture.proc.returncode, 2, combined)
        for needle in needles:
            self.assertIn(needle, combined)


class FixtureSanityTests(HostCase):
    """The synthetic host itself: these pass before the tool exists, so later failures are the tool's."""

    def test_fake_commands_print_the_canned_shapes(self):
        env = self.host.env()

        def out(*argv):
            return subprocess.run(list(argv), env=env, capture_output=True, text=True, cwd=self.host.repo).stdout

        self.assertEqual(out("claude", "--version"), "2.1.284 (Claude Code)\n")
        self.assertIn("plugin:fixture-plugin:fixture-plugin:", out("claude", "mcp", "list"))
        self.assertIn("Vectors:  3284 embedded", out("qmd", "--index", "fixture-index", "status"))
        shown = out("systemctl", "--user", "show", "ecosystem-otelcol", "-p", "MainPID", "-p", "LoadState")
        self.assertEqual(sorted(shown.split()), ["LoadState=loaded", "MainPID=1001"])
        self.assertIn("not-found", out("systemctl", "--user", "show", "cognee-live", "-p", "LoadState"))
        self.assertNotIn("UNIT_SECRET", out("systemctl", "--user", "show", "omniroute", "-p", "ActiveState"))
        self.assertEqual(subprocess.run(["systemctl", "--user", "show", "x", "-p", "A"], env={**env, "PATH": str(self.host.sysbin)},
                                        capture_output=True).returncode if shutil.which("systemctl", path=str(self.host.sysbin)) else 127, 127,
                         "the real systemctl must not be reachable from the fixture PATH")

    def test_fake_repo_is_a_clean_checkout_with_the_repo_scripts(self):
        self.assertEqual(self.host.git("--no-optional-locks", "status", "--porcelain", "--untracked-files=no"), "")
        wiring = subprocess.run([sys.executable, "-B", "scripts/adoption_status.py", "--client-wiring", "--json"],
                                cwd=self.host.repo, capture_output=True, text=True).stdout
        self.assertEqual(json.loads(wiring)["client_wiring"]["codex"]["ai_memory_hook_events_trusted"], 7)
        quota = subprocess.run([sys.executable, "-B", "scripts/codex_quota.py", "--json"], cwd=self.host.repo,
                               capture_output=True, text=True).stdout
        self.assertEqual(json.loads(quota)["window_minutes"], 10080)

    def test_credential_stores_exist_in_the_fake_home_with_a_marker(self):
        for relative in (".claude.json", ".claude/.credentials.json", ".codex/auth.json"):
            self.assertIn(self.host.credential_marker, (self.host.home / relative).read_text(encoding="utf-8"))

    def test_the_loopback_server_records_requests(self):
        server = Loopback()
        self.addCleanup(server.close)
        server.routes = {"/x": (200, {"k": 1}, {})}
        import urllib.request
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.assertEqual(json.loads(opener.open(server.base_url + "/x", timeout=5).read()), {"k": 1})
        self.assertEqual([s["path"] for s in server.seen], ["/x"])


class CatalogueTests(HostCase):
    def list_frozen(self, *extra: str) -> subprocess.CompletedProcess:
        return self.host.run(self.tool, "list-frozen", *extra)

    def test_list_frozen_prints_id_and_how_to_check_lines(self):
        proc = self.list_frozen()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = [line.split("\t") for line in proc.stdout.splitlines() if line.strip()]
        self.assertGreater(len(rows), 60, f"only {len(rows)} lines")
        self.assertTrue(all(len(row) == 2 and row[0] and row[1] for row in rows), rows[:3])
        by_id = {row[0]: row[1] for row in rows}
        self.assertIn("rev-parse HEAD", by_id["repo.head"])
        self.assertIn("MainPID", by_id["services.ecosystem-otelcol.main_pid"])
        self.assertIn("claude mcp list", by_id["claude.mcp.*"])
        self.assertIn("RUNBOOK.md", by_id["repo.sealed.RUNBOOK.md"])
        self.assertFalse([row[0] for row in rows if row[0].startswith(("time.", "capacity."))], "informational listed")

    def test_list_frozen_all_adds_the_informational_items_and_json_is_machine_readable(self):
        proc = self.list_frozen("--all", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        ids = {row["id"]: row for row in rows}
        self.assertEqual(len(ids), len(rows), "duplicate ids")
        self.assertEqual(ids["time.capture_start_utc"]["class"], "informational")
        self.assertEqual(ids["capacity.codex.weekly_used_percent"]["class"], "informational")
        self.assertEqual(ids["repo.head"]["class"], "frozen")
        self.assertTrue(ids["claude.mcp.*"]["family"] and not ids["repo.head"]["family"])
        for unit in UNITS:
            for prop in ("load_state", "active_state", "main_pid", "n_restarts", "config_sha256"):
                self.assertIn(f"services.{unit}.{prop}", ids)
        for role in ROLES:
            for copy in (*COPIES, "identical_across_copies"):
                self.assertIn(f"roles.{role}.{copy}", ids)

    def test_the_readme_table_covers_every_catalogue_id_and_names_no_other_one(self):
        """Every backticked id pattern of the README (`a.{b,c}.<d>.*`) is matched against list-frozen, both ways."""
        readme = (DEFAULT_TOOL.parent / "README.md").read_text(encoding="utf-8")
        rows = [line for line in readme.splitlines() if line.startswith("| `")]  # table rows only: prose wildcards cover nothing
        patterns = sorted({span for row in rows for span in re.findall(r"`([^`]+)`", row) if span.startswith(OWNER_PREFIXES)}, key=len)
        compiled = [(pattern, re.compile(pattern_regex(expanded))) for pattern in patterns for expanded in expand_braces(pattern)]
        ids = [row["id"] for row in json.loads(self.list_frozen("--all", "--json").stdout)]
        uncovered = [item_id for item_id in ids if not any(rx.fullmatch(item_id) for _, rx in compiled)]
        self.assertEqual(uncovered, [], "catalogue ids the README table does not cover")
        documented_only = ("gateways.", "extra.")
        stale = sorted({pattern for pattern, rx in compiled
                        if not pattern.startswith(documented_only) and not any(rx.fullmatch(item_id) for item_id in ids)})
        self.assertEqual(stale, [], "README id patterns that match no catalogue id")
        for command in ("capture", "compare", "check", "list-frozen", "--no-usage-probe", "--full", "--quiet"):
            self.assertIn(command, readme)
        for code in ("`0`", "`1`", "`2`", "`3`"):
            self.assertIn(code, readme)

    def test_capture_produces_every_catalogued_id_with_a_status(self):
        listing = json.loads(self.list_frozen("--all", "--json").stdout)
        static = [row["id"] for row in listing if not row["family"]]
        families = [row["id"][:-1] for row in listing if row["family"]]
        self.assertEqual(sorted(families), sorted(FAMILIES))
        items = self.capture("full").items()
        self.assertEqual(sorted(items), list(items), "items are sorted by id")
        self.assertEqual([i for i in static if i not in items], [], "catalogued ids missing from the capture")
        for prefix in FAMILIES:
            self.assertTrue([i for i in items if i.startswith(prefix)], f"no item in family {prefix}")
        for item in items.values():
            self.assertTrue({"id", "class", "status", "value", "method"} <= set(item), item)
            self.assertIn(item["class"], ("frozen", "informational"))
            self.assertIn(item["status"], ("ok", "missing", "error", "not_applicable"))
        not_ok = {i: v["status"] for i, v in items.items() if v["class"] == "frozen" and v["status"] != "ok"}
        expected_not_ok = {f"services.{u}.config_sha256": "not_applicable" for u in NO_CONFIG_UNITS}
        for unit in NOT_FOUND_UNITS:
            for prop in ("active_state", "main_pid", "n_restarts", "config_sha256"):
                expected_not_ok[f"services.{unit}.{prop}"] = "missing"
        self.assertEqual(not_ok, expected_not_ok)

    def test_classes_follow_the_brief(self):
        items = self.capture("classes").items()
        for item_id, item in items.items():
            informational = item_id.startswith(("time.", "capacity."))
            self.assertEqual(item["class"], "informational" if informational else "frozen", item_id)
        self.assertEqual(len([i for i in items if i.startswith("time.")]), 5)

    def test_values_have_the_documented_shapes(self):
        cap = self.capture("shapes")
        self.assertEqual(cap.value("repo.head"), self.host.git("rev-parse", "HEAD").strip())
        self.assertIs(cap.value("repo.tree_clean"), True)
        self.assertEqual(cap.value("repo.sealed.RUNBOOK.md"), sha256_path(self.host.repo / SEALED / "RUNBOOK.md"))
        self.assertEqual(cap.value("repo.sealed.fixtures:table.json"), sha256_path(self.host.repo / SEALED / "fixtures" / "table.json"))
        self.assertEqual(cap.value("repo.carrier.token-lanes-block.builder.md"),
                         sha256_path(self.host.repo / "adoption" / "hooks" / "claude" / "token-lanes-block.builder.md"))
        self.assertEqual(cap.value("repo.capability_gate.briefs:m13.md"),
                         sha256_path(self.host.repo / "tools" / "capability-gate" / "briefs" / "m13.md"))
        self.assertNotIn("repo.capability_gate.README.md", cap.items(), "the README is not a launch file")
        self.assertEqual(cap.value("claude.version"), "2.1.284 (Claude Code)")
        launcher = self.host.home / ".local" / "share" / "codex-ecosystem" / "bin" / "claude"
        self.assertEqual(cap.value("claude.launcher.sha256"), sha256_path(launcher))
        self.assertEqual(cap.value("claude.launcher.size"), launcher.stat().st_size)
        self.assertEqual(cap.value("claude.binary.version_name"), "2.1.284")
        self.assertEqual(cap.value("claude.binary.size"), len(b"fake claude binary bytes"))
        self.assertEqual(cap.value("claude.binary.sha256"), sha256_bytes(b"fake claude binary bytes"))
        self.assertEqual(cap.value("claude.user_claude_md.sha256"), sha256_path(self.host.home / ".claude" / "CLAUDE.md"))
        self.assertEqual(cap.value("codex.version"), "codex-cli 0.157.1")
        self.assertIs(cap.value("codex.stack_worker_profile.present"), True)
        self.assertEqual(cap.value("codex.rtk_md.sha256"), sha256_path(self.host.home / ".codex" / "RTK.md"))
        self.assertEqual(cap.value("tools.rtk.version"), "rtk 0.50.0")
        self.assertEqual(cap.value("tools.node.version"), "v24.21.0")
        self.assertEqual(cap.value("tools.python.version"), "Python 3.13.15")
        self.assertEqual(cap.value("tools.tokenizer.version"), "3.4.0")
        self.assertEqual(cap.value("tools.token_manifest.sha256"), sha256_path(self.host.repo / "tools" / "token-report" / "token_manifest.py"))
        self.assertEqual(cap.value("services.ecosystem-otelcol.active_state"), "active")
        self.assertEqual(cap.value("services.ecosystem-otelcol.main_pid"), 1001)
        self.assertEqual(cap.value("services.ecosystem-otelcol.n_restarts"), 0)
        self.assertEqual(cap.value("services.ecosystem-otelcol.load_state"), "loaded")
        self.assertEqual(cap.value("services.cognee-live.load_state"), "not-found")
        self.assertEqual(cap.value("tools.qmd.documents"), 288)
        self.assertEqual(cap.value("tools.qmd.orphaned"), 952)

    def test_output_files_permissions_and_shape(self):
        cap = self.capture("perm")
        self.assertEqual(stat.S_IMODE(cap.full.stat().st_mode), 0o600)
        full = json.loads(cap.full.read_text(encoding="utf-8"))
        clean = json.loads(cap.sanitized.read_text(encoding="utf-8"))
        self.assertEqual((full["schema"], clean["schema"]), ("freeze-snapshot-v1", "freeze-snapshot-v1"))
        self.assertEqual((full["sanitized"], clean["sanitized"]), (False, True))
        self.assertEqual(full["label"], "perm")
        self.assertEqual([i["id"] for i in full["items"]], [i["id"] for i in clean["items"]])
        self.assertTrue([i for i in full["items"] if "path" in i], "the private capture records the paths it read")
        self.assertFalse([i for i in clean["items"] if "path" in i], "the sanitized capture carries no path field")
        by_id = {i["id"]: i for i in clean["items"]}
        for item in full["items"]:
            for key in ("id", "class", "status", "value"):
                self.assertEqual(item[key], by_id[item["id"]][key], item["id"])

    def test_output_policy_label_directory_and_overwrite(self):
        outside = self.host.root / "elsewhere"
        for label in ("../x", "a/b", "", "a b", "x" * 80):
            proc = self.host.run(self.tool, "capture", "--label", label, "--out", str(outside), "--repo", str(self.host.repo))
            self.assertEqual(proc.returncode, 2, f"label {label!r}: {proc.stdout}{proc.stderr}")
        self.assertFalse(outside.exists() and list(outside.iterdir()), "nothing is written for a refused label")
        first = self.host.capture(self.tool, "once", out=outside)
        self.assertEqual(first.proc.returncode, 0, first.proc.stderr)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o700, "a directory the tool creates is private")
        again = self.host.capture(self.tool, "once", out=outside)
        self.assertEqual(again.proc.returncode, 2, "an existing capture is never overwritten")
        inside = self.host.capture(self.tool, "inside", out=self.host.repo / "scratch")
        self.assertEqual(inside.proc.returncode, 2, "the private capture must not land inside the checkout")
        self.assertFalse((self.host.repo / "scratch").exists())

    def test_capture_summary_line_and_repo_default(self):
        first = self.capture("summary").proc.stdout.splitlines()[0]
        self.assertTrue(first.startswith("freeze-snapshot capture: label=summary items="), first)
        for key in ("ok=", "missing=", "error=", "not_applicable=", "frozen_not_ok="):
            self.assertIn(key, first)
        proc = self.host.run(self.tool, "capture", "--label", "cwd", "--out", str(self.host.out), "--platform", "linux",
                             "--no-usage-probe", cwd=self.host.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        again = Capture(proc, self.host.out / "freeze-cwd.json", self.host.out / "freeze-cwd.sanitized.json")
        self.assertEqual(again.value("repo.head"), self.host.git("rev-parse", "HEAD").strip(), "--repo defaults to the checkout of the cwd")


class PrivacyTests(HostCase):
    PLANTED = "zz-planted-env-marker-6e1c9a04f3d7b2"

    def planted_env(self) -> dict[str, str]:
        return {"FREEZE_PLANTED_MARKER": self.PLANTED, "ANTHROPIC_API_KEY": "sk-" + self.PLANTED,
                "SECRET_TOKEN": "tok-" + self.PLANTED, "CLAUDE_CODE_EFFORT_LEVEL": "eff-" + self.PLANTED.upper(),
                "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "teams-" + self.PLANTED.upper(),
                "CLAUDE_CODE_SUBAGENT_MODEL": "SUB-" + self.PLANTED.upper()}

    def leaks(self, cap: Capture, extra_env: dict[str, str]) -> list[str]:
        host = self.host
        texts = {"stdout": cap.proc.stdout, "stderr": cap.proc.stderr,
                 "sanitized": cap.sanitized.read_text(encoding="utf-8") if cap.sanitized.exists() else "",
                 "full": cap.full.read_text(encoding="utf-8") if cap.full.exists() else ""}
        forbidden = {"settings secret": host.settings_marker, "unit secret": host.unit_marker,
                     "credential secret": host.credential_marker, "home path": str(host.home), "repo path": str(host.repo),
                     "test root": str(host.root), "bin path": str(host.bin), "fake user": host.user}
        forbidden.update({f"env {key}": value for key, value in extra_env.items()})
        words = {"real user": pwd.getpwuid(os.getuid()).pw_name, "hostname": socket.gethostname().split(".")[0]}
        return find_leaks(texts, forbidden, words)

    def test_outputs_contain_no_environment_value_user_host_or_path(self):
        planted = self.planted_env()
        cap = self.host.capture(self.tool, "privacy", env=self.host.env(**planted))
        self.assertEqual(cap.proc.returncode, 0, cap.proc.stdout + cap.proc.stderr)
        self.assertEqual(self.leaks(cap, planted), [])
        self.assertIs(cap.value("claude.process.effort_level_unset"), False, "the variable is set, only that is recorded")
        self.assertEqual(cap.value("claude.process.agent_teams_env"), "other")
        self.assertEqual(cap.value("claude.process.subagent_model_env"), "other", "an unrecognizable alias is never printed")

    def test_sanitized_output_holds_no_path_character_in_any_string(self):
        cap = self.capture("plain")

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, inner in value.items():
                    yield key
                    yield from strings(inner)
            elif isinstance(value, list):
                for inner in value:
                    yield from strings(inner)

        bad = [s for s in strings(json.loads(cap.sanitized.read_text(encoding="utf-8"))) if any(c in s for c in "/\\~")]
        self.assertEqual(bad, [])
        full = cap.full.read_text(encoding="utf-8")
        self.assertIn("~/.claude/settings.json", full, "the private capture stores home paths as ~/...")
        self.assertNotIn(str(self.host.home), full)

    def test_private_paths_are_home_or_repo_relative_and_only_in_the_full_capture(self):
        paths = {i["id"]: i["path"] for i in self.capture("paths").items("full").values() if "path" in i}
        self.assertEqual(paths["claude.settings.user.sha256"], "~/.claude/settings.json")
        self.assertEqual(paths["repo.sealed.RUNBOOK.md"], f"<repo>/{SEALED}/RUNBOOK.md")
        self.assertEqual(paths["services.ecosystem-otelcol.config_sha256"], "~/.config/ecosystem-observability/collector.yaml")

    def test_capture_refuses_when_an_environment_value_would_be_written(self):
        """A value of the environment that the output would contain (here the claude version line) stops the capture."""
        result = self.host.capture(self.tool, "guard", env=self.host.env(FREEZE_PLANTED_VERSION="2.1.284 (Claude Code)"))
        self.assertEqual(result.proc.returncode, 3, result.proc.stdout + result.proc.stderr)
        self.assertFalse(result.sanitized.exists() or result.full.exists(), "a refused capture writes no file")
        self.assertNotIn("2.1.284", result.proc.stderr + result.proc.stdout, "the refusal does not echo the value")
        self.assertIn("FREEZE_PLANTED_VERSION", result.proc.stderr, "but it names the variable, which is not a value")

    def test_a_value_or_name_that_the_catalogue_already_contains_is_not_a_leak(self):
        """A host whose user is called `claude` or whose variable equals a catalogue id must still be able to capture."""
        env = self.host.env(FREEZE_COINCIDENCE="claude.mcp_count", USER="claude", LOGNAME="claude")
        cap = self.host.capture(self.tool, "coincide", env=env)
        self.assertEqual(cap.proc.returncode, 0, cap.proc.stdout + cap.proc.stderr)
        self.assertEqual(cap.status("claude.mcp_count"), "ok")
        structural = self.host.capture(self.tool, "structural", env=self.host.env(USER="status", LOGNAME="reason"))
        self.assertEqual(structural.proc.returncode, 0, structural.proc.stdout + structural.proc.stderr)

    def test_the_user_name_in_a_family_id_is_refused_and_nothing_is_written(self):
        self.host.write(self.host.home / ".claude" / "hooks" / f"{self.host.user}.py", "hook\n")
        result = self.host.capture(self.tool, "identity")
        self.assertEqual(result.proc.returncode, 3, result.proc.stdout + result.proc.stderr)
        self.assertFalse(result.sanitized.exists() or result.full.exists())
        self.assertIn("hooks.installed.*", result.proc.stderr, "the refusal names the family, not the member")
        self.assertNotIn(self.host.user, result.proc.stdout + result.proc.stderr, "and never the value")

    def test_capture_never_requests_the_unit_environment(self):
        self.capture("units")
        requested = (self.host.data / "systemctl.log").read_text(encoding="utf-8")
        self.assertNotIn("Environment", requested)
        self.assertTrue(requested.strip())
        self.assertTrue(all(line.startswith("--user show ") for line in requested.splitlines()), requested)


class CompareTests(HostCase):
    def test_identical_captures_do_not_drift(self):
        first, second = self.capture("a"), self.capture("b")
        proc = self.compare(first, second)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        kinds = self.kinds(proc)
        self.assertEqual({k for k in kinds if k != "INFO"}, set(), proc.stdout)
        self.assertTrue(set(kinds.get("INFO", [])) <= {i for i in first.items() if i.startswith(("time.", "capacity."))})
        self.assertIn("compare: frozen_drift=0 frozen_missing=0 frozen_error=0", proc.stdout)

    def test_informational_changes_never_fail(self):
        first = self.capture("a")
        array = json.loads(json.dumps(CLAUDE_P_ARRAY))
        array[2]["rate_limit_info"]["unifiedWindows"]["five_hour"]["utilization"] = 0.61
        self.host.fake_text("claude.p.verbose.json", json.dumps(array))
        second = self.capture("b")
        proc = self.compare(first, second)
        kinds = self.kinds(proc)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("capacity.claude.five_hour_utilization_fraction", kinds.get("INFO", []), proc.stdout)
        self.assertFalse({"DRIFT", "MISSING", "ERROR"} & set(kinds), proc.stdout)
        third = self.capture("c", probe=False)  # the informational items become missing on one side: listed, never a failure
        skipped = self.compare(second, third)
        self.assertEqual(skipped.returncode, 0, skipped.stdout)
        self.assertIn("capacity.claude.seven_day_resets_at_utc", self.kinds(skipped).get("INFO", []), skipped.stdout)

    def test_item_present_on_one_side_only_is_reported(self):
        first = self.capture("a")
        self.host.write(self.host.home / ".claude" / "hooks" / "added-hook.py", "new hook\n")
        second = self.capture("b")
        proc = self.compare(first, second)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(self.kinds(proc).get("MISSING"), ["hooks.installed.added-hook.py"], proc.stdout)

    def test_error_status_on_a_frozen_item_fails_the_comparison(self):
        self.host.fake_text("rtk.exit", "3")
        first, second = self.capture("a"), self.capture("b")
        self.assertEqual(first.status("tools.rtk.version"), "error")
        proc = self.compare(first, second)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("tools.rtk.version", self.kinds(proc).get("ERROR", []), proc.stdout)

    def test_missing_on_both_sides_is_identical_not_drift(self):
        first, second = self.capture("a"), self.capture("b")
        self.assertEqual(first.status("services.cognee-live.main_pid"), "missing")
        self.assertNotIn("services.cognee-live.main_pid", self.compare(first, second).stdout)

    def test_full_and_sanitized_captures_compare_alike_and_hashes_print_short_by_default(self):
        first = self.capture("a")
        self.host.append_byte(self.host.repo / SEALED / "RUNBOOK.md")
        second = self.capture("b")
        mixed = self.host.run(self.tool, "compare", str(first.full), str(second.sanitized))
        self.assertEqual(mixed.returncode, 1, mixed.stdout)
        line = [row for row in mixed.stdout.splitlines() if row.startswith("DRIFT repo.sealed.RUNBOOK.md ")][0]
        self.assertNotIn(second.value("repo.sealed.RUNBOOK.md"), line, "hashes print abbreviated by default")
        self.assertIn(second.value("repo.sealed.RUNBOOK.md"), self.compare(first, second, "--full").stdout)

    def test_unreadable_or_foreign_input_is_a_usage_error(self):
        first = self.capture("a")
        junk = self.host.write(self.host.root / "junk.json", "{not json")
        foreign = self.host.write(self.host.root / "foreign.json", json.dumps({"schema": "other-v1", "items": []}))
        for other in (junk, foreign, self.host.root / "absent.json"):
            proc = self.host.run(self.tool, "compare", str(first.sanitized), str(other))
            self.assertEqual(proc.returncode, 2, f"{other.name}: {proc.stdout}{proc.stderr}")


class DriftTests(HostCase):
    """One test per catalogue class: a changed byte in a source of that class is reported per item id."""

    def drift(self, mutate, expected: list[str], label: str = "x") -> None:
        first = self.capture(f"{label}-a")
        mutate()
        self.assert_drift(first, self.capture(f"{label}-b"), expected)

    def test_repo_class_drift(self):
        sealed = self.host.repo / SEALED / "RUNBOOK.md"
        self.drift(lambda: self.host.append_byte(sealed), ["repo.sealed.RUNBOOK.md", "repo.tree_clean"])
        self.host.commit_all("baseline")
        before = self.capture("h-a")
        self.host.write(self.host.repo / "another.txt", "x\n")
        self.host.commit_all("advance")
        self.assert_drift(before, self.capture("h-b"), ["repo.head"])

    def test_roles_class_drift(self):
        role = self.host.home / ".claude" / "agents" / "isolated-builder.md"
        self.drift(lambda: self.host.append_byte(role),
                   ["roles.isolated-builder.user", "roles.isolated-builder.identical_across_copies"])

    def test_hooks_class_drift(self):
        hook = self.host.home / ".claude" / "hooks" / "token-lanes-block.md"
        self.drift(lambda: self.host.append_byte(hook), ["hooks.installed.token-lanes-block.md", "hooks.carriers_match_repo"])

    def test_claude_class_drift(self):
        first = self.capture("c-a")
        self.host.append_byte(self.host.home / ".claude" / "settings.json")
        self.host.fake_text("claude.version", "2.1.285 (Claude Code)\n")
        listing = (self.host.data / "claude.mcp").read_text(encoding="utf-8")
        self.host.fake_text("claude.mcp", listing.replace("--project-from-cwd - ✔ Connected", "--project-from-cwd - ✘ Failed to connect"))
        self.host.append_byte(self.host.home / ".local" / "share" / "codex-ecosystem" / "bin" / "claude")
        self.assert_drift(first, self.capture("c-b"), ["claude.launcher.sha256", "claude.launcher.size", "claude.mcp.serena",
                                                       "claude.settings.user.sha256", "claude.version"])

    def test_codex_class_drift(self):
        self.drift(lambda: self.host.append_byte(self.host.home / ".codex" / "config.toml"), ["codex.config.sha256"])
        before = self.capture("d-a")
        (self.host.home / ".codex" / "stack-worker.config.toml").unlink()
        self.assert_drift(before, self.capture("d-b"), ["codex.stack_worker_profile.present", "codex.stack_worker_profile.sha256"])

    def test_tools_class_drift(self):
        first = self.capture("t-a")
        self.host.append_byte(self.host.home / ".config" / "rtk" / "config.toml")
        self.host.fake_text("qmd.status", QMD_STATUS.format(home=str(self.host.home)).replace("3284 embedded", "3300 embedded"))
        package = self.host.home / ".local" / "share" / "native-token-report" / "tokenizer" / "node_modules" / "gpt-tokenizer"
        self.host.append_byte(package / "cjs" / "bpeRanks" / "o200k_base.js")
        self.host.append_byte(self.host.parser_dir / "node_modules" / "tree-sitter-bash" / "tree-sitter-bash.wasm")
        self.host.append_byte(self.host.repo / "tools" / "token-report" / "token_manifest.py")
        self.host.commit_all("token manifest")
        self.assert_drift(first, self.capture("t-b"), [
            "repo.head", "tools.parser.all_match_pin", "tools.parser.file.tree-sitter-bash:tree-sitter-bash.wasm",
            "tools.qmd.vectors", "tools.rtk.config.sha256", "tools.token_manifest.sha256", "tools.tokenizer.o200k_bpe_ranks.sha256"])

    def test_adoption_derived_items_drift(self):
        first = self.capture("w-a")
        wiring = json.loads(json.dumps(ADOPTION_WIRING))
        wiring["client_wiring"]["codex"]["ai_memory_hook_events_trusted"] = 6
        pins = json.loads(json.dumps(ADOPTION_PINS))
        pins["profiles"][0]["pinned_versions"][0]["matches_pin"] = False
        pins["pinned_versions_match"] = False
        self.host.set_repo_scripts(wiring, pins, CODEX_QUOTA)
        self.host.commit_all("scripts")
        self.assert_drift(first, self.capture("w-b"), ["codex.wiring.ai_memory_hook_events_trusted", "repo.head",
                                                       "tools.pinned.codex", "tools.pinned_versions_match"])

    def test_services_class_drift(self):
        first = self.capture("s-a")
        observability = f"{self.host.home}/.config/ecosystem-observability"
        self.host.set_unit("ecosystem-otelcol", main_pid=4242, exec_start=f"/usr/bin/otelcol --config=file:{observability}/collector.yaml")
        self.host.append_byte(self.host.home / ".config" / "ecosystem-observability" / "loki.yaml")
        self.host.set_unit("omniroute", main_pid=1005, exec_start="/opt/omniroute/server.js --port 20128", restarts=2)
        self.assert_drift(first, self.capture("s-b"), ["services.ecosystem-otelcol.main_pid", "services.ecosystem-loki.config_sha256",
                                                       "services.omniroute.n_restarts"])

    def test_gateways_class_drift(self):
        server = Loopback()
        self.addCleanup(server.close)
        server.routes = {"/health": (200, {"build": "abc1234", "uptime": 5}, {}), "/v1/models": (200, {"data": [1, 2]}, {})}
        config = self.host.write(self.host.root / "freeze.json", json.dumps({"gateways": [{
            "id": "gw", "base_url": server.base_url,
            "routes": [{"id": "health", "path": "/health", "ignore_keys": ["uptime", "build"]}, {"id": "models", "path": "/v1/models"}],
            "build_id": {"route": "health", "field": "build"}}]}))
        first = self.capture("g-a", "--config", str(config))
        server.routes["/v1/models"] = (200, {"data": [1, 2, 3]}, {})
        second = self.capture("g-b", "--config", str(config))
        self.assert_drift(first, second, ["gateways.gw.route.models"])
        server.routes["/health"] = (200, {"build": "def5678", "uptime": 9}, {})
        self.assert_drift(second, self.capture("g-c", "--config", str(config)), ["gateways.gw.build_id"])


class CheckTests(HostCase):
    def test_identical_expectations_pass_and_a_sanitized_capture_is_a_valid_expectation_file(self):
        seal, later = self.capture("seal"), self.capture("open")
        proc = self.check(later, seal.sanitized)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        kinds = self.kinds(proc)
        self.assertNotIn("FAIL", kinds)
        frozen = [i for i, v in seal.items().items() if v["class"] == "frozen"]
        self.assertEqual(sorted(kinds["PASS"]), sorted(frozen), "PASS is printed per frozen item id")
        self.assertIn(f"check: pass={len(frozen)} fail=0", proc.stdout)

    def test_a_single_mismatch_fails_only_that_item(self):
        seal = self.capture("seal")
        self.host.append_byte(self.host.home / ".claude" / "settings.json")
        proc = self.check(self.capture("open"), seal.sanitized)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(self.kinds(proc)["FAIL"], ["claude.settings.user.sha256"], proc.stdout)
        self.assertIn("fail=1", proc.stdout)

    def test_a_tracked_file_change_fails_its_item_and_the_clean_tree_item(self):
        seal = self.capture("seal")
        self.host.append_byte(self.host.repo / "tools" / "skill-usage" / "skill_usage.py")
        proc = self.check(self.capture("open"), seal.sanitized)
        self.assertEqual(sorted(self.kinds(proc)["FAIL"]), ["repo.tool.skill_usage.py", "repo.tree_clean"], proc.stdout)
        self.assertEqual(proc.returncode, 1)

    def test_missing_expected_item_fails_and_extra_family_member_fails(self):
        seal = self.capture("seal")
        expected = json.loads(seal.sanitized.read_text(encoding="utf-8"))
        expected["items"].append({"id": "repo.only_in_expectations", "class": "frozen", "status": "ok", "value": "abc", "method": "x"})
        expected["items"] = [i for i in expected["items"] if i["id"] != "hooks.installed.secret_path_guard.py"]
        path = self.host.write(self.host.root / "expected.json", json.dumps(expected))
        proc = self.check(self.capture("open"), path)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(sorted(self.kinds(proc)["FAIL"]), ["hooks.installed.secret_path_guard.py", "repo.only_in_expectations"], proc.stdout)

    def test_informational_expected_items_are_not_checked(self):
        seal = self.capture("seal")
        expected = json.loads(seal.sanitized.read_text(encoding="utf-8"))
        for item in expected["items"]:
            if item["id"] == "capacity.codex.weekly_used_percent":
                item["value"] = 1
        path = self.host.write(self.host.root / "expected.json", json.dumps(expected))
        self.assertEqual(self.check(self.capture("open"), path).returncode, 0)

    def test_a_sealed_absence_passes_while_the_capture_is_absent_too(self):
        seal = self.capture("seal")
        self.assertEqual(seal.status("services.cognee-live.active_state"), "missing")
        self.assertEqual(self.check(self.capture("open"), seal.sanitized).returncode, 0)
        self.host.set_unit("cognee-live", main_pid=77, exec_start="/usr/bin/x --port 3800")
        proc = self.check(self.capture("later"), seal.sanitized)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("services.cognee-live.main_pid", self.kinds(proc)["FAIL"])

    def test_quiet_prints_only_failures_and_bad_input_is_a_usage_error(self):
        seal = self.capture("seal")
        proc = self.check(self.capture("open"), seal.sanitized, "--quiet")
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("PASS", proc.stdout)
        bad = self.host.write(self.host.root / "bad.json", json.dumps({"schema": "freeze-snapshot-v1", "items": "x"}))
        self.assertEqual(self.check(seal, bad).returncode, 2)
        self.assertEqual(self.check(seal, self.host.root / "absent.json").returncode, 2)


class ConfigTests(HostCase):
    def config(self, body: dict) -> Path:
        return self.host.write(self.host.root / "freeze.json", json.dumps(body))

    def test_credential_store_paths_are_refused(self):
        stores = ("~/.claude.json", "~/.claude/.credentials.json", "~/.codex/auth.json")
        for spelling in stores:
            for path in (spelling, str(self.host.home / spelling[2:]), f"~/.claude/../{spelling[2:]}"):
                out = self.host.root / "out-refused"
                result = self.host.capture(self.tool, "c", "--config", str(self.config({"files": [{"id": "x", "path": path}]})), out=out)
                self.expect_refused(result, "credential store")
                self.assertNotIn(self.host.credential_marker, result.proc.stdout + result.proc.stderr)
                self.assertFalse(out.exists() and list(out.iterdir()), "nothing is written")

    def test_a_symlink_to_a_credential_store_is_refused_by_identity(self):
        os.symlink(self.host.home / ".claude" / ".credentials.json", self.host.home / ".claude" / "innocent-name.json")
        result = self.host.capture(self.tool, "c", "--config", str(self.config({"files": [{"id": "x", "path": "~/.claude/innocent-name.json"}]})))
        self.expect_refused(result, "credential store")

    def test_paths_outside_the_repository_and_home_are_refused(self):
        outside = self.host.write(self.host.root / "outside.txt", "outside\n")
        for path in (str(outside), "/etc/hosts", "~/../outside.txt", "../outside.txt"):
            result = self.host.capture(self.tool, "c", "--config", str(self.config({"files": [{"id": "x", "path": path}]})))
            self.expect_refused(result, "outside the repository and the home directory")

    def test_list_frozen_applies_the_path_policy_without_a_checkout(self):
        """list-frozen runs from any directory; with no --repo the home directory is the only root."""
        for path in ("/etc/hosts", "~/../outside.txt", "../outside.txt", "~/.codex/auth.json"):
            proc = self.host.run(self.tool, "list-frozen", "--config", str(self.config({"files": [{"id": "x", "path": path}]})))
            self.assertEqual(proc.returncode, 2, f"{path}: {proc.stdout}{proc.stderr}")
        for path in ("tools/skill-usage/skill_usage.py", "~/.local/state/x.json", str(self.host.home / "y.txt")):
            proc = self.host.run(self.tool, "list-frozen", "--config", str(self.config({"files": [{"id": "x", "path": path}]})))
            self.assertEqual(proc.returncode, 0, f"{path}: {proc.stdout}{proc.stderr}")
            self.assertIn("extra.x", proc.stdout)

    def test_extra_files_units_and_overrides_are_captured(self):
        self.host.write(self.host.home / ".local" / "state" / "report" / "config.json", "{}\n")
        self.host.set_unit("extra-unit", main_pid=9, exec_start="/usr/bin/x --port 1")
        config = self.config({"files": [{"id": "report-config", "path": "~/.local/state/report/config.json"},
                                        {"id": "repo-note", "path": "tools/skill-usage/skill_usage.py", "class": "informational"}],
                              "units": ["extra-unit"], "qmd_index": "other-index"})
        cap = self.capture("cfg", "--config", str(config))
        self.assertEqual(cap.value("extra.report-config"), sha256_path(self.host.home / ".local" / "state" / "report" / "config.json"))
        self.assertEqual(cap.item("extra.repo-note")["class"], "informational")
        self.assertEqual(cap.value("services.extra-unit.main_pid"), 9)
        self.assertIn("--index other-index status", (self.host.data / "qmd.log").read_text(encoding="utf-8"))
        self.assertEqual(cap.item("extra.report-config", "full")["path"], "~/.local/state/report/config.json")
        listing = self.host.run(self.tool, "list-frozen", "--config", str(config), "--repo", str(self.host.repo))
        self.assertIn("extra.report-config", listing.stdout)
        self.assertIn("services.extra-unit.main_pid", listing.stdout)
        self.assertNotIn("extra.repo-note", listing.stdout, "an informational extra is listed only with --all")

    def test_a_configured_unit_can_be_informational_and_a_default_unit_cannot(self):
        """Paper-trading units run inside a run window and are recorded at its start and end, so their state must not fail."""
        self.host.set_unit("paper-unit", main_pid=5, exec_start="/usr/bin/x --port 1")
        config = self.config({"units": [{"name": "paper-unit", "class": "informational"}, "omniroute"]})
        first = self.capture("u-a", "--config", str(config))
        self.assertEqual(first.item("services.paper-unit.main_pid")["class"], "informational")
        self.assertEqual(first.item("services.omniroute.main_pid")["class"], "frozen")
        self.host.set_unit("paper-unit", main_pid=6, exec_start="/usr/bin/x --port 1", restarts=1)
        second = self.capture("u-b", "--config", str(config))
        proc = self.compare(first, second)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(sorted(k for k in self.kinds(proc).get("INFO", []) if k.startswith("services.")),
                         ["services.paper-unit.main_pid", "services.paper-unit.n_restarts"])
        for body in ({"units": [{"name": "omniroute", "class": "informational"}]},
                     {"units": [{"name": "x", "class": "other"}]}, {"units": [{"name": "x", "extra": 1}]}, {"units": [{"class": "frozen"}]}):
            result = self.host.capture(self.tool, "bad", "--config", str(self.config(body)))
            self.assertEqual(result.proc.returncode, 2, f"{body}: {result.proc.stdout}{result.proc.stderr}")

    def test_invalid_configuration_is_a_usage_error(self):
        bad = ({"nope": 1}, {"files": [{"id": "has space", "path": "~/x"}]}, {"files": [{"id": "x"}]}, {"units": ["../evil"]},
               {"units": ["-p"]}, {"gateways": [{"id": "g", "base_url": "http://example.com", "routes": []}]}, {"files": "x"},
               {"qmd_index": ["a"]})
        for body in bad:
            result = self.host.capture(self.tool, "c", "--config", str(self.config(body)))
            self.assertEqual(result.proc.returncode, 2, f"{body}: {result.proc.stdout}{result.proc.stderr}")
        absent = self.host.run(self.tool, "capture", "--label", "c", "--out", str(self.host.out), "--repo", str(self.host.repo),
                               "--config", str(self.host.root / "absent.json"))
        self.assertEqual(absent.returncode, 2)

    def test_parser_location_can_be_overridden(self):
        moved = self.host.home / "moved-parser"
        shutil.copytree(self.host.parser_dir, moved)
        shutil.rmtree(self.host.parser_dir)
        before = self.capture("p-a")
        self.assertIs(before.value("tools.parser.all_match_pin"), False, "nothing installed cannot match the pin")
        self.assertEqual(before.status("tools.parser.file.tree-sitter-bash:package.json"), "missing")
        cap = self.capture("p-b", "--config", str(self.config({"parser_dir": "~/moved-parser"})))
        self.assertIs(cap.value("tools.parser.all_match_pin"), True)

    def test_a_configured_file_that_is_not_a_regular_file_is_an_error_and_never_blocks(self):
        os.mkfifo(self.host.home / "pipe")
        config = self.config({"files": [{"id": "pipe", "path": "~/pipe"}, {"id": "dir", "path": "~/.claude"}]})
        cap = self.host.capture(self.tool, "fifo", "--config", str(config), timeout=60)
        self.assertEqual(cap.proc.returncode, 0, cap.proc.stdout + cap.proc.stderr)
        self.assertEqual((cap.status("extra.pipe"), cap.item("extra.pipe")["reason"]), ("error", "not_regular_file"))
        self.assertEqual((cap.status("extra.dir"), cap.item("extra.dir")["reason"]), ("error", "is_directory"))

    def test_a_parser_pin_with_an_unusable_key_is_unrecognized_not_partly_read(self):
        pin_path = self.host.repo / "examples" / "claude-native" / "workflows" / "shell-parser.pin.json"
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        pin["files"]["node_modules/tree-sitter-bash/has space.json"] = "0" * 64
        self.host.write(pin_path, json.dumps(pin))
        cap = self.capture("pin")
        self.assertEqual((cap.status("tools.parser.all_match_pin"), cap.item("tools.parser.all_match_pin")["reason"]),
                         ("error", "unrecognized_pin"))
        self.assertFalse([i for i in cap.items() if i.startswith("tools.parser.file.")])

    def test_tokenizer_location_can_be_overridden(self):
        moved = self.host.home / "moved-tokenizer"
        shutil.copytree(self.host.home / ".local" / "share" / "native-token-report" / "tokenizer", moved)
        shutil.rmtree(self.host.home / ".local" / "share" / "native-token-report")
        self.assertEqual(self.capture("k-a").status("tools.tokenizer.version"), "missing")
        cap = self.capture("k-b", "--config", str(self.config({"tokenizer_prefix": "~/moved-tokenizer"})))
        self.assertEqual(cap.value("tools.tokenizer.version"), "3.4.0")
        self.assertEqual(cap.status("tools.tokenizer.o200k_base.sha256"), "ok")


class GatewayTests(HostCase):
    def setUp(self):
        super().setUp()
        self.server = Loopback()
        self.addCleanup(self.server.close)
        self.server.routes = {"/health": (200, {"build": "abc1234"}, {"X-Build": "hdr-99"}), "/v1/models": (200, {"b": 1, "a": [2]}, {}),
                              "/denied": (401, {"error": "auth"}, {}), "/text": (200, b"not json", {}),
                              "/moved": (302, b"", {"Location": self.server.base_url + "/target"}),
                              "/target": (200, {"followed": True}, {})}

    def gateway(self, routes, build_id=None, base_url=None) -> Path:
        entry = {"id": "gw", "base_url": base_url or self.server.base_url, "routes": routes}
        if build_id:
            entry["build_id"] = build_id
        return self.host.write(self.host.root / "freeze.json", json.dumps({"gateways": [entry]}))

    def test_digest_rule_is_sha256_of_sorted_json_and_build_id_comes_from_the_report(self):
        config = self.gateway([{"id": "models", "path": "/v1/models"}, {"id": "health", "path": "/health"}], {"route": "health", "field": "build"})
        env = self.host.env(HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9", ALL_PROXY="http://127.0.0.1:9")
        cap = self.capture("gw", "--config", str(config), env=env)
        expected = hashlib.sha256(json.dumps({"b": 1, "a": [2]}, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(cap.value("gateways.gw.route.models"), expected)
        self.assertEqual(cap.value("gateways.gw.build_id"), "abc1234")
        self.assertEqual(cap.item("gateways.gw.build_id")["class"], "frozen")
        self.assertEqual([seen["path"] for seen in self.server.seen], ["/v1/models", "/health"])

    def test_no_credential_is_sent_and_no_redirect_is_followed(self):
        config = self.gateway([{"id": "moved", "path": "/moved"}, {"id": "health", "path": "/health"}])
        env = self.host.env(ANTHROPIC_API_KEY="sk-planted", OPENAI_API_KEY="sk-planted-2", HTTP_PROXY="http://127.0.0.1:9")
        cap = self.capture("gw", "--config", str(config), env=env)
        for seen in self.server.seen:
            self.assertFalse({"authorization", "cookie", "x-api-key", "proxy-authorization"} & set(seen["headers"]), seen)
        self.assertEqual(cap.status("gateways.gw.route.moved"), "error")
        self.assertEqual(cap.status("gateways.gw.route.health"), "ok")
        self.assertEqual([s["path"] for s in self.server.seen], ["/moved", "/health"], "the redirect target was not requested")

    def test_auth_failure_is_an_error_status_not_a_bypass(self):
        cap = self.capture("gw", "--config", str(self.gateway([{"id": "denied", "path": "/denied"}, {"id": "text", "path": "/text"},
                                                                {"id": "gone", "path": "/absent"}])))
        for route in ("denied", "text", "gone"):
            self.assertEqual(cap.status(f"gateways.gw.route.{route}"), "error", route)
        self.assertEqual(cap.value("gateways.gw.route.denied"), "http_401")
        self.assertEqual(cap.value("gateways.gw.route.text"), "not_json")
        self.assertEqual(len([s for s in self.server.seen if s["path"] == "/denied"]), 1, "one unauthenticated request")

    def test_build_id_from_a_response_header(self):
        cap = self.capture("gw", "--config", str(self.gateway([{"id": "health", "path": "/health"}], {"route": "health", "header": "X-Build"})))
        self.assertEqual(cap.value("gateways.gw.build_id"), "hdr-99")

    def test_only_loopback_http_origins_and_plain_paths_are_accepted(self):
        for base in ("http://example.com", "http://192.0.2.1:80", "https://127.0.0.1:9", "http://user:pw@127.0.0.1:9",
                     "http://127.0.0.1:9/prefix", "ftp://127.0.0.1"):
            result = self.host.capture(self.tool, "c", "--config", str(self.gateway([{"id": "r", "path": "/x"}], base_url=base)))
            self.assertEqual(result.proc.returncode, 2, f"{base}: {result.proc.stdout}{result.proc.stderr}")
        for path in ("x", "/x?token=1", "//evil/x", "/x#f", "/x@y"):
            result = self.host.capture(self.tool, "c", "--config", str(self.gateway([{"id": "r", "path": path}])))
            self.assertEqual(result.proc.returncode, 2, f"{path}: {result.proc.stdout}{result.proc.stderr}")
        self.assertEqual(self.server.seen, [])

    def test_an_unreachable_gateway_is_an_error_status(self):
        self.server.close()
        cap = self.capture("gw", "--config", str(self.gateway([{"id": "health", "path": "/health"}])))
        self.assertEqual(cap.status("gateways.gw.route.health"), "error")
        self.assertEqual(cap.value("gateways.gw.route.health"), "unreachable")


class CapacityTests(HostCase):
    def test_codex_weekly_window_is_read_from_the_quota_script(self):
        cap = self.capture("q")
        self.assertEqual(cap.value("capacity.codex.weekly_used_percent"), 95)
        self.assertEqual(cap.value("capacity.codex.weekly_resets_at_utc"), "2026-10-04T00:35Z")
        quota = dict(CODEX_QUOTA, used_percent=12, window_minutes=300, resets_at_utc="2026-09-29T11:00Z",
                     secondary={"used_percent": 61, "window_minutes": 10080, "resets_at_utc": "2026-10-06T00:00Z"})
        self.host.set_repo_scripts(ADOPTION_WIRING, ADOPTION_PINS, quota)
        self.assertEqual(self.capture("q2").value("capacity.codex.weekly_used_percent"), 61, "the weekly window may be the secondary one")
        self.host.set_repo_scripts(ADOPTION_WIRING, ADOPTION_PINS, dict(CODEX_QUOTA, window_minutes=300))
        self.assertEqual(self.capture("q3").status("capacity.codex.weekly_used_percent"), "missing")

    def test_claude_windows_come_from_the_unified_windows_of_the_rate_limit_event(self):
        cap = self.capture("q")
        self.assertEqual(cap.value("capacity.claude.five_hour_utilization_fraction"), 0.52)
        self.assertEqual(cap.value("capacity.claude.seven_day_utilization_fraction"), 0.78)
        self.assertEqual(cap.value("capacity.claude.five_hour_resets_at_utc"), utc_minute(CLAUDE_RESETS["five_hour"]))
        self.assertEqual(cap.value("capacity.claude.seven_day_resets_at_utc"), utc_minute(CLAUDE_RESETS["seven_day"]))

    def test_the_probe_is_quiet_and_isolated(self):
        self.capture("q", env=self.host.env(OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=run", RTK_DB_PATH="/x/rtk.db"))
        argv = (self.host.data / "claude.p.argv").read_text(encoding="utf-8").split()
        self.assertEqual(argv[:3], ["-p", "OK", "--model"])
        for flag in ("haiku", "--output-format", "json", "--verbose", "--no-session-persistence", "--setting-sources", "project"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project", "the probe loads no user settings, hooks or MCP servers")
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertEqual((self.host.data / "claude.p.env").read_text(encoding="utf-8").split(), ["otel_unset", "rtk_unset"])
        cwd = Path((self.host.data / "claude.p.cwd").read_text(encoding="utf-8").strip()).resolve()
        self.assertNotEqual(cwd, self.host.repo.resolve())
        self.assertNotIn(self.host.repo.resolve(), cwd.parents)
        self.assertFalse(cwd.exists(), "the temporary working directory is removed")

    def test_no_usage_probe_skips_the_model_call(self):
        cap = self.capture("q", probe=False)
        self.assertFalse((self.host.data / "claude.p.argv").exists(), "the model call was skipped")
        for name in ("five_hour_utilization_fraction", "seven_day_resets_at_utc"):
            self.assertEqual(cap.status(f"capacity.claude.{name}"), "missing")
            self.assertEqual(cap.item(f"capacity.claude.{name}")["reason"], "skipped")

    def test_a_single_object_answer_or_no_rate_limit_event_is_missing_not_a_crash(self):
        self.host.fake_text("claude.p.verbose.json", json.dumps(CLAUDE_P_PLAIN))
        self.assertEqual(self.capture("a").status("capacity.claude.five_hour_utilization_fraction"), "missing")
        self.host.fake_text("claude.p.verbose.json", json.dumps([e for e in CLAUDE_P_ARRAY if e["type"] != "rate_limit_event"]))
        self.assertEqual(self.capture("b").status("capacity.claude.seven_day_utilization_fraction"), "missing")
        self.host.fake_text("claude.p.verbose.json", "not json at all")
        self.assertEqual(self.capture("c").status("capacity.claude.seven_day_utilization_fraction"), "error")

    def test_host_load_time_items_and_platform(self):
        cap = self.capture("q")
        self.assertEqual(len(cap.value("capacity.host.load_average")), 3)
        self.assertTrue(cap.value("time.capture_start_utc").endswith("Z"))
        self.assertLessEqual(cap.value("time.capture_start_utc"), cap.value("time.capture_end_utc"))
        self.assertEqual(cap.value("time.tool_sha256"), sha256_path(self.tool))
        head = subprocess.run([REAL_GIT, "-C", str(self.tool.parent), "rev-parse", "HEAD"], capture_output=True, text=True,
                              env=tests.hermetic_git_environment())
        if head.returncode == 0:
            self.assertEqual(cap.value("time.tool_revision"), head.stdout.strip())
        else:
            self.assertEqual(cap.status("time.tool_revision"), "missing")
        darwin = self.host.run(self.tool, "capture", "--label", "mac", "--out", str(self.host.out), "--repo", str(self.host.repo),
                               "--platform", "darwin", "--no-usage-probe")
        self.assertEqual(darwin.returncode, 0, darwin.stdout + darwin.stderr)
        mac = json.loads((self.host.out / "freeze-mac.sanitized.json").read_text(encoding="utf-8"))
        statuses = {i["id"]: i["status"] for i in mac["items"]}
        self.assertEqual(statuses["capacity.host.memory_available_mib"], "not_applicable")
        self.assertEqual(statuses["services.ecosystem-otelcol.main_pid"], "not_applicable")
        self.assertEqual(statuses["repo.head"], "ok")


class SettingsTests(HostCase):
    def settings(self, name: str, body) -> None:
        text = body if isinstance(body, str) else json.dumps(body)
        path = {"user": self.host.home / ".claude" / "settings.json", "project": self.host.repo / ".claude" / "settings.json",
                "local": self.host.repo / ".claude" / "settings.local.json"}[name]
        self.host.write(path, text)

    def test_derived_values_are_booleans_and_classes_read_from_the_whole_file(self):
        cap = self.capture("s")
        prefix = "claude.settings.user."
        self.assertEqual(cap.value(prefix + "sha256"), sha256_path(self.host.home / ".claude" / "settings.json"))
        self.assertIs(cap.value(prefix + "effort_level_env_unset"), True)
        self.assertEqual(cap.value(prefix + "agent_teams_env"), "1")
        self.assertEqual(cap.value(prefix + "subagent_model_env"), "opus")
        self.assertIs(cap.value(prefix + "has_model_settings"), True)
        self.assertIs(cap.value(prefix + "has_effort_level"), True)
        self.assertEqual(cap.value(prefix + "advisor_model"), "opus")
        project = "claude.settings.project."
        self.assertEqual(cap.value(project + "agent_teams_env"), "unset")
        self.assertEqual(cap.value(project + "subagent_model_env"), "unset")
        self.assertIs(cap.value(project + "has_model_settings"), False)
        self.assertEqual(cap.value(project + "advisor_model"), "unset")
        self.assertEqual(cap.value("claude.settings.local.agent_teams_env"), "unset")

    def test_effort_level_variable_teams_flag_and_model_alias_classes(self):
        self.settings("user", {"env": {"CLAUDE_CODE_EFFORT_LEVEL": "max", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "true",
                                       "CLAUDE_CODE_SUBAGENT_MODEL": "Not-An-Alias-" + "x" * 60}, "advisorModel": "claude-opus-4-5[1m]"})
        cap = self.capture("s")
        prefix = "claude.settings.user."
        self.assertIs(cap.value(prefix + "effort_level_env_unset"), False)
        self.assertEqual(cap.value(prefix + "agent_teams_env"), "other")
        self.assertEqual(cap.value(prefix + "subagent_model_env"), "other")
        self.assertEqual(cap.value(prefix + "advisor_model"), "claude-opus-4-5[1m]")
        self.assertIs(cap.value(prefix + "has_effort_level"), False)
        self.settings("user", {"env": {"CLAUDE_CODE_EFFORT_LEVEL": ""}})
        self.assertIs(self.capture("t").value(prefix + "effort_level_env_unset"), False, "set but empty is set")

    def test_process_environment_classes(self):
        cap = self.capture("p", env=self.host.env(CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS="1", CLAUDE_CODE_SUBAGENT_MODEL="opus"))
        self.assertIs(cap.value("claude.process.effort_level_unset"), True)
        self.assertEqual(cap.value("claude.process.agent_teams_env"), "1")
        self.assertEqual(cap.value("claude.process.subagent_model_env"), "opus")
        bare = self.capture("q")
        self.assertEqual(bare.value("claude.process.agent_teams_env"), "unset")
        self.assertEqual(bare.value("claude.process.subagent_model_env"), "unset")

    def test_an_unparsable_settings_file_keeps_its_hash_and_reports_error(self):
        self.settings("project", "{ not json")
        cap = self.capture("s")
        self.assertEqual(cap.value("claude.settings.project.sha256"), sha256_path(self.host.repo / ".claude" / "settings.json"))
        self.assertEqual(cap.status("claude.settings.project.agent_teams_env"), "error")
        self.assertEqual(cap.status("claude.settings.user.agent_teams_env"), "ok")

    def test_an_absent_local_settings_file_is_missing(self):
        (self.host.repo / ".claude" / "settings.local.json").unlink()
        cap = self.capture("s")
        self.assertEqual(cap.status("claude.settings.local.sha256"), "missing")
        self.assertEqual(cap.status("claude.settings.local.advisor_model"), "missing")

    def test_roles_report_each_copy_and_whether_all_four_are_identical(self):
        cap = self.capture("r")
        for role in ROLES:
            self.assertIs(cap.value(f"roles.{role}.identical_across_copies"), True)
            self.assertEqual(cap.value(f"roles.{role}.user"), sha256_bytes(f"role body {role}\n".encode()))
        self.host.append_byte(self.host.repo / "examples" / "claude-native" / "agents" / "source-scout.md")
        cap = self.capture("r2")
        self.assertIs(cap.value("roles.source-scout.identical_across_copies"), False)
        self.assertNotEqual(cap.value("roles.source-scout.examples"), cap.value("roles.source-scout.user"))
        (self.host.home / ".claude" / "agents" / "stack-researcher.md").unlink()
        cap = self.capture("r3")
        self.assertIs(cap.value("roles.stack-researcher.identical_across_copies"), False)
        self.assertEqual(cap.status("roles.stack-researcher.user"), "missing")

    def test_installed_carriers_are_compared_with_the_repository_copies_and_backups_are_skipped(self):
        cap = self.capture("h")
        self.assertIs(cap.value("hooks.carriers_match_repo"), True)
        self.assertIn("hooks.installed.secret_path_guard.py", cap.items())
        self.assertIn("hooks.installed.effort-default-guard.py", cap.items())
        self.assertFalse([i for i in cap.items() if ".bak" in i], "backup files are inert and not part of the frozen set")
        (self.host.home / ".claude" / "hooks" / "token-lanes-block.verifier.md").unlink()
        cap = self.capture("h2")
        self.assertEqual(cap.status("hooks.installed.token-lanes-block.verifier.md"), "missing")
        self.assertIs(cap.value("hooks.carriers_match_repo"), False)

    def test_pinned_versions_keep_null_for_unchecked_components_and_wiring_keeps_booleans_and_counts(self):
        cap = self.capture("p")
        self.assertEqual(cap.value("tools.pinned.codex"), {"version": "0.157.1", "checked": True, "matches_pin": True})
        self.assertEqual(cap.value("tools.pinned.context-mode"), {"version": "1.0.169", "checked": False, "matches_pin": None})
        self.assertIs(cap.value("tools.pinned_versions_match"), True)
        self.assertIs(cap.value("claude.wiring.rtk_hook"), True)
        self.assertEqual(cap.value("claude.wiring.ai_memory_hook_events"), 8)
        self.assertIs(cap.value("claude.wiring.project.codex_mcp_servers_present.serena"), False)
        self.assertEqual(cap.value("codex.wiring.ai_memory_hook_events_trusted"), 7)
        self.assertIs(cap.value("codex.wiring.mcp_servers_present.serena"), True)
        self.assertIs(cap.value("wiring.complete"), True)

    def test_parser_pin_is_missing_without_the_pin_file_and_compares_installed_bytes_with_it(self):
        cap = self.capture("pin")
        self.assertIs(cap.value("tools.parser.all_match_pin"), True)
        for relative, text in self.host.parser_files.items():
            key = relative.replace("node_modules/", "", 1).replace("/", ":")
            self.assertEqual(cap.value(f"tools.parser.file.{key}"), sha256_bytes(text.encode()))
        (self.host.repo / "examples" / "claude-native" / "workflows" / "shell-parser.pin.json").unlink()
        cap = self.capture("nopin")
        self.assertEqual(cap.status("tools.parser.all_match_pin"), "missing")
        self.assertEqual(cap.status("repo.workflow.shell-parser.pin.json"), "missing")
        self.assertFalse([i for i in cap.items() if i.startswith("tools.parser.file.")])

    def test_mcp_servers_keep_names_and_connected_flags_only(self):
        cap = self.capture("m")
        servers = {i[len("claude.mcp."):]: v["value"] for i, v in cap.items().items() if i.startswith("claude.mcp.")}
        self.assertEqual(servers, {"plugin:fixture-plugin:fixture-plugin": True, "ai-memory": True, "serena": True, "qmd": True})
        listing = (self.host.data / "claude.mcp").read_text(encoding="utf-8")
        self.host.fake_text("claude.mcp", listing.replace("--index fixture-index mcp - ✔ Connected", "--index fixture-index mcp - ✘ Failed to connect"))
        self.assertIs(self.capture("m2").value("claude.mcp.qmd"), False)


class ResilienceTests(HostCase):
    def test_missing_tool_is_status_missing_and_capture_continues(self):
        (self.host.bin / "qmd").unlink()
        (self.host.bin / "systemctl").unlink()
        cap = self.capture("m")
        for name in ("documents", "vectors", "pending", "orphaned"):
            self.assertEqual(cap.status(f"tools.qmd.{name}"), "missing", name)
        self.assertEqual(cap.status("services.ecosystem-otelcol.active_state"), "missing")
        self.assertEqual(cap.status("services.ecosystem-otelcol.config_sha256"), "missing")
        self.assertEqual(cap.status("claude.version"), "ok")
        self.assertEqual(cap.status("repo.head"), "ok")

    def test_a_tool_that_exits_nonzero_or_prints_something_odd_is_an_error_status(self):
        self.host.fake_text("codex.exit", "1")
        self.host.fake_text("node.version", "/home/x/bin/node is at ~/somewhere\n")
        cap = self.capture("e")
        self.assertEqual(cap.status("codex.version"), "error")
        self.assertEqual(cap.status("tools.node.version"), "error")
        self.assertIsNone(cap.value("tools.node.version"), "an unrecognizable version line is not recorded")

    def test_no_adoption_status_script_gives_missing_items(self):
        (self.host.repo / "scripts" / "adoption_status.py").unlink()
        cap = self.capture("a")
        self.assertEqual(cap.status("tools.pinned_versions_match"), "missing")
        self.assertFalse([i for i in cap.items() if i.startswith(("tools.pinned.", "claude.wiring.", "codex.wiring."))])

    def test_a_file_that_cannot_be_read_is_an_error_not_an_abort(self):
        target = self.host.home / ".codex" / "AGENTS.md"
        target.chmod(0)
        self.addCleanup(target.chmod, 0o644)
        if os.access(target, os.R_OK):
            self.skipTest("running with privileges that ignore file modes")
        cap = self.capture("u")
        self.assertEqual(cap.status("codex.agents_md.sha256"), "error")
        self.assertEqual(cap.status("codex.rtk_md.sha256"), "ok")

    def test_qmd_index_counts_treat_absent_lines_as_zero(self):
        self.host.fake_text("qmd.status", QMD_STATUS_ZERO.format(home=str(self.host.home)))
        cap = self.capture("z")
        self.assertEqual((cap.value("tools.qmd.documents"), cap.value("tools.qmd.vectors")), (288, 3284))
        self.assertEqual((cap.value("tools.qmd.pending"), cap.value("tools.qmd.orphaned")), (0, 0))
        self.host.fake_text("qmd.status", "QMD Status\n\nsomething else entirely\n")
        self.assertEqual(self.capture("y").status("tools.qmd.documents"), "error")

    def test_services_read_the_config_path_only_from_the_unit_and_apply_the_path_policy(self):
        cap = self.capture("s")
        folder = self.host.home / ".config" / "ecosystem-observability"
        self.assertEqual(cap.value("services.ecosystem-otelcol.config_sha256"), sha256_path(folder / "collector.yaml"))
        self.assertEqual(cap.value("services.ecosystem-loki.config_sha256"), sha256_path(folder / "loki.yaml"))
        self.assertEqual(cap.value("services.ecosystem-prometheus.config_sha256"), sha256_path(folder / "prometheus.yml"))
        self.assertEqual(cap.value("services.ecosystem-grafana.config_sha256"), sha256_path(folder / "grafana.ini"))
        for unit in NO_CONFIG_UNITS:
            self.assertEqual(cap.status(f"services.{unit}.config_sha256"), "not_applicable")
        self.host.set_unit("ecosystem-otelcol", main_pid=1, exec_start="/usr/bin/otelcol --config=/etc/passwd")
        moved = self.capture("s2")
        self.assertEqual(moved.status("services.ecosystem-otelcol.config_sha256"), "error")
        self.assertEqual(moved.item("services.ecosystem-otelcol.config_sha256")["reason"], "refused_path")
        self.host.set_unit("ecosystem-otelcol", main_pid=1, exec_start="/usr/bin/otelcol --config=https://example.invalid/c.yaml")
        self.assertEqual(self.capture("s3").status("services.ecosystem-otelcol.config_sha256"), "error")

    def test_unit_state_is_read_with_one_call_per_unit_named_exactly(self):
        self.capture("s")
        log = (self.host.data / "systemctl.log").read_text(encoding="utf-8").splitlines()
        self.assertTrue(all(line.startswith("--user show ") and " -p " in line for line in log), log[:2])
        self.assertEqual([line.split()[2] for line in log], list(UNITS))


class GitTests(HostCase):
    def test_every_git_call_avoids_optional_locks_and_the_index_is_untouched(self):
        index = self.host.repo / ".git" / "index"
        before = index.read_bytes()
        os.utime(self.host.repo / SEALED / "RUNBOOK.md", (1, 1))  # a stat change that a plain git status would refresh
        self.capture("g")
        calls = (self.host.data / "git.log").read_text(encoding="utf-8").splitlines()
        self.assertTrue(calls)
        self.assertTrue(all("--no-optional-locks" in line.split() for line in calls), calls)
        self.assertEqual(index.read_bytes(), before, "the capture must not rewrite the checkout's index")

    def test_tracked_modification_is_not_clean_and_untracked_files_are_ignored(self):
        self.host.write(self.host.repo / "untracked.txt", "x\n")
        self.assertIs(self.capture("a").value("repo.tree_clean"), True)
        self.host.append_byte(self.host.repo / "tools" / "skill-usage" / "skill_usage.py")
        self.assertIs(self.capture("b").value("repo.tree_clean"), False)

    def test_inherited_git_variables_do_not_redirect_the_checkout(self):
        other = self.host.root / "other-repo"
        subprocess.run([REAL_GIT, "init", "-q", str(other)], env=tests.hermetic_git_environment(), check=True)
        env = self.host.env(GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other), GIT_INDEX_FILE=str(other / ".git" / "index"))
        cap = self.capture("g", env=env)
        self.assertEqual(cap.value("repo.head"), self.host.git("rev-parse", "HEAD").strip())

    def test_a_directory_that_is_not_a_checkout_is_a_usage_error(self):
        proc = self.host.run(self.tool, "capture", "--label", "x", "--out", str(self.host.out), "--repo", str(self.host.home))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)


class ParserTests(unittest.TestCase):
    """The parsers, called directly, against the shapes observed on a real host."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(TOOL.parent))
        sys.modules.pop("freeze_snapshot", None)
        cls.module = importlib.import_module("freeze_snapshot")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(TOOL.parent))

    def api(self, name: str):
        found = getattr(self.module, name, None)
        if found is None:
            raise AssertionError(f"freeze_snapshot.{name} is not defined")
        return found

    def test_parse_mcp_list_reads_only_the_server_block(self):
        text = MCP_LIST.format(home="/fake/home", repo="/fake/repo")
        parse = self.api("parse_mcp_list")
        self.assertEqual(parse(text), {"plugin:fixture-plugin:fixture-plugin": True, "ai-memory": True, "serena": True, "qmd": True})
        mixed = ("Checking MCP server health…\n\n"
                 "qmd: /x/qmd mcp - ✘ Failed to connect\n"
                 "serena: /x/serena start - ! Needs authentication\n"
                 "ai-memory: http://127.0.0.1:1/mcp (HTTP) - ✔ Connected\n"
                 "odd name: has a space - ✔ Connected\n"
                 "\nMCP config diagnostics\n\nLocation: /p - q [project: /r - s]\n")
        self.assertEqual(parse(mixed), {"qmd": False, "serena": False, "ai-memory": True})
        other = "Checking MCP server health\u2026\n\na: x - \u2718 Disconnected\nb: x - Connecting...\nc: x - \u2714 Connected\n"
        self.assertEqual(parse(other), {"a": False, "b": False, "c": True})
        detail = "Checking MCP server health\u2026\n\nd: x - \u2714 Connected (12 tools)\ne: x - \u2718 Failed to connect (Connected earlier)\n"
        self.assertEqual(parse(detail), {"d": True, "e": False}, "a Connected status may carry a suffix; the word must lead")
        self.assertEqual(parse("Checking MCP server health…\n\n"), {})
        self.assertEqual(parse("No MCP servers configured\n"), {})
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("something unrelated\n"))

    def test_parse_systemd_show_keys_by_property_name_in_any_order(self):
        parsed = self.api("parse_systemd_show")(
            "NRestarts=2\nMainPID=99\nExecStart={ path=/x ; argv[]=/x --a=b ; ignore_errors=no }\nActiveState=active\n")
        self.assertEqual((parsed["NRestarts"], parsed["MainPID"], parsed["ActiveState"]), ("2", "99", "active"))
        self.assertTrue(parsed["ExecStart"].startswith("{ path=/x ; argv[]=/x --a=b"))

    def test_exec_start_config_path_recognises_the_flag_spellings(self):
        find = self.api("exec_start_config_path")

        def shown(argv: str) -> str:
            return "{ path=/bin/x ; argv[]=" + argv + " ; ignore_errors=no ; start_time=[n/a] }"

        cases = {"/bin/x --config=/h/c.yaml": "/h/c.yaml", "/bin/x --config=file:/h/c.yaml": "/h/c.yaml",
                 "/bin/x -config.file=/h/l.yaml -x": "/h/l.yaml", "/bin/x --config.file=/h/p.yml --web=1": "/h/p.yml",
                 "/bin/x --homepath=/o --config=/h/g.ini": "/h/g.ini", "/bin/x --config /h/c.yaml --x": "/h/c.yaml",
                 "/bin/x --port 1 --no-open": None, "/bin/x --config=env:VAR": "env:VAR", "/bin/x --config": None,
                 "/bin/x --config --port 1": None}
        for argv, expected in cases.items():
            self.assertEqual(find(shown(argv)), expected, argv)
        self.assertIsNone(find(""))

    def test_parse_qmd_status_counts_and_absent_lines_are_zero(self):
        parse = self.api("parse_qmd_status")
        self.assertEqual(parse(QMD_STATUS.format(home="/fake")), {"documents": 288, "vectors": 3284, "orphaned": 952, "pending": 15})
        self.assertEqual(parse(QMD_STATUS_ZERO.format(home="/fake")), {"documents": 288, "vectors": 3284, "orphaned": 0, "pending": 0})
        colored = QMD_STATUS.format(home="/fake").replace("  Total:", "  \x1b[1mTotal:").replace("files indexed", "files indexed\x1b[0m")
        self.assertEqual(parse(colored)["documents"], 288)
        self.assertIsNone(parse("QMD Status\n"))
        self.assertIsNone(parse("Collections\n  x (qmd://x/)\n    Files:    9 (updated 1h ago)\n"))

    def test_unified_windows_from_the_last_rate_limit_event_with_windows(self):
        parse = self.api("parse_unified_windows")
        self.assertEqual(parse(CLAUDE_P_ARRAY), {"five_hour": {"utilization": 0.52, "resets_at_utc": utc_minute(1790672400)},
                                                 "seven_day": {"utilization": 0.78, "resets_at_utc": utc_minute(1790791200)}})
        self.assertIsNone(parse(CLAUDE_P_PLAIN))
        self.assertIsNone(parse([{"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}}]))
        self.assertIsNone(parse([{"type": "rate_limit_event", "rate_limit_info": {"unifiedWindows": {"five_hour": {"utilization": "x"}}}}]))

    def test_alias_or_other_prints_only_model_alias_shaped_values(self):
        alias = self.api("alias_or_other")
        for value in ("opus", "sonnet", "haiku", "opus[1m]", "claude-opus-4-5-20251101", "gpt-6-astra"):
            self.assertEqual(alias(value), value)
        for value in ("Opus", "sk-ant-" + "a" * 60, "a b", "opus/../x", "", "1x", "x" * 41, 7, None, ["opus"]):
            self.assertEqual(alias(value), "other", repr(value))

    def test_guard_output_refuses_substrings_and_whole_words_and_path_characters_in_the_sanitized_record(self):
        guard, refusal = self.api("guard_output"), self.api("PrivacyRefusal")
        mark = self.api("WORD_MARK")
        record = {"items": [{"id": "a.b", "value": "prefix-zz-secret-7f3a-suffix"}, {"id": "c.d", "value": "fine"}]}
        with self.assertRaises(refusal) as caught:
            guard(record, json.dumps(record), ["zz-secret-7f3a"], False)
        self.assertEqual(caught.exception.items, ["a.b"])
        guard(record, json.dumps(record), [mark + "name", "unrelated-value"], False)
        named = {"items": [{"id": "e.f", "value": "the Name here"}, {"id": "g.h", "value": "renamed"}]}
        with self.assertRaises(refusal) as caught:
            guard(named, json.dumps(named), [mark + "name"], False)
        self.assertEqual(caught.exception.items, ["e.f"], "a whole word matches, a substring of a longer word does not")
        pathy = {"items": [{"id": "i.j", "value": "a/b", "path": "~/x"}]}
        guard(pathy, json.dumps(pathy), [], False)
        with self.assertRaises(refusal):
            guard(pathy, json.dumps(pathy), [], True)
        with self.assertRaises(refusal) as caught:
            guard({"items": [], "label": "zz-secret-7f3a"}, "{}", ["zz-secret-7f3a"], True)
        self.assertEqual(caught.exception.items, ["record"])

    def test_digest_rule_and_ignore_keys(self):
        digest = self.api("digest_body")
        body = {"b": [1, {"z": 1, "ts": 5}], "a": 1, "ts": 7}
        self.assertEqual(digest(body), hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest())
        without = {"b": [1, {"z": 1}], "a": 1}
        self.assertEqual(digest(body, ("ts",)), hashlib.sha256(json.dumps(without, sort_keys=True).encode("utf-8")).hexdigest())

    def test_strip_ansi_and_plain_text_helpers(self):
        strip, plain = self.api("strip_ansi"), self.api("is_plain")
        self.assertEqual(strip("\x1b[33mOrphaned:\x1b[0m 3"), "Orphaned: 3")
        self.assertEqual(strip("\x1b[1;31;40"), "", "an unterminated sequence is dropped, never a hang")
        self.assertTrue(plain("2.1.284 (Claude Code)"))
        for text in ("/home/x", "a\\b", "~/x", "a\nb", "x" * 300, "http://x"):
            self.assertFalse(plain(text), repr(text))

    def test_scanners_are_linear_on_adversarial_input(self):
        started = time.monotonic()
        self.api("parse_mcp_list")(("x: " + "- " * 20000 + "\n") * 5 + "\n")
        self.api("strip_ansi")("\x1b[" * 50000)
        self.api("parse_qmd_status")("Documents\n" + "  Total: " * 20000)
        self.api("exec_start_config_path")("{ path=/x ; argv[]=" + "--config " * 20000 + " ; ignore_errors=no }")
        self.assertLess(time.monotonic() - started, 5.0)

    def test_run_kills_the_process_group_on_timeout_and_reports_missing_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "slow"
            script.write_text("#!/bin/sh\nsleep 30 &\nsleep 30\n", encoding="utf-8")
            script.chmod(0o755)
            context = self.api("Ctx").for_tests(Path(folder), Path(folder), {"PATH": folder + os.pathsep + "/usr/bin:/bin"})
            started = time.monotonic()
            result = context.run(["slow"], timeout=0.5)
            self.assertEqual(result.state, "timeout")
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(context.run(["no-such-tool-here"]).state, "missing")


class MutationControlTests(unittest.TestCase):
    """Each mutant breaks one property of the tool; the real test for that property must fail on it.

    A mutant is the tool source with one or two exact anchor lines replaced. The anchors must occur exactly once, so a
    refactor that moves them fails here instead of leaving a mutant that changes nothing. The nested run is
    `python3 -m unittest <test id>` with FREEZE_SNAPSHOT_TOOL pointing at the mutant.
    """

    DUMP = ('        "items": items,\n', '        "items": items,\n        "debug_environment": dict(os.environ),\n')
    GUARD_OFF = ("def guard_output(record: dict, text: str, forbidden: list[str], sanitized: bool) -> None:\n",
                 "def guard_output(record: dict, text: str, forbidden: list[str], sanitized: bool) -> None:\n    return\n")
    MUTANTS = (
        ("leak_environment_unguarded", (DUMP, GUARD_OFF), "PrivacyTests.test_outputs_contain_no_environment_value_user_host_or_path"),
        ("leak_environment_guarded", (DUMP,), "PrivacyTests.test_outputs_contain_no_environment_value_user_host_or_path"),
        ("print_environment", (("    items = run_collectors(ctx)\n", "    items = run_collectors(ctx)\n    print(dict(os.environ))\n"),),
         "PrivacyTests.test_outputs_contain_no_environment_value_user_host_or_path"),
        ("guard_disabled", (GUARD_OFF,), "PrivacyTests.test_capture_refuses_when_an_environment_value_would_be_written"),
        ("blind_repo", (blind_patch("repo"),), "DriftTests.test_repo_class_drift"),
        ("blind_roles", (blind_patch("roles"),), "DriftTests.test_roles_class_drift"),
        ("blind_hooks", (blind_patch("hooks"),), "DriftTests.test_hooks_class_drift"),
        ("blind_claude", (blind_patch("claude"),), "DriftTests.test_claude_class_drift"),
        ("blind_codex", (blind_patch("codex"),), "DriftTests.test_codex_class_drift"),
        ("blind_tools", (blind_patch("tools"),), "DriftTests.test_tools_class_drift"),
        ("blind_adoption", (blind_patch("adoption"),), "DriftTests.test_adoption_derived_items_drift"),
        ("blind_services", (blind_patch("services"),), "DriftTests.test_services_class_drift"),
        ("blind_gateways", (blind_patch("gateways"),), "DriftTests.test_gateways_class_drift"),
        ("informational_fails", (("        frozen = (a_item or b_item).get(\"class\") == FROZEN\n", "        frozen = True\n"),),
         "CompareTests.test_informational_changes_never_fail"),
        ("check_always_passes", (("        if got_status == want_status and got_value == want_value:\n", "        if True:\n"),),
         "CheckTests.test_a_single_mismatch_fails_only_that_item"),
        ("credentials_not_refused", (("def is_credential_store(path: str, home: Path) -> bool:\n",
                                     "def is_credential_store(path: str, home: Path) -> bool:\n    return False\n"),),
         "ConfigTests.test_credential_store_paths_are_refused"),
        ("missing_tool_raises", (('            return RunResult("missing", None, "", "")\n', "            raise FileNotFoundError(argv[0])\n"),),
         "ResilienceTests.test_missing_tool_is_status_missing_and_capture_continues"),
    )

    def mutant_dir(self) -> Path:
        kept = os.environ.get("FREEZE_MUTANT_DIR")
        if kept:
            Path(kept).mkdir(parents=True, exist_ok=True)
            return Path(kept)
        folder = Path(tempfile.mkdtemp(prefix="freeze-mutants-", dir=os.environ.get("TMPDIR") or None))
        self.addCleanup(shutil.rmtree, folder, True)
        return folder

    def nested(self, tool: Path, target: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in ("FREEZE_MUTANT_DIR", "FREEZE_SNAPSHOT_TOOL")}
        env["FREEZE_SNAPSHOT_TOOL"] = str(tool)
        return subprocess.run([sys.executable, "-B", "-m", "unittest", f"tests.test_freeze_snapshot.{target}"],
                              cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600)

    def test_the_nested_runner_passes_on_the_real_tool(self):
        proc = self.nested(DEFAULT_TOOL, "CatalogueTests.test_list_frozen_prints_id_and_how_to_check_lines")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])

    def test_each_mutant_fails_the_test_for_its_property(self):
        source = DEFAULT_TOOL.read_text(encoding="utf-8")
        folder = self.mutant_dir()
        prepared = []
        for name, patches, target in self.MUTANTS:
            mutated = source
            for anchor, replacement in patches:
                self.assertEqual(mutated.count(anchor), 1, f"{name}: anchor not found exactly once: {anchor!r}")
                mutated = mutated.replace(anchor, replacement)
            compile(mutated, name, "exec")  # a mutant that does not compile would fail every test for the wrong reason
            path = folder / name / "freeze_snapshot.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(mutated, encoding="utf-8")
            prepared.append((name, path, target))
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as pool:
            results = list(pool.map(lambda entry: self.nested(entry[1], entry[2]), prepared))
        for (name, path, target), proc in zip(prepared, results):
            with self.subTest(mutant=name):
                lines = proc.stderr.splitlines()
                shown = [line for line in lines if line.startswith(("AssertionError", "FAILED"))][:4]
                (folder / name / "result.txt").write_text(f"target: {target}\nexit: {proc.returncode}\n" + "\n".join(shown) + "\n",
                                                          encoding="utf-8")
                self.assertNotEqual(proc.returncode, 0, f"{name}: {target} still passes against the mutant")
                self.assertIn("FAILED", proc.stderr, f"{name}: the nested run did not fail on an assertion\n" + "\n".join(lines[-14:]))


if __name__ == "__main__":
    unittest.main()
