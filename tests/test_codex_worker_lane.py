"""Tests for the Codex worker lane: its templates, tools/adoption/apply_codex_lane.py and
tools/adoption/prove_codex_lane.py.

Evidence classes (docs/acceptance-evidence-policy.md):
- template and block tests are structural validation: they read the repository files only;
- the apply, dry-run and rollback tests are synthetic: they drive the script against a fake `codex` written below,
  which speaks the app-server stdio protocol as openai/codex rust-v0.157.1 defines it (no "jsonrpc" field,
  `initialize` then `initialized`, `config/read` with layers and a sha256 version, `config/batchWrite` with
  `expectedVersion`, a null value deleting a key) and answers `mcp get`, `mcp list` and `debug prompt-input`;
- the prove verdict tests read event fixtures cut from real `codex exec --json` runs of codex-cli 0.157.1
  (tests/fixtures/codex-worker-lane/, paths masked; see that directory's items for what each run was);
- CodexIntegrationTests runs the real codex app-server of the pinned version (lane.CODEX_VERSION, 0.159.3) against a
  scratch Codex home, only when NAS_CODEX_INTEGRATION=1 and that codex is on PATH (local integration evidence;
  skipped in CI).
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import os
import re
import shutil
import signal
import string
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import apply_codex_lane as lane  # noqa: E402
import prove_codex_lane as prove  # noqa: E402
import render_config  # noqa: E402
from scripts import adoption_status  # noqa: E402

TEMPLATES = ROOT / "adoption" / "templates"
FIXTURES = ROOT / "tests" / "fixtures" / "codex-worker-lane"
# The staged top-rule block (827 words by Python `str.split()`, marker line included; 153 before the standing
# clauses, routing and skill-matching lines of docs/decisions/2026-09-30-rule-text-every-layer.md, 595 before the
# wave-2 records of 2026-10-03 added semble to the token lanes and the session-lanes lines: context-mode's working
# directory, semble, GPT Researcher and Claude Code messaging, and 800 before the long-command line that runs the
# research script and the messaging courier with yield_time_ms and write_stdin polling, wave-2 messaging ruling,
# change 1) and rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec),
# both byte for byte.
TOP_RULE_SHA256 = "3201144dccd9d134110a2459a1e795d55e8cb747a9592e779e4c4778d8b8bc1c"
RTK_AWARENESS_SHA256 = "278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc"
UPSTREAM_MARKER = "<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->\n"

# A minimal TOML writer for the fake (tables, strings, numbers, booleans, string arrays): enough for these fixtures.
EMITTER = r'''
def key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k)


def scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(scalar(x) for x in v) + "]"
    return json.dumps(v)


def emit(tree):
    lines = []

    def table(path, t):
        if path:
            lines.append("[" + ".".join(key(p) for p in path) + "]")
        lines.extend(f"{key(k)} = {scalar(v)}" for k, v in t.items() if not isinstance(v, dict))
        lines.append("")
        for k, v in t.items():
            if isinstance(v, dict):
                table(path + [k], v)
    table([], tree)
    return "\n".join(lines).strip("\n") + "\n"
'''
_EMIT_NAMESPACE: dict = {}
exec("import json, re\n" + EMITTER, _EMIT_NAMESPACE)
emit_toml = _EMIT_NAMESPACE["emit"]

# The fake's `codex doctor --json`, in the shape codex-cli 0.157.1 printed in a scratch home (observed 2026-09-29:
# exit 1, because auth.credentials fails without a sign-in; 21 checks keyed by id; stdout is only the JSON). A clean
# config.load has no `startup warning*` detail at all. A warning adds `startup warnings` (a count, as a string), one
# count per area, and `startup warning` (a string, or a list when it repeats). The value text embeds the role file's
# absolute path, which the installer must never echo. Sources: openai/codex rust-v0.157.1 codex-rs/cli/src/doctor.rs
# (JsonDoctorReport, config_check, push_startup_warning_counts, structured_json_details). At rust-v0.159.2 that file
# differs only in one handshake-error match arm, and CodexIntegrationTests read the real 0.159.2 report (2026-09-30).
DOCTOR = r'''
ROLE_WARNING = "Ignoring malformed agent role definition"
CANARY = "/canary-host-path/agents/stack-researcher.toml"


def role_warnings(mode, has_roles):
    if mode == "preexisting":  # a warning the scratch home has with or without the role files
        return [f"{ROLE_WARNING}: failed to parse {CANARY}: preexisting"]
    if not has_roles:
        return []
    if mode == "role_string":
        return [f"{ROLE_WARNING}: failed to parse {CANARY}: missing field `developer_instructions`"]
    if mode == "role_list":
        return [f"{ROLE_WARNING}: failed to parse {CANARY}: first", f"{ROLE_WARNING}: failed to parse {CANARY}: second"]
    if mode == "redacted_rise":  # redact_detail replaced the value (it held a credential word)
        return ["<redacted>"]
    return []


def doctor_output(mode, has_roles, home):
    if mode == "not_json":
        return "doctor: this is not a JSON report\n"
    checks = {"auth.credentials": {"id": "auth.credentials", "category": "auth", "status": "fail",
                                   "summary": "not signed in", "details": {}, "remediation": None, "durationMs": 2}}
    if mode != "no_config_load":
        warnings = role_warnings(mode, has_roles)
        details = {"CODEX_HOME": str(home), "mcp servers": "0", "model": "<default>"}
        status, summary = "ok", "config loaded"
        if mode == "load_fail" and has_roles:  # an unreadable agents folder fails the whole load (loader.rs `?`)
            status, summary, details = "fail", "config could not be loaded", {}
        elif warnings:
            status = "warning"
            details.update({"startup warnings": str(len(warnings)), "startup warning skills": "0",
                            "startup warning hooks": "0", "startup warning plugins": "0",
                            "startup warning MCP": "0", "startup warning deprecated": "0"})
            details["startup warning"] = warnings[0] if len(warnings) == 1 else warnings
        checks["config.load"] = {"id": "config.load", "category": "config", "status": status, "summary": summary,
                                 "details": details, "remediation": None, "durationMs": 3}
    return json.dumps({"schemaVersion": 1, "generatedAt": "2026-09-29T00:00:00Z", "overallStatus": "fail",
                       "codexVersion": "0.159.3", "checks": checks}) + "\n"
'''
_DOCTOR_NAMESPACE: dict = {}
exec("import json\n" + DOCTOR, _DOCTOR_NAMESPACE)
doctor_output = _DOCTOR_NAMESPACE["doctor_output"]
DOCTOR_CANARY = _DOCTOR_NAMESPACE["CANARY"]

# The two Codex role carriers (adoption/agents/codex/), by file name; the installer step copies them.
ROLES_SOURCE_DIR = ROOT / "adoption" / "agents" / "codex"
ROLE_NAMES = ("stack-researcher.toml", "stack-verifier.toml")

FAKE_CODEX = r'''#!{python}
"""Fake codex 0.159.3 for tests/test_codex_worker_lane.py (see its docstring)."""
import hashlib, json, os, re, sys, tomllib
from pathlib import Path

HOME = Path(os.environ["CODEX_HOME"])
argv = sys.argv[1:]
profile = None
if "-p" in argv:
    i = argv.index("-p"); profile = argv[i + 1]; del argv[i:i + 2]

def load(path):
    return tomllib.loads(path.read_text()) if path.is_file() else {}

def merge(base, over):
    for k, v in over.items():
        base[k] = merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base

def effective():
    config = load(HOME / "config.toml")
    return merge(config, load(HOME / f"{profile}.config.toml")) if profile else config

{emitter}

{doctor}

def version(config):
    return "sha256:" + hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

def segments(path):
    out, cur, quoted = [], "", False
    for ch in path:
        if ch == '"': quoted = not quoted
        elif ch == "." and not quoted: out.append(cur); cur = ""
        else: cur += ch
    return out + [cur]

if argv == ["--version"]:
    print("codex-cli 0.159.3"); sys.exit(0)
if argv[:1] == ["app-server"]:
    race = os.environ.get("FAKE_CODEX_RACE")
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        method, params = msg["method"], msg.get("params") or {}
        if method == "initialize":
            print(json.dumps({"id": msg["id"], "result": {"codexHome": str(HOME)}})); sys.stdout.flush(); continue
        config = load(HOME / "config.toml")
        if method == "config/read":
            print(json.dumps({"method": "remoteControl/status/changed", "params": {"status": "disabled"}}))
            layer = {"name": {"type": "user", "file": str(HOME / "config.toml"), "profile": None},
                     "version": version(config), "config": config}
            print(json.dumps({"id": msg["id"], "result": {"config": config, "origins": {}, "layers": [layer]}}))
        elif method == "config/batchWrite":
            if race or params.get("expectedVersion") != version(config):
                print(json.dumps({"id": msg["id"], "error": {"code": -32600, "message": "Configuration was modified",
                                  "data": {"config_write_error_code": "configVersionConflict"}}}))
            else:
                for edit in params["edits"]:
                    path = segments(edit["keyPath"]); node = config
                    for s in path[:-1]:
                        node = node.setdefault(s, {})
                    if edit["value"] is None:
                        node.pop(path[-1], None)
                    else:
                        node[path[-1]] = edit["value"]
                (HOME / "config.toml").write_text(emit(config))
                print(json.dumps({"id": msg["id"], "result": {"status": "ok", "version": version(config)}}))
        sys.stdout.flush()
    sys.exit(0)
if argv[:2] == ["mcp", "get"]:
    table = effective().get("mcp_servers", {}).get(argv[2])
    if table is None:
        print(f"Error: No MCP server named '{argv[2]}' found.", file=sys.stderr); sys.exit(1)
    transport = ({"type": "streamable_http", "url": table["url"]} if "url" in table else
                 {"type": "stdio", "command": table.get("command"), "args": table.get("args", []),
                  "env": table.get("env"), "env_vars": [], "cwd": table.get("cwd")})
    print(json.dumps({"name": argv[2], "enabled": table.get("enabled", True), "transport": transport,
                      "enabled_tools": table.get("enabled_tools"), "disabled_tools": table.get("disabled_tools")}))
    sys.exit(0)
if argv[:2] == ["mcp", "list"]:
    print(json.dumps([{"name": n} for n in effective().get("mcp_servers", {})])); sys.exit(0)
if argv[:2] == ["debug", "prompt-input"]:
    text = ""
    for name in ("AGENTS.override.md", "AGENTS.md"):
        path = HOME / name
        if path.is_file() and path.read_text().strip():
            text = path.read_text(); break
    ultra = effective().get("model_reasoning_effort") == "ultra"
    mode = ("Proactive multi-agent delegation is active." if ultra else
            "Do not spawn sub-agents unless the user asks.")
    items = [{"type": "message", "role": "developer", "content": [{"type": "input_text", "text": mode}]}]
    if text:
        items.append({"type": "message", "role": "user", "content": [{"type": "input_text",
                      "text": "# AGENTS.md instructions\n\n<INSTRUCTIONS>\n" + text + "</INSTRUCTIONS>"}]})
    print(json.dumps(items, indent=2)); sys.exit(0)
if argv[:2] == ["doctor", "--json"]:
    # Like the real binary in a scratch home this always exits 1. The mode comes from a file beside this script, not
    # from the environment (the installer's rehearsal passes a closed environment); the role files decide "after".
    import time
    mode_file = Path(__file__).with_name("doctor-mode")
    mode = mode_file.read_text().strip() if mode_file.is_file() else "clean"
    if mode == "hang":
        time.sleep(5)
    agents = HOME / "agents"
    has_roles = agents.is_dir() and any(agents.rglob("*.toml"))
    sys.stdout.write(doctor_output(mode, has_roles, HOME)); sys.exit(1)
print("fake codex: unsupported " + " ".join(argv), file=sys.stderr); sys.exit(64)
'''


def template_segments() -> tuple[str, str, str]:
    """(top-rule block, upstream awareness text, exceptions block) of the AGENTS template."""
    text = (TEMPLATES / "codex.AGENTS.template.md").read_text(encoding="utf-8")
    body = text.split("\n", 1)[1]  # after the begin marker line
    top, rest = body.split("\n" + UPSTREAM_MARKER, 1)
    upstream, exceptions = rest.split("\n<!-- native-agent-stack:rtk-exceptions -->\n", 1)
    return top, upstream, exceptions


class TemplateTests(unittest.TestCase):
    def test_agents_template_is_one_managed_block(self):
        text = (TEMPLATES / "codex.AGENTS.template.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(lane.BLOCK_BEGIN))
        self.assertTrue(text.endswith(lane.BLOCK_END + "\n"))
        self.assertEqual(text.count(lane.BLOCK_BEGIN), 1)
        self.assertEqual(text.count(lane.TOP_RULE_MARKER), 1)
        self.assertEqual(text.count(lane.EXCEPTIONS_MARKER), 1)
        self.assertEqual(lane.agents_block(), text)
        # Codex expands no @ reference (codex-rs/core/src/agents_md.rs at rust-v0.157.1): the text is inline.
        self.assertFalse([line for line in text.splitlines() if line.startswith("@")])
        self.assertLess(len(text.encode("utf-8")), 8192)  # local size budget; the project-doc limit does not cap global instructions

    def test_top_rule_and_upstream_text_are_verbatim(self):
        top, upstream, _ = template_segments()
        self.assertEqual(hashlib.sha256(top.encode("utf-8")).hexdigest(), TOP_RULE_SHA256)
        self.assertEqual(len(top.split()), 827)
        self.assertEqual(hashlib.sha256(upstream.encode("utf-8")).hexdigest(), RTK_AWARENESS_SHA256)

    # The standing clauses of docs/decisions/2026-09-30-rule-text-every-layer.md, as the Codex block states them,
    # with the Sol-primary routing of docs/decisions/2026-09-30-sol-primary-quality-defaults.md and skill matching.
    STANDING_PHRASES = (
        "`search-first`", "`find-skills`", "`skill-creator`", "`$skill-name`", "its description", "SKILL.md",
        "native workflow", "A coordinator, not a bounded worker, invokes", "when no listed skill fits the task",
        "promptfoo", "paired benchmark", "Harbor or Inspect", "never a self-written runner", "completeness critic",
        "next landscape sweep", "lifecycle task", "each coordinator unit names the north-star action",
        "For unpinned work, `gpt-6.1-sol` at ultra", "`gpt-6-astra` at ultra", "complex workflow that needs Astra",
        "single consequential judgment", "complex changes across systems", "one bounded Sol repair",
        "children inherit that pin", "a spawn call names neither", "a coordinator records the trigger",
        "never a delegated child, starts a cross-family lane", "OmniRoute", "`codex -p omniroute`", "Opus 5.5 at max",
        "cooperation lanes", "A coordinator records each decision", "`docs/decisions/YYYY-MM-DD-<slug>.md`",
        "No audits, trials or network at startup", "due-file line", "one lane per artifact")

    def test_top_rule_carries_the_standing_clauses_and_a_lane_for_every_configured_server(self):
        # Each MCP server the user config template registers needs a token lane in this block, so a server added to
        # codex.config.template.toml without one fails here.
        top, _, _ = template_segments()
        servers = tomllib.loads((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))["mcp_servers"]
        lanes = next((line for line in top.splitlines() if line.startswith("Token lanes")), "")
        self.assertEqual([name for name in servers if f"`{name}`" not in lanes], [])
        self.assertEqual([phrase for phrase in self.STANDING_PHRASES if phrase not in top], [])

    def test_exceptions_name_every_raw_sensitive_form(self):
        _, _, exceptions = template_segments()
        for needle in ("`git show REV:path`", "git -C DIR show REV:path", "`diff`", "`git branch`", "`git log`",
                       "`jq`", "`find`", "`rtk proxy <command>`", "`cd`", "`export`", "`source`", "127"):
            self.assertIn(needle, exceptions)

    def test_adoption_status_finds_the_rtk_text_inline(self):
        # scripts/adoption_status.py (#368) counts RTK as wired only when RTK.md's text is inline in what Codex
        # reads; the template carries it verbatim, and a bare pointer stays false.
        _, upstream, _ = template_segments()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "RTK.md").write_text(upstream, encoding="utf-8")
            (home / "AGENTS.md").write_text("@/home/example/.codex/RTK.md\n\n" + lane.agents_block(), encoding="utf-8")
            self.assertIs(adoption_status.rtk_instructions_inline(home), True)
            (home / "AGENTS.md").write_text("@/home/example/.codex/RTK.md\n", encoding="utf-8")
            self.assertIs(adoption_status.rtk_instructions_inline(home), False)

    def test_the_lane_pins_the_linux_codex_pin(self):
        # apply_codex_lane.py refuses a codex whose --version is not CODEX_VERSION, and CodexIntegrationTests skip any
        # other codex, so a Linux pin moved without the lane leaves a pinned host unable to apply it and the opt-in
        # tests unable to run. Found 2026-09-30: the pin moved to 0.159.2 while CODEX_VERSION still named 0.157.1.
        pins = adoption_status.read_pins(ROOT / "adoption" / "pins-linux-x86_64.json")
        self.assertEqual(lane.CODEX_VERSION, pins["codex"]["version"])

    def test_profile_template(self):
        profile = tomllib.loads((TEMPLATES / "codex.stack-worker.config.toml").read_text(encoding="utf-8"))
        # A literal, not render_config.py's CODEX_MODEL placeholder: the lane installs this file verbatim, worker_pins()
        # passes its model as -m, and the lane refuses any codex but CODEX_VERSION (the Linux pin). So the literal must
        # be the model that placeholder's rule gives for that version, one the pinned client's catalog lists.
        self.assertEqual(profile["model"], render_config.codex_model_for(lane.CODEX_VERSION))
        self.assertEqual(profile["model"], "gpt-6.1-sol")
        # max, the effort of #359's control arm; ultra (the user default) turns on proactive delegation.
        self.assertEqual(profile["model_reasoning_effort"], "max")
        self.assertEqual(profile["web_search"], "live")
        self.assertLessEqual(set(profile), {"model", "model_reasoning_effort", "web_search", "mcp_servers",
                                            "shell_environment_policy"})
        # Profile-v2 is a full config layer (config/src/loader/mod.rs at rust-v0.157.1).
        # Context Hub v0.1.4 cli/src/lib/telemetry.js checks these before loading home-scoped config.
        self.assertEqual(profile.get("shell_environment_policy"),
                         {"set": {"CHUB_TELEMETRY": "0", "CHUB_FEEDBACK": "0"}})
        user = tomllib.loads((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))
        # Each table only amends a server the user template registers; alone it would be an invalid server.
        self.assertLessEqual(set(profile["mcp_servers"]), set(user["mcp_servers"]))
        writes = {"ai-memory": {"memory_write_page", "memory_delete_page", "memory_consolidate", "memory_feedback",
                                "memory_forget_sweep", "memory_auto_improve", "memory_handoff_begin",
                                "memory_handoff_accept", "memory_handoff_cancel", "memory_message_send",
                                "memory_message_pop", "memory_message_cancel", "memory_lint",
                                "memory_install_self_routing", "memory_explore"},
                  "socraticode": {"codebase_index", "codebase_update", "codebase_remove", "codebase_prune",
                                  "codebase_stop", "codebase_watch", "codebase_graph_build", "codebase_graph_remove",
                                  "codebase_graph_visualize", "codebase_context_search", "codebase_context_index",
                                  "codebase_context_remove", "codebase_graph_query", "codebase_impact",
                                  "codebase_flow", "codebase_symbol", "codebase_symbols"},
                  "headroom": set()}
        for name, excluded in writes.items():
            table = profile["mcp_servers"][name]
            self.assertEqual(table["default_tools_approval_mode"], "approve", name)
            self.assertTrue(table["enabled_tools"], name)
            self.assertFalse(set(table["enabled_tools"]) & excluded, name)
        self.assertLessEqual({"ctx_upgrade", "ctx_purge"}, set(profile["mcp_servers"]["context-mode"]["disabled_tools"]))
        self.assertNotIn("default_tools_approval_mode", profile["mcp_servers"]["context-mode"])

    def test_worker_startup_timeouts_layer_over_user_servers(self):
        # openai/codex rust-v0.157.1: RawMcpServerConfig.startup_timeout_sec in
        # core/config.schema.json; codex-mcp/src/rmcp_client.rs:103 defaults to 30 s.
        # config/src/config_layer_source.rs: profile 21 < project 25 < session 30.
        profile = tomllib.loads((TEMPLATES / "codex.stack-worker.config.toml").read_text(encoding="utf-8"))
        user = tomllib.loads((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))
        for name in ("serena", "codebase-memory"):
            with self.subTest(server=name):
                self.assertIn("command", user["mcp_servers"][name])
                self.assertEqual(profile["mcp_servers"].get(name), {"startup_timeout_sec": 60})

    def test_project_jcodemunch_approves_only_read_front_door(self):
        # openai/codex rust-v0.157.1 codex-mcp/src/mcp/mod.rs:89-98 and core/config.schema.json;
        # jgravelle/jcodemunch-mcp 8f7b34abe16fb459e0bf1c04747d584216dfe32e
        # src/jcodemunch_mcp/counter.py FRONT_DOOR, server.py:5500-5511 (order defaults read-only).
        project = tomllib.loads((TEMPLATES / "project.codex.config.template.toml").read_text(encoding="utf-8"))
        server = project["mcp_servers"]["jcodemunch"]
        self.assertEqual(server.get("default_tools_approval_mode"), "approve")
        self.assertEqual(set(server.get("enabled_tools", [])), {"route", "menu", "order"})
        for name in ("codex.config.template.toml", "codex.stack-worker.config.toml"):
            with self.subTest(template=name):
                config = tomllib.loads((TEMPLATES / name).read_text(encoding="utf-8"))
                self.assertNotIn("jcodemunch", config["mcp_servers"])

    def test_owned_edits_stay_on_the_lanes_keys(self):
        live = {"mcp_servers": {"headroom": {"command": "/x/headroom", "env": {"HEADROOM_OFFLINE": "1"}}}}
        edits = lane.owned_edits(live, "/opt/eco", "/usr/bin:/bin")
        keys = [tuple(edit["key"]) for edit in edits]
        self.assertEqual(keys[:2], [("mcp_servers", "context-mode"),
                                    ("plugins", "context-mode@context-mode", "mcp_servers", "context-mode", "enabled")])
        self.assertEqual({key[3] for key in keys[2:]}, set(lane.HEADROOM_OFFLINE_KEYS))
        entry = edits[0]["value"]
        self.assertNotIn("cwd", entry)
        self.assertEqual(entry["default_tools_approval_mode"], "approve")
        self.assertEqual(entry["env"]["PATH"], "/opt/eco/bin:/usr/bin:/bin")
        self.assertEqual(len(lane.owned_edits({}, "/opt/eco", "/usr/bin")), 2)  # no headroom registered: no env keys

    def test_key_paths_quote_what_parse_key_path_would_split(self):
        self.assertEqual(lane.key_path(["plugins", "context-mode@context-mode", "mcp_servers", "context-mode"]),
                         'plugins."context-mode@context-mode".mcp_servers.context-mode')
        self.assertEqual(lane.key_path(["projects", "/a.b/c"]), 'projects."/a.b/c"')

    def test_owned_edits_restore_the_start_up_allowance_of_registered_servers(self):
        # `codex mcp add` takes no timeout option (its --help at 0.157.1 and 0.159.2), so a server it registered has
        # none and Codex waits its 30 s default; the template gives serena 60 s and socraticode 120 s.
        user = tomllib.loads((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))
        live = {"mcp_servers": {"serena": {"command": "/x/serena"}, "socraticode": {"command": "/x/node"}}}
        timeouts = {tuple(e["key"]): e["value"] for e in lane.owned_edits(live, "/opt/eco", "/usr/bin")
                    if e["key"][-1] == "startup_timeout_sec"}
        self.assertEqual(timeouts, {("mcp_servers", name, "startup_timeout_sec"):
                                    user["mcp_servers"][name]["startup_timeout_sec"]
                                    for name in lane.STARTUP_TIMEOUT_SERVERS})
        self.assertEqual(set(timeouts.values()), {60, 120})
        only_serena = lane.owned_edits({"mcp_servers": {"serena": {"command": "/x/serena"}}}, "/opt/eco", "/usr/bin")
        self.assertEqual([e["key"][1] for e in only_serena if e["key"][-1] == "startup_timeout_sec"], ["serena"])

    def test_omniroute_profile_template(self):
        # Conflicts K1, K2, K3 and K5 of the 2026-09-27 settings synthesis, with the host's verified profile: the
        # cx/ slug with no gateway alias, the provider block in the profile (never the base config), env_key plus a
        # keyed filter that keeps the key out of model-run commands, websockets left at the default.
        text = (TEMPLATES / "codex.omniroute.config.toml").read_text(encoding="utf-8")
        self.assertNotIn("${", text)  # installed verbatim; render_config.py never renders it
        profile = tomllib.loads(text)
        self.assertEqual({k: profile[k] for k in ("model", "model_provider", "model_reasoning_effort", "web_search")},
                         {"model": "cx/gpt-6-astra", "model_provider": "omniroute", "model_reasoning_effort": "max",
                          "web_search": "live"})
        self.assertEqual(set(profile), {"model", "model_provider", "model_reasoning_effort", "web_search",
                                        "model_providers", "shell_environment_policy", "features"})
        provider = profile["model_providers"]["omniroute"]
        self.assertEqual(provider["name"], "OmniRoute")  # "OpenAI" would switch on is_openai() paths
        self.assertEqual(provider["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(provider["env_key"], "OMNIROUTE_API_KEY")
        self.assertEqual(provider["wire_api"], "responses")
        self.assertIs(provider["requires_openai_auth"], False)
        self.assertIs(provider["supports_standalone_web_search"], True)
        self.assertNotIn("supports_websockets", provider)
        self.assertNotIn("auth", provider)  # env_key, not a command (K3)
        instructions = provider["env_key_instructions"]
        self.assertIn("inventory id omniroute", instructions)
        helper = "tools/credentials/open_credential_terminal.sh"
        self.assertIn(helper, instructions)
        self.assertTrue((ROOT / helper).is_file())
        inventory = json.loads((ROOT / "adoption" / "credential-inventory.json").read_text(encoding="utf-8"))
        entry = next(e for e in inventory["entries"] if e["id"] == "omniroute")
        self.assertIn(provider["env_key"], entry["variables"])
        # The canonical keyed form only: mixing it with the legacy exclude/include_only arrays in one layer is a
        # config error, and no `set` here, so the base config's [shell_environment_policy.set] keeps applying.
        self.assertEqual(profile["shell_environment_policy"], {"filters": {"OMNIROUTE_API_KEY": "exclude"}})
        self.assertEqual(profile["features"], {"standalone_web_search": True, "shell_snapshot": False})
        # K2: the base template stays gateway-free, so render_config.py --check still compares like with like. Its
        # interactive default is GPT-6.1 Sol at ultra (the user's decision of 2026-09-30, model-currency addendum)
        # where the platform's Codex pin lists it: rendered here for the Linux pin, the lane's CODEX_VERSION. This
        # gateway profile keeps the judgment lanes' cx/gpt-6-astra at max.
        user = tomllib.loads(render_config.render_one(TEMPLATES / "codex.config.template.toml",
                                                      render_config.load_host_values("example"), "linux-x86_64"))
        self.assertNotIn("model_providers", user)
        self.assertNotIn("model_provider", user)
        self.assertEqual((user["model"], user["model_reasoning_effort"]), ("gpt-6.1-sol", "ultra"))

    def test_landscape_sweep_lane_home_matches_the_omniroute_profile(self):
        # The sweep's gateway lane cannot use `-p omniroute` (its one --profile slot is stack-worker), so its lane
        # home writes the route itself. Every model, provider and feature key it writes must equal the profile's, or
        # one of them drifted. Its config.toml has no env_key_instructions, key filter or web_search: web_search =
        # "live" comes from the stack-worker profile and the runner's -c flag, and without the filter a real key in
        # the sweep's environment reaches the model's commands (recipes/README.md, "Codex through OmniRoute"). No
        # assertion here pins those absences, so the sweep lane can add the filter without breaking this test.
        spec = importlib.util.spec_from_file_location(
            "landscape_sweep_build_args_for_lane_test", ROOT / "tools/sota-convergence/landscape-sweep/build_args.py")
        build_args = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build_args)
        profile = tomllib.loads((TEMPLATES / "codex.omniroute.config.toml").read_text(encoding="utf-8"))
        provider = profile["model_providers"]["omniroute"]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            host = work / "fixture-host.json"
            host.write_text(json.dumps({
                "HOME": "/home/example", "ECO_ROOT": "/home/example/.local/share/codex-ecosystem",
                "PROJECT_ROOT": "/home/example/code/agent-lab", "HOST_PATH": "/usr/bin:/bin",
                "CODE_INDEX_PATH": "/home/example/.code-index", "OTEL_ENDPOINT": "127.0.0.1:14318",
                "AI_MEMORY_URL": "127.0.0.1:49374", "QDRANT_URL": "127.0.0.1:16333", "EMBED_URL": "127.0.0.1:8231"}))
            build_args.stage_lane_home(work, model=profile["model"], base_url=provider["base_url"], host=str(host),
                                       profile=TEMPLATES / "codex.stack-worker.config.toml", repo_root=ROOT)
            staged = tomllib.loads((work / build_args.LANE_HOME / "config.toml").read_text(encoding="utf-8"))
        for key in ("model", "model_provider", "model_reasoning_effort"):
            self.assertEqual(staged[key], profile[key], key)
        for key, value in staged["model_providers"]["omniroute"].items():
            self.assertEqual(value, provider.get(key), f"model_providers.omniroute.{key}")
        self.assertEqual(staged["features"], profile["features"])
        self.assertEqual(build_args.OMNIROUTE_KEY_ENV, provider["env_key"])
        self.assertEqual(build_args.OMNIROUTE_DEFAULT_URL, provider["base_url"])
        self.assertEqual(build_args.OMNIROUTE_DEFAULT_MODEL, profile["model"])


class BlockTests(unittest.TestCase):
    def test_insert_replace_and_remove(self):
        block = lane.agents_block()
        for original in ("", "@/home/example/.codex/RTK.md\n", "a\n\nb\n"):
            with self.subTest(original=original):
                applied = lane.with_block(original, block)
                self.assertEqual(applied.count(lane.BLOCK_BEGIN), 1)
                self.assertTrue(applied.startswith(original.rstrip("\n")))
                self.assertEqual(lane.with_block(applied, block), applied)
                self.assertEqual(lane.without_block(applied), original)
        old = block.replace("Top rule:", "Old rule:")
        self.assertEqual(lane.with_block("x\n\n" + old + "y\n", block), "x\n\n" + block + "y\n")

    def test_damaged_markers_are_refused(self):
        for damaged in (lane.BLOCK_BEGIN + " -->\nno end\n", "text\n" + lane.BLOCK_END + "\n",
                        lane.agents_block() * 2):
            with self.subTest(damaged=damaged[:40]), self.assertRaises(lane.Refused):
                lane.block_span(damaged)


class FakeHost:
    """A scratch home, ecosystem prefix and fake codex for one test."""

    def __init__(self, testcase: unittest.TestCase):
        self.tmp = Path(tempfile.mkdtemp(prefix="codex-worker-lane-test-"))
        testcase.addCleanup(shutil.rmtree, self.tmp, True)
        self.codex_home = self.tmp / "home" / ".codex"
        self.codex_home.mkdir(parents=True)
        self.eco = self.tmp / "eco"
        (self.eco / "bin").mkdir(parents=True)
        node = self.eco / "bin" / "node"
        node.write_text("#!/bin/sh\nexit 0\n")
        node.chmod(0o755)
        start = self.eco / f"tools/context-mode-{lane.CONTEXT_MODE_VERSION}/lib/node_modules/context-mode/start.mjs"
        start.parent.mkdir(parents=True)
        start.write_text("// stand-in for start.mjs\n")
        self.codex = self.tmp / "bin" / "codex"
        self.codex.parent.mkdir()
        self.codex.write_text(FAKE_CODEX.replace("{python}", sys.executable).replace("{emitter}", EMITTER)
                              .replace("{doctor}", DOCTOR))
        self.codex.chmod(0o755)
        self.state = self.tmp / "state"
        eco = str(self.eco)
        self.config = {
            "model": "gpt-6-astra", "model_reasoning_effort": "ultra", "approval_policy": "never",
            "features": {"hooks": True, "daemon_auto_start": False},
            "shell_environment_policy": {"set": {"PATH": f"{eco}/bin:/usr/bin:/bin"}},
            "mcp_servers": {"ai-memory": {"url": "http://127.0.0.1:1/mcp"},
                            "socraticode": {"command": f"{eco}/bin/node", "args": ["x.js"]},
                            "headroom": {"command": f"{eco}/bin/headroom", "env": {"HEADROOM_OFFLINE": "1"}}},
            "plugins": {"context-mode@context-mode": {"enabled": True}},
            "projects": {"/home/example/code/x": {"trust_level": "trusted"}},
        }
        self.write_config(self.config)
        _, upstream, _ = template_segments()
        (self.codex_home / "RTK.md").write_text(upstream)
        (self.codex_home / "AGENTS.md").write_text("@/home/example/.codex/RTK.md\n")
        (self.codex_home / "AGENTS.md").chmod(0o600)
        testcase.addCleanup(setattr, lane, "START_MJS_SHA256", lane.START_MJS_SHA256)
        lane.START_MJS_SHA256 = hashlib.sha256(start.read_bytes()).hexdigest()
        self.base_args = ["--codex", str(self.codex), "--codex-home", str(self.codex_home), "--eco-root", eco,
                          "--state-dir", str(self.state), "--codex-process-name", "nas-no-such-process-x"]

    def set_doctor(self, mode: str) -> None:
        """Choose what the fake `codex doctor --json` prints (see DOCTOR): a file beside the fake binary, because the
        rehearsal's environment is closed."""
        (self.codex.parent / "doctor-mode").write_text(mode + "\n")

    def write_config(self, config: dict) -> None:
        (self.codex_home / "config.toml").write_text(emit_toml(config))
        (self.codex_home / "config.toml").chmod(0o600)

    def read_config(self) -> dict:
        return tomllib.loads((self.codex_home / "config.toml").read_text())

    def sha(self, name: str) -> str:
        return lane.sha256_file(self.codex_home / name) or "absent"

    def run(self, *args: str, env: dict | None = None) -> tuple[int, str]:
        out = io.StringIO()
        saved = dict(os.environ)
        try:
            os.environ.update(env or {})
            with contextlib.redirect_stdout(out):
                code = lane.main([*self.base_args, *args])
        finally:
            os.environ.clear()
            os.environ.update(saved)
        return code, out.getvalue()

    def apply(self, **env) -> tuple[int, str]:
        return self.run("--apply", "--expect-config-sha256", self.sha("config.toml"),
                        "--expect-agents-sha256", self.sha("AGENTS.md"), env=env or None)

    def latest_run(self) -> Path:
        return (self.state / "codex-lane" / "latest").resolve()


