#!/usr/bin/env python3
"""Stage 1: preconditions and builds, no sessions (pilot spec stage 1).

  python3 -B prepare.py --run-id <id> [--cells c1,c2] [--tasks item_id:INSTANCE,...] [--seed N] [--smoke]
                        [--skip-oracle-tests] [--skip-quota] [--allow-timing]

Creates RUNS_ROOT/<run_id>/ with: run.json (every frozen input and hash), harness/ (frozen copy of this directory's
code), launchers/<cell> shims, cells/<cell>/promptfooconfig.yaml (tests in seeded random order), codex-rules/,
settings templates, clone samples, s7/baseline.json and schedule.json. Prints one summary JSON line.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CODEX_HOME_REAL, FREEZE_COMMIT, HOME, LANE, LANE_PROMPTED, NEUTRAL_ROOT, PROTOCOL_ID, RUNS_ROOT, T_SECONDS,  # noqa: E402
                    TRIAL_ROOT_BASE,
                    gateway_build, load_json, newest_meter_reading, parse_stream_text, prior_allows, run, s7_snapshot,
                    sha256_bytes, sha256_file, sha256_json, utc_now, write_json)
import arms  # noqa: E402
import fixture  # noqa: E402
import suite  # noqa: E402

HARNESS_FILES = ("common.py", "suite.py", "fixture.py", "arms.py", "launcher.py", "sdk_claude.py", "sdk_codex.mjs",
                 "prepare.py", "block.py", "collect.py", "grade.py", "pilot.py", "stage2-canaries.json")
PROBE_HASHES = {"claude/CLAUDE.md": "b86ea2c4655637fa", "claude/settings.json": "861959ff0e49803f"}
BLACKOUTS = (("10:35", "10:55"), ("13:20", "13:45"))
GH_EMPTY = HOME / ".cache" / "ws-empty-config"   # neutral name: no experiment, tool, client, arm or task word


def repo_root() -> Path:
    return HERE.parents[3]


def in_blackout(now=None) -> bool:
    hhmm = time.strftime("%H:%M", time.gmtime(now or time.time()))
    return any(start <= hhmm < end for start, end in BLACKOUTS)


def config_settled(minutes: int = 30) -> dict:
    """Host configuration files unchanged for `minutes` (~/.claude.json churns with every session and is excluded)."""
    paths = [HOME / ".claude/settings.json", HOME / ".claude/CLAUDE.md", CODEX_HOME_REAL / "config.toml",
             CODEX_HOME_REAL / "AGENTS.md", CODEX_HOME_REAL / "hooks.json", CODEX_HOME_REAL / "omniroute.config.toml"]
    newest = max(p.stat().st_mtime for p in paths if p.exists())
    age = (time.time() - newest) / 60
    return {"newest_change_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest)), "age_min": round(age, 1),
            "settled": age >= minutes}


def binaries() -> dict:
    claude_link = HOME / ".local/bin/claude"
    codex_link = HOME / ".local/bin/codex"
    claude_real, codex_real = os.path.realpath(claude_link), os.path.realpath(codex_link)
    out = {
        "claude": {"path": claude_real, "realpath": claude_real, "link": str(claude_link).replace(str(HOME), "~"),
                   "version": run([claude_real, "--version"], timeout=60).stdout.decode().strip(),
                   "sha256": sha256_file(claude_real)},
        "codex": {"path": codex_real, "realpath": codex_real, "link": str(codex_link).replace(str(HOME), "~"),
                  "version": run([codex_real, "--version"], timeout=60).stdout.decode().strip(),
                  "sha256": sha256_file(codex_real)},
        "python": sys.executable,
        "node": shutil.which("node") or "node",
        "promptfoo": (run(["promptfoo", "--version"], timeout=120).stdout.decode().strip().splitlines() or [""])[-1],
        "claude_sdk_python": str(HOME / ".local/share/new-wsl-native-stack/tools/claude-agent-sdk/bin/python"),
        "codex_sdk_dir": str(HOME / ".local/share/new-wsl-native-stack/tools/codex-sdk/node_modules/@openai/codex-sdk"),
    }
    sdk_pkg = Path(out["codex_sdk_dir"]) / "package.json"
    out["codex_sdk_version"] = load_json(sdk_pkg).get("version") if sdk_pkg.exists() else None
    return out


def host_fanout() -> dict:
    settings = load_json(HOME / ".claude/settings.json")
    env = settings.get("env") or {}
    keys = ("CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH",
            "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
    return {**{k: env.get(k) for k in keys}, "teammateMode": settings.get("teammateMode"),
            "permissions.defaultMode": (settings.get("permissions") or {}).get("defaultMode")}


def reference_init() -> dict | None:
    """The newest Claude system/init event on this host (tool names for the R2 (b) lexicon)."""
    from common import V1_ROOT
    candidates = sorted([p for p in RUNS_ROOT.glob("*/raw/*.stream.jsonl") if not p.parts[-3].startswith("selftest-")]
                        + list(V1_ROOT.glob("**/*claude*.out")), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[:20]:
        for event in parse_stream_text(path.read_text(encoding="utf-8", errors="replace")):
            if isinstance(event, dict) and event.get("type") == "system" and event.get("subtype") == "init":
                return event
    return None


def harness_agent_items(lex_names: list[str]) -> dict:
    """Which user agent definitions (harness-authored, ~/.claude/agents) name which items (R1 tag 3)."""
    out = {}
    for path in sorted((HOME / ".claude/agents").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        named = sorted(n for n in lex_names if len(n) >= 3 and re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text))
        out[path.stem] = named
    return out


def yaml_quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def promptfoo_config(root: Path, cell: str, tests: list[dict]) -> str:
    lines = [f"description: {yaml_quote(f'{PROTOCOL_ID} {root.name} {cell}')}",
             "prompts:", "  - '{{task_text}}'",
             "providers:", f"  - id: {yaml_quote('exec: ' + str(root / 'launchers' / cell))}",
             f"    label: {yaml_quote(cell)}", "    config:", f"      basePath: {yaml_quote(str(root))}", "      maxRetries: 0",
             "tests:"]
    for test in tests:
        lines.append(f"  - description: {yaml_quote(test['description'])}")
        lines.append("    metadata:")
        lines.append(f"      test_key: {yaml_quote(test['test_key'])}")
        lines.append("    vars:")
        for key in ("task_id", "instance", "arm", "cell", "sandbox", "network", "lane", "prompt_sha256", "task_text"):
            lines.append(f"      {key}: {yaml_quote(str(test[key]))}")
    return "\n".join(lines) + "\n"


def app_server_config(root: Path, trial_id: str, test: dict, fixture_dir: Path, clone: Path, gh_dir: Path) -> str:
    """CL7b: promptfoo's own openai:codex-app-server provider, one provider entry (and config) per trial."""
    otel = f"ecosystem.task.id={trial_id},ecosystem.lane={test['lane']},service.instance.id={trial_id}"
    from common import login_path as _login_path
    login_path = _login_path()
    cfg = [f"description: {yaml_quote(f'{PROTOCOL_ID} {root.name} codex-app-server {trial_id}')}",
           "prompts:", "  - '{{task_text}}'", "providers:",
           "  - id: openai:codex-app-server", f"    label: {yaml_quote('codex-app-server ' + trial_id)}", "    config:",
           f"      codex_path_override: {yaml_quote(os.path.realpath(HOME / '.local/bin/codex'))}",
           f"      working_dir: {yaml_quote(str(fixture_dir))}", "      skip_git_repo_check: true", "      ephemeral: false",
           "      reuse_server: false", "      approval_policy: never", f"      sandbox_mode: {yaml_quote(test['sandbox'])}",
           "      network_access_enabled: false", "      model: gpt-6.1-sol", "      model_reasoning_effort: max",
           f"      turn_timeout_ms: {T_SECONDS * 1000}", "      cli_config:", "        profile: omniroute",
           "        service_tier: default", "        otel:", f"          environment: {yaml_quote(trial_id)}",
           "      cli_env:", f"        CODEX_HOME: {yaml_quote(str(clone))}", "        OMNIROUTE_API_KEY: local-loopback",
           f"        OTEL_RESOURCE_ATTRIBUTES: {yaml_quote(otel)}", f"        PATH: {yaml_quote(login_path)}",
           f"        HOME: {yaml_quote(str(HOME))}", "tests:", f"  - description: {yaml_quote(test['description'])}",
           "    metadata:", f"      test_key: {yaml_quote(test['test_key'])}", f"      trial_id: {yaml_quote(trial_id)}", "    vars:"]
    for key in ("task_id", "instance", "arm", "cell", "sandbox", "network", "lane", "prompt_sha256", "task_text"):
        cfg.append(f"      {key}: {yaml_quote(str(test[key]))}")
    return "\n".join(cfg) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cells", default=",".join(suite.CELLS))
    parser.add_argument("--tasks", default="", help="restrict to item_id:INSTANCE pairs (comma-separated)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--lane", default=LANE)
    parser.add_argument("--repo", default=str(repo_root()))
    parser.add_argument("--suite", default=str(suite.SUITE_PATH))
    parser.add_argument("--skip-oracle-tests", action="store_true")
    parser.add_argument("--skip-quota", action="store_true")
    parser.add_argument("--allow-timing", action="store_true", help="record, but do not refuse, a blackout or unsettled host")
    parser.add_argument("--force-fixture", action="store_true")
    parser.add_argument("--prompted", default=None, help="JSON list of prompted runs (stage 2 and 3): "
                        "[{key, cell, prompt, sandbox?, task_id?, instance?}]; lane organic-e2e-prompted")
    parser.add_argument("--skip-tests", default="", help="test keys to leave out (comma-separated), e.g. the give-way "
                        "rule's G1|claude-sdk when a Claude probe is required")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.run_id):
        parser.error("run id: letters, digits, dot, underscore and hyphen")
    root = RUNS_ROOT / args.run_id
    if (root / "run.json").exists():
        parser.error(f"run root exists: {root}")
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 2**31)
    repo = Path(args.repo)
    timing = {"blackout": in_blackout(), "settled": config_settled(), "at": utc_now()}
    if (timing["blackout"] or not timing["settled"]["settled"]) and not args.allow_timing:
        print(json.dumps({"refused": "timing", **timing}))
        return 2
    for sub in ("harness", "launchers", "cells", "codex-rules", "raw", "draft", "manifests", "s7", "clone-samples",
                "promptfoo-home", "loki", "rollouts", "transcripts", "gateway", "agentsview", "call-ledgers", "grades"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    # The neutral per-run trial root: settings, prompts, -o files, CODEX_HOME clones and the SDK launchers, whose paths
    # reach a client's argv or environment (a process listing shows them), so R2 (f) applies to them.
    import secrets as _secrets
    TRIAL_ROOT_BASE.mkdir(parents=True, exist_ok=True)
    trial_root = TRIAL_ROOT_BASE / _secrets.token_hex(4)
    while trial_root.exists():
        trial_root = TRIAL_ROOT_BASE / _secrets.token_hex(4)
    for sub in ("settings", "prompts", "last", "clones", "bin"):
        (trial_root / sub).mkdir(parents=True, exist_ok=True)
    os.chmod(trial_root, 0o700)
    # Freeze the harness code into the run root.
    harness_hashes = {}
    for name in HARNESS_FILES:
        src = HERE / name
        if src.exists():
            shutil.copy2(src, root / "harness" / name)
            harness_hashes[name] = sha256_file(src)
    # The quota gate's script, frozen beside the harness (§9.2 runs it before every Codex block).
    shutil.copy2(repo / "scripts/codex_quota.py", root / "harness" / "codex_quota.py")
    harness_hashes["codex_quota.py (scripts/)"] = sha256_file(repo / "scripts/codex_quota.py")
    # SDK launchers under neutral names in the trial root (CL6 runs on the base interpreter with the SDK venv's
    # site-packages first on sys.path; CL7 imports the SDK through a neutral symlink).
    sdk_venv_site = sorted((HOME / ".local/share/new-wsl-native-stack/tools/claude-agent-sdk/lib").glob("python3*/site-packages"))
    header = f"import sys\nsys.path.insert(0, {json.dumps(str(sdk_venv_site[0]))})\n" if sdk_venv_site else ""
    (trial_root / "bin" / "run.py").write_text(header + (HERE / "sdk_claude.py").read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy2(HERE / "sdk_codex.mjs", trial_root / "bin" / "run.mjs")
    sdk_dir = HOME / ".local/share/new-wsl-native-stack/tools/codex-sdk/node_modules/@openai/codex-sdk"
    if sdk_dir.exists():
        os.symlink(sdk_dir, trial_root / "bin" / "sdk")
    # Suite, amendments, lexicon.
    loaded = suite.load_suite(Path(args.suite))
    items, amend_log = suite.amend(loaded["items"])
    tasks = suite.pilot_tasks(items)
    init = reference_init()
    tool_functions = sorted({t.split("__", 2)[2] for t in (init or {}).get("tools", []) if t.startswith("mcp__") and t.count("__") >= 2})
    tools_by_server = {}
    for tool in (init or {}).get("tools", []):
        if tool.startswith("mcp__") and tool.count("__") >= 2:
            _, server, function = tool.split("__", 2)
            tools_by_server.setdefault(server, []).append(function)
    lex = suite.lexicon(items, tool_functions)
    roots = [HOME / ".agents/skills", HOME / ".claude/plugins/cache", CODEX_HOME_REAL / "skills", CODEX_HOME_REAL / "plugins/cache"]
    descriptions = suite.skill_descriptions(roots)
    lex["skill_names"] = sorted(descriptions)
    lex["task_words"] = sorted({t["item"].lower() for t in tasks} | {t["key"].lower() for t in tasks})
    # Fixture (template, strip, gate, setup, tar, oracles, registry candidates).
    fx = fixture.build(repo, lex_names=lex["names"], run_tests=not args.skip_oracle_tests, force=args.force_fixture)
    if not fx["gate"]["pass"] or not fx["gate_after_setup"]["pass"]:
        print(json.dumps({"refused": "fixture gate", "gate": fx["gate"]}))
        return 2
    # R2 lint over every pilot prompt and the launch strings a model can see.
    lint = {}
    for task in tasks:
        lint[f"{task['task_id']}:{task['instance']}"] = suite.lint_text(task["prompt"], lex, descriptions)
    sample_cwd, sample_name = f"~/.cache/{NEUTRAL_ROOT.name}/0a1b2c3d", "s-0a1b2c3d"
    lint["launch_strings"] = suite.lint_text(f"{sample_cwd} {sample_name}", lex, launch_string=True)
    # Claude settings and Codex rules.
    credential = arms.committed_credential_denies(repo, FREEZE_COMMIT)
    deny = arms.deny_list(credential)
    claude_settings = {arm: arms.claude_settings(arm, deny) for arm in ("native", "env")}
    rules_text = arms.codex_rules_text()
    (root / "codex-rules" / "organic-e2e.rules").write_text(rules_text, encoding="utf-8")
    bins = binaries()
    rules_check = arms.verify_codex_rules(root / "codex-rules" / "organic-e2e.rules", bins["codex"]["path"])
    GH_EMPTY.mkdir(parents=True, exist_ok=True)
    os.chmod(GH_EMPTY, 0o500)
    clone_samples = {}
    for arm in ("native", "env"):
        dest = root / "clone-samples" / arm
        clone_samples[arm] = arms.build_clone(dest, arm, GH_EMPTY, rules_text)
    # S7 baseline, probe rule, meter, quota, gateway.
    baseline = s7_snapshot({"fixture_tar": fx["tar"]["path"]})
    write_json(root / "s7" / "baseline.json", baseline, 0o600)
    probe_required = any(not (baseline["files"].get(label) or "").startswith(prefix) for label, prefix in PROBE_HASHES.items())
    meter = newest_meter_reading()
    quota = {"skipped": True}
    if not args.skip_quota:
        proc = run(["python3", "-B", str(repo / "scripts/codex_quota.py"), "--json", "--gate", "70"], timeout=120,
                   env={k: v for k, v in os.environ.items() if k != "CODEX_HOME"})
        try:
            snapshot = json.loads(proc.stdout.decode() or "{}")
        except ValueError:
            snapshot = {}
        quota = {"rc": proc.returncode, "used_percent": snapshot.get("used_percent"),
                 "secondary_used_percent": (snapshot.get("secondary") or {}).get("used_percent"),
                 "gate": snapshot.get("gate"), "checked_at_utc": snapshot.get("checked_at_utc")}
    # Cells, tests and promptfoo configs.
    wanted_cells = [c for c in args.cells.split(",") if c]
    wanted_tasks = {tuple(t.split(":", 1)) for t in args.tasks.split(",") if t}
    rng = random.Random(seed)
    by_key = {(t["task_id"], t["instance"]): t for t in tasks}
    plan = []
    for cell in wanted_cells:
        spec = suite.CELLS[cell]
        tests = []
        for item_id, instance, sandbox in spec["tasks"]:
            if wanted_tasks and (item_id, instance) not in wanted_tasks:
                continue
            task = by_key[(item_id, instance)]
            tests.append({"description": f"{task['key']}|{cell}", "test_key": f"{task['key']}|{cell}",
                          "task_id": item_id, "instance": instance, "arm": spec["arm"], "cell": cell,
                          "sandbox": sandbox if spec["client"] == "codex" else "none",
                          "network": "off" if spec["client"] == "codex" else "available", "lane": args.lane,
                          "prompt_sha256": task["prompt_sha256"], "task_text": task["prompt"]})
        plan.append((cell, spec, tests))
    # Prompted runs (stage 2 probes and canaries, stage 3 oracle runs): their own cells on lane organic-e2e-prompted,
    # their own fixtures, never organic (R10). Entries: {key, cell (a base cell), prompt, sandbox?, task_id?, instance?}.
    prompted_tasks = []
    if args.prompted:
        grouped = {}
        for entry in load_json(Path(args.prompted)):
            base = suite.CELLS[entry["cell"]]
            name = f"prompted-{entry['cell']}"
            prompt = entry["prompt"]
            task_id, instance = entry.get("task_id") or f"prompted/{entry['key']}", entry.get("instance") or "X"
            digest = sha256_bytes(prompt.encode())
            prompted_tasks.append({"task_id": task_id, "instance": instance, "key": entry["key"], "item": entry["key"],
                                   "kind": "prompted", "prompt": prompt, "prompt_sha256": digest})
            grouped.setdefault(name, (dict(base), []))[1].append({
                "description": f"{entry['key']}|{name}", "test_key": f"{entry['key']}|{name}", "task_id": task_id,
                "instance": instance, "arm": base["arm"], "cell": name,
                "sandbox": entry.get("sandbox", "read-only") if base["client"] == "codex" else "none",
                "network": "off" if base["client"] == "codex" else "available", "lane": LANE_PROMPTED,
                "prompt_sha256": digest, "task_text": prompt})
        for name, (spec, tests) in grouped.items():
            spec.update({"repeat": 1, "pilot_block": "stage 2/3 (prompted)", "lane": LANE_PROMPTED})
            plan.append((name, spec, tests))
    skip = {k for k in args.skip_tests.split(",") if k}
    cells, schedule = {}, []
    for cell, spec, tests in plan:
        tests = [t for t in tests if t["test_key"] not in skip]
        if not tests:
            continue
        rng.shuffle(tests)
        cell_dir = root / "cells" / cell
        cell_dir.mkdir(parents=True, exist_ok=True)
        record = {k: v for k, v in spec.items() if k != "tasks"}
        record.update({"model": "opus" if spec["client"] == "claude" else "gpt-6.1-sol",
                       "tier": "default", "route": "claude-code native sign-in" if spec["client"] == "claude"
                       else "OmniRoute 127.0.0.1:21128 profile omniroute", "tests": [t["test_key"] for t in tests]})
        if spec["kind"] == "app-server":
            record["trials"] = []
            from fixture import extract_fixture
            import uuid as _uuid
            for index, test in enumerate(tests):
                trial_id = str(_uuid.uuid4())
                fixture_dir = extract_fixture(Path(fx["tar"]["path"]), fx["tar"]["sha256"])
                clone = trial_root / "clones" / trial_id
                clone_record = arms.build_clone(clone, spec["arm"], GH_EMPTY, rules_text)
                sub = cell_dir / f"t{index}"
                sub.mkdir(exist_ok=True)
                text = app_server_config(root, trial_id, test, fixture_dir, clone, GH_EMPTY)
                (sub / "promptfooconfig.yaml").write_text(text, encoding="utf-8")
                record["trials"].append({"trial_id": trial_id, "test_key": test["test_key"], "config": str(sub / "promptfooconfig.yaml"),
                                         "config_sha256": sha256_bytes(text.encode()), "fixture_private": str(fixture_dir),
                                         "clone_gate": clone_record["gate"]})
                from common import append_jsonl
                append_jsonl(root / "ledger.jsonl", {"run_id": args.run_id, "trial_id": trial_id, "cell": cell,
                                                     "client": "codex", "arm": spec["arm"], "task": test["task_id"],
                                                     "instance": test["instance"], "lane": args.lane, "phase": "pre-launch",
                                                     "at": utc_now(), "prebuilt_by": "stage 1 (CL7b has no launcher)",
                                                     "fixture_private": str(fixture_dir), "clone": clone_record,
                                                     "hashes": {"fixture_tar": fx["tar"]["sha256"], "prompt": test["prompt_sha256"]}})
        else:
            text = promptfoo_config(root, cell, tests)
            (cell_dir / "promptfooconfig.yaml").write_text(text, encoding="utf-8")
            record["config_sha256"] = sha256_bytes(text.encode())
            shim = root / "launchers" / cell
            shim.write_text(f"#!/bin/sh\nexec {sys.executable} -B {root / 'harness' / 'launcher.py'} {cell} \"$@\"\n")
            os.chmod(shim, 0o755)
            record["launcher_sha256"] = sha256_file(shim)
        cells[cell] = record
        for test in tests:
            schedule.append({"cell": cell, "client": spec["client"], "test_key": test["test_key"]})
    # Claude order: G1 first (the meter-reading trial), the rest in seeded random order across the Claude cells.
    claude = [s for s in schedule if s["client"] == "claude"]
    first = [s for s in claude if s["test_key"].startswith("G1|claude-native")]
    rest = [s for s in claude if s not in first]
    rng.shuffle(rest)
    claude_order = first + rest
    codex_order = [s for s in schedule if s["client"] == "codex"]
    write_json(root / "schedule.json", {"seed": seed, "claude": claude_order, "codex_blocks": sorted({s["cell"] for s in codex_order})})
    tasks_frozen = [{k: v for k, v in t.items()} for t in tasks if not wanted_tasks or (t["task_id"], t["instance"]) in wanted_tasks]
    tasks_frozen += prompted_tasks
    write_json(root / "tasks.json", {"amendments": amend_log, "tasks": tasks_frozen})
    write_json(root / "registry.json", load_json(Path(fx["dir"]) / "routing-registry.json"), 0o600)
    run_json = {
        "run_id": args.run_id, "protocol": PROTOCOL_ID, "created_at": utc_now(), "seed": seed, "lane": args.lane,
        "repo": str(repo), "repo_head": fixture.git(repo, "rev-parse", "HEAD").decode().strip(),
        "trial_root": str(trial_root),
        "protocol_file_sha256": sha256_file(HERE.parent / "PROTOCOL-v1.1.md") if (HERE.parent / "PROTOCOL-v1.1.md").exists() else None,
        "pilot_spec_file_sha256": sha256_file(HERE.parent / "PILOT-SPEC-v1.1.md") if (HERE.parent / "PILOT-SPEC-v1.1.md").exists() else None,
        "harness_sha256": harness_hashes, "binaries": bins, "host_fanout": host_fanout(), "timing": timing,
        "suite": {"path": loaded["path"], "sha256": loaded["sha256"], "sha_matches_protocol": loaded["sha_matches_protocol"],
                  "amended_sha256": sha256_json(items), "amendments": amend_log},
        "tasks_sha256": sha256_json(tasks_frozen),
        "fixture": {"record": str(Path(fx["dir"]) / "fixture.json"), "tar_path": fx["tar"]["path"], "tar_sha256": fx["tar"]["sha256"],
                    "tar_bytes": fx["tar"]["bytes"], "template_manifest_path": str(Path(fx["dir"]) / "template-manifest.json"),
                    "template_manifest_sha256": fx["template_manifest_sha256"], "commit": fx["commit"],
                    "gate": fx["gate_after_setup"], "experiment_check": fx["experiment_check"], "setup_gaps": fx["setup_gaps"],
                    "oracles_path": str(Path(fx["dir"]) / "oracles.json"), "oracles_sha256": fx["oracles_sha256"],
                    "reused": fx.get("reused", False)},
        "registry": {"path": str(root / "registry.json"), "sha256": fx["registry_sha256"], "counts": fx["registry_counts"],
                     "status": "provisional (hint-reader review pending)"},
        "lexicon": lex, "lint": lint, "harness_agents": harness_agent_items(lex["names"]), "tools_by_server": tools_by_server,
        "claude_settings": claude_settings, "claude_settings_sha256": {a: sha256_json(s) for a, s in claude_settings.items()},
        "credential_denies_source_sha256": credential["source_sha256"],
        "codex_rules_sha256": sha256_bytes(rules_text.encode()), "codex_rules_check": rules_check,
        "clone_samples": clone_samples, "gh_config_dir": str(GH_EMPTY),
        "s7_baseline": str(root / "s7" / "baseline.json"), "probe_required": probe_required,
        "baseline_hash_prefixes": {k: (baseline["files"].get(k) or "")[:16] for k in PROBE_HASHES} | {
            "codex/AGENTS.md": (baseline["files"].get("codex/AGENTS.md") or "")[:16]},
        "meter_stage1": {k: v for k, v in (meter or {}).items() if k != "source_private"} or None,
        "meter_stage1_allows": prior_allows(meter), "quota_stage1": quota, "gateway_build": gateway_build(),
        "cells": cells, "schedule": str(root / "schedule.json"),
        "unavailable_cells": suite.UNAVAILABLE_CELLS, "label_vector_sha256": None,
        "labels": "pending: R4 labels come from the other model family before any trajectory (coordinator)",
        "hint_read": "pending: cross-family hint reader (coordinator)",
    }
    run_sha = write_json(root / "run.json", run_json, 0o600)
    summary = {"run_root": str(root), "run_json_sha256": run_sha, "seed": seed, "cells": {c: len(v["tests"]) for c, v in cells.items()},
               "fixture_tar_sha256": fx["tar"]["sha256"], "fixture_reused": fx.get("reused", False), "gate": fx["gate_after_setup"]["pass"],
               "experiment_check": fx["experiment_check"], "rules_check": {k: rules_check[k] for k in ("probes", "passed", "pass")},
               "clone_gates": {a: r["gate"]["pass"] for a, r in clone_samples.items()}, "probe_required": probe_required,
               "lint_hits": {k: len(v) for k, v in lint.items() if v}, "meter_allows": prior_allows(meter),
               "quota": quota.get("rc"), "gateway_build": run_json["gateway_build"], "timing": timing}
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
