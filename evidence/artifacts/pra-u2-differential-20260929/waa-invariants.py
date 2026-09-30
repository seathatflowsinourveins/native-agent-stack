"""Real-window invariants over the U2 kernel's lanes sweep (U2 design 10, step 4). Reads the sweep's JSON output and prints counts only:
call-state invariant violations over every actor and every per-server row, hook blocks against claims per event, and each MCP server's
M15 counts and flags.
  python3 waa-invariants.py <sweep output .json>"""
import json
import sys

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
    m15[scope] = {s: {k: r[k] for k in ("attempted", "infrastructure_errors", "new_class_errors", "unknowns", "rate", "rate_lower_bound",
                                        "threshold_sensitive", "every_error_classified")} for s, r in sorted(g["m15"]["by_server"].items())}
print(json.dumps({"kind": "pra_u2_real_window_invariants", "window": out["window"], "children_in_window": out["children_in_window"],
                  "main_sessions_in_window": out["main_sessions_in_window"], "call_state_invariant_violations": viol,
                  "hook_context_by_event": hooks, "m15_by_server": m15}, indent=1, sort_keys=True))
