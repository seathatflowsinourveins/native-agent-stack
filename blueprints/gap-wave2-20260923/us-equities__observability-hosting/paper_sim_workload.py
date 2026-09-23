#!/usr/bin/env python3
"""Paper-runtime workload for the observability-hosting paper arm (gap wave 2, 2026-09-23).

Runs the adaptive-paper runtime's own native path (runner.run_native: NautilusTrader
2.0.0rc5 node, AdaptiveStrategy, Controller, SQLite Ledger journal) against the
repository's synthetic broker port (simulation.SimulatedPort: no networking, no
credentials, no broker or paper-account contact). Wiring mirrors
tests/test_adaptive_paper_runner.py::test_native_adaptive_policy_reaches_ledger_and_flat_reconciliation
with a longer duration. The runtime's own event sink (controller.events) is streamed to
stdout as JSON lines tagged with --mark so a log pipeline can ship it; this streaming is
added by this driver, the runtime itself has no OTLP exporter.
"""
import argparse, asyncio, json, sqlite3, sys, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
from runner import Controller, run_native, load_config  # noqa: E402
from safety import Ledger, RiskLimits  # noqa: E402
from strategies import PolicyConfig  # noqa: E402
from simulation import SimulatedPort  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--journal", required=True)
ap.add_argument("--result", required=True)
ap.add_argument("--mark", required=True)
ap.add_argument("--seconds", type=int, default=20)
a = ap.parse_args()


def emit(kind, **kw):
    print(json.dumps({"mark": a.mark, "kind": kind, "at": time.time(), **kw}, default=str), flush=True)


class StreamingEvents(list):
    def append(self, e):
        super().append(e)
        emit("runtime_event", event=e)


config, _, _ = load_config(SOURCE / "config.json")
config.update(duration_seconds=a.seconds, cleanup_seconds=5, order_timeout_seconds=1)
limits = RiskLimits(trial_seconds=a.seconds, cleanup_seconds=5)
ledger = Ledger(Path(a.journal), limits)
ledger.start_trial(time.time())
controller = Controller(ledger, time.time() + 3600, market_open=True)
controller.events = StreamingEvents()
policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                      warmup_samples=4, warmup_seconds=.06, sample_seconds=.02,
                      rebalance_seconds=.02, min_hold_seconds=.05, max_hold_seconds=.4,
                      cooldown_seconds=.05)


def price(symbol, tick):
    slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
    return Decimal("100") + min(tick, 70) * slope


port = SimulatedPort(controller, policy.symbols, price=price)
controller.port = port
emit("paper_sim_start", seconds=a.seconds, symbols=list(policy.symbols))
result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                "obsgap", config, "100000"))
ledger.close()
Path(a.result).write_text(json.dumps(result, indent=1, default=str))
db = sqlite3.connect(a.journal)
counts = {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
          for t in ("intents", "requests", "events", "positions", "marks", "trials")}
db.close()
emit("paper_sim_end", status=result.get("status"), flat=result.get("flat"),
     native_fill_events=result.get("native_fill_events"), journal_counts=counts)
sys.exit(0 if result.get("status") == "passed" else 3)
