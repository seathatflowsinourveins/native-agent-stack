#!/usr/bin/env python3
"""Put the Codex worker lane on one Codex home, through Codex's own config writer. Dry run by default.

The lane (docs/decisions/2026-09-26-codex-worker-lane.md) is three changes, four with --omniroute-profile:

  config.toml   written only through `codex app-server` `config/batchWrite` with `expectedVersion`, the writer
                Codex's own clients use: [mcp_servers.context-mode] exactly as adoption/templates/
                codex.config.template.toml renders it (upstream start.mjs from the pinned npm install, no `cwd`,
                `default_tools_approval_mode = "approve"`), the context-mode plugin's own server turned off,
                headroom's four offline variables when headroom is registered, and the template's
                `startup_timeout_sec` for serena and socraticode when they are registered (`codex mcp add` takes no
                timeout option, so a server it registered has none). No other key is sent.
  AGENTS.md     the managed block of adoption/templates/codex.AGENTS.template.md (the top rule, rtk-ai/rtk
                v0.50.0's awareness text verbatim, this catalog's exceptions), inserted or replaced between its
                begin and end markers; every other line is kept. Hash-guarded atomic write.
  stack-worker.config.toml
                the worker profile, adoption/templates/codex.stack-worker.config.toml, for `codex exec -p
                stack-worker`. Created only when absent (or already identical).
  omniroute.config.toml
                only with --omniroute-profile: the gateway profile, adoption/templates/codex.omniroute.config.toml,
                for `codex -p omniroute` through a local OmniRoute. Created only when absent (or already identical).
                A config.toml that still defines [model_providers.omniroute] is reported as a host step, because
                the profile now carries that table and the lane sends no key it does not own.

Modes:
  (default)   dry run. Checks the preconditions, prints each planned change against the live files, then
              rehearses the same batchWrite, AGENTS.md block and profiles on private copies in a scratch Codex
              home (network namespace off where bwrap works) and prints Codex's own read-back of the result:
              `codex mcp get`, `codex debug prompt-input` with and without `-p stack-worker` (and `-p omniroute`).
              Nothing under the target Codex home is written; the scratch home is removed afterwards.
  --apply     refuses while a `codex` process runs or when a file differs from the --expect-* hash the dry run
              printed. Writes a run record and 0600 backups of config.toml and AGENTS.md first (never auth.json
              or any other file), prints the rollback command, then makes the changes, each read back.
  --rollback RUN_DIR
              undoes what that run changed, key by key and block by block, skipping anything someone changed
              since; safe to re-run.

It never opens auth.json, never touches ~/.claude, and never edits a project's .codex/config.toml: Codex's writer
refuses any file but the user config ("Only writes to the user config are allowed", app-server/src/
config_manager_service.rs at rust-v0.157.1). A project config that still pins context-mode to one directory is
reported as a host step with the exact tables to delete (--project-config).

Exit status: 0 done (or nothing to do), 2 refused before any write, 3 a write or read-back failed or rollback met a
conflict, 1 unexpected error.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# Reused, not rewritten: the app-server client of the quota probe, and the RTK-inline check and Rust whitespace
# rule of the adoption status report.
from scripts import adoption_status, codex_quota  # noqa: E402

TEMPLATES = ROOT / "adoption" / "templates"
USER_TEMPLATE = TEMPLATES / "codex.config.template.toml"
AGENTS_TEMPLATE = TEMPLATES / "codex.AGENTS.template.md"
PROFILE_TEMPLATE = TEMPLATES / "codex.stack-worker.config.toml"
PROFILE_NAME = "stack-worker"
OMNIROUTE_TEMPLATE = TEMPLATES / "codex.omniroute.config.toml"
OMNIROUTE_PROFILE = "omniroute"
# User-scope servers whose template start-up allowance the lane restores when they are registered. A host that
# registered them with `codex mcp add` has no value, so Codex waits its default 30 s (codex-mcp/src/rmcp_client.rs
# L103 and L342 at rust-v0.157.1), while the template gives serena 60 s and socraticode 120 s.
STARTUP_TIMEOUT_SERVERS = ("serena", "socraticode")
BLOCK_BEGIN = "<!-- native-agent-stack:codex-user-instructions:begin"
BLOCK_END = "<!-- native-agent-stack:codex-user-instructions:end -->"
TOP_RULE_MARKER = "native-agent-stack:top-rule"
EXCEPTIONS_MARKER = "native-agent-stack:rtk-exceptions"
# adoption/pins-linux-x86_64.json "codex"; the writer's behaviour below was read and probed at this version.
CODEX_VERSION = "0.157.1"
CONTEXT_MODE_VERSION = "1.0.169"
# start.mjs of context-mode 1.0.169: the npm install and the plugin pin 6f0cc684 carry the same file.
START_MJS_SHA256 = "0324441841b2aef98db606194ec779c014fba3c8031c725f1be273c65f26e57b"
HEADROOM_OFFLINE_KEYS = ("HEADROOM_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "DO_NOT_TRACK")
RECORD_SCHEMA = "native-agent-stack/codex-lane-apply/v1"
REQUEST_TIMEOUT = 60.0


class Refused(Exception):
    """Stop before any write (exit 2)."""


class Failed(Exception):
    """A write, read-back or rollback step failed (exit 3)."""


class AppServerError(Exception):
    def __init__(self, method: str, error: dict):
        self.method, self.error = method, error
        data = error.get("data") or {}
        self.code = data.get("config_write_error_code") if isinstance(data, dict) else None
        super().__init__(f"{method}: {error.get('message')} ({self.code or error.get('code')})")


# ---------------------------------------------------------------------------------------------------------------
# small helpers

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except FileNotFoundError:
        return None


def utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def key_path(segments: list[str]) -> str:
    """A batchWrite keyPath: dotted, with any segment outside [A-Za-z0-9_-] quoted (parse_key_path accepts
    "..." segments with backslash escapes)."""
    parts = []
    for segment in segments:
        if re.fullmatch(r"[A-Za-z0-9_-]+", segment):
            parts.append(segment)
        else:
            parts.append('"' + segment.replace("\\", "\\\\").replace('"', '\\"') + '"')
    return ".".join(parts)


def get_path(tree, segments: list[str]):
    """(present, value) at segments."""
    node = tree
    for segment in segments:
        if not isinstance(node, dict) or segment not in node:
            return False, None
        node = node[segment]
    return True, node


def delete_path(tree: dict, segments: list[str]) -> None:
    node = tree
    for segment in segments[:-1]:
        if not isinstance(node, dict) or segment not in node:
            return
        node = node[segment]
    if isinstance(node, dict):
        node.pop(segments[-1], None)


def prune_empty(node):
    if isinstance(node, dict):
        return {k: prune_empty(v) for k, v in node.items() if not (isinstance(v, dict) and not prune_empty(v))}
    return node


def without_owned(config: dict, owned: list[list[str]]) -> dict:
    rest = copy.deepcopy(config)
    for segments in owned:
        delete_path(rest, segments)
    return prune_empty(rest)


def describe(present: bool, value) -> str:
    if not present:
        return "absent"
    if isinstance(value, dict):
        return "{" + ", ".join(sorted(value)) + "}"
    return json.dumps(value)


def file_state(live: bytes | None, template: bytes) -> str:
    """A profile file against its template: create (absent), same, or differs (never overwritten)."""
    if live is None:
        return "create"
    return "same" if live == template else "differs"


def atomic_write(path: Path, data: bytes, mode: int, expect_sha: str | None, create_only: bool = False) -> None:
    """Write via a temporary file in the same directory. With create_only the target must not exist (os.link
    refuses an existing name); otherwise the target must still hash to expect_sha (None: must be absent) right
    before the rename."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if create_only:
            os.link(tmp, path)
        else:
            if sha256_file(path) != expect_sha:
                raise Failed(f"{path} changed since it was read; nothing written")
            os.replace(tmp, path)
            tmp = None
    finally:
        if tmp is not None:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)


