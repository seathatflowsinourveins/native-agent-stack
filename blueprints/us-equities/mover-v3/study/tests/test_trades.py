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
    return Ctx(cal=cal, stage=stage, segs=segs, actions=list(actions), fees=costs.Fees(FEES), cells=CELLS, mode=mode)


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
        want = costs.trade_net_return(20_000.0, entry_mid, exit_mid, 1.0, 0.0, c_in, c_out, costs.Fees(FEES), d[5])
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
        f = costs.Fees(FEES)
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
        return Ctx(cal=self.cal, stage="holdout", segs=self.seg, fees=costs.Fees(FEES_2028), cells=CELLS, **kw)

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


FEES_2028 = {"sec_section31_usd_per_million_of_sales": [
    {"from": "2016-01-01", "to": "2028-12-31", "rate": 13.00, "source": "synthetic"}],
    "finra_taf_covered_equity_sales": [
    {"from": "2016-01-01", "to": "2028-12-31", "usd_per_share": 0.000119, "max_per_trade": 5.95, "source": "synthetic"}]}


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

    def test_embargo_applies_to_multi_session_arms_only(self):
        cal = self.cal
        ev = make_event(cal, "2020-01-03")
        self.assertEqual(trade(ev, "b_lane", ctx_for(cal), Store())["status"], "embargoed")
        self.assertEqual(trade(ev, "b_overnight", ctx_for(cal), Store())["status"], "embargoed")
        self.assertNotEqual(trade(ev, "a_intraday", ctx_for(cal), Store()).get("status"), "embargoed")

    def test_decision_whose_entry_lies_in_no_segment_is_dropped(self):
        cal = self.cal
        ev = make_event(cal, "2020-12-31")
        self.assertEqual(trade(ev, "a_intraday", ctx_for(cal), Store())["status"], "dropped_no_segment")


class H3c(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"

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
