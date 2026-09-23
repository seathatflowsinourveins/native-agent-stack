#!/usr/bin/env python3
"""Two-family, counterbalanced adjudication of the layers on which the two lanes disagree.

A layer's Claude and Codex returns (``<work-dir>/{claude,codex}/<catalog>__<layer_id>.json``) disagree
when their winner component sets, resolved against the layer packet with
``scripts/landscape.py lane_winner_components``, differ. Such a layer is judged blind by both model
families, each in both presentation orders, and every judgment is attacked by one refuter:

1. ``inputs``: writes ``<work-dir>/adjudication-inputs/<name>.AB.json`` (A = the scrubbed Claude
   return, B = the scrubbed Codex return) and ``<name>.BA.json`` (swapped), plus ``index.json``.
   Scrubbing keeps only the judged content (SCRUB_KEEP) and drops any kept key present in one return
   but not the other, so lane identity, model and provenance are not shown to the judge.
2. ``codex``: one ``codex exec`` judge call and one refuter call per input file, built like
   codex_lane.py's command (read-only sandbox, codex_lane.ISOLATION_ARGS, ``--output-schema``,
   ``-o``, ``--json``). Writes ``<work-dir>/adjudication-judgments/codex/<name>.<order>.json``.
3. ``claude-args`` / ``claude-collect``: the args for ``adjudication-lane.js`` (the Claude family's
   saved workflow) and the step that turns its return into
   ``<work-dir>/adjudication-judgments/claude/<name>.<order>.json`` in the same shape.
4. ``assemble``: builds one adjudication record per layer, ``<out>/<name>.json``, validated by
   ``scripts/landscape.py judge_adjudication(raw, grandfathered=False, packet_sha256=...)`` before it is
   written; ``record_verdicts.py --adjudications <out>`` reads them.

A winner needs unanimous, unrefuted judgments from both families, each covering both orders; anything
else is a split (winner_lane null). A judgment counts only when both its judge and its refuter returned
a valid object: a lost refuter is never read as "unrefuted". Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for _path in (HERE, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import codex_lane  # noqa: E402
from scripts.landscape import (  # noqa: E402
    FAMILY_MODEL_PATTERNS, LANE_FAMILIES, judge_adjudication, lane_winner_components)

PROMPT_PATH = HERE / "adjudication-prompt.md"
JUDGE_SCHEMA = HERE / "adjudication-judge.schema.json"
REFUTE_SCHEMA = HERE / "adjudication-refute.schema.json"
REFUTER_MARKER = "<!-- refuter -->"
ORDERS = ("AB", "BA")
# claude_position per order: AB shows the Claude return as A, BA shows it as B.
CLAUDE_POSITION = {"AB": "A", "BA": "B"}
FAMILIES = {"claude": "anthropic", "codex": "openai"}
assert FAMILIES == LANE_FAMILIES
SCRUB_KEEP = ("winner_keys", "why_selected", "winner_evidence_class", "winner_evidence_refs", "alternatives",
              "challenger_preferred", "overturn_when", "overturn_protocol", "open_gaps", "sources_read", "limits")
# Words that can name a lane in the kept prose. Only reported (index.json identity_mentions), never
# redacted: a candidate can legitimately be called "codex" or "claude".
IDENTITY_WORDS = re.compile(r"\b(claude|codex|anthropic|openai|opus|sonnet|haiku|gpt-[\w.-]+)\b", re.IGNORECASE)
MIN_WHY = 60
DEFAULT_TIMEOUT = 900.0
INPUTS_DIR = "adjudication-inputs"
JUDGMENTS_DIR = "adjudication-judgments"
JUDGMENT_SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- inputs

def scrub_pair(claude_return: dict, codex_return: dict):
    """(scrubbed claude, scrubbed codex): only SCRUB_KEEP keys present in both returns."""
    shared = [key for key in SCRUB_KEEP if key in claude_return and key in codex_return]
    return ({key: claude_return[key] for key in shared}, {key: codex_return[key] for key in shared})


def identity_mentions(scrubbed: dict) -> list:
    return sorted({match.group(0).lower() for match in IDENTITY_WORDS.finditer(json.dumps(scrubbed))})


def components_list(components) -> list:
    return sorted([component_id, repository] for component_id, repository in components)


def build_inputs(work_dir: Path, layers=None) -> dict:
    """Write the counterbalanced input files and index.json; return the index."""
    work_dir = Path(work_dir).resolve()
    out_dir = work_dir / INPUTS_DIR
    index = {"schema_version": 1, "layers": [], "skipped": []}
    for packet_path in sorted((work_dir / "packets").glob("*.json")):
        name = packet_path.stem
        if "__" not in name or (layers and name.split("__", 1)[1] not in layers and name not in layers):
            continue
        paths = {lane: work_dir / lane / f"{name}.json" for lane in FAMILIES}
        if not all(path.is_file() for path in paths.values()):
            continue
        packet_sha256 = sha256_file(packet_path)
        returns, reasons = {}, []
        try:
            packet = load_json(packet_path)
        except (OSError, ValueError) as error:
            index["skipped"].append({"layer": name, "reason": f"packet unreadable: {error}"})
            continue
        for lane, path in paths.items():
            try:
                data = load_json(path)
            except (OSError, ValueError) as error:
                reasons.append(f"{lane} return does not parse: {error}")
                continue
            if not isinstance(data, dict):
                reasons.append(f"{lane} return is not a JSON object")
            elif data.get("packet_sha256") != packet_sha256:
                reasons.append(f"{lane} return packet_sha256 {data.get('packet_sha256')!r} is not the packet's "
                               f"{packet_sha256}")
            else:
                returns[lane] = data
        components = {}
        for lane, data in returns.items():
            issue, found = lane_winner_components(data, packet)
            if issue:
                reasons.append(f"{lane} return: {issue}")
            else:
                components[lane] = found
        if reasons:
            index["skipped"].append({"layer": name, "reason": "; ".join(reasons)})
            continue
        entry = {"layer": name, "packet_path": str(packet_path), "packet_sha256": packet_sha256,
                 "components": {lane: components_list(components[lane]) for lane in FAMILIES}}
        if components["claude"] == components["codex"]:
            entry["agreement"] = "agree"
            index["layers"].append(entry)
            continue
        entry["agreement"] = "disagree"
        claude_scrubbed, codex_scrubbed = scrub_pair(returns["claude"], returns["codex"])
        entry["identity_mentions"] = sorted(set(identity_mentions(claude_scrubbed))
                                            | set(identity_mentions(codex_scrubbed)))
        entry["inputs"] = {}
        for order in ORDERS:
            a, b = (claude_scrubbed, codex_scrubbed) if order == "AB" else (codex_scrubbed, claude_scrubbed)
            input_path = out_dir / f"{name}.{order}.json"
            write_json(input_path, {"layer": name, "packet_path": str(packet_path), "packet_sha256": packet_sha256,
                                    "A": a, "B": b})
            entry["inputs"][order] = str(input_path)
        index["layers"].append(entry)
    write_json(out_dir / "index.json", index)
    return index


def load_index(work_dir: Path) -> dict:
    path = Path(work_dir).resolve() / INPUTS_DIR / "index.json"
    if not path.is_file():
        raise SystemExit(f"adjudicate: {path} is missing; run `adjudicate.py inputs` first")
    return load_json(path)


def pending_items(index: dict, layers=None) -> list:
    """[(name, order, input_path, packet_sha256)] for every disagreeing layer."""
    items = []
    for entry in index.get("layers") or []:
        if entry.get("agreement") != "disagree":
            continue
        name = entry["layer"]
        if layers and name not in layers and name.split("__", 1)[1] not in layers:
            continue
        for order in ORDERS:
            items.append((name, order, entry["inputs"][order], entry["packet_sha256"]))
    return items


# ---------------------------------------------------------------- judgment objects

def valid_judge(data):
    """The judge object reduced to its schema keys, or None."""
    if not isinstance(data, dict):
        return None
    why, refs = data.get("why"), data.get("evidence_refs")
    if (data.get("preferred") not in ("A", "B") or not isinstance(why, str) or len(why.strip()) < MIN_WHY
            or not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs)):
        return None
    return {"preferred": data["preferred"], "why": why, "evidence_refs": refs}


def valid_refuter(data):
    if not isinstance(data, dict):
        return None
    refs = data.get("evidence_refs")
    if (type(data.get("refuted")) is not bool or not isinstance(data.get("reason"), str)
            or not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs)):
        return None
    return {"refuted": data["refuted"], "reason": data["reason"], "evidence_refs": refs}


def judgment_record(family, name, order, input_path, packet_sha256, model, repo, judge, refuter,
                    failure=None, exit_codes=None) -> dict:
    return {"schema_version": JUDGMENT_SCHEMA_VERSION, "family": family, "layer": name, "order": order,
            "input_path": str(input_path), "packet_sha256": packet_sha256, "model": model,
            "repo": str(repo) if repo else None, "judge": judge, "refuter": refuter, "failure": failure,
            "exit_codes": exit_codes or {}}


def usable_judgment(data, family, order, packet_sha256):
    """None when the judgment file counts, else the reason it does not."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("family") != family or data.get("order") != order:
        return "family or order does not match its file name"
    if data.get("packet_sha256") != packet_sha256:
        return "judged a different packet"
    if valid_judge(data.get("judge")) is None:
        return data.get("failure") or "no valid judge object"
    if valid_refuter(data.get("refuter")) is None:
        return data.get("failure") or "no valid refuter object"
    return None


