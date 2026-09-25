#!/usr/bin/env python3
"""sim-capacity: build and run the simulation-lane capacity infrastructure test
on NautilusTrader 2.0.0rc5.

This is INFRASTRUCTURE EVIDENCE ONLY (evidence_class `sim_capacity_infrastructure`):
it measures how many fills/minute the pinned engine, a native rate limiter, a
primary-reference (not "calibrated") latency setting, quotes-only L1 execution
(see H1 in README.md for why trade ticks are excluded from the engine feed)
and a cited fee model can sustain. Of the three realism flags this lane sets
on `add_venue` (`trade_execution`, `liquidity_consumption`, `queue_position`),
only `liquidity_consumption` was measured to change results in this quotes-
only, IOC-only setup; the other two are documented, not claimed as active
realism features here (see README.md). No strategy manufactures a trade to hit
a throughput target (see blueprints/us-equities/adaptive-paper/README.md L41
and blueprints/us-equities/mover-v3/README.md's "A high-rate capacity replay
is an infrastructure test, never strategy evidence").

  python3 runner.py fetch --pages PRIVATE/pages --catalog PRIVATE/catalog [--replay]
  python3 runner.py run --catalog PRIVATE/catalog \
      --receipt receipts/20260924-sim-capacity.json
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import fetcher  # noqa: E402
from schedule import NS_PER_MIN, full_minutes, minute_bucket  # noqa: E402

UTC = timezone.utc
RUN_SECONDS = 1800.0  # 14:00:00Z - 14:30:00Z
FLATTEN_BUFFER_SECONDS = 65.0  # >1 rate-limit window (60s) of no new exerciser submits
# before flattening: the risk engine's rolling max_order_submit_rate budget is
# shared with the flatten market orders, and closing 8 symbols' positions in
# one burst right at the tail of a saturated window got RATE_LIMIT-denied on
# every close (measured directly: a 10s buffer left every position open,
# flat_at_end False). Letting a full window elapse with zero exerciser
# submits first guarantees the budget is empty before flatten needs it.
PRIMARY_LATENCY_MS = 70
POSITION_CAP = 300  # generous per-symbol inventory cap: random-walk drift from partial IOC
# fills (a BUY/SELL round-robin alternation, sized independently each time from
# displayed book depth rather than matched exactly to the outstanding open
# quantity) can wander well past a tight cap over a 30-minute, thousands-of-
# cycles run; a too-tight cap (an earlier 20-share cap was tried and measured)
# throttles the exerciser on its own bookkeeping rather than on the rate
# limiter or the market data, which would misattribute a scheduling artifact
# as the venue's throughput ceiling.
LATENCY_SWEEP_MS = (0, 70, 250, 1000)
PROFILES = {
    "paper-parity": {"max_order_submit_rate": "180/00:01:00", "submits_per_sec": 5.0, "commission_plan": "none",
                      "note": "Mirrors Alpaca standard tier: 200 req/min x 0.9 = 180/min. "
                              "Fills cannot exceed 180/min here by construction of the limiter. "
                              "300 submits/min attempted against a 180/min budget: the limiter binds "
                              "and denials are expected and counted."},
    "elite-tier": {"max_order_submit_rate": "900/00:01:00", "submits_per_sec": 1000.0 / 60.0,
                    "commission_plan": "all_in",
                    "note": "Alpaca Elite / non-retail tier: 0.9x the advertised 1000 req/min "
                            "REQUEST-RATE entitlement (a request budget, not a fill-throughput figure) "
                            "= 900/min. "
                            "Must sustain >=180 fills/min in every full simulated minute. "
                            "~1000 submits/min attempted against a 900/min budget so the native "
                            "limiter actually binds here too (a prior cadence of exactly 15/s = "
                            "900/min never triggered a single denial); denials are counted."},
}


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")
    os.chmod(path, 0o644)


# ---------------------------------------------------------------------------
# argv redaction (adapted from replay_compare.redact_args: built from the
# parsed namespace, never raw argv text, with allow_abbrev=False)
# ---------------------------------------------------------------------------
_SENSITIVE_ARG_NAMES = ("env_file", "pages", "catalog", "out")
_PATH_TRIMMED_ARG_NAMES = ("receipt",)
_ARG_ORDER = ("command", "env_file", "pages", "catalog", "out", "replay", "receipt", "profile", "latency_ms")


def _repo_relative_or_basename(value: str) -> str:
    """Repo-relative path when the value is inside this repository, else just
    the basename -- never the full absolute path, which could carry the
    invoking user's home directory (adapted from
    sim-paper-compare/replay_compare.py's `_repo_relative_or_basename`)."""
    p = Path(value)
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return p.name


