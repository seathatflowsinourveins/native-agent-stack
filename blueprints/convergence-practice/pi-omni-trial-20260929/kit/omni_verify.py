#!/usr/bin/env python3
"""Read-back and probe of the two loopback OmniRoute gateways before a pi run (local integration script, not upstream acceptance).

    omni_verify.py [--model gpt-6.1-sol] [--skip-cache] [--json OUT]

Prints value-free facts only: unit properties, the CODEX_CLIENT_VERSION of the running process, the compression settings
from GET /api/settings/compression (never /api/settings or a provider route: those return decrypted credentials), the
model listing, the probe trio (control, target, made-up id) on 20128, the 20129 chain, and the prompt-cache share of an
append-only conversation on both routes. It writes nothing to a gateway and spends a few thousand cached tokens.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ENTRY, SHARED = "http://127.0.0.1:20129", "http://127.0.0.1:20128"


def get(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def post(base, path, body, headers=None, timeout=180):
    cid = "verify-" + uuid.uuid4().hex[:8]
    h = {"content-type": "application/json", "authorization": "Bearer local-loopback", "X-Correlation-Id": cid, "X-OmniRoute-Session-Id": cid}
    h.update(headers or {})
    request = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers=h)
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except Exception as error:
        return {"exception": repr(error)[:100]}
    out = {"http": status, "s": round(time.time() - started, 1)}
    try:
        data = json.loads(raw)
    except ValueError:
        out["body_head"] = raw[:100].decode("utf-8", "replace")
        return out
    if status == 200:
        out["served"] = data.get("model") or (data.get("response") or {}).get("model")
        usage = data.get("usage") or {}
        details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
        out["in"], out["cached"] = usage.get("input_tokens") or usage.get("prompt_tokens"), details.get("cached_tokens")
    else:
        error = data.get("error") if isinstance(data.get("error"), dict) else data
        out["error"] = str(error.get("message"))[:150]
    return out


def systemd(unit):
    props = subprocess.run(["systemctl", "--user", "show", unit, "-p", "ActiveState,MainPID,NRestarts,ActiveEnterTimestamp", "--no-pager"],
                           capture_output=True, text=True).stdout.strip().replace("\n", " | ")
    pid = re.search(r"MainPID=(\d+)", props)
    env = []
    if pid and pid.group(1) != "0":
        try:
            env = [l for l in open(f"/proc/{pid.group(1)}/environ", "rb").read().decode(errors="replace").split("\0") if l.startswith("CODEX_CLIENT_VERSION=")]
        except OSError:
            pass
    dropins = sorted(p.name for p in (pathlib.Path.home() / ".config/systemd/user" / f"{unit}.d").glob("*.conf")) if (pathlib.Path.home() / ".config/systemd/user" / f"{unit}.d").exists() else []
    return {"props": props, "codex_client_version": env, "drop_ins": dropins}


def compression(base):
    data = get(base + "/api/settings/compression")
    engines = data.get("engines") or {}
    on = sorted(k for k, v in engines.items() if (v.get("enabled") if isinstance(v, dict) else v) is True)
    levels = {k: v.get("level") for k, v in engines.items() if isinstance(v, dict) and v.get("level")}
    pipeline = [step.get("engine") for step in (data.get("stackedPipeline") or []) if isinstance(step, dict)]
    keys = ("enabled", "defaultMode", "autoTriggerMode", "autoTriggerTokens", "cacheMinutes", "preserveSystemPrompt", "preserveSystemPromptMode",
            "compressionComboId", "activeComboId", "enginesExplicit", "outputStyles", "liveZone", "sessionDedup", "lite", "headroom", "exclusions")
    out = {k: data.get(k) for k in keys}
    out["contextBudget_mode"] = (data.get("contextBudget") or {}).get("mode")
    # stacked_pipeline is the configured stackedPipeline key (used by stacked-mode requests such as auto-trigger); a headerless request's plan
    # derives from the engines map when enginesExplicit is true, so the plan is evidenced by tokens.compressed in the call logs, not by this key.
    return out | {"engines_on": on, "engine_levels": levels, "stacked_pipeline": pipeline}


def conversation(static, n):
    items = [{"role": "user", "content": static}]
    for i in range(1, n + 1):
        items.append({"role": "user", "content": f"Question {i}: reply with exactly: ok-{i}"})
        if i < n:
            items.append({"role": "assistant", "content": [{"type": "output_text", "text": f"ok-{i}"}]})
    return items


def cache_share(base, model, turns=4):
    key = "verify-cache-" + uuid.uuid4().hex[:8]
    static = f"Run {key}\n" + "\n".join(f"Rule {k:03d}: keep every answer short and exact, never add commentary, and never restate rule {k:03d}." for k in range(1, 261))
    rows = []
    for n in range(1, turns + 1):
        rows.append(post(base, "/v1/responses", {"model": model, "input": conversation(static, n), "stream": False, "prompt_cache_key": key}))
        time.sleep(3.0)  # the provider's cache write lands asynchronously; 1.2 s gave intermittent turn-2 misses
    later = [r for r in rows[1:] if r.get("in") and r.get("cached") is not None]
    return {"turns": rows, "cached_share_turns_2_plus": round(sum(r["cached"] for r in later) / max(sum(r["in"] for r in later), 1), 3) if later else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument("--json", type=pathlib.Path)
    a = parser.parse_args()
    report = {"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    report["units"] = {u: systemd(u) for u in ("omniroute.service", "omniroute-fw.service")}
    report["compression"] = {"20128": compression(SHARED), "20129": compression(ENTRY)}
    ids = [m["id"] for m in get(SHARED + "/v1/models")["data"]]
    report["listed_on_20128"] = [i for i in ids if a.model in i]
    prompt = {"messages": [{"role": "user", "content": "Reply with exactly: ok"}]}
    report["trio_20128"] = {
        "control cx/gpt-6-sol": post(SHARED, "/v1/chat/completions", {"model": "cx/gpt-6-sol", **prompt}),
        "control as a Codex caller (Version 0.157.1)": post(SHARED, "/v1/chat/completions", {"model": "cx/gpt-6-sol", **prompt},
                                                            {"Version": "0.157.1", "User-Agent": "codex_exec/0.157.1 (Linux; x86_64)"}),
        f"target cx/{a.model}": post(SHARED, "/v1/chat/completions", {"model": f"cx/{a.model}", **prompt}),
        "negative made-up id": post(SHARED, "/v1/chat/completions", {"model": f"cx/{a.model}-zzz-nonexistent", **prompt}),
    }
    report["chain_20129"] = {m: post(ENTRY, "/v1/responses", {"model": m, "input": "Reply with exactly: ok", "stream": False})
                             for m in (f"sharedgw/{a.model}", "sharedgw/gpt-6-sol")}
    if not a.skip_cache:
        report["cache"] = {f"20129 sharedgw/{a.model}": cache_share(ENTRY, f"sharedgw/{a.model}"), f"20128 cx/{a.model}": cache_share(SHARED, f"cx/{a.model}")}
    pool = get(SHARED + "/api/usage/provider-limits")["caches"].values()
    report["pool_remaining_points"] = sorted(((v.get("quotas") or {}).get("session") or {}).get("remaining") for v in pool)
    print(json.dumps(report, indent=1))
    if a.json:
        a.json.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
