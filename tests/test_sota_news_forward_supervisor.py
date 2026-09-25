"""SYN: news-forward GPU schedule gate and shadow snapshot scheduling (no GPU, no network)."""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
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
    """Paper broker double: positions, open orders, fills and cancels, all in memory."""

    def __init__(self):
        self.pos = {"AAA": "20", "BBB": "-15"}
        self.open = {"o-rth": {"id": "o-rth", "client_order_id": "nf1-20260925-rth-CCC-long", "symbol": "CCC",
                               "submitted_at": ny(15, 20), "status": "new"}}
        self.sent, self.cancelled = [], []
        self.cash = "100000"

    def account(self):
        return {"status": "ACTIVE", "equity": "100000", "cash": self.cash}

    def positions(self):
        return [{"symbol": s, "qty": q, "market_value": "0"} for s, q in self.pos.items()]

    def orders(self, status="open", after=None, symbols=None, limit=500):
        if status == "open":
            return list(self.open.values())
        return [{"client_order_id": "nf1-20260925-opg-AAA-long", "side": "buy", "filled_qty": "20", "filled_avg_price": "10"},
                {"client_order_id": "nf1-20260925-cls-AAA-long", "side": "sell", "filled_qty": "20", "filled_avg_price": "10.5"},
                {"client_order_id": "other-1", "side": "sell", "filled_qty": "5", "filled_avg_price": "1"}]

    def submit(self, intent):
        self.sent.append(intent)
        oid = f"o{len(self.sent)}"
        self.open[oid] = {"id": oid, "client_order_id": intent["client_order_id"], "symbol": intent["symbol"],
                          "submitted_at": ny(15, 40), "status": "accepted"}
        return {"id": oid, "client_order_id": intent["client_order_id"], "status": "accepted"}

    def cancel(self, order_id):
        self.cancelled.append(self.open.pop(order_id)["client_order_id"])


class PaperCloseOut(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="nf-close-")
        self.broker = Broker()
        journal = common.Journal(self.dir, date(2026, 9, 25))
        sup = supervisor.Supervisor.__new__(supervisor.Supervisor)
        sup.mode, sup.schedule, sup.trade_date, sup.journal = "paper", SCHED, date(2026, 9, 25), journal
        sup.executor = supervisor.ex.Executor("paper", journal, self.dir, broker=self.broker)
        sup.done_steps, sup.exit_orders, sup.ext_round, sup.last_ext, sup.last_stale_check = set(), {}, 0, None, None
        sup.counts, sup.sim_positions, sup.sod = supervisor.Counter(), {}, {"cash": "100000", "equity": "100000"}
        sup.data = mock.Mock()
        sup.data.latest_quotes.return_value = {"AAA": {"bp": 10.0, "ap": 10.02}, "BBB": {"bp": 5.0, "ap": 5.02}}
        self.sup = sup

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_sequence(self):
        sup, b = self.sup, self.broker
        sup.run_exits(ny(15, 24))  # the RTH entry is only 4 minutes old
        self.assertEqual(b.cancelled, [])
        sup.run_exits(ny(15, 26))  # stale after 5 minutes
        self.assertEqual(b.cancelled, ["nf1-20260925-rth-CCC-long"])
        sup.run_exits(ny(15, 40))
        self.assertEqual([(i["symbol"], i["side"], i["time_in_force"]) for i in b.sent],
                         [("AAA", "sell", "cls"), ("BBB", "buy", "cls")])
        b.pos["DDD"] = "7"  # an entry filled after the CLS step
        sup.run_exits(ny(15, 55))
        self.assertEqual([(i["symbol"], i["time_in_force"], i["type"]) for i in b.sent[2:]], [("DDD", "day", "market")])
        b.open.clear()
        b.pos = {"BBB": "-15"}  # the CLS buy did not fill
        sup.run_exits(ny(16, 2))
        ext = b.sent[-1]
        self.assertEqual((ext["symbol"], ext["side"], ext["limit_price"], ext["extended_hours"], ext["client_order_id"]),
                         ("BBB", "buy", "5.05", True, "nf1-20260925-ext1-BBB-short"))
        b.pos, b.open, b.cash = {}, {}, "100010"
        rec = sup.reconcile()
        self.assertTrue(rec["ok"], rec)
        self.assertEqual((rec["fills"], rec["realized_pnl"]), (2, "10.0"))
        kinds = [r["kind"] for r in common.read_jsonl(sup.journal.path)]
        self.assertEqual(kinds.count("fill"), 2)
        self.assertEqual(kinds.count("order_submitted"), 4)


if __name__ == "__main__":
    unittest.main()
