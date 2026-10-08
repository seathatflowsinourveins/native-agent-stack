#!/usr/bin/env python3
"""Stage a landscape-sweep run into its work directory and write the compact Workflow args.

  build_args.py --work-dir W --sweep-id landscape-sweep-YYYYMMDD --date YYYY-MM-DD
                [--layers id,id,... | --due-report report.json] [--smoke LAYER_ID]
                [--stars PATH | --no-stars] [--gpt6-model gpt-6-astra] [--slots 3] [--lock-dir DIR]
                [--quota-stop-percent PERCENT] [--skills-checked-at YYYY-MM-DD] [--no-embed] [--force]
                [--gpt6-provider omniroute --codex-host HOST [--omniroute-base-url URL]
                 [--omniroute-header NAME=VALUE ...] [--stack-worker-profile PATH] [--omniroute-require-key]]

Needs <work-dir>/layers.json and <work-dir>/inputs/ from build_inputs.py. Writes into the work dir:
  templates.json         the repository templates with <<DATE>>, <<LAYER_COUNT>> and <<SKILLS_CHECKED_AT>> filled
                         (the skills date is adoption/skills/manifest.json checked_at) and the run's modality
                         resolved into the role keys (fill_build); frozen for the run
  prompts_sha256.txt     sha256 of json.dumps(templates, sort_keys=True, ensure_ascii=False): the record's
                         prompts_sha256
  schemas/               discover, discover-skills, votes and critic (the workers' strict return schemas) and probe
  codex_call.sh, codex_job.py, make_prompt.py, codex_quota.py
                         the GPT-6 runtime the wrapper agents call, copied so a checkout change mid-run cannot
                         alter a running sweep (codex_quota.py is the checkout's scripts/codex_quota.py, the quota
                         probe codex_job.py runs when codex.quota_stop_percent is set)
  prompts/gpt6-discover-<layer>.txt, prompts/gpt6-probe.txt
                         the first-round GPT-6 discovery prompts and a one-call lane probe
  staged.json            provenance (harness commit and file hashes, skills, prompts_sha256) and the GPT-6 settings
                         codex_job.py reads (model, slots, lock dir, and quota_stop_percent only when
                         --quota-stop-percent is given: the quota gate is off by default)
  args.json              the Workflow args: {S, stars, sweep_id, T, schemas, layers: [{layer_id, catalog}], test?};
                         a skills run (skills-* layers from build_inputs.py --modality skills) adds
                         schemas["discover-skills"] and modality "skills" to each layer. A run covers one modality.
  sweep.embedded.js      sweep.js with its one `const A = args` line replaced by those args, launched as
                         Workflow({scriptPath: "<work-dir>/sweep.embedded.js"}) with no args, so the ~12 KB of
                         templates and schemas never pass through the coordinator's context and a resume needs
                         only the scriptPath (--no-embed skips it)
Refuses a work dir inside a git repository, templates naming a skill the pinned skills manifest lacks, a selection
that mixes repository and skills-* layers, and restaging a work dir whose gpt6/ already holds jobs (an earlier run's
"already done" jobs would be reused) unless --force.
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
import codex_job  # noqa: E402
import make_prompt  # noqa: E402
from sweep_common import REPO_ROOT, load_json, prompts_sha256, sha256_bytes, work_dir, write_json  # noqa: E402

RUNTIME = ("codex_call.sh", "codex_job.py", "make_prompt.py")
QUOTA_PROBE = REPO_ROOT / "scripts" / "codex_quota.py"  # staged beside codex_job.py as codex_quota.py
SCHEMAS = ("discover", "discover-skills", "votes", "critic", "probe")
# The skills modality (skills-* layers, build_inputs.py --modality skills) and its discovery return schema; a
# layers.json row without "modality" is a repository layer.
SKILLS_SCHEMA = "discover-skills"
REPOSITORY_MODALITY, SKILLS_MODALITY = "repository", "skills"
MODALITIES = (REPOSITORY_MODALITY, SKILLS_MODALITY)
# The role keys whose template a modality replaces (fill_build); facts, fit, common and followup are shared.
MODALITY_TEMPLATES = {REPOSITORY_MODALITY: {}, SKILLS_MODALITY: {"discover": "discover_skills",
                                                                  "critic": "critic_skills"}}
# templates.json: the role keys plus the skills modality's templates (modality_skills fills <<MODALITY>>).
TEMPLATE_KEYS = (*make_prompt.RUNTIME_PLACEHOLDERS, "discover_skills", "critic_skills", "modality_skills")
V2_TEMPLATE_KEYS = ("common_v2", "discover_v2", "facts_v2", "fit_v2")
SKILLS_MANIFEST = "adoption/skills/manifest.json"
# Every skill the templates name, in the order of the "Skills (...)" paragraph of templates.json "common". Every
# template reaches a worker (the skills modality's discover_skills, critic_skills and modality_skills too), so
# skills_problems scans them all: a pinned skill named in any template must be listed here and in that paragraph. A
# test keeps this list, the paragraph and the pinned skills manifest in step. skill-creator joined on 2026-09-30 when
# unit F3 (#553) pinned it: the skills templates name its paired with-skill/without-skill benchmark as the comparison
# that would overturn a skills-* verdict, and the manifest keeps it off in Codex (codex_enabled false). semgrep (retired)
# and agent-browser (held) left on 2026-10-03 with the wave-2 skills ruling (changes 1 and 3; adoption/skills/manifest.json).
TEMPLATE_SKILLS = ("search-first", "iterative-retrieval",
                   "supply-chain-risk-auditor", "fp-check", "agentic-actions-auditor", "security-threat-model",
                   "codeql", "sarif-parsing", "property-based-testing", "mcp-builder", "modern-python",
                   "skill-creator")
USABLE_SKILL_STATUS = ("kept", "trial")
PROBE_PROMPT = ("Use web search. What is the latest release tag of https://github.com/ggml-org/llama.cpp and roughly "
                "how many GitHub stars does it have? Answer only in the required JSON.")
ARGS_LINE = re.compile(r"^const A = args$", re.MULTILINE)
SWEEP_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
# Kept equal to codex_job.MODEL_NAME: at most one provider segment, e.g. "cx/gpt-6-astra" or the framework
# instance's "sharedgw/gpt-6-astra-max". Codex strips one namespace for metadata lookup, and only one of letters,
# digits, '_' and '-'; another slug gets fallback metadata (openai/codex rust-v0.157.1,
# codex-rs/models-manager/src/manager.rs L763-780).
MODEL_NAME = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9_-]{0,31}/)?[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# Static provider headers (--omniroute-header NAME=VALUE), rendered as model_providers.omniroute.http_headers. Codex
# 0.157.1 adds them to every request to the provider and silently skips a name or value that is not a valid HTTP header
# (codex-rs/model-provider-info/src/lib.rs:166-168 and 385-412 at rust-v0.157.1; config reference
# https://developers.openai.com/codex/config-reference), so both are checked here. Kept equal to codex_job.py.
# Names: only OmniRoute 3.8.51's per-request switches, lowercase (field names are case-insensitive, RFC 9110 section
# 5.1). staged.json and every job's inputs.json record the values, and other x-omniroute-* headers carry secrets under
# names without a credential word: x-omniroute-self-hop (open-sse/utils/selfHop.ts:1-12) and
# x-omniroute-video-bridge-broker (src/lib/guardrails/videoBridgeBrokerAuth.ts:7-19), for example. So the switches
# are listed, not filtered by word.
OMNIROUTE_REQUEST_HEADERS = (
    "x-omniroute-compression",  # a compression plan or allow-lossy (open-sse/handlers/chatCore/headers.ts:35-46)
    "x-omniroute-no-cache",  # "true" skips the semantic cache (src/lib/semanticCache.ts:483-486 and 501-504)
    "x-omniroute-no-memory",  # true, 1 or yes skips memory injection (open-sse/handlers/chatCore/headers.ts:18-33)
    "x-omniroute-strip-reasoning",  # true, 1 or yes strips reasoning_content (the same file, 48-65)
)
# Values: printable ASCII without '"' or '\' and without a space at either end, at most 128 characters: a valid HTTP
# field value (RFC 9110 section 5.5) that json.dumps writes as a TOML basic string without escapes.
HEADER_VALUE = re.compile(r"[!#-\[\]-~](?:[ !#-\[\]-~]{0,126}[!#-\[\]-~])?")
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
# therefore allows each file under $HOME/.agents/skills by its exact path. Residual: the matcher turns backslashes into
# slashes before matching while the executor opens the literal Linux name, so a file whose name holds backslashes that
# normalize to a listed path would pass too; none exists, and making one takes the write access ctx_execute already
# has. The #852 boundary limits ctx_execute_file only: ctx_execute, which the stack-worker profile leaves enabled, runs
# code with the user's own file access outside Codex's read-only sandbox. Codex reads no .claude/ files, so the file
# adds no Codex project layer.
LANE_CONTEXT_SETTINGS = Path("empty") / ".claude" / "settings.json"
LANE_SKILL_ROOT = "$HOME/.agents/skills"
CODEX_TEMPLATE = Path("adoption/templates/codex.config.template.toml")
STACK_WORKER_PROFILE = Path("adoption/templates/codex.stack-worker.config.toml")
TABLE_HEADER = re.compile(r"^\s*\[")
# [mcp_servers.<name>...] as TOML writes a table header: optional spaces inside the brackets and around the dots, and
# a bare, double-quoted or single-quoted (literal) name.
MCP_TABLE_HEADER = re.compile(
    r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))\s*(?:\.[^\]]*)?\]\s*(?:#.*)?$""")


