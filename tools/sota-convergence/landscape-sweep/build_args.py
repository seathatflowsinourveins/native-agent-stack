#!/usr/bin/env python3
"""Stage a landscape-sweep run into its work directory and write the compact Workflow args.

  build_args.py --work-dir W --sweep-id landscape-sweep-YYYYMMDD --date YYYY-MM-DD
                [--layers id,id,... | --due-report report.json] [--smoke LAYER_ID]
                [--stars PATH | --no-stars] [--gpt6-model gpt-6-astra] [--slots 3] [--lock-dir DIR]
                [--quota-stop-percent PERCENT] [--skills-checked-at YYYY-MM-DD] [--no-embed] [--force]

Needs <work-dir>/layers.json and <work-dir>/inputs/ from build_inputs.py. Writes into the work dir:
  templates.json         the repository templates with <<DATE>>, <<LAYER_COUNT>> and <<SKILLS_CHECKED_AT>> filled
                         (the skills date is adoption/skills/manifest.json checked_at); frozen for the run
  prompts_sha256.txt     sha256 of json.dumps(templates, sort_keys=True, ensure_ascii=False): the record's
                         prompts_sha256
  schemas/               discover, votes and critic (the workers' strict return schemas) and probe
  codex_call.sh, codex_job.py, make_prompt.py, codex_quota.py
                         the GPT-6 runtime the wrapper agents call, copied so a checkout change mid-run cannot
                         alter a running sweep (codex_quota.py is the checkout's scripts/codex_quota.py, the quota
                         probe codex_job.py runs when codex.quota_stop_percent is set)
  prompts/gpt6-discover-<layer>.txt, prompts/gpt6-probe.txt
                         the first-round GPT-6 discovery prompts and a one-call lane probe
  staged.json            provenance (harness commit and file hashes, skills, prompts_sha256) and the GPT-6 settings
                         codex_job.py reads (model, slots, lock dir, and quota_stop_percent only when
                         --quota-stop-percent is given: the quota gate is off by default)
  args.json              the Workflow args: {S, stars, sweep_id, T, schemas, layers: [{layer_id, catalog}], test?}
  sweep.embedded.js      sweep.js with its one `const A = args` line replaced by those args, launched as
                         Workflow({scriptPath: "<work-dir>/sweep.embedded.js"}) with no args, so the ~12 KB of
                         templates and schemas never pass through the coordinator's context and a resume needs
                         only the scriptPath (--no-embed skips it)
Refuses a work dir inside a git repository, templates naming a skill the pinned skills manifest lacks, and restaging
a work dir whose gpt6/ already holds jobs (an earlier run's "already done" jobs would be reused) unless --force.
No network, no model calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_prompt  # noqa: E402
from sweep_common import REPO_ROOT, load_json, prompts_sha256, sha256_bytes, work_dir, write_json  # noqa: E402

RUNTIME = ("codex_call.sh", "codex_job.py", "make_prompt.py")
QUOTA_PROBE = REPO_ROOT / "scripts" / "codex_quota.py"  # staged beside codex_job.py as codex_quota.py
SCHEMAS = ("discover", "votes", "critic", "probe")
SKILLS_MANIFEST = "adoption/skills/manifest.json"
# Every skill the templates name, in the order of the "Skills (...)" paragraph of templates.json "common". A test
# keeps this list, the paragraph and the pinned skills manifest in step.
TEMPLATE_SKILLS = ("search-first", "iterative-retrieval", "verification-before-completion",
                   "supply-chain-risk-auditor", "fp-check", "agentic-actions-auditor", "security-threat-model",
                   "codeql", "semgrep", "sarif-parsing", "property-based-testing", "mcp-builder", "modern-python",
                   "agent-browser")
USABLE_SKILL_STATUS = ("kept", "trial")
PROBE_PROMPT = ("Use web search. What is the latest release tag of https://github.com/ggml-org/llama.cpp and roughly "
                "how many GitHub stars does it have? Answer only in the required JSON.")
ARGS_LINE = re.compile(r"^const A = args$", re.MULTILINE)
SWEEP_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
# Kept equal to codex_job.MODEL_NAME: an optional provider prefix for gateway routes, e.g. "cx/gpt-6-astra".
MODEL_NAME = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._-]{0,31}/)?[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# GPT-6 lane providers. native: Codex's own login (--ignore-user-config). omniroute: a lane-local CODEX_HOME whose
# config.toml routes Codex through the local OmniRoute gateway (Codex model_providers with env_key; see
# https://developers.openai.com/codex/config-reference) and carries the token-stack MCP servers.
PROVIDERS = ("native", "omniroute")
OMNIROUTE_DEFAULT_URL = "http://127.0.0.1:20128/v1"
OMNIROUTE_DEFAULT_MODEL = "cx/gpt-6-astra"
OMNIROUTE_KEY_ENV = "OMNIROUTE_API_KEY"
# A loopback OmniRoute set up without a login or API key (upstream `omniroute setup --non-interactive`, REQUIRE_API_KEY
# false) accepts any value; Codex's env_key only needs the variable to exist (upstream CODEX-CLI-CONFIGURATION.md,
# "Local unauthenticated OmniRoute"). The runner uses this placeholder only when the variable is unset.
OMNIROUTE_KEYLESS_PLACEHOLDER = "local-loopback"
LOOPBACK_V1_URL = re.compile(r"http://(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?/v1")
LANE_HOME = "codex-home"
LANE_PROFILE = "stack-worker"
# context-mode's ctx_execute_file refuses a path outside its project directory (for the lane, the runner's cwd
# <work-dir>/empty) unless a Read(...) allow rule in <project>/.claude/settings.json names it (build/security.js
# evaluateProjectContainment and readToolPermissionPatterns at context-mode 1.0.169, issue #852). The lane's GPT-6 loads
# its pinned skills with that tool. Codex lists user skills from $CODEX_HOME/skills, here the lane home holding only
# Codex's .system cache, and $HOME/.agents/skills, where install_skills.py puts the pinned skills
# (codex-rs/ext/skills/src/host_roots.rs at rust-v0.157.1). context-mode matches an allow rule against the raw path as
# well as the resolved one, so a wildcard rule such as <root>/** would also admit <root>/../elsewhere: the lane
# therefore allows each file under $HOME/.agents/skills by its exact path, and nothing else. Codex reads no .claude/
# files, so the file adds no Codex project layer.
LANE_CONTEXT_SETTINGS = Path("empty") / ".claude" / "settings.json"
LANE_SKILL_ROOT = "$HOME/.agents/skills"
CODEX_TEMPLATE = Path("adoption/templates/codex.config.template.toml")
STACK_WORKER_PROFILE = Path("adoption/templates/codex.stack-worker.config.toml")
TABLE_HEADER = re.compile(r"^\s*\[")
# [mcp_servers.<name>...] as TOML writes a table header: optional spaces inside the brackets and around the dots, and
# a bare, double-quoted or single-quoted (literal) name.
MCP_TABLE_HEADER = re.compile(
    r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))\s*(?:\.[^\]]*)?\]\s*(?:#.*)?$""")


