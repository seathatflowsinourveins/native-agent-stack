#!/usr/bin/env python3
"""Provider-, symbol- and session-range-parameterized successor of authenticated-data/compare.py.

Gap 5 (market-data-reference, gap wave 2, 2026-09-23). Two sources are compared in memory:
a *reference* and a *provider*, each chosen from a registry of source adapters. Only
aggregate counts, the maximum absolute close difference and input hashes are printed;
prices never leave the process. Matching values do not establish original historical
availability or data rights.

Source kinds (``KIND:ARG[,ARG...]``):
  alpaca-run:RUN_DIR,RECEIPT_SHA256   receipt-verified private collect.py run (bars + actions)
  alpaca-parquet:PATH                 retained broad-market Alpaca SIP daily parquet (raw_c column; needs duckdb)
  normalized-csv:PATH                 any provider export with header symbol,session_date,close[,...]
                                      (decimal text; e.g. a Databento or Massive daily export)
  lean-probe:PATH,SHA256              frozen LEAN CorporateActionProbe native-results.json (bars + events)
  lean-daily:DATA_DIR                 LEAN bundled Data/equity/usa/daily/<sym>.zip (raw deci-cent integers)

For the AAPL 25-session reference arm, the per-symbol result has exactly the shape and values
of the original compare.py output (checked by gap-5 receipt), so earlier receipts stay comparable.
"""
import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / "blueprints/us-equities/authenticated-data/compare.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original = _load(ORIGINAL, "authenticated_compare")
numeric = original.numeric  # identical decimal validation to the original comparator


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Source:
    """bars: {symbol: {session_date: decimal_text}} or a stage failure; actions/events optional."""

    def __init__(self, kind, label, bars_status="complete", reason=None):
        self.kind, self.label = kind, label
        self.bars_status, self.bars_reason = bars_status, reason
        self.bars = {}
        self.actions = None  # provider side: {"status", "rows"} as produced by collect.py
        self.events = None   # reference side: {symbol: [event dicts]}
        self.hashes = {}


def _put(source, symbol, day, close):
    per = source.bars.setdefault(symbol, {})
    if day in per:
        raise ValueError("duplicate_date_or_wrong_symbol")
    per[day] = close


def alpaca_run(args, symbols, start, end):
    run, receipt = args
    collector = original.load_collector()
    stages = collector.verify(Path(run), receipt)
    src = Source("alpaca-run", "Alpaca private collect.py run")
    src.hashes["alpaca_receipt"] = receipt
    bars = stages["bars"]
    if bars["status"] != "complete":
        src.bars_status, src.bars_reason = "unavailable", bars.get("reason", "stage_failed")
    else:
        for row in bars["rows"]:
            if row["symbol"] in symbols and start <= row["session_date"] <= end:
                _put(src, row["symbol"], row["session_date"], row["c"])
    actions = stages["actions"]
    if actions["status"] == "complete":
        # Fix round 1: keep only requested symbols and rows whose ex_date (when present) is in range.
        actions = dict(actions, rows=[r for r in actions["rows"] if r.get("symbol") in symbols
                                      and (r.get("ex_date") is None or start <= r["ex_date"] <= end)])
    src.actions = actions
    return src


def alpaca_parquet(args, symbols, start, end):
    import duckdb  # only this adapter needs it
    (path,) = args
    src = Source("alpaca-parquet", "Alpaca broad-market SIP raw daily parquet")
    src.hashes["alpaca_parquet_bytes"] = Path(path).stat().st_size
    con = duckdb.connect()
    rows = con.execute(
        "select symbol, strftime(session_date, '%Y-%m-%d'), raw_c from read_parquet(?) "
        "where in_raw and symbol in (select unnest(?)) and session_date between ?::date and ?::date "
        "order by symbol, session_date", [path, sorted(symbols), start, end]).fetchall()
    for symbol, day, close in rows:
        # repr() is the shortest round-tripping decimal text of the stored double.
        _put(src, symbol, day, repr(float(close)))
    return src


def normalized_csv(args, symbols, start, end):
    (path,) = args
    src = Source("normalized-csv", "normalized provider export")
    src.hashes["normalized_csv"] = sha256_file(path)
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"symbol", "session_date", "close"} <= set(reader.fieldnames or []):
            raise ValueError("normalized_csv_header")
        for row in reader:
            if row["symbol"] in symbols and start <= row["session_date"] <= end:
                _put(src, row["symbol"], row["session_date"], row["close"])
    return src


def lean_probe(args, symbols, start, end):
    path, expected = args
    collector = original.load_collector()
    raw = collector.read(Path(path))
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("lean_reference_hash_mismatch")
    lean = collector.strict_json(raw)
    src = Source("lean-probe", "LEAN CorporateActionProbe native results")
    src.hashes["lean_native_results"] = expected
    for row in lean["observations"]:
        if row["mapped_symbol"] != lean["symbol"]:
            raise ValueError("duplicate_date_or_wrong_symbol")
        if lean["symbol"] in symbols and start <= row["date"] <= end:
            _put(src, lean["symbol"], row["date"], row["raw_close"])
    src.events = {lean["symbol"]: [e for e in lean["events"] if start <= e["date"] <= end]}
    return src


def lean_daily(args, symbols, start, end):
    (data_dir,) = args
    src = Source("lean-daily", "LEAN bundled raw daily equity data")
    for symbol in sorted(symbols):
        path = Path(data_dir) / "daily" / (symbol.lower() + ".zip")
        if not path.exists():
            continue
        src.hashes["lean_daily_" + symbol] = sha256_file(path)
        with zipfile.ZipFile(path) as archive:
            (member,) = archive.namelist()
            for line in io.TextIOWrapper(archive.open(member), encoding="ascii"):
                stamp, _o, _h, _l, close, _v = line.strip().split(",")
                day = f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"
                if start <= day <= end:
                    # LEAN stores equity prices as integer deci-cents (price * 10000).
                    _put(src, symbol, day, str(Decimal(close).scaleb(-4)))
    return src


