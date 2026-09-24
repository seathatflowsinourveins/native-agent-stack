#!/usr/bin/env python3
"""Run the Codex lane of the layer-verdict convergence.

For each packet under ``<work-dir>/packets/`` (written by ``lane_packets.py``)
without a valid ``<work-dir>/codex/<catalog>__<layer_id>.json`` already on
disk, fill the shared lane prompt (``lane-prompt.md``) with that packet's
absolute path, the repository root and ``LANE=codex``, then run

    codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
        -C <repo> --output-schema <schema> -o <out.tmp> --json \
        -c model_reasoning_effort=<effort> \
        --ignore-user-config -c features.hooks=false -c features.plugin_hooks=false \
        -c 'web_search="disabled"' -c 'cli_auth_credentials_store="file"' <prompt>

capturing the JSON event stream to
``<work-dir>/codex/events/<catalog>__<layer_id>.jsonl`` and a usage row per
attempt to ``<work-dir>/codex/usage.jsonl``. The event stream shape is not
assumed beyond "a sequence of JSON objects, one per line" -- extraction of a
model name or usage/token fields tolerates unknown shapes and never fails a
layer merely because neither was found in a given run.

``out.tmp`` (the agent's last message, written by ``-o``) is parsed as one
JSON object: ``lane`` is always forced to ``"codex"``; ``packet_sha256`` is
filled from the packet file's own sha256 when the model did not set it;
``model`` is runner-owned and never taken from the model's response text
(2026-09-23 peer audit): ``model.name`` is the runner's own observation -- the
``--model`` it passed to ``codex exec -m``, else the model name the event stream
carried, else ``"unknown"`` (which then fails record_verdicts.py's family
pattern) -- ``model.effort`` is ``--effort``, and ``model.family`` is
``"openai"`` (``codex exec`` is OpenAI's CLI; a non-OpenAI model name then fails
record_verdicts.py's family pattern). ``provenance`` is also runner-owned:
``{codex_lane_py_sha256, prompt_sha256}`` -- the sha256 of this script file and
of the prompt template it filled. The strict schema copy passed to ``codex
exec`` omits ``provenance``, ``model.family`` and the Claude lane's
``refutation``, since Codex strict output requires every listed property;
whatever ``model`` the response carries is replaced. A failing attempt
(non-zero exit, timeout, missing or unparseable ``out.tmp``) is retried
exactly once before the layer is recorded as failed (with its last reason in
``<work-dir>/codex/failures.json``, which record_verdicts.py turns into a
``failed`` run-manifest outcome) and left for the next run (resumable). Nothing here validates the full lane-return JSON Schema --
that is ``record_verdicts.py``'s job; this runner only fills the three
fields the contract assigns to it.

``--dry-run`` prints the exact command it would run for every pending layer,
one per line, and writes nothing -- no directories, no events, no usage rows,
no output files. Stdlib only; this script is a subprocess/text pipeline, not
a landscape-schema validator, so it does not import scripts/landscape.py.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import errno
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PROMPT = HERE / "lane-prompt.md"
DEFAULT_SCHEMA = HERE / "lane-return.schema.json"
# Codex structured output runs in strict mode, which rejects some JSON Schema keywords
# (observed 2026-09-22 with codex-cli 0.155.1: "In context=('properties', 'winner_keys'),
# 'uniqueItems' is not permitted", HTTP 400 invalid_json_schema). The strict copy drops
# them; record_verdicts.py still enforces every dropped rule when it validates a return.
STRICT_UNSUPPORTED_KEYWORDS = frozenset({"uniqueItems", "$schema", "$id", "title", "description"})
# Keywords whose value maps property names to subschemas or to name arrays: the names are
# data (a property may be called "title"), so only the subschemas are filtered and name
# arrays pass through unchanged.
SCHEMA_MAP_KEYWORDS = frozenset({"properties", "patternProperties", "$defs", "definitions", "dependentSchemas",
                                 "dependentRequired", "dependencies"})
# Keywords whose value is instance data, never a schema, so it is kept verbatim.
DATA_KEYWORDS = frozenset({"const", "enum", "default", "examples"})


def _top_level_lane_schema(schema) -> bool:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    return isinstance(properties, dict) and "provenance" in properties and "lane" in properties


def strict_output_schema(schema):
    """Return a copy of ``schema`` without keywords Codex strict output rejects."""
    if isinstance(schema, list):
        return [strict_output_schema(value) for value in schema]
    if not isinstance(schema, dict):
        return schema
    if _top_level_lane_schema(schema):
        schema = without_runner_owned(json.loads(json.dumps(schema)))
    strict = {}
    for key, value in schema.items():
        if key in STRICT_UNSUPPORTED_KEYWORDS:
            continue
        if key in DATA_KEYWORDS:
            strict[key] = value
        elif key in SCHEMA_MAP_KEYWORDS and isinstance(value, dict):
            strict[key] = {name: strict_output_schema(subschema) for name, subschema in value.items()}
        else:
            strict[key] = strict_output_schema(value)
    return strict


# Written by a runner, never asked of the model: (object path, property). refutation is the Claude
# lane's refutation summary (written by claude_lane.py), never a Codex field.
RUNNER_OWNED_PROPERTIES = ((), "provenance"), (("model",), "family"), ((), "refutation")
# The layers this run tried and could not produce a return for, with the reason, for
# record_verdicts.py's run manifest (outcome "failed" instead of a bare "missing").
FAILURES_NAME = "failures.json"


def without_runner_owned(schema):
    """Drop the runner-owned properties (and their ``required`` entries) from a lane schema copy."""
    for path, name in RUNNER_OWNED_PROPERTIES:
        node = schema
        for step in path:
            node = (node.get("properties") or {}).get(step) if isinstance(node, dict) else None
        if isinstance(node, dict):
            (node.get("properties") or {}).pop(name, None)
            if isinstance(node.get("required"), list):
                node["required"] = [item for item in node["required"] if item != name]
    return schema


def write_strict_schema(schema_path: Path, codex_dir: Path) -> Path:
    codex_dir.mkdir(parents=True, exist_ok=True)
    strict_path = codex_dir / "lane-return.codex-strict.schema.json"
    strict = strict_output_schema(json.loads(schema_path.read_text(encoding="utf-8")))
    strict_path.write_text(json.dumps(strict, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return strict_path
DEFAULT_TIMEOUT = 900.0
DEFAULT_EFFORT = "high"
LANE = "codex"

# Recognized directly on an event dict or anywhere nested under it (e.g. a
# ``turn.completed`` event's ``usage`` object). Extra keys on the event are
# ignored; missing keys are simply omitted from the extracted usage dict --
# this list is a superset covering both codex's ``usage`` shape
# (input_tokens/cached_input_tokens/cache_write_input_tokens/output_tokens/
# reasoning_output_tokens) and a couple of plausible synonyms, so an
# unrecognized future shape degrades to "no usage found" instead of raising.
USAGE_KEYS = (
    "input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "reasoning_output_tokens", "reasoning_tokens", "cached_tokens", "total_tokens",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def discover_packets(work_dir: Path, layers: "set[str] | None") -> list:
    """Sorted ``(catalog, layer_id, packet_path)`` for every
    ``packets/<catalog>__<layer_id>.json`` file, optionally filtered to the
    given set of layer ids (the part after ``__``, matched across every
    catalog). ``packets/SHA256SUMS`` itself is never a packet."""
    packets_dir = work_dir / "packets"
    found = []
    if not packets_dir.is_dir():
        return found
    for path in sorted(packets_dir.glob("*.json")):
        stem = path.stem
        if "__" not in stem:
            continue
        catalog, layer_id = stem.split("__", 1)
        if layers is not None and layer_id not in layers:
            continue
        found.append((catalog, layer_id, path))
    return found


def existing_output_is_valid(out_path: Path, catalog: str, layer_id: str, packet_sha256: str,
                             provenance: dict = None, configured_model: str = None,
                             configured_effort: str = None) -> bool:
    """Resumable-skip check: the file must parse as a JSON object already
    forced onto this lane and this exact packet. A present-but-different
    ``packet_sha256`` (the packet changed since the file was written) is
    treated as invalid so the layer reruns; a missing ``packet_sha256`` on an
    otherwise-matching old file is not itself disqualifying -- a rerun would
    only fill it in, so there is nothing to gain by discarding the file.

    ``provenance`` is the current ``lane_provenance(prompt_path)``: when given, the file's own
    ``provenance`` must equal it field for field. A return written by older lane code or from an older
    prompt (or one without provenance) is stale: record_verdicts.py rejects it, so skipping it would
    leave the layer rejected on every later run (PR #141 review). It reruns instead.

    A return whose ``model.name`` is ``"unknown"`` (no model was configured or observed; record_verdicts.py
    rejects it by family pattern), or differs from a given ``configured_model`` (the ``--model`` of this
    run), also reruns (round-2 review)."""
    if not out_path.exists():
        return False
    try:
        data = load_json(out_path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("lane") != LANE:
        return False
    if data.get("catalog") != catalog or data.get("layer_id") != layer_id:
        return False
    existing_hash = data.get("packet_sha256")
    if existing_hash and existing_hash != packet_sha256:
        return False
    if provenance is not None:
        # Field for field and nothing more: landscape.py rejects a provenance object with extra keys, so a
        # return carrying one is rerun, not skipped (Codex review of #145).
        if data.get("provenance") != provenance:
            return False
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    if model.get("name") in (None, "", "unknown"):
        return False
    if configured_model and model.get("name") != configured_model:
        return False
    # A changed --effort reruns the layer too (Codex review of #145): the requested reasoning setting must
    # not be silently ignored by resuming a return made at another effort.
    if configured_effort and model.get("effort") != configured_effort:
        return False
    return True


def fill_prompt(template: str, packet_path: Path, repo_root: Path) -> str:
    return (
        template.replace("{PACKET_PATH}", str(packet_path))
        .replace("{REPO_ROOT}", str(repo_root))
        .replace("{LANE}", LANE)
    )


def build_command(repo_root: Path, schema_path: Path, out_tmp: Path, effort: str, prompt_text: str,
                  model: str = None, isolation=()) -> list:
    return [
        "codex", "exec",
        *(["-m", model] if model else []),
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", str(repo_root),
        "--output-schema", str(schema_path),
        "-o", str(out_tmp),
        "--json",
        "-c", f"model_reasoning_effort={effort}",
        *isolation,
        prompt_text,
    ]


# Channels a lane child is denied by configuration (2026-09-23 re-record); memory stores, code indexes and
# the web can return the incumbent verdicts or the catalog's selection labels.
# - ``--ignore-user-config`` skips ``$CODEX_HOME/config.toml`` (auth still uses ``CODEX_HOME``), so the user's
#   MCP servers, plugins, profiles and project trust do not load, and without trust no project
#   ``.codex/config.toml`` loads either. Measured with codex-cli 0.155.1 from the agent-lab checkout
#   (RUST_LOG=info): a default ``codex exec`` initialized seven MCP servers (ai-memory, SocratiCode,
#   jCodeMunch, Serena, context-mode, plugin-runtime, OpenAI Developers MCP); with these flags only
#   plugin-runtime and OpenAI Developers MCP initialized.
# - Lifecycle hooks are off (``features.hooks``, ``features.plugin_hooks``).
# - Native web search is off (``web_search="disabled"``): without it a probe child ran a web search, with
#   it the child reported no web search tool.
# - A blind child runs with a run-scoped CODEX_HOME and an empty HOME (isolated_codex_home): the flags do not skip
#   ``$CODEX_HOME/AGENTS.md`` or user skills under ``~/.agents/skills``, which probe children loaded otherwise.
# Not denied: shell reads under ``--sandbox read-only`` (any host path, and CLIs such as ai-memory on PATH).
# Those rest on lane-prompt.md rule 1, a repository without ``.git`` (refused unless --allow-git-history) and the
# post-run blind audit below. A non-blind --allow-git-history run inherits the native Codex home.
# Per-server ``mcp_servers.<name>.enabled=false`` overrides are not used: codex rejects them as a partial
# table ("invalid transport") when the loaded config does not define that server.
# The file credential store is pinned (round 5, ISO-R5-4): a keyring or auto store from a system or managed layer
# would save a blind child's rotated tokens apart from the native auth.json.
ISOLATION_ARGS = ("--ignore-user-config", "-c", "features.hooks=false", "-c", "features.plugin_hooks=false",
                  "-c", 'web_search="disabled"', "-c", 'cli_auth_credentials_store="file"')

AUDIT_NAME = "blind-audit.json"
# CLIs that reach memory stores, code indexes, session history, git history or the network.
AUDIT_TOOLS = ("git", "ai-memory", "agentsview", "mcporter", "qmd", "socraticode", "jcodemunch", "serena",
               "sqlite3", "curl", "wget")
ABSOLUTE_PATH = re.compile(r"(?<![\w.~}-])(/[^\s'\"|;&<>()`]+)")
HOME_PATH = re.compile(r"(?:~|\$HOME|\$\{HOME\})(?:/[^\s'\"|;&<>()`]*)?")
# Any other environment variable used as a path (``$CODEX_HOME/AGENTS.md``, ``${XDG_DATA_HOME}/x``) can point
# outside the repository; only its value, which the event does not show, says where (round-2 review).
VARIABLE_PATH = re.compile(r"\$(?:\{(?!HOME\})[A-Za-z_]\w*\}|(?!HOME\b)[A-Za-z_]\w*)/[^\s'\"|;&<>()`]*")
# Only an expansion that transforms its value (${X%/*}, ${X:-/p}, ${X/a/b}, ${!X}) hides the path it builds; a plain
# ${name} is caught by VARIABLE_PATH when used as a path (independent review of 52344da8).
PARAMETER_EXPANSION = re.compile(r"\$\{(?:![^}]*|[^}]*[%#:/^,@*?\[][^}]*)\}")
# A ``cd`` that leaves the working directory for somewhere the command does not name: bare ``cd`` (home),
# ``cd -``, ``cd ~`` and ``cd $OLDPWD`` / ``cd "${OLDPWD}"`` (the previous directory), or any other bare variable.
CD_TARGET = re.compile(r"(?:^|[;&|\n(]|\b(?:ba|z|da)?sh\s+-l?c\s+['\"])\s*cd(?=$|[\s;&|)'\"])([^;&|\n)]*)")
UNNAMED_CD_TARGETS = re.compile(r"-|~|\$[A-Za-z_]\w*|\$\{[A-Za-z_]\w*\}|")
PARENT_PATH = re.compile(r"(?:^|[\s'\"=:])((?:[^\s'\"|;&<>()`]*/)?\.\.(?:/[^\s'\"|;&<>()`]*)?)")
ROOT_PATH = re.compile(r"(?:^|[\s'\"=])/(?=$|[\s'\";&|)])")
# Only the executable token of a command segment is exempt, and only when it is a system executable: the
# first word at the start, after ``;``, ``&&``, ``||``, ``|`` or a newline, or right after ``bash -lc '``
# (``sh -c "`` and the like). Every other absolute path outside the roots is flagged, a ``/usr/...`` or
# ``/bin/...`` data path included -- ``/bin/cat /usr/local/share/prior-verdict.json`` reads data (PR #141
# review). ``/dev/null`` stays exempt wherever it appears.
EXECUTABLE_TOKEN = re.compile(r"(?:^|;|&&|\|\||\||\n|\b(?:ba|z|da)?sh\s+-l?c\s+['\"])\s*(?=/)")
# ``/usr/`` only for its executable directories: ``bash -lc '/usr/local/share/verdicts/show'`` runs a script
# kept with data and is flagged (round-2 review).
SYSTEM_EXECUTABLE_PREFIXES = ("/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/", "/usr/local/bin/")
EXEMPT_PATHS = ("/dev/null",)


def executable_token_starts(command: str) -> set:
    """Offsets where a command segment's executable token begins, when that token is an absolute path."""
    return {match.end() for match in EXECUTABLE_TOKEN.finditer(command)}


def outside_paths(command: str, allowed_roots) -> list:
    """Absolute paths in ``command`` outside ``allowed_roots``, except /dev/null and a segment's system
    executable token."""
    executables = executable_token_starts(command)
    found = []
    for match in ABSOLUTE_PATH.finditer(command):
        path = match.group(1)
        if path in EXEMPT_PATHS:
            continue
        if match.start(1) in executables and path.startswith(SYSTEM_EXECUTABLE_PREFIXES):
            continue
        if any(path == root or path.startswith(root.rstrip("/") + "/") for root in allowed_roots):
            continue
        found.append(path)
    return found


def unnamed_cd_targets(command: str) -> list:
    """The raw argument of every ``cd`` in ``command`` that goes home or back rather than to a named path."""
    found = []
    for match in CD_TARGET.finditer(command):
        target = match.group(1).strip().strip("'\"").strip()
        if UNNAMED_CD_TARGETS.fullmatch(target):
            found.append(target or "(home)")
    return found


def blind_audit(events_path: Path, allowed_roots) -> dict:
    """Report-only reading of one child's event stream: web searches, MCP tool calls, and commands that
    name an absolute path outside ``allowed_roots`` (the repository and the packets directory) or run a
    CLI in AUDIT_TOOLS. A flag is evidence for the coordinator to review and disclose, not a verdict.

    This is a heuristic lower bound, not a boundary: it reads command text only, so a path a program
    computes (``python3 -c`` joining parts, a glob, a variable set earlier) and anything a command reads
    indirectly (a script's own reads, a config it loads, a symlink under the repository) are not seen."""
    report = {"web_search": 0, "mcp_tool_calls": 0, "commands": 0, "flagged_commands": []}
    if not events_path.is_file():
        return report
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        kind = item.get("type")
        if kind == "web_search":
            report["web_search"] += 1
        elif kind == "mcp_tool_call":
            report["mcp_tool_calls"] += 1
        elif kind == "command_execution":
            report["commands"] += 1
            command = item.get("command") if isinstance(item.get("command"), str) else ""
            reasons = [f"path outside the repository and packets: {path}"
                       for path in outside_paths(command, allowed_roots)]
            reasons += ["names the filesystem root /"] if ROOT_PATH.search(command) else []
            reasons += [f"home-relative path: {path}" for path in HOME_PATH.findall(command)]
            reasons += [f"variable path: {path}" for path in VARIABLE_PATH.findall(command)]
            # Parameter expansion (${CODEX_HOME%/*}, ${X:-/path}) builds a path the event does not show
            # (independent review of #145, BIND-R4-7).
            reasons += [f"parameter expansion: {match}" for match in PARAMETER_EXPANSION.findall(command)]
            reasons += [f"cd leaves for an unnamed directory: cd {target}" for target in unnamed_cd_targets(command)]
            reasons += [f"path climbs out of the working directory: {path}" for path in PARENT_PATH.findall(command)]
            words = set(re.findall(r"[A-Za-z][\w.-]*", command))
            reasons += [f"runs {tool}" for tool in AUDIT_TOOLS if tool in words]
            if reasons:
                report["flagged_commands"].append({"command": command, "reasons": reasons})
    return report


# The CODEX_HOME every blind child runs with (isolated_codex_home), or None to inherit the caller's.
CHILD_CODEX_HOME = None
# Where run-scoped Codex homes live: outside the work dir (which holds both lanes' returns) and outside the
# adjudication state dir (the position index), so no path a child derives from $CODEX_HOME reaches either
# (independent review of #145, BIND-R4-7). Each run gets a fresh directory there (mkdtemp); nothing is ever
# removed to make one (round 5, INT-R5-2: removing a home that was, or held, the native home deleted it).
CODEX_HOME_BASE_ENV = "NAS_CODEX_HOME_DIR"
DEFAULT_CODEX_HOME_BASE = Path("~/.local/state/native-agent-stack/codex-home")


class CodexHomeRefused(ValueError):
    """The run-scoped Codex home cannot be set up without touching a credential or a lane input."""


def codex_home_base() -> Path:
    """``$NAS_CODEX_HOME_DIR``, else ``~/.local/state/native-agent-stack/codex-home``, absolutized."""
    return Path(os.environ.get(CODEX_HOME_BASE_ENV) or DEFAULT_CODEX_HOME_BASE).expanduser().absolute()


def codex_home_prefix(work_dir: Path) -> str:
    """The name prefix of ``work_dir``'s run homes under codex_home_base: sha256(resolved work dir)[:16]."""
    return hashlib.sha256(str(Path(work_dir).resolve()).encode("utf-8")).hexdigest()[:16]


def native_codex_home() -> Path:
    """The native Codex home: ``$CODEX_HOME``, else ``~/.codex``, absolutized."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().absolute()


def native_auth_path() -> Path:
    """The native Codex credential, ``native_codex_home()/auth.json``."""
    return native_codex_home() / "auth.json"


def _contains(outer: Path, inner: Path) -> bool:
    return inner == outer or outer in inner.parents


def _overlap(first: Path, second: Path) -> bool:
    spellings = [(a, b) for a in {first, Path(os.path.realpath(first))} for b in {second, Path(os.path.realpath(second))}]
    return any(_contains(a, b) or _contains(b, a) for a, b in spellings)


def isolated_codex_home(work_dir: Path, repo: Path = None) -> Path:
    """Create a fresh run-scoped CODEX_HOME (mode 0700) under codex_home_base, holding only a symlink to the native
    ``auth.json`` (never a copy) and the child's empty HOME. ``--ignore-user-config`` skips config.toml but not
    ``$CODEX_HOME/AGENTS.md``, the user's global instructions, which name adopted tools (measured 2026-09-24: a
    child quoted its "# AGENTS.md instructions" block; with this home it answered "none"). A fresh directory per
    run (tempfile.mkdtemp) means no leftover AGENTS.md or config is loaded and nothing is removed to make it; the
    caller removes the credential link when the run ends (remove_codex_home_link). The child's sessions and logs
    stay in the run home for inspection.

    The child's HOME is the empty ``<run home>/home`` (child_home): Codex also discovers user Agent Skills under
    ``$HOME/.agents/skills``, whose names are adopted tools (review of #145, measured 2026-09-24: a child with this
    CODEX_HOME but the caller's HOME listed qmd, tavily-* and typesafe-ai; with the empty HOME it listed only the
    CLI's bundled skills).

    Raises CodexHomeRefused, creating nothing, when the base and the native Codex home are one directory or one
    lies inside the other (either spelling), when the base lies inside the work dir or ``repo``, or when there is
    neither a native auth.json nor CODEX_API_KEY/OPENAI_API_KEY (independent review of #145, rounds 4 and 5)."""
    base = codex_home_base()
    native_home = native_codex_home()
    if _overlap(base, native_home):
        raise CodexHomeRefused(f"the run-scoped Codex homes' base {base} and the native Codex home {native_home} "
                               f"overlap; set {CODEX_HOME_BASE_ENV} to a directory apart from the native home")
    for place in (Path(work_dir).resolve(), *([Path(repo).resolve()] if repo is not None else [])):
        if _overlap(base, place):
            raise CodexHomeRefused(f"the run-scoped Codex homes' base {base} overlaps {place}; set "
                                   f"{CODEX_HOME_BASE_ENV} to a directory outside the work dir and the export")
    native = native_auth_path()
    if not native.is_file() and not (os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        raise CodexHomeRefused(f"no native Codex credential at {native} and no CODEX_API_KEY or OPENAI_API_KEY; sign "
                               "in natively with `codex login`")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    home = Path(tempfile.mkdtemp(prefix=f"{codex_home_prefix(work_dir)}-", dir=base))
    home.chmod(0o700)
    child_home(home).mkdir(mode=0o700)
    if native.is_file():
        (home / "auth.json").symlink_to(native)
    return home


def remove_codex_home_link(home) -> None:
    """Remove the run-scoped home's credential link at the end of a run (independent review of #145, OPS-4); the
    child's sessions and logs stay for inspection. Only a symlink is ever removed."""
    if home is None:
        return
    link = Path(home) / "auth.json"
    if link.is_symlink():
        link.unlink()


RUN_LOCK_NAME = ".run.lock"


class RunLocked(RuntimeError):
    """Another run holds this work dir's lock."""


@contextlib.contextmanager
def exclusive_run_lock(path: Path):
    """Hold an exclusive, non-blocking flock on ``path`` for the run (independent review of #145, BIND-R4-5): two
    runs on one work dir would recreate each other's Codex home and interleave each other's events files."""
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RunLocked(f"another run holds {path}; wait for it to finish") from None
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


# The environment a blind child gets (independent review of #145, round 5, ISO-R5-2): not the caller's, which
# carries the coordinator's transcript pointer, cross-session messaging socket and token, and broker variables.
CHILD_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
                       "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy",
                       "all_proxy")
# Extra variable-name prefixes a child keeps; empty in production (the test fixtures' fake codex reads its own).
CHILD_ENV_EXTRA_PREFIXES = ()


def child_env(codex_home: Path) -> dict:
    """The whole environment of a blind child: the allowlisted variables, CODEX_HOME, the empty HOME, and an API
    key variable only when the run home holds no linked auth.json."""
    env = {key: value for key, value in os.environ.items()
           if key in CHILD_ENV_ALLOWLIST or (CHILD_ENV_EXTRA_PREFIXES and key.startswith(CHILD_ENV_EXTRA_PREFIXES))}
    env.update({"CODEX_HOME": str(codex_home), "HOME": str(child_home(codex_home))})
    if not (Path(codex_home) / "auth.json").exists():
        env.update({key: os.environ[key] for key in ("CODEX_API_KEY", "OPENAI_API_KEY") if os.environ.get(key)})
    return env


def child_home(codex_home: Path) -> Path:
    """The empty HOME a blind child runs with, inside its run-scoped CODEX_HOME (isolated_codex_home)."""
    return Path(codex_home) / "home"


def run_attempt(cmd: list, timeout: float) -> dict:
    started = time.monotonic()
    env = child_env(CHILD_CODEX_HOME) if CHILD_CODEX_HOME is not None else None
    try:
        # No stdin (round 5, ISO-R5-3): codex exec appends a non-terminal stdin to the prompt and waits for its end.
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                                   stdin=subprocess.DEVNULL)
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "elapsed": time.monotonic() - started,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills the child and re-raises after collecting
        # whatever communicate() had already buffered. On POSIX the partial
        # output arrives as bytes even with text=True, so decode it rather
        # than discard the events and usage an attempt produced before timing out.
        def decoded(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value if isinstance(value, str) else ""

        stdout = decoded(exc.stdout)
        stderr = decoded(exc.stderr)
        return {
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed": time.monotonic() - started,
            "timed_out": True,
        }


def parse_events(stdout_text: str) -> list:
    """One JSON object per non-blank line; a line that fails to parse (e.g.
    truncated mid-write by a killed timeout) is dropped rather than raising --
    the event stream is diagnostic, not a contract this script enforces."""
    events = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _find_first_str(node, key: str):
    if isinstance(node, dict):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
        for child in node.values():
            found = _find_first_str(child, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_str(item, key)
            if found is not None:
                return found
    return None


def _find_usage(node):
    if isinstance(node, dict):
        matched = {key: node[key] for key in USAGE_KEYS if key in node}
        if matched:
            return matched
        for child in node.values():
            found = _find_usage(child)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_usage(item)
            if found:
                return found
    return None


def extract_events_summary(events: list):
    """Model name and usage/token fields found in the *last* events that
    carry them (later events -- e.g. ``turn.completed`` -- override earlier
    ones), tolerant of any event shape. Returns ``(model_name_or_None,
    usage_dict_possibly_empty)``; never raises."""
    model_name = None
    usage: dict = {}
    for event in events:
        found_model = _find_first_str(event, "model")
        if found_model:
            model_name = found_model
        found_usage = _find_usage(event)
        if found_usage:
            usage = found_usage
    return model_name, usage


LANE_FAMILY = "openai"


# The repository roots the blind-adjudicator role refuses (agent-lab PR #40), enforced by every blind tool:
# blind_checkout --export, both lane runners and adjudicate (round-2 review; independent review of #145, O3).
MIN_ROOT_COMPONENTS = 4
REFUSED_ROOTS = ("/", "/home", "/tmp", "/Users", "/root")


def root_issue(path) -> str:
    """None when ``path`` is a repository root blind-adjudicator accepts, else why not: it must be absolute with
    no ``.``/``..`` segment, ``~``, ``$`` or wildcard, and not ``/``, ``/home``, ``/tmp``, a home directory
    (``/home/<name>``, ``/Users/<name>``, ``/root`` or this user's home) or a path of fewer than four
    components."""
    text = str(path)
    parts = [part for part in text.split("/") if part]
    if not text.startswith("/"):
        return f"{text!r} is not an absolute path"
    if any(part in (".", "..") for part in parts) or any(char in text for char in "~$*?["):
        return f"{text!r} has a '.', '..', '~', '$' or wildcard segment"
    if any(char.isspace() for char in text):
        # Path scrubbing tokenizes on whitespace, so a root with a space could not be recognized in the returns.
        return f"{text!r} contains whitespace"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", text):
        # Parentheses, quotes, backticks and the other tokenizer delimiters would split the root in scrubbing.
        return f"{text!r} contains a character outside [A-Za-z0-9._/-]"
    home = str(Path.home()).rstrip("/")
    if (text.rstrip("/") or "/") in REFUSED_ROOTS or text.rstrip("/") == home or (
            len(parts) == 2 and parts[0] in ("home", "Users")):
        return f"{text!r} is /, /home, /tmp or a home directory"
    if len(parts) < MIN_ROOT_COMPONENTS:
        return f"{text!r} has {len(parts)} path components; a repository root needs at least {MIN_ROOT_COMPONENTS}"
    return None


def tree_sha256(repo: Path, allow_escaping_links: bool = False) -> str:
    """A digest of the evidence repository's content: every regular file's relative path and sha256, sorted,
    and each retained symlink's text. The packet names evidence paths, not their bytes, so a return (and an
    adjudication judgment) is bound to the tree it read."""
    repo = Path(repo)
    if not repo.is_dir():
        # An empty walk would hash to a valid-looking digest (Codex review of #145).
        raise NotADirectoryError(f"evidence repository {repo} is not an existing directory")
    digest = hashlib.sha256()
    root = repo.resolve()
    for path in sorted(repo.rglob("*")):
        relative = path.relative_to(repo).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            try:
                # A loop is found by stat (ELOOP) on every Python version: 3.13's resolve() no longer raises on one
                # (delta review of #145). A dangling internal link (ENOENT) is hashed by its text.
                os.stat(path)
            except OSError as error:
                if error.errno == errno.ELOOP:
                    if not allow_escaping_links:
                        raise ValueError(f"evidence repository {repo} has a symlink loop: {relative}")
                    # A non-blind run hashes a looping link by its text without resolving it: 3.12's resolve()
                    # raises RuntimeError on a loop (independent review of #145, R4-REG-4).
                    digest.update(f"{relative}\0->{target}\n".encode("utf-8"))
                    continue
            resolved = (path.parent / target).resolve(strict=False)
            if not allow_escaping_links and (os.path.isabs(target)
                                             or not (resolved == root or root in resolved.parents)):
                # Content behind an escaping link could change under an unchanged digest (Codex review of #145);
                # blind_checkout --export removes such links, so one here means the tree is not a blind export.
                raise ValueError(f"evidence repository {repo} has a symlink leaving it: {relative} -> {target}")
            # A retained internal link: its text is part of the tree (the target file is hashed on its own).
            digest.update(f"{relative}\0->{target}\n".encode("utf-8"))
        elif path.is_file():
            digest.update(f"{relative}\0{sha256_file(path)}\n".encode("utf-8"))
        elif not path.is_dir() and not allow_escaping_links:
            # A FIFO, socket or device is not evidence and would otherwise be skipped silently (cross-family
            # review of #145). A deliberately non-blind run may hold git's fsmonitor socket, so it is not refused.
            raise ValueError(f"evidence repository {repo} has a non-regular entry: {relative}")
    return digest.hexdigest()


def lane_provenance(prompt_path: Path, repo: Path = None, allow_escaping_links: bool = False) -> dict:
    """What produced a return: this runner file's and the filled prompt template's sha256, and (given
    ``repo``) the digest of the evidence tree the lane read, so a resume against another export reruns
    (Codex review of #145)."""
    provenance = {"codex_lane_py_sha256": sha256_file(Path(__file__).resolve()),
                  "prompt_sha256": sha256_file(Path(prompt_path))}
    if repo is not None:
        provenance["repo_tree_sha256"] = tree_sha256(Path(repo), allow_escaping_links)
    return provenance


def finalize_lane_return(data: dict, catalog: str, layer_id: str, packet_sha256: str,
                          event_model_name, effort: str, provenance: dict = None,
                          configured_model: str = None) -> dict:
    data = dict(data)
    data["lane"] = LANE
    if not data.get("packet_sha256"):
        data["packet_sha256"] = packet_sha256
    # Runner-owned: the model identity is what this runner configured or observed in the event
    # stream, never the model's self-declared name, effort, family or provenance.
    data["model"] = {"name": configured_model or event_model_name or "unknown", "effort": effort,
                     "family": LANE_FAMILY}
    if provenance is not None:
        data["provenance"] = dict(provenance)
    return data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2] if len(__doc__.splitlines()) > 2 else __doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--layers", default=None,
                         help="Comma-separated layer ids to run (matched across every catalog); default: all.")
    parser.add_argument("--effort", default=DEFAULT_EFFORT, help="model_reasoning_effort passed via -c.")
    parser.add_argument("--model", default=None,
                        help="Model passed to codex exec -m and recorded as the return's model.name "
                             "(default: Codex's configured model, recorded from the event stream).")
    parser.add_argument("--jobs", type=int, default=1, help="Concurrent codex exec invocations.")
    parser.add_argument("--dry-run", action="store_true", help="Print the command per pending layer; write nothing.")
    parser.add_argument("--allow-git-history", action="store_true",
                        help="Run against a --repo that has .git. A blind wave never does: git history recovers "
                             "every label blind_checkout.py strips, so give the lanes its --export copy.")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT,
                         help="Override the lane prompt template path (default: lane-prompt.md next to this script).")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA,
                         help="Override the JSON Schema path passed to --output-schema "
                              "(default: lane-return.schema.json next to this script).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                         help="Per-attempt codex exec timeout in seconds (default: 900).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    work_dir = args.work_dir.resolve()
    repo = args.repo.resolve()
    prompt_path = args.prompt
    schema_path = args.schema

    if not prompt_path.exists():
        print(f"codex_lane: prompt template not found: {prompt_path}", file=sys.stderr)
        return 2
    if not schema_path.exists():
        print(f"codex_lane: output schema not found: {schema_path}", file=sys.stderr)
        return 2
    template = prompt_path.read_text(encoding="utf-8")
    if not repo.is_dir():
        print(f"codex_lane: --repo {repo} is not an existing directory", file=sys.stderr)
        return 2
    if not args.allow_git_history:
        # The blind export must sit where the adjudicator role accepts it, checked as given and resolved (O3).
        for candidate in (Path(os.path.abspath(args.repo)), repo):
            issue = root_issue(candidate)
            if issue:
                print(f"codex_lane: --repo {issue}; place the blind export at least four directories deep (not /, "
                      "/home, /tmp or a home directory itself) and outside every repository", file=sys.stderr)
                return 2
    git_dirs = [str(path) for path in (repo, *repo.parents) if (path / ".git").exists()]
    if git_dirs and not args.allow_git_history:
        # git walks up from a subdirectory, so an export inside any repository still reaches history.
        print(f"codex_lane: {git_dirs[0]} has .git, whose history a child can read from {repo}; run the lane on a "
              "blind_checkout.py --export copy placed outside every repository, or pass --allow-git-history "
              "outside a blind wave", file=sys.stderr)
        return 2

    work_repos = [str(path) for path in (work_dir, *work_dir.parents) if (path / ".git").exists()]
    if work_repos and not args.allow_git_history:
        # WORK_DIR sits outside every repository, as the recipe says (independent review of #145, round 4, OPS-6).
        print(f"codex_lane: --work-dir {work_dir} is inside the git repository {work_repos[0]}; place it outside "
              "every repository", file=sys.stderr)
        return 2

    layers_filter = None
    if args.layers:
        layers_filter = {item.strip() for item in args.layers.split(",") if item.strip()}

    packets = discover_packets(work_dir, layers_filter)
    codex_dir = work_dir / "codex"
    events_dir = codex_dir / "events"
    usage_path = codex_dir / "usage.jsonl"

    global CHILD_CODEX_HOME
    try:
        # A deliberately non-blind run (--allow-git-history) may read a checkout whose ignored .venv links leave
        # it (re-review L2); a blind export never has such links.
        provenance = lane_provenance(prompt_path, repo, allow_escaping_links=args.allow_git_history)
    except ValueError as error:  # an escaping symlink: not a blind export
        print(f"codex_lane: {error}", file=sys.stderr)
        return 2
    pending = []
    for catalog, layer_id, packet_path in packets:
        packet_sha256 = sha256_file(packet_path)
        out_path = codex_dir / f"{catalog}__{layer_id}.json"
        if existing_output_is_valid(out_path, catalog, layer_id, packet_sha256, provenance, args.model,
                                    args.effort):
            continue
        pending.append((catalog, layer_id, packet_path, packet_sha256, out_path))

    blind = not args.allow_git_history
    if args.dry_run:
        strict_display = codex_dir / "lane-return.codex-strict.schema.json"
        print(f"# --dry-run writes nothing; a real run first writes {strict_display}", file=sys.stderr)
        # A blind child's environment is printed with its command; the dry run creates no home (OPS-4).
        run_home = codex_home_base() / f"{codex_home_prefix(work_dir)}-<run>"
        if blind:
            print(f"# a real run creates a fresh {run_home} (mkdtemp) and runs each child with only this environment",
                  file=sys.stderr)
        # Never an API key value on stdout: the printed environment omits the key variables.
        env_prefix = ["env", "-i", *(f"{key}={value}" for key, value in child_env(run_home).items()
                                     if key not in ("CODEX_API_KEY", "OPENAI_API_KEY"))] if blind else []
        for catalog, layer_id, packet_path, packet_sha256, out_path in pending:
            prompt_text = fill_prompt(template, packet_path.resolve(), repo)
            tmp_out = codex_dir / f"{catalog}__{layer_id}.out.tmp"
            cmd = build_command(repo, strict_display, tmp_out, args.effort, prompt_text, args.model, ISOLATION_ARGS)
            print(shlex.join(env_prefix + cmd))
        return 0

    if pending and shutil.which("codex") is None:
        # A missing CLI is a setup error, not a lane failure: say so instead of a traceback.
        print("codex_lane: the codex CLI is not on PATH; install it and sign in natively "
              "(see adoption/) before running the Codex lane", file=sys.stderr)
        return 2
    with contextlib.ExitStack() as stack:
        if pending:
            try:
                stack.enter_context(exclusive_run_lock(codex_dir / RUN_LOCK_NAME))
            except RunLocked as error:
                print(f"codex_lane: {error}", file=sys.stderr)
                return 2
        if pending and blind:
            # Blind children never load the user's global Codex instructions or user skills (isolated_codex_home),
            # set up only once every refusal has passed, the run holds its lock and something is to run (R4-REG-3).
            try:
                CHILD_CODEX_HOME = isolated_codex_home(work_dir, repo)
            except CodexHomeRefused as error:
                print(f"codex_lane: {error}", file=sys.stderr)
                return 2
        try:
            return run_pending(args, work_dir, repo, template, schema_path, codex_dir, events_dir, usage_path,
                               pending, provenance)
        finally:
            remove_codex_home_link(CHILD_CODEX_HOME)
            CHILD_CODEX_HOME = None


