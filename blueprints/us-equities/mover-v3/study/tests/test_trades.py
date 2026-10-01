"""The arms, terminal exits (delisting inside a hold and at a segment end), censoring, mergers, split records,
the net return and H3-c's legs, with quote windows served by the plan's own requests."""
import json
import unittest
from pathlib import Path

from core import costs, plan
from core import evaluate as EV
from core.records import ts_epoch
from core.store import Store
from core.trades import Ctx, h3c_event, trade
from tests import synth
from tests.synth import quote
from tests.test_costs import FEES

REPO = Path(__file__).resolve().parents[5]
CELLS = costs.monotone(costs.load_table(REPO / "blueprints/us-equities/mover-early-entry/evidence/cost-table-run-v1.json"))


def make_event(cal, t, sym="MOVR", price=10.0, split_at=None, missing=()):
    first, last = cal.offset(t, -60), cal.offset(t, 12)
    raw, split, allc = synth.series(cal, first, last, lambda d: price if not split_at or d < min(split_at) else price / list(split_at.values())[0],
                                    split_at=split_at, missing=missing)
    prints = synth.prints_from(raw)
    minute = []
    for d in cal.range(cal.offset(t, -19), last):
        minute += synth.minute_rows(cal, d, price, 50_000, start="04:00", n=16 * 60)
    return {"symbol": sym, "t": t, "raw": raw, "split": split, "all": allc, "prints": prints, "minute": minute,
            "med20": 5_000_000.0, "sigma_d": 0.05, "incomplete": [], "least_exposed": False, "max21": 0.1}


def resolve(ev, arm, ctx, store, quotes_by_symbol, fail=()):
    """Serve every window the trade asks for from a quote list (a fake market), until the trade is decided."""
    for _ in range(100):
        tr = trade(ev, arm, ctx, store)
        if "needs" not in tr:
            return tr
        for req in tr["needs"]:
            sym = req["params"]["symbols"]
            lo, hi = ts_epoch(req["params"]["start"]), ts_epoch(req["params"]["end"])
            qs = [q for q in quotes_by_symbol.get(sym, []) if lo <= q["t"] <= hi]
            synth.put_quotes(store, req, sym, qs, complete=req["kind"] not in fail)
    raise AssertionError("trade did not settle")


def ctx_for(cal, stage="validation", actions=(), segs=None, mode="read"):
    segs = segs or [("2020-01-02", "2020-12-31")]
    return Ctx(cal=cal, stage=stage, segs=segs, actions=list(actions), fees=costs.Fees(FEES, cal=cal), cells=CELLS, mode=mode)


def book(cal, d, hhmm, bp=10.0, ap=10.02, dt=0.0):
    return quote(cal.at(d, hhmm) + dt, bp, ap)


