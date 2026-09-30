"""Real-window invariants over the U2 kernel's lanes sweep (U2 design 10, step 4). Reads the sweep's JSON output and prints counts only:
call-state invariant violations over every actor and every per-server row, hook blocks against claims per event, and each MCP server's
M15 counts and flags. Server names outside the stack's vocabulary (manifests/stack.json servers, with context-mode's plugin names; the
set of scans/kernel-m14-m15.mjs) are folded into (other), their counts summed and their rates computed again.
  python3 waa-invariants.py <sweep output .json>"""
import json
import sys

PUBLIC_SERVERS = {"ai-memory", "codebase-memory", "context-mode", "headroom", "jcodemunch", "plugin_context-mode",
                  "plugin_context-mode_context-mode", "qmd", "serena", "socraticode"}
THRESHOLD_CALLS_PER_ERROR = 100  # preregistration.json thresholds.M15: at most 0.01, compared on the counts


def fold(by_server):
    rows = {}
    for server, r in by_server.items():
        key = server if server in PUBLIC_SERVERS else "(other)"
        t = rows.setdefault(key, {"attempted": 0, "infrastructure_errors": 0, "new_class_errors": 0, "unknowns": 0, "every_error_classified": True})
        for k in ("attempted", "infrastructure_errors", "new_class_errors", "unknowns"):
            t[k] += r[k]
        t["every_error_classified"] = t["every_error_classified"] and r["every_error_classified"]
    for t in rows.values():
        n, known, every = t["attempted"], t["infrastructure_errors"] + t["new_class_errors"], t["infrastructure_errors"] + t["new_class_errors"] + t["unknowns"]
        t["rate"] = round(every / n, 4) if n else None
        t["rate_lower_bound"] = round(known / n, 4) if n else None
        t["threshold_sensitive"] = every * THRESHOLD_CALLS_PER_ERROR > n and not known * THRESHOLD_CALLS_PER_ERROR > n
    return dict(sorted(rows.items()))


out = json.load(open(sys.argv[1], encoding="utf-8"))
viol = {"actors_checked": 0, "server_rows_checked": 0, "actor_attempted": 0, "actor_executed": 0, "actor_rejected_sources": 0,
        "server_attempted": 0, "server_executed": 0, "final_return_counts_without_measured": 0}


def check(cs):
    attempted = cs["attempted"] == (cs["executed"] + cs["rejected"] + cs["invalid"] + cs["cancelled_with_result"]
                                    + cs["cancelled_or_unfinished"] + cs["unknown"])
    executed = cs["executed"] == cs["succeeded"] + cs["failed"] + cs["interrupted"]
    return attempted, executed


for actor in out["actors"]:
    m = actor["measurement"]
    cs = m["call_states"]
    viol["actors_checked"] += 1
    ok, ex = check(cs)
    viol["actor_attempted"] += not ok
    viol["actor_executed"] += not ex
    viol["actor_rejected_sources"] += cs["rejected"] != sum(cs["rejected_by_source"].values())
    for row in cs["by_server"].values():
        viol["server_rows_checked"] += 1
        ok, ex = check(row)
        viol["server_attempted"] += not ok
        viol["server_executed"] += not ex
    f = m["final_return"]
    if f["status"] != "measured" and any(f[k] is not None for k in ("final", "empty_text", "wait_notice", "background_started", "background_pending")):
        viol["final_return_counts_without_measured"] += 1

hooks, m15 = {}, {}
for scope, g in (("children", out["groups"]["all"]["measurement"]), ("main", out["main"]["measurement"])):
    h = g["hook_context"]
    events = sorted(list(h["blocks_by_event"]) + [e for e in h["claimed_by_event"] if e not in h["blocks_by_event"]])
    hooks[scope] = {e: {"blocks": h["blocks_by_event"].get(e, 0), "claimed": h["claimed_by_event"].get(e, 0)} for e in events}
    hooks[scope]["(claimed_plain_stdout)"] = h["claimed_plain_stdout"]
    hooks[scope]["(other_hook_rows)"] = h["other_hook_rows"]
    m15[scope] = fold(g["m15"]["by_server"])
print(json.dumps({"kind": "pra_u2_real_window_invariants", "window": out["window"], "children_in_window": out["children_in_window"],
                  "main_sessions_in_window": out["main_sessions_in_window"], "call_state_invariant_violations": viol,
                  "hook_context_by_event": hooks, "m15_by_server": m15}, indent=1, sort_keys=True))
