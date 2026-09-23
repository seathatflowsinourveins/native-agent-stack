#!/usr/bin/env python3
"""Run the Codex lane of the 2026-09-22 layer-verdict convergence.

For each packet under ``<work-dir>/packets/`` (written by ``lane_packets.py``)
without a valid ``<work-dir>/codex/<catalog>__<layer_id>.json`` already on
disk, fill the shared lane prompt (``lane-prompt.md``) with that packet's
absolute path, the repository root and ``LANE=codex``, then run

    codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
        -C <repo> --output-schema <schema> -o <out.tmp> --json \
        -c model_reasoning_effort=<effort> <prompt>

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
import hashlib
import json
import shlex
import subprocess
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


def existing_output_is_valid(out_path: Path, catalog: str, layer_id: str, packet_sha256: str) -> bool:
    """Resumable-skip check: the file must parse as a JSON object already
    forced onto this lane and this exact packet. A present-but-different
    ``packet_sha256`` (the packet changed since the file was written) is
    treated as invalid so the layer reruns; a missing ``packet_sha256`` on an
    otherwise-matching old file is not itself disqualifying -- a rerun would
    only fill it in, so there is nothing to gain by discarding the file."""
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
    return True


def fill_prompt(template: str, packet_path: Path, repo_root: Path) -> str:
    return (
        template.replace("{PACKET_PATH}", str(packet_path))
        .replace("{REPO_ROOT}", str(repo_root))
        .replace("{LANE}", LANE)
    )


def build_command(repo_root: Path, schema_path: Path, out_tmp: Path, effort: str, prompt_text: str,
                  model: str = None) -> list:
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
        prompt_text,
    ]


def run_attempt(cmd: list, timeout: float) -> dict:
    started = time.monotonic()
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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


def lane_provenance(prompt_path: Path) -> dict:
    """What produced a return: this runner file's and the filled prompt template's sha256."""
    return {"codex_lane_py_sha256": sha256_file(Path(__file__).resolve()),
            "prompt_sha256": sha256_file(Path(prompt_path))}


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

    layers_filter = None
    if args.layers:
        layers_filter = {item.strip() for item in args.layers.split(",") if item.strip()}

    packets = discover_packets(work_dir, layers_filter)
    codex_dir = work_dir / "codex"
    events_dir = codex_dir / "events"
    usage_path = codex_dir / "usage.jsonl"

    pending = []
    for catalog, layer_id, packet_path in packets:
        packet_sha256 = sha256_file(packet_path)
        out_path = codex_dir / f"{catalog}__{layer_id}.json"
        if existing_output_is_valid(out_path, catalog, layer_id, packet_sha256):
            continue
        pending.append((catalog, layer_id, packet_path, packet_sha256, out_path))

    if args.dry_run:
        strict_display = codex_dir / "lane-return.codex-strict.schema.json"
        print(f"# --dry-run writes nothing; a real run first writes {strict_display}", file=sys.stderr)
        for catalog, layer_id, packet_path, packet_sha256, out_path in pending:
            prompt_text = fill_prompt(template, packet_path.resolve(), repo)
            tmp_out = codex_dir / f"{catalog}__{layer_id}.out.tmp"
            cmd = build_command(repo, strict_display, tmp_out, args.effort, prompt_text, args.model)
            print(shlex.join(cmd))
        return 0

    events_dir.mkdir(parents=True, exist_ok=True)
    strict_schema_path = write_strict_schema(schema_path, codex_dir)
    provenance = lane_provenance(prompt_path)
    usage_lock = threading.Lock()
    failures: list = []

    def process(item):
        catalog, layer_id, packet_path, packet_sha256, out_path = item
        prompt_text = fill_prompt(template, packet_path.resolve(), repo)
        tmp_out = codex_dir / f"{catalog}__{layer_id}.out.tmp"
        cmd = build_command(repo, strict_schema_path.resolve(), tmp_out, args.effort, prompt_text, args.model)
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
            failures.append((catalog, layer_id, f"failed after retry: {last_failure}"))

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            list(executor.map(process, pending))
    else:
        for item in pending:
            process(item)

    failures_path = codex_dir / FAILURES_NAME
    if failures:
        failures_path.write_text(json.dumps({"lane": LANE, "failures": [
            {"catalog": catalog, "layer_id": layer_id, "reason": reason}
            for catalog, layer_id, reason in sorted(failures)]}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        for catalog, layer_id, _reason in sorted(failures):
            print(f"codex_lane: {catalog}__{layer_id} failed after retry", file=sys.stderr)
        return 1
    failures_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
