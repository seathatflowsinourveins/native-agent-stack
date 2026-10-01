#!/usr/bin/env python3
"""Cross-family (GPT-6.1 Sol) half of the blind clean-install selection wf_c2377ebb-65c.

Runs the frozen judge prompt over the 21 frozen packets with 11 judges in 3 groups, then the frozen critic prompt once
per group, each as an independent `codex exec` process (read-only sandbox, live web search, ephemeral, schema-bound
output). Every attempt, failure and usage figure is kept. Usage: run_xfam.py <xfam dir> <frozen evidence dir>
"""
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

X, D = sys.argv[1], sys.argv[2]
PRE = os.path.join(X, "prereg")
OUT = os.path.join(X, "out")
WORK = os.path.join(X, "work")
MODEL, EFFORT = "gpt-6.1-sol", "max"
TIMEOUT_S = 90 * 60
SLOTS = 4
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "run.log"), "a", buffering=1)
LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    with LOCK:
        LOG.write(f"{now()} {msg}\n")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


criteria = read(os.path.join(D, "criteria.txt")).rstrip("\n")
judge_prompt = read(os.path.join(D, "judge-prompt.txt"))
critic_prompt = read(os.path.join(D, "critic-prompt.txt"))
adapter = read(os.path.join(PRE, "adapter.txt"))
assignment = json.loads(read(os.path.join(PRE, "assignment.json")))


def packet_file(layer_id):
    return layer_id.replace(":", "_") + ".json"


def packet_lines(layers):
    return "\n".join(
        f"- {os.path.join(X, 'input', 'packets', packet_file(l))} "
        f"(facts: {os.path.join(X, 'input', 'facts', packet_file(l))})" for l in layers)


def candidate_keys(layer_id):
    return [c["key"] for c in json.loads(read(os.path.join(X, "input", "packets", packet_file(layer_id))))["candidates"]]


def run_codex(run_id, prompt, schema, expect_layers):
    """One independent codex exec; retried once. Returns the parsed object or None, and the attempt records."""
    attempts = []
    for attempt in (1, 2):
        wd = os.path.join(WORK, f"{run_id}-a{attempt}")
        os.makedirs(wd, exist_ok=True)
        base = os.path.join(OUT, f"{run_id}.a{attempt}")
        with open(base + ".prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        cmd = ["codex", "exec", "-m", MODEL, "-c", f'model_reasoning_effort="{EFFORT}"', "-c", 'web_search="live"',
               "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "--json",
               "--output-schema", os.path.join(PRE, schema), "-o", base + ".last.json", "-C", wd, prompt]
        start = time.time()
        log(f"start {run_id} attempt {attempt}")
        with open(base + ".events.jsonl", "w") as ev, open(base + ".stderr.txt", "w") as er:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=ev, stderr=er)
            try:
                code = proc.wait(timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = "timeout"
        rec = {"run_id": run_id, "attempt": attempt, "exit": code, "seconds": round(time.time() - start, 1),
               "usage": usage_of(base + ".events.jsonl"), "problems": []}
        obj = None
        try:
            obj = json.loads(read(base + ".last.json"))
        except Exception as e:  # noqa: BLE001 - recorded, not hidden
            rec["problems"].append(f"no parseable output: {type(e).__name__}")
        if obj is not None:
            got = [l.get("layer_id") for l in obj.get("layers", [])]
            missing = [l for l in expect_layers if l not in got]
            if missing:
                rec["problems"].append(f"missing layers: {missing}")
        log(f"end {run_id} attempt {attempt} exit={code} problems={rec['problems']}")
        attempts.append(rec)
        if code == 0 and obj is not None and not rec["problems"]:
            return obj, attempts
    return obj, attempts


def usage_of(events_path):
    total = {}
    try:
        for line in open(events_path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "turn.completed":
                for k, v in (e.get("usage") or {}).items():
                    total[k] = total.get(k, 0) + (v or 0)
    except OSError:
        pass
    return total


def key_coverage(obj, layer_id):
    """The frozen prompt's rule: every candidate key appears exactly once. Violations are recorded, never fixed."""
    entry = next((l for l in obj.get("layers", []) if l.get("layer_id") == layer_id), None)
    if entry is None:
        return ["layer missing"]
    seen = [s["key"] for s in entry.get("selection", [])] + [s["key"] for s in entry.get("not_selected", [])] + \
           [s["key"] for s in entry.get("excluded", [])]
    keys = candidate_keys(layer_id)
    out = []
    for k in keys:
        if seen.count(k) != 1:
            out.append(f"{k} appears {seen.count(k)} times")
    extra = sorted(set(seen) - set(keys))
    if extra:
        out.append(f"unknown keys {extra}")
    return out


results, records = {}, []
judges = {j["judge"]: j for j in assignment["judges"]}
group_done = {g["group"]: threading.Event() for g in assignment["groups"]}


def judge(jid):
    layers = judges[jid]["packets"]
    prompt = adapter + judge_prompt.replace("__CRITERIA__", criteria).replace("__PACKETS__", packet_lines(layers))
    obj, att = run_codex(jid, prompt, "judge-schema.json", layers)
    cov = {l: key_coverage(obj, l) for l in layers} if obj else {}
    with LOCK:
        results[jid] = obj
        records.extend(att)
        records.append({"run_id": jid, "key_coverage": cov})
    return jid


def critic(group):
    layers = [l for jid in group["judges"] for l in judges[jid]["packets"]]
    judged = {"layers": [l for jid in group["judges"] if results.get(jid) for l in results[jid]["layers"]]}
    prompt = adapter + critic_prompt.replace("__CRITERIA__", criteria).replace(
        "__JUDGMENTS__", json.dumps(judged, indent=1)).replace("__PACKETS__", packet_lines(layers))
    cid = "C-" + group["group"]
    obj, att = run_codex(cid, prompt, "critic-schema.json", layers)
    with LOCK:
        results[cid] = obj
        records.extend(att)
    return cid


log(f"run start model={MODEL} effort={EFFORT} slots={SLOTS}")
with ThreadPoolExecutor(SLOTS) as pool:
    futures = {jid: pool.submit(judge, jid) for jid in judges}
    critic_futures = []
    pending = list(assignment["groups"])
    while pending:
        for g in list(pending):
            if all(futures[j].done() for j in g["judges"]):
                critic_futures.append(pool.submit(critic, g))
                pending.remove(g)
        time.sleep(10)
    for f in critic_futures:
        f.result()

summary = {"finished_at": now(), "model": MODEL, "effort": EFFORT, "records": records,
           "outputs": {k: (v is not None) for k, v in results.items()}}
with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(results, f, indent=1)
with open(os.path.join(OUT, "summary.json"), "w") as f:
    json.dump(summary, f, indent=1)
log("run end")
