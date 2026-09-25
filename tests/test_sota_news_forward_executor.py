"""SYN: news-forward account binding, order submission path and reconciliation.

Every broker below is a test double; no network and no real credential is read. The
credential files are synthetic, written under a private temporary directory.
"""

import importlib.util
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

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-forward"
sys.path.insert(0, str(BLUEPRINT))

import common  # noqa: E402
import executor as ex  # noqa: E402
import planner  # noqa: E402

HAS_ALPACA = importlib.util.find_spec("alpaca") is not None


def write_env(directory, name, key="PKTESTKEY000001", secret="secretvalue000001", mode=0o600):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="ascii") as handle:
        handle.write(f"APCA_API_KEY_ID={key}\nAPCA_API_SECRET_KEY={secret}\n")
    os.chmod(path, mode)
    return path


class PrivateDir(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp(prefix="nf-test-"))
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class AccountRefusal(PrivateDir):
    def test_missing_file(self):
        with self.assertRaises(ex.AccountRefused) as ctx:
            ex.trading_credentials(os.path.join(self.dir, "alpaca-paper-3.env"), os.path.join(self.dir, "none.env"))
        self.assertEqual(str(ctx.exception), "trading_env_missing")

    def test_paper_2_is_refused_by_name(self):
        path = write_env(self.dir, "alpaca-paper-2.env")
        with self.assertRaises(ex.AccountRefused) as ctx:
            ex.trading_credentials(path, path)
        self.assertEqual(str(ctx.exception), "trading_env_not_paper_3")

    def test_paper_2_key_copied_into_paper_3_is_refused(self):
        data = write_env(self.dir, "alpaca-paper-2.env", key="PKSAMEKEY0001")
        trading = write_env(self.dir, "alpaca-paper-3.env", key="PKSAMEKEY0001", secret="other00000001")
        with self.assertRaises(ex.AccountRefused) as ctx:
            ex.trading_credentials(trading, data)
        self.assertEqual(str(ctx.exception), "trading_key_is_paper_2")

    def test_guard_refuses_loose_mode(self):
        trading = write_env(self.dir, "alpaca-paper-3.env", mode=0o644)
        with self.assertRaises(ex.AccountRefused) as ctx:
            ex.trading_credentials(trading, os.path.join(self.dir, "none.env"))
        self.assertTrue(str(ctx.exception).startswith("trading_env_guard:credential_file_permissions:mode"))

    def test_distinct_paper_3_passes(self):
        data = write_env(self.dir, "alpaca-paper-2.env", key="PKDATAKEY0001")
        trading = write_env(self.dir, "alpaca-paper-3.env", key="PKTRADEKEY001")
        self.assertEqual(ex.trading_credentials(trading, data), ("PKTRADEKEY001", "secretvalue000001"))

    def test_live_host_is_refused(self):
        with self.assertRaises(ex.AccountRefused):
            ex.AlpacaBroker(SimpleNamespace(_base_url="https://api.alpaca.markets"))
        ex.AlpacaBroker(SimpleNamespace(_base_url="https://paper-api.alpaca.markets"))

    def test_paper_mode_needs_a_verified_broker(self):
        with self.assertRaises(ex.AccountRefused):
            ex.Executor("paper", None, self.dir, broker=None)


class FakeBroker:
    def __init__(self, open_orders=(), positions=(), history=(), account=None):
        self._open = list(open_orders)
        self._positions = list(positions)
        self._history = list(history)
        self._account = account or {"status": "ACTIVE", "equity": "100000", "cash": "100000",
                                    "trading_blocked": False, "account_blocked": False}
        self.submitted = []

    def account(self):
        return dict(self._account)

    def positions(self):
        return list(self._positions)

    def orders(self, status="open", after=None, symbols=None, limit=500):
        if status == "open":
            return list(self._open)
        rows = self._history
        if symbols:
            rows = [o for o in rows if o["symbol"] in symbols]
        return list(rows)

    def submit(self, intent):
        self.submitted.append(intent)
        return {"id": f"id-{len(self.submitted)}", "client_order_id": intent["client_order_id"], "status": "accepted",
                "symbol": intent["symbol"]}

    def cancel(self, order_id):
        pass


