#!/usr/bin/env python3
"""Replay a retained adaptive-paper trial's order decisions through NautilusTrader's
BacktestEngine, fed with historical Alpaca SIP quotes, and compare simulated fills
against the trial's paper fills (trading-lane audit gap #7).

  python replay_compare.py \
    --trial ../adaptive-paper/trials/20260923g-main-passed \
    --env-file "$PAPER_ENV_FILE" \
    --pages "$PRIVATE_CACHE_DIR/pages" \
    --out "$PRIVATE_CACHE_DIR/run"

Data fetch is GET-only against the existing Alpaca data path (SIP feed), reusing the
mover-early-entry `Fetcher` page-retention pattern: every response is kept gzip'd with
a sha256 ledger under --pages, and --replay re-derives the same run from those pages
without a new network request. Replay uses the same fee/fill-model configuration as
the accepted baseline in engine-nautilus/equity-replay (native default `FillModel`,
`FixedFeeModel`, `book_type=L1_MBP`): Alpaca equities are commission-free, and the
default fill model matches limit orders against the fed L1 quote book with no
synthetic slippage or partial-fill assumption.

This is a single trial with five orders (four filled, one canceled). It measures
paper/simulated fill agreement for that one window; it is not a fill-rate or
slippage calibration and must not be read as one.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import re
import socket
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


# ---------------------------------------------------------------------------
# Small helpers (timestamps, hashing, JSON I/O)
# ---------------------------------------------------------------------------

def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_path(path: Path) -> str:
    return digest_bytes(Path(path).read_bytes())


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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


def bps(sim_price, paper_price):
    if sim_price is None or paper_price is None or paper_price == 0:
        return None
    return float((Decimal(str(sim_price)) / Decimal(str(paper_price)) - 1) * 10000)


# ---------------------------------------------------------------------------
# GET with page retention/replay (adapted from mover-early-entry/mover_scan.py's
# Fetcher; reimplemented locally to avoid pulling that module's numpy/rules/
# sessions_io dependency chain into the pinned Nautilus-only runtime).
# ---------------------------------------------------------------------------

def req_key(path: str, params: dict) -> str:
    return hashlib.sha256((path + "?" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:32]


class PageFetcher:
    def __init__(self, pages: Path, headers=None, replay: bool = False):
        self.pages, self.headers, self.replay = Path(pages), headers, replay
        self.ledger = {}
        lpath = self.pages / "ledger.jsonl"
        if lpath.exists():
            for line in lpath.read_text().splitlines():
                rec = json.loads(line)
                self.ledger[rec["key"]] = rec
        if not replay:
            self.pages.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.lfile = lpath.open("a")

    def get(self, base: str, path: str, params: dict):
        token = None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            key = req_key(base + path, q)
            if self.replay or key in self.ledger:
                rec = self.ledger[key]
                raw = gzip.decompress((self.pages / rec["file"]).read_bytes())
                if digest_bytes(raw) != rec["sha256"]:
                    raise SystemExit(f"page hash mismatch {rec['file']}")
                status = rec["status"]
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
                self.lfile.write(json.dumps(rec) + "\n")
                self.lfile.flush()
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
    timestamps. Raises on anything the replay cannot faithfully reconstruct."""
    orders = []
    for raw in broker_orders["orders"]:
        if raw["type"] != "limit":
            raise ValueError(f"unsupported_order_type:{raw['type']}")
        orders.append({
            "client_order_id": raw["client_order_id"],
            "symbol": raw["symbol"],
            "side": raw["side"].upper(),
            "qty": int(Decimal(raw["qty"])),
            "limit_price": str(Decimal(raw["limit_price"])),
            "time_in_force": raw["time_in_force"].upper(),
            "status": raw["status"],
            "filled_qty": int(Decimal(raw["filled_qty"])),
            "filled_avg_price": None if raw["filled_avg_price"] in (None, "None") else str(Decimal(raw["filled_avg_price"])),
            "submitted_at_ns": ts_ns(raw["submitted_at"]),
            "filled_at_ns": ts_ns(raw["filled_at"]) if raw.get("filled_at") else None,
        })
    orders.sort(key=lambda o: o["submitted_at_ns"])
    return orders


def build_decisions(paper_orders: list[dict]) -> list[dict]:
    """Turn the paper order sequence into submit/cancel decisions. A paper order
    left `canceled` with no fill has no recorded cancel timestamp in the trial
    receipt; this replay cancels it immediately before the next order decision
    for the same (symbol, side) is submitted -- the earliest point the trial
    itself is known to have superseded it. This declared, documented approximation
    is the only place a paper timestamp is not used directly."""
    decisions = [{"ts_ns": o["submitted_at_ns"], "action": "submit", "order": o} for o in paper_orders]
    by_symbol_side: dict[tuple, list[dict]] = {}
    for o in paper_orders:
        by_symbol_side.setdefault((o["symbol"], o["side"]), []).append(o)
    for group in by_symbol_side.values():
        for prev, nxt in zip(group, group[1:]):
            if prev["status"] == "canceled":
                decisions.append({"ts_ns": nxt["submitted_at_ns"] - 1, "action": "cancel", "order": prev})
    decisions.sort(key=lambda d: (d["ts_ns"], 0 if d["action"] == "submit" else 1))
    return decisions