def redact_args(args: argparse.Namespace) -> list[str]:
    parts = []
    for name in _ARG_ORDER:
        value = getattr(args, name, None)
        if name == "command":
            if value:
                parts.append(str(value))
            continue
        flag = "--" + name.replace("_", "-")
        if name == "replay":
            if value:
                parts.append(flag)
            continue
        if value is None:
            continue
        parts.append(flag)
        if name in _SENSITIVE_ARG_NAMES:
            parts.append("<redacted>")
        elif name in _PATH_TRIMMED_ARG_NAMES:
            parts.append(_repo_relative_or_basename(str(value)))
        else:
            parts.append(str(value))
    return parts


# ---------------------------------------------------------------------------
# Fetch + catalog
# ---------------------------------------------------------------------------

def _window_bounded_counts(rows_by_symbol: dict, window_end_ns: int) -> dict[str, int]:
    """Count only rows at or before the reported analysis window's end, even
    though the fetch itself pulls a few extra minutes of pad data past it (for
    the exerciser's end-of-window flatten -- see fetcher.py's FETCH_END_ISO).
    The receipt's counts must describe the analysis window, not the pad."""
    return {s: sum(1 for r in rows if r["ts_ns"] <= window_end_ns) for s, rows in rows_by_symbol.items()}


def cmd_fetch(args) -> int:
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")
    key, secret = fetcher.load_credentials(args.replay)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret} if key else None
    pf = fetcher.rc.PageFetcher(args.pages, headers, replay=args.replay)
    raw_quotes = fetcher.fetch_quotes(pf)
    raw_trades = fetcher.fetch_trades(pf)
    quotes, quote_drops = fetcher.normalize_quotes(raw_quotes)
    trades, trade_drops = fetcher.normalize_trades(raw_trades)
    catalog_stats = fetcher.build_catalog(args.catalog, quotes, trades)

    # Exactly this run's served pages (from pf.page_events, populated only by
    # the .get() calls this process actually made), not the whole cumulative
    # ledger.jsonl on disk (which can carry pages from earlier, unrelated
    # fetches/re-fetches against the same private cache directory).
    this_run_hashes = sorted({pf.ledger[e["request_digest"]]["sha256"] for e in pf.page_events})
    this_run_hashes_digest = fetcher.rc.digest_bytes(json.dumps(this_run_hashes).encode())
    window_end_ns = fetcher.rc.ts_ns(fetcher.WINDOW_END_ISO)

    manifest = {
        "fetched_at_utc": utcnow_iso(),
        "window": {"start": fetcher.WINDOW_START_ISO, "end": fetcher.WINDOW_END_ISO},
        "fetch_window_end_with_flatten_pad": fetcher.FETCH_END_ISO,
        "symbols": list(fetcher.SYMBOLS),
        "quote_counts": _window_bounded_counts(quotes, window_end_ns),
        "trade_counts": _window_bounded_counts(trades, window_end_ns),
        "quote_drop_counts": quote_drops,
        "trade_drop_counts": trade_drops,
        "catalog_stats": catalog_stats,
        "page_events": {"from_cache": pf.from_cache, "from_network": pf.from_network,
                        "this_run_page_count": len(pf.page_events),
                        "this_run_page_hashes": this_run_hashes,
                        "this_run_page_hashes_digest": this_run_hashes_digest,
                        "cumulative_ledger_page_count": len(pf.ledger)},
    }
    save(args.catalog / "fetch-manifest.json", manifest)
    # Also keep the normalized rows privately (not committed) for `run` to consume
    # without re-fetching or re-normalizing.
    save(args.catalog / "quotes.private.json", quotes)
    save(args.catalog / "trades.private.json", trades)
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("quote_counts", "trade_counts")}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Engine run (one profile x one latency)
# ---------------------------------------------------------------------------

def dataframe_to_rows(df) -> list[dict]:
    """Convert a NautilusTrader pandas report to plain dict rows, converting any
    `datetime*` column to a true integer **nanosecond** epoch.
    `DataFrame.to_json`'s default 'epoch' date format does not preserve raw
    event-time nanoseconds for a tz-aware `datetime64[ns, UTC]` column: it is a
    plain units mismatch (milliseconds, not nanoseconds) -- verified directly
    on the pinned runtime: a `ts_event` of `1970-01-21 20:00:00.500000+00:00`,
    i.e. exactly 1,800,000,500,000,000 ns, serializes through
    `to_json(date_format='epoch')` as `1800000500`, which is
    1,800,000,500,000,000 // 1_000_000 -- epoch milliseconds. This is exactly
    the pandas report trap `sim-paper-compare/replay_compare.py`'s module
    docstring warns about ("no tz-aware-column-to-int64 conversion in
    between"); this helper does that conversion explicitly.

    Calling `.astype('int64')` directly on a datetime column is not itself
    safe against every possible source unit: on a `datetime64[us, UTC]`
    column (microseconds), `.astype('int64')` returns microseconds, not
    nanoseconds, silently (verified directly: casting the same instant to
    `datetime64[us, UTC]` first, then `.astype('int64')`, yields
    1,800,000,500,000 -- microseconds, 1000x too small for a caller assuming
    ns). This helper therefore always normalizes to `datetime64[ns]` first,
    so the unit of the extracted integer cannot silently depend on whatever
    unit pandas happened to store the column in."""
    out = df.reset_index()
    for column in out.columns:
        dtype = str(out[column].dtype)
        if dtype.startswith("datetime64"):
            # Force ns precision before extracting the integer, tz-aware or
            # not (a plain `.astype("datetime64[ns]")` raises on a tz-aware
            # column; a tz-aware target dtype instead just re-precisions it).
            target = "datetime64[ns, UTC]" if ", " in dtype else "datetime64[ns]"
            out[column] = out[column].astype(target).astype("int64")
    return out.to_dict(orient="records")


