#!/usr/bin/env python3
"""Counts-only check of a private Codex call ledger against its own lane report (PR-A U3 repair round, binding correction 1).

Usage: python3 -B ledger-host-check.py <report.json> <ledger.jsonl>

Prints only counts, states, kinds and booleans: never an id, a path, a tool name outside a fixed class list, or command text.
Invariants checked against the kernel's published per-actor call_states (PR-A U2's kernel):
  - total rows == sum of call_states.attempted over the actors, and per actor by actor_ordinal;
  - rows per M14 state == the per-state sums;
  - rows with sandbox true == sum of call_states.sandbox and == sum of sandbox_operations;
  - each row's owner_kind == the kind of the actor its actor_ordinal names;
  - no ledger id (thread or call) appears in the report, as a string value or inside one.
"""
import collections
import json
import os
import stat
import sys


def strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def main(report_path, ledger_path):
    report = json.loads(open(report_path, encoding="utf-8").read())
    rows = [json.loads(line) for line in open(ledger_path, encoding="utf-8") if line.strip()]
    mode = stat.S_IMODE(os.stat(ledger_path).st_mode)
    actors = report["actors"]
    out = collections.OrderedDict()
    out["ledger.mode_0600"] = mode == 0o600
    out["ledger.rows"] = len(rows)
    out["ledger.schema"] = sorted({row.get("schema") for row in rows})
    out["ledger.field_sets"] = len({tuple(row) for row in rows})
    out["report.actors"] = len(actors)
    out["report.sessions_in_window"] = report.get("sessions_in_window")
    out["ledger.actors_with_rows"] = len({row["actor_ordinal"] for row in rows})
    out["ledger.threads"] = len({row["thread_id"] for row in rows})
    out["ledger.call_id_null"] = sum(row["call_id"] is None for row in rows)
    keys = collections.Counter((row["thread_id"], row["call_id"]) for row in rows if row["call_id"] is not None)
    out["ledger.duplicate_keys"] = sum(1 for count in keys.values() if count > 1)
    out["ledger.by_state"] = dict(sorted(collections.Counter(row["state"] for row in rows).items()))
    out["ledger.by_owner_kind"] = dict(sorted(collections.Counter(str(row["owner_kind"]) for row in rows).items()))
    out["ledger.by_history_mode"] = dict(sorted(collections.Counter(row["history_mode"] for row in rows).items()))
    out["ledger.by_native_status"] = dict(sorted(collections.Counter(str(row["native_status"]) for row in rows).items()))
    out["ledger.by_cause"] = dict(sorted(collections.Counter(str(row["cause"]) for row in rows).items()))

    def tool_class(tool):
        return ("mcp" if isinstance(tool, str) and tool.startswith("mcp__") else tool
                if tool in ("Bash", "exec", "wait", "WebSearch", "WebFetch", "spawn_agent", "wait_agent", "apply_patch",
                            "update_plan", "view_image", "write_stdin") else "other")
    out["ledger.by_tool_class"] = dict(sorted(collections.Counter(tool_class(row["tool"]) for row in rows).items()))
    out["ledger.sandbox_true"] = sum(bool(row["sandbox"]) for row in rows)
    out["ledger.code_mode_true"] = sum(bool(row["code_mode"]) for row in rows)
    out["ledger.server_set"] = sum(row["server"] is not None for row in rows)

    # Invariants against the published per-actor measurement.
    states = [actor["measurement"].get("call_states") for actor in actors]
    out["report.actors_with_call_states"] = sum(isinstance(s, dict) for s in states)
    attempted = sum(s["attempted"] for s in states if isinstance(s, dict))
    out["inv.rows_eq_attempted"] = (len(rows), attempted, len(rows) == attempted)
    per_state = collections.Counter()
    for s in states:
        if isinstance(s, dict):
            for key in ("succeeded", "failed", "interrupted", "rejected", "invalid", "cancelled_with_result",
                        "cancelled_or_unfinished", "unknown"):
                per_state[key] += s.get(key, 0)
    by_state = collections.Counter(row["state"] for row in rows)
    out["inv.states_eq"] = all(by_state.get(k, 0) == per_state.get(k, 0) for k in set(by_state) | set(per_state))
    out["inv.state_mismatches"] = {k: (by_state.get(k, 0), per_state.get(k, 0)) for k in sorted(set(by_state) | set(per_state))
                                   if by_state.get(k, 0) != per_state.get(k, 0)}
    sandbox_states = sum(s.get("sandbox", 0) for s in states if isinstance(s, dict))
    sandbox_ops = sum(actor["measurement"].get("sandbox_operations", 0) for actor in actors)
    out["inv.sandbox"] = (out["ledger.sandbox_true"], sandbox_states, sandbox_ops)
    per_actor = collections.Counter(row["actor_ordinal"] for row in rows)
    out["inv.actor_count_mismatches"] = sum(per_actor.get(actor["ordinal"], 0) != (actor["measurement"].get("call_states") or {}).get("attempted", -1)
                                            for actor in actors)
    kinds = {actor["ordinal"]: actor["kind"] for actor in actors}
    out["inv.owner_kind_mismatches"] = sum(row["owner_kind"] != kinds.get(row["actor_ordinal"]) for row in rows)
    # Privacy at scale: no ledger id in the report.
    ids = {row["thread_id"] for row in rows if row["thread_id"]} | {row["call_id"] for row in rows if row["call_id"]}
    values = set(strings(report))
    out["privacy.ids"] = len(ids)
    out["privacy.id_equal_to_a_report_string"] = len(ids & values)
    text = json.dumps(report)
    out["privacy.thread_id_inside_report_text"] = sum(thread in text for thread in {row["thread_id"] for row in rows if row["thread_id"]})
    long_calls = [c for c in {row["call_id"] for row in rows if row["call_id"]} if len(c) >= 12]
    out["privacy.long_call_ids_checked"] = len(long_calls)
    out["privacy.long_call_id_inside_report_text"] = sum(call in text for call in long_calls)
    for key, value in out.items():
        print(f"{key}\t{json.dumps(value, sort_keys=True)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
