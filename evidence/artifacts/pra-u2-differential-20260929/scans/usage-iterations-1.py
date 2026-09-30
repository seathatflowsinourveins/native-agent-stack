"""Count-only scan of assistant-row usage structure in Claude Code transcripts (B9 / U2 corrections).

Prints key names, enum value classes (model names, speed, service_tier, inference_geo, iteration types) and counts only:
never ids, paths, text or command content. Usage: python3 scan_iterations.py <root> [<root> ...]
"""
import json
import os
import sys
from collections import Counter, defaultdict

COUNTERS = ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"]
roots = sys.argv[1:]
files = 0
rows_assistant = 0
rows_with_usage = 0
rows_with_iterations = 0
files_with_iterations = 0
iteration_types = Counter()
iteration_keys = defaultdict(Counter)
iteration_models = defaultdict(Counter)
iteration_cache_creation_keys = defaultdict(Counter)
usage_keys = Counter()
usage_enum = defaultdict(Counter)
cache_creation_keys = Counter()
invariant = Counter()
advisor_in_top = Counter()
versions_with_iterations = Counter()
iterations_nonlist = 0
iteration_not_object = 0
iteration_counter_types = Counter()
split_vs_combined = Counter()
stream = defaultdict(lambda: {"rows": 0, "with_it": 0, "sigs": set()})
content_block_names = Counter()
msg_with_advisor_block = 0
msg_with_advisor_block_no_iterations = 0
iteration_lengths = Counter()
model_of_rows_with_iterations = Counter()
top_model_vs_message_iteration_model = Counter()


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