def split_prompt(text: str):
    if REFUTER_MARKER not in text:
        raise SystemExit(f"adjudicate: the prompt has no {REFUTER_MARKER} line separating judge and refuter")
    judge, refuter = text.split(REFUTER_MARKER, 1)
    return judge.strip() + "\n", refuter.strip() + "\n"


def fill(template: str, input_path, repo, judgment=None) -> str:
    text = template.replace("{INPUT_PATH}", str(input_path)).replace("{REPO_ROOT}", str(repo))
    return text.replace("{JUDGMENT}", json.dumps(judgment, sort_keys=True)) if judgment is not None else text


def refuse_git_repo(repo: Path):
    git_dirs = [str(path) for path in (repo, *repo.parents) if (path / ".git").exists()]
    if git_dirs:
        return (f"adjudicate: {git_dirs[0]} has .git, whose history a judge can read from {repo}; judge against a "
                "blind_checkout.py --export copy placed outside every repository")
    return None


# ---------------------------------------------------------------- codex

def run_codex_call(repo, schema, out_tmp, effort, prompt, model, timeout, events_path, validate):
    """Run one codex exec call, retried once. Returns (object or None, event model or None, exit codes, failure)."""
    cmd = codex_lane.build_command(repo, schema, out_tmp, effort, prompt, model, codex_lane.ISOLATION_ARGS)
    exit_codes, event_model, failure = [], None, "no attempt ran"
    events_path.write_text("", encoding="utf-8")
    for _attempt in (1, 2):
        out_tmp.unlink(missing_ok=True)
        result = codex_lane.run_attempt(cmd, timeout)
        exit_codes.append(result["exit_code"])
        with events_path.open("a", encoding="utf-8") as handle:
            for line in result["stdout"].splitlines():
                if line.strip():
                    handle.write(line + "\n")
        found_model, _usage = codex_lane.extract_events_summary(codex_lane.parse_events(result["stdout"]))
        event_model = found_model or event_model
        if result["timed_out"] or result["exit_code"] != 0:
            failure = "timed out" if result["timed_out"] else f"codex exec exited {result['exit_code']}"
            continue
        try:
            data = load_json(out_tmp)
        except (OSError, ValueError):
            failure = "codex exec wrote no parseable output"
            continue
        finally:
            out_tmp.unlink(missing_ok=True)
        checked = validate(data)
        if checked is None:
            failure = "the output did not satisfy the schema"
            continue
        return checked, event_model, exit_codes, None
    return None, event_model, exit_codes, f"failed after retry: {failure}"