class StartChecks(unittest.TestCase):
    def test_foreign_position_refused(self):
        broker = FakeBroker(positions=[{"symbol": "ACME", "qty": "5"}],
                            history=[{"symbol": "ACME", "client_order_id": "adaptive-x", "filled_qty": "5"}])
        with self.assertRaises(ex.AccountRefused) as ctx:
            ex.start_check(broker)
        self.assertEqual(str(ctx.exception), "foreign_orders_or_positions")

    def test_foreign_open_order_refused(self):
        broker = FakeBroker(open_orders=[{"symbol": "ACME", "client_order_id": "other-1"}])
        with self.assertRaises(ex.AccountRefused):
            ex.start_check(broker)

    def test_nf1_holdings_accepted(self):
        broker = FakeBroker(open_orders=[{"symbol": "ACME", "client_order_id": "nf1-20260924-cls-ACME-long"}],
                            positions=[{"symbol": "ACME", "qty": "5"}],
                            history=[{"symbol": "ACME", "client_order_id": "nf1-20260924-opg-ACME-long", "filled_qty": "5"}])
        self.assertEqual(ex.start_check(broker)["status"], "ACTIVE")

    def test_blocked_account_refused(self):
        broker = FakeBroker(account={"status": "ACTIVE", "trading_blocked": True})
        with self.assertRaises(ex.AccountRefused):
            ex.start_check(broker)


E = Decimal("900000")
LIMITS = {arm: planner.Limits.for_arm(arm, E, 1) for arm in planner.ARM_PREFIX}


def gate():
    return ex.RiskGate(LIMITS, 4 * E)


def entry_ctx(leg="long", ref="10.00", window=planner.RTH, arm=planner.CORE):
    return {"purpose": "entry", "arm": arm, "session_label": window, "leg": leg, "ref_price": ref}


