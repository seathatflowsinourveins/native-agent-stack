#!/usr/bin/env python3
"""Replay a retained adaptive-paper trial's order decisions through NautilusTrader's
BacktestEngine, fed with historical Alpaca SIP quotes, and compare simulated fills
against the trial's paper fills.

  python replay_compare.py \
    --trial ../adaptive-paper/trials/20260923g-main-passed \
    --env-file "$PAPER_ENV_FILE" \
    --pages "$PRIVATE_CACHE_DIR/pages" \
    --out "$PRIVATE_CACHE_DIR/run" \
    --receipt receipts/20260923g-main-passed.json

Data fetch is GET-only against the existing Alpaca data path (SIP feed), reusing the
mover-early-entry `Fetcher` page-retention pattern: every response is kept gzip'd with
a sha256 ledger under --pages, and --replay re-derives the same run from those pages
without a new network request (and without opening any credential file -- see main()).
Replay uses the same fee/fill-model configuration as the accepted baseline in
engine-nautilus/equity-replay (native default `FillModel`, `FixedFeeModel`,
`book_type=L1_MBP`): Alpaca equities are commission-free, and the default fill model
matches limit orders against the fed L1 quote book with no synthetic slippage or
partial-fill assumption at zero latency.

This is a single trial with five orders (four filled, one canceled). It measures
paper/simulated fill agreement for that one window, at a declared latency-sensitivity
sweep (see LATENCY_SWEEP_MS). It is not a fill-rate or slippage calibration and must
not be read as one.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTIVE_PAPER = HERE.parents[0] / "adaptive-paper"
DATA = "https://data.alpaca.markets"
UTC = timezone.utc
VENUE_NAME = "SIM"
FILL_MODEL_NOTE = ("native default nautilus_trader.execution.FillModel(); matches limit orders "
                    "against the fed L1 top-of-book quotes deterministically (no probabilistic "
                    "slippage or partial-fill draw), the same baseline configuration used by "
                    "engine-nautilus/equity-replay's zero-fee case")
DEFAULT_ORDER_TIMEOUT_SECONDS = 10  # only used when no config match and no recorded cancel request exist
LATENCY_SWEEP_MS = (0, 5, 50, 70, 100, 250, 650, 1000)


# ---------------------------------------------------------------------------
# Small helpers (timestamps, hashing, JSON I/O)
# ---------------------------------------------------------------------------

def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_path(path: Path) -> str:
    return digest_bytes(Path(path).read_bytes())


def chmod_private_dir(path: Path) -> None:
    """mkdir's `mode=` argument is masked by the process umask; chmod explicitly
    so private cache/output directories are 0700 regardless of the caller's umask."""
    os.chmod(path, 0o700)


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")
    os.chmod(path, 0o600)


_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(?:Z|\+00:00)")


def ts_ns(value: str) -> int:
    """Parse an RFC3339 UTC timestamp (Alpaca's `Z` form or the broker readback's
    `+00:00` form) to integer nanoseconds, without floating-point rounding. The
    `Z`-only regex is adapted from alpaca-historical/collect.py; the `+00:00`
    alternative is required by the retained trial's broker-orders.json."""
    match = _TS_RE.fullmatch(value)
    if not match:
        raise ValueError(f"invalid_timestamp:{value!r}")
    parsed = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**9 + int((match[2] or "").ljust(9, "0"))


def ns_to_iso(value: int) -> str:
    seconds, ns = divmod(value, 10**9)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{ns:09d}Z"


def epoch_seconds_to_ns(value: float) -> int:
    """Host-clock float seconds (paper-output.json's `requests[].timestamp`) to integer
    nanoseconds. The float carries microsecond resolution in the source, so round to
    the nearest microsecond before scaling to avoid spurious sub-microsecond noise."""
    return int(round(value * 1e6)) * 1000


def bps(sim_price, paper_price):
    if sim_price is None or paper_price is None or paper_price == 0:
        return None
    return float((Decimal(str(sim_price)) / Decimal(str(paper_price)) - 1) * 10000)


def signed_slippage_bps(side, fill_price, limit_price):
    """Side-aware slippage of a fill against its limit price, in bps, where positive
    always means worse for the trader (paid more on a BUY, received less on a SELL)."""
    if fill_price is None or limit_price is None:
        return None
    limit_dec = Decimal(str(limit_price))
    if limit_dec == 0:
        return None
    raw = (Decimal(str(fill_price)) - limit_dec) / limit_dec * 10000
    return float(raw if side == "BUY" else -raw)


