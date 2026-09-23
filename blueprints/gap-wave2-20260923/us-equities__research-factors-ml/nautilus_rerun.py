#!/usr/bin/env python3
"""Re-run the frozen research-evaluation selections in a NautilusTrader 2.0.0rc5 BacktestEngine.

Paths: 'development' (each skfolio WalkForward fold's chosen candidate on its
evaluation episodes, P6 arm = accepted receipt) and 'reserved' (momentum20 on
2021Q1). Arms: RAW (unadjusted LEAN prices; dividends computed independently
from LEAN factor files and NOT credited by the engine) and ADJ (raw price x LEAN
price factor, i.e. dividend-inclusive back-adjusted prices, rounded to 4 dp).
Each session is two TradeTicks per asset (09:30 open, 16:00 close, New York).
Orders: at an exit session's open, market SELL the whole position; on its fill,
market BUY the next episode's asset with floor(free / (open * 1.001)) shares.
Fees: MakerTakerFeeModel with instrument taker_fee 0.001 (10 bp per side).
Every fill, commission and cash transition is audited with independent Decimal
arithmetic; RAW per-episode fill price ratios are compared with evaluate.label.
"""
import argparse
import datetime as dt
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO / "blueprints/us-equities/research-evaluation"
sys.path.insert(0, str(EVAL_DIR))
import evaluate as ev  # noqa: E402

FEE = Decimal("0.001")
CAPITAL = Decimal("100000")
NY = ZoneInfo("America/New_York")
MAX_PARTICIPATION = Decimal("0.01")


def factor_rows(root, asset):
    rows = []
    for line in (root / ("Data/equity/usa/factor_files/" + asset.lower() + ".csv")).read_text().split():
        d, pf, sf, ref = line.split(",")
        rows.append((d, Decimal(pf), Decimal(sf), Decimal(ref)))
    return rows


def price_factor(rows, date):
    key = date.replace("-", "")
    for d, pf, sf, _ in rows:
        if d >= key:
            if sf != 1:
                raise ValueError("split factor != 1 inside study")
            return pf
    raise ValueError("no factor row")


def dividends(rows, start, end):
    """(row_date D, ex_date>D, amount) with D inside [start, end]; amount = ref*(1-pf_D/pf_next)."""
    out = []
    for (d, pf, _sf, ref), (_d2, pf2, _s2, _r2) in zip(rows, rows[1:]):
        if start.replace("-", "") <= d <= end.replace("-", "") and pf != pf2:
            out.append({"record_close_date": d[:4] + "-" + d[4:6] + "-" + d[6:], "amount": ref * (1 - pf / pf2), "reference_close": ref})
    return out


def build_schedule(panel, dates, plan, folds, path):
    cost = Decimal(plan["round_trip_cost_fraction"])
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    anchor = eligible[0]
    index = {d: i for i, d in enumerate(dates)}
    if path == "development":
        size = next(i for i, d in enumerate(dates) if d >= plan["reserved_start"])
        seg_panel = {s: rows[:size] for s, rows in panel.items()}
        windows = [(f["id"], f["chosen"], index[f["test_first"]], index[f["test_last"]]) for f in folds]
    else:
        seg_panel = panel
        reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
        windows = [("reserved-2021q1", "momentum20", reserved[0], reserved[-1])]
    episodes = []
    for fold, cand, first, last in windows:
        for t in range(first, last + 1):
            if (t - anchor) % 5:
                continue
            lab = ev.label(seg_panel, t, cand, cost)
            if lab["status"] != "observed":
                continue
            w = ev.weights(seg_panel, t, cand)
            if w and (len(w) != 1 or list(w.values())[0] != 1):
                raise ValueError("unexpected multi-asset weight")
            episodes.append({"fold": fold, "candidate": cand, "decision": dates[t], "entry": dates[t + 1], "exit": dates[t + 6],
                             "asset": next(iter(w), None), "gross_price_label": lab["gross_price_label"]})
    return episodes, seg_panel


def momentum_choice(history, lookback):
    scores = {s: h[-1] / h[-1 - lookback] - 1 for s, h in history.items()}
    best = min(scores, key=lambda s: (-scores[s], s))
    return best if scores[best] > 0 else None


