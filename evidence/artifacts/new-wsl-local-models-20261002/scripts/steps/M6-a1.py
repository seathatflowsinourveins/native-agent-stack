#!/usr/bin/env python3
"""Part A1 of PREREGISTRATION-local-models.md: co-residency at a 64k context. Runs inside the measurement
distribution against the one Ollama server. For each arm, from a server with nothing loaded: load the embedder with
keep_alive -1, load the arm with num_ctx 64000 and keep_alive -1 on a long fixed prompt, then record what the server
and the GPU report. Prints one JSON object per arm and the raw `ollama ps` text; decides nothing."""
import hashlib
import json
import pathlib
import subprocess
import time
import urllib.request

BASE = "http://127.0.0.1:21434"
ARMS = ["qwen3.8:27b", "gpt-oss:20b"]
EMBEDDER = "qwen3-embedding:0.6b"
TEXT_URL = "https://www.gutenberg.org/cache/epub/1342/pg1342.txt"
PREFIX_CHARS = 236000
env = {"OLLAMA_HOST": "127.0.0.1:21434", "PATH": str(pathlib.Path.home() / ".local/share/mise/shims") + ":/usr/lib/wsl/lib:/usr/bin:/bin"}


def call(path, body=None, timeout=1200):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def run(*argv):
    return subprocess.run(list(argv), capture_output=True, text=True, env=env).stdout.strip()


def unload_all():
    for model in call("/api/ps").get("models", []):
        kind = "/api/embed" if "embed" in model["name"] else "/api/generate"
        body = {"model": model["name"], "keep_alive": 0}
        body["input" if kind == "/api/embed" else "prompt"] = ""
        try:
            call(kind, body, timeout=120)
        except Exception as error:  # an unload that errors is recorded by the next /api/ps
            print("unload error:", model["name"], type(error).__name__)
    for _ in range(30):
        if not call("/api/ps").get("models"):
            return
        time.sleep(2)


cache = pathlib.Path.home() / "measure-logs" / "pg1342.txt"
if not cache.is_file():
    cache.write_bytes(urllib.request.urlopen(TEXT_URL, timeout=120).read())
text = cache.read_text(encoding="utf-8", errors="replace")[:PREFIX_CHARS]
prompt = text + "\n\nIn one sentence: who wrote the text above?"
print(json.dumps({"prompt_chars": len(prompt), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "source": TEXT_URL, "server_version": call("/api/version").get("version"),
                  "gpu_before_any_load": run("nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader")}))
print(run("ollama", "list"))
for arm in ARMS:
    unload_all()
    record = {"arm": arm, "gpu_empty_server": run("nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader")}
    started = time.time()
    try:
        call("/api/embed", {"model": EMBEDDER, "input": "co-residency probe", "keep_alive": -1})
        record["embedder_loaded_s"] = round(time.time() - started, 1)
        started = time.time()
        answer = call("/api/generate", {"model": arm, "prompt": prompt, "stream": False, "keep_alive": -1,
                                        "options": {"num_ctx": 64000, "num_predict": 64}})
        record.update(generate_s=round(time.time() - started, 1), prompt_eval_count=answer.get("prompt_eval_count"),
                      eval_count=answer.get("eval_count"),
                      prompt_tokens_per_s=round(answer["prompt_eval_count"] / (answer["prompt_eval_duration"] / 1e9), 1)
                      if answer.get("prompt_eval_duration") else None,
                      eval_tokens_per_s=round(answer["eval_count"] / (answer["eval_duration"] / 1e9), 1)
                      if answer.get("eval_duration") else None,
                      done_reason=answer.get("done_reason"))
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    models = call("/api/ps").get("models", [])
    record["loaded"] = [{"name": m["name"], "size": m.get("size"), "size_vram": m.get("size_vram"),
                         "gpu_share": round(m["size_vram"] / m["size"], 4) if m.get("size") else None,
                         "context_length": m.get("context_length")} for m in models]
    record["gpu_after"] = run("nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader")
    names = {m["name"] for m in models}
    record["both_resident_fully_on_gpu"] = bool(
        arm in names and any("qwen3-embedding" in n for n in names) and all(m.get("size") == m.get("size_vram") for m in models))
    print(json.dumps(record))
    print(run("ollama", "ps"))
unload_all()
print(json.dumps({"after_unload": run("nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader")}))
