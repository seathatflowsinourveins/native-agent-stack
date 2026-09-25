"""Read-only Alpaca SIP quote/trade fetch, page retention and NautilusTrader
catalog build for the sim-capacity infrastructure lane.

Reuses `sim-paper-compare/replay_compare.py`'s `PageFetcher` (gzip pages plus a
sha256 ledger, `--replay` never touches the network or a credential file) and
`adaptive-paper/runner.py`'s `credentials()` loader, rather than reimplementing
either. This module adds only what sim-capacity needs on top: a trades fetch
(in addition to quotes), crossed-quote/trade normalization for both books, and
a `ParquetDataCatalog` write.

This is infrastructure evidence only (see README.md `claim_boundary`); nothing
here manufactures a trade to hit a throughput target.
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SIM_PAPER_COMPARE = HERE.parents[0] / "sim-paper-compare"
ADAPTIVE_PAPER = HERE.parents[0] / "adaptive-paper"

for _p in (str(SIM_PAPER_COMPARE), str(ADAPTIVE_PAPER), str(REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replay_compare as rc  # noqa: E402  (PageFetcher, digest_bytes, save, ts_ns, ns_to_iso, chmod_private_dir)
import credential_status as cs  # noqa: E402

DATA = rc.DATA
SYMBOLS = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMD", "TSLA")
WINDOW_START_ISO = "2026-09-24T14:00:00Z"  # the reported/analysis window: exactly 30
WINDOW_END_ISO = "2026-09-24T14:30:00Z"    # regular-session minutes, avoiding the open
FETCH_END_ISO = "2026-09-24T14:35:00Z"     # +5min pad fetched (never reported as
# analysis data) purely so the exerciser's end-of-window flatten has quotes to
# execute its close orders against, and so the shared rate-limit budget has
# room to refill before those closes submit, without eating into the 30
# reported minutes' own submit schedule (see exerciser.py's on_start).
VENUE_NAME = "SIM"


def resolve_paper_credential_path(env=None, root: Path = REPO_ROOT) -> Path:
    """Resolve the alpaca-paper inventory entry's store path via
    `credential_status.expand_template`, exactly as
    `tools/credentials/alpaca_rate_limit_probe.py.paper_store_file` does. Never
    reads, prints or logs the resolved path's contents here."""
    inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    entry = next(e for e in inventory["entries"] if e["id"] == "alpaca-paper")
    return cs.expand_template(entry["store"]["path_template"], os.environ if env is None else env)


def load_credentials(replay: bool):
    """Never opens a credential file in --replay mode: PageFetcher(replay=True)
    never sends a request, so no header/credential is required at all."""
    if replay:
        return None, None
    sys.path.insert(0, str(ADAPTIVE_PAPER))
    import runner as adaptive_runner  # noqa: E402  (adaptive-paper credential loader)
    path = resolve_paper_credential_path()
    return adaptive_runner.credentials(path)


def fetch_quotes(fetcher: "rc.PageFetcher", symbols=SYMBOLS, start_iso=WINDOW_START_ISO,
                  end_iso=FETCH_END_ISO) -> dict[str, list[dict]]:
    quotes: dict[str, list[dict]] = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "start": start_iso, "end": end_iso,
              "feed": "sip", "limit": 10000, "sort": "asc"}
    for body in fetcher.get(DATA, "/v2/stocks/quotes", params):
        for symbol, rows in (body.get("quotes") or {}).items():
            quotes[symbol].extend(rows)
    return quotes


def fetch_trades(fetcher: "rc.PageFetcher", symbols=SYMBOLS, start_iso=WINDOW_START_ISO,
                  end_iso=FETCH_END_ISO) -> dict[str, list[dict]]:
    trades: dict[str, list[dict]] = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "start": start_iso, "end": end_iso,
              "feed": "sip", "limit": 10000, "sort": "asc"}
    for body in fetcher.get(DATA, "/v2/stocks/trades", params):
        for symbol, rows in (body.get("trades") or {}).items():
            trades[symbol].extend(rows)
    return trades


