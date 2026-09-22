#!/usr/bin/env python3
"""Retained engine probe: how the pinned simulated exchange fills a market order.

This is the evidence behind the ``market_on_open_proxy`` mapping row. It uses
four synthetic bars whose open, high, low and close are all distinct, so the
resulting fill price identifies which bar and which OHLC point was matched.

Modes:

* ``plain``    - a MARKET order submitted from ``on_bar`` for bar 0.
* ``atopen``   - the same order carrying ``TimeInForce.AT_THE_OPEN``.
* ``on_start`` - a MARKET order submitted before any bar has been processed, so
  it is already pending when bar 0 arrives.

Freshly generated UUID4 identities are replaced with ``<uuid4>`` so the retained
transcript is stable; nothing else is filtered.

Run it the way the replay runs, under the pinned interpreter and bwrap:

    bwrap --unshare-all --die-with-parent --new-session --clearenv \
      --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
      --symlink usr/lib64 /lib64 --proc /proc --dev /dev --tmpfs /tmp \
      --ro-bind "$NENV" "$NENV" --ro-bind "$REPO" /repo --chdir /repo \
      --setenv LANG C.UTF-8 --setenv PATH /usr/bin:/bin \
      --setenv PYTHONDONTWRITEBYTECODE 1 \
      "$NENV/bin/python" -I \
      /repo/blueprints/us-equities/engine-nautilus/spy-parity/probes/fill_semantics_probe.py <mode>
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from decimal import Decimal

UUID4_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
BAR_SPECS = [(100.0, 101.0, 99.0, 100.5), (200.0, 202.0, 198.0, 201.0),
             (300.0, 303.0, 297.0, 301.0), (400.0, 404.0, 396.0, 401.0)]
BASE_NS = 1_600_000_000_000_000_000
STEP_NS = 3_600_000_000_000


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return UUID4_RE.sub("<uuid4>", value) if isinstance(value, str) else value


def main(mode: str) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId,
                                       Money, OmsType, OrderSide, Price, Quantity, Symbol,
                                       TimeInForce, Venue)
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    equity = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 2,
                    Price.from_str("0.01"), 0, 0, lot_size=Quantity.from_int(1))
    bar_type = BarType.from_str("SPY.SIM-1-HOUR-LAST-EXTERNAL")
    bars = [Bar(bar_type, *[Price.from_str(f"{x:.2f}") for x in spec], Quantity.from_int(1000),
                BASE_NS + index * STEP_NS, BASE_NS + index * STEP_NS)
            for index, spec in enumerate(BAR_SPECS)]

    class Probe(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.index = -1
            self.events = []

        def _order(self):
            kwargs = {"time_in_force": TimeInForce.AT_THE_OPEN} if mode == "atopen" else {}
            return self.order_factory.market(equity.id, OrderSide.BUY, Quantity.from_int(10),
                                             **kwargs)

        def on_start(self):
            self.subscribe_bars(bar_type)
            if mode == "on_start":
                self.events.append({"event": "submit", "when": "on_start",
                                    "clock_ns": self.clock.timestamp_ns()})
                self.submit_order(self._order())

        def on_bar(self, bar):
            self.index += 1
            self.events.append({"event": "bar", "index": self.index, "ts_event": bar.ts_event,
                                "open": str(bar.open), "high": str(bar.high),
                                "low": str(bar.low), "close": str(bar.close)})
            if self.index == 0 and mode in ("plain", "atopen"):
                self.events.append({"event": "submit", "when": "on_bar[0]",
                                    "clock_ns": self.clock.timestamp_ns()})
                self.submit_order(self._order())

        def on_order_event(self, event):
            self.events.append({"event": type(event).__name__, "ts_event": event.ts_event,
                                "reason": str(getattr(event, "reason", "") or "") or None,
                                "last_px": str(getattr(event, "last_px", "") or "") or None})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH,
                         [Money(Decimal("100000"), usd)], base_currency=usd)
        engine.add_instrument(equity)
        engine.add_data(bars)
        probe = Probe()
        engine.add_strategy(probe)
        engine.run()
        fills = json.loads(engine.generate_order_fills_report().to_json(orient="records"))
        return {"probe": "fill_semantics", "mode": mode,
                "engine_version": importlib.metadata.version("nautilus_trader"),
                "python": sys.version.split()[0],
                "bar_specs": [{"index": i, "open": s[0], "high": s[1], "low": s[2], "close": s[3]}
                              for i, s in enumerate(BAR_SPECS)],
                "events": probe.events,
                "fills": [{k: f.get(k) for k in ("side", "quantity", "filled_qty", "avg_px",
                                                 "status", "time_in_force", "ts_init", "ts_last")}
                          for f in fills]}
    finally:
        engine.dispose()


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode not in ("plain", "atopen", "on_start"):
        raise SystemExit("mode must be plain, atopen or on_start")
    print(json.dumps(scrub(main(mode)), indent=2, sort_keys=True))
