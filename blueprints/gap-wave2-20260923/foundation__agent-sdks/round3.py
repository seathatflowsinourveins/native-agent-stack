#!/usr/bin/env python3
"""Round 3 driver for the agent-sdks gap wave (2026-09-23). Usage: round3.py STEP

Steps: stage, controls, config, worker-bare, events, worker-ctxmode, claude-resume, schema, mcp-startup (late);
fix round: stage-np, config-np, mcp-startup-np, worker-bare-np.
Writes private outputs to $HOME/.cache/gap-wave2-20260923/agent-sdks/round3/runs; export_round3.py
sanitizes them into the evidence directory. Before each Codex model call it waits while 2 or more
real `codex exec` processes run (classified by argv).
"""
from __future__ import annotations

import http.server
import json
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HOME = Path.home()
CACHE = HOME / ".cache/gap-wave2-20260923/agent-sdks"
R3 = CACHE / "round3"
RUNS = R3 / "runs"
V = CACHE / "codex-sdk-01551"
PY = V / "bin/python"
SDK_BIN = V / "lib/python3.13/site-packages/codex_cli_bin/bin/codex"
NATIVE_BIN = HOME / ".local/share/codex-ecosystem/bin/codex"
WORKER = ROOT / "blueprints/us-equities/workers/native_worker.py"
NS = ["pasta", "--config-net", "-T", "none", "-U", "none", "-t", "none", "-u", "none", "--no-map-gw", "--quiet",
      "--", "unshare", "--mount", "--pid", "--fork", "--mount-proc", "bash", str(HERE / "iso_ns.sh")]
ISO_TOML = """[features]
hooks = false
plugin_hooks = false
apps = false

[analytics]
enabled = false

[otel]
exporter = "none"
metrics_exporter = "none"
"""
CTX_TOML = ISO_TOML + """
[marketplaces.context-mode]
source_type = "git"
source = "https://github.com/mksglu/context-mode.git"

[plugins."context-mode@context-mode"]
enabled = true
"""
NP_TOML = ISO_TOML.replace("apps = false\n", "apps = false\nplugins = false\nremote_plugin = false\n"
                                                      "skill_mcp_dependency_install = false\n")
