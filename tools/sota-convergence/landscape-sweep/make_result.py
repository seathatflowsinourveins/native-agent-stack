#!/usr/bin/env python3
"""Assemble the RESULT.json that `saturation_ledger.py --append` takes, for a completed landscape sweep.

  make_result.py --layers OUT/layers.json --reviews OUT/reviews.json --sweep-id landscape-sweep-YYYYMMDD
                 --returns-ref evidence/artifacts/<lane>/returns.json
                 --usage-ref evidence/artifacts/<lane>-attempts/child-usage-<run>.json
                 --manifest-ref catalogs/sota-convergence/manifest-YYYYMMDD.json
                 (--prompts-sha256 HEX | --work-dir W) [--lane NAME] [--reopen reopen.json] [--note TEXT ...]
                 [--repo-root .] > RESULT.json

Reads convert.py's layers.json and replaces each @RETURNS@ with --returns-ref; gives every survivor the
source_review path source_reviews.py wrote for it (--reviews is that script's stdout, and a review's path is taken
relative to the returns file's directory); reads workflow_run from the usage record's child_usage.transcript_dir
(its last segment, as the ledger binds it), lost_workers from that record's incomplete children, and date from the
manifest's checked_at. prompts_sha256 comes from --prompts-sha256 or <work-dir>/prompts_sha256.txt. --reopen is an
optional {"<layer_id>": [{"trigger": ..., "ref": ...}]} of reopen entries (recipes/saturation-sweep.md section 4),
added to the retained_failure entries convert.py wrote, never replacing them.
Computed fields (prev_sha256, the hashes, known, new) are left to --append. A stopped run is recorded by hand
(recipe section 4). This tool refuses: usage that is not complete, a usage measurement whose child-usage.mjs exit
code is not 0 (1 is accepted only for effort mismatches that the returns cover), a child or superseded attempt that
did not run at effort max only unless the returns list it as an effort_deviation retained failure (convert.py
--usage), a child or superseded attempt without a measured web_search (child-usage.mjs before the WebSearch count), a
worker with a capped WebSearch call that the returns do not list as a web_search_capped retained failure, and a layer
whose retained failures (returns.json failures/<layer>) lack their retained_failure reopen entry. Both retained
failures are checked per worker and per layer, as convert.py records them: a <role>:<layer>[:followup] worker's in
that layer's round, the completeness critic's in every layer of the record, so one layer's failure never covers
another layer. Paths are repository-relative and must exist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import REPO_ROOT, canon, deviation_rounds, load_json, pointer_token  # noqa: E402

PLACEHOLDER = "@RETURNS@"
HEX64 = re.compile(r"[0-9a-f]{64}")
REQUIRED_EFFORT = "max"  # every agent() call of sweep.js names effort 'max'


def substitute(value, returns_ref: str):
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, returns_ref)
    if isinstance(value, list):
        return [substitute(item, returns_ref) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, returns_ref) for key, item in value.items()}
    return value


def review_key(repository: str) -> str:
    """A survivor's and a review's repository compared as the ledger compares them (saturation_ledger.norm_repo:
    no trailing slash, lowercased), after canon() for GitHub URLs; a Hugging Face model URL keeps its host."""
    return canon(repository).strip().rstrip("/").lower()


def worker_item(child) -> dict:
    """A per-worker finding as convert.py records it in a retained failure: the child label (or agent id) and, for
    an attempt the runtime re-ran, superseded_by."""
    if not isinstance(child, dict):
        return {"child": child}
    item = {"child": child.get("label") or child.get("child") or child.get("agent_id")}
    if child.get("superseded_by"):
        item["superseded_by"] = child["superseded_by"]
    return item


def missing_failures(items: list, cause: str, returns: dict | None, layer_ids) -> list[str]:
    """'<worker> in <layer>' for every layer a worker belongs to (sweep_common.deviation_rounds: its own layer's round,
    or every layer of the record for the completeness critic) whose failures in the returns lack that worker's
    retained failure of `cause`; a worker naming no layer of the record is listed too. One layer's failure never
    covers another layer (GPT-6 review of the 2026-09-26 record: a global check let a layer lose its critic failure
    and its reopen entry and count as clean)."""
    failures = (returns or {}).get("failures") or {}
    recorded = {(layer_id, failure.get("round"), failure.get("child"), failure.get("superseded_by"))
                for layer_id, entries in failures.items() for failure in (entries if isinstance(entries, list) else [])
                if isinstance(failure, dict) and failure.get("cause") == cause}
    by_layer, unmapped = deviation_rounds(items, list(layer_ids))
    missing = [f"{item['child']} in {layer_id}" for layer_id, entries in by_layer.items() for rnd, item in entries
               if (layer_id, rnd, item["child"], item.get("superseded_by")) not in recorded]
    return missing + [f"{item['child']} (names no layer of this record)" for item in unmapped]


def check_usage(usage: dict, usage_ref: str, returns: dict | None = None, layer_ids=()) -> dict:
    """The usage record's child_usage, when it shows a complete run measured at effort max throughout, or whose
    every worker measured at another effort is an effort_deviation retained failure in the returns (convert.py
    --usage records one per worker and layer, and the layer is reopened). layer_ids are the record's layers."""
    child_usage = usage.get("child_usage") or {}
    if child_usage.get("status") != "complete":
        raise ValueError(f"{usage_ref}: child_usage.status is {child_usage.get('status')!r}; a completed sweep needs "
                         "complete usage (record a stopped run by hand, recipe section 4)")
    attempts = [*(child_usage.get("children") or []), *(child_usage.get("superseded_attempts") or [])]
    off = [worker_item(child) for child in attempts
           if isinstance(child, dict) and child.get("efforts") != [REQUIRED_EFFORT]]
    listed = [worker_item(item) for item in child_usage.get("effort_mismatches") or []]
    exit_code = (usage.get("measurement") or {}).get("exit_code")
    # child-usage.mjs exits 1 for incomplete usage or an effort mismatch; with complete usage only a mismatch is left.
    if exit_code != 0 and not (exit_code == 1 and (off or listed)):
        raise ValueError(f"{usage_ref}: measurement.exit_code is {exit_code!r}; child-usage.mjs reported incomplete "
                         "usage or an effort mismatch")
    uncovered = missing_failures(listed, "effort_deviation", returns, layer_ids)
    if uncovered:
        raise ValueError(f"{usage_ref}: effort_mismatches have no effort_deviation retained failure in the returns "
                         f"(convert.py --usage records one per worker and layer): {uncovered}")
    uncovered = missing_failures(off, "effort_deviation", returns, layer_ids)
    if uncovered:
        raise ValueError(f"{usage_ref}: children that did not run at effort {REQUIRED_EFFORT} only have no "
                         f"effort_deviation retained failure in their layers: {uncovered}")
    # The session's WebSearch cap: a worker it refused went on without searching, so its layer must be reopened.
    unmeasured = [child.get("label") or child.get("agent_id") for child in attempts if isinstance(child, dict)
                  and not (isinstance((child.get("web_search") or {}).get("calls"), int)
                           and isinstance((child.get("web_search") or {}).get("capped"), int))]
    if unmeasured:
        raise ValueError(f"{usage_ref}: children without a measured web_search (re-measure with this checkout's "
                         f"child-usage.mjs): {unmeasured[:5]}{' ...' if len(unmeasured) > 5 else ''}")
    capped = [worker_item(child) for child in attempts if isinstance(child, dict) and child["web_search"]["capped"] > 0]
    uncapped = missing_failures(capped, "web_search_capped", returns, layer_ids)
    if uncapped:
        raise ValueError(f"{usage_ref}: workers with capped WebSearch calls have no web_search_capped retained "
                         f"failure in the returns (convert.py --usage records one per worker and layer): {uncapped}")
    return child_usage


