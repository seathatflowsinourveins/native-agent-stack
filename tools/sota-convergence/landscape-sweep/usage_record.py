#!/usr/bin/env python3
"""Measure a sweep run's per-child Claude usage and write the sanitized record the saturation ledger binds.

  usage_record.py --transcript-dir <session>/subagents/workflows/<run id> --out child-usage-<run id>.json
                  [--require-effort max] [--repo-root .]
  usage_record.py --raw-output child-usage-stdout.json --exit-code N --out ...   (wrap output captured earlier)

Runs this checkout's vendored examples/claude-native/workflows/child-usage.mjs (node) over the run's transcripts,
which Claude Code keeps under <config dir>/projects/<project>/<session id>/subagents/workflows/<run id>/, and
writes {schema_version, measurement, child_usage} in the shape of
evidence/artifacts/landscape-sweep-20260923-attempts/child-usage-*.json:
  measurement  tool, tool_commit (null when the tool differs from HEAD), tool_sha256, command, exit_code,
               raw_output_sha256 (of the unsanitized stdout), measured_at_utc, note, post_processing when applicable
  child_usage  the post-processed output with transcript_dir rewritten to <session-transcripts>/subagents/workflows/<run id>
The ledger needs child_usage.status "complete" for a completed sweep, reads workflow_run from the last segment of
transcript_dir, and requires lost_workers to equal the incomplete children. An attempt the runtime re-ran under the
same call key (after a usage-limit pause) is under child_usage.superseded_attempts, not a lost child. Before
sanitizing, this wrapper also links children whose issues include "no result entry in journal" to later complete
attempts with the same label, using the journal order that child-usage.mjs summarizeRun preserves in children.
Precondition: sweep.js issues one logical call per label per run; runtime retries may produce multiple attempts.
A label with more than one complete child is ambiguous and is never linked. The record carries neither call keys
nor timestamps, so linking observes only a missing result and a later complete same-label attempt. These attempts
keep their superseded_by and observed reason; their usage already counts in by_resolved_model and is never added again. With no
incomplete children or superseded usage_issues left, status becomes complete and reason counts the new links.
An effort mismatch of a superseded attempt is covered only by its same-label re-run completed at the required
effort. measurement.exit_code and raw_output_sha256 remain the tool's raw result; post_processing names the
links and covered mismatches, including source_status, source_reason, linked_agent_ids, covered_agent_ids and
covered_effort_mismatches. multi_model_children is recomputed over the remaining children after a move.
Refuses to write (exit 3) when the
sanitized record still matches a scripts/validate.py PRIVATE_CONTENT pattern. Exit 1, with the record still written
(a stopped run keeps it as a lower bound), when the post-processed usage is incomplete, when the raw tool exit
cannot be explained by these recoveries, or when an uncovered attempt ran at another effort than --require-effort.
The summary raw_exit_code is the tool's exit code and exit_code is the wrapper's. Every worker of this lane runs at effort max; convert.py retains
uncovered effort_deviations and make_result.py checks them. The summary also names the children whose WebSearch
calls the session's cap refused (child_usage.web_search, measured by child-usage.mjs); convert.py --usage makes each a
web_search_capped retained failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import REPO_ROOT, private_content, private_findings, sha256_bytes, write_json  # noqa: E402

TOOL = "examples/claude-native/workflows/child-usage.mjs"
MARKER = "/subagents/workflows/"
NOTE = ("Per-request provider usage of the Claude workflow children, from the retained native transcripts (message "
        "ids counted once). web_search counts each child's WebSearch calls and those the session's WebSearch cap "
        "refused (capped). The GPT-6 jobs are Codex usage, retained per job in the run's returns (raw and "
        "gpt6_usage); the two counters are never summed.")
SAME_LABEL_REASON = "no result entry; a later complete attempt with the same label returned; call keys not compared"


def superseded_at_required_effort(attempt: dict, output: dict, required: str = "max") -> bool:
    """Whether this attempt's superseded_by chain ends at a complete same-label re-run at `required` effort.

    Follow agent ids, never just a repeated label; an absent target, another label or a cycle covers nothing.
    child-usage.mjs can chain same-key re-runs through an intermediate attempt that also returned nothing.
    """
    if not isinstance(attempt, dict):
        return False
    label = attempt.get("label") or attempt.get("child") or attempt.get("agent_id")
    if not label:
        return False
    attempts = [*(output.get("children") or []), *(output.get("superseded_attempts") or [])]
    by_id = {c["agent_id"]: c for c in attempts if isinstance(c, dict) and c.get("agent_id")}
    seen = {attempt.get("agent_id")}
    target_id = attempt.get("superseded_by")
    while target_id and target_id not in seen:
        seen.add(target_id)
        target = by_id.get(target_id)
        if not target or (target.get("label") or target.get("agent_id")) != label:
            return False
        if target.get("complete") is True:
            return target.get("efforts") == [required]
        target_id = target.get("superseded_by")
    return False


def post_process(output: dict, required: str) -> dict:
    """Link no-result attempts in journal order, assuming one logical call per label per run.

    A label with multiple complete children is ambiguous. Call keys are not available in the native summary.
    """
    children = output.get("children") or []
    complete_counts = Counter(c.get("label") for c in children if isinstance(c, dict) and c.get("complete") is True)
    linked, retained = [], []
    for i, child in enumerate(children):
        if (not isinstance(child, dict) or child.get("complete") is True or not child.get("label")
                or "no result entry in journal" not in (child.get("issues") or [])
                or complete_counts[child["label"]] != 1):
            retained.append(child)
            continue
        later = next((c for c in children[i + 1:] if isinstance(c, dict) and c.get("complete") is True
                      and c.get("label") == child["label"] and c.get("agent_id")
                      and c["agent_id"] != child.get("agent_id")), None)
        if later:
            linked.append(dict(child, superseded_by=later["agent_id"], reason=SAME_LABEL_REASON))
        else:
            retained.append(child)
    source_status = output["status"]
    source_reason = output.get("reason")
    if linked:
        output["children"] = retained
        output["superseded_attempts"] = [*(output.get("superseded_attempts") or []), *linked]
        output["multi_model_children"] = [c.get("label") or c.get("agent_id") for c in retained
                                          if isinstance(c, dict) and len(c.get("resolved_models") or []) > 1]
        incomplete = sum(not isinstance(c, dict) or c.get("complete") is not True for c in retained)
        uncounted = sum(bool(c.get("usage_issues")) for c in output["superseded_attempts"] if isinstance(c, dict))
        output["status"] = "incomplete" if incomplete or uncounted else "complete"
        gaps = [f"{incomplete} child(ren) incomplete" if incomplete else None,
                f"{uncounted} superseded attempt(s) with usage_issues" if uncounted else None]
        output["reason"] = (f"{len(linked)} incomplete attempt(s) linked to later complete same-label attempts: "
                            f"{SAME_LABEL_REASON}; " + ("; ".join(g for g in gaps if g) or "every remaining child is complete"))
    # The raw tool's mismatches name labels, not agent ids. Bind each newly linked finding to its re-run before
    # filtering; other mismatches with that label (including an unsuperseded non-max attempt) remain uncovered.
    mismatches = [dict(item) if isinstance(item, dict) else item for item in output.get("effort_mismatches") or []]
    for child in linked:
        finding = next((item for item in mismatches if isinstance(item, dict) and not item.get("superseded_by")
                        and item.get("child") == (child.get("label") or child.get("agent_id"))
                        and item.get("efforts") == child.get("efforts")), None)
        if finding is not None:
            finding["superseded_by"] = child["superseded_by"]
    covered, uncovered = [], []
    for item in mismatches:
        (covered if superseded_at_required_effort(item, output, required) else uncovered).append(item)
    if "effort_mismatches" in output:
        output["effort_mismatches"] = uncovered
    attempts = [*(output.get("children") or []), *(output.get("superseded_attempts") or [])]
    covered_ids = [c["agent_id"] for c in attempts if isinstance(c, dict) and c.get("agent_id")
                   and c.get("efforts") != [required] and superseded_at_required_effort(c, output, required)]
    return {"name": "link_incomplete_children_to_later_complete_same_label", "linked_attempts": len(linked),
            "effort_mismatches_covered": len(covered), "source_status": source_status, "source_reason": source_reason,
            "linked_agent_ids": [c.get("agent_id") for c in linked], "covered_agent_ids": covered_ids,
            "covered_effort_mismatches": covered}


def sanitize_transcript_dir(path: str) -> str:
    text = str(path).rstrip("/")
    if MARKER in text:
        return "<session-transcripts>" + MARKER + text.split(MARKER, 1)[1]
    return "<session-transcripts>/" + text.rsplit("/", 1)[-1]


def tool_commit(repo_root: Path) -> str | None:
    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
        except OSError:
            return None
    head = git("rev-parse", "HEAD")
    changed = git("diff", "--quiet", "HEAD", "--", TOOL)
    if head is None or head.returncode != 0 or changed is None or changed.returncode != 0:
        return None
    return head.stdout.strip()


def record(raw: bytes, exit_code: int, command: str, repo_root: Path, measured_at: str | None = None,
           required_effort: str = "max") -> dict:
    output = json.loads(raw)
    if not isinstance(output, dict) or "status" not in output:
        raise ValueError("child-usage output is not a run summary (no status)")
    output = dict(output)
    processing = post_process(output, required_effort)
    output["transcript_dir"] = sanitize_transcript_dir(output.get("transcript_dir") or "")
    return {"schema_version": 1,
            "measurement": {"tool": f"native-agent-stack {TOOL}", "tool_commit": tool_commit(repo_root),
                            "tool_sha256": sha256_bytes((repo_root / TOOL).read_bytes()), "command": command,
                            "exit_code": exit_code, "raw_output_sha256": sha256_bytes(raw),
                            "measured_at_utc": measured_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "note": NOTE, "post_processing": processing},
            "child_usage": output}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--transcript-dir", help="the run's transcript directory (the Workflow tool prints it)")
    source.add_argument("--raw-output", type=Path, help="child-usage.mjs stdout captured earlier")
    parser.add_argument("--exit-code", type=int, help="with --raw-output: the tool's exit code")
    parser.add_argument("--require-effort", default="max", help="child-usage.mjs --require-effort (default max)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    try:
        if args.transcript_dir:
            done = subprocess.run(["node", str(repo / TOOL), args.transcript_dir, "--require-effort", args.require_effort],
                                  capture_output=True, check=False)
            if not done.stdout.strip():
                raise ValueError(f"child-usage.mjs printed nothing (exit {done.returncode}): "
                                 f"{done.stderr.decode('utf-8', 'replace').strip()[:300]}")
            raw, code, run_dir = done.stdout, done.returncode, args.transcript_dir
        else:
            if args.exit_code is None:
                raise ValueError("--raw-output needs --exit-code")
            raw, code = args.raw_output.read_bytes(), args.exit_code
            run_dir = json.loads(raw).get("transcript_dir") or ""
        command = f"node {TOOL} {sanitize_transcript_dir(run_dir)} --require-effort {args.require_effort}"
        document = record(raw, code, command, repo, required_effort=args.require_effort)
        findings = private_findings(document, private_content(repo))
    except (ValueError, OSError) as error:
        print(f"usage_record.py: {error}", file=sys.stderr)
        return 2
    if findings:
        print("refusing to write: possible private content (text not shown):", file=sys.stderr)
        for pointer, kind in findings:
            print(f"  {pointer}: {kind}", file=sys.stderr)
        return 3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, document)
    usage = document["child_usage"]
    children = usage.get("children") or []
    mismatches = usage.get("effort_mismatches") or []
    attempts = [*children, *(usage.get("superseded_attempts") or [])]
    off = any(isinstance(c, dict) and c.get("efforts") != [args.require_effort]
              and not superseded_at_required_effort(c, usage, args.require_effort) for c in attempts)
    processing = document["measurement"]["post_processing"]
    recovered = processing["linked_attempts"] or processing["effort_mismatches_covered"]
    wrapper_code = 0 if (usage.get("status") == "complete" and not mismatches and not off
                         and (code == 0 or code == 1 and recovered)) else 1
    print(json.dumps({"out": str(args.out), "status": usage.get("status"), "raw_exit_code": code, "exit_code": wrapper_code,
                      "workflow_run": usage["transcript_dir"].rsplit("/", 1)[-1], "children": len(children),
                      "incomplete": [c.get("label") for c in children if isinstance(c, dict) and c.get("complete") is not True],
                      "superseded_attempts": [c.get("label") for c in usage.get("superseded_attempts") or []
                                              if isinstance(c, dict)],
                      # A superseded attempt whose usage by_resolved_model cannot count makes the status incomplete.
                      "superseded_usage_issues": {c.get("label") or c.get("agent_id"): c["usage_issues"]
                                                  for c in usage.get("superseded_attempts") or []
                                                  if isinstance(c, dict) and c.get("usage_issues")},
                      "effort_mismatches": mismatches,
                      "web_search": usage.get("web_search")},
                     indent=1))
    return wrapper_code


if __name__ == "__main__":
    raise SystemExit(main())