STAGES = {"bare": "bare", "events": "bare", "ctxmode": "ctxmode", "bare-np": "bare"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def real_codex_exec() -> int:
    out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout
    n = 0
    for line in out.splitlines():
        argv = line.split()[1:]
        if len(argv) > 2 and Path(argv[0]).name == "node":
            argv = argv[1:]
        if len(argv) > 1 and Path(argv[0]).name in ("codex", "codex.js") and argv[1] == "exec":
            n += 1
    return n


def wait_for_slot(log: list) -> None:
    for _ in range(120):
        n = real_codex_exec()
        log.append({"at": now(), "real_codex_exec": n})
        if n < 2:
            return
        time.sleep(10)
    raise SystemExit("codex exec slot never freed")


def stage_dir(name: str) -> Path:
    return R3 / name


def make_stage(name: str) -> None:
    s = stage_dir(name)
    if s.exists():
        raise SystemExit(f"stage {s} exists; refusing to reuse")
    for sub in ("codex-home", "ws", "out"):
        (s / sub).mkdir(parents=True)
    (s / "codex-home/auth.json").touch()  # empty placeholder; the sign-in is bind-mounted read-only inside
    (s / "codex-home/config.toml").write_text({"ctxmode": CTX_TOML, "bare-np": NP_TOML}.get(name, ISO_TOML))
    if name == "ctxmode":
        src = HOME / ".codex/plugins/cache/context-mode/context-mode/1.0.169"
        shutil.copytree(src, s / "codex-home/plugins/cache/context-mode/context-mode/1.0.169", symlinks=True)
        for f in ("engine-receipt.json", "deerflow-native-receipt.json"):
            shutil.copy2(CACHE / "c4-ws" / f, s / "ws" / f)


def ns(name: str, argv: list[str], timeout: int) -> dict:
    t0 = time.time()
    p = subprocess.run(["timeout", "--signal=TERM", "--kill-after=10s", f"{timeout}s", *NS,
                        str(stage_dir(name)), STAGES[name], "--", *argv],
                       capture_output=True, text=True, cwd="/tmp")
    return {"exit_code": p.returncode, "seconds": round(time.time() - t0, 2), "stdout": p.stdout[-6000:],
            "stderr_tail": [ln for ln in p.stderr.splitlines() if "IPv6" not in ln][-15:]}


class Listener:
    def __init__(self):
        self.token = "r3-listener-" + secrets.token_hex(6)
        token = self.token.encode()

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(token)

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


def parse_lines(text: str) -> dict:
    out = {}
    for ln in text.splitlines():
        try:
            d = json.loads(ln)
            out[d["check"]] = d["result"]
        except (json.JSONDecodeError, KeyError):
            pass
    return out


def step_controls_and_worker(listener: Listener, rec: dict, with_worker: bool, stage: str = "bare") -> None:
    env = {"HOME": str(HOME), "PATH": f"{HOME}/.local/share/codex-ecosystem/bin:/usr/bin:/bin"}
    ctl = [str(HERE / "iso_controls.sh"), str(listener.port), listener.token]
    o = subprocess.run(["env", "-i", *[f"{k}={v}" for k, v in env.items()], "bash", *ctl], capture_output=True, text=True)
    rec["controls_outside"] = parse_lines(o.stdout)
    i = ns(stage, ["bash", *ctl], 60)
    rec["controls_inside"] = parse_lines(i["stdout"])
    rec["controls_inside_run"] = {k: i[k] for k in ("exit_code", "seconds", "stderr_tail")}
    rec["controls_differ"] = {k: [rec["controls_outside"].get(k), rec["controls_inside"].get(k)]
                              for k in sorted(set(rec["controls_outside"]) | set(rec["controls_inside"]))}
    if not with_worker:
        return
    s = stage_dir(stage)
    prompt = s / "out/worker-iso.prompt"
    prompt.write_text(
        "Isolation probe. Use shell commands and report what happens; do not change files outside this workspace.\n"
        "1) Run `echo sandbox-ok`, `id -un` and `ls -A ~ ~/.codex`.\n"
        "2) Find the Context Mode MCP server: search for a file named start.mjs under your home directory "
        "(for example `find ~ -maxdepth 9 -name start.mjs`), and check `command -v mcporter`.\n"
        "3) If you find start.mjs, run it with `timeout 5 node <path> </dev/null`; if mcporter exists, run "
        "`mcporter list`.\n"
        f"4) Run `curl -s --max-time 3 http://127.0.0.1:{listener.port}/`.\n"
        "5) List the MCP servers and MCP tools available to you in this session.\n"
        "Reply with one JSON object: for each step, the commands you ran, their exit codes and a one-line result.\n")
    rec["worker_slot_checks"] = []
    wait_for_slot(rec["worker_slot_checks"])
    rec["worker_started_at"] = now()
    rec["worker_run"] = ns(stage, [str(PY), str(WORKER), "run", "--codex-bin", str(SDK_BIN),
                                    "--codex-home", str(HOME / ".codex"), "--workspace", str(s / "ws"),
                                    "--prompt", str(prompt), "--receipt", str(s / "out/worker-iso.json"),
                                    "--turn-deadline-seconds", "300", "--sandbox", "workspace-write",
                                    "--approval-mode", "deny_all"], 420)
    rec["worker_finished_at"] = now()


def main() -> int:
    step = sys.argv[1]
    RUNS.mkdir(parents=True, exist_ok=True)
    rec: dict = {"step": step, "started_at": now()}
    if step == "stage":
        for n in ("bare", "events", "ctxmode"):
            make_stage(n)
        rec["stages"] = sorted(p.name for p in R3.iterdir() if p.is_dir() and p.name != "runs")
    elif step == "controls":
        lst = Listener()
        try:
            step_controls_and_worker(lst, rec, with_worker=False)
        finally:
            lst.stop()
    elif step == "config":
        rec["parent"] = subprocess.run(
            ["env", "-i", f"HOME={HOME}", f"PATH={HOME}/.local/share/codex-ecosystem/bin:/usr/bin:/bin", str(PY),
             str(HERE / "iso_config.py"), str(NATIVE_BIN), str(HOME / ".codex"), str(stage_dir("bare") / "ws"),
             str(RUNS / "config-parent.json"), "--no-mcp-status"], capture_output=True, text=True).returncode
        for n in ("bare", "ctxmode"):
            s = stage_dir(n)
            rec[n] = ns(n, [str(PY), str(HERE / "iso_config.py"), str(SDK_BIN), str(HOME / ".codex"),
                            str(s / "ws"), str(s / "out/config-iso.json")], 180)
    elif step == "stage-np":
        make_stage("bare-np")
    elif step == "config-np":
        s = stage_dir("bare-np")
        rec["bare-np"] = ns("bare-np", [str(PY), str(HERE / "iso_config.py"), str(SDK_BIN), str(HOME / ".codex"),
                                        str(s / "ws"), str(s / "out/config-iso.json")], 180)
    elif step in ("worker-bare", "worker-bare-np"):
        lst = Listener()
        try:
            step_controls_and_worker(lst, rec, with_worker=True, stage="bare" if step == "worker-bare" else "bare-np")
        finally:
            lst.stop()
    elif step in ("mcp-startup", "mcp-startup-np"):  # no-inference probe (late for 'bare'; fix-round for 'bare-np')
        name = "bare" if step == "mcp-startup" else "bare-np"
        s = stage_dir(name)
        rec["run"] = ns(name, [str(PY), str(HERE / "mcp_startup_probe.py"), str(SDK_BIN), str(HOME / ".codex"),
                                 str(s / "ws"), str(s / "out/mcp-startup.json")], 120)
    elif step == "events":
        s = stage_dir("events")
        rec["slot_checks"] = []
        wait_for_slot(rec["slot_checks"])
        rec["run"] = ns("events", [str(PY), str(HERE / "events_turn.py"), str(SDK_BIN), str(HOME / ".codex"),
                                   str(s / "ws"), str(s / "out/events-turn.json")], 360)
    elif step == "worker-ctxmode":
        s = stage_dir("ctxmode")
        shutil.copy2(CACHE / "runs/c4-t2.prompt", s / "out/c4-t2.prompt")
        rec["slot_checks"] = []
        wait_for_slot(rec["slot_checks"])
        rec["run"] = ns("ctxmode", [str(PY), str(WORKER), "run", "--codex-bin", str(SDK_BIN),
                                    "--codex-home", str(HOME / ".codex"), "--workspace", str(s / "ws"),
                                    "--prompt", str(s / "out/c4-t2.prompt"), "--receipt", str(s / "out/c4-t2-iso.json"),
                                    "--turn-deadline-seconds", "300", "--persistent", "--sandbox", "workspace-write",
                                    "--approval-mode", "auto_review"], 420)
        cm = s / "codex-home/context-mode"
        rec["iso_context_mode_files"] = sorted(str(p.relative_to(cm)) for p in cm.rglob("*") if p.is_file()) if cm.is_dir() else []
        rec["iso_sessions"] = sorted(p.name for p in (s / "codex-home/sessions").rglob("*.jsonl")) \
            if (s / "codex-home/sessions").is_dir() else []
    elif step == "claude-resume":
        py = CACHE / "claude-sdk/bin/python"
        p = subprocess.run(["env", "-i", f"HOME={HOME}", f"PATH={HOME}/.local/share/codex-ecosystem/bin:/usr/bin:/bin",
                            "timeout", "240", str(py), str(HERE / "claude_resume.py"),
                            "--session-file", str(CACHE / "runs/claude-interrupt.json"),
                            "--workspace", str(CACHE / "ws-claude"), "--out", str(RUNS / "claude-resume.json")],
                           capture_output=True, text=True)
        rec["exit_code"], rec["stdout"] = p.returncode, p.stdout[-800:]
    elif step == "schema":
        sd = R3 / "schema"
        g = subprocess.run([str(NATIVE_BIN), "app-server", "generate-json-schema", "--experimental", "--out", str(sd)],
                           capture_output=True, text=True)
        rec["generate_exit_code"] = g.returncode
        rec["native_version"] = subprocess.run([str(NATIVE_BIN), "--version"], capture_output=True, text=True).stdout.strip()
        p = subprocess.run([str(CACHE / "schema-check/bin/python"), str(HERE / "schema_dispatch.py"), str(sd),
                            str(RUNS / "schema-dispatch.json")], capture_output=True, text=True,
                           env={"HOME": str(HOME), "PATH": "/usr/bin:/bin",
                                "PYTHONPATH": str(V / "lib/python3.13/site-packages")})
        rec["exit_code"], rec["stdout"], rec["stderr_tail"] = p.returncode, p.stdout[-1500:], p.stderr[-1500:]
    else:
        raise SystemExit(f"unknown step {step}")
    rec["finished_at"] = now()
    (RUNS / f"step-{step}.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("controls_outside", "controls_inside")}, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
