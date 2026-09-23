#!/usr/bin/env python3
"""Reuse the minimal MCP stdio client for code-memory."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "watcher-kill-restart-recovery"))
from mcp_client import McpProc

CM_BIN = os.path.expanduser("~/.local/share/codex-ecosystem/tools/code-memory-5a8db16-w2/.venv/bin/code-memory")

def spawn_cm(cwd, extra_env=None):
    env = os.environ.copy()
    env["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"  # permitted (Apache-2.0), matches ai-memory's model, avoids the CC-BY-NC-4.0 default flagged in source review
    env["HF_HOME"] = os.path.join(os.path.dirname(__file__), "hf-cache")
    if extra_env:
        env.update(extra_env)
    p = McpProc([CM_BIN], env, cwd)
    p.initialize(timeout=60)
    return p
