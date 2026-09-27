#!/usr/bin/env python3
"""Offline smoke test for prove_check.py's refactored live-path plumbing (argparse moved into main(),
build_checks(), and instant()/by() taking explicit loki/selector/window arguments instead of module globals).

This does NOT test privacy logic -- see failing_first_ab.py (synthetic A/B) and offline_recheck.py (real
retained data) for that. It tests that the CLI, argparse, build_checks() and the --dry-run loop actually run
end to end after the refactor, with no NameError/AttributeError, since the next real prove.sh run depends on
this exact code path for its 15 non-privacy dry-run checks (12 CHECKS + 3 ZERO_CHECKS).

A local http.server on an ephemeral loopback port answers every GET with an empty, successful Loki instant
-query response; prove_check.py's own --dry-run mode is run against it as a real subprocess (not an import),
so this also exercises argument parsing exactly as prove.sh invokes it.

Usage: dry_run_smoke.py <prove_check.py's directory>
Exit 0 iff exactly 15 "PASS dry run ..." lines were printed and the process exited 0.
"""
import http.server
import json
import sys
import subprocess
import threading


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"status": "success", "data": {"resultType": "vector", "result": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep this script's own output limited to the derived summary


def main():
    pc_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [sys.executable, f"{pc_dir}/prove_check.py", f"http://127.0.0.1:{port}", "smoke-test-task", "0",
             "--dry-run"],
            capture_output=True, text=True, timeout=30)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    print(result.stdout, end="")
    if result.stderr.strip():
        print("STDERR:\n" + result.stderr, file=sys.stderr)
    pass_lines = [line for line in result.stdout.splitlines() if line.startswith("PASS dry run query parses")]
    crashed = "Traceback" in result.stderr or "Error" in result.stderr
    ok = result.returncode == 0 and len(pass_lines) == 15 and not crashed
    print(f"SUMMARY dry_run_smoke: returncode={result.returncode} pass_lines={len(pass_lines)} "
          f"(expect 15) crashed={crashed} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