def load_templates() -> dict:
    return load_json(HERE / "templates.json")


def mcp_sections(rendered: str) -> tuple[str, list[str]]:
    """The [mcp_servers.*] tables of a rendered Codex config.toml, verbatim and in order, and the server names.

    Top-level keys, [projects.*] trust and [hooks.state.*] trust are left out on purpose: they describe the host's
    interactive client, not the lane."""
    kept, names, keep = [], [], False
    for line in rendered.splitlines():
        if TABLE_HEADER.match(line):
            match = MCP_TABLE_HEADER.match(line)
            keep = match is not None
            name = (match.group(1) or match.group(2) or match.group(3)) if match else None
            if keep and name not in names:
                names.append(name)
        if keep:
            kept.append(line)
    text = "\n".join(kept).strip() + "\n"
    # Line extraction is checked against a real TOML parse: the extracted text must parse to exactly the
    # mcp_servers table of the whole rendered config, every server and every nested setting, or staging fails closed
    # rather than dropping a server or a server's env. Without tomllib (Python 3.11+) nothing can check it.
    try:
        import tomllib
    except ImportError:
        raise ValueError("checking the extracted [mcp_servers.*] tables needs Python 3.11+ (tomllib)") from None
    try:
        full = tomllib.loads(rendered).get("mcp_servers") or {}
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"the rendered Codex config is not valid TOML: {error}") from None
    if not isinstance(full, dict):
        raise ValueError("the rendered Codex config's mcp_servers is not a table")
    try:
        extracted = tomllib.loads(text).get("mcp_servers") or {}
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"extracted [mcp_servers.*] tables are not valid TOML: {error}") from None
    if extracted != full or set(names) != set(full):
        differ = sorted(name for name in set(full) | set(extracted) | set(names)
                        if full.get(name) != extracted.get(name) or name not in full or name not in names)
        raise ValueError(f"MCP extraction mismatch: the extracted tables differ from the rendered config for {differ}")
    return text, names


