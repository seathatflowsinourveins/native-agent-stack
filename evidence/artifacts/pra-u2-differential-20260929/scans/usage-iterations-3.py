"""Third count-only scan: the anomalous rows (top-level zero with a nonzero message iteration, fallback rows) and the message ids
with an advisor call but no advisor_message iteration. Counts and enum value classes only."""
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
                for raw in fh:
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
                    if not isinstance(u, dict) or not isinstance(msg.get("id"), str):
                        continue
                    groups[msg["id"]].append(row)
            for mid, rows in groups.items():
                best = None
                for r in rows:
                    if best is None or total(r["message"]["usage"]) >= total(best["message"]["usage"]):
                        best = r
                u = best["message"]["usage"]
                it = u.get("iterations")
                types = [x.get("type") for x in it if isinstance(x, dict)] if isinstance(it, list) else None
                blocks = [b for r in rows for b in (r["message"].get("content") or []) if isinstance(b, dict)] if all(isinstance(r["message"].get("content"), list) for r in rows) else []
                block_types = sorted({b.get("type") for b in blocks if isinstance(b.get("type"), str)})
                # anomalous zero-top rows among counted rows
                if isinstance(it, list) and types == ["message"] and total(u) == 0 and total(it[0]) > 0:
                    c["zero_top_counted"]["model=%s version=%s stop=%s blocks=%s" % (best["message"].get("model"), best.get("version"), best["message"].get("stop_reason"), ",".join(block_types))] += 1
                # any zero-top row with nonzero single iteration, counted or not
                for r in rows:
                    ru = r["message"]["usage"]
                    rit = ru.get("iterations")
                    if isinstance(rit, list) and len(rit) == 1 and isinstance(rit[0], dict) and total(ru) == 0 and total(rit[0]) > 0:
                        c["zero_top_any_row"]["counted_row=%s rows_in_id=%d" % (r is best, len(rows))] += 1
                if types and "fallback_message" in types:
                    c["fallback_counted"]["types=%s model=%s blocks=%s stop=%s" % ("+".join(types), best["message"].get("model"), ",".join(block_types), best["message"].get("stop_reason"))] += 1
                    for x in it:
                        if isinstance(x, dict):
                            c["fallback_entries"]["%s model=%s total_zero=%s output_zero=%s" % (x.get("type"), x.get("model"), total(x) == 0, x.get("output_tokens") == 0)] += 1
                adv_calls = [b for b in blocks if b.get("type") == "server_tool_use" and b.get("name") == "advisor"]
                adv_results = [b for b in blocks if b.get("type") == "advisor_tool_result"]
                if adv_calls or adv_results:
                    has_adv = bool(types and "advisor_message" in types)
                    kinds = Counter()
                    for b in adv_results:
                        ct = b.get("content")
                        k = ct.get("type") if isinstance(ct, dict) else type(ct).__name__
                        if isinstance(ct, dict) and ct.get("type") == "advisor_tool_result_error":
                            k += ":" + str(ct.get("error_code"))
                        kinds[k] += 1
                    c["advisor_ids"]["advisor_message_on_counted_row=%s calls=%d results=%d result_kinds=%s counted_types=%s" % (
                        has_adv, min(len(adv_calls), 3), min(len(adv_results), 3), ",".join(sorted(kinds)), "+".join(types) if types is not None else "(no iterations key)")] += 1
                    if has_adv:
                        n_adv = types.count("advisor_message")
                        c["advisor_calls_vs_iterations"]["calls=%d results=%d advisor_iterations=%d" % (len(adv_calls), len(adv_results), n_adv)] += 1
print(json.dumps({k: dict(v) for k, v in c.items()}, indent=1, sort_keys=True))
