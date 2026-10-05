#!/usr/bin/env python3
"""Bounded rc5 paper trial using upstream's built-in ExecTester.

The rc5 engine cap is configured; quote admission and quantity one hold this
trial's runner bound on the SMART/IB route affected by #4946. --plan-only and
--help never connect. Synthetic tests do not establish broker acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN_PATH = HERE / "plan.json"
FROZEN_RUN = HERE.parent / "ibkr-paper-orders" / "run.py"
KIND = "ibkr_paper_orders_nautilus_2_0_0rc5"
UPSTREAM_COMMIT = "1b0a49d2792a9432a3aca3fcb617ce7a630d905e"
SOURCE = f"https://github.com/nautechsystems/nautilus_trader/blob/{UPSTREAM_COMMIT}"
CASE_IDS = ("C1", "C2", "C3", "C4")
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
TERMINAL_FAILURES = {"OrderDenied", "OrderRejected", "OrderExpired", "OrderCancelRejected"}
# NMS Limit Up-Limit Down Plan, Tier 1 core-session price band. This is a
# single-band admission stress, not a submission-time engine notional cap.
LULD_TIER1_CORE_BAND = Decimal("0.05")
# NMS LULD Plan, Tier 1 last-25-minutes band: do not let the planned
# order/close horizon enter this double-width period with a 5% admission stress.
LULD_TIER1_CLOSING_PERIOD_BAND = Decimal("0.10")
LULD_TIER1_CLOSING_PERIOD_START_ET = (15, 35)
# The frozen USD 1/order allowance needs USD 0.02 for run 3's USD 1.02 sell fee.
COMMISSION_MARGIN_PER_ORDER_USD = Decimal("0.02")
TESTER_SETTINGS = {
    "order_qty": "1", "open_position_on_start_qty": "1", "open_position_on_first_quote": True,
    "open_position_time_in_force": "IOC", "enable_limit_buys": True, "enable_limit_sells": False,
    "enable_stop_buys": False, "enable_stop_sells": False, "enable_brackets": False,
    "tob_offset_ticks": "floor(0.5 * admitted_bid / 0.01)", "limit_time_in_force": "GTD", "order_expire_time_delta_mins": 7,
    "modify_orders_to_maintain_tob_offset": False, "cancel_replace_orders_to_maintain_tob_offset": False,
    "use_post_only": False, "use_individual_cancels_on_stop": True,
    "cancel_orders_on_stop": True, "close_positions_on_stop": True,
    "reduce_only_on_stop": False, "dry_run": False, "log_data": False,
}
CASE_DEFINITIONS = [
    {"id": "C1", "name": "accept_resting", "order_type": "LIMIT", "side": "BUY", "expect": "OrderAccepted"},
    {"id": "C2", "name": "cancel_resting", "order_type": "LIMIT", "side": "BUY", "expect": "OrderCanceled for C1 after stop"},
    {"id": "C3", "name": "fill_buy", "order_type": "MARKET", "side": "BUY", "expect": "OrderFilled quantity 1"},
    {"id": "C4", "name": "flatten", "order_type": "MARKET", "side": "SELL", "expect": "OrderFilled quantity 1 after stop and independent flat proof"},
]

# Original sources, read at v2.0.0rc5 (UPSTREAM_COMMIT):
# examples/live/interactive_brokers/exec_tester.py: builder + ExecTester config.
# examples/live/interactive_brokers/_common.py: bounded node timeouts.
# crates/testkit/src/testers/exec/strategy.rs: native entry/cancel/close paths.
# crates/risk/src/engine/mod.rs: check_orders_risk_for_account returns true
# when account_for_venue(SMART) is absent, before checking max_notional. The
# IB account is registered under IB. Config support is not enforcement.
RISK_NOTE = "engine notional cap configured, not enforced on this route (#4946, fixed on develop, unreleased); bound held by qty=1 and quote admission"
RISK_ROUTE = {
    "issue": "https://github.com/nautechsystems/nautilus_trader/issues/4946",
    "issue_state": "closed",
    "pin_fix_present": False,
    "upstream_fix": "fixed on develop; included in v2.0.0rc6; absent from the selected rc5 pin",
    "source": SOURCE + "/crates/risk/src/engine/mod.rs#L1218",
    "reason": "rc5 stock orders can skip account-scoped max_notional_per_order on the SMART/IB venue path",
}
RELEASE_VERIFICATION = {
    "checked_at": "2026-10-05",
    "fix_commit": "ed6fc8bf47fd37dda97d63b9b2df160719ee2bac",
    "released_in": "v2.0.0rc6",
    "published_at": "2026-10-05T03:03:18Z",
    "source": "https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc6",
    "correction": "The requested note's unreleased clause reflects earlier metadata; the fix is now released in rc6, while this trial stays pinned to rc5.",
}
BLOCKED_STEPS = [
    {"acceptance_step": 3, "operation": "reconnect_with_open_order", "exercised": False,
     "issues": [{"number": 5057, "state": "open"}, {"number": 5060, "state": "open"}]},
    {"acceptance_step": 3, "operation": "restart_reconciliation", "exercised": False,
     "issues": [{"number": 5007, "state": "open"}, {"number": 5057, "state": "open"},
                {"number": 5060, "state": "open"}]},
    {"acceptance_step": 4, "operation": "kill_switch", "exercised": False,
     "issues": [{"number": 5060, "state": "open"}]},
]
for _step in BLOCKED_STEPS:
    _step["issue_states_checked_at"] = "2026-10-05"
    for _issue in _step["issues"]:
        _issue["url"] = f"https://github.com/nautechsystems/nautilus_trader/issues/{_issue['number']}"


@lru_cache(maxsize=1)
def frozen():
    """Reuse the frozen official-ibapi checker, window parser and redaction.

    Source: ../ibkr-paper-orders/run.py, bound by source_hashes in the receipt.
    No frozen strategy is used; the node uses rc5's built-in ExecTester.
    """
    spec = importlib.util.spec_from_file_location("ibkr_frozen_readonly", FROZEN_RUN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def safety():
    spec = importlib.util.spec_from_file_location("ibkr_orders_rc5_safety", HERE / "safety.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite numeric input")
    return result


def load_plan(path=PLAN_PATH):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate plan key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def validate_plan(plan, *, port=None, node_client_id=None, check_client_id=None):
    """All static bounds are checked without importing a client or connecting."""
    errors = []

    def need(condition, reason):
        if not condition:
            errors.append(reason)

    try:
        need(type(plan["schema_version"]) is int and plan["schema_version"] == 1
             and plan["kind"] == "ibkr_paper_orders_plan_rc5", "plan schema")
        need(plan["engine"]["version"] == "2.0.0rc5" and plan["engine"]["ibapi_version"] == "10.45.1", "runtime pins")
        need(plan["engine"]["upstream_commit"] == UPSTREAM_COMMIT, "upstream pin")
        need(plan["host"] == "127.0.0.1", "loopback host required")
        ports = plan["paper_ports"]
        need(isinstance(ports, list) and bool(ports) and all(type(p) is int and p in (4002, 7497) for p in ports), "paper ports")
        need(plan["default_port"] in ports and type(plan["default_port"]) is int, "default paper port")
        need(port is None or type(port) is int and port in ports and port in (4002, 7497), "selected paper port")
        need(plan["account_prefix"] == "DU" and plan["require_single_managed_account"] is True, "single DU account")
        need(plan["client_ids"] == {"node": 91, "check": 92}
             and all(type(v) is int for v in plan["client_ids"].values()), "client ids 91/92")
        need(node_client_id is None or type(node_client_id) is int and node_client_id == 91, "node client id 91")
        need(check_client_id is None or type(check_client_id) is int and check_client_id == 92, "check client id 92")
        inst = plan["instrument"]
        need(tuple(inst[k] for k in ("symbol", "sec_type", "exchange", "primary_exchange", "currency"))
             == ("SPY", "STK", "SMART", "ARCA", "USD"), "SPY STK SMART/ARCA USD only")
        need(inst["nautilus_instrument_id"] == "SPY=STK.SMART" and inst["expected_price_increment"] == "0.01", "RAW stock identity and tick")
        b = plan["bounds"]
        need(type(b["max_orders"]) is int and 3 <= b["max_orders"] <= 6, "order budget 3..6")
        need(type(b["max_quantity_per_order"]) is int and b["max_quantity_per_order"] == 1, "quantity 1")
        for name, ceiling in (("max_notional_per_order_usd", 1000), ("max_roundtrip_loss_usd", 5)):
            need(not isinstance(b[name], bool) and 0 < decimal(b[name]) <= ceiling, name)
        need(decimal(b["commission_allowance_per_order_usd"]) >= 0, "commission allowance")
        s = plan["session"]
        need((s["timezone"], s["open"], s["close"]) == ("America/New_York", "09:30", "16:00"), "regular trading hours")
        need(s["weekdays_only"] is True and s["whole_run_inside_window"] is True
             and s["use_contract_liquid_hours"] is True, "whole run with broker liquid hours")
        need(type(s["close_buffer_minutes"]) is int and s["close_buffer_minutes"] >= 10, "10 minute close buffer")
        expected_times = {"check_seconds": 30, "node_start_seconds": 60, "per_step_seconds": 45,
                          "cleanup_seconds": 45, "node_stop_allowance_seconds": 15,
                          "post_check_reserve_seconds": 60, "overall_deadline_seconds": 420}
        need(plan["timeouts"] == expected_times and all(type(v) is int for v in plan["timeouts"].values()),
             "frozen timeouts and hard deadline")
        r = plan["risk"]
        need(r["bypass"] is False and r["require_enforced_notional_before_connection"] is False,
             "native risk configured with runner quote admission")
        need(not isinstance(r["notional_headroom_usd"], bool)
             and decimal(r["notional_headroom_usd"]) == 10, "USD 10 quote admission headroom")
        need(r["max_order_submit_rate"] == f"{b['max_orders']}/00:07:00", "whole-run native submit throttle")
        # No configurable strategy knobs can quietly turn this into another trial.
        need(plan["exec_tester"] == TESTER_SETTINGS
             and all(type(plan["exec_tester"][k]) is type(v) for k, v in TESTER_SETTINGS.items()),
             "frozen ExecTester settings")
        need(plan["data"] == {"market_data_type": "REALTIME", "quote_max_age_seconds": 10,
                              "clock_resolution_tolerance_seconds": 2, "batch_quotes": False}, "real-time quote bounds")
        need(plan["cases"] == CASE_DEFINITIONS, "frozen cases C1..C4")
        need(plan["end_disposition"] == {"positions": 0, "open_orders": 0}, "flat disposition")
        need(plan["receipt"]["kind"] == KIND and plan["evidence_class"] == "native_paper", "receipt identity")
    except (KeyError, TypeError, ValueError, InvalidOperation):
        errors.append("missing or malformed plan field")
    return errors


def runtime_versions():
    def version(package):
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None
    try:
        import ibapi
        ib_version = ibapi.__version__
    except (ImportError, AttributeError):
        ib_version = None
    try:
        import nautilus_trader
        engine_version = nautilus_trader.__version__
    except (ImportError, AttributeError):
        engine_version = None
    return {"nautilus_trader": engine_version, "nautilus_trader_distribution": version("nautilus_trader"), "ibapi": ib_version,
            "nautilus_ibapi_distribution": version("nautilus-ibapi"),
            "protobuf": version("protobuf"), "python": platform.python_version()}


def runtime_refusal(versions):
    if versions.get("nautilus_trader") != "2.0.0rc5" or versions.get("ibapi") != "10.45.1":
        return "refused_unpinned_runtime"
    if "nautilus_trader_distribution" in versions and versions["nautilus_trader_distribution"] != "2.0.0rc5":
        return "refused_unpinned_runtime"
    return None


def resting_offset_ticks(bid, plan):
    """Frozen half-bid placement through upstream ExecTester's supported offset."""
    tick = decimal(plan["instrument"]["expected_price_increment"])
    return int((decimal(bid) * Decimal("0.5") / tick).to_integral_value(rounding=ROUND_FLOOR))


