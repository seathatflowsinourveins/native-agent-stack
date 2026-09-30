#!/usr/bin/env python3
"""Stage the pi trial arms: scratch HOMEs, no credentials, no model calls.

Local integration glue around upstream tools (see pins.json); it is not upstream acceptance. It renders the
config templates, takes the pi extension and the awareness text from rtk itself, assembles the instruction file
from the repository's canonical blocks, installs the already-installed context-mode package into pi, and can
check the result offline (--check).

    stage.py --pi-src DIR [--state DIR] [--eco-root DIR] [--arm stack|plain|all] [--check]

--pi-src is a checkout of earendil-works/pi at kit/pins.json's commit, built with `npm ci --ignore-scripts` and
`npm run build`. Arms: stack = the ecosystem's token-save practice on; plain = the same pi, model and gateway
route with none of it (no compression header, extension, package, MCP or instruction file).
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEMPLATES = HERE / "templates"
CONTEXT_MODE = "tools/context-mode-1.0.169/lib/node_modules/context-mode"
TOP_RULE_SOURCE = "adoption/templates/codex.AGENTS.template.md"
LANES_SOURCE = "adoption/hooks/claude/token-lanes-block.md"

# The only sentence that is not canonical text: pi loads deferred tools with tool_search, not ToolSearch select:.
PI_TOOLS_BULLET = (
    "- Tools: the ctx_* tools (ctx_execute, ctx_batch_execute, ctx_search, ctx_fetch_and_index, ctx_execute_file, "
    "ctx_index, ctx_stats) are always declared. Serena, jcodemunch, qmd and headroom tools are deferred: call tool_search "
    "with the tool name or purpose to load them, then call them directly."
)
# (bullet prefix, action): "keep", "drop", "replace", or (old, new) substrings that must be present.
LANE_RULES = [
    ("- Load deferred token tools in ONE ToolSearch call", "replace"),
    ("- Fetch pages with ctx_fetch_and_index", "keep"),
    ("- Use ctx_search with specific queries", "keep"),
    ("- For output over ~5 KB", "keep"),
    ("- Automatic RTK:", "keep"),
    ("- Use Serena find_symbol", ("; socraticode codebase_search(query, projectPath) with explicit projectPath for conceptual questions", "")),
    ("- Use codebase-memory trace_path", "drop"),
    ("- Use qmd query with collections", (" Use ai-memory memory_query with workspace/project from .ai-memory.toml as historical evidence only, never authority.", "")),
    ("- Use TOON", "keep"),
    ("- For large selected text, use headroom_compress", "keep"),
    ("- Use one lane per artifact", "keep"),
    ("- Show evidence before a success claim", (" Research upstream first with the installed search-first skill before writing custom code. Source: skillOverrides in adoption/templates/claude.settings.template.json.", "")),
]
RTK_HOOK_CASES = [
    ("git show HEAD:x | tail -n 5", False), ("diff a.txt b.txt", False), ("git -C repo show HEAD:x", False),
    ("git branch -a", False), ("jq . x.json", False), ("git status", True), ("ls -la", True),
]


CTX_TOOLS = ("execute_file", "batch_execute", "fetch_and_index", "execute", "search", "index", "stats")


def family(arm):
    return "plain" if arm == "plain" else "stack"


def mcp_names(text):
    """The MCP arm reaches context-mode through pi's MCP client, so its tools are namespaced mcp__context-mode__ctx_*."""
    import re as _re
    return _re.sub(r"\bctx_(" + "|".join(CTX_TOOLS) + r")\b", r"mcp__context-mode__ctx_\1", text)


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def render(name, mapping):
    text = (TEMPLATES / name).read_text()
    for key, value in mapping.items():
        text = text.replace(key, value)
    data = json.loads(text)
    headers = data.get("providers", {}).get("omni-fw", {}).get("headers")
    if headers is not None and headers.get("x-omniroute-compression") == "":
        del headers["x-omniroute-compression"]  # empty --stack-compression: the arm sends no compression header
        text = json.dumps(data, indent=2) + "\n"
    return text