def run_one(quotes_by_symbol: dict, trades_by_symbol: dict, *, profile_name: str, latency_ms: int,
            run_seconds: float = RUN_SECONDS) -> dict:
    """Run one profile x latency combination.

    `trades_by_symbol` is accepted for interface/signature stability (and is
    still what `fetcher.build_catalog` writes to the private
    `ParquetDataCatalog` for future passive-order work) but is **not** fed
    into the engine here -- see README.md's H1 finding: on the pinned rc5
    engine, an L1 book overwrites *both* sides with a trade print's price and
    size, and nothing restores the prior quote after a NO_AGGRESSOR trade
    (Alpaca's historical trade data carries no aggressor-side field at all),
    so an IOC order can match a stale, trade-locked book until the next quote
    arrives. Measured directly: with trade ticks included, 41.2% of elite-tier
    fills beat the NBBO touch in force (8,923 of 21,652); quotes-only puts
    every one of them at the touch. The exerciser is taker-only (marketable
    IOC), so quotes-only is the realistic engine feed for this lane."""
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, RiskEngineConfig
    from nautilus_trader.execution import StaticLatencyModel
    from nautilus_trader.model import (AccountType, BookType, Currency, Equity, InstrumentId,
                                        Money, OmsType, Price, Quantity, QuoteTick, Symbol, Venue)

    from exerciser import CapacityExerciser, CapacityExerciserParams
    from fee_model import build_nautilus_fee_model

    profile = PROFILES[profile_name]
    usd, venue = Currency.from_str("USD"), Venue(fetcher.VENUE_NAME)
    symbols = sorted(quotes_by_symbol)
    instruments = {}
    for symbol in symbols:
        iid = InstrumentId.from_str(f"{symbol}.{fetcher.VENUE_NAME}")
        instruments[symbol] = Equity(iid, Symbol(symbol), usd, 2, Price.from_str("0.01"), 0, 0,
                                      lot_size=Quantity.from_int(1))

    # Quotes only -- see the H1 note in this function's docstring and in
    # README.md. `trades_by_symbol` is deliberately not read here.
    ticks = []
    start_ns = min(row["ts_ns"] for rows in quotes_by_symbol.values() for row in rows)
    for symbol, rows in quotes_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                                    Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                                    row["ts_ns"], row["ts_ns"]))
    ticks.sort(key=lambda t: t.ts_event)

    engine_cfg = BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR),
                                       risk_engine=RiskEngineConfig(max_order_submit_rate=profile["max_order_submit_rate"]))
    engine = BacktestEngine(engine_cfg)
    fee_model = build_nautilus_fee_model(commission_plan=profile.get("commission_plan", "none"))
    latency_model = StaticLatencyModel(base_latency_nanos=int(latency_ms * 1_000_000)) if latency_ms else None
    wall_start = time.monotonic()
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("1000000"), usd)],
                          base_currency=usd, fee_model=fee_model, latency_model=latency_model,
                          book_type=BookType.L1_MBP, trade_execution=True, liquidity_consumption=True,
                          queue_position=True)
        for instrument in instruments.values():
            engine.add_instrument(instrument)
        engine.add_data(ticks)
        params = CapacityExerciserParams(symbols=tuple(symbols), venue=fetcher.VENUE_NAME,
                                          submits_per_sec=profile["submits_per_sec"], position_cap=POSITION_CAP,
                                          qty_min=1, qty_max=5, collar="0.01", run_seconds=run_seconds,
                                          flatten_buffer_seconds=FLATTEN_BUFFER_SECONDS)
        strategy = CapacityExerciser(params)
        engine.add_strategy(strategy)
        engine.run()
        wall_seconds = time.monotonic() - wall_start

        fills_report = engine.generate_fills_report()
        order_fills_report = engine.generate_order_fills_report()
        fill_rows = dataframe_to_rows(fills_report)
        order_fill_rows = dataframe_to_rows(order_fills_report)
        net_positions = {symbol: float(strategy.portfolio.net_position(instruments[symbol].id)) for symbol in symbols}
        # Every exerciser order's actual time-in-force, straight off the live
        # order object (not re-derived): lets a test independently confirm the
        # exerciser really only ever submits IOC through the real engine path.
        tif_counts: dict[str, int] = {}
        for order in strategy.cache.orders():
            if str(order.client_order_id).startswith("CAP-"):
                key = str(order.time_in_force)
                tif_counts[key] = tif_counts.get(key, 0) + 1

        return {
            "profile": profile_name, "latency_ms": latency_ms, "start_ns": start_ns,
            "counters": dict(strategy.counters), "events": strategy.events,
            "filled_qty": strategy.filled_qty, "filled_notional": str(strategy.filled_notional),
            "fills_report_rows": fill_rows, "order_fills_report_rows": order_fill_rows,
            "n_ticks": len(ticks), "wall_seconds": wall_seconds, "tif_counts": tif_counts,
            "net_positions_at_end": net_positions, "flat_at_end": all(v == 0 for v in net_positions.values()),
            "run_seconds": run_seconds,
        }
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Per-minute bucketing, independent recount, naive L1 sample check
# ---------------------------------------------------------------------------

