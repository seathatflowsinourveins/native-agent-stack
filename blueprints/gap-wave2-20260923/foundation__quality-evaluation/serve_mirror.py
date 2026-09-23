#!/usr/bin/env python3
"""Serve a local TodoMVC mirror over TLS on loopback, logging every request.

Usage: serve_mirror.py MIRROR_DIR PORT CERT KEY LOG

Paths under /todomvc/ map to MIRROR_DIR; /todomvc redirects to /todomvc/ as the
real host does. Each served file is logged with its sha256 so a run can show
which application bytes the browser actually received.
"""
import hashlib
import http.server
import os
import ssl
import sys

mirror, port, cert, key, log_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
log = open(log_path, "a", buffering=1)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/todomvc":
            self.send_response(301)
            self.send_header("Location", "/todomvc/")
            self.end_headers()
            log.write(f"301 {path}\n")
            return
        if not path.startswith("/todomvc/"):
            self.send_error(404)
            log.write(f"404 {path}\n")
            return
        rel = path[len("/todomvc/"):] or "index.html"
        full = os.path.realpath(os.path.join(mirror, rel))
        if not full.startswith(os.path.realpath(mirror) + os.sep) or not os.path.isfile(full):
            self.send_error(404)
            log.write(f"404 {path}\n")
            return
        body = open(full, "rb").read()
        ctype = {"html": "text/html", "css": "text/css", "js": "application/javascript"}.get(full.rsplit(".", 1)[-1], "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        log.write(f"200 {path} sha256={hashlib.sha256(body).hexdigest()}\n")


server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(cert, key)
server.socket = ctx.wrap_socket(server.socket, server_side=True)
server.serve_forever()
