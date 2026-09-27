#!/usr/bin/env python3
"""Run one Codex capability gate through promptfoo 0.123.1 and reconcile it with native Codex OTel in Loki.

promptfoo's openai:codex-sdk provider drives `codex exec --profile stack-worker` (through codex-profile-exec) and scores
each row with its own assertions: trajectory spans plus the tool-result checks in assertions.js. This wrapper adds only
what promptfoo does not do:
- it creates the two M13 worktrees at HEAD and removes them afterwards;
- it keeps promptfoo's database and results in a private temporary directory, with telemetry and sharing off;
- it reads the verdicts from promptfoo's results file: every gate row must pass, and every control row must fail by
  assertion rather than by a provider error;
- it counts, per row, the MCP calls in the provider's raw items and the `codex.tool_result` records that Codex's own
  OTel exporter sent to Loki for the same conversation. The two counts must be equal for every row.

It prints counts and verdicts only, never model text, tool results or conversation ids; its first line fits in the
400-character excerpt that `scripts/host_receipts.py record` keeps. Exit 0 means the gate passed.

Loki: http://127.0.0.1:13100 (observability/backends/README.md), override with CAPABILITY_GATE_LOKI. Runs through the
SDK arrive as service_name "codex_sdk_ts": the bundled @openai/codex-sdk 0.153.4 sets
CODEX_INTERNAL_ORIGINATOR_OVERRIDE=codex_sdk_ts unless the environment already carries it. conversation_id is the
thread id, and MCP records are keyed on tool_namespace "mcp__<server>" (observability/collector/README.md).

Usage: run_gate.py {jcodemunch,ai-memory,m13} [--keep]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTFOO_VERSION = "0.123.1"
GATES = {
    "jcodemunch": {"config": "jcodemunch.yaml", "servers": ("jcodemunch",), "worktrees": False, "concurrency": 1},
    "ai-memory": {"config": "ai-memory.yaml", "servers": ("ai-memory",), "worktrees": False, "concurrency": 1},
    "m13": {"config": "m13.yaml", "servers": ("context-mode", "serena"), "worktrees": True, "concurrency": 2},
}
SERVICE = "codex_sdk_ts"
LOKI = os.environ.get("CAPABILITY_GATE_LOKI", "http://127.0.0.1:13100")
ASSERTION_FAILED = 1  # promptfoo ResultFailureReason.ASSERT; 2 is ERROR (a provider or runtime error)


def namespace(server: str) -> str:
    return "mcp__" + server.replace("-", "_")


def arm_of(label: str, gate: str) -> str:
    return label.rsplit("-", 1)[0] if gate == "m13" else label


def parse_rows(results: dict, gate: str) -> list[dict]:
    """One dict per promptfoo row: arm, pass/fail, failure reason, conversation id, MCP call counts, M13 class verdicts."""
    servers = GATES[gate]["servers"]
    rows = []
    for row in results["results"]["results"]:
        response = row.get("response") or {}
        try:
            raw = response.get("raw")
            items = json.loads(raw if isinstance(raw, str) else json.dumps(raw or {})).get("items") or []
        except (TypeError, ValueError):
            items = []
        calls = Counter(item.get("server") for item in items
                        if item.get("type") == "mcp_tool_call" and item.get("server") in servers)
        classes = {}
        for component in (row.get("gradingResult") or {}).get("componentResults") or []:
            cls = ((component.get("assertion") or {}).get("config") or {}).get("cls")
            if cls:
                classes[cls] = component.get("reason")
        rows.append({
            "arm": arm_of((row.get("provider") or {}).get("label") or "", gate),
            "success": bool(row.get("success")),
            "failure_reason": row.get("failureReason"),
            "session": response.get("sessionId") or (row.get("metadata") or {}).get("sessionId"),
            "calls": calls,
            "classes": classes,
        })
    return rows


def verdict(rows: list[dict]) -> dict:
    """Per arm: rows, passed, failed by assertion, errored. The gate arm must pass every row and each control arm must
    fail every row by assertion; a provider error fails the gate either way."""
    arms: dict[str, Counter] = {}
    for row in rows:
        tally = arms.setdefault(row["arm"], Counter())
        tally["rows"] += 1
        if row["success"]:
            tally["passed"] += 1
        elif row["failure_reason"] == ASSERTION_FAILED:
            tally["failed"] += 1
        else:
            tally["errored"] += 1
    gate_ok = "gate" in arms and arms["gate"]["passed"] == arms["gate"]["rows"] > 0
    controls = {arm: tally for arm, tally in arms.items() if arm.startswith("ctrl-")}
    controls_ok = bool(controls) and all(t["failed"] == t["rows"] > 0 for t in controls.values())
    return {"arms": arms, "gate_ok": gate_ok, "controls_ok": controls_ok}


def class_tallies(rows: list[dict]) -> dict[str, dict[str, Counter]]:
    tallies: dict[str, dict[str, Counter]] = {}
    for row in rows:
        for cls, reason in row["classes"].items():
            tallies.setdefault(row["arm"], {}).setdefault(cls, Counter())[reason] += 1
    return tallies


def loki_records(start_ns: int, end_ns: int) -> list[dict]:
    """Every record of the SDK's service in the window, stream labels merged with structured metadata."""
    out, start = [], start_ns
    while True:
        params = {"query": f'{{service_name="{SERVICE}"}}', "start": str(start), "end": str(end_ns),
                  "limit": "5000", "direction": "forward"}
        with urllib.request.urlopen(f"{LOKI}/loki/api/v1/query_range?" + urllib.parse.urlencode(params),
                                    timeout=60) as response:
            data = json.loads(response.read())
        batch = []
        for stream in data["data"]["result"]:
            labels = stream.get("stream") or {}
            for value in stream["values"]:
                meta = (value[2] if len(value) > 2 else {}).get("structuredMetadata") or {}
                batch.append((int(value[0]), {**labels, **meta}))
        out.extend(record for _, record in batch)
        if len(batch) < 5000:
            return out
        start = max(ts for ts, _ in batch) + 1