class Submission(PrivateDir):
    def journal(self):
        return common.Journal(self.dir, date(2026, 9, 25))

    def rows(self, journal):
        return common.read_jsonl(journal.path)

    def test_dry_run_sends_nothing_and_is_idempotent(self):
        j = self.journal()
        e = ex.Executor("dry-run", j, self.dir, gate=gate())
        self.assertIsNone(e.broker)
        intent = planner.entry_intent(date(2026, 9, 25), "opg", "ACME", "long", 20, "opg")
        first = e.send(intent, entry_ctx(ref="50", window=planner.OPEN_AUCTION))
        second = e.send(intent, entry_ctx(ref="50", window=planner.OPEN_AUCTION))
        self.assertIs(first, second)
        self.assertEqual((first["status"], first["simulated"], first["filled_avg_price"]), ("filled", True, "50"))
        kinds = [r["kind"] for r in self.rows(j)]
        self.assertEqual(kinds, ["order_intent"])
        self.assertEqual(self.rows(j)[0]["envelope"]["intent"]["time_in_force"], "opg")

    def test_paper_submission_goes_through_the_contract_and_the_gate(self):
        j = self.journal()
        broker = FakeBroker()
        e = ex.Executor("paper", j, self.dir, broker=broker, gate=gate())
        e.send(planner.entry_intent(date(2026, 9, 25), "rth", "ACME", "long", 19, "day", "100.26"), entry_ctx(ref="100.26"))
        self.assertEqual(broker.submitted[0]["limit_price"], "100.26")
        bad = planner.entry_intent(date(2026, 9, 25), "rth", "BETA", "short", 19, "day", "100.261")
        self.assertIsNone(e.send(bad, entry_ctx("short", ref="100.261")))
        foreign = dict(planner.entry_intent(date(2026, 9, 25), "rth", "BETA", "long", 1, "day", "10.00"), client_order_id="x-1")
        self.assertIsNone(e.send(foreign, entry_ctx()))
        repeat = planner.entry_intent(date(2026, 9, 25), "opg", "ACME", "long", 1, "opg")
        self.assertIsNone(e.send(repeat, entry_ctx(ref="100", window=planner.OPEN_AUCTION)))  # one name per arm and day
        huge = planner.entry_intent(date(2026, 9, 25), "rth", "HUGE", "long", 500, "day", "100.00")
        self.assertIsNone(e.send(huge, entry_ctx(ref="100.00")))  # 50,000 > the 45,000 per-order cap
        no_ref = planner.entry_intent(date(2026, 9, 25), "opg", "NOREF", "long", 5, "opg")
        self.assertIsNone(e.send(no_ref, {"purpose": "entry", "arm": "core", "session_label": planner.OPEN_AUCTION, "leg": "long"}))
        self.assertEqual(len(broker.submitted), 1)
        reasons = [r.get("reason") for r in self.rows(j) if r["kind"] == "order_refused"]
        self.assertTrue(reasons[0].startswith("contract:"))
        self.assertEqual(reasons[1:], ["client_order_id_prefix", "executor_cap:per_name_repeat", "executor_cap:per_order_cap",
                                       "executor_cap:no_gate_or_reference_price"])
        self.assertEqual(e.ref_prices, {"nf1-20260925-rth-ACME-long": "100.26"})

    def test_stop_file_and_kill_switch(self):
        j = self.journal()
        broker = FakeBroker()
        e = ex.Executor("paper", j, self.dir, broker=broker, gate=gate())
        e.killed = True
        entry = planner.entry_intent(date(2026, 9, 25), "rth", "ACME", "long", 1, "day", "10.00")
        self.assertIsNone(e.send(entry, entry_ctx()))
        flat = planner.exit_intent(date(2026, 9, 25), "kill1", "ACME", "1")
        self.assertIsNotNone(e.send(flat, {"purpose": "kill_flatten"}))
        close = planner.exit_intent(date(2026, 9, 25), "cls1", "OTHER", "1")
        self.assertIsNotNone(e.send(close, {"purpose": "exit"}))  # B1: exits are never refused for the kill
        Path(self.dir, "STOP").touch()
        flat2 = planner.exit_intent(date(2026, 9, 25), "kill2", "BETA", "1")
        self.assertIsNone(e.send(flat2, {"purpose": "kill_flatten"}))
        self.assertEqual([i["symbol"] for i in broker.submitted], ["ACME", "OTHER"])

    def test_exit_only_deadline_and_first_order_time(self):
        j = self.journal()
        broker = FakeBroker()
        now = {"t": datetime(2026, 9, 25, 13, 20, tzinfo=timezone.utc)}
        e = ex.Executor("paper", j, self.dir, broker=broker, gate=gate(), exit_only=True, clock=lambda: now["t"],
                        not_before=datetime(2026, 9, 25, 13, 15, tzinfo=timezone.utc))
        self.assertIsNone(e.send(planner.entry_intent(date(2026, 9, 25), "rth", "ACME", "long", 1, "day", "10.00"), entry_ctx()))
        cutoff = datetime(2026, 9, 25, 13, 27, tzinfo=timezone.utc)
        self.assertIsNotNone(e.send(planner.exit_intent(date(2026, 9, 24), "xopg1", "OLD", "5"), {"purpose": "exit"}, deadline=cutoff))
        now["t"] = datetime(2026, 9, 25, 13, 27, 1, tzinfo=timezone.utc)
        self.assertIsNone(e.send(planner.exit_intent(date(2026, 9, 24), "xopg2", "OLD", "5"), {"purpose": "exit"}, deadline=cutoff))
        now["t"] = datetime(2026, 9, 25, 13, 14, tzinfo=timezone.utc)
        self.assertIsNone(e.send(planner.exit_intent(date(2026, 9, 24), "xopg3", "OLD", "5"), {"purpose": "exit"}))
        reasons = [r.get("reason") for r in self.rows(j) if r["kind"] == "order_refused"]
        self.assertEqual(reasons, ["exit_only_mode", "deadline_passed", "before_first_order_time"])

    def test_idempotent_existing_is_journaled_separately(self):
        j = self.journal()
        broker = FakeBroker()
        broker.submit = lambda intent: {"id": "old", "client_order_id": intent["client_order_id"], "status": "filled",
                                        "idempotent_existing": True}
        e = ex.Executor("paper", j, self.dir, broker=broker, gate=gate())
        e.send(planner.exit_intent(date(2026, 9, 25), "cls1", "ACME", "5"), {"purpose": "exit"})
        self.assertEqual([r["kind"] for r in self.rows(j)], ["order_intent", "order_idempotent_existing"])