# ---------------------------------------------------------------------------------------------------------------
# what the lane owns

def rendered_user_template(eco_root: str, host_path: str) -> dict:
    text = string.Template(USER_TEMPLATE.read_text(encoding="utf-8")).safe_substitute(
        ECO_ROOT=eco_root, HOST_PATH=host_path)
    return tomllib.loads(text)


def context_mode_entry(eco_root: str, host_path: str) -> dict:
    entry = rendered_user_template(eco_root, host_path)["mcp_servers"]["context-mode"]
    if "${" in json.dumps(entry):
        raise Refused("the template's context-mode entry still has a placeholder after rendering")
    return entry


def owned_edits(live: dict, eco_root: str, host_path: str) -> list[dict]:
    """[{key: segments, value}] for the user config. headroom's variables and the serena and socraticode start-up
    allowances are sent only when that server is registered; registering servers is not this lane's job."""
    template = rendered_user_template(eco_root, host_path)
    edits = [
        {"key": ["mcp_servers", "context-mode"], "value": context_mode_entry(eco_root, host_path)},
        {"key": ["plugins", "context-mode@context-mode", "mcp_servers", "context-mode", "enabled"],
         "value": template["plugins"]["context-mode@context-mode"]["mcp_servers"]["context-mode"]["enabled"]},
    ]
    if get_path(live, ["mcp_servers", "headroom"])[0]:
        for name in HEADROOM_OFFLINE_KEYS:
            edits.append({"key": ["mcp_servers", "headroom", "env", name],
                          "value": template["mcp_servers"]["headroom"]["env"][name]})
    for server in STARTUP_TIMEOUT_SERVERS:
        if get_path(live, ["mcp_servers", server])[0]:
            edits.append({"key": ["mcp_servers", server, "startup_timeout_sec"],
                          "value": template["mcp_servers"][server]["startup_timeout_sec"]})
    return edits


def worker_pins() -> list[str]:
    """The profile's model, effort and web search as command-line flags. A project .codex/config.toml outranks a
    profile file (config_layer_source.rs: project 25, profile 21) but not `-c` (session flags, 30), so a worker
    launch repeats them on its command line and the profile stays a convenience for the tool settings."""
    profile = tomllib.loads(PROFILE_TEMPLATE.read_text(encoding="utf-8"))
    return ["-m", profile["model"], "-c", f'model_reasoning_effort="{profile["model_reasoning_effort"]}"',
            "-c", f'web_search="{profile["web_search"]}"']


def worker_command() -> str:
    """How a worker lane starts: the profile plus the pinned flags, stdin closed."""
    pins = " ".join(f"'{flag}'" if '"' in flag else flag for flag in worker_pins())
    return f"codex exec -p {PROFILE_NAME} {pins} -s <sandbox> ... < /dev/null"


def agents_block() -> str:
    text = AGENTS_TEMPLATE.read_text(encoding="utf-8")
    if not (text.startswith(BLOCK_BEGIN) and text.endswith(BLOCK_END + "\n")):
        raise Refused(f"{AGENTS_TEMPLATE} must be exactly one managed block")
    return text


def block_span(text: str) -> tuple[int, int] | None:
    """(start, end) of the managed block's lines, end after the end marker's newline; None when absent."""
    begins = [m.start() for m in re.finditer(r"(?m)^" + re.escape(BLOCK_BEGIN), text)]
    ends = [m.end() for m in re.finditer(r"(?m)^" + re.escape(BLOCK_END) + r"\n?", text)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise Refused("AGENTS.md has a damaged managed block (markers missing, repeated or out of order)")
    return begins[0], ends[0]


def with_block(text: str, block: str) -> str:
    span = block_span(text)
    if span:
        return text[:span[0]] + block + text[span[1]:]
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def without_block(text: str) -> str:
    span = block_span(text)
    if not span:
        return text
    head, tail = text[:span[0]], text[span[1]:]
    if not tail.strip():
        head = head.rstrip("\n") + ("\n" if head.strip() else "")
    return head + tail


def default_host_path(live: dict, eco_root: str) -> str | None:
    """HOST_PATH as this host already states it: the user config's shell_environment_policy PATH, which the
    template renders as "${ECO_ROOT}/bin:${HOST_PATH}"."""
    present, value = get_path(live, ["shell_environment_policy", "set", "PATH"])
    prefix = f"{eco_root}/bin:"
    if present and isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix):
        return value[len(prefix):]
    return None


# ---------------------------------------------------------------------------------------------------------------
# Codex itself