def run_codex(args) -> int:
    work_dir = args.work_dir.resolve()
    repo = args.repo.resolve()
    refusal = refuse_git_repo(repo)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    judge_template, refute_template = split_prompt(args.prompt.read_text(encoding="utf-8"))
    layers = {item.strip() for item in args.layers.split(",") if item.strip()} if args.layers else None
    items = pending_items(load_index(work_dir), layers)
    out_dir = work_dir / JUDGMENTS_DIR / "codex"
    pending = []
    for name, order, input_path, packet_sha256 in items:
        out_path = out_dir / f"{name}.{order}.json"
        try:
            if usable_judgment(load_json(out_path), "openai", order, packet_sha256) is None:
                continue
        except (OSError, ValueError):
            pass
        pending.append((name, order, input_path, packet_sha256, out_path))
    if pending and shutil.which("codex") is None:
        print("adjudicate: the codex CLI is not on PATH", file=sys.stderr)
        return 2
    events_dir = out_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    schemas = {}
    for label, source in (("judge", JUDGE_SCHEMA), ("refute", REFUTE_SCHEMA)):
        schemas[label] = out_dir / f"adjudication-{label}.codex-strict.schema.json"
        schemas[label].write_text(json.dumps(codex_lane.strict_output_schema(load_json(source)), indent=1,
                                             sort_keys=True) + "\n", encoding="utf-8")
    failures, lock = [], threading.Lock()

    def process(item):
        name, order, input_path, packet_sha256, out_path = item
        stem = f"{name}.{order}"
        judge, judge_model, judge_codes, failure = run_codex_call(
            repo, schemas["judge"], out_dir / f"{stem}.judge.out.tmp", args.effort,
            fill(judge_template, input_path, repo), args.model, args.timeout,
            events_dir / f"{stem}.judge.jsonl", valid_judge)
        refuter, refute_model, refute_codes = None, None, []
        if judge is not None:
            refuter, refute_model, refute_codes, failure = run_codex_call(
                repo, schemas["refute"], out_dir / f"{stem}.refute.out.tmp", args.effort,
                fill(refute_template, input_path, repo, judge), args.model, args.timeout,
                events_dir / f"{stem}.refute.jsonl", valid_refuter)
            failure = f"refuter {failure}" if failure else None
        elif failure:
            failure = f"judge {failure}"
        model = judge_model or args.model or "unknown"
        write_json(out_path, judgment_record(
            "openai", name, order, input_path, packet_sha256, model, repo, judge, refuter, failure,
            {"judge": judge_codes, "refuter": refute_codes}))
        if refute_model and refute_model != judge_model:
            print(f"adjudicate: {stem} judge model {judge_model!r} and refuter model {refute_model!r} differ",
                  file=sys.stderr)
        if failure:
            with lock:
                failures.append((stem, failure))

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            list(executor.map(process, pending))
    else:
        for item in pending:
            process(item)

    roots = [str(repo), str((work_dir / INPUTS_DIR).resolve()), str((work_dir / "packets").resolve())]
    audit = {stem.name[:-len(".jsonl")]: codex_lane.blind_audit(stem, roots) for stem in sorted(events_dir.glob("*.jsonl"))}
    write_json(out_dir / "blind-audit.json", {"schema_version": 1, "allowed_roots": roots, "calls": audit})
    flagged = sorted(key for key, entry in audit.items()
                     if entry["web_search"] or entry["mcp_tool_calls"] or entry["flagged_commands"])
    if flagged:
        print(f"adjudicate: blind audit flags {len(flagged)} call(s) for review: {', '.join(flagged)}",
              file=sys.stderr)
    for stem, failure in sorted(failures):
        print(f"adjudicate: codex {stem}: {failure}", file=sys.stderr)
    return 1 if failures else 0


