#!/usr/bin/env python3
"""Stage 5: collection (pilot spec stage 5). Read-only against the host; writes only into the run root.

  python3 -B collect.py --run-root <root> [--flush-wait 60]

Per trial: Claude transcripts and child transcripts (copied), the trial's auto-memory and team directories (listed),
Loki rows (Claude by session.id and ecosystem.task.id; Codex by env, never codex.sse_event), Codex rollouts of the
trial's thread and its child threads (copied into rollouts/<trial_id>/, so skill_usage.py --lanes reads only that trial),
skill_usage.py --lanes --call-ledger over them, the gateway call logs joined on client_metadata.thread_id, and the
agentsview second parse. Nothing is deleted.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import HOME, gateway_calls_for_threads, load_json, parse_stream_text, read_jsonl, run, utc_now, write_json  # noqa: E402

LOKI = "http://127.0.0.1:21300/loki/api/v1/query_range"
KEEP_FIELDS = ("event_name", "tool_name", "tool_use_id", "success", "decision", "mcp_server_name", "mcp_tool_name",
               "skill_name", "invocation_trigger", "model", "effort", "query_source", "cost_usd", "actor",
               "subagent_type", "agent_name", "agent_type", "workflow_run_id", "ecosystem_task_id", "ecosystem_lane",
               "service_instance_id", "session_id", "env", "conversation_id", "call_id", "tool_namespace", "tool_family",
               "duration_ms", "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens",
               "model_reasoning_effort", "reasoning_effort", "service_tier", "originator", "service_name",
               "receiver_thread_id", "sender_thread_id", "kind", "state", "status", "error_type", "attempt",
               "http_response_status_code", "event_timestamp", "shell_rtk", "output_truncated")


def iso_to_ns(stamp: str) -> int:
    return calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")) * 1_000_000_000


def loki(query: str, start_ns: int, end_ns: int) -> list[dict]:
    rows, cursor = [], start_ns
    while True:
        params = urllib.parse.urlencode({"query": query, "start": str(cursor), "end": str(end_ns), "limit": "5000",
                                         "direction": "forward"})
        with urllib.request.urlopen(f"{LOKI}?{params}", timeout=120) as response:
            data = json.load(response)
        batch = [(int(v[0]), s["stream"]) for s in data["data"]["result"] for v in s["values"]]
        rows += [{"ts_ns": ts, **{k: st[k] for k in KEEP_FIELDS if k in st}} for ts, st in batch]
        if len(batch) < 5000:
            break
        cursor = max(ts for ts, _ in batch) + 1
    rows.sort(key=lambda r: r["ts_ns"])
    return rows


def claude_slug(path: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in path)


def listing(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    for dirpath, _, filenames in os.walk(path):
        for name in sorted(filenames):
            p = Path(dirpath) / name
            out.append({"path": p.relative_to(path).as_posix(), "bytes": p.stat().st_size,
                        "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))})
    return out


def trials(root: Path) -> list[dict]:
    """One record per trial: its ledger rows merged (pre-launch, prepared, meter, launched, exit)."""
    merged = {}
    for row in read_jsonl(root / "ledger.jsonl"):
        tid = row.get("trial_id")
        if not tid:
            continue
        entry = merged.setdefault(tid, {"trial_id": tid, "phases": {}})
        entry["phases"][row.get("phase")] = row
        for key in ("cell", "client", "arm", "task", "instance", "lane", "repeatIndex"):
            if row.get(key) is not None:
                entry[key] = row[key]
    return list(merged.values())


def codex_thread(stream_path: Path) -> str | None:
    for event in parse_stream_text(stream_path.read_text(encoding="utf-8", errors="replace") if stream_path.exists() else ""):
        if isinstance(event, dict) and event.get("type") == "thread.started":
            return event.get("thread_id")
    return None


def rollouts_for(thread_id: str, start: str, end: str) -> list[Path]:
    """The thread's rollout and the rollouts of threads it spawned (their session_meta names it), written in the window."""
    sessions = HOME / ".codex" / "sessions"
    days = {start[:10], end[:10]}
    found = []
    for day in sorted(days):
        folder = sessions / day[:4] / day[5:7] / day[8:10]
        if not folder.exists():
            continue
        for path in sorted(folder.glob("rollout-*.jsonl")):
            if thread_id in path.name:
                found.append(path)
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    head = handle.readline()
            except OSError:
                continue
            if thread_id in head:
                found.append(path)
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--flush-wait", type=int, default=60)
    args = parser.parse_args(argv)
    root = Path(args.run_root)
    cfg = load_json(root / "run.json")
    all_trials = trials(root)
    ends = [t["phases"].get("exit", {}).get("at") for t in all_trials if t["phases"].get("exit")]
    if ends:
        newest = max(iso_to_ns(e) for e in ends) / 1e9
        wait = args.flush_wait - (time.time() - newest)
        if wait > 0:
            time.sleep(wait)
    summary = {"collected_at": utc_now(), "trials": {}}
    first_start = min((t["phases"].get("pre-launch", {}).get("at") for t in all_trials if t["phases"].get("pre-launch")), default=None)
    for trial in all_trials:
        tid, client = trial["trial_id"], trial.get("client")
        pre = trial["phases"].get("pre-launch", {})
        exit_row = trial["phases"].get("exit", {})
        launched = trial["phases"].get("launched", {})
        start = launched.get("at") or pre.get("at")
        end = exit_row.get("at") or utc_now()
        record = {"client": client, "cell": trial.get("cell"), "window": [start, end]}
        start_ns, end_ns = iso_to_ns(start) - 120 * 10**9, iso_to_ns(end) + 600 * 10**9
        stream = root / "raw" / f"{tid}.stream.jsonl"
        if client == "claude":
            hits = sorted((HOME / ".claude/projects").glob(f"*/{tid}.jsonl"))
            dest = root / "transcripts" / tid
            dest.mkdir(parents=True, exist_ok=True)
            if hits:
                shutil.copy2(hits[0], dest / "main.jsonl")
                project = hits[0].parent
                children = project / tid
                if children.exists() and not (dest / "children").exists():
                    shutil.copytree(children, dest / "children")
                record["transcript"] = {"found": True, "children": [p["path"] for p in listing(dest / "children")]}
                record["auto_memory"] = listing(project / "memory")
                record["project_slug_matches_fixture"] = project.name == claude_slug(exit_row.get("fixture_private") or
                                                                                      trial["phases"].get("prepared", {}).get("fixture_private") or "")
            else:
                record["transcript"] = {"found": False}
            window = (iso_to_ns(start) / 1e9 - 60, iso_to_ns(end) / 1e9 + 60)
            record["team_dirs"] = sorted(p.name for base in ("teams", "tasks") for p in (HOME / ".claude" / base).glob("*")
                                         if p.exists() and window[0] <= p.stat().st_mtime <= window[1]) if (HOME / ".claude").exists() else []
            try:
                by_session = loki(f'{{service_name="claude-code"}} | session_id="{tid}"', start_ns, end_ns)
                by_task = loki(f'{{service_name="claude-code"}} | ecosystem_task_id="{tid}"', start_ns, end_ns)
                write_json(root / "loki" / f"{tid}.json", {"by_session_id": by_session, "by_ecosystem_task_id": by_task}, 0o600)
                record["loki"] = {"by_session_id": len(by_session), "by_ecosystem_task_id": len(by_task)}
            except Exception as error:  # noqa: BLE001
                record["loki"] = {"error": type(error).__name__}
        elif client == "codex":
            thread = codex_thread(stream)
            if not thread and trial.get("cell") == "codex-app-server":
                thread = None  # recorded from the app-server rollout below
            record["thread_id"] = thread
            files = rollouts_for(thread, start, end) if thread else []
            if trial.get("cell") == "codex-app-server" and not files:
                files = [p for p in rollouts_for(tid, start, end)]
            dest = root / "rollouts" / tid
            dest.mkdir(parents=True, exist_ok=True)
            for path in files:
                if not (dest / path.name).exists():
                    shutil.copy2(path, dest / path.name)
            record["rollouts"] = [p.name for p in files]
            try:
                rows = loki(f'{{service_name=~"codex.*"}} | env="{tid}" | event_name!="codex.sse_event"', start_ns, end_ns)
                write_json(root / "loki" / f"{tid}.json", {"by_env": rows}, 0o600)
                record["loki"] = {"by_env": len(rows)}
            except Exception as error:  # noqa: BLE001
                record["loki"] = {"error": type(error).__name__}
            if files:
                ledger_path = root / "call-ledgers" / f"{tid}.jsonl"
                if ledger_path.exists():
                    ledger_path = root / "call-ledgers" / f"{tid}.{int(time.time())}.jsonl"
                repo = Path(cfg["repo"])
                proc = run(["python3", "-B", str(repo / "tools/skill-usage/skill_usage.py"), "--lanes", "--codex-root", str(dest),
                            "--since", start, "--until", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(iso_to_ns(end) / 1e9 + 600)),
                            "--json", "--call-ledger", str(ledger_path)], timeout=600, cwd=str(root))
                try:
                    lanes = json.loads(proc.stdout.decode() or "{}")
                except ValueError:
                    lanes = {"unparsed": proc.stdout.decode(errors="replace")[:500]}
                write_json(root / "rollouts" / f"{tid}.lanes.json", {"rc": proc.returncode, "report": lanes,
                                                                      "stderr_tail": proc.stderr.decode(errors="replace")[-800:]}, 0o600)
                record["lanes_rc"] = proc.returncode
            threads = set()
            for path in files:
                try:
                    with open(path, encoding="utf-8") as handle:
                        meta = json.loads(handle.readline()).get("payload") or {}
                    threads.add(meta.get("id"))
                except (OSError, ValueError):
                    continue
            threads.discard(None)
            if threads:
                calls = gateway_calls_for_threads(threads, start, time.strftime("%Y-%m-%dT%H:%M:%S.999Z", time.gmtime(iso_to_ns(end) / 1e9 + 60)))
                write_json(root / "gateway" / f"{tid}.json", calls, 0o600)
                record["gateway"] = {"threads": len(threads), "calls": sum(len(v) for v in calls["by_thread"].values()),
                                     "errors": calls["errors"]}
        summary["trials"][tid] = record
    # agentsview second parse (S10): one export per client, tool calls per trial session.
    if first_start:
        for agent in ("claude", "codex"):
            proc = run(["agentsview", "export", "sessions", "--agent", agent, "--active-since", first_start,
                        "--include-automated", "--include-one-shot", "--include-children", "--json"], timeout=300)
            try:
                export = json.loads(proc.stdout.decode() or "{}")
            except ValueError:
                export = {"unparsed": True}
            write_json(root / "agentsview" / f"export-{agent}.json", {"rc": proc.returncode, "export": export}, 0o600)
        for tid, record in summary["trials"].items():
            session = tid if record.get("client") == "claude" else record.get("thread_id")
            if not session:
                continue
            ids = [session]
            export = load_json(root / "agentsview" / f"export-{record['client']}.json").get("export")
            for item in (export.get("sessions") if isinstance(export, dict) else export) or []:
                sid = str(item.get("id") or item.get("session_id") or "")
                if session in sid and sid not in ids:
                    ids.insert(0, sid)
            for sid in ids:
                proc = run(["agentsview", "session", "tool-calls", sid, "--json"], timeout=120)
                if proc.returncode == 0 and proc.stdout.strip():
                    try:
                        write_json(root / "agentsview" / f"{tid}.tool-calls.json", {"id": sid, "calls": json.loads(proc.stdout.decode())}, 0o600)
                        record["agentsview"] = {"id_matched": True}
                        break
                    except ValueError:
                        continue
            else:
                record["agentsview"] = {"id_matched": False}
    write_json(root / "collect.json", summary, 0o600)
    print(json.dumps({"trials": len(summary["trials"]), "collected_at": summary["collected_at"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
