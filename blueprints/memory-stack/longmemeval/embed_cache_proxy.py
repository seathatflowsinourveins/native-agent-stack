#!/usr/bin/env python3
"""Byte-exact embedding cache in front of the benchmark embed server (amendment A13).

Key = sha256(method, path, raw request body). Value = the upstream's raw 200 response body, zlib-compressed.
A hit returns the bytes the upstream returned for a byte-identical request, so a cached arm sees exactly
what recomputation on the single-slot server returns (checked at start-up by `--selftest`). Every other
request, and every non-200 response, passes through uncached.

    embed_cache_proxy.py UPSTREAM PORT DB [--selftest MODEL]
"""
import hashlib
import http.client
import http.server
import json
import sqlite3
import sys
import threading
import time
import urllib.parse
import zlib

UPSTREAM, PORT, DB = sys.argv[1].rstrip("/"), int(sys.argv[2]), sys.argv[3]
CACHED = {"/v1/embeddings", "/api/embed", "/api/embeddings"}
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "proxy-connection", "upgrade", "te"}
up = urllib.parse.urlsplit(UPSTREAM)

db = sqlite3.connect(DB, check_same_thread=False, isolation_level=None)
db.execute("PRAGMA journal_mode=WAL")
db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, ctype TEXT, body BLOB, tokens INTEGER, created REAL)")
lock = threading.Lock()
stats = {"hits": 0, "misses": 0, "passthrough": 0, "upstream_errors": 0, "hit_tokens": 0, "miss_tokens": 0,
         "started": time.strftime("%Y-%m-%dT%H:%M:%S")}


def tokens_of(body: bytes) -> int:
    try:
        d = json.loads(body)
        return int((d.get("usage") or {}).get("prompt_tokens") or d.get("prompt_eval_count") or 0)
    except Exception:  # noqa: BLE001 - statistics only
        return 0


def forward(method: str, path: str, headers: dict, body: bytes):
    conn = http.client.HTTPConnection(up.hostname, up.port, timeout=3600)
    try:
        conn.request(method, path, body=body if body else None, headers=headers)
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type", "application/json"), r.read()
    finally:
        conn.close()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def _body(self) -> bytes:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            out = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                        pass
                    return out
                out += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _reply(self, status: int, ctype: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self):
        body = self._body() if self.command in ("POST", "PUT", "PATCH") else b""
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        path = urllib.parse.urlsplit(self.path).path
        if self.command != "POST" or path not in CACHED:
            with lock:
                stats["passthrough"] += 1
            try:
                self._reply(*forward(self.command, self.path, headers, body))
            except OSError as e:
                with lock:
                    stats["upstream_errors"] += 1
                self._reply(502, "text/plain", f"upstream error: {e}".encode())
            return
        key = hashlib.sha256(b"POST\0" + self.path.encode() + b"\0" + body).hexdigest()
        with lock:
            row = db.execute("SELECT ctype, body, tokens FROM c WHERE k = ?", (key,)).fetchone()
        if row:
            with lock:
                stats["hits"] += 1
                stats["hit_tokens"] += row[2]
            self._reply(200, row[0], zlib.decompress(row[1]))
            return
        try:
            status, ctype, resp = forward("POST", self.path, headers, body)
        except OSError as e:
            with lock:
                stats["upstream_errors"] += 1
            self._reply(502, "text/plain", f"upstream error: {e}".encode())
            return
        if status == 200:
            n = tokens_of(resp)
            with lock:
                db.execute("INSERT OR IGNORE INTO c VALUES (?, ?, ?, ?, ?)",
                           (key, ctype, zlib.compress(resp, 1), n, time.time()))
                stats["misses"] += 1
                stats["miss_tokens"] += n
        else:
            with lock:
                stats["upstream_errors"] += 1
        self._reply(status, ctype, resp)

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_PATCH = _handle


def write_stats(path: str):
    while True:
        time.sleep(60)
        with lock:
            snap = dict(stats, rows=db.execute("SELECT COUNT(*) FROM c").fetchone()[0],
                        at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(path, "w") as fh:
            json.dump(snap, fh, indent=1)


def selftest(model: str) -> None:
    """Direct miss vs proxied miss vs proxied hit: the vectors must be identical."""
    text = f"A13 cache self-test {time.time_ns()}: the user asked about the blue notebook on 2023/05/01."
    req = json.dumps({"model": model, "input": [text]}).encode()
    h = {"Content-Type": "application/json"}
    direct = json.loads(forward("POST", "/v1/embeddings", h, req)[2])["data"][0]["embedding"]
    via = []
    for _ in range(2):
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=600)
        c.request("POST", "/v1/embeddings", body=req, headers=h)
        via.append(c.getresponse().read())
        c.close()
    same_bytes = via[0] == via[1]
    same_vec = json.loads(via[0])["data"][0]["embedding"] == direct
    print(f"selftest: proxied hit byte-identical={same_bytes}; recomputation identical={same_vec}; "
          f"dims={len(direct)}; stats={stats}", flush=True)
    if not (same_bytes and same_vec):
        sys.exit(1)


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    threading.Thread(target=write_stats, args=(DB + ".stats.json",), daemon=True).start()
    if "--selftest" in sys.argv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        selftest(sys.argv[sys.argv.index("--selftest") + 1])
        srv.shutdown()
    else:
        print(f"embed cache proxy on 127.0.0.1:{PORT} -> {UPSTREAM}; db {DB}", flush=True)
        srv.serve_forever()
