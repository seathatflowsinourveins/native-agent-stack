#!/usr/bin/env python3
"""Run one Codex capability gate through promptfoo 0.123.1 and reconcile it with native Codex OTel in Loki.

promptfoo's openai:codex-sdk provider drives `codex exec --profile stack-worker` (through codex-profile-exec) and scores
each row with its own assertions: trajectory spans plus the tool-result checks in assertions.js. This wrapper adds only
what promptfoo does not do:
- it creates the two M13 worktrees at HEAD and removes them afterwards;
- it keeps promptfoo's database, logs and results in a private temporary directory, with telemetry and sharing off;
- it retains a copy of the results file, which holds the Codex items every verdict is scored from, in a private state
  directory (see retain), and prints the copy's sha256 in the verdict line, so the verdicts can be checked again
  against the returned results;
- it reads the verdicts from promptfoo's results file. Every arm must produce exactly its expected rows, each in its
  own conversation; every gate row must pass; and every control row must fail by assertion (not by a provider
  error), with the outcome its manipulation predicts while the tools it does not touch keep working;
- it counts, per row, the MCP calls in the provider's raw items and the `codex.tool_result` records that Codex's own
  OTel exporter sent to Loki for the same conversation. The two counts must be equal for every row.

It prints counts, verdicts and the retained file's hash only, never model text, tool results or conversation ids; its
first line fits in the 400-character excerpt that `scripts/host_receipts.py record` keeps. Exit 0 means the gate passed.

Loki: http://127.0.0.1:13100 (observability/backends/README.md), override with CAPABILITY_GATE_LOKI. Runs through the
SDK arrive as service_name "codex_sdk_ts": the bundled @openai/codex-sdk 0.153.4 sets
CODEX_INTERNAL_ORIGINATOR_OVERRIDE=codex_sdk_ts unless the environment already carries it. conversation_id is the
thread id, and MCP records are keyed on tool_namespace "mcp__<server>" (observability/collector/README.md).

Usage: run_gate.py {jcodemunch,ai-memory,m13} --provider native|omniroute
       [--omniroute-base-url http://127.0.0.1:PORT/v1] [--keep]

Retention: CAPABILITY_GATE_RETAIN overrides the state directory (see retain_root).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
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
sys.path.insert(0, str(HERE.parent / "sota-convergence"))
import codex_lane as provider_routes  # noqa: E402
PROMPTFOO_VERSION = "0.123.1"
# Per gate: the MCP servers it counts, whether it needs the two M13 worktrees, promptfoo's concurrency, and the exact
# number of rows each arm must produce (the configs' tests and repeats; m13_tests.js for M13).
GATES = {
    "jcodemunch": {"config": "jcodemunch.yaml", "servers": ("jcodemunch",), "worktrees": False, "concurrency": 1,
                   "rows": {"gate": 6, "ctrl-prompt": 2, "ctrl-disabled": 2}},
    "ai-memory": {"config": "ai-memory.yaml", "servers": ("ai-memory",), "worktrees": False, "concurrency": 1,
                  "rows": {"gate": 6, "ctrl-prompt": 2, "ctrl-disabled": 2}},
    "m13": {"config": "m13.yaml", "servers": ("context-mode", "serena"), "worktrees": True, "concurrency": 2,
            "rows": {"gate": 40, "ctrl-disabled": 6, "ctrl-wrongroot": 6}},
}
SERVICE = "codex_sdk_ts"
LOKI = os.environ.get("CAPABILITY_GATE_LOKI", "http://127.0.0.1:13100")
# A label filter expression also filters on structured metadata (Loki v3.7.8,
# docs/sources/get-started/labels/structured-metadata.md#L74); on the 2026-09-27 smoke window it returned the same
# 604 tool results as filtering the whole service stream client-side.
LOKI_QUERY = f'{{service_name="{SERVICE}"}} | event_name="codex.tool_result"'
LOKI_PAGE = 5000
ASSERTION_FAILED = 1  # promptfoo ResultFailureReason.ASSERT; 2 is ERROR (a provider or runtime error)
# The error of an MCP call that needs approval under approval policy never (openai/codex rust-v0.157.1,
# codex-rs/core/src/mcp_tool_call.rs#L1612), as the 2026-09-27 smoke's refused calls carried it.
REFUSED = "MCP tool call requires approval, but approval policy is never"
CTX_CLASSES = ("ctx_execute", "ctx_execute_file", "ctx_index_search")
UNAFFECTED_CLASSES = ("shell", "serena")
WRONG_ROOT_OUTCOMES = ("wrong_root_or_stale", "error_only", "miss")


class LokiPageError(RuntimeError):
    """A full Loki page within one timestamp: the query cannot advance without skipping records."""


def namespace(server: str) -> str:
    return "mcp__" + server.replace("-", "_")


def arm_of(label: str, gate: str) -> str:
    return label.rsplit("-", 1)[0] if gate == "m13" else label


def error_message(error) -> str:
    return str(error.get("message", "")) if isinstance(error, dict) else str(error or "")


def parse_rows(results: dict, gate: str) -> list[dict]:
    """One dict per promptfoo row: arm, pass/fail, failure reason, conversation id, per-server MCP calls (all, completed
    without error, refused for approval) and M13 class verdicts."""
    servers = GATES[gate]["servers"]
    rows = []
    for row in results["results"]["results"]:
        response = row.get("response") or {}
        try:
            raw = response.get("raw")
            items = json.loads(raw if isinstance(raw, str) else json.dumps(raw or {})).get("items") or []
        except (TypeError, ValueError):
            items = []
        mcp = [item for item in items if item.get("type") == "mcp_tool_call" and item.get("server") in servers]
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
            "calls": Counter(item["server"] for item in mcp),
            "completed": Counter(item["server"] for item in mcp
                                 if item.get("status") == "completed" and not item.get("error")),
            "refused": Counter(item["server"] for item in mcp
                               if item.get("status") == "failed" and REFUSED in error_message(item.get("error"))),
            "classes": classes,
        })
    return rows


def rows_without_sentinel(results: dict, gate: str) -> int:
    """How many m13 rows lack their own sentinel in the results file, so that their class verdicts could not be checked
    again from it. m13_hooks.js stores it as vars.sentinel; promptfoo 0.123.1's sanitizer (src/util/sanitizer.ts)
    writes secret-named vars, `token` among them, as [REDACTED]."""
    if gate != "m13":
        return 0
    missing = 0
    for row in results["results"]["results"]:
        variables = row.get("vars") or {}
        own = rf"CGTOK-{re.escape(str(variables.get('tree')))}-{re.escape(str(variables.get('rep')))}-[0-9a-f]{{16}}"
        if not re.fullmatch(own, str(variables.get("sentinel"))):
            missing += 1
    return missing


def control_outcome(row: dict, gate: str) -> bool:
    """Whether a control row failed the way its manipulation predicts, with the tools it does not touch still working:
    - ctrl-prompt: every call to the server was attempted and refused for approval, none completed;
    - ctrl-disabled (jcodemunch, ai-memory): no call to the server;
    - M13 ctrl-disabled: no call of any context-mode class, while the shell and serena classes read their own token;
    - M13 ctrl-wrongroot: no context-mode class returns its own token after a prescribed call (each returns the other
      tree's token, an error or nothing), while the shell and serena classes read their own token."""
    arm = row["arm"]
    if gate == "m13":
        classes = row["classes"]
        if any(classes.get(cls) != "own" for cls in UNAFFECTED_CLASSES):
            return False
        if arm == "ctrl-disabled":
            return all(classes.get(cls) == "no_call" for cls in CTX_CLASSES)
        if arm == "ctrl-wrongroot":
            return all(classes.get(cls) in WRONG_ROOT_OUTCOMES for cls in CTX_CLASSES)
        return False
    server = GATES[gate]["servers"][0]
    if arm == "ctrl-prompt":
        return row["calls"][server] >= 1 and row["refused"][server] == row["calls"][server] and not row["completed"][server]
    if arm == "ctrl-disabled":
        return row["calls"][server] == 0
    return False


def verdict(rows: list[dict], gate: str) -> dict:
    """Per arm: rows, passed, failed by assertion, failed as predicted (controls), errored. The gate passes only when:
    - every arm has exactly its expected number of rows, and no other arm appears;
    - every row has a conversation id and no two rows share one;
    - every gate row passes;
    - every control row fails by assertion with its predicted outcome (control_outcome); a provider error never counts."""
    expected = GATES[gate]["rows"]
    arms: dict[str, Counter] = {}
    for row in rows:
        tally = arms.setdefault(row["arm"], Counter())
        tally["rows"] += 1
        if row["success"]:
            tally["passed"] += 1
        elif row["failure_reason"] == ASSERTION_FAILED:
            tally["failed"] += 1
            if row["arm"].startswith("ctrl-") and control_outcome(row, gate):
                tally["predicted"] += 1
        else:
            tally["errored"] += 1
    sessions = [row["session"] for row in rows]
    return {
        "arms": arms,
        "rows": len(rows),
        "expected_rows": sum(expected.values()),
        "matrix_ok": {arm: tally["rows"] for arm, tally in arms.items()} == expected,
        "distinct_sessions": len({session for session in sessions if session}),
        "sessions_ok": all(sessions) and len(set(sessions)) == len(sessions),
        "gate_ok": arms.get("gate", Counter())["passed"] == expected["gate"],
        "controls_ok": all(arms.get(arm, Counter())["predicted"] == n for arm, n in expected.items() if arm != "gate"),
    }


def class_tallies(rows: list[dict]) -> dict[str, dict[str, Counter]]:
    tallies: dict[str, dict[str, Counter]] = {}
    for row in rows:
        for cls, reason in row["classes"].items():
            tallies.setdefault(row["arm"], {}).setdefault(cls, Counter())[reason] += 1
    return tallies


def loki_page(start_ns: int, end_ns: int) -> dict:
    params = {"query": LOKI_QUERY, "start": str(start_ns), "end": str(end_ns), "limit": str(LOKI_PAGE),
              "direction": "forward"}
    with urllib.request.urlopen(f"{LOKI}/loki/api/v1/query_range?" + urllib.parse.urlencode(params),
                                timeout=60) as response:
        return json.loads(response.read())


def loki_records(start_ns: int, end_ns: int, page=loki_page) -> list[dict]:
    """Every codex.tool_result record of the SDK's service in [start, end), stream labels merged with structured
    metadata. query_range returns timestamps >= start and < end (Loki v3.7.8,
    docs/sources/reference/loki-http-api.md#L474-L475), so a full page continues from its last timestamp inclusive and
    drops records it has already seen: records sharing the boundary timestamp are neither skipped nor counted twice. A
    full page within a single timestamp cannot advance and raises LokiPageError."""
    out, seen, start = [], set(), start_ns
    while True:
        batch = []
        for stream in page(start, end_ns)["data"]["result"]:
            labels = stream.get("stream") or {}
            for value in stream["values"]:
                meta = (value[2] if len(value) > 2 else {}).get("structuredMetadata") or {}
                key = (value[0], json.dumps(labels, sort_keys=True), value[1], json.dumps(meta, sort_keys=True))
                batch.append((int(value[0]), key, {**labels, **meta}))
        for _, key, record in batch:
            if key not in seen:
                seen.add(key)
                out.append(record)
        if len(batch) < LOKI_PAGE:
            return out
        first, last = min(ts for ts, _, _ in batch), max(ts for ts, _, _ in batch)
        if first == last:
            raise LokiPageError(f"{LOKI_PAGE} records share one timestamp")
        start = last


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


def summary(gate: str, result: dict, recon: tuple[int, int, int], versions: str,
            results_sha256: str = "") -> tuple[str, bool]:
    """The first output line and the gate verdict (see verdict), which also needs every row to reconcile with Loki and
    the results file to be retained (its sha256 given)."""
    arms = result["arms"]
    parts = []
    for arm in sorted(arms, key=lambda a: (a != "gate", a)):
        t = arms[arm]
        n, what = (t["passed"], "pass") if arm == "gate" else (t["predicted"], "fail as predicted")
        parts.append(f"{arm} {n}/{t['rows']} {what}" + (f", {t['errored']} errored" if t["errored"] else ""))
    ok = (result["matrix_ok"] and result["sessions_ok"] and result["gate_ok"] and result["controls_ok"]
          and recon[1] > 0 and recon[0] == recon[1] and bool(results_sha256))
    rows = (f"{result['rows']} rows {'as expected' if result['matrix_ok'] else 'NOT the expected ' + str(result['expected_rows']) + ' by arm'}"
            f", {result['distinct_sessions']} distinct sessions")
    return (f"capability-gate {gate}: {'PASS' if ok else 'FAIL'} | " + "; ".join(parts) + f" | {rows}"
            f" | loki {recon[0]}/{recon[1]} rows match ({recon[2]} MCP tool results)"
            f" | results {results_sha256 or 'NOT retained'} | {versions}"), ok


def retain_root() -> Path:
    """Where runs' results are retained: CAPABILITY_GATE_RETAIN, else native-agent-stack/capability-gate under
    $XDG_STATE_HOME (default ~/.local/state). This is private host state and is never committed."""
    configured = os.environ.get("CAPABILITY_GATE_RETAIN")
    if configured:
        return Path(configured)
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "native-agent-stack" / "capability-gate"


def retain(results_path: Path, root: Path, name: str) -> tuple[str, str]:
    """Copy the results file to <root>/<name>/results.json and return its sha256 and its path relative to root. The run
    directory must be new and the file is never overwritten; directories are 0700 and the file 0600, because it holds
    tool results and model text (docs/acceptance-evidence-policy.md: keep sensitive raw output private)."""
    data = results_path.read_bytes()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    (root / name).mkdir(mode=0o700)
    target = root / name / "results.json"
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(data)
    return hashlib.sha256(data).hexdigest(), f"{name}/results.json"


def promptfoo_env(private: Path, main_checkout: str, *, provider: str, base_url: str | None = None) -> dict[str, str]:
    """The environment for promptfoo and, through inherit_process_env, Codex. Inherited PROMPTFOO_* settings are
    dropped, so none can move promptfoo's database, logs or cache out of the private directory, and the log directory
    is pinned inside it: promptfoo 0.123.1 src/logger.ts#L227 honors PROMPTFOO_LOG_DIR and otherwise uses
    <config dir>/logs."""
    provider_routes.provider_args(provider, base_url)
    env = {key: os.environ[key] for key in os.environ
           if not key.startswith("PROMPTFOO_") and key not in {"NAS_CODEX_PROVIDER", "NAS_CODEX_BASE_URL"}
           and not (provider == "omniroute" and key == "OMNIROUTE_API_KEY")}
    env = provider_routes.provider_env(provider, env)
    env.update({"PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1",
                "PROMPTFOO_CONFIG_DIR": str(private / "promptfoo"), "PROMPTFOO_LOG_DIR": str(private / "logs"),
                "CAPABILITY_GATE_LAUNCHER": str(HERE / "codex-profile-exec"),
                "CAPABILITY_GATE_MAIN_CHECKOUT": main_checkout, "NAS_CODEX_PROVIDER": provider})
    if base_url is not None:
        env["NAS_CODEX_BASE_URL"] = base_url
    return env


def run(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gate", choices=sorted(GATES))
    parser.add_argument("--keep", action="store_true", help="keep the private directory (results, log, worktrees)")
    parser.add_argument("--provider", choices=("native", "omniroute"), required=True,
                        help="explicit Codex model provider for every gate and control")
    parser.add_argument("--omniroute-base-url", help="explicit public loopback gateway base URL ending /v1")
    args = parser.parse_args(argv)
    try:
        provider_routes.provider_args(args.provider, args.omniroute_base_url)
    except ValueError as error:
        parser.error(str(error))
    spec = GATES[args.gate]

    repo = Path(run(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"]))
    porcelain = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"]).splitlines()
    main_checkout = next(line.split(" ", 1)[1] for line in porcelain if line.startswith("worktree "))
    promptfoo = os.environ.get("CAPABILITY_GATE_PROMPTFOO") or shutil.which("promptfoo")
    if not promptfoo:
        print("capability-gate: FAIL | promptfoo is not on PATH (set CAPABILITY_GATE_PROMPTFOO)")
        return 2

    private = Path(tempfile.mkdtemp(prefix="capability-gate-"))
    worktrees: list[Path] = []
    env = promptfoo_env(private, main_checkout, provider=args.provider, base_url=args.omniroute_base_url)
    try:
        found = run([promptfoo, "--version"], env=env).splitlines()[-1].strip()
        if found != PROMPTFOO_VERSION:
            print(f"capability-gate: FAIL | promptfoo {found} found, {PROMPTFOO_VERSION} required")
            return 2
        codex = run([str(HERE / "codex-profile-exec"), "--version"]).splitlines()[-1].strip()
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
        stamp = datetime.datetime.fromtimestamp(started / 1e9, datetime.timezone.utc)
        try:
            results_sha256, retained = retain(results_path, retain_root(),
                                              f"{args.gate}-{stamp:%Y%m%dT%H%M%SZ}-{os.getpid()}")
        except OSError as error:
            print(f"capability-gate {args.gate}: FAIL | the results file could not be retained ({type(error).__name__})")
            args.keep = True
            return 1
        results = json.loads(results_path.read_text())
        missing = rows_without_sentinel(results, args.gate)
        if missing:
            print(f"capability-gate {args.gate}: FAIL | {missing} rows lack their sentinel in the retained results, so "
                  "their verdicts cannot be checked again")
            return 1
        rows = parse_rows(results, args.gate)
        result = verdict(rows, args.gate)
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
        except (OSError, ValueError, KeyError, LokiPageError) as error:  # URLError and timeouts are OSErrors
            print(f"capability-gate {args.gate}: FAIL | Loki query failed ({type(error).__name__})")
            return 1
        recon = reconcile(rows, counts)
        versions = f"promptfoo {PROMPTFOO_VERSION}, {codex}, run {stamp:%Y-%m-%dT%H:%M:%SZ}"
        line, ok = summary(args.gate, result, recon, versions, results_sha256)
        print(line)
        for arm, classes in sorted(class_tallies(rows).items()):
            print(f"  {arm}: " + "; ".join(f"{cls} " + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))
                                           for cls, c in sorted(classes.items())))
        print(f"  retained results: {retained} in the capability-gate state directory (sha256 {results_sha256})")
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