# ---------------------------------------------------------------------------
# GET with page retention/replay (adapted from mover-early-entry/mover_scan.py's
# Fetcher; reimplemented locally to avoid pulling that module's numpy/rules/
# sessions_io dependency chain into the pinned Nautilus-only runtime).
# ---------------------------------------------------------------------------

def req_key(path: str, params: dict) -> str:
    return hashlib.sha256((path + "?" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:32]


class PageFetcher:
    """GET-with-retention fetcher. `--replay` never opens the ledger file for
    writing and never requires headers/credentials; every page it serves in replay
    mode must already be present, keyed by request, in the retained page cache.
    `page_events` records, per served page, whether it came from `network` or
    `cache`, so replay reproducibility claims are backed by per-page evidence
    rather than an aggregate statement."""

    def __init__(self, pages: Path, headers=None, replay: bool = False):
        self.pages, self.headers, self.replay = Path(pages), headers, replay
        self.ledger = {}
        self.page_events: list[dict] = []
        lpath = self.pages / "ledger.jsonl"
        if lpath.exists():
            for line in lpath.read_text().splitlines():
                rec = json.loads(line)
                self.ledger[rec["key"]] = rec
        if not replay:
            self.pages.mkdir(parents=True, exist_ok=True)
            chmod_private_dir(self.pages)

    @property
    def from_cache(self) -> int:
        return sum(1 for e in self.page_events if e["source"] == "cache")

    @property
    def from_network(self) -> int:
        return sum(1 for e in self.page_events if e["source"] == "network")

    def get(self, base: str, path: str, params: dict):
        token = None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            key = req_key(base + path, q)
            if self.replay and key not in self.ledger:
                raise SystemExit(f"replay requested but no retained page for {path} (key {key}); "
                                  f"re-run without --replay once to populate the page cache")
            if self.replay or key in self.ledger:
                rec = self.ledger[key]
                raw = gzip.decompress((self.pages / rec["file"]).read_bytes())
                if digest_bytes(raw) != rec["sha256"]:
                    raise SystemExit(f"page hash mismatch {rec['file']}")
                status = rec["status"]
                self.page_events.append({"key": key, "source": "cache"})
            else:
                url = base + path + "?" + urllib.parse.urlencode(q)
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as r:
                        raw, status = r.read(), r.status
                except urllib.error.HTTPError as exc:
                    raw, status = exc.read() or b"{}", exc.code
                name = f"{key}.json.gz"
                with gzip.open(self.pages / name, "wb", compresslevel=6) as f:
                    f.write(raw)
                rec = {"key": key, "file": name, "path": path, "status": status,
                       "sha256": digest_bytes(raw), "bytes": len(raw)}
                self.ledger[key] = rec
                # Opened and closed per write (not held open for the fetcher's lifetime).
                with (self.pages / "ledger.jsonl").open("a") as lf:
                    lf.write(json.dumps(rec) + "\n")
                self.page_events.append({"key": key, "source": "network"})
            if status != 200:
                raise SystemExit(f"GET {path} returned {status}")
            body = json.loads(raw)
            yield body
            token = body.get("next_page_token") if isinstance(body, dict) else None
            if not token:
                return


# ---------------------------------------------------------------------------
# Paper trial parsing (pure, offline-testable)
# ---------------------------------------------------------------------------

def load_paper_orders(broker_orders: dict) -> list[dict]:
    """Normalize broker-orders.json's read-only order readback into the fields
    needed to replay decisions: symbol, side, qty, order type, limit price and
    timestamps. Raises on anything the replay cannot faithfully reconstruct: a
    non-limit order type, a time-in-force other than DAY (the replay always
    submits TimeInForce.DAY), or a fractional quantity (refused, not truncated)."""
    orders = []
    for raw in broker_orders["orders"]:
        if raw["type"] != "limit":
            raise ValueError(f"unsupported_order_type:{raw['type']}")
        tif = raw["time_in_force"].upper()
        if tif != "DAY":
            raise ValueError(f"unsupported_time_in_force:{tif}")
        qty_dec = Decimal(raw["qty"])
        if qty_dec != qty_dec.to_integral_value():
            raise ValueError(f"fractional_qty_not_supported:{raw['qty']}")
        filled_qty_dec = Decimal(raw["filled_qty"])
        if filled_qty_dec != filled_qty_dec.to_integral_value():
            raise ValueError(f"fractional_filled_qty_not_supported:{raw['filled_qty']}")
        orders.append({
            "client_order_id": raw["client_order_id"],
            "symbol": raw["symbol"],
            "side": raw["side"].upper(),
            "qty": int(qty_dec),
            "limit_price": str(Decimal(raw["limit_price"])),
            "time_in_force": tif,
            "status": raw["status"],
            "filled_qty": int(filled_qty_dec),
            "filled_avg_price": None if raw["filled_avg_price"] in (None, "None") else str(Decimal(raw["filled_avg_price"])),
            "submitted_at_ns": ts_ns(raw["submitted_at"]),
            "filled_at_ns": ts_ns(raw["filled_at"]) if raw.get("filled_at") else None,
        })
    orders.sort(key=lambda o: o["submitted_at_ns"])
    return orders


def parse_cancel_request_ns(paper_output: dict) -> list[int]:
    """Cancel-request host-clock timestamps recorded in paper-output.json's
    `requests` log, sorted ascending. These are the runner's own cancel-submit
    instants -- not a derived/approximated time."""
    return sorted(epoch_seconds_to_ns(r["timestamp"]) for r in paper_output.get("requests", [])
                  if r.get("kind") == "cancel")


def resolve_order_timeout_seconds(ingest_receipt: dict) -> tuple[int, str]:
    """Find the adaptive-paper config file whose sha256 matches this trial's
    ingest-receipt config_sha256 and read its order_timeout_seconds, so the
    fallback cancel time (submit + timeout) uses the config this trial actually
    ran with, not an assumed constant. Falls back to DEFAULT_ORDER_TIMEOUT_SECONDS
    with an explicit "source" marker if no config file matches."""
    config_sha256 = ingest_receipt.get("config_sha256")
    if config_sha256:
        for cfg_path in sorted(ADAPTIVE_PAPER.glob("config*.json")):
            if cfg_path.is_file() and digest_path(cfg_path) == config_sha256:
                cfg = json.loads(cfg_path.read_text())
                if "order_timeout_seconds" in cfg:
                    return int(cfg["order_timeout_seconds"]), f"matched_config:{cfg_path.name}"
    return DEFAULT_ORDER_TIMEOUT_SECONDS, "default_fallback_no_config_match"


def resolve_cancel_timestamps(paper_orders: list[dict], paper_output: dict, order_timeout_seconds: int) -> dict:
    """Resolve each canceled paper order's actual cancel time, in priority order:
    (1) a recorded cancel request in paper-output.json's `requests` log, matched
    to canceled orders in submission order when the counts agree (unambiguous for
    the common single-cancel case, and this trial has exactly one of each); (2)
    submitted_at + order_timeout_seconds, the runner's own cancel-on-timeout rule,
    when no recorded cancel request is available or counts disagree. Both branches
    use a real, declared, non-negotiated cancel instant -- never a successor
    order's submit time."""
    canceled = [o for o in paper_orders if o["status"] == "canceled"]
    cancel_reqs = parse_cancel_request_ns(paper_output)
    resolved = {}
    if canceled and len(canceled) == len(cancel_reqs):
        for order, cancel_ns in zip(canceled, cancel_reqs):
            resolved[order["client_order_id"]] = {"cancel_ts_ns": cancel_ns, "source": "recorded_cancel_request"}
    else:
        for order in canceled:
            resolved[order["client_order_id"]] = {
                "cancel_ts_ns": order["submitted_at_ns"] + order_timeout_seconds * 10**9,
                "source": "submit_plus_order_timeout_seconds",
            }
    return resolved


def build_decisions(paper_orders: list[dict], cancel_resolution: dict | None = None) -> list[dict]:
    """Turn the paper order sequence into submit/cancel decisions. A canceled
    order's cancel decision is timed at its resolved cancel timestamp (see
    resolve_cancel_timestamps) when one is supplied; a canceled order with no
    entry in `cancel_resolution` gets no cancel decision at all (it is left open
    for the strategy's on_stop() end-of-window cleanup) rather than an inferred
    successor-order time."""
    cancel_resolution = cancel_resolution or {}
    decisions = [{"ts_ns": o["submitted_at_ns"], "action": "submit", "order": o} for o in paper_orders]
    for o in paper_orders:
        if o["status"] == "canceled" and o["client_order_id"] in cancel_resolution:
            decisions.append({"ts_ns": cancel_resolution[o["client_order_id"]]["cancel_ts_ns"],
                               "action": "cancel", "order": o})
    decisions.sort(key=lambda d: (d["ts_ns"], 0 if d["action"] == "submit" else 1))
    return decisions


def fetch_window(paper_orders: list[dict], *, pad_seconds: int = 60) -> tuple[int, int]:
    starts = [o["submitted_at_ns"] for o in paper_orders]
    ends = [o["filled_at_ns"] or o["submitted_at_ns"] for o in paper_orders]
    return min(starts) - pad_seconds * 10**9, max(ends) + pad_seconds * 10**9


# ---------------------------------------------------------------------------
# Alpaca SIP historical quotes
# ---------------------------------------------------------------------------

def fetch_quotes(fetcher: PageFetcher, symbols: list[str], start_ns: int, end_ns: int, asof: str) -> dict[str, list[dict]]:
    quotes: dict[str, list[dict]] = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "start": ns_to_iso(start_ns), "end": ns_to_iso(end_ns),
              "feed": "sip", "asof": asof, "limit": 10000, "sort": "asc"}
    for body in fetcher.get(DATA, "/v2/stocks/quotes", params):
        for symbol, rows in (body.get("quotes") or {}).items():
            quotes[symbol].extend(rows)
    return quotes