class Arms(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"
        self.ev = make_event(self.cal, self.t)
        self.d = [self.cal.offset(self.t, k) for k in range(0, 12)]

    def test_b_lane_normal_exit_and_net(self):
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:34", dt=59.5), book(cal, d[5], "15:55", 11.0, 11.02, dt=-0.2)]
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["exit"]), ("filled", "normal"))
        self.assertEqual(tr["notional"], 20_000.0)
        entry_mid, exit_mid = 10.01, 11.01
        imp = costs.impact(1.0, 0.05, 20_000.0, 5_000_000.0)
        from core import formulas as FM
        cum_in = FM.cum_dv_at(cal, self.ev["minute"], d[1], cal.at(d[1], "09:35"))
        c_in = costs.per_side(CELLS[costs.cell_key(d[1], cal.at(d[1], "09:35"), entry_mid, cum_in)],
                              0.02 / 20.02, imp)
        cum_out = FM.cum_dv_at(cal, self.ev["minute"], d[5], cal.at(d[5], "15:55"))
        c_out = costs.per_side(CELLS[costs.cell_key(d[5], cal.at(d[5], "15:55"), exit_mid, cum_out)], 0.02 / 22.02, imp)
        want = costs.trade_net_return(20_000.0, entry_mid, exit_mid, 1.0, 0.0, c_in, c_out, costs.Fees(FEES, cal=self.cal), d[5])
        self.assertAlmostEqual(tr["nets"]["primary"], want, places=12)

    def test_a_intraday_and_b_overnight(self):
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:35"), book(cal, d[1], "15:55", 10.5, 10.52), book(cal, d[2], "09:30", 10.4, 10.42, dt=1)]
        a = resolve(self.ev, "a_intraday", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((a["status"], a["exit"], a["F"], a["cash"]), ("filled", "normal", 1.0, 0.0))
        b = resolve(self.ev, "b_overnight", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((b["status"], b["exit"], b["exit_session"]), ("filled", "normal", d[2]))

    def test_delisting_inside_a_hold_is_terminal_zero_and_kept(self):
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:35"), book(cal, d[3], "11:00", 4.0, 4.05)]
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["exit"]), ("filled", "terminal_zero"))
        self.assertEqual(tr["nets"]["primary"], -1.0)
        self.assertTrue(tr["no_merger_record"])
        self.assertIsNotNone(tr["terminal_rebooked_at_last_bid"])  # the sensitivity at the last bid (4.00)
        rows = EV.item_trades("H3-a", [], [])
        tr["tercile"] = "low"
        rows = EV.item_trades("H1-D-b_lane-low", [tr], [])
        self.assertEqual([r["value"] for r in rows], [-1.0])

    def test_halt_resuming_on_E_plus_3_is_a_delayed_exit(self):
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:35"), book(cal, d[8], "10:17", 9.0, 9.02)]
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["exit"], tr["exit_session"]), ("delayed", d[8]))

    def test_halt_not_resumed_by_E_plus_5_is_terminal(self):
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:35"), book(cal, cal.offset(d[10], 1), "10:00", 9.0, 9.02)]
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual(tr["exit"], "terminal_zero")

    def test_empty_exit_response_is_terminal_and_counted(self):
        cal, d = self.cal, self.d
        store = Store()
        tr = resolve(self.ev, "b_lane", ctx_for(cal), store, {"MOVR": [book(cal, d[1], "09:35")]})
        self.assertEqual(tr["exit"], "terminal_zero")
        empties = [k for k, r in store.req.items() if r["kind"] == "quote_exit" and store.empty(k, "MOVR")]
        self.assertEqual(len(empties), 6)  # W0 (15:55 + 300 s is the close, so no W1) and E+1 .. E+5
        # review round 11, C6: the empty windows are carried on the trade and counted per item
        self.assertEqual((tr["exit_windows_empty"], tr["search_windows_empty"]), (1, 5))
        no_quote = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {})
        self.assertEqual((no_quote["status"], no_quote.get("entry_window_empty")), ("no_entry", True))
        tr["tercile"], no_quote["tercile"] = "low", "low"
        ev = dict(self.ev, data={"empty": ["event_auctions"]})
        h3c = [{"symbol": "MOVR", "t": self.t, "status": "complete"}]
        got = EV.empty_by_item(("H1-D-b_lane-low", "H3-a", "H3-c"), [tr, no_quote], h3c, [ev])
        self.assertEqual(got["H1-D-b_lane-low"], {"entry_window": 1, "event_request:event_auctions": 2,
                                                  "exit_windows": 1, "search_windows": 5})
        self.assertEqual(got["H3-a"], {})
        self.assertEqual(got["H3-c"], {"event_request:event_auctions": 1})

    def test_per_event_close_differences_never_change_membership(self):
        """Review round 11, C7 (universe_and_identity.request_shapes): the screen close governs membership; a
        per-event official close of t or t-1 that differs from the screen's is counted, and the event stands."""
        from collections import Counter
        from core import events as EVS
        from core import formulas as FM
        cal, t, ev = self.cal, self.t, self.ev
        data = {"incomplete": [], "empty": [], "daily": {"raw": ev["raw"], "split": ev["split"], "all": ev["all"]},
                "minute": ev["minute"], "prints": ev["prints"]}
        close_t, prev = FM.official_close(ev["prints"][t]), FM.official_close(ev["prints"][cal.offset(t, -1)])
        same, differs = Counter(), Counter()
        a = EVS.build_event(cal, {"symbol": "MOVR", "t": t, "close_t": close_t, "prev_close": prev}, data, same)
        b = EVS.build_event(cal, {"symbol": "MOVR", "t": t, "close_t": close_t + 0.5, "prev_close": prev - 0.25},
                            data, differs)
        self.assertEqual(same["per_event_close_differs_from_screen"], 0)
        self.assertEqual(differs["per_event_close_differs_from_screen"], 2)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual({k: v for k, v in a.items() if k != "data"}, {k: v for k, v in b.items() if k != "data"})

    def test_cash_merger_inside_the_hold_books_the_last_eligible_bid(self):
        cal, d = self.cal, self.d
        merger = {"type": "cash_merger", "acquiree_symbol": "MOVR", "acquirer_symbol": "BIG", "date": d[4], "rate": 12.0}
        qs = [book(cal, d[1], "09:35"), book(cal, d[4], "15:59", 11.9, 11.95), book(cal, d[4], "15:59", 11.9, 11.9, dt=30)]
        tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[merger]), Store(), {"MOVR": qs})
        self.assertEqual((tr["exit"], tr["terminal_booking"]), ("terminal_merger", "merger"))
        f = costs.Fees(FEES, cal=self.cal)
        imp = costs.impact(1.0, 0.05, 20_000.0, 5_000_000.0)
        self.assertLess(abs(tr["nets"]["primary"] - (11.9 / 10.01 - 1)), 0.03)
        # review round 12, F6: exactly the net with c_out = 0 and fees on the raw bid (populations.corporate_actions)
        from core import formulas as FM
        cum_in = FM.cum_dv_at(cal, self.ev["minute"], d[1], cal.at(d[1], "09:35"))
        c_in = costs.per_side(CELLS[costs.cell_key(d[1], cal.at(d[1], "09:35"), 10.01, cum_in)], 0.02 / 20.02, imp)
        want = costs.trade_net_return(20_000.0, 10.01, 11.9, 1.0, 0.0, c_in, 0.0, f, d[4])
        self.assertAlmostEqual(tr["nets"]["primary"], want, places=12)
        self.assertEqual(tr["exit_session"], d[4])
        # the acquirer side does not qualify
        acq = {**merger, "acquiree_symbol": "OTHER", "acquirer_symbol": "MOVR"}
        tr2 = resolve(self.ev, "b_lane", ctx_for(cal, actions=[acq]), Store(), {"MOVR": qs})
        self.assertEqual(tr2["exit"], "terminal_zero")

    def test_merger_effective_window_is_entry_session_through_e_plus_5(self):
        """Review round 12, F6: a merger record effective on the entry session or on E+5 qualifies; E+6 does not."""
        cal, d = self.cal, self.d
        qs = [book(cal, d[1], "09:35"), book(cal, d[4], "15:59", 11.9, 11.95)]
        for day, want in ((d[1], "terminal_merger"), (d[10], "terminal_merger"), (d[11], "terminal_zero"),
                          (d[0], "terminal_zero")):
            merger = {"type": "cash_merger", "acquiree_symbol": "MOVR", "date": day}
            tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[merger]), Store(), {"MOVR": qs})
            self.assertEqual(tr["exit"], want, day)

    def test_rename_window_is_after_the_entry_session_through_e_plus_5(self):
        """Review round 12, F8: a name_change with process_date in (entry session, E+5] is counted and re-requested;
        one on the entry session or on E+6 is not."""
        cal, d = self.cal, self.d
        for day, counted in ((d[8], True), (d[10], True), (d[11], False), (d[1], False)):
            rn = {"type": "name_change", "old_symbol": "MOVR", "new_symbol": "NEWR", "date": day}
            tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[rn]), Store(),
                         {"MOVR": [book(cal, d[1], "09:35")], "NEWR": [book(cal, d[5], "15:55", 10.5, 10.6)]})
            self.assertEqual(tr["exit"], "terminal_zero", day)
            self.assertEqual(tr["rename_record_in_window"], counted, day)
            self.assertEqual("rename_sensitivity" in tr, counted, day)

    def test_merger_without_any_bid_books_terminal_zero(self):
        cal, d = self.cal, self.d
        merger = {"type": "stock_merger", "acquiree_symbol": "MOVR", "date": d[4]}
        tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[merger]), Store(), {"MOVR": [book(cal, d[1], "09:35")]})
        self.assertEqual(tr["exit"], "terminal_zero")
        self.assertTrue(tr["merger_without_bid"])

    def test_backward_windows_are_requested_latest_first_and_stop(self):
        cal, d = self.cal, self.d
        store = Store()
        resolve(self.ev, "b_lane", ctx_for(cal), store, {"MOVR": [book(cal, d[1], "09:35"), book(cal, d[4], "10:00")]})
        back = sorted(ts_epoch(r["params"]["start"]) for r in store.req.values() if r["kind"] == "quote_backward")
        self.assertEqual(len(back), 2)  # E (empty), then E-1 holds the bid; E-2 .. entry never requested
        self.assertEqual(ts_epoch(plan.t_floor(cal.open(d[4]))), back[0])

    def test_rename_inside_the_search_window_is_counted_and_rerequested(self):
        cal, d = self.cal, self.d
        rn = {"type": "name_change", "old_symbol": "MOVR", "new_symbol": "NEWR", "date": d[3]}
        tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[rn]), Store(),
                     {"MOVR": [book(cal, d[1], "09:35")], "NEWR": [book(cal, d[5], "15:55", 10.5, 10.6)]})
        self.assertEqual(tr["exit"], "terminal_zero")
        self.assertTrue(tr["rename_record_in_window"])
        self.assertEqual(tr["rename_sensitivity"]["status"], "fill")
        self.assertEqual(tr["rename_sensitivity"]["fill_session"], d[5])

    def test_entry_timeout_and_no_fill(self):
        cal, d = self.cal, self.d
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": [book(cal, d[1], "09:41")]})
        self.assertEqual(tr["status"], "no_entry")
        thin = dict(self.ev, med20=50_000.0)
        self.assertEqual(trade(thin, "b_lane", ctx_for(cal), Store())["status"], "no_fill")

    def test_fetch_incomplete_exit_window_excludes_the_trade(self):
        cal, d = self.cal, self.d
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": [book(cal, d[1], "09:35")]}, fail=("quote_exit",))
        self.assertEqual(tr["status"], "fetch_incomplete")
        tr = resolve(self.ev, "b_lane", ctx_for(cal), Store(), {"MOVR": []}, fail=("quote_entry",))
        self.assertEqual(tr["status"], "fetch_incomplete")
        ev = dict(self.ev, incomplete=["event_auctions"])
        self.assertEqual(trade(ev, "b_lane", ctx_for(cal), Store())["status"], "fetch_incomplete")


