"""Read-only live manifest of an adaptive paper run: decisions, intents, fills, risk.

Serves on loopback only:

- ``/``            a page that refreshes every two seconds;
- ``/api/state``   the same state as JSON;
- ``/metrics``     Prometheus text for the local Prometheus/Grafana stack.

Sources, all read-only: the run's ``--live-dir`` (``events.jsonl`` from
``runner.py --live-dir`` and NautilusTrader's own JSON log under ``nautilus/``), the
durable ledger (``sqlite3`` ``mode=ro``) and the STOP file. It never talks to the broker,
never writes a ledger, and never shows the account id, its fingerprint or balances: the
ledger holds deltas from the baseline, not the balance, and account identifiers are
redacted from log lines.

  python3 live_manifest.py --live-dir ~/.local/state/native-agent-stack/alpaca-paper/live/<trial>
"""
from __future__ import annotations

import argparse
import collections
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
import time

HERE = Path(__file__).resolve().parent
STATE_ROOT = Path.home() / ".local/state/native-agent-stack/alpaca-paper"
TAIL_BYTES = 2_000_000
ACCOUNT_ID = re.compile(r"ALPACA-PAPER-[0-9a-f]{8,64}|\b[0-9a-f]{64}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
# NautilusTrader logs every AccountState at INFO with the account's balances and margins.
BALANCES = re.compile(r"(balances|margins)=\[[^\]]*\]")


def redact(text):
    return ACCOUNT_ID.sub("[redacted]", BALANCES.sub(r"\1=[redacted]", str(text)))


def tail_jsonl(path, limit):
    """Last ``limit`` parseable JSON lines of a file, reading at most TAIL_BYTES."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            lines = f.read().splitlines()
    except OSError:
        return []
    if size > TAIL_BYTES:
        lines = lines[1:]
    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def find_ledger(state_root):
    ledgers = sorted(Path(state_root).glob("*/adaptive/ledger.sqlite3"), key=lambda p: p.stat().st_mtime)
    return ledgers[-1] if ledgers else None


def read_ledger(path):
    if path is None:
        return {"available": False}
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        db.row_factory = sqlite3.Row
        try:
            meta = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM meta")}
            intents = [dict(r) for r in db.execute(
                "SELECT client_id, symbol, side, qty, limit_price, status, filled_qty, average_price "
                "FROM intents ORDER BY rowid DESC LIMIT 200")]
            # every trial this ledger has run, not only the latest 200 rows shown
            intent_statuses = dict(db.execute("SELECT status, COUNT(*) FROM intents GROUP BY status").fetchall())
            positions = [dict(r) for r in db.execute("SELECT symbol, qty, cost_basis FROM positions")]
            events = [{"kind": r["kind"], "client_id": r["client_id"]} for r in db.execute(
                "SELECT kind, client_id FROM events ORDER BY id DESC LIMIT 50")]
            requests = db.execute("SELECT COUNT(*) FROM requests WHERE at > ?", (time.time() - 60,)).fetchone()[0]
        finally:
            db.close()
        limits = json.loads(meta["limits"]) if meta.get("limits") else None
        trial_start = float(meta.get("trial_start") or 0)
    except (sqlite3.Error, ValueError) as exc:
        return {"available": False, "error": type(exc).__name__}
    return {"available": True, "trial_id": meta.get("trial_id"), "halted_reason": meta.get("halted_reason") or None,
            "cash_delta_usd": meta.get("cash_delta"), "realized_usd": meta.get("realized"),
            "realized_loss_usd": meta.get("realized_loss"), "peak_pnl_usd": meta.get("peak_pnl"),
            "limits": limits, "intent_statuses": intent_statuses,
            "requests_last_minute": requests, "intents": intents, "positions": positions, "events": events,
            "trial_start": trial_start}


def summarize_events(rows):
    decisions = [r for r in rows if r.get("type") == "decision"]
    intents = [r for r in rows if r.get("type") == "intent"]
    latest = decisions[-1] if decisions else None
    return {"counts": dict(collections.Counter(r.get("type") for r in rows)),
            "latest_decision": latest,
            "regimes": dict(collections.Counter(d.get("regime") for d in decisions)),
            "strategies": dict(collections.Counter(i.get("strategy") for i in intents)),
            "recent": rows[-60:][::-1]}


def nautilus_log(live_dir, limit=80):
    files = sorted((Path(live_dir) / "nautilus").glob("*.json*"), key=lambda p: p.stat().st_mtime) if live_dir else []
    if not files:
        return []
    rows = tail_jsonl(files[-1], limit)
    return [{"timestamp": r.get("timestamp"), "level": r.get("level"), "component": r.get("component"),
             "message": redact(r.get("message", ""))[:400]} for r in rows][::-1]


def state(live_dir, state_root, stop_file):
    events = tail_jsonl(Path(live_dir) / "events.jsonl", 5000) if live_dir else []
    return {"generated_at": time.time(), "endpoint": "paper", "stop_present": Path(stop_file).exists(),
            "live_dir": Path(live_dir).name if live_dir else None,
            "ledger": read_ledger(find_ledger(state_root)), "events": summarize_events(events),
            "nautilus_log": nautilus_log(live_dir)}


def metrics(s):
    ledger, ev = s["ledger"], s["events"]
    out = ["# TYPE adaptive_paper_up gauge", "adaptive_paper_up 1",
           "# TYPE adaptive_paper_stop_present gauge", f"adaptive_paper_stop_present {int(s['stop_present'])}",
           "# TYPE adaptive_paper_events gauge"]
    for kind, n in sorted(ev["counts"].items(), key=lambda kv: str(kv[0])):
        out.append(f'adaptive_paper_events{{type="{kind}"}} {n}')
    out.append("# TYPE adaptive_paper_intents_by_strategy gauge")
    for name, n in sorted(ev["strategies"].items(), key=lambda kv: str(kv[0])):
        out.append(f'adaptive_paper_intents_by_strategy{{strategy="{name}"}} {n}')
    latest = ev["latest_decision"] or {}
    out.append("# TYPE adaptive_paper_regime gauge")
    for regime in ("trend", "range", "risk_off", "unavailable"):
        out.append(f'adaptive_paper_regime{{regime="{regime}"}} {int(latest.get("regime") == regime)}')
    if latest.get("effective_leverage") is not None:
        out += ["# TYPE adaptive_paper_effective_leverage gauge",
                f"adaptive_paper_effective_leverage {float(latest['effective_leverage'])}"]
    if ledger.get("available"):
        for key in ("cash_delta_usd", "realized_usd", "realized_loss_usd", "peak_pnl_usd"):
            if ledger.get(key) is not None:
                out += [f"# TYPE adaptive_paper_{key} gauge", f"adaptive_paper_{key} {float(ledger[key])}"]
        out.append("# TYPE adaptive_paper_ledger_intents gauge")
        for status, n in sorted(ledger["intent_statuses"].items()):
            out.append(f'adaptive_paper_ledger_intents{{status="{status}"}} {n}')
        out += ["# TYPE adaptive_paper_open_positions gauge",
                f"adaptive_paper_open_positions {sum(1 for p in ledger['positions'] if float(p['qty']))}",
                "# TYPE adaptive_paper_halted gauge", f"adaptive_paper_halted {int(bool(ledger['halted_reason']))}",
                "# TYPE adaptive_paper_rest_requests_last_minute gauge",
                f"adaptive_paper_rest_requests_last_minute {ledger['requests_last_minute']}"]
    return "\n".join(out) + "\n"


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Paper Live Manifest</title>
<style>
:root{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--ok:#1f7a4d;--bad:#b3261e;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#9a998f;--line:#2f2e2a;--ok:#5cc28f;--bad:#f2867d;--card:#1e1e1c}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:18px 0 6px}
.muted{color:var(--muted)}.ok{color:var(--ok)}.bad{color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 10px}
.card b{display:block;font-size:18px;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;white-space:nowrap;font-size:13px}
code{font-size:12px}
</style></head><body><main>
<h1>Paper live manifest</h1><div class="muted" id="sub">loading...</div>
<div class="grid" id="cards"></div>
<h2>Latest decision</h2><div class="card scroll" id="decision"></div>
<h2>Ledger intents (orders)</h2><div class="scroll"><table id="intents"></table></div>
<h2>Decision and intent stream</h2><div class="scroll"><table id="stream"></table></div>
<h2>NautilusTrader engine log</h2><div class="scroll"><table id="nlog"></table></div>
</main><script>
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const t=x=>x?new Date(x*1000).toLocaleTimeString():"";
function table(id,cols,rows){document.getElementById(id).innerHTML="<tr>"+cols.map(c=>"<th>"+esc(c[0])+"</th>").join("")+"</tr>"+
 rows.map(r=>"<tr>"+cols.map(c=>"<td>"+esc(c[1](r))+"</td>").join("")+"</tr>").join("")}
async function tick(){try{const s=await (await fetch("api/state")).json();const L=s.ledger||{},E=s.events||{};
document.getElementById("sub").innerHTML="Paper endpoint · run "+esc(s.live_dir||"none")+" · ledger trial "+esc(L.trial_id||"?")+
 " · updated "+t(s.generated_at)+(s.stop_present?' · <span class="bad">STOP hold present</span>':' · <span class="ok">no STOP hold</span>');
const card=(k,v,cls)=>'<div class="card"><span class="muted">'+esc(k)+'</span><b class="'+(cls||"")+'">'+esc(v)+"</b></div>";
document.getElementById("cards").innerHTML=[card("Decisions",(E.counts||{}).decision||0),card("Intents",(E.counts||{}).intent||0),
 card("Regime",(E.latest_decision||{}).regime||"-"),card("Cash delta USD",L.cash_delta_usd??"-"),card("Realized USD",L.realized_usd??"-"),
 card("Realized loss USD",L.realized_loss_usd??"-"),card("Halt",L.halted_reason||"none",L.halted_reason?"bad":"ok"),
 card("REST req/min",L.requests_last_minute??"-")].join("");
const d=E.latest_decision;document.getElementById("decision").innerHTML=d?("<div class='muted'>"+t(d.at)+" · leverage "+esc(d.effective_leverage)+"</div>"+
 "<div>targets <code>"+esc(JSON.stringify(d.targets))+"</code></div><div>exits <code>"+esc(JSON.stringify(d.exits))+"</code></div>"+
 "<div>signals <code>"+esc(JSON.stringify((d.signals||[]).slice(0,12)))+"</code></div>"):"no decision yet";
table("intents",[["client id",r=>r.client_id],["symbol",r=>r.symbol],["side",r=>r.side],["qty",r=>r.qty],["limit",r=>r.limit_price],
 ["status",r=>r.status],["filled",r=>r.filled_qty],["avg price",r=>r.average_price]],L.intents||[]);
table("stream",[["time",r=>t(r.at)],["type",r=>r.type],["regime / symbol",r=>r.regime||r.symbol],["strategy / side",r=>r.strategy||r.side],
 ["detail",r=>r.type==="decision"?JSON.stringify(r.targets):(r.reason||"")]],E.recent||[]);
table("nlog",[["time",r=>(r.timestamp||"").slice(11,23)],["level",r=>r.level],["component",r=>r.component],["message",r=>r.message]],s.nautilus_log||[]);
}catch(e){document.getElementById("sub").textContent="manifest unavailable: "+e}}
tick();setInterval(tick,2000);
</script></body></html>"""


def serve(args):
    stop_file = args.state_root / "STOP"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            return

        def do_GET(self):
            if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                self.send_error(403)  # loopback names only (DNS rebinding)
                return
            if self.path not in ("/", "/index.html", "/api/state", "/metrics"):
                self.send_error(404)
                return
            code = 200
            try:
                live_dir = args.live_dir or newest_live_dir(args.state_root / "live")
                if self.path == "/api/state":
                    body, ctype = json.dumps(state(live_dir, args.state_root, stop_file), default=str).encode(), "application/json"
                elif self.path == "/metrics":
                    body, ctype = metrics(state(live_dir, args.state_root, stop_file)).encode(), "text/plain; version=0.0.4"
                else:
                    body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                code, body, ctype = 500, json.dumps({"error": type(exc).__name__}).encode(), "application/json"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


def newest_live_dir(root):
    dirs = sorted((d for d in Path(root).glob("*") if d.is_dir()), key=lambda d: d.stat().st_mtime) if Path(root).is_dir() else []
    return dirs[-1] if dirs else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live-dir", type=Path, default=None, help="default: newest directory under <state-root>/live")
    ap.add_argument("--state-root", type=Path, default=STATE_ROOT)
    ap.add_argument("--port", type=int, default=17610)
    serve(ap.parse_args(argv))


if __name__ == "__main__":
    main()
