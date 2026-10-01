#!/usr/bin/env python3
"""U3 before/after host differential of the Codex lane report (PR-A U3, research-u3.design.md section 10 step 4).

For each revision it extracts tools/skill-usage, examples/claude-native/workflows and adoption/skills with `git archive` into a
private scratch directory (no worktree is added), runs `skill_usage.py --lanes` over the Codex sessions root named by the
CODEX_SESSIONS environment variable with a fixed window (--since, --until, --now = --until), and reduces the report to
aggregate counts: every group field flattened, and per-actor histograms (attempt routes, usage completeness, M4 status, spawn
states). The reports stay private (mode 0600, under --work); only the summaries' deltas are printed. Nothing here reads or
prints an id, a path, a host name or command text: the report is ID-free by construction (tests/test_skill_usage.py privacy
tests) and the summary keeps only its keys, counts, states and model/effort keys.

Usage: CODEX_SESSIONS=<root> python3 -B run-differential.py --repo <checkout> --work <private dir> \
           --since 2026-01-01T00:00:00Z --until 2026-09-29T00:00:00Z [--rtk-check] LABEL=REV [LABEL=REV ...]
       python3 -B run-differential.py --compare <work>/summary/A.json <work>/summary/B.json
       python3 -B run-differential.py --totals <work>/summary/A.json [<work>/summary/B.json ...]

--totals prints, per summary, the sum over the three disjoint groups (workers, negative_controls, unclassified) of the
fields the U3 README quotes, and the distinct values of their status fields.
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

VOLATILE = {"generated_at", "sessions_ran_past_window_end"}  # the live store keeps appending after --until


def flatten(value, prefix="", out=None):
    out = {} if out is None else out
    if isinstance(value, dict):
        for key in sorted(value):
            flatten(value[key], f"{prefix}.{key}" if prefix else str(key), out)
    elif isinstance(value, list):
        out[prefix] = json.dumps(value, sort_keys=True)
    else:
        out[prefix] = value
    return out


def summarize(report: dict) -> dict:
    top = {key: value for key, value in report.items()
           if key not in ("actors", "limits", "window", "marker", "generated_at", "kind", "schema_version")}
    actors = report.get("actors", [])
    hist = collections.Counter()
    for actor in actors:
        measurement = actor.get("measurement", {})
        usage = measurement.get("provider_usage", {})
        hist[f"actor.kind={actor.get('kind')}"] += 1
        hist[f"actor.provider_usage.complete={usage.get('complete')}"] += 1
        hist[f"actor.m4.status={measurement.get('m4', {}).get('status')}"] += 1
        hist[f"actor.cli_lanes.status={measurement.get('cli_lanes', {}).get('status')}"] += 1
        for attempt in usage.get("attempts", []):
            hist[f"attempt.route={attempt.get('configured_model')}|{attempt.get('effort')}"] += 1
            hist[f"attempt.state={attempt.get('state')}"] += 1
            for key, count in (attempt.get("usage") or {}).items():
                hist[f"attempt.usage.{key}.null"] += count is None
            if "max_request_input_tokens" in attempt:
                hist[f"attempt.max_request_input_tokens.null={attempt['max_request_input_tokens'] is None}"] += 1
        for key, count in (usage.get("totals") or {}).items():
            hist[f"actor.provider_usage.totals.{key}.null"] += count is None
        spawn = actor.get("spawn")
        if isinstance(spawn, dict):
            for path, value in flatten(spawn).items():
                hist[f"spawn.{path}={value}"] += 1
    return {"top": flatten(top), "actors": dict(sorted(hist.items()))}


GROUPS = ("workers", "negative_controls", "unclassified")
TOTALS = ("sandbox_operations", "calls_without_result", "m3.results", "m5.results", "proxy.nested", "m4.remote_fetches",
          "m4.shell_fetch", "m4.ctx_sandbox_fetch", "m4.unclassifiable", "m4.fetch_mentions_unconfirmed",
          "by_carrier.code_mode.results", "by_carrier.other.results", "code_mode.exec_calls", "code_mode.wait_calls",
          "code_mode.nested_items", "code_mode.unattributed_items", "code_mode.legacy_unobservable_exec_calls",
          "code_mode.legacy_unobservable_sites", "code_mode.outer_http_mentions", "code_mode.outer_http_unverified_exec_calls",
          "rtk_parts.calls", "rtk_parts.eligible_parts", "rtk_parts.ineligible_parts", "rtk_parts.unknown_calls",
          "rtk_parts.observed_covered_parts", "rtk_parts.explicit_rtk_on_excluded_or_sensitive", "rtk_parts.d7.eligible_parts",
          "rtk_parts.d7.covered_parts", "rtk_parts.d7.log_find_unresolved_parts", "rtk_parts.d7.log_find_requires_raw_parts",
          "rtk_parts.d7.wrapped_exceptions")
STATUSES = ("m4.status", "rtk_parts.status", "rtk_parts.agent", "rtk_parts.d7.status")


def totals(summary: dict) -> dict:
    top = summary.get("top", {})
    out = {"sessions_in_window": top.get("sessions_in_window"), "files_scanned": top.get("files_scanned")}
    for field in TOTALS:
        values = [top.get(f"groups.{group}.measurement.{field}") for group in GROUPS]
        out[field] = sum(v for v in values if isinstance(v, int)) if any(isinstance(v, int) for v in values) else "(absent)"
    for field in STATUSES:
        out[field] = sorted({str(top.get(f"groups.{group}.measurement.{field}", "(absent)")) for group in GROUPS})
    return out


def compare(before: dict, after: dict) -> list:
    rows = []
    for section in ("top", "actors"):
        a, b = before.get(section, {}), after.get(section, {})
        for key in sorted(set(a) | set(b)):
            if key.split(".")[-1] in VOLATILE or key in VOLATILE:
                continue
            if a.get(key, "(absent)") != b.get(key, "(absent)"):
                rows.append((section, key, a.get(key, "(absent)"), b.get(key, "(absent)")))
    return rows


def run(repo: Path, work: Path, label: str, rev: str, since: str, until: str, root: str, rtk_check: bool = False) -> dict:
    src = work / "src" / label
    src.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", rev, "tools/skill-usage", "examples/claude-native/workflows",
                              "adoption/skills"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(src)], input=archive, check=True)
    out = work / "out" / f"{label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(out.parent, 0o700)
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-B", str(src / "tools/skill-usage/skill_usage.py"), "--lanes", "--codex-root", root,
                             "--since", since, "--until", until, "--now", until, "--json", "--out", str(out),
                             *(["--rtk-check"] if rtk_check else [])],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False)
    elapsed = round(time.monotonic() - started, 1)
    if result.returncode:
        raise SystemExit(f"{label}: skill_usage.py exited {result.returncode}")  # stderr withheld: it could name a path
    os.chmod(out, 0o600)
    summary = summarize(json.loads(out.read_text()))
    summary["run"] = {"label": label, "rev": rev, "since": since, "until": until, "rtk_check": rtk_check, "seconds": elapsed}
    target = work / "summary" / f"{label}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--compare", nargs=2, type=Path)
    parser.add_argument("--totals", nargs="+", type=Path)
    parser.add_argument("--rtk-check", action="store_true", help="pass --rtk-check (the rtk replay needs Linux and rtk 0.50.0)")
    parser.add_argument("runs", nargs="*")
    args = parser.parse_args()
    if args.compare:
        before, after = (json.loads(path.read_text()) for path in args.compare)
        rows = compare(before, after)
        for section, key, a, b in rows:
            print(f"{section}\t{key}\t{a}\t->\t{b}")
        print(f"DELTAS {len(rows)}")
        return 0
    if args.totals:
        for path in args.totals:
            summary = json.loads(path.read_text())
            print(json.dumps({"run": summary.get("run", {}).get("label", path.stem), **totals(summary)}, sort_keys=True))
        return 0
    root = os.environ.get("CODEX_SESSIONS")
    if not root:
        raise SystemExit("set CODEX_SESSIONS")
    for spec in args.runs:
        label, rev = spec.split("=", 1)
        summary = run(args.repo, args.work, label, rev, args.since, args.until, root, args.rtk_check)
        top = summary["top"]
        print(f"{label} rev={rev[:12]} seconds={summary['run']['seconds']} sessions={top.get('sessions_in_window')} "
              f"files={top.get('files_scanned')} parse_errors={top.get('parse_errors')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
