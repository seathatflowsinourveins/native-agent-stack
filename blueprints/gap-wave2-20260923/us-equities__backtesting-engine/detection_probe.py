#!/usr/bin/env python3
"""Synthetic detection probe for ca_window_replay.reconcile (no engine, no provider data).

Builds 25 synthetic sessions and a synthetic native result, then mutates it the way a
native corporate-action credit would appear: (a) a dividend cash credit on a held bar,
(b) a 4:1 split quantity change on a held bar, and (c) a fill stamped 1 ms off its
bar instant. Prints which reconciliation checks fail.
"""
import copy
import importlib.util
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

spec = importlib.util.spec_from_file_location("ca", Path(__file__).with_name("ca_window_replay.py"))
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)

days, d = [], date(2020, 8, 3)
while len(days) < 25:
    if d.weekday() < 5:
        days.append(d.isoformat())
    d += timedelta(days=1)
rows = [{"session_date": s, "c": "100.00"} for s in days]
actions = [{"type": "cash_dividend", "ex_date": days[4], "rate": "0.50", "qualification": "qualified"},
           {"type": "forward_split", "ex_date": days[20], "old_rate": "1", "new_rate": "4", "qualification": "qualified"}]


def iso(s):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ca.close_ns(s) // 10**9, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


held_cash = str(ca.CAPITAL - 10 * Decimal("100.00"))
clean = {"reports": {"fills": [{"side": s, "filled_qty": "10", "avg_px": "100.00", "ts_init": iso(days[i]), "ts_last": iso(days[i])}
                               for s, i in (("BUY", 0), ("SELL", 24))],
                     "account": [{"total": "100000.00"}, {"total": held_cash}, {"total": "100000.00"}]},
         "marks": [{"bar_index": i, "session_date": s, "phase": "before_order", "net_position": "0" if i == 0 else "10",
                    "cash_total": "100000.00 USD" if i == 0 else held_cash + " USD"} for i, s in enumerate(days)]
         + [{"phase": "on_stop", "net_position": "0", "cash_total": "100000.00 USD"}],
         "open_positions": 0, "open_orders": 0}
dividend = copy.deepcopy(clean)
for m in dividend["marks"][5:25]:
    m["cash_total"] = str(Decimal(held_cash) + 5) + " USD"
split = copy.deepcopy(clean)
for m in split["marks"][21:25]:
    m["net_position"] = "40"
shifted = copy.deepcopy(clean)
shifted["reports"]["fills"][0]["ts_init"] = shifted["reports"]["fills"][0]["ts_init"].replace(".000Z", ".001Z")
out = {}
for name, native in (("clean", clean), ("dividend_credit", dividend), ("split_quantity", split), ("fill_shift_1ms", shifted)):
    r = ca.reconcile(rows, actions, native)
    out[name] = {"all_checks_pass": r["all_checks_pass"], "failed_checks": sorted(k for k, v in r["checks"].items() if not v)}
print(json.dumps(out, indent=1))
ok = (out["clean"]["all_checks_pass"] and "cash_constant_while_held" in out["dividend_credit"]["failed_checks"]
      and "position_quantity_constant_10_while_held" in out["split_quantity"]["failed_checks"]
      and "fill_BUY_at_bar_instant" in out["fill_shift_1ms"]["failed_checks"])
raise SystemExit(0 if ok else 1)