def loki_counts(records: list[dict], sessions: set, servers: tuple) -> dict[str, Counter]:
    by_namespace = {namespace(server): server for server in servers}
    counts: dict[str, Counter] = {}
    for record in records:
        if record.get("event_name") != "codex.tool_result" or record.get("conversation_id") not in sessions:
            continue
        server = by_namespace.get(record.get("tool_namespace"))
        if server:
            counts.setdefault(record["conversation_id"], Counter())[server] += 1
    return counts


def reconcile(rows: list[dict], counts: dict[str, Counter]) -> tuple[int, int, int]:
    """(rows whose Loki counts equal their item counts, rows, MCP tool results seen in Loki). A row without a
    conversation id cannot be matched and counts as a mismatch."""
    matched = sum(1 for row in rows if row["session"] and counts.get(row["session"], Counter()) == row["calls"])
    return matched, len(rows), sum(sum(c.values()) for c in counts.values())


def summary(gate: str, result: dict, recon: tuple[int, int, int], versions: str) -> tuple[str, bool]:
    """The first output line and the gate verdict: gate rows all pass, every control row fails by assertion, and
    every row reconciles with Loki."""
    arms = result["arms"]
    parts = []
    for arm in sorted(arms, key=lambda a: (a != "gate", a)):
        t = arms[arm]
        what = "pass" if arm == "gate" else "fail by assertion"
        n = t["passed"] if arm == "gate" else t["failed"]
        parts.append(f"{arm} {n}/{t['rows']} {what}" + (f", {t['errored']} errored" if t["errored"] else ""))
    ok = result["gate_ok"] and result["controls_ok"] and recon[1] > 0 and recon[0] == recon[1]
    return (f"capability-gate {gate}: {'PASS' if ok else 'FAIL'} | " + "; ".join(parts) +
            f" | loki {recon[0]}/{recon[1]} rows match ({recon[2]} MCP tool results) | {versions}"), ok