def rtk_exclusions():
    text = (REPO / "recipes/README.md").read_text()
    for match in re.finditer(r"```toml\n(.*?)```", text, re.S):
        if "exclude_commands" in match.group(1):
            return match.group(1)
    raise SystemExit("recipes/README.md: no exclude_commands toml block")


def rtk_awareness():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / ".claude").mkdir()
        result = run(["rtk", "init", "-g", "--no-patch"], env={**os.environ, "HOME": tmp}, cwd=tmp, stdin=subprocess.DEVNULL)
        path = Path(tmp) / ".claude" / "RTK.md"
        if not path.exists():
            raise SystemExit("rtk init -g wrote no RTK.md: " + (result.stdout + result.stderr)[-300:])
        return path.read_text().rstrip("\n")


def top_rule():
    lines = (REPO / TOP_RULE_SOURCE).read_text().splitlines()
    block = lines[2:8]
    if not block[0].startswith("Top rule:") or not block[-1].startswith("When a claim proves wrong"):
        raise SystemExit(TOP_RULE_SOURCE + ": lines 3-8 no longer hold the top-rule block")
    return "\n".join(block)


def lanes_block():
    lines = (REPO / LANES_SOURCE).read_text().splitlines()
    out, seen = [lines[0]], []
    for line in lines[1:]:
        if not line.startswith("- "):
            continue
        rule = next((r for r in LANE_RULES if line.startswith(r[0])), None)
        if rule is None:
            raise SystemExit(LANES_SOURCE + ": unclassified bullet: " + line[:60])
        seen.append(rule[0])
        action = rule[1]
        if action == "drop":
            continue
        if action == "replace":
            line = PI_TOOLS_BULLET
        elif isinstance(action, tuple):
            if action[0] not in line:
                raise SystemExit(LANES_SOURCE + ": expected text missing in bullet: " + rule[0])
            line = line.replace(action[0], action[1])
        out.append(line)
    missing = [r[0] for r in LANE_RULES if r[0] not in seen]
    if missing:
        raise SystemExit(LANES_SOURCE + ": bullets no longer present: " + "; ".join(missing))
    return "\n".join(out)


def launcher(arm, a, home):
    return (
        "#!/usr/bin/env bash\n"
        f"# Generated by stage.py: pi trial launcher, arm {arm}. Scratch HOME, no telemetry, pinned source build.\n"
        f"export ECO_ROOT={shlex.quote(str(a.eco_root))}\n"
        f"export HOME={shlex.quote(str(home))}\n"
        'export PATH="$ECO_ROOT/bin:$PATH"\n'
        "export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0\n"
        f"exec node {shlex.quote(str(a.pi_src / 'packages/coding-agent/dist/bundle/cli.js'))} \"$@\"\n"
    )


def stage_arm(arm, a):
    arm_dir = a.state / "arms" / arm
    home = arm_dir / "home"
    agent = home / ".pi" / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    mapping = {"@ECO_ROOT@": str(a.eco_root), "@STATE@": str(a.state), "@STACK_COMPRESSION@": a.stack_compression}
    for name in ("models", "settings"):
        (agent / f"{name}.json").write_text(render(f"{name}.{family(arm)}.json.tmpl", mapping))
    if arm != "plain":
        (agent / "mcp.json").write_text(render(f"mcp.{arm}.json.tmpl", mapping))
    (a.state / "bin").mkdir(parents=True, exist_ok=True)
    exe = a.state / "bin" / f"pi-{arm}"
    exe.write_text(launcher(arm, a, home))
    exe.chmod(0o755)
    if arm != "plain":
        (arm_dir / "serena-home").mkdir(exist_ok=True)
        (arm_dir / "jcodemunch-index").mkdir(exist_ok=True)
        rtk_config = home / ".config" / "rtk"
        rtk_config.mkdir(parents=True, exist_ok=True)
        (rtk_config / "config.toml").write_text(rtk_exclusions())
        env = {**os.environ, "HOME": str(home)}
        init = run(["rtk", "init", "-g", "--agent", "pi"], env=env, cwd=home, stdin=subprocess.DEVNULL)
        if not (agent / "extensions" / "rtk.ts").exists():
            raise SystemExit("rtk init --agent pi installed no extension: " + (init.stdout + init.stderr)[-300:])
        instructions = "\n\n".join([top_rule(), rtk_awareness(), lanes_block()]) + "\n"
        (agent / "AGENTS.md").write_text(mcp_names(instructions) if arm == "stack" else instructions)
        settings = json.loads((agent / "settings.json").read_text())
        if arm == "stack-ext" and not settings.get("packages"):
            package = a.eco_root / CONTEXT_MODE
            done = run([exe, "install", package], cwd=home)
            if done.returncode != 0:
                raise SystemExit("pi install failed: " + (done.stdout + done.stderr)[-300:])
    print(f"staged arm {arm}: {agent}")