class ApplyFlowTests(unittest.TestCase):
    """Synthetic: the fake codex above stands in for codex-cli 0.159.3."""

    def setUp(self):
        self.host = FakeHost(self)

    def test_dry_run_writes_nothing_under_the_codex_home(self):
        before = {p.name: p.read_bytes() for p in self.host.codex_home.iterdir()}
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("rehearsal passed", out)
        self.assertIn(f"--expect-config-sha256 {self.host.sha('config.toml')}", out)
        self.assertEqual({p.name: p.read_bytes() for p in self.host.codex_home.iterdir()}, before)
        self.assertFalse(self.host.state.exists())

    def test_apply_needs_the_reviewed_hashes(self):
        code, out = self.host.run("--apply")
        self.assertEqual(code, 2, out)
        code, out = self.host.run("--apply", "--expect-config-sha256", "0" * 64, "--expect-agents-sha256",
                                  self.host.sha("AGENTS.md"))
        self.assertEqual(code, 2, out)
        self.assertIn("differs from the reviewed", out)
        self.assertFalse((self.host.codex_home / "stack-worker.config.toml").exists())
        self.assertFalse(self.host.state.exists())

    def test_apply_refuses_while_the_named_process_runs(self):
        sleeper = subprocess.Popen(["sleep", "30"])
        self.addCleanup(sleeper.kill)
        base = self.host.base_args
        self.host.base_args = base[:-1] + ["sleep"]
        code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn("codex processes", out)

    def test_apply_is_read_back_and_idempotent_and_rollback_restores(self):
        original_config = self.host.read_config()
        original_agents = (self.host.codex_home / "AGENTS.md").read_bytes()
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        config = self.host.read_config()
        entry = config["mcp_servers"]["context-mode"]
        self.assertNotIn("cwd", entry)
        self.assertEqual(entry["args"], [str(self.host.eco / "tools/context-mode-1.0.169/lib/node_modules/"
                                                               "context-mode/start.mjs")])
        self.assertIs(config["plugins"]["context-mode@context-mode"]["mcp_servers"]["context-mode"]["enabled"], False)
        self.assertEqual(config["mcp_servers"]["headroom"]["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(lane.without_owned(config, [e["key"] for e in lane.owned_edits(original_config, "", "x")]),
                         lane.without_owned(original_config, [e["key"] for e in lane.owned_edits(original_config, "", "x")]))
        agents = (self.host.codex_home / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("@/home/example/.codex/RTK.md\n\n" + lane.BLOCK_BEGIN))
        self.assertEqual((self.host.codex_home / "AGENTS.md").stat().st_mode & 0o777, 0o600)
        profile = self.host.codex_home / "stack-worker.config.toml"
        self.assertEqual(profile.read_bytes(), (TEMPLATES / "codex.stack-worker.config.toml").read_bytes())
        self.assertEqual(profile.stat().st_mode & 0o777, 0o600)
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["status"], "applied")
        for name in ("config.toml.before", "AGENTS.md.before", "record.json"):
            self.assertEqual((run / name).stat().st_mode & 0o777, 0o600, name)
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        self.assertNotIn("auth", " ".join(p.name for p in run.iterdir()))

        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertIn("already in place", out)
        self.assertEqual(self.host.latest_run(), run)

        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.host.read_config(), original_config)
        self.assertEqual((self.host.codex_home / "AGENTS.md").read_bytes(), original_agents)
        self.assertFalse(profile.exists())
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertIn("already", out)
        self.assertEqual(json.loads((run / "record.json").read_text())["status"], "rolled-back")

    def test_rollback_keeps_what_others_changed_since(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        config = self.host.read_config()
        config["mcp_servers"]["context-mode"]["startup_timeout_sec"] = 90  # a later writer
        self.host.write_config(config)
        agents = self.host.codex_home / "AGENTS.md"
        agents.write_text(agents.read_text() + "\nA line someone added later.\n")
        code, out = self.host.run("--rollback", str(self.host.latest_run()))
        self.assertEqual(code, 3, out)
        self.assertIn("CONFLICT: mcp_servers.context-mode changed since the run", out)
        after = self.host.read_config()
        self.assertEqual(after["mcp_servers"]["context-mode"]["startup_timeout_sec"], 90)
        self.assertNotIn("mcp_servers", after["plugins"]["context-mode@context-mode"])
        self.assertNotIn("HF_HUB_OFFLINE", after["mcp_servers"]["headroom"]["env"])
        text = agents.read_text()
        self.assertNotIn(lane.BLOCK_BEGIN, text)
        self.assertIn("@/home/example/.codex/RTK.md", text)
        self.assertIn("A line someone added later.", text)

    def test_rollback_removes_shared_created_root_and_preserves_foreign_values(self):
        # The same created_root owns multiple Headroom env edits. A native null write
        # must delete the table only when its remaining contents still belong to this run.
        for later_change in ("none", "partial-undo", "foreign-key", "edited-key"):
            with self.subTest(later_change=later_change):
                host = FakeHost(self)
                del host.config["mcp_servers"]["headroom"]["env"]
                host.write_config(host.config)
                before = host.read_config()
                code, out = host.apply()
                self.assertEqual(code, 0, out)
                current = host.read_config()
                env = current["mcp_servers"]["headroom"]["env"]
                self.assertGreater(len(env), 1)
                owned_key = next(iter(env))
                if later_change == "partial-undo":
                    del env[owned_key]
                elif later_change == "foreign-key":
                    env["LATER_SETTING"] = "keep"
                    before["mcp_servers"]["headroom"]["env"] = {"LATER_SETTING": "keep"}
                elif later_change == "edited-key":
                    env[owned_key] = "changed"
                    before["mcp_servers"]["headroom"]["env"] = {owned_key: "changed"}
                host.write_config(current)
                run = host.latest_run()
                for attempt in range(2):
                    code, out = host.run("--rollback", str(run))
                    self.assertEqual(code, 3 if later_change == "edited-key" else 0, out)
                    self.assertEqual(host.read_config(), before, f"rollback attempt {attempt}: {out}")

    def test_a_version_conflict_writes_nothing_and_blocks_the_next_apply(self):
        before_agents = (self.host.codex_home / "AGENTS.md").read_bytes()
        code, out = self.host.apply(FAKE_CODEX_RACE="1")
        self.assertEqual(code, 3, out)
        self.assertIn("configVersionConflict", out)
        self.assertEqual((self.host.codex_home / "AGENTS.md").read_bytes(), before_agents)
        self.assertFalse((self.host.codex_home / "stack-worker.config.toml").exists())
        run = self.host.latest_run()
        self.assertEqual(json.loads((run / "record.json").read_text())["status"], "failed")
        code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn("roll it back first", out)
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)

    def test_rollback_conflicts_on_an_edited_managed_block(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        run = self.host.latest_run()
        agents = self.host.codex_home / "AGENTS.md"
        edited = agents.read_text().replace(lane.TOP_RULE_MARKER,
                                            lane.TOP_RULE_MARKER + "\nAn instruction edited after apply.", 1)
        agents.write_text(edited)
        code, out = self.host.run("--rollback", str(run))
        conflict = "AGENTS.md: the managed block changed since the run; left in place"
        self.assertEqual(code, 3, out)
        self.assertIn("CONFLICT: " + conflict, out.splitlines())
        self.assertEqual(agents.read_bytes(), edited.encode())
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["status"], "rollback-conflict")
        self.assertEqual(record["rollbacks"][-1]["conflicts"], [conflict])
        self.assertNotIn("agents", record["rollbacks"][-1]["outcome"])

    def test_rollback_restores_a_prior_managed_block_verbatim(self):
        # Both the whole-file restore and the prior-block splice must preserve literal bytes.
        prior = (lane.BLOCK_BEGIN + " prior -->\nEarlier instruction with trailing spaces.  \n"
                 "\tKeep this indentation.\n\n" + lane.BLOCK_END + "\n")
        prefix, suffix = "Existing prefix.\n\n", "\nExisting suffix.\n"
        for outside_edits in (False, True):
            with self.subTest(outside_edits=outside_edits):
                host = FakeHost(self)
                agents = host.codex_home / "AGENTS.md"
                original = (prefix + prior + suffix).encode()
                agents.write_bytes(original)
                code, out = host.apply()
                self.assertEqual(code, 0, out)
                self.assertEqual(agents.read_text(), prefix + lane.agents_block() + suffix)
                run = host.latest_run()
                if outside_edits:
                    agents.write_text("New prefix.\n" + agents.read_text() + "\nNew suffix.\n")
                code, out = host.run("--rollback", str(run))
                self.assertEqual(code, 0, out)
                expected = b"New prefix.\n" + original + b"\nNew suffix.\n" if outside_edits else original
                self.assertEqual(agents.read_bytes(), expected)
                outcome = ("the earlier block is back; edits made since outside it are kept" if outside_edits
                           else "restored from the backup")
                record = json.loads((run / "record.json").read_text())
                self.assertEqual(record["rollbacks"][-1]["outcome"]["agents"], outcome)
                self.assertIn("agents: " + outcome, out.splitlines())

    def test_rollback_keeps_the_prior_block_backup_when_the_managed_block_was_removed(self):
        prior = lane.BLOCK_BEGIN + " prior -->\nPrior instructions.\n" + lane.BLOCK_END + "\n"
        original = ("Existing prefix.\n\n" + prior + "\nExisting suffix.\n").encode()
        agents = self.host.codex_home / "AGENTS.md"
        agents.write_bytes(original)
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertNotIn("Prior instructions.", agents.read_text())
        self.assertIn(lane.agents_block(), agents.read_text())
        run = self.host.latest_run()
        removed = b"Existing prefix.\n\nThe block was removed elsewhere.\n\nExisting suffix.\n"
        agents.write_bytes(removed)
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        outcome = "no managed block left; nothing to undo"
        self.assertIn("agents: " + outcome, out.splitlines())
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["rollbacks"][-1]["outcome"]["agents"], outcome)
        self.assertEqual(agents.read_bytes(), removed)
        backup = run / "AGENTS.md.before"
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_bytes(), original)
        self.assertIn(prior.encode(), backup.read_bytes())

    def test_an_override_with_text_and_a_damaged_block_are_refused(self):
        (self.host.codex_home / "AGENTS.override.md").write_text("override\n")
        code, out = self.host.run()
        self.assertEqual(code, 2, out)
        self.assertIn("[fail] AGENTS.override.md", out)
        (self.host.codex_home / "AGENTS.override.md").write_text("  \n")  # blank, as Rust's trim sees it
        (self.host.codex_home / "AGENTS.md").write_text(lane.BLOCK_BEGIN + " -->\n")
        code, out = self.host.run()
        self.assertEqual(code, 2, out)
        self.assertIn("[fail] AGENTS.md block", out)

    def test_a_different_profile_is_not_overwritten(self):
        (self.host.codex_home / "stack-worker.config.toml").write_text('model = "other"\n')
        code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertEqual((self.host.codex_home / "stack-worker.config.toml").read_text(), 'model = "other"\n')

    def test_project_config_host_step_is_reported(self):
        project = self.host.tmp / "project" / ".codex" / "config.toml"
        project.parent.mkdir(parents=True)
        project.write_text('[plugins."context-mode@context-mode".mcp_servers.context-mode]\nenabled = false\n\n'
                           '[mcp_servers.context-mode]\ncommand = "/x/node"\ncwd = "/x"\n\n'
                           '[mcp_servers.context-mode.env]\nCONTEXT_MODE_PROJECT_DIR = "/x"\n\n'
                           '[mcp_servers.jcodemunch]\ncommand = "/x/jcodemunch-mcp"\n')
        code, out = self.host.run("--project-config", str(project))
        self.assertEqual(code, 0, out)
        for line in ("line 1: [plugins.", "line 4: [mcp_servers.context-mode]", "line 8: [mcp_servers.context-mode.env]"):
            self.assertIn(line, out)
        self.assertNotIn("jcodemunch", out.split("HOST STEP", 1)[1].split("rehearsal", 1)[0])

    def test_start_up_allowances_are_written_for_registered_servers_and_rolled_back(self):
        # FakeHost registers socraticode without startup_timeout_sec; add serena the same way (a `codex mcp add`
        # registration). codebase-memory has no template allowance and is left alone.
        self.host.config["mcp_servers"]["serena"] = {"command": f"{self.host.eco}/bin/serena"}
        self.host.config["mcp_servers"]["codebase-memory"] = {"command": f"{self.host.eco}/bin/codebase-memory-mcp"}
        self.host.write_config(self.host.config)
        before = self.host.read_config()
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("set  mcp_servers.serena.startup_timeout_sec: absent -> 60", out)
        self.assertIn("set  mcp_servers.socraticode.startup_timeout_sec: absent -> 120", out)
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        after = self.host.read_config()
        self.assertEqual(after["mcp_servers"]["serena"]["startup_timeout_sec"], 60)
        self.assertEqual(after["mcp_servers"]["socraticode"]["startup_timeout_sec"], 120)
        self.assertNotIn("startup_timeout_sec", after["mcp_servers"]["codebase-memory"])
        code, out = self.host.run("--rollback", str(self.host.latest_run()))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.host.read_config(), before)

    def test_omniroute_profile_is_opt_in_created_read_back_and_rolled_back(self):
        profile = self.host.codex_home / "omniroute.config.toml"
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertFalse(profile.exists())  # without --omniroute-profile nothing about it is written
        first = self.host.latest_run()
        self.assertNotIn("omniroute_profile", json.loads((first / "record.json").read_text()))
        code, out = self.host.run("--omniroute-profile")
        self.assertEqual(code, 0, out)
        self.assertIn("omniroute.config.toml: create", out)
        self.assertIn("prompt input -p omniroute:", out)
        self.assertIn(" --omniroute-profile ", out)  # the printed apply command keeps the flag
        self.assertFalse(profile.exists())  # the dry run writes nothing
        code, out = self.host.run("--omniroute-profile", "--apply", "--expect-config-sha256", self.host.sha("config.toml"),
                                  "--expect-agents-sha256", self.host.sha("AGENTS.md"))
        self.assertEqual(code, 0, out)
        self.assertEqual(profile.read_bytes(), (TEMPLATES / "codex.omniroute.config.toml").read_bytes())
        self.assertEqual(profile.stat().st_mode & 0o777, 0o600)
        run = self.host.latest_run()
        self.assertNotEqual(run, first)
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["omniroute_profile"]["state"], "done")
        self.assertIs(record["omniroute_profile"]["created"], True)
        self.assertTrue(record["readback"]["prompt_input_omniroute"]["no_spawn_unless_asked"])
        self.assertFalse(record["readback"]["prompt_input_omniroute"]["proactive_delegation"])
        code, out = self.host.run("--omniroute-profile", "--apply", "--expect-config-sha256",
                                  self.host.sha("config.toml"), "--expect-agents-sha256", self.host.sha("AGENTS.md"))
        self.assertEqual(code, 0, out)
        self.assertIn("already in place", out)
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertIn("omniroute_profile: removed", out)
        self.assertFalse(profile.exists())
        self.assertTrue((self.host.codex_home / "stack-worker.config.toml").exists())  # the first run's, untouched
        code, out = self.host.run("--rollback", str(first))  # an older record without the entry
        self.assertEqual(code, 0, out)
        self.assertNotIn("omniroute_profile", out)

    def test_a_different_omniroute_profile_is_not_overwritten(self):
        profile = self.host.codex_home / "omniroute.config.toml"
        profile.write_text('model = "cx/gpt-6-astra"\nmodel_provider = "omniroute"\n')
        code, out = self.host.run("--omniroute-profile", "--apply", "--expect-config-sha256",
                                  self.host.sha("config.toml"), "--expect-agents-sha256", self.host.sha("AGENTS.md"))
        self.assertEqual(code, 2, out)
        self.assertIn("[fail] omniroute profile", out)
        self.assertEqual(profile.read_text(), 'model = "cx/gpt-6-astra"\nmodel_provider = "omniroute"\n')
        self.assertFalse(self.host.state.exists())

    def test_a_base_config_provider_block_is_reported_as_a_host_step(self):
        self.host.config["model_providers"] = {"omniroute": {"name": "OmniRoute", "base_url": "http://127.0.0.1:1/v1",
                                                             "env_key": "OMNIROUTE_API_KEY"}}
        self.host.write_config(self.host.config)
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertNotIn("HOST STEP", out)  # reported only when the gateway profile is part of the run
        code, out = self.host.run("--omniroute-profile")
        self.assertEqual(code, 0, out)
        step = out.split("HOST STEP", 1)[1].split("rehearsal", 1)[0]
        lines = (self.host.codex_home / "config.toml").read_text().splitlines()
        number = lines.index("[model_providers.omniroute]") + 1
        self.assertIn(f"line {number}: [model_providers.omniroute]", step)
        # The lane never sends that table: the rehearsed write leaves it as it was.
        self.assertNotIn("model_providers", " ".join(line for line in out.splitlines() if line.startswith("  set ")))

    def test_base_config_gateway_selectors_are_part_of_the_host_step(self):
        # Upstream's guide puts model = "cx/..." and model_provider = "omniroute" in config.toml
        # (docs/guides/CODEX-CLI-CONFIGURATION.md L28-29 at a58000c7). Deleting only the table would leave every launch
        # without the profile at "Model provider `omniroute` not found" (codex-cli 0.157.1, measured 2026-09-27).
        code, out = self.host.run("--omniroute-profile")
        self.assertEqual(code, 0, out)
        self.assertNotIn("HOST STEP", out)  # the control: a native model and no gateway selector
        self.host.config = {"model": "cx/gpt-6-astra", "model_provider": "omniroute",
                            **{k: v for k, v in self.host.config.items() if k != "model"}}
        self.host.write_config(self.host.config)
        code, out = self.host.run("--omniroute-profile")
        self.assertEqual(code, 0, out)
        step = out.split("HOST STEP", 1)[1].split("rehearsal", 1)[0]
        lines = (self.host.codex_home / "config.toml").read_text().splitlines()
        for text in ('model = "cx/gpt-6-astra"', 'model_provider = "omniroute"'):
            self.assertIn(f"line {lines.index(text) + 1}: {text}", step)
        self.assertNotIn("[model_providers.omniroute]", step)  # no table here, so none is listed
        self.assertIn("`codex debug prompt-input probe`", step)  # the read-back covers a launch without the profile
        self.assertIn("Model provider `omniroute` not found", step)


