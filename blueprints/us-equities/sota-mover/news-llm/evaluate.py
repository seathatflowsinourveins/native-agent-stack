#!/usr/bin/env python3
"""Confirmatory evaluation of the news-LLM direction study (runs only after the freeze).

Refuses to read any data unless protocol.json has status "frozen", frozen_before_outcomes
true, and its sha256 equals --protocol-sha256. Inputs whose sha256 the frozen protocol
lists under frozen_inputs must match too. Everything the protocol preregisters (windows,
prices, costs, portfolios, items, multiplicity, gates) is applied exactly once, here.

Core computations are pure functions (build_positions, series_stats, evaluate_items) so
the synthetic tests exercise every path without data; the loaders are thin.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone


_HERE = os.path.dirname(os.path.abspath(__file__))


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", os.path.join(_HERE, "news_signal.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
FROZEN_STATUS = "frozen"
PRIVATE_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm")
MINUTE_ROOT = os.path.expanduser("~/.local/share/native-agent-stack/minute-bars/stage1/bars")


class Refusal(SystemExit):
    """Raised before any data is read when the protocol is not frozen and pinned."""


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def check_protocol(path, expected_sha256):
    """Return the parsed protocol only if it is frozen and byte-identical to the pin."""
    if not expected_sha256 or len(expected_sha256) != 64:
        raise Refusal("refusing: --protocol-sha256 must be the 64-hex sha256 of the frozen protocol")
    with open(path, "rb") as handle:
        raw = handle.read()
    actual = sha256_bytes(raw)
    if actual != expected_sha256.lower():
        raise Refusal(f"refusing: protocol sha256 {actual} does not match --protocol-sha256")
    protocol = json.loads(raw)
    if protocol.get("status") != FROZEN_STATUS or protocol.get("frozen_before_outcomes") is not True:
        raise Refusal(
            f"refusing: protocol status is {protocol.get('status')!r} and frozen_before_outcomes is "
            f"{protocol.get('frozen_before_outcomes')!r}; evaluation needs status 'frozen' and true"
        )
    return protocol


def check_inputs(protocol, root):
    """Every frozen input the protocol pins must exist with the pinned sha256."""
    pinned = protocol.get("frozen_inputs") or {}
    missing = [k for k, v in pinned.items() if not v]
    if missing:
        raise Refusal(f"refusing: frozen_inputs without a sha256: {sorted(missing)}")
    for rel, digest in pinned.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            raise Refusal(f"refusing: frozen input missing: {rel}")
        if sha256_file(path) != digest:
            raise Refusal(f"refusing: frozen input changed: {rel}")


# --------------------------------------------------------------------------------------
# Pure evaluation
# --------------------------------------------------------------------------------------


def entry_cost_fraction(ev, costs, spread_lookup):
    """Per-side adverse cost at entry (fraction of price) for an event."""
    if ev["window"] == sig.RTH:
        hs = spread_lookup(ev)
        return hs + costs["rth_entry_allowance_bps"] / 1e4
    return costs["auction_slippage_bps_per_side"][ev["lane"]] / 1e4


def exit_cost_fraction(ev, costs):
    return costs["auction_slippage_bps_per_side"][ev["lane"]] / 1e4


def build_positions(events, scores, open_prices, close_prices, rth_entries, spread_lookup, fees, costs,
                    expected_template=None):
    """Positions with gross and net returns, plus exclusion counts.

    events: prepared events; scores: event_id -> score row; open_prices / close_prices:
    (symbol, session) -> price (official auction, already selected); rth_entries:
    event_id -> entry price from the first minute bar at/after release + 15 min.
    """
    positions = []
    excluded = Counter()
    for ev in events:
        row = scores.get(ev["event_id"])
        if row is None:
            excluded["no_score"] += 1
            continue
        if expected_template and row.get("template_sha256") != expected_template:
            excluded["template_mismatch"] += 1
            continue
        side = int(row["score"])
        if side == 0:
            excluded[f"no_position_{row['label']}"] += 1
            continue
        key = (ev["symbol"], ev["session"])
        exit_price = close_prices.get(key)
        if ev["window"] == sig.OVERNIGHT:
            entry_price = open_prices.get(key)
        else:
            entry_price = rth_entries.get(ev["event_id"])
        if entry_price is None:
            excluded[f"missing_entry_{ev['window']}"] += 1
            continue
        if exit_price is None:
            excluded[f"missing_exit_{ev['window']}"] += 1
            continue
        day = date.fromisoformat(ev["session"])
        entry_cost = entry_cost_fraction(ev, costs, spread_lookup)
        exit_cost = exit_cost_fraction(ev, costs)
        net = sig.position_net_return(side, entry_price, exit_price, day, fees, costs["notional_usd"], entry_cost, exit_cost)
        gross = sig.gross_return(side, entry_price, exit_price)
        positions.append({
            "event_id": ev["event_id"],
            "symbol": ev["symbol"],
            "session": ev["session"],
            "window": ev["window"],
            "lane": ev["lane"],
            "side": side,
            "gross": gross,
            "net": net,
            "cost": gross - net,
        })
    return positions, excluded


def daily_series(positions, window, lane, field):
    """Daily long, short and long-short series for one window x lane on `field` returns."""
    chosen = [{"session": p["session"], "side": p["side"], "ret": p[field]}
              for p in positions if p["window"] == window and p["lane"] == lane]
    return sig.daily_portfolios(chosen)


def series_stats(values, lags):
    values = [v for v in values if v is not None]
    n = len(values)
    if n < 2:
        return {"n_days": n, "mean": values[0] if values else None, "t_nw": None, "p_one_sided": None}
    t, se = sig.newey_west_t(values, lags)
    mu = sum(values) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))
    return {
        "n_days": n,
        "mean": mu,
        "sd": sd,
        "se_nw": se,
        "t_nw": t,
        "p_one_sided": sig.normal_sf(t) if not math.isnan(t) else None,
        "sharpe_annualized": (mu / sd * math.sqrt(252)) if sd > 0 else None,
        "hit_rate": sum(1 for v in values if v > 0) / n,
    }


def in_segment(session_iso, segment):
    return segment["first_session"] <= session_iso <= segment["last_session"]


def leg_values(daily, leg, segment):
    return [v[leg] for d, v in sorted(daily.items()) if in_segment(d, segment) and v[leg] is not None]


def break_even_round_trip(gross_daily, segment):
    """Per-position round-trip cost that sets the mean long-short return to zero."""
    num, legs = 0.0, 0
    days = 0
    for d, v in gross_daily.items():
        if not in_segment(d, segment) or v["long_short"] is None:
            continue
        days += 1
        num += v["long_short"]
        legs += (v["long"] is not None) + (v["short"] is not None)
    if days == 0 or legs == 0:
        return None
    return (num / days) / (legs / days)


def evaluate_items(protocol, positions):
    """Preregistered confirmatory items with Holm adjustment and gates."""
    lags = protocol["inference"]["newey_west_lags"]
    alpha = protocol["inference"]["family_alpha"]
    segments = protocol["segments"]
    results = {}
    raw_p = {}
    for item in protocol["items"]:
        daily = daily_series(positions, item["window"], item["lane"], "net")
        seg = segments[item["segment"]]
        values = leg_values(daily, item["leg"], seg)
        stats = series_stats(values, lags)
        stats["min_days"] = item["min_days"]
        stats["sample_ok"] = stats["n_days"] >= item["min_days"]
        results[item["id"]] = stats
        raw_p[item["id"]] = stats["p_one_sided"] if stats["sample_ok"] else None
    adjusted = sig.holm(raw_p)
    for item in protocol["items"]:
        r = results[item["id"]]
        r["p_holm"] = adjusted[item["id"]]
        if not r["sample_ok"]:
            r["verdict"] = "insufficient_sample"
        elif r["p_holm"] <= alpha and r["mean"] is not None and r["mean"] > 0:
            r["verdict"] = "pass"
        else:
            r["verdict"] = "fail"
    return results


def descriptive(protocol, positions):
    """Legs, gross versions, per-year and small-cap lane tables (never confirmatory)."""
    lags = protocol["inference"]["newey_west_lags"]
    out = {}
    for window in (sig.OVERNIGHT, sig.RTH):
        for lane in (sig.LIQUID, sig.SMALL):
            net_daily = daily_series(positions, window, lane, "net")
            gross_daily = daily_series(positions, window, lane, "gross")
            if not net_daily:
                continue
            block = {}
            for seg_name, seg in protocol["segments"].items():
                if not isinstance(seg, dict):
                    continue  # e.g. the "justification" text
                block[seg_name] = {
                    f"{field}_{leg}": series_stats(leg_values(daily, leg, seg), lags)
                    for field, daily in (("net", net_daily), ("gross", gross_daily))
                    for leg in ("long", "short", "long_short")
                }
                block[seg_name]["break_even_round_trip"] = break_even_round_trip(gross_daily, seg)
            years = sorted({d[:4] for d in net_daily})
            block["by_year_net_long_short"] = {
                y: series_stats([v["long_short"] for d, v in net_daily.items() if d[:4] == y and v["long_short"] is not None], lags)
                for y in years
            }
            chosen = [p for p in positions if p["window"] == window and p["lane"] == lane]
            block["positions"] = len(chosen)
            block["mean_cost_per_position"] = (sum(p["cost"] for p in chosen) / len(chosen)) if chosen else None
            out[f"{window}:{lane}"] = block
    return out


# --------------------------------------------------------------------------------------
# Loaders (thin I/O)
# --------------------------------------------------------------------------------------


def read_jsonl(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_scores(score_dir):
    scores = {}
    for name in sorted(os.listdir(score_dir)):
        if name.startswith("scores-") and name.endswith(".jsonl"):
            for row in read_jsonl(os.path.join(score_dir, name)):
                scores.setdefault(row["event_id"], row)
    return scores


def load_auction_prices(path, events):
    listing = {(ev["symbol"], ev["session"]): ev.get("exchange") for ev in events}
    opens, closes = {}, {}
    for row in read_jsonl(path):
        key = (row["symbol"], row["session"])
        venue = listing.get(key)
        o = sig.select_auction_price(row["o"], "open", venue)
        c = sig.select_auction_price(row["c"], "close", venue)
        if o:
            opens[key] = o[0]
        if c:
            closes[key] = c[0]
    return opens, closes


def load_rth_entries(events, minute_root, memory_limit="2.5GB", threads=4):
    wanted = defaultdict(list)
    for ev in events:
        if ev["window"] == sig.RTH:
            d, m = sig.rth_entry_minute(ev["entry_utc"])
            wanted[(ev["symbol"], d.year)].append((ev["event_id"], d, m))
    entries = {}
    if not wanted:
        return entries
    import duckdb  # noqa: PLC0415 - only the data runtime has it

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={threads}")
    for (symbol, year), items in sorted(wanted.items()):
        path = os.path.join(minute_root, f"symbol={symbol}", f"year={year}", "full.parquet")
        if not os.path.exists(path):
            continue
        days = sorted({d for _, d, _ in items})
        rows = con.execute(
            "SELECT et_date, et_minute, o FROM read_parquet(?) WHERE et_date IN (SELECT unnest(?::DATE[]))",
            [path, days],
        ).fetchall()
        bars = defaultdict(dict)
        for d, m, o in rows:
            bars[d][int(m)] = {"o": o}
        for event_id, d, m in items:
            hit = sig.pick_entry_bar(bars.get(d, {}), m)
            if hit:
                entries[event_id] = hit[1]
    con.close()
    return entries


def spread_lookup_factory(quotes_path, events, fallback_bps):
    """Event half-spread, else the symbol-year median, else the lane median, else fallback."""
    by_event = {}
    if os.path.exists(quotes_path):
        for row in read_jsonl(quotes_path):
            for q in row["quotes"]:
                hs = sig.half_spread_fraction(q)
                if hs is not None:
                    by_event.setdefault(row["event_id"], hs)
                    break
    lane_of = {ev["event_id"]: ev for ev in events}
    by_symbol_year = defaultdict(list)
    all_values = []
    for event_id, hs in by_event.items():
        ev = lane_of.get(event_id)
        if ev is None:
            continue
        by_symbol_year[(ev["symbol"], ev["session"][:4])].append(hs)
        all_values.append(hs)

    def median(xs):
        xs = sorted(xs)
        n = len(xs)
        return None if n == 0 else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)

    lane_median = median(all_values)
    sy_median = {k: median(v) for k, v in by_symbol_year.items()}

    def lookup(ev):
        if ev["event_id"] in by_event:
            return by_event[ev["event_id"]]
        m = sy_median.get((ev["symbol"], ev["session"][:4]))
        if m is not None:
            return m
        if lane_median is not None:
            return lane_median
        return fallback_bps / 1e4

    return lookup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", default=os.path.join(_HERE, "protocol.json"))
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--data-root", default=PRIVATE_ROOT)
    parser.add_argument("--minute-root", default=MINUTE_ROOT)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    protocol = check_protocol(args.protocol, args.protocol_sha256)
    check_inputs(protocol, args.data_root)
    with open(os.path.join(REPO, protocol["costs"]["fees"]["file"]), encoding="utf-8") as handle:
        fees = json.load(handle)
    events = list(read_jsonl(os.path.join(args.data_root, "events.jsonl.gz")))
    scores = load_scores(os.path.join(args.data_root, "scores"))
    opens, closes = load_auction_prices(os.path.join(args.data_root, "auctions", "auctions.jsonl.gz"), events)
    rth_entries = load_rth_entries(events, args.minute_root)
    lookup = spread_lookup_factory(os.path.join(args.data_root, "spreads", "quotes.jsonl"), events,
                                   protocol["costs"]["rth_half_spread_fallback_bps"])
    positions, excluded = build_positions(events, scores, opens, closes, rth_entries, lookup, fees, protocol["costs"],
                                          expected_template=protocol["scoring"]["template_sha256"])
    results = {
        "schema": "sota-news-llm-results/1",
        "evidence_label": "HIST",
        "protocol_sha256": args.protocol_sha256,
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "positions": len(positions),
        "excluded": dict(excluded),
        "items": evaluate_items(protocol, positions),
        "descriptive": descriptive(protocol, positions),
    }
    out = args.out or os.path.join(args.data_root, "results.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1, sort_keys=True)
    print(json.dumps({k: results[k] for k in ("positions", "excluded", "items")}, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
