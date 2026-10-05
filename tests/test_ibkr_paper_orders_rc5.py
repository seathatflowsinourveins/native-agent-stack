"""Offline local integration checks and synthetic fixtures; never a broker run.

Native configuration/model checks require exactly rc5 and otherwise skip.
Every orchestration test supplies fake checker/process results. No test starts
a LiveNode, official-ibapi reader or gateway connection.
"""
import copy
import contextlib
import importlib.util
import io
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-paper-orders-rc5"
SPEC = importlib.util.spec_from_file_location("ibkr_orders_rc5", DIRECTORY / "run.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
PLAN = RUN.load_plan()
PINNED = {"nautilus_trader": "2.0.0rc5", "ibapi": "10.45.1"}
NY = ZoneInfo("America/New_York")
# Generated synthetic identifier, never an actual account.
FAKE_ACCOUNT = "DU" + "7654321"
FAKE_HOME = "/" + "home/" + "synthetic"
NOW = datetime(2026, 10, 5, 10, tzinfo=NY).astimezone(timezone.utc)
STOP_NS = 2_000_000_000
FLAT = {"client": "ibapi", "client_id": 92, "status": "passed",
        "observed": {"account_count": 1, "paper_accounts": True, "positions": 0, "open_orders": 0}}


def event(kind, order="O1", typ="LIMIT", side="BUY", when=1_000_000_000, **changes):
    value = {"type": kind, "order": order, "order_type": typ, "side": side,
             "quantity": "1", "price": "765.00" if typ == "LIMIT" else None,
             "instrument_id": "SPY=STK.SMART", "ts_event": when, "ts_init": when,
             "at": RUN.frozen().ns_to_iso(when), "reconciliation": False}
    if kind == "OrderFilled":
        value.update(fill_price="770.00" if side == "BUY" else "769.94", fill_quantity="1",
                     commission="1.00", commission_currency="USD", currency="USD")
    value.update(changes)
    return value


def sequence():
    # ExecTester opens the market position before resting the limit: case labels
    # describe obligations rather than implying the frozen strategy's chronology.
    return [event("OrderInitialized", "O2", "MARKET"),
            event("OrderSubmitted", "O2", "MARKET"),
            event("OrderFilled", "O2", "MARKET"),
            event("OrderInitialized"), event("OrderSubmitted"), event("OrderAccepted"),
            event("OrderPendingCancel", when=3_000_000_000), event("OrderCanceled", when=3_000_000_000),
            event("OrderInitialized", "O3", "MARKET", "SELL", 3_000_000_000),
            event("OrderSubmitted", "O3", "MARKET", "SELL", 3_000_000_000),
            event("OrderFilled", "O3", "MARKET", "SELL", 3_000_000_000)]


class PlanValidation(unittest.TestCase):
    def test_frozen_plan(self):
        self.assertEqual(RUN.validate_plan(PLAN), [])
        self.assertEqual(PLAN["bounds"]["max_orders"], 6)
        self.assertEqual(PLAN["timeouts"]["overall_deadline_seconds"], 420)

    def test_bound_mutations(self):
        mutations = [("max_orders", 7), ("max_orders", True), ("max_quantity_per_order", 2),
                     ("max_quantity_per_order", True), ("max_notional_per_order_usd", 1001),
                     ("max_notional_per_order_usd", 0), ("max_notional_per_order_usd", float("nan")),
                     ("max_roundtrip_loss_usd", 5.01), ("max_roundtrip_loss_usd", float("inf"))]
        for name, value in mutations:
            with self.subTest(name=name, value=value):
                plan = copy.deepcopy(PLAN)
                plan["bounds"][name] = value
                self.assertTrue(RUN.validate_plan(plan))

    def test_symbol_host_account_and_strategy_scope(self):
        for section, key, value in [("instrument", "symbol", "AAPL"), ("instrument", "currency", "EUR"),
                                    ("exec_tester", "order_qty", "2"), ("exec_tester", "enable_limit_sells", True),
                                    ("exec_tester", "enable_brackets", True), ("risk", "bypass", True),
                                    ("risk", "require_enforced_notional_before_connection", False),
                                    ("session", "weekdays_only", False), ("session", "close_buffer_minutes", 9)]:
            with self.subTest(section=section, key=key):
                plan = copy.deepcopy(PLAN)
                plan[section][key] = value
                self.assertTrue(RUN.validate_plan(plan))
        for key, value in [("host", "192.0.2.1"), ("account_prefix", "U"), ("require_single_managed_account", False)]:
            plan = copy.deepcopy(PLAN)
            plan[key] = value
            self.assertTrue(RUN.validate_plan(plan))

    def test_ports_and_client_ids(self):
        for port in (4001, 7496, 0, True, 4002.0):
            self.assertTrue(RUN.validate_plan(PLAN, port=port))
        for port in (4002, 7497):
            self.assertEqual(RUN.validate_plan(PLAN, port=port), [])
        for node, check in ((92, 92), (91, 91), (101, 92), (91.0, 92), (91, 92.0)):
            self.assertTrue(RUN.validate_plan(PLAN, node_client_id=node, check_client_id=check))
        plan = copy.deepcopy(PLAN)
        plan["paper_ports"] = [4001]
        self.assertTrue(RUN.validate_plan(plan))

    def test_malformed(self):
        for value in (None, [], {}, {"schema_version": 1}, "not a plan"):
            self.assertTrue(RUN.validate_plan(value))

    def test_duplicate_plan_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"host": "127.0.0.1", "host": "elsewhere"}')
            with self.assertRaises(ValueError):
                RUN.load_plan(path)

    def test_native_argument_types_are_checked_before_connection(self):
        for section, key, value in (("exec_tester", "enable_limit_buys", 1),
                                    ("exec_tester", "order_expire_time_delta_mins", 7.0),
                                    ("timeouts", "node_start_seconds", 60.0)):
            plan = copy.deepcopy(PLAN)
            plan[section][key] = value
            self.assertTrue(RUN.validate_plan(plan))
        plan = copy.deepcopy(PLAN)
        plan["schema_version"] = True
        self.assertTrue(RUN.validate_plan(plan))

    def test_malformed_cli_is_refused_with_exit_three(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as refused:
            RUN.parser().parse_args(["--port", FAKE_ACCOUNT])
        self.assertEqual(refused.exception.code, 3)
        self.assertNotIn(FAKE_ACCOUNT, stderr.getvalue())


class WindowsAndPins(unittest.TestCase):
    def test_whole_run_and_buffer(self):
        for hour, minute, allowed in ((9, 29, False), (9, 30, True), (15, 43, True),
                                      (15, 44, False), (15, 50, False), (16, 0, False)):
            now = NOW.astimezone(NY).replace(hour=hour, minute=minute)
            self.assertEqual(RUN.frozen().rth_check(now, PLAN)[0], allowed)

    def test_weekend_and_early_close(self):
        self.assertFalse(RUN.frozen().rth_check(NOW.replace(day=10), PLAN)[0])
        local = NOW.astimezone(NY)
        sessions = [(local.replace(hour=9, minute=30), local.replace(hour=13, minute=0))]
        self.assertFalse(RUN.frozen().rth_check(local.replace(hour=12, minute=44), PLAN, sessions)[0])
        self.assertFalse(RUN.frozen().rth_check(NOW, PLAN, [])[0])
        self.assertIsNone(RUN.frozen().parse_liquid_hours("malformed", "US/Eastern", local.date()))

    def test_runtime_pins(self):
        self.assertIsNone(RUN.runtime_refusal(PINNED))
        for versions in ({}, {"nautilus_trader": "1.231.0", "ibapi": "10.45.1"},
                         {"nautilus_trader": "2.0.0rc5", "ibapi": "10.44.0"},
                         {"nautilus_trader": "2.0.0rc5", "ibapi": "10.45.1", "nautilus_trader_distribution": "1.231.0"},
                         {"nautilus_trader": "2.0.0rc5.dev1", "ibapi": "10.45.1"}):
            self.assertEqual(RUN.runtime_refusal(versions), "refused_unpinned_runtime")


class EventsAndRoundtrip(unittest.TestCase):
    def test_complete_sequence(self):
        outcomes = RUN.case_outcomes(sequence(), stop_ns=STOP_NS, flat_proof=FLAT)
        self.assertEqual([outcomes[c]["outcome"] for c in RUN.CASE_IDS], ["passed"] * 4)
        self.assertEqual(outcomes["C1"]["order"], outcomes["C2"]["order"])
        self.assertEqual(outcomes["C3"]["order_type"], "MARKET")
        self.assertEqual(outcomes["C1"]["price"], "765.00")
        rt = RUN.roundtrip(sequence(), 5)
        self.assertEqual((rt["gross_usd"], rt["commissions_usd"], rt["net_usd"]), ("-0.06", "2.00", "-2.06"))
        self.assertFalse(rt["loss_bound_breach"])

    def test_independent_flat_proof_required(self):
        for proof in (None, {"status": "passed"}, {"status": "incomplete"},
                      {"status": "passed", "observed": {"positions": 1, "open_orders": 0}}):
            self.assertEqual(RUN.case_outcomes(sequence(), stop_ns=STOP_NS, flat_proof=proof)["C4"]["outcome"], "filled_unproven")

    def test_wrong_cancel_or_before_stop_cannot_pass(self):
        events = sequence()
        events[7]["order"] = "another_order"
        self.assertNotEqual(RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)["C2"]["outcome"], "passed")
        self.assertNotEqual(RUN.case_outcomes(sequence(), stop_ns=4_000_000_000, flat_proof=FLAT)["C2"]["outcome"], "passed")
        self.assertNotEqual(RUN.case_outcomes(sequence(), stop_ns=4_000_000_000, flat_proof=FLAT)["C4"]["outcome"], "passed")

    def test_reconciliation_cannot_supply_venue_acceptance(self):
        events = sequence()
        events[5]["reconciliation"] = True
        outcomes = RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)
        self.assertEqual(outcomes["C1"]["outcome"], "failed")
        self.assertEqual(outcomes["C2"]["outcome"], "failed")

    def test_missing_fill_and_wrong_quantity(self):
        events = [e for e in sequence() if not (e["type"] == "OrderFilled" and e["side"] == "BUY")]
        self.assertEqual(RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)["C3"]["outcome"], "incomplete")
        events = sequence()
        for e in events:
            if e["order"] == "O2":
                e["quantity"] = "2"
        self.assertEqual(RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)["C3"]["outcome"], "failed")

    def test_accidental_resting_fill_fails(self):
        events = sequence() + [event("OrderFilled")]
        self.assertEqual(RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)["C1"]["outcome"], "failed")
        self.assertFalse(RUN.roundtrip(events, 5)["closed"])

    def test_missing_or_zero_commission_and_loss_breach(self):
        for fee in (None, "0.00"):
            events = sequence()
            events[-1]["commission"] = fee
            rt = RUN.roundtrip(events, 5)
            self.assertTrue(rt["commission_unresolved"])
            self.assertIsNone(rt["net_usd"])
        events = sequence()
        events[-1]["fill_price"] = "760.00"
        self.assertTrue(RUN.roundtrip(events, 5)["loss_bound_breach"])

    def test_empty_sequence(self):
        self.assertIsNone(RUN.roundtrip([], 5))
        self.assertEqual([c["outcome"] for c in RUN.case_outcomes([]).values()], ["not_run"] * 4)

    def test_observed_bounds_never_pass_silently(self):
        for field, value in (("quantity", "2"), ("price", "1000.01"), ("instrument_id", "AAPL=STK.SMART")):
            events = sequence()
            for e in events:
                if e["order"] == "O1":
                    e[field] = value
            receipt = RUN.new_receipt(PLAN, DIRECTORY / "plan.json", PINNED)
            RUN.update_observations(receipt, events, PLAN)
            self.assertTrue(receipt["failures"])

    def test_event_seconds_need_not_match_observation_nanoseconds(self):
        events = sequence()
        events[-1]["ts_event"] = 1_000_000_000
        self.assertEqual(RUN.case_outcomes(events, stop_ns=STOP_NS, flat_proof=FLAT)["C4"]["outcome"], "passed")


