"""Round 4 shared helpers: loopback vLLM provider metrics (agent-sdks gap wave, 2026-09-23).

The provider is a vLLM 0.25.0 server this unit started on 127.0.0.1:28431. Its Prometheus
/metrics counters are the provider-side consumption channel: prompt and generation token
totals, running/waiting request gauges and finished-request counts by reason.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

BASE = "http://127.0.0.1:28431"
KEYS = ("vllm:prompt_tokens_total", "vllm:generation_tokens_total", "vllm:num_requests_running",
        "vllm:num_requests_waiting")
LINE = re.compile(r'^(vllm:[a-z_]+)(\{[^}]*\})?\s+([0-9.eE+-]+)$')


def metrics() -> dict:
    text = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    out: dict = {"at": time.time()}
    finished: dict = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        name, labels, value = m.group(1), m.group(2) or "", float(m.group(3))
        if name in KEYS:
            out[name] = out.get(name, 0.0) + value
        elif name == "vllm:request_success_total":
            reason = re.search(r'finished_reason="([^"]+)"', labels)
            key = reason.group(1) if reason else "?"
            finished[key] = finished.get(key, 0.0) + value
    out["vllm:request_success_total_by_reason"] = finished
    return out


def delta(a: dict, b: dict) -> dict:
    d = {k: b.get(k, 0.0) - a.get(k, 0.0) for k in ("vllm:prompt_tokens_total", "vllm:generation_tokens_total")}
    ra, rb = a.get("vllm:request_success_total_by_reason", {}), b.get("vllm:request_success_total_by_reason", {})
    d["finished_by_reason"] = {k: rb.get(k, 0.0) - ra.get(k, 0.0) for k in sorted(set(ra) | set(rb))
                               if rb.get(k, 0.0) != ra.get(k, 0.0)}
    d["seconds"] = round(b["at"] - a["at"], 3)
    return d


def wait_idle(timeout: float = 60) -> dict:
    """Wait until no request runs or waits, so a sample belongs to one client."""
    end = time.time() + timeout
    m = metrics()
    while time.time() < end and (m.get("vllm:num_requests_running", 0) or m.get("vllm:num_requests_waiting", 0)):
        time.sleep(0.5)
        m = metrics()
    return m


def control(max_tokens: int = 120) -> dict:
    """Detector: one uninterrupted request; its reported usage must appear in the counters."""
    before = wait_idle()
    body = json.dumps({"model": "qwen3-4b", "max_tokens": max_tokens, "temperature": 0,
                       "messages": [{"role": "user", "content": "Count from 1 to 200 separated by spaces."}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", body, {"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    time.sleep(1.5)
    after = metrics()
    usage = resp.get("usage") or {}
    d = delta(before, after)
    return {"usage": usage, "provider_delta": d,
            "generation_counter_matches_usage": d["vllm:generation_tokens_total"] == usage.get("completion_tokens"),
            "prompt_counter_matches_usage": d["vllm:prompt_tokens_total"] == usage.get("prompt_tokens")}