def bucket_events_by_minute(events: list[dict], start_ns: int) -> dict[int, dict[str, int]]:
    buckets: dict[int, dict[str, int]] = {}
    for ev in events:
        m = minute_bucket(ev["ts_ns"], start_ns)
        b = buckets.setdefault(m, {"submits": 0, "fills": 0})
        kind = ev["kind"]
        if kind == "submit":
            b["submits"] += 1
        elif kind == "fill":
            b["fills"] += 1
        else:
            b[kind] = b.get(kind, 0) + 1
    return buckets


def recount_fills_from_report(fill_rows: list[dict], start_ns: int, ts_key_candidates=("ts_event", "ts_init")) -> dict[int, int]:
    ts_key = None
    for candidate in ts_key_candidates:
        if fill_rows and candidate in fill_rows[0]:
            ts_key = candidate
            break
    counts: dict[int, int] = {}
    for row in fill_rows:
        ts_ns = int(row[ts_key]) if ts_key else None
        if ts_ns is None:
            continue
        m = minute_bucket(ts_ns, start_ns)
        counts[m] = counts.get(m, 0) + 1
    return counts


def fills_per_minute_stats(bucket_fill_counts: dict[int, int], total_full_minutes: int) -> dict:
    values = [bucket_fill_counts.get(m, 0) for m in range(total_full_minutes)]
    if not values:
        return {"min": 0, "median": 0, "max": 0, "full_minutes_at_or_above_180": 0, "per_minute": values}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    return {"min": min(values), "median": median, "max": max(values),
            "full_minutes_at_or_above_180": sum(1 for v in values if v >= 180),
            "total_full_minutes": total_full_minutes, "per_minute": values}


def _quotes_in_force(rows: list[dict], ts_list: list[int], ts_ns: int) -> list[dict]:
    """Every quote row sharing the same timestamp as the last quote at or
    before `ts_ns` (rows/ts_list are already time-sorted). Two SIP quotes can
    legitimately share one nanosecond timestamp (1,342 such pairs measured in
    this data); the engine's actual processing order between same-ns rows is
    not observable from the retained data, so every row at that exact
    timestamp is a candidate the fill could plausibly have matched against --
    not just whichever one happens to sort last. Returns an empty list if
    `ts_ns` precedes every retained quote."""
    import bisect
    i = bisect.bisect_right(ts_list, ts_ns) - 1
    if i < 0:
        return []
    tie_ts = ts_list[i]
    lo = bisect.bisect_left(ts_list, tie_ts)
    hi = bisect.bisect_right(ts_list, tie_ts)
    return rows[lo:hi]