class UsageError(ValueError):
    """A usage refusal before staging any output."""


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
    except *, ? and ** and anchors it, so a rule without them matches only that path, up to the backslash residual
    above; a path containing either is left out rather than widening its rule."""
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


def profile_servers_without_base(profile_bytes: bytes, base_servers: list) -> list:
    """The worker profile's [mcp_servers.<name>] tables that define no transport (command or url) and overlay no server
    of the lane config. Codex merges the profile over config.toml and rejects a merged server table with neither
    (codex-rs/config/src/mcp_types.rs:454-510 at rust-v0.157.1), so each such name would stop -p stack-worker loading."""
    import tomllib  # mcp_sections has already required it (Python 3.11+)
    try:
        tables = tomllib.loads(profile_bytes.decode("utf-8")).get("mcp_servers") or {}
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"the {LANE_PROFILE} profile is not valid TOML: {error}") from None
    return sorted(name for name, table in tables.items()
                  if name not in base_servers and not (isinstance(table, dict) and ("command" in table or "url" in table)))


def codex_user_instructions(repo_root: Path) -> str:
    """The Codex user instructions a host installs as $CODEX_HOME/AGENTS.md: the managed block of
    adoption/templates/codex.AGENTS.template.md (the philosophy core and rtk-ai/rtk v0.51.0's default awareness
    paragraph, hooks/rtk-awareness.md, verbatim; on 2026-10-08 the full awareness text left it and the RTK exactness
    exceptions moved to docs/token-practice.md), read through tools/adoption/apply_codex_lane.py's agents_block(), never a copy of it. Codex reads
    $CODEX_HOME/AGENTS.md as global instructions, so a lane home without it gives its model neither the philosophy
    core nor RTK's instructions, which the native lane's workers get from ~/.codex."""
    saved = list(sys.path)  # the installer prepends the repository root itself on import (apply_codex_lane.py:69)
    sys.path.insert(0, str(repo_root / "tools" / "adoption"))
    try:
        import apply_codex_lane  # noqa: E402  (the checkout's installer)
    finally:
        sys.path[:] = saved
    try:
        return apply_codex_lane.agents_block()
    except apply_codex_lane.Refused as error:
        raise ValueError(str(error)) from None


def omniroute_headers(specs) -> dict[str, str]:
    """--omniroute-header NAME=VALUE options as the lane's static provider headers, sorted by name: OmniRoute's
    per-request switches (OMNIROUTE_REQUEST_HEADERS), each once, with a HEADER_VALUE value. A refused value is never
    echoed, nor a refused name."""
    headers = {}
    for number, spec in enumerate(specs or (), 1):
        name, separator, value = spec.partition("=")
        name = name.lower()
        if not separator:
            raise ValueError(f"--omniroute-header #{number} must be NAME=VALUE")
        if name not in OMNIROUTE_REQUEST_HEADERS:
            raise ValueError(f"--omniroute-header #{number}: only OmniRoute's per-request switches can be staged "
                             f"({', '.join(OMNIROUTE_REQUEST_HEADERS)}); other headers can carry a secret, and "
                             "staged.json and each job's inputs.json record header values")
        if name in headers:
            raise ValueError(f"--omniroute-header {name} is given more than once")
        if not HEADER_VALUE.fullmatch(value):
            raise ValueError(f"--omniroute-header {name}: the value must be 1-128 printable ASCII characters without "
                             "'\"' or '\\' and without a space at either end")
        headers[name] = value
    return dict(sorted(headers.items()))


def stage_lane_home(work: Path, *, model: str, base_url: str, host: str, profile: Path, repo_root: Path,
                    require_key: bool = False, http_headers: dict | None = None) -> dict:
    """Write <work>/codex-home: config.toml (the OmniRoute provider block, with http_headers only when given, plus the
    rendered token MCP servers), stack-worker.config.toml (the worker profile, verbatim) and AGENTS.md (the host's
    Codex user instructions: the philosophy core and RTK's, as codex_user_instructions reads them), and
    <work>/empty/.claude/settings.json (context-mode read access to each pinned skill file by its exact path). Return
    what staged.json records about them. http_headers must come from omniroute_headers."""
    http_headers = dict(sorted((http_headers or {}).items()))
    header_lines = []
    if http_headers:
        header_lines = [
            "# Static request headers (build_args.py --omniroute-header): Codex 0.157.1 adds http_headers to every",
            "# request to this provider (codex-rs/model-provider-info/src/lib.rs:166-168 and 385-412). OmniRoute reads",
            "# x-omniroute-compression per request, and allow-lossy keeps its operator compression plan instead of the",
            "# safe downgrade (open-sse/handlers/chatCore/headers.ts:41-46, services/compression/lossyRequestPolicy.ts:",
            "# 29-47 at 3.8.51). A chained OmniRoute forwards none of these headers to the next gateway: of the",
            "# client's headers only User-Agent, x-opencode-*, x-session-id and x-title pass (open-sse/executors/",
            "# default.ts:678-685, open-sse/utils/opencodeHeaders.ts:102-116), so Codex's session-id, thread-id and",
            "# x-codex-* headers stop at the first gateway too.",
            "http_headers = { " + ", ".join(f"{json.dumps(name)} = {json.dumps(value)}"
                                            for name, value in http_headers.items()) + " }",
        ]
    rendered = render_codex_template(repo_root, host)
    host_label = Path(host).stem if host.endswith(".json") else host  # never a private path in the lane record
    servers_text, servers = mcp_sections(rendered)
    if not servers:
        raise ValueError(f"{CODEX_TEMPLATE} rendered for {host!r} has no [mcp_servers.*] table")
    profile_bytes = Path(profile).read_bytes()
    unbased = profile_servers_without_base(profile_bytes, servers)
    if unbased:
        raise ValueError(
            f"{profile} has [mcp_servers.*] tables without command or url for {', '.join(unbased)}, which the "
            f"{CODEX_TEMPLATE} rendered for host {host_label!r} does not define: Codex 0.157.1 rejects such a server as "
            f"'invalid transport' (codex-rs/config/src/mcp_types.rs:454-510), so -p {LANE_PROFILE} would not load")
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
        *header_lines,
        "",
        servers_text,
    ])
    agents_text = codex_user_instructions(repo_root)
    home = work / LANE_HOME
    home.mkdir(exist_ok=True)
    (home / "config.toml").write_text(config, encoding="utf-8")
    (home / f"{LANE_PROFILE}.config.toml").write_bytes(profile_bytes)
    (home / "AGENTS.md").write_text(agents_text, encoding="utf-8")
    import tomllib  # mcp_sections has already required it (Python 3.11+)
    for name in ("config.toml", f"{LANE_PROFILE}.config.toml"):
        try:
            tomllib.loads((home / name).read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"{LANE_HOME}/{name} is not valid TOML: {error}") from None
    # Codex's ModelProviderInfo denies unknown fields only in its JSON schema, not when serde loads the config
    # (lib.rs:133-136), so a header table under the wrong key would load silently: read it back as Codex will.
    provider = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))["model_providers"]["omniroute"]
    if provider.get("http_headers", {}) != http_headers:
        raise ValueError(f"{LANE_HOME}/config.toml does not parse back to the requested provider headers")
    settings = work / LANE_CONTEXT_SETTINGS
    settings.parent.mkdir(parents=True, exist_ok=True)
    skill_rules = lane_skill_read_rules(Path.home())
    write_json(settings, {"permissions": {"allow": skill_rules}})
    keyless = {} if require_key else {"api_key_placeholder": OMNIROUTE_KEYLESS_PLACEHOLDER}
    return {"provider": "omniroute", "codex_home": LANE_HOME, "profile": LANE_PROFILE,
            "api_key_env": OMNIROUTE_KEY_ENV, **keyless, "base_url": base_url,
            "http_headers": http_headers,  # names and values; omniroute_headers admits only OmniRoute's switches
            "lane_home": {"host": host_label,
                          "template": str(CODEX_TEMPLATE), "template_sha256": template_sha,
                          "mcp_servers": servers,
                          "config_sha256": sha256_bytes((home / "config.toml").read_bytes()),
                          "profile_sha256": sha256_bytes(profile_bytes),
                          "agents_sha256": sha256_bytes(agents_text.encode("utf-8")),
                          # the symbolic root and a count only: the file itself holds this host's absolute paths
                          "context_mode_skill_reads": {"settings": str(LANE_CONTEXT_SETTINGS),
                                                       "root": LANE_SKILL_ROOT, "exact_files": len(skill_rules)}}}


def fill_build(templates: dict, run_date: str, layer_count: int, skills_checked_at: str,
               modality: str = REPOSITORY_MODALITY, contract_version: int = 1) -> dict:
    """The run's frozen templates: the role keys sweep.js and make_prompt.py read (make_prompt.RUNTIME_PLACEHOLDERS),
    with only their per-call placeholders left. The modality is resolved here: a skills run's discover and critic are
    discover_skills and critic_skills, and its facts and fit end in modality_skills (<<MODALITY>>), which a repository
    run fills with "", so a repository run's frozen templates are the templates it had before the skills modality."""
    if set(templates) not in (set(TEMPLATE_KEYS), set(TEMPLATE_KEYS) | set(V2_TEMPLATE_KEYS)):
        raise ValueError(f"templates must hold exactly {sorted(TEMPLATE_KEYS)}, with all or no {sorted(V2_TEMPLATE_KEYS)}")
    if modality not in MODALITY_TEMPLATES:
        raise ValueError(f"modality {modality!r} is not one of {sorted(MODALITY_TEMPLATES)}")
    if contract_version not in (1, 2):
        raise ValueError("contract_version must be 1 or 2")
    if contract_version == 2 and modality == SKILLS_MODALITY:
        raise ValueError("the skills modality keeps version 1")
    if contract_version == 2 and not set(V2_TEMPLATE_KEYS) <= set(templates):
        raise ValueError("version 2 requires all V2 templates")
    roles = {**{key: key for key in make_prompt.RUNTIME_PLACEHOLDERS}, **MODALITY_TEMPLATES[modality]}
    if contract_version == 2:
        roles.update({key.removesuffix("_v2"): key for key in V2_TEMPLATE_KEYS})
    values = {"DATE": run_date, "LAYER_COUNT": str(layer_count), "SKILLS_CHECKED_AT": skills_checked_at,
              "MODALITY": templates["modality_skills"] if modality == SKILLS_MODALITY else ""}
    filled = {key: make_prompt.fill(templates[source], values) for key, source in roles.items()}
    for key, text in filled.items():
        left = set(make_prompt.PLACEHOLDER.findall(text))
        if left != make_prompt.RUNTIME_PLACEHOLDERS[key]:
            raise ValueError(f"template {key} holds {sorted(left)}, expected {sorted(make_prompt.RUNTIME_PLACEHOLDERS[key])}")
    return filled


def skill_mentions(text: str, names) -> list[str]:
    return [name for name in names if re.search(rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])", text)]


def skills_problems(templates: dict, manifest: dict) -> list[str]:
    """The templates name exactly TEMPLATE_SKILLS, each named in common's Skills paragraph and each a kept or trial
    skill of the pinned manifest; a pinned skill named in any template must be one of them."""
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
    for key, text in templates.items():
        extra = sorted(set(skill_mentions(text, pinned)) - set(TEMPLATE_SKILLS))
        if extra:
            problems.append(f"templates.json {key} names pinned skills missing from TEMPLATE_SKILLS: {extra}")
    return problems


def run_modality(selected: list) -> str:
    """The one modality of the selected layers.json rows ("repository" for a row without "modality"). A run covers
    one modality: sweep.js runs one completeness critic, labelled `critic`, whose template is the run's modality's,
    and make_result.py counts that critic in every layer of the record."""
    modalities = sorted({layer.get("modality") or REPOSITORY_MODALITY for layer in selected})
    unknown = [name for name in modalities if name not in MODALITIES]
    if unknown:
        raise ValueError(f"layers.json names unknown modalities {unknown}; expected {list(MODALITIES)}")
    if len(modalities) > 1:
        raise ValueError(f"the selected layers mix modalities {modalities}: stage one modality per run (repository "
                         "layers and skills-* layers in separate runs; pass --layers)")
    return modalities[0]


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
          repo_root: Path = REPO_ROOT, quota_stop_percent: float | None = None, lane: dict | None = None,
          fallback: dict | None = None) -> dict:
    if fallback is not None:
        if lane is not None or "/" in gpt6_model:
            raise UsageError("codex.fallback needs the native provider and a model without a provider segment")
        try:
            codex_job.fallback_model(gpt6_model, codex_job.request_effort(gpt6_model, "max"))
        except codex_job.UsageError as error:
            raise UsageError(str(error)) from error
    jobs = [path.name for path in (work / "gpt6").glob("*") if path.is_dir()] if (work / "gpt6").is_dir() else []
    if jobs and not force:
        raise ValueError(f"{work}/gpt6 already holds {len(jobs)} job(s) from an earlier run; move gpt6/ and prompts/ "
                         "to attempts/<name>/ first (their finished jobs would be reused), or pass --force")
    modality = run_modality(selected)
    manifest = load_json(repo_root / SKILLS_MANIFEST)
    templates = load_templates()
    problems = skills_problems(templates, manifest)
    if problems:
        raise ValueError("; ".join(problems))
    frozen = fill_build(templates, run_date, len(selected), skills_checked_at or manifest["checked_at"], modality)
    schemas = {name: load_json(HERE / "schemas" / f"{name}.json") for name in SCHEMAS}
    first_prompts = {}
    for layer in selected:  # everything is checked before anything is written
        layer_input = load_json(work / "inputs" / f"{layer['layer_id']}.json")
        if layer.get("contract_version", 1) != 1 or layer_input.get("contract_version", 1) != 1:
            raise ValueError("V2 inputs require the future V2 runner; sweep.js and make_prompt.py still use the "
                             "V1 shared input and proposal projection, so no launchable run is staged")
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            if not layer_input.get(field):
                raise ValueError(f"inputs/{layer['layer_id']}.json has no {field}; rebuild it with build_inputs.py")
        # The frozen templates are the run's modality's (fill_build), and sweep.js reads each row's modality for the
        # discovery schema and the merge, so an input of another modality would get the wrong prompts.
        if (layer_input.get("modality") or REPOSITORY_MODALITY) != modality:
            raise ValueError(f"inputs/{layer['layer_id']}.json has modality "
                             f"{layer_input.get('modality') or REPOSITORY_MODALITY!r} but layers.json {modality!r}; "
                             "rebuild both with build_inputs.py")
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
    skills = modality != REPOSITORY_MODALITY
    worker_schemas = ("discover", "votes", "critic", *((SKILLS_SCHEMA,) if skills else ()))
    args = {"S": str(work), "stars": str(stars) if stars else None, "sweep_id": sweep_id, "T": frozen,
            "schemas": {name: schemas[name] for name in worker_schemas},
            "layers": [{"layer_id": layer["layer_id"], "catalog": layer["catalog"],
                        **({"modality": modality} if skills else {})} for layer in selected]}
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
    if fallback is not None:
        codex["fallback"] = fallback
    if lane is not None:
        codex.update(stage_lane_home(work, model=gpt6_model, base_url=lane["base_url"], host=lane["host"],
                                     profile=lane["profile"], repo_root=repo_root,
                                     require_key=lane.get("require_key", False),
                                     http_headers=lane.get("http_headers")))
    harness_files = sorted([*RUNTIME, "sweep.js", "templates.json", *(f"schemas/{name}.json" for name in SCHEMAS)])
    staged = {"schema_version": 1, "kind": "landscape_sweep_staging", "sweep_id": sweep_id, "date": run_date,
              "test": test, "modality": modality, "layers": [layer["layer_id"] for layer in selected],
              "prompts_sha256": digest,
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
    parser.add_argument("--contract-version", type=int, choices=(1, 2), default=1,
                        help="V1 runner only; V2 producer contracts await the future V2 runner")
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
    parser.add_argument("--gpt6-fallback", choices=("omniroute",),
                        help="opt in to transport-only native-limit failover, keeping the native prompt and inputs")
    parser.add_argument("--fallback-codex-host", metavar="HOST:PORT",
                        help="keyless loopback fallback gateway (default 127.0.0.1:20128); needs --gpt6-fallback")
    parser.add_argument("--omniroute-base-url", default=OMNIROUTE_DEFAULT_URL,
                        help=f"loopback OmniRoute Responses endpoint (default {OMNIROUTE_DEFAULT_URL})")
    parser.add_argument("--codex-host", metavar="HOST",
                        help="a host name (adoption/hosts/HOST.json in the checkout) or a path to a private host "
                             "value file (*.json; real hosts' files are gitignored), whose values render the lane's "
                             "token MCP servers (required with --gpt6-provider omniroute)")
    parser.add_argument("--stack-worker-profile", type=Path,
                        help=f"the Codex worker profile overlay (default {STACK_WORKER_PROFILE} in the checkout)")
    parser.add_argument("--omniroute-header", action="append", default=[], metavar="NAME=VALUE",
                        help="a static request header for the gateway (repeatable; --gpt6-provider omniroute only), "
                             "rendered as model_providers.omniroute.http_headers and recorded in staged.json: one of "
                             f"OmniRoute's per-request switches ({', '.join(OMNIROUTE_REQUEST_HEADERS)}) with a "
                             "printable ASCII value, e.g. x-omniroute-compression=allow-lossy")
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
    if args.contract_version == 2:
        parser.error("V2 staging requires the future V2 runner; prepare fields with build_inputs.py "
                     "--contract-version 2 without activating the V1 workflow")
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
        namespace, slash, rest = gpt6_model.partition("/")
        if slash and ("/" in rest or not re.fullmatch(r"[A-Za-z0-9_-]+", namespace)):
            raise UsageError("--gpt6-model may have one provider segment, of letters, digits, '_' and '-' only: "
                             "Codex strips only such a namespace, and any other slug gets fallback metadata "
                             "(openai/codex rust-v0.157.1, codex-rs/models-manager/src/manager.rs L763-780)")
        if not MODEL_NAME.fullmatch(gpt6_model):
            raise ValueError("--gpt6-model is not a model name")
        if args.omniroute_header and args.gpt6_provider != "omniroute":
            raise ValueError("--omniroute-header needs --gpt6-provider omniroute: the native lane has no provider block")
        fallback = None
        if args.fallback_codex_host and not args.gpt6_fallback:
            raise ValueError("--fallback-codex-host needs --gpt6-fallback omniroute")
        if args.gpt6_fallback:
            if args.gpt6_provider != "native" or slash:
                raise ValueError("--gpt6-fallback needs the native provider and a model without a provider segment")
            host = args.fallback_codex_host or "127.0.0.1:20128"
            match = re.fullmatch(r"(?:127\.0\.0\.1|localhost):([0-9]{1,5})", host)
            if match is None or not 1 <= int(match[1]) <= 65535:
                raise ValueError("--fallback-codex-host must be 127.0.0.1:PORT or localhost:PORT (1-65535)")
            fallback = {"provider": "omniroute", "base_url": f"http://{host}/v1"}
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
                    "require_key": args.omniroute_require_key,
                    "http_headers": omniroute_headers(args.omniroute_header)}
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
                        repo_root=args.repo_root.resolve(), quota_stop_percent=args.quota_stop_percent, lane=lane,
                        fallback=fallback)
    except (ValueError, OSError, KeyError) as error:
        print(f"build_args.py: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
