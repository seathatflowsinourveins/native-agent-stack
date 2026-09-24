"""Mover trial mode through the real NautilusTrader LiveNode, controller, ledger and
reconciliation, against a local synthetic port (evidence class SYN). Never a broker,
network or credential; not paper or live acceptance."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
try:
    import nautilus_trader  # noqa: F401
    import alpaca  # noqa: F401
    import mover
    import mover_runner
    import native_adapter
    import safety as safety_module
    from mover_simulation import MoverSimulatedPort, piecewise_path
    from runner import _apply_forced_recovery_outcome
    from safety import Ledger
    from sessions import order_extended_hours_flag
    from transport import normalize_intent
    NATIVE = True
except ImportError:
    NATIVE = False

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


CONFIG = SOURCE / "config-mover.json"
SCAN_TIME = datetime(2026, 9, 24, 12, 0, 5, tzinfo=timezone.utc).timestamp()  # 08:00:05 ET
PRE_TS = datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)                   # 08:30 ET
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def row(symbol, rank, price):
    return {"symbol": symbol, "rank": rank, "price_at_t": price, "dollar_volume_at_t": "50000000",
            "entry_bar_dollar_volume": "2000000"}


def scan_raw(rows):
    return json.dumps({"schema_version": 1, "kind": "mover_scan", "protocol": "mover-early-entry-v1-20260924",
                       "rule": "08:00|G20|V1000000|any", "scan_time": "2026-09-24T12:00:05Z",
                       "regime": {"factor": "1"}, "symbols": rows}).encode()


def flat(price, spread="0.02"):
    return [(0, D(price), D(spread))]


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class MoverNativeEndToEnd(unittest.TestCase):
    def run_trial(self, rows, points, *, exit_rule="X2", hold=1.5, flatten=6.0, window=10.0, entry_timeout=1.0,
                  partial_fill=None, stop_after=None, extended_hours=False, block_sells=False, trial="t1",
                  snapshot_latency=0.0, reconcile_every=None, exit_orders=None):
        """One trial through run_mover. With ``block_sells`` no sell fills during the trial;
        the residual then goes through mover_runner.recover_mover on a fresh port on the
        same synthetic account (sells fill), as command_paper does. ``self.outcome`` keeps
        run_mover's own outcome and ``self.recovery_port`` the recovery port."""
        data = json.loads(CONFIG.read_text())
        data["mover"]["exit"] = exit_rule
        data["mover"]["exit_orders"].update(exit_orders or {})
        self.recovery_port = None
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config.json"
            path.write_text(json.dumps(data))
            config, limits, settings = mover.load_mover_config(path)
            scan = mover.load_scan(scan_raw(rows), settings, now=SCAN_TIME + 20)
            symbols = [r["symbol"] for r in rows]
            cfg = mover.engine_config(config if extended_hours else mover_runner.synthetic_config(config), symbols)
            ledger = Ledger(Path(root) / "ledger.sqlite3", limits)
            try:
                t0 = time.time()
                ledger.begin_next_trial(t0, trial)
                before = ledger.accounting()
                session = mover.plan_session(None, equity=limits.capital_usd, rung_schedule=settings.rung_schedule)
                timing = mover.Timing(t0, t0 + 2.0, entry_timeout, 1.0, t0 + flatten, t0 + window,
                                      t0 + hold if exit_rule == "X1" else None, hold)
                plan = mover.build_plan(settings, limits, scan, session, trial_id=trial, evidence_class="SYN", t0=t0,
                                        equity=limits.capital_usd, timing=timing)
                controller = mover_runner.MoverController(ledger, t0 + 36000, market_open=True)
                port = MoverSimulatedPort(controller, cfg["symbols"], path=piecewise_path(points),
                                          partial_fill=partial_fill, extended_hours_allowed=extended_hours)
                port.fill_sells = not block_sells
                port.snapshot_latency = snapshot_latency
                controller.port = controller.bind(port)
                stop = Path(root) / "STOP"

                async def trigger():
                    await asyncio.sleep(stop_after)
                    stop.write_text("stop\n")

                async def trial_coro():
                    jobs = [mover_runner.run_mover(controller, plan, cfg, format(port.cash, "f"))]
                    if stop_after is not None:
                        jobs.append(trigger())
                    return (await asyncio.gather(*jobs))[0]

                cadence = reconcile_every or mover_runner.RECONCILE_EVERY_SECONDS
                with patch.object(safety_module, "DEFAULT_STOP", stop), \
                     patch.object(mover_runner, "RECONCILE_EVERY_SECONDS", cadence):
                    outcome = asyncio.run(trial_coro())
                    self.outcome = dict(outcome)
                    if block_sells:
                        controller.stop = True
                        controller.port = self.recovery_port = controller.bind(port.successor(fill_sells=True))
                        metadata = {"trial_id": trial, "baseline_cash": "100000"}
                        outcome = _apply_forced_recovery_outcome(outcome, asyncio.run(
                            mover_runner.recover_mover(controller, metadata, cfg)))
                receipt = mover_runner.build_receipt(plan=plan, outcome=outcome, config_sha256="0" * 64, scan=scan,
                                                     ledger=ledger, ledger_before=before,
                                                     prefixes=(f"mvr-{trial}-", f"rec-{trial}-"))
                held = {s: str(p.qty) for s, p in ledger.positions().items()}
                unresolved = len(ledger.unresolved())
            finally:
                ledger.close()
        return receipt, port, held, unresolved

    def legs(self, receipt):
        return {leg["symbol"]: leg for leg in receipt["symbols"]}

    def assert_clean(self, receipt, held, unresolved, status="passed"):
        self.assertEqual(receipt["status"], status, receipt.get("adapter_errors"))
        self.assertTrue(receipt["flat"])
        self.assertEqual((held, unresolved), ({}, 0))
        self.assertEqual(receipt["evidence_class"], "SYN")
        self.assertEqual(receipt["adapter_errors"], [])
        self.assertTrue(receipt["totals"]["pnl_consistent"], receipt["totals"])
        self.assertIsNone(UUID.search(json.dumps(receipt)))

    def buys_per_symbol(self, port):
        counts = {}
        for payload in port.payloads:
            if payload["side"] == "buy":
                counts[payload["symbol"]] = counts.get(payload["symbol"], 0) + 1
        return counts

    def test_x2_exits_with_a_partial_entry_timeout_and_an_unfilled_entry(self):
        rows = [row("AAA", 1, "10.00"), row("BBB", 2, "5.50"), row("CCC", 3, "8.00")]
        points = {"AAA": flat("10.00"), "BBB": flat("5.50"), "CCC": flat("8.00")}
        receipt, port, held, unresolved = self.run_trial(rows, points, partial_fill={"BBB": "0.5", "CCC": "0"})
        self.assert_clean(receipt, held, unresolved)
        legs = self.legs(receipt)
        aaa, bbb, ccc = legs["AAA"], legs["BBB"], legs["CCC"]
        self.assertEqual((aaa["state"], aaa["exit_reason"], aaa["entry"]["status"]), ("closed", "x2_time", "filled"))
        self.assertEqual((aaa["entry"]["qty"], aaa["entry"]["limit_price"]), ("19", "10.06"))   # floor(200 / 10.06)
        self.assertEqual((bbb["state"], bbb["exit_reason"]), ("closed", "x2_time"))
        self.assertEqual((bbb["entry"]["status"], bbb["entry"]["cancel_reason"]), ("canceled", "entry_timeout"))
        self.assertEqual(D(bbb["entry"]["filled_qty"]), (D(bbb["entry"]["qty"]) / 2).to_integral_value(rounding="ROUND_FLOOR"))
        self.assertEqual((ccc["state"], ccc["entry"]["filled_qty"], ccc["exits"]), ("no_fill", "0", []))
        self.assertEqual(self.buys_per_symbol(port), {"AAA": 1, "BBB": 1, "CCC": 1})   # one buy each, never chased
        for leg in (aaa, bbb):
            self.assertIsNotNone(leg["entry"]["accepted_at"])
            self.assertTrue(leg["entry"]["fills"] and leg["exits"][0]["fills"])
            self.assertIsNotNone(leg["realized_pnl_usd"])
        self.assertEqual(receipt["reconciliation"]["end"]["cash_match"], True)
        self.assertEqual(receipt["totals"]["entries_filled"], 2)

    def test_x3_trails_out_at_085_of_the_running_high(self):
        rows = [row("AAA", 1, "10.00")]
        points = {"AAA": [(0, D("10.00"), D("0.02")), (1.0, D("10.00"), D("0.02")), (2.0, D("12.00"), D("0.02")),
                          (3.5, D("9.80"), D("0.02"))]}
        receipt, port, held, unresolved = self.run_trial(rows, points, exit_rule="X3", flatten=8.0, window=12.0)
        self.assert_clean(receipt, held, unresolved)
        leg = self.legs(receipt)["AAA"]
        self.assertEqual(leg["exit_reason"], "x3_trail")
        self.assertGreaterEqual(D(leg["running_high"]), D("11.9"))
        self.assertLessEqual(D(leg["exits"][0]["reference_price"]), D("0.85") * D(leg["running_high"]))

    def test_x4_brackets_target_and_stop_with_chunked_exits(self):
        rows = [row("AAA", 1, "10.00"), row("BBB", 2, "10.00")]
        points = {"AAA": [(0, D("10.00"), D("0.02")), (1.0, D("10.00"), D("0.02")), (2.0, D("15.60"), D("0.02"))],
                  "BBB": [(0, D("10.00"), D("0.02")), (1.0, D("10.00"), D("0.02")), (2.0, D("8.00"), D("0.02"))]}
        receipt, port, held, unresolved = self.run_trial(rows, points, exit_rule="X4", flatten=8.0, window=12.0)
        self.assert_clean(receipt, held, unresolved)
        legs = self.legs(receipt)
        self.assertEqual((legs["AAA"]["exit_reason"], legs["BBB"]["exit_reason"]), ("x4_target", "x4_stop"))
        # 19 shares near 15 USD exceed the 200 USD per-order cap, so the target exit is chunked.
        self.assertGreaterEqual(len(legs["AAA"]["exits"]), 2)
        for leg in legs.values():
            for order in leg["exits"]:
                self.assertLessEqual(D(order["qty"]) * D(order["limit_price"]), D(200))

    def test_hard_flatten_preempts_a_longer_x2_hold(self):
        rows = [row("AAA", 1, "10.00")]
        receipt, port, held, unresolved = self.run_trial(rows, {"AAA": flat("10.00")}, hold=30.0, flatten=3.0,
                                                         window=8.0)
        self.assert_clean(receipt, held, unresolved)
        leg = self.legs(receipt)["AAA"]
        self.assertEqual((leg["exit_reason"], receipt["force_reason"]), ("hard_flatten", "hard_flatten"))

    def test_stop_file_stops_entries_and_flattens(self):
        rows = [row("AAA", 1, "10.00"), row("BBB", 2, "8.00")]
        points = {"AAA": flat("10.00"), "BBB": flat("8.00")}
        receipt, port, held, unresolved = self.run_trial(rows, points, hold=30.0, flatten=20.0, window=25.0,
                                                         entry_timeout=10.0, partial_fill={"BBB": "0"},
                                                         stop_after=1.5)
        self.assert_clean(receipt, held, unresolved, status="passed")
        legs = self.legs(receipt)
        self.assertEqual(receipt["force_reason"], "kill_switch")
        self.assertEqual(legs["AAA"]["exit_reason"], "kill_switch")
        self.assertEqual((legs["BBB"]["state"], legs["BBB"]["entry"]["cancel_reason"]),
                         ("no_fill", "force:kill_switch"))
        self.assertEqual(self.buys_per_symbol(port), {"AAA": 1, "BBB": 1})
        self.assertLess(receipt["native"]["elapsed_seconds"], 15)

    def test_extended_hours_orders_carry_the_flag_and_meet_the_transport_contract(self):
        rows = [row("AAA", 1, "10.00"), row("PNY", 2, "0.8123")]
        points = {"AAA": flat("10.00"), "PNY": flat("0.8123", "0.0010")}
        real = order_extended_hours_flag
        with patch.object(native_adapter, "order_extended_hours_flag", lambda ts, policy: real(PRE_TS, policy)):
            receipt, port, held, unresolved = self.run_trial(rows, points, extended_hours=True)
        self.assert_clean(receipt, held, unresolved)
        self.assertEqual(receipt["native"]["session_policy"]["extended_hours"], True)
        self.assertTrue(port.payloads)
        for payload in port.payloads:
            self.assertEqual((payload["type"], payload["time_in_force"], payload["extended_hours"]), ("limit", "day", True))
            normalize_intent(payload, tuple(port.symbols), allow_extended_hours=True)
        for leg in receipt["symbols"]:
            entry = leg["entry"]
            self.assertEqual(D(entry["limit_price"]), mover.buy_limit_price(
                D(entry["reference_price"]), D(50), leg["sizing"]["price_decimals"]))
            for order in leg["exits"]:
                self.assertEqual(D(order["limit_price"]), mover.sell_limit_price(
                    D(order["reference_price"]), D(50), leg["sizing"]["price_decimals"]))
        self.assertEqual(self.legs(receipt)["PNY"]["entry"]["limit_price"][-5:-4], ".")  # sub-penny 4-decimal limit

    def test_forced_recovery_flattens_when_exits_cannot_complete(self):
        rows = [row("AAA", 1, "10.00")]
        receipt, port, held, unresolved = self.run_trial(rows, {"AAA": flat("10.00")}, hold=1.0, flatten=4.0,
                                                         window=6.0, block_sells=True)
        self.assertEqual(receipt["status"], "needs_attention")        # the failed trial stays failed
        self.assertTrue(receipt["flat"])
        self.assertEqual((held, unresolved), ({}, 0))
        recovery = receipt["reconciliation"]["recovery"]
        self.assertEqual((recovery["status"], recovery["buy_submissions"]), ("passed", 0))
        self.assertTrue(receipt["totals"]["pnl_consistent"])

    def test_forced_recovery_sells_an_appreciated_position_in_whole_shares(self):
        # 19 shares entered near 10; at recovery the bid is 10.60, so the ledger admits at most
        # floor(200 / 10.60) = 18 shares per sell. The notional capacity at the 10.58 limit is
        # 18.90 shares, which reserve_intent would refuse.
        rows = [row("AAA", 1, "10.00")]
        points = {"AAA": [(0, D("10.00"), D("0.02")), (1.0, D("10.00"), D("0.02")), (2.0, D("10.61"), D("0.02"))]}
        receipt, port, held, unresolved = self.run_trial(rows, points, hold=1.0, flatten=4.0, window=6.0,
                                                         block_sells=True)
        self.assertEqual(receipt["status"], "needs_attention")        # the trial's own exits could not fill
        self.assertTrue(receipt["flat"])
        self.assertEqual((held, unresolved), ({}, 0))
        recovery = receipt["reconciliation"]["recovery"]
        self.assertEqual((recovery["status"], recovery["errors"]), ("passed", []))
        sells = [p for p in self.recovery_port.payloads if p["side"] == "sell"]
        self.assertEqual([(p["qty"], p["limit_price"]) for p in sells], [("18", "10.58"), ("1", "10.58")])
        self.assertTrue(receipt["totals"]["pnl_consistent"])

    def test_exhausted_exits_hand_off_to_recovery_soon_after_the_hard_flatten(self):
        # No sell fills, the sell window is 60 s and each leg may send two exits. Without the
        # hand-off the loop idled, position unmanaged, until the sell window ended.
        receipt, port, held, unresolved = self.run_trial(
            [row("AAA", 1, "10.00")], {"AAA": flat("10.00")}, hold=1.0, flatten=3.0, window=60.0,
            block_sells=True, exit_orders={"max_orders_per_symbol": 2})
        handoff = self.outcome["handoff_to_recovery"]
        self.assertIsNotNone(handoff)
        self.assertIn(handoff["reason"], ("exits_blocked", "no_exit_progress"))
        self.assertEqual(handoff["force_reason"], "hard_flatten")
        bound = mover.HANDOFF_EXIT_TIMEOUTS * 1.0                      # this trial's exit timeout is 1 s
        self.assertLessEqual(handoff["seconds_after_force"], bound + 0.5)
        self.assertLess(self.outcome["elapsed_seconds"], 3.0 + bound + 3.0)
        leg = self.legs(receipt)["AAA"]
        self.assertLessEqual(len(leg["exits"]), 4)                     # the budget, then one fresh budget
        self.assertTrue(all(order["status"] == "canceled" for order in leg["exits"]))
        self.assertEqual((receipt["status"], receipt["flat"]), ("needs_attention", True))
        self.assertEqual(receipt["reconciliation"]["recovery"]["status"], "passed")
        self.assertEqual((held, unresolved), ({}, 0))

    def test_a_symbol_scanned_above_one_dollar_stops_out_below_it_with_a_sub_penny_fill(self):
        # Scanned at 1.10, the symbol falls to a sub-penny bid near 0.935, where X4's stop
        # fires. On a 2-decimal instrument the sell either rested above the bid (a limit
        # rounded up to 0.94) or, once marketable, filled at a price the native adapter
        # refuses (cumulative_fill_precision_requires_reconciliation). Every mover
        # instrument is therefore registered at 4 decimals.
        rows = [row("AAA", 1, "1.10")]
        points = {"AAA": [(0, D("1.10"), D("0.01")), (2.0, D("1.10"), D("0.01")), (2.5, D("0.9354"), D("0.001"))]}
        receipt, port, held, unresolved = self.run_trial(rows, points, exit_rule="X4", flatten=8.0, window=12.0)
        self.assert_clean(receipt, held, unresolved)
        leg = self.legs(receipt)["AAA"]
        self.assertEqual((leg["sizing"]["price_decimals"], leg["exit_reason"]), (4, "x4_stop"))
        self.assertEqual(leg["entry"]["limit_price"], "1.10")          # whole cents at or above 1 USD
        self.assertIsNone(receipt["handoff_to_recovery"])
        first = leg["exits"][0]
        self.assertEqual(first["status"], "filled")
        self.assertLess(D(first["reference_price"]), 1)
        self.assertLessEqual(D(first["limit_price"]), D(first["reference_price"]))
        self.assertEqual(D(first["limit_price"]), mover.sell_limit_price(D(first["reference_price"]), D(50), 4))
        self.assertLess(D(first["fills"][0]["price"]), 1)               # a sub-dollar fill, carried natively

    def test_periodic_reconciliation_with_snapshot_latency_while_holding(self):
        # Quote-driven exits are suspended while a snapshot is in flight. Without that, the
        # X3 exit fires inside a 1.5 s snapshot and the reconcile that follows raises
        # submitted_intent_absent (measured 3/3 with suspension disabled; 3/3 clean with it).
        rows = [row("AAA", 1, "10.00")]
        points = {"AAA": [(0, D("10.00"), D("0.02")), (1.0, D("10.00"), D("0.02")), (2.0, D("12.00"), D("0.02")),
                          (3.5, D("9.80"), D("0.02"))]}
        receipt, port, held, unresolved = self.run_trial(rows, points, exit_rule="X3", flatten=8.0, window=12.0,
                                                         snapshot_latency=1.5, reconcile_every=0.25)
        self.assert_clean(receipt, held, unresolved)
        self.assertEqual(self.legs(receipt)["AAA"]["exit_reason"], "x3_trail")
        self.assertGreaterEqual(port.snapshots, 3)   # startup, at least one periodic, final

    def test_a_suspended_strategy_sends_nothing_from_quotes(self):
        from unittest.mock import Mock
        from mover_strategy import MoverStrategy
        book = Mock()
        strategy = MoverStrategy(book, None)
        strategy.started = strategy.suspended = True
        strategy.on_quote(object())
        book.evaluate.assert_not_called()
        self.assertEqual(strategy.received_quotes, 1)

    def test_synthetic_command_writes_a_syn_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            scan_path, out = Path(root) / "scan.json", Path(root) / "receipt.json"
            scan_path.write_bytes(scan_raw([row("AAA", 1, "10.00"), row("BBB", 2, "4.20")]))
            with patch("builtins.print"):
                code = mover_runner.main(["synthetic", "--scan", str(scan_path), "--output", str(out),
                                          "--allow-stale-scan", "--hold-seconds", "2", "--trial", "syn-1"])
            receipt = json.loads(out.read_text())
        self.assertEqual((code, receipt["status"], receipt["evidence_class"], receipt["flat"]), (0, "passed", "SYN", True))
        self.assertEqual(receipt["synthetic"]["scan_age_check"], "skipped")
        self.assertEqual({leg["exit_reason"] for leg in receipt["symbols"]}, {"x2_time"})
        self.assertIsNone(UUID.search(json.dumps(receipt)))


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class MoverPaperCommandWiring(unittest.TestCase):
    """``mover_runner.py paper`` end to end with a fake preflight observation and the
    synthetic port in place of AlpacaPaperTransport: preflight gates, the account lock,
    the mover state directory, session counting, trial.json and the receipt. The
    receipt says PAPER because the command does; this run is a SYN wiring fixture."""

    SERVER = datetime(2026, 9, 24, 12, 0, 30, tzinfo=timezone.utc).timestamp()  # 08:00:30 ET, PRE
    FINGERPRINT = "a" * 64

    def observation(self, symbols):
        """The read-only preflight, reflecting the synthetic account's positions and open orders."""
        server_ns, now_ns = int(self.SERVER * 1e9), time.time_ns()
        cash = format(self.broker.cash, "f") if self.broker is not None else "100000"
        positions = [] if self.broker is None else [
            {"symbol": s, "qty": format(q, "f"), "avg_entry_price": "10"} for s, q in self.broker.positions.items() if q]
        orders = [] if self.broker is None else [
            self.broker._public(o) for o in self.broker.orders.values() if o["status"] in ("new", "partially_filled")]
        return {"account": {"status": "ACTIVE", "currency": "USD", "cash": cash, "equity": cash,
                            "buying_power": cash, "trading_blocked": False, "account_blocked": False,
                            "trade_suspended_by_user": False},
                "account_identity_sha256": self.FINGERPRINT,
                "clock": {"is_open": False, "received_at_ns": server_ns, "timestamp_ns": server_ns,
                          "next_close_ns": server_ns + 8 * 3600 * 10 ** 9, "next_open_ns": server_ns + 5400 * 10 ** 9},
                "positions": positions, "orders": orders, "open_orders_complete": True,
                "assets": [{"symbol": s, "status": "active", "tradable": True} for s in symbols],
                "quotes": [{"symbol": s, "bid": "100", "ask": "100.01", "ts_ns": now_ns} for s in symbols],
                "quote_errors": {}}

    def run_recover(self, root, name="recover", config=None):
        """``mover_runner.py recover`` with the same fakes as ``run_paper``."""
        return self.run_paper(root, None, command="recover", output=name, config=config)

    def run_paper(self, root, trial, *extra, refuse_plan=False, command="paper", output=None, config=None):
        import signal
        import transport
        out = Path(root) / f"{output or trial}.json"
        real_load_scan, real_build_plan, real_flag = mover_runner.load_scan, mover_runner.build_plan, \
            native_adapter.order_extended_hours_flag

        def compressed_plan(settings, limits, scan, session, *, t0, **kwargs):
            if refuse_plan:
                raise mover.MoverRefusal("mover_window_too_short")
            timing = mover.Timing(t0, t0 + 2.0, 1.0, 1.0, t0 + 4.0, t0 + 8.0, None, 1.5)
            return real_build_plan(settings, limits, scan, session, t0=t0, timing=timing, **kwargs)

        def fake_transport(key, secret, symbols, **kwargs):
            # One synthetic "account": orders, positions and cash persist across ports and
            # trials, as the broker's do (the real snapshot pages all orders since the lane began).
            controller = kwargs["before_request"].__self__
            port = MoverSimulatedPort(controller, symbols, path=piecewise_path({s: flat("10.00") for s in symbols}),
                                      extended_hours_allowed=kwargs.get("extended_hours_allowed", False))
            if self.broker is not None:
                port.orders, port.positions, port.cash = self.broker.orders, self.broker.positions, self.broker.cash
            port.fill_sells = self.sell_blocked_ports <= 0     # the next N ports leave every sell resting
            self.sell_blocked_ports -= 1
            self.ports.append(port)
            self.broker = port
            return port

        args = [command, "--env-file", str(Path(root) / "unused.env"), "--output", str(out),
                "--state-root", str(Path(root) / "state")]
        if command == "paper":
            args += ["--scan", str(Path(root) / "scan.json"), "--trial", trial]
        if config is not None:
            args += ["--config", str(config)]
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            with patch.object(mover_runner, "credentials", return_value=("key", "secret")), \
                 patch.object(transport, "preflight", lambda key, secret, symbols, **kw: self.observation(symbols)), \
                 patch.object(transport, "AlpacaPaperTransport", fake_transport), \
                 patch.object(mover_runner, "load_scan",
                              lambda raw, settings, *, now: real_load_scan(raw, settings, now=SCAN_TIME + 20)), \
                 patch.object(mover_runner, "build_plan", compressed_plan), \
                 patch.object(mover_runner, "_controller_session", lambda close, now, policy: (now + 36000, True)), \
                 patch.object(native_adapter, "order_extended_hours_flag", lambda ts, p: real_flag(PRE_TS, p)), \
                 patch("builtins.print"):
                code = mover_runner.main(args + list(extra))
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        return code, json.loads(out.read_text())

    def setUp(self):
        self.broker = None
        self.sell_blocked_ports = 0
        self.ports = []

    def fast_config(self, root):
        """config-mover.json with a 1 s recovery order timeout (the example uses 10 s)."""
        data = json.loads(CONFIG.read_text())
        data["order_timeout_seconds"] = 1
        path = Path(root) / "config-fast.json"
        path.write_text(json.dumps(data))
        return path

    def trial_json(self, root):
        return json.loads((Path(root) / "state" / self.FINGERPRINT / "mover" / "trial.json").read_text())

    def test_paper_command_counts_sessions_persists_state_and_guards_a_shared_account(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "scan.json").write_bytes(scan_raw([row("AAA", 1, "10.00"), row("BBB", 2, "8.00")]))
            state = Path(root) / "state" / self.FINGERPRINT
            code, receipt = self.run_paper(root, "cli-1", refuse_plan=True)   # refused before the trial begins
            self.assertEqual((code, receipt["stage"], receipt["reason"]), (2, "trial_start", "mover_window_too_short"))
            code, receipt = self.run_paper(root, "cli-1")                     # so the trial id was not consumed
            self.assertEqual((code, receipt["status"], receipt["flat"]), (0, "passed", True), receipt.get("reason"))
            self.assertEqual({leg["exit_reason"] for leg in receipt["symbols"]}, {"x2_time"})
            self.assertEqual(receipt["session"]["number"], 1)
            self.assertIsNone(receipt["inter_trial_cash_changed"])            # first trial of the lane
            self.assertEqual(receipt["preflight"]["promotion_gate"], "not_supplied")
            self.assertTrue(receipt["totals"]["pnl_consistent"])
            self.assertNotIn(self.FINGERPRINT, json.dumps(receipt))
            trial = json.loads((state / "mover" / "trial.json").read_text())
            self.assertEqual((trial["phase"], trial["status"], trial["lane_state"]["sessions_started"]),
                             ("finished", "passed", 1))
            self.assertEqual(len(trial["history"]), 1)
            code, receipt = self.run_paper(root, "cli-1")          # a trial id is never reused
            self.assertEqual((code, receipt["status"], receipt["reason"]), (2, "not_started", "trial_id_already_used"))
            code, receipt = self.run_paper(root, "cli-2")
            self.assertEqual((code, receipt["status"], receipt["session"]["number"]), (0, "passed", 2))
            self.assertFalse(receipt["inter_trial_cash_changed"])
            self.broker.cash += D("5.00")    # activity outside the lane between trials is recorded, not refused
            code, receipt = self.run_paper(root, "cli-2b")
            self.assertEqual((code, receipt["status"], receipt["inter_trial_cash_changed"]), (0, "passed", True))
            self.assertEqual(json.loads((state / "mover" / "trial.json").read_text())["inter_trial_cash_change_usd"],
                             "5.00")
            (state / "adaptive").mkdir()
            code, receipt = self.run_paper(root, "cli-3")
            self.assertEqual((code, receipt["reason"]), (2, "account_shared_with_adaptive_lane"))
            code, receipt = self.run_paper(root, "cli-4", "--allow-shared-account")
            self.assertEqual((code, receipt["status"], receipt["shared_account_override"]), (0, "passed", True))
            trial = json.loads((state / "mover" / "trial.json").read_text())
            self.assertEqual([h["session_number"] for h in trial["history"]], [1, 2, 3, 4])

    def test_a_later_session_on_other_symbols_recovers_and_recover_clears_the_lane(self):
        # The mover ledger keeps every session's intents; session 2 trades other symbols than
        # session 1, and its recovery ports subscribe only session 2's symbols (or only SPY).
        with tempfile.TemporaryDirectory() as root:
            config, scan = self.fast_config(root), Path(root) / "scan.json"
            scan.write_bytes(scan_raw([row("AAA", 1, "10.00")]))
            code, first = self.run_paper(root, "lane-1", config=config)
            self.assertEqual((code, first["status"]), (0, "passed"))
            aaa = first["symbols"][0]
            aaa_orders = 1 + len(aaa["exits"]) + len(aaa["recovery_exits"])
            scan.write_bytes(scan_raw([row("BBB", 1, "10.00")]))
            self.sell_blocked_ports = 1                               # session 2's own exits never fill
            code, receipt = self.run_paper(root, "lane-2", config=config)
            recovery = receipt["reconciliation"]["recovery"]
            self.assertEqual((recovery["status"], recovery["flat"], recovery["errors"]), ("passed", True, []))
            self.assertEqual(recovery["adoption_scope"]["skipped_terminal_unsubscribed"], aaa_orders)
            self.assertEqual((code, receipt["status"], receipt["flat"]), (3, "needs_attention", True))
            self.assertEqual(self.trial_json(root)["phase"], "needs_attention")
            code, receipt = self.run_paper(root, "lane-3", config=config)
            self.assertEqual((code, receipt["reason"]), (2, "existing_trial_requires_explicit_recovery"))
            code, result = self.run_recover(root, config=config)
            self.assertEqual((code, result["status"], result["flat"], result["errors"]), (0, "passed", True, []))
            self.assertEqual(result["adoption_scope"]["adopted"], 0)  # flat: the port subscribes SPY only
            self.assertEqual(result["exit_attempt_client_ids"], [])
            self.assertEqual(self.trial_json(root)["phase"], "finished")
            code, receipt = self.run_paper(root, "lane-3", config=config)
            self.assertEqual((code, receipt["status"], receipt["session"]["number"]), (0, "passed", 3))

    def test_recover_flattens_a_residual_that_the_forced_recovery_left(self):
        with tempfile.TemporaryDirectory() as root:
            config, scan = self.fast_config(root), Path(root) / "scan.json"
            scan.write_bytes(scan_raw([row("AAA", 1, "10.00")]))
            self.assertEqual(self.run_paper(root, "lane-1", config=config)[0], 0)
            scan.write_bytes(scan_raw([row("BBB", 1, "10.00")]))
            self.sell_blocked_ports = 2                               # the trial's port and the forced recovery's
            code, receipt = self.run_paper(root, "lane-2", config=config)
            self.assertEqual((code, receipt["status"], receipt["flat"]), (3, "needs_attention", False))
            self.assertEqual(receipt["reconciliation"]["recovery"]["errors"], ["exit_unfilled_no_blind_retry"])
            self.assertGreater(self.broker.positions.get("BBB", D(0)), 0)
            code, receipt = self.run_paper(root, "lane-3", config=config)
            self.assertEqual((code, receipt["stage"], receipt["reason"]),
                             (2, "preflight", "clean_native_start_requires_flat_account"))
            code, result = self.run_recover(root, config=config)
            self.assertEqual((code, result["status"], result["flat"], result["errors"]), (0, "passed", True, []))
            self.assertEqual(result["exit_attempt_client_ids"], ["rec-lane-2-0000002"])
            self.assertFalse(self.broker.positions.get("BBB"))
            self.assertEqual(self.trial_json(root)["phase"], "finished")
            code, receipt = self.run_paper(root, "lane-3", config=config)
            self.assertEqual((code, receipt["status"]), (0, "passed"))


if __name__ == "__main__":
    unittest.main()