def check_no_fill_beats_nbbo_touch(events: list[dict], quotes_by_symbol: dict) -> dict:
    """H1 guard: independently re-derive, for every exerciser fill, the NBBO
    touch in force *at fill time* (not at submit or modeled-arrival time --
    the engine's own matching instant), using only the retained normalized
    quote rows, never the engine's internal book state. A BUY fill must never
    be strictly better than the ask in force, and a SELL fill must never be
    strictly better than the bid in force ("through the touch" -- i.e. paying
    more / receiving less than the touch, from a marketable IOC's collar over-
    crossing the market a little -- is expected and fine; the opposite,
    "better than the touch", is exactly the on-rc5-only artifact from a trade
    print locking the L1 book that motivated excluding trade ticks from the
    engine feed (see run_one's H1 docstring)).

    A fill is flagged only if it beats the touch of **every** quote sharing
    the in-force timestamp (see `_quotes_in_force`) -- if it is legitimately
    at-or-through even one of several same-ns candidates, it is not counted
    as a violation, since that candidate could be the one the engine actually
    matched against."""
    quote_ts = {s: [r["ts_ns"] for r in rows] for s, rows in quotes_by_symbol.items()}
    violations = []
    checked = 0
    for ev in events:
        if ev["kind"] != "fill" or not ev["client_order_id"].startswith("CAP-"):
            continue
        symbol = ev["instrument_id"].split(".")[0]
        rows = quotes_by_symbol.get(symbol, [])
        ts_list = quote_ts.get(symbol, [])
        candidates = _quotes_in_force(rows, ts_list, ev["ts_ns"])
        if not candidates:
            continue
        checked += 1
        px = Decimal(ev["price"])
        touches = []
        beats_every_candidate = True
        for q in candidates:
            bid, ask = Decimal(q["bid"]), Decimal(q["ask"])
            touch = ask if ev["side"] == "BUY" else bid
            touches.append(str(touch))
            beats_this_one = (px < ask) if ev["side"] == "BUY" else (px > bid)
            if not beats_this_one:
                beats_every_candidate = False
        if beats_every_candidate:
            violations.append({"client_order_id": ev["client_order_id"], "symbol": symbol, "side": ev["side"],
                                "fill_price": ev["price"], "candidate_touches": touches})
    return {"checked": checked, "violations": violations[:20], "violation_count": len(violations)}


def submit_to_fill_latency_ms(events: list[dict]) -> dict:
    """Submit -> fill latency distribution (ms), from the exerciser's own
    submit/fill event log. This is a measured distribution, not a claim that
    `latency_ms`/`PRIMARY_LATENCY_MS` is a calibrated broker latency: on rc5 a
    deferred order is released at the first of its own next quote or *any* due
    clock timer (see README.md's latency note), so the exerciser's own tick
    cadence mixes into this measured distribution alongside the configured
    StaticLatencyModel delay."""
    submits_by_id = {ev["client_order_id"]: ev["ts_ns"] for ev in events if ev["kind"] == "submit"}
    deltas_ms = sorted((ev["ts_ns"] - submits_by_id[ev["client_order_id"]]) / 1e6
                        for ev in events if ev["kind"] == "fill" and ev["client_order_id"] in submits_by_id)
    if not deltas_ms:
        return {"n": 0, "min_ms": None, "p50_ms": None, "p90_ms": None, "max_ms": None}
    n = len(deltas_ms)

    def pct(q):
        return deltas_ms[min(n - 1, int(q * (n - 1)))]

    return {"n": n, "min_ms": deltas_ms[0], "p50_ms": pct(0.5), "p90_ms": pct(0.9), "max_ms": deltas_ms[-1]}


def alpaca_rounding_delta(fills: list[dict], commission_plan: str) -> dict:
    """Measured difference between this model's per-fill, half-up rounding and
    Alpaca's actual documented method: aggregate each fee TYPE separately
    across every fill, then round each type's total UP to the cent (per the
    Brokerage Fee Schedule PDF: "Each fee type is aggregated separately at the
    daily, per-account level. After aggregation, each fee total is rounded up
    to the nearest cent."). This recomputes both totals directly from the
    fills rather than asserting a fixed dollar figure, since the difference
    depends on the actual run's fill counts/sizes."""
    import fee_model as fm

    sums = {"cat": Decimal("0"), "commission": Decimal("0"), "sec": Decimal("0"), "taf": Decimal("0")}
    model_total = Decimal("0")
    for f in fills:
        qty, px, side = f["qty"], Decimal(f["price"]), f["side"]
        model_total += Decimal(f["fee_usd"])
        sums["cat"] += fm.cat_fee(quantity=qty)
        sums["commission"] += fm.elite_commission(quantity=qty, plan=commission_plan)
        if side == "SELL":
            sums["sec"] += px * qty * fm.SEC_SECTION31_RATE_USD_PER_DOLLAR
            sums["taf"] += min(Decimal(qty) * fm.FINRA_TAF_USD_PER_SHARE, fm.FINRA_TAF_MAX_USD_PER_TRADE)
    alpaca_by_type = {k: v.quantize(fm.CENT, rounding=ROUND_CEILING) for k, v in sums.items()}
    alpaca_total = sum(alpaca_by_type.values(), Decimal("0"))
    return {"model_total_usd": str(model_total), "alpaca_method_total_usd": str(alpaca_total),
            "model_minus_alpaca_usd": str(model_total - alpaca_total),
            "alpaca_method_by_type_usd": {k: str(v) for k, v in alpaca_by_type.items()}}


