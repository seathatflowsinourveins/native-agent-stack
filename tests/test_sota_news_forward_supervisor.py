"""SYN: news-forward GPU schedule gate and shadow snapshot scheduling (no GPU, no network)."""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
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


class Broker:
    """Paper broker double: every order in one list; positions derive from fills."""

    LIVE = ("new", "accepted", "partially_filled")

    def __init__(self):
        self.all = []
        self.cash = "100000"

    def add(self, cid, side, qty, filled, status="filled", at=None, price="10"):
        info = planner.parse_cid(cid)
        order = {"id": f"o{len(self.all)}", "client_order_id": cid, "symbol": info["symbol"], "side": side, "qty": str(qty),
                 "filled_qty": str(filled), "filled_avg_price": price if Decimal(str(filled)) else None,
                 "status": status, "submitted_at": at or ny(9, 20)}
        self.all.append(order)
        return order

    def fill(self, cid, qty=None):
        for o in self.all:
            if o["client_order_id"] == cid:
                o["filled_qty"], o["status"], o["filled_avg_price"] = str(qty or o["qty"]), "filled", "10"

    def account(self):
        return {"status": "ACTIVE", "equity": "100000", "cash": self.cash}

    def positions(self):
        net = {}
        for (arm, day, sym), q in planner.ledger(self.all).items():
            net[sym] = net.get(sym, Decimal("0")) + q
        return [{"symbol": s, "qty": str(q), "market_value": "0"} for s, q in net.items() if q]

    def orders(self, status="open", after=None, symbols=None, limit=500):
        if status == "open":
            return [o for o in self.all if o["status"] in self.LIVE]
        if status == "closed":
            return [o for o in self.all if o["status"] not in self.LIVE]
        return list(self.all)

    def submit(self, intent):
        o = self.add(intent["client_order_id"], intent["side"], intent["qty"], 0, status="accepted", at=ny(15, 40))
        o.update(time_in_force=intent["time_in_force"], type=intent["type"], limit_price=intent.get("limit_price"),
                 extended_hours=intent.get("extended_hours", False))
        return dict(o)

    def cancel(self, order_id):
        for o in self.all:
            if o["id"] == order_id:
                o["status"] = "canceled"


class PaperCloseOut(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="nf-close-")
        b = self.broker = Broker()
        b.add("nf1-20260925-opg-AAA-long", "buy", 20, 20)
        b.add("nf1-20260925-opg-BBB-short", "sell", 15, 15)
        b.add("nf1-20260925-rth-CCC-long", "buy", 9, 0, status="new", at=ny(15, 20))
        b.add("nf1x-pm-20260925-ent-AAA-long", "buy", 5, 5)
        b.add("nf1x-ah-20260924-ent-OLD-long", "buy", 8, 8)
        b.add("nf1x-ah-20260924-opg-OLD-long", "sell", 8, 8)
        journal = common.Journal(self.dir, date(2026, 9, 25))
        sup = supervisor.Supervisor.__new__(supervisor.Supervisor)
        sup.mode, sup.schedule, sup.trade_date, sup.journal, sup.state = "paper", SCHED, date(2026, 9, 25), journal, self.dir
        sup.prev_session = common.load_calendar().previous(date(2026, 9, 25))
        sup.cfg = {"arms": {"pm": {"orders_from": "2026-09-25"}, "ah": {"orders_from": "2026-09-25"}}}
        sup.clock = lambda: ny(16, 30)
        sup.executor = supervisor.ex.Executor("paper", journal, self.dir, broker=b)
        sup.done_steps, sup.ext_round, sup.last_ext, sup.last_stale_check = set(), 0, None, None
        sup.counts, sup.sod = supervisor.Counter(), {"cash": "100000", "equity": "100000"}
        sup.data = mock.Mock()
        sup.data.latest_quotes.return_value = {"AAA": {"bp": 10.0, "ap": 10.02}, "BBB": {"bp": 5.0, "ap": 5.02}}
        self.sup = sup

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def ids(self, since):
        return [o["client_order_id"] for o in self.broker.all[since:]]

    def test_sequence(self):
        sup, b = self.sup, self.broker
        sup.run_exits(ny(15, 24))  # the RTH entry is only 4 minutes old
        self.assertEqual(b.all[2]["status"], "new")
        sup.last_stale_check = None
        sup.run_exits(ny(15, 26))  # stale after 5 minutes
        self.assertEqual(b.all[2]["status"], "canceled")
        n = len(b.all)
        sup.run_exits(ny(15, 40))
        self.assertEqual(self.ids(n), ["nf1-20260925-cls-AAA-long", "nf1-20260925-cls-BBB-short", "nf1x-pm-20260925-cls-AAA-long"])
        self.assertEqual([o["time_in_force"] for o in b.all[n:]], ["cls"] * 3)
        b.add("nf1-20260925-rth-EEE-long", "buy", 7, 7)  # an entry filled after the CLS step
        n = len(b.all)
        sup.run_exits(ny(15, 55))
        self.assertEqual(self.ids(n), ["nf1-20260925-mkt-EEE-long"])
        # at the close: AAA (both arms) and EEE fill; the BBB CLS order is left unfilled
        for cid in ("nf1-20260925-cls-AAA-long", "nf1x-pm-20260925-cls-AAA-long", "nf1-20260925-mkt-EEE-long"):
            b.fill(cid)
        b.add("nf1x-ah-20260925-ent-FFF-long", "buy", 3, 3)  # tonight's overnight hold (ah arm)
        n = len(b.all)
        sup.run_exits(ny(16, 2))
        self.assertEqual(self.ids(n), ["nf1-20260925-ext1-BBB-short"])
        ext = b.all[n]
        self.assertEqual((ext["side"], ext["limit_price"], ext["extended_hours"]), ("buy", "5.05", True))
        self.assertEqual([o["status"] for o in b.all if o["client_order_id"] == "nf1-20260925-cls-BBB-short"], ["canceled"])
        b.fill("nf1-20260925-ext1-BBB-short")
        b.cash = "99970"  # fill cash flows: -200+150-50-80+80-70+200+50+70-30-150 = -30
        rec = sup.reconcile()
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(rec["overnight_holdings"], {"FFF": "3"})
        rows = common.read_jsonl(os.path.join(self.dir, "autolev-daily-paper.jsonl"))
        self.assertEqual((rows[0]["evidence_label"], rows[0]["arm"], rows[0]["core_flat"]), ("pilot", "core", True))


if __name__ == "__main__":
    unittest.main()