for root in roots:
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            files += 1
            path = os.path.join(dirpath, name)
            file_has = False
            local_stream = defaultdict(lambda: {"rows": 0, "with_it": 0, "sigs": set()})
            try:
                fh = open(path, "rb")
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
                    if not isinstance(row, dict) or row.get("type") != "assistant":
                        continue
                    msg = row.get("message")
                    if not isinstance(msg, dict):
                        continue
                    rows_assistant += 1
                    content = msg.get("content")
                    has_adv_block = False
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") in ("server_tool_use", "advisor_tool_result", "server_tool_result"):
                                nm = b.get("name") if b.get("type") == "server_tool_use" else b.get("type")
                                content_block_names[str(b.get("type")) + ":" + (str(nm) if isinstance(nm, str) and len(nm) < 40 else "(other)")] += 1
                                if (b.get("type") == "server_tool_use" and b.get("name") == "advisor") or b.get("type") == "advisor_tool_result":
                                    has_adv_block = True
                    u = msg.get("usage")
                    if not isinstance(u, dict):
                        continue
                    rows_with_usage += 1
                    for k in u:
                        usage_keys[k] += 1
                    for k in ("speed", "service_tier", "inference_geo"):
                        if k in u:
                            v = u[k]
                            usage_enum[k][v if isinstance(v, str) and len(v) < 30 else ("(null)" if v is None else "(other-type)")] += 1
                        else:
                            usage_enum[k]["(absent)"] += 1
                    cc = u.get("cache_creation")
                    if isinstance(cc, dict):
                        for k in cc:
                            cache_creation_keys[k] += 1
                        s = sum(cc.get(k, 0) for k in ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens") if num(cc.get(k)))
                        comb = u.get("cache_creation_input_tokens")
                        split_vs_combined["equal" if num(comb) and s == comb else "differ" if num(comb) else "no_combined"] += 1
                    else:
                        split_vs_combined["no_split_object"] += 1
                    mid = msg.get("id")
                    it = u.get("iterations")
                    key = mid if isinstance(mid, str) else None
                    if has_adv_block:
                        msg_with_advisor_block += 1
                        if not isinstance(it, list) or not it:
                            msg_with_advisor_block_no_iterations += 1
                    if key is not None:
                        s = local_stream[key]
                        s["rows"] += 1
                    if it is None:
                        continue
                    if not isinstance(it, list):
                        iterations_nonlist += 1
                        continue
                    rows_with_iterations += 1
                    iteration_lengths[len(it)] += 1
                    file_has = True
                    model_of_rows_with_iterations[msg.get("model") if isinstance(msg.get("model"), str) else "(none)"] += 1
                    versions_with_iterations[row.get("version") if isinstance(row.get("version"), str) else "(none)"] += 1
                    sums = defaultdict(lambda: Counter())
                    for x in it:
                        if not isinstance(x, dict):
                            iteration_not_object += 1
                            continue
                        t = x.get("type") if isinstance(x.get("type"), str) else "(none)"
                        iteration_types[t] += 1
                        for k in x:
                            iteration_keys[t][k] += 1
                        m = x.get("model")
                        iteration_models[t][m if isinstance(m, str) and len(m) < 60 else ("(absent)" if m is None else "(other)")] += 1
                        if t == "message" and isinstance(m, str):
                            top_model_vs_message_iteration_model["same" if m == msg.get("model") else "differ"] += 1
                        icc = x.get("cache_creation")
                        if isinstance(icc, dict):
                            for k in icc:
                                iteration_cache_creation_keys[t][k] += 1
                        for k in COUNTERS:
                            v = x.get(k)
                            iteration_counter_types[t + ":" + k + ":" + ("num" if num(v) else "absent" if v is None else "other")] += 1
                            if num(v):
                                sums[t][k] += v
                    # invariant: top-level counters == sum of 'message' iterations
                    ok = all(num(u.get(k)) and u.get(k) == sums["message"][k] for k in COUNTERS)
                    invariant["top==sum(message)" if ok else "top!=sum(message)"] += 1
                    if "advisor_message" in sums:
                        both = all(num(u.get(k)) and u.get(k) == sums["message"][k] + sums["advisor_message"][k] for k in COUNTERS)
                        advisor_in_top["top==message+advisor" if both else "top!=message+advisor"] += 1
                    if key is not None:
                        s = local_stream[key]
                        s["with_it"] += 1
                        s["sigs"].add(json.dumps(it, sort_keys=True))
            if file_has:
                files_with_iterations += 1
            for k, s in local_stream.items():
                g = stream[(files, k)]
                g.update(s)

# streaming: per message id (within a file) how iterations appear across repeated rows
stream_shapes = Counter()
for (_, _), s in stream.items():
    if s["with_it"] == 0:
        continue
    stream_shapes["rows=%s with_it=%s distinct_iterations=%s" % ("1" if s["rows"] == 1 else ">1", "all" if s["with_it"] == s["rows"] else "some", len(s["sigs"]))] += 1

out = {
    "files": files, "assistant_rows": rows_assistant, "rows_with_usage": rows_with_usage,
    "rows_with_iterations_list": rows_with_iterations, "files_with_iterations": files_with_iterations,
    "iterations_not_a_list": iterations_nonlist, "iteration_entries_not_objects": iteration_not_object,
    "iteration_lengths": dict(iteration_lengths), "iteration_types": dict(iteration_types),
    "iteration_keys": {t: dict(c) for t, c in iteration_keys.items()},
    "iteration_models": {t: dict(c) for t, c in iteration_models.items()},
    "iteration_cache_creation_keys": {t: dict(c) for t, c in iteration_cache_creation_keys.items()},
    "iteration_counter_types": dict(iteration_counter_types),
    "invariant_top_equals_sum_of_message_iterations": dict(invariant),
    "top_equals_message_plus_advisor": dict(advisor_in_top),
    "usage_keys": dict(usage_keys), "usage_enum": {k: dict(c) for k, c in usage_enum.items()},
    "cache_creation_keys": dict(cache_creation_keys), "cache_creation_split_vs_combined": dict(split_vs_combined),
    "versions_with_iterations": dict(versions_with_iterations),
    "model_of_rows_with_iterations": dict(model_of_rows_with_iterations),
    "message_iteration_model_vs_row_model": dict(top_model_vs_message_iteration_model),
    "server_tool_blocks": dict(content_block_names),
    "rows_with_advisor_block": msg_with_advisor_block, "rows_with_advisor_block_without_iterations": msg_with_advisor_block_no_iterations,
    "stream_shapes_for_ids_with_iterations": dict(stream_shapes),
}
print(json.dumps(out, indent=1, sort_keys=True))
