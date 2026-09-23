#!/usr/bin/env python3
"""Index one frozen corpus with SocratiCode 1.14.0 against the disposable Qdrant and run
a query list through codebase_search in one persistent MCP stdio session.

Usage: socraticode_eval.py PROJECT_DIR QUERIES_JSON OUT_RAW_JSON [--limit 10]
QUERIES_JSON: list of {"id","query"} or a doc with "queries".
Writes the raw MCP responses plus parsed hits (file, start, end, score) per query.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mcp_client  # noqa: E402

CACHE = Path.home() / ".cache/gap-wave2-20260923/agents-models-workers"
QDRANT_URL = "http://127.0.0.1:27333"
HIT = re.compile(r"^--- (?P<file>.+?) \(lines (?P<start>\d+)-(?P<end>\d+)\) \[[^\]]*\] score: (?P<score>[0-9.]+) ---$", re.M)


def build_env():
    env = os.environ.copy()
    home = CACHE / "sc-home"
    home.mkdir(parents=True, exist_ok=True)
    env.update({
        "HOME": str(home),
        "SOCRATICODE_GLOBAL_CONFIG_DIR": str(home / ".socraticode"),
        "QDRANT_MODE": "external",
        "QDRANT_URL": QDRANT_URL,
        "QDRANT_COLLECTION_PREFIX": "g2amw_",
        # Same embedding profile as the adopted agent-lab SocratiCode registration
        # (.codex/config.toml); read-only /v1/embeddings calls to the live vLLM endpoint.
        "EMBEDDING_PROVIDER": "lmstudio",
        "LMSTUDIO_URL": "http://127.0.0.1:8231/v1",
        "EMBEDDING_MODEL": "nvidia/Nemotron-3-Embed-1B-BF16",
        "EMBEDDING_DIMENSIONS": "2048",
        "EMBEDDING_CONTEXT_LENGTH": "4096",
        "EMBEDDING_QUERY_PREFIX": "query: ",
        "EMBEDDING_DOCUMENT_PREFIX": "passage: ",
        "EMBEDDING_DOCUMENT_INCLUDE_PATH": "true",
        "RESPECT_GITIGNORE": "true",
        "INCLUDE_DOT_FILES": "false",
        "SOCRATICODE_WATCHER": "off",
        "SOCRATICODE_AUTO_RESUME": "off",
        "SEARCH_DEFAULT_LIMIT": "10",
    })
    return env


def text_of(resp):
    try:
        return "\n".join(c.get("text", "") for c in resp["result"]["content"])
    except (KeyError, TypeError):
        return json.dumps(resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("queries")
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    project = str(Path(a.project).resolve())
    q = json.load(open(a.queries))
    queries = q["queries"] if isinstance(q, dict) else q
    proc = mcp_client.McpProc([mcp_client.NODE, mcp_client.SC], build_env(), project)
    proc.initialize()
    raw = {"project": project, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
    t0 = time.time()
    r = proc.call_tool("codebase_index", {"projectPath": project}, timeout=120)
    raw["steps"].append({"step": "codebase_index", "text": text_of(r)})
    status_text = ""
    while time.time() - t0 < 900:
        time.sleep(3)
        status_text = text_of(proc.call_tool("codebase_status", {"projectPath": project}, timeout=60))
        if "in progress" not in status_text and "INCOMPLETE" not in status_text and "Indexed chunks: 0" not in status_text:
            break
    raw["index_seconds"] = round(time.time() - t0, 1)
    raw["final_status"] = status_text
    results = []
    for item in queries:
        s = time.time()
        resp = proc.call_tool("codebase_search", {"projectPath": project, "query": item["query"],
                                                  "limit": a.limit, "minScore": 0}, timeout=120)
        txt = text_of(resp)
        hits = [{"file": m["file"], "start": int(m["start"]), "end": int(m["end"]), "score": float(m["score"])}
                for m in HIT.finditer(txt)]
        results.append({"id": item["id"], "query": item["query"], "latency_ms": round((time.time() - s) * 1000),
                        "hits": hits, "raw_text": txt})
    raw["results"] = results
    raw["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    proc.terminate_clean()
    Path(a.out).write_text(json.dumps(raw, indent=1) + "\n")
    print(json.dumps({"index_seconds": raw["index_seconds"], "queries": len(results),
                      "status_head": status_text.splitlines()[:6]}))


if __name__ == "__main__":
    main()
