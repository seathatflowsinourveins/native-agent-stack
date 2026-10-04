"""Second count-only scan: explains the invariant mismatches, the split-vs-combined differences and the streamed-row shapes.

Prints counts and enum value classes only (no ids, paths or text)."""
import json
import os
import sys
from collections import Counter, defaultdict

COUNTERS = ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"]


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def total(u):
    return sum(u.get(k, 0) for k in COUNTERS if num(u.get(k)))


c = defaultdict(Counter)
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            groups = defaultdict(list)
            try:
                fh = open(os.path.join(dirpath, name), "rb")
            except OSError:
                continue
            with fh:
                for i, raw in enumerate(fh):
                    if b'"assistant"' not in raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(row, dict) or row.get("type") != "assistant" or not isinstance(row.get("message"), dict):
                        continue
                    msg = row["message"]
                    u = msg.get("usage")
                    if not isinstance(u, dict):
                        continue
                    it = u.get("iterations")
                    types = tuple(x.get("type") for x in it) if isinstance(it, list) else None
                    model = msg.get("model") if isinstance(msg.get("model"), str) else "(none)"
                    synthetic = model == "<synthetic>"
                    # (a) invariant, by iteration shape
                    if isinstance(it, list):
                        sums = defaultdict(Counter)
                        for x in it:
                            if isinstance(x, dict):
                                for k in COUNTERS:
                                    if num(x.get(k)):
                                        sums[x.get("type")][k] += x[k]
                        shape = "+".join(types) if types else "(empty)"
                        eq_msg = all(num(u.get(k)) and u[k] == sums["message"][k] for k in COUNTERS)
                        eq_fb = all(num(u.get(k)) and u[k] == sums["fallback_message"][k] for k in COUNTERS)
                        eq_msg_fb = all(num(u.get(k)) and u[k] == sums["message"][k] + sums["fallback_message"][k] for k in COUNTERS)
                        eq_all = all(num(u.get(k)) and u[k] == sum(s[k] for s in sums.values()) for k in COUNTERS)
                        c["invariant_by_shape"][shape + (" synthetic" if synthetic else "") + " :: top==msg " + str(eq_msg) + " top==fallback " + str(eq_fb) + " top==msg+fallback " + str(eq_msg_fb) + " top==all " + str(eq_all)] += 1
                        if not it:
                            c["empty_iterations_model"][model] += 1
                            c["empty_iterations_total_zero"]["zero" if total(u) == 0 else "nonzero"] += 1
                            c["empty_iterations_version"][row.get("version") if isinstance(row.get("version"), str) else "(none)"] += 1
                            c["empty_iterations_stop_reason"][str(msg.get("stop_reason"))] += 1
                            c["empty_iterations_isApiError"][str(bool(row.get("isApiErrorMessage")))] += 1
                        for x in it:
                            if isinstance(x, dict) and x.get("type") == "message" and "model" in x:
                                c["message_iteration_model_value"][x["model"] if isinstance(x["model"], str) else repr(x["model"])] += 1
                    # (b) split vs combined at top level
                    cc = u.get("cache_creation")
                    if isinstance(cc, dict) and num(u.get("cache_creation_input_tokens")):
                        s = sum(cc.get(k, 0) for k in ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens") if num(cc.get(k)))
                        adv = 0
                        if isinstance(it, list):
                            for x in it:
                                if isinstance(x, dict) and x.get("type") == "advisor_message" and num(x.get("cache_creation_input_tokens")):
                                    adv += x["cache_creation_input_tokens"]
                        tag = "equal" if s == u["cache_creation_input_tokens"] else ("split==combined+advisor" if adv and s == u["cache_creation_input_tokens"] + adv else "differ")
                        tag2 = ("iterations " + ("+".join(types) if types else "(empty)")) if types is not None else "no_iterations_key"
                        c["split_vs_combined"][tag + " | " + tag2] += 1
                        if tag == "differ":
                            c["differ_split_minus_combined_sign"]["split>combined" if s > u["cache_creation_input_tokens"] else "split<combined"] += 1
                            c["differ_model"][model] += 1
                    # iteration-level split vs combined
                    if isinstance(it, list):
                        for x in it:
                            if not isinstance(x, dict):
                                continue
                            icc = x.get("cache_creation")
                            if isinstance(icc, dict) and num(x.get("cache_creation_input_tokens")):
                                s = sum(icc.get(k, 0) for k in ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens") if num(icc.get(k)))
                                c["iteration_split_vs_combined"][str(x.get("type")) + ":" + ("equal" if s == x["cache_creation_input_tokens"] else "differ")] += 1
                    mid = msg.get("id")
                    if isinstance(mid, str):
                        groups[mid].append((i, types, total(u), row.get("requestId") is not None, json.dumps(it, sort_keys=True) if isinstance(it, list) else None,
                                            bool(any(isinstance(b, dict) and b.get("type") == "server_tool_use" and b.get("name") == "advisor" for b in (msg.get("content") or []) if isinstance(msg.get("content"), list)))))
            # (c) streamed rows per id
            for mid, rows in groups.items():
                with_it = [r for r in rows if r[1] is not None]
                if len(rows) > 1:
                    pattern = "".join("I" if r[1] is not None else "-" for r in rows)
                    if len(pattern) > 6:
                        pattern = pattern[:3] + "..." + pattern[-3:]
                    c["multi_row_pattern"][pattern] += 1
                    totals = [r[2] for r in rows]
                    c["multi_row_totals"]["equal" if len(set(totals)) == 1 else ("max_on_iteration_row" if with_it and max(r[2] for r in with_it) == max(totals) else "max_on_plain_row")] += 1
                    # would transcriptUsage's pick (largest total, ties -> later row) carry iterations?
                    best = None
                    for r in rows:
                        if best is None or r[2] >= best[2]:
                            best = r
                    c["kernel_pick_has_iterations"][("yes" if best[1] is not None else "no") + (" (id has iterations elsewhere)" if with_it and best[1] is None else "")] += 1
                    sigs = {r[4] for r in with_it}
                    c["distinct_iterations_per_id"][str(len(sigs))] += 1
                    adv_rows = [r for r in rows if r[5]]
                    if adv_rows:
                        has_adv_it = any(r[4] and "advisor_message" in r[4] for r in with_it)
                        c["advisor_block_ids"]["advisor_message iteration on some row: " + str(has_adv_it)] += 1
                else:
                    r = rows[0]
                    if r[5]:
                        c["advisor_block_ids"]["single row; advisor_message iteration: " + str(bool(r[4] and "advisor_message" in r[4]))] += 1
print(json.dumps({k: dict(v) for k, v in c.items()}, indent=1, sort_keys=True))