class Round9(unittest.TestCase):
    """Review round 9: paper exposure and late sessions at the holdout (M-7, L-2), backward windows that are
    fetch-incomplete (M-7, L-1) and the ratio rule inside a hold (M-7)."""

    def setUp(self):
        self.cal = synth.calendar("2026-06-01", "2028-06-30")
        self.t = "2027-02-01"
        self.d = [self.cal.offset(self.t, k) for k in range(0, 12)]
        self.seg = [("2026-11-30", self.cal.offset("2026-11-30", 251))]

    def hctx(self, **kw):
        return Ctx(cal=self.cal, stage="holdout", segs=self.seg, fees=costs.Fees(FEES_2028, cal=self.cal), cells=CELLS, **kw)

    def test_paper_exposure_and_late_sessions_at_the_holdout(self):
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        qs = {"MOVR": [book(cal, d[1], "09:35"), book(cal, d[5], "15:55")]}
        self.assertFalse(resolve(ev, "b_lane", self.hctx(), Store(), qs)["paper_exposed"])
        exposed = resolve(ev, "b_lane", self.hctx(paper_exposed=frozenset({("MOVR", d[3])})), Store(), qs)
        self.assertTrue(exposed["paper_exposed"])
        self.assertTrue(resolve(ev, "b_lane", self.hctx(late_sessions=frozenset({d[4]})), Store(), qs)["paper_exposed"])
        # a session after the exit does not expose the trade
        self.assertFalse(resolve(ev, "b_lane", self.hctx(late_sessions=frozenset({d[7]})), Store(), qs)["paper_exposed"])
        # L-2: an H3-c event is exposed over t .. t+5
        self.assertFalse(h3c_event(ev, self.hctx())["paper_exposed"])
        self.assertTrue(h3c_event(ev, self.hctx(paper_exposed=frozenset({("MOVR", d[5])})))["paper_exposed"])
        self.assertFalse(h3c_event(ev, self.hctx(paper_exposed=frozenset({("MOVR", d[6])})))["paper_exposed"])
        rows = EV.item_trades("H3-c", [], [h3c_event(ev, self.hctx(late_sessions=frozenset({d[2]})))])
        self.assertTrue(rows[0]["rec"]["paper_exposed"])

    def test_merger_with_an_incomplete_backward_window_excludes_the_trade(self):
        cal = synth.calendar()
        t = "2020-06-01"
        d = [cal.offset(t, k) for k in range(0, 12)]
        ev = make_event(cal, t)
        merger = {"type": "cash_merger", "acquiree_symbol": "MOVR", "date": d[4]}
        tr = resolve(ev, "b_lane", ctx_for(cal, actions=[merger]), Store(), {"MOVR": [book(cal, d[1], "09:35")]},
                     fail=("quote_backward",))
        self.assertEqual((tr["status"], tr["incomplete"]), ("fetch_incomplete", ["quote_backward"]))
        # without a merger record the trade stays terminal-zero, flagged for the rebooking sensitivity only (L-1)
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": [book(cal, d[1], "09:35")]}, fail=("quote_backward",))
        self.assertEqual((tr["status"], tr["exit"], tr["nets"]["primary"]), ("filled", "terminal_zero", -1.0))
        self.assertTrue(tr["backward_incomplete"])
        self.assertNotIn("terminal_rebooked_at_last_bid", tr)

    def test_ratio_rule_inside_the_hold_is_flagged(self):
        cal = synth.calendar()
        t = "2020-06-01"
        d = [cal.offset(t, k) for k in range(0, 12)]
        ev = make_event(cal, t)
        qs = {"MOVR": [book(cal, d[1], "09:35"), book(cal, d[5], "15:55")]}
        self.assertFalse(resolve(ev, "b_lane", ctx_for(cal), Store(), qs)["ratio_rule_in_hold"])
        ev["raw"][d[3]] = dict(ev["raw"][d[3]], c=ev["raw"][d[2]]["c"] * 2.0)   # a 2:1 raw ratio with f = 1
        ev["split"][d[3]] = dict(ev["split"][d[3]], c=ev["split"][d[3]]["c"] * 2.0)
        self.assertTrue(resolve(ev, "b_lane", ctx_for(cal), Store(), qs)["ratio_rule_in_hold"])