def normalize_quotes(raw_rows: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Keep two-sided, positively priced NBBO quotes, dropping crossed quotes
    (bid > ask). Locked quotes (bid == ask) are kept. Same algorithm as
    `replay_compare.normalize_quote_rows`, reimplemented locally (rather than
    imported) so sim-capacity's own crossed-quote-dropping behavior has an
    independent, directly-testable unit here."""
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
            kept.append({"symbol": symbol, "ts_ns": rc.ts_ns(row["t"]),
                         "bid": str(Decimal(str(bp)).quantize(Decimal("0.01"))),
                         "ask": str(Decimal(str(ap)).quantize(Decimal("0.01"))),
                         "bid_size": int(bs), "ask_size": int(asz)})
        kept.sort(key=lambda q: q["ts_ns"])
        out[symbol] = kept
        drop_counts[symbol] = dropped
    return out, drop_counts


def normalize_trades(raw_rows: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Keep positively priced/sized trades. Alpaca's historical trade record
    carries no aggressor-side field (no `taker_side`/`aggressor` key in the SIP
    trade schema), so every trade is tagged NO_AGGRESSOR downstream in
    `to_trade_ticks`. Documented consequence: a matching/queue model that relies
    on aggressor side to deplete the resting side of the book cannot do so from
    this data, which makes any queue-depletion-based fill estimate from these
    trade ticks optimistic (it never actually removes liquidity from a known
    side) -- disclosed here and in README.md rather than worked around with a
    heuristic side classifier, which would need its own calibration/validation."""
    out: dict[str, list[dict]] = {}
    drop_counts: dict[str, dict] = {}
    for symbol, rows in raw_rows.items():
        kept = []
        dropped = {"nonpositive": 0}
        for row in rows:
            p, s = row.get("p"), row.get("s")
            if not p or p <= 0 or not s or s <= 0:
                dropped["nonpositive"] += 1
                continue
            kept.append({"symbol": symbol, "ts_ns": rc.ts_ns(row["t"]),
                         "price": str(Decimal(str(p)).quantize(Decimal("0.0001"))),
                         "size": int(s), "trade_id": str(row.get("i", len(kept)))})
        kept.sort(key=lambda t: t["ts_ns"])
        out[symbol] = kept
        drop_counts[symbol] = dropped
    return out, drop_counts


def build_catalog(catalog_dir: Path, quotes_by_symbol: dict[str, list[dict]],
                   trades_by_symbol: dict[str, list[dict]]):
    """Write a NautilusTrader ParquetDataCatalog under `catalog_dir` (a private,
    non-repo directory) from normalized quote/trade rows. Requires the pinned
    nautilus_trader runtime; import is deferred so pure normalization above
    stays importable (and testable) on system Python without nautilus_trader
    installed."""
    from nautilus_trader.model import (AggressorSide, Currency, Equity, InstrumentId, Price,
                                        Quantity, QuoteTick, Symbol, TradeId, TradeTick)
    from nautilus_trader.persistence import ParquetDataCatalog

    usd, venue_name = Currency.from_str("USD"), VENUE_NAME
    symbols = sorted(set(quotes_by_symbol) | set(trades_by_symbol))
    instruments = {}
    for symbol in symbols:
        iid = InstrumentId.from_str(f"{symbol}.{venue_name}")
        instruments[symbol] = Equity(iid, Symbol(symbol), usd, 2, Price.from_str("0.01"), 0, 0,
                                      lot_size=Quantity.from_int(1))

    total_quotes = total_trades = 0
    catalog_dir.mkdir(parents=True, exist_ok=True)
    rc.chmod_private_dir(catalog_dir)
    catalog = ParquetDataCatalog(str(catalog_dir))
    catalog.write_instruments(list(instruments.values()))
    # Written per instrument: the catalog writer refuses a single call mixing
    # more than one instrument's identity metadata ("write each instrument or
    # bar type separately", raised directly by the pinned runtime).
    for symbol, rows in quotes_by_symbol.items():
        if not rows:
            continue
        iid = instruments[symbol].id
        ticks = [QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                            Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                            row["ts_ns"], row["ts_ns"]) for row in rows]
        ticks.sort(key=lambda t: t.ts_event)
        catalog.write_quote_ticks(ticks)
        total_quotes += len(ticks)
    for symbol, rows in trades_by_symbol.items():
        if not rows:
            continue
        iid = instruments[symbol].id
        ticks = [TradeTick(iid, Price(Decimal(row["price"]), 2), Quantity.from_int(row["size"]),
                            AggressorSide.NO_AGGRESSOR, TradeId(row["trade_id"]),
                            row["ts_ns"], row["ts_ns"]) for row in rows]
        ticks.sort(key=lambda t: t.ts_event)
        catalog.write_trade_ticks(ticks)
        total_trades += len(ticks)
    return {"instruments": sorted(instruments), "quote_ticks": total_quotes, "trade_ticks": total_trades}