class Gate(unittest.TestCase):
    def test_every_cap_at_100pct(self):
        g = ex.RiskGate({planner.CORE: planner.Limits(E, Decimal("100000"), Decimal("45000"), Decimal("90000"))}, Decimal("120000"))
        self.assertEqual(g.check("core", "rth", "long", "A", Decimal("45000.01")), "per_order_cap")
        self.assertIsNone(g.check("core", "rth", "long", "A", Decimal("45000")))
        g.commit("core", "rth", "long", "A", Decimal("45000"))
        self.assertEqual(g.check("core", "rth", "short", "A", Decimal("100")), "per_name_repeat")
        g.commit("core", "rth", "long", "B", Decimal("40000"))
        self.assertEqual(g.check("core", "rth", "long", "C", Decimal("10000")), "net_cap")    # 95k long, 0 short
        self.assertEqual(g.check("core", "rth", "short", "C", Decimal("20000")), "gross_cap")  # 105k > 100k
        self.assertIsNone(g.check("core", "rth", "short", "C", Decimal("15000")))
        g.exposures["pm"] = planner.Exposure(gross=Decimal("30000"))
        self.assertEqual(g.check("core", "rth", "short", "C", Decimal("15000")), "account_gross_cap")  # 115k + 15k > 120k
        g.sync({"core": planner.Exposure()})
        self.assertIsNone(g.check("core", "rth", "long", "A", Decimal("45000")))  # synced to the broker's state
        self.assertEqual(g.check("zz", "rth", "long", "A", Decimal("1")), "no_limits_for_arm")