def closing_period_admission(plan, start):
    """Refuse closing-band overlap before any official-client request.

    node_stop_at reserves proof, cleanup and stop allowance from the overall
    deadline; adding the close horizon restores cleanup and stop allowance.
    Source: the NMS LULD Plan's Tier 1 last-25-minutes double-width band.
    """
    times = plan["timeouts"]
    node_stop_seconds = (times["overall_deadline_seconds"] - times["post_check_reserve_seconds"]
                         - times["cleanup_seconds"] - times["node_stop_allowance_seconds"])
    close_horizon = times["cleanup_seconds"] + times["node_stop_allowance_seconds"]
    horizon = node_stop_seconds + close_horizon
    start_et = start.astimezone(frozen().ZoneInfo("America/New_York"))
    end_et = start_et + timedelta(seconds=horizon)
    closing_start = start_et.replace(hour=LULD_TIER1_CLOSING_PERIOD_START_ET[0],
                                    minute=LULD_TIER1_CLOSING_PERIOD_START_ET[1], second=0, microsecond=0)
    result = {"status": "passed", "stage": "luld_tier1_closing_period_band",
              "order_horizon_seconds": horizon, "closing_band_fraction": str(LULD_TIER1_CLOSING_PERIOD_BAND),
              "planned_order_window_end": end_et.isoformat()}
    if end_et >= closing_start:
        result.update(status="refused_luld_closing_period", reason="planned_order_window_overlaps_15_35_et")
    return result


def admit_quote(plan, quote, server_time_epoch, *, elapsed_seconds=0, delayed=False, errors=()):
    """Pure admission using IB's timestamped BidAsk and its independent clock."""
    result = {"source": "ibapi.reqTickByTickData.BidAsk/reqCurrentTime", "status": None,
              "bid": None, "ask": None, "quote_age_seconds": None}
    if delayed or any(code in (10089, 10167) for code in errors):
        result["status"] = "refused_delayed_quote"
        return result
    if errors:
        result["status"] = "refused_quote_error"
        return result
    try:
        bid, ask = decimal(quote["bid"]), decimal(quote["ask"])
        age = decimal(server_time_epoch) - decimal(quote["quote_time_epoch"]) + decimal(elapsed_seconds)
        result.update(bid=str(bid), ask=str(ask), quote_time_epoch=int(quote["quote_time_epoch"]),
                      server_time_epoch=int(server_time_epoch), quote_age_seconds=float(max(age, Decimal(0))))
        if bid <= 0 or ask < bid:
            result["status"] = "refused_invalid_quote"
        elif age < -decimal(plan["data"]["clock_resolution_tolerance_seconds"]) or age > decimal(plan["data"]["quote_max_age_seconds"]):
            result["status"] = "refused_stale_quote"
        else:
            notional = ask * plan["bounds"]["max_quantity_per_order"]
            headroom = decimal(plan["risk"]["notional_headroom_usd"])
            band_notional = notional * (1 + LULD_TIER1_CORE_BAND)
            result.update(ask_notional_usd=str(notional), headroom_usd=str(headroom),
                          luld_core_band_fraction=str(LULD_TIER1_CORE_BAND), band_adjusted_notional_usd=str(band_notional),
                          tob_offset_ticks=resting_offset_ticks(bid, plan))
            spread_loss = (ask - bid) * plan["bounds"]["max_quantity_per_order"]
            commissions = 2 * (decimal(plan["bounds"]["commission_allowance_per_order_usd"]) + COMMISSION_MARGIN_PER_ORDER_USD)
            loss_bound = decimal(plan["bounds"]["max_roundtrip_loss_usd"])
            result.update(spread_loss_usd=str(spread_loss), expected_roundtrip_commissions_usd=str(commissions),
                          commission_margin_per_order_usd=str(COMMISSION_MARGIN_PER_ORDER_USD),
                          expected_roundtrip_loss_usd=str(spread_loss + commissions), max_roundtrip_loss_usd=str(loss_bound))
            if spread_loss + commissions > loss_bound:
                result.update(status="refused_quote_loss_bound", stage="spread_and_commissions")
            elif band_notional + headroom > decimal(plan["bounds"]["max_notional_per_order_usd"]) or result["tob_offset_ticks"] <= 0:
                result.update(status="refused_quote_notional", stage="notional")
            else:
                result.update(status="passed", stage="admitted")
    except (KeyError, TypeError, ValueError, InvalidOperation):
        result["status"] = "refused_invalid_quote"
    return result


# Official ibapi 10.45.1 client.py reqTickByTickData and wrapper.py callbacks
# were inspected in the prepared runtime. Delayed enums come from ticktype.py.
DELAYED_TICKS = set(range(66, 77)) | {80, 81, 82, 83, 88, 90, 103, 104}
CONNECTIVITY_CODES = {326, 502, 503, 504, 507, 1100, 1300, 2110}