FEES_2028 = synth.fee_document([("2016-01-01", "2028-12-31", 13.00)], [("2016-01-01", "2028-12-31", 0.000119, 5.95)])


class Splits(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"
        self.d = [self.cal.offset(self.t, k) for k in range(0, 12)]

    def test_split_record_not_carried_by_bars_excludes_the_trade(self):
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        rec = {"type": "forward_split", "symbol": "MOVR", "date": d[3], "new_rate": 2, "old_rate": 1}
        tr = trade(ev, "b_lane", ctx_for(cal, actions=[rec]), _entry_store(cal, ev, d))
        self.assertEqual(tr["status"], "split_record_excluded")

    def test_split_carried_by_bars_is_booked_with_F(self):
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t, split_at={d[3]: 2.0})
        rec = {"type": "forward_split", "symbol": "MOVR", "date": d[3], "new_rate": 2, "old_rate": 1}
        qs = [book(cal, d[1], "09:35"), book(cal, d[5], "15:55", 5.5, 5.51)]
        tr = resolve(ev, "b_lane", ctx_for(cal, actions=[rec]), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["F"]), ("filled", 2.0))
        self.assertGreater(tr["nets"]["primary"], 0.0)

    def test_split_on_the_exit_session_of_b_overnight(self):
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t, split_at={d[2]: 2.0})
        qs = [book(cal, d[1], "15:55"), book(cal, d[2], "09:30", 5.0, 5.01, dt=1)]
        tr = resolve(ev, "b_overnight", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["F"], tr["exit_session"]), (2.0, d[2]))
        self.assertLess(abs(tr["nets"]["primary"]), 0.02)

    def test_missing_bar_on_exit_session_makes_F_undefined(self):
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t, missing=(d[5],))
        qs = [book(cal, d[1], "09:35"), book(cal, d[5], "15:55")]
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual(tr["status"], "undefined_factor")


