#!/usr/bin/env python3
"""Direct native stdio observation independent of native_token_ci.Run and its MCP parser.

Native interface: oraios/serena c6fbd1c5932df2494ffa0020af5a9fbe80b82143,
src/serena/cli.py start_mcp_server and src/serena/mcp.py.
This is a local native operation, not an upstream test or a provider/model run.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile


parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
binary = shutil.which("serena")
assert binary
report = {"evidence_class": "independent_native_observation",
          "upstream_revision": "c6fbd1c5932df2494ffa0020af5a9fbe80b82143", "contexts": {},
          "limits": ["Existing installed executable; fresh prefix is exercised separately",
                     "No active project, language server, credentials, provider or model",
                     "Retained stdout contains exact native MCP response bytes",
                     "Retained stderr replaces the owned temporary directory, native HOME and executable paths"]}
with tempfile.TemporaryDirectory(prefix="serena-independent-") as directory:
    work = Path(directory)
    cwd = work / "no-project"
    cwd.mkdir()
    for context in ("claude-code", "codex"):
        home = work / context
        home.mkdir()
        env = {key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ}
        env.update({"SERENA_HOME": str(home), "XDG_CONFIG_HOME": str(work / "config"),
                    "XDG_CACHE_HOME": str(work / "cache"), "XDG_DATA_HOME": str(work / "data"),
                    "XDG_STATE_HOME": str(work / "state"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                    "NO_COLOR": "1", "CI": "true"})
        argv = [binary, "start-mcp-server", "--context", context, "--project-from-cwd",
                "--enable-web-dashboard", "false", "--open-web-dashboard", "false"]
        started = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryFile() as err:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=err)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            lines = []
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "native-token-ci", "version": "1"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ]
            try:
                for request in requests:
                    process.stdin.write((json.dumps(request) + "\n").encode())
                    process.stdin.flush()
                    assert selector.select(timeout=30), "Native response timed out"
                    line = process.stdout.readline()
                    response = json.loads(line)
                    assert response["id"] == request["id"] and "error" not in response
                    lines.append(line)
                    if request["method"] == "initialize":
                        process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                        process.stdin.flush()
                process.stdin.close()
                exit_code = process.wait(timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                selector.close()
            err.seek(0)
            stderr = err.read()
        stdout = b"".join(lines)
        (args.output / f"{context}.stdout.txt").write_bytes(stdout)
        text = stderr.decode()
        for source, target in [(str(work), "<WORK>"), (os.environ.get("HOME", ""), "<NATIVE_HOME>"),
                               (binary, "<TOOL:serena>")]:
            if source:
                text = text.replace(source, target)
        (args.output / f"{context}.stderr.txt").write_text(text)
        report["contexts"][context] = {"argv": ["<TOOL:serena>"] + argv[1:], "cwd": "<WORK>/no-project",
                                       "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                                       "exit_code": exit_code, "requests": requests,
                                       "responses": [{"id": request["id"], "bytes": len(line),
                                                      "sha256": hashlib.sha256(line).hexdigest()}
                                                     for request, line in zip(requests, lines)],
                                       "stdout_raw_sha256": hashlib.sha256(stdout).hexdigest(),
                                       "stderr_raw_sha256": hashlib.sha256(stderr).hexdigest(),
                                       "tool_names": [t["name"] for t in json.loads(lines[1])["result"]["tools"]]}
        assert exit_code == 0
report["cleanup"] = {"owned_temporary_directory_absent": not work.exists()}
(args.output / "observation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"contexts": {k: {"exit_code": v["exit_code"], "responses": v["responses"]}
                               for k, v in report["contexts"].items()}, "cleanup": report["cleanup"]}))
