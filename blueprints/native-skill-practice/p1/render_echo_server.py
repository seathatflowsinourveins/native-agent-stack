#!/usr/bin/env python3
"""Loopback echo for P1's render check: every POST is answered with its own request body, unchanged.

render-check.yaml points copies of arm J's three providers at this server, so promptfoo's output for
each copy is the exact request body arm J would send for that case (report r1 section 5.0, "Same
input"). It binds 127.0.0.1 only, writes no log line and no file, and is meant to run inside the
render check's own network namespace, which has no other interface:

  unshare -rn sh -c 'ip link set lo up; python3 render_echo_server.py & ...; promptfoo eval ...'
"""

from __future__ import annotations

import argparse
import http.server

PORT = 47121    # the port render-check.yaml names; nothing else listens inside the namespace


class Echo(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server's handler name
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # no request text in any log
        return


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Echo) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