class Round15Accounting(unittest.TestCase):
    """Review round 15: F01 (spin-off accounting), F05 (the count applies the read's accounting eligibility) and N06
    (a delayed exit is checked for split records through its actual exit session)."""

    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"
        self.d = [self.cal.offset(self.t, k) for k in range(0, 12)]

    def _both(self, ev, arm, actions=(), qs=None):
        """(read status, count status) of one trade, the read served from qs."""
        cal, d = self.cal, self.d
        qs = qs or [book(cal, d[1], "09:35"), book(cal, d[1], "15:55"), book(cal, d[2], "09:30", dt=1),
                    book(cal, d[5], "15:55")]
        read = resolve(ev, arm, ctx_for(cal, actions=actions), Store(), {"MOVR": qs})
        count = resolve(ev, arm, ctx_for(cal, actions=actions, mode="count"), Store(), {"MOVR": qs})
        return read["status"], count["status"]

    def test_a_split_record_during_a_delayed_exit_excludes_the_trade(self):
        """N06: E = d[5]; no quote on E or E+1, a fill on E+2 = d[7], and a forward split record effective on d[7]
        that the adjusted bars do not carry (F = 1). At e7529b47 only (d1, E] was checked, so the trade was booked
        with F = 1 at a post-split price (a 50% loss that is an artifact)."""
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        rec = {"type": "forward_split", "symbol": "MOVR", "date": d[7], "new_rate": 2, "old_rate": 1}
        qs = [book(cal, d[1], "09:35"), book(cal, d[7], "10:00", 5.0, 5.01)]
        tr = resolve(ev, "b_lane", ctx_for(cal, actions=[rec]), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["exit_session"]), ("split_record_excluded", d[7]))
        # the same fill with no record books a delayed exit
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["exit"]), ("filled", "delayed"))

    def test_a_spin_off_record_excludes_the_trade_and_the_h3c_event_in_both_paths(self):
        """F01: a spin-off's entitlement is shares of another issuer. With a spin_off record of the held symbol
        effective inside the hold, the trade (read and count) and the H3-c event are excluded and counted; at
        e7529b47 the all/split step was booked as a dividend and the trade stayed in the statistic."""
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        spin = {"type": "spin_off", "source_symbol": "MOVR", "new_symbol": "SPUN", "date": d[3], "source_rate": 1,
                "new_rate": 0.5}
        self.assertEqual(self._both(ev, "b_lane", [spin]), ("spin_off_record_excluded", "spin_off_record_excluded"))
        self.assertEqual(self._both(ev, "a_intraday", [spin])[0], "filled")      # same-session hold: none spans it
        for mode in ("read", "count"):
            self.assertEqual(h3c_event(ev, ctx_for(cal, actions=[spin], mode=mode))["status"],
                             "spin_off_record_excluded")
        other = dict(spin, source_symbol="ELSE")
        self.assertEqual(self._both(ev, "b_lane", [other])[0], "filled")

    def test_a_spin_off_record_is_parsed_with_its_ex_date(self):
        from core import records
        body = {"corporate_actions": {"spin_offs": [{"source_symbol": "MOVR", "new_symbol": "SPUN",
                                                     "ex_date": "2020-06-04", "process_date": "2020-06-05",
                                                     "source_rate": 1, "new_rate": 0.5}]}}
        self.assertEqual(records.corporate_actions(body), [{"type": "spin_off", "date": "2020-06-04",
                                                            "source_symbol": "MOVR", "new_symbol": "SPUN",
                                                            "new_rate": 0.5}])

    def test_a_distribution_without_a_record_is_booked_as_cash(self):
        """F01's limitation, pinned: a distribution that the provider's all adjustment carries but no retained record
        names (a spin-off whose record is missing looks the same) is booked as cash at its adjustment value, the
        close before its ex-date times the step, never as a share change."""
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        raw, split, allc = synth.series(cal, cal.offset(self.t, -60), cal.offset(self.t, 12),
                                        lambda x: 10.0 if x < d[3] else 9.0, cash_at={d[3]: 1.0})
        ev.update({"raw": raw, "split": split, "all": allc})
        qs = [book(cal, d[1], "09:35"), book(cal, d[5], "15:55", 9.0, 9.02)]
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((tr["status"], tr["F"]), ("filled", 1.0))
        self.assertAlmostEqual(tr["cash"], 1.0, places=9)

    def test_the_count_excludes_what_the_read_excludes_for_an_undefined_factor(self):
        """F05: E = d[5] traded (its raw bar exists) but its split bar is missing, so F(d1, E) is undefined: the read
        books nothing ('undefined_factor') and the count now agrees; at e7529b47 the count returned 'counted' before
        the accounting checks. With no raw bar on E at all (a halt or a delisting), the count keeps the trade and the
        read decides it (a terminal trade stays in the statistic)."""
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        del ev["split"][d[5]]
        self.assertEqual(self._both(ev, "b_lane"), ("undefined_factor", "undefined_factor"))
        halted = make_event(cal, self.t, missing=(d[5],))
        qs = [book(cal, d[1], "09:35"), book(cal, d[3], "11:00", 4.0, 4.05)]
        read, count = self._both(halted, "b_lane", qs=qs)
        self.assertEqual(count, "counted")
        tr = resolve(halted, "b_lane", ctx_for(cal), Store(), {"MOVR": qs})
        self.assertEqual((read, tr["exit"]), ("filled", "terminal_zero"))

    def test_the_h3c_count_applies_the_reads_leg_accounting(self):
        """F05: H3-c overnight legs whose all bars are missing have an undefined cash term: the read excludes the event
        and the count now does too (at e7529b47 the count returned 'counted' once the 8 prints existed)."""
        cal, d = self.cal, self.d
        ev = make_event(cal, self.t)
        raw, split, allc = synth.series(cal, cal.offset(self.t, -60), cal.offset(self.t, 12),
                                        lambda x: 10.0 if x < d[3] else 9.0, cash_at={d[3]: 1.0})
        del allc[d[3]]
        ev.update({"raw": raw, "split": split, "all": allc})
        del ev["all"][d[2]]
        for mode in ("read", "count"):
            self.assertEqual(h3c_event(ev, ctx_for(cal, mode=mode))["status"], "undefined_factor", mode)