# ---------------------------------------------------------------- claude

def claude_args(work_dir: Path, repo: Path, prompt_path: Path = PROMPT_PATH, layers=None) -> dict:
    """The adjudication-lane.js args for every disagreeing layer."""
    items = pending_items(load_index(work_dir), layers)
    return {"repo": str(repo), "prompt": prompt_path.read_text(encoding="utf-8"),
            "items": [{"name": name, "order": order, "path": path, "packet_sha256": sha}
                      for name, order, path, sha in items]}


def collect_claude(work_dir: Path, result, model: str, repo=None) -> list:
    """Write the Claude family's judgment files from the workflow return; returns the missing (stem, reason)."""
    work_dir = Path(work_dir).resolve()
    if not (isinstance(model, str) and FAMILY_MODEL_PATTERNS["anthropic"].fullmatch(model)):
        raise ValueError(f"--model {model!r} does not match the anthropic pattern "
                         f"{FAMILY_MODEL_PATTERNS['anthropic'].pattern}")
    if isinstance(result, dict) and "items" not in result and isinstance(result.get("result"), dict):
        result = result["result"]
    returned = {}
    for item in (result.get("items") if isinstance(result, dict) else None) or []:
        if isinstance(item, dict) and item.get("order") in ORDERS and isinstance(item.get("name"), str):
            returned[(item["name"], item["order"])] = item
    repo = repo or (result.get("repo") if isinstance(result, dict) else None)
    missing = []
    for name, order, input_path, packet_sha256 in pending_items(load_index(work_dir)):
        item = returned.get((name, order)) or {}
        judge, refuter = valid_judge(item.get("judge")), valid_refuter(item.get("refuter"))
        if not item:
            failure = "lost: the workflow returned no item"
        elif judge is None:
            failure = "judge lost or invalid"
        elif refuter is None:
            failure = "refuter lost or invalid"
        else:
            failure = None
        if item and item.get("packet_sha256") not in (None, packet_sha256):
            failure, judge, refuter = "the workflow judged a different packet", None, None
        write_json(work_dir / JUDGMENTS_DIR / "claude" / f"{name}.{order}.json", judgment_record(
            "anthropic", name, order, input_path, packet_sha256, model, repo, judge, refuter, failure))
        if failure:
            missing.append((f"{name}.{order}", failure))
    return missing


