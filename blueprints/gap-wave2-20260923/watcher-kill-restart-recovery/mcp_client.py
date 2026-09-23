#!/usr/bin/env python3
"""Minimal MCP stdio JSON-RPC client for driving a SocratiCode process directly,
so we control process lifetime (start/kill/restart) around tool calls."""
import json, subprocess, sys, os, time, threading, queue

class McpProc:
    def __init__(self, cmd, env, cwd):
        self.proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._id = 0
        self._q = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._stderr_lines = []
        self._ereader = threading.Thread(target=self._err_loop, daemon=True)
        self._ereader.start()

    def _read_loop(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._q.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    def _err_loop(self):
        for line in self.proc.stderr:
            self._stderr_lines.append(line.rstrip())

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _next_id(self):
        self._id += 1
        return self._id

    def _wait_response(self, want_id, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("id") == want_id:
                return msg
        raise TimeoutError(f"no response for id={want_id} within {timeout}s; stderr_tail={self._stderr_lines[-10:]}")

    def initialize(self, timeout=30):
        rid = self._next_id()
        self._send({
            "jsonrpc": "2.0", "id": rid, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gap-wave2-rag-ops", "version": "0.1.0"},
            },
        })
        resp = self._wait_response(rid, timeout)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return resp

    def call_tool(self, name, arguments, timeout=60):
        rid = self._next_id()
        self._send({
            "jsonrpc": "2.0", "id": rid, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        return self._wait_response(rid, timeout)

    def kill(self, sig=9):
        os.kill(self.proc.pid, sig)

    def terminate_clean(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()

    def poll(self):
        return self.proc.poll()


def build_env(qdrant_url, home_dir, watcher="auto"):
    env = os.environ.copy()
    env.update({
        "HOME": home_dir,
        "QDRANT_MODE": "external",
        "QDRANT_URL": qdrant_url,
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
        "SOCRATICODE_WATCHER": watcher,
        "SEARCH_DEFAULT_LIMIT": "5",
        "SOCRATICODE_AUTO_RESUME": "off",
    })
    return env

NODE = os.path.expanduser("~/.local/share/codex-ecosystem/bin/node")
SC = os.path.expanduser("~/.local/share/codex-ecosystem/tools/socraticode-1.14.0/lib/node_modules/socraticode/dist/index.js")

def spawn(qdrant_url, home_dir, cwd, watcher="auto"):
    env = build_env(qdrant_url, home_dir, watcher)
    p = McpProc([NODE, SC], env, cwd)
    p.initialize()
    return p
