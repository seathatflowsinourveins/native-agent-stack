#!/usr/bin/env python3
"""Report skill pin/HEAD drift without invoking the mutating `skills check`.

References: vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73
src/cli.ts:398-401 aliases check to update; src/update.ts:549-574,849-868
resolves the recorded ref, not HEAD. Source-tree comparison follows
src/skill-lock.ts:168-171. Workflow/artifact pattern: catalog-freshness.yml.
This checks manifest source identity, not an installed worker or its lock.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "blueprints/runtime-workers/skills/manifest.json"
CLI_REF = "7407f3893ad4dceab546ac002c3ef806e4000c73"
CHECK_SOURCE = f"https://github.com/vercel-labs/skills/blob/{CLI_REF}/src/cli.ts#L398"


def gh_json(endpoint: str) -> dict:
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True,
                            timeout=60, check=False, stdin=subprocess.DEVNULL)
    if result.returncode:
        # Native stderr may include local auth/setup details; keep the public report value-free.
        raise ValueError(f"gh api failed (exit {result.returncode}): {endpoint}")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {endpoint}")
    return data


def fetch_source(source: str, refs: list[str], api=gh_json) -> dict:
    """One bounded source task; resolve HEAD once, then use its immutable SHA."""
    result: dict = {"source": source, "head": None, "trees": {}, "errors": []}
    try:
        result["head"] = api(f"repos/{source}/commits/HEAD")["sha"]
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        result["errors"].append(str(error))
    for ref in sorted(set(refs + ([result["head"]] if result["head"] else []))):
        try:
            tree = api(f"repos/{source}/git/trees/{ref}?recursive=1")
            if tree.get("truncated") or not isinstance(tree.get("tree"), list):
                raise ValueError(f"incomplete recursive tree: {source}@{ref}")
            result["trees"][ref] = {x["path"]: x["sha"] for x in tree["tree"] if x.get("type") == "tree"}
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            result["errors"].append(str(error))
    return result


def compare_skill(skill: dict, upstream: dict) -> dict:
    head = upstream["head"]
    trees = upstream["trees"]
    pin_tree = trees.get(skill["ref"], {}).get(skill["path"])
    head_tree = trees.get(head, {}).get(skill["path"])
    complete = head is not None and skill["ref"] in trees and head in trees
    valid_pin = pin_tree == skill["tree_sha"] if skill["ref"] in trees else None
    state = "unfetched" if not complete else "invalid-pin" if not valid_pin else (
        "removed-at-head" if head_tree is None else "skill-drift" if head_tree != pin_tree else (
            "repository-drift" if head != skill["ref"] else "current"))
    return {"name": skill["name"], "source": skill["source"], "path": skill["path"],
            "status": skill["status"], "pinned_ref": skill["ref"], "head_ref": head,
            "pinned_tree": pin_tree, "head_tree": head_tree,
            "manifest_tree_matches_pin": valid_pin, "state": state,
            "native_check_ref": skill["ref"], "native_check_advances_commit_pin": False}


def build_report(manifest: dict, api=gh_json, workers: int = 4) -> dict:
    by_source: dict[str, set[str]] = {}
    for skill in manifest["skills"]:
        by_source.setdefault(skill["source"], set()).add(skill["ref"])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fetched = list(pool.map(lambda item: fetch_source(item[0], sorted(item[1]), api), sorted(by_source.items())))
    sources = {s["source"]: s for s in fetched}
    entries = [compare_skill(s, sources[s["source"]]) for s in manifest["skills"]]
    errors = [error for source in fetched for error in source["errors"]]
    cli = {"pinned": manifest["cli"]["version"], "latest": None, "drift": None}
    try:
        release = api("repos/vercel-labs/skills/releases/latest")
        cli.update(latest=release["tag_name"], drift=release["tag_name"].removeprefix("v") != cli["pinned"])
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        errors.append(str(error))
    return {
        "schema_version": 1, "kind": "runtime_skill_freshness_report",
        "checked_at": datetime.now(timezone.utc).isoformat(), "report_only": True,
        "cli": cli,
        "native_check": {"executed": False, "source": CHECK_SOURCE,
                         "semantics_verified_version": "1.7.0",
                         "version_matches_semantics": manifest["cli"]["version"] == "1.7.0",
                         "reason": "check aliases update and can reinstall/remove. Commit refs remain pinned; HEAD comparison is separate. No worker lock or installation was read or changed."},
        "skills": entries, "errors": errors,
        "ok": not errors and all(e["manifest_tree_matches_pin"] is True for e in entries)
              and manifest["cli"]["version"] == "1.7.0",
    }


def render_markdown(report: dict) -> str:
    lines = ["# Runtime-worker skills freshness (report only)", "",
             f"Checked: {report['checked_at']}", "",
             f"CLI pin: {report['cli']['pinned']}; latest release: {report['cli']['latest'] or 'unfetched'}.", "",
             f"[`skills check`]({CHECK_SOURCE}) aliases update at 1.7.0 and was not executed. "
             "It follows recorded refs; these commit pins do not advance to HEAD. "
             "This report checks source trees, not installed files or native worker invocation.", "",
             "| Skill | Source | Pin | HEAD | Result |", "| --- | --- | --- | --- | --- |"]
    for entry in report["skills"]:
        lines.append(f"| {entry['name']} | {entry['source']} | {entry['pinned_ref'][:12]} | "
                     f"{(entry['head_ref'] or 'unfetched')[:12]} | {entry['state']} |")
    if report["errors"]:
        lines += ["", "Incomplete fetches remain unknown:", ""] + [f"- {e}" for e in report["errors"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 7), default=4)
    args = parser.parse_args(argv)
    report = build_report(json.loads(args.manifest.read_text()), workers=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report))
    print(json.dumps({"ok": report["ok"], "skills": len(report["skills"]),
                      "drift": sum(e["state"] in {"skill-drift", "repository-drift", "removed-at-head"} for e in report["skills"]),
                      "errors": len(report["errors"]), "report_only": True}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