def check(arm, a):
    exe = a.state / "bin" / f"pi-{arm}"
    agent = a.state / "arms" / arm / "home" / ".pi" / "agent"
    cwd = a.state / "check-cwd"
    cwd.mkdir(exist_ok=True)
    bad = 0

    def report(ok, text):
        nonlocal bad
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + f"[{arm}] {text}")

    version = run([exe, "--version"], cwd=cwd, stdin=subprocess.DEVNULL)
    report(version.returncode == 0, "pi --version -> " + version.stdout.strip())
    if arm == "plain":
        report(not (agent / "extensions").exists() and not (agent / "mcp.json").exists() and not (agent / "AGENTS.md").exists(),
               "no extension, MCP config or instruction file")
        return bad
    report((agent / "extensions" / "rtk.ts").exists(), "rtk extension installed by rtk init --agent pi")
    has_package = bool(json.loads((agent / "settings.json").read_text()).get("packages"))
    report(has_package == (arm == "stack-ext"),
           "context-mode pi extension " + ("installed" if arm == "stack-ext" else "absent (tools come through MCP, no message-injecting hooks)"))
    listed = run([exe, "mcp", "list"], cwd=cwd, timeout=180, stdin=subprocess.DEVNULL)
    for server in (("context-mode",) if arm == "stack" else ()) + ("serena", "jcodemunch", "qmd", "headroom"):
        report(f"{server}: connected" in listed.stdout, f"mcp {server} connected")
    report(listed.returncode == 0, "pi mcp list exits 0")
    env = {**os.environ, "HOME": str(a.state / "arms" / arm / "home")}
    for command, rewritten in RTK_HOOK_CASES:
        checked = run(["rtk", "hook", "check", command], env=env)
        # rtk prints a one-time "[rtk] ... No hook installed" nag on its first call in a fresh HOME; the verdict is the last other line
        lines = [l for l in (checked.stdout + checked.stderr).splitlines() if l.strip() and not l.startswith("[rtk]")]
        out = lines[-1].strip() if lines else ""
        report(out.startswith("No rewrite") != rewritten, f"rtk hook check {command!r} -> {out[:48]}")
    return bad


def main():
    home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pi-src", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=home / "native-agent-stack" / "pi-trial")
    parser.add_argument("--eco-root", type=Path, default=Path(os.environ.get("ECO_ROOT", Path.home() / ".local/share/codex-ecosystem")))
    parser.add_argument("--arm", choices=["stack", "stack-ext", "plain", "all"], default="all")
    parser.add_argument("--stack-compression", default="",
                        help="value of x-omniroute-compression for the stack arm; empty sends none (the gateway's default lane)")
    parser.add_argument("--check", action="store_true", help="check only; stage nothing")
    a = parser.parse_args()
    a.state.mkdir(parents=True, exist_ok=True)
    a.state.chmod(0o700)
    if not (a.pi_src / "packages/coding-agent/dist/bundle/cli.js").exists():
        raise SystemExit("--pi-src has no built dist/bundle/cli.js; run npm ci --ignore-scripts && npm run build there")
    arms = ["stack", "stack-ext", "plain"] if a.arm == "all" else [a.arm]
    if not a.check:
        for arm in arms:
            stage_arm(arm, a)
    failures = sum(check(arm, a) for arm in arms)
    print("result:", "FAIL" if failures else "ok", f"({failures} failed checks)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
