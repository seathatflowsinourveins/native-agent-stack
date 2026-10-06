#!/usr/bin/env python3
"""Stage 1: preconditions and builds, no sessions (pilot spec stage 1).

  python3 -B prepare.py --run-id <id> [--cells c1,c2] [--tasks item_id:INSTANCE,...] [--seed N] [--prompted file]
                        [--claude-completion censor-at-T|complete-at-result --amendment-ref TEXT]
                        [--claude-grace-s N] [--claude-t-seconds N] [--registry-review file]
                        [--allow-provisional-registry] [--repeat-override K] [--skip-oracle-tests] [--skip-quota]
                        [--allow-timing]

Creates RUNS_ROOT/<run_id>/ with run.json (every frozen input and hash), harness/ (frozen copy of this directory's
code), codex-rules/, settings templates, clone samples, s7/baseline.json and schedule.json; and a neutral trial root
(~/.cache/wsr/<8 hex>/) holding everything whose path or name reaches a process listing: per-trial settings, prompts,
-o files and CODEX_HOME clones, the stubs bin/l.py (launcher), bin/b.py (block) and bin/p.py (pilot) that import the
frozen harness through bin/.r, one shim bin/<cell code> per cell, bin/r (a link to promptfoo's entry point), and the
promptfoo configs p/<cell code>.yaml whose tests carry only an opaque ref and the task text. Cells and tests map back
through run.json cell_codes and tests_by_ref. Prints one summary JSON line.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import secrets
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CLAUDE_SESSION_CAP, CODEX_HOME_REAL, FREEZE_COMMIT, HOME, LANE, LANE_PROMPTED, NEUTRAL_ROOT,  # noqa: E402
                    POST_RESULT_GRACE_S, PROTOCOL_ID, RUNS_ROOT, T_SECONDS, TRIAL_ROOT_BASE, append_jsonl, gateway_build,
                    load_json, login_path, newest_meter_reading, parse_stream_text, prior_allows, run, s7_snapshot,
                    sha256_bytes, sha256_file, sha256_json, utc_now, write_json)
import arms  # noqa: E402
import fixture  # noqa: E402
import suite  # noqa: E402

HARNESS_FILES = ("common.py", "suite.py", "fixture.py", "arms.py", "launcher.py", "sdk_claude.py", "sdk_codex.mjs",
                 "prepare.py", "block.py", "collect.py", "grade.py", "pilot.py", "stage2-canaries.json")
PROBE_HASHES = {"claude/CLAUDE.md": "b86ea2c4655637fa", "claude/settings.json": "861959ff0e49803f"}
BLACKOUTS = (("10:35", "10:55"), ("13:20", "13:45"))
GH_EMPTY = HOME / ".cache" / "ws-empty-config"   # neutral name: no experiment, tool, client, arm or task word
PROMPTFOO_ENTRY = HOME / ".local/share/codex-ecosystem/bin/promptfoo"
STUB = '''import sys
from pathlib import Path
_root = Path((Path(__file__).resolve().parent / ".r").read_text(encoding="utf-8").strip())
sys.path.insert(0, str(_root / "harness"))
{body}
'''
STUB_BODIES = {
    "l.py": "import launcher\nsys.exit(launcher.main(sys.argv))",
    "b.py": "import block\nsys.exit(block.main(['--run-root', str(_root)] + sys.argv[1:]))",
    "p.py": "import pilot\nsys.exit(pilot.main(['--run-id', _root.name, '--from-stub'] + sys.argv[1:]))",
}


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
    node = shutil.which("node") or "node"
    out = {
        "claude": {"path": claude_real, "realpath": claude_real, "link": str(claude_link).replace(str(HOME), "~"),
                   "version": run([claude_real, "--version"], timeout=60).stdout.decode().strip(),
                   "sha256": sha256_file(claude_real)},
        "codex": {"path": codex_real, "realpath": codex_real, "link": str(codex_link).replace(str(HOME), "~"),
                  "version": run([codex_real, "--version"], timeout=60).stdout.decode().strip(),
                  "sha256": sha256_file(codex_real)},
        "python": sys.executable,
        # The real node binary: the ecosystem's node link sits in a directory whose name is a client word, and node's
        # path appears in the argv of the runner and the CL7 launcher.
        "node": os.path.realpath(node), "node_real": os.path.realpath(node),
        "promptfoo": (run(["promptfoo", "--version"], timeout=120).stdout.decode().strip().splitlines() or [""])[-1],
        "promptfoo_entry": os.path.realpath(PROMPTFOO_ENTRY) if PROMPTFOO_ENTRY.exists() else None,
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


# Keys every Codex launch sets itself (CL3's -m and -c model_reasoning_effort; CL7's model and modelReasoningEffort;
# CL7b's model and model_reasoning_effort), so the profile layer below leaves them out.
PROFILE_KEYS_SET_BY_LAUNCH = ("model", "model_reasoning_effort")


def codex_profile_layer(profile: str = "omniroute") -> dict:
    """The omniroute profile as --config overrides for the cells whose client cannot pass --profile (CL7, CL7b).

    codex-cli 0.160.0 selects a profile only with `-p/--profile <name>`, which layers $CODEX_HOME/<name>.config.toml over
    config.toml (`codex exec --help`); `profile = "omniroute"` given through --config is refused ("legacy `profile =
    \"omniroute\"` config is no longer supported; use `--profile omniroute` with `omniroute.config.toml` instead",
    smoke-20261005f CL7 and CL7b). @openai/codex-sdk 0.160.0 builds `codex exec` with --config, --model, --sandbox and
    --cd only (dist/index.js CodexExec.run), and promptfoo 0.123.1's openai:codex-app-server passes cli_config as -c
    pairs (codex-app-server-B9-ncut6.js buildAppServerArgs); `codex app-server --help` lists no --profile. So those two
    cells carry the profile file's own keys, minus the keys each launch sets, at the --config layer, which sits above the
    profile layer CL3 gets from -p: every key resolves to the same value. The profile file is the host's, the same
    bytes as each clone's copy (clone gate copies_match_host)."""
    import tomllib
    path = CODEX_HOME_REAL / f"{profile}.config.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    layer = {k: v for k, v in data.items() if k not in PROFILE_KEYS_SET_BY_LAUNCH}
    return {"profile": profile, "source": str(path).replace(str(HOME), "~"), "sha256": sha256_file(path),
            "omitted": [k for k in PROFILE_KEYS_SET_BY_LAUNCH if k in data], "config": layer}