ADAPTERS = {"alpaca-run": alpaca_run, "alpaca-parquet": alpaca_parquet, "normalized-csv": normalized_csv,
            "lean-probe": lean_probe, "lean-daily": lean_daily}


def open_source(spec, symbols, start, end):
    kind, _, rest = spec.partition(":")
    if kind not in ADAPTERS:
        raise ValueError("unknown_source_kind")
    return ADAPTERS[kind](rest.split(",") if rest else [], symbols, start, end)


def compare_bars(reference, provider):
    for value in reference.values():
        numeric(value)
    common = sorted(reference.keys() & provider.keys())
    with localcontext() as context:
        context.prec = 200
        deltas = [numeric(provider[d]) - numeric(reference[d]) for d in common]
    missing, extra = len(reference.keys() - provider.keys()), len(provider.keys() - reference.keys())
    mismatches = sum(d != 0 for d in deltas)
    return {"status": "equal" if not (missing or extra or mismatches) else "differences",
            "compared": len(common), "equal": len(common) - mismatches, "different": mismatches,
            "missing": missing, "extra": extra,
            "maximum_absolute_close_difference": str(max(d.copy_abs() for d in deltas)) if deltas else None}


def compare_actions(symbol, events, actions):
    """The original compare.py action logic with the symbol parameterized."""
    if actions["status"] != "complete":
        return {"status": "unavailable", "reason": actions.get("reason", "stage_failed"), "compared": 0}
    counts = {"equal": 0, "different": 0, "missing": 0, "ambiguous": 0, "unknown_currency": 0}
    numeric_matches = 0
    for event in events:
        kind = {"dividend": "cash_dividend", "split": "forward_split"}[event["kind"]]
        candidates = [r for r in actions["rows"] if r["type"] == kind and r.get("ex_date") == event["date"]
                      and r.get("qualification") == "qualified" and r.get("symbol") == symbol]
        if len(candidates) != 1:
            counts["ambiguous" if candidates else "missing"] += 1
            continue
        row = candidates[0]
        with localcontext() as context:
            context.prec = 200
            value_equal = (numeric(row["rate"], allow_zero=True) == numeric(event["distribution"], allow_zero=True)) if kind == "cash_dividend" else (
                numeric(row["old_rate"]) == numeric(event["factor"]) * numeric(row["new_rate"]))
        numeric_matches += value_equal
        if kind == "cash_dividend" and row.get("currency") is None:
            counts["unknown_currency"] += 1
        else:
            equal = value_equal and (kind != "cash_dividend" or row["currency"] == "USD")
            counts["equal" if equal else "different"] += 1
    return {"status": "equal" if counts["equal"] == len(events) else "reconciliation_incomplete",
            "reference_events": len(events), "provider_records": sum(r.get("symbol") == symbol for r in actions["rows"]),
            "compared": counts["equal"] + counts["different"] + counts["unknown_currency"],
            "numeric_values_equal": numeric_matches, **counts,
            "scope": "qualified ex-date/type candidates; cash per raw share and old/new split ratio; process-date window may omit events"}


def compare(reference, provider, symbols, expect_sessions=None):
    results = {}
    for symbol in symbols:
        ref = reference.bars.get(symbol, {})
        if expect_sessions is not None and len(ref) != expect_sessions:
            raise ValueError("unsupported_reference_session_count")
        result = {"reference_sessions": len(ref), "basis": "raw daily close by New York session date",
                  "original_historical_availability": "not_established", "strategy_or_return_computed": False}
        # Fix round 1: an unavailable or empty reference is never reported as equal.
        if reference.bars_status != "complete":
            result["bars"] = {"status": "unavailable", "reason": "reference_" + (reference.bars_reason or "stage_failed"), "compared": 0}
        elif not ref:
            result["bars"] = {"status": "unavailable", "reason": "no_reference_sessions", "compared": 0}
        elif provider.bars_status != "complete":
            result["bars"] = {"status": "unavailable", "reason": provider.bars_reason or "stage_failed", "compared": 0}
        else:
            result["bars"] = compare_bars(ref, provider.bars.get(symbol, {}))
        if reference.events is not None and provider.actions is not None and symbol in reference.events:
            result["actions"] = compare_actions(symbol, reference.events[symbol], provider.actions)
        else:
            result["actions"] = {"status": "not_scored", "reason": "reference has no events or provider has no action stage", "compared": 0}
        results[symbol] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--symbols", required=True, help="comma-separated, e.g. AAPL,IBM")
    parser.add_argument("--start", required=True, help="inclusive New York session date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="inclusive New York session date YYYY-MM-DD")
    parser.add_argument("--expect-sessions", type=int, help="fail unless every reference symbol has exactly N sessions")
    args = parser.parse_args()
    symbols = [s for s in args.symbols.split(",") if s]
    if not symbols or len(set(symbols)) != len(symbols) or args.start > args.end:
        raise ValueError("invalid_symbols_or_range")
    reference = open_source(args.reference, set(symbols), args.start, args.end)
    provider = open_source(args.provider, set(symbols), args.start, args.end)
    out = {"reference": reference.kind, "provider": provider.kind, "symbols": symbols,
           "session_range": [args.start, args.end],
           "results": compare(reference, provider, symbols, args.expect_sessions),
           "input_hashes": {**reference.hashes, **provider.hashes,
                            "comparison_code": sha256_file(__file__), "original_comparison_code": sha256_file(ORIGINAL)}}
    print(json.dumps(out, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
