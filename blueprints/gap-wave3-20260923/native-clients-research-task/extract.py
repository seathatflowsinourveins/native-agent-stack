#!/usr/bin/env python3
"""Extract answer text, usage and a mechanical TIMESTAMP check from raw
claude -p (--output-format json, a JSON array of stream events) and
codex exec --json (JSONL of events) outputs for the frozen research task.
Writes a summary JSON (no session UUIDs) and one stripped judge-packet .txt
per run under judge-packets/.
"""
import json, os, re, sys, hashlib

RAW = os.path.expanduser("~/codex-ecosystem/state/gap-wave3-20260923/native-clients/raw")
OUTDIR = os.path.dirname(os.path.abspath(__file__))
PACKETS = os.path.join(OUTDIR, "judge-packets")
os.makedirs(PACKETS, exist_ok=True)

RUNS = [
    ("run1_codex", "codex"),
    ("run2_claude", "claude"),
    ("run3_codex", "codex"),
    ("run4_codex", "codex"),
    ("run5_claude", "claude"),
    ("run6_claude", "claude"),
]

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def load_claude(path):
    raw = open(path, "rb").read()
    events = json.loads(raw.decode("utf-8"))
    last = events[-1]
    answer = last.get("result", "")
    usage = last.get("usage", {})
    cost = last.get("total_cost_usd")
    rate_limits = [e["rate_limit_info"] for e in events if e.get("type") == "rate_limit_event"]
    return {
        "answer": answer,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "total_cost_usd": cost,
        "rate_limit_events": rate_limits,
        "is_error": last.get("is_error"),
        "raw_sha256": sha256_bytes(raw),
        "raw_bytes": len(raw),
    }

def load_codex(path):
    raw = open(path, "rb").read()
    lines = [l for l in raw.decode("utf-8").splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    answer = None
    usage = {}
    for ev in events:
        if ev.get("type") == "item.completed" and ev.get("item", {}).get("type") == "agent_message":
            answer = ev["item"]["text"]
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage", {})
    return {
        "answer": answer or "",
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
        "raw_sha256": sha256_bytes(raw),
        "raw_bytes": len(raw),
    }

TS_RE = re.compile(r"TIMESTAMP:\s*(\S+)")

summary = {}
for label, arm in RUNS:
    path = os.path.join(RAW, f"{label}.json")
    data = load_claude(path) if arm == "claude" else load_codex(path)
    m = TS_RE.search(data["answer"])
    data["timestamp_line_present"] = bool(m)
    data["timestamp_value"] = m.group(1) if m else None
    data["arm"] = arm
    data["label"] = label
    summary[label] = data
    # stripped judge packet: prompt-agnostic answer text only, TIMESTAMP line removed
    stripped = TS_RE.sub("", data["answer"]).strip()
    with open(os.path.join(PACKETS, f"{label}.txt"), "w") as f:
        f.write(stripped)

with open(os.path.join(OUTDIR, "extract-summary.json"), "w") as f:
    json.dump(summary, f, indent=2)

print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("answer",)} for k, v in summary.items()}, indent=2))