def host_values_from_file(path: Path) -> dict:
    """A private host value file given by path. Real hosts' files are gitignored (adoption/hosts/*.json), so they
    exist only in the checkout that owns them, never in a worktree. Same shape render_config requires."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(value, str) for value in data.values()):
        raise ValueError(f"{path} must be a flat JSON object of string values")
    return data


def render_codex_template(repo_root: Path, host: str) -> str:
    """adoption/templates/codex.config.template.toml rendered for a host by the checkout's own
    tools/adoption/render_config.py (render_one), never by a copy of its logic. host is a name
    (adoption/hosts/<name>.json, via render_config.load_host_values) or a path to a private host value file."""
    sys.path.insert(0, str(repo_root / "tools" / "adoption"))
    try:
        import render_config  # noqa: E402  (the checkout's renderer)
    finally:
        sys.path.pop(0)
    try:
        values = (host_values_from_file(Path(host)) if host.endswith(".json")
                  else render_config.load_host_values(host))
        return render_config.render_one(repo_root / CODEX_TEMPLATE, values)
    except render_config.RenderError as error:
        raise ValueError(f"rendering {CODEX_TEMPLATE} for host {Path(host).name!r}: {error}") from None


def lane_skill_read_rules(home: Path) -> list[str]:
    """One exact Read(...) allow rule per file under <home>/.agents/skills (LANE_SKILL_ROOT), sorted, by the path Codex
    lists (symlinked directories followed, each real directory once). context-mode escapes every character of a rule
    except *, ? and ** and anchors it, so a rule without them matches only that path; a path containing either is
    left out rather than widening its rule."""
    root = home / ".agents" / "skills"
    rules, seen = [], set()
    for directory, subdirectories, files in os.walk(root, followlinks=True):
        real = os.path.realpath(directory)
        if real in seen:  # a symlink cycle, or a second route to a directory already listed
            subdirectories[:] = []
            continue
        seen.add(real)
        subdirectories.sort()
        rules.extend(f"Read({path})" for path in (str(Path(directory) / name) for name in sorted(files))
                     if not any(character in path for character in "*?"))
    return rules


def stage_lane_home(work: Path, *, model: str, base_url: str, host: str, profile: Path, repo_root: Path,
                    require_key: bool = False) -> dict:
    """Write <work>/codex-home: config.toml (the OmniRoute provider block plus the rendered token MCP servers) and
    stack-worker.config.toml (the worker profile, verbatim), and <work>/empty/.claude/settings.json (context-mode
    read access to each pinned skill file by its exact path). Return what staged.json records about them."""
    rendered = render_codex_template(repo_root, host)
    host_label = Path(host).stem if host.endswith(".json") else host  # never a private path in the lane record
    servers_text, servers = mcp_sections(rendered)
    if not servers:
        raise ValueError(f"{CODEX_TEMPLATE} rendered for {host!r} has no [mcp_servers.*] table")
    profile_bytes = Path(profile).read_bytes()
    template_sha = sha256_bytes((repo_root / CODEX_TEMPLATE).read_bytes())
    config = "\n".join([
        "# Lane-local Codex home for the landscape sweep's GPT-6 lane, written by build_args.py",
        "# (--gpt6-provider omniroute). It is the lane's whole configuration: Codex runs with CODEX_HOME set here,",
        "# without --ignore-user-config, and with -p stack-worker. Project and hook trust are deliberately absent.",
        f"# MCP servers: the [mcp_servers.*] tables of {CODEX_TEMPLATE} (sha256 {template_sha}) rendered for host",
        f"# {host_label!r} by tools/adoption/render_config.py. The provider key comes from ${OMNIROUTE_KEY_ENV}; it is never",
        "# stored here. supports_websockets stays unset (false): OmniRoute's WebSocket bridge drops the client headers",
        "# that carry the Codex version, which only its HTTP /v1/responses path forwards.",
        "# Web search: GPT-6 Astra runs Responses Lite, which carries no hosted tools, so search reaches it only as",
        "# Codex's standalone web search (web.run). A custom provider advertises that with",
        "# supports_standalone_web_search (Codex config docs, config-advanced) and the standalone_web_search feature",
        "# turns it on (under development in 0.157.1); the lane's parity check must show it works through OmniRoute.",
        "# shell_snapshot is off: Codex's shell snapshot writes the exported environment, the provider key included,",
        "# to <CODEX_HOME>/shell_snapshots (codex-rs/shell-command/src/shell_snapshot_exports.rs at rust-v0.157.1).",
        f"# {OMNIROUTE_KEY_ENV} is filtered out of model-run commands: 0.157.1 skips its default *KEY*/*SECRET*/*TOKEN*",
        "# excludes unless ignore_default_excludes is false, and it defaults to true",
        "# (codex-rs/config/src/shell_environment_policy.rs, codex-rs/protocol/src/shell_environment.rs).",
        f'model = "{model}"',
        'model_provider = "omniroute"',
        'model_reasoning_effort = "max"',
        "",
        "[features]",
        "shell_snapshot = false",
        "standalone_web_search = true",
        "",
        "[shell_environment_policy.filters]",
        f'{OMNIROUTE_KEY_ENV} = "exclude"',
        "",
        "[model_providers.omniroute]",
        'name = "OmniRoute"',
        f'base_url = "{base_url}"',
        f'env_key = "{OMNIROUTE_KEY_ENV}"',
        "requires_openai_auth = false",
        'wire_api = "responses"',
        "supports_standalone_web_search = true",
        "",
        servers_text,
    ])
    home = work / LANE_HOME
    home.mkdir(exist_ok=True)
    (home / "config.toml").write_text(config, encoding="utf-8")
    (home / f"{LANE_PROFILE}.config.toml").write_bytes(profile_bytes)
    try:
        import tomllib  # Python 3.11+; older interpreters skip this syntax check
    except ImportError:
        tomllib = None
    if tomllib is not None:
        for name in ("config.toml", f"{LANE_PROFILE}.config.toml"):
            try:
                tomllib.loads((home / name).read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as error:
                raise ValueError(f"{LANE_HOME}/{name} is not valid TOML: {error}") from None
    settings = work / LANE_CONTEXT_SETTINGS
    settings.parent.mkdir(parents=True, exist_ok=True)
    skill_rules = lane_skill_read_rules(Path.home())
    write_json(settings, {"permissions": {"allow": skill_rules}})
    keyless = {} if require_key else {"api_key_placeholder": OMNIROUTE_KEYLESS_PLACEHOLDER}
    return {"provider": "omniroute", "codex_home": LANE_HOME, "profile": LANE_PROFILE,
            "api_key_env": OMNIROUTE_KEY_ENV, **keyless, "base_url": base_url,
            "lane_home": {"host": host_label,
                          "template": str(CODEX_TEMPLATE), "template_sha256": template_sha,
                          "mcp_servers": servers,
                          "config_sha256": sha256_bytes((home / "config.toml").read_bytes()),
                          "profile_sha256": sha256_bytes(profile_bytes),
                          # the symbolic root and a count only: the file itself holds this host's absolute paths
                          "context_mode_skill_reads": {"settings": str(LANE_CONTEXT_SETTINGS),
                                                       "root": LANE_SKILL_ROOT, "exact_files": len(skill_rules)}}}


def fill_build(templates: dict, run_date: str, layer_count: int, skills_checked_at: str) -> dict:
    """The run's frozen templates; only the per-call placeholders sweep.js and make_prompt.py fill may remain."""
    values = {"DATE": run_date, "LAYER_COUNT": str(layer_count), "SKILLS_CHECKED_AT": skills_checked_at}
    filled = {key: make_prompt.fill(text, values) for key, text in templates.items()}
    if set(filled) != set(make_prompt.RUNTIME_PLACEHOLDERS):
        raise ValueError(f"templates must hold exactly {sorted(make_prompt.RUNTIME_PLACEHOLDERS)}")
    for key, text in filled.items():
        left = set(make_prompt.PLACEHOLDER.findall(text))
        if left != make_prompt.RUNTIME_PLACEHOLDERS[key]:
            raise ValueError(f"template {key} holds {sorted(left)}, expected {sorted(make_prompt.RUNTIME_PLACEHOLDERS[key])}")
    return filled