def promptfoo_config(work: Path, code: str, tests: list[dict]) -> str:
    """One exec: provider (the cell's neutral shim) and the cell's tests. A test carries only its opaque ref and the
    task text: promptfoo passes the whole test case to the launcher's argv (finding 10)."""
    lines = [f"description: {yaml_quote(code)}",
             "prompts:", "  - '{{task_text}}'",
             "providers:", f"  - id: {yaml_quote('exec: ' + str(work / 'bin' / code))}",
             f"    label: {yaml_quote(code)}", "    config:", f"      basePath: {yaml_quote(str(work))}", "      maxRetries: 0",
             "tests:"]
    for test in tests:
        lines += [f"  - description: {yaml_quote(test['ref'])}", "    metadata:", f"      ref: {yaml_quote(test['ref'])}",
                  "    vars:", f"      ref: {yaml_quote(test['ref'])}", f"      task_text: {yaml_quote(test['task_text'])}"]
    return "\n".join(lines) + "\n"


def app_server_config(code: str, trial_id: str, test: dict, fixture_dir: Path, clone: Path, gh_dir: Path,
                      path_value: str, t_seconds: int = T_SECONDS, profile_layer: dict | None = None) -> str:
    """CL7b: promptfoo's own openai:codex-app-server provider, one provider entry (and config) per trial. cli_config is
    the omniroute profile layer (codex_profile_layer: app-server takes no --profile) plus the CL3 overrides, written as
    one YAML flow mapping (JSON) that promptfoo flattens into -c key=value pairs."""
    otel = f"ecosystem.task.id={trial_id},ecosystem.lane={test['lane']},service.instance.id={trial_id}"
    # model_reasoning_effort here as well as in the provider's turn settings: CL3 sets it with -c, which is the thread
    # default codex.conversation_starts reports (devcheck-cl7-20261006a: without it the app-server thread started at the
    # host config's ultra while each turn asked for max).
    cli_config = {**((profile_layer or {}).get("config") or {}), "model_reasoning_effort": "max", "service_tier": "default",
                  "otel": {"environment": trial_id}}
    cfg = [f"description: {yaml_quote(code)}",
           "prompts:", "  - '{{task_text}}'", "providers:",
           "  - id: openai:codex-app-server", f"    label: {yaml_quote(code)}", "    config:",
           f"      codex_path_override: {yaml_quote(os.path.realpath(HOME / '.local/bin/codex'))}",
           f"      working_dir: {yaml_quote(str(fixture_dir))}", "      skip_git_repo_check: true", "      ephemeral: false",
           "      reuse_server: false", "      approval_policy: never", f"      sandbox_mode: {yaml_quote(test['sandbox'])}",
           "      network_access_enabled: false", "      model: gpt-6.1-sol", "      model_reasoning_effort: max",
           f"      turn_timeout_ms: {t_seconds * 1000}", f"      cli_config: {json.dumps(cli_config, sort_keys=True)}",
           "      cli_env:", f"        CODEX_HOME: {yaml_quote(str(clone))}", "        OMNIROUTE_API_KEY: local-loopback",
           f"        GH_CONFIG_DIR: {yaml_quote(str(gh_dir))}",
           f"        OTEL_RESOURCE_ATTRIBUTES: {yaml_quote(otel)}", f"        PATH: {yaml_quote(path_value)}",
           f"        HOME: {yaml_quote(str(HOME))}", "tests:", f"  - description: {yaml_quote(test['ref'])}",
           "    metadata:", f"      ref: {yaml_quote(test['ref'])}", "    vars:",
           f"      ref: {yaml_quote(test['ref'])}", f"      task_text: {yaml_quote(test['task_text'])}"]
    return "\n".join(cfg) + "\n"


