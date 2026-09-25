#!/usr/bin/env python3
"""sim-capacity: build and run the simulation-lane capacity infrastructure test
on NautilusTrader 2.0.0rc5.

This is INFRASTRUCTURE EVIDENCE ONLY (evidence_class `sim_capacity_infrastructure`):
it measures how many fills/minute the pinned engine, a native rate limiter, a
calibrated latency model, realistic L1 execution (trade_execution,
liquidity_consumption, queue_position all on) and a cited fee model can sustain.
No strategy manufactures a trade to hit a throughput target (see
blueprints/us-equities/adaptive-paper/README.md L40 and
blueprints/us-equities/mover-v3/README.md's "A high-rate capacity replay is an
infrastructure test, never strategy evidence").

  python3 runner.py fetch --pages PRIVATE/pages --catalog PRIVATE/catalog \
      --env-file "$PAPER_ENV_FILE" [--replay]
  python3 runner.py run --catalog PRIVATE/catalog --out PRIVATE/run \
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
from decimal import Decimal
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
    "paper-parity": {"max_order_submit_rate": "180/00:01:00", "submits_per_sec": 5.0,
                      "note": "Mirrors Alpaca standard tier: 200 req/min x 0.9 = 180/min. "
                              "Fills cannot exceed 180/min here by construction of the limiter."},
    "elite-tier": {"max_order_submit_rate": "900/00:01:00", "submits_per_sec": 15.0,
                    "note": "Alpaca Elite / non-retail tier: 1000 req/min x 0.9 = 900/min. "
                            "Must sustain >=180 fills/min in every full simulated minute."},
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

    manifest = {
        "fetched_at_utc": utcnow_iso(),
        "window": {"start": fetcher.WINDOW_START_ISO, "end": fetcher.WINDOW_END_ISO},
        "symbols": list(fetcher.SYMBOLS),
        "quote_counts": {s: len(v) for s, v in quotes.items()},
        "trade_counts": {s: len(v) for s, v in trades.items()},
        "quote_drop_counts": quote_drops,
        "trade_drop_counts": trade_drops,
        "catalog_stats": catalog_stats,
        "page_events": {"from_cache": pf.from_cache, "from_network": pf.from_network,
                        "page_hashes": sorted({rec["sha256"] for rec in pf.ledger.values()})},
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
    `datetime64[ns, UTC]` column to a true integer nanosecond epoch via
    `.astype('int64')` first. `DataFrame.to_json`'s default 'epoch' date format
    does NOT round-trip to raw event-time nanoseconds for these tz-aware
    columns (verified directly on the pinned runtime: a `ts_event` of
    `1970-01-21 20:00:00.500000+00:00`, i.e. 1,800,000,500,000 ns, serializes
    through `to_json(date_format='epoch')` as `1800000500` -- three orders of
    magnitude off, not a units mismatch alone). This is exactly the pandas
    report trap `sim-paper-compare/replay_compare.py`'s module docstring
    warns about ("no tz-aware-column-to-int64 conversion in between"); this
    helper does that conversion explicitly and is unit-tested directly against
    that reproduced case."""
    out = df.reset_index()
    for column in out.columns:
        if str(out[column].dtype).startswith("datetime64"):
            out[column] = out[column].astype("int64")
    return out.to_dict(orient="records")