def skill_mentions(text: str, names) -> list[str]:
    return [name for name in names if re.search(rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])", text)]


def skills_problems(templates: dict, manifest: dict) -> list[str]:
    """The templates name exactly TEMPLATE_SKILLS, and each is a kept or trial skill of the pinned manifest."""
    pinned = {entry.get("name"): entry for entry in manifest.get("skills") or [] if isinstance(entry, dict)}
    problems = []
    for name in TEMPLATE_SKILLS:
        if not skill_mentions(templates["common"], [name]):
            problems.append(f"skill {name} is listed in TEMPLATE_SKILLS but not named in templates.json common")
        entry = pinned.get(name)
        if entry is None:
            problems.append(f"skill {name} is not pinned in {SKILLS_MANIFEST}")
        elif entry.get("status") not in USABLE_SKILL_STATUS:
            problems.append(f"skill {name} has status {entry.get('status')!r} in {SKILLS_MANIFEST}")
    extra = sorted(set(skill_mentions(templates["common"], pinned)) - set(TEMPLATE_SKILLS))
    if extra:
        problems.append(f"templates.json common names pinned skills missing from TEMPLATE_SKILLS: {extra}")
    return problems


def select_layers(layers: list, only=None, due_report=None, smoke=None) -> list:
    by_id = {layer["layer_id"]: layer for layer in layers}
    if smoke:
        wanted = [smoke]
    elif only:
        wanted = list(dict.fromkeys(only))
    elif due_report is not None:
        due = {(row.get("catalog"), row.get("layer_id")) for row in due_report.get("layers") or [] if row.get("due")}
        wanted = [layer["layer_id"] for layer in layers if (layer["catalog"], layer["layer_id"]) in due]
    else:
        wanted = [layer["layer_id"] for layer in layers]
    unknown = [layer_id for layer_id in wanted if layer_id not in by_id]
    if unknown:
        raise ValueError(f"layers not in layers.json: {unknown}")
    if not wanted:
        raise ValueError("no layer selected")
    return [by_id[layer_id] for layer_id in wanted]