def normalize_quote_rows(raw_rows: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Keep two-sided, positively priced NBBO quotes, each stamped in ns, dropping
    crossed quotes (bid > ask, which cannot be matched sanely and would let a
    limit order fill through a data artifact). Locked quotes (bid == ask) are
    valid market data and are kept. Returns (quotes, drop_counts_by_symbol)."""
    out: dict[str, list[dict]] = {}
    drop_counts: dict[str, dict] = {}
    for symbol, rows in raw_rows.items():
        kept = []
        dropped = {"one_sided_or_nonpositive": 0, "crossed": 0}
        for row in rows:
            bp, ap = row.get("bp"), row.get("ap")
            bs, asz = row.get("bs"), row.get("as")
            if not bp or not ap or bp <= 0 or ap <= 0 or not bs or not asz:
                dropped["one_sided_or_nonpositive"] += 1
                continue
            if bp > ap:
                dropped["crossed"] += 1
                continue
            # Quantize both sides to the instrument's 2-decimal price precision:
            # SIP quotes occasionally carry a shorter decimal string on one side
            # (e.g. "120.5" vs "120.50"), and QuoteTick requires equal precision.
            kept.append({"symbol": symbol, "ts_ns": ts_ns(row["t"]),
                         "bid": str(Decimal(str(bp)).quantize(Decimal("0.01"))),
                         "ask": str(Decimal(str(ap)).quantize(Decimal("0.01"))),
                         "bid_size": int(bs), "ask_size": int(asz)})
        kept.sort(key=lambda q: q["ts_ns"])
        out[symbol] = kept
        drop_counts[symbol] = dropped
    return out, drop_counts


# ---------------------------------------------------------------------------
# Comparison (pure, offline-testable)
# ---------------------------------------------------------------------------

def compare_orders(paper_orders: list[dict], sim_orders_by_id: dict[str, dict]) -> dict:
    rows = []
    for paper in paper_orders:
        sim = sim_orders_by_id.get(paper["client_order_id"])
        sim_filled_qty = sim.get("filled_qty", 0) if sim else 0
        row = {
            "client_order_id": paper["client_order_id"], "symbol": paper["symbol"], "side": paper["side"],
            "qty": paper["qty"], "limit_price": paper["limit_price"],
            "paper_status": paper["status"], "paper_filled_qty": paper["filled_qty"],
            "paper_filled": paper["filled_qty"] > 0,
            "paper_fill_price": paper["filled_avg_price"],
            "paper_fill_ts": ns_to_iso(paper["filled_at_ns"]) if paper["filled_at_ns"] else None,
            "sim_present": sim is not None,
            "sim_status": sim.get("status") if sim else None,
            "sim_filled_qty": sim_filled_qty, "sim_filled": sim_filled_qty > 0,
            "sim_reject_reason": sim.get("reject_reason") if sim else None,
            "sim_fill_price": sim.get("avg_px") if sim else None,
            "sim_fill_ts": ns_to_iso(sim["ts_last"]) if sim and sim_filled_qty else None,
            # Quantity-based agreement (not a status-string comparison) so a partial
            # fill on one side and a full/no fill on the other is scored as a real
            # disagreement rather than folded into a boolean "filled" match.
            "fill_agreement": paper["filled_qty"] == sim_filled_qty,
            "paper_slippage_vs_limit_bps": (signed_slippage_bps(paper["side"], paper["filled_avg_price"], paper["limit_price"])
                                             if paper["filled_qty"] else None),
            "sim_slippage_vs_limit_bps": (signed_slippage_bps(paper["side"], sim.get("avg_px"), paper["limit_price"])
                                           if sim and sim_filled_qty else None),
        }
        if paper["filled_qty"] and sim_filled_qty and paper["filled_at_ns"] and sim.get("ts_last") is not None:
            row["fill_price_delta_bps"] = bps(row["sim_fill_price"], row["paper_fill_price"])
            row["fill_time_delta_s"] = (sim["ts_last"] - paper["filled_at_ns"]) / 1e9
        else:
            row["fill_price_delta_bps"] = None
            row["fill_time_delta_s"] = None
        rows.append(row)

    n = len(rows)
    agreements = sum(1 for r in rows if r["fill_agreement"])
    both_filled = [r for r in rows if r["paper_filled"] and r["sim_filled"]]
    price_deltas = [abs(r["fill_price_delta_bps"]) for r in both_filled if r["fill_price_delta_bps"] is not None]
    time_deltas = [abs(r["fill_time_delta_s"]) for r in both_filled if r["fill_time_delta_s"] is not None]

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    def median(xs):
        if not xs:
            return None
        s = sorted(xs)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    aggregates = {
        "orders": n, "fill_agreements": agreements, "fill_agreement_rate": agreements / n if n else None,
        "both_filled": len(both_filled),
        "abs_fill_price_delta_bps_mean": mean(price_deltas), "abs_fill_price_delta_bps_median": median(price_deltas),
        "abs_fill_price_delta_bps_max": max(price_deltas) if price_deltas else None,
        "abs_fill_time_delta_s_mean": mean(time_deltas), "abs_fill_time_delta_s_median": median(time_deltas),
        "abs_fill_time_delta_s_max": max(time_deltas) if time_deltas else None,
    }
    return {"rows": rows, "aggregates": aggregates}


# ---------------------------------------------------------------------------
# NautilusTrader BacktestEngine replay (imports deferred; requires the pinned
# 2.0.0rc5 runtime, not needed by the pure functions above or their tests)
# ---------------------------------------------------------------------------

def run_replay(paper_orders: list[dict], quotes_by_symbol: dict[str, list[dict]], *, out_dir: Path,
                cancel_resolution: dict | None = None, latency_ns: int = 0, queue_position: bool = False) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel, StaticLatencyModel
    from nautilus_trader.model import (AccountType, BookType, ClientOrderId, Currency, Equity, InstrumentId,
                                        Money, OmsType, OrderSide, Price, Quantity, QuoteTick, Symbol,
                                        TimeInForce, Venue)
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue(VENUE_NAME)
    symbols = sorted(quotes_by_symbol)
    instruments = {}
    for symbol in symbols:
        iid = InstrumentId.from_str(f"{symbol}.{VENUE_NAME}")
        instruments[symbol] = Equity(iid, Symbol(symbol), usd, 2, Price.from_str("0.01"), 0, 0,
                                      lot_size=Quantity.from_int(1))

    decisions = build_decisions(paper_orders, cancel_resolution)
    for d in decisions:
        d["order"] = dict(d["order"], instrument_id=instruments[d["order"]["symbol"]].id)

    ticks = []
    for symbol, rows in quotes_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                                    Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                                    row["ts_ns"], row["ts_ns"]))
    ticks.sort(key=lambda t: t.ts_event)
    if not ticks:
        raise ValueError("no_quote_ticks_fetched")

    out_dir.mkdir(parents=True, exist_ok=True)

    class ScheduledReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.decisions = decisions
            self.applied = []

        def on_start(self):
            for iid in {instruments[s].id for s in symbols}:
                self.subscribe_quotes(iid)
            # Exact scheduled submit/cancel times via native time alerts, not "on the
            # next quote of any symbol" (which could arrive up to ~257ms late for a
            # thinly-traded symbol and, worse, misattributed any observed timing gap
            # to the decision itself rather than to the polling granularity).
            for i, d in enumerate(self.decisions):
                self.clock.set_time_alert_ns(f"decision-{i}", d["ts_ns"], lambda event, d=d: self._apply(d))

        def on_stop(self):
            for order in list(self.cache.orders_open()):
                self.cancel_order(order.client_order_id)

        def _apply(self, d):
            o = d["order"]
            if d["action"] == "submit":
                order = self.order_factory.limit(
                    instrument_id=o["instrument_id"], order_side=OrderSide.BUY if o["side"] == "BUY" else OrderSide.SELL,
                    quantity=Quantity.from_int(o["qty"]), price=Price(Decimal(o["limit_price"]), 2),
                    time_in_force=getattr(TimeInForce, o["time_in_force"]), client_order_id=ClientOrderId(o["client_order_id"]))
                self.submit_order(order)
            else:
                order = self.cache.order(ClientOrderId(o["client_order_id"]))
                if order is not None and order.is_open:
                    self.cancel_order(order.client_order_id)
            # clock_ts_ns is the engine clock's time when this handler actually ran
            # (the scheduled time alert fires as soon as the clock reaches ts_ns, so
            # this is the actual application instant, not a re-statement of ts_ns).
            self.applied.append({"ts_ns": d["ts_ns"], "clock_ts_ns": self.clock.timestamp_ns(),
                                  "action": d["action"], "client_order_id": o["client_order_id"]})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    fee_model = FixedFeeModel(Money(Decimal("0"), usd))
    latency_model = StaticLatencyModel(base_latency_nanos=latency_ns) if latency_ns else None
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("10000"), usd)],
                         base_currency=usd, fee_model=fee_model, latency_model=latency_model,
                         book_type=BookType.L1_MBP, liquidity_consumption=False, queue_position=queue_position)
        for instrument in instruments.values():
            engine.add_instrument(instrument)
        engine.add_data(ticks)
        strategy = ScheduledReplay()
        engine.add_strategy(strategy)
        engine.run()

        fills_report = engine.generate_order_fills_report()
        orders_report = engine.generate_orders_report()
        fills_report.to_csv(out_dir / "fills.csv")
        orders_report.to_csv(out_dir / "orders.csv")

        # Built from live order objects (strategy.cache.orders()), not from the
        # pandas reports: ts_last/status/reject reason come straight off the order
        # and its events, with no tz-aware-column-to-int64 conversion in between.
        orders = list(strategy.cache.orders())
        sim_by_id = {}
        for order in orders:
            coid = str(order.client_order_id)
            status = str(order.status).rsplit(".", 1)[-1]
            filled_qty = int(Decimal(str(order.filled_qty))) if order.filled_qty is not None else 0
            avg_px = str(order.avg_px) if order.avg_px is not None else None
            ts_last = int(order.ts_last) if order.ts_last else None
            reject_reason = None
            if status == "REJECTED":
                events = order.events() if callable(order.events) else order.events
                for ev in events:
                    if type(ev).__name__ == "OrderRejected":
                        reject_reason = getattr(ev, "reason", None)
            sim_by_id[coid] = {"status": status, "filled_qty": filled_qty, "avg_px": avg_px,
                                "ts_last": ts_last, "reject_reason": reject_reason}

        fill_rows = json.loads(fills_report.reset_index().to_json(orient="records", default_handler=str, date_format="iso"))
        order_rows = json.loads(orders_report.reset_index().to_json(orient="records", default_handler=str, date_format="iso"))
        # init_id is a random UUID assigned per order construction; strip it before
        # hashing so the report hash reflects the run's actual results, not a
        # fresh random ID generated on every replay.
        for row in order_rows:
            row.pop("init_id", None)
        for row in fill_rows:
            row.pop("init_id", None)
        save(out_dir / "reports.json", {"fills": fill_rows, "orders": order_rows, "applied_decisions": strategy.applied})

        return {"sim_by_id": sim_by_id,
                "reports": {
                    "fills": {"rows": len(fill_rows),
                              "sha256_excluding_init_id": digest_bytes(json.dumps(fill_rows, sort_keys=True, default=str).encode())},
                    "orders": {"rows": len(order_rows),
                               "sha256_excluding_init_id": digest_bytes(json.dumps(order_rows, sort_keys=True, default=str).encode())},
                },
                "engine": {"latency_ns": latency_ns, "queue_position": queue_position, "liquidity_consumption": False}}
    finally:
        engine.dispose()


def run_latency_sweep(paper_orders: list[dict], quotes_by_symbol: dict[str, list[dict]], *, cancel_resolution: dict,
                       out_dir: Path, baseline_comparison: dict) -> list[dict]:
    """Run the declared latency-sensitivity sweep (LATENCY_SWEEP_MS) and report
    agreement/deltas at each point. This is a sensitivity check, not a calibration:
    it shows how the zero-latency default's disagreement on orders 4/5 changes as
    StaticLatencyModel's broker/network latency assumption increases, nothing more."""
    sweep = []
    for ms in LATENCY_SWEEP_MS:
        if ms == 0:
            comparison = baseline_comparison
        else:
            result = run_replay(paper_orders, quotes_by_symbol, out_dir=out_dir / f"{ms}ms",
                                 cancel_resolution=cancel_resolution, latency_ns=ms * 10**6)
            comparison = compare_orders(paper_orders, result["sim_by_id"])
        agg = comparison["aggregates"]
        sweep.append({
            "latency_ms": ms,
            "fill_agreements": agg["fill_agreements"], "orders": agg["orders"],
            "fill_agreement_rate": agg["fill_agreement_rate"], "both_filled": agg["both_filled"],
            "abs_fill_price_delta_bps_mean": agg["abs_fill_price_delta_bps_mean"],
            "abs_fill_time_delta_s_mean": agg["abs_fill_time_delta_s_mean"],
            "disagreeing_client_order_ids": sorted(r["client_order_id"] for r in comparison["rows"] if not r["fill_agreement"]),
        })
    return sweep


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def redact_argv(argv: list[str]) -> list[str]:
    """Redact the values of flags that can carry a private credential-file path or
    another host-specific private path (page cache, output directory). Flag names
    are kept (so the recorded argv still shows what was passed) but no personal
    path or session identifier ever enters the committed receipt."""
    redact_flags = {"--env-file", "--env-file-from-file", "--pages", "--out"}
    out = []
    redact_next = False
    for arg in argv:
        if redact_next:
            out.append("<redacted>")
            redact_next = False
            continue
        if "=" in arg and arg.split("=", 1)[0] in redact_flags:
            out.append(arg.split("=", 1)[0] + "=<redacted>")
            continue
        out.append(arg)
        if arg in redact_flags:
            redact_next = True
    return out


def main(argv=None) -> int:
    started_utc = datetime.now(UTC).isoformat()
    raw_argv = list(argv if argv is not None else sys.argv[1:])

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trial", type=Path, required=True, help="Retained adaptive-paper trial directory")
    ap.add_argument("--env-file", type=Path, help="Private paper-credential env file (never printed); "
                                                    "not required in --replay mode")
    ap.add_argument("--env-file-from-file", type=Path,
                     help="A file whose sole line is the private env file's path (for shells that must not "
                          "spell the credential store path directly in a command); not required in --replay mode")
    ap.add_argument("--pages", type=Path, required=True, help="Private page cache (gzip + sha256 ledger)")
    ap.add_argument("--out", type=Path, required=True, help="Fresh private output directory (must not already exist)")
    ap.add_argument("--replay", action="store_true", help="Reuse retained pages only; no network request, "
                                                            "no credential file opened")
    ap.add_argument("--receipt", type=Path, required=True, help="Repo-committed receipt path (hashes and results only)")
    args = ap.parse_args(argv)

    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")

    # --replay never opens a credential file: the page cache already holds every
    # response this run needs, and PageFetcher(replay=True) never sends a request.
    key = secret = None
    if not args.replay:
        env_file = args.env_file
        if env_file is None:
            if args.env_file_from_file is None:
                raise SystemExit("one of --env-file or --env-file-from-file is required when not --replay")
            env_file = Path(args.env_file_from_file.read_text().strip())
        sys.path.insert(0, str(ADAPTIVE_PAPER))
        import runner  # noqa: E402  (adaptive-paper/runner.py's credential loader)
        key, secret = runner.credentials(env_file)

    broker_orders_path = args.trial / "broker-orders.json"
    broker_orders = json.loads(broker_orders_path.read_text())
    paper_output = json.loads((args.trial / "paper-output.json").read_text())
    ingest_receipt = json.loads((args.trial / "ingest-receipt.json").read_text())
    paper_orders = load_paper_orders(broker_orders)
    symbols = sorted({o["symbol"] for o in paper_orders})
    start_ns, end_ns = fetch_window(paper_orders)
    day = ns_to_iso(paper_orders[0]["submitted_at_ns"])[:10]

    order_timeout_seconds, timeout_source = resolve_order_timeout_seconds(ingest_receipt)
    cancel_resolution = resolve_cancel_timestamps(paper_orders, paper_output, order_timeout_seconds)

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"--out must be a fresh (empty or nonexistent) directory: {args.out} is not empty")
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=True)
    chmod_private_dir(args.out)

    fetcher = PageFetcher(args.pages, {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret} if key else None,
                           replay=args.replay)
    raw_quotes = fetch_quotes(fetcher, symbols, start_ns, end_ns, day)
    quotes, quote_drop_counts = normalize_quote_rows(raw_quotes)
    save(args.out / "quotes.private.json", quotes)

    replay_result = run_replay(paper_orders, quotes, out_dir=args.out, cancel_resolution=cancel_resolution, latency_ns=0)
    comparison = compare_orders(paper_orders, replay_result["sim_by_id"])
    save(args.out / "comparison.json", comparison)

    latency_sweep = run_latency_sweep(paper_orders, quotes, cancel_resolution=cancel_resolution,
                                       out_dir=args.out / "latency-sweep", baseline_comparison=comparison)

    try:
        alpaca_py_version = importlib.metadata.version("alpaca-py")
    except importlib.metadata.PackageNotFoundError:
        alpaca_py_version = None

    completed_utc = datetime.now(UTC).isoformat()
    summary = {"receipt": str(args.receipt), "aggregates": comparison["aggregates"],
               "latency_sweep": [{"latency_ms": s["latency_ms"], "fill_agreement_rate": s["fill_agreement_rate"]}
                                  for s in latency_sweep]}
    stdout_text = json.dumps(summary, indent=2)

    receipt = {
        "kind": "sim_vs_paper_fill_comparison",
        "protocol": "sim-paper-compare-v1-20260924",
        "evidence_class": "local_integration_check",
        "trial": str(broker_orders_path.parent.name),
        "trial_window_utc": broker_orders["window_utc"],
        "inputs_sha256": {
            "broker_orders_json": digest_path(broker_orders_path),
            "paper_output_json": digest_path(args.trial / "paper-output.json"),
            "ingest_receipt_json": digest_path(args.trial / "ingest-receipt.json"),
        },
        "data_provenance": {
            "source": "Alpaca historical quotes, GET https://data.alpaca.markets/v2/stocks/quotes",
            "feed": "sip", "adjustment": "n/a (quotes)", "symbols": symbols,
            "asof": day, "window_utc": [ns_to_iso(start_ns), ns_to_iso(end_ns)],
            "quote_counts": {s: len(rows) for s, rows in quotes.items()},
            "quote_drop_counts": quote_drop_counts,
            "page_ledger_sha256": digest_path(args.pages / "ledger.jsonl"),
            "page_sources": {"cache": fetcher.from_cache, "network": fetcher.from_network,
                              "pages": fetcher.page_events},
            "alpaca_py_version": alpaca_py_version,
            "alpaca_py_version_measured": alpaca_py_version is not None,
        },
        "cancel_timestamp_resolution": {
            "order_timeout_seconds": order_timeout_seconds,
            "order_timeout_seconds_source": timeout_source,
            "by_client_order_id": cancel_resolution,
        },
        "engine": {
            "engine_version": importlib.metadata.version("nautilus_trader"),
            "book_type": "L1_MBP", "oms_type": "NETTING", "account_type": "CASH",
            "fee_model": {"class": "FixedFeeModel", "commission_usd": "0", "source": "reused from engine-nautilus/equity-replay baseline case"},
            "fill_model": {"class": "nautilus_trader.execution.FillModel (native default, unconfigured)", "note": FILL_MODEL_NOTE},
            "liquidity_consumption": replay_result["engine"]["liquidity_consumption"],
            "queue_position": replay_result["engine"]["queue_position"],
            "latency_model": None if replay_result["engine"]["latency_ns"] == 0 else
                              {"class": "StaticLatencyModel", "base_latency_nanos": replay_result["engine"]["latency_ns"]},
            "reports": replay_result["reports"],
        },
        "results": comparison,
        "latency_sensitivity_sweep": {
            "declared_sweep_ms": list(LATENCY_SWEEP_MS),
            "purpose": "Sensitivity check, not a calibration: shows how fill agreement changes as "
                       "StaticLatencyModel's broker/network latency assumption increases from the "
                       "zero-latency default.",
            "points": latency_sweep,
        },
        "scope": "One retained trial, five order decisions (four filled, one canceled). This is an agreement "
                 "measurement between one paper session and one deterministic quote-driven replay, not a fill-rate "
                 "or slippage calibration, and not a claim about any other trial, symbol, session or market regime.",
        "replay_from_retained_pages_only": args.replay,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "exit_code": 0,
        "argv": redact_argv(raw_argv),
        "stdout_sha256": digest_bytes(stdout_text.encode()),
        "runner_sha256": digest_path(Path(__file__)),
    }
    save(args.receipt, receipt)
    print(stdout_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