def run(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gate", choices=sorted(GATES))
    parser.add_argument("--keep", action="store_true", help="keep the private directory (results, log, worktrees)")
    args = parser.parse_args()
    spec = GATES[args.gate]

    repo = Path(run(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"]))
    porcelain = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"]).splitlines()
    main_checkout = next(line.split(" ", 1)[1] for line in porcelain if line.startswith("worktree "))
    promptfoo = os.environ.get("CAPABILITY_GATE_PROMPTFOO") or shutil.which("promptfoo")
    if not promptfoo:
        print("capability-gate: FAIL | promptfoo is not on PATH (set CAPABILITY_GATE_PROMPTFOO)")
        return 2
    found = run([promptfoo, "--version"], env={**os.environ, "PROMPTFOO_DISABLE_TELEMETRY": "1"}).splitlines()[-1]
    if found.strip() != PROMPTFOO_VERSION:
        print(f"capability-gate: FAIL | promptfoo {found.strip()} found, {PROMPTFOO_VERSION} required")
        return 2
    codex = run([str(HERE / "codex-profile-exec"), "--version"]).splitlines()[-1].strip()

    private = Path(tempfile.mkdtemp(prefix="capability-gate-"))
    worktrees: list[Path] = []
    env = {**os.environ,
           "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1",
           "PROMPTFOO_CONFIG_DIR": str(private / "promptfoo"),
           "CAPABILITY_GATE_LAUNCHER": str(HERE / "codex-profile-exec"),
           "CAPABILITY_GATE_MAIN_CHECKOUT": main_checkout}
    try:
        if spec["worktrees"]:
            for tree in ("a", "b"):
                path = private / f"wt-{tree}"
                run(["git", "-C", str(repo), "worktree", "add", "--detach", str(path), "HEAD"])
                worktrees.append(path)
                env[f"CAPABILITY_GATE_WT_{tree.upper()}"] = str(path)
        started = time.time_ns()
        results_path = private / "results.json"
        with open(private / "promptfoo.log", "w") as log:
            subprocess.run([promptfoo, "eval", "-c", str(HERE / spec["config"]), "--no-cache", "--no-share",
                            "--max-concurrency", str(spec["concurrency"]), "-o", str(results_path)],
                           cwd=HERE, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                           check=False)
        if not results_path.exists():
            print(f"capability-gate {args.gate}: FAIL | promptfoo wrote no results (log kept in the private directory)")
            args.keep = True
            return 1
        rows = parse_rows(json.loads(results_path.read_text()), args.gate)
        result = verdict(rows)
        sessions = {row["session"] for row in rows if row["session"]}
        expected = sum(sum(row["calls"].values()) for row in rows)
        counts: dict[str, Counter] = {}
        try:
            for _ in range(12):  # Codex exports on a batch timer; wait up to three minutes for ingestion
                end = time.time_ns() + 60_000_000_000
                counts = loki_counts(loki_records(started - 60_000_000_000, end), sessions, spec["servers"])
                if sum(sum(c.values()) for c in counts.values()) >= expected:
                    break
                time.sleep(15)
        except OSError as error:  # urllib's URLError and timeouts are OSErrors
            print(f"capability-gate {args.gate}: FAIL | Loki query failed ({type(error).__name__})")
            return 1
        recon = reconcile(rows, counts)
        versions = (f"promptfoo {PROMPTFOO_VERSION}, {codex}, run "
                    f"{datetime.datetime.fromtimestamp(started / 1e9, datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
        line, ok = summary(args.gate, result, recon, versions)
        print(line)
        for arm, classes in sorted(class_tallies(rows).items()):
            print(f"  {arm}: " + "; ".join(f"{cls} " + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))
                                           for cls, c in sorted(classes.items())))
        return 0 if ok else 1
    finally:
        # The worktrees are removed even with --keep, so no registered worktree outlives the run. Literal targets: the
        # two paths this run created inside its own private directory.
        for path in worktrees:
            assert path.parent == private and path.name in ("wt-a", "wt-b"), path
            subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(path)],
                           capture_output=True, check=False)
        if args.keep:
            print(f"  private directory kept: {private}", file=sys.stderr)
        else:
            shutil.rmtree(private, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