class RenamedActions(unittest.TestCase):
    """Action symbols follow the issuer of the asof=t request, with dated ticker-reuse boundaries."""

    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"
        self.d = [self.cal.offset(self.t, k) for k in range(12)]
        self.ev = make_event(self.cal, self.t, sym="OLD")

    def _rename(self, old, new, day):
        return {"type": "name_change", "old_symbol": old, "new_symbol": new, "date": day}

    def _assert_statuses(self, actions, excluded=None):
        cal, d = self.cal, self.d
        qs = {"OLD": [book(cal, d[1], "09:35"), book(cal, d[5], "15:55")]}
        for mode in ("read", "count"):
            with self.subTest(mode=mode, path="trade"):
                result = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions, mode=mode), Store(), qs)
                self.assertEqual(result["status"], excluded or ("filled" if mode == "read" else "counted"))
                if excluded:
                    self.assertNotIn("nets", result)
            with self.subTest(mode=mode, path="h3c"):
                result = h3c_event(self.ev, ctx_for(cal, actions=actions, mode=mode))
                self.assertEqual(result["status"], excluded or ("complete" if mode == "read" else "counted"))
                if excluded or mode == "count":
                    self.assertNotIn("value", result)

    def test_successor_spin_off_excludes_trade_and_h3c_in_both_paths(self):
        d = self.d
        spin = {"type": "spin_off", "source_symbol": "NEW", "new_symbol": "SPUN", "date": d[3]}
        chains = [[self._rename("OLD", "NEW", d[2])],
                  [self._rename("MID", "NEW", d[2]), self._rename("OLD", "MID", d[1])],
                  [self._rename("MID", "NEW", d[2]), self._rename("OLD", "MID", d[2])]]
        for chain in chains:
            with self.subTest(chain=chain):
                self._assert_statuses([spin, *chain], "spin_off_record_excluded")
        # Same-session intraday holds and another issuer's entitlement remain eligible.
        self._assert_statuses([*chains[0], dict(spin, source_symbol="ELSE")])
        for mode in ("read", "count"):
            tr = resolve(self.ev, "a_intraday", ctx_for(self.cal, actions=[spin, *chains[0]], mode=mode), Store(),
                         {"OLD": [book(self.cal, d[1], "09:35"), book(self.cal, d[1], "15:55")]})
            self.assertEqual(tr["status"], "filled" if mode == "read" else "counted")

    def test_successor_unadjusted_splits_exclude_trade_and_h3c_in_both_paths(self):
        cal, d = self.cal, self.d
        for typ, ratio in (("forward_split", 2.0), ("reverse_split", 0.5)):
            with self.subTest(split_type=typ):
                raw, split, allc = synth.series(cal, cal.offset(self.t, -60), cal.offset(self.t, 12),
                                                lambda s: 10.0 if s < d[3] else 10.0 / ratio)
                self.ev.update(raw=raw, split=split, all=allc, prints=synth.prints_from(raw))
                rec = {"type": typ, "symbol": "NEW", "date": d[3], "new_rate": ratio, "old_rate": 1}
                self._assert_statuses([rec, self._rename("OLD", "NEW", d[2])], "split_record_excluded")

    def test_successor_actions_during_delayed_exit_exclude_the_read(self):
        cal, d = self.cal, self.d
        for typ, field, excluded in (("spin_off", "source_symbol", "spin_off_record_excluded"),
                                     ("forward_split", "symbol", "split_record_excluded"),
                                     ("reverse_split", "symbol", "split_record_excluded")):
            with self.subTest(action=typ):
                actions = [self._rename("OLD", "NEW", d[2]), {"type": typ, field: "NEW", "date": d[7]}]
                qs = {"OLD": [book(cal, d[1], "09:35"), book(cal, d[7], "10:00", 5.0, 5.01)]}
                count = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions, mode="count"), Store(), qs)
                self.assertEqual(count["status"], "counted")  # count knows only the planned exit, d[5]
                self.assertEqual(h3c_event(self.ev, ctx_for(cal, actions=actions))["status"], "complete")
                read = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions), Store(), qs)
                self.assertEqual((read["status"], read["exit_session"]), (excluded, d[7]))
                self.assertNotIn("nets", read)

    def test_successor_terminal_mergers_book_the_last_bid_or_flag_no_bid(self):
        cal, d = self.cal, self.d
        chain = [self._rename("MID", "NEW", d[2]), self._rename("OLD", "MID", d[1])]
        for typ in ("cash_merger", "stock_merger", "stock_and_cash_merger"):
            for has_bid in (True, False):
                with self.subTest(merger_type=typ, has_bid=has_bid):
                    actions = [{"type": typ, "acquiree_symbol": "NEW", "acquirer_symbol": "BIG", "date": d[3]},
                               *chain]
                    qs = [book(cal, d[1], "09:35")]
                    if has_bid:
                        qs.append(book(cal, d[3], "15:59", 11.9, 11.95))
                    count = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions, mode="count"), Store(), {"OLD": qs})
                    self.assertEqual(count["status"], "counted")
                    read = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions), Store(), {"OLD": qs})
                    if has_bid:
                        self.assertEqual(read["exit"], "terminal_merger")
                        self.assertEqual((read["terminal_booking"], read["exit_session"]), ("merger", d[3]))
                        self.assertEqual(read["primary_parts"][2], 11.9)
                        self.assertEqual(read["primary_parts"][6], 0.0)  # no exit spread or impact
                    else:
                        self.assertTrue(read.get("merger_without_bid"))
                        self.assertEqual((read["exit"], read["nets"]["primary"]), ("terminal_zero", -1.0))

    def test_action_exclusions_respect_dated_rename_and_ticker_reuse_boundaries(self):
        d = self.d
        for typ, field, excluded in (("spin_off", "source_symbol", "spin_off_record_excluded"),
                                     ("forward_split", "symbol", "split_record_excluded"),
                                     ("reverse_split", "symbol", "split_record_excluded")):
            rec = {"type": typ, field: "OLD", "date": d[3]}
            cases = [
                # After OLD becomes NEW, a reused OLD is a different issuer, even if OLD renames again.
                ([self._rename("OLD", "NEW", d[2]), self._rename("OLD", "OTHER", d[3])], rec, None),
                # A future successor's action does not belong to the holding before the rename.
                ([self._rename("OLD", "NEW", d[4])], dict(rec, **{field: "NEW"}), None),
                # OLD still owns its action before its own rename.
                ([self._rename("OLD", "NEW", d[4])], rec, excluded),
                # A previous holder of OLD renamed before asof=t; the current OLD is a new issuer.
                ([self._rename("OLD", "PREVIOUS", self.cal.offset(self.t, -1))], rec, excluded),
                ([self._rename("OLD", "PREVIOUS", self.cal.offset(self.t, -1))],
                 dict(rec, **{field: "PREVIOUS"}), None),
                # The process date is the start of the successor symbol's interval.
                ([self._rename("OLD", "NEW", d[3])], dict(rec, **{field: "NEW"}), excluded),
                ([self._rename("OLD", "NEW", d[3])], rec, None),
                # An undated rename cannot attach a successor action to this issuer.
                ([self._rename("OLD", "NEW", None)], dict(rec, **{field: "NEW"}), None),
            ]
            for chain, action, want in cases:
                with self.subTest(action=action, chain=chain):
                    self._assert_statuses([action, *chain], want)

    def test_terminal_merger_identity_respects_reuse_dates_and_acquiree_role(self):
        cal, d = self.cal, self.d
        rename = self._rename("OLD", "NEW", d[2])
        merger = {"type": "cash_merger", "acquiree_symbol": "NEW", "acquirer_symbol": "BIG", "date": d[3]}
        cases = [(dict(merger, acquiree_symbol="OLD"), "terminal_zero", True),
                 (dict(merger, acquiree_symbol="ELSE", acquirer_symbol="NEW"), "terminal_zero", True),
                 (dict(merger, date=d[1]), "terminal_zero", True),
                 (dict(merger, date=d[10]), "terminal_merger", None),
                 (dict(merger, date=d[11]), "terminal_zero", False)]
        qs = {"OLD": [book(cal, d[1], "09:35"), book(cal, d[3], "15:59", 11.9, 11.95)]}
        for action, exit_kind, no_record in cases:
            with self.subTest(action=action):
                result = resolve(self.ev, "b_lane", ctx_for(cal, actions=[action, rename]), Store(), qs)
                self.assertEqual(result["exit"], exit_kind)
                if no_record is not None:
                    self.assertEqual(result["no_merger_record"], no_record)

    def test_terminal_zero_chained_rename_is_counted_and_rerequested(self):
        """Round 17 F2 re-review: use the dated issuer chain from Ctx.issuer_records at 1961e23f,
        including an entry-day transition that is itself outside the diagnostic interval."""
        cal, d = self.cal, self.d
        for first_day, successor in ((d[1], "NEW"), (d[3], "MID")):
            with self.subTest(first_day=first_day):
                # Reverse provider order must not change the issuer's transition order.
                actions = [self._rename("MID", "NEW", d[3]), self._rename("OLD", "MID", first_day)]
                store = Store()
                tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions), store,
                             {"OLD": [book(cal, d[1], "09:35")],
                              successor: [book(cal, d[5], "15:55", 10.5, 10.6)]})
                self.assertEqual((tr["exit"], tr["nets"]["primary"]), ("terminal_zero", -1.0))
                self.assertTrue(tr["rename_record_in_window"])
                self.assertEqual(tr["rename_sensitivity"]["new_symbol"], successor)
                self.assertEqual(tr["rename_sensitivity"]["status"], "fill")
                self.assertEqual(tr["rename_sensitivity"]["fill_session"], d[5])
                requests = [r for r in store.req.values() if r["kind"] == "quote_rename"]
                self.assertEqual([(r["params"]["symbols"], r["params"]["asof"]) for r in requests],
                                 [(successor, d[3])])

    def test_terminal_zero_single_rename_requests_successor_asof_process_date(self):
        cal, d = self.cal, self.d
        store = Store()
        tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[self._rename("OLD", "NEW", d[3])]), store,
                     {"OLD": [book(cal, d[1], "09:35")], "NEW": [book(cal, d[5], "15:55", 10.5, 10.6)]})
        self.assertEqual((tr["exit"], tr["nets"]["primary"]), ("terminal_zero", -1.0))
        self.assertTrue(tr["rename_record_in_window"])
        self.assertEqual(tr["rename_sensitivity"]["new_symbol"], "NEW")
        self.assertEqual(tr["rename_sensitivity"]["status"], "fill")
        self.assertAlmostEqual(tr["rename_sensitivity"]["fill_mid"], 10.55)
        requests = [r for r in store.req.values() if r["kind"] == "quote_rename"]
        self.assertEqual([(r["params"]["symbols"], r["params"]["asof"]) for r in requests], [("NEW", d[3])])

    def test_terminal_zero_rename_diagnostic_keeps_strict_date_window(self):
        cal, d = self.cal, self.d
        cases = ((cal.offset(self.t, -1), False), (self.t, False), (d[1], False),
                 (d[2], True), (d[10], True), (d[11], False), (None, False))
        for day, counted in cases:
            with self.subTest(day=day):
                store = Store()
                tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=[self._rename("OLD", "NEW", day)]), store,
                             {"OLD": [book(cal, d[1], "09:35")]})
                self.assertEqual((tr["exit"], tr["nets"]["primary"]), ("terminal_zero", -1.0))
                self.assertEqual(tr["rename_record_in_window"], counted)
                self.assertEqual("rename_sensitivity" in tr, counted)
                requests = [r for r in store.req.values() if r["kind"] == "quote_rename"]
                self.assertEqual(bool(requests), counted)
                if counted:
                    self.assertEqual({(r["params"]["symbols"], r["params"]["asof"]) for r in requests},
                                     {("NEW", day)})

    def test_terminal_zero_rename_diagnostic_rejects_other_issuers(self):
        cal, d = self.cal, self.d
        cases = [
            # OLD is reused after the held issuer has renamed away on entry day.
            [self._rename("OLD", "MID", d[1]), self._rename("OLD", "OTHER", d[3])],
            # A pre-t (or t-day) rename belongs to an earlier holder of OLD.
            [self._rename("OLD", "MID", cal.offset(self.t, -1)), self._rename("MID", "NEW", d[3])],
            [self._rename("OLD", "MID", self.t), self._rename("MID", "NEW", d[3])],
            # Matching only new_symbol would attach an unrelated issuer to the holding.
            [self._rename("OTHER", "OLD", d[3])],
            [self._rename("OLD", "MID", d[1]), self._rename("OTHER", "MID", d[3])],
        ]
        for actions in cases:
            with self.subTest(actions=actions):
                store = Store()
                tr = resolve(self.ev, "b_lane", ctx_for(cal, actions=actions), store,
                             {"OLD": [book(cal, d[1], "09:35")]})
                self.assertEqual((tr["exit"], tr["nets"]["primary"]), ("terminal_zero", -1.0))
                self.assertFalse(tr["rename_record_in_window"])
                self.assertNotIn("rename_sensitivity", tr)
                self.assertFalse(any(r["kind"] == "quote_rename" for r in store.req.values()))