# ---------------------------------------------------------------------------
# Receipt assembly for one profile run (at one or more latencies)
# ---------------------------------------------------------------------------

def summarize_run(result: dict, quotes_by_symbol: dict) -> dict:
    events = result["events"]
    start_ns = result["start_ns"]
    total_full_minutes = full_minutes(int(result["run_seconds"] * 1_000_000_000))
    buckets = bucket_events_by_minute(events, start_ns)
    fill_counts_by_minute = {m: b.get("fills", 0) for m, b in buckets.items()}
    strategy_stats = fills_per_minute_stats(fill_counts_by_minute, total_full_minutes)

    report_fill_counts = recount_fills_from_report(result["fills_report_rows"], start_ns)
    report_stats = fills_per_minute_stats(report_fill_counts, total_full_minutes)
    recount_agrees = (strategy_stats["per_minute"] == report_stats["per_minute"]
                       and result["counters"].get("fills", 0) == len(result["fills_report_rows"]))

    fills = [ev for ev in events if ev["kind"] == "fill"]
    total_fees = sum(Decimal(f["fee_usd"]) for f in fills)
    execution_cost_vs_mid = Decimal("0")
    for f in fills:
        if f.get("mid_at_fill") is None:
            continue
        mid, px, qty = Decimal(f["mid_at_fill"]), Decimal(f["price"]), f["qty"]
        execution_cost_vs_mid += (px - mid) * qty if f["side"] == "BUY" else (mid - px) * qty
    cash_flow = Decimal("0")
    for f in fills:
        qty, px = f["qty"], Decimal(f["price"])
        cash_flow += (-qty * px) if f["side"] == "BUY" else (qty * px)
    net_pnl = cash_flow - total_fees
    minutes_elapsed = result["run_seconds"] / 60.0
    simulated_cost_per_minute = float((total_fees + execution_cost_vs_mid) / Decimal(str(minutes_elapsed)))

    nbbo_touch_check = check_no_fill_beats_nbbo_touch(events, quotes_by_symbol)
    latency_dist = submit_to_fill_latency_ms(events)

    reject_reasons: dict[str, int] = {}
    denied_reasons: dict[str, int] = {}
    for ev in events:
        if ev["kind"] == "reject":
            reject_reasons[ev["reason"]] = reject_reasons.get(ev["reason"], 0) + 1
        elif ev["kind"] == "denied":
            denied_reasons[ev["reason"]] = denied_reasons.get(ev["reason"], 0) + 1

    commission_plan = PROFILES.get(result["profile"], {}).get("commission_plan", "none")
    fee_rounding = alpaca_rounding_delta(fills, commission_plan)

    return {
        "profile": result["profile"], "latency_ms": result["latency_ms"],
        "per_minute": {"submits": {m: buckets[m].get("submits", 0) for m in sorted(buckets)},
                        "fills": {m: buckets[m].get("fills", 0) for m in sorted(buckets)},
                        "ioc_expiries": {m: buckets[m].get("ioc_expiry", 0) for m in sorted(buckets)},
                        "rate_limit_denied": {m: buckets[m].get("denied", 0) for m in sorted(buckets)}},
        "fills_per_minute_stats": strategy_stats,
        "counters": result["counters"],
        "reject_reasons": reject_reasons, "denied_reasons": denied_reasons,
        "fee_rounding": fee_rounding,
        "filled_qty": result["filled_qty"], "filled_notional_usd": result["filled_notional"],
        "fees_usd": str(total_fees), "execution_cost_vs_mid_usd": str(execution_cost_vs_mid),
        "simulated_cost_per_minute_usd": simulated_cost_per_minute,
        "net_pnl_usd": str(net_pnl), "net_pnl_expected_negative": net_pnl < 0,
        "flat_at_end": result["flat_at_end"], "net_positions_at_end": result["net_positions_at_end"],
        "wall_seconds": result["wall_seconds"], "n_ticks": result["n_ticks"],
        "events_per_second": (result["n_ticks"] / result["wall_seconds"]) if result["wall_seconds"] else None,
        "recount": {"agrees": recount_agrees, "engine_fills_report_stats": report_stats,
                    "strategy_own_counter_stats": strategy_stats,
                    "fills_report_row_count": len(result["fills_report_rows"]),
                    "strategy_fill_counter": result["counters"].get("fills", 0)},
        "fill_vs_nbbo_touch": nbbo_touch_check,
        "submit_to_fill_latency_ms": latency_dist,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_run(args) -> int:
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")
    quotes = json.loads((args.catalog / "quotes.private.json").read_text())
    trades = json.loads((args.catalog / "trades.private.json").read_text())
    fetch_manifest = json.loads((args.catalog / "fetch-manifest.json").read_text())

    def _sweep_entry(latency_ms, summary):
        return {"latency_ms": latency_ms, "fills_per_minute_stats": summary["fills_per_minute_stats"],
                "recount_agrees": summary["recount"]["agrees"],
                "fill_vs_nbbo_touch_violations": summary["fill_vs_nbbo_touch"]["violation_count"],
                "reject_reasons": summary["reject_reasons"], "denied_reasons": summary["denied_reasons"]}

    profiles = list(PROFILES) if args.profile == "all" else [args.profile]
    summaries = []
    latency_sensitivity = []
    for profile_name in profiles:
        primary = run_one(quotes, trades, profile_name=profile_name, latency_ms=PRIMARY_LATENCY_MS)
        primary_summary = summarize_run(primary, quotes)
        summaries.append(primary_summary)
        if profile_name != "elite-tier":
            # Latency sensitivity is run once, on the elite-tier profile (the
            # profile carrying the >=180 fills/min claim); paper-parity is
            # reported only at the primary 70ms latency since its headline
            # number is capped by the rate limiter, not by latency.
            continue
        for latency_ms in LATENCY_SWEEP_MS:
            if latency_ms == PRIMARY_LATENCY_MS:
                latency_sensitivity.append(_sweep_entry(latency_ms, primary_summary))
                continue
            result = run_one(quotes, trades, profile_name=profile_name, latency_ms=latency_ms)
            summary = summarize_run(result, quotes)
            latency_sensitivity.append(_sweep_entry(latency_ms, summary))

    # cmd_run raises explicit errors on these checks, rather than merely
    # computing and reporting them, and rather than using `assert` (which
    # Python's -O flag silently disables): an unhandled RuntimeError here is
    # the intended failure mode if a future change ever makes NautilusTrader's
    # own fills report disagree with the strategy's own counters, or lets a
    # fill beat the NBBO touch, in ANY run -- primary or latency-sweep alike.
    for s in summaries:
        if not s["recount"]["agrees"]:
            raise RuntimeError(f"recount disagreement in profile {s['profile']}")
        if s["fill_vs_nbbo_touch"]["violation_count"] != 0:
            raise RuntimeError(f"{s['fill_vs_nbbo_touch']['violation_count']} exerciser fill(s) beat the "
                               f"NBBO touch in profile {s['profile']} (see H1 in README.md)")
    for row in latency_sensitivity:
        if not row["recount_agrees"]:
            raise RuntimeError(f"recount disagreement at latency {row['latency_ms']}ms")
        if row["fill_vs_nbbo_touch_violations"] != 0:
            raise RuntimeError(f"{row['fill_vs_nbbo_touch_violations']} exerciser fill(s) beat the NBBO "
                               f"touch at latency {row['latency_ms']}ms (see H1 in README.md)")

    runner_sha256 = fetcher.rc.digest_bytes(Path(__file__).read_bytes())
    engine_versions = {"nautilus_trader": importlib.metadata.version("nautilus_trader"),
                        "alpaca_py": importlib.metadata.version("alpaca-py"),
                        "python": platform.python_version()}
    receipt = {
        "evidence_class": "sim_capacity_infrastructure",
        "claim_boundary": ("This receipt measures simulation-lane fill throughput under a native rate "
                            "limiter, a primary-reference (not calibrated) latency setting and a cited "
                            "fee model. It is a synthetic fixture for infrastructure capacity only and "
                            "must never be cited as broker throughput or strategy performance "
                            "(docs/harness-rules-convergence-20260922.md NS-06); no order here reacts to "
                            "a signal, and no strategy manufactures a trade to hit a throughput target "
                            "(blueprints/us-equities/adaptive-paper/README.md L41). The elite-tier "
                            "limiter is deliberately made to bind (submits attempted above its budget) "
                            "so a non-binding limiter cannot be misread as broker throughput either."),
        "generated_at_utc": utcnow_iso(),
        "window": fetch_manifest["window"], "symbols": fetch_manifest["symbols"],
        "engine_feed_note": ("The engine is fed QuoteTicks only (quotes-only); trade ticks are fetched "
                             "and written to the private ParquetDataCatalog for future passive-order "
                             "work, but are not replayed into this engine run -- see H1 in README.md and "
                             "run_one's docstring. The catalog itself is not read back by this run "
                             "(quotes/trades are read from the private normalized JSON instead); a future "
                             "BacktestNode-based run could read from it directly."),
        "data": {"quote_counts": fetch_manifest["quote_counts"], "trade_counts": fetch_manifest["trade_counts"],
                  "quote_drop_counts": fetch_manifest["quote_drop_counts"],
                  "trade_drop_counts": fetch_manifest["trade_drop_counts"],
                  "counts_exclude_flatten_pad": True,
                  "this_run_page_count": fetch_manifest["page_events"]["this_run_page_count"],
                  "this_run_page_hashes": fetch_manifest["page_events"]["this_run_page_hashes"],
                  "this_run_page_hashes_digest": fetch_manifest["page_events"]["this_run_page_hashes_digest"],
                  "no_aggressor_note": ("Alpaca historical trades carry no aggressor-side field. This is "
                                        "moot for this run's engine feed (trades are not replayed into "
                                        "the engine at all -- see engine_feed_note/H1); it still matters "
                                        "for the catalog's trade ticks, tagged AggressorSide.NO_AGGRESSOR, "
                                        "which is why they are kept for future passive-order work only, "
                                        "not replayed as taker-side liquidity here.")},
        "profiles": {name: PROFILES[name] for name in profiles},
        "runs": summaries,
        "latency_sensitivity_elite_tier": latency_sensitivity,
        "latency_note": ("PRIMARY_LATENCY_MS=70 is a primary-reference point, chosen near the retained "
                         "sim-to-paper receipt's own sensitivity-check flip point (~69.2ms) -- it is far "
                         "BELOW that receipt's observed paper submit-to-fill range (0.65-1.09s), not "
                         "inside it; of this lane's own 0/70/250/1000ms sweep points, 1000ms is the "
                         "closest to that observed range. It is explicitly NOT a calibration (that "
                         "receipt itself says 'Sensitivity check, not a calibration'). "
                         "On rc5 a deferred order is released at the first of its own next quote or ANY "
                         "due clock timer, so the exerciser's own tick cadence mixes into the measured "
                         "submit-to-fill distribution alongside the configured latency; the sweep below "
                         "therefore varies configured latency together with that timer-cadence effect, "
                         "not latency alone. See each run's submit_to_fill_latency_ms for the measured "
                         "distribution."),
        "fee_model": {
            "alpaca_commission_usd": "0 (retail routing)",
            "sec_section31_usd_per_dollar": "20.60/1000000 (effective 2026-04-04, open-ended at retrieval)",
            "finra_taf_usd_per_share": "0.000195", "finra_taf_cap_usd_per_trade": "9.79",
            "finra_cat_usd_per_share": "0.000003 (buys and sells)",
            "elite_commission_all_in_usd_per_share": "0.0040 (elite-tier profile only, both sides)",
            "elite_commission_cost_plus_usd_per_share": "0.0025 (partial: excludes exchange fee/rebate pass-through)",
            "source_sec_taf": "blueprints/us-equities/mover-v3/data/fees-v3.json (retrieved_at 2026-09-24)",
            "source_cat_and_elite": ("https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf "
                                     "(Revised on September 17, 2026; retrieved 2026-09-25; sha256 "
                                     "7bc75e3cd86f5c1950f8ce1292049965280340a3cebe727ca7aee4a7d2d71b12)"),
            "taf_cap_scope": ("Per execution for this exerciser (settled): FINRA TAF FAQ A200.17 -- "
                             "https://www.finra.org/rules-guidance/guidance/faqs/trading-activity-fee -- "
                             "verbatim, a member 'may choose to calculate the Trading Activity Fee on "
                             "either the individual street side executions or on the account level "
                             "average price confirmation' (its own example: ten 100,000-share executions "
                             "of a 1,000,000-share order bill as 'ten sales at $5' under the "
                             "street-side-execution method, vs 'one sale at $5' under the account-level "
                             "method; this choice is specifically for average-price-allocated orders). "
                             "This exerciser does no average-price allocation, so the "
                             "street-side-execution (per-fill) method applies."),
            "partial": ["The cost_plus commission plan's exchange-fee/rebate pass-through component "
                        "is not modeled."],
            "rounding_method_note": ("Alpaca aggregates each fee type per day, per account, and rounds "
                                     "the day's total UP to the cent; this model instead rounds each "
                                     "fill's total fee half-up. See each run's fee_rounding for the "
                                     "measured difference on this run's actual fills."),
        },
        "engine_and_runtime": engine_versions,
        "runner_sha256": runner_sha256,
        "argv": redact_args(args),
    }
    save(args.receipt, receipt)
    print(json.dumps({"receipt": str(args.receipt), "profiles_run": profiles,
                       "recount_agrees": all(s["recount"]["agrees"] for s in summaries)}, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch")
    fetch_p.add_argument("--pages", type=Path, required=True)
    fetch_p.add_argument("--catalog", type=Path, required=True)
    fetch_p.add_argument("--replay", action="store_true",
                          help="Reuse retained pages only; no network request, no credential file opened")
    fetch_p.set_defaults(func=cmd_fetch)

    run_p = sub.add_parser("run")
    run_p.add_argument("--catalog", type=Path, required=True)
    run_p.add_argument("--receipt", type=Path, required=True)
    run_p.add_argument("--profile", choices=["all", *PROFILES], default="all")
    run_p.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