def snapshot(root: Path) -> dict:
    """{relative path: file bytes, link target, or None for a directory} of everything under root, links not followed."""
    found = {}
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(directory, name)
            key = path.relative_to(root).as_posix()
            if path.is_symlink():
                found[key] = os.readlink(path)
            else:
                found[key] = None if path.is_dir() else path.read_bytes()
    return found


def need(test: unittest.TestCase, owner, name: str):
    """owner.name, or a failure by assertion when the change under test has not added it yet."""
    value = getattr(owner, name, None)
    if value is None:
        test.fail(f"{getattr(owner, '__name__', type(owner).__name__)}.{name} is missing")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RoleStepTests(unittest.TestCase):
    """The installer's role step: the two Codex role carriers of adoption/agents/codex/, installed user-wide under
    $CODEX_HOME/agents by discovery only (no [agents.<name>] table). Synthetic: the fake codex answers `doctor --json`
    in the shape the real 0.157.1 binary printed in a scratch home (always exit 1; see DOCTOR). Case letters follow
    section 4.3 of the U13 design; the controls at the end are its section 4.5."""

    def setUp(self):
        self.host = FakeHost(self)
        # /etc/codex is a config layer of every launch: the tests never read the host's.
        self.system = self.host.tmp / "etc-codex"
        self.system.mkdir()
        patcher = mock.patch.object(lane, "SYSTEM_CODEX_DIR", self.system, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.agents = self.host.codex_home / "agents"
        self.sources = {name: (ROLES_SOURCE_DIR / name).read_bytes() for name in ROLE_NAMES}

    def installed(self, name: str) -> bytes:
        path = self.agents / name
        self.assertTrue(path.is_file(), f"agents/{name} was not installed")
        return path.read_bytes()

    def alternate_sources(self, change=None, drop=None, sums=True) -> Path:
        """A fresh copy of the shipped carriers with `change(name, bytes)` applied; `drop` names one to leave out.
        `sums` is the SHA256SUMS beside them: True copies the shipped file, False leaves it out, a string is its text."""
        alt = self.host.tmp / "sources"
        shutil.rmtree(alt, ignore_errors=True)
        alt.mkdir()
        for name, data in self.sources.items():
            if name != drop:
                (alt / name).write_bytes(change(name, data) if change else data)
        if sums is True:
            shutil.copyfile(ROLES_SOURCE_DIR / "SHA256SUMS", alt / "SHA256SUMS")
        elif sums:
            (alt / "SHA256SUMS").write_text(sums, encoding="utf-8")
        return alt

    # --- a: the dry run
    def test_a_dry_run_plans_both_roles_writes_nothing_and_reads_the_doctor(self):
        before = snapshot(self.host.codex_home)
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        for name in ROLE_NAMES:
            self.assertIn(f"agents/{name}: create", out.splitlines())
            self.assertIn(f"[ok] agent role source {name}: sha256 ", out)
        for line in ("[ok] agents directory: absent; will be created", "[ok] extra agent role files: 0",
                     "[ok] agent role tables: 0", "[ok] system agent roles: 0"):
            self.assertIn(line, out)
        self.assertIn("codex doctor config.load: startup warnings 0 -> 0 with the role files "
                      "(0 agent role warnings)", out)
        self.assertIn("result: rehearsal passed", out)
        self.assertEqual(snapshot(self.host.codex_home), before)
        self.assertFalse(self.host.state.exists())

    # --- b: apply, second apply, rollback
    def test_b_apply_creates_the_roles_read_back_and_rollback_removes_them(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.agents.is_dir(), "the agents directory was not created")
        self.assertEqual(self.agents.stat().st_mode & 0o777, 0o700)
        for name in ROLE_NAMES:
            self.assertEqual(self.installed(name), self.sources[name])
            self.assertEqual((self.agents / name).stat().st_mode & 0o777, 0o600)
            self.assertIn(f"agents/{name}: in place", out.splitlines())
        self.assertEqual(sorted(p.name for p in self.agents.iterdir()), sorted(ROLE_NAMES))  # no temporary file left
        self.assertNotIn("agents", self.host.read_config())  # discovery only: no [agents.<name>] table is written
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertIn("agent_roles", record)
        roles = record["agent_roles"]
        self.assertIs(roles["created_dir"], True)
        for name in ROLE_NAMES:
            entry = roles["files"][name]
            self.assertEqual((entry["state"], entry["existed"], entry["created"]), ("done", False, True))
            self.assertEqual(entry["sha256_after"], digest(self.sources[name]))

        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertIn("already in place: nothing to do", out)
        self.assertEqual(self.host.latest_run(), run)

        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        for name in ROLE_NAMES:
            self.assertIn(f"agents/{name}: removed", out.splitlines())
        self.assertIn("agents directory: removed (the run created it)", out.splitlines())
        self.assertFalse(self.agents.exists())
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertIn("agents/stack-researcher.toml: already absent", out.splitlines())

    # --- c: the short-circuit needs the roles too
    def test_c_a_host_with_the_rest_of_the_lane_in_place_still_gets_the_roles(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        shutil.rmtree(self.agents, ignore_errors=True)  # a host set up before the roles existed
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertNotIn("already in place: nothing to do", out)
        for name in ROLE_NAMES:
            self.assertEqual(self.installed(name), self.sources[name])

    # --- d: a differing installed role is never overwritten
    def test_d_a_differing_installed_role_is_refused_and_left_alone(self):
        self.agents.mkdir(mode=0o700)
        (self.agents / ROLE_NAMES[0]).write_text('name = "stack-researcher"\n')
        code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn(f"[fail] agent role {ROLE_NAMES[0]}", out)
        self.assertEqual((self.agents / ROLE_NAMES[0]).read_text(), 'name = "stack-researcher"\n')
        self.assertFalse((self.agents / ROLE_NAMES[1]).exists())
        self.assertFalse(self.host.state.exists())
        code, out = self.host.run()
        self.assertEqual(code, 2, out)
        self.assertIn("apply would refuse", out)

    # --- e: an extra role file is reported as a count only
    def test_e_an_extra_nested_toml_is_a_count_only_warning(self):
        (self.agents / "nested").mkdir(parents=True)
        (self.agents / "nested" / "extra-role-name.toml").write_text('name = "extra"\n')
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("[warn] extra agent role files: 1", out)
        self.assertNotIn("extra-role-name", out)

    def test_e_a_linked_folder_below_agents_is_an_unknown_count_warning(self):
        # Codex enters a linked folder (see test_agents_toml_count_counts_recursively_and_is_unknown_behind_a_folder_link),
        # so the extra-role count can be neither 0 nor N there: it is unknown, in words that hold no name.
        other = self.host.tmp / "roles-elsewhere"
        other.mkdir()
        (other / "elsewhere-role-name.toml").write_text('name = "extra"\n')
        self.agents.mkdir(parents=True)
        (self.agents / "shared-folder-name").symlink_to(other)
        code, out = self.host.run()
        self.assertEqual(code, 0, out)  # a warning, like an extra file: the carriers can still be installed
        self.assertIn("[warn] extra agent role files: unknown", out)
        self.assertNotIn("elsewhere-role-name", out)
        self.assertNotIn("shared-folder-name", out)

    # --- f: a created role edited afterwards is a conflict, not a deletion
    def test_f_a_role_edited_after_apply_is_a_rollback_conflict(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        run = self.host.latest_run()
        edited = self.installed(ROLE_NAMES[1]) + b"# edited after the run\n"
        (self.agents / ROLE_NAMES[1]).write_bytes(edited)
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 3, out)
        self.assertIn(f"CONFLICT: agents/{ROLE_NAMES[1]} changed since the run; left in place", out.splitlines())
        self.assertEqual((self.agents / ROLE_NAMES[1]).read_bytes(), edited)
        self.assertFalse((self.agents / ROLE_NAMES[0]).exists())  # the untouched one is removed
        self.assertIn("agents directory: left in place (not empty)", out.splitlines())
        self.assertEqual(json.loads((run / "record.json").read_text())["status"], "rollback-conflict")

    # --- g, h, i: the doctor's startup warnings rise with the role files
    def test_g_a_role_warning_string_fails_the_rehearsal(self):
        self.host.set_doctor("role_string")
        code, out = self.host.run()
        self.assertEqual(code, 3, out)
        self.assertIn("PROBLEM: codex doctor startup warnings rose from 0 to 1 with the role files "
                      "(1 agent role warnings)", out)
        self.assertIn("result: the rehearsal failed; do not apply", out)
        self.assertNotIn("rehearsal passed", out)

    def test_h_a_role_warning_list_counts_each_warning(self):
        self.host.set_doctor("role_list")
        code, out = self.host.run()
        self.assertEqual(code, 3, out)
        self.assertIn("PROBLEM: codex doctor startup warnings rose from 0 to 2 with the role files "
                      "(2 agent role warnings)", out)

    def test_i_a_redacted_rise_still_fails_the_rehearsal(self):
        # redact_detail hides the text (a credential word in it); the count key survives the redaction.
        self.host.set_doctor("redacted_rise")
        code, out = self.host.run()
        self.assertEqual(code, 3, out)
        self.assertIn("PROBLEM: codex doctor startup warnings rose from 0 to 1 with the role files "
                      "(0 agent role warnings)", out)

    def test_a_config_that_no_longer_loads_with_the_roles_fails_the_rehearsal(self):
        # loader.rs propagates a directory-read error with `?`, so doctor reports config.load as failed, not warned.
        self.host.set_doctor("load_fail")
        code, out = self.host.run()
        self.assertEqual(code, 3, out)
        self.assertIn("PROBLEM: codex doctor could not load the config with the role files", out)

    def test_a_warning_the_scratch_home_has_without_the_roles_is_not_blamed_on_them(self):
        # A malformed system-layer role warns in both passes: no rise, so the rehearsal passes. The system-role
        # count line is what reports that layer.
        self.host.set_doctor("preexisting")
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("codex doctor config.load: startup warnings 1 -> 1 with the role files "
                      "(0 agent role warnings)", out)
        self.assertIn("result: rehearsal passed", out)

    # --- j: no readable config.load is unknown, and the dry run can still pass
    def test_j_an_unreadable_doctor_report_is_a_warning_not_a_failure(self):
        for mode in ("no_config_load", "not_json"):
            with self.subTest(mode=mode):
                self.host.set_doctor(mode)
                code, out = self.host.run()
                self.assertEqual(code, 0, out)
                self.assertIn("[warn] doctor config.load unknown", out)
                self.assertIn("result: rehearsal passed", out)

    def test_a_doctor_that_hangs_is_unknown_after_its_timeout(self):
        self.host.set_doctor("hang")
        with mock.patch.object(lane, "DOCTOR_TIMEOUT", 1.0, create=True):
            code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("[warn] doctor config.load unknown", out)
        self.assertIn("result: rehearsal passed", out)

    # --- k: literal targets only
    def test_k_an_agents_directory_that_is_a_link_or_a_file_is_refused(self):
        elsewhere = self.host.tmp / "elsewhere"
        elsewhere.mkdir()
        self.agents.symlink_to(elsewhere)
        code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn("[fail] agents directory", out)
        self.assertEqual(list(elsewhere.iterdir()), [])  # nothing was written through the link
        self.assertFalse(self.host.state.exists())
        self.agents.unlink()
        self.agents.write_text("not a directory\n")
        code, out = self.host.run()
        self.assertEqual(code, 2, out)
        self.assertIn("[fail] agents directory", out)
        self.assertEqual(self.agents.read_text(), "not a directory\n")

    # --- l: the source is checked against its pinned row before anything is copied
    def test_l_a_carrier_with_one_byte_changed_is_refused(self):
        def flip(name, data):
            changed = data.replace(b"your output", b"your Output", 1)
            self.assertNotEqual(changed, data)
            return changed if name == ROLE_NAMES[1] else data

        with mock.patch.object(lane, "ROLES_SOURCE", self.alternate_sources(flip), create=True):
            code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn(f"[fail] agent role source {ROLE_NAMES[1]}: sha256_row", out)
        self.assertNotIn(f"[fail] agent role source {ROLE_NAMES[0]}", out)
        self.assertFalse(self.agents.exists())
        self.assertFalse(self.host.state.exists())

    def test_l_a_sums_row_that_is_not_the_sources_digest_is_refused(self):
        rows = {name: digest(data) for name, data in self.sources.items()}
        rows[ROLE_NAMES[1]] = "0" * 64
        text = "".join(f"{value}  {name}\n" for name, value in rows.items())
        with mock.patch.object(lane, "ROLES_SOURCE", self.alternate_sources(sums=text)):
            code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn(f"[fail] agent role source {ROLE_NAMES[1]}: sha256_row", out)
        self.assertNotIn(f"[fail] agent role source {ROLE_NAMES[0]}", out)
        self.assertFalse(self.agents.exists())
        self.assertFalse(self.host.state.exists())

    def test_l_a_missing_or_malformed_sums_file_refuses_both_carriers(self):
        for label, sums in (("missing", False), ("malformed", "not a checksum line\n")):
            with self.subTest(sums=label):
                with mock.patch.object(lane, "ROLES_SOURCE", self.alternate_sources(sums=sums)):
                    code, out = self.host.run()
                self.assertEqual(code, 2, out)
                for name in ROLE_NAMES:
                    self.assertIn(f"[fail] agent role source {name}: sha256_row, sha256sums_names", out)

    def test_l_a_third_name_in_the_sums_file_refuses_both_carriers(self):
        text = (ROLES_SOURCE_DIR / "SHA256SUMS").read_text(encoding="utf-8") + f"{'1' * 64}  stack-x.toml\n"
        with mock.patch.object(lane, "ROLES_SOURCE", self.alternate_sources(sums=text)):
            code, out = self.host.run()
        self.assertEqual(code, 2, out)
        for name in ROLE_NAMES:
            self.assertIn(f"[fail] agent role source {name}: sha256sums_names", out)

    def test_l_a_consistent_edit_that_breaks_a_structural_rule_is_refused(self):
        # The carrier was edited together with its row, so its digest agrees with SHA256SUMS: the structural rules
        # of design 3.3 are what refuse it, and the line names the rule id, not the text.
        anchor = b"You do not spawn, message or follow up with other agents."
        edited = {name: (data.replace(anchor, anchor + b" Use ToolSearch.", 1) if name == ROLE_NAMES[0] else data)
                  for name, data in self.sources.items()}
        self.assertNotEqual(edited[ROLE_NAMES[0]], self.sources[ROLE_NAMES[0]])
        text = "".join(f"{digest(data)}  {name}\n" for name, data in edited.items())
        with mock.patch.object(lane, "ROLES_SOURCE", self.alternate_sources(change=lambda name, data: edited[name],
                                                                             sums=text)):
            code, out = self.host.apply()
        self.assertEqual(code, 2, out)
        self.assertIn(f"[fail] agent role source {ROLE_NAMES[0]}: claude_only_name", out)
        self.assertNotIn("ToolSearch", out)
        self.assertNotIn(f"[fail] agent role source {ROLE_NAMES[1]}", out)
        self.assertFalse(self.agents.exists())

    def test_role_source_problems_name_each_rule(self):
        problems = need(self, lane, "role_source_problems")
        stem = ROLE_NAMES[0][:-len(".toml")].encode()
        cases = (("intact", lambda data: data, []),
                 ("missing", None, ["source_missing"]),
                 ("one byte", lambda data: data.replace(b"your output", b"your Output", 1), ["sha256_row"]),
                 ("not toml", lambda data: data + b"\n[[[\n", ["sha256_row", "toml_parse"]),
                 ("renamed", lambda data: data.replace(b'name = "' + stem + b'"', b'name = "' + stem + b'-x"', 1),
                  ["name_stem", "sha256_row"]))
        for label, change, expected in cases:
            with self.subTest(case=label):
                alt = self.alternate_sources(lambda name, data: change(data) if name == ROLE_NAMES[0] else data,
                                             drop=ROLE_NAMES[0] if change is None else None)
                with mock.patch.object(lane, "ROLES_SOURCE", alt, create=True):
                    found = problems()
                self.assertEqual(found, {ROLE_NAMES[0]: expected, ROLE_NAMES[1]: []})

    def test_the_pinned_rows_are_shipped_in_sha256sums_and_the_installer_holds_no_second_copy(self):
        # design 3.1: the rows the installer checks against are adoption/agents/codex/SHA256SUMS, the same ones that
        # tests/test_codex_agents.py pins as independent literals.
        from tests.test_codex_agents import STACK_ROLE_ROWS
        import codex_roles
        expected = {}
        for row in STACK_ROLE_ROWS:
            name, value = (cell.strip().strip("`") for cell in row.strip().strip("|").split("|"))
            expected[name] = value
        rows = codex_roles.sha256sums(ROLES_SOURCE_DIR / "SHA256SUMS")
        self.assertEqual(rows, expected)
        self.assertEqual(rows, {name: digest(self.sources[name]) for name in ROLE_NAMES})
        self.assertFalse(hasattr(lane, "ROLE_ROWS"), "the installer carries a second copy of the rows")
        self.assertFalse(hasattr(lane, "role_pins"), "the installer carries a second reader of the rows")
        self.assertEqual(tuple(need(self, lane, "ROLE_FILES")), ROLE_NAMES)
        self.assertEqual(Path(need(self, lane, "ROLES_SOURCE")), ROLES_SOURCE_DIR)
        self.assertEqual(need(self, lane, "role_source_problems")(), {name: [] for name in ROLE_NAMES})
        # the helpers are the shared module's, not copies
        for helper in ("agents_toml_count", "role_table_count", "doctor_role_state", "path_kind"):
            with self.subTest(helper=helper):
                self.assertIs(getattr(lane, helper, None), getattr(codex_roles, helper))

    # --- m: the doctor parser, on fixture pairs
    def test_m_doctor_role_state_on_the_fixture_pairs(self):
        state = need(self, lane, "doctor_role_state")
        home = "/home/example/.codex"
        clean = doctor_output("clean", False, home)
        failed = doctor_output("load_fail", True, home)  # config.load status fail

        def result(kind, before, after, roles=0, redacted=0, load_failed=False):
            return {"state": kind, "startup_warnings_before": before, "startup_warnings_after": after,
                    "role_warnings": roles, "redacted": redacted, "load_failed": load_failed}

        cases = (
            ("clean, clean", clean, doctor_output("clean", True, home), result("ok", 0, 0)),
            ("string", clean, doctor_output("role_string", True, home), result("problem", 0, 1, roles=1)),
            ("list", clean, doctor_output("role_list", True, home), result("problem", 0, 2, roles=2)),
            ("redacted", clean, doctor_output("redacted_rise", True, home), result("problem", 0, 1, redacted=1)),
            ("no config.load", doctor_output("no_config_load", False, home), doctor_output("no_config_load", True, home),
             result("unknown", None, None)),
            ("not JSON", doctor_output("not_json", False, home), doctor_output("not_json", True, home),
             result("unknown", None, None)),
            ("timeout before", None, doctor_output("clean", True, home), result("unknown", None, 0)),
            ("timeout after", clean, None, result("unknown", 0, None)),
            ("pre-existing", doctor_output("preexisting", False, home), doctor_output("preexisting", True, home),
             result("ok", 1, 1)),
            ("rise counted", doctor_output("role_string", True, home), doctor_output("role_list", True, home),
             result("problem", 1, 2, roles=1)),
            ("load fails with the roles", clean, failed, result("problem", 0, None, load_failed=True)),
            ("load fails without them", failed, failed, result("unknown", None, None)),
            ("warnings fall", doctor_output("role_list", True, home), clean, result("ok", 2, 0)),
        )
        for label, before, after, expected in cases:
            with self.subTest(case=label):
                self.assertEqual(state(before, after), expected)

    def test_the_doctor_report_never_reaches_the_output(self):
        # The real warning embeds the role file's absolute path; only counts may be printed.
        self.host.set_doctor("role_string")
        code, out = self.host.run()
        self.assertEqual(code, 3, out)
        self.assertNotIn(DOCTOR_CANARY, out)
        self.assertNotIn("canary", out)
        self.assertNotIn("developer_instructions", out)
        for line in out.splitlines():
            if "doctor" in line or "agent role" in line or "agents" in line:
                self.assertNotIn(str(self.host.tmp), line, line)

    # --- what the plan counts
    def test_role_tables_and_system_roles_are_counts_only_warnings(self):
        config = self.host.config
        config["agents"] = {"enabled": True, "max_concurrent_threads_per_session": 4,
                            "one": {"description": "first"}, "two": {"description": "second"}}
        self.host.write_config(config)
        (self.system / "agents").mkdir()
        (self.system / "agents" / "system-role-name.toml").write_text('name = "s"\n')
        (self.system / "config.toml").write_text('[agents.declared]\ndescription = "x"\n')
        code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertIn("[warn] agent role tables: 2", out)  # the scalar keys under [agents] are not roles
        self.assertIn("[warn] system agent roles: 2", out)
        self.assertNotIn("system-role-name", out)

    def test_a_role_table_in_the_live_profile_is_counted(self):
        (self.host.codex_home / "stack-worker.config.toml").write_text(
            (TEMPLATES / "codex.stack-worker.config.toml").read_text() + '\n[agents.extra]\ndescription = "x"\n')
        code, out = self.host.run()
        self.assertEqual(code, 2, out)  # a profile that differs from the template is refused anyway
        self.assertIn("[warn] agent role tables: 1", out)

    def test_agents_toml_count_counts_recursively_and_is_unknown_behind_a_folder_link(self):
        # Codex follows links below agents/: LocalFileSystem::read_directory takes a link's target's type
        # (openai/codex rust-v0.157.1 codex-rs/exec-server/src/local_file_system.rs:710-735), so discovery.rs enters a linked
        # folder, collects a link to a regular file by the link's own name and skips a dangling link. Checked against codex-cli
        # 0.157.1 by CodexIntegrationTests.test_codex_follows_links_below_agents_and_the_role_count_never_undercounts_it. A
        # count that skipped the linked folder would report fewer role files than Codex loads, so it is unknown (None) there.
        count = need(self, lane, "agents_toml_count")
        root = self.host.tmp / "counted"
        self.assertEqual(count(root), 0)  # absent
        (root / "deep" / "er").mkdir(parents=True)
        for name in ("a.toml", "deep/er/b.toml", "A.TOML", ".toml", "c.toml.bak", "deep/d.txt"):
            (root / name).write_text("")
        elsewhere = self.host.tmp / "linked"
        elsewhere.mkdir()
        (elsewhere / "z.toml").write_text("")
        (root / "link.toml").symlink_to(elsewhere / "z.toml")  # a link to a file, named *.toml: counted, never read
        (root / "dangling.toml").symlink_to(elsewhere / "absent.toml")  # Codex skips it; counting it errs on the safe side
        (root / "renamed.txt").symlink_to(elsewhere / "z.toml")  # the link's own name has no .toml extension
        self.assertEqual(count(root), 4)
        for where in (root, root / "deep", root / "deep" / "er"):  # a link to a folder, at any depth
            with self.subTest(link_in=where.name):
                (where / "linked-dir").symlink_to(elsewhere)
                self.assertIsNone(count(root), "a folder link below the root was skipped: the count undercounts")
                (where / "linked-dir").unlink()
                self.assertEqual(count(root), 4)
        (root / "dir.toml").symlink_to(elsewhere)  # a link named *.toml to a folder is a folder link
        self.assertIsNone(count(root), "a folder link named *.toml was skipped")
        (root / "dir.toml").unlink()
        (root / "linked-top").symlink_to(elsewhere)
        self.assertIsNone(count(root / "linked-top"))  # the top folder itself is a link: not a directory it may read
        (root / "linked-top").unlink()
        self.assertIsNone(count(root / "a.toml"))
        if os.geteuid() != 0:
            (root / "deep").chmod(0)
            self.addCleanup((root / "deep").chmod, 0o700)
            self.assertIsNone(count(root))  # unreadable

    def test_role_table_count_ignores_the_scalar_keys(self):
        table_count = need(self, lane, "role_table_count")
        self.assertEqual(table_count({}), 0)
        self.assertEqual(table_count({"agents": {"enabled": True, "max_depth": 2}}), 0)
        self.assertEqual(table_count({"agents": {"enabled": True, "a": {}, "b": {"description": "x"}}}), 2)
        self.assertEqual(table_count({"agents": "not a table"}), 0)

    # --- journal, rollback
    def test_an_interrupted_role_write_is_journaled_and_rolled_back(self):
        real = lane.atomic_write

        def fail_on_the_second(path, data, mode, expect_sha, create_only=False):
            if path.name == ROLE_NAMES[1]:
                raise lane.Failed("synthetic write failure")
            return real(path, data, mode, expect_sha, create_only)

        with mock.patch.object(lane, "atomic_write", fail_on_the_second):
            code, out = self.host.apply()
        self.assertEqual(code, 3, out)
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertIn("agent_roles", record)
        first, second = (record["agent_roles"]["files"][name] for name in ROLE_NAMES)
        self.assertIs(first["created"], True)
        self.assertIs(second["creating"], True)  # journaled before the write
        self.assertIsNot(second.get("created"), True)
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertFalse(self.agents.exists())

    def test_rollback_trusts_a_creation_that_was_only_journaled(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertIn("agent_roles", record)
        roles = record["agent_roles"]
        roles.update(created_dir=False, creating_dir=True)
        for entry in roles["files"].values():
            entry.update(created=False, creating=True)  # the run stopped between the link and its note
        (run / "record.json").write_text(json.dumps(record))
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertFalse(self.agents.exists())

    def test_an_existing_agents_directory_and_identical_roles_are_not_the_runs_to_remove(self):
        self.agents.mkdir(mode=0o750)
        for name in ROLE_NAMES:
            (self.agents / name).write_bytes(self.sources[name])
            (self.agents / name).chmod(0o600)
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertIn("[ok] extra agent role files: 0", out)  # the two carriers themselves are not extras
        for name in ROLE_NAMES:
            self.assertIn(f"agents/{name}: in place", out.splitlines())
        self.assertEqual(self.agents.stat().st_mode & 0o777, 0o750)  # not ours to change
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertIn("agent_roles", record)
        self.assertIs(record["agent_roles"]["created_dir"], False)
        self.assertEqual([record["agent_roles"]["files"][n]["created"] for n in ROLE_NAMES], [False, False])
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertIn(f"agents/{ROLE_NAMES[0]}: not created by this run", out.splitlines())
        for name in ROLE_NAMES:
            self.assertEqual(self.installed(name), self.sources[name])

    def test_rollback_keeps_an_agents_directory_that_existed_before_the_run(self):
        # The folder is the run's to remove only when the run made it: here it was there, empty, and the run only
        # filled it, so after the rollback it is empty again and still there.
        self.agents.mkdir(mode=0o750)
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        for name in ROLE_NAMES:
            self.assertEqual(self.installed(name), self.sources[name])
        code, out = self.host.run("--rollback", str(self.host.latest_run()))
        self.assertEqual(code, 0, out)
        for name in ROLE_NAMES:
            self.assertFalse((self.agents / name).exists())
        self.assertTrue(self.agents.is_dir(), "a folder this run did not make was removed")
        self.assertEqual(self.agents.stat().st_mode & 0o777, 0o750)
        self.assertIn("agents directory: not created by this run", out.splitlines())

    def test_rollback_leaves_an_agents_directory_that_gained_other_files(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.agents.is_dir(), "the agents directory was not created")
        (self.agents / "somebody-elses.txt").write_text("keep\n")
        code, out = self.host.run("--rollback", str(self.host.latest_run()))
        self.assertEqual(code, 0, out)
        self.assertFalse((self.agents / ROLE_NAMES[0]).exists())
        self.assertEqual((self.agents / "somebody-elses.txt").read_text(), "keep\n")
        self.assertIn("agents directory: left in place (not empty)", out.splitlines())

    def test_a_record_without_agent_roles_leaves_the_role_files_alone(self):
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        record.pop("agent_roles", None)  # what a run of an older tool recorded
        (run / "record.json").write_text(json.dumps(record))
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertNotIn("agents/", out)
        for name in ROLE_NAMES:
            self.assertEqual(self.installed(name), self.sources[name])

    def test_a_role_file_that_appears_after_the_plan_is_left_alone(self):
        # The write is create-only (os.link refuses an existing name), so a file made between the plan and the write
        # is never replaced. Simulated by a plan that still says create for a file that exists.
        self.agents.mkdir(mode=0o700)
        (self.agents / ROLE_NAMES[0]).write_text("someone else's\n")
        with mock.patch.object(lane.Plan, "role_states", lambda self: {name: "create" for name in ROLE_NAMES}):
            code, out = self.host.apply()
        self.assertEqual(code, 3, out)
        self.assertIn(f"agents/{ROLE_NAMES[0]} appeared since it was read; left as it is", out)
        self.assertEqual((self.agents / ROLE_NAMES[0]).read_text(), "someone else's\n")
        self.assertFalse((self.agents / ROLE_NAMES[1]).exists())
        run = self.host.latest_run()
        record = json.loads((run / "record.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertIs(record["agent_roles"]["files"][ROLE_NAMES[0]]["creating"], False)  # it is not ours
        code, out = self.host.run("--rollback", str(run))
        self.assertEqual(code, 0, out)
        self.assertEqual((self.agents / ROLE_NAMES[0]).read_text(), "someone else's\n")
        self.assertTrue(self.agents.is_dir())  # the folder was there before the run

    # --- controls (design 4.5): each load-bearing check, disabled, lets the case it guards through
    def test_control_the_role_precondition_is_what_refuses_a_differing_role(self):
        need(self, lane.Plan, "role_preconditions")
        self.agents.mkdir(mode=0o700)
        (self.agents / ROLE_NAMES[0]).write_text("differs\n")
        with mock.patch.object(lane.Plan, "role_preconditions", lambda self: []):
            code, out = self.host.apply()
        self.assertNotEqual(code, 2, out)  # without it nothing refuses before the writes
        self.assertEqual((self.agents / ROLE_NAMES[0]).read_text(), "differs\n")  # the state check still spares it

    def test_control_the_doctor_verdict_is_what_fails_the_rehearsal(self):
        need(self, lane, "doctor_role_state")
        self.host.set_doctor("role_string")
        with mock.patch.object(lane, "doctor_role_state", return_value={
                "state": "ok", "startup_warnings_before": 0, "startup_warnings_after": 1, "role_warnings": 1,
                "redacted": 0, "load_failed": False}):
            code, out = self.host.run()
        self.assertEqual(code, 0, out)
        self.assertNotIn("PROBLEM", out)

    def test_control_the_short_circuit_needs_its_role_term(self):
        need(self, lane.Plan, "role_states")
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.agents.is_dir(), "the agents directory was not created")
        shutil.rmtree(self.agents)
        with mock.patch.object(lane.Plan, "role_states", lambda self: {name: "same" for name in ROLE_NAMES}):
            code, out = self.host.apply()
        self.assertIn("already in place: nothing to do", out)  # what test c refuses to see with the real term
        self.assertFalse(self.agents.exists())


def fixture_events(name: str) -> list[dict]:
    """A run's `codex exec --json` events, one JSON array per run (`*.jsonl` is git-ignored here)."""
    return json.loads((FIXTURES / name).read_text())


class ProveVerdictTests(unittest.TestCase):
    """Real codex-cli 0.157.1 event shapes, plus explicitly synthetic adversarial cases."""

    def test_pwd_verdict_on_a_bound_and_an_unbound_worker(self):
        bound = {"events": fixture_events("pwd-bound.events.json"), "exit": 0, "timed_out": False}
        ok, detail = prove.pwd_verdict(bound, "/scratch/npm-live/wP1", "/scratch/npm-live/wP2")
        self.assertTrue(ok, detail)
        ok, _ = prove.pwd_verdict(bound, "/scratch/npm-live/wP2", "/scratch/npm-live/wP1")
        self.assertFalse(ok)
        # The bare-CLI control of the same run: the server followed another session's log (ADVERSARY).
        unbound = {"events": fixture_events("pwd-adversary.events.json"), "exit": 0, "timed_out": False}
        ok, detail = prove.pwd_verdict(unbound, "/scratch/npm-live/wC1", "/scratch/npm-live/wP1")
        self.assertFalse(ok)
        self.assertIn("ADVERSARY", detail)

    def test_pwd_verdict_rejects_synthetic_directory_spoofs(self):
        # Synthetic completed items: the claimed output is right, but the arguments do not
        # query the inherited working directory. Keep the real captured fixtures unchanged.
        own, other = "/scratch/worker-a", "/scratch/worker-b"
        for language, code in (("shell", f"echo {own}"),
                               ("shell", f"echo {own} # pwd"),
                               ("shell", f"cd {own}; pwd"),
                               ("javascript", f"console.log('{own}')"),
                               ("javascript", f"console.log('{own}') // process.cwd()")):
            with self.subTest(language=language, code=code):
                item = {"type": "mcp_tool_call", "server": "context-mode", "tool": "ctx_execute",
                        "arguments": {"language": language, "code": code}, "status": "completed",
                        "result": {"content": [{"type": "text", "text": own + "\n"}]}}
                run = {"events": [{"type": "item.completed", "item": item}], "exit": 0, "timed_out": False}
                ok, detail = prove.pwd_verdict(run, own, other)
                self.assertFalse(ok, detail)

    def test_pwd_verdict_accepts_synthetic_direct_directory_queries(self):
        # Synthetic positive controls for the explicit query forms; the shell pwd fixture
        # above remains the evidence for a real captured invocation.
        own, other = "/scratch/worker-a", "/scratch/worker-b"
        for language, code in (("shell", "pwd"), ("shell", "rtk pwd"), ("shell", "rtk proxy pwd"),
                               ("javascript", "console.log(process.cwd());")):
            with self.subTest(language=language, code=code):
                item = {"type": "mcp_tool_call", "server": "context-mode", "tool": "ctx_execute",
                        "arguments": {"language": language, "code": code}, "status": "completed",
                        "result": {"content": [{"type": "text", "text": own + "\n"}]}}
                run = {"events": [{"type": "item.completed", "item": item}], "exit": 0, "timed_out": False}
                ok, detail = prove.pwd_verdict(run, own, other)
                self.assertTrue(ok, detail)

    def test_pwd_verdict_rejects_an_explicit_cwd_override(self):
        own, other = "/scratch/worker-a", "/scratch/worker-b"
        # Even an apparently correct directory masks what the server actually inherited.
        for cwd in (own, other, "", None):
            with self.subTest(cwd=cwd):
                item = {"type": "mcp_tool_call", "server": "context-mode", "tool": "ctx_execute",
                        "arguments": {"language": "shell", "code": "pwd", "cwd": cwd}, "status": "completed",
                        "result": {"content": [{"type": "text", "text": own + "\n"}]}}
                run = {"events": [{"type": "item.completed", "item": item}], "exit": 0, "timed_out": False}
                ok, detail = prove.pwd_verdict(run, own, other)
                self.assertFalse(ok, detail)

    def test_approval_verdicts(self):
        items = json.loads((FIXTURES / "approval-items.json").read_text())

        def run(item):
            return {"events": [{"type": "item.completed", "item": item}], "exit": 0, "timed_out": False}

        self.assertTrue(prove.approval_verdict(run(items["approved"]), expect_refusal=False)[0])
        self.assertFalse(prove.approval_verdict(run(items["refused"]), expect_refusal=False)[0])
        self.assertTrue(prove.approval_verdict(run(items["refused"]), expect_refusal=True)[0])
        self.assertFalse(prove.approval_verdict(run(items["approved"]), expect_refusal=True)[0])
        self.assertFalse(prove.approval_verdict({"events": [], "exit": 1, "timed_out": False}, False)[0])

    def test_rtk_verdict(self):
        fixture = json.loads((FIXTURES / "rtk-worker-items.json").read_text())
        blob = prove.big_blob()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), fixture["blob_sha256"])  # same fixture text as the run

        def run(items):
            return {"events": [{"type": "item.completed", "item": item} for item in items], "exit": 0,
                    "timed_out": False}

        status, show = fixture["items"]
        # The run's own output bytes are not retained; they are the blob, which the run measured byte-exact.
        show = {**show, "aggregated_output": blob.decode()}
        self.assertTrue(prove.rtk_verdict(run([status, show]), blob)[0])
        for command in ("/bin/bash -lc 'rtk git show HEAD:big.txt'", "/bin/bash -lc 'cd x && rtk git show HEAD:big.txt'"):
            self.assertFalse(prove.rtk_verdict(run([status, {**show, "command": command}]), blob)[0], command)
        self.assertTrue(prove.rtk_verdict(run([status, {**show, "command": "/bin/bash -lc 'git show HEAD:big.txt'"}]),
                                          blob)[0])
        self.assertFalse(prove.rtk_verdict(run([{**status, "command": "/bin/bash -lc 'git status --short'"}, show]),
                                           blob)[0])
        self.assertFalse(prove.rtk_verdict(run([status, {**show, "aggregated_output": blob.decode()[:8192]}]), blob)[0])
        crlf = {**show, "aggregated_output": blob.decode().replace("\n", "\r\n")}
        self.assertTrue(prove.rtk_verdict(run([status, crlf]), blob)[0])

    def test_every_worker_pins_model_effort_and_web_search(self):
        # A project .codex/config.toml outranks the profile file and `-c` outranks both (config_layer_source.rs at
        # rust-v0.157.1), so the launch itself carries the profile's model, effort and web search.
        pins = lane.worker_pins()
        self.assertEqual(pins, ["-m", "gpt-6.1-sol", "-c", 'model_reasoning_effort="max"', "-c", 'web_search="live"'])
        for profile in (True, False):
            argv = prove.exec_argv("codex", "prompt", profile)
            self.assertEqual(argv[:2], ["codex", "exec"])
            self.assertEqual("-p" in argv, profile)
            joined = " ".join(argv)
            self.assertIn(" ".join(pins), joined)
            self.assertIn("-s read-only", joined)
        self.assertEqual(lane.worker_command(), "codex exec -p stack-worker -m gpt-6.1-sol "
                         "-c 'model_reasoning_effort=\"max\"' -c 'web_search=\"live\"' -s <sandbox> ... < /dev/null")
        recipe = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8")
        self.assertIn('codex exec -p stack-worker -m gpt-6.1-sol -c model_reasoning_effort="max" -c web_search="live"',
                      recipe)

    def test_prove_json_declares_local_integration_and_retention_limits(self):
        # Exercise main -> live_checks -> JSON without a model call or real Codex home.
        # Synthetic worker failures also verify that cleanup failures survive summarization.
        def worker_runs(specs, timeout):
            return [{"name": spec["name"], "exit": None, "timed_out": True, "seconds": 1,
                     "cleanup_error": "TimeoutExpired: synthetic cleanup failure",
                     "events": [{"type": "turn.completed", "usage": {"input_tokens": 7}}]}
                    for spec in specs]

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            skill_path = Path(tmp) / "SKILL.md"
            skill_path.write_text("# Synthetic installed skill\n", encoding="utf-8")
            with mock.patch.object(prove, "make_repo", return_value=b"synthetic blob"), \
                 mock.patch.object(prove, "static_checks"), \
                 mock.patch.object(prove, "quota_gate", return_value=(True, "synthetic open gate")), \
                 mock.patch.object(prove, "run_workers", side_effect=worker_runs), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = prove.main(["--codex", "/synthetic/codex", "--codex-home", tmp,
                                   "--live", "--skill-file", str(skill_path), "--json", str(report_path)])
            self.assertEqual(code, 1)
            report = json.loads(report_path.read_text())
        self.assertEqual(report.get("evidence_class"), "local integration check")
        self.assertIs(report["host_acceptance"], False)
        for requirement in ("official pinned installation", "upstream commands", "arguments",
                            "returned output", "exit statuses", "declared sanitization"):
            self.assertIn(requirement, report["acceptance_requirements"])
        for omitted in ("native_events", "invocation_arguments", "returned_output"):
            self.assertIs(report["retention"][omitted], False)
        self.assertIs(report["retention"]["worker_exits"], True)
        self.assertIn("not sanitized", report["sanitization"])
        self.assertEqual(len(report["live_runs"]), 6)
        for run in report["live_runs"]:
            self.assertIn("TimeoutExpired", run["cleanup_error"])
            self.assertEqual(run["usage"], {"input_tokens": 7})
            self.assertNotIn("events", run)

    def test_prove_json_names_no_codex_home_path_beside_its_rows(self):
        # corrections item 5 (recheck L4): the JSON keeps its rows but no longer says where the Codex home is. A
        # boolean says whether the home was the default one, and a hash-labelled identifier lets two reports of one
        # home be compared without publishing the path. Scanned outside the rows, which keep their own privacy note.
        def worker_runs(specs, timeout):
            return [{"name": spec["name"], "exit": 0, "timed_out": False, "seconds": 1, "cleanup_error": None,
                     "events": [{"type": "turn.completed", "usage": {"input_tokens": 7}}]} for spec in specs]

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, item in value.items():
                    yield key
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)

        def absolute_paths(value):
            """Whitespace-separated tokens that start with a slash and name something (a linear scan)."""
            return [token for text in strings(value) for token in text.split()
                    if token.startswith("/") and len(token) > 1]

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            skill_path = Path(tmp) / "SKILL.md"
            skill_path.write_text("# Synthetic installed skill\n", encoding="utf-8")
            with mock.patch.object(prove, "make_repo", return_value=b"synthetic blob"), \
                 mock.patch.object(prove, "static_checks"), \
                 mock.patch.object(prove, "quota_gate", return_value=(True, "synthetic open gate")), \
                 mock.patch.object(prove, "run_workers", side_effect=worker_runs), \
                 contextlib.redirect_stdout(io.StringIO()):
                prove.main(["--codex", "/synthetic/codex", "--codex-home", tmp, "--live", "--skill-file",
                            str(skill_path), "--json", str(report_path)])
                default_path = Path(tmp) / "default.json"
                with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}):
                    prove.main(["--codex", "/synthetic/codex", "--json", str(default_path)])
            report = json.loads(report_path.read_text())
            default = json.loads(default_path.read_text())
            planted = dict(report, elsewhere={"note": f"see {tmp}"})
        self.assertNotIn("codex_home", report)
        self.assertIs(report.get("codex_home_is_default"), False)  # a scratch home is not ~/.codex
        self.assertIs(default.get("codex_home_is_default"), False)  # nor is a non-default $CODEX_HOME
        self.assertNotIn("codex_home_id", report)  # no identifier of the home: an unsalted digest confirms a guessed user name
        self.assertNotIn("codex_home_id", default)
        self.assertNotIn(tmp, json.dumps({key: value for key, value in report.items() if key != "checks"}))
        self.assertEqual(absolute_paths({key: value for key, value in report.items() if key != "checks"}), [])
        self.assertEqual(absolute_paths({key: value for key, value in planted.items() if key != "checks"}), [tmp])  # control
        self.assertIn("checks", report)  # the rows are kept

    def test_rtk_verdict_rejects_a_synthetic_failed_status_command(self):
        # Synthetic fault injected into the captured item shape; no command is executed here.
        fixture = json.loads((FIXTURES / "rtk-worker-items.json").read_text())
        status, show = fixture["items"]
        blob = prove.big_blob()
        show = {**show, "aggregated_output": blob.decode()}
        failed = {**status, "exit_code": 1}
        # A successful unprefixed command cannot rescue a failed prefixed command.
        raw_success = {**status, "command": "git status --short", "exit_code": 0}
        for statuses in ([failed], [failed, raw_success]):
            with self.subTest(status_commands=len(statuses)):
                run = {"events": [{"type": "item.completed", "item": item} for item in [*statuses, show]],
                       "exit": 0, "timed_out": False}
                ok, detail = prove.rtk_verdict(run, blob)
                self.assertFalse(ok, detail)

    def test_rtk_verdict_rejects_command_mentions_in_comments_or_quoted_data(self):
        blob = prove.big_blob()
        # Isolate each false positive as well as the reviewer's combined example. The
        # output bytes are intentionally right, so only the executed argv can reject it.
        cases = [("echo 'rtk git status'", "git show HEAD:big.txt"),
                 ("true # rtk git status --short", "git show HEAD:big.txt"),
                 ("rtk git status --short", "cat big.txt # HEAD:big.txt"),
                 ("rtk git status --short", "echo 'git show HEAD:big.txt'"),
                 ("echo 'rtk git status'", "cat big.txt # HEAD:big.txt"),
                 ("echo 'rtk git status'", "cat big.txt # git show HEAD:big.txt"),
                 ("printf '%s' 'rtk git status --short'", "git show HEAD:big.txt")]
        for status_command, show_command in cases:
            for wrapped in (False, True):
                with self.subTest(status=status_command, show=show_command, wrapped=wrapped):
                    if wrapped:
                        import shlex
                        status_command, show_command = ("/bin/bash -lc " + shlex.quote(command)
                                                        for command in (status_command, show_command))
                    items = [{"type": "command_execution", "command": status_command, "exit_code": 0},
                             {"type": "command_execution", "command": show_command, "exit_code": 0,
                              "aggregated_output": blob.decode()}]
                    run = {"events": [{"type": "item.completed", "item": item} for item in items],
                           "exit": 0, "timed_out": False}
                    ok, detail = prove.rtk_verdict(run, blob)
                    self.assertFalse(ok, detail)

    def test_verdicts_reject_synthetic_failed_or_timed_out_workers(self):
        # Synthetic run lifetimes around otherwise-valid captured completed items. The
        # successful controls prove that worker completion alone changes these verdicts.
        approvals = json.loads((FIXTURES / "approval-items.json").read_text())
        rtk_items = json.loads((FIXTURES / "rtk-worker-items.json").read_text())["items"]
        blob = prove.big_blob()
        rtk_items[-1] = {**rtk_items[-1], "aggregated_output": blob.decode()}
        cases = (("pwd", prove.pwd_verdict, fixture_events("pwd-bound.events.json"),
                  ("/scratch/npm-live/wP1", "/scratch/npm-live/wP2")),
                 ("approved", prove.approval_verdict,
                  [{"type": "item.completed", "item": approvals["approved"]}], (False,)),
                 ("refused", prove.approval_verdict,
                  [{"type": "item.completed", "item": approvals["refused"]}], (True,)),
                 ("rtk", prove.rtk_verdict,
                  [{"type": "item.completed", "item": item} for item in rtk_items], (blob,)))
        for name, verdict, events, args in cases:
            valid = {"events": events, "exit": 0, "timed_out": False}
            self.assertTrue(verdict(valid, *args)[0], name)
            for exit_code, timed_out in ((0, True), (7, False), (None, False), (-signal.SIGTERM, False)):
                with self.subTest(verdict=name, exit=exit_code, timed_out=timed_out):
                    run = {**valid, "exit": exit_code, "timed_out": timed_out}
                    ok, detail = verdict(run, *args)
                    self.assertFalse(ok, detail)

    def test_grep_count_counts_lines(self):
        self.assertEqual(prove.grep_count("a x\nb\nx x\n", "x"), 2)

    def test_run_workers_kills_a_worker_past_the_deadline(self):
        started = __import__("time").monotonic()
        runs = prove.run_workers([{"name": "slow", "argv": ["sh", "-c", "sleep 30; echo late"], "cwd": "/",
                                   "env": dict(os.environ)},
                                  {"name": "quick", "argv": ["sh", "-c", 'echo \'{"type": "turn.completed"}\''],
                                   "cwd": "/", "env": dict(os.environ)}], timeout=1.0)
        self.assertLess(__import__("time").monotonic() - started, 15)
        self.assertTrue(runs[0]["timed_out"])
        self.assertEqual(runs[1]["events"], [{"type": "turn.completed"}])

    def test_run_workers_cleans_started_groups_and_handles_on_launch_failure_or_cancellation(self):
        # Real OS workers and handles, with deterministic faults at the launch/wait boundary.
        # The test's finally also reaps the children on the red run.
        real_popen, real_file = subprocess.Popen, tempfile.TemporaryFile
        for fault in ("launch-error", "launch-cancel", "wait-cancel", "handle-error"):
            with self.subTest(fault=fault):
                processes, handles = [], []

                def open_handle():
                    if fault == "handle-error" and len(handles) == 5:
                        raise OSError("synthetic handle failure")
                    handle = real_file()
                    handles.append(handle)
                    return handle

                def launch(*args, **kwargs):
                    if len(processes) == 2 and fault.startswith("launch-"):
                        if fault == "launch-cancel":
                            raise KeyboardInterrupt("synthetic cancellation")
                        raise OSError("synthetic launch failure")
                    proc = real_popen(*args, **kwargs)
                    processes.append(proc)
                    if fault == "wait-cancel" and len(processes) == 1:
                        proc.wait = mock.Mock(side_effect=[KeyboardInterrupt("synthetic cancellation"),
                                                          mock.DEFAULT], wraps=proc.wait)
                    return proc

                specs = [{"name": str(i), "argv": [sys.executable, "-c", "import time; time.sleep(60)"],
                          "cwd": "/", "env": dict(os.environ)} for i in range(3)]
                try:
                    with mock.patch.object(prove.tempfile, "TemporaryFile", side_effect=open_handle), \
                         mock.patch.object(prove.subprocess, "Popen", side_effect=launch):
                        with self.assertRaises(KeyboardInterrupt if "cancel" in fault else OSError):
                            prove.run_workers(specs, timeout=1.0)
                    self.assertTrue(all(proc.returncode is not None for proc in processes),
                                    "started workers were not terminated and reaped")
                    self.assertTrue(all(not prove.group_alive(proc.pid) for proc in processes),
                                    "a started process group survived cleanup")
                    self.assertTrue(all(handle.closed for handle in handles), "worker handles leaked")
                finally:
                    for proc in processes:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(proc.pid, signal.SIGKILL)
                        # Bypass the injected cancellation when cleaning up the red test.
                        subprocess.Popen.wait.__get__(proc)(timeout=5)
                    for handle in handles:
                        handle.close()

    def test_run_workers_collects_partial_results_after_final_wait_timeout(self):
        # Synthetic process boundary: SIGKILL has been sent but reaping still times out.
        # No signals reach real processes; later workers must still be cleaned and collected.
        handles = []
        processes = [mock.Mock(pid=101, returncode=None), mock.Mock(pid=102, returncode=None)]
        for proc in processes:
            proc.poll.side_effect = lambda proc=proc: proc.returncode
            proc.wait.side_effect = subprocess.TimeoutExpired(["synthetic-worker"], 5)

        def launch(*args, **kwargs):
            index = len(handles) // 2
            handles.extend([kwargs["stdout"], kwargs["stderr"]])
            kwargs["stdout"].write(json.dumps({"type": "partial", "worker": index}).encode() + b"\n")
            kwargs["stderr"].write(f"stderr {index}".encode())
            return processes[index]

        def signal_group(pid, sig):
            if pid == 102:
                processes[1].returncode = -sig

        specs = [{"name": str(i), "argv": ["synthetic-worker"], "cwd": "/", "env": {}} for i in range(2)]
        with mock.patch.object(prove.subprocess, "Popen", side_effect=launch), \
             mock.patch.object(prove.os, "killpg", side_effect=signal_group) as killpg, \
             mock.patch.object(prove, "group_alive", return_value=False), \
             mock.patch.object(prove.time, "monotonic", side_effect=itertools.count(0, 6)):
            runs = prove.run_workers(specs, timeout=1)
        self.assertEqual(len(runs), 2)
        self.assertIn("TimeoutExpired", runs[0]["cleanup_error"])
        self.assertIsNone(runs[0]["exit"])
        self.assertIsNone(runs[1]["cleanup_error"])
        self.assertEqual(runs[1]["exit"], -signal.SIGTERM)
        self.assertEqual(killpg.call_args_list, [mock.call(101, signal.SIGTERM), mock.call(101, signal.SIGKILL),
                                               mock.call(102, signal.SIGTERM)])
        for i, run in enumerate(runs):
            self.assertTrue(run["timed_out"])
            self.assertEqual(run["events"], [{"type": "partial", "worker": i}])
            self.assertEqual(run["stderr_tail"], f"stderr {i}")
        self.assertTrue(all(handle.closed for handle in handles))

    @unittest.skipUnless(hasattr(os, "fork") and hasattr(os, "killpg"), "requires POSIX process groups")
    def test_run_workers_kills_descendants_after_the_leader_exits(self):
        # Synthetic workers, real OS processes. Mirror the stubborn-child observation in
        # tests/test_codex_quota.py: a zombie has exited and cannot continue doing work.
        worker = '''
import json, os, signal, sys, time
from pathlib import Path
reader, writer = os.pipe()
child = os.fork()
if child == 0:
    os.close(reader)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(writer, b"ready")
    os.close(writer)
    time.sleep(60)
    os._exit(0)
os.close(writer)
os.read(reader, 5)
os.close(reader)
Path(sys.argv[1]).write_text(json.dumps({"child": child, "group": os.getpgrp()}))
if sys.argv[2] == "already-exited":
    sys.exit(0)
while True:
    signal.pause()
'''
        for mode in ("exits-on-term", "already-exited"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                pids = Path(tmp) / "pids.json"
                try:
                    runs = prove.run_workers([{"name": mode, "argv": [sys.executable, "-c", worker, str(pids), mode],
                                               "cwd": tmp, "env": dict(os.environ)}], timeout=1.0)
                    self.assertEqual(runs[0]["timed_out"], mode == "exits-on-term")
                    self.assertEqual(runs[0]["exit"], -signal.SIGTERM if mode == "exits-on-term" else 0)
                    child = json.loads(pids.read_text())["child"]
                    state = subprocess.run(["ps", "-o", "stat=", "-p", str(child)], capture_output=True,
                                           text=True, check=False).stdout.strip()
                    self.assertTrue(not state or state.startswith("Z"), "a child ignoring SIGTERM survived cleanup")
                finally:
                    # The red run must also leave no running descendants behind.
                    if pids.exists():
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(json.loads(pids.read_text())["group"], signal.SIGKILL)


class RolesRowTests(unittest.TestCase):
    """prove_codex_lane's static `roles` row (design 4.3 case o): the installed carriers against their pinned rows,
    the *.toml files under agents, the role tables of the live config and profile, and the system layer. Counts
    and booleans only; no model call. Live role checks are deliberately not part of this tool: its --live workers
    run with --ephemeral, which persists no rollout, and at rust-v0.157.1 with multi-agent V2 the exec JSONL stream
    carries no item for a spawn_agent call (a successful one emits a SubAgentActivity item that exec's mapping
    drops, a failed one none, and wait_agent's item has empty receiver_thread_ids), so a live check here could not
    tell a found role from an unknown one."""

    ROW = "installed {equal}/2 equal to SHA256SUMS; *.toml under agents {count}; role tables {tables}; system roles {system}"

    def setUp(self):
        self.host = FakeHost(self)
        self.system = self.host.tmp / "etc-codex"
        self.system.mkdir()
        self.agents = self.host.codex_home / "agents"

    def install_roles(self) -> None:
        self.agents.mkdir(mode=0o700, exist_ok=True)
        for name in ROLE_NAMES:
            (self.agents / name).write_bytes((ROLES_SOURCE_DIR / name).read_bytes())
            (self.agents / name).chmod(0o600)

    def row(self) -> tuple[bool, str]:
        return need(self, prove, "roles_row")(self.host.codex_home, self.system)

    def expected(self, equal=2, count=2, tables=0, system=0) -> str:
        return self.ROW.format(equal=equal, count=count, tables=tables, system=system)

    def test_two_matching_roles_and_nothing_else_pass(self):
        self.install_roles()
        self.assertEqual(self.row(), (True, self.expected()))

    def test_each_departure_fails_with_its_own_count(self):
        need(self, prove, "roles_row")
        self.install_roles()
        (self.agents / "extra.toml").write_text('name = "extra"\n')
        self.assertEqual(self.row(), (False, self.expected(count=3)))
        (self.agents / "extra.toml").unlink()
        (self.agents / ROLE_NAMES[0]).write_bytes(b'name = "stack-researcher"\n')
        self.assertEqual(self.row(), (False, self.expected(equal=1)))
        self.install_roles()
        config = self.host.read_config()
        config["agents"] = {"enabled": True, "stray": {"description": "x"}}
        self.host.write_config(config)
        self.assertEqual(self.row(), (False, self.expected(tables=1)))
        self.host.write_config(self.host.config)
        (self.host.codex_home / "stack-worker.config.toml").write_text('[agents.stray]\ndescription = "x"\n')
        self.assertEqual(self.row(), (False, self.expected(tables=1)))
        (self.host.codex_home / "stack-worker.config.toml").unlink()
        (self.system / "agents").mkdir()
        (self.system / "agents" / "system.toml").write_text('name = "s"\n')
        self.assertEqual(self.row(), (False, self.expected(system=1)))

    def test_absent_roles_and_an_unreadable_config_fail(self):
        self.assertEqual(self.row(), (False, self.expected(equal=0, count=0)))
        self.install_roles()
        (self.host.codex_home / "config.toml").write_text("not = [valid toml\n")
        ok, detail = self.row()
        self.assertFalse(ok)
        self.assertIn("role tables unknown", detail)

    def test_a_folder_link_below_agents_is_unknown_and_never_a_pass(self):
        # Codex enters a linked folder and loads what it finds there as roles (openai/codex rust-v0.157.1
        # exec-server/src/local_file_system.rs:710-735; checked against codex-cli 0.157.1 by the integration test
        # test_codex_follows_links_below_agents_and_the_role_count_never_undercounts_it), so an extra role behind one must
        # not leave the row green: the count is unknown, and unknown is not a pass.
        need(self, prove, "roles_row")
        self.install_roles()
        other = self.host.tmp / "roles-elsewhere"
        other.mkdir()
        (other / "extra.toml").write_text('name = "extra"\n')
        (self.agents / "shared").symlink_to(other)
        ok, detail = self.row()
        self.assertFalse(ok, "the row passed with a role that Codex would load behind a linked folder")
        self.assertEqual(detail, self.expected(count="unknown"))
        self.assertNotIn(str(self.host.tmp), detail)
        (self.agents / "shared").unlink()  # control: without the link the same folder passes again
        self.assertEqual(self.row(), (True, self.expected()))

    def test_the_row_is_part_of_the_static_checks_and_carries_no_paths(self):
        need(self, prove, "roles_row")
        code, out = self.host.apply()
        self.assertEqual(code, 0, out)
        with mock.patch.object(lane, "SYSTEM_CODEX_DIR", self.system, create=True):
            rows = {}
            for planted in (False, True):
                if planted:
                    (self.agents / "extra.toml").write_text('name = "extra"\n')
                results = prove.Results()
                repo = self.host.tmp / f"repo-{planted}"
                blob = prove.make_repo(repo)
                with mock.patch.object(prove.shutil, "which", return_value=None), \
                     contextlib.redirect_stdout(io.StringIO()):
                    prove.static_checks(str(self.host.codex), self.host.codex_home, str(self.host.eco), ROOT, repo,
                                        blob, results)
                rows[planted] = {row["check"]: row for row in results.rows}.get("roles")
        self.assertIsNotNone(rows[False], "static_checks adds no roles row")
        self.assertEqual((rows[False]["ok"], rows[False]["detail"]), (True, self.expected()))
        self.assertEqual((rows[True]["ok"], rows[True]["detail"]), (False, self.expected(count=3)))
        for row in rows.values():
            self.assertNotIn(str(self.host.tmp), row["detail"])


class SandboxProbeControlTests(unittest.TestCase):
    """Synthetic controls for the local probe, not native Codex acceptance.

    Exercise the sibling sandbox test's availability convention and the command
    output contract from rust-v0.157.1 cli/src/debug_sandbox.rs without a provider.
    """

    def test_unavailable_sandbox_skips_after_collecting_all_cases(self):
        test = CodexIntegrationTests("test_worker_profile_sets_chub_opt_outs_in_an_isolated_home")
        unavailable = subprocess.CompletedProcess([], 1, "", "sandbox unavailable (synthetic)")
        with mock.patch.object(CodexIntegrationTests, "isolation", return_value=[]), \
             mock.patch.object(shutil, "which", return_value="/fixture/bin/codex"), \
             mock.patch.object(subprocess, "run", return_value=unavailable) as run:
            with self.assertRaises(unittest.SkipTest):
                test.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home()
        self.assertEqual(run.call_count, 6)
        self.assertTrue(all(call.kwargs["timeout"] == 120 for call in run.call_args_list))

    def test_partial_sandbox_failure_is_not_skipped(self):
        test = CodexIntegrationTests("test_worker_profile_sets_chub_opt_outs_in_an_isolated_home")
        started = subprocess.CompletedProcess([], 0,
            "telemetry=1\nfeedback=1\nbase=kept\nchubdir=unset\nfilter=absent\n", "")
        failed = subprocess.CompletedProcess([], 1, "", "one sandbox failed (synthetic)")
        with mock.patch.object(CodexIntegrationTests, "isolation", return_value=[]), \
             mock.patch.object(shutil, "which", return_value="/fixture/bin/codex"), \
             mock.patch.object(subprocess, "run", side_effect=[started, failed, started, started, started, started]):
            with self.assertRaises(AssertionError):
                test.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home()


@unittest.skipUnless(os.environ.get("NAS_CODEX_INTEGRATION") == "1" and shutil.which("codex"),
                     "set NAS_CODEX_INTEGRATION=1 with codex-cli 0.159.3 on PATH to run the real app-server")
class CodexIntegrationTests(unittest.TestCase):
    """Local integration with the real codex: its app-server writes a scratch Codex home and rollback restores it
    byte for byte; a project config outranks the profile but not the pinned flags; the gateway profile loads under
    --strict-config and its env filter keeps the key out of commands; and the two strict-mode limits the recipe states
    hold at this pin. No sign-in, gateway or network needed (the dry run's rehearsal and the gateway-profile tests run
    under bwrap --unshare-net when it can)."""

    def setUp(self):
        version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout
        if lane.CODEX_VERSION not in version:
            self.skipTest(f"codex on PATH is {version.strip()}, not {lane.CODEX_VERSION}")

    @staticmethod
    def isolation(root: Path) -> list[str]:
        """bwrap with no network and a private /tmp (codex sandbox keeps a lock there) around the scratch root, when
        bwrap works here; [] otherwise."""
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return []
        wrapper = [bwrap, "--unshare-net", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                   "--tmpfs", "/tmp", "--bind", str(root), str(root), "--"]
        return wrapper if subprocess.run([*wrapper, "true"], capture_output=True, check=False).returncode == 0 else []

    @staticmethod
    def gateway_home(root: Path, profile_text: str) -> dict:
        """A scratch Codex home: a base config whose only table is a `set`, and the given gateway profile."""
        codex_home = root / "home" / ".codex"
        codex_home.mkdir(parents=True)
        (codex_home / "config.toml").write_text('[shell_environment_policy.set]\nNAS_PROBE_SET = "kept"\n')
        (codex_home / "omniroute.config.toml").write_text(profile_text)
        (root / "cwd").mkdir()
        return {"HOME": str(root / "home"), "CODEX_HOME": str(codex_home), "LANG": "C.UTF-8",
                "PATH": os.pathsep.join([str(Path(shutil.which("codex")).parent), os.defpath])}

    def test_the_omniroute_profile_loads_strictly_and_names_its_key(self):
        # --strict-config rejects an unknown key at load. With the key unset, Codex then stops at the provider's
        # env_key (model-provider-info/src/lib.rs api_key at rust-v0.157.1) before any request, printing the
        # profile's env_key_instructions: the provider came from the profile layer.
        text = (TEMPLATES / "codex.omniroute.config.toml").read_text(encoding="utf-8")
        instructions = tomllib.loads(text)["model_providers"]["omniroute"]["env_key_instructions"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.gateway_home(root, text)
            got = subprocess.run([*self.isolation(root), "codex", "--strict-config", "-p", "omniroute", "exec",
                                  "--skip-git-repo-check", "-s", "read-only", "reply ok"], cwd=root / "cwd", env=env,
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("Missing environment variable: `OMNIROUTE_API_KEY`", got.stderr)
        self.assertIn(instructions, got.stderr)

    def test_the_omniroute_filter_keeps_the_key_out_of_commands(self):
        # A failing-first control. `codex sandbox` builds its command's environment from shell_environment_policy
        # with create_env, as a model-run command does (cli/src/debug_sandbox.rs L258-259 at rust-v0.157.1), and
        # --profile applies to it. The same fixture value reaches the command without the profile's filter and not
        # with it; the base config's `set` reaches it either way (the two forms merge across layers).
        text = (TEMPLATES / "codex.omniroute.config.toml").read_text(encoding="utf-8")
        unfiltered = text.replace('[shell_environment_policy.filters]\n"OMNIROUTE_API_KEY" = "exclude"\n', "")
        self.assertNotEqual(unfiltered, text)
        probe = ('if [ -n "${OMNIROUTE_API_KEY+x}" ]; then echo key=present; else echo key=absent; fi; '
                 'echo "set=${NAS_PROBE_SET:-missing}"')
        runs = {}
        for label, profile_text in (("filtered", text), ("unfiltered", unfiltered)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = {**self.gateway_home(root, profile_text), "OMNIROUTE_API_KEY": "fixture-not-a-key"}
                runs[label] = subprocess.run([*self.isolation(root), "codex", "-p", "omniroute", "sandbox", "--",
                                              "sh", "-c", probe], cwd=root / "cwd", env=env,
                                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        if all(run.returncode != 0 for run in runs.values()):
            self.skipTest(f"codex sandbox cannot run here: {runs['unfiltered'].stderr.strip()[-200:]}")
        self.assertEqual(runs["unfiltered"].stdout.split(), ["key=present", "set=kept"])  # the control
        self.assertEqual(runs["filtered"].stdout.split(), ["key=absent", "set=kept"])
        self.assertNotIn("fixture-not-a-key", runs["filtered"].stdout + runs["filtered"].stderr)

    def test_worker_profile_sets_chub_opt_outs_in_an_isolated_home(self):
        # Profile-v2 shell environment: real output, no provider. Sources at openai/codex rust-v0.157.1:
        # config/src/loader/mod.rs (profile-v2 layering), cli/src/debug_sandbox.rs (create_env),
        # protocol/src/shell_environment.rs (set overrides inherited variables).
        profile = (TEMPLATES / "codex.stack-worker.config.toml").read_text(encoding="utf-8")
        probe = ('printf "%s\\n" "telemetry=${CHUB_TELEMETRY:-missing}" '
                 '"feedback=${CHUB_FEEDBACK:-missing}" "base=${NAS_PROBE_SET:-missing}" '
                 '"chubdir=${CHUB_DIR:-unset}"; '
                 'if [ -n "${NAS_PROBE_FILTERED+x}" ]; then echo filter=present; else echo filter=absent; fi')
        runs = []
        for chub_dir in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = self.gateway_home(root, "")  # allowlisted environment; HOME and CODEX_HOME are scratch
                env.update(CHUB_TELEMETRY="1", CHUB_FEEDBACK="1", NAS_PROBE_FILTERED="fixture")
                if chub_dir:
                    env["CHUB_DIR"] = str(root / "separate-chub")
                    Path(env["CHUB_DIR"]).mkdir()
                expected_tail = ["base=kept", f"chubdir={env.get('CHUB_DIR', 'unset')}", "filter=absent"]
                home = Path(env["CODEX_HOME"])
                base = ('[shell_environment_policy.set]\nNAS_PROBE_SET = "kept"\n'
                        'CHUB_TELEMETRY = "1"\nCHUB_FEEDBACK = "1"\n'
                        '[shell_environment_policy.filters]\nNAS_PROBE_FILTERED = "exclude"\n')
                # Register each amended server; sandbox runs no MCP server or model.
                for name in tomllib.loads(profile)["mcp_servers"]:
                    base += f'[mcp_servers."{name}"]\ncommand = "/bin/false"\n'
                (home / "config.toml").write_text(base, encoding="utf-8")
                (home / "stack-worker.config.toml").write_text(profile, encoding="utf-8")
                cases = (("base", [], ["telemetry=1", "feedback=1"]),
                         ("worker", ["-p", "stack-worker"], ["telemetry=0", "feedback=0"]),
                         ("override", ["-p", "stack-worker", "-c", 'shell_environment_policy.set.CHUB_TELEMETRY="1"'],
                          ["telemetry=1", "feedback=0"]))
                for label, flags, expected in cases:
                    got = subprocess.run([*self.isolation(root), "codex", *flags, "sandbox", "--", "sh", "-c", probe],
                                         cwd=root / "cwd", env=env, stdin=subprocess.DEVNULL,
                                         capture_output=True, text=True, timeout=120)
                    runs.append((chub_dir, label, got, expected + expected_tail))
        if all(got.returncode != 0 for _, _, got, _ in runs):
            self.skipTest(f"codex sandbox cannot run here: {runs[0][2].stderr.strip()[-200:]}")
        for chub_dir, label, got, expected in runs:
            with self.subTest(chub_dir_overridden=chub_dir, case=label):
                self.assertEqual(got.returncode, 0, got.stderr[-400:])
                self.assertEqual(got.stdout.splitlines(), expected)

    def strict_exec(self, root: Path, env: dict, *flags: str, strict: bool = True) -> subprocess.CompletedProcess:
        """`codex [--strict-config] <flags> exec` in a scratch home with stdin closed. At 0.157.1 `codex debug`
        refuses --strict-config ("not supported for `codex debug`"), so exec is the strict read: without the gateway
        key it stops at that key, or earlier at a configuration error, before any request."""
        return subprocess.run([*self.isolation(root), "codex", *(["--strict-config"] if strict else []), *flags,
                               "exec", "--skip-git-repo-check", "-s", "read-only", "reply ok"], cwd=root / "cwd",
                              env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)

    def test_strict_config_refuses_the_launchers_model_flag(self):
        # recipes/README.md "Never `omniroute run codex --model`". The launcher defines the provider inline and adds
        # the model as a provider field (bin/cli/commands/launch-codex.mjs L173-194 at a58000c7): Codex ignores that
        # key with a warning and runs another model, and under --strict-config refuses the launch
        # (config/src/loader/mod.rs L257-258 and L647-669 at rust-v0.157.1). The contrast: the same key alone is only
        # warned about, because that layer on its own has an empty provider name and fails to deserialize
        # (config/src/config_toml.rs L979-983 and L992-1001), and a failing layer reports no ignored field
        # (config/src/strict_config.rs L97-110). A probe of the lone key alone once drew the wrong conclusion.
        launcher = ["-c", 'model_provider="omniroute"', "-c", 'model_providers.omniroute.name="OmniRoute"',
                    "-c", 'model_providers.omniroute.base_url="http://127.0.0.1:20128/v1"',
                    "-c", 'model_providers.omniroute.env_key="OMNIROUTE_API_KEY"',
                    "-c", 'model_providers.omniroute.wire_api="responses"',
                    "-c", "model_providers.omniroute.requires_openai_auth=false",
                    "-c", 'model_providers.omniroute.model="cx/nas-probe-model"']
        text = (TEMPLATES / "codex.omniroute.config.toml").read_text(encoding="utf-8")
        runs = {}
        for label, flags, strict in (("launcher strict", launcher, True), ("launcher", launcher, False),
                                     ("lone key strict", ["-p", "omniroute", *launcher[-2:]], True)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                runs[label] = self.strict_exec(root, self.gateway_home(root, text), *flags, strict=strict)
        refused = runs["launcher strict"]
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("unknown configuration field `model_providers.omniroute.model` in -c/--config override",
                      refused.stderr)
        for label in ("launcher", "lone key strict"):
            got = runs[label]
            self.assertIn("`model_providers.omniroute.model` is ignored", got.stderr, label)
            self.assertNotIn("model: cx/nas-probe-model", got.stderr, label)  # the requested model never runs
            self.assertIn("Missing environment variable: `OMNIROUTE_API_KEY`", got.stderr, label)  # loaded, stopped

    def test_strict_config_refuses_the_stack_worker_profile_at_this_pin(self):
        # recipes/README.md: start stack-worker lanes without --strict-config. Strict mode validates each
        # configuration file on its own as a whole configuration (config/src/loader/mod.rs L594-600 and L625-645 at
        # rust-v0.157.1), and the profile's server tables amend servers the base config registers, naming no command.
        # The control: without --strict-config the same home renders the profile's prompt input.
        fixture = {"HOME": "/home/example", "ECO_ROOT": "/home/example/.local/share/codex-ecosystem",
                   "PROJECT_ROOT": "/home/example/code/agent-lab", "HOST_PATH": "/usr/bin:/bin",
                   "OTEL_ENDPOINT": "127.0.0.1:1", "AI_MEMORY_URL": "127.0.0.1:1", "QDRANT_URL": "127.0.0.1:1",
                   "EMBED_URL": "127.0.0.1:1", "SOCRATICODE_VERSION": "1.15.0",
                   "CODEX_MODEL": render_config.codex_model_for(lane.CODEX_VERSION)}  # the model this codex lists
        base = string.Template((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.gateway_home(root, "")
            codex_home = Path(env["CODEX_HOME"])
            (codex_home / "config.toml").write_text(base.substitute(fixture))
            (codex_home / "stack-worker.config.toml").write_bytes(
                (TEMPLATES / "codex.stack-worker.config.toml").read_bytes())
            strict = self.strict_exec(root, env, "-p", "stack-worker")
            plain = subprocess.run([*self.isolation(root), "codex", "-p", "stack-worker", "debug", "prompt-input",
                                    "probe"], cwd=root / "cwd", env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, timeout=120)
        self.assertNotEqual(strict.returncode, 0)
        self.assertIn("stack-worker.config.toml", strict.stderr)
        self.assertIn("invalid transport", strict.stderr)
        self.assertEqual(plain.returncode, 0, plain.stderr[-400:])
        self.assertTrue(lane.prompt_input_counts(plain.stdout)["no_spawn_unless_asked"])  # the profile's max effort

    def test_the_jcodemunch_recipe_step_registers_the_server_only_where_it_is_copied(self):
        # recipes/README.md "Focused jCodeMunch retrieval": the recipe's own sed range, copied into a trusted
        # checkout's .codex/config.toml, is that directory's whole jcodemunch registration, and an unrelated directory
        # lists no MCP server at all (the user config here registers none).
        section = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8")
        section = section.split("\n## Focused jCodeMunch retrieval\n", 1)[1].split("\n## ", 1)[0]
        expression = re.search(r"sed -n '([^']+)' \\\n", section).group(1)
        eco = "/home/example/.local/share/codex-ecosystem"
        rendered = string.Template((TEMPLATES / "project.codex.config.template.toml").read_text(encoding="utf-8"))
        rendered = rendered.substitute(ECO_ROOT=eco, HOST_PATH="/usr/bin:/bin", CODE_INDEX_PATH="/home/example/.ci")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.gateway_home(root, "")
            project, other = root / "checkout", root / "cwd"
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            source = root / "project.codex.config.toml"
            source.write_text(rendered)
            (project / ".codex").mkdir()
            (project / ".codex" / "config.toml").write_text(
                subprocess.run(["sed", "-n", expression, str(source)], capture_output=True, text=True,
                               check=True).stdout)
            (Path(env["CODEX_HOME"]) / "config.toml").write_text(
                f'[projects."{project}"]\ntrust_level = "trusted"\n')
            got, listed = (subprocess.run([*self.isolation(root), "codex", "mcp", *args, "--json"], cwd=cwd, env=env,
                                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
                           for cwd, args in ((project, ["get", "jcodemunch"]), (other, ["list"])))
        self.assertEqual(got.returncode, 0, got.stderr[-400:])
        self.assertEqual(json.loads(got.stdout)["transport"]["command"], f"{eco}/bin/jcodemunch-mcp")
        self.assertEqual(listed.returncode, 0, listed.stderr[-400:])
        self.assertEqual(json.loads(listed.stdout), [])

    def test_real_app_server_apply_and_byte_exact_rollback(self):
        host = FakeHost(self)
        host.base_args[1] = shutil.which("codex")
        text = ('# a comment the writer keeps\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "ultra"\n\n'
                f'[features]\ndaemon_auto_start = false\n\n[shell_environment_policy.set]\n'
                f'PATH = "{host.eco}/bin:/usr/bin:/bin"\n\n[mcp_servers.ai-memory]\nurl = "http://127.0.0.1:1/mcp"\n\n'
                f'[mcp_servers.serena]\ncommand = "{host.eco}/bin/serena"\n\n'
                '[mcp_servers.codebase-memory]\ncommand = "/bin/false"\n\n'
                f'[mcp_servers.socraticode]\ncommand = "{host.eco}/bin/node"\nstartup_timeout_sec = 120\n\n'
                f'[mcp_servers.headroom]\ncommand = "{host.eco}/bin/headroom"\n\n[mcp_servers.headroom.env]\n'
                'HEADROOM_OFFLINE = "1"\n\n[plugins."context-mode@context-mode"]\nenabled = true\n')
        (host.codex_home / "config.toml").write_text(text)
        before = {name: (host.codex_home / name).read_bytes() for name in ("config.toml", "AGENTS.md")}
        code, out = host.run()
        self.assertEqual(code, 0, out)
        code, out = host.apply()
        self.assertEqual(code, 0, out)
        written = (host.codex_home / "config.toml").read_text()
        self.assertIn("# a comment the writer keeps", written)
        self.assertIn("startup_timeout_sec = 120\n", written)  # an integer stays an integer
        # serena, registered without an allowance (as `codex mcp add` leaves it), gets the template's 60 s
        self.assertEqual(tomllib.loads(written)["mcp_servers"]["serena"]["startup_timeout_sec"], 60)
        code, out = host.run("--rollback", str(host.latest_run()))
        self.assertEqual(code, 0, out)
        for name, data in before.items():
            self.assertEqual((host.codex_home / name).read_bytes(), data, name)
        self.assertFalse((host.codex_home / "stack-worker.config.toml").exists())

    def test_the_doctor_reader_accepts_the_shipped_roles_and_flags_a_malformed_one(self):
        # The parser of the installer's rehearsal against the real binary: `codex doctor --json` in a scratch home
        # exits 1 (auth.credentials fails without a sign-in) and still prints config.load. The two shipped carriers
        # add no startup warning; a role file without developer_instructions adds exactly one, "Ignoring malformed
        # agent role definition", so the same reader gives ok for the first and problem for the second.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.gateway_home(root, "")
            codex_home, cwd = Path(env["CODEX_HOME"]), root / "cwd"
            wrapper = lane.bwrap_wrapper(root)
            reports = {"none": lane.run_doctor(shutil.which("codex"), env, wrapper, cwd)}
            agents = codex_home / "agents"
            agents.mkdir(mode=0o700)
            for name in ROLE_NAMES:
                shutil.copy(ROLES_SOURCE_DIR / name, agents / name)
            reports["shipped"] = lane.run_doctor(shutil.which("codex"), env, wrapper, cwd)
            (agents / ROLE_NAMES[1]).write_text('name = "stack-verifier"\ndescription = "no developer_instructions"\n')
            reports["malformed"] = lane.run_doctor(shutil.which("codex"), env, wrapper, cwd)
        for label, stdout in reports.items():
            self.assertIsNotNone(lane.doctor_config_load(stdout), f"{label}: no config.load in the report")
        shipped = lane.doctor_role_state(reports["none"], reports["shipped"])
        self.assertEqual(shipped, {"state": "ok", "startup_warnings_before": 0, "startup_warnings_after": 0,
                                   "role_warnings": 0, "redacted": 0, "load_failed": False})
        malformed = lane.doctor_role_state(reports["none"], reports["malformed"])
        self.assertEqual(malformed, {"state": "problem", "startup_warnings_before": 0, "startup_warnings_after": 1,
                                     "role_warnings": 1, "redacted": 0, "load_failed": False})

    def test_codex_follows_links_below_agents_and_the_role_count_never_undercounts_it(self):
        # Upstream behaviour, checked with the real binary and not assumed: LocalFileSystem::read_directory takes a link's
        # target's type (openai/codex rust-v0.157.1 codex-rs/exec-server/src/local_file_system.rs:710-735), so
        # agent-roles/src/discovery.rs enters a linked folder, collects a link to a regular file by the link's own name and
        # skips a dangling one. `codex doctor --json` in a scratch home with the network off records one startup warning per
        # malformed role file Codex collects, so the number of role warnings is how many files it loaded. Controls: the
        # empty folder and a valid role give none, and a real subfolder gives one (a folder is entered). The invariant the
        # tools rest on: agents_toml_count is None or at least what Codex collected, never less. This is a check of what
        # Codex does, not a failing-first test of the tools: if a later pin stops following links, this is the test that says
        # so and the rule can be revisited (docs/decisions/2026-09-26-codex-worker-lane.md, 2026-09-29 addendum).
        good = 'name = "probe"\ndescription = "d"\ndeveloper_instructions = "x"\n'
        bad = 'name = "bad"\ndescription = "d"\n'  # no developer_instructions: one role warning when Codex collects it

        def elsewhere(root):
            folder = root / "elsewhere"
            folder.mkdir()
            (folder / "bad.toml").write_text(bad)
            (folder / "bad.txt").write_text(bad)
            return folder

        def empty_folder(agents, root):
            pass

        def valid_role(agents, root):
            (agents / "ok.toml").write_text(good)

        def real_subfolder(agents, root):
            (agents / "sub").mkdir()
            (agents / "sub" / "bad.toml").write_text(bad)

        def link_to_folder(agents, root):
            (agents / "linked").symlink_to(elsewhere(root))

        def link_named_toml_to_folder(agents, root):
            (agents / "dir.toml").symlink_to(elsewhere(root))

        def link_named_toml_to_file(agents, root):
            (agents / "file.toml").symlink_to(elsewhere(root) / "bad.txt")

        def dangling_link_named_toml(agents, root):
            (agents / "dangling.toml").symlink_to(root / "nowhere")

        def toml_behind_a_txt_link(agents, root):
            (agents / "renamed.txt").symlink_to(elsewhere(root) / "bad.toml")

        scenarios = (  # label, setup, the role warnings Codex records, the *.toml files it collects
            ("an empty folder (control)", empty_folder, 0, 0),
            ("a valid role (control)", valid_role, 0, 1),
            ("a malformed role in a real subfolder (control)", real_subfolder, 1, 1),
            ("a link to a folder", link_to_folder, 1, 1),
            ("a link named x.toml to a folder", link_named_toml_to_folder, 1, 1),
            ("a link named x.toml to a file", link_named_toml_to_file, 1, 1),
            ("a dangling link named x.toml", dangling_link_named_toml, 0, 0),
            ("a malformed role behind a link named x.txt", toml_behind_a_txt_link, 0, 0),
        )
        codex = shutil.which("codex")

        def observe(scenario):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = self.gateway_home(root, "")
                agents = Path(env["CODEX_HOME"]) / "agents"
                agents.mkdir(mode=0o700)
                scenario[1](agents, root)
                stdout = lane.run_doctor(codex, env, lane.bwrap_wrapper(root), root / "cwd")
                return lane.doctor_config_load(stdout), lane.agents_toml_count(agents)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            observed = list(pool.map(observe, scenarios))
        for (label, _setup, role_warnings, collected), (loaded, count) in zip(scenarios, observed):
            with self.subTest(scenario=label):
                self.assertIsNotNone(loaded, "no config.load in the report")
                warnings = lane.codex_roles.startup_warnings(loaded[1])
                self.assertEqual(sum(text.startswith(lane.codex_roles.ROLE_WARNING_PREFIX) for text in warnings),
                                 role_warnings, "the role files Codex collected")
                self.assertTrue(count is None or count >= collected,
                                f"the count says {count}, but Codex collected {collected}: the count undercounts")

    def test_a_project_config_outranks_the_profile_but_not_the_pinned_flags(self):
        # The multi_agent_mode sentence tells the efforts apart: ultra delegates proactively, max does not.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, project = root / "home", root / "project"
            (home / ".codex").mkdir(parents=True)
            (project / ".codex").mkdir(parents=True)
            shutil.copy(TEMPLATES / "codex.stack-worker.config.toml", home / ".codex" / "stack-worker.config.toml")
            (home / ".codex" / "config.toml").write_text(
                'model_reasoning_effort = "max"\n[mcp_servers.ai-memory]\nurl = "http://127.0.0.1:1/mcp"\n'
                '[mcp_servers.socraticode]\ncommand = "/bin/false"\n[mcp_servers.headroom]\ncommand = "/bin/false"\n'
                '[mcp_servers.serena]\ncommand = "/bin/false"\n[mcp_servers.codebase-memory]\ncommand = "/bin/false"\n'
                f'[mcp_servers.context-mode]\ncommand = "/bin/false"\n[projects."{project}"]\ntrust_level = "trusted"\n')
            (project / ".codex" / "config.toml").write_text('model_reasoning_effort = "ultra"\n')
            subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
            env = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"), "LANG": "C.UTF-8",
                   "PATH": os.pathsep.join([str(Path(shutil.which("codex")).parent), os.defpath])}

            def rendered(*flags):
                got = subprocess.run(["codex", *flags, "debug", "prompt-input", "probe"], cwd=project, env=env,
                                     stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
                self.assertEqual(got.returncode, 0, got.stderr[-300:])
                return got.stdout

            self.assertIn("Proactive multi-agent delegation is active", rendered("-p", "stack-worker"))
            self.assertIn("Do not spawn sub-agents unless",
                          rendered("-p", "stack-worker", "-c", 'model_reasoning_effort="max"'))


if __name__ == "__main__":
    unittest.main()