# ---------------------------------------------------------------- assemble

def relative_ref(ref: str, repo) -> str:
    if repo and isinstance(ref, str) and ref.startswith(str(repo).rstrip("/") + "/"):
        return ref[len(str(repo).rstrip("/")) + 1:]
    return ref


def assemble_layer(work_dir: Path, entry: dict):
    """(record, notes) for one disagreeing layer; notes name every judgment that does not count."""
    name, packet_sha256 = entry["layer"], entry["packet_sha256"]
    judgments, whys, refs, notes = [], [], set(), []
    for lane, family in FAMILIES.items():
        for order in ORDERS:
            path = work_dir / JUDGMENTS_DIR / lane / f"{name}.{order}.json"
            try:
                data = load_json(path)
            except (OSError, ValueError):
                notes.append(f"{family} {order}: no judgment file")
                continue
            reason = usable_judgment(data, family, order, packet_sha256)
            if reason:
                notes.append(f"{family} {order}: {reason}")
                continue
            judge, refuter = data["judge"], data["refuter"]
            claude_position = CLAUDE_POSITION[order]
            preferred = judge["preferred"]
            judgments.append({
                "claude_position": claude_position, "preferred_position": preferred,
                "preferred_lane": "claude" if preferred == claude_position else "codex",
                "refuting_votes": 1 if refuter["refuted"] else 0,
                "judge": {"model": data.get("model"), "family": family},
                "stripped_packet_sha256": packet_sha256})
            whys.append(f"{family} {order}: {' '.join(judge['why'].split())}"
                        + (f" [refuted: {' '.join(refuter['reason'].split())}]" if refuter["refuted"] else ""))
            refs.update(relative_ref(ref, data.get("repo")) for ref in judge["evidence_refs"] + refuter["evidence_refs"])
    families = {judgment["judge"]["family"]: set() for judgment in judgments}
    for judgment in judgments:
        families[judgment["judge"]["family"]].add(judgment["claude_position"])
    missing = [family for family in sorted(set(FAMILIES.values())) if families.get(family) != {"A", "B"}]
    lanes = {judgment["preferred_lane"] for judgment in judgments}
    refuted = sum(judgment["refuting_votes"] for judgment in judgments)
    winner = next(iter(lanes)) if judgments and len(lanes) == 1 and not refuted and not missing else None
    if winner:
        head = f"winner {winner}: all {len(judgments)} judgments from both families in both orders agree, none refuted"
    elif missing:
        head = f"split: missing {', '.join(missing)} judgments in both presentation orders"
    elif refuted:
        head = f"split: {refuted} judgment(s) refuted"
    else:
        head = "split: the judgments chose different lanes"
    record = {"winner_lane": winner, "why": head + ". " + " | ".join(whys) if whys else head,
              "evidence_refs": sorted(refs), "judgments": judgments}
    if missing:
        record["missing_families"] = missing
    return record, notes