def _entry_store(cal, ev, d):
    store = Store()
    req = plan.entry_window(cal, "MOVR", ev["t"], "b_lane")
    synth.put_quotes(store, req, "MOVR", [book(cal, d[1], "09:35")])
    return store


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()

    def test_delisting_on_the_segment_last_session_is_censored_terminal(self):
        cal = self.cal
        t = "2020-12-28"
        ev = make_event(cal, t)
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": [book(cal, "2020-12-29", "09:35"),
                                                                 book(cal, "2020-12-31", "11:00")]})
        self.assertEqual((tr["exit"], tr["censored"], tr["planned_exit_session"]), ("censored_terminal", True, "2020-12-31"))

    def test_censored_trade_filled_after_the_segment_end(self):
        cal = self.cal
        t = "2020-12-28"
        ev = make_event(cal, t)
        tr = resolve(ev, "b_lane", ctx_for(cal), Store(), {"MOVR": [book(cal, "2020-12-29", "09:35"),
                                                                 book(cal, "2021-01-04", "10:00", 9, 9.02)]})
        self.assertEqual((tr["exit"], tr["exit_session"]), ("censored_delayed", "2021-01-04"))

    def test_no_b_overnight_entry_on_a_segment_last_session(self):
        cal = self.cal
        ev = make_event(cal, "2020-12-30")
        self.assertEqual(trade(ev, "b_overnight", ctx_for(cal), Store())["status"], "no_entry_segment_last")

    def test_embargo_applies_to_every_arm(self):
        """Review round 15, F10: H3-a's exit search can run to E+5, so its entries in the first 6 sessions of a segment
        are embargoed like every other arm's; e7529b47 asserted the exemption."""
        cal = self.cal
        ev = make_event(cal, "2020-01-03")
        self.assertEqual(trade(ev, "b_lane", ctx_for(cal), Store())["status"], "embargoed")
        self.assertEqual(trade(ev, "b_overnight", ctx_for(cal), Store())["status"], "embargoed")
        self.assertEqual(trade(ev, "a_intraday", ctx_for(cal), Store())["status"], "embargoed")
        from core.params import BOOT
        self.assertEqual(BOOT["block_sessions"]["H3-a"], 10)      # the block covers its E+5 horizon too

    def test_decision_whose_entry_lies_in_no_segment_is_dropped(self):
        cal = self.cal
        ev = make_event(cal, "2020-12-31")
        self.assertEqual(trade(ev, "a_intraday", ctx_for(cal), Store())["status"], "dropped_no_segment")