def embed(script: str, args: dict) -> str:
    """sweep.js with its single `const A = args` line replaced by the args as a JSON literal (ASCII-only)."""
    lines = ARGS_LINE.findall(script)
    if len(lines) != 1:
        raise ValueError(f"sweep.js must hold exactly one `const A = args` line, found {len(lines)}")
    literal = json.dumps(args, ensure_ascii=True, separators=(",", ":"))
    return ARGS_LINE.sub(lambda _: "const A = " + literal, script, count=1)


def git_state(repo_root: Path) -> dict:
    """The checkout's HEAD and whether this harness directory differs from it (None outside a git checkout)."""
    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
        except OSError:
            return None
    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--", str(HERE))
    return {"commit": head.stdout.strip() if head is not None and head.returncode == 0 else None,
            "dirty": bool(status.stdout.strip()) if status is not None and status.returncode == 0 else None}


def stage(work: Path, *, sweep_id: str, run_date: str, selected: list, test: bool, stars, gpt6_model: str,
          slots: int, lock_dir, skills_checked_at: str | None, embed_script: bool, force: bool,
          repo_root: Path = REPO_ROOT, quota_stop_percent: float | None = None, lane: dict | None = None) -> dict:
    jobs = [path.name for path in (work / "gpt6").glob("*") if path.is_dir()] if (work / "gpt6").is_dir() else []
    if jobs and not force:
        raise ValueError(f"{work}/gpt6 already holds {len(jobs)} job(s) from an earlier run; move gpt6/ and prompts/ "
                         "to attempts/<name>/ first (their finished jobs would be reused), or pass --force")
    manifest = load_json(repo_root / SKILLS_MANIFEST)
    templates = load_templates()
    problems = skills_problems(templates, manifest)
    if problems:
        raise ValueError("; ".join(problems))
    frozen = fill_build(templates, run_date, len(selected), skills_checked_at or manifest["checked_at"])
    schemas = {name: load_json(HERE / "schemas" / f"{name}.json") for name in SCHEMAS}
    first_prompts = {}
    for layer in selected:  # everything is checked before anything is written
        layer_input = load_json(work / "inputs" / f"{layer['layer_id']}.json")
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            if not layer_input.get(field):
                raise ValueError(f"inputs/{layer['layer_id']}.json has no {field}; rebuild it with build_inputs.py")
        first_prompts[layer["layer_id"]] = make_prompt.compose(frozen, "discover", layer_input)
    for name in ("gpt6", "prompts", "empty", "schemas"):
        (work / name).mkdir(exist_ok=True)
    if lane is None:  # a native lane has no context-mode, so an earlier gateway staging's read rules go
        (work / LANE_CONTEXT_SETTINGS).unlink(missing_ok=True)
        if (work / LANE_CONTEXT_SETTINGS.parent).is_dir() and not any((work / LANE_CONTEXT_SETTINGS.parent).iterdir()):
            (work / LANE_CONTEXT_SETTINGS.parent).rmdir()
    for name in RUNTIME:
        shutil.copy2(HERE / name, work / name)
    shutil.copy2(QUOTA_PROBE, work / QUOTA_PROBE.name)
    write_json(work / "templates.json", frozen)
    for name, schema in schemas.items():
        write_json(work / "schemas" / f"{name}.json", schema)
    for layer_id, text in first_prompts.items():
        (work / "prompts" / f"gpt6-discover-{layer_id}.txt").write_text(text + "\n", encoding="utf-8")
    (work / "prompts" / "gpt6-probe.txt").write_text(PROBE_PROMPT + "\n", encoding="utf-8")
    digest = prompts_sha256(frozen)
    (work / "prompts_sha256.txt").write_text(digest + "\n", encoding="utf-8")
    args = {"S": str(work), "stars": str(stars) if stars else None, "sweep_id": sweep_id, "T": frozen,
            "schemas": {name: schemas[name] for name in ("discover", "votes", "critic")},
            "layers": [{"layer_id": layer["layer_id"], "catalog": layer["catalog"]} for layer in selected]}
    if test:
        args["test"] = True
    args_text = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
    (work / "args.json").write_text(args_text + "\n", encoding="utf-8")
    pinned = {entry["name"]: entry for entry in manifest.get("skills") or []}
    codex = {"model": gpt6_model, "effort": "max", "slots": slots}
    if lock_dir:
        codex["lock_dir"] = str(Path(lock_dir).expanduser().resolve())
    if quota_stop_percent is not None:
        codex["quota_stop_percent"] = quota_stop_percent
    if lane is not None:
        codex.update(stage_lane_home(work, model=gpt6_model, base_url=lane["base_url"], host=lane["host"],
                                     profile=lane["profile"], repo_root=repo_root,
                                     require_key=lane.get("require_key", False)))
    harness_files = sorted([*RUNTIME, "sweep.js", "templates.json", *(f"schemas/{name}.json" for name in SCHEMAS)])
    staged = {"schema_version": 1, "kind": "landscape_sweep_staging", "sweep_id": sweep_id, "date": run_date,
              "test": test, "layers": [layer["layer_id"] for layer in selected], "prompts_sha256": digest,
              "harness": {"path": "tools/sota-convergence/landscape-sweep", **git_state(repo_root),
                          "files": {name: sha256_bytes((HERE / name).read_bytes()) for name in harness_files},
                          "quota_probe": {"path": "scripts/codex_quota.py",
                                          "sha256": sha256_bytes(QUOTA_PROBE.read_bytes())}},
              "skills": {"manifest": SKILLS_MANIFEST, "checked_at": manifest.get("checked_at"),
                         "named": list(TEMPLATE_SKILLS),
                         "codex_enabled": [name for name in TEMPLATE_SKILLS if pinned[name].get("codex_enabled")]},
              "codex": codex}
    write_json(work / "staged.json", staged)
    summary = {"work_dir": str(work), "sweep_id": sweep_id, "date": run_date, "layers": len(selected), "test": test,
               "prompts_sha256": digest, "args": str(work / "args.json"), "args_bytes": len(args_text.encode("utf-8"))}
    if embed_script:
        script = embed((HERE / "sweep.js").read_text(encoding="utf-8"), args)
        (work / "sweep.embedded.js").write_text(script, encoding="utf-8")
        summary.update(embedded=str(work / "sweep.embedded.js"), embedded_sha256=sha256_bytes(script.encode("utf-8")),
                       launch=f'Workflow({{scriptPath: "{work / "sweep.embedded.js"}"}})')
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", default=os.environ.get("SWEEP_WORK_DIR"))
    parser.add_argument("--sweep-id", required=True, help="lane name, e.g. landscape-sweep-20260926")
    parser.add_argument("--date", required=True, help="the run's date (YYYY-MM-DD), filled into the templates")
    choose = parser.add_mutually_exclusive_group()
    choose.add_argument("--layers", help="comma-separated layer ids, swept in the order given")
    choose.add_argument("--due-report", type=Path, help="saturation_ledger.py --report --json output: its due layers")
    choose.add_argument("--smoke", metavar="LAYER_ID", help="one layer, first round only (args.test = true)")
    stars = parser.add_mutually_exclusive_group()
    stars.add_argument("--stars", type=Path, help="star-candidates.json (default <work-dir>/work/star-candidates.json)")
    stars.add_argument("--no-stars", action="store_true")
    parser.add_argument("--gpt6-model", default=None,
                        help=f"default gpt-6-astra; {OMNIROUTE_DEFAULT_MODEL} with --gpt6-provider omniroute")
    parser.add_argument("--gpt6-provider", choices=PROVIDERS, default="native",
                        help="native: Codex's own login (default). omniroute: a lane-local CODEX_HOME that routes "
                             f"Codex through the local OmniRoute gateway with the token-stack MCP servers; the key "
                             f"comes from ${OMNIROUTE_KEY_ENV} in the harness's environment")
    parser.add_argument("--omniroute-base-url", default=OMNIROUTE_DEFAULT_URL,
                        help=f"loopback OmniRoute Responses endpoint (default {OMNIROUTE_DEFAULT_URL})")
    parser.add_argument("--codex-host", metavar="HOST",
                        help="a host name (adoption/hosts/HOST.json in the checkout) or a path to a private host "
                             "value file (*.json; real hosts' files are gitignored), whose values render the lane's "
                             "token MCP servers (required with --gpt6-provider omniroute)")
    parser.add_argument("--stack-worker-profile", type=Path,
                        help=f"the Codex worker profile overlay (default {STACK_WORKER_PROFILE} in the checkout)")
    parser.add_argument("--omniroute-require-key", action="store_true",
                        help=f"the gateway requires an API key: stage no {OMNIROUTE_KEYLESS_PLACEHOLDER!r} placeholder, "
                             f"so a job without ${OMNIROUTE_KEY_ENV} ends before codex starts")
    parser.add_argument("--slots", type=int, default=3, help="concurrent codex jobs per lock dir (default 3)")
    parser.add_argument("--lock-dir", help="semaphore directory; share one across sweeps that run at the same time")
    parser.add_argument("--quota-stop-percent", type=float, metavar="PERCENT",
                        help="refuse each GPT-6 job like a usage limit once the Codex account's used_percent reaches "
                             "PERCENT (scripts/codex_quota.py --gate); off by default")
    parser.add_argument("--skills-checked-at", help=f"override {SKILLS_MANIFEST} checked_at (reproduce a past run)")
    parser.add_argument("--no-embed", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        work = work_dir(args.work_dir)
        date.fromisoformat(args.date)
        if not SWEEP_ID.fullmatch(args.sweep_id):
            raise ValueError(f"--sweep-id must match {SWEEP_ID.pattern}")
        if args.slots < 1:
            raise ValueError("--slots must be at least 1")
        if args.quota_stop_percent is not None and not 0 < args.quota_stop_percent <= 100:
            raise ValueError("--quota-stop-percent must be above 0 and at most 100")
        gpt6_model = args.gpt6_model or (OMNIROUTE_DEFAULT_MODEL if args.gpt6_provider == "omniroute"
                                         else "gpt-6-astra")
        if not MODEL_NAME.fullmatch(gpt6_model):
            raise ValueError("--gpt6-model is not a model name")
        lane = None
        if args.gpt6_provider == "omniroute":
            if args.quota_stop_percent is not None:
                raise ValueError("--quota-stop-percent reads the native Codex login; it cannot gate the OmniRoute "
                                 "account pool, so drop it with --gpt6-provider omniroute")
            if not args.codex_host:
                raise ValueError("--gpt6-provider omniroute needs --codex-host HOST (a name under adoption/hosts/ "
                                 "or a path to a private host value file)")
            if args.codex_host.endswith(".json"):
                if not Path(args.codex_host).is_file():
                    raise ValueError(f"--codex-host file {args.codex_host} does not exist")
            elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.codex_host):
                raise ValueError("--codex-host must be a host name or a path to a *.json host value file")
            if not LOOPBACK_V1_URL.fullmatch(args.omniroute_base_url):
                raise ValueError("--omniroute-base-url must be a loopback http URL ending in /v1")
            profile = args.stack_worker_profile or (args.repo_root.resolve() / STACK_WORKER_PROFILE)
            if not Path(profile).is_file():
                raise ValueError(f"stack-worker profile {profile} does not exist: the default "
                                 f"{STACK_WORKER_PROFILE} arrives with the Codex worker-lane change; until the "
                                 "checkout has it, pass --stack-worker-profile PATH")
            lane = {"host": args.codex_host, "base_url": args.omniroute_base_url, "profile": Path(profile).resolve(),
                    "require_key": args.omniroute_require_key}
        if args.skills_checked_at:
            date.fromisoformat(args.skills_checked_at)
        layers = load_json(work / "layers.json")
        selected = select_layers(layers, only=[x.strip() for x in args.layers.split(",") if x.strip()] if args.layers else None,
                                 due_report=load_json(args.due_report) if args.due_report else None,
                                 smoke=args.smoke)
        default_stars = work / "work" / "star-candidates.json"
        stars_path = None if args.no_stars else (args.stars.resolve() if args.stars else
                                                  (default_stars if default_stars.is_file() else None))
        if stars_path is not None and not Path(stars_path).is_file():
            raise ValueError(f"--stars {stars_path} does not exist")
        summary = stage(work, sweep_id=args.sweep_id, run_date=args.date, selected=selected, test=bool(args.smoke),
                        stars=stars_path, gpt6_model=gpt6_model, slots=args.slots, lock_dir=args.lock_dir,
                        skills_checked_at=args.skills_checked_at, embed_script=not args.no_embed, force=args.force,
                        repo_root=args.repo_root.resolve(), quota_stop_percent=args.quota_stop_percent, lane=lane)
    except (ValueError, OSError, KeyError) as error:
        print(f"build_args.py: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