def build_result(*, layers: list, reviews: list, usage: dict, manifest: dict, sweep_id: str, lane: str,
                 returns_ref: str, usage_ref: str, manifest_ref: str, prompts_sha256: str, reopen=None,
                 notes=(), returns: dict | None = None) -> dict:
    child_usage = check_usage(usage, usage_ref, returns, [layer.get("layer_id") for layer in layers])
    transcript_dir = str(child_usage.get("transcript_dir") or "")
    run = transcript_dir.rstrip("/").rsplit("/", 1)[-1]
    if not run.startswith("wf_"):
        raise ValueError(f"{usage_ref}: transcript_dir {transcript_dir!r} does not end in a workflow run id")
    if not HEX64.fullmatch(prompts_sha256 or ""):
        raise ValueError("prompts_sha256 must be 64 lowercase hex characters")
    base = returns_ref.rsplit("/", 1)[0]
    by_repo = {}
    for review in reviews:
        by_repo.setdefault(review_key(review["repository"]), []).append(review)
    reopen = substitute(reopen or {}, returns_ref)
    unknown = sorted(set(reopen) - {layer.get("layer_id") for layer in layers})
    if unknown:
        raise ValueError(f"--reopen names layers this sweep did not cover: {unknown}")
    failures = (returns or {}).get("failures") or {}
    out_layers, missing, unreopened = [], [], []
    for layer in substitute(layers, returns_ref):
        for entry in layer.get("survived") or []:
            matches = [r for r in by_repo.get(review_key(entry["repo"]), []) if layer["layer_id"] in r.get("layers", [])]
            if not matches:
                missing.append(f"{layer['layer_id']}: {entry['repo']}")
                continue
            entry["source_review"] = f"{base}/{matches[0]['path']}"
        entries = list(layer.get("reopen") or [])
        entries += [item for item in reopen.get(layer["layer_id"], []) if item not in entries]
        layer["reopen"] = entries
        failure_ref = f"{returns_ref}#/failures/{pointer_token(layer['layer_id'])}"
        if failures.get(layer["layer_id"]) and not any(
                isinstance(item, dict) and item.get("trigger") == "retained_failure" and item.get("ref") == failure_ref
                for item in entries):
            unreopened.append(layer["layer_id"])
        out_layers.append(layer)
    if missing:
        raise ValueError(f"survivors without a source review in --reviews: {missing}")
    if unreopened:
        raise ValueError(f"layers with retained failures but no retained_failure reopen entry (a failed lane never "
                         f"counts as clean; use convert.py's layers.json): {unreopened}")
    lost = [child.get("label") for child in child_usage.get("children") or []
            if isinstance(child, dict) and child.get("complete") is not True]
    result = {"sweep_id": sweep_id, "date": manifest.get("checked_at"), "workflow_run": run, "status": "completed",
              "manifest_ref": manifest_ref, "lane": lane, "prompts_sha256": prompts_sha256, "usage_ref": usage_ref,
              "lower_bound_usage": False, "returns_ref": returns_ref}
    if lost:
        result["lost_workers"] = lost
    if notes:
        result["notes"] = list(notes)
    result["layers"] = out_layers
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layers", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True, help="source_reviews.py stdout ([] when nothing survived)")
    parser.add_argument("--sweep-id", required=True)
    parser.add_argument("--lane", help="default: --sweep-id")
    parser.add_argument("--returns-ref", required=True)
    parser.add_argument("--usage-ref", required=True)
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--prompts-sha256")
    parser.add_argument("--work-dir", default=os.environ.get("SWEEP_WORK_DIR"))
    parser.add_argument("--reopen", type=Path)
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    try:
        for ref in (args.returns_ref, args.usage_ref, args.manifest_ref):
            if ref.startswith("/") or ".." in Path(ref).parts or not (repo / ref).is_file():
                raise ValueError(f"{ref} must be an existing repository-relative path")
        digest = args.prompts_sha256
        if digest is None:
            if not args.work_dir:
                raise ValueError("pass --prompts-sha256 or --work-dir (for prompts_sha256.txt)")
            digest = (Path(args.work_dir) / "prompts_sha256.txt").read_text(encoding="utf-8").strip()
        result = build_result(layers=load_json(args.layers), reviews=load_json(args.reviews),
                              usage=load_json(repo / args.usage_ref), manifest=load_json(repo / args.manifest_ref),
                              sweep_id=args.sweep_id, lane=args.lane or args.sweep_id, returns_ref=args.returns_ref,
                              usage_ref=args.usage_ref, manifest_ref=args.manifest_ref, prompts_sha256=digest,
                              reopen=load_json(args.reopen) if args.reopen else None, notes=args.note,
                              returns=load_json(repo / args.returns_ref))
    except (ValueError, OSError, KeyError) as error:
        print(f"make_result.py: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