def _normalized_oracles(oracles: dict) -> dict:
    """The oracle values G12 compares: timing out (computed_at, the unittest run's elapsed seconds)."""
    out = {k: v for k, v in oracles.items() if k != "computed_at"}
    tests = out.get("mcp_server/both/context-mode.P1")
    if isinstance(tests, dict):
        ran = re.search(r"Ran (\d+) tests?", tests.get("ran") or "")
        out["mcp_server/both/context-mode.P1"] = {**{k: v for k, v in tests.items() if k != "ran"},
                                                  "tests_ran": int(ran.group(1)) if ran else None}
    return out


def reproduce_oracles(fx: dict, run_tests: bool) -> dict:
    """G12: recompute the D oracles inside a fresh extraction of the hashed template tarball and compare them with the
    frozen ones (stage 1). The scratch extraction is removed afterwards; trial fixtures are never touched."""
    frozen = load_json(Path(fx["dir"]) / "oracles.json")
    scratch = Path(fx["dir"]) / f"g12-{secrets.token_hex(4)}"
    try:
        fixture.extract_tar(Path(fx["tar"]["path"]), scratch)
        again = fixture.compute_oracles(scratch, run_tests=run_tests)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    a, b = _normalized_oracles(frozen), _normalized_oracles(again)
    differing = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return {"pass": not differing, "differing": differing, "compared": len(set(a) | set(b)),
            "tests_run": run_tests, "frozen_sha256": fx.get("oracles_sha256"), "at": utc_now()}


