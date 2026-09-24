#!/usr/bin/env python3
"""Review-2 fix probe (agent-sdks gap wave 2, round 3): does the parent config-snapshot request sequence export OTLP?

The round-3 parent snapshot (iso_config.py against the live $HOME/.codex, no overrides) ran with the live home's
OTLP exporters pointed at the local viewer. This probe repeats that request sequence with both OTLP endpoints
redirected to a loopback listener it starts and stops, and with hooks and plugin hooks off, so neither the live viewer
nor a hook is reached. No inference, no credential read.

Arms (each a separate native `codex app-server` process):
  parent_sequence   CODEX_HOME = live home; initialize, config/read, hooks/list, skills/list (as iso_config.py
                    with --no-mcp-status); no thread.
  positive_control  CODEX_HOME = a fresh temp home (hooks, plugins, remote plugins, apps, analytics off); initialize,
                    config/read, thread/start (no turn, so no inference).
Detection: an arm "exports" if the listener receives any HTTP request between that arm's start and FLUSH seconds after
its process exits. The positive control shows whether this binary/config posts anything at all to the redirect.
Usage: otel_probe.py CODEX_BIN LIVE_CODEX_HOME WORKDIR OUT
"""
from __future__ import annotations

import hashlib
import http.server
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from openai_codex.client import CodexClient, CodexConfig

FLUSH = 8.0


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Listener:
    def __init__(self) -> None:
        self.hits: list[dict] = []
        hits = self.hits

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                hits.append({"t": time.time(), "method": "POST", "path": self.path, "bytes": len(body),
                             "content_type": self.headers.get("Content-Type")})
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):  # noqa: N802
                hits.append({"t": time.time(), "method": "GET", "path": self.path, "bytes": 0, "content_type": None})
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.th.start()

    def stop(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


def call(client, method, params):
    try:
        out = client.request(method, params, response_model=Loose).model_dump(mode="json", by_alias=True)
        return {"ok": True, "keys": sorted(out)[:20], "value": out}
    except Exception as error:  # record, do not hide
        return {"ok": False, "error_type": type(error).__name__, "error": str(error)[:400]}


def otel_overrides(port: int) -> tuple[str, ...]:
    return (f'otel.exporter={{otlp-http={{endpoint="http://127.0.0.1:{port}/v1/logs",protocol="binary"}}}}',
            f'otel.metrics_exporter={{otlp-http={{endpoint="http://127.0.0.1:{port}/v1/metrics",protocol="binary"}}}}')


def arm(name: str, lst: Listener, codex_bin: str, home: Path, ws: Path, overrides: tuple[str, ...],
        thread: bool) -> dict:
    rec: dict = {"arm": name, "codex_home": str(home).replace(str(Path.home()), "$HOME"),
                 "config_overrides": list(overrides), "started_at": now()}
    t0 = time.time()
    cfg = CodexConfig(codex_bin=codex_bin, cwd=str(ws), env={"CODEX_HOME": str(home)}, config_overrides=overrides)
    calls = {}
    with CodexClient(cfg) as client:
        client.initialize()
        conf = call(client, "config/read", {"cwd": str(ws), "includeLayers": False})
        c = (conf.get("value") or {}).get("config") or {}
        rec["effective"] = {"otel": {k: (c.get("otel") or {}).get(k) for k in ("exporter", "metrics_exporter")},
                            "features": {k: (c.get("features") or {}).get(k)
                                         for k in ("hooks", "plugin_hooks", "plugins", "apps")}}
        calls["config/read"] = conf["ok"]
        if thread:
            ts = call(client, "thread/start", {"cwd": str(ws)})
            calls["thread/start"] = ts["ok"] if ts["ok"] else ts
        else:
            h = call(client, "hooks/list", {"cwds": [str(ws)]})
            calls["hooks/list"] = h["ok"]
            data = (h.get("value") or {}).get("data") or []
            rec["hooks_listed"] = sum(len((e or {}).get("hooks") or []) for e in data)
            rec["hooks_enabled_flags"] = sorted({str(x.get("enabled")) for e in data for x in (e or {}).get("hooks") or []})
            calls["skills/list"] = call(client, "skills/list", {"cwds": [str(ws)]})["ok"]
    t_exit = time.time()
    time.sleep(FLUSH)
    rec["calls"] = calls
    rec["process_seconds"] = round(t_exit - t0, 2)
    rec["hits"] = [{**h, "t_rel": round(h.pop("t") - t0, 2)} for h in [dict(x) for x in lst.hits if t0 <= x["t"]]]
    rec["exported"] = bool(rec["hits"])
    rec["finished_at"] = now()
    return rec


def main() -> int:
    codex_bin, live, work, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    work.mkdir(parents=True, exist_ok=True)
    ws = work / "ws"
    ws.mkdir(exist_ok=True)
    res = {"started_at": now(), "codex_bin_sha256": hashlib.sha256(Path(codex_bin).read_bytes()).hexdigest(),
           "flush_seconds_after_exit": FLUSH}
    lst = Listener()
    res["listener"] = f"127.0.0.1:{lst.port} (ephemeral, started and stopped by this probe)"
    try:
        ov = otel_overrides(lst.port)
        res["parent_sequence"] = arm("parent_sequence", lst, codex_bin, live, ws,
                                     ("features.hooks=false", "features.plugin_hooks=false") + ov, thread=False)
        lst.hits.clear()
        tmp_home = Path(tempfile.mkdtemp(prefix="codex-home-", dir=work))
        (tmp_home / "config.toml").write_text(
            "[features]\nhooks = false\nplugin_hooks = false\napps = false\nplugins = false\nremote_plugin = false\n"
            "skill_mcp_dependency_install = false\n\n[analytics]\nenabled = false\n")
        res["positive_control"] = arm("positive_control", lst, codex_bin, tmp_home, ws, ov, thread=True)
        res["positive_control"]["temp_home_entries"] = sorted(p.name for p in tmp_home.iterdir())
    finally:
        lst.stop()
    res["finished_at"] = now()
    text = json.dumps(res, indent=2, default=str).replace(str(Path.home()), "$HOME")
    out.write_text(text + "\n")
    print(json.dumps({k: (v.get("exported"), v.get("calls"), v.get("effective"), len(v.get("hits") or []))
                      for k, v in res.items() if isinstance(v, dict)}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
