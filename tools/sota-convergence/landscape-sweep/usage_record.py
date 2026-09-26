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
               raw_output_sha256 (of the unsanitized stdout), measured_at_utc, note
  child_usage  the tool's output with transcript_dir rewritten to <session-transcripts>/subagents/workflows/<run id>
The ledger needs child_usage.status "complete" for a completed sweep, reads workflow_run from the last segment of
transcript_dir, and requires lost_workers to equal the incomplete children. An attempt the runtime re-ran under the
same call key (after a usage-limit pause) is under child_usage.superseded_attempts, not a lost child; its usage
counts in by_resolved_model. Refuses to write (exit 3) when the
sanitized record still matches a scripts/validate.py PRIVATE_CONTENT pattern. Exit 1, with the record still written
(a stopped run keeps it as a lower bound), when the usage is incomplete, when child-usage.mjs exited non-zero, or
when a child ran at another effort than --require-effort (effort_mismatches): every worker of this lane runs at
effort max, and make_result.py refuses such a record. The summary it prints also names the children whose WebSearch
calls the session's cap refused (child_usage.web_search, measured by child-usage.mjs); convert.py --usage makes each a
web_search_capped retained failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def record(raw: bytes, exit_code: int, command: str, repo_root: Path, measured_at: str | None = None) -> dict:
    output = json.loads(raw)
    if not isinstance(output, dict) or "status" not in output:
        raise ValueError("child-usage output is not a run summary (no status)")
    output = dict(output)
    output["transcript_dir"] = sanitize_transcript_dir(output.get("transcript_dir") or "")
    return {"schema_version": 1,
            "measurement": {"tool": f"native-agent-stack {TOOL}", "tool_commit": tool_commit(repo_root),
                            "tool_sha256": sha256_bytes((repo_root / TOOL).read_bytes()), "command": command,
                            "exit_code": exit_code, "raw_output_sha256": sha256_bytes(raw),
                            "measured_at_utc": measured_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "note": NOTE},
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
        document = record(raw, code, command, repo)
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
    print(json.dumps({"out": str(args.out), "status": usage.get("status"), "exit_code": code,
                      "workflow_run": usage["transcript_dir"].rsplit("/", 1)[-1], "children": len(children),
                      "incomplete": [c.get("label") for c in children if isinstance(c, dict) and c.get("complete") is not True],
                      "superseded_attempts": [c.get("label") for c in usage.get("superseded_attempts") or []
                                              if isinstance(c, dict)],
                      "effort_mismatches": mismatches,
                      "web_search": usage.get("web_search")},
                     indent=1))
    return 0 if usage.get("status") == "complete" and code == 0 and not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
