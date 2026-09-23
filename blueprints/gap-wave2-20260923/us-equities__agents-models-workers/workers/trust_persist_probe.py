#!/usr/bin/env python3
"""Fix-round-2 probe: does native `codex app-server` persist a thread/start config.projects trust
override (as codex-acp 1.12.0 createSessionConfig sends) into $CODEX_HOME/config.toml?
Runs with an empty temporary CODEX_HOME and HOME under the unit cache; no auth, no turn/start.
Usage: trust_persist_probe.py OUT_JSON            (arms T0, T1)
       trust_persist_probe.py OUT_JSON arms2      (arms T2, T3; fix-round-2 addendum)
       trust_persist_probe.py OUT_JSON positive   (arm P: config/value/write positive control)
"""
import json, os, subprocess, sys, tempfile, time, hashlib
from pathlib import Path

CODEX = Path.home() / ".local/share/codex-ecosystem/bin/codex"
BASE = Path.home() / ".cache/gap-wave2-20260923/agents-models-workers/trustprobe"


def arm(name, with_override, second_ephemeral=False, first=True, positive=False):
    root = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=BASE))
    home, chome, ws = root / "home", root / "codex-home", root / "ws"
    for d in (home, chome, ws):
        d.mkdir()
    cfg = chome / "config.toml"
    before = cfg.exists()
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "CODEX_HOME": str(chome), "LANG": "C.UTF-8"}
    p = subprocess.Popen([str(CODEX), "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env, cwd=ws)
    def send(o):
        p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()
    config = {"features": {"hooks": False, "plugin_hooks": False}}
    if with_override:
        config["projects"] = {str(ws): {"trust_level": "trusted"}}
    send({"id": 0, "method": "initialize", "params": {"clientInfo": {"name": "trust-probe", "version": "0"}}})
    send({"method": "initialized"})
    want = 1
    if first:
        send({"id": 1, "method": "thread/start", "params": {"config": config, "cwd": str(ws)}})
    if positive:
        send({"id": 1, "method": "config/value/write", "params": {"keyPath": "projects", "mergeStrategy": "upsert",
              "value": {str(ws): {"trust_level": "trusted"}}}})
    if second_ephemeral:
        send({"id": 2, "method": "thread/start", "params": {"cwd": str(ws), "ephemeral": True}})
        want = 2
    lines, resp, t0 = [], None, time.monotonic()
    import select
    while time.monotonic() - t0 < 45:
        r, _, _ = select.select([p.stdout], [], [], 1)
        if not r:
            continue
        line = p.stdout.readline()
        if not line:
            break
        lines.append(line.strip()[:400])
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("id") == want:
            resp = o
            break
    time.sleep(2)
    p.terminate()
    try:
        _, err = p.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill(); _, err = p.communicate()
    after = cfg.read_text() if cfg.exists() else None
    red = lambda s: None if s is None else s.replace(str(Path.home()), "$HOME")
    return {"arm": name, "override_sent": with_override, "first_thread_start": first, "second_ephemeral_thread_start": second_ephemeral, "config_toml_existed_before": before,
            "thread_start_ok": bool(resp and "result" in resp),
            "thread_start_error": red(json.dumps(resp.get("error"))) if resp and "error" in resp else None,
            "config_toml_after": red(after),
            "config_toml_after_sha256": hashlib.sha256(after.encode()).hexdigest() if after else None,
            "stdout_first_lines": [red(l) for l in lines[:6]], "stderr_tail": red(err[-1500:]),
            "exit_code": p.returncode, "ws": red(str(ws))}


if __name__ == "__main__":
    BASE.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = {"started_at": started, "codex_version": subprocess.run([str(CODEX), "--version"], capture_output=True, text=True).stdout.strip(),
           "arms": ([arm("T0-control", False), arm("T1-override", True)] if len(sys.argv) < 3 else
                    [arm("P-positive-control", False, first=False, positive=True)] if sys.argv[2] == "positive" else
                    [arm("T2-override-then-ephemeral", True, second_ephemeral=True),
                     arm("T3-ephemeral-only", False, second_ephemeral=True, first=False)]),
           "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps([{k: a[k] for k in ("arm", "thread_start_ok", "thread_start_error", "config_toml_after")} for a in out["arms"]], indent=1))
