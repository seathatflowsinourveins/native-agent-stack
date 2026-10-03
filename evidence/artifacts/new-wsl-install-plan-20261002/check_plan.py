#!/usr/bin/env python3
"""Consistency checker for the new-WSL install plan. Standard library only (Python 3.11 or newer, for tomllib).

Reads install-plan.json, owners.json, install.sh, accept.sh, mise.toml, config/ and the merged definitive manifest, names every
disagreement and exits 1; prints one summary line and exits 0 when they agree. It runs `bash install.sh --list` (read-only) and
installs nothing.

usage: python3 -B check_plan.py [--plan-dir DIR] [--manifest PATH]
"""
import argparse
import collections
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
    by_slot = {r["slot"]: r for r in rows}

    # one row per foundation row of the manifest, with its layer, default and repository
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
        if not r.get("measurement_only") and (r["owner"], r["repository"]) != (m["default"], m["repository"]):
            bad("manifest", f"row {r['slot']}: owner/repository differ from the manifest's default/repository")
        state, outcome = m.get("state") or "open", (m.get("resolution") or {}).get("outcome")
        if r["installed"] and r.get("measurement_only"):
            bad("rows", f"row {r['slot']} is both installed and measurement_only")
        if r["installed"]:
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

    # functions: a row that installs (or is measurement-only) has an install function and an acceptance function; no other row has either
    helpers = {n for n, b in install_funcs.items() if n not in by_slot and any(x.strip().startswith("run_command ") for x in b.splitlines())}
    for r in rows:
        slot, active = r["slot"], r["installed"] or r.get("measurement_only")
        for script, funcs in (("install.sh", install_funcs), ("accept.sh", accept_funcs)):
            if active and slot not in funcs:
                bad("functions", f"{'selected' if r['installed'] else 'measurement-only'} row {slot} has no function in {script}")
            if not active and slot in funcs:
                bad("functions", f"row {slot} is not selected and not measurement_only, but {script} defines a function for it")
        if r["installed"] and "post_install" not in r["acceptance"]:
            bad("acceptance", f"selected row {slot} has no post-install acceptance")
        if not active and (r["commands"] or r["acceptance"]):
            bad("rows", f"row {slot} is not installed but keeps commands or acceptance")

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
        if slot in accept_funcs and (r["installed"] or r.get("measurement_only")):
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

    # --only lists and dispatch cover every row
    for script, text in (("install.sh", install_text), ("accept.sh", accept_text)):
        match = re.search(r"^case \"\$only\" in\n  ''\|([^)]*)\) ;;", text, re.M)
        if not match or match.group(1).split("|") != slots:
            bad("dispatch", f"{script}: the --only slot list is not the slots of install-plan.json, in order")
    for r in selected + measured:
        slot = r["slot"]
        if not re.search(r"(run_slot|measured_slot) '?" + re.escape(slot) + r"'?(;|$)|^\s+" + re.escape(slot) + r"$", install_text, re.M):
            bad("dispatch", f"install.sh never runs row {slot}")
        if f"== {slot} ]]; then {slot};" not in accept_text:
            bad("dispatch", f"accept.sh never runs row {slot}")
    loop = re.search(r"^for slot in ([^;]*); do\n  if \[\[ -z \"\$only\" \|\| \"\$only\" == \"\$slot\" \]\]; then skipped", accept_text, re.M)
    if not loop or [s.strip("'") for s in loop.group(1).split()] != [r["slot"] for r in excluded]:
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

    # config files: each copy_config target exists and every file is copied; ports do not collide between rows
    config = {p.name for p in (plan_dir / "config").iterdir()}
    copied = set(re.findall(r"copy_config '([^']+)'", install_text))
    for name in sorted(copied - config):
        bad("config", f"install.sh copies config/{name}, which does not exist")
    for name in sorted(config - copied):
        bad("config", f"config/{name} is copied by no install function")
    claims = collections.defaultdict(set)
    for r in rows:
        if (r.get("service") or {}).get("port") is not None:
            claims[r["service"]["port"]].add(r["slot"])
        for path in r["config_paths"]:
            name = path.rsplit("/", 1)[-1]
            if name in config:
                for port in ports_in((plan_dir / "config" / name).read_text()):
                    claims[port].add(r["slot"])
    for port, who in sorted(claims.items()):
        if len(who) > 1:
            bad("ports", f"port {port} is claimed by rows {sorted(who)}")

    if problems:
        print("\n".join(problems))
        print(f"FAILED: {len(problems)} problem(s)")
        return 1
    print(f"OK: {len(rows)} rows: {len(selected)} installed ({len(selected) - len(named_only)} by the default run, {len(named_only)} only when named), "
          f"{len(measured)} measurement-only, {len(excluded)} not installed; "
          f"{sum(len(r['commands']) for r in rows)} commands and {sum(len(r['acceptance']) for r in rows)} acceptance entries agree with the scripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