@unittest.skipUnless(HAS_ALPACA, "alpaca-py not installed in this interpreter")
class AlpacaWrapper(unittest.TestCase):
    """AlpacaBroker against a mocked TradingClient (alpaca-py request models are real)."""

    def client(self):
        from alpaca.trading.enums import OrderSide, PositionSide

        calls = []
        positions = [SimpleNamespace(symbol="AAA", qty="20", side=PositionSide.LONG, avg_entry_price="10",
                                     market_value="200", unrealized_pl="0"),
                     SimpleNamespace(symbol="BBB", qty="15", side=PositionSide.SHORT, avg_entry_price="10",
                                     market_value="-150", unrealized_pl="0")]
        closed = [SimpleNamespace(id="1", client_order_id="nf1-20260925-opg-AAA-long", symbol="AAA", side=OrderSide.BUY,
                                  qty="20", filled_qty="20", filled_avg_price="10", status="filled", type="market",
                                  time_in_force="opg", limit_price=None, submitted_at=None, filled_at=None, extended_hours=False),
                  SimpleNamespace(id="2", client_order_id="nf1-20260925-cls-AAA-long", symbol="AAA", side=OrderSide.SELL,
                                  qty="20", filled_qty="20", filled_avg_price="10.5", status="filled", type="market",
                                  time_in_force="cls", limit_price=None, submitted_at=None, filled_at=None, extended_hours=False)]

        class Client:
            _base_url = "https://paper-api.alpaca.markets"

            def get_all_positions(self):
                return positions

            def get_orders(self, filter=None):
                calls.append(("get_orders", filter.status.value))
                return closed if filter.status.value == "closed" else []

            def get_account(self):
                return SimpleNamespace(status="ACTIVE", equity="100010", last_equity="100000", cash="100010",
                                       buying_power="1", multiplier="1", trading_blocked=False, account_blocked=False,
                                       shorting_enabled=True, pattern_day_trader=False)

            def submit_order(self, order_data=None):
                calls.append(("submit", order_data.time_in_force.value, order_data.client_order_id))
                raise RuntimeError("client_order_id must be unique")

            def get_order_by_client_id(self, client_id):
                return closed[1] if client_id == closed[1].client_order_id else (_ for _ in ()).throw(KeyError(client_id))

        return Client(), calls

    def test_positions_signed_and_reconciliation(self):
        client, calls = self.client()
        broker = ex.AlpacaBroker(client)
        self.assertEqual([(p["symbol"], p["qty"]) for p in broker.positions()], [("AAA", "20"), ("BBB", "-15")])
        fills = broker.orders("closed")
        self.assertEqual(fills[0]["side"], "buy")
        rec = planner.reconcile("100000", broker.account()["cash"], fills, [], broker.orders("open"))
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(rec["realized_pnl"], "10.0")
        rec = planner.reconcile("100000", broker.account()["cash"], fills, broker.positions(), [])
        self.assertIn("positions_open", rec["problems"])

    def test_all_orders_paginates_without_gaps(self):
        base = datetime(2026, 9, 25, 13, 0, tzinfo=timezone.utc)
        orders = [SimpleNamespace(id=str(i), client_order_id=f"nf1-20260925-rth-S{i}-long", symbol=f"S{i}", side="buy", qty="1",
                                  filled_qty="0", filled_avg_price=None, status="new", type="limit", time_in_force="day",
                                  limit_price="1", submitted_at=base + timedelta(seconds=i), filled_at=None, extended_hours=False)
                  for i in range(7)]
        calls = []

        class Client:
            _base_url = "https://paper-api.alpaca.markets"

            def get_orders(self, filter=None):
                calls.append((filter.after, filter.direction.value, filter.limit))
                return [o for o in orders if o.submitted_at > filter.after][: filter.limit]

        got = ex.AlpacaBroker(Client()).all_orders(base - timedelta(seconds=1), page=3)
        self.assertEqual([o["id"] for o in got], [str(i) for i in range(7)])
        self.assertEqual(len(calls), 4)
        self.assertEqual({c[1] for c in calls}, {"asc"})

    def test_duplicate_client_id_is_idempotent(self):
        client, calls = self.client()
        broker = ex.AlpacaBroker(client)
        existing = broker.submit(planner.exit_intent(date(2026, 9, 25), "cls", "AAA", "20"))
        self.assertTrue(existing["idempotent_existing"])
        self.assertEqual(calls[-1], ("submit", "cls", "nf1-20260925-cls-AAA-long"))
        with self.assertRaises(RuntimeError):
            broker.submit(planner.exit_intent(date(2026, 9, 25), "cls", "ZZZ", "1"))


class DataClientAllowList(unittest.TestCase):
    def test_only_read_endpoints(self):
        import live_news

        seen = []

        def transport(url, headers, timeout=30):
            seen.append(url)
            return 200, json.dumps({"news": []}).encode(), {}

        client = live_news.DataClient("k", "s", limiter=live_news.RateLimiter(300, sleep=lambda s: None), transport=transport)
        client.news_since(common.utc_now())
        self.assertTrue(seen[0].startswith("https://data.alpaca.markets/v1beta1/news?"))
        for host, path in [(live_news.PAPER_HOST, "/v2/orders"), (live_news.PAPER_HOST, "/v2/positions"),
                           (live_news.PAPER_HOST, "/v2/account"), ("https://api.alpaca.markets", "/v2/assets")]:
            with self.assertRaises(ValueError):
                client.get(host, path)
        client.get(live_news.PAPER_HOST, "/v2/assets/BRK.B")
        with self.assertRaises(ValueError):
            live_news.RateLimiter(301)


if __name__ == "__main__":
    unittest.main()