def codex_env(codex_home: Path, base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    env["CODEX_HOME"] = str(codex_home)
    return env


def run_codex(codex: str, args: list[str], env: dict, cwd: str | Path = "/", timeout: float = 120,
              wrapper: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([*(wrapper or []), codex, *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout, check=False)


def last_line(text: str) -> str:
    """The last non-blank line of a tool's stderr (its error), bounded."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def codex_version(codex: str, env: dict) -> str | None:
    result = run_codex(codex, ["--version"], env, timeout=30)
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
    return match.group(1) if result.returncode == 0 and match else None


class AppServer:
    """A `codex app-server --listen stdio://` session over scripts/codex_quota.py's client (its own process group,
    bounded reads, a deadline per request, server requests answered): `initialize` with the experimental API,
    the `initialized` notification, then config/read and config/batchWrite."""

    def __init__(self, codex: str, env: dict, cwd: str | Path, wrapper: list[str] | None = None):
        self.argv = [*(wrapper or []), codex, "app-server", "--listen", "stdio://"]
        self.codex, self.env, self.cwd = codex, env, str(cwd)
        self.server, self.next_id = None, 1

    def __enter__(self):
        self.server = codex_quota.AppServer(self.codex, self.cwd, argv=self.argv, env=self.env)
        try:
            self.request("initialize", {"clientInfo": {"name": "native_agent_stack_codex_lane", "version": "1"},
                                        "capabilities": {"experimentalApi": True}})
            self.server.send({"method": "initialized"}, "initialized")
        except BaseException:
            self.server.close()
            raise
        return self

    def __exit__(self, *exc):
        self.server.close()
        return False

    def request(self, method: str, params: dict) -> dict:
        request_id, self.next_id = self.next_id, self.next_id + 1
        try:
            return self.server.request(request_id, method, params, time.monotonic() + REQUEST_TIMEOUT)
        except codex_quota.ProbeError as error:
            if error.answer is not None:  # a config error from the local writer: safe to show
                raise AppServerError(method, error.answer) from None
            raise Failed(f"codex app-server, {method}: {error.message}") from None

    def user_layer(self) -> tuple[str, dict]:
        """(version, config) of the base user layer, as config/read reports it."""
        result = self.request("config/read", {"includeLayers": True})
        for layer in result.get("layers") or []:
            name = layer.get("name") or {}
            if name.get("type") == "user" and not name.get("profile"):
                return layer["version"], layer.get("config") or {}
        raise Failed("config/read reported no user layer")

    def batch_write(self, edits: list[dict], expected_version: str) -> dict:
        return self.request("config/batchWrite", {
            "edits": [{"keyPath": key_path(e["key"]), "value": e["value"], "mergeStrategy": "replace"} for e in edits],
            "expectedVersion": expected_version})


# ---------------------------------------------------------------------------------------------------------------
# plan

class Plan:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        self.eco_root = str(Path(args.eco_root or Path.home() / ".local/share/codex-ecosystem").expanduser())
        self.config_path = self.codex_home / "config.toml"
        self.agents_path = self.codex_home / "AGENTS.md"
        self.override_path = self.codex_home / "AGENTS.override.md"
        self.profile_path = self.codex_home / f"{PROFILE_NAME}.config.toml"
        self.config_bytes = self.config_path.read_bytes() if self.config_path.is_file() else b""
        self.live = tomllib.loads(self.config_bytes.decode("utf-8")) if self.config_bytes else {}
        self.host_path = args.host_path or default_host_path(self.live, self.eco_root)
        self.agents_bytes = self.agents_path.read_bytes() if self.agents_path.is_file() else None
        self.profile_bytes = self.profile_path.read_bytes() if self.profile_path.is_file() else None
        self.block = agents_block()
        self.profile_template = PROFILE_TEMPLATE.read_bytes()
        tomllib.loads(self.profile_template.decode("utf-8"))  # the template itself must parse
        # The gateway profile is opt-in (--omniroute-profile); without the flag nothing about it is read or written.
        self.omniroute = bool(getattr(args, "omniroute_profile", False))
        self.omniroute_path = self.codex_home / f"{OMNIROUTE_PROFILE}.config.toml"
        self.omniroute_template = OMNIROUTE_TEMPLATE.read_bytes() if self.omniroute else b""
        if self.omniroute:
            tomllib.loads(self.omniroute_template.decode("utf-8"))
        self.omniroute_bytes = (self.omniroute_path.read_bytes()
                                if self.omniroute and self.omniroute_path.is_file() else None)
        self.edits = owned_edits(self.live, self.eco_root, self.host_path or "") if self.host_path else []
        current_agents = (self.agents_bytes or b"").decode("utf-8")
        try:
            self.new_agents = with_block(current_agents, self.block)
        except Refused:
            self.new_agents = None  # reported by preconditions()

    # --- state of each part
    def config_changes(self) -> list[dict]:
        """Each owned key with its live value. created_root is the shallowest table the write creates (a
        rollback deletes that table, since deleting only the key would leave its empty header behind)."""
        changes = []
        for edit in self.edits:
            present, value = get_path(self.live, edit["key"])
            created_root = None
            if not present:
                created_root = next(edit["key"][:n] for n in range(1, len(edit["key"]) + 1)
                                    if not get_path(self.live, edit["key"][:n])[0])
            changes.append({**edit, "before_present": present, "before": value, "created_root": created_root,
                            "changed": not (present and value == edit["value"])})
        return changes

    def agents_changed(self) -> bool:
        return (self.agents_bytes or b"").decode("utf-8") != self.new_agents

    def profile_state(self) -> str:
        return file_state(self.profile_bytes, self.profile_template)

    def omniroute_state(self) -> str | None:
        """create | same | differs for the gateway profile; None when --omniroute-profile was not given."""
        return file_state(self.omniroute_bytes, self.omniroute_template) if self.omniroute else None

    def base_provider_step(self) -> list[str]:
        """Report lines when config.toml still defines the gateway provider the profile now carries (a host step)."""
        if not self.omniroute or not get_path(self.live, ["model_providers", OMNIROUTE_PROFILE])[0]:
            return []
        lines = self.config_bytes.decode("utf-8").splitlines()
        found = [f"line {number}: {line.strip()}" for number, line in enumerate(lines, 1)
                 if re.fullmatch(r"\[\s*model_providers\s*\.\s*\"?omniroute\"?\s*\]", line.strip())]
        return ["  HOST STEP (not scripted; the lane sends only its own keys): config.toml defines "
                "[model_providers.omniroute], which",
                f"  {OMNIROUTE_PROFILE}.config.toml now carries. Once the profile is in place, back config.toml up "
                "privately and delete that table:",
                *[f"    {entry}" for entry in found or ["[model_providers.omniroute] (a dotted or inline form)"]],
                "  Read back: `codex -p omniroute debug prompt-input probe` still renders, and `render_config.py "
                "--check` no longer lists the table."]

    def preconditions(self, codex: str, for_apply: bool) -> list[tuple[str, str, str]]:
        """[(level, name, detail)]; level ok|warn|fail. Apply refuses on any fail; the dry run reports."""
        checks = []
        version = codex_version(codex, codex_env(self.codex_home))
        checks.append(("ok" if version == CODEX_VERSION else "fail", "codex version",
                       f"codex-cli {version} (pin {CODEX_VERSION})"))
        start_mjs = Path(self.eco_root) / f"tools/context-mode-{CONTEXT_MODE_VERSION}/lib/node_modules/context-mode/start.mjs"
        digest = sha256_file(start_mjs)
        checks.append(("ok" if digest == START_MJS_SHA256 else "fail", "context-mode start.mjs",
                       f"{start_mjs}: sha256 {digest[:12] if digest else 'missing'} (expected {START_MJS_SHA256[:12]})"))
        node = Path(self.eco_root) / "bin/node"
        checks.append(("ok" if os.access(node, os.X_OK) else "fail", "node", str(node)))
        checks.append(("ok" if self.host_path else "fail", "HOST_PATH",
                       self.host_path or "not derivable from shell_environment_policy.set.PATH; pass --host-path"))
        checks.append(("ok" if self.config_bytes else "fail", "config.toml",
                       f"{self.config_path} {'present' if self.config_bytes else 'missing'}"))
        present, value = get_path(self.live, ["features", "daemon_auto_start"])
        checks.append(("ok" if present and value is False else "fail", "features.daemon_auto_start",
                       "false" if present and value is False else "not false: set it first (recipes/README.md codex row)"))
        override = self.override_path.read_text(encoding="utf-8") if self.override_path.is_file() else ""
        checks.append(("fail" if override.strip(adoption_status.RUST_WHITESPACE) else "ok", "AGENTS.override.md",
                       "has text, so Codex would read it instead of AGENTS.md" if override.strip(
                           adoption_status.RUST_WHITESPACE) else "none with text"))
        try:
            block_span((self.agents_bytes or b"").decode("utf-8"))
            checks.append(("ok", "AGENTS.md block", "markers intact or absent"))
        except Refused as error:
            checks.append(("fail", "AGENTS.md block", str(error)))
        profile = self.profile_state()
        checks.append(("fail" if profile == "differs" else "ok", "stack-worker profile",
                       {"create": "absent; will be created", "same": "already the template",
                        "differs": f"{self.profile_path} exists and differs from the template"}[profile]))
        omniroute = self.omniroute_state()
        if omniroute is not None:
            checks.append(("fail" if omniroute == "differs" else "ok", "omniroute profile",
                           {"create": "absent; will be created", "same": "already the template",
                            "differs": f"{self.omniroute_path} exists and differs from the template; move it "
                                       "aside privately first"}[omniroute]))
        running = codex_processes(self.args.codex_process_name)
        checks.append((("fail" if for_apply else "warn") if running else "ok", "codex processes",
                       f"{len(running)} running (pids {', '.join(running)})" if running else "none"))
        if for_apply:
            for name, expected, actual in (("config.toml", self.args.expect_config_sha256, sha256_bytes(self.config_bytes)),
                                           ("AGENTS.md", self.args.expect_agents_sha256,
                                            sha256_bytes(self.agents_bytes) if self.agents_bytes is not None else "absent")):
                if expected is None:
                    checks.append(("fail", f"--expect-{name.split('.')[0].lower()}-sha256",
                                   f"missing; the dry run prints it ({actual})"))
                elif expected != actual:
                    checks.append(("fail", f"{name} hash", f"{actual} differs from the reviewed {expected}"))
        return checks


def codex_processes(name: str) -> list[str]:
    """PIDs whose executable name is exactly `name` (codex: the musl binary serves exec, the TUI and the app-server
    alike). An argument pattern would match every scratch path that contains the word."""
    result = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, check=False)
    return result.stdout.split()


def project_block_step(path: Path) -> list[str]:
    """Report lines for a project .codex/config.toml that still pins context-mode (the host step)."""
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"  {path}: unreadable ({error}); inspect by hand"]
    tables = []
    if get_path(data, ["mcp_servers", "context-mode"])[0]:
        tables += ["[mcp_servers.context-mode]", "[mcp_servers.context-mode.env]"]
    if get_path(data, ["plugins", "context-mode@context-mode", "mcp_servers", "context-mode"])[0]:
        tables.append('[plugins."context-mode@context-mode".mcp_servers.context-mode]')
    if not tables:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    found = [f"line {number}: {line.strip()}" for number, line in enumerate(lines, 1)
             if line.strip() in tables]
    return [f"  HOST STEP (not scripted; Codex's writer cannot edit a project config): in {path}, back the file up",
            "  privately, then delete each of these tables, from its header line to the line before the next header:",
            *[f"    {entry}" for entry in found],
            "  Read back from that project's root: `codex mcp get context-mode --json` shows \"cwd\": null and the",
            "  user-scope command, and `codex mcp list --json` lists exactly one context-mode."]


# ---------------------------------------------------------------------------------------------------------------
# rehearsal on private copies

def bwrap_wrapper(root: Path) -> list[str] | None:
    """bwrap without a network namespace for the scratch home, when it works here (Linux); None otherwise."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return None
    wrapper = [bwrap, "--unshare-net", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
               "--bind", str(root), str(root), "--"]
    probe = subprocess.run([*wrapper, "true"], capture_output=True, check=False)
    return wrapper if probe.returncode == 0 else None


def prompt_input_counts(stdout: str) -> dict:
    return {"top_rule": stdout.count(TOP_RULE_MARKER), "rtk_exceptions": stdout.count(EXCEPTIONS_MARKER),
            "prefix_rule": stdout.count("Prefix every shell command with"),
            "no_spawn_unless_asked": "Do not spawn sub-agents unless" in stdout,
            "proactive_delegation": "Proactive multi-agent delegation is active" in stdout}


def readbacks(codex: str, env: dict, wrapper: list[str] | None, cwd: Path, omniroute: bool = False) -> dict:
    """Codex's own view of the lane: the context-mode server, the model-visible input with and without the
    profile (and with the gateway profile when it is part of the run), and the profile's read-only servers."""
    out = {}
    got = run_codex(codex, ["mcp", "get", "context-mode", "--json"], env, cwd, wrapper=wrapper)
    out["context_mode"] = json.loads(got.stdout) if got.returncode == 0 else {"error": last_line(got.stderr)}
    inputs = [("prompt_input", []), ("prompt_input_profile", ["-p", PROFILE_NAME])]
    if omniroute:
        inputs.append(("prompt_input_omniroute", ["-p", OMNIROUTE_PROFILE]))
    for label, extra in inputs:
        got = run_codex(codex, [*extra, "debug", "prompt-input", "probe"], env, cwd, wrapper=wrapper)
        out[label] = prompt_input_counts(got.stdout) if got.returncode == 0 else {"error": last_line(got.stderr)}
    profile = tomllib.loads(PROFILE_TEMPLATE.read_text(encoding="utf-8"))
    out["profile_servers"] = {}
    for name in sorted(profile.get("mcp_servers", {})):
        got = run_codex(codex, ["-p", PROFILE_NAME, "mcp", "get", name, "--json"], env, cwd, wrapper=wrapper)
        if got.returncode != 0:
            out["profile_servers"][name] = {"error": last_line(got.stderr)}
            continue
        entry = json.loads(got.stdout)
        out["profile_servers"][name] = {"enabled_tools": entry.get("enabled_tools"),
                                        "disabled_tools": entry.get("disabled_tools"),
                                        "env": {key: ((entry.get("transport") or {}).get("env") or {}).get(key)
                                                for key in profile["mcp_servers"][name].get("env", {})}}
    return out


def context_mode_problems(entry: dict, eco_root: str) -> list[str]:
    """`codex mcp get context-mode --json` against the session-bound form (the cm-deep plan's step 3 read-back)."""
    problems = []
    if "error" in entry:
        return [f"codex mcp get context-mode failed: {entry['error']}"]
    transport = entry.get("transport") or {}
    expected_args = [f"{eco_root}/tools/context-mode-{CONTEXT_MODE_VERSION}/lib/node_modules/context-mode/start.mjs"]
    if transport.get("command") != f"{eco_root}/bin/node" or transport.get("args") != expected_args:
        problems.append(f"context-mode launcher is {transport.get('command')} {transport.get('args')}")
    if transport.get("cwd") is not None:
        problems.append(f"context-mode cwd is {transport.get('cwd')}, not null")
    if sorted((transport.get("env") or {})) != ["CONTEXT_MODE_PLATFORM", "PATH", "RTK_TELEMETRY_DISABLED"]:
        problems.append(f"context-mode env keys are {sorted(transport.get('env') or {})}")
    if transport.get("env_vars") not in ([], None):
        problems.append(f"context-mode forwards {transport.get('env_vars')}")
    if entry.get("enabled") is not True:
        problems.append("context-mode is not enabled")
    return problems


def check_readbacks(found: dict, eco_root: str) -> list[str]:
    """Problems in a read-back; empty when the lane is in place."""
    problems = context_mode_problems(found.get("context_mode", {}), eco_root)
    plain, profiled = found.get("prompt_input", {}), found.get("prompt_input_profile", {})
    labelled = [("default", plain), ("-p stack-worker", profiled)]
    if "prompt_input_omniroute" in found:
        labelled.append((f"-p {OMNIROUTE_PROFILE}", found["prompt_input_omniroute"]))
    for label, counts in labelled:
        if counts.get("top_rule") != 1 or counts.get("rtk_exceptions") != 1 or counts.get("prefix_rule", 0) < 1:
            problems.append(f"{label} prompt input: {counts}")
    for label, counts in labelled[1:]:
        if not counts.get("no_spawn_unless_asked") or counts.get("proactive_delegation"):
            problems.append(f"the {label} profile's effort did not reach the prompt input "
                            "(max turns proactive delegation off)")
    profile = tomllib.loads(PROFILE_TEMPLATE.read_text(encoding="utf-8"))
    for name, table in profile.get("mcp_servers", {}).items():
        got = found.get("profile_servers", {}).get(name, {})
        for key in ("enabled_tools", "disabled_tools"):
            if key in table and got.get(key) != table[key]:
                problems.append(f"-p {PROFILE_NAME} {name} {key} is {got.get(key)}")
        if table.get("env", {}) and got.get("env") != table["env"]:
            problems.append(f"-p {PROFILE_NAME} {name} env is {got.get('env')}")
    return problems


def rehearse(plan: Plan, codex: str) -> tuple[list[str], list[str]]:
    """Run the batchWrite, the AGENTS.md block and the profile on copies in a scratch Codex home. Returns
    (report lines, problems)."""
    lines, problems = [], []
    scratch = Path(tempfile.mkdtemp(prefix="codex-lane-rehearsal-"))
    try:
        home, codex_home, cwd = scratch / "home", scratch / "home" / ".codex", scratch / "cwd"
        codex_home.mkdir(parents=True, mode=0o700)
        cwd.mkdir()
        (codex_home / "config.toml").write_bytes(plan.config_bytes)
        os.chmod(codex_home / "config.toml", 0o600)
        (codex_home / "AGENTS.md").write_text(plan.new_agents, encoding="utf-8")
        (codex_home / f"{PROFILE_NAME}.config.toml").write_bytes(plan.profile_template)
        if plan.omniroute:
            (codex_home / f"{OMNIROUTE_PROFILE}.config.toml").write_bytes(plan.omniroute_template)
        env = {"HOME": str(home), "CODEX_HOME": str(codex_home), "LANG": "C.UTF-8",
               "PATH": os.pathsep.join([str(Path(codex).parent), os.defpath])}
        wrapper = bwrap_wrapper(scratch)
        lines.append(f"  scratch Codex home, network namespace {'off (bwrap)' if wrapper else 'not isolated (no bwrap)'}")
        changes = [c for c in plan.config_changes() if c["changed"]]
        with AppServer(codex, env, cwd, wrapper) as server:
            version, before = server.user_layer()
            if changes:
                result = server.batch_write(changes, version)
                lines.append(f"  config/batchWrite: {result.get('status')}, version {version[:19]}... -> "
                             f"{result.get('version', '')[:19]}...")
            else:
                lines.append("  config/batchWrite: nothing to send")
            _, after = server.user_layer()
        owned = [e["key"] for e in plan.edits]
        for edit in plan.edits:
            if get_path(after, edit["key"]) != (True, edit["value"]):
                problems.append(f"after the write {key_path(edit['key'])} is {describe(*get_path(after, edit['key']))}")
        if without_owned(before, owned) != without_owned(after, owned):
            problems.append("the write changed keys outside the lane's own")
        else:
            lines.append("  keys outside the lane's own: unchanged (config/read, before and after)")
        written = (codex_home / "config.toml").read_bytes()
        tomllib.loads(written.decode("utf-8"))
        diff = list(difflib.unified_diff(plan.config_bytes.decode("utf-8").splitlines(),
                                         written.decode("utf-8").splitlines(), "config.toml", "config.toml (rehearsed)",
                                         lineterm="", n=1))
        lines += ["  config.toml diff:", *[f"    {line}" for line in diff[2:]]] if diff else ["  config.toml: unchanged"]
        found = readbacks(codex, env, wrapper, cwd, omniroute=plan.omniroute)
        transport = found.get("context_mode", {}).get("transport") or {}
        lines.append(f"  codex mcp get context-mode: command {transport.get('command')}, cwd {transport.get('cwd')}, "
                     f"env keys {sorted(transport.get('env') or {})}")
        lines.append(f"  prompt input: {found.get('prompt_input')}")
        lines.append(f"  prompt input -p {PROFILE_NAME}: {found.get('prompt_input_profile')}")
        if plan.omniroute:
            lines.append(f"  prompt input -p {OMNIROUTE_PROFILE}: {found.get('prompt_input_omniroute')}")
        lines.append(f"  -p {PROFILE_NAME} servers: {json.dumps(found.get('profile_servers'))}")
        problems += check_readbacks(found, plan.eco_root)
    finally:
        if plan.args.keep_rehearsal:
            lines.append(f"  kept: {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)
    return lines, problems


# ---------------------------------------------------------------------------------------------------------------
# commands

def print_plan(plan: Plan, checks: list[tuple[str, str, str]]) -> None:
    print(f"Codex worker lane for CODEX_HOME={plan.codex_home}")
    print("preconditions:")
    for level, name, detail in checks:
        print(f"  [{level}] {name}: {detail}")
    print("config.toml, through codex app-server config/batchWrite (expectedVersion from config/read):")
    for change in plan.config_changes():
        verb = "set " if change["changed"] else "keep"
        print(f"  {verb} {key_path(change['key'])}: {describe(change['before_present'], change['before'])}"
              + (f" -> {describe(True, change['value'])}" if change["changed"] else ""))
    agents_sha = sha256_bytes(plan.agents_bytes) if plan.agents_bytes is not None else "absent"
    if plan.new_agents is None:
        print(f"AGENTS.md: damaged managed block (sha256 {agents_sha}); fix it by hand first")
    else:
        print(f"AGENTS.md: {'writes the managed block' if plan.agents_changed() else 'block already in place'} "
              f"(sha256 {agents_sha} -> {sha256_bytes(plan.new_agents.encode('utf-8'))})")
    print(f"{PROFILE_NAME}.config.toml: {plan.profile_state()}")
    if plan.omniroute:
        print(f"{OMNIROUTE_PROFILE}.config.toml: {plan.omniroute_state()}")
        for line in plan.base_provider_step():
            print(line)
    for path in plan.args.project_config or []:
        for line in project_block_step(Path(path).expanduser()):
            print(line)


def cmd_plan(args: argparse.Namespace, codex: str) -> int:
    plan = Plan(args)
    checks = plan.preconditions(codex, for_apply=False)
    print("DRY RUN: nothing under the Codex home is written.")
    print_plan(plan, checks)
    if any(level == "fail" for level, _, _ in checks):
        print("result: apply would refuse (fix the [fail] lines first)")
        return 2
    print("rehearsal on private copies:")
    lines, problems = rehearse(plan, codex)
    print("\n".join(lines))
    for problem in problems:
        print(f"  PROBLEM: {problem}")
    if problems:
        print("result: the rehearsal failed; do not apply")
        return 3
    agents_sha = sha256_bytes(plan.agents_bytes) if plan.agents_bytes is not None else "absent"
    print("result: rehearsal passed. Apply in a quiet window (no codex process) with:")
    print(f"  python3 {Path(__file__).resolve().relative_to(ROOT)} --apply"
          + (f" --codex-home {plan.codex_home}" if args.codex_home else "")
          + (f" --eco-root {plan.eco_root}" if args.eco_root else "")
          + (f" --host-path '{plan.host_path}'" if args.host_path else "")
          + (" --omniroute-profile" if plan.omniroute else "")
          + f" --expect-config-sha256 {sha256_bytes(plan.config_bytes)} --expect-agents-sha256 {agents_sha}")
    print(f"workers then start with: {worker_command()}")
    return 0


def state_root(args: argparse.Namespace) -> Path:
    base = args.state_dir or os.environ.get("XDG_STATE_HOME") and Path(os.environ["XDG_STATE_HOME"]) / "native-agent-stack"
    return Path(base or Path.home() / ".local/state/native-agent-stack").expanduser() / "codex-lane"


def write_record(run: Path, record: dict) -> None:
    tmp = run / ".record.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, run / "record.json")


def git_head() -> str | None:
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None


def cmd_apply(args: argparse.Namespace, codex: str) -> int:
    plan = Plan(args)
    checks = plan.preconditions(codex, for_apply=True)
    print_plan(plan, checks)
    root = state_root(args)
    latest = root / "latest"
    if latest.exists():
        previous = json.loads((latest / "record.json").read_text(encoding="utf-8"))
        if previous.get("status") in ("in-progress", "failed"):
            checks.append(("fail", "previous run", f"{latest.resolve()} is {previous['status']}; roll it back first: "
                           f"--rollback {latest.resolve()}"))
            print(f"  [fail] previous run: {checks[-1][2]}")
    if any(level == "fail" for level, _, _ in checks):
        print("refused: nothing written")
        return 2
    changes = plan.config_changes()
    if (not any(c["changed"] for c in changes) and not plan.agents_changed() and plan.profile_state() == "same"
            and plan.omniroute_state() in (None, "same")):
        print("already in place: nothing to do")
        return 0
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    run = Path(tempfile.mkdtemp(prefix=utc_stamp() + "-", dir=root))  # unique, 0700
    (run / "config.toml.before").write_bytes(plan.config_bytes)
    os.chmod(run / "config.toml.before", 0o600)
    if plan.agents_bytes is not None:
        (run / "AGENTS.md.before").write_bytes(plan.agents_bytes)
        os.chmod(run / "AGENTS.md.before", 0o600)
    record = {
        "schema": RECORD_SCHEMA, "created_at": utc_stamp(), "tool": "tools/adoption/apply_codex_lane.py",
        "catalog_commit": git_head(), "codex_home": str(plan.codex_home), "codex_version": CODEX_VERSION,
        "status": "in-progress",
        "config": {"path": str(plan.config_path), "sha256_before": sha256_bytes(plan.config_bytes),
                   "edits": [{"key": c["key"], "before_present": c["before_present"], "before": c["before"],
                              "created_root": c["created_root"], "after": c["value"], "changed": c["changed"]}
                             for c in changes],
                   "state": "pending"},
        "agents": {"path": str(plan.agents_path), "existed": plan.agents_bytes is not None,
                   "mode": oct(plan.agents_path.stat().st_mode & 0o777) if plan.agents_bytes is not None else "0o600",
                   "sha256_before": sha256_bytes(plan.agents_bytes) if plan.agents_bytes is not None else None,
                   "sha256_after": sha256_bytes(plan.new_agents.encode("utf-8")),
                   "block_sha256": sha256_bytes(plan.block.encode("utf-8")), "state": "pending"},
        "profile": {"path": str(plan.profile_path), "existed": plan.profile_bytes is not None,
                    "sha256_after": sha256_bytes(plan.profile_template), "state": "pending"},
        "rollbacks": [],
    }
    if plan.omniroute:  # records of runs without --omniroute-profile, and older records, have no such entry
        record["omniroute_profile"] = {"path": str(plan.omniroute_path), "existed": plan.omniroute_bytes is not None,
                                       "sha256_after": sha256_bytes(plan.omniroute_template), "state": "pending"}
    write_record(run, record)
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run.name)
    print(f"run record: {run}/record.json")
    print(f"to undo: python3 {Path(__file__).resolve().relative_to(ROOT)} --rollback {run}"
          + (f" --codex-home {plan.codex_home}" if args.codex_home else ""))
    env = codex_env(plan.codex_home)
    try:
        # 1. config.toml
        to_send = [c for c in changes if c["changed"]]
        with AppServer(codex, env, run) as server:
            version, before = server.user_layer()
            for change in changes:  # the app-server's view must match what the dry run was checked against
                if get_path(before, change["key"]) != (change["before_present"], change["before"]):
                    raise Failed(f"{key_path(change['key'])} changed since it was read; nothing written")
            if to_send:
                result = server.batch_write(to_send, version)
                record["config"]["write_status"] = result.get("status")
            _, after = server.user_layer()
        owned = [c["key"] for c in changes]
        for change in changes:
            if get_path(after, change["key"]) != (True, change["value"]):
                raise Failed(f"read-back: {key_path(change['key'])} is {describe(*get_path(after, change['key']))}")
        if without_owned(before, owned) != without_owned(after, owned):
            raise Failed("read-back: keys outside the lane's own changed")
        tomllib.loads(plan.config_path.read_text(encoding="utf-8"))
        record["config"].update(state="done", sha256_after=sha256_file(plan.config_path))
        write_record(run, record)
        print("config.toml: written and read back")
        # 2. AGENTS.md
        if plan.agents_changed():
            mode = int(record["agents"]["mode"], 8)
            atomic_write(plan.agents_path, plan.new_agents.encode("utf-8"), mode, record["agents"]["sha256_before"])
        if sha256_file(plan.agents_path) != record["agents"]["sha256_after"]:
            raise Failed("read-back: AGENTS.md does not hold the planned text")
        record["agents"]["state"] = "done"
        write_record(run, record)
        print("AGENTS.md: written and read back")
        # 3. the profiles: journal each creation first, so an interruption after the link still leaves a record
        # that rollback trusts (it removes a file only while it holds the template)
        profiles = [("profile", plan.profile_path, plan.profile_template, plan.profile_state())]
        if plan.omniroute:
            profiles.append(("omniroute_profile", plan.omniroute_path, plan.omniroute_template,
                             plan.omniroute_state()))
        for part, path, template, state in profiles:
            if state == "create":
                record[part]["creating"] = True
                write_record(run, record)
                try:
                    atomic_write(path, template, 0o600, None, create_only=True)
                except FileExistsError:
                    record[part]["creating"] = False  # another writer made it in between; it is not ours
                    raise Failed(f"{path} appeared since it was read; left as it is") from None
                record[part]["created"] = True
            if sha256_file(path) != record[part]["sha256_after"]:
                raise Failed(f"read-back: {path} does not hold the template")
            record[part]["state"] = "done"
            write_record(run, record)
            print(f"{path.name}: in place")
        # 4. Codex's own view
        found = readbacks(codex, env, None, Path("/"), omniroute=plan.omniroute)
        record["readback"] = found
        problems = check_readbacks(found, plan.eco_root)
        if adoption_status.rtk_instructions_inline(plan.codex_home) is not True:
            problems.append("scripts/adoption_status.py does not find RTK.md's text in the instructions Codex loads")
        if problems:
            raise Failed("read-back through codex: " + "; ".join(problems))
    except (Failed, AppServerError, OSError, ValueError, subprocess.SubprocessError) as error:
        record["status"] = "failed"
        record["error"] = str(error)
        write_record(run, record)
        print(f"FAILED: {error}")
        print(f"undo with: python3 {Path(__file__).resolve().relative_to(ROOT)} --rollback {run}"
              + (f" --codex-home {plan.codex_home}" if args.codex_home else ""))
        return 3
    record["status"] = "applied"
    write_record(run, record)
    print("applied. Prove it: python3 tools/adoption/prove_codex_lane.py (add --live for the worker runs)")
    print(f"workers start with: {worker_command()}")
    return 0


def cmd_rollback(args: argparse.Namespace, codex: str) -> int:
    run = Path(args.rollback).expanduser().resolve()
    record = json.loads((run / "record.json").read_text(encoding="utf-8"))
    if record.get("schema") != RECORD_SCHEMA:
        print(f"refused: {run} is not a run record of this tool")
        return 2
    codex_home = Path(record["codex_home"])
    if args.codex_home and Path(args.codex_home).expanduser() != codex_home:
        print(f"refused: the run changed {codex_home}, not {args.codex_home}")
        return 2
    running = codex_processes(args.codex_process_name)
    if running:
        print(f"refused: {len(running)} codex processes running (pids {', '.join(running)})")
        return 2
    outcome, conflicts = {}, []
    # 3. the profiles: remove one only if this run created it (or was creating it when it stopped) and nobody
    # changed it since. A record without "omniroute_profile" (no --omniroute-profile, or an older run) has only one.
    for part in ("profile", "omniroute_profile"):
        entry = record.get(part)
        if entry is None:
            continue
        profile = Path(entry["path"])
        if entry.get("created") or entry.get("creating"):
            digest = sha256_file(profile)
            if digest is None:
                outcome[part] = "already absent"
            elif digest == entry["sha256_after"]:
                profile.unlink()
                outcome[part] = "removed"
            else:
                conflicts.append(f"{profile} changed since the run; left in place")
        else:
            outcome[part] = "not created by this run"
    # 2. AGENTS.md: restore the backup when the file is exactly what the run wrote. When it changed since, swap back
    # only the block, and only while the block is still the one the run installed; the earlier block comes back
    # if there was one.
    agents = Path(record["agents"]["path"])
    digest = sha256_file(agents)
    backup = run / "AGENTS.md.before"
    if digest == record["agents"]["sha256_before"]:
        outcome["agents"] = "already as before"
    elif digest == record["agents"]["sha256_after"]:
        if record["agents"]["existed"]:
            atomic_write(agents, backup.read_bytes(), int(record["agents"]["mode"], 8), digest)
            outcome["agents"] = "restored from the backup"
        else:
            agents.unlink()
            outcome["agents"] = "removed (the run created it)"
    elif digest is not None:
        text = agents.read_text(encoding="utf-8")
        try:
            span = block_span(text)
            prior_text = backup.read_text(encoding="utf-8") if record["agents"]["existed"] else ""
            prior_span = block_span(prior_text)
        except Refused as error:
            conflicts.append(f"AGENTS.md: {error}; left in place")
        else:
            if span is None:
                outcome["agents"] = "no managed block left; nothing to undo"
            elif sha256_bytes(text[span[0]:span[1]].encode("utf-8")) != record["agents"].get("block_sha256"):
                conflicts.append("AGENTS.md: the managed block changed since the run; left in place")
            else:
                prior = prior_text[prior_span[0]:prior_span[1]] if prior_span else None
                restored = text[:span[0]] + prior + text[span[1]:] if prior is not None else without_block(text)
                atomic_write(agents, restored.encode("utf-8"), agents.stat().st_mode & 0o777, digest)
                outcome["agents"] = ("the earlier block is back" if prior is not None else "the run's block removed") \
                    + "; edits made since outside it are kept"
    else:
        outcome["agents"] = "absent"
    # 1. config.toml: each owned key back to its recorded value, only where it still holds what the run wrote
    env = codex_env(codex_home)
    restore = []
    try:
        with AppServer(codex, env, run) as server:
            version, current = server.user_layer()
            created_roots = {}
            for edit in record["config"]["edits"]:
                if not edit["before_present"]:
                    root = tuple(edit.get("created_root") or edit["key"])
                    created_roots.setdefault(root, []).append(edit)
            removed_roots = set()
            for root, edits in created_roots.items():
                # Reconstruct all still-present values owned by this run, not one leaf
                # at a time. Exact root equality preserves foreign keys and edited values.
                # Already removed leaves need not prevent removal of the remaining table.
                only_ours = {}
                for edit in edits:
                    if not get_path(current, edit["key"])[0]:
                        continue
                    relative = edit["key"][len(root):]
                    if not relative:
                        only_ours = edit["after"]
                    else:
                        node = only_ours
                        for segment in relative[:-1]:
                            node = node.setdefault(segment, {})
                        node[relative[-1]] = edit["after"]
                if get_path(current, root) == (True, only_ours):
                    restore.append({"key": list(root), "value": None})
                    removed_roots.add(root)
            for edit in record["config"]["edits"]:
                if tuple(edit.get("created_root") or edit["key"]) in removed_roots:
                    continue
                now = get_path(current, edit["key"])
                if now == (edit["before_present"], edit["before"]):
                    continue
                if now != (True, edit["after"]):
                    conflicts.append(f"{key_path(edit['key'])} changed since the run; left as {describe(*now)}")
                elif edit["before_present"]:
                    restore.append({"key": edit["key"], "value": edit["before"]})
                else:
                    restore.append({"key": edit["key"], "value": None})
            if restore:
                server.batch_write(restore, version)
                _, current = server.user_layer()
                for item in restore:
                    checked = item.get("checks", item["key"])
                    expected = (False, None) if item["value"] is None else (True, item["value"])
                    if get_path(current, checked) != expected:
                        conflicts.append(f"read-back: {key_path(checked)} not restored")
        outcome["config"] = f"{len(restore)} keys restored" if restore else "already as before"
    except (Failed, AppServerError, OSError, subprocess.SubprocessError) as error:
        conflicts.append(f"config.toml: {error}")
    record["rollbacks"].append({"at": utc_stamp(), "outcome": outcome, "conflicts": conflicts})
    record["status"] = "rollback-conflict" if conflicts else "rolled-back"
    write_record(run, record)
    for part, text in outcome.items():
        print(f"{part}: {text}")
    for conflict in conflicts:
        print(f"CONFLICT: {conflict}")
    return 3 if conflicts else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    mode.add_argument("--rollback", metavar="RUN_DIR", help="undo the run recorded in RUN_DIR")
    parser.add_argument("--codex-home", help="the Codex home to change (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--eco-root", help="the ecosystem prefix (default: ~/.local/share/codex-ecosystem)")
    parser.add_argument("--host-path", help="the template's HOST_PATH (default: the user config's "
                        "shell_environment_policy.set.PATH after ${ECO_ROOT}/bin:)")
    parser.add_argument("--codex", default=None, help="the codex executable (default: codex on PATH)")
    parser.add_argument("--state-dir", help="where run records go (default: $XDG_STATE_HOME/native-agent-stack, "
                        "else ~/.local/state/native-agent-stack); a codex-lane/ directory is made under it")
    parser.add_argument("--project-config", action="append", metavar="PATH",
                        help="a project .codex/config.toml to check for a context-mode entry bound to one "
                             "directory (reported as a host step; repeatable)")
    parser.add_argument("--expect-config-sha256", help="--apply: config.toml's sha256 from the reviewed dry run")
    parser.add_argument("--expect-agents-sha256", help="--apply: AGENTS.md's sha256 from the reviewed dry run "
                        "(\"absent\" when it had none)")
    parser.add_argument("--omniroute-profile", action="store_true",
                        help="also install adoption/templates/codex.omniroute.config.toml as "
                             "$CODEX_HOME/omniroute.config.toml, the opt-in profile for `codex -p omniroute` through a "
                             "local OmniRoute gateway (created only when absent; rollback removes it)")
    parser.add_argument("--keep-rehearsal", action="store_true", help="dry run: keep the scratch Codex home")
    parser.add_argument("--codex-process-name", default="codex",
                        help="the executable name the no-running-Codex check looks for (default: codex)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    codex = args.codex or shutil.which("codex")
    if not codex:
        print("refused: no codex executable on PATH")
        return 2
    try:
        if args.rollback:
            return cmd_rollback(args, codex)
        if args.apply:
            return cmd_apply(args, codex)
        return cmd_plan(args, codex)
    except Refused as error:
        print(f"refused: {error}")
        return 2
    except Failed as error:
        print(f"FAILED: {error}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
