#!/usr/bin/env python3
"""MCP Inspector qualification arm (run inside sandbox.sh: private loopback-only network, / read-only, /mnt hidden).

Usage: accept_inspector.py <inspector-prefix> <qmd-executable> <arm-dir> <results.json>

Steps (each records argv, exit code, duration and output hashes; outputs go to <arm-dir>/out/<step>.{out,err}):
  A0  installed version from the package's own package.json (never `mcp-inspector --version`) and launcher sha256
  A1  fixture: a project-local QMD index (`qmd init`) over one Markdown file holding a unique marker
  A2  --cli stdio tools/list                 -> tool names == [get, multi_get, query, status]
  A3  --cli stdio tools/call query (lex)     -> exactly one hit, scratch/note.md, marker in the text
  A4  --cli stdio tools/call unknown tool    -> exit 5, error.code tool_not_found (positive control)
  A5  --cli stdio resources/list, prompts/list (recorded, compared across arms)
  A6  --cli stdio tools/list --strict        (recorded: tool-schema portability report and exit code)
  A7  --cli http tools/list and tools/call against `qmd mcp --http` on a namespace-private port, default era and
      --protocol-era auto
  A8  --web auth gate: DANGEROUSLY_OMIT_AUTH unset / "false" / "0" / "yes" / "true" with a scratch API token;
      GET /api/config without and with the x-mcp-remote-auth header, plus the banner's Auth line (token redacted)
Every web start sets MCP_AUTO_OPEN_ENABLED=false (the sandbox also hides /mnt, so no browser can start).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

prefix, qmd, arm, results_path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
inspector = str(prefix / "bin" / "mcp-inspector")
package_dir = prefix / "lib" / "node_modules" / "@modelcontextprotocol" / "inspector"
out_dir = arm / "out"
out_dir.mkdir(parents=True, exist_ok=True)
work = arm / "work"
(work / "docs").mkdir(parents=True, exist_ok=True)
MARK = "mcpi-qual-" + secrets.token_hex(6)
steps: list[dict] = []
env_base = dict(os.environ, MCP_AUTO_OPEN_ENABLED="false")
for key in ("DANGEROUSLY_OMIT_AUTH", "MCP_INSPECTOR_API_TOKEN", "MCP_PROXY_AUTH_TOKEN"):
    env_base.pop(key, None)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(step: str, argv: list[str], *, cwd: Path = work, timeout: int = 90, env: dict | None = None) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env or env_base, capture_output=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = "timeout", exc.stdout or b"", exc.stderr or b""
    record = {"step": step, "argv": [a.replace(str(arm), "<arm>").replace(str(prefix), "<prefix>") for a in argv],
              "exit": code, "duration_s": round(time.monotonic() - started, 3),
              "stdout_sha256": sha(out), "stderr_sha256": sha(err)}
    (out_dir / f"{step}.out").write_bytes(out)
    (out_dir / f"{step}.err").write_bytes(err)
    record["_stdout"], record["_stderr"] = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    return record


def finish(record: dict, passed: bool, note: str) -> None:
    record["pass"], record["note"] = bool(passed), note
    record.pop("_stdout", None)
    record.pop("_stderr", None)
    steps.append(record)
    print(f"{record['step']}: {'PASS' if passed else 'FAIL'} {note}", flush=True)


def last_json(text: str):
    for line in reversed([l for l in text.splitlines() if l.strip()]):
        try:
            return json.loads(line)
        except ValueError:
            continue
    try:
        return json.loads(text)
    except ValueError:
        return None


# A0 identity
package_json = json.loads((package_dir / "package.json").read_text())
launcher = (package_dir / "clients" / "launcher" / "build" / "index.js").read_bytes()
steps.append({"step": "A0-identity", "pass": True, "version": package_json["version"],
              "launcher_sha256": sha(launcher), "note": "package.json version; the launcher has no version flag"})
print("A0-identity:", package_json["version"], sha(launcher)[:16], flush=True)

# A1 fixture
(work / "docs" / "note.md").write_text(f"# Scratch fixture\n\n{MARK} appears exactly once in this fresh fixture file.\n")
ok = True
for step, argv in (("A1-qmd-init", [qmd, "init"]),
                   ("A1-qmd-collection-add", [qmd, "collection", "add", str(work / "docs"), "--name", "scratch"]),
                   ("A1-qmd-update", [qmd, "update"])):
    rec = run(step, argv)
    ok = ok and rec["exit"] == 0
    finish(rec, rec["exit"] == 0, "fixture preparation")
mcp_json = work / "mcp.json"
mcp_json.write_text(json.dumps({"mcpServers": {"qmd": {"type": "stdio", "command": qmd, "args": ["mcp"]}}}))
cli = [inspector, "--cli", "--config", str(mcp_json), "--server", "qmd", "--stored-auth-only", "--cwd", str(work)]

# A2 tools/list
rec = run("A2-stdio-tools-list", cli + ["--method", "tools/list", "--format", "json"])
data = last_json(rec["_stdout"]) or {}
names = sorted(t.get("name") for t in (data.get("result") or {}).get("tools", []))
rec["tool_names"] = names
finish(rec, rec["exit"] == 0 and names == ["get", "multi_get", "query", "status"], f"tools {names}")

# A3 tools/call query
args = json.dumps({"searches": [{"type": "lex", "query": MARK}], "limit": 5, "collections": ["scratch"],
                   "rerank": False})
rec = run("A3-stdio-tools-call-query", cli + ["--method", "tools/call", "--tool-name", "query",
                                               "--tool-args-json", args, "--format", "json"])
data = last_json(rec["_stdout"]) or {}
result = data.get("result") or {}
text = ((result.get("content") or [{}])[0]).get("text", "")
hits = (result.get("structuredContent") or {}).get("results", [])
rec["hits"] = [{"file": h.get("file"), "score": h.get("score")} for h in hits]
finish(rec, rec["exit"] == 0 and "Found 1 result" in text and MARK in text and len(hits) == 1
       and hits[0].get("file") == "scratch/note.md", f"hits {rec['hits']}")

# A4 positive control
rec = run("A4-stdio-unknown-tool", cli + ["--method", "tools/call", "--tool-name", "does_not_exist_probe",
                                           "--tool-args-json", "{}", "--format", "json"])
err_json = last_json(rec["_stderr"]) or last_json(rec["_stdout"]) or {}
code = (err_json.get("error") or {}).get("code")
rec["error_code"] = code
finish(rec, rec["exit"] == 5 and code == "tool_not_found", f"exit {rec['exit']} code {code}")

# A5 resources/prompts
for step, method in (("A5-stdio-resources-list", "resources/list"), ("A5-stdio-prompts-list", "prompts/list")):
    rec = run(step, cli + ["--method", method, "--format", "json"])
    data = last_json(rec["_stdout"]) or {}
    res = data.get("result") or {}
    rec["result_keys"] = sorted(res.keys())
    rec["counts"] = {k: len(v) for k, v in res.items() if isinstance(v, list)}
    finish(rec, rec["exit"] == 0, f"counts {rec['counts']}")

# A6 --strict
rec = run("A6-stdio-tools-list-strict", cli + ["--method", "tools/list", "--format", "json", "--strict"])
rec["stderr_tail"] = rec["_stderr"][-600:]
finish(rec, rec["exit"] in (0, 6), f"exit {rec['exit']} (0 clean, 6 error-severity portability findings)")

# A7 HTTP transport against a namespace-private qmd HTTP server
port = 18181
server_log = open(out_dir / "A7-qmd-http-server.log", "wb")
server = subprocess.Popen([qmd, "mcp", "--http", "--port", str(port)], cwd=work, env=env_base,
                          stdout=server_log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                          start_new_session=True)
url = f"http://localhost:{port}/mcp"
ready = False
for _ in range(100):
    try:
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
        ready = True
        break
    except urllib.error.HTTPError:
        ready = True
        break
    except Exception:
        time.sleep(0.2)
steps.append({"step": "A7-qmd-http-server-start", "pass": ready, "note": f"qmd mcp --http --port {port} ready={ready}"})
http_base = [inspector, "--cli", url, "--transport", "http", "--stored-auth-only"]
for era in ("default", "auto"):
    extra = [] if era == "default" else ["--protocol-era", era]
    rec = run(f"A7-http-{era}-tools-list", http_base + extra + ["--method", "tools/list", "--format", "json"])
    data = last_json(rec["_stdout"]) or {}
    names = sorted(t.get("name") for t in (data.get("result") or {}).get("tools", []))
    rec["tool_names"] = names
    finish(rec, rec["exit"] == 0 and names == ["get", "multi_get", "query", "status"], f"era {era} tools {names}")
    rec = run(f"A7-http-{era}-tools-call-query", http_base + extra + [
        "--method", "tools/call", "--tool-name", "query", "--tool-args-json", args, "--format", "json"])
    data = last_json(rec["_stdout"]) or {}
    result = data.get("result") or {}
    hits = (result.get("structuredContent") or {}).get("results", [])
    rec["hits"] = [{"file": h.get("file"), "score": h.get("score")} for h in hits]
    finish(rec, rec["exit"] == 0 and len(hits) == 1 and hits[0].get("file") == "scratch/note.md",
           f"era {era} hits {rec['hits']}")
os.killpg(server.pid, signal.SIGTERM)
try:
    server.wait(timeout=10)
except subprocess.TimeoutExpired:
    os.killpg(server.pid, signal.SIGKILL)
    server.wait()
server_log.close()

# A8 web auth gate
token = secrets.token_hex(24)


def http_status(path: str, headers: dict) -> int | str:
    request = urllib.request.Request(f"http://127.0.0.1:16274{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


for label, value in (("unset", None), ("false", "false"), ("0", "0"), ("yes", "yes"), ("true", "true")):
    env = dict(env_base, CLIENT_PORT="16274", MCP_SANDBOX_PORT="16275", MCP_INSPECTOR_API_TOKEN=token)
    if value is not None:
        env["DANGEROUSLY_OMIT_AUTH"] = value
    log_path = out_dir / f"A8-web-{label}.log"
    log = open(log_path, "wb")
    started = time.monotonic()
    web = subprocess.Popen([inspector, "--web"], cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, start_new_session=True)
    up = False
    for _ in range(150):
        if b"is up and running" in log_path.read_bytes():
            up = True
            break
        if web.poll() is not None:
            break
        time.sleep(0.2)
    no_header = http_status("/api/config", {}) if up else None
    with_header = http_status("/api/config", {"x-mcp-remote-auth": f"Bearer {token}"}) if up else None
    wrong_header = http_status("/api/config", {"x-mcp-remote-auth": "Bearer " + "0" * 48}) if up else None
    try:
        os.killpg(web.pid, signal.SIGTERM)
        web.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(web.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        web.wait()
    log.close()
    text = log_path.read_bytes().decode("utf-8", "replace").replace(token, "<scratch-token>")
    log_path.write_text(text)
    auth_line = next((l.strip() for l in text.splitlines() if l.strip().startswith("Auth")), None)
    browser_line = any("Opening browser" in l for l in text.splitlines())
    record = {"step": f"A8-web-auth-{label}", "DANGEROUSLY_OMIT_AUTH": value, "banner_up": up,
              "auth_line": auth_line, "opening_browser_line": browser_line,
              "api_config_no_header": no_header, "api_config_scratch_token": with_header,
              "api_config_wrong_token": wrong_header, "duration_s": round(time.monotonic() - started, 3),
              "log_sha256": sha(text.encode())}
    expected_off = value in ("true",)
    gate_on = no_header == 401 and wrong_header == 401 and with_header == 200
    gate_off = no_header == 200
    record["gate"] = "on" if gate_on else ("off" if gate_off else "other")
    steps.append(record)
    print(f"A8-web-auth-{label}: gate={record['gate']} auth_line={auth_line!r} no_header={no_header} "
          f"token={with_header} wrong={wrong_header} browser_line={browser_line}", flush=True)

results = {"inspector_version": package_json["version"], "marker_prefix": "mcpi-qual-", "steps": steps,
           "gated_pass": all(s.get("pass", True) for s in steps if not s["step"].startswith("A8")),
           "web_auth_gate": {s["step"].removeprefix("A8-web-auth-"): s["gate"] for s in steps
                             if s["step"].startswith("A8")}}
results_path.write_text(json.dumps(results, indent=2) + "\n")
print("gated_pass:", results["gated_pass"], "web_auth_gate:", results["web_auth_gate"])