def assemble(work_dir: Path, out_dir: Path, layers=None):
    """Write every valid record; return (written names, issues)."""
    work_dir, out_dir = Path(work_dir).resolve(), Path(out_dir)
    written, issues = [], []
    for entry in load_index(work_dir).get("layers") or []:
        if entry.get("agreement") != "disagree":
            continue
        name = entry["layer"]
        if layers and name not in layers and name.split("__", 1)[1] not in layers:
            continue
        record, notes = assemble_layer(work_dir, entry)
        for note in notes:
            print(f"adjudicate: {name}: {note}", file=sys.stderr)
        issue, _result = judge_adjudication(record, grandfathered=False, packet_sha256=entry["packet_sha256"])
        if issue:
            issues.append((name, issue))
            continue
        write_json(out_dir / f"{name}.json", record)
        written.append(name)
    return written, issues


# ---------------------------------------------------------------- cli

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Two-family counterbalanced adjudication of disagreeing layers.")
    sub = parser.add_subparsers(dest="command", required=True)
    inputs = sub.add_parser("inputs", help="Write the AB/BA input files for every disagreeing layer.")
    inputs.add_argument("--work-dir", required=True, type=Path)
    inputs.add_argument("--layers", default=None)
    codex = sub.add_parser("codex", help="Run the Codex judge and refuter for every input file.")
    codex.add_argument("--work-dir", required=True, type=Path)
    codex.add_argument("--repo", required=True, type=Path)
    codex.add_argument("--model", default=None)
    codex.add_argument("--effort", default="high")
    codex.add_argument("--jobs", type=int, default=1)
    codex.add_argument("--layers", default=None)
    codex.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    codex.add_argument("--prompt", type=Path, default=PROMPT_PATH)
    cargs = sub.add_parser("claude-args", help="Print the adjudication-lane.js args JSON.")
    cargs.add_argument("--work-dir", required=True, type=Path)
    cargs.add_argument("--repo", required=True, type=Path)
    cargs.add_argument("--layers", default=None)
    collect = sub.add_parser("claude-collect", help="Write the Claude judgments from the workflow return.")
    collect.add_argument("--work-dir", required=True, type=Path)
    collect.add_argument("--result", required=True, type=Path)
    collect.add_argument("--model", required=True, help="The resolved child model, e.g. claude-opus-5-5.")
    collect.add_argument("--repo", default=None, type=Path, help="The repo the workflow judged (relativizes refs).")
    assemble_parser = sub.add_parser("assemble", help="Build and validate one adjudication record per layer.")
    assemble_parser.add_argument("--work-dir", required=True, type=Path)
    assemble_parser.add_argument("--out", required=True, type=Path)
    assemble_parser.add_argument("--layers", default=None)
    return parser.parse_args(argv)


def layer_set(text):
    return {item.strip() for item in text.split(",") if item.strip()} if text else None


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.command == "inputs":
        index = build_inputs(args.work_dir, layer_set(args.layers))
        for skipped in index["skipped"]:
            print(f"adjudicate: skipped {skipped['layer']}: {skipped['reason']}", file=sys.stderr)
        disagree = [entry["layer"] for entry in index["layers"] if entry["agreement"] == "disagree"]
        print(f"adjudicate: {len(disagree)} disagreeing layer(s), "
              f"{len(index['layers']) - len(disagree)} agreeing, {len(index['skipped'])} skipped")
        return 1 if index["skipped"] else 0
    if args.command == "codex":
        return run_codex(args)
    if args.command == "claude-args":
        print(json.dumps(claude_args(args.work_dir, args.repo.resolve(), layers=layer_set(args.layers)), indent=1))
        return 0
    if args.command == "claude-collect":
        try:
            missing = collect_claude(args.work_dir, load_json(args.result), args.model,
                                     str(args.repo.resolve()) if args.repo else None)
        except ValueError as error:
            print(f"adjudicate: {error}", file=sys.stderr)
            return 2
        for stem, reason in missing:
            print(f"adjudicate: claude {stem}: missing ({reason})", file=sys.stderr)
        return 1 if missing else 0
    written, issues = assemble(args.work_dir, args.out, layer_set(args.layers))
    for name, issue in issues:
        print(f"adjudicate: {name}: not written: {issue}", file=sys.stderr)
    print(f"adjudicate: wrote {len(written)} adjudication record(s) to {args.out}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