def run_one(quotes_by_symbol: dict, trades_by_symbol: dict, *, profile_name: str, latency_ms: int,
            run_seconds: float = RUN_SECONDS) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, RiskEngineConfig
    from nautilus_trader.execution import StaticLatencyModel
    from nautilus_trader.model import (AccountType, AggressorSide, BookType, Currency, Equity, InstrumentId,
                                        Money, OmsType, Price, Quantity, QuoteTick, Symbol, TradeId, TradeTick,
                                        Venue)

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

    ticks = []
    start_ns = min(row["ts_ns"] for rows in quotes_by_symbol.values() for row in rows)
    for symbol, rows in quotes_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                                    Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                                    row["ts_ns"], row["ts_ns"]))
    for symbol, rows in trades_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(TradeTick(iid, Price(Decimal(row["price"]), 2), Quantity.from_int(row["size"]),
                                    AggressorSide.NO_AGGRESSOR, TradeId(row["trade_id"]),
                                    row["ts_ns"], row["ts_ns"]))
    ticks.sort(key=lambda t: t.ts_event)

    engine_cfg = BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR),
                                       risk_engine=RiskEngineConfig(max_order_submit_rate=profile["max_order_submit_rate"]))
    engine = BacktestEngine(engine_cfg)
    fee_model = build_nautilus_fee_model()
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

        return {
            "profile": profile_name, "latency_ms": latency_ms, "start_ns": start_ns,
            "counters": dict(strategy.counters), "events": strategy.events,
            "filled_qty": strategy.filled_qty, "filled_notional": str(strategy.filled_notional),
            "fills_report_rows": fill_rows, "order_fills_report_rows": order_fill_rows,
            "n_ticks": len(ticks), "wall_seconds": wall_seconds,
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


def naive_l1_marketability_sample(events: list[dict], quotes_by_symbol: dict, latency_ns: int, sample_size: int = 200) -> dict:
    """For a sample of fills, independently re-derive whether the order was
    marketable against the quote in force at its modelled arrival time
    (submit_ts + latency), using only the retained normalized quote rows (never
    the engine's own internal book state) -- an offline cross-check of the
    engine's own fill decision, not a re-statement of it."""
    submits_by_id = {ev["client_order_id"]: ev for ev in events if ev["kind"] == "submit"}
    fills = [ev for ev in events if ev["kind"] == "fill"]
    sample = fills[:sample_size]
    checked, agree = 0, 0
    disagreements = []
    for fill in sample:
        submit = submits_by_id.get(fill["client_order_id"])
        if submit is None:
            continue
        symbol = submit["symbol"]
        arrival_ns = submit["ts_ns"] + latency_ns
        rows = quotes_by_symbol.get(symbol, [])
        # last quote at or before arrival_ns
        in_force = None
        for row in rows:
            if row["ts_ns"] <= arrival_ns:
                in_force = row
            else:
                break
        if in_force is None:
            continue
        checked += 1
        limit_price = Decimal(submit["limit_price"])  # the order's actual submitted limit, not the fill price
        side = submit["side"]
        marketable = (limit_price >= Decimal(in_force["ask"])) if side == "BUY" else (limit_price <= Decimal(in_force["bid"]))
        if marketable:
            agree += 1
        else:
            disagreements.append({"client_order_id": fill["client_order_id"], "symbol": symbol})
    return {"checked": checked, "agree": agree, "disagreements": disagreements[:20],
            "sample_size_requested": sample_size}


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

    latency_ns = result["latency_ms"] * 1_000_000
    naive_check = naive_l1_marketability_sample(events, quotes_by_symbol, latency_ns)

    return {
        "profile": result["profile"], "latency_ms": result["latency_ms"],
        "per_minute": {"submits": {m: buckets[m].get("submits", 0) for m in sorted(buckets)},
                        "fills": {m: buckets[m].get("fills", 0) for m in sorted(buckets)},
                        "ioc_expiries": {m: buckets[m].get("ioc_expiry", 0) for m in sorted(buckets)},
                        "rate_limit_denied": {m: buckets[m].get("denied", 0) for m in sorted(buckets)}},
        "fills_per_minute_stats": strategy_stats,
        "counters": result["counters"],
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
        "naive_l1_marketability_sample": naive_check,
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
                latency_sensitivity.append({"latency_ms": latency_ms,
                                             "fills_per_minute_stats": primary_summary["fills_per_minute_stats"],
                                             "recount_agrees": primary_summary["recount"]["agrees"]})
                continue
            result = run_one(quotes, trades, profile_name=profile_name, latency_ms=latency_ms)
            summary = summarize_run(result, quotes)
            latency_sensitivity.append({"latency_ms": latency_ms,
                                         "fills_per_minute_stats": summary["fills_per_minute_stats"],
                                         "recount_agrees": summary["recount"]["agrees"]})

    runner_sha256 = fetcher.rc.digest_bytes(Path(__file__).read_bytes())
    engine_versions = {"nautilus_trader": importlib.metadata.version("nautilus_trader"),
                        "alpaca_py": importlib.metadata.version("alpaca-py"),
                        "python": platform.python_version()}
    receipt = {
        "evidence_class": "sim_capacity_infrastructure",
        "claim_boundary": ("This receipt measures simulation-lane fill throughput under a native rate "
                            "limiter, calibrated latency and a cited fee model. It is a synthetic fixture "
                            "for infrastructure capacity only and must never be cited as broker throughput "
                            "or strategy performance (docs/harness-rules-convergence-20260922.md NS-06); no "
                            "order here reacts to a signal, and no strategy manufactures a trade to hit a "
                            "throughput target (blueprints/us-equities/adaptive-paper/README.md L40)."),
        "generated_at_utc": utcnow_iso(),
        "window": fetch_manifest["window"], "symbols": fetch_manifest["symbols"],
        "data": {"quote_counts": fetch_manifest["quote_counts"], "trade_counts": fetch_manifest["trade_counts"],
                  "quote_drop_counts": fetch_manifest["quote_drop_counts"],
                  "trade_drop_counts": fetch_manifest["trade_drop_counts"],
                  "page_hashes": fetch_manifest["page_events"]["page_hashes"],
                  "no_aggressor_note": ("Alpaca historical trades carry no aggressor-side field; every "
                                        "TradeTick built here is tagged AggressorSide.NO_AGGRESSOR. A "
                                        "queue-depletion fill model that relies on aggressor side to remove "
                                        "resting liquidity therefore never actually depletes a known side "
                                        "from this trade data, which makes queue-position-based fill "
                                        "estimates from these trade ticks optimistic.")},
        "profiles": {name: PROFILES[name] for name in profiles},
        "runs": summaries,
        "latency_sensitivity_elite_tier": latency_sensitivity,
        "fee_model": {
            "alpaca_commission_usd": "0",
            "sec_section31_usd_per_dollar": "20.60/1000000 (effective 2026-04-04, open-ended at retrieval)",
            "finra_taf_usd_per_share": "0.000195", "finra_taf_cap_usd_per_trade": "9.79",
            "source": "blueprints/us-equities/mover-v3/data/fees-v3.json (retrieved_at 2026-09-24)",
            "unverified": ["Whether the FINRA TAF cap applies per order or per execution/fill; this model "
                           "applies it per fill (see fee_model.py module docstring)."],
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
