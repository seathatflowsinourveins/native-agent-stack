#!/usr/bin/env python3
"""A1 of the extension (amendments 2, 3 and 3a of PREREGISTRATION-local-models.md) for arms served by the measurement
Ollama server: co-residency at a 64,000-token context in the order of use. For each arm named on the command line,
from a server with nothing loaded: load the arm (context 64,000 in the request, keep_alive -1, a short prompt), call
the embedder (its own context of 8,192 in the request, keep_alive -1), then call the arm with the fixed long prompt of
A1 (64 output tokens). Records what the server and the GPU report after each call, prints one JSON object per arm,
and unloads everything at the end. Decides nothing."""
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:21434"
ARMS = sys.argv[1:]
EMBEDDER, EMBED_CTX, CTX = "qwen3-embedding:0.6b", 8192, 64000
TEXT_URL = "https://www.gutenberg.org/cache/epub/1342/pg1342.txt"
PREFIX_CHARS = 236000
ENV = {"OLLAMA_HOST": "127.0.0.1:21434",
       "PATH": str(pathlib.Path.home() / ".local/share/mise/shims") + ":/usr/lib/wsl/lib:/usr/bin:/bin"}


def call(path, body=None, timeout=1500):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def run(*argv):
    return subprocess.run(list(argv), capture_output=True, text=True, env=ENV).stdout.strip()


def gpu():
    return run("nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader")


def resident():
    return [{"name": m["name"], "size": m.get("size"), "size_vram": m.get("size_vram"),
             "gpu_share": round(m["size_vram"] / m["size"], 4) if m.get("size") else None,
             "context_length": m.get("context_length")} for m in call("/api/ps").get("models", [])]


def unload_all():
    for model in call("/api/ps").get("models", []):
        embed = "embed" in model["name"]
        body = {"model": model["name"], "keep_alive": 0}
        body["input" if embed else "prompt"] = ""
        try:
            call("/api/embed" if embed else "/api/generate", body, timeout=120)
        except Exception as error:  # an unload that errors shows in the next /api/ps
            print("unload error:", model["name"], type(error).__name__)
    for _ in range(30):
        if not call("/api/ps").get("models"):
            return True
        time.sleep(2)
    return False


cache = pathlib.Path.home() / "measure-logs" / "pg1342.txt"
if not cache.is_file():
    cache.write_bytes(urllib.request.urlopen(TEXT_URL, timeout=120).read())
prompt = cache.read_text(encoding="utf-8", errors="replace")[:PREFIX_CHARS] + "\n\nIn one sentence: who wrote the text above?"
print(json.dumps({"prompt_chars": len(prompt), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "server_version": call("/api/version").get("version"), "gpu_before_any_load": gpu(),
                  "resident_before_any_load": resident(), "context": CTX, "embedder_context": EMBED_CTX}))
print(run("ollama", "list"))
for arm in ARMS:
    record = {"arm": arm, "unloaded_before": unload_all(), "gpu_empty_server": gpu()}
    try:
        started = time.time()
        first = call("/api/generate", {"model": arm, "prompt": "Reply with the word ready.", "stream": False, "keep_alive": -1,
                                       "options": {"num_ctx": CTX, "num_predict": 16}})
        record.update(arm_loaded_s=round(time.time() - started, 1), load_duration_s=round(first.get("load_duration", 0) / 1e9, 1),
                      after_arm=resident(), gpu_after_arm=gpu())
        started = time.time()
        call("/api/embed", {"model": EMBEDDER, "input": "co-residency probe", "keep_alive": -1, "options": {"num_ctx": EMBED_CTX}})
        record.update(embedder_loaded_s=round(time.time() - started, 1), after_embedder=resident(), gpu_after_embedder=gpu())
        started = time.time()
        answer = call("/api/generate", {"model": arm, "prompt": prompt, "stream": False, "keep_alive": -1,
                                        "options": {"num_ctx": CTX, "num_predict": 64}})
        record.update(long_prompt_s=round(time.time() - started, 1), prompt_eval_count=answer.get("prompt_eval_count"),
                      eval_count=answer.get("eval_count"), done_reason=answer.get("done_reason"),
                      prompt_tokens_per_s=round(answer["prompt_eval_count"] / (answer["prompt_eval_duration"] / 1e9), 1)
                      if answer.get("prompt_eval_duration") else None,
                      eval_tokens_per_s=round(answer["eval_count"] / (answer["eval_duration"] / 1e9), 1)
                      if answer.get("eval_duration") else None)
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    models = resident()
    record["after_long_prompt"] = models
    record["gpu_after_long_prompt"] = gpu()
    names = {m["name"].split(":")[0] for m in models}
    record["both_resident_fully_on_gpu"] = bool(
        arm.split(":")[0] in names and EMBEDDER.split(":")[0] in names and all(m.get("size") == m.get("size_vram") for m in models))
    print(json.dumps(record))
    print(run("ollama", "ps"))
print(json.dumps({"unloaded_at_end": unload_all(), "gpu_after_unload": gpu()}))