class QuoteState:
    """Read-only callback state, kept independent of ibapi for synthetic tests."""

    def __init__(self):
        self.ready = threading.Event()
        self.quote_ready = threading.Event()
        self.clock_ready = threading.Event()
        self.accounts_ready = threading.Event()
        self.accounts = []  # Memory only.
        self.quote = None
        self.server_time = None
        self.clock_received = None
        self.delayed = False
        self.errors = []
        self.info = []
        self.started_monotonic = time.monotonic()
        self.last_stage = "initializing"
        self.stage_elapsed_seconds = {}
        self.stage_duration_seconds = {}
        self.stage_started = self.started_monotonic
        self.quote_phase = False

    def mark(self, stage):
        if stage not in self.stage_elapsed_seconds:
            now = time.monotonic()
            self.stage_elapsed_seconds[stage] = round(now - self.started_monotonic, 4)
            self.stage_duration_seconds[stage] = round(now - self.stage_started, 4)
            self.stage_started, self.last_stage = now, stage

    def diagnostics(self):
        return {"last_stage": self.last_stage, "elapsed_seconds": round(time.monotonic() - self.started_monotonic, 4),
                "last_stage_elapsed_seconds": round(time.monotonic() - self.stage_started, 4),
                "stage_elapsed_seconds": dict(self.stage_elapsed_seconds),
                "stage_duration_seconds": dict(self.stage_duration_seconds),
                "errors": list(self.errors), "info": list(self.info)}

    def nextValidId(self, orderId):
        self.mark("nextValidId")
        self.ready.set()

    def managedAccounts(self, accountsList):
        self.accounts = [value.strip() for value in (accountsList or "").split(",") if value.strip()]
        self.mark("accounts")
        self.accounts_ready.set()

    def tickByTickBidAsk(self, reqId, timestamp, bidPrice, askPrice, bidSize, askSize, tickAttribBidAsk):
        if reqId == 9202:
            self.quote = {"bid": str(bidPrice), "ask": str(askPrice), "quote_time_epoch": timestamp}
            self.mark("quote")
            self.quote_ready.set()

    def currentTime(self, timestamp):
        self.server_time, self.clock_received = timestamp, time.monotonic()
        if self.quote_phase:
            self.mark("clock")
        self.clock_ready.set()

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in (10089, 10167):
            self.delayed = True
        entry = {"reqId": reqId, "code": errorCode,
                 "text": frozen().scrub_serialized(frozen().redact(errorString)[:160], self.accounts)}
        fatal = reqId == 9202 or errorCode in CONNECTIVITY_CODES or errorCode in (10089, 10167)
        (self.errors if fatal else self.info).append(entry)
        if fatal:
            self.quote_ready.set()
            self.clock_ready.set()
            if errorCode in CONNECTIVITY_CODES:
                self.ready.set()
                self.accounts_ready.set()

    def marketDataType(self, reqId, marketDataType):
        if marketDataType in (3, 4):
            self.delayed = True
            self.quote_ready.set()

    def delayed_tick(self, tickType):
        if tickType in DELAYED_TICKS:
            self.delayed = True
            self.quote_ready.set()

    def tickPrice(self, reqId, tickType, price, attrib):
        self.delayed_tick(tickType)

    def tickSize(self, reqId, tickType, size):
        self.delayed_tick(tickType)

    def tickString(self, reqId, tickType, value):
        self.delayed_tick(tickType)

    def tickGeneric(self, reqId, tickType, value):
        self.delayed_tick(tickType)

    def tickOptionComputation(self, reqId, tickType, *values):
        self.delayed_tick(tickType)


class AdmissionState(frozen().CheckState, QuoteState):
    """Reuse frozen flat-check callbacks and quote callbacks on one session."""

    def __init__(self):
        frozen().CheckState.__init__(self)
        QuoteState.__init__(self)

    def managedAccounts(self, accountsList):
        frozen().CheckState.managedAccounts(self, accountsList)
        QuoteState.managedAccounts(self, accountsList)

    def currentTime(self, timestamp):
        frozen().CheckState.currentTime(self, timestamp)
        QuoteState.currentTime(self, timestamp)

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        frozen().CheckState.error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)
        QuoteState.error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)


def build_admission_client():
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class QuoteClient(AdmissionState, EWrapper, EClient):
        def __init__(self):
            AdmissionState.__init__(self)
            EClient.__init__(self, self)

    return QuoteClient()


class CheckSession:
    """Hold the frozen check's session until quote admission and join its reader.

    Official ibapi 10.45.1 client.py: connect creates EReader and startApi;
    run drains the shared message queue; disconnect closes/reset but does not
    join those threads. Intercept only the frozen harness's final disconnect,
    leaving EClient's own disconnect on connection loss unchanged.
    """

    def __init__(self, client):
        self.client, self.runner = client, None

    def __getattr__(self, name):
        return getattr(self.client, name)

    def connect(self, host, port, client_id):
        self.client.connect(host, port, client_id)
        if self.client.isConnected():
            self.client.mark("connected")

    def run(self):
        self.runner = threading.current_thread()
        self.client.run()

    def disconnect(self):
        pass  # The outer admission scope owns teardown after both read phases.

    def close(self, deadline):
        reader = getattr(self.client, "reader", None)
        try:
            self.client.disconnect()
        finally:
            for thread in (self.runner, reader):
                if thread is not None and thread is not threading.current_thread():
                    thread.join(timeout=max(0, deadline - time.monotonic()))


def quote_check(plan, account_id, *, deadline, client):
    """Continue the already-connected flat-check client; never reconnect."""
    requested = False

    def wait(event):
        while not event.is_set() and time.monotonic() < deadline:
            if client.errors or not client.isConnected():
                return False
            event.wait(min(0.05, max(0, deadline - time.monotonic())))
        return event.is_set()

    def result(value):
        return {**value, **client.diagnostics()}

    def failed_wait(status):
        if client.errors or client.delayed:
            return result(admit_quote(plan, client.quote, client.server_time,
                                      delayed=client.delayed, errors=[entry["code"] for entry in client.errors]))
        return result({"status": status, "error": "quote_check_deadline" if time.monotonic() >= deadline else "connection_lost"})

    try:
        if not client.isConnected():
            return result({"status": "not_connected"})
        if not wait(client.ready) or not wait(client.accounts_ready):
            return failed_wait("not_connected")
        if client.errors:
            return failed_wait("not_connected")
        if client.accounts != [account_id] or not account_id.startswith("DU"):
            return result({"status": "refused_quote_account_scope"})
        client.quote_phase = True
        client.reqMarketDataType(1)
        requested = True
        client.mark("tick requested")
        client.reqTickByTickData(9202, frozen().spy_contract(), "BidAsk", 0, False)
        if not wait(client.quote_ready):
            return failed_wait("refused_quote_unavailable")
        if client.delayed or client.errors:
            return failed_wait("refused_quote_error")
        client.clock_ready.clear()  # Discard the clock from the flat pre-check.
        client.server_time, client.clock_received = None, None
        client.reqCurrentTime()
        if not wait(client.clock_ready):
            return failed_wait("refused_quote_clock")
        elapsed = max(0, time.monotonic() - client.clock_received) if client.clock_received is not None else 0
        admitted = admit_quote(plan, client.quote, client.server_time, elapsed_seconds=elapsed,
                              delayed=client.delayed, errors=[entry["code"] for entry in client.errors])
        admitted["admitted_monotonic"] = time.monotonic()
        return result(admitted)
    finally:
        if requested:
            client.cancelTickByTickData(9202)


def validate_child_admission(plan, payload, *, monotonic_now=None):
    """Recompute age, cap and offset from the pipe; no account in diagnostics."""
    try:
        admitted = payload["quote_admission"]
        now = time.monotonic() if monotonic_now is None else monotonic_now
        elapsed = decimal(now) - decimal(admitted["admitted_monotonic"])
        if admitted["status"] != "passed" or elapsed < 0:
            return False
        # Stored age already includes time since the independent server callback.
        rechecked = admit_quote(plan, admitted, decimal(admitted["quote_time_epoch"]) + decimal(admitted["quote_age_seconds"]),
                                elapsed_seconds=elapsed)
        offset = payload["tob_offset_ticks"]
        return (rechecked["status"] == "passed" and type(offset) is int
                and offset == resting_offset_ticks(admitted["bid"], plan)
                and offset == admitted["tob_offset_ticks"]
                and isinstance(payload["account_id"], str) and payload["account_id"].startswith("DU"))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False


