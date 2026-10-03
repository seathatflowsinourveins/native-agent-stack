"""Fourth count-only scan: what the top-level cache_creation 5m/1h object equals on multi-iteration rows, and the client versions of
counted rows (with a successful advisor result) that carry no iterations. Counts and enum value classes only."""
import json
import os
import sys
from collections import Counter, defaultdict

COUNTERS = ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"]
SPLIT = ["ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"]


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def total(u):
    return sum(u.get(k, 0) for k in COUNTERS if num(u.get(k)))


def split(o):
    cc = o.get("cache_creation") if isinstance(o, dict) else None
    return tuple(cc.get(k) if isinstance(cc, dict) and num(cc.get(k)) else None for k in SPLIT)


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
                    if not isinstance(u, dict):
                        continue
                    it = u.get("iterations")
                    c["rows_by_iterations_key_and_version"][("list" if isinstance(it, list) else "absent" if "iterations" not in u else "null") + " " + str(row.get("version"))[:8]] += 1
                    if isinstance(it, list) and len(it) > 1:
                        top = split(u)
                        msgs = [x for x in it if isinstance(x, dict) and x.get("type") == "message"]
                        if not msgs:
                            continue
                        s5 = sum(split(x)[0] or 0 for x in msgs)
                        s1 = sum(split(x)[1] or 0 for x in msgs)
                        comb = u.get("cache_creation_input_tokens")
                        c["multi_sum_of_message_splits_equals_combined"][str(num(comb) and s5 + s1 == comb)] += 1
                        tags = []
                        if top == (s5, s1):
                            tags.append("top==sum(message splits)")
                        if top == split(msgs[-1]):
                            tags.append("top==last message split")
                        if top == split(msgs[0]):
                            tags.append("top==first message split")
                        if top == split(it[-1]):
                            tags.append("top==last entry split")
                        c["multi_top_split_is"][" & ".join(tags) or "none of these"] += 1
                    if isinstance(msg.get("id"), str):
                        groups[msg["id"]].append(row)
            for mid, rows in groups.items():
                best = None
                for r in rows:
                    if best is None or total(r["message"]["usage"]) >= total(best["message"]["usage"]):
                        best = r
                blocks = [b for r in rows for b in (r["message"].get("content") or []) if isinstance(b, dict)] if all(isinstance(r["message"].get("content"), list) for r in rows) else []
                ok = [b for b in blocks if b.get("type") == "advisor_tool_result" and isinstance(b.get("content"), dict) and b["content"].get("type") in ("advisor_result", "advisor_redacted_result")]
                if ok and not isinstance(best["message"]["usage"].get("iterations"), list):
                    c["advisor_ok_without_iterations_version"][str(best.get("version"))] += 1
print(json.dumps({k: dict(v) for k, v in c.items()}, indent=1, sort_keys=True))