def write_stubs(work: Path, root: Path) -> dict:
    """The neutral entry points (bin/l.py, b.py, p.py) and bin/.r, the one place that names the run root."""
    bin_dir = work / "bin"
    (bin_dir / ".r").write_text(str(root) + "\n", encoding="utf-8")
    os.chmod(bin_dir / ".r", 0o600)
    hashes = {}
    for name, body in STUB_BODIES.items():
        text = STUB.format(body=body)
        (bin_dir / name).write_text(text, encoding="utf-8")
        hashes[name] = sha256_bytes(text.encode())
    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cells", default=",".join(c for c in suite.CELLS if c != "codex-native-gate0"))
    parser.add_argument("--tasks", default="", help="restrict to item_id:INSTANCE pairs (comma-separated); "
                        "cell@item_id:INSTANCE restricts a pair to one cell")
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
    parser.add_argument("--no-gate0", action="store_true", help="leave out the stage-2 gate-0 cell (self-tests only)")
    parser.add_argument("--claude-completion", choices=("censor-at-T", "complete-at-result"), default=None,
                        help="what a Claude result event before T means; needs --amendment-ref (finding 3)")
    parser.add_argument("--claude-grace-s", type=int, default=POST_RESULT_GRACE_S)
    parser.add_argument("--claude-t-seconds", type=int, default=T_SECONDS,
                        help="the run's T for every cell, CL7b's turn timeout included (another value needs --amendment-ref)")
    parser.add_argument("--amendment-ref", default=None, help="the CC amendment the completion policy or T rests on")
    parser.add_argument("--registry-review", default=None, help="JSON {reviewed: [paths], reviewer, at}: the hint "
                        "reader's reviewed routing-file registry; organic trials refuse while it is provisional")
    parser.add_argument("--allow-provisional-registry", action="store_true",
                        help="development smoke only: let organic trials run on the provisional registry (recorded)")
    parser.add_argument("--repeat-override", type=int, default=None, help="every cell's repeat (smoke runs)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.run_id):
        parser.error("run id: letters, digits, dot, underscore and hyphen")
    if (args.claude_completion or args.claude_t_seconds != T_SECONDS) and not args.amendment_ref:
        parser.error("a completion policy or a T other than the protocol's 900 s needs --amendment-ref")
    root = RUNS_ROOT / args.run_id
    if (root / "run.json").exists():
        parser.error(f"run root exists: {root}")
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 2**31)
    repo = Path(args.repo)
    timing = {"blackout": in_blackout(), "settled": config_settled(), "at": utc_now()}
    if (timing["blackout"] or not timing["settled"]["settled"]) and not args.allow_timing:
        print(json.dumps({"refused": "timing", **timing}))
        return 2
    # Prompted entries: refuse a base cell that no stage runs (finding 14).
    prompted_entries = load_json(Path(args.prompted)) if args.prompted else []
    bad = [e.get("key") for e in prompted_entries if e.get("cell") not in suite.PROMPTED_BASE_CELLS]
    if bad:
        print(json.dumps({"refused": "prompted entries name a base cell no stage runs", "keys": bad,
                          "allowed": list(suite.PROMPTED_BASE_CELLS)}))
        return 2
    wanted_cells = [c for c in args.cells.split(",") if c]
    if "codex-native" in wanted_cells and not args.no_gate0 and "codex-native-gate0" not in wanted_cells:
        wanted_cells.append("codex-native-gate0")
    # --tasks entries: item_id:INSTANCE (every selected cell) or cell@item_id:INSTANCE (that cell only).
    wanted_tasks, cell_tasks = set(), {}
    for entry in (t for t in args.tasks.split(",") if t):
        cell_part, _, task_part = entry.rpartition("@")
        pair = tuple(task_part.split(":", 1))
        if cell_part:
            cell_tasks.setdefault(cell_part, set()).add(pair)
        else:
            wanted_tasks.add(pair)
    restricted = bool(wanted_tasks or cell_tasks)

    def task_selected(cell: str, item_id: str, instance: str) -> bool:
        return not restricted or (item_id, instance) in wanted_tasks or (item_id, instance) in cell_tasks.get(cell, set())

    skip = {k for k in args.skip_tests.split(",") if k}
    # The Claude cap holds before anything is built (finding 4): organic and prompted Claude tests together.
    organic_claude = sum((args.repeat_override or suite.CELLS[cell]["repeat"])
                         for cell in wanted_cells if suite.CELLS[cell]["client"] == "claude"
                         for item_id, instance, _ in suite.CELLS[cell]["tasks"]
                         if task_selected(cell, item_id, instance)
                         and f"{suite.task_key(item_id, instance)}|{cell}" not in skip)
    prompted_claude = sum(1 for e in prompted_entries if suite.CELLS[e["cell"]]["client"] == "claude"
                          and f"{e['key']}|prompted-{e['cell']}" not in skip)
    if organic_claude + prompted_claude > CLAUDE_SESSION_CAP:
        print(json.dumps({"refused": "claude schedule exceeds the session cap", "organic": organic_claude,
                          "prompted": prompted_claude, "cap": CLAUDE_SESSION_CAP}))
        return 2
    registry_review = load_json(Path(args.registry_review)) if args.registry_review else None
    for sub in ("harness", "cells", "codex-rules", "raw", "draft", "manifests", "s7", "clone-samples",
                "loki", "rollouts", "transcripts", "gateway", "agentsview", "call-ledgers", "grades"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    # The neutral per-run trial root: everything whose path or name reaches a process listing or a client's argv.
    TRIAL_ROOT_BASE.mkdir(parents=True, exist_ok=True)
    work = TRIAL_ROOT_BASE / secrets.token_hex(4)
    while work.exists():
        work = TRIAL_ROOT_BASE / secrets.token_hex(4)
    for sub in ("settings", "prompts", "last", "clones", "bin", "p", "o", "h"):
        (work / sub).mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
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
    stub_hashes = write_stubs(work, root)
    # SDK launchers under neutral names in the trial root (CL6 runs on the base interpreter with the SDK venv's
    # site-packages first on sys.path; CL7 imports the SDK through a neutral symlink).
    sdk_venv_site = sorted((HOME / ".local/share/new-wsl-native-stack/tools/claude-agent-sdk/lib").glob("python3*/site-packages"))
    header = f"import sys\nsys.path.insert(0, {json.dumps(str(sdk_venv_site[0]))})\n" if sdk_venv_site else ""
    (work / "bin" / "run.py").write_text(header + (HERE / "sdk_claude.py").read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy2(HERE / "sdk_codex.mjs", work / "bin" / "run.mjs")
    sdk_dir = HOME / ".local/share/new-wsl-native-stack/tools/codex-sdk/node_modules/@openai/codex-sdk"
    if sdk_dir.exists():
        os.symlink(sdk_dir, work / "bin" / "sdk")
    bins = binaries()
    if not bins.get("promptfoo_entry"):
        print(json.dumps({"refused": "promptfoo entry point not found"}))
        return 2
    os.symlink(bins["promptfoo_entry"], work / "bin" / "r")
    # Interpreters under neutral names: the host's runtime manager names an item, and the interpreter path is argv[0]
    # of every harness process a trial can list (launcher, runner, block, pilot, the CL6 and CL7 launchers).
    os.symlink(os.path.realpath(sys.executable), work / "bin" / "py")
    os.symlink(bins["node_real"], work / "bin" / "n")
    bins["python_neutral"], bins["node_neutral"] = str(work / "bin" / "py"), str(work / "bin" / "n")
    path_value = login_path()
    # The omniroute profile as --config overrides for CL7 and CL7b (their clients cannot pass --profile), frozen here;
    # bin/c.json is what the CL7 launcher reads (a neutral name: its path reaches the launcher's argv).
    profile_layer = codex_profile_layer()
    profile_layer["file"] = str(work / "bin" / "c.json")
    profile_layer["file_sha256"] = write_json(work / "bin" / "c.json", profile_layer["config"], 0o600)
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
    # Fixture (template, strip, gate, setup, tar, oracles, registry candidates) and G12.
    fx = fixture.build(repo, lex_names=lex["names"], run_tests=not args.skip_oracle_tests, force=args.force_fixture)
    if not fx["gate"]["pass"] or not fx["gate_after_setup"]["pass"]:
        print(json.dumps({"refused": "fixture gate", "gate": fx["gate"]}))
        return 2
    g12 = reproduce_oracles(fx, run_tests=not args.skip_oracle_tests)
    # Routing-file registry: provisional (pattern candidates under the protocol's example globs) until the hint
    # reader's reviewed list comes in through --registry-review.
    registry = load_json(Path(fx["dir"]) / "routing-registry.json")
    registry_status = {"status": "provisional", "allow_provisional": bool(args.allow_provisional_registry)}
    if registry_review is not None:
        manifest = load_json(Path(fx["dir"]) / "template-manifest.json")
        reviewed = sorted(set(registry_review.get("reviewed") or []))
        missing = [p for p in reviewed if p not in manifest]
        if missing or not reviewed:
            print(json.dumps({"refused": "registry review names paths outside the template", "missing": missing[:20]}))
            return 2
        registry.update({"reviewed": reviewed, "review": {k: registry_review.get(k) for k in ("reviewer", "at", "basis")},
                         "review_source_sha256": sha256_file(args.registry_review)})
        registry_status = {"status": "reviewed", "allow_provisional": False, "reviewed": len(reviewed)}
    registry_sha = write_json(root / "registry.json", registry, 0o600)
    # R2 lint over every pilot prompt and the launch strings a model can see.
    lint = {}
    for task in tasks:
        lint[f"{task['task_id']}:{task['instance']}"] = suite.lint_text(task["prompt"], lex, descriptions)
    sample = (f"~/.cache/{NEUTRAL_ROOT.name}/0a1b2c3d s-0a1b2c3d {str(work).replace(str(HOME), '~')}/prompts/x.txt "
              f"{str(work).replace(str(HOME), '~')}/bin/0a1b2c3d {str(GH_EMPTY).replace(str(HOME), '~')}")
    lint["launch_strings"] = suite.lint_text(sample, lex, launch_string=True)
    # Claude settings and Codex rules.
    credential = arms.committed_credential_denies(repo, FREEZE_COMMIT)
    deny = arms.deny_list(credential)
    claude_settings = {arm: arms.claude_settings(arm, deny) for arm in ("native", "env")}
    rules_text = arms.codex_rules_text()
    (root / "codex-rules" / "organic-e2e.rules").write_text(rules_text, encoding="utf-8")
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
    rng = random.Random(seed)
    by_key = {(t["task_id"], t["instance"]): t for t in tasks}
    used_tokens: set[str] = set()

    def token() -> str:
        while True:
            value = secrets.token_hex(4)
            if value not in used_tokens and not re.fullmatch(r"[0-9]+", value):
                used_tokens.add(value)
                return value

    plan = []
    for cell in wanted_cells:
        spec = suite.CELLS[cell]
        tests = []
        for item_id, instance, sandbox in spec["tasks"]:
            if not task_selected(cell, item_id, instance) and not spec.get("gate_trial"):
                continue
            task = by_key[(item_id, instance)]
            tests.append({"description": f"{task['key']}|{cell}", "test_key": f"{task['key']}|{cell}",
                          "task_id": item_id, "instance": instance, "arm": spec["arm"], "cell": cell,
                          "sandbox": sandbox if spec["client"] == "codex" else "none",
                          "network": "off" if spec["client"] == "codex" else "available", "lane": args.lane,
                          "prompt_sha256": task["prompt_sha256"], "task_text": task["prompt"],
                          "kind": "gate0" if spec.get("gate_trial") else "organic",
                          "gate_trial": bool(spec.get("gate_trial")), "stage": spec.get("stage", 4)})
        plan.append((cell, dict(spec), tests))
    # Prompted runs (stage 2 probes and canaries, stage 3 oracle runs): their own cells on lane organic-e2e-prompted,
    # their own fixtures, never organic (R10). Entries: {key, cell (a base cell), prompt, sandbox?, task_id?, instance?}.
    prompted_tasks = []
    grouped = {}
    for entry in prompted_entries:
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
            "prompt_sha256": digest, "task_text": prompt, "kind": "prompted", "gate_trial": False, "stage": 2,
            "probe_key": entry["key"]})
    for name, (spec, tests) in grouped.items():
        spec.update({"repeat": 1, "pilot_block": "stage 2/3 (prompted)", "lane": LANE_PROMPTED, "stage": 2})
        plan.append((name, spec, tests))
    cells, schedule, tests_by_ref, cell_codes = {}, [], {}, {}
    for cell, spec, tests in plan:
        tests = [t for t in tests if t["test_key"] not in skip]
        if not tests:
            continue
        rng.shuffle(tests)
        code = token()
        cell_codes[code] = cell
        for test in tests:
            test["ref"] = token()
            tests_by_ref[test["ref"]] = {k: v for k, v in test.items() if k not in ("task_text", "description")}
        cell_dir = root / "cells" / cell
        cell_dir.mkdir(parents=True, exist_ok=True)
        record = {k: v for k, v in spec.items() if k != "tasks"}
        if args.repeat_override:
            record["repeat"] = args.repeat_override
        record.update({"code": code, "model": "opus" if spec["client"] == "claude" else "gpt-6.1-sol",
                       "tier": "default", "route": "claude-code native sign-in" if spec["client"] == "claude"
                       else "OmniRoute 127.0.0.1:21128 profile omniroute", "tests": [t["test_key"] for t in tests],
                       "refs": [t["ref"] for t in tests]})
        if spec["kind"] == "app-server":
            record["trials"] = []
            import uuid as _uuid
            for index, test in enumerate(tests):
                trial_id = str(_uuid.uuid4())
                fixture_dir = fixture.extract_fixture(Path(fx["tar"]["path"]), fx["tar"]["sha256"])
                clone = work / "clones" / trial_id
                clone_record = arms.build_clone(clone, spec["arm"], GH_EMPTY, rules_text)
                text = app_server_config(code, trial_id, test, fixture_dir, clone, GH_EMPTY, path_value, args.claude_t_seconds,
                                         profile_layer)
                neutral = work / "p" / f"{code}-t{index}.yaml"
                neutral.write_text(text, encoding="utf-8")
                record["trials"].append({"trial_id": trial_id, "ref": test["ref"], "test_key": test["test_key"],
                                         "config_neutral": str(neutral), "config_sha256": sha256_bytes(text.encode()),
                                         "fixture_private": str(fixture_dir), "clone_gate": clone_record["gate"]})
                append_jsonl(root / "ledger.jsonl", {"run_id": args.run_id, "trial_id": trial_id, "cell": cell,
                                                     "client": "codex", "arm": spec["arm"], "task": test["task_id"],
                                                     "instance": test["instance"], "lane": test["lane"], "ref": test["ref"],
                                                     "test_key": test["test_key"], "phase": "pre-launch",
                                                     "at": utc_now(), "prebuilt_by": "stage 1 (CL7b has no launcher)",
                                                     "fixture_private": str(fixture_dir), "clone": clone_record,
                                                     "hashes": {"fixture_tar": fx["tar"]["sha256"], "prompt": test["prompt_sha256"]}})
                append_jsonl(root / "ledger.jsonl", {"run_id": args.run_id, "trial_id": trial_id, "cell": cell,
                                                     "client": "codex", "phase": "prepared", "at": utc_now(),
                                                     "ref": test["ref"], "fixture_private": str(fixture_dir), "clone": clone_record})
        else:
            text = promptfoo_config(work, code, tests)
            (work / "p" / f"{code}.yaml").write_text(text, encoding="utf-8")
            record["config_sha256"] = sha256_bytes(text.encode())
            shim = work / "bin" / code
            shim.write_text(f"#!/bin/sh\nexec {work / 'bin' / 'py'} -B {work / 'bin' / 'l.py'} {code} \"$@\"\n")
            os.chmod(shim, 0o755)
            record["launcher_sha256"] = sha256_file(shim)
        cells[cell] = record
        for test in tests:
            schedule.append({"cell": cell, "code": code, "client": spec["client"], "ref": test["ref"],
                             "test_key": test["test_key"], "stage": test["stage"], "kind": test["kind"]})
    claude_sessions = sum(cells[s["cell"]]["repeat"] for s in schedule if s["client"] == "claude")
    if claude_sessions > CLAUDE_SESSION_CAP:
        print(json.dumps({"refused": "claude schedule exceeds the session cap", "claude_sessions": claude_sessions}))
        return 2
    # Claude order: G1 first (the meter-reading trial), the rest in seeded random order across the Claude cells; the
    # stage-2 Claude probe runs before stage 4 (pilot.py gate 0).
    claude = [s for s in schedule if s["client"] == "claude" and s["stage"] == 4]
    first = [s for s in claude if s["test_key"].startswith("G1|claude-native")]
    rest = [s for s in claude if s not in first]
    rng.shuffle(rest)
    write_json(root / "schedule.json", {"seed": seed, "claude": first + rest,
                                        "claude_stage2": [s for s in schedule if s["client"] == "claude" and s["stage"] == 2],
                                        "codex_stage2": [s for s in schedule if s["client"] == "codex" and s["stage"] == 2],
                                        "codex_blocks": sorted({s["cell"] for s in schedule if s["client"] == "codex" and s["stage"] == 4})})
    selected_pairs = wanted_tasks | {pair for pairs in cell_tasks.values() for pair in pairs}
    tasks_frozen = [{k: v for k, v in t.items()} for t in tasks if not restricted or (t["task_id"], t["instance"]) in selected_pairs
                    or (t["task_id"], t["instance"]) == ("control/both/G1", "N")]
    tasks_frozen += prompted_tasks
    write_json(root / "tasks.json", {"amendments": amend_log, "tasks": tasks_frozen})
    completion = {"policy": args.claude_completion or "censor-at-T", "grace_s": args.claude_grace_s,
                  "t_seconds": args.claude_t_seconds, "amendment": args.amendment_ref,
                  "decided": bool(args.claude_completion and args.amendment_ref)}
    run_json = {
        "run_id": args.run_id, "protocol": PROTOCOL_ID, "created_at": utc_now(), "seed": seed, "lane": args.lane,
        "repo": str(repo), "repo_head": fixture.git(repo, "rev-parse", "HEAD").decode().strip(),
        "trial_root": str(work), "stub_sha256": stub_hashes, "login_path": path_value,
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
        "oracles_reproduce": g12,
        "registry": {"path": str(root / "registry.json"), "sha256": registry_sha, "counts": fx["registry_counts"],
                     **registry_status},
        "lexicon": lex, "lint": lint, "harness_agents": harness_agent_items(lex["names"]), "tools_by_server": tools_by_server,
        "claude_settings": claude_settings, "claude_settings_sha256": {a: sha256_json(s) for a, s in claude_settings.items()},
        "credential_denies_source_sha256": credential["source_sha256"],
        "codex_rules_sha256": sha256_bytes(rules_text.encode()), "codex_rules_check": rules_check,
        "codex_profile_layer": profile_layer,
        "clone_samples": clone_samples, "gh_config_dir": str(GH_EMPTY), "gh_readonly_account": None,
        "s7_baseline": str(root / "s7" / "baseline.json"), "probe_required": probe_required,
        "baseline_hash_prefixes": {k: (baseline["files"].get(k) or "")[:16] for k in PROBE_HASHES} | {
            "codex/AGENTS.md": (baseline["files"].get("codex/AGENTS.md") or "")[:16]},
        "meter_stage1": {k: v for k, v in (meter or {}).items() if k != "source_private"} or None,
        "meter_stage1_allows": prior_allows(meter), "quota_stage1": quota, "gateway_build": gateway_build(),
        "claude_session_cap": CLAUDE_SESSION_CAP, "claude_completion": completion,
        "cells": cells, "cell_codes": cell_codes, "tests_by_ref": tests_by_ref, "schedule": str(root / "schedule.json"),
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
               "quota": quota.get("rc"), "gateway_build": run_json["gateway_build"], "timing": timing,
               "g12": {k: g12[k] for k in ("pass", "differing")}, "registry": registry_status,
               "claude_completion": completion, "claude_sessions": claude_sessions}
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
