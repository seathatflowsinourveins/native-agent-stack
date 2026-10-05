#!/usr/bin/env python3
"""Consistency checker for the new-WSL install plan. Standard library only (Python 3.11 or newer, for tomllib).

Reads install-plan.json, owners.json, install.sh, accept.sh, mise.toml, config/ and the merged definitive manifest, names every
disagreement and exits 1; prints actual installed, measurement-only, excluded, command and acceptance counts
and exits 0 when they agree. It runs `bash install.sh --list` (read-only) and
installs nothing.

usage: python3 -B check_plan.py [--plan-dir DIR] [--manifest PATH]
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import shlex
import subprocess
import sys
import tomllib

STAGES = ("post_install", "service_health", "after_sign_in")
RUNTIME_PINS = {"node", "python", "uv"}  # install.sh installs these unconditionally, before any mise tool
ON_DEMAND = {"mcp-inspector", "base-distribution"}  # the manifest says installs; the plan installs nothing for them (README.md)
GATE = "interim_acknowledged"  # install.sh's gate of the interim installs (amendment 3 of the manifest's decision rule)
FUNCTION = re.compile(r"^([A-Za-z0-9_.-]+) ?\(\) ?\{(.*)$")
PORT_IN_CONFIG = (re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}:(\d{4,5})\b|\[[0-9a-f:]*\]:(\d{4,5})\b|(?<![\w.]):(\d{4,5})\b"),
                  re.compile(r"(?i)\b\w*port\w*\s*[=:]\s*[\"']?(\d{4,5})\b"))


def functions(text):
    found, name, body = {}, None, []
    for line in text.splitlines():
        if name is None:
            match = FUNCTION.match(line)
            if match and match.group(2).rstrip().endswith("}"):  # a one-line function
                found[match.group(1)] = match.group(2).rstrip()[:-1]
            elif match:
                name, body = match.group(1), []
        elif line == "}":
            found[name] = "\n".join(body)
            name = None
        else:
            body.append(line)
    return found


def run_commands(name, funcs, helpers, trail=()):
    """The strings passed to run_command in function `name`, in order; a helper function that runs commands is expanded where it is called."""
    out = []
    for line in funcs[name].splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("run_command "):
            out.append(shlex.split(stripped)[1])
            continue
        for helper in helpers:
            if helper not in trail and helper != name and re.search(r"(?<![\w-])" + re.escape(helper) + r"(?![\w-])", stripped):
                out.extend(run_commands(helper, funcs, helpers, trail + (name,)))
    return out


def checks_of(body):
    """(stage, kind, program) of every `check <slot> <kind> <program>` call in an accept.sh function, plus the slot argument."""
    lexer = shlex.shlex(body, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    tokens, stage, found, i = list(lexer), None, [], 0
    while i < len(tokens):
        if re.fullmatch(r"(post_install|service_health|after_sign_in)\)", tokens[i]):
            stage = tokens[i][:-1]
        elif tokens[i] == "check" and i + 3 < len(tokens):
            found.append((stage, tokens[i + 1], tokens[i + 2], tokens[i + 3]))
            i += 3
        i += 1
    return found


def sourced(body, marker):
    """Names the `marker` lines (run_command / check) that are not preceded by a comment block with `Source: https://`."""
    missing, has_source = 0, False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            has_source = has_source or bool(re.search(r"Source: https?://", stripped))
        elif stripped.startswith(marker):
            missing += 0 if has_source else 1
            has_source = False
        elif stripped:
            has_source = False
    return missing


def ports_in(text):
    found = set()
    for line in text.splitlines():
        line = re.sub(r"\s[#;].*$", "", line)
        if line.lstrip().startswith(("#", ";")):
            continue
        for pattern in PORT_IN_CONFIG:
            for match in pattern.finditer(line):
                found.update(int(g) for g in match.groups() if g)
    return found


def client_additional_checks(row, funcs, bad):
    """The two G1 native operations supplement independently checked inventory/SDK checks.

    Sources: openai/codex@rust-v0.160.0:codex-rs/app-server-test-client/src/lib.rs:1072,1994;
    anthropics/skills@8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4:
    skills/skill-creator/scripts/quick_validate.py:9,96.
    """
    owned = {
        "codex-sdk-and-codex-exec-app-server": ("after_sign_in", "codex-sdk-and-codex-exec-app-server-protocol"),
        "skill-authoring": ("post_install", "skill-authoring-upstream"),
    }
    slot = row["slot"]
    if slot not in owned:
        return
    stage, helper = owned[slot]
    entries = row["acceptance"].get(stage, {}).get("additional_checks")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        bad("acceptance", f"row {slot} {stage}: requires its additional native upstream check")
        return
    entry = entries[0]
    if not entry.get("command") or entry.get("kind") != "smoke" or not str(entry.get("source", {}).get("url", "")).startswith("https://"):
        bad("sources", f"row {slot} {stage}: the additional check needs a command, smoke kind and upstream source URL")
        return
    branch = re.search(r"^\s*" + stage + r"\)\n(.*?)^\s*;;", funcs.get(slot, ""), re.M | re.S)
    if not branch or not re.search(r"^\s*" + re.escape(helper) + r"\s*$", branch.group(1), re.M):
        bad("sync", f"row {slot} {stage}: accept.sh does not call {helper} in this stage")
    try:
        actual = checks_of(funcs.get(helper, ""))
    except ValueError as error:
        bad("sync", f"row {slot}: {helper} does not parse ({error})")
        return
    if actual != [(stage, slot, entry["kind"], entry["command"])]:
        bad("sync", f"row {slot}: {helper} differs from the declared additional check")
    if sourced(funcs.get(helper, ""), "check "):
        bad("sources", f"row {slot}: {helper} has no Source comment above its check")
    if slot == "codex-sdk-and-codex-exec-app-server":
        required = ("codex debug app-server send-message-v2", "^< initialize response:", "^< thread/start response:",
                    "^< turn/start response:", "grep -qx '< turn/completed notification: Completed'", "text: \"4\"")
        if any(token not in entry["command"] for token in required):
            bad("acceptance", f"row {slot}: the app-server check must require its protocol responses, Completed and reply")
        if "codexPathOverride" in row["acceptance"][stage]["command"] or "new Codex()" not in row["acceptance"][stage]["command"]:
            bad("acceptance", f"row {slot}: the SDK quickstart must exercise its default bundled-binary lookup")
    else:
        required = ('codex debug prompt-input >/dev/null',
                    'python -B "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/skill-creator/scripts/quick_validate.py"',
                    'python -B "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py"')
        if not row["needs"]["python"] or not any("uv pip install --python" in cmd and "PyYAML==6.0.3" in cmd for cmd in row["commands"]):
            bad("acceptance", f"row {slot}: its session-default Python prerequisite must provision pinned PyYAML")
        if any(token not in entry["command"] for token in required):
            bad("acceptance", f"row {slot}: initialize the native embedded cache, then run both upstream validators through python with bytecode disabled")

def agent_messaging_contract(plan_dir, by_slot, bad):
    """Round-2 hcom pin and mapped posture; no new model trial.

    Sources: aannoo/hcom@2c5f343:tests/cli_smoke.rs:129,140;
    https://developers.openai.com/codex/rules; this PR: config/hcom-client-config.py.
    """
    row = by_slot.get("agent-messaging", {})
    if not row.get("installed") or row.get("release") != "v0.7.27":
        bad("agent-messaging", "round 2 adopts the pinned hcom 0.7.27 transport")
        return
    try:
        # --plan-dir supports a standalone copied plan in the existing tests.
        # Its native map stays beside this checker in the source checkout;
        # check the rules and adapter from the selected plan, including copies.
        source_root = pathlib.Path(__file__).resolve().parents[3]
        mapping = json.loads((source_root / "adoption/new-wsl/client-config-map.json").read_text())
        spec = mapping["slot_configs"]["agent-messaging"]
        posture = spec["hcom_config"]
        if (posture["terminal"]["title_mode"] != "off" or posture["relay"]["enabled"] is not False
                or posture["launch"]["auto_trust_workspace"] is not False
                or posture["preferences"]["auto_approve"] is not True):
            bad("agent-messaging", "mapped hcom configuration differs from the accepted posture")
        deny = set(spec["claude_settings"]["permissions"]["deny"])
        for prefix in ("hcom", "uvx hcom"):
            for tail in ("term *", "relay *", "config *", "hooks *", "run *", "kill *", "stop *", "reset *",
                         "update *", "claude-pty *", "* claude-pty *", "--name *", "--go *",
                         "send -b *", "send --from *", "send --from=*"):
                if f"Bash({prefix} {tail})" not in deny:
                    bad("agent-messaging", f"mapped Claude deny is missing: {prefix} {tail}")
        rules = (plan_dir / "config" / pathlib.Path(spec["codex_rule_file"]).name).read_text()
        if rules.count('decision = "forbidden"') != 4 or "not_match =" not in rules:
            bad("agent-messaging", "Codex requires all four forbidden rules and their native inline examples")
        adapter = (plan_dir / "config/hcom-client-config.py").read_text()
        if '"execpolicy", "check", "--pretty", "--rules"' not in adapter:
            bad("agent-messaging", "the configuration adapter must run the mandatory native rule check")
    except (OSError, ValueError, KeyError, TypeError):
        bad("agent-messaging", "mapped native posture or rules are missing")
    acceptance = row.get("acceptance", {}).get("post_install", {}).get("command", "")
    if not all(token in acceptance for token in ("status --json", "list --json", "send @nobody -- hi", "listen --name", "events --last 10", "env -i", "--check")):
        bad("agent-messaging", "post-install must check upstream CLI smoke behavior and installed client posture")


def code_docs_contract(plan_dir, by_slot, bad):
    """The three g3 fixes: selected Serena pin, search AND rewrite, and local MinerU skill/quality wiring."""
    serena = by_slot.get("serena", {})
    pin = "c6fbd1c5932df2494ffa0020af5a9fbe80b82143"
    # oraios/serena@c6fbd1c: README.md:237; src/serena/cli.py:957,1067-1088.
    if serena.get("release") != pin or not any(f"git+https://github.com/oraios/serena@{pin}" in c
                                              for c in serena.get("commands", [])):
        bad("serena", "install plan must use the development pin already selected by stack/profile/architecture")
    if "serena project health-check" not in serena.get("acceptance", {}).get("post_install", {}).get("command", ""):
        bad("serena", "initialization alone does not accept symbol/reference navigation; the upstream health-check is required")
    if "after_sign_in" not in serena.get("acceptance", {}):
        bad("serena", "fresh Claude Code and Codex symbol/reference checks are required")

    # ast-grep/ast-grep@0.45.3: README.md:84; crates/cli/src/run.rs:349.
    structural = by_slot.get("structural-search", {}).get("acceptance", {}).get("post_install", {}).get("command", "")
    if "-r '$A?.()'" not in structural or "control.ts" not in structural:
        bad("structural-search", "the published rewrite example and its no-match control are required")

    mineru = by_slot.get("mineru", {})
    commands = "\n".join(mineru.get("commands", []))
    # opendatalab/MinerU@c221cc41: README.md:66,559-576; skills/mineru/SKILL.md:1.
    manifest_path = plan_dir / "config/mineru-skills-manifest.json"
    try:
        skill_manifest = json.loads(manifest_path.read_text())
        skill, = skill_manifest["skills"]
        skill_pin = "c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93"
        if (skill["name"] != "mineru" or skill["ref"] != skill_pin or skill["path"] != "skills/mineru"
                or skill["url"] != f"https://github.com/opendatalab/MinerU/tree/{skill_pin}/skills/mineru"
                or skill["tree_sha"] != "38d108595980854f65640d46ab27ecea002b549d"
                or skill["skill_md_sha256"] != "dec330a3549d232fed44db2b0c9bc0b64505a11d2526008ddf044b3f94681d96"
                or skill["claude_listing"] != "on" or skill["codex_enabled"] is not True
                or skill_manifest["cli"]["version"] != "1.7.0"):
            bad("mineru", "skill manifest must retain the verified upstream pin and both native client targets")
    except (OSError, ValueError, KeyError, TypeError):
        bad("mineru", "a valid scoped config/mineru-skills-manifest.json is required")
    if '--manifest "$plan_dir/config/mineru-skills-manifest.json"' not in commands:
        bad("mineru", "native skill wiring must use the pinned repository installer with the scoped manifest")
    order = [commands.find(c) for c in ("models download --tier standard", "models verify --tier standard",
                                       "config set parse_server.local.managed_tier standard",
                                       "config set parse_server.local.mode managed")]
    if -1 in order or order != sorted(order):
        bad("mineru", "download and verify Standard models before setting managed_tier and then managed mode")
    if (mineru.get("service") or {}).get("start") != "mineru server start":
        bad("mineru", "the upstream local server lifecycle is required")
    if not {"service_health", "after_sign_in"}.issubset(mineru.get("acceptance", {})):
        bad("mineru", "local Standard parse/read and fresh native client use are required")

def browser_contract(by_slot, install_funcs, bad):
    """Wave-5 browser owner; existing slot ID, one upstream stdio server in each client.

    ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df:
    docs/client-configurations.md:71,109; docs/troubleshooting.md:103-105;
    docs/advanced-usage.md:22-25; README.md:45,65; scripts/test.js:28-38.
    This is structural consistency, never destination acceptance or a new trial.
    """
    row = by_slot.get("playwright-cli", {})
    pin = "e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df"
    if (not row.get("installed") or row.get("measurement_only")
            or row.get("release") != "chrome-devtools-mcp-v1.10.1" or row.get("source_pin") != pin):
        bad("playwright-cli", "the wave-5 Chrome DevTools MCP 1.10.1 owner must install by default at its release commit")
    commands = row.get("commands", [])
    # The destination map is the sole registration writer (round-2 G2 handoff).
    # Like hcom's posture check, read the source map even for --plan-dir copies.
    source_root = pathlib.Path(__file__).resolve().parents[3]
    args = ["-y", "chrome-devtools-mcp@1.10.1", "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux"]
    try:
        additions = source_root / "adoption/new-wsl/templates"
        claude = json.loads((additions / "claude-user.mcp.additions.json").read_text())["mcpServers"]["chrome-devtools"]
        codex = tomllib.loads((additions / "codex.config.additions.toml").read_text())["mcp_servers"]["chrome-devtools"]
        mapping = json.loads((source_root / "adoption/new-wsl/client-config-map.json").read_text())
        for client, server in (("Claude Code", claude), ("Codex", codex)):
            if server.get("command") != "npx" or server.get("args") != args or server.get("type", "stdio") != "stdio":
                bad("playwright-cli", f"one mapped {client} stdio server with the required pin and flags is required")
        for piece in ("claude/mcp/server/chrome-devtools", "codex/config/mcp_servers.chrome-devtools.*"):
            entries = [e for e in mapping["entries"] if piece in e["match"]]
            if len(entries) != 1 or entries[0]["wiring"] != "slot:playwright-cli" or entries[0].get("owner") != row["owner"]:
                bad("playwright-cli", f"the destination map must wire {piece} through its wave-5 owner")
    except (OSError, ValueError, KeyError, TypeError):
        bad("playwright-cli", "mapped Chrome stdio server or client additions are missing")
    if any("mcp add chrome-devtools" in command for command in commands):
        bad("playwright-cli", "the client map owns registration; installer CLI registrations would add a second writer")
    if any("sudo" in command or "@playwright/cli" in command or "claude plugin" in command for command in commands):
        bad("playwright-cli", "privilege belongs to a declared prerequisite helper; no second browser/Claude plugin install")
    expected_integrity = "sha512-Klw6HWDqHC/XS1JwZldd2r49aUhbUJN9m9Mvcx4SEueIPXtzuQX+QelxAViobv8YUkDZ7HWDrmViR6LeYK0wAw=="
    if (row.get("checksum", {}).get("integrity") != expected_integrity
            or not any("npm view chrome-devtools-mcp@1.10.1 dist.integrity" in command for command in commands)):
        bad("playwright-cli", "the published npm SHA512 must be retained and compared with the native npx registry pin; no unused archive implies runtime verification")
    steps = row.get("prerequisite_steps", [])
    helper = install_funcs.get("chrome_devtools_linux_chrome", "")
    if (row.get("needs", {}).get("sudo") is not True
            or not any(step.get("name") == "chrome_devtools_linux_chrome"
                       and step.get("needs", {}).get("sudo") is True for step in steps)
            or "sudo apt-get install" not in helper
            or "sudo apt-get install -y --no-install-recommends google-chrome-stable ||" not in helper
            or "--with-colons --show-keys" not in helper
            or "Signed-By: /etc/apt/keyrings/google-chrome.asc EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796" not in helper
            or "chrome_devtools_linux_chrome ||" not in install_funcs.get("playwright-cli", "")):
        bad("playwright-cli", "Linux-side Google Chrome requires a declared and invoked privileged prerequisite")
    if (len(steps) != 1 or steps[0].get("command") != "chrome_devtools_linux_chrome"
            or steps[0].get("program") != helper):
        bad("playwright-cli", "privileged prerequisite declaration differs from the actual Chrome helper")
    if ("native-stack-google-chrome.sources" not in helper or 'repo_add_once="false"' not in helper
            or "google-chrome-stable=$" in helper):
        bad("playwright-cli", "current stable must use the separate restricted source with package repo creation disabled")
    post = row.get("acceptance", {}).get("post_install", {})
    if (post.get("kind") != "upstream tests" or "npm run test:no-build -- tests/index.test.ts" not in post.get("command", "")
            or "google-chrome-stable --version >" not in post.get("command", "")
            or 'dpkg --compare-versions "$installed_chrome" ge 154.0.8037.97-1' not in post.get("command", "")
            or "apt-cache madison google-chrome-stable" not in post.get("command", "")):
        bad("playwright-cli", "unchanged upstream browser tests and the installed Chrome version record are required")
    native = row.get("acceptance", {}).get("after_sign_in", {})
    if (not native.get("needs_user")
            or not all(name in native.get("command", "") for name in
                       ("navigate_page", "take_snapshot", "list_console_messages", "claude.jsonl", "codex.jsonl"))):
        bad("playwright-cli", "fresh native-client navigation/snapshot/console checks must remain gated on native sign-in")


def main():
    here = pathlib.Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan-dir", type=pathlib.Path, default=here)
    ap.add_argument("--manifest", type=pathlib.Path,
                    default=here.parent / "new-wsl-definitive-defaults-20261001" / "definitive-manifest.json")
    args = ap.parse_args()
    plan_dir = args.plan_dir.resolve()
    problems = []

    def bad(tag, message):
        problems.append(f"[{tag}] {message}")

    plan = json.loads((plan_dir / "install-plan.json").read_text())
    rows = plan["owners"]
    owners = json.loads((plan_dir / "owners.json").read_text())["owners"]
    manifest = {s["slot_id"]: s for s in json.loads(args.manifest.read_text())["slots"] if s["catalog"] == "foundation"}
    install_text, accept_text = (plan_dir / "install.sh").read_text(), (plan_dir / "accept.sh").read_text()
    install_funcs, accept_funcs = functions(install_text), functions(accept_text)

    slots = [r["slot"] for r in rows]
    for slot, count in collections.Counter(slots).items():
        if count > 1:
            bad("rows", f"slot {slot} appears {count} times in install-plan.json")
    selected = [r for r in rows if r["installed"]]
    measured = [r for r in rows if r.get("measurement_only")]
    excluded = [r for r in rows if not r["installed"] and not r.get("measurement_only")]
    # Native review is supplied by the installed clients. It installs no third
    # component, but its destination qualification must execute rather than skip.
    acceptance_only = [r for r in rows if r.get("acceptance_only")]
    for r in acceptance_only:
        if (r["slot"] != "cross-family-review" or r["installed"] or r.get("measurement_only")
                or r["route"] != "none" or r["commands"] or set(r["acceptance"]) != {"after_sign_in"}):
            bad("rows", f"row {r['slot']}: acceptance_only is reserved for native cross-family-review after sign-in")
    by_slot = {r["slot"]: r for r in rows}
    agent_messaging_contract(plan_dir, by_slot, bad)
    code_docs_contract(plan_dir, by_slot, bad)
    browser_contract(by_slot, install_funcs, bad)

    # Node rows must receive the runtime bootstrap even when selected alone.
    for flag in ("needs_execution", "needs_runtime"):
        bootstrapped = set()
        for match in re.finditer(r"for slot in (.*?); do selected \"\$slot\" && " + flag + r"=true; done", install_text):
            bootstrapped.update(shlex.split(match[1]))
        for r in selected:
            if r["needs"]["node"] and r["slot"] not in bootstrapped:
                bad("prerequisites", f"row {r['slot']}: Node requires the {flag} bootstrap")
    for slot, name, command in (
            ("mcp-inspector", "inspector_chromium_host_dependencies", "npx -y playwright@1.62.1 install-deps chromium"),
            ("betterleaks", "betterleaks_test_toolchain", "apt-get install -y --no-install-recommends build-essential")):
        row = by_slot[slot]
        steps = row.get("prerequisite_steps", [])
        if not (row["needs"]["sudo"] and any(s.get("name") == name and s.get("command") == command
                and s.get("needs", {}).get("sudo") is True for s in steps)):
            bad("prerequisites", f"row {slot}: declare its named privileged prerequisite")
        if command not in install_funcs.get(name, "") or not re.search(r"then " + name + r"; fi", install_text):
            bad("prerequisites", f"row {slot}: named prerequisite is not executed by install.sh")

    # The base image is already the execution environment. Its Canonical tests
    # are owed even though it installs no extra package and stays in owners.json
    # as installed=False. This exception applies only to the base-image slot.
    base_image = by_slot.get("base-distribution", {})
    inherited = [base_image] if base_image.get("environment_prerequisite") is True else []
    if not inherited or base_image.get("installed") or base_image.get("commands") or "post_install" not in base_image.get("acceptance", {}):
        bad("base-distribution", "base image must keep its no-install row and define Canonical post-install acceptance")

    # one row per foundation row of the manifest, with its layer, default and repository. A manifest row with an interim
    # (amendment 3 of the decision rule) is installed as its interim: the plan row names the interim's owner and repository,
    # and the row's decided default, which installs nothing, stays as the rounds recorded it. A row the owner added, or gave
    # an owner default (amendment 4), carries its owner's default and repository as the row's own.
    for slot in manifest:
        if slot not in by_slot:
            bad("manifest", f"manifest row {slot} has no row in install-plan.json")
    for r in rows:
        m = manifest.get(r["slot"])
        if m is None:
            bad("manifest", f"row {r['slot']} has no counterpart in the manifest's foundation rows")
            continue
        if r["layer"] != m["layer_id"]:
            bad("manifest", f"row {r['slot']}: layer {r['layer']!r} differs from the manifest's {m['layer_id']!r}")
        interim = m.get("interim")
        default, repository = (interim["default"], interim["repository"]) if interim else (m["default"], m["repository"])
        if not r.get("measurement_only") and (r["owner"], r["repository"]) != (default, repository):
            bad("manifest", f"row {r['slot']}: owner/repository differ from the manifest's "
                            + ("interim's default/repository" if interim else "default/repository"))
        state, outcome = m.get("state") or "open", (m.get("resolution") or {}).get("outcome")
        if r["installed"] and r.get("measurement_only"):
            bad("rows", f"row {r['slot']} is both installed and measurement_only")
        if interim:
            if not r["installed"]:
                bad("manifest", f"row {r['slot']}: the manifest records an interim install, and the plan does not install it")
        elif r["installed"]:
            if m["installs_nothing_extra"]:
                bad("manifest", f"selected row {r['slot']}: the manifest says it installs nothing extra")
            if outcome == "not_installed":
                bad("manifest", f"selected row {r['slot']}: the manifest outcome is not_installed")
            if state == "split":
                bad("manifest", f"selected row {r['slot']}: the manifest state is split")
        elif r.get("measurement_only") and state != "split":
            bad("manifest", f"measurement-only row {r['slot']}: the manifest state is {state}, not split")
        elif (not r.get("measurement_only") and not m["installs_nothing_extra"] and outcome != "not_installed"
              and state != "split" and r["slot"] not in ON_DEMAND):
            bad("manifest", f"row {r['slot']} is not installed, but the manifest says it installs ({state}, {outcome})")

    # owners.json follows install-plan.json
    if [(o["layer"], o["slot"], o["owner"], o["repository"], o["installed"], o.get("measurement_only", False)) for o in owners] != \
            [(r["layer"], r["slot"], r["owner"], r["repository"], r["installed"], r.get("measurement_only", False)) for r in rows]:
        bad("owners", "owners.json rows differ from install-plan.json rows (layer, slot, owner, repository, installed, measurement_only)")

    # Inspector is a pinned on-demand invocation, with acceptance but no persistent install function.
    helpers = {n for n, b in install_funcs.items() if n not in by_slot and any(x.strip().startswith("run_command ") for x in b.splitlines())}
    for r in rows:
        slot, active = r["slot"], r["installed"] or r.get("measurement_only")
        on_demand = slot in ON_DEMAND and bool(r["commands"])
        for script, funcs in (("install.sh", install_funcs), ("accept.sh", accept_funcs)):
            script_active = active or (script == "accept.sh" and (r in acceptance_only or on_demand or r in inherited))
            if script_active and slot not in funcs:
                label = "selected" if r["installed"] else "native-capability" if r in acceptance_only else "measurement-only"
                bad("functions", f"{label} row {slot} has no function in {script}")
            if not script_active and slot in funcs:
                bad("functions", f"row {slot} is not selected and not measurement_only, but {script} defines a function for it")
        if r["installed"] and "post_install" not in r["acceptance"]:
            bad("acceptance", f"selected row {slot} has no post-install acceptance")
        if not active and not on_demand and (r["commands"] or (r["acceptance"] and r not in acceptance_only and r not in inherited)):
            bad("rows", f"row {slot} is not installed but keeps commands or acceptance")
        if on_demand and (slot != "mcp-inspector" or not r["version_pinned"] or not r["needs"]["node"]
                          or r["commands"] != [f'npx -y @modelcontextprotocol/inspector@{r["release"]} --web']
                          or "post_install" not in r["acceptance"]):
            bad("rows", f"row {slot}: on-demand Inspector requires a pinned Web command, Node and post-install acceptance")

    # an interim install waits for the acknowledgements of the layer consensus's batches (wave2, wave3, ...): its install
    # function calls the gate before anything else, and the gate reads the owed acknowledgements. Only an interim row is
    # gated: a row whose owner default (amendment 4) replaced its interim carries none and installs on the owner's decision.
    gated = [r for r in rows if (manifest.get(r["slot"]) or {}).get("interim")]
    if gated and "acknowledgements_owed" not in install_funcs.get(GATE, ""):
        bad("interim", f"install.sh has no {GATE} function that reads the wave batches' acknowledgements_owed, the gate "
                       "every interim install calls first")
    for r in gated:
        body = [line.strip() for line in install_funcs.get(r["slot"], "").splitlines()
                if line.strip() and not line.strip().startswith("#")]
        if body[:1] != [f'{GATE} {r["slot"]} || return "$?"']:
            bad("interim", f"row {r['slot']}: its install function in install.sh does not call `{GATE} {r['slot']}` "
                           "before anything else, so an interim install would run while an acknowledgement is owed")
    for r in rows:
        if r not in gated and re.search(r"^\s*" + re.escape(GATE) + r"\b", install_funcs.get(r["slot"], ""), re.M):
            bad("interim", f"row {r['slot']}: its install function in install.sh calls `{GATE}`, but the manifest records no "
                           "interim for it")

    # commands and acceptance in the scripts are the ones in the JSON; every command has a source URL
    for r in rows:
        slot = r["slot"]
        if r["commands"] and not str((r.get("install_source") or {}).get("url", "")).startswith("https://"):
            bad("sources", f"row {slot} has commands but no install_source.url")
        for stage, entry in r["acceptance"].items():
            if stage not in STAGES:
                bad("acceptance", f"row {slot}: unknown acceptance stage {stage}")
            elif entry["kind"] == "unavailable":
                if entry.get("command") is not None or not entry.get("reason"):
                    bad("acceptance", f"row {slot} {stage}: an unavailable check has no command and needs a reason")
            elif not str((entry.get("source") or {}).get("url", "")).startswith("https://") or not entry.get("command"):
                bad("sources", f"row {slot} {stage}: acceptance lacks a command or a source URL")
        if slot in install_funcs and (r["installed"] or r.get("measurement_only")):
            if run_commands(slot, install_funcs, helpers) != r["commands"]:
                bad("sync", f"row {slot}: the run_command lines in install.sh differ from commands in install-plan.json")
            bodies = [install_funcs[slot]] + [install_funcs[h] for h in helpers if h in install_funcs and h in install_funcs[slot]]
            if sum(sourced(b, "run_command ") for b in bodies):
                bad("sources", f"row {slot}: a run_command in install.sh has no `Source: https://` comment above it")
        if slot in accept_funcs and (r["installed"] or r.get("measurement_only") or r in acceptance_only or r in inherited or (slot in ON_DEMAND and r["commands"])):
            try:
                found = checks_of(accept_funcs[slot])
            except ValueError as error:
                bad("sync", f"row {slot}: accept.sh function does not parse ({error})")
                continue
            want = {stage: (e["kind"], e["command"]) for stage, e in r["acceptance"].items() if e["kind"] != "unavailable"}
            got = {}
            for stage, name, kind, program in found:
                if name != slot:
                    bad("sync", f"row {slot}: accept.sh check names slot {name}")
                if stage in got:
                    bad("sync", f"row {slot}: accept.sh runs two checks in stage {stage}")
                got[stage] = (kind, program)
            if got != want:
                bad("sync", f"row {slot}: the check calls in accept.sh differ from acceptance in install-plan.json")
            if sourced(accept_funcs[slot], "check "):
                bad("sources", f"row {slot}: a check in accept.sh has no `Source: https://` comment above it")
            client_additional_checks(r, accept_funcs, bad)

    # --only lists and dispatch cover every row
    for script, text in (("install.sh", install_text), ("accept.sh", accept_text)):
        match = re.search(r"^case \"\$only\" in\n  ''\|([^)]*)\) ;;", text, re.M)
        if not match or match.group(1).split("|") != slots:
            bad("dispatch", f"{script}: the --only slot list is not the slots of install-plan.json, in order")
    for r in selected + measured:
        slot = r["slot"]
        dispatch = (r"^if (?:selected|named) '" + re.escape(slot)
                    + r"'; then run_slot '" + re.escape(slot) + r"';(?: |$)"
                    + r"|^measured_slot '?" + re.escape(slot) + r"'?(?:;|$)")
        # Existing native bootstrap/dependency guards also name the exact slot
        # they invoke. Keep these bounded forms; another slot's selector cannot
        # satisfy them (the original hcom-under-srt failure).
        dependency_dispatch = {
            "container-engine": r"^if \$needs_docker \|\| selected container-engine; then\n  run_slot container-engine(?:\n|$)",
            "docker-compose": r"^if \$needs_docker \|\| selected docker-compose; then run_slot docker-compose; fi$",
            "mise": r"^if \$needs_runtime \|\| selected mise; then\n(?:  #[^\n]*\n)*  mise\n",
        }.get(slot)
        if not re.search(dispatch, install_text, re.M) and not (
                dependency_dispatch and re.search(dependency_dispatch, install_text, re.M)):
            bad("dispatch", f"install.sh never runs row {slot}")
    for r in selected + measured + acceptance_only:
        slot = r["slot"]
        if f"== {slot} ]]; then {slot};" not in accept_text:
            bad("dispatch", f"accept.sh never runs row {slot}")
    on_demand_rows = [r for r in excluded if r["slot"] in ON_DEMAND and r["commands"]]
    for r in on_demand_rows:
        slot = r["slot"]
        if f'if [[ "$only" == {slot} ]]; then {slot}; elif [[ -z "$only" ]]; then skipped {slot}; fi' not in accept_text:
            bad("dispatch", f"accept.sh: on-demand row {slot} must run only when explicitly named")
    for r in inherited:
        if f"== {r['slot']} ]]; then {r['slot']};" not in accept_text:
            bad("base-distribution", "accept.sh never runs the base-image acceptance")
    loop = re.search(r"^for slot in ([^;]*); do\n  if \[\[ -z \"\$only\" \|\| \"\$only\" == \"\$slot\" \]\]; then skipped", accept_text, re.M)
    if not loop or [s.strip("'") for s in loop.group(1).split()] != [r["slot"] for r in excluded if r not in acceptance_only and r not in on_demand_rows and r not in inherited]:
        bad("dispatch", "accept.sh: the skipped-slot loop is not the rows that are neither installed nor measurement-only")
    # An installed row that install.sh runs only when named (the default run skips it) has its checks gated the same way.
    named_only = [r for r in selected
                  if re.search(r"^if named '" + re.escape(r["slot"]) + r"'; then run_slot '" + re.escape(r["slot"]) + r"';", install_text, re.M)]
    for r in named_only:
        slot = r["slot"]
        if f'if [[ "$only" == {slot} ]]; then {slot}; elif [[ -z "$only" ]]; then skipped {slot}; fi' not in accept_text:
            bad("dispatch", f"accept.sh checks row {slot} in the default run, but install.sh installs it only when named")
    # ... and the converse: accept.sh skips no installed row in the default run that install.sh installs by default.
    for r in selected:
        slot = r["slot"]
        if r not in named_only and f'if [[ "$only" == {slot} ]]; then {slot}; elif [[ -z "$only" ]]; then skipped {slot}; fi' in accept_text:
            bad("dispatch", f"accept.sh skips row {slot} in the default run, but install.sh installs it by default")

    # --list prints exactly the rows of install-plan.json
    proc = subprocess.run(["bash", str(plan_dir / "install.sh"), "--list"], capture_output=True, text=True, cwd=plan_dir, timeout=120)
    if proc.returncode != 0:
        bad("list", f"bash install.sh --list exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    printed = []
    for line in proc.stdout.splitlines():
        parts = line.split(" | ")
        printed.append((parts[0], " | ".join(parts[1:-2]), parts[-2], parts[-1]) if len(parts) >= 4 else (line, "", "", ""))
    expected = [(r["slot"], r["owner"], r["route"], "planned" if r["installed"] else "measurement-only" if r.get("measurement_only") else "excluded")
                for r in rows]
    if printed != expected:
        missing = [e[0] for e in expected if e not in printed]
        extra = [p[0] for p in printed if p not in expected]
        bad("list", f"--list prints {len(printed)} lines, install-plan.json has {len(expected)} rows; "
                    f"missing or different: {missing}; extra or different: {extra}" + ("" if missing or extra else "; same rows, different order"))

    # mise.toml tools belong to selected or measurement-only rows
    tools = tomllib.loads((plan_dir / "mise.toml").read_text()).get("tools", {})
    owned = {r.get("mise_tool"): r for r in selected + measured if r.get("mise_tool")}
    for tool in tools:
        if tool not in RUNTIME_PINS and tool not in owned:
            bad("mise", f"mise.toml tool {tool} belongs to no selected or measurement-only row")
    for tool, r in owned.items():
        if tool not in tools:
            bad("mise", f"row {r['slot']} names mise tool {tool}, which mise.toml does not pin")
        elif r["commands"][:1] != [f"mise use -g {tool}@{tools[tool]}"]:
            bad("mise", f"row {r['slot']}: its first command is not `mise use -g {tool}@{tools[tool]}` (the mise.toml pin)")
    for r in selected + measured:
        if r["route"] == "mise" and not r.get("mise_tool"):
            bad("mise", f"row {r['slot']} has route mise but names no mise_tool")

    # D-ollama: owner-approved native user-unit adaptation; no host apply here.
    # Source: Ollama v0.35.0 docs/linux.mdx:57-89; D-ollama-2 on-demand/30m owner ruling.
    ollama = by_slot.get("local-model-server", {})
    if not ollama.get("needs", {}).get("systemd_user_unit"):
        bad("local-model-server", "lasting GPU owner requires its user-unit prerequisite")
    native_enable = "systemctl --user daemon-reload && systemctl --user enable --now ollama.service"
    if native_enable not in ollama.get("commands", []):
        bad("local-model-server", "missing native daemon-reload and boot enable/start command")
    health = (ollama.get("acceptance", {}).get("service_health") or {}).get("command") or ""
    if "systemctl --user is-enabled ollama.service" not in health.splitlines():
        bad("local-model-server", "service_health must require boot-enabled ollama.service")
    if (health.splitlines()[:2] != ["systemctl --user is-enabled ollama.service",
                                    "systemctl --user is-active ollama.service"]
            or health.count("/api/embed") != 1 or health.count("/api/ps") != 1
            or health.index("/api/embed") > health.index("/api/ps")
            or '.size_vram == .size' not in health
            or 'qwen3-embedding-8k:latest' not in health):
        bad("local-model-server", "service_health must load the embedder on demand before its positive GPU-residency gate")
    if any("ollama-warmup.sh" in value for value in ollama.get("commands", []) + ollama.get("config_paths", [])):
        bad("local-model-server", "D-ollama-2 removes the warmup asset and all installer references")
    assets = {
        "ollama.service": "5e8e8bc42306f2d1ebc6da912e34daa28c6ce73eccf793d3155851733dccc6db",
    }
    for name, expected in assets.items():
        path = plan_dir / "config" / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            bad("local-model-server", f"{name} differs from its designated owner-approved bytes")
        if f"copy_config '{name}'" not in install_funcs.get("local-model-server", ""):
            bad("local-model-server", f"install function must place {name} through copy_config")

    # G4: these are plan contracts, not a claim that a host or a notification receiver passed.
    # Source: OTel v0.162.0 otelcol/command_validate.go:15; Grafana v13.2.3 query-editor/_index.md:47;
    # Alertmanager v0.34.1 docs/configuration.md:1939; Prometheus v3.15.0 unit_testing_rules.md:6.
    collector = by_slot.get("otel-collector-contrib", {})
    collector_check = collector.get("acceptance", {}).get("post_install", {}).get("command", "")
    if "NS2604_OBSERVABILITY_DATA=" not in collector_check:
        bad("observability", "otel-collector-contrib: validate must receive the service's data-directory environment")
    grafana = by_slot.get("grafana", {})
    if grafana.get("acceptance", {}).get("post_install", {}).get("kind") == "version only":
        bad("observability", "grafana: a version check cannot accept provisioned dashboards")
    dashboard_path = plan_dir / "config/grafana-token-layer.json"
    if not dashboard_path.is_file():
        bad("observability", "grafana: missing the provisioned token-layer dashboard")
    else:
        dashboard = json.loads(dashboard_path.read_text())
        hourly = [p for p in dashboard.get("panels", []) if any(
            "[1h]" in t.get("expr", "") and "claude_code_" in t.get("expr", "")
            for t in p.get("targets", []))]
        if len(hourly) != 6 or any(t.get("interval") != "1m" for p in hourly for t in p["targets"]):
            bad("observability", "grafana: all six hourly Claude panels must retain [1h] with a 1m minimum step")
    alerting = by_slot.get("alerting", {})
    alert_check = alerting.get("acceptance", {}).get("post_install", {}).get("command", "")
    if "check rules" not in alert_check or "test rules" not in alert_check:
        bad("observability", "alerting: acceptance must check and unit-test the Prometheus rules with promtool")
    if not alerting.get("needs_user") or "after_sign_in" not in alerting.get("acceptance", {}):
        bad("observability", "alerting: destination choice and an independently confirmed delivery are required")

    # Config files: service copy_config calls and direct, preserving tool-config installs both consume plan files.
    # Ports do not collide between rows. Only the install source operand counts, never an arbitrary filename mention.
    config = {p.name for p in (plan_dir / "config").iterdir()}
    copied = set(re.findall(r"copy_config '([^']+)'", install_text))
    commands = "\n".join(command for row in rows for command in row["commands"])
    copied.update(re.findall(r'install -m 0600 -- "\$plan_dir/config/([A-Za-z0-9._@-]+)" "[^"\n]+"', commands))
    # MinerU consumes its scoped skill manifest directly through the installer's native --manifest argument.
    if '--manifest "$plan_dir/config/mineru-skills-manifest.json"' in "\n".join(by_slot.get("mineru", {}).get("commands", [])):
        copied.add("mineru-skills-manifest.json")
    # The no-install base-image check consumes its script directly from the plan.
    # No other config asset is exempt from the existing installation check.
    base_acceptance = (base_image.get("acceptance", {}).get("post_install") or {}).get("command")
    if base_acceptance == 'bash "$plan_dir/config/base-distribution-accept.sh"':
        copied.add("base-distribution-accept.sh")
    elif inherited:
        bad("base-distribution", "base-image acceptance must consume config/base-distribution-accept.sh")
    for name in sorted(copied - config):
        bad("config", f"install.sh copies config/{name}, which does not exist")
    # Round-2 gpt-gateway-topology excludes local carries from the clean default.
    # Source: https://github.com/diegosouzapw/OmniRoute/pull/15167
    # These retained historical artifacts still support the canary regression
    # tests, but the published release row must neither install nor accept them.
    historical_gateway_configs = set()
    gateway = by_slot.get("gpt-gateway", {})
    if gateway.get("release") == "3.8.51" and not gateway.get("source_build"):
        historical_gateway_configs = {
            "omniroute-canary-check.py", "omniroute-canary-evidence.json", "omniroute-canary-install.sh",
        }
        if historical_gateway_configs & copied:
            bad("gpt-gateway", "published clean release must not install historical canary assets")
    for name in sorted(config - copied - historical_gateway_configs):
        bad("config", f"config/{name} is copied by no install function")
    claims = collections.defaultdict(set)
    # G4 configs wire existing listeners. Scrape/datasource/exporter targets and synthetic
    # promtool input-series labels are references, rather than additional listening sockets.
    observability_references = {
        "otel.yaml": {21300},
        "prometheus.yaml": {21090, 21093, 21888, 21889},
        "grafana-datasources.yaml": {21090, 21300, 21093},
        "prometheus-alerts.test.yaml": {21090, 21997},
    }
    for r in rows:
        if (r.get("service") or {}).get("port") is not None:
            claims[r["service"]["port"]].add(r["slot"])
        for path in r["config_paths"]:
            name = path.rsplit("/", 1)[-1]
            if name in config:
                config_text = (plan_dir / "config" / name).read_text()
                if r["slot"] == "research-harnesses" and name == "deer-flow-config.yaml":
                    # The embedded model consumes the gateway's base_url; it owns no listener.
                    config_text = "\n".join(line for line in config_text.splitlines()
                                            if not line.strip().startswith("base_url:"))
                for port in ports_in(config_text) - observability_references.get(name, set()):
                    if r["slot"] == "promptfoo" and name in ("promptfoo-gateway.yaml", "promptfoo-skills.json") and port == 21128:
                        # Promptfoo's apiBaseUrl consumes the gateway; its MCP uses STDIO and binds no port.
                        if (by_slot.get("gpt-gateway", {}).get("service") or {}).get("port") != port:
                            bad("ports", "Promptfoo's gateway client endpoint has no matching gateway service")
                        continue
                    claims[port].add(r["slot"])
    for port, who in sorted(claims.items()):
        if len(who) > 1:
            bad("ports", f"port {port} is claimed by rows {sorted(who)}")

    if problems:
        print("\n".join(problems))
        print(f"FAILED: {len(problems)} problem(s)")
        return 1
    additional_count = sum(len(entry.get("additional_checks", [])) for row in rows for entry in row["acceptance"].values())
    print(f"OK: {len(rows)} rows: {len(selected)} installed ({len(selected) - len(named_only)} by the default run, {len(named_only)} only when named), "
          f"{len(measured)} measurement-only, {len(excluded)} not installed; "
          f"{sum(len(r['commands']) for r in rows)} commands and {sum(len(r['acceptance']) for r in rows) + additional_count} acceptance entries agree with the scripts ({additional_count} additional checks included)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