class H3c(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"

    def _split_event(self, ratios, adjusted):
        """Official prices reflect every split; adjusted bars carry only the selected records."""
        import math
        cal, t = self.cal, self.t
        ev = make_event(cal, t)
        raw, split, allc = synth.series(
            cal, cal.offset(t, -60), cal.offset(t, 12),
            lambda s: 10.0 / math.prod(r for day, r in ratios.items() if day <= s), split_at=adjusted)
        ev.update(raw=raw, split=split, all=allc, prints=synth.prints_from(raw))
        records = [{"type": "forward_split" if ratio > 1 else "reverse_split", "symbol": "MOVR", "date": day,
                    "new_rate": ratio, "old_rate": 1} for day, ratio in ratios.items()]
        return ev, records

    def _assert_split_eligibility(self, ratios, missing, no_record_value):
        adjusted, records = self._split_event(ratios, ratios)
        unadjusted, _ = self._split_event(ratios, {day: r for day, r in ratios.items() if day not in missing})
        # Without a retained record a price move is an outcome, never a primary ratio-rule exclusion.
        self.assertAlmostEqual(h3c_event(unadjusted, ctx_for(self.cal))["value"], no_record_value, places=12)
        for mode, status in (("read", "complete"), ("count", "counted")):
            with self.subTest(mode=mode, adjusted=True):
                result = h3c_event(adjusted, ctx_for(self.cal, actions=records, mode=mode))
                self.assertEqual(result["status"], status)
                if mode == "read":
                    self.assertAlmostEqual(result["value"], 0.0, places=12)
                else:
                    self.assertNotIn("value", result)
            with self.subTest(mode=mode, adjusted=False):
                result = h3c_event(unadjusted, ctx_for(self.cal, actions=records, mode=mode))
                self.assertEqual(result["status"], "split_record_excluded")
                self.assertNotIn("value", result)

    def test_forward_split_record_excludes_unadjusted_h3c_in_both_paths(self):
        """A retained 2:1 split on t+3 must not produce log(0.5)/4 from $10 -> $5 prints."""
        day = self.cal.offset(self.t, 3)
        self._assert_split_eligibility({day: 2.0}, {day}, -0.17328679513998632)

    def test_reverse_split_record_excludes_unadjusted_h3c_in_both_paths(self):
        """A retained 1:2 split on t+3 must not produce log(2)/4 from $10 -> $20 prints."""
        day = self.cal.offset(self.t, 3)
        self._assert_split_eligibility({day: 0.5}, {day}, 0.17328679513998632)

    def test_h3c_checks_each_split_when_another_split_is_adjusted(self):
        """An adjustment on one overnight leg cannot conceal an unadjusted split on another."""
        days = [self.cal.offset(self.t, k) for k in (2, 4)]
        for missing in days:
            with self.subTest(missing=missing):
                self._assert_split_eligibility(dict.fromkeys(days, 2.0), {missing}, -0.17328679513998632)

    def test_legs_decompose_close_to_close(self):
        cal, t = self.cal, self.t
        ev = make_event(cal, t)
        d = [cal.offset(t, k) for k in range(6)]
        opens = {d[k]: 10.0 + 0.1 * k for k in range(1, 6)}
        closes = {d[k]: 10.05 + 0.1 * k for k in range(1, 6)}
        for k in range(1, 6):
            ev["prints"][d[k]] = synth.auction(opens[d[k]], closes[d[k]])
        res = h3c_event(ev, ctx_for(cal))
        import math
        on = [math.log(opens[d[k + 1]] / closes[d[k]]) for k in range(1, 5)]
        intra = [math.log(closes[d[k]] / opens[d[k]]) for k in range(2, 6)]
        self.assertAlmostEqual(res["value"], sum(on) / 4 - sum(intra) / 4)
        self.assertAlmostEqual(sum(on) + sum(intra), math.log(closes[d[5]] / closes[d[1]]))

    def test_missing_leg_and_segment_end(self):
        cal, t = self.cal, self.t
        ev = make_event(cal, t)
        ev["prints"][cal.offset(t, 3)] = synth.auction(None, 10.0, no_open=True)
        self.assertEqual(h3c_event(ev, ctx_for(cal))["status"], "missing_leg")
        ev2 = make_event(cal, t)
        for k in (4, 5):
            ev2["prints"].pop(cal.offset(t, k))
        self.assertEqual(h3c_event(ev2, ctx_for(cal))["status"], "terminal")
        late = make_event(cal, "2020-12-24")
        self.assertEqual(h3c_event(late, ctx_for(cal))["status"], "legs_cross_segment_end")

    def test_count_mode_is_presence_only(self):
        ev = make_event(self.cal, self.t)
        self.assertEqual(h3c_event(ev, ctx_for(self.cal, mode="count"))["status"], "counted")


if __name__ == "__main__":
    unittest.main()