def fetch_window(paper_orders: list[dict], *, pad_seconds: int = 60) -> tuple[int, int]:
    starts = [o["submitted_at_ns"] for o in paper_orders]
    ends = [o["filled_at_ns"] or o["submitted_at_ns"] for o in paper_orders]
    return min(starts) - pad_seconds * 10**9, max(ends) + pad_seconds * 10**9


# ---------------------------------------------------------------------------
# Alpaca SIP historical quotes
# ---------------------------------------------------------------------------

def fetch_quotes(fetcher: PageFetcher, headers, symbols: list[str], start_ns: int, end_ns: int, asof: str) -> dict[str, list[dict]]:
    quotes: dict[str, list[dict]] = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "start": ns_to_iso(start_ns), "end": ns_to_iso(end_ns),
              "feed": "sip", "asof": asof, "limit": 10000, "sort": "asc"}
    for body in fetcher.get(DATA, "/v2/stocks/quotes", params):
        for symbol, rows in (body.get("quotes") or {}).items():
            quotes[symbol].extend(rows)
    return quotes


def normalize_quote_rows(raw_rows: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Keep only two-sided, positively priced NBBO quotes, each stamped in ns."""
    out: dict[str, list[dict]] = {}
    for symbol, rows in raw_rows.items():
        kept = []
        for row in rows:
            bp, ap = row.get("bp"), row.get("ap")
            bs, asz = row.get("bs"), row.get("as")
            if not bp or not ap or bp <= 0 or ap <= 0 or not bs or not asz:
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
    return out


# ---------------------------------------------------------------------------
# Comparison (pure, offline-testable)
# ---------------------------------------------------------------------------

def compare_orders(paper_orders: list[dict], sim_orders_by_id: dict[str, dict]) -> dict:
    rows = []
    for paper in paper_orders:
        sim = sim_orders_by_id.get(paper["client_order_id"])
        paper_filled = paper["status"] == "filled"
        sim_filled = bool(sim and sim.get("filled"))
        row = {
            "client_order_id": paper["client_order_id"], "symbol": paper["symbol"], "side": paper["side"],
            "qty": paper["qty"], "limit_price": paper["limit_price"],
            "paper_status": paper["status"], "paper_filled": paper_filled,
            "paper_fill_price": paper["filled_avg_price"], "paper_fill_ts": ns_to_iso(paper["filled_at_ns"]) if paper["filled_at_ns"] else None,
            "sim_present": sim is not None, "sim_filled": sim_filled,
            "sim_fill_price": sim.get("avg_px") if sim else None,
            "sim_fill_ts": ns_to_iso(sim["ts_last"]) if sim and sim.get("ts_last") else None,
            "fill_agreement": paper_filled == sim_filled,
        }
        if paper_filled and sim_filled:
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

def run_replay(paper_orders: list[dict], quotes_by_symbol: dict[str, list[dict]], *, out_dir: Path) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel
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

    decisions = build_decisions(paper_orders)
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

    class ScheduledReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.decisions = decisions
            self.idx = 0
            self.applied = []

        def on_start(self):
            for iid in {instruments[s].id for s in symbols}:
                self.subscribe_quotes(iid)

        def on_quote(self, quote):
            now = quote.ts_event
            while self.idx < len(self.decisions) and self.decisions[self.idx]["ts_ns"] <= now:
                self._apply(self.decisions[self.idx])
                self.idx += 1

        def on_stop(self):
            while self.idx < len(self.decisions):
                self._apply(self.decisions[self.idx])
                self.idx += 1
            for order in list(self.cache.orders_open()):
                self.cancel_order(order.client_order_id)

        def _apply(self, d):
            o = d["order"]
            if d["action"] == "submit":
                order = self.order_factory.limit(
                    instrument_id=o["instrument_id"], order_side=OrderSide.BUY if o["side"] == "BUY" else OrderSide.SELL,
                    quantity=Quantity.from_int(o["qty"]), price=Price(Decimal(o["limit_price"]), 2),
                    time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(o["client_order_id"]))
                self.submit_order(order)
            else:
                order = self.cache.order(ClientOrderId(o["client_order_id"]))
                if order is not None and order.is_open:
                    self.cancel_order(order.client_order_id)
            self.applied.append({"ts_ns": d["ts_ns"], "action": d["action"], "client_order_id": o["client_order_id"]})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    fee_model = FixedFeeModel(Money(Decimal("0"), usd))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("10000"), usd)],
                         base_currency=usd, fee_model=fee_model, book_type=BookType.L1_MBP)
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
        # Both reports are indexed by client_order_id; to_json(orient="records")
        # drops the index, so reset it into a column first. ts_init/ts_last are
        # tz-aware pandas Timestamp columns; to_json would silently downcast them
        # to millisecond epoch integers, so convert to int64 nanoseconds explicitly.
        for report in (fills_report, orders_report):
            for col in ("ts_init", "ts_last"):
                if col in report.columns:
                    report[col] = report[col].astype("int64")
        fill_rows = json.loads(fills_report.reset_index().to_json(orient="records"))
        order_rows = json.loads(orders_report.reset_index().to_json(orient="records"))
        save(out_dir / "reports.json", {"fills": fill_rows, "orders": order_rows, "applied_decisions": strategy.applied})

        sim_by_id = {}
        for row in order_rows:
            coid = row.get("client_order_id")
            if coid is None:
                continue
            filled = row.get("status") == "FILLED"
            sim_by_id[coid] = {"filled": filled, "status": row.get("status"), "avg_px": None, "ts_last": None}
        for row in fill_rows:
            coid = row.get("client_order_id")
            if coid in sim_by_id:
                sim_by_id[coid].update({"filled": True, "avg_px": str(Decimal(str(row["avg_px"]))), "ts_last": int(row["ts_last"])})
        return {"sim_by_id": sim_by_id,
                "reports": {"fills": {"rows": len(fill_rows), "sha256": digest_path(out_dir / "fills.csv")},
                            "orders": {"rows": len(order_rows), "sha256": digest_path(out_dir / "orders.csv")}}}
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trial", type=Path, required=True, help="Retained adaptive-paper trial directory")
    ap.add_argument("--env-file", type=Path, help="Private paper-credential env file (never printed)")
    ap.add_argument("--env-file-from-file", type=Path,
                     help="A file whose sole line is the private env file's path (for shells that must not "
                          "spell the credential store path directly in a command)")
    ap.add_argument("--pages", type=Path, required=True, help="Private page cache (gzip + sha256 ledger)")
    ap.add_argument("--out", type=Path, required=True, help="Fresh private output directory")
    ap.add_argument("--replay", action="store_true", help="Reuse retained pages only; no network request")
    ap.add_argument("--receipt", type=Path, required=True, help="Repo-committed receipt path (hashes and results only)")
    args = ap.parse_args(argv)

    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")

    env_file = args.env_file
    if env_file is None:
        if args.env_file_from_file is None:
            raise SystemExit("one of --env-file or --env-file-from-file is required")
        env_file = Path(args.env_file_from_file.read_text().strip())

    sys.path.insert(0, str(ADAPTIVE_PAPER))
    import runner  # noqa: E402  (adaptive-paper/runner.py's credential loader)
    key, secret = runner.credentials(env_file)

    broker_orders_path = args.trial / "broker-orders.json"
    broker_orders = json.loads(broker_orders_path.read_text())
    paper_orders = load_paper_orders(broker_orders)
    symbols = sorted({o["symbol"] for o in paper_orders})
    start_ns, end_ns = fetch_window(paper_orders)
    day = ns_to_iso(paper_orders[0]["submitted_at_ns"])[:10]

    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)

    fetcher = PageFetcher(args.pages, {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, replay=args.replay)
    raw_quotes = fetch_quotes(fetcher, fetcher.headers, symbols, start_ns, end_ns, day)
    quotes = normalize_quote_rows(raw_quotes)
    save(args.out / "quotes.private.json", quotes)

    replay_result = run_replay(paper_orders, quotes, out_dir=args.out)
    comparison = compare_orders(paper_orders, replay_result["sim_by_id"])
    save(args.out / "comparison.json", comparison)

    receipt = {
        "kind": "sim_vs_paper_fill_comparison",
        "protocol": "sim-paper-compare-v1-20260924",
        "trading_lane_audit_gap": 7,
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
            "page_ledger_sha256": digest_path(args.pages / "ledger.jsonl"),
            "alpaca_py_declared_version": "0.44.0",
        },
        "engine": {
            "engine_version": importlib.metadata.version("nautilus_trader"),
            "book_type": "L1_MBP", "oms_type": "NETTING", "account_type": "CASH",
            "fee_model": {"class": "FixedFeeModel", "commission_usd": "0", "source": "reused from engine-nautilus/equity-replay baseline case"},
            "fill_model": {"class": "nautilus_trader.execution.FillModel (native default, unconfigured)", "note": FILL_MODEL_NOTE},
            "liquidity_consumption": False,
            "reports": replay_result["reports"],
        },
        "results": comparison,
        "cancel_timestamp_assumption": "canceled paper orders have no recorded cancel timestamp in broker-orders.json; "
                                        "the replay cancels the simulated order 1ns before the next same-symbol/side "
                                        "order's paper submit timestamp (build_decisions())",
        "scope": "One retained trial, five order decisions (four filled, one canceled). This is an agreement "
                 "measurement between one paper session and one deterministic quote-driven replay, not a fill-rate "
                 "or slippage calibration, and not a claim about any other trial, symbol, session or market regime.",
        "network_interfaces": socket.if_nameindex(),
        "replay_from_retained_pages_only": args.replay,
        "completed_utc": datetime.now(UTC).isoformat(),
        "runner_sha256": digest_path(Path(__file__)),
    }
    save(args.receipt, receipt)
    print(json.dumps({"receipt": str(args.receipt), "aggregates": comparison["aggregates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
