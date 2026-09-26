#!/usr/bin/env python3
"""Check where a key appears while the local-model reachability request runs, in both recipe forms.

Usage: credential-argv-probe.py <connect-local-llm-safe.sh>

Extended copy of ../credential-argv-probe.py, which stays byte-identical as the version behind
credential-argv-probe-20260926T111651Z.txt. It adds the safe form under callers whose
environment would export the key variable: KEY already exported (under sh and under bash), and
bash's allexport option exported through SHELLOPTS (bash imports it at startup, also when it
runs as /bin/sh).

Uses no real key. The probe writes a random dummy value that no service accepts to a 0600
file in a private temporary directory. A loopback HTTP listener that the probe starts on a
free port stands in for llama.cpp. It records whether the request carried
"Authorization: Bearer <dummy>", and it holds the response for 2 s, so the client is still
running while the probe inspects it. Nothing is sent to port 18232 or to any other service.

  first-pass form      sh -c 'KEY=$(cat <file>); exec curl ... -H "Authorization: Bearer $KEY" ...',
                       the header form of connect-local-llm.sh. Its `brv providers connect
                       --api-key "$KEY"` put the key on a command line the same way.
  safe form            sh <script> <file> http://127.0.0.1:<port>/v1 <models-out>, with KEY and
                       SHELLOPTS removed from the environment
  safe form, KEY exported by the caller
                       the same with KEY=probe-inherited-placeholder in the environment
  safe form under bash, KEY exported by the caller
                       bash <script> ..., the same environment
  safe form under bash, allexport exported through SHELLOPTS
                       bash <script> ..., SHELLOPTS=allexport in the environment, no KEY

While a request is held, the probe reads the command line and environment of the client
process and of every descendant, which it finds from its own child's pid through
/proc/<pid>/task/<tid>/children rather than by listing /proc. It records whether the dummy
value appears in any of them. The value itself is never printed.

Expected before the run:
  first-pass form: header delivered, value in a command line.
  every safe form: header delivered, value in no command line and no environment, script
  exit 0, http_code=200, value not in the script's output.
Prints one JSON line per form and a summary, and exits 0 only when every expectation held.
Local integration check.
"""

from __future__ import annotations

import http.server
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HOLD_S = 2.0
PLACEHOLDER = "probe-inherited-placeholder"


def descendants(root: int) -> list[int]:
    found, pending = [], [root]
    while pending:
        pid = pending.pop()
        found.append(pid)
        try:
            threads = os.listdir(f"/proc/{pid}/task")
        except OSError:
            continue
        for thread in threads:
            try:
                pending.extend(int(v) for v in Path(f"/proc/{pid}/task/{thread}/children").read_text().split())
            except (OSError, ValueError):
                continue
    return found


def read_bytes(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError:
        return b""


def main() -> int:
    safe_script = Path(sys.argv[1]).resolve()
    dummy = "probe-dummy-" + secrets.token_hex(16)
    state = {"expected_header": f"Bearer {dummy}", "delivered": None}
    received = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            state["delivered"] = self.headers.get("Authorization") == state["expected_header"]
            received.set()
            threading.Event().wait(HOLD_S)
            body = b'{"object":"list","data":[{"id":"probe-model"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    clean_env = {name: value for name, value in os.environ.items() if name not in ("KEY", "SHELLOPTS")}
    bash = shutil.which("bash")
    results = []
    with tempfile.TemporaryDirectory() as work:
        key_file = Path(work) / "key"
        key_file.touch(mode=0o600)
        key_file.write_text(dummy + "\n", encoding="utf-8")
        safe_args = [str(safe_script), str(key_file), base_url, str(Path(work) / "models.json")]
        forms = [
            ("first-pass form", ["sh", "-c", 'KEY=$(cat "$1"); exec curl -s -o /dev/null -w "%{http_code}" '
                                 '-H "Authorization: Bearer $KEY" "$2/models"', "sh", str(key_file), base_url],
             clean_env),
            ("safe form", ["sh", *safe_args], clean_env),
            ("safe form, KEY exported by the caller", ["sh", *safe_args], {**clean_env, "KEY": PLACEHOLDER}),
            ("safe form under bash, KEY exported by the caller", [bash or "bash", *safe_args],
             {**clean_env, "KEY": PLACEHOLDER}),
            ("safe form under bash, allexport exported through SHELLOPTS", [bash or "bash", *safe_args],
             {**clean_env, "SHELLOPTS": "allexport"}),
        ]
        for form, command, env in forms:
            if command[0] == "bash" and bash is None:
                results.append({"form": form, "error": "bash not found", "expectation_held": False})
                continue
            received.clear()
            state["delivered"] = None
            client = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            in_argv = in_env = False
            inspected = 0
            if received.wait(timeout=30):
                for pid in descendants(client.pid):
                    inspected += 1
                    in_argv = in_argv or dummy.encode() in read_bytes(f"/proc/{pid}/cmdline")
                    in_env = in_env or dummy.encode() in read_bytes(f"/proc/{pid}/environ")
            stdout, _stderr = client.communicate(timeout=60)
            text = stdout.decode("utf-8", "replace")
            row = {"form": form, "header_delivered": state["delivered"], "processes_inspected": inspected,
                   "value_in_a_command_line": in_argv, "value_in_an_environment": in_env,
                   "exit_code": client.returncode,
                   "value_in_stdout": dummy in text}
            if form.startswith("safe form"):
                codes = [line for line in text.splitlines() if line.startswith("http_code=")]
                row["http_code_line"] = codes[0] if codes else None
                row["expectation_held"] = (row["header_delivered"] is True and inspected > 0 and not in_argv
                                           and not in_env and client.returncode == 0
                                           and row["http_code_line"] == "http_code=200" and not row["value_in_stdout"])
            else:
                row["expectation_held"] = row["header_delivered"] is True and inspected > 0 and in_argv
            results.append(row)
    server.shutdown()
    for row in results:
        print(json.dumps(row))
    passed = len(results) == len(forms) and all(row["expectation_held"] for row in results)
    print(json.dumps({"forms": len(results), "all_expectations_held": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
