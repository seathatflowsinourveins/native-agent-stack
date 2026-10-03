#!/usr/bin/env python3
"""Blind merit packets for the clean-install selection (2026-10-01). Each packet: the layer's requirement, what a
deciding comparison measures, and the candidates as name + repository only, shuffled with a per-layer seed. No tags,
rationales, statuses, pins or host receipts. Comparisons on record appear only where every named arm ran, worded
without selection or production labels. Usage: build_packets.py <worktree at main> <merit-view.json> <out-dir>"""
import hashlib
import json
import random
import sys
from pathlib import Path

root, view_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
view = json.loads(view_path.read_text())
land = {r["layer_id"]: r for r in json.loads((root / "catalogs/landscape/foundation.json").read_text())["layers"]}
state = {r["layer_id"]: r for r in json.loads((root / "catalogs/landscape/research-state.json").read_text())["layers"]
         if r.get("catalog") == "foundation"}
COMPARISONS = {
    "durable-memory": [
        "LongMemEval-S, session-level retrieval, 470 questions, recall_all@5, on a Mac (descriptive): agentmemory 0.9.29 "
        "with the all-MiniLM-L6-v2 embedder over its REST path 0.821; ai-memory (a 2.5 pre-release build) with "
        "Qwen3-Embedding-4B and its LLM reranker turned off 0.570; plain BM25 0.747. Not run: ai-memory with its LLM "
        "reranker, agentmemory through its Claude Code hooks, Hindsight 0.10.1 and MemPalace 3.10.0. The two systems "
        "captured different amounts of each session and used different embedders."],
    "semantic-rag": [
        "A sealed 35-query code-retrieval set on this project's repository: SocratiCode answered 30 of 35 and a "
        "traversal-ordered ripgrep baseline 20 of 35; the run's own record says it does not show general superiority."],
    "mcp-surfaces": [
        "A 37-check lifecycle comparison of mcporter 0.14.1 and MCP Inspector 2.8.0 (list, call, stop, restart, forced "
        "kill and recovery): both passed 37 of 37; one ps-listing regression of mcporter 0.14.1 was recorded."],
    "scheduling-supervision": [
        "A recovery comparison of Dagu, Prefect and Temporal on one maintenance workload, with material deviations and "
        "unequal recovery configuration between the arms; it named no winner."],
}
DISTRO = {
    "title": "WSL2 base distribution",
    "requirement": ("The base Linux distribution for a new WSL2 instance on this Windows host (WSL 2.7.13, kernel "
                    "6.18), installed from a vendor image whose checksum can be verified, with systemd user services, "
                    "current toolchains for Python 3.13, Node 24 and Rust, NVIDIA GPU access through WSL for an RTX "
                    "4090, and long-term security support."),
    "deciding": "A clean install of each candidate image with the stack's bootstrap, then its first-boot, systemd, "
                "GPU and toolchain checks on the same host.",
    "candidates": [{"name": "Ubuntu 26.04.1 LTS (Canonical WSL image)", "repository": "https://ubuntu.com/download/server"},
                   {"name": "Ubuntu 24.04.5 LTS (Canonical WSL image)", "repository": "https://ubuntu.com/download/server"},
                   {"name": "Debian 13 (WSL distribution)", "repository": "https://github.com/microsoft/WSL/blob/master/distributions/DistributionInfo.json"},
                   {"name": "Fedora (WSL distribution)", "repository": "https://github.com/microsoft/WSL/blob/master/distributions/DistributionInfo.json"},
                   {"name": "Arch Linux (WSL distribution)", "repository": "https://github.com/microsoft/WSL/blob/master/distributions/DistributionInfo.json"}],
}
# Selection words in the project's own requirement and comparison texts that describe the evaluation, not a candidate,
# are made neutral so no packet reads as if a choice already exists.
NEUTRAL = [("Use the installed CI skill", "Use a CI-repair skill"), ("Use a selected pinned skill", "Use a pinned skill"),
           ("native single-agent and selected worker graph", "native single-agent and a worker graph"),
           ("plus selected difficult-layout ingestion", "plus difficult-layout ingestion"),
           ("Run the selected local typed application", "Run a local typed application"),
           ("where the selected task requires", "where a task requires"), ("Run selected local workflows", "Run local workflows"),
           ("interact with selected pages", "interact with chosen pages"), ("Reproduce selected tools", "Reproduce the tools"),
           ("on an explicitly adopted host", "on an explicitly chosen host"),
           ("independently restore selected application state", "independently restore application state"),
           ("with the stack's bootstrap", "with the project's bootstrap")]
manifest = []
for layer in view["layers"]:
    if layer["catalog"] != "foundation" and layer["layer_id"] != "cross:wsl-distro":
        continue
    lid = layer["layer_id"]
    if lid == "cross:wsl-distro":
        req, deciding, cands = DISTRO["requirement"], DISTRO["deciding"], list(DISTRO["candidates"])
        title = DISTRO["title"]
    else:
        req, deciding, title = land[lid]["requirement"], state.get(lid, {}).get("next_action"), land[lid]["title"]
        cands = [{"name": c["name"], "repository": c.get("repository")} for c in layer["candidates"]]
    for a, b in NEUTRAL:
        req = req.replace(a, b) if req else req
        deciding = deciding.replace(a, b) if deciding else deciding
    seed = int(hashlib.sha256(f"merit-20261001:{lid}".encode()).hexdigest()[:16], 16)
    random.Random(seed).shuffle(cands)
    packet = {"layer_id": lid, "title": title, "requirement": req,
              "a_deciding_comparison_would_measure": deciding,
              "candidates": [{"key": f"C{i + 1:02d}", **c} for i, c in enumerate(cands)],
              "comparisons_on_record_where_every_named_arm_ran": COMPARISONS.get(lid, []),
              "target_hosts": "Primary: a new WSL2 Ubuntu-family instance on a Windows workstation, x86_64, 48 cores, "
                              "104 GB RAM, NVIDIA RTX 4090 24 GB. Secondary: macOS arm64 laptops. Users: Claude Code "
                              "and Codex agent sessions on that host."}
    path = out / f"{lid.replace(':', '_')}.json"
    data = json.dumps(packet, indent=1, ensure_ascii=False) + "\n"
    path.write_text(data, encoding="utf-8")
    manifest.append({"layer_id": lid, "packet": str(path), "sha256": hashlib.sha256(data.encode()).hexdigest(),
                     "candidates": len(cands)})
(out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
print(len(manifest), "packets;", sum(m["candidates"] for m in manifest), "candidates")