def sanitize(value):
    """Prices/quantities remain structured; all untrusted text uses frozen redaction."""
    if isinstance(value, dict):
        return {frozen().redact(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        # Constant source locators are public evidence, not untrusted error text.
        public_sources = {RISK_ROUTE["source"], RISK_ROUTE["issue"], RELEASE_VERIFICATION["source"]}
        public_sources.update(issue["url"] for step in BLOCKED_STEPS for issue in step["issues"])
        if value in public_sources:
            return frozen().scrub_serialized(value)
        return frozen().redact(value)
    return value


def serialized_receipt(receipt, secret_values=()):
    text = json.dumps(sanitize(receipt), indent=2, sort_keys=True, allow_nan=False)
    # Final id-shaped-text pass also covers dictionary keys and unexpected nested fields.
    return frozen().scrub_serialized(text, secret_values) + "\n"


def write_receipt(path, receipt, secret_values=(), *, replace=True):
    path = Path(path)
    protected = {PLAN_PATH.resolve(), Path(__file__).resolve(), FROZEN_RUN.resolve()}
    if path.resolve() in protected or frozen().is_gate_receipt(path):
        raise ValueError("protected receipt destination")
    if not replace and path.exists():
        return False
    raw = serialized_receipt(receipt, secret_values)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".paper-receipt-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        if replace:
            os.replace(temporary, path)
        else:
            # Publish complete bytes without replacing a receipt created by
            # another parent. Python os.link provides atomic create-if-absent.
            try:
                os.link(temporary, path)
            except FileExistsError:
                return False
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def case_outcomes(events, *, stop_ns=None, flat_proof=None):
    """Pure mapping of sanitized native cache events; no strings imply acceptance.

    Each event carries an opaque local order alias and its type/side/quantity/price.
    C2 must cancel C1, and C4 must fill after stop AND have an independent flat proof.
    Duplicate native event ids are removed in snapshot_events, before this mapping.
    """
    definitions = (("LIMIT", "BUY"), ("LIMIT", "BUY"), ("MARKET", "BUY"), ("MARKET", "SELL"))
    result = {cid: {"id": cid, "order_type": typ, "side": side, "price": None,
                    "order": None, "events": [], "outcome": "not_run", "reason": None}
              for cid, (typ, side) in zip(CASE_IDS, definitions)}
    aliases = {}
    for event in events:
        aliases.setdefault(event["order"], event)
    chosen = {}
    for cid, shape in (("C1", ("LIMIT", "BUY")), ("C3", ("MARKET", "BUY")), ("C4", ("MARKET", "SELL"))):
        candidates = [key for key, e in aliases.items() if (e["order_type"], e["side"]) == shape]
        if candidates:
            chosen[cid] = candidates[0]
    if "C1" in chosen:
        chosen["C2"] = chosen["C1"]
    for cid, alias in chosen.items():
        case = result[cid]
        seq = [e for e in events if e["order"] == alias]
        case.update(order=alias, price=seq[0].get("price"), events=seq, outcome="incomplete")
        confirmed = [e for e in seq if not e.get("reconciliation", False)]
        bad = [e for e in seq if e["type"] in TERMINAL_FAILURES or e.get("reconciliation", False)]
        if bad:
            case.update(outcome="failed", reason=f"{cid}_unconfirmed_or_rejected")
            continue
        if decimal(seq[0]["quantity"]) != 1:
            case.update(outcome="failed", reason=f"{cid}_quantity_bound")
            continue
        if cid == "C1":
            if any(e["type"] == "OrderFilled" for e in confirmed):
                case.update(outcome="failed", reason="C1_resting_order_filled")
            elif any(e["type"] == "OrderAccepted" for e in confirmed):
                case["outcome"] = "passed"
        elif cid == "C2":
            accepted = [e for e in confirmed if e["type"] == "OrderAccepted"]
            canceled = [e for e in confirmed if e["type"] == "OrderCanceled"]
            if stop_ns is not None and accepted and any(e["ts_init"] >= stop_ns and e["ts_init"] >= accepted[0]["ts_init"] for e in canceled):
                case["outcome"] = "passed"
        else:
            fills = [e for e in confirmed if e["type"] == "OrderFilled"]
            filled = sum((decimal(e["fill_quantity"]) for e in fills), Decimal(0))
            if filled > 1:
                case.update(outcome="failed", reason=f"{cid}_overfill")
            elif filled == 1:
                if cid == "C3":
                    case["outcome"] = "passed"
                elif stop_ns is not None and all(e["ts_init"] >= stop_ns for e in fills):
                    case["outcome"] = "filled_unproven"
                    if flat_proof and flat_proof.get("status") == "passed":
                        observed = flat_proof.get("observed", {})
                        if observed.get("positions") == 0 and observed.get("open_orders") == 0:
                            case["outcome"] = "passed"
        if case["outcome"] == "incomplete":
            case["reason"] = f"{cid}_expected_event_missing"
    return result


def roundtrip(events, loss_bound):
    fills = [e for e in events if e["type"] == "OrderFilled"]
    if not fills:
        return None
    buys = sum((decimal(e["fill_quantity"]) for e in fills if e["side"] == "BUY"), Decimal(0))
    sells = sum((decimal(e["fill_quantity"]) for e in fills if e["side"] == "SELL"), Decimal(0))
    gross = sum((decimal(e["fill_price"]) * decimal(e["fill_quantity"]) * (1 if e["side"] == "SELL" else -1) for e in fills), Decimal(0))
    unresolved = any(e.get("commission") is None or decimal(e["commission"]) <= 0
                     or e.get("commission_currency") != "USD" or e.get("currency") != "USD" for e in fills)
    fees = None if unresolved else sum((decimal(e["commission"]) for e in fills), Decimal(0))
    closed = buys == sells == 1
    net = gross - fees if fees is not None and closed else None
    return {"buy_quantity": str(buys), "sell_quantity": str(sells), "closed": closed,
            "gross_usd": str(gross) if buys == sells else None,
            "commissions_usd": str(fees) if fees is not None else None,
            "net_usd": str(net) if net is not None else None,
            "commission_unresolved": unresolved,
            "loss_bound_breach": net < -decimal(loss_bound) if net is not None else None}


def new_receipt(plan, plan_path, versions):
    if not isinstance(plan, dict):
        plan = {}
    bounds = plan.get("bounds") if isinstance(plan.get("bounds"), dict) else {}
    try:
        cap = str(decimal(bounds["max_notional_per_order_usd"]))
    except (KeyError, ValueError, InvalidOperation):
        cap = None
    try:
        plan_hash = sha256(plan_path)
    except OSError:
        plan_hash = None
    return {"schema_version": 1, "kind": KIND, "evidence_class": "native_paper",
            "run_nonce": uuid.uuid4().hex,
            "started_at": datetime.now(timezone.utc).isoformat(), "versions": versions,
            "plan_sha256": plan_hash, "harness_sha256": sha256(__file__),
            "source_hashes": {"frozen_checker_sha256": sha256(FROZEN_RUN), "safety_sha256": sha256(HERE / "safety.py")},
            "upstream_commit": UPSTREAM_COMMIT, "pre_check": None, "quote_admission": None,
            "cases": case_outcomes([]), "events": [], "reconciled_external": [], "fills": [], "roundtrip": None,
            "flat_proof": None, "node": {"started": False, "child_launched": False, "stop_ns": None},
            "account_lease": {"acquired": False}, "journal": None,
            "risk": {"bypass": False, "max_notional_per_order_usd": cap,
                     "enforcement": "runner_quantity_and_quote_admission", "note": RISK_NOTE,
                     "engine_route": RISK_ROUTE, "submit_budget_enforcement": "engine_throttle",
                     "release_verification": RELEASE_VERIFICATION},
            "blocked_steps": BLOCKED_STEPS, "failures": [],
            "status": "cleanup_required", "exit_code": 3}


def finish(receipt, status, *, reason=None, step=2, cases=CASE_IDS):
    receipt["status"] = status
    receipt["exit_code"] = 3 if status == "not_started" else frozen().exit_code_for(status)
    receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
    if reason:
        receipt["failures"].append({"acceptance_step": step, "cases_blocked": list(cases), "reason": reason})
    return receipt["exit_code"]


def native_configs(plan, port, account_id, *, tob_offset_ticks):
    """Only upstream configs, with installed rc5 signatures verified offline.

    Source: v2.0.0rc5 examples/live/interactive_brokers/{exec_tester,_common}.py.
    Construction does not connect. Actual account_id is supplied by the official
    pre-check in memory, never from TWS_ACCOUNT or a command line argument.
    """
    from nautilus_trader.adapters import interactive_brokers as ib
    from nautilus_trader.config import LiveRiskEngineConfig
    from nautilus_trader.model import ClientId, InstrumentId, Quantity, StrategyId, TimeInForce
    from nautilus_trader.testkit import ExecTesterConfig
    instrument = InstrumentId.from_str(plan["instrument"]["nautilus_instrument_id"])
    provider = ib.InteractiveBrokersInstrumentProviderConfig(symbology_method=ib.SymbologyMethod.RAW, load_ids={instrument})
    common = dict(host=plan["host"], port=port, client_id=plan["client_ids"]["node"],
                  connection_timeout=10, request_timeout=30, instrument_provider=provider)
    tester_values = dict(plan["exec_tester"])
    tester_values["tob_offset_ticks"] = tob_offset_ticks
    tester_values["order_qty"] = Quantity.from_str(tester_values["order_qty"])
    tester_values["open_position_on_start_qty"] = Decimal(tester_values["open_position_on_start_qty"])
    for key in ("open_position_time_in_force", "limit_time_in_force"):
        tester_values[key] = TimeInForce.from_str(tester_values[key])
    tester = ExecTesterConfig(strategy_id=StrategyId.from_str("EXEC_TESTER-001"), instrument_id=instrument,
                              client_id=ClientId.from_str("IB"), external_order_instrument_ids=[instrument],
                              subscribe_quotes=True, subscribe_trades=True, **tester_values)
    risk = LiveRiskEngineConfig(bypass=False, max_order_submit_rate=plan["risk"]["max_order_submit_rate"],
                                max_notional_per_order={str(instrument): str(plan["bounds"]["max_notional_per_order_usd"])})
    return (ib, ib.InteractiveBrokersDataClientConfig(market_data_type=ib.MarketDataType.REALTIME, batch_quotes=False, **common),
            ib.InteractiveBrokersExecutionClientConfig(account_id=account_id, **common), risk, tester)


def build_node(plan, port, account_id, *, tob_offset_ticks):
    from nautilus_trader.common import Environment, LoggerConfig, LogLevel
    from nautilus_trader.live import LiveNode
    from nautilus_trader.model import TraderId
    ib, data, execution, risk, tester = native_configs(plan, port, account_id, tob_offset_ticks=tob_offset_ticks)
    node = (LiveNode.builder("IB-EXEC-TESTER-001", TraderId.from_str("TESTER-001"), Environment.LIVE)
            .with_reconciliation(True).with_risk_engine_config(risk)
            .with_logging(LoggerConfig(stdout_level=LogLevel.OFF, fileout_level=LogLevel.OFF, print_config=False))
            .with_timeout_connection(plan["timeouts"]["node_start_seconds"])
            .with_timeout_reconciliation(5).with_timeout_portfolio(5)
            .with_timeout_disconnection_secs(5).with_delay_post_stop_secs(plan["timeouts"]["cleanup_seconds"])
            .add_data_client(None, ib.InteractiveBrokersDataClientFactory(), data)
            .add_exec_client(None, ib.InteractiveBrokersExecutionClientFactory(), execution).build())
    node.add_builtin_strategy("ExecTester", tester)
    return node


class RunOrderScope:
    """In-memory client-order-id lineage, including pending local intents.

    Pinned upstream: crates/execution/src/engine/mod.rs materializes and claims
    external orders using this strategy id and the current initialization time.
    Neither alone proves ownership. IB execution/core_orders.rs emits a local
    OrderSubmitted with the original client_order_id on this run's submit path.
    The supported factory's O-date-time-trader_tag-strategy_tag-counter identity
    identifies local intents before submission; its creation second must belong
    to this launch and match initialization. Pinned engine/mod.rs (1176, 1273)
    and live/src/execution/manager.rs (4379) set reconciliation=True on external
    materialization. model/src/orders/market.rs TryFrom<OrderInitialized> (533)
    then calls new_checked, which rebuilds initialization with False (99-108).
    This explains the external MARKET init flags in historical cache receipts;
    it does not describe the original materialization event. Identity checks
    exclude old orders independently. Source:
    crates/common/src/generators/client_order_id.rs write_fixed_prefix/generate.
    Also retain the matching local submission lineage for already sent orders.
    Retain ownership if later events reconcile, so the never-pass rule applies.
    Raw identifiers stay here; receipts use stable O/X aliases only.
    """

    def __init__(self, started_ns):
        self.started_ns = started_ns
        self.owned = {}
        self.external = {}

    def generated_here(self, event):
        parts = str(event.client_order_id).split("-")
        if len(parts) != 6 or parts[0] != "O" or parts[3:5] != ["001", "001"] or not parts[5].isdigit() or int(parts[5]) <= 0:
            return False
        try:
            second = int(datetime.strptime(parts[1] + parts[2], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            return False
        return second >= self.started_ns // 1_000_000_000 and 0 <= event.ts_init // 1_000_000_000 - second <= 1

    def initialized_here(self, order):
        if str(order.strategy_id) != "EXEC_TESTER-001" or str(order.trader_id) != "TESTER-001":
            return False
        initialized = submitted = generated = False
        for event in order.events():
            if (str(event.client_order_id) != str(order.client_order_id)
                    or str(event.strategy_id) != str(order.strategy_id)
                    or str(event.trader_id) != str(order.trader_id)
                    or event.ts_init < self.started_ns
                    or getattr(event, "reconciliation", False)):
                continue
            initialized |= type(event).__name__ == "OrderInitialized"
            submitted |= type(event).__name__ == "OrderSubmitted"
            if type(event).__name__ == "OrderInitialized":
                generated |= self.generated_here(event)
        return initialized and (generated or submitted)

    def partition(self, orders):
        own, other = [], []
        for order in sorted(orders, key=lambda order: (order.ts_init, str(order.client_order_id))):
            key = str(order.client_order_id)
            if key not in self.owned and self.initialized_here(order):
                self.owned[key] = f"O{len(self.owned) + 1}"
            if key in self.owned:
                own.append(order)
            else:
                self.external.setdefault(key, f"X{len(self.external) + 1}")
                other.append(order)
        return own, other


def tester_orders(cache, scope):
    return scope.partition(cache.orders())[0]


def snapshot_events(cache, scope, *, external=False):
    """Read cloned order histories, never serialize account/order/venue/trade ids."""
    orders = scope.partition(cache.orders())[1 if external else 0]
    orders.sort(key=lambda order: (order.ts_init, str(order.client_order_id)))
    events, seen = [], set()
    for order in orders:
        for event in order.events():
            key = str(event.event_id)
            if key in seen:
                continue
            seen.add(key)
            price = getattr(order, "price", None)
            alias = (scope.external if external else scope.owned)[str(order.client_order_id)]
            record = {"order": alias, "order_type": order.order_type.name, "side": order.side.name,
                      "instrument_id": str(order.instrument_id),
                      "quantity": str(order.quantity), "price": str(price) if price is not None else None,
                      "type": type(event).__name__, "ts_event": int(event.ts_event), "ts_init": int(event.ts_init),
                      "at": frozen().ns_to_iso(event.ts_event), "reconciliation": bool(getattr(event, "reconciliation", False))}
            if record["type"] == "OrderFilled":
                commission = event.commission
                record.update(fill_price=str(event.last_px), fill_quantity=str(event.last_qty), currency=str(event.currency),
                              commission=str(commission.as_decimal()) if commission is not None else None,
                              commission_currency=str(commission.currency) if commission is not None else None)
            if external:
                record.pop("instrument_id")
            if not external and hasattr(event, "reason"):
                record["reason"] = frozen().redact(event.reason)
            events.append(record)
    return sorted(events, key=lambda event: (event["ts_init"], event["ts_event"]))


def update_observations(receipt, events, plan):
    receipt["events"] = events
    receipt["cases"] = case_outcomes(events, stop_ns=receipt["node"]["stop_ns"], flat_proof=receipt["flat_proof"])
    receipt["fills"] = [e for e in events if e["type"] == "OrderFilled"]
    receipt["roundtrip"] = roundtrip(events, plan["bounds"]["max_roundtrip_loss_usd"])
    orders = {e["order"]: e for e in events}
    violations = []
    if len(orders) > plan["bounds"]["max_orders"]:
        violations.append(("observed_order_budget_breach", list(CASE_IDS)))
    for e in orders.values():
        cases = ["C1", "C2"] if e["order_type"] == "LIMIT" else ["C3" if e["side"] == "BUY" else "C4"]
        quantity = decimal(e["quantity"])
        if quantity != 1:
            violations.append(("observed_quantity_bound_breach", cases))
        if e.get("instrument_id") != plan["instrument"]["nautilus_instrument_id"]:
            violations.append(("observed_instrument_bound_breach", cases))
        if e.get("price") is not None and decimal(e["price"]) * quantity > decimal(plan["bounds"]["max_notional_per_order_usd"]):
            violations.append(("observed_notional_bound_breach", cases))
    for e in events:
        if e["type"] == "OrderFilled" and decimal(e["fill_price"]) * decimal(e["fill_quantity"]) > decimal(plan["bounds"]["max_notional_per_order_usd"]):
            violations.append(("observed_fill_notional_bound_breach", ["C3" if e["side"] == "BUY" else "C4"]))
    for reason, cases in violations:
        if not any(f["reason"] == reason and f["cases_blocked"] == cases for f in receipt["failures"]):
            receipt["failures"].append({"reason": reason, "cases_blocked": cases, "acceptance_step": 2})


def orders_in_flight(orders):
    """Upstream close-on-stop runs once; wait for entry resolution before stop."""
    terminal = {"FILLED", "CANCELED", "EXPIRED", "REJECTED", "DENIED"}
    return any(order.status.name not in terminal and
               (order.order_type.name == "MARKET" or order.time_in_force.name in ("IOC", "FOK")
                or order.status.name == "SUBMITTED" or order.venue_order_id is None) for order in orders)


def stop_ready(orders, now, node_stop_at):
    return now >= node_stop_at or not orders_in_flight(orders)


def journal_order_events(cache, scope, journal, account_id):
    """Retain original native identities privately; cache events preserve intent order.

    This is observation after native dispatch, not a pre-dispatch fsync barrier.
    rc5's Rust BusTap provides that barrier (common/src/msgbus/mod.rs), but is
    not exposed by the selected Python surface. Do not wrap ExecTester submits.
    """
    for order in tester_orders(cache, scope):
        for event in order.events():
            kind = type(event).__name__
            venue_id = None if kind == "OrderInitialized" else getattr(event, "venue_order_id", None) or order.venue_order_id
            record = {"kind": kind, "event_id": str(event.event_id), "client_order_id": str(order.client_order_id),
                      "venue_order_id": str(venue_id) if venue_id is not None else None,
                      "order_type": order.order_type.name, "side": order.side.name, "quantity": str(order.quantity),
                      "price": str(order.price) if getattr(order, "price", None) is not None else None,
                      "ts_init": int(event.ts_init), "ts_event": int(event.ts_event),
                      "reconciliation": bool(getattr(event, "reconciliation", False))}
            if kind == "OrderFilled":
                commission = event.commission
                record.update(fill_price=str(event.last_px), fill_quantity=str(event.last_qty),
                              commission=str(commission.as_decimal()) if commission is not None else None,
                              commission_currency=str(commission.currency) if commission is not None else None)
            if hasattr(event, "reason"):
                record["reason"] = frozen().scrub_serialized(frozen().redact(event.reason), (account_id,))
            journal.event(record)


async def node_phase(plan, port, receipt_path, payload):
    """Hosted upstream run: cache + thread-safe handle captured before run_async.

    Source: crates/live/src/python/node.rs at UPSTREAM_COMMIT. The parent owns
    the hard deadline; OS process termination cannot strand this awaitable.
    """
    if not validate_child_admission(plan, payload):
        return persist_child_refusal(receipt_path, payload, "refused_child_quote_admission")
    receipt, account_id = payload["receipt"], payload["account_id"]
    journal = None
    try:
        if payload.get("journal_path"):
            journal = safety().Journal(Path(payload["journal_path"]).parent, payload["run_id"], ROOT, create=False)
    except (safety().SafetyError, OSError, TypeError, ValueError):
        return persist_child_refusal(receipt_path, payload, "refused_child_journal")
    node = build_node(plan, port, account_id, tob_offset_ticks=payload["tob_offset_ticks"])
    # Live view: node.rs py_cache uses PyCache::from_rc(kernel.cache());
    # common/src/python/cache.rs PyCache(Rc<RefCell<Cache>>) borrows on each
    # orders() call. Individual returned orders are clones; re-read each poll.
    cache, handle = node.cache, node.handle()
    loop = asyncio.get_running_loop()
    pending_stop = None
    registered_signals = []
    task = None
    scope = RunOrderScope(time.time_ns())

    def observe():
        if journal is not None:
            journal_order_events(cache, scope, journal, account_id)
        update_observations(receipt, snapshot_events(cache, scope), plan)
        receipt["reconciled_external"] = snapshot_events(cache, scope, external=True)
        if journal is not None:
            receipt["journal"] = journal.summary()

    def stop(reason):
        if receipt["node"]["stop_ns"] is None:
            receipt["node"].update(stop_ns=time.time_ns(), stop_reason=reason)
            try:
                if journal is not None:
                    journal.append("stop_request", reason=reason, stop_ns=receipt["node"]["stop_ns"])
            except Exception as exc:
                record_error("journal_stop", exc)
            finally:
                handle.stop()

    def request_stop(reason):
        nonlocal pending_stop
        pending_stop = pending_stop or reason

    def record_error(step, exc):
        receipt["failures"].append({"acceptance_step": 3, "cases_blocked": list(CASE_IDS),
                                    "reason": frozen().redact(f"{step}: {type(exc).__name__}: {exc}")})

    observed_start = None
    try:
        for sig in SIGNALS:
            loop.add_signal_handler(sig, request_stop, f"signal_{sig.name}")
            registered_signals.append(sig)
        task = asyncio.create_task(node.run_async())
        try:
            while not task.done():
                if handle.is_running:
                    receipt["node"]["started"] = True
                    observed_start = observed_start or time.monotonic()
                observe()
                cases = receipt["cases"]
                now = time.monotonic()
                if receipt["failures"] or any(c["outcome"] == "failed" for c in cases.values()):
                    request_stop("case_failure")
                elif cases["C1"]["outcome"] == cases["C3"]["outcome"] == "passed":
                    request_stop("C1_accepted_C3_filled")
                elif observed_start is not None and now - observed_start >= plan["timeouts"]["per_step_seconds"]:
                    request_stop("case_timeout")
                if now >= payload["node_stop_at"]:
                    stop("deadline")
                elif pending_stop:
                    if stop_ready(tester_orders(cache, scope), now, payload["node_stop_at"]):
                        stop(pending_stop)
                write_receipt(receipt_path, receipt, (account_id,))
                await asyncio.sleep(0.1)
        except Exception as exc:
            record_error("node_poll", exc)
            # An accepted MARKET IOC can still fill; preserve close-on-stop's
            # one opportunity to see its position even if observation failed.
            while not task.done() and time.monotonic() < payload["node_stop_at"]:
                try:
                    if stop_ready(tester_orders(cache, scope), time.monotonic(), payload["node_stop_at"]):
                        break
                except Exception:
                    pass  # Unknown state waits only to the bounded deadline.
                await asyncio.sleep(0.1)
            stop("poll_exception")
        await task  # Native cancel/close runs even after an observer exception.
    except Exception as exc:
        record_error("node_run", exc)
        stop("node_exception")
        if task is not None and not task.done():
            try:
                await task
            except Exception as task_exc:
                record_error("node_shutdown", task_exc)
    finally:
        try:
            observe()
        except Exception as exc:
            record_error("final_snapshot", exc)
        try:
            write_receipt(receipt_path, receipt, (account_id,))
        except Exception as exc:
            record_error("final_receipt", exc)
        for sig in registered_signals:
            try:
                loop.remove_signal_handler(sig)
            except Exception as exc:
                record_error("signal_removal", exc)
        try:
            node.dispose()
        except Exception as exc:
            record_error("node_dispose", exc)
        if journal is not None:
            try:
                receipt["journal"] = journal.summary()
            except Exception as exc:
                record_error("journal_summary", exc)
            try:
                journal.close()
            except Exception as exc:
                record_error("journal_close", exc)
        # Persist cleanup errors independently, without skipping disposal.
        write_receipt(receipt_path, receipt, (account_id,))
    return receipt


class CheckTimeout(TimeoutError):
    pass


def official_check(plan, port, *, with_session, deadline):
    """Bound frozen ibapi connect/handshake as well as its request waits."""
    seconds = min(plan["timeouts"]["check_seconds"], max(0, deadline - time.monotonic()))
    if seconds <= 0:
        return {"client": "ibapi", "client_id": 92, "status": "incomplete", "observed": {}}, None

    def expired(_sig, _frame):
        raise CheckTimeout("official_check_deadline")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return frozen().run_check(plan, port, with_session=with_session, deadline_s=seconds)
    except Exception as exc:
        return {"client": "ibapi", "client_id": 92, "status": "incomplete", "observed": {},
                "error": frozen().redact(f"{type(exc).__name__}: {exc}")}, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def official_admission(plan, port, *, deadline, client_factory=None):
    """Flat pre-check and quote admission share one official client-92 session."""
    seconds = min(plan["timeouts"]["check_seconds"], max(0, deadline - time.monotonic()))
    client = (client_factory or build_admission_client)()
    session = CheckSession(client)
    check_deadline = time.monotonic() + seconds
    pre = {"client": "ibapi", "client_id": 92, "status": "incomplete", "observed": {}}
    account_id = None
    phase = "pre_check"
    pre_timed_out = False

    def failure(exc):
        status = "not_connected"
        if "tick requested" in client.stage_elapsed_seconds:
            status = "refused_quote_clock" if "quote" in client.stage_elapsed_seconds else "refused_quote_unavailable"
        if client.delayed:
            status = "refused_delayed_quote"
        elif client.errors and status != "not_connected":
            status = "refused_quote_error"
        return {"status": status, "error": frozen().redact(exc), **client.diagnostics()}

    if seconds <= 0:
        pre["error"] = "CheckTimeout: pre_check_deadline"
        return pre, None, {"status": "not_run", **client.diagnostics()}

    def expired(_sig, _frame):
        nonlocal pre_timed_out
        pre_timed_out = phase == "pre_check"
        raise CheckTimeout(f"{phase}_deadline")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        pre, account_id = frozen().run_check(plan, port, with_session=True,
                                             client_factory=lambda: session, deadline_s=seconds)
        pre["observed"] = copy.deepcopy(pre.get("observed", {}))
        # ibapi.connect / frozen run_check can catch TimeoutError as OSError.
        # Preserve the alarm's phase even when that path returns normally.
        if pre_timed_out:
            pre.update(status="incomplete", error="CheckTimeout: pre_check_deadline")
            return pre, None, {"status": "not_run", **client.diagnostics()}
        phase = "quote_check"
        if pre["status"] != "passed" or not account_id:
            return pre, account_id, {"status": "not_run", **client.diagnostics()}
        admitted = quote_check(plan, account_id, deadline=check_deadline, client=client)
        return pre, account_id, admitted
    except Exception as exc:
        if phase == "pre_check":
            pre.update(status="incomplete", observed=copy.deepcopy(client.r), requests_completed=client.completed(),
                       error=frozen().redact(f"pre_check: {type(exc).__name__}: {exc}"))
            return pre, None, {"status": "not_run", **client.diagnostics()}
        return pre, account_id, failure(exc)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        session.close(check_deadline)


def final_status(receipt, *, interrupted=False, child_returncode=0):
    """Flat-proof failure dominates; observed/case/loss breaches remain failed."""
    if receipt["flat_proof"]["status"] != "passed":
        return "cleanup_required", "independent_flat_proof", 4, ("C4",)
    child_refusal = receipt["node"].get("pre_node_refusal")
    if not receipt["node"]["started"] and child_refusal:
        return child_refusal, child_refusal, 2, CASE_IDS
    rt = receipt["roundtrip"]
    if (any(f["reason"].startswith("observed_") for f in receipt["failures"])
            or any(c["outcome"] == "failed" for c in receipt["cases"].values())
            or rt and rt["loss_bound_breach"]):
        return "failed", "case_or_loss_bound", 2, CASE_IDS
    if interrupted or receipt["failures"] or child_returncode != 0:
        return "incomplete", "signal_or_node_failure", 3, CASE_IDS
    if all(c["outcome"] == "passed" for c in receipt["cases"].values()) and rt and rt["closed"] and not rt["commission_unresolved"]:
        return "passed", None, 2, CASE_IDS
    return "incomplete", "cases_or_commissions_unresolved", 3, CASE_IDS


def parent_failure_status(receipt):
    """Parent I/O failure must preserve launch evidence and any known failure."""
    node = receipt["node"]
    if not (node.get("child_launched", False) or node.get("started", False)):
        return "not_started"
    if not receipt.get("flat_proof") or receipt["flat_proof"].get("status") != "passed":
        return "cleanup_required"
    return "failed" if receipt["status"] == "failed" else "incomplete"


def run_trial(args, *, now=None, versions=None):
    """Every admission refusal precedes official-check and node construction."""
    started_monotonic = time.monotonic()
    try:
        plan = load_plan(args.plan)
    except (ValueError, OSError):
        plan = {}
    versions = runtime_versions() if versions is None else versions
    receipt = new_receipt(plan, args.plan, versions)
    errors = validate_plan(plan, port=args.port, node_client_id=args.node_client_id, check_client_id=args.check_client_id)
    status = "refused_plan" if errors else runtime_refusal(versions)
    now = now or datetime.now(timezone.utc)
    if status is None:
        inside, window = frozen().rth_check(now, plan)
        receipt["window"] = window
        if not inside:
            status = "refused_outside_window"
    if status is None:
        closing_admission = closing_period_admission(plan, now)
        if closing_admission["status"] != "passed":
            receipt["quote_admission"] = closing_admission
            status = closing_admission["status"]
    if status:
        finish(receipt, status, reason="; ".join(errors) if errors else status)
        if args.receipt:
            write_receipt(args.receipt, receipt, replace=False)
        return receipt
    if args.plan_only:
        finish(receipt, "passed")
        receipt["evidence_class"] = "structural_validation"
        if args.receipt:
            write_receipt(args.receipt, receipt, replace=False)
        return receipt
    if args.receipt is None:
        finish(receipt, "refused_receipt_required", reason="receipt required before node")
        return receipt
    # Command-center r2 decision: runner quantity + quote admission hold the
    # bound; the engine cap remains configured with its route limitation stated.
    deadline = started_monotonic + plan["timeouts"]["overall_deadline_seconds"]
    expected_account = os.environ.get("TWS_ACCOUNT")
    private_accounts = [expected_account]
    lease = journal = None
    try:
        # Account-derived lock keys stay on the host; never put them in evidence.
        lease = safety().AccountLease(expected_account)
        receipt["account_lease"]["acquired"] = True
        run_id = args.run_id or uuid.uuid4().hex
        output = args.private_output_dir or Path(args.receipt).resolve().parent / ("private-" + run_id)
        journal = safety().Journal(output, run_id, ROOT, create=True,
                                   hashes={"plan_sha256": receipt["plan_sha256"], "harness_sha256": receipt["harness_sha256"]})
        receipt["journal"] = journal.summary()
        receipt = run_admitted_trial(args, plan, receipt, deadline, expected_account, lease, journal, now, private_accounts)
    except (safety().SafetyError, OSError) as exc:
        launched = receipt["node"].get("child_launched", False)
        reason = str(exc) if isinstance(exc, safety().SafetyError) else (
            "post_launch_io_error" if launched else "lease_or_journal_storage_error")
        finish(receipt, parent_failure_status(receipt), reason=reason, step=4 if launched else 2)
    finally:
        try:
            if journal is not None:
                try:
                    receipt["journal"] = journal.summary()
                finally:
                    journal.close()
        except Exception as exc:
            finish(receipt, parent_failure_status(receipt),
                   reason="private_journal: " + frozen().redact(exc))
        finally:
            try:
                # Refusals are console-only if any prior receipt already exists.
                # A child launch owns its provisional receipt and can refresh it.
                write_receipt(args.receipt, receipt, private_accounts,
                              replace=receipt["node"].get("child_launched", False))
            except OSError:
                launched = receipt["node"].get("child_launched", False)
                finish(receipt, parent_failure_status(receipt),
                       reason="final_receipt_write_error", step=4 if launched else 2)
            finally:
                if lease is not None:
                    lease.close()
    return receipt


def run_admitted_trial(args, plan, receipt, deadline, expected_account, lease, journal, now, private_accounts):
    port = args.port if args.port is not None else plan["default_port"]
    pre, account_id, admitted = official_admission(plan, port, deadline=deadline)
    private_accounts.append(account_id)
    liquid = pre.pop("liquid_hours", "")
    pre.pop("trading_hours", None)
    zone = pre.pop("time_zone_id", "America/New_York")
    receipt["pre_check"] = pre
    receipt["quote_admission"] = admitted
    if pre["status"] != "passed" or not account_id:
        finish(receipt, pre["status"] if pre["status"] != "passed" else "refused_account_scope", reason="pre_check")
        return receipt
    if account_id != expected_account:
        finish(receipt, "refused_changed_account", reason="pre_check_expected_account")
        return receipt
    sessions = frozen().parse_liquid_hours(liquid, zone, now.astimezone(frozen().ZoneInfo("America/New_York")).date())
    if sessions is None or not frozen().rth_check(datetime.now(timezone.utc), plan, sessions, horizon_s=deadline - time.monotonic())[0]:
        finish(receipt, "refused_liquid_hours", reason="whole_run_broker_window")
        return receipt
    if admitted["status"] != "passed":
        finish(receipt, admitted["status"], reason="quote_admission")
        return receipt
    # Atomic provisional cleanup_required receipt BEFORE creating the child/node.
    write_receipt(args.receipt, receipt, (account_id,))
    child = None
    run_nonce = receipt["run_nonce"]
    interrupted = []
    old_handlers = {}

    def signaled(sig, _frame):
        interrupted.append(signal.Signals(sig).name)
        if child is not None and child.poll() is None:
            child.send_signal(sig)

    try:
        for sig in SIGNALS:
            old_handlers[sig] = signal.signal(sig, signaled)
        stop_at = deadline - plan["timeouts"]["post_check_reserve_seconds"] - plan["timeouts"]["cleanup_seconds"] - plan["timeouts"]["node_stop_allowance_seconds"]
        command = [sys.executable, str(Path(__file__).resolve()), "--_node-phase", "--plan", str(Path(args.plan).resolve()),
                   "--port", str(port), "--receipt", str(Path(args.receipt).resolve())]
        child_env = {key: value for key, value in os.environ.items()
                     if key not in ("RUST_LOG", "NAUTILUS_LOG", "TWS_ACCOUNT")}
        # Conservative launch marker survives Popen/pipe/storage failures even
        # when the child never manages to persist node.started.
        receipt["node"]["child_launched"] = True
        child = subprocess.Popen(command, stdin=subprocess.PIPE, text=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=child_env, pass_fds=(lease.fd,))
        # Anonymous pipe only: no account in argv, environment, file or receipt.
        child.stdin.write(json.dumps({"account_id": account_id, "receipt": receipt, "node_stop_at": stop_at,
                                     "run_nonce": run_nonce,
                                     "quote_admission": admitted, "tob_offset_ticks": admitted["tob_offset_ticks"],
                                     "journal_path": str(journal.path), "run_id": journal.run_id}))
        child.stdin.close()
        try:
            child.wait(timeout=max(0, stop_at - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.send_signal(signal.SIGTERM)
            child.wait(timeout=max(0, deadline - plan["timeouts"]["post_check_reserve_seconds"] - time.monotonic()))
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
        receipt["failures"].append({"acceptance_step": 4, "cases_blocked": ["C2", "C4"], "reason": "node_hard_deadline"})
    except Exception as exc:
        receipt["failures"].append({"acceptance_step": 3, "cases_blocked": list(CASE_IDS), "reason": frozen().redact(exc)})
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=plan["timeouts"]["node_stop_allowance_seconds"])
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        saved_failures = receipt["failures"]
        launched = receipt["node"].get("child_launched", False)
        try:
            latest = json.loads(Path(args.receipt).read_text())
            if latest.get("run_nonce") != run_nonce:
                # Other accounts can hold separate leases but share this path.
                # Preserve our provisional evidence and still perform flat proof.
                receipt["failures"].append({"acceptance_step": 3, "cases_blocked": list(CASE_IDS),
                                            "reason": "child_receipt_nonce_mismatch"})
            else:
                latest["failures"].extend(saved_failures)
                latest["node"]["child_launched"] = launched
                # Keep the caller's object current even if flat proof or a later
                # receipt write raises. Never revert to pre-node evidence.
                receipt.clear()
                receipt.update(latest)
        except (OSError, ValueError):
            pass  # Preserve provisional state; a corrupt receipt can never pass.
        proof, proof_account = official_check(plan, port, with_session=False, deadline=deadline)
        private_accounts.append(proof_account)
        if proof["status"] == "passed" and proof_account != account_id:
            proof["status"] = "refused_changed_account"
        receipt["flat_proof"] = proof
        try:
            journal.append("flat_proof", status=proof["status"], positions=proof.get("observed", {}).get("positions"),
                           open_orders=proof.get("observed", {}).get("open_orders"))
        except Exception as exc:
            receipt["failures"].append({"acceptance_step": 4, "cases_blocked": ["C4"], "reason": "journal_flat_proof: " + frozen().redact(exc)})
        update_observations(receipt, receipt["events"], plan)
        status, reason, step, cases = final_status(receipt, interrupted=bool(interrupted),
                                                 child_returncode=child.returncode if child is not None else None)
        finish(receipt, status, reason=reason, step=step, cases=cases)
        try:
            write_receipt(args.receipt, receipt, (account_id, proof_account))
        except OSError:
            finish(receipt, parent_failure_status(receipt),
                   reason="final_receipt_write_error", step=4)
    return receipt


class PaperArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(3, "refused_arguments: " + frozen().redact(message) + "\n")


def parser():
    result = PaperArgumentParser(description=__doc__)
    result.add_argument("--plan", type=Path, default=PLAN_PATH)
    result.add_argument("--receipt", type=Path, help="sanitized, atomically replaced receipt; required for an order run")
    result.add_argument("--plan-only", action="store_true", help="validate plan, pins and window WITHOUT connecting; quote admission is not exercised")
    result.add_argument("--private-output-dir", type=Path, help="0700 directory outside the repository for the private journal; defaults beside receipt")
    result.add_argument("--run-id", help="stable private journal identity; reuse refuses before connection; default is a new UUID")
    result.add_argument("--port", type=int, help="4002 (default) or 7497 only")
    result.add_argument("--node-client-id", type=int, help="91 only")
    result.add_argument("--check-client-id", type=int, help="92 only")
    result.add_argument("--_node-phase", action="store_true", help=argparse.SUPPRESS)
    return result


def persist_child_refusal(path, payload, reason):
    """Keep a sanitized pre-node reason even though child output is discarded."""
    receipt = payload.get("receipt") if isinstance(payload, dict) else None
    if not isinstance(receipt, dict):
        try:
            receipt = json.loads(Path(path).read_text())
        except (OSError, TypeError, ValueError):
            receipt = new_receipt(load_plan(), PLAN_PATH, runtime_versions())
    receipt["node"]["pre_node_refusal"] = reason
    finish(receipt, reason, reason=reason)
    if path is not None:
        account = payload.get("account_id") if isinstance(payload, dict) else None
        write_receipt(path, receipt, (account,))
    return receipt


def run_child(args):
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("invalid child payload")
    except (ValueError, OSError):
        persist_child_refusal(args.receipt, {}, "refused_child_payload")
        return 3
    try:
        plan = load_plan(args.plan)
        reason = "refused_child_plan" if validate_plan(plan, port=args.port) else None
    except (ValueError, OSError):
        reason = "refused_child_plan"
    if reason is None and runtime_refusal(runtime_versions()):
        reason = "refused_child_runtime"
    if reason is None:
        nonce = payload.get("run_nonce")
        child_receipt = payload.get("receipt")
        if (not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce)
                or not isinstance(child_receipt, dict) or child_receipt.get("run_nonce") != nonce):
            reason = "refused_child_receipt_nonce"
    if reason is None:
        try:
            inside = frozen().rth_check(datetime.now(timezone.utc), plan,
                                        horizon_s=max(0, payload["node_stop_at"] - time.monotonic()))[0]
            if not inside:
                reason = "refused_child_window"
        except (KeyError, TypeError, ValueError):
            reason = "refused_child_payload"
    if reason is None and not validate_child_admission(plan, payload):
        reason = "refused_child_quote_admission"
    if reason is None:
        try:
            journal_path = Path(payload["journal_path"]).resolve()
            if journal_path.name != payload["run_id"] + ".jsonl" or ROOT in journal_path.parents:
                reason = "refused_child_journal"
            elif not journal_path.is_file():
                reason = "refused_child_journal"
        except (KeyError, TypeError, ValueError):
            reason = "refused_child_journal"
    if reason:
        persist_child_refusal(args.receipt, payload, reason)
        return 3
    receipt = asyncio.run(node_phase(plan, args.port, args.receipt, payload))
    if receipt["node"].get("pre_node_refusal"):
        return 3
    return 1 if receipt["failures"] else 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args._node_phase:
            # The pipe supplies the admitted quote and derived offset; validate
            # before node creation. This entry never loads an account from env.
            return run_child(args)
        receipt = run_trial(args)
    except Exception as exc:
        print(frozen().scrub_serialized(json.dumps({"status": "incomplete", "exit_code": 1, "error": frozen().redact(exc)})))
        return 1
    print(frozen().scrub_serialized(json.dumps({"status": receipt["status"], "exit_code": receipt["exit_code"], "window": receipt.get("window"),
                      "failures": sanitize(receipt["failures"])})))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
