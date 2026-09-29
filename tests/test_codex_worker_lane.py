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
- CodexIntegrationTests runs the real codex 0.157.1 app-server against a scratch Codex home, only when
  NAS_CODEX_INTEGRATION=1 and that codex is on PATH (local integration evidence; skipped in CI).
"""

from __future__ import annotations

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
from scripts import adoption_status  # noqa: E402

TEMPLATES = ROOT / "adoption" / "templates"
FIXTURES = ROOT / "tests" / "fixtures" / "codex-worker-lane"
# The staged top-rule block (153 words by `wc -w`, marker line included) and rtk-ai/rtk v0.50.0
# hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec), both byte for byte.
TOP_RULE_SHA256 = "ce957fd86d5457f0e0a83fa726afa5aa4fbfd94d49471835dc83526ce3aa3b9d"
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

FAKE_CODEX = r'''#!{python}
"""Fake codex 0.157.1 for tests/test_codex_worker_lane.py (see its docstring)."""
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
    print("codex-cli 0.157.1"); sys.exit(0)
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
        self.assertLess(len(text.encode("utf-8")), 8192)  # far under Codex's 32 KiB project_doc_max_bytes

    def test_top_rule_and_upstream_text_are_verbatim(self):
        top, upstream, _ = template_segments()
        self.assertEqual(hashlib.sha256(top.encode("utf-8")).hexdigest(), TOP_RULE_SHA256)
        self.assertEqual(len(top.split()), 153)
        self.assertEqual(hashlib.sha256(upstream.encode("utf-8")).hexdigest(), RTK_AWARENESS_SHA256)

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

    def test_profile_template(self):
        profile = tomllib.loads((TEMPLATES / "codex.stack-worker.config.toml").read_text(encoding="utf-8"))
        self.assertEqual(profile["model"], "gpt-6-astra")
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
        # `codex mcp add` takes no timeout option (its --help at 0.157.1), so a server it registered has none and
        # Codex waits its 30 s default; the template gives serena 60 s and socraticode 120 s.
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
        # K2: the base template stays gateway-free, so render_config.py --check still compares like with like.
        user = tomllib.loads((TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8"))
        self.assertNotIn("model_providers", user)
        self.assertNotIn("model_provider", user)
        self.assertEqual(user["model"], "gpt-6-astra")

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
        self.codex.write_text(FAKE_CODEX.replace("{python}", sys.executable).replace("{emitter}", EMITTER))
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
    """Synthetic: the fake codex above stands in for codex-cli 0.157.1."""

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
        self.assertEqual(pins, ["-m", "gpt-6-astra", "-c", 'model_reasoning_effort="max"', "-c", 'web_search="live"'])
        for profile in (True, False):
            argv = prove.exec_argv("codex", "prompt", profile)
            self.assertEqual(argv[:2], ["codex", "exec"])
            self.assertEqual("-p" in argv, profile)
            joined = " ".join(argv)
            self.assertIn(" ".join(pins), joined)
            self.assertIn("-s read-only", joined)
        self.assertEqual(lane.worker_command(), "codex exec -p stack-worker -m gpt-6-astra "
                         "-c 'model_reasoning_effort=\"max\"' -c 'web_search=\"live\"' -s <sandbox> ... < /dev/null")
        recipe = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8")
        self.assertIn('codex exec -p stack-worker -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live"',
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
                     "set NAS_CODEX_INTEGRATION=1 with codex-cli 0.157.1 on PATH to run the real app-server")
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
                   "EMBED_URL": "127.0.0.1:1", "SOCRATICODE_VERSION": "1.15.0"}
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