def run_pending(args, work_dir, repo, template, schema_path, codex_dir, events_dir, usage_path, pending,
                provenance) -> int:
    events_dir.mkdir(parents=True, exist_ok=True)
    strict_schema_path = write_strict_schema(schema_path, codex_dir)
    usage_lock = threading.Lock()
    failures: list = []

    def process(item):
        catalog, layer_id, packet_path, packet_sha256, out_path = item
        prompt_text = fill_prompt(template, packet_path.resolve(), repo)
        tmp_out = codex_dir / f"{catalog}__{layer_id}.out.tmp"
        cmd = build_command(repo, strict_schema_path.resolve(), tmp_out, args.effort, prompt_text, args.model,
                            ISOLATION_ARGS)
        events_path = events_dir / f"{catalog}__{layer_id}.jsonl"
        events_path.write_text("", encoding="utf-8")

        succeeded = False
        last_model_name = None
        last_failure = "no attempt ran"
        for attempt in (1, 2):
            # Clear any stale out.tmp left by a killed prior run (SIGKILL,
            # Ctrl-C, OOM) before launching this attempt, so a codex exec
            # that exits 0 without writing -o is never misread as having
            # produced a stale earlier attempt's (or run's) output.
            tmp_out.unlink(missing_ok=True)
            result = run_attempt(cmd, args.timeout)
            events = parse_events(result["stdout"])
            with events_path.open("a", encoding="utf-8") as handle:
                for line in result["stdout"].splitlines():
                    if line.strip():
                        handle.write(line + "\n")

            model_name, usage = extract_events_summary(events)
            if model_name:
                last_model_name = model_name

            usage_row = {
                "catalog": catalog, "layer": layer_id, "attempt": attempt,
                "exit_code": result["exit_code"], "timed_out": result["timed_out"],
                "model": model_name, "seconds": round(result["elapsed"], 3),
            }
            usage_row.update(usage)
            with usage_lock, usage_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(usage_row, sort_keys=True) + "\n")

            if result["timed_out"] or result["exit_code"] != 0:
                last_failure = "timed out" if result["timed_out"] else f"codex exec exited {result['exit_code']}"
                tmp_out.unlink(missing_ok=True)
                continue
            if not tmp_out.exists():
                last_failure = "codex exec wrote no output file"
                continue
            try:
                data = load_json(tmp_out)
            except (json.JSONDecodeError, UnicodeDecodeError):
                last_failure = "the output file was not valid JSON"
                tmp_out.unlink(missing_ok=True)
                continue
            if not isinstance(data, dict):
                last_failure = "the output was not a JSON object"
                tmp_out.unlink(missing_ok=True)
                continue

            final = finalize_lane_return(data, catalog, layer_id, packet_sha256, last_model_name, args.effort,
                                         provenance, configured_model=args.model)
            out_path.write_text(json.dumps(final, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            tmp_out.unlink(missing_ok=True)
            succeeded = True
            break

        if not succeeded:
            # A stale return (e.g. one rejected for an older packet hash) must
            # not survive, so record_verdicts.py records this `failed` reason.
            out_path.unlink(missing_ok=True)
            failures.append((catalog, layer_id, f"failed after retry: {last_failure}"))

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            list(executor.map(process, pending))
    else:
        for item in pending:
            process(item)

    try:
        tree_after = tree_sha256(repo, allow_escaping_links=args.allow_git_history)
    except ValueError:
        tree_after = None
    if pending and tree_after != provenance["repo_tree_sha256"]:
        # The evidence changed while the children read it (Codex review of #145): no return of this run is
        # bound to one tree, so each is set aside (kept for inspection, never resumed or sealed).
        for catalog, layer_id, _packet_path, _packet_sha256, out_path in pending:
            if out_path.is_file():
                out_path.replace(out_path.with_name(out_path.name + ".tree-changed"))
            failures.append((catalog, layer_id, "the evidence tree changed during the run; rerun on a fixed export"))

    audit_path = codex_dir / AUDIT_NAME
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
    except ValueError:
        audit = {}
    layers = audit.get("layers") if isinstance(audit.get("layers"), dict) else {}
    roots = [str(repo), str((work_dir / "packets").resolve())]
    for catalog, layer_id, _packet_path, _packet_sha256, _out_path in pending:
        layers[f"{catalog}__{layer_id}"] = blind_audit(events_dir / f"{catalog}__{layer_id}.jsonl", roots)
    audit_path.write_text(json.dumps({"schema_version": 1, "allowed_roots": roots, "layers": layers},
                                     indent=1, sort_keys=True) + "\n", encoding="utf-8")
    flagged = sorted(name for name, entry in layers.items()
                     if entry["web_search"] or entry["mcp_tool_calls"] or entry["flagged_commands"])
    if flagged:
        print(f"codex_lane: blind audit flags {len(flagged)} layer(s) for review in {audit_path}: "
              + ", ".join(flagged), file=sys.stderr)
    if not args.allow_git_history:
        # In a blind run a flagged layer (a read outside the export and packets, web search or an MCP tool) is void,
        # as an adjudication judgment is: it may have read the packet keys or another lane's return (Codex review of
        # #145). Its return is set aside and the layer is recorded as failed.
        this_run = {f"{catalog}__{layer_id}": out_path for catalog, layer_id, _p, _s, out_path in pending}
        for name in flagged:
            out_path = this_run.get(name)
            if out_path is None:
                continue
            if out_path.is_file():
                out_path.replace(out_path.with_name(out_path.name + ".audit-flagged"))
            catalog, _, layer_id = name.partition("__")
            failures.append((catalog, layer_id, "the blind audit flagged this layer's calls (web, MCP or a read "
                                                 "outside the export and packets)"))

    failures_path = codex_dir / FAILURES_NAME
    if failures:
        failures_path.write_text(json.dumps({"lane": LANE, "failures": [
            {"catalog": catalog, "layer_id": layer_id, "reason": reason}
            for catalog, layer_id, reason in sorted(failures)]}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        for catalog, layer_id, reason in sorted(failures):
            print(f"codex_lane: {catalog}__{layer_id}: {reason}", file=sys.stderr)
        return 1
    failures_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
