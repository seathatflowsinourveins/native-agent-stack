#!/usr/bin/env python3
"""Gap 9: one codex-native-sdk worker with an isolated ai-memory MCP (loopback 27374, temp data
dir) and a disposable-Qdrant SocratiCode MCP; run 1 is SIGKILLed (process group) as soon as its
ai-memory handoff appears in the isolated store; run 2 is a fresh worker that recovers via the
handoff and finishes. Usage: g9_composed.py OUT_DIR"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache/gap-wave2-20260923/agents-models-workers"
PY = str(Path.home() / ".local/share/codex-ecosystem/tools/equity-worker-sdk/bin/python")
AIM = str(Path.home() / ".local/share/codex-ecosystem/tools/ai-memory-2.3.2/ai-memory")
PROJECT = str(CACHE / "corpus-scripts")
NODE = str(Path.home() / ".local/share/codex-ecosystem/bin/node")
SC = str(Path.home() / ".local/share/codex-ecosystem/tools/socraticode-1.14.0/lib/node_modules/socraticode/dist/index.js")
SC_ENV = {"HOME": str(CACHE / "sc-home"), "SOCRATICODE_GLOBAL_CONFIG_DIR": str(CACHE / "sc-home/.socraticode"),
          "QDRANT_MODE": "external", "QDRANT_URL": "http://127.0.0.1:27333", "QDRANT_COLLECTION_PREFIX": "g2amw_",
          "EMBEDDING_PROVIDER": "lmstudio", "LMSTUDIO_URL": "http://127.0.0.1:8231/v1",
          "EMBEDDING_MODEL": "nvidia/Nemotron-3-Embed-1B-BF16", "EMBEDDING_DIMENSIONS": "2048",
          "EMBEDDING_CONTEXT_LENGTH": "4096", "EMBEDDING_QUERY_PREFIX": "query: ", "EMBEDDING_DOCUMENT_PREFIX": "passage: ",
          "EMBEDDING_DOCUMENT_INCLUDE_PATH": "true", "RESPECT_GITIGNORE": "true", "INCLUDE_DOT_FILES": "false",
          "SOCRATICODE_WATCHER": "off", "SOCRATICODE_AUTO_RESUME": "off", "SEARCH_DEFAULT_LIMIT": "10",
          "PATH": os.environ["PATH"]}
OVR = ['mcp_servers.ai-memory.url="http://127.0.0.1:27374/mcp"',
       'mcp_servers.ai-memory.default_tools_approval_mode="approve"',
       'mcp_servers.ai-memory.enabled_tools=["memory_handoff_begin","memory_handoff_accept","memory_handoff_list"]',
       f'mcp_servers.socraticode.command={json.dumps(NODE)}', f'mcp_servers.socraticode.args=[{json.dumps(SC)}]',
       f'mcp_servers.socraticode.cwd={json.dumps(PROJECT)}', 'mcp_servers.socraticode.startup_timeout_sec=120',
       'mcp_servers.socraticode.default_tools_approval_mode="approve"',
       'mcp_servers.socraticode.enabled_tools=["codebase_search","codebase_status"]']
OVR += [f"mcp_servers.socraticode.env.{k}={json.dumps(v)}" for k, v in SC_ENV.items()]
AENV = dict(os.environ, HOME=str(CACHE / "aim-home"), AI_MEMORY_SERVER_URL="http://127.0.0.1:27374")

def handoffs():
    p = subprocess.run([AIM, "--data-dir", str(CACHE / "aim-data"), "handoffs", "--workspace", "g2amw", "--project", "g9-composed"],
                       capture_output=True, text=True, env=AENV)
    return p.stdout.strip()

def worker(prompt_file, receipt, ws):
    ws.mkdir(parents=True, exist_ok=True)
    prompt = ws / "prompt.md"; prompt.write_text(prompt_file.read_text().replace("PROJECT_PATH", PROJECT))
    cmd = [PY, str(HERE / "sdk_arm.py"), "run", "--workspace", str(ws), "--prompt", str(prompt), "--receipt", str(receipt)]
    for o in OVR:
        cmd += ["--override", o]
    return subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    rec = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "handoffs_before": handoffs()}
    p1 = worker(HERE / "g9-step1-prompt.md", out / "run1-receipt.json", CACHE / "ws/g9-run1")
    t0 = time.time(); killed = None
    while time.time() - t0 < 360:
        if p1.poll() is not None:
            break
        h = handoffs()
        if h and not h.startswith("No open handoffs"):
            os.killpg(p1.pid, signal.SIGKILL); killed = round(time.time() - t0, 2); rec["handoffs_at_kill"] = h; break
        time.sleep(0.5)
    p1.wait()
    rec["run1"] = {"returncode": p1.returncode, "killed_after_s": killed, "receipt_written": (out / "run1-receipt.json").exists(),
                   "stdout": p1.stdout.read()[-2000:], "stderr_tail": p1.stderr.read()[-2000:]}
    time.sleep(2)
    rec["orphans_after_kill"] = subprocess.run(["pgrep", "-af", "g9-run1"], capture_output=True, text=True).stdout
    rec["handoffs_between_runs"] = handoffs()
    p2 = worker(HERE / "g9-step2-prompt.md", out / "run2-receipt.json", CACHE / "ws/g9-run2")
    so, se = p2.communicate(timeout=480)
    rec["run2"] = {"returncode": p2.returncode, "stdout": so[-2000:], "stderr_tail": se[-2000:]}
    rec["handoffs_after_run2"] = handoffs()
    rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "orchestration.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("handoffs_between_runs", "handoffs_after_run2")}, indent=1)[:2000])
    print(json.dumps(rec["run1"])[:800])

if __name__ == "__main__":
    main()