def run_arm(arm, path, panel, dates, plan, episodes, factors, volumes, out):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import MakerTakerFeeModel
    from nautilus_trader.model import (AccountType, AggressorSide, Currency, Equity, InstrumentId, Money, OmsType,
                                       OrderSide, Price, Quantity, Symbol, TradeId, TradeTick, Venue)
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    assets = plan["assets"]
    last_date = episodes[-1]["exit"]
    sessions = [d for d in dates if d <= last_date]

    def px(asset, i, field):
        raw = panel[asset][i][field]
        if arm == "RAW":
            return raw
        return (raw * price_factor(factors[asset], dates[i])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

    ins = {a: Equity(InstrumentId.from_str(a + ".SIM"), Symbol(a), usd, 4, Price.from_str("0.0001"), 0, 0,
                     lot_size=Quantity.from_int(1), maker_fee=FEE, taker_fee=FEE) for a in assets}
    ticks, n = [], 0
    for i, d in enumerate(sessions):
        day = dt.date.fromisoformat(d)
        for hh, mm, field in ((9, 30, "open"), (16, 0, "close")):
            ts = int(dt.datetime.combine(day, dt.time(hh, mm), NY).timestamp()) * 10**9
            for a in assets:
                n += 1
                ticks.append(TradeTick(ins[a].id, Price.from_str(format(px(a, i, field), ".4f")), Quantity.from_int(int(volumes[a][i])),
                                       AggressorSide.NO_AGGRESSOR, TradeId(str(n)), ts, ts))
    by_entry = {e["entry"]: e for e in episodes}
    by_exit = {}
    for e in episodes:
        by_exit.setdefault(e["exit"], []).append(e)
    decisions = {e["decision"]: e for e in episodes}

    class FrozenSelection(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.seen = {}
            self.closes = {a: [] for a in assets}
            self.opens = {}
            self.holding = None  # (asset, qty)
            self.pending = None
            self.recomputed = []
            self.denied = []

        def on_start(self):
            for i in ins.values():
                self.subscribe_trades(i.id)

        def buy(self, e):
            if e["asset"] is None:
                return
            free = Decimal(str(self.portfolio.account(venue).balance_free(usd).as_decimal()))
            price = self.opens[e["asset"]]
            qty = (free / (price * (1 + FEE))).to_integral_value(rounding=ROUND_FLOOR)
            self.submit_order(self.order_factory.market(ins[e["asset"]].id, OrderSide.BUY, Quantity.from_int(int(qty))))
            self.holding = (e["asset"], qty)

        def on_trade(self, tick):
            ts = dt.datetime.fromtimestamp(tick.ts_event / 1e9, NY)
            d, field = ts.date().isoformat(), ("open" if ts.hour < 12 else "close")
            a = str(tick.instrument_id).split(".")[0]
            key = (d, field)
            self.seen[key] = self.seen.get(key, 0) + 1
            if field == "close":
                self.closes[a].append(Decimal(str(tick.price)))
                if self.seen[key] == len(assets) and d in decisions:
                    e = decisions[d]
                    lookback = None if e["candidate"] == "cash" else int(e["candidate"].removeprefix("momentum"))
                    mine = None if lookback is None else momentum_choice(self.closes, lookback)
                    self.recomputed.append({"decision": d, "candidate": e["candidate"], "strategy_choice": mine, "frozen": e["asset"]})
                return
            self.opens[a] = Decimal(str(tick.price))
            if self.seen[key] != len(assets):
                return
            entry = by_entry.get(d)
            if self.holding and d in by_exit:
                asset, qty = self.holding
                self.holding = None
                self.pending = entry
                self.submit_order(self.order_factory.market(ins[asset].id, OrderSide.SELL, Quantity.from_int(int(qty))))
            elif entry is not None:
                self.buy(entry)

        def on_order_filled(self, event):
            if event.order_side == OrderSide.SELL and self.pending is not None:
                entry, self.pending = self.pending, None
                self.buy(entry)

        def on_order_denied(self, event):
            self.denied.append(str(event))

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd,
                         fee_model=MakerTakerFeeModel())
        for i in ins.values():
            engine.add_instrument(i)
        engine.add_data(ticks)
        strat = FrozenSelection()
        engine.add_strategy(strat)
        engine.run()
        fills = json.loads(engine.generate_order_fills_report().reset_index().to_json(orient="records", date_format="iso"))
        accounts = json.loads(engine.generate_account_report(venue=venue).reset_index().to_json(orient="records", date_format="iso"))
        positions = json.loads(engine.generate_positions_report().reset_index().to_json(orient="records", date_format="iso"))
        open_orders, open_positions = len(engine.cache.orders_open()), len(engine.cache.positions_open())
    finally:
        engine.dispose()
    (out / (path + "-" + arm + ".reports.json")).write_text(json.dumps({"fills": fills, "accounts": accounts, "positions": positions,
        "recomputed": strat.recomputed, "denied": strat.denied}, indent=1, default=str) + "\n")
    return audit(arm, path, panel, dates, episodes, fills, accounts, positions, strat, open_orders, open_positions, px, factors, volumes)


def number(v):
    return Decimal(str(v).split()[0].replace(",", ""))


def audit(arm, path, panel, dates, episodes, fills, accounts, positions, strat, open_orders, open_positions, px, factors, volumes):
    index = {d: i for i, d in enumerate(dates)}
    fills = sorted(fills, key=lambda f: (f["ts_last"], 0 if f["side"] == "SELL" else 1))
    traded = [e for e in episodes if e["asset"]]
    expected = []
    for e in traded:
        expected.append(("BUY", e["asset"], e["entry"], e))
        expected.append(("SELL", e["asset"], e["exit"], e))
    expected.sort(key=lambda x: (x[2], 0 if x[0] == "SELL" else 1))
    problems = []
    if len(fills) != len(expected):
        problems.append("fill count %d != expected %d" % (len(fills), len(expected)))
    cash, fees, rule_hits = CAPITAL, Decimal(0), {"half_even": 0, "half_up": 0}
    held, episode_rows, max_part = {}, [], Decimal(0)
    for f, (side, asset, date, e) in zip(fills, expected):
        i = index[date]
        price = px(asset, i, "open")
        qty = number(f["filled_qty"])
        if f["side"] != side or f["instrument_id"] != asset + ".SIM" or number(f["avg_px"]) != price or f["status"] != "FILLED":
            problems.append("fill mismatch %s %s %s" % (date, side, asset))
        notional = qty * price
        commission = sum(number(c) for c in f["commissions"])
        he, hu = (notional * FEE).quantize(Decimal("0.01"), ROUND_HALF_EVEN), (notional * FEE).quantize(Decimal("0.01"), ROUND_HALF_UP)
        rule_hits["half_even"] += commission == he
        rule_hits["half_up"] += commission == hu
        if commission not in (he, hu):
            problems.append("commission %s != %s on %s" % (commission, he, date))
        max_part = max(max_part, qty / Decimal(volumes[asset][i]))
        # Audit v2 (fix round 1): the engine books notional at USD precision, half-even.
        booked = notional.quantize(Decimal("0.01"), ROUND_HALF_EVEN)
        cash += (-booked if side == "BUY" else booked) - commission
        fees += commission
        if side == "BUY":
            held[id(e)] = (qty, price, commission)
        else:
            bq, bp, bc = held.pop(id(e))
            if bq != qty:
                problems.append("round-trip qty mismatch " + date)
            ratio = price / bp - 1
            row = {"fold": e["fold"], "asset": asset, "entry": e["entry"], "exit": e["exit"], "qty": str(qty),
                   "entry_px": str(bp), "exit_px": str(price), "fill_ratio_minus_1": str(ratio), "fees": str(bc + commission),
                   "pnl_net": str(qty * (price - bp) - bc - commission)}
            if arm == "RAW":
                row["evaluate_gross_price_label"] = e["gross_price_label"]
                row["parity_exact"] = ratio == Decimal(e["gross_price_label"])
            episode_rows.append(row)
    totals = [number(a["total"]) for a in accounts]
    running, seq_ok = CAPITAL, totals[0] == CAPITAL
    for f, t in zip(fills, totals[1:]):
        running += (-1 if f["side"] == "BUY" else 1) * (number(f["filled_qty"]) * number(f["avg_px"])).quantize(Decimal("0.01"), ROUND_HALF_EVEN) - sum(number(c) for c in f["commissions"])
        seq_ok &= running == t
    if len(totals) != len(fills) + 1:
        problems.append("account rows %d != fills+1 %d" % (len(totals), len(fills) + 1))
    if not seq_ok:
        problems.append("cash sequence mismatch")
    if totals[-1] != cash:
        problems.append("final cash %s != independent %s" % (totals[-1], cash))
    realized = sum(number(p["realized_pnl"]) for p in positions)
    ordered = sorted(positions, key=lambda p: p["ts_opened"])
    pnl_exact, pnl_max_diff = 0, Decimal(0)
    if len(ordered) != len(episode_rows):
        problems.append("position count %d != round trips %d" % (len(ordered), len(episode_rows)))
    for pos, r in zip(ordered, episode_rows):
        mine = (Decimal(r["qty"]) * (Decimal(r["exit_px"]) - Decimal(r["entry_px"]))).quantize(Decimal("0.01"), ROUND_HALF_EVEN) - Decimal(r["fees"])
        diff = abs(number(pos["realized_pnl"]) - mine)
        pnl_exact += diff == 0
        pnl_max_diff = max(pnl_max_diff, diff)
        if diff > Decimal("0.01") or pos["instrument_id"] != r["asset"] + ".SIM":
            problems.append("position pnl %s vs independent %s" % (pos["realized_pnl"], mine))
    pnl_check = {"positions": len(ordered), "exact": pnl_exact, "max_abs_diff_usd": str(pnl_max_diff),
                 "sum_realized_minus_cash_delta_usd": str(realized - (cash - CAPITAL))}
    if open_orders or open_positions or strat.denied:
        problems.append("open orders/positions or denials")
    # Dividends on held episodes: entitled when entry <= record_close_date < exit.
    div_rows, div_total = [], Decimal(0)
    for r in episode_rows:
        for dv in dividends(factors[r["asset"]], r["entry"], r["exit"]):
            if r["entry"] <= dv["record_close_date"] < r["exit"]:
                amt = (Decimal(r["qty"]) * dv["amount"]).quantize(Decimal("0.01"))
                div_rows.append({"asset": r["asset"], "record_close_date": dv["record_close_date"], "per_share": str(dv["amount"].quantize(Decimal("0.000001"))),
                                 "qty": r["qty"], "amount_usd": str(amt)})
                div_total += amt
    decisions_ok = None
    if arm == "RAW":
        mism = [x for x in strat.recomputed if x["strategy_choice"] != x["frozen"]]
        decisions_ok = {"checked": len(strat.recomputed), "mismatches": len(mism)}
        if mism:
            problems.append("strategy momentum recomputation disagrees with frozen weights")
        if not all(r["parity_exact"] for r in episode_rows):
            problems.append("raw fill ratio != evaluate gross_price_label")
    else:
        decisions_ok = {"checked": len(strat.recomputed),
                        "adjusted_price_choice_differs_from_frozen_raw": sum(x["strategy_choice"] != x["frozen"] for x in strat.recomputed)}
    return {"arm": arm, "path": path, "episodes": len(episodes), "traded_episodes": len(traded), "cash_episodes": len(episodes) - len(traded),
            "fills": len(fills), "fees_usd": str(fees), "ending_cash_usd": str(cash), "engine_ending_cash_usd": str(totals[-1]),
            "net_pnl_usd": str(cash - CAPITAL), "realized_pnl_usd": str(realized), "realized_pnl_check": pnl_check,
            "audit_version": 2, "commission_rule_hits": rule_hits,
            "max_daily_volume_participation": str(max_part.quantize(Decimal("0.0000001"))),
            "participation_within_1pct": max_part <= MAX_PARTICIPATION,
            "dividends_entitled_usd": str(div_total), "dividend_events": div_rows,
            "dividends_credited_by_engine": False,
            "dividend_treatment": ("computed independently from LEAN factor files; not in engine cash" if arm == "RAW" else "embedded in back-adjusted prices (reinvested); the listed amounts are the raw-dividend equivalent for reference"),
            "strategy_decision_check": decisions_ok, "open_orders": open_orders, "open_positions": open_positions,
            "denied_orders": len(strat.denied), "problems": problems, "reconciled": not problems, "episode_rows": episode_rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lean-source", type=Path, required=True)
    p.add_argument("--folds", type=Path, required=True, help="evaluate_purge.py results.json (P6 arm)")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")
    root = args.lean_source.resolve()
    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    inputs = ev.verify_inputs(root, plan["inputs"])
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    panel, dates, _aux, _counts = ev.load_panel(root, plan)
    folds = json.loads(args.folds.read_text())["arms"]["P6"]["folds"]
    accepted = json.loads((EVAL_DIR / "receipt.json").read_text())["results"]["development_folds"]
    if [(f["test_first"], f["chosen"]) for f in folds] != [(f["test_first"], f["chosen"]) for f in accepted]:
        raise ValueError("P6 folds differ from accepted receipt")
    import csv, io, zipfile
    volumes = {}
    for a in plan["assets"]:
        with zipfile.ZipFile(root / ("Data/equity/usa/daily/" + a.lower() + ".zip")) as z:
            rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
        vol = {dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat(): int(r[5]) for r in rows}
        volumes[a] = [vol[d] for d in dates]
    factors = {a: factor_rows(root, a) for a in plan["assets"]}
    results = []
    for path in ("development", "reserved"):
        episodes, _ = build_schedule(panel, dates, plan, folds, path)
        (args.out / (path + ".schedule.json")).write_text(json.dumps(episodes, indent=1) + "\n")
        for arm in ("RAW", "ADJ"):
            results.append(run_arm(arm, path, panel, dates, plan, episodes, factors, volumes, args.out))
    summary = {"engine": "nautilus_trader " + importlib.metadata.version("nautilus_trader"), "plan_sha256": ev.digest(EVAL_DIR / "plan.json"),
               "runner_sha256": ev.digest(__file__), "inputs_unchanged": ev.verify_inputs(root, plan["inputs"]) == inputs,
               "results": results, "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    brief = [{k: r[k] for k in ("arm", "path", "episodes", "traded_episodes", "fills", "fees_usd", "ending_cash_usd", "net_pnl_usd",
                                "dividends_entitled_usd", "max_daily_volume_participation", "strategy_decision_check", "reconciled", "problems")}
             for r in results]
    print(json.dumps({"results": brief, "inputs_unchanged": summary["inputs_unchanged"], "summary_sha256": ev.digest(args.out / "summary.json")}, indent=1))


if __name__ == "__main__":
    main()
