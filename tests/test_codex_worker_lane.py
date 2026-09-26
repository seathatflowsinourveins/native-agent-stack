"""Tests for the Codex worker lane: its templates, tools/adoption/apply_codex_lane.py and
tools/adoption/prove_codex_lane.py.

Evidence classes (docs/acceptance-evidence-policy.md):
- template and block tests read the repository files only;
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
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import apply_codex_lane as lane  # noqa: E402
import prove_codex_lane as prove  # noqa: E402
from scripts import adoption_status  # noqa: E402

TEMPLATES = ROOT / "adoption" / "templates"
FIXTURES = ROOT / "tests" / "fixtures" / "codex-worker-lane"
# The staged top-rule block (120 words by `wc -w`, marker line included) and rtk-ai/rtk v0.50.0
# hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec), both byte for byte.
TOP_RULE_SHA256 = "476b73c52ecc64bdf5152fe4b5188aef8d22db6f3f8816789a0842abe2841311"
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
        self.assertEqual(len(top.split()), 120)
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
        self.assertLessEqual(set(profile), {"model", "model_reasoning_effort", "web_search", "mcp_servers"})
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


def fixture_events(name: str) -> list[dict]:
    """A run's `codex exec --json` events, one JSON array per run (`*.jsonl` is git-ignored here)."""
    return json.loads((FIXTURES / name).read_text())


class ProveVerdictTests(unittest.TestCase):
    """The live verdicts on event shapes from real codex-cli 0.157.1 `codex exec --json` runs."""

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


@unittest.skipUnless(os.environ.get("NAS_CODEX_INTEGRATION") == "1" and shutil.which("codex"),
                     "set NAS_CODEX_INTEGRATION=1 with codex-cli 0.157.1 on PATH to run the real app-server")
class CodexIntegrationTests(unittest.TestCase):
    """Local integration with the real codex: its app-server writes a scratch Codex home and rollback restores it
    byte for byte; a project config outranks the profile but not the pinned flags. No sign-in or network needed
    (the dry run's rehearsal runs under bwrap --unshare-net when it can)."""

    def setUp(self):
        version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout
        if lane.CODEX_VERSION not in version:
            self.skipTest(f"codex on PATH is {version.strip()}, not {lane.CODEX_VERSION}")

    def test_real_app_server_apply_and_byte_exact_rollback(self):
        host = FakeHost(self)
        host.base_args[1] = shutil.which("codex")
        text = ('# a comment the writer keeps\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "ultra"\n\n'
                f'[features]\ndaemon_auto_start = false\n\n[shell_environment_policy.set]\n'
                f'PATH = "{host.eco}/bin:/usr/bin:/bin"\n\n[mcp_servers.ai-memory]\nurl = "http://127.0.0.1:1/mcp"\n\n'
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