class SanitizationAndReceipt(unittest.TestCase):
    def test_account_ids_endpoints_paths_and_amounts(self):
        raw = {"error": f"IB-{FAKE_ACCOUNT}: margin [123456.78 USD], Available Funds: 98765.43 at 127.0.0.1:4002 {FAKE_HOME}/private/file.txt",
               "nested": {"I1234567": ["U1234567", "DF1234567", "F1234567", FAKE_ACCOUNT]},
               "fill_price": "770.00", "commission": "1.00"}
        encoded = RUN.serialized_receipt(raw, (FAKE_ACCOUNT,))
        self.assertIsNone(re.search(r"\b(?:D?[UF]|I)\d{5,}\b", encoded))
        for secret in (FAKE_ACCOUNT, "127.0.0.1", FAKE_HOME, "123456.78", "98765.43"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(json.loads(encoded)["fill_price"], "770.00")

    def test_exact_known_secret_removed_without_word_boundaries(self):
        self.assertNotIn(FAKE_ACCOUNT, RUN.serialized_receipt({"error": "prefix" + FAKE_ACCOUNT + "suffix"}, (FAKE_ACCOUNT,)))

    def test_source_urls_survive_but_untrusted_urls_are_scrubbed(self):
        raw = {"source": RUN.RISK_BLOCKER["source"], "error": f"https://github.com/nautechsystems/nautilus_trader/{FAKE_ACCOUNT}/127.0.0.1/file"}
        encoded = RUN.serialized_receipt(raw, (FAKE_ACCOUNT,))
        self.assertEqual(json.loads(encoded)["source"], RUN.RISK_BLOCKER["source"])
        self.assertNotIn("127.0.0.1", encoded)

    def test_shape_and_atomic_replacement(self):
        receipt = RUN.new_receipt(PLAN, DIRECTORY / "plan.json", PINNED)
        for key in ("kind", "evidence_class", "versions", "plan_sha256", "harness_sha256", "source_hashes",
                    "pre_check", "cases", "fills", "roundtrip", "flat_proof", "status", "exit_code", "blocked_steps"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["kind"], RUN.KIND)
        self.assertEqual(receipt["status"], "cleanup_required")
        self.assertEqual(set(receipt["cases"]), {"C1", "C2", "C3", "C4"})
        for key in ("plan_sha256", "harness_sha256"):
            self.assertRegex(receipt[key], r"^[a-f0-9]{64}$")
        issues = {issue["number"]: issue["state"] for step in receipt["blocked_steps"] for issue in step["issues"]}
        self.assertEqual(issues, {5007: "open", 5057: "open", 5060: "open"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            RUN.write_receipt(path, receipt)
            RUN.finish(receipt, "refused_unpinned_runtime", reason="pin")
            RUN.write_receipt(path, receipt)
            self.assertEqual(json.loads(path.read_text())["exit_code"], 3)
            self.assertEqual(list(path.parent.glob(".paper-receipt-*")), [])

    def test_protected_destinations(self):
        for destination in (RUN.PLAN_PATH, DIRECTORY / "run.py", RUN.FROZEN_RUN, RUN.frozen().GATE_RECEIPT):
            with self.assertRaises(ValueError):
                RUN.write_receipt(destination, {})

    def test_exit_codes(self):
        for status, expected in (("passed", 0), ("failed", 1), ("incomplete", 1), ("not_connected", 2),
                                 ("refused_plan", 3), ("cleanup_required", 3)):
            receipt = RUN.new_receipt(PLAN, DIRECTORY / "plan.json", PINNED)
            self.assertEqual(RUN.finish(receipt, status), expected)


class AdmissionRefusals(unittest.TestCase):
    def args(self, path, *extra):
        return RUN.parser().parse_args(["--receipt", str(path), *extra])

    def test_pins_window_ports_and_ids_refuse_without_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            tests = [((), {"nautilus_trader": "1.231.0", "ibapi": "10.45.1"}, NOW, "refused_unpinned_runtime"),
                     ((), PINNED, NOW.replace(hour=1), "refused_outside_window"),
                     (("--port", "4001"), PINNED, NOW, "refused_plan"),
                     (("--node-client-id", "101"), PINNED, NOW, "refused_plan"),
                     (("--check-client-id", "91"), PINNED, NOW, "refused_plan")]
            for extra, versions, now, expected in tests:
                with self.subTest(expected=expected, extra=extra), mock.patch.object(RUN, "official_check") as check, mock.patch.object(RUN, "build_node") as node:
                    receipt = RUN.run_trial(self.args(path, *extra), now=now, versions=versions)
                    self.assertEqual(receipt["status"], expected)
                    self.assertEqual(receipt["exit_code"], 3)
                    check.assert_not_called()
                    node.assert_not_called()

    def test_source_proven_risk_refusal_precedes_all_sockets(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(RUN, "official_check") as check, mock.patch.object(RUN, "build_node") as node, mock.patch.object(RUN.subprocess, "Popen") as process:
            receipt = RUN.run_trial(self.args(Path(directory) / "receipt.json"), now=NOW, versions=PINNED)
            self.assertEqual(receipt["status"], "refused_unenforced_notional")
            self.assertEqual(receipt["risk"]["blocker"]["issue_state"], "closed")
            self.assertFalse(receipt["risk"]["blocker"]["pin_fix_present"])
            self.assertEqual(receipt["failures"][0]["cases_blocked"], list(RUN.CASE_IDS))
            check.assert_not_called()
            node.assert_not_called()
            process.assert_not_called()

    def test_plan_only_has_no_socket_path(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(RUN, "official_check") as check:
            receipt = RUN.run_trial(self.args(Path(directory) / "receipt.json", "--plan-only"), now=NOW, versions=PINNED)
            self.assertEqual(receipt["exit_code"], 3)
            check.assert_not_called()

    def test_invalid_json_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "bad.json"
            plan.write_text("{broken")
            args = self.args(Path(directory) / "receipt.json", "--plan", str(plan))
            receipt = RUN.run_trial(args, now=NOW, versions=PINNED)
            self.assertEqual(receipt["status"], "refused_plan")


class SyntheticOrchestration(unittest.TestCase):
    """Counterfactual cap resolution, injected only in memory in unit tests.

    This is not a runtime override and proves no upstream/broker behavior.
    """
    def drive(self, proof=None, proof_account=FAKE_ACCOUNT, pre_status="passed"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "receipt.json"
        args = RUN.parser().parse_args(["--receipt", str(path)])
        pre = copy.deepcopy(FLAT)
        pre.update(status=pre_status, liquid_hours="20261005:0930-20261005:1600", time_zone_id="US/Eastern")
        proof = copy.deepcopy(FLAT if proof is None else proof)
        test = self

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)

        class Pipe(io.StringIO):
            def close(pipe):
                payload = json.loads(pipe.getvalue())
                test.assertEqual(payload["account_id"], FAKE_ACCOUNT)
                receipt = payload["receipt"]
                receipt["node"].update(started=True, stop_ns=STOP_NS)
                RUN.update_observations(receipt, sequence(), PLAN)
                RUN.write_receipt(path, receipt, (FAKE_ACCOUNT,))
                super().close()

        class Process:
            returncode = None

            def __init__(self, command, **kwargs):
                # The provisional state exists before process construction.
                provisional = json.loads(path.read_text())
                test.assertEqual(provisional["status"], "cleanup_required")
                test.assertNotIn(FAKE_ACCOUNT, path.read_text())
                test.assertNotIn(FAKE_ACCOUNT, str(command))
                test.assertNotIn("env", kwargs)
                self.stdin = Pipe()

            def wait(self, timeout=None):
                self.returncode = 0

            def poll(self):
                return self.returncode

        with mock.patch.object(RUN, "risk_refusal", return_value=None), mock.patch.object(RUN, "datetime", FixedDateTime), mock.patch.object(RUN, "official_check", side_effect=[(pre, FAKE_ACCOUNT), (proof, proof_account)]) as checker, mock.patch.object(RUN.subprocess, "Popen", Process):
            receipt = RUN.run_trial(args, now=NOW, versions=PINNED)
        self.assertNotIn(FAKE_ACCOUNT, path.read_text())
        return receipt, checker

    def test_provisional_receipt_and_final_flat_proof(self):
        receipt, checker = self.drive()
        self.assertEqual(checker.call_count, 2)
        self.assertTrue(checker.call_args_list[0].kwargs["with_session"])
        self.assertFalse(checker.call_args_list[1].kwargs["with_session"])
        self.assertEqual(receipt["status"], "passed")

    def test_unproven_flat_is_cleanup_required(self):
        receipt, _ = self.drive({"status": "refused_existing_state", "observed": {"positions": 1, "open_orders": 0}})
        self.assertEqual((receipt["status"], receipt["exit_code"]), ("cleanup_required", 3))
        self.assertEqual(receipt["failures"][-1]["cases_blocked"], ["C4"])

    def test_changed_account_is_cleanup_required(self):
        receipt, _ = self.drive(proof_account="DU" + "9999999")
        self.assertEqual(receipt["status"], "cleanup_required")

    def test_precheck_refusal_does_not_construct_node(self):
        receipt, checker = self.drive(pre_status="refused_existing_state")
        self.assertEqual(checker.call_count, 1)
        self.assertEqual(receipt["exit_code"], 3)


@unittest.skipUnless(RUN.runtime_versions()["nautilus_trader"] == "2.0.0rc5", "requires installed NautilusTrader 2.0.0rc5; no broker")
class InstalledRc5Surface(unittest.TestCase):
    def test_real_configs_without_node_or_connection(self):
        _, data, execution, risk, tester = RUN.native_configs(PLAN, 4002, FAKE_ACCOUNT)
        self.assertEqual((data.client_id, execution.client_id), (91, 91))
        self.assertEqual(execution.account_id, FAKE_ACCOUNT)
        self.assertFalse(risk.bypass)
        self.assertEqual(risk.max_notional_per_order, {"SPY=STK.SMART": "1000"})
        self.assertEqual(risk.max_order_submit_rate, "6/00:07:00")
        self.assertEqual(str(tester.order_qty), "1")
        self.assertEqual(str(tester.open_position_on_start_qty), "1")
        self.assertTrue(tester.cancel_orders_on_stop and tester.close_positions_on_stop)
        self.assertFalse(tester.enable_limit_sells or tester.enable_stop_buys or tester.enable_stop_sells or tester.enable_brackets)
        self.assertFalse(tester.modify_orders_to_maintain_tob_offset or tester.cancel_replace_orders_to_maintain_tob_offset)

    def test_real_market_order_cache_projection(self):
        from nautilus_trader.core import UUID4
        from nautilus_trader.model import ClientOrderId, InstrumentId, MarketOrder, OrderSide, Quantity, StrategyId, TimeInForce, TraderId
        order = MarketOrder(trader_id=TraderId.from_str("TESTER-001"), strategy_id=StrategyId.from_str("EXEC_TESTER-001"),
                            instrument_id=InstrumentId.from_str("SPY=STK.SMART"), client_order_id=ClientOrderId.from_str("SYNTHETIC-001"),
                            order_side=OrderSide.BUY, quantity=Quantity.from_str("1"), init_id=UUID4(),
                            ts_init=1_000_000_000, time_in_force=TimeInForce.IOC, reduce_only=False, quote_quantity=False)
        projected = RUN.snapshot_events(SimpleNamespace(orders=lambda **kwargs: [order]))
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["type"], "OrderInitialized")
        self.assertIsNone(projected[0]["price"])
        self.assertEqual(projected[0]["order_type"], "MARKET")
        self.assertNotIn("SYNTHETIC-001", json.dumps(projected))


if __name__ == "__main__":
    unittest.main()
