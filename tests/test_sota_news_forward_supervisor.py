"""SYN: news-forward supervisor flows against a stateful paper-broker double.

Covers the GPU schedule gate, shadow snapshots, the day's close-out (stale entries, CLS
retries, the 15:55 market pass, after-hours flatten with the last-trade fallback,
reconciliation), the kill switch (failed flatten then re-flatten, persistence across a
restart, exits while killed, cancel before re-flatten), the OPG basket (pre-market gates,
95% sizing, a rejected leg, an unfilled leg trimmed after the open), the restart rebuild,
a cancel race, carry-over exits, exit-only mode and the arm entries. No GPU, no network.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/sota-mover/news-forward"))

import common  # noqa: E402
import planner  # noqa: E402
import shadow  # noqa: E402
import supervisor  # noqa: E402

NY = ZoneInfo("America/New_York")
SCHED = planner.day_schedule(common.load_calendar(), date(2026, 9, 25))


def ny(hh, mm=0):
    return datetime(2026, 9, 25, hh, mm, tzinfo=NY).astimezone(timezone.utc)


def at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=NY).astimezone(timezone.utc)


class GpuGate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="nf-gpu-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def gate(self, now, free=20000, others=(), on_gpu=False):
        with mock.patch.object(supervisor, "gpu_free_mib", return_value=free), \
             mock.patch.object(supervisor, "other_gpu_jobs_active", return_value=list(others)):
            return supervisor.gpu_allowed(now, SCHED, self.dir, on_gpu)

    def test_before_0830_needs_marker_and_no_other_jobs(self):
        self.assertEqual(self.gate(ny(5)), (False, "before_0830_without_gpu_early_ok"))
        Path(self.dir, "gpu-early-ok").touch()
        self.assertEqual(self.gate(ny(5), others=["sota-news-score-x.service"]), (False, "other_gpu_jobs_active"))
        self.assertEqual(self.gate(ny(5)), (True, "ok"))

    def test_free_vram_threshold(self):
        self.assertEqual(self.gate(ny(8, 30), free=9215)[0], False)
        self.assertEqual(self.gate(ny(8, 30), free=9216), (True, "ok"))
        self.assertEqual(self.gate(ny(8, 30), free=None)[1], "nvidia_smi_unavailable")
        self.assertEqual(self.gate(ny(5), free=100, on_gpu=True), (True, "already_loaded"))


class ShadowSchedule(unittest.TestCase):
    def test_three_snapshots_once_each(self):
        t = shadow.ShadowTracker()
        ev = {"event_id": "1:ACME", "symbol": "ACME", "created_at": common.iso(ny(17)), "session_label": "open_auction",
              "ext_segment": "ext_post", "lane": "liquid", "label": "FAVORABLE"}
        t.add(ev, "extended_hours", ny(17))
        t.add(ev, "extended_hours", ny(17))
        self.assertEqual(len(t), 3)
        self.assertEqual([s for _, s, _, _ in t.pop_due(ny(17, 15))], ["release", "plus15"])
        due = t.pop_due(ny(19))
        rec = shadow.quote_record(*due[0], {"bp": 10.0, "ap": 10.02, "t": "x"}, ny(19))
        self.assertTrue(rec["late"])
        self.assertEqual((rec["stage"], rec["session_label"], rec["trade_window"]), ("plus60", "ext_post", "open_auction"))
        self.assertEqual(len(t), 0)

    def test_release_snapshot_waits_for_receipt(self):
        times = planner.shadow_times(common.iso(ny(17)), ny(17, 5))
        self.assertEqual([s for s, _ in times], ["release", "plus15", "plus60"])
        self.assertEqual(times[0][1], ny(17, 5))
        self.assertEqual(times[2][1], ny(18))


ex = supervisor.ex
FRIDAY = date(2026, 9, 25)


class Broker:
    """Stateful paper-broker double: orders, fills, cancels; positions derive from fills.

    reject(intent) -> reason or None refuses a submission; fill_on_submit(intent) -> price or
    None fills it at once (a market order during RTH). Ids in cancel_race answer a cancel
    with pending_cancel for one read, then fill instead (a fill that beats the cancel).
    """

    LIVE = ("new", "accepted", "partially_filled", "pending_new", "pending_cancel")

    def __init__(self, equity="900000"):
        self.all = []
        self.cash = "900000"
        self.equity = equity
        self.reject = lambda intent: None
        self.fill_on_submit = lambda intent: None
        self.cancel_race = set()
        self.countdown = {}
        self.now = ny(9, 0)

    def add(self, cid, side, qty, filled, status="filled", at_=None, price="50", limit=None, tif="day"):
        info = planner.parse_cid(cid)
        filled = Decimal(str(filled))
        stamp = at_ or self.now
        o = {"id": f"o{len(self.all)}", "client_order_id": cid, "symbol": info["symbol"] if info else cid, "side": side,
             "qty": str(qty), "filled_qty": str(filled), "filled_avg_price": price if filled else None, "status": status,
             "submitted_at": stamp, "filled_at": stamp if filled else None, "limit_price": limit, "time_in_force": tif,
             "type": "limit" if limit else "market", "extended_hours": False}
        self.all.append(o)
        return o

    def find(self, cid):
        return next(o for o in self.all if o["client_order_id"] == cid)

    def fill(self, cid, qty=None, price="50"):
        o = self.find(cid)
        o.update(filled_qty=str(qty or o["qty"]), status="filled", filled_avg_price=price, filled_at=self.now)

    def account(self):
        return {"status": "ACTIVE", "equity": self.equity, "cash": self.cash, "multiplier": "4",
                "trading_blocked": False, "account_blocked": False}

    def positions(self):
        net = {}
        for o in self.all:
            q = Decimal(o["filled_qty"])
            if q:
                net[o["symbol"]] = net.get(o["symbol"], Decimal("0")) + (q if o["side"] == "buy" else -q)
        return [{"symbol": s, "qty": str(q), "market_value": "0"} for s, q in net.items() if q]

    def orders(self, status="open", after=None, symbols=None, limit=500, direction=None):
        for oid in list(self.countdown):
            if self.countdown[oid] > 0:
                self.countdown[oid] -= 1
            else:
                o = next(o for o in self.all if o["id"] == oid)
                o.update(status="filled", filled_qty=o["qty"], filled_avg_price="50", filled_at=self.now)
                del self.countdown[oid]
        rows = self.all
        if status == "open":
            rows = [o for o in rows if o["status"] in self.LIVE]
        elif status == "closed":
            rows = [o for o in rows if o["status"] not in self.LIVE]
        if symbols:
            rows = [o for o in rows if o["symbol"] in symbols]
        return [dict(o) for o in rows]

    def all_orders(self, after):
        return [dict(o) for o in self.all]

    def submit(self, intent):
        why = self.reject(intent)
        if why:
            raise RuntimeError(f"submit_failed:{why}")
        o = self.add(intent["client_order_id"], intent["side"], intent["qty"], 0, status="accepted",
                     limit=intent.get("limit_price"), tif=intent["time_in_force"])
        o["extended_hours"] = intent.get("extended_hours", False)
        price = self.fill_on_submit(intent)
        if price is not None:
            self.fill(intent["client_order_id"], price=price)
        return dict(o)

    def cancel(self, order_id):
        for o in self.all:
            if o["id"] == order_id and o["status"] in self.LIVE:
                if order_id in self.cancel_race:
                    o["status"] = "pending_cancel"
                    self.countdown[order_id] = 1
                else:
                    o["status"] = "canceled"


def make_sup(tmp, broker, day=FRIDAY, mode="paper", arms=None):
    """A supervisor without network: the broker double, a fixed clock and mocked market data."""
    cal = common.load_calendar()
    sup = supervisor.Supervisor.__new__(supervisor.Supervisor)
    sup._init_runtime()
    sup.sleep = lambda seconds: None
    clock = {"now": at(day, 9, 0)}
    sup.clock = lambda: clock["now"]
    sup.args = SimpleNamespace(preview_basket=False)
    sup.cfg = {"arms": arms or {"pm": {"orders_from": "2026-09-28"}, "ah": {"orders_from": "2026-09-24"}}}
    sup.mode, sup.state, sup.calendar, sup.trade_date = mode, tmp, cal, day
    sup.requested_mode = mode
    sup.schedule = planner.day_schedule(cal, day)
    sup.prev_session = cal.previous(day)
    sup.journal = common.Journal(tmp, day, clock=sup.clock)
    sup.ledger_epoch = at(date(2026, 9, 24), 0)
    sup.runstate = supervisor.RunState(os.path.join(tmp, "runstate", f"{day.isoformat()}-{mode}.json"))
    sup.equity = Decimal("900000")
    sup.sod = {"equity": "900000", "cash": "900000"}
    sup.l_core = Decimal("1")
    sup.limits = {a: planner.Limits.for_arm(a, sup.equity, 1, extra_cap=sup.equity) for a in planner.ARM_PREFIX}
    sup.account_gross_cap = 4 * sup.equity
    sup.executor = ex.Executor(mode, sup.journal, tmp, broker=broker if mode == "paper" else None, clock=sup.clock,
                               gate=ex.RiskGate(sup.limits, sup.account_gross_cap))
    sup.executor.killed = bool(sup.runstate.get("killed"))
    sup.ref_path = os.path.join(tmp, "ref-prices.json")
    sup.exposures = {a: planner.Exposure() for a in planner.ARM_PREFIX}
    sup.data = mock.Mock()
    sup.quotes = {}
    sup.data.snapshots.side_effect = lambda syms: {s: {"latestQuote": sup.quotes.get(s, {"bp": 49.95, "ap": 50.05}),
                                                       "latestTrade": {"p": 50.0, "t": common.iso(clock["now"])}} for s in syms}
    sup.data.asset.return_value = {"tradable": True, "shortable": True, "easy_to_borrow": True}
    sup._ca_keys = ("k", "s")
    return sup, clock


class Scenario(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="nf-sup-")
        self.b = Broker()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def rows(self, sup, kind=None):
        rows = common.read_jsonl(sup.journal.path)
        return [r for r in rows if kind is None or r["kind"] == kind]

    def ids(self, since=0):
        return [o["client_order_id"] for o in self.b.all[since:]]

    def tick(self, sup, clock, when, *, exits=True, kill=False):
        clock["now"] = self.b.now = when
        sup.refresh(when)
        if kill:
            sup.kill_check(when)
        if exits:
            sup.run_exits(when)


class PaperCloseOut(Scenario):
    def test_day_close_out_sequence(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        b.add("nf1-20260925-opg-BBB-short", "sell", 15, 15)
        b.add("nf1-20260925-rth-CCC-long", "buy", 9, 0, status="new", at_=ny(15, 20), limit="50.10")
        b.add("nf1x-pm-20260925-ent-AAA-long", "buy", 5, 5)
        b.add("nf1x-ah-20260924-ent-OLD-long", "buy", 8, 8, at_=at(date(2026, 9, 24), 16, 20))
        b.add("nf1x-ah-20260924-xopg1-OLD-long", "sell", 8, 8, at_=ny(9, 20))
        sup, clock = make_sup(self.dir, b)
        self.tick(sup, clock, ny(15, 24))
        self.assertEqual(b.find("nf1-20260925-rth-CCC-long")["status"], "new")  # 4 minutes old
        self.tick(sup, clock, ny(15, 26))
        self.assertEqual(b.find("nf1-20260925-rth-CCC-long")["status"], "canceled")  # stale after 5 minutes
        n = len(b.all)
        self.tick(sup, clock, ny(15, 40))
        self.assertEqual(self.ids(n), ["nf1-20260925-cls1-AAA-long", "nf1-20260925-cls1-BBB-short", "nf1x-pm-20260925-cls1-AAA-long"])
        self.assertEqual({o["time_in_force"] for o in b.all[n:]}, {"cls"})
        b.add("nf1-20260925-rth-EEE-long", "buy", 7, 7, at_=ny(15, 40))  # a fill that arrived after the first pass
        n = len(b.all)
        self.tick(sup, clock, ny(15, 40) + timedelta(seconds=30))
        self.assertEqual(self.ids(n), ["nf1-20260925-cls2-EEE-long"])  # M1: the CLS pass is re-planned
        n = len(b.all)
        self.tick(sup, clock, ny(15, 55))
        self.assertEqual(self.ids(n), [])  # every holding is covered by a working CLS order
        b.now = ny(16, 0)
        for cid in ("nf1-20260925-cls1-AAA-long", "nf1x-pm-20260925-cls1-AAA-long", "nf1-20260925-cls2-EEE-long"):
            b.fill(cid)
        b.find("nf1-20260925-cls1-BBB-short")["status"] = "expired"  # the BBB auction exit did not fill
        b.add("nf1x-ah-20260925-ent-FFF-long", "buy", 3, 3, at_=ny(16, 20))  # tonight's one-night ah hold
        n = len(b.all)
        self.tick(sup, clock, ny(16, 22))
        self.assertEqual(self.ids(n), ["nf1-20260925-ext1-BBB-short"])
        ext = b.all[n]
        self.assertEqual((ext["side"], ext["limit_price"], ext["extended_hours"]), ("buy", "50.31", True))
        b.fill("nf1-20260925-ext1-BBB-short")
        b.cash = "900250"  # the day's fill cash flows net to +250 (the 09-24 OLD entry is not today's)
        rec = sup.reconcile()
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(rec["overnight_holdings"], {"FFF": "3"})
        rows = common.read_jsonl(os.path.join(self.dir, "autolev-daily-paper.jsonl"))
        self.assertEqual((len(rows), rows[0]["core_flat"], rows[0]["round_trips"]), (1, True, 3))
        sup.reconcile()  # M8: a second reconciliation adds no second row for the session
        self.assertEqual(len(common.read_jsonl(os.path.join(self.dir, "autolev-daily-paper.jsonl"))), 1)

    def test_cls_retried_until_accepted_then_market_at_1555(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        attempts = []

        def reject(intent):
            if intent["time_in_force"] == "cls":
                attempts.append(intent["client_order_id"])
                return "cls_rejected"
            return None

        b.reject = reject
        sup, clock = make_sup(self.dir, b)
        when = ny(15, 40)
        while when <= ny(15, 50):
            self.tick(sup, clock, when)
            when += timedelta(seconds=30)
        self.assertEqual(attempts[:2], ["nf1-20260925-cls1-AAA-long", "nf1-20260925-cls2-AAA-long"])
        self.assertEqual(len(attempts), 19)  # 15:40:00 .. 15:49:00 every 30 s; none after 15:49
        self.tick(sup, clock, ny(15, 55))
        self.assertEqual([(o["client_order_id"], o["time_in_force"], o["type"]) for o in b.all[1:]],
                         [("nf1-20260925-mkt1-AAA-long", "day", "market")])

    def test_cancel_race_fill_is_covered_by_the_close(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        racing = b.add("nf1-20260925-rth-RRR-long", "buy", 10, 0, status="new", at_=ny(15, 39), limit="50.10")
        b.cancel_race = {racing["id"]}
        sup, clock = make_sup(self.dir, b)
        self.tick(sup, clock, ny(15, 40))
        self.assertEqual(b.find("nf1-20260925-rth-RRR-long")["status"], "filled")  # the fill beat the cancel
        cls = {o["client_order_id"]: o["qty"] for o in b.all if "-cls1-" in o["client_order_id"]}
        self.assertEqual(cls, {"nf1-20260925-cls1-AAA-long": "20", "nf1-20260925-cls1-RRR-long": "10"})

    def test_after_close_price_fallback_and_retry(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        sup, clock = make_sup(self.dir, b)
        sup.quotes["AAA"] = {}  # no quote after the close: the last trade (50.0) prices the exit
        self.tick(sup, clock, ny(16, 5))
        self.assertEqual((b.all[-1]["client_order_id"], b.all[-1]["limit_price"]), ("nf1-20260925-ext1-AAA-long", "49.75"))
        b.find("nf1-20260925-ext1-AAA-long")["status"] = "canceled"
        sup.data.snapshots.side_effect = lambda syms: {s: {} for s in syms}  # no quote and no trade
        self.tick(sup, clock, ny(16, 16))
        self.assertIn("exit_no_price", [r.get("event") for r in self.rows(sup, "risk")])
        sup.data.snapshots.side_effect = lambda syms: {s: {"latestQuote": {"bp": 49.0, "ap": 49.1}} for s in syms}
        self.tick(sup, clock, ny(16, 27))
        self.assertEqual((b.all[-1]["client_order_id"], b.all[-1]["limit_price"]), ("nf1-20260925-ext3-AAA-long", "48.75"))


class KillSwitch(Scenario):
    def test_failed_flatten_is_retried_and_the_kill_survives_a_restart(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        b.add("nf1-20260925-opg-BBB-short", "sell", 15, 15)
        b.equity = "881000"  # below 98% of the 900,000 start-of-day equity
        b.fill_on_submit = lambda intent: "50" if intent["type"] == "market" else None
        b.reject = lambda intent: "rejected" if intent["client_order_id"] == "nf1-20260925-kill1-AAA-long" else None
        sup, clock = make_sup(self.dir, b)
        self.tick(sup, clock, ny(10, 0), exits=False, kill=True)
        self.assertTrue(sup.executor.killed)
        self.assertEqual(self.ids(2), ["nf1-20260925-kill1-BBB-short"])  # AAA's first flatten was rejected
        self.tick(sup, clock, ny(10, 0) + timedelta(seconds=25), exits=False, kill=True)
        self.assertEqual(self.ids(3), ["nf1-20260925-kill2-AAA-long"])
        self.assertEqual(b.positions(), [])
        self.tick(sup, clock, ny(10, 1), exits=False, kill=True)
        self.assertIn("kill_flat", [r.get("event") for r in self.rows(sup, "risk")])
        entry = planner.entry_intent(FRIDAY, "rth", "NEW", "long", 1, "day", "10.00")
        self.assertIsNone(sup.executor.send(entry, {"purpose": "entry", "arm": "core", "session_label": "rth", "leg": "long",
                                                    "ref_price": "10.00"}))
        # restart: a new supervisor reads the persisted kill and continues its rounds
        b.add("nf1-20260925-rth-LATE-long", "buy", 4, 4, at_=ny(10, 2))  # e.g. a fill that landed during the restart
        sup2, clock2 = make_sup(self.dir, b)
        self.assertTrue(sup2.executor.killed)
        self.assertEqual(sup2.runstate.get("kill_round"), 2)
        self.tick(sup2, clock2, ny(10, 3), exits=False, kill=True)
        self.assertEqual(self.ids()[-1], "nf1-20260925-kill3-LATE-long")

    def test_exits_keep_running_while_the_kill_flatten_fails(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        b.reject = lambda intent: "rejected" if "-kill" in intent["client_order_id"] else None
        sup, clock = make_sup(self.dir, b)
        sup.runstate.update(killed=True)
        sup.executor.killed = True
        self.tick(sup, clock, ny(15, 40), kill=True)
        self.assertEqual(self.ids(1), ["nf1-20260925-cls1-AAA-long"])  # B1: the kill never skips the close

    def test_kill_waits_for_cancels_before_reflattening(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        working = b.add("nf1-20260925-cls1-AAA-long", "sell", 20, 0, status="accepted", tif="cls")
        b.cancel_race = {working["id"]}  # the pending cancel is overtaken by a fill
        sup, clock = make_sup(self.dir, b)
        sup.runstate.update(killed=True)
        sup.executor.killed = True
        self.tick(sup, clock, ny(15, 45), exits=False, kill=True)
        self.assertEqual(b.positions(), [])
        self.assertFalse(any("-kill" in c for c in self.ids()))  # nothing left to flatten: no oversell


class OpenBasket(Scenario):
    def pool(self, sup, symbols):
        for i, (sym, label) in enumerate(symbols):
            c = {"event_id": f"{i}:{sym}", "news_id": str(i), "symbol": sym, "label": label, "lane": "liquid",
                 "created_at": common.iso(at(date(2026, 9, 24), 17, i)), "session": "2026-09-25",
                 "session_label": planner.OPEN_AUCTION, "sigma": 0.02, "prior_median_dollar_volume_20": 50_000_000.0,
                 "prior_close": 50.0}
            prior = common.load_calendar().prior_sessions(FRIDAY, 2)
            sup.bars[(sym, "2026-09-25")] = [{"t": common.iso(datetime(d.year, d.month, d.day, tzinfo=NY)), "c": 50.0, "v": 1e6,
                                             "l": 49.0} for d in prior]
            sup.candidates[c["event_id"]] = sup.open_pool[c["event_id"]] = c
            sup.scores[c["event_id"]] = {"label": label}

    def test_gates_95pct_sizing_and_a_rejected_leg(self):
        b = self.b
        sup, clock = make_sup(self.dir, b)
        self.pool(sup, [("LA", "FAVORABLE"), ("SA", "UNFAVORABLE"), ("LB", "FAVORABLE"), ("SB", "UNFAVORABLE"),
                        ("LC", "FAVORABLE"), ("SC", "UNFAVORABLE"), ("WID", "FAVORABLE"), ("GAP", "FAVORABLE")])
        sup.quotes.update({"WID": {"bp": 49.0, "ap": 51.0}, "GAP": {"bp": 59.99, "ap": 60.01}})
        b.reject = lambda intent: "short_rejected" if intent["side"] == "sell" else None
        clock["now"] = b.now = ny(9, 15)
        sup.run_open_basket(ny(9, 15))
        reasons = {r["symbol"]: r["reason"] for r in self.rows(sup, "decision")}
        self.assertEqual((reasons["WID"], reasons["GAP"]), ("premarket_spread_above_100bps", "mid_outside_15pct_of_prior_close"))
        enter = [r for r in self.rows(sup, "decision") if r["action"] == "enter"]
        # min(0.0015 x 900k / 0.02, 0.5% x 50M, 5% x 900k) = 45,000 -> 95% = 42,750 -> 855 shares at the 50.00 mid
        self.assertEqual({(r["qty"], r["est_notional"]) for r in enter}, {(855, "42750.00")})
        refused = {r["intent"]["symbol"]: r["reason"] for r in self.rows(sup, "order_refused")}
        # shorts are rejected; the gate then keeps the long book inside the 90k net cap: L3 is skipped
        self.assertEqual(refused["LC"], "executor_cap:net_cap")
        self.assertTrue(all(refused[s].startswith("submit_failed:short_rejected") for s in ("SA", "SB", "SC")))
        self.assertEqual(sorted(self.ids()), ["nf1-20260925-opg-LA-long", "nf1-20260925-opg-LB-long"])
        net = self.rows(sup, "net_cap")[0]
        self.assertEqual((net["pre_cap"]["net"], net["post_cap"]["net"], net["net_cap"]), ("0.00", "0.00", "85500.0000"))

    def test_unfilled_leg_is_trimmed_after_the_open(self):
        b = self.b
        sup, clock = make_sup(self.dir, b)
        self.pool(sup, [("LA", "FAVORABLE"), ("SA", "UNFAVORABLE"), ("LB", "FAVORABLE"), ("SB", "UNFAVORABLE"),
                        ("LC", "FAVORABLE"), ("SC", "UNFAVORABLE")])
        clock["now"] = b.now = ny(9, 15)
        sup.run_open_basket(ny(9, 15))
        self.assertEqual(len(b.all), 6)  # interleaved legs keep every running net inside the cap
        b.now = ny(9, 30)
        for o in b.all:
            if o["side"] == "buy":
                b.fill(o["client_order_id"])
            else:
                o["status"] = "expired"  # the short leg did not fill in the auction
        self.tick(sup, clock, ny(9, 31))
        trims = [o for o in b.all if "-trim1-" in o["client_order_id"]]
        # filled 128,250 long vs 0 short: trim to 85,500 -> 42,750 pro rata = 14,250 each -> 285 shares at 49.70
        self.assertEqual({(o["qty"], o["limit_price"], o["side"]) for o in trims}, {("285", "49.7", "sell")})  # the contract canonicalizes 49.70
        self.assertEqual(len(trims), 3)
        actual = self.rows(sup, "net_actual")[-1]["windows"]["core:open_auction"]
        self.assertEqual((actual["long"], actual["short"]), ("128250", "0"))


class Restart(Scenario):
    def test_exposure_rebuilt_from_fills_and_reference_prices(self):
        b = self.b
        b.add("nf1-20260925-opg-P1-long", "buy", 800, 0, status="accepted", tif="opg")
        b.add("nf1-20260925-opg-P2-short", "sell", 700, 0, status="accepted", tif="opg")  # no reference price saved
        b.add("nf1-20260925-rth-R1-long", "buy", 100, 40, status="partially_filled", limit="50.20")
        b.add("nf1-20260925-opg-X1-long", "buy", 500, 0, status="rejected", tif="opg")
        sup, clock = make_sup(self.dir, b)
        sup.executor.ref_prices = {"nf1-20260925-opg-P1-long": "50.00"}
        sup.save_ref_prices()
        sup.executor.ref_prices = supervisor._json_file(sup.ref_path)  # as __init__ reloads it
        sup.refresh(ny(9, 20), force=True)
        core = sup.exposures["core"]
        # P1 800 x 50 + P2 at the 45,000 per-order cap + R1 40 x 50 + 60 x 50.20; X1 rejected: released
        self.assertEqual(core.gross, Decimal("40000.00") + Decimal("45000.00") + Decimal("2000") + Decimal("3012.00"))
        self.assertEqual(core.symbols, {"P1", "P2", "R1", "X1"})
        self.assertEqual(sup.executor.gate.exposures["core"].gross, core.gross)
        self.assertEqual(sup.executor.gate.check("core", planner.RTH, "long", "X1", Decimal("100")), "per_name_repeat")


class ExitOnly(Scenario):
    def open(self, sup):
        with mock.patch.object(ex, "trading_credentials", return_value=("k", "s")), \
             mock.patch.object(ex, "make_trading_client", return_value=object()), \
             mock.patch.object(ex, "AlpacaBroker", return_value=self.b):
            return sup.open_account()

    def test_failed_account_check_with_positions_runs_exit_only(self):
        b = self.b
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        b.all.append({"id": "f1", "client_order_id": "manual-1", "symbol": "ZZZ", "side": "buy", "qty": "1",
                      "filled_qty": "0", "status": "new", "submitted_at": ny(9, 0)})
        sup, clock = make_sup(self.dir, b)
        broker, account, exit_only, mode, verdict = self.open(sup)
        self.assertEqual((exit_only, mode, verdict), (True, "paper", "exit_only:foreign_orders_or_positions"))
        e = ex.Executor(mode, sup.journal, self.dir, broker=broker, gate=ex.RiskGate(sup.limits, sup.account_gross_cap),
                        exit_only=exit_only, clock=sup.clock)
        sup.executor = e
        self.assertIsNone(e.send(planner.entry_intent(FRIDAY, "rth", "NEW", "long", 1, "day", "10.00"),
                                 {"purpose": "entry", "arm": "core", "session_label": "rth", "leg": "long", "ref_price": "10.00"}))
        self.tick(sup, clock, ny(15, 40))
        self.assertIn("nf1-20260925-cls1-AAA-long", self.ids())  # exits stay active
        self.assertEqual(b.find("manual-1")["status"], "new")  # a foreign order is never touched

    def test_failed_account_check_without_positions_falls_back_to_dry_run(self):
        b = self.b
        b.all.append({"id": "f1", "client_order_id": "manual-1", "symbol": "ZZZ", "side": "buy", "qty": "1",
                      "filled_qty": "0", "status": "new", "submitted_at": ny(9, 0)})
        sup, clock = make_sup(self.dir, b)
        self.assertEqual(self.open(sup)[2:], (False, "dry-run", "refused:foreign_orders_or_positions"))
        self.assertIn("paper_refused_no_positions", [r.get("event") for r in self.rows(sup, "risk")])


def bars_for(days, close=50.0):
    return [{"t": common.iso(datetime(d.year, d.month, d.day, tzinfo=NY)), "c": close, "v": 1_000_000, "l": close * 0.99}
            for d in days]


class ArmFlows(Scenario):
    def event(self, sup, sym, created, session, label="FAVORABLE", nid=1):
        ev = {"event_id": f"{nid}:{sym}", "news_id": str(nid), "symbol": sym, "label": label, "lane": "liquid",
              "created_at": common.iso(created), "session": session, "session_label": planner.OPEN_AUCTION,
              "sigma": 0.02, "prior_median_dollar_volume_20": 50_000_000.0, "prior_close": 50.0,
              "entry_utc": common.iso(created + timedelta(minutes=15))}
        sup.bars[(sym, session)] = bars_for(common.load_calendar().prior_sessions(date.fromisoformat(session), 2))
        sup.candidates[ev["event_id"]] = ev
        return ev

    def test_ah_entry_with_corporate_action_guard(self):
        ca = common.load_by_path("adaptive_paper_corporate_actions",
                                 os.path.join(common.REPO, "blueprints/us-equities/adaptive-paper/corporate_actions.py"))
        thursday = date(2026, 9, 24)  # the next session (Friday) is the next day: one night only
        sup, clock = make_sup(self.dir, self.b, day=thursday)
        for i, sym in enumerate(("AAA", "BBB", "CCC")):
            ev = self.event(sup, sym, at(thursday, 16, 5 + i), "2026-09-25", nid=10 + i)
            sup.arm_pending[planner.AH][ev["event_id"]] = ev
        guard = {"AAA": ca.GuardDecision("AAA", False, False, False, None),
                 "BBB": ca.GuardDecision("BBB", True, False, False, "corporate_action_split")}
        clock["now"] = at(thursday, 16, 25)
        with mock.patch.object(sup, "corporate_action_block", return_value=guard):
            sup.run_arm_entries(at(thursday, 16, 25), planner.AH)
        reasons = {d["symbol"]: d["reason"] for d in self.rows(sup, "decision")}
        self.assertEqual(reasons, {"AAA": "ok", "BBB": "corporate_action_split", "CCC": "corporate_action_lookup_failed"})
        self.assertEqual(len(self.b.all), 1)
        sent = self.b.all[0]
        # 25% of min(0.0015 x 900k / 0.02, 0.5% x 50M, 5% x 900k) = 11,250 -> 224 shares at 50.21
        self.assertEqual((sent["client_order_id"], sent["extended_hours"], sent["time_in_force"], sent["limit_price"], sent["qty"]),
                         ("nf1x-ah-20260924-ent-AAA-long", True, "day", "50.21", "224"))

    def test_ah_skips_friday_and_pre_holiday_before_any_lookup(self):
        for n, (day, session) in enumerate(((FRIDAY, "2026-09-28"), (date(2026, 11, 25), "2026-11-27"))):
            sup, clock = make_sup(self.dir, self.b, day=day)
            ev = self.event(sup, f"X{n}", at(day, 16, 5), session, nid=20 + n)
            sup.arm_pending[planner.AH] = {ev["event_id"]: ev}
            clock["now"] = at(day, 16, 25)
            with mock.patch.object(sup, "corporate_action_block") as ca_block:
                sup.run_arm_entries(at(day, 16, 25), planner.AH)
            ca_block.assert_not_called()
            sup.data.snapshots.assert_not_called()
            self.assertEqual(sup.arm_pending[planner.AH], {})
            self.assertEqual([(d["symbol"], d["reason"]) for d in self.rows(sup, "decision")],
                             [(f"X{n}", "ah_next_session_not_next_day")])
        self.assertEqual(self.b.all, [])

    def test_pm_is_gated_and_follows_core_first_event(self):
        sup, clock = make_sup(self.dir, self.b)
        first = self.event(sup, "AAA", ny(6, 0), "2026-09-25", nid=1)
        self.event(sup, "BBB", ny(3, 0), "2026-09-25", nid=2)  # the core's first BBB event is overnight
        second = self.event(sup, "BBB", ny(6, 0), "2026-09-25", nid=3)
        for e in (first, second):
            sup.arm_pending[planner.PM][e["event_id"]] = e
        clock["now"] = ny(6, 16)
        sup.run_arm_entries(ny(6, 16), planner.PM)
        reasons = {d["symbol"]: d["reason"] for d in self.rows(sup, "decision")}
        self.assertEqual(reasons, {"AAA": "ok", "BBB": "pm_event_not_core_first_in_window"})
        self.assertEqual(self.b.all, [])  # pm orders start 2026-09-28: intent journaled, nothing sent
        intents = self.rows(sup, "order_intent")
        self.assertEqual([(r["mode"], r["arm"], r["envelope"]["intent"]["extended_hours"]) for r in intents], [("dry-run", "pm", True)])

    def test_first_order_time_is_enforced(self):
        sup, clock = make_sup(self.dir, self.b)
        sup.executor.not_before = ny(9, 15)
        intent = planner.entry_intent(FRIDAY, "opg", "AAA", "long", 5, "opg")
        ctx = {"purpose": "entry", "session_label": planner.OPEN_AUCTION, "leg": "long", "ref_price": "50"}
        clock["now"] = ny(9, 14)
        self.assertIsNone(sup.send(intent, ctx))
        clock["now"] = ny(9, 15)
        self.assertIsNotNone(sup.send(intent, ctx))
        self.assertEqual(len(self.b.all), 1)

    def test_carry_over_exits_at_the_open_then_falls_back(self):
        b = self.b
        b.add("nf1x-ah-20260924-ent-OLD-long", "buy", 8, 8, at_=at(date(2026, 9, 24), 16, 20))
        b.add("nf1-20260923-opg-STALE-short", "sell", 6, 6, at_=at(date(2026, 9, 23), 9, 20))  # a missed close-out
        sup, clock = make_sup(self.dir, b)
        self.tick(sup, clock, ny(9, 15))
        self.assertEqual([(o["client_order_id"], o["time_in_force"]) for o in b.all[2:]],
                         [("nf1-20260923-xopg1-STALE-short", "opg"), ("nf1x-ah-20260924-xopg1-OLD-long", "opg")])
        OpenBasket.pool(self, sup, [("OLD", "FAVORABLE"), ("NEW", "UNFAVORABLE")])
        sup.run_open_basket(ny(9, 15))
        reasons = {r["symbol"]: r["reason"] for r in self.rows(sup, "decision")}
        self.assertEqual(reasons["OLD"], "symbol_exiting_carry_over_position")
        b.now = ny(9, 30)
        b.find("nf1-20260923-xopg1-STALE-short")["status"] = "expired"  # unfilled in the auction
        b.fill("nf1x-ah-20260924-xopg1-OLD-long")
        n = len(b.all)
        self.tick(sup, clock, ny(9, 31))
        self.assertEqual([(o["client_order_id"], o["side"], o["limit_price"]) for o in b.all[n:]
                          if "-cof" in o["client_order_id"]], [("nf1-20260923-cof1-STALE-short", "buy", "50.31")])


class ReversalFlow(Scenario):
    """The preregistered rth_reversal arm inside the supervisor (paper broker double)."""

    def reversal_sup(self, mode="paper"):
        sup, clock = make_sup(self.dir, self.b, mode=mode)
        sup.reversal = True
        sup.cfg["rth_reversal"] = {"from": "2026-09-25"}
        return sup, clock

    def rth(self, sup, sym, label, created, nid, entry_quote_delay=1):
        c = {"event_id": f"{nid}:{sym}", "news_id": str(nid), "symbol": sym, "label": label, "lane": "liquid",
             "created_at": common.iso(created), "session": "2026-09-25", "window": "rth", "session_label": planner.RTH,
             "entry_utc": common.iso(created + timedelta(minutes=15)), "sigma": 0.02, "exchange": "NYSE",
             "prior_median_dollar_volume_20": 50_000_000.0, "prior_close": 50.0, "label_rule": "exact",
             "strict_label": label, "received_at": common.iso(created + timedelta(seconds=5))}
        sup.bars[(sym, "2026-09-25")] = bars_for(common.load_calendar().prior_sessions(FRIDAY, 2))
        sup.candidates[c["event_id"]] = sup.rth_pending[c["event_id"]] = c
        sup.quotes[sym] = {"bp": 49.95, "ap": 50.05,
                           "t": common.iso(created + timedelta(minutes=15, seconds=entry_quote_delay))}
        return c

    def at_entry(self, sup, clock, created, seconds=2):
        now = created + timedelta(minutes=15, seconds=seconds)
        clock["now"] = self.b.now = now
        return now

    def test_entry_against_the_label_with_the_momentum_shadow(self):
        sup, clock = self.reversal_sup()
        t0 = ny(10, 0)
        for i, (sym, label) in enumerate((("FAV", "FAVORABLE"), ("UNF", "UNFAVORABLE"), ("UNC", "UNCLEAR"))):
            self.rth(sup, sym, label, t0, 11 + i)
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        # leg-balanced: min(section A 45,000, 0.10 E / 12 = 7,500) at the touch: 150 at 49.95, 149 at 50.05
        self.assertEqual({o["client_order_id"]: (o["side"], o["limit_price"], o["qty"]) for o in self.b.all},
                         {"nf1r-20260925-rth-FAV-short": ("sell", "49.95", "150"),
                          "nf1r-20260925-rth-UNF-long": ("buy", "50.05", "149")})
        bench = {r["symbol"]: r for r in self.rows(sup, "benchmark_quote")}
        self.assertEqual(set(bench), {"FAV", "UNF", "UNC"})  # every first-in-window liquid event, whatever its label
        self.assertEqual((bench["UNC"]["label"], bench["UNC"]["quote_ask"]), ("UNCLEAR", "50.05"))
        decisions = self.rows(sup, "decision")
        rev = {d["symbol"]: d for d in decisions if d["arm"] == "rev"}
        shadow = {d["symbol"]: d for d in decisions if d["arm"] == supervisor.SHADOW_ARM}
        self.assertEqual({s: (d["action"], d.get("reason")) for s, d in rev.items()},
                         {"FAV": ("enter", "ok"), "UNF": ("enter", "ok"), "UNC": ("skip", "label_unclear")})
        self.assertEqual({s: (d["action"], d.get("leg")) for s, d in shadow.items()},
                         {"FAV": ("shadow_enter", "long"), "UNF": ("shadow_enter", "short"), "UNC": ("skip", None)})
        self.assertFalse(any("client_order_id" in d for d in shadow.values()))  # a shadow is never an order
        self.assertEqual((rev["FAV"]["quote_bid"], rev["FAV"]["quote_ask"], rev["FAV"]["ssr"]["restricted"]), ("49.95", "50.05", False))
        submitted = {r["order"]["client_order_id"]: r for r in self.rows(sup, "order_submitted")}
        self.assertEqual(submitted["nf1r-20260925-rth-FAV-short"]["arm_label"], "preregistered_forward")
        self.assertEqual(sup.rth_pending, {})

    def test_an_older_quote_waits_inside_the_entry_minute(self):
        sup, clock = self.reversal_sup()
        t0 = ny(10, 0)
        c = self.rth(sup, "OLD", "FAVORABLE", t0, 21, entry_quote_delay=-3)  # stamped 3 s before the entry time
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        self.assertEqual((self.b.all, list(sup.rth_pending)), ([], [c["event_id"]]))
        self.assertEqual([r["reason"] for r in self.rows(sup, "decision_wait")], ["quote_before_entry_time"] * 2)
        sup.quotes["OLD"]["t"] = common.iso(t0 + timedelta(minutes=15, seconds=20))
        sup.run_rth_entries(self.at_entry(sup, clock, t0, seconds=21))
        self.assertEqual([o["client_order_id"] for o in self.b.all], ["nf1r-20260925-rth-OLD-short"])
        self.assertEqual(sup.rth_pending, {})

    def test_unfilled_entry_is_cancelled_after_its_minute(self):
        sup, clock = self.reversal_sup()
        t0 = ny(10, 0)
        self.rth(sup, "UNF", "UNFAVORABLE", t0, 31)
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        entry = self.b.find("nf1r-20260925-rth-UNF-long")
        self.tick(sup, clock, t0 + timedelta(minutes=15, seconds=40))
        self.assertEqual(entry["status"], "accepted")  # 38 s old
        self.tick(sup, clock, t0 + timedelta(minutes=16, seconds=3))
        self.assertEqual(entry["status"], "canceled")  # 61 s after submission

    def test_the_last_entry_minute_is_covered_by_the_close(self):
        sup, clock = self.reversal_sup()
        t0 = ny(15, 29)  # released a minute before the RTH window ends: entry 15:44, after the M2 15:40 stop
        self.rth(sup, "LAT", "UNFAVORABLE", t0, 41)
        self.b.fill_on_submit = lambda intent: "50.05" if intent["client_order_id"].startswith("nf1r-") else None
        now = self.at_entry(sup, clock, t0)
        sup.run_entries(now)
        self.assertEqual([o["client_order_id"] for o in self.b.all], ["nf1r-20260925-rth-LAT-long"])
        self.tick(sup, clock, ny(15, 44) + timedelta(seconds=30))
        cls = [o for o in self.b.all if "-cls" in o["client_order_id"]]
        self.assertEqual([(o["client_order_id"], o["time_in_force"], o["qty"]) for o in cls],
                         [("nf1r-20260925-cls1-LAT-long", "cls", "149")])

    def test_harm_halt_first_in_window_and_the_sweep(self):
        sup, clock = self.reversal_sup()
        Path(self.dir, supervisor.HALT_REVERSAL).write_text("{}")
        t0 = ny(11, 0)
        self.rth(sup, "HLT", "FAVORABLE", t0, 51)
        second = self.rth(sup, "HLT", "UNFAVORABLE", t0 + timedelta(minutes=1), 52)
        sup.quotes["HLT"]["t"] = common.iso(t0 + timedelta(minutes=15, seconds=1))  # one quote stream per symbol
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        self.assertEqual(self.b.all, [])
        rows = {(d["arm"], d["event_id"]): d["reason"] for d in self.rows(sup, "decision")}
        self.assertEqual(rows[("rev", "51:HLT")], "harm_halt")
        self.assertEqual(rows[(supervisor.SHADOW_ARM, "51:HLT")], "ok")  # the shadow is descriptive and keeps running
        sup.run_rth_entries(self.at_entry(sup, clock, t0 + timedelta(minutes=1)))
        self.assertEqual({a: rows_ for a, rows_ in ((d["arm"], d["reason"]) for d in self.rows(sup, "decision")
                                                    if d["event_id"] == second["event_id"])},
                         {"rev": "not_first_in_window", supervisor.SHADOW_ARM: "not_first_in_window"})
        late = self.rth(sup, "SWP", "FAVORABLE", ny(15, 20), 53, entry_quote_delay=-5)
        sup.rth_pending = {late["event_id"]: late}
        sup.sweep_after_cls_start(ny(15, 46) + timedelta(seconds=1))
        self.assertEqual({d["arm"]: d["reason"] for d in self.rows(sup, "decision") if d["event_id"] == late["event_id"]},
                         {"rev": "entry_after_last_entry_minute", supervisor.SHADOW_ARM: "entry_after_last_entry_minute"})

    def test_dry_run_journals_intents_and_sends_nothing(self):
        sup, clock = self.reversal_sup(mode="dry-run")
        t0 = ny(10, 30)
        self.rth(sup, "DRY", "FAVORABLE", t0, 61)
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        intents = self.rows(sup, "order_intent")
        self.assertEqual([(r["mode"], r["arm"], r["envelope"]["intent"]["client_order_id"]) for r in intents],
                         [("dry-run", "rev", "nf1r-20260925-rth-DRY-short")])
        self.assertEqual((self.b.all, self.rows(sup, "order_submitted")), ([], []))

    def test_operative_label_and_read_only_external_scores(self):
        sup, clock = self.reversal_sup(mode="dry-run")
        own = os.path.join(self.dir, "scores.jsonl")
        other_dir = tempfile.mkdtemp(prefix="nf-other-")
        self.addCleanup(shutil.rmtree, other_dir, True)
        external = os.path.join(other_dir, "scores.jsonl")
        with open(own, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_id": "71:AAA", "raw_output": "UNFLEXIBLE", "stop": "eos",
                                     "label": "PARSE_FAIL", "score": 0}) + "\n")
        with open(external, "w", encoding="utf-8") as handle:
            for eid, raw in (("71:AAA", "FAVORABLE"), ("72:BBB", "FAVORABLE is the answer")):
                handle.write(json.dumps({"event_id": eid, "raw_output": raw, "stop": "eos", "label": "FAVORABLE", "score": 1}) + "\n")
        before = os.stat(external)
        sup.scores_path, sup.extra_scores_path = own, external
        for nid, sym in ((71, "AAA"), (72, "BBB")):
            c = self.rth(sup, sym, None, ny(10, 0), nid)
            c.update(ext_segment="closed", arm_release=None)
            del sup.rth_pending[c["event_id"]]
        sup.read_scores(ny(10, 1))
        scores = {r["event_id"]: r for r in self.rows(sup, "score")}
        self.assertEqual((scores["71:AAA"]["label"], scores["71:AAA"]["strict_label"], scores["71:AAA"]["label_rule"],
                          scores["71:AAA"]["score_source"]), ("UNFAVORABLE", "PARSE_FAIL", "prefix", "own"))
        self.assertEqual((scores["72:BBB"]["label"], scores["72:BBB"]["score_source"]), ("FAVORABLE", "external"))
        self.assertEqual(sup.candidates["71:AAA"]["label"], "UNFAVORABLE")
        after = os.stat(external)
        self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))  # never written

    def test_close_marks_rev_daily_and_the_core_execution_test_label(self):
        sup, clock = self.reversal_sup()
        t0 = ny(10, 0)
        self.rth(sup, "FAV", "FAVORABLE", t0, 81)
        self.rth(sup, "UNF", "UNFAVORABLE", t0, 82)
        self.b.fill_on_submit = lambda intent: "50" if intent["client_order_id"].startswith("nf1r-") else None
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        self.tick(sup, clock, ny(15, 40))
        for o in self.b.all:
            if "-cls1-" in o["client_order_id"]:
                self.b.now = ny(16, 0)
                self.b.fill(o["client_order_id"], price="50")
        sup.data.auctions.return_value = {"FAV": {"c": [{"c": "6", "p": 49.5, "x": "N"}]}, "UNF": {"c": []}}
        sup.record_close_marks(ny(16, 5))
        sup.record_close_marks(ny(16, 45))  # the last attempt records a missing print as such
        marks = {r["symbol"]: r for r in self.rows(sup, "close_mark")}
        self.assertEqual((marks["FAV"]["official_close"], marks["FAV"]["condition"]), (49.5, "6"))
        self.assertEqual((marks["UNF"]["official_close"], marks["UNF"]["note"]), (None, "no_close_auction_print"))
        self.b.cash = "900000"
        sup.reconcile()
        daily = self.rows(sup, "rev_daily")[0]
        self.assertEqual((daily["entry_fills"], daily["names_long"], daily["names_short"], daily["flat"]), (2, 1, 1, True))
        self.assertFalse(daily["long_short_defined"])  # one name per leg: no long-short value under the study's rule
        core = common.read_jsonl(os.path.join(self.dir, "autolev-daily-paper.jsonl"))[-1]
        self.assertEqual(core["evidence_label"], "execution_test")
        self.assertEqual(supervisor.autolev.counted([{**core, "core_flat": True}]), [])

    def test_restart_keeps_the_first_receipt_time(self):
        sup, clock = self.reversal_sup()
        sup.journal.write("news", id=91, received_at="2026-09-25T14:00:05Z")
        sup.journal.write("news", id=91, received_at="2026-09-25T15:30:00Z")  # a re-read after a restart
        self.assertEqual(sup.first_received_today(), {"91": "2026-09-25T14:00:05Z"})
        client = mock.Mock()
        client.news_since.return_value = [{"id": 91, "created_at": "2026-09-25T14:00:00Z"}]
        poller = supervisor.live_news.NewsPoller(client, ny(9), clock=lambda: ny(11, 30), first_received=sup.first_received_today())
        self.assertEqual(poller.poll()[0]["received_at"], "2026-09-25T14:00:05Z")

    def test_received_at_is_stamped_on_the_response(self):
        now = {"t": ny(10, 0)}

        def slow_fetch(since):  # the pages take 40 s to arrive
            now["t"] = ny(10, 0) + timedelta(seconds=40)
            return [{"id": 92, "created_at": "2026-09-25T13:59:50Z"}]

        client = mock.Mock()
        client.news_since.side_effect = slow_fetch
        poller = supervisor.live_news.NewsPoller(client, ny(9), clock=lambda: now["t"])
        self.assertEqual(poller.poll()[0]["received_at"], common.iso(ny(10, 0) + timedelta(seconds=40)))

    def test_rev_only_runtime_plans_no_other_arm(self):
        sup, clock = self.reversal_sup()
        sup.cfg["arms_enabled"] = ["rev"]
        base = {"lane": "liquid", "session": "2026-09-25", "sigma": 0.02, "prior_median_dollar_volume_20": 5e7, "prior_close": 50.0,
                "label": None, "exchange": "NYSE", "news_id": "1"}
        cands = {"1:OPG": {**base, "event_id": "1:OPG", "symbol": "OPG", "session_label": planner.OPEN_AUCTION, "window": "overnight",
                           "created_at": common.iso(ny(6, 0)), "received_at": common.iso(ny(6, 0)), "ext_segment": "ext_pre",
                           "arm_release": "pm"},
                 "2:RTH": {**base, "event_id": "2:RTH", "symbol": "RTH", "session_label": planner.RTH, "window": "rth",
                           "created_at": common.iso(ny(10, 0)), "received_at": common.iso(ny(10, 0)), "ext_segment": "closed",
                           "arm_release": None, "entry_utc": common.iso(ny(10, 15))}}
        sup.candidates.update(cands)
        sup.scores_path = os.path.join(self.dir, "no-scores.jsonl")
        for eid in cands:
            sup.scores[eid] = {"event_id": eid, "raw_output": "FAVORABLE", "stop": "eos", "label": "FAVORABLE", "score": 1}
        sup.read_scores(ny(10, 1))
        self.assertEqual((sup.open_pool, sup.arm_pending[planner.PM], list(sup.rth_pending)), ({}, {}, ["2:RTH"]))
        with mock.patch.object(sup, "run_open_basket") as basket:
            sup.run_entries(ny(9, 20))
        basket.assert_not_called()
        self.assertEqual([supervisor.arm_orders_enabled(sup.cfg, a, FRIDAY) for a in ("core", "pm", "ah", "rev")],
                         [False, False, False, True])
        shipped = json.loads((ROOT / "blueprints/us-equities/sota-mover/news-reversal/runtime-config.json").read_text())
        self.assertEqual((shipped["account"], shipped["arms_enabled"], shipped["mode"]), ("paper-4", ["rev"], "paper"))
        self.assertGreaterEqual(shipped["rth_reversal"]["from"], "2026-09-28")

    def test_rev_never_trades_a_symbol_another_arm_holds_or_works(self):
        sup, clock = self.reversal_sup()
        self.b.add("nf1-20260925-opg-XAR-long", "buy", 20, 20)  # a core holding (another arm in the same account)
        self.b.add("nf1x-pm-20260925-ent-WRK-short", "sell", 5, 0, status="accepted", limit="50.00")  # a working pm order
        sup.refresh(ny(10, 0), force=True)
        t0 = ny(10, 0)
        for i, sym in enumerate(("XAR", "WRK", "FREE")):
            self.rth(sup, sym, "UNFAVORABLE", t0, 91 + i)
        sup.run_rth_entries(self.at_entry(sup, clock, t0))
        rev = {d["symbol"]: d for d in self.rows(sup, "decision") if d["arm"] == "rev"}
        self.assertEqual({s: (d["reason"], d.get("held_by")) for s, d in rev.items()},
                         {"XAR": ("symbol_held_by_other_arm", ["core"]), "WRK": ("symbol_held_by_other_arm", ["pm"]),
                          "FREE": ("ok", None)})
        deviations = self.rows(sup, "deviation")
        self.assertEqual(sorted((d["deviation"], d["symbol"]) for d in deviations),
                         [("cross_arm_symbol_skip", "WRK"), ("cross_arm_symbol_skip", "XAR")])
        self.assertEqual([o["client_order_id"] for o in self.b.all if o["client_order_id"].startswith("nf1r-")],
                         ["nf1r-20260925-rth-FREE-long"])
        self.assertEqual(len([d for d in self.rows(sup, "decision") if d["arm"] == supervisor.SHADOW_ARM]), 3)  # descriptive

    def race_at_the_last_entry_second(self, cancel_race):
        sup, clock = self.reversal_sup()
        t0 = ny(15, 29) + timedelta(seconds=59)  # release 15:29:59 -> entry 15:44:59, last decision second 15:45:59
        self.rth(sup, "RCE", "UNFAVORABLE", t0, 97, entry_quote_delay=59)
        now = t0 + timedelta(minutes=16)  # 15:45:59: exactly 60 s after the entry time
        clock["now"] = self.b.now = now
        sup.run_entries(now)
        order = self.b.find("nf1r-20260925-rth-RCE-long")
        self.assertEqual(order["qty"], "149")
        self.b.now = now + timedelta(seconds=1)
        order.update(filled_qty="60", status="partially_filled", filled_avg_price="50.05", filled_at=self.b.now)
        if cancel_race:
            self.b.cancel_race = {order["id"]}  # the cancel is overtaken by the remainder's fill
        self.tick(sup, clock, now + timedelta(seconds=66))  # the 60 s cancel, then the CLS pass in the same step
        cls = [o for o in self.b.all if "-cls" in o["client_order_id"]]
        return order, cls

    def test_partial_fill_at_1545_59_then_cancel_is_covered_by_the_close(self):
        order, cls = self.race_at_the_last_entry_second(cancel_race=False)
        self.assertEqual((order["status"], order["filled_qty"]), ("canceled", "60"))
        self.assertEqual([(o["client_order_id"], o["qty"], o["time_in_force"]) for o in cls], [("nf1r-20260925-cls1-RCE-long", "60", "cls")])

    def test_partial_fill_at_1545_59_whose_remainder_beats_the_cancel_is_covered_in_full(self):
        order, cls = self.race_at_the_last_entry_second(cancel_race=True)
        self.assertEqual((order["status"], order["filled_qty"]), ("filled", "149"))
        self.assertEqual([(o["client_order_id"], o["qty"]) for o in cls], [("nf1r-20260925-cls1-RCE-long", "149")])  # no gap, no oversell

    def test_reconciliation_backfill_guards(self):
        cfg = {"mode": "paper"}
        args = lambda **kw: SimpleNamespace(**{"mode": None, "date": None, "dry_run": False, **kw})  # noqa: E731
        before_close = lambda: at(FRIDAY, 16, 5)  # noqa: E731
        with self.assertRaises(SystemExit):
            supervisor.reconcile_only(args(mode="dry-run", date=FRIDAY), cfg, clock=before_close)
        with self.assertRaises(SystemExit):
            supervisor.reconcile_only(args(), cfg, clock=before_close)  # needs --date
        with self.assertRaises(SystemExit) as ctx:
            supervisor.reconcile_only(args(date=FRIDAY), cfg, clock=before_close)
        self.assertIn("close + 10 min", str(ctx.exception))
        with self.assertRaises(SystemExit):
            supervisor.reconcile_only(args(date=date(2026, 9, 26)), cfg, clock=before_close)  # a Saturday
        with self.assertRaises(SystemExit):
            supervisor.main(["--data-env", "alpaca-paper-3.env"])  # a data override only with --dry-run

    def test_config_switch_and_cli_guards(self):
        cfg = {"rth_reversal": {"from": "2026-09-28"}}
        self.assertFalse(supervisor.reversal_active(cfg, FRIDAY))
        self.assertTrue(supervisor.reversal_active(cfg, date(2026, 9, 28)))
        self.assertFalse(supervisor.reversal_active({"rth_reversal": {"from": "2026-09-28", "enabled": False}}, date(2026, 9, 28)))
        self.assertFalse(supervisor.reversal_active({}, date(2026, 9, 28)))
        self.assertFalse(supervisor.arm_orders_enabled(cfg, "rev", FRIDAY))
        self.assertTrue(supervisor.arm_orders_enabled(cfg, "rev", date(2026, 9, 28)))
        with self.assertRaises(SystemExit):
            supervisor.main(["--scores-from", "/nonexistent/scores.jsonl"])  # only with --dry-run
        with self.assertRaises(SystemExit):
            supervisor.main(["--dry-run", "--state", self.dir, "--scores-from", os.path.join(self.dir, "scores.jsonl")])
        shipped = json.loads((ROOT / "blueprints/us-equities/sota-mover/news-forward/config.json").read_text())
        self.assertEqual(shipped["rth_reversal"]["from"], "2026-09-28")  # never a pilot day


if __name__ == "__main__":
    unittest.main()
