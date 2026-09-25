"""IBKR local acceptance, steps 2-4, on NautilusTrader 1.231.0's own IB execution engine.

Runs the cases of acceptance-plan.md section 5 that the 2026-09-23 paper-order receipt left
open: client-id ownership, reconnect with an open order, restart reconciliation and the step-4
kill switch. Three fresh-process TradingNode phases run against a signed-in PAPER IB Gateway
or TWS, bracketed by an independent official-ibapi observer.

Subcommands:
  preflight    Read-only: plan, runtime pins, port, prerequisites, kill-switch latch, session
               window, paper account (every managed account starts with DU), zero positions and
               open orders, and the node's client id free. Places and cancels nothing.
  run          The acceptance run. Refused unless --enable-paper-orders is given.
  kill-switch  'status', or 'clear --confirm --reason TEXT' (the only way to remove the latch).
  phase        Internal: one TradingNode phase (A, B or C) in a fresh process, started by 'run'.

Every order is a non-marketable resting LIMIT BUY of 1 SPY; the runner has no marketable or
flattening order. The gate receipt (receipt.json next to this file, kind
native_ibkr_local_acceptance) is written only when every case and checkpoint passed and the
prerequisite receipts named in the plan exist with status passed. Heavy modules
(nautilus_trader, ibapi) are imported lazily; nothing connects at import time.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUNNER_PATH = Path(__file__).resolve()
SHARED_PATH = HERE.parent / "ibkr-paper-orders" / "run.py"
# Predeclared plans only: the regular-session plan and its after-hours variant.
PLAN_NAMES = ("local-acceptance-plan.json", "local-acceptance-plan-post.json")
GATE_RECEIPT = HERE / "receipt.json"
PLAN_KIND = "ibkr_local_acceptance_plan"
RECEIPT_KIND = "ibkr_local_acceptance_steps_2_4"
PHASE_KIND = "ibkr_local_acceptance_phase"
GATE_KIND = "native_ibkr_local_acceptance"
SCHEMA_VERSION = 1
CASES = (("A1", "accept_resting", "A"), ("A2", "client_id_ownership", "A"), ("A3", "reconnect_open_order", "A"),
         ("A4", "restart_setup", "A"), ("B1", "restart_reconciliation", "B"), ("B2", "kill_switch", "B"),
         ("C1", "kill_switch_persists", "C"))
CASE_IDS = tuple(c[0] for c in CASES)
CASE_NAMES = {c[0]: c[1] for c in CASES}
PHASES = ("A", "B", "C")
PHASE_CASES = {p: tuple(c[0] for c in CASES if c[2] == p) for p in PHASES}
ORDER_SUFFIXES = ("R1", "R2", "P1", "P2")
LIVE_PORTS = (4001, 7496)
TOKEN_ENV = "IBKR_LOCAL_ACCEPTANCE_TOKEN"
ACCOUNT_ENV = "IBKR_LOCAL_ACCEPTANCE_ACCOUNT"
HALTED_DENIAL = "TradingState.HALTED"
WORKING_STATUSES = {"Submitted", "PreSubmitted"}
CANCELLED_STATUSES = {"Cancelled", "ApiCancelled"}
SESSIONS = {("09:30", "16:00"): "regular", ("16:00", "20:00"): "after_hours"}
DEFAULT_STATE_DIR = (Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
                     / "native-agent-stack" / "ibkr-local-acceptance")
PHASE_GRACE_SECONDS = 30
TERMINATE_GRACE_SECONDS = 20
# Node build, the first-tick start of a phase's first case and the 1 s watchdog granularity of
# each step, on top of the steps' own limits.
PHASE_SLACK_SECONDS = 15
IBAPI_CONNECT_SECONDS = 10
IBAPI_LISTING_SECONDS = 10


def _load_shared():
    """The reviewed ibkr-paper-orders harness: redaction, the official-ibapi check, prices,
    budget, session window, node config and the node stop control are reused from it."""
    spec = importlib.util.spec_from_file_location("ibkr_paper_orders_shared", SHARED_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PO = _load_shared()
redact = PO.redact
BudgetError = PO.BudgetError
_dec = PO._dec
# The shared harness names the same flip receipt; one definition keeps the refusal in step.
is_gate_receipt = PO.is_gate_receipt
assert PO.GATE_RECEIPT.resolve() == GATE_RECEIPT.resolve()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def rel(path, repo=None) -> str:
    """Repository-relative path when inside the repository; otherwise a private marker."""
    try:
        return str(Path(path).resolve().relative_to(Path(repo or REPO).resolve()))
    except ValueError:
        return "<private>"


# --------------------------------------------------------------------------- plan


def load_plan(path) -> dict:
    return json.loads(Path(path).read_text())


def validate_plan(plan: dict) -> list[str]:
    """Return every violation of the frozen bounds; empty means valid."""
    errors: list[str] = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    try:
        need(plan.get("schema_version") == 1, "schema_version must be 1")
        need(plan.get("kind") == PLAN_KIND, f"kind must be {PLAN_KIND}")
        need(plan.get("host") == "127.0.0.1", "host must be 127.0.0.1")
        ports = plan.get("paper_ports") or []
        need(bool(ports) and set(ports) <= {4002, 7497}, "paper_ports must be a non-empty subset of {4002, 7497}")
        need(sorted(plan.get("live_ports_refused") or []) == sorted(LIVE_PORTS), "live_ports_refused must be [4001, 7496]")
        need(plan.get("account_prefix") == "DU", "account_prefix must be DU")
        need(plan.get("require_single_managed_account") is True, "require_single_managed_account must be true")
        e = plan["engine"]
        need((e["version"], e["ibapi_version"]) == ("1.231.0", "10.45.1"), "engine must be nautilus_trader 1.231.0 on ibapi 10.45.1")
        ids = plan["client_ids"]
        node, check, band = ids["node"], ids["check"], ids["adapter_fallback_band"]
        need(node == 93 and check == 98, "client ids must be node 93 and check 98")
        # 1.231.0 client/connection.py: _max_client_id_offset = 4 after three 326 collisions.
        need(band == [node, node + 4], "adapter_fallback_band must be [node, node + 4]")
        taken = set(range(band[0], band[1] + 1))
        need(check not in taken and not taken & set(ids.get("reserved_elsewhere", [])),
             "the check id and reserved ids must lie outside the adapter fallback band")
        inst = plan["instrument"]
        need((inst["symbol"], inst["sec_type"], inst["exchange"], inst["primary_exchange"], inst["currency"],
              inst["nautilus_instrument_id"]) == ("SPY", "STK", "SMART", "ARCA", "USD", "SPY.ARCA"),
             "instrument must be SPY STK SMART/ARCA USD (SPY.ARCA)")
        b = plan["bounds"]
        need(b["max_orders"] == 4 and b["order_ids"] == list(ORDER_SUFFIXES), "max_orders must be 4: R1, R2, P1, P2")
        need(b["max_orders_reaching_ib"] == 2, "max_orders_reaching_ib must be 2 (R1, R2)")
        need(b["max_quantity_per_order"] == 1, "max_quantity_per_order must be 1")
        need(0 < b["max_notional_per_order_usd"] <= 1000, "max_notional_per_order_usd must be in (0, 1000]")
        need(0 < b["resting_fraction_of_bid"] <= 0.5, "resting_fraction_of_bid must be in (0, 0.5]")
        need(b["resting_price_floor_usd"] >= 0.01, "resting_price_floor_usd must be >= 0.01")
        need((b["order_side"], b["order_type"], b["time_in_force"]) == ("BUY", "LIMIT", "DAY"),
             "orders must be BUY LIMIT DAY")
        need(b["marketable_orders"] is False, "marketable_orders must be false")
        rate_n, rate_iv = PO.submit_rate_parts(b["max_order_submit_rate"])
        spacing = b["min_submit_spacing_seconds"]
        need(spacing >= 1.2, "min_submit_spacing_seconds must be >= 1.2")
        need(rate_n / rate_iv >= 2.0 / spacing and rate_n >= 2, "max_order_submit_rate would throttle the harness's spacing")
        need(isinstance(b["max_cancel_attempts_per_order"], int) and 2 <= b["max_cancel_attempts_per_order"] <= 5,
             "max_cancel_attempts_per_order must be 2..5")
        s = plan["session"]
        need(s["timezone"] == "America/New_York", "session timezone must be America/New_York")
        kind = SESSIONS.get((s["open"], s["close"]))
        need(kind is not None, "session must be 09:30-16:00 (regular) or 16:00-20:00 (after hours)")
        need(s.get("outside_rth", False) is (kind == "after_hours"), "outside_rth must be true exactly for the after-hours session")
        need(s.get("contract_hours_field", "liquidHours") == ("tradingHours" if kind == "after_hours" else "liquidHours"),
             "the after-hours session reads the contract's tradingHours; the regular session its liquidHours")
        need(s.get("use_contract_liquid_hours") is True, "the session must check today's contract hours")
        need(s["close_buffer_minutes"] >= 10, "close_buffer_minutes must be >= 10")
        d = plan["data"]
        need(0 < d["quote_max_age_seconds"] <= 10, "quote_max_age_seconds must be in (0, 10]")
        need(0 <= d["clock_resolution_tolerance_seconds"] <= 2, "clock tolerance must be in [0, 2]")
        t = plan["timeouts"]
        need(t["node_start_seconds"] == 60 and t["per_step_seconds"] == 45, "node_start_seconds 60 and per_step_seconds 45")
        need(0 < t["probe_seconds"] <= t["per_step_seconds"], "probe_seconds must fit one step")
        need(30 <= t["reconnect_seconds"] <= 90, "reconnect_seconds must be in [30, 90]")
        need(0 < t["recancel_interval_seconds"] <= t["cleanup_seconds"] / 3, "recancel_interval_seconds must fit 3x in cleanup")
        need(3 <= t["post_stop_cancel_grace_seconds"] and t["post_stop_cancel_grace_seconds"] + 10
             <= t["node_stop_allowance_seconds"], "post_stop_cancel_grace_seconds + 10 s disconnect must fit the stop allowance")
        pd = t["phase_deadline_seconds"]
        need(set(pd) == set(PHASES), "phase_deadline_seconds must name phases A, B and C")
        step, start, stop = t["per_step_seconds"], t["node_start_seconds"], t["node_stop_allowance_seconds"]
        # Each phase aborts into cleanup at deadline - stop - cleanup (cmd_phase), so every step at
        # its own limit, plus the slack, must still fit before that point.
        tail = t["cleanup_seconds"] + stop + PHASE_SLACK_SECONDS
        need(pd["A"] >= start + 3 * step + t["reconnect_seconds"] + step + tail, "phase A deadline does not fit its steps")
        need(pd["B"] >= start + 2 * step + tail, "phase B deadline does not fit its steps")
        need(pd["C"] >= start + step + tail, "phase C deadline does not fit its step")
        need(worst_case_seconds(plan) <= t["overall_deadline_seconds"],
             "the worst-case run time does not fit overall_deadline_seconds")
        need(t["observer_attempts"] >= 1 and t["ibapi_cancel_attempts"] >= 1, "observer and cancel attempts must be >= 1")
        x = plan["exec_engine"]
        need(x["inflight_check_threshold_ms"] * x["inflight_check_retries"] / 1000 > max(pd.values()),
             "exec_engine in-flight resolution must lie beyond every phase deadline")
        need(x["inflight_check_interval_ms"] > 0, "inflight_check_interval_ms must stay > 0")
        need([c["id"] for c in plan["cases"]] == list(CASE_IDS), "cases must be exactly A1..A4, B1, B2, C1 in order")
        need([(c["name"], c["phase"]) for c in plan["cases"]] == [(CASE_NAMES[c], c[0]) for c in CASE_IDS],
             "case names or phases do not match")
        need(set(plan["phases"]) == set(PHASES), "phases must be A, B and C")
        r = plan["receipt"]
        need(r["kind"] == RECEIPT_KIND, "receipt kind mismatch")
        g = r["gate_receipt"]
        need(g["path"] == rel(GATE_RECEIPT), "gate receipt path must be ibkr-acceptance/receipt.json")
        need(g["schema"] == {"schema_version": 1, "kind": GATE_KIND, "broker": "ibkr"}, "gate receipt schema mismatch")
        need(bool(g["prerequisites"]) and all(p.get("status") == "passed" for p in g["prerequisites"]),
             "gate prerequisites must each require status passed")
        need(bool(plan.get("version_selection_record")), "version_selection_record is required")
        need(plan.get("evidence_class") == "native_paper", "evidence_class must be native_paper")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"plan field missing or malformed: {exc!r}")
    return errors


def worst_case_seconds(plan: dict) -> int:
    """Upper bound of one run's wall time; overall_deadline_seconds must cover it, because the
    session-window check refuses a start whose [now, now + overall] leaves the window."""
    t = plan["timeouts"]
    pre = t["check_seconds"] + IBAPI_CONNECT_SECONDS  # the read-only check and the client-id contender
    phases = sum(t["phase_deadline_seconds"].values()) + len(PHASES) * (PHASE_GRACE_SECONDS + TERMINATE_GRACE_SECONDS)
    observer = (t["check_seconds"] * t["observer_attempts"]
                + t["observer_retry_delay_seconds"] * (t["observer_attempts"] - 1))
    # ibapi_cancel_run_orders: one observation per round plus a final one; per cancel round up to
    # one holder id per phase (connect, listing, cancel wait) and the pause before the next round.
    holder = IBAPI_CONNECT_SECONDS + IBAPI_LISTING_SECONDS + t["ibapi_cancel_wait_seconds"]
    rounds = t["ibapi_cancel_attempts"]
    cleanup = (rounds + 1) * t["check_seconds"] + rounds * (len(PHASES) * holder + t["recancel_interval_seconds"])
    return pre + phases + 3 * observer + cleanup


def port_refusal(plan: dict, port: int) -> str | None:
    """Live ports first, so 4001/7496 always read as live, then any other non-paper port."""
    if port in LIVE_PORTS or port in plan.get("live_ports_refused", []):
        return "refused_live_port"
    if port not in plan["paper_ports"]:
        return "refused_not_paper_port"
    return None


def gate_prerequisites(plan: dict, repo: Path | None = None) -> tuple[bool, list[dict]]:
    """Each prerequisite receipt must exist with its required status; the version-selection
    record must exist. Returns (ok, entries with sha256)."""
    repo = REPO if repo is None else Path(repo)
    entries = []
    for p in plan["receipt"]["gate_receipt"]["prerequisites"]:
        entry = {"path": p["path"], "required_status": p["status"], "covers": p.get("covers")}
        path = repo / p["path"]
        try:
            data = json.loads(path.read_text())
            entry.update(sha256=PO.sha256_file(path), status=data.get("status"), ok=data.get("status") == p["status"])
        except (OSError, ValueError) as exc:
            entry.update(ok=False, reason=f"unreadable: {type(exc).__name__}")
        entries.append(entry)
    record = repo / plan["version_selection_record"]
    entry = {"path": plan["version_selection_record"], "covers": "dated version-selection record"}
    entry.update(ok=record.is_file(), sha256=PO.sha256_file(record) if record.is_file() else None)
    entries.append(entry)
    return all(e["ok"] for e in entries), entries


# --------------------------------------------------------------------------- kill switch latch


def _fsync_dir(path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_private(path, text: str, durable: bool = True) -> None:
    """Atomic 0600 replace; with durable, fsync of the file and its directory as well. The
    provisional phase result is rewritten on the event loop at every state change, so it is
    written without fsync, like the shared harness's provisional receipt."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode())
        if durable:
            os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    if durable:
        _fsync_dir(path.parent)


def private_dir(path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


class KillSwitch:
    """A file latch independent of any strategy logic. Its existence is the engaged state, so
    an unreadable or corrupt latch still reads as engaged. Only clear() removes it, after an
    audit line is on disk; no restart path clears it."""

    def __init__(self, state_dir):
        self.dir = Path(state_dir)
        self.path = self.dir / "kill-switch.json"
        self.audit_path = self.dir / "kill-switch-audit.jsonl"

    def engaged(self) -> bool:
        return self.path.exists() or self.path.is_symlink()

    def status(self) -> dict:
        if not self.engaged():
            return {"engaged": False}
        try:
            return {"engaged": True, "readable": True, "record": json.loads(self.path.read_text())}
        except (OSError, ValueError):
            return {"engaged": True, "readable": False}

    def _audit(self, entry: dict) -> None:
        fd = os.open(str(self.audit_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (json.dumps(entry, sort_keys=True) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)

    def engage(self, run_prefix: str, reason: str, now: str | None = None) -> dict:
        private_dir(self.dir)
        record = {"engaged": True, "engaged_at": now or utc_now_iso(), "run_prefix": run_prefix,
                  "reason": redact(reason)[:200],
                  "policy": "halt new submits (RiskEngine HALTED), cancel every open order of the run, retain none"}
        write_private(self.path, json.dumps(record, indent=2) + "\n")
        self._audit({"event": "engaged", **record})
        return record

    def clear(self, confirm: bool, reason: str | None, now: str | None = None) -> dict:
        if not confirm:
            return {"status": "refused_not_confirmed"}
        if not reason or not reason.strip():
            return {"status": "refused_reason_required"}
        if not self.engaged():
            return {"status": "not_engaged"}
        entry = {"event": "cleared", "cleared_at": now or utc_now_iso(), "reason": redact(reason)[:200],
                 "prior": self.status().get("record")}
        self._audit(entry)  # the audit line is durable before the latch goes
        self.path.unlink()
        _fsync_dir(self.dir)
        return {"status": "cleared", **entry}


def acquire_lock(state_dir):
    """Single writer per state directory: a held lock refuses a second run. Returns the open
    file (keep it referenced) or None when another process holds it."""
    fh = open(Path(state_dir) / "run.lock", "a+")  # noqa: SIM115 - held for the run's lifetime
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


# --------------------------------------------------------------------------- official ibapi observer


OBSERVER_KEYS = ("accounts", "next_id", "positions", "open_orders", "completed", "executions", "refused")


class ObserverState:
    """Official-ibapi callbacks kept free of ibapi so they test offline; mixed into
    EWrapper/EClient by build_observer_client. No order method is called on it except
    cancelOrder in ibapi_cancel_run_orders. Account ids stay in memory only."""

    def __init__(self):
        self.done = {k: threading.Event() for k in OBSERVER_KEYS}
        self._accounts: list[str] = []
        self._open_keys: set = set()
        self._completed_keys: set = set()
        self._exec_keys: set = set()
        self.order_status: dict = {}
        self.r = {"account_count": 0, "paper_accounts": None, "positions": [], "open_orders": [],
                  "completed_orders": [], "executions": [], "errors": [], "info": []}

    def managedAccounts(self, accountsList):
        # The shared check's latched paper-account rule: once any callback reports a non-paper
        # account the observer stays refused.
        PO.CheckState.managedAccounts(self, accountsList)

    def nextValidId(self, orderId):
        self.done["next_id"].set()

    def position(self, account, contract, pos, avgCost):
        if pos:
            self.r["positions"].append({"symbol": getattr(contract, "symbol", None),
                                        "sec_type": getattr(contract, "secType", None), "quantity": str(pos)})

    def positionEnd(self):
        self.done["positions"].set()

    @staticmethod
    def _order_entry(order_id, contract, order, state) -> dict:
        return {"order_id": order_id, "client_id": getattr(order, "clientId", None),
                "perm_id": getattr(order, "permId", 0), "order_ref": str(getattr(order, "orderRef", "") or ""),
                "status": str(getattr(state, "status", "") or ""), "action": getattr(order, "action", None),
                "quantity": str(getattr(order, "totalQuantity", "")), "limit_price": str(getattr(order, "lmtPrice", "")),
                "tif": getattr(order, "tif", None), "symbol": getattr(contract, "symbol", None)}

    def openOrder(self, orderId, contract, order, orderState):
        key = getattr(order, "permId", 0) or ("order", getattr(order, "clientId", None), orderId)
        if key in self._open_keys:
            return
        self._open_keys.add(key)
        self.r["open_orders"].append(self._order_entry(orderId, contract, order, orderState))

    def openOrderEnd(self):
        self.done["open_orders"].set()

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice,
                    clientId, whyHeld, mktCapPrice):
        self.order_status[orderId] = str(status)

    def completedOrder(self, contract, order, orderState):
        key = getattr(order, "permId", 0) or ("ref", getattr(order, "orderRef", ""))
        if key in self._completed_keys:
            return
        self._completed_keys.add(key)
        entry = self._order_entry(getattr(order, "orderId", None), contract, order, orderState)
        entry["completed_status"] = redact(getattr(orderState, "completedStatus", "") or "")[:120]
        self.r["completed_orders"].append(entry)

    def completedOrdersEnd(self):
        self.done["completed"].set()

    def execDetails(self, reqId, contract, execution):
        key = getattr(execution, "execId", None) or len(self._exec_keys)
        if key in self._exec_keys:
            return
        self._exec_keys.add(key)
        self.r["executions"].append({"order_ref": str(getattr(execution, "orderRef", "") or ""),
                                     "perm_id": getattr(execution, "permId", 0),
                                     "client_id": getattr(execution, "clientId", None),
                                     "side": getattr(execution, "side", None), "shares": str(getattr(execution, "shares", "")),
                                     "symbol": getattr(contract, "symbol", None)})

    def execDetailsEnd(self, reqId):
        self.done["executions"].set()

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        # ibapi 10.45 signature: (reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)
        entry = {"reqId": reqId, "code": errorCode, "text": redact(errorString)[:160]}
        (self.r["info"] if errorCode in PO.INFO_CODES else self.r["errors"]).append(entry)
        if errorCode == 326:  # client id already in use
            self.done["refused"].set()

    def completed(self) -> dict:
        return {k: v.is_set() for k, v in self.done.items()}

    def single_account(self) -> str | None:
        return self._accounts[0] if len(self._accounts) == 1 else None


def build_observer_client():
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class ObserverClient(ObserverState, EWrapper, EClient):
        def __init__(self):
            ObserverState.__init__(self)
            EClient.__init__(self, self)

    return ObserverClient()


def _connect(p, host, port, client_id) -> bool:
    try:
        p.connect(host, port, client_id)
    except OSError as exc:
        p.r["errors"].append({"reqId": -1, "code": None, "text": redact(f"{type(exc).__name__}: {exc}")[:160]})
        return False
    # EClient.run drains the queue while connected or while messages remain (an IB 326 arrives
    # just before the gateway closes the socket), so it starts whenever connect did not raise.
    threading.Thread(target=p.run, daemon=True).start()
    return p.isConnected()


def _disconnect(p) -> None:
    try:
        p.disconnect()
    except Exception:  # noqa: BLE001
        pass


def _exec_filter(plan: dict):
    from ibapi.execution import ExecutionFilter

    f = ExecutionFilter()
    f.clientId = plan["client_ids"]["node"]
    return f


def observer_verdict(r: dict, completed: dict, required) -> str:
    if r["paper_accounts"] is not True:
        return "refused_not_paper_account"
    if r["account_count"] != 1:
        return "refused_account_scope"
    return "passed" if all(completed.get(k) for k in required) else "incomplete"


def _observed(p) -> dict:
    return {k: p.r[k] for k in ("account_count", "paper_accounts", "positions", "open_orders", "completed_orders",
                                "executions", "errors", "info")}


def observe(plan: dict, port: int, *, include=("positions", "open_orders"), client_factory=None,
            deadline_s: float | None = None) -> dict:
    """One read-only snapshot on the check client id (independent of the Nautilus adapter's
    connection). The paper-account check is latched and runs before every request."""
    t = plan["timeouts"]
    budget = t["check_seconds"] if deadline_s is None else min(deadline_s, t["check_seconds"])
    host, cid = plan["host"], plan["client_ids"]["check"]
    out = {"client": "ibapi", "client_id": cid, "port": port, "include": list(include), "status": None}
    refusal = port_refusal(plan, port)
    if refusal:
        out["status"] = refusal
        return out
    p = (client_factory or build_observer_client)()
    deadline = time.monotonic() + budget

    def wait(key, seconds):
        return p.done[key].wait(max(0.0, min(seconds, deadline - time.monotonic())))

    try:
        if not _connect(p, host, port, cid) or not wait("accounts", 10):
            out.update(status="not_connected", observed=_observed(p))
            return out
        steps = []
        if "positions" in include:
            steps.append(("positions", p.reqPositions, p.cancelPositions))
        if "open_orders" in include:
            steps.append(("open_orders", p.reqAllOpenOrders, None))
        if "completed" in include:
            steps.append(("completed", lambda: p.reqCompletedOrders(True), None))
        if "executions" in include:
            steps.append(("executions", lambda: p.reqExecutions(9801, _exec_filter(plan)), None))
        for key, request, after in steps:
            if p.r["paper_accounts"] is not True:  # checked before every request
                break
            request()
            wait(key, 10)
            if after:
                after()
        required = ("accounts",) + tuple(k for k, *_ in steps)
        completed = p.completed()
        out.update(status=observer_verdict(p.r, completed, required), observed=_observed(p),
                   requests_completed={k: completed[k] for k in required})
        return out
    finally:
        _disconnect(p)


def observe_with_retry(observe_fn, plan: dict, port: int, include, sleep_fn=time.sleep) -> dict:
    t = plan["timeouts"]
    attempts = []
    for i in range(t["observer_attempts"]):
        if i:
            sleep_fn(t["observer_retry_delay_seconds"])
        try:
            snap = observe_fn(plan, port, include=include)
        except Exception as exc:  # noqa: BLE001
            snap = {"status": "error", "error": redact(f"{type(exc).__name__}: {exc}")[:200]}
        attempts.append(snap.get("status"))
        if snap.get("status") == "passed" or str(snap.get("status", "")).startswith("refused_"):
            break
    snap["attempts"] = attempts
    return snap


def contender_probe(plan: dict, port: int, *, client_factory=None, wait_s: float = 10.0) -> dict:
    """Connect with the node's client id and send no request. 'refused_326' while the node is
    connected shows the node owns the id; 'connected' before the node starts shows it is free.
    Disconnects on every path."""
    host, cid = plan["host"], plan["client_ids"]["node"]
    out = {"client_id": cid, "outcome": None}
    refusal = port_refusal(plan, port)
    if refusal:
        out["outcome"] = refusal
        return out
    p = (client_factory or build_observer_client)()
    try:
        connected = _connect(p, host, port, cid)
        end = time.monotonic() + wait_s
        while time.monotonic() < end:
            if p.done["refused"].is_set() or (p.done["accounts"].is_set() and p.done["next_id"].is_set()):
                break
            time.sleep(0.05)
        if p.done["refused"].is_set():
            outcome = "refused_326"
        elif p.done["accounts"].is_set():
            outcome = "connected" if p.r["paper_accounts"] is True else "refused_not_paper_account"
        elif not connected:
            outcome = "not_connected"
        else:
            outcome = "no_answer"
        out.update(outcome=outcome, errors=[e for e in p.r["errors"] if e.get("code") != 326][:5],
                   codes=sorted({e["code"] for e in p.r["errors"] if e.get("code") is not None}))
        return out
    finally:
        _disconnect(p)


def _order_cancel():
    from ibapi.order_cancel import OrderCancel

    return OrderCancel()


def _cancel_as(plan: dict, port: int, client_id: int, prefix: str, out: dict, attempt: int, client_factory) -> int:
    """Connect on one client id of the adapter's band, list that id's own open orders and cancel
    this run's. Returns how many cancels IB confirmed. An incomplete listing cancels nothing."""
    t = plan["timeouts"]
    p = (client_factory or build_observer_client)()
    try:
        if not _connect(p, plan["host"], port, client_id) or not p.done["accounts"].wait(IBAPI_CONNECT_SECONDS):
            out["notes"].append(f"client {client_id}: not connected")
            return 0
        if p.r["paper_accounts"] is not True or p.r["account_count"] != 1:
            out["notes"].append(f"client {client_id}: not a single paper account; nothing sent")
            return 0
        p.reqOpenOrders()
        if not p.done["open_orders"].wait(IBAPI_LISTING_SECONDS):
            out["notes"].append(f"client {client_id}: open-order listing incomplete; nothing sent")
            return 0
        mine = [o for o in p.r["open_orders"] if is_run_order(o, prefix) and o.get("client_id") == client_id]
        for o in mine:
            p.cancelOrder(o["order_id"], _order_cancel())
            out["cancel_sent"].append({"order_ref": o["order_ref"], "order_id": o["order_id"], "client_id": client_id,
                                       "attempt": attempt + 1})
        end = time.monotonic() + t["ibapi_cancel_wait_seconds"]
        while time.monotonic() < end and not all(p.order_status.get(o["order_id"]) in CANCELLED_STATUSES for o in mine):
            time.sleep(0.1)
        return sum(p.order_status.get(o["order_id"]) in CANCELLED_STATUSES for o in mine)
    finally:
        _disconnect(p)


def ibapi_cancel_run_orders(plan: dict, port: int, prefix: str, *, client_factory=None, observe_fn=None,
                            sleep_fn=time.sleep) -> dict:
    """Cleanup only, after the phase process has exited. The observer (check id, all clients)
    lists this run's open orders and the client ids holding them; for each holder inside the
    adapter's fallback band (the node's id or a fallback the adapter took) the order is cancelled
    on that id, the only one IB lets cancel it. 'none_open' needs a complete observer listing
    without an order of the run. Never places an order and never touches a foreign order."""
    t = plan["timeouts"]
    lo, hi = plan["client_ids"]["adapter_fallback_band"]
    out = {"attempts": [], "cancel_sent": [], "notes": [], "status": None}
    refusal = port_refusal(plan, port)
    if refusal:
        out["status"] = refusal
        return out
    observe_fn = observe_fn or (lambda plan_, port_, include: observe(plan_, port_, include=include,
                                                                       client_factory=client_factory))
    rounds = t["ibapi_cancel_attempts"]
    for attempt in range(rounds + 1):  # the last round only observes, after the last cancels
        if attempt:
            sleep_fn(t["recancel_interval_seconds"])
        snap = observe_fn(plan, port, ("open_orders",))
        if snap.get("status") != "passed":
            out["attempts"].append({"status": f"observer_{snap.get('status')}"})
            if str(snap.get("status", "")).startswith("refused_"):
                out["status"] = snap["status"]
                return out
            continue
        ours = [o for o in _listed(snap, "open_orders") if is_run_order(o, prefix)]
        if not ours:
            out["attempts"].append({"status": "none_open"})
            out["status"] = "none_open" if not out["cancel_sent"] else "cancelled"
            return out
        holders = sorted({o.get("client_id") for o in ours if o.get("client_id") is not None})
        entry = {"status": "open", "orders": len(ours), "client_ids": holders,
                 "outside_band": [c for c in holders if not lo <= c <= hi]}
        if attempt < rounds:
            entry["confirmed"] = sum(_cancel_as(plan, port, c, prefix, out, attempt, client_factory)
                                     for c in holders if lo <= c <= hi)
        out["attempts"].append(entry)
    out["status"] = "cancel_unconfirmed"
    return out


# --------------------------------------------------------------------------- verdicts (pure)


def order_ref_client_id(ref) -> str:
    """The 1.231.0 adapter sends orderRef '<client order id>:<orderId>' (client/order.py place_order)."""
    return str(ref or "").rsplit(":", 1)[0]


def order_ref_suffix(ref) -> str:
    parts = str(ref or "").rsplit(":", 1)
    return parts[1] if len(parts) == 2 else ""


def is_run_order(entry: dict, prefix: str) -> bool:
    return bool(prefix) and str(entry.get("order_ref") or "").startswith(prefix + "-")


def venue_ids_for(entry: dict) -> set:
    """VenueOrderId forms the 1.231.0 adapter uses: PERM-<permId> once IB assigned one, else the orderId."""
    ids = set()
    if entry.get("perm_id"):
        ids.add(f"PERM-{entry['perm_id']}")
    if entry.get("order_id") not in (None, 0):
        ids.add(str(entry["order_id"]))
    return ids


def perm_from_venue(venue_order_id) -> int | None:
    v = str(venue_order_id or "")
    return int(v[5:]) if v.startswith("PERM-") and v[5:].isdigit() else None


def _listed(snapshot: dict | None, key: str) -> list:
    return list(((snapshot or {}).get("observed") or {}).get(key) or [])


def ownership_verdict(plan: dict, probe: dict | None, node: dict, r1_client_order_id: str) -> dict:
    """Step 2: the node owns its client id and IB's view of R1 maps onto the node's order."""
    reasons = []
    probe = probe or {}
    contender, obs = probe.get("contender") or {}, probe.get("observer") or {}
    node_id = plan["client_ids"]["node"]
    if probe.get("error"):
        reasons.append("probe_error")
    if contender.get("outcome") != "refused_326":
        reasons.append(f"contender_{contender.get('outcome')}")
    if obs.get("status") != "passed":
        reasons.append(f"observer_{obs.get('status')}")
    matches = [o for o in _listed(obs, "open_orders") if order_ref_client_id(o.get("order_ref")) == r1_client_order_id]
    facts = {"contender_outcome": contender.get("outcome"), "observer_status": obs.get("status"),
             "observer_matches": len(matches)}
    if len(matches) != 1:
        reasons.append("r1_not_listed_once")
    else:
        m = matches[0]
        facts.update(order_id=m.get("order_id"), perm_id=m.get("perm_id"), client_id=m.get("client_id"), status=m.get("status"))
        if m.get("client_id") != node_id:
            reasons.append("r1_client_id_mismatch")
        if order_ref_suffix(m.get("order_ref")) != str(m.get("order_id")):
            reasons.append("r1_order_ref_suffix_mismatch")
        if node.get("r1_venue_order_id") not in venue_ids_for(m):
            reasons.append("r1_venue_order_id_mismatch")
        if m.get("status") not in WORKING_STATUSES:
            reasons.append("r1_not_working_at_ib")
    adapter = node.get("adapter") or {}
    facts["adapter_client_id"] = adapter.get("client_id")
    if adapter.get("client_id") != node_id or adapter.get("configured_client_id") != node_id:
        reasons.append("adapter_client_id_changed")
    if adapter.get("fetch_all_open_orders"):
        reasons.append("adapter_client_id_fallback")
    if not node.get("r1_open"):
        reasons.append("r1_not_open_in_node")
    return {"passed": not reasons, "reasons": reasons, **facts}


def still_open_verdict(plan: dict, snapshot: dict | None, client_order_id: str, expected: dict) -> dict:
    """After the reconnect: the same IB order (orderId, permId) still works on the node's client id."""
    reasons = []
    if (snapshot or {}).get("error"):
        reasons.append("probe_error")
    if (snapshot or {}).get("status") != "passed":
        reasons.append(f"observer_{(snapshot or {}).get('status')}")
    matches = [o for o in _listed(snapshot, "open_orders") if order_ref_client_id(o.get("order_ref")) == client_order_id]
    facts = {"observer_matches": len(matches)}
    if len(matches) != 1:
        reasons.append("order_not_listed_once")
    else:
        m = matches[0]
        facts.update(order_id=m.get("order_id"), perm_id=m.get("perm_id"), status=m.get("status"))
        if m.get("client_id") != plan["client_ids"]["node"]:
            reasons.append("client_id_mismatch")
        if expected.get("perm_id") and m.get("perm_id") != expected["perm_id"]:
            reasons.append("perm_id_changed")
        if expected.get("order_id") is not None and m.get("order_id") != expected["order_id"]:
            reasons.append("order_id_changed")
        if m.get("status") not in WORKING_STATUSES:
            reasons.append("not_working_at_ib")
    return {"passed": not reasons, "reasons": reasons, **facts}


def adoption_verdict(expected: dict, views: list[dict], strategy_id: str) -> dict:
    """Step 3 restart reconciliation: after a fresh-process restart the node holds exactly one order
    of this run, R2, claimed by this strategy, open, and equal to what phase A placed."""
    reasons = []
    facts = {"run_orders_in_cache": len(views)}
    if len(views) != 1:
        reasons.append("not_exactly_one_run_order")
    match = [v for v in views if v.get("client_order_id") == expected.get("client_order_id")]
    if len(match) != 1:
        reasons.append("r2_not_in_cache")
        return {"passed": False, "reasons": reasons, **facts}
    v = match[0]
    # Phase A's own venue id, plus the forms IB itself listed for R2 at the after-A checkpoint: the
    # adapter moves from the raw orderId to PERM-<permId> once IB assigns one (client/common.py).
    known = {expected.get("venue_order_id"), *(expected.get("venue_order_ids") or [])} - {None}
    facts.update(status=v.get("status"), strategy_matches=v.get("strategy_id") == strategy_id,
                 venue_order_id_matches=v.get("venue_order_id") in known)
    if v.get("strategy_id") != strategy_id:
        reasons.append("r2_not_claimed_by_strategy")
    # PreSubmitted reconciles as SUBMITTED (parsing/execution.py MAP_ORDER_STATUS); both are live at IB.
    if v.get("status") not in ("ACCEPTED", "SUBMITTED"):
        reasons.append("r2_not_working")
    if v.get("venue_order_id") not in known:
        reasons.append("r2_venue_order_id_changed")
    if (v.get("side"), v.get("time_in_force")) != ("BUY", "DAY"):
        reasons.append("r2_side_or_tif_changed")
    if _dec(v.get("quantity") or 0) != _dec(expected.get("quantity") or 0):
        reasons.append("r2_quantity_changed")
    if v.get("price") is None or _dec(v["price"]) != _dec(expected.get("price") or 0):
        reasons.append("r2_price_changed")
    return {"passed": not reasons, "reasons": reasons, **facts}


def _state_facts(snapshot: dict | None, prefix: str) -> dict:
    open_orders, positions = _listed(snapshot, "open_orders"), _listed(snapshot, "positions")
    return {"observer_status": (snapshot or {}).get("status"), "open_orders": len(open_orders),
            "positions": len(positions), "run_open_orders": [order_ref_client_id(o.get("order_ref")) for o in open_orders
                                                              if is_run_order(o, prefix)],
            "foreign_open_orders": len([o for o in open_orders if not is_run_order(o, prefix)])}


def after_a_verdict(plan: dict, snapshot: dict | None, prefix: str, carry: dict) -> dict:
    """Between phase A and the restart: R2 alone works at IB on the node's client id; no position."""
    facts = _state_facts(snapshot, prefix)
    reasons = [] if facts["observer_status"] == "passed" else [f"observer_{facts['observer_status']}"]
    if facts["positions"]:
        reasons.append("positions_present")
    if facts["foreign_open_orders"]:
        reasons.append("foreign_open_orders")
    r2 = (carry or {}).get("R2") or {}
    ours = [o for o in _listed(snapshot, "open_orders") if is_run_order(o, prefix)]
    if len(ours) != 1 or order_ref_client_id(ours[0].get("order_ref")) != r2.get("client_order_id"):
        reasons.append("r2_not_the_only_open_order_of_the_run")
    else:
        m = ours[0]
        facts.update(r2_perm_id=m.get("perm_id"), r2_order_id=m.get("order_id"), r2_status=m.get("status"),
                     r2_venue_order_ids=sorted(venue_ids_for(m)))
        if m.get("client_id") != plan["client_ids"]["node"]:
            reasons.append("r2_client_id_mismatch")
        if r2.get("venue_order_id") not in venue_ids_for(m):
            reasons.append("r2_venue_order_id_mismatch")
        if m.get("status") not in WORKING_STATUSES:
            reasons.append("r2_not_working_at_ib")
    return {"passed": not reasons, "reasons": reasons, **facts}


def _completed_facts(snapshot: dict | None, prefix: str, ids: dict, probes) -> tuple[dict, list]:
    """IB's own completed-orders list must show R1 and R2 cancelled. That makes the list evidence
    that it covers this run, so a probe order missing from it (and from the open orders and the
    executions) never reached IB; an empty or partial list fails instead of passing vacuously."""
    completed = _listed(snapshot, "completed_orders")
    ours = {order_ref_client_id(o.get("order_ref")): o.get("status") for o in completed if is_run_order(o, prefix)}
    listed_r = all(ours.get(ids[s]) in CANCELLED_STATUSES for s in ("R1", "R2"))
    reasons = [] if listed_r else ["completed_orders_do_not_show_r1_r2_cancelled"]
    for s in probes:
        if ids[s] in ours:
            reasons.append(f"{s.lower()}_reached_ib")
    return {"run_completed_orders": ours, "r1_r2_listed_cancelled": listed_r}, reasons


def after_b_verdict(plan: dict, snapshot: dict | None, prefix: str, ids: dict) -> dict:
    facts = _state_facts(snapshot, prefix)
    reasons = [] if facts["observer_status"] == "passed" else [f"observer_{facts['observer_status']}"]
    if facts["open_orders"]:
        reasons.append("open_orders_present")
    if facts["positions"]:
        reasons.append("positions_present")
    extra, more = _completed_facts(snapshot, prefix, ids, ("P1",))
    facts.update(extra)
    reasons += more
    return {"passed": not reasons, "reasons": reasons, **facts}


def final_verdict(plan: dict, snapshot: dict | None, prefix: str, ids: dict) -> dict:
    """End of run: flat, no open order, no execution of this run, and neither probe order at IB."""
    facts = _state_facts(snapshot, prefix)
    status_ok = facts["observer_status"] == "passed"
    reasons = [] if status_ok else [f"observer_{facts['observer_status']}"]
    if facts["open_orders"]:
        reasons.append("open_orders_present")
    if facts["positions"]:
        reasons.append("positions_present")
    run_execs = [e for e in _listed(snapshot, "executions") if is_run_order(e, prefix)]
    facts["run_executions"] = len(run_execs)
    if run_execs:
        reasons.append("executions_of_the_run")
    extra, more = _completed_facts(snapshot, prefix, ids, ("P1", "P2"))
    facts.update(extra)
    reasons += more
    facts["flat"] = status_ok and not facts["open_orders"] and not facts["positions"]
    return {"passed": not reasons, "reasons": reasons, **facts}


# --------------------------------------------------------------------------- phase context (pure)


def new_run_prefix(now_utc: datetime) -> str:
    return f"NTA-{now_utc:%m%d-%H%M%S}-{secrets.token_hex(3)}"


class PhaseContext:
    """Case state, orders, events and probes of one phase. Pure Python; the Nautilus strategy
    calls into it and the phase result is built from it. Compatible with the shared
    NodeStopControl (node, notes, errors, started, finished, cleanup, start_cleanup)."""

    def __init__(self, plan: dict, prefix: str, phase: str, carry: dict | None = None, orders_created: int = 0,
                 server_minus_local_s: float = 0.0):
        self.plan, self.prefix, self.phase = plan, prefix, phase
        self.carry = carry or {}
        self.server_minus_local_s = server_minus_local_s or 0.0
        b = plan["bounds"]
        self.budget = PO.OrderBudget(b["max_orders"], b["max_quantity_per_order"], b["max_notional_per_order_usd"])
        self.budget.used = int(orders_created)  # the four-order budget spans all three phases
        self.on_change = None
        self.cases = {cid: {"id": cid, "name": CASE_NAMES[cid], "outcome": "not_run", "reason": None,
                            "started_at": None, "ended_at": None} for cid in PHASE_CASES[phase]}
        self.orders: dict[str, dict] = {}
        self.events: list[dict] = []
        self.fills: list[dict] = []
        self.alerts: list[dict] = []
        self.current: str | None = None
        self.started = False
        self.finished = False
        self.cleanup: dict | None = None
        self.carry_out: dict | None = None
        self.reconnect: dict | None = None
        self.kill_switch: dict | None = None
        self.notes: list[str] = []
        self.errors: list[str] = []
        self.unconfirmed: list[dict] = []
        self.duplicates: list[dict] = []
        self.cancel_requests: list[dict] = []
        self.node: dict = {"built": False, "strategy_started": False, "stop_requested_by": None}

    def changed(self):
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception as exc:  # noqa: BLE001 - persistence must never interrupt the phase
            if len(self.errors) < 20:
                self.errors.append(redact(f"provisional phase result write failed: {type(exc).__name__}")[:200])

    def client_order_id(self, suffix: str) -> str:
        return f"{self.prefix}-{suffix}"

    def suffix_for(self, client_order_id: str) -> str | None:
        for s in ORDER_SUFFIXES:
            if client_order_id == self.client_order_id(s):
                return s
        return None

    def carry_keep(self) -> set:
        """Orders deliberately left working: R2, only once phase A completed."""
        if self.phase == "A" and self.carry_out:
            return {self.client_order_id("R2")}
        return set()

    def begin(self, cid: str, now_ns: int):
        self.current = cid
        self.cases[cid].update(outcome="running", started_at=PO.ns_to_iso(now_ns))
        self.changed()

    def pass_case(self, cid: str, now_ns: int, **fields):
        c = self.cases[cid]
        c.update(fields)
        c.update(outcome="passed", ended_at=PO.ns_to_iso(now_ns))
        self.changed()

    def end_case(self, cid: str, outcome: str, reason: str, now_ns: int):
        c = self.cases[cid]
        if c["outcome"] in ("passed", "failed", "incomplete"):
            return
        c.update(outcome=outcome, reason=redact(reason)[:200], ended_at=PO.ns_to_iso(now_ns))
        self.changed()

    def all_passed(self) -> bool:
        return all(c["outcome"] == "passed" for c in self.cases.values())

    def register_order(self, suffix: str, client_order_id: str, price, submit_n: int, now_ns: int):
        self.orders[suffix] = {"client_order_id": client_order_id, "side": "BUY", "quantity": "1",
                               "limit_price": str(price), "notional_usd": str(_dec(price)), "time_in_force": "DAY",
                               "order_number": submit_n, "created_at": PO.ns_to_iso(now_ns)}
        self.changed()

    def record_event(self, suffix: str, event_type: str, ts_event_ns, ts_init_ns=None, **extra):
        entry = {"order": suffix, "type": event_type, "ts_event": PO.ns_to_iso(ts_event_ns),
                 "ts_init": PO.ns_to_iso(ts_init_ns), "case": self.current}
        entry.update({k: (redact(v)[:200] if isinstance(v, str) else v) for k, v in extra.items()})
        self.events.append(entry)
        self.changed()

    def add_fill(self, suffix: str, price, qty, ts_event_ns):
        self.fills.append({"order": suffix, "price": str(price), "quantity": str(qty), "ts_event": PO.ns_to_iso(ts_event_ns)})
        self.changed()

    def start_cleanup(self, reason: str, kind: str, now_ns: int):
        self.end_case(self.current or PHASE_CASES[self.phase][0], kind, reason, now_ns)
        self.cleanup = {"triggered": True, "reason": redact(reason)[:200], "kind": kind, "started_at": PO.ns_to_iso(now_ns),
                        "deadline_ns": now_ns + int(self.plan["timeouts"]["cleanup_seconds"] * 1e9),
                        "ended_at": None, "end_reason": None}
        self.changed()

    def summary(self) -> dict:
        cleanup = dict(self.cleanup) if self.cleanup else {"triggered": False}
        cleanup.pop("deadline_ns", None)
        return {"phase": self.phase, "run_prefix": self.prefix, "cases": [self.cases[c] for c in PHASE_CASES[self.phase]],
                "orders": self.orders, "events": self.events, "fills": self.fills, "alerts": self.alerts,
                "reconnect": self.reconnect, "kill_switch": self.kill_switch, "carry_out": self.carry_out,
                "orders_created": self.budget.used, "max_orders": self.budget.max_orders, "cleanup": cleanup,
                "unconfirmed_events": self.unconfirmed, "duplicate_events": self.duplicates,
                "cancel_requests": self.cancel_requests, "node": self.node, "notes": self.notes, "errors": self.errors}


def phase_status(ctx: PhaseContext, *, error: bool = False, interrupted: bool = False) -> str:
    if ctx.fills:
        return "cleanup_required"  # an unexpected position; the runner never flattens
    if ctx.all_passed() and not error and not interrupted and ctx.node.get("finish_reason") == "phase_complete":
        return "passed"
    if any(c["outcome"] == "failed" for c in ctx.cases.values()):
        return "failed"
    return "incomplete"


def order_view(order) -> dict:
    """A plain view of a Nautilus order (for adoption checks and the receipt)."""
    price = getattr(order, "price", None)
    # 1.231.0 enums print as integers (str(OrderSide.BUY) == "1"); the *_string() helpers name them.
    return {"client_order_id": order.client_order_id.value, "strategy_id": str(order.strategy_id),
            "status": order.status_string(), "is_open": bool(order.is_open),
            "venue_order_id": None if order.venue_order_id is None else order.venue_order_id.value,
            "side": order.side_string(), "quantity": str(order.quantity),
            "price": None if price is None else str(price), "time_in_force": order.tif_string()}


# --------------------------------------------------------------------------- Nautilus strategy (lazy)


def build_strategy_class():
    """Define the phase strategy against the installed NautilusTrader 1.231.0 API."""
    from nautilus_trader.adapters.interactive_brokers.common import IBOrderTags
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.events import (OrderAccepted, OrderCanceled, OrderCancelRejected, OrderDenied,
                                              OrderExpired, OrderFilled, OrderRejected, OrderSubmitted)
    from nautilus_trader.model.identifiers import ClientOrderId, InstrumentId
    from nautilus_trader.model.objects import Price
    from nautilus_trader.trading.strategy import Strategy

    TERMINAL = (OrderCanceled, OrderRejected, OrderDenied, OrderExpired)

    class AcceptanceStrategy(Strategy):
        def __init__(self, config, ctx: PhaseContext, hooks):
            super().__init__(config)
            self.ctx, self.hooks = ctx, hooks
            self._iid = InstrumentId.from_str(ctx.plan["instrument"]["nautilus_instrument_id"])
            self._quote = None  # (bid Decimal, ask Decimal, ts_event_ns)
            self._waiting_quote = False
            self._step_deadline_ns = 0
            self._cancels: dict = {}
            self._terminal: dict = {}
            self._last_submit_ns = None
            self._window_end = None
            self._in_cleanup = False
            self._probe = None
            self._first_case = None
            self._a3: dict = {}
            self._b2: dict = {}

        # ---------------------------------------------------------- lifecycle
        def on_start(self):
            ctx = self.ctx
            if ctx.finished or ctx.cleanup:
                ctx.notes.append("strategy started after the phase was stopped; no case started")
                return
            ctx.started = True
            ctx.node.update(strategy_started=True, strategy_started_at=PO.ns_to_iso(self._now()), strategy_id=str(self.id))
            try:
                instrument = self.cache.instrument(self._iid)
                if instrument is None:
                    self.abort("instrument_not_loaded", kind="failed")
                    return
                if instrument.price_increment != Price.from_str(ctx.plan["instrument"]["expected_price_increment"]):
                    self.abort("unexpected_price_increment", kind="failed")
                    return
                if ctx.phase == "A":
                    self.subscribe_quote_ticks(self._iid, params={"batch_quotes": False})
                # The first case begins on the first timer tick, not here: 1.231.0's
                # Strategy.handle_event drops every event while the strategy is not RUNNING
                # (trading/strategy.pyx:1917), so an order event raised inside on_start (a
                # synchronous OrderDenied, for one) would never reach on_order_event.
                self._first_case = PHASE_CASES[ctx.phase][0]
                self.clock.set_timer("ibla-watchdog", timedelta(seconds=1), callback=self._on_watchdog)
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def on_stop(self):
            # Runs before the kernel waits timeout_post_stop and disconnects, so cancels still reach
            # the adapter. R2 is kept only when phase A completed (ctx.carry_keep).
            ctx = self.ctx
            if not ctx.finished:
                ctx.notes.append("strategy stopped before the phase finished")
            try:
                sent = self._sweep_cancels("on_stop", force=True)
                if sent:
                    ctx.notes.append(f"on_stop sent a final cancel for {sent} open order(s) of this run")
            except Exception as exc:  # noqa: BLE001
                ctx.errors.append(redact(f"on_stop cancel sweep: {type(exc).__name__}: {exc}")[:200])

        # ---------------------------------------------------------- helpers
        def _now(self) -> int:
            return self.clock.timestamp_ns()

        def _fault(self, exc):
            self.ctx.errors.append(redact(f"{type(exc).__name__}: {exc}")[:200])
            self.abort(f"exception_{type(exc).__name__}", kind="failed")

        def _order(self, suffix):
            return self.cache.order(ClientOrderId(self.ctx.client_order_id(suffix)))

        def _run_orders(self):
            """Every order of this run in the cache, including one adopted by reconciliation."""
            return [o for o in self.cache.orders(instrument_id=self._iid)
                    if o.client_order_id.value.startswith(self.ctx.prefix + "-")]

        def _outstanding(self, exclude=()):
            return [o for o in self._run_orders() if not o.is_closed and o.client_order_id.value not in exclude]

        def _fresh_quote(self):
            if self._quote is None:
                return None
            bid, ask, ts = self._quote
            d = self.ctx.plan["data"]
            age = PO.quote_age_seconds(self._now() / 1e9, self.ctx.server_minus_local_s, ts / 1e9)
            if not PO.quote_is_valid(bid, ask) or not PO.quote_is_fresh(age, d["quote_max_age_seconds"],
                                                                        d["clock_resolution_tolerance_seconds"]):
                return None
            return bid, ask, age

        def _inside_window(self) -> bool:
            return self._window_end is None or self.clock.utc_now() <= self._window_end

        def _begin(self, cid: str):
            t = self.ctx.plan["timeouts"]
            self.ctx.begin(cid, self._now())
            budget = t["per_step_seconds"] + (t["reconnect_seconds"] if cid == "A3" else 0)
            self._step_deadline_ns = self._now() + int(budget * 1e9)
            getattr(self, f"_start_{cid}")()

        def _pass(self, cid: str, **fields):
            self.ctx.pass_case(cid, self._now(), **fields)
            order = PHASE_CASES[self.ctx.phase]
            i = order.index(cid)
            if i + 1 < len(order):
                self._begin(order[i + 1])
            else:
                if self.ctx.phase == "A":
                    self.ctx.carry_out = self._carry_record()
                self._finish("phase_complete")

        def _carry_record(self) -> dict:
            out = {}
            for s in ("R1", "R2"):
                o = self._order(s)
                if o is None:
                    continue
                venue = None if o.venue_order_id is None else o.venue_order_id.value
                out[s] = {"client_order_id": o.client_order_id.value, "venue_order_id": venue,
                          "perm_id": perm_from_venue(venue), "price": str(o.price), "quantity": str(o.quantity),
                          "side": "BUY", "time_in_force": "DAY"}
            return out

        # ---------------------------------------------------------- order creation (the only factory call)
        def _order_tags(self):
            return [IBOrderTags(outsideRth=True).value] if self.ctx.plan["session"].get("outside_rth") else None

        def _new_resting_order(self, price, qty, suffix):
            return self.order_factory.limit(
                instrument_id=self._iid, order_side=OrderSide.BUY, quantity=qty, price=price,
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(self.ctx.client_order_id(suffix)),
                tags=self._order_tags())

        def _submit(self, suffix: str, price_dec, *, kill_switch_probe: bool = False):
            """Refuse while the latch is engaged (except the two kill-switch probes, which test the
            RiskEngine itself), check spacing, reserve budget, then create and submit."""
            now = self._now()
            if suffix not in ORDER_SUFFIXES or (suffix in ("P1", "P2")) is not kill_switch_probe:
                raise BudgetError(f"order {suffix} is not a planned order of this path")
            if not kill_switch_probe and self.hooks.kill_switch_engaged():
                raise BudgetError("kill switch engaged: no new order")
            if not PO.spacing_ok(now, self._last_submit_ns, self.ctx.plan["bounds"]["min_submit_spacing_seconds"]):
                raise BudgetError("min_submit_spacing_seconds not elapsed")
            price_dec = _dec(price_dec)
            b = self.ctx.plan["bounds"]
            if price_dec <= 0 or price_dec > _dec(b["max_notional_per_order_usd"]):
                raise BudgetError(f"price {price_dec} outside (0, max_notional_per_order_usd]")
            n = self.ctx.budget.reserve(suffix, 1, price_dec)  # raises BudgetError before any order exists
            instrument = self.cache.instrument(self._iid)
            order = self._new_resting_order(instrument.make_price(float(price_dec)), instrument.make_qty(1), suffix)
            cid = order.client_order_id.value
            self.ctx.register_order(suffix, cid, price_dec, n, self._now())
            self._last_submit_ns = now
            self.submit_order(order)
            return cid

        def _spacing_ok(self) -> bool:
            return PO.spacing_ok(self._now(), self._last_submit_ns, self.ctx.plan["bounds"]["min_submit_spacing_seconds"])

        # ---------------------------------------------------------- cancels (the only cancel call site)
        def _send_cancel(self, order, where: str):
            key = order.client_order_id.value
            st = self._cancels.setdefault(key, {"attempts": 0, "last_ns": None})
            st["attempts"] += 1
            st["last_ns"] = self._now()
            self.ctx.cancel_requests.append({"order": self.ctx.suffix_for(key), "where": where, "attempt": st["attempts"],
                                             "status": order.status_string(), "at": PO.ns_to_iso(st["last_ns"])})
            self.ctx.changed()
            self.cancel_order(order)

        def _sweep_cancels(self, where: str, force: bool = False) -> int:
            """Cancel every open order of this run that IB has acknowledged, except R2 once phase A
            completed. Re-sends are bounded; an order in PENDING_CANCEL is left for the runner's
            ibapi cleanup (Strategy.cancel_order refuses those, and cancel_all_orders would touch
            every SPY order in the cache)."""
            b, t = self.ctx.plan["bounds"], self.ctx.plan["timeouts"]
            now, sent = self._now(), 0
            for o in self._outstanding(exclude=self.ctx.carry_keep()):
                if o.venue_order_id is None or o.is_pending_cancel:
                    continue
                st = self._cancels.get(o.client_order_id.value, {"attempts": 0, "last_ns": None})
                action = PO.cancel_decision(False, st["attempts"], st["last_ns"], now, t["recancel_interval_seconds"],
                                            b["max_cancel_attempts_per_order"], force=force)
                if action == "cancel":
                    self._send_cancel(o, where)
                    sent += 1
            return sent

        # ---------------------------------------------------------- phase A
        def _start_A1(self):
            self._waiting_quote = True
            self._try_quote_step()

        _start_A4 = _start_A1

        def _try_quote_step(self):
            ctx = self.ctx
            if ctx.cleanup or ctx.finished or not self._waiting_quote:
                return
            q = self._fresh_quote()
            if q is None:
                return
            if not self._inside_window():
                self.abort("session_window_closed", kind="incomplete")
                return
            if not self._spacing_ok():
                return
            bid, ask, age = q
            b = ctx.plan["bounds"]
            price = PO.resting_buy_price(bid, b["resting_fraction_of_bid"], b["resting_price_floor_usd"])
            if price > _dec(b["max_notional_per_order_usd"]) or price >= bid:
                self.abort(f"{ctx.current}_price_not_resting_within_notional", kind="failed")
                return
            self._waiting_quote = False
            ctx.cases[ctx.current]["quote"] = {"bid": str(bid), "ask": str(ask), "age_s": age}
            try:
                self._submit("R1" if ctx.current == "A1" else "R2", price)
            except BudgetError as exc:
                self.abort(f"budget: {exc}", kind="failed")

        def _node_view(self, suffix: str) -> dict:
            o = self._order(suffix)
            return {"adapter": self.hooks.adapter_state(), "r1_open": bool(o is not None and o.is_open),
                    "r1_venue_order_id": None if o is None or o.venue_order_id is None else o.venue_order_id.value}

        def _start_A2(self):
            self._probe = self.hooks.start_probe("ownership", self.ctx.client_order_id("R1"))

        def _poll_A2(self):
            if self._probe is None or not self._probe.done():
                return
            verdict = ownership_verdict(self.ctx.plan, self._probe.result(), self._node_view("R1"),
                                        self.ctx.client_order_id("R1"))
            self._probe = None
            self.ctx.cases["A2"]["ownership"] = verdict
            if verdict["passed"]:
                self._pass("A2")
            else:
                self.abort("A2_ownership: " + ",".join(verdict["reasons"]), kind="failed")

        def _start_A3(self):
            ctx, r1 = self.ctx, self._order("R1")
            if r1 is None or not r1.is_open:
                self.abort("A3_r1_not_open_before_fault", kind="failed")
                return
            now = self._now()
            self._a3 = {"stage": "down_wait", "fault_ns": now, "terminal_before": dict(self._terminal),
                        "deadline_ns": now + int(ctx.plan["timeouts"]["reconnect_seconds"] * 1e9)}
            ctx.reconnect = {"adapter_before": self.hooks.adapter_state(), "fault_at": PO.ns_to_iso(now)}
            try:
                ctx.reconnect["fault"] = self.hooks.inject_disconnect()
            except Exception as exc:  # noqa: BLE001
                self.abort(f"A3_fault_injection_failed: {type(exc).__name__}", kind="incomplete")

        def _poll_A3(self):
            ctx, a3, now = self.ctx, self._a3, self._now()
            stage = a3.get("stage")
            state = self.hooks.adapter_state()
            up = bool(state.get("ib_connected") and state.get("ready") and state.get("socket_connected"))
            # The adapter itself must have recorded a disconnection after the fault
            # (_last_disconnection_ns, set in _handle_disconnection); a transient not-ready alone
            # is no evidence that it saw the dead socket and reconnected.
            recorded = (state.get("last_disconnection_ns") or 0) >= a3["fault_ns"]
            if stage == "down_wait":
                if not state.get("socket_connected") or not state.get("ib_connected") or recorded:
                    a3["stage"] = "up_wait"
                    ctx.reconnect["down_seen_at"] = PO.ns_to_iso(now)
                elif now > a3["deadline_ns"]:
                    self.abort("A3_disconnect_not_detected", kind="incomplete")
                    return
                stage = a3["stage"]
            if stage == "up_wait":
                if not up or not recorded:
                    if now > a3["deadline_ns"]:
                        self.abort("A3_reconnect_timeout" if not up else "A3_disconnect_not_recorded", kind="incomplete")
                    return
                ctx.reconnect.update(reconnected_at=PO.ns_to_iso(now), adapter_after=state,
                                     seconds_to_reconnect=round((now - a3["fault_ns"]) / 1e9, 3))
                node_id = ctx.plan["client_ids"]["node"]
                if state.get("client_id") != node_id or state.get("fetch_all_open_orders"):
                    self.abort("A3_client_id_changed_on_reconnect", kind="failed")
                    return
                r1 = self._order("R1")
                if r1 is None or not r1.is_open or ctx.client_order_id("R1") in self._terminal:
                    self.abort("A3_r1_closed_during_reconnect", kind="failed")
                    return
                a3["stage"] = "observe"
                self._step_deadline_ns = now + int(ctx.plan["timeouts"]["per_step_seconds"] * 1e9)
                self._probe = self.hooks.start_probe("still_open", ctx.client_order_id("R1"))
                return
            if stage == "observe" and self._probe is not None and self._probe.done():
                own = ctx.cases["A2"].get("ownership") or {}
                verdict = still_open_verdict(ctx.plan, self._probe.result(), ctx.client_order_id("R1"),
                                             {"perm_id": own.get("perm_id"), "order_id": own.get("order_id")})
                self._probe = None
                ctx.reconnect["observer_after"] = verdict
                if not verdict["passed"]:
                    self.abort("A3_after_reconnect: " + ",".join(verdict["reasons"]), kind="failed")
                    return
                a3["stage"] = "cancel_sent"
                self._send_cancel(self._order("R1"), "A3")

        # ---------------------------------------------------------- phase B
        def _start_B1(self):
            ctx = self.ctx
            views = [order_view(o) for o in self._run_orders()]
            verdict = adoption_verdict((ctx.carry or {}).get("R2") or {}, views, str(self.id))
            verdict["orders"] = views
            ctx.cases["B1"]["adoption"] = verdict
            if verdict["passed"]:
                self._pass("B1")
            else:
                self.abort("B1_adoption: " + ",".join(verdict["reasons"]), kind="failed")

        def _start_B2(self):
            ctx = self.ctx
            self._b2 = {"p1_denied": None, "r2_canceled": False}
            try:
                engaged = self.hooks.engage_kill_switch("acceptance case B2")
            except Exception as exc:  # noqa: BLE001
                self.abort(f"B2_engage_failed: {type(exc).__name__}", kind="failed")
                return
            ctx.kill_switch = {"latch": engaged, "trading_state_after_engage": self.hooks.trading_state()}
            if ctx.kill_switch["trading_state_after_engage"] != "HALTED":
                self.abort("B2_risk_engine_not_halted", kind="failed")
                return
            # The kill-switch disposition: cancel every open order of the run, retain none.
            ctx.kill_switch["cancels_sent"] = self._sweep_cancels("kill_switch")
            try:
                self._submit("P1", ctx.carry["R2"]["price"], kill_switch_probe=True)
            except (BudgetError, KeyError, TypeError) as exc:
                self.abort(f"B2_probe_not_sent: {exc}", kind="failed")

        def _check_B2(self):
            b2 = self._b2
            if b2.get("p1_denied") is None or not b2.get("r2_canceled"):
                return
            if HALTED_DENIAL not in b2["p1_denied"]:
                self.abort(f"B2_p1_denied_for_another_reason: {b2['p1_denied']}", kind="failed")
                return
            self._pass("B2", p1_denied_reason=b2["p1_denied"])

        # ---------------------------------------------------------- phase C
        def _start_C1(self):
            ctx = self.ctx
            state, latch = self.hooks.trading_state(), self.hooks.kill_switch_engaged()
            open_run = [order_view(o) for o in self._outstanding()]
            ctx.kill_switch = {"trading_state_at_start": state, "latch_engaged_at_start": latch,
                               "open_run_orders_at_start": open_run}
            if state != "HALTED" or not latch:
                self.abort("C1_kill_switch_not_in_force_after_restart", kind="failed")
                return
            if open_run:
                self.abort("C1_open_order_of_the_run_after_restart", kind="failed")
                return
            try:
                self._submit("P2", ctx.carry["R2"]["price"], kill_switch_probe=True)
            except (BudgetError, KeyError, TypeError) as exc:
                self.abort(f"C1_probe_not_sent: {exc}", kind="failed")

        # ---------------------------------------------------------- events
        def on_quote_tick(self, tick):
            try:
                self._quote = (Decimal(str(tick.bid_price)), Decimal(str(tick.ask_price)), tick.ts_event)
                if self._waiting_quote:
                    self._try_quote_step()
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def on_order_event(self, event):
            try:
                self._handle_order_event(event)
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def _handle_order_event(self, event):
            ctx = self.ctx
            cid = event.client_order_id.value
            suffix = ctx.suffix_for(cid)
            if suffix is None:
                return
            etype = type(event).__name__
            terminal = isinstance(event, TERMINAL)
            extra = {}
            if isinstance(event, (OrderRejected, OrderDenied, OrderCancelRejected)):
                extra["reason"] = str(event.reason)
            if isinstance(event, OrderAccepted):
                extra["venue_order_id"] = None if event.venue_order_id is None else event.venue_order_id.value
            reconciliation = bool(getattr(event, "reconciliation", False))
            if reconciliation:
                extra["reconciliation"] = True
            # Engine-generated closes are not an IB status callback and never pass a case.
            unconfirmed = terminal and not isinstance(event, OrderDenied) and reconciliation
            duplicate = terminal and cid in self._terminal
            if duplicate:
                extra["duplicate_ignored"] = True
            ctx.record_event(suffix, etype, event.ts_event, event.ts_init, **extra)
            if duplicate:
                ctx.duplicates.append({"order": suffix, "type": etype, "first": self._terminal[cid]})
                return
            if terminal:
                self._terminal[cid] = etype
            if unconfirmed:
                ctx.unconfirmed.append({"order": suffix, "type": etype, "case": ctx.current})
            if isinstance(event, OrderFilled):
                ctx.add_fill(suffix, Decimal(str(event.last_px)), Decimal(str(event.last_qty)), event.ts_event)
                if not ctx.cleanup and not ctx.finished:
                    self.abort(f"{suffix}_unexpected_fill", kind="failed")
                return
            if ctx.cleanup or ctx.finished:
                if not ctx.finished:
                    self._cleanup_tick()
                return
            self._on_case_event(suffix, event, unconfirmed, extra.get("reason", ""))

        def _on_case_event(self, suffix, event, unconfirmed, reason):
            cur = self.ctx.current
            if unconfirmed:
                self.abort(f"{cur}_{suffix}_unconfirmed_{type(event).__name__}", kind="incomplete")
                return
            if suffix in ("P1", "P2"):
                if isinstance(event, OrderDenied) and (cur, suffix) in (("B2", "P1"), ("C1", "P2")):
                    if cur == "B2":
                        self._b2["p1_denied"] = reason
                        self._check_B2()
                    elif HALTED_DENIAL in reason:
                        self._pass("C1", p2_denied_reason=reason)
                    else:
                        self.abort(f"C1_p2_denied_for_another_reason: {reason}", kind="failed")
                elif isinstance(event, (OrderSubmitted, OrderAccepted, OrderRejected)):
                    self.abort(f"{cur}_{suffix}_passed_the_kill_switch_{type(event).__name__}", kind="failed")
                return
            if isinstance(event, (OrderRejected, OrderDenied, OrderExpired)):
                self.abort(f"{cur}_{suffix}_{type(event).__name__}: {reason}", kind="failed")
                return
            if isinstance(event, OrderCancelRejected):
                self.abort(f"{cur}_{suffix}_cancel_rejected: {reason}", kind="failed")
                return
            if isinstance(event, OrderAccepted):
                if (cur, suffix) in (("A1", "R1"), ("A4", "R2")):
                    self._pass(cur, venue_order_id_present=event.venue_order_id is not None)
                return
            if isinstance(event, OrderCanceled):
                if cur == "A3" and suffix == "R1" and self._a3.get("stage") == "cancel_sent":
                    self._pass("A3")
                elif cur == "B2" and suffix == "R2":
                    self._b2["r2_canceled"] = True
                    self._check_B2()
                else:
                    self.abort(f"{cur}_{suffix}_canceled_unexpectedly", kind="failed")

        # ---------------------------------------------------------- watchdog, abort and cleanup
        def _on_watchdog(self, _event):
            try:
                ctx = self.ctx
                if ctx.finished:
                    return
                if ctx.cleanup:
                    self._cleanup_tick()
                    return
                if self._first_case is not None:
                    cid, self._first_case = self._first_case, None
                    self._begin(cid)
                    return
                poll = getattr(self, f"_poll_{ctx.current}", None)
                if poll is not None:
                    poll()
                if self._waiting_quote:
                    self._try_quote_step()
                if not ctx.finished and not ctx.cleanup and self._now() > self._step_deadline_ns:
                    self.abort(f"{ctx.current}_step_timeout", kind="incomplete")
            except Exception as exc:  # noqa: BLE001
                self.ctx.errors.append(redact(f"watchdog {type(exc).__name__}: {exc}")[:200])
                if not self.ctx.cleanup:
                    self.abort("watchdog_exception", kind="failed")

        def abort(self, reason: str, kind: str = "incomplete"):
            """Stop the case sequence; cancel every open order of this run (nothing is carried
            over after a failure), then stop the node."""
            ctx = self.ctx
            if ctx.finished or ctx.cleanup:
                return
            self._waiting_quote = False
            ctx.carry_out = None
            ctx.start_cleanup(reason, kind, self._now())
            if not ctx.started:
                self._finish("aborted_before_start")
                return
            self._cleanup_tick()

        def _cleanup_tick(self):
            # Order events are delivered synchronously from submit/cancel calls; never re-enter.
            if self._in_cleanup or self.ctx.finished:
                return
            self._in_cleanup = True
            try:
                ctx = self.ctx
                if self._now() > ctx.cleanup["deadline_ns"]:
                    self._finish("cleanup_deadline")
                    return
                self._sweep_cancels("cleanup")
                if self._outstanding():
                    return
                if ctx.unconfirmed:
                    self._finish("cleanup_unconfirmed_order_state")
                elif ctx.fills:
                    self._finish("cleanup_position_left")
                else:
                    self._finish("cleanup_flat")
            finally:
                self._in_cleanup = False

        def _finish(self, reason: str):
            ctx = self.ctx
            if ctx.finished:
                return
            ctx.finished = True
            try:
                sent = self._sweep_cancels(f"finish:{reason}", force=True)
                if sent:
                    ctx.notes.append(f"finish ({reason}) sent a final cancel for {sent} open order(s) of this run")
            except Exception as exc:  # noqa: BLE001
                ctx.errors.append(redact(f"finish cancel sweep: {type(exc).__name__}: {exc}")[:200])
            if ctx.cleanup:
                ctx.cleanup.update(ended_at=PO.ns_to_iso(self._now()), end_reason=reason)
            ctx.node["finish_reason"] = reason
            ctx.changed()
            try:
                self.clock.cancel_timer("ibla-watchdog")
            except Exception:  # noqa: BLE001
                pass
            self.hooks.request_stop(f"strategy:{reason}")

    return AcceptanceStrategy


# --------------------------------------------------------------------------- live hooks and node phase


class ProbeHandle:
    """A read-only ibapi probe on a daemon thread; the strategy polls done() from its timer."""

    def __init__(self, fn):
        self._event = threading.Event()
        self._result = None

        def target():
            try:
                self._result = fn()
            except Exception as exc:  # noqa: BLE001
                self._result = {"error": redact(f"{type(exc).__name__}: {exc}")[:200]}
            finally:
                self._event.set()

        threading.Thread(target=target, daemon=True).start()

    def done(self) -> bool:
        return self._event.is_set()

    def result(self):
        return self._result


class LiveHooks:
    """What the strategy needs from outside Nautilus: the adapter's connection state, the fault
    injection, the independent ibapi probes, the kill switch and the stop request."""

    def __init__(self, plan: dict, port: int, node, ctx: PhaseContext, kill: KillSwitch, request_stop):
        self.plan, self.port, self.node, self.ctx, self.kill = plan, port, node, ctx, kill
        self.request_stop = request_stop

    def adapter(self):
        from nautilus_trader.adapters.interactive_brokers import factories

        return factories.IB_CLIENTS.get((self.plan["host"], self.port, self.plan["client_ids"]["node"]))

    def adapter_state(self) -> dict:
        c = self.adapter()
        if c is None:
            return {"present": False}
        return {"present": True, "client_id": c._client_id, "configured_client_id": c._configured_client_id,
                "ready": c.is_ready, "ib_connected": c._is_ib_connected.is_set(),
                "socket_connected": bool(c._eclient.isConnected()), "fetch_all_open_orders": c._fetch_all_open_orders,
                "client_id_collisions": c._client_id_collision_count, "last_disconnection_ns": c._last_disconnection_ns}

    def inject_disconnect(self) -> dict:
        """Shut the adapter's TWS socket down in both directions, as a network drop would; the
        adapter's own reader, watchdog and reconnect path then run unmodified (1.231.0
        client/client.py _run_connection_watchdog, client/connection.py _handle_reconnect)."""
        sock = self.adapter()._eclient.conn.socket
        sock.shutdown(socket.SHUT_RDWR)
        return {"kind": "socket_shutdown_rdwr", "at": utc_now_iso()}

    def start_probe(self, kind: str, client_order_id: str) -> ProbeHandle:
        plan, port, probe_s = self.plan, self.port, self.plan["timeouts"]["probe_seconds"]
        if kind == "ownership":
            def fn():
                contender = contender_probe(plan, port, wait_s=min(10.0, probe_s / 3))
                return {"contender": contender, "observer": observe(plan, port, include=("open_orders",),
                                                                    deadline_s=probe_s - min(10.0, probe_s / 3))}
        else:
            def fn():
                return observe(plan, port, include=("open_orders",), deadline_s=probe_s)
        return ProbeHandle(fn)

    def engage_kill_switch(self, reason: str) -> dict:
        from nautilus_trader.model.enums import TradingState

        record = self.kill.engage(self.ctx.prefix, reason)
        self.node.kernel.risk_engine.set_trading_state(TradingState.HALTED)
        alert = {"kind": "kill_switch_engaged", "at": record["engaged_at"], "reason": record["reason"]}
        self.ctx.alerts.append(alert)
        print(f"ALERT kill switch engaged for run {self.ctx.prefix}: {record['reason']}", file=sys.stderr, flush=True)
        return record

    def trading_state(self) -> str:
        from nautilus_trader.model.enums import trading_state_to_str

        return trading_state_to_str(self.node.kernel.risk_engine.trading_state)

    def kill_switch_engaged(self) -> bool:
        return self.kill.engaged()


def run_phase_node(plan: dict, account_id: str, port: int, ctx: PhaseContext, kill: KillSwitch, *, abort_at: float,
                   hard_stop_at: float, window_end, log_level: str = "WARNING") -> None:
    """Build and run one TradingNode phase with the 1.231.0 Python IB clients; returns when it stops."""
    from nautilus_trader.adapters.interactive_brokers.common import IB
    from nautilus_trader.adapters.interactive_brokers.factories import (InteractiveBrokersLiveDataClientFactory,
                                                                        InteractiveBrokersLiveExecClientFactory)
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.live.node import TradingNode
    from nautilus_trader.model.enums import TradingState
    from nautilus_trader.model.identifiers import InstrumentId

    t = plan["timeouts"]
    node = TradingNode(config=PO.build_node_config(plan, account_id, port, log_level))
    control = PO.NodeStopControl(ctx, plan, node=node)
    hooks = LiveHooks(plan, port, node, ctx, kill, control.request_stop)
    # After a restart the order of the run comes back from IB through reconciliation; the claim
    # assigns it to this strategy instead of EXTERNAL (live/execution_engine.py _generate_order).
    claims = [InstrumentId.from_str(plan["instrument"]["nautilus_instrument_id"])] if ctx.phase in ("B", "C") else None
    strategy = build_strategy_class()(StrategyConfig(order_id_tag="001", external_order_claims=claims), ctx, hooks)
    strategy._window_end = window_end
    control.abort = lambda reason: strategy.abort(reason, kind="incomplete")
    node.trader.add_strategy(strategy)
    node.add_data_client_factory(IB, InteractiveBrokersLiveDataClientFactory)
    node.add_exec_client_factory(IB, InteractiveBrokersLiveExecClientFactory)
    node.build()
    ctx.node["built"] = True
    if kill.engaged():
        # A restart honours the latch before anything can submit (risk/engine.pyx _execution_gateway).
        node.kernel.risk_engine.set_trading_state(TradingState.HALTED)
        ctx.node["risk_engine_halted_before_run"] = True
    loop = node.get_event_loop()
    control.loop = loop
    for sig in PO.RUN_SIGNALS:
        loop.add_signal_handler(sig, control.on_signal, sig)
    now = time.monotonic()
    loop.call_later(t["node_start_seconds"], control.on_node_start_deadline)
    loop.call_later(max(0.0, abort_at - now), control.on_abort_deadline)
    loop.call_later(max(0.0, hard_stop_at - now), control.on_hard_stop)
    try:
        node.run()
    finally:
        try:
            node.dispose()
        finally:
            PO.install_signal_handlers()


# --------------------------------------------------------------------------- receipts


def base_receipt(plan_path: Path, versions_fn=None) -> dict:
    v = (versions_fn or PO.versions)()
    return {"schema_version": SCHEMA_VERSION, "kind": RECEIPT_KIND, "generated_at": utc_now_iso(),
            "nautilus_trader_version": v.get("nautilus_trader"), "ibapi_version": v.get("ibapi"),
            "plan": plan_path.name, "plan_sha256": PO.sha256_file(plan_path) if plan_path.exists() else None,
            "runner_sha256": PO.sha256_file(RUNNER_PATH), "shared_harness_sha256": PO.sha256_file(SHARED_PATH),
            "evidence_class": "none", "gate_receipt": {"eligible": False}}


def write_json(path, receipt: dict, secret_values=(), quiet=False) -> int:
    code = PO._write_receipt_file(path, receipt, secret_values)
    if not quiet:
        print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code", "run_prefix")}))
    return code


def gate_receipt(plan: dict, receipt: dict, receipt_path: Path, prerequisites: list[dict], repo=None) -> dict:
    """The preregistered flip receipt; built only for a passed run."""
    phases = {p["phase"]: p for p in receipt.get("phases", [])}

    def case(phase, cid):
        for c in ((phases.get(phase) or {}).get("result") or {}).get("summary", {}).get("cases", []):
            if c["id"] == cid:
                return c
        return None

    return {"schema_version": 1, "kind": GATE_KIND, "status": "passed", "broker": "ibkr",
            "generated_at": utc_now_iso(), "evidence_class": "native_paper",
            "engine": {"nautilus_trader": receipt.get("nautilus_trader_version"), "ibapi": receipt.get("ibapi_version"),
                       "adapter": plan["engine"]["adapter"], "selected_by": plan["version_selection_record"]},
            "gateway": {"port": receipt.get("port"), "paper_account_prefix": plan["account_prefix"], "managed_accounts": 1},
            "run_prefix": receipt.get("run_prefix"),
            "steps": {"step_1_read_only": "prerequisite receipt plus this run's pre_check",
                      "step_2_client_id_ownership": case("A", "A2"),
                      "step_3_submit_cancel_fill_flatten": "prerequisite receipt (2026-09-23, C1-C4)",
                      "step_3_reconnect_with_open_order": case("A", "A3"),
                      "step_3_restart_reconciliation": case("B", "B1"),
                      "step_4_kill_switch": [case("B", "B2"), case("C", "C1")],
                      "step_4_final_disposition": receipt.get("final")},
            "steps_receipt": {"path": rel(receipt_path, repo), "sha256": PO.sha256_file(receipt_path)},
            "prerequisites": prerequisites,
            "runner_sha256": receipt.get("runner_sha256"), "shared_harness_sha256": receipt.get("shared_harness_sha256"),
            "plan": receipt.get("plan"), "plan_sha256": receipt.get("plan_sha256"),
            "qualification": plan["receipt"]["gate_receipt"]["qualification"]}


def run_status(phases: list[dict], checkpoints: dict, final: dict | None) -> str:
    if final is None or not final.get("flat"):
        return "cleanup_required"
    statuses = [((p.get("result") or {}).get("status")) for p in phases]
    if (statuses == ["passed"] * 3 and all(c.get("passed") for c in checkpoints.values()) and final.get("passed")
            and set(checkpoints) == {"after_A", "after_B"}):
        return "passed"
    if "failed" in statuses or any(c.get("passed") is False for c in checkpoints.values()) or final.get("passed") is False:
        return "failed"
    return "incomplete"


# --------------------------------------------------------------------------- parent: phases


class ParentSignals:
    """The parent never raises on a signal: it stops starting phases and forwards the signal to
    the running phase process (started in its own session, so a terminal signal reaches only the
    parent). A second signal is forwarded too, which forces the phase's node stop."""

    def __init__(self):
        self.received: list[str] = []
        self.child = None

    def handler(self, signum, frame):
        self.received.append(signal.Signals(signum).name)
        child = self.child
        if child is not None and child.poll() is None:
            try:
                child.send_signal(signal.SIGTERM)
            except OSError:
                pass

    def install(self):
        for sig in PO.RUN_SIGNALS:
            signal.signal(sig, self.handler)

    @property
    def interrupted(self) -> bool:
        return bool(self.received)


def spawn_phase(phase: str, manifest_path: Path, env: dict, deadline_s: float, signals: ParentSignals) -> dict:
    """Run one phase in a fresh process and wait for it, bounded by its deadline plus a grace."""
    proc = subprocess.Popen([sys.executable, str(RUNNER_PATH), "phase", phase, "--manifest", str(manifest_path)],
                            env=env, start_new_session=True)
    signals.child = proc
    terminated_at = None
    out = {"terminated": False, "killed": False}
    try:
        end = time.monotonic() + deadline_s + PHASE_GRACE_SECONDS
        while True:
            try:
                out["exit_code"] = proc.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                now = time.monotonic()
                if terminated_at is None and now > end:
                    proc.send_signal(signal.SIGTERM)
                    terminated_at, out["terminated"] = now, True
                elif terminated_at is not None and now > terminated_at + TERMINATE_GRACE_SECONDS:
                    proc.kill()
                    out["killed"] = True
                    out["exit_code"] = proc.wait()
                    break
    finally:
        signals.child = None
    return out


def read_phase_result(path: Path, prefix: str) -> dict | None:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if data.get("kind") != PHASE_KIND or data.get("run_prefix") != prefix:
        return None
    return data


def order_ids(prefix: str) -> dict:
    return {s: f"{prefix}-{s}" for s in ORDER_SUFFIXES}


# --------------------------------------------------------------------------- CLI: preflight and run


def _refuse(receipt: dict, path, status: str, secret_values=(), **fields) -> int:
    """Nothing of this run was placed on these paths, so an unwritable receipt only loses the record."""
    receipt.update(status=status, **fields)
    try:
        return write_json(path, receipt, secret_values)
    except OSError as exc:
        code = PO.exit_code_for(status)
        print(json.dumps({"status": status, "exit_code": code, "receipt_written": False,
                          "error": redact(f"{type(exc).__name__}: {exc}")[:200]}))
        return code


def _session_sessions(plan: dict, pre: dict, now: datetime):
    """Today's contract sessions (liquidHours or tradingHours per plan); None when unknown."""
    field = plan["session"].get("contract_hours_field", "liquidHours")
    hours = pre.get("trading_hours" if field == "tradingHours" else "liquid_hours") or ""
    tz_name = pre.get("time_zone_id") or plan["session"]["timezone"]
    local_day = now.astimezone(ZoneInfo(plan["session"]["timezone"])).date()
    return field, bool(hours), PO.parse_liquid_hours(hours, tz_name, local_day)


def _checks_before_orders(a, plan: dict, receipt: dict, *, check_fn, contender_fn, now_fn, t0):
    """The read-only gate shared by preflight and run. Returns (status, account, window_end)."""
    now = now_fn()
    ok, why = PO.rth_check(now, plan)
    receipt["session_check"] = {"fixed_window": why}
    if not ok:
        return "refused_outside_rth", None, None
    pre, account = check_fn(plan, a.port, with_session=True)
    receipt["pre_check"] = PO._sanitized_check(pre)
    if pre["status"] == "not_connected":
        return "not_connected", None, None
    if pre["status"] != "passed" or not account or not account.startswith(plan["account_prefix"]):
        return (pre["status"] if pre["status"].startswith("refused_") else "refused_check_not_passed"), account, None
    now = now_fn()
    field, present, sessions = _session_sessions(plan, pre, now)
    receipt["session_check"].update(contract_hours_field=field, liquid_hours_present=present,
                                    liquid_hours_parsed=sessions is not None)
    if sessions is None:
        receipt["session_check"]["with_liquid_hours"] = "today_missing_or_unparseable"
        return "refused_liquid_hours_unavailable", account, None
    remaining = plan["timeouts"]["overall_deadline_seconds"] - (time.monotonic() - t0)
    ok, why = PO.rth_check(now, plan, sessions, horizon_s=remaining)
    receipt["session_check"]["with_liquid_hours"] = why
    if not ok:
        return "refused_outside_rth", account, None
    contender = contender_fn(plan, a.port)
    receipt["client_id_free_check"] = contender
    outcome = contender.get("outcome")
    if outcome == "not_connected":
        return "not_connected", account, None
    if outcome == "refused_326":
        return "refused_client_id_in_use", account, None
    if outcome != "connected":
        return (outcome if str(outcome).startswith("refused_") else "refused_client_id_unverified"), account, None
    window = PO.session_window(now, plan, sessions)
    receipt["server_minus_local_s"] = (pre.get("observed") or {}).get("server_minus_local_s")
    return "ready", account, (window[1] if window else None)


def _static_refusal(a, plan_path: Path, plan: dict | None, versions_fn) -> tuple[str | None, dict]:
    """Refusals that need no connection: plan, port, runtime pins, prerequisites."""
    if plan is None:
        return "refused_plan_invalid", {"plan_errors": ["plan unreadable"]}
    errors = validate_plan(plan)
    if errors:
        return "refused_plan_invalid", {"plan_errors": errors}
    refusal = port_refusal(plan, a.port)
    if refusal:
        return refusal, {}
    observed = (versions_fn or PO.versions)()
    if not PO.pinned_runtime(plan, observed):
        return "refused_unpinned_runtime", {"runtime": observed}
    ok, entries = gate_prerequisites(plan)
    if not ok:
        return "refused_gate_prerequisites_missing", {"prerequisites": entries}
    return None, {"prerequisites": entries}


def _load_plan_or_none(path: Path):
    try:
        return load_plan(path)
    except (OSError, ValueError):
        return None


def cmd_preflight(a, *, check_fn=None, contender_fn=None, now_fn=None, versions_fn=None) -> int:
    t0 = time.monotonic()
    plan_path = HERE / a.plan
    plan = _load_plan_or_none(plan_path)
    out = {"kind": "ibkr_local_acceptance_preflight", "plan": a.plan, "port": a.port}
    status, fields = _static_refusal(a, plan_path, plan, versions_fn)
    out.update(fields)
    account = None
    if status is None:
        state = Path(a.state_dir)
        if KillSwitch(state).engaged():
            status = "refused_kill_switch_engaged"
        else:
            status, account, _ = _checks_before_orders(
                a, plan, out, check_fn=check_fn or PO.run_check, contender_fn=contender_fn or contender_probe,
                now_fn=now_fn or (lambda: datetime.now(timezone.utc)), t0=t0)
    out["status"] = status
    out["exit_code"] = 0 if status == "ready" else PO.exit_code_for(status)
    print(PO.scrub_serialized(json.dumps(out, default=str), [account]))
    return out["exit_code"]


def cmd_run(a, *, check_fn=None, contender_fn=None, observe_fn=None, cancel_fn=None, phase_fn=None, now_fn=None,
            versions_fn=None, sleep_fn=time.sleep, signals: ParentSignals | None = None, gate_path=None,
            repo_root=None) -> int:
    t0 = time.monotonic()
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    observe_fn, cancel_fn = observe_fn or observe, cancel_fn or ibapi_cancel_run_orders
    receipt_path = Path(a.receipt)
    if is_gate_receipt(receipt_path):
        print(json.dumps({"status": "refused_gate_receipt_path", "exit_code": 3}))
        return 3
    plan_path = HERE / a.plan
    receipt = base_receipt(plan_path, versions_fn)
    receipt.update(port=a.port, status=None)
    if not a.enable_paper_orders:
        return _refuse(receipt, receipt_path, "refused_orders_not_enabled",
                       note="run places paper orders only with --enable-paper-orders; nothing was connected")
    plan = _load_plan_or_none(plan_path)
    status, fields = _static_refusal(a, plan_path, plan, versions_fn)
    receipt.update(fields)
    if status:
        return _refuse(receipt, receipt_path, status)
    state = private_dir(a.state_dir)
    kill = KillSwitch(state)
    if kill.engaged():
        return _refuse(receipt, receipt_path, "refused_kill_switch_engaged", kill_switch=kill.status())
    lock = acquire_lock(state)
    if lock is None:
        return _refuse(receipt, receipt_path, "refused_concurrent_run")
    signals = signals or ParentSignals()
    account = None
    try:
        signals.install()
        status, account, window_end = _checks_before_orders(
            a, plan, receipt, check_fn=check_fn or PO.run_check, contender_fn=contender_fn or contender_probe,
            now_fn=now_fn, t0=t0)
        if status != "ready":
            if status == "not_connected":
                receipt["evidence_class"] = "not_connected"
            return _refuse(receipt, receipt_path, status, [account])
        if signals.interrupted:
            return _refuse(receipt, receipt_path, "incomplete", [account], interrupted=True)
        prefix = new_run_prefix(now_fn())
        ids = order_ids(prefix)
        run_dir = private_dir(private_dir(state / "runs") / prefix)
        token = secrets.token_hex(16)
        receipt.update(run_prefix=prefix, evidence_class="native_paper", phases=[], checkpoints={}, cleanup=None, final=None)
        # A cleanup_required receipt stands before any phase can place an order.
        try:
            write_json(receipt_path, {**receipt, "status": "cleanup_required", "provisional": True,
                                      "note": "provisional: if this remains, orders carrying run_prefix may be at IB; run "
                                              "'preflight', cancel them in the Gateway and check the account is flat"},
                       [account], quiet=True)
        except OSError as exc:
            print(json.dumps({"status": "refused_receipt_unwritable", "exit_code": 3,
                              "error": redact(f"{type(exc).__name__}: {exc}")[:200]}))
            return 3
        return _run_phases(a, plan, receipt, receipt_path, account, prefix, ids, run_dir, token, window_end, kill,
                           observe_fn=observe_fn, cancel_fn=cancel_fn, phase_fn=phase_fn, sleep_fn=sleep_fn,
                           signals=signals, t0=t0, gate_path=Path(gate_path) if gate_path else GATE_RECEIPT,
                           repo=repo_root)
    finally:
        PO.install_signal_handlers()
        lock.close()


def _run_phases(a, plan, receipt, receipt_path, account, prefix, ids, run_dir, token, window_end, kill, *, observe_fn,
                cancel_fn, phase_fn, sleep_fn, signals, t0, gate_path, repo=None) -> int:
    t = plan["timeouts"]
    carry, orders_created = {}, 0
    phases, checkpoints = receipt["phases"], receipt["checkpoints"]
    env = {**os.environ, TOKEN_ENV: token, ACCOUNT_ENV: account}
    needs_cleanup = False

    def persist():
        try:
            write_json(receipt_path, {**receipt, "status": "cleanup_required", "provisional": True}, [account], quiet=True)
        except OSError:
            pass

    for phase in PHASES:
        if signals.interrupted:
            receipt["interrupted"] = signals.received
            break
        if PO.sha256_file(HERE / a.plan) != receipt["plan_sha256"]:
            # The plan is bound at run start; each phase process re-checks the same hash.
            receipt["plan_changed_during_run"] = True
            break
        result_path = run_dir / f"phase-{phase}.json"
        manifest = {"schema_version": 1, "run_prefix": prefix, "phase": phase, "token_sha256": sha256_text(token),
                    "plan": a.plan, "plan_sha256": receipt["plan_sha256"], "port": a.port,
                    "state_dir": str(Path(a.state_dir).resolve()), "result_path": str(result_path), "carry": carry,
                    "orders_created": orders_created, "deadline_seconds": t["phase_deadline_seconds"][phase],
                    "window_end": window_end.isoformat() if window_end else None,
                    "server_minus_local_s": receipt.get("server_minus_local_s") or 0.0, "log_level": a.log_level}
        manifest_path = run_dir / f"manifest-{phase}.json"
        write_private(manifest_path, json.dumps(manifest, indent=2))
        needs_cleanup = True  # from here an order of the run may exist at IB
        proc = (phase_fn or spawn_phase)(phase, manifest_path, env, t["phase_deadline_seconds"][phase], signals)
        result = read_phase_result(result_path, prefix)
        entry = {"phase": phase, "process": proc, "result": result}
        phases.append(entry)
        if result is not None:
            orders_created = int((result.get("summary") or {}).get("orders_created") or orders_created)
            if phase == "A":
                carry = (result.get("summary") or {}).get("carry_out") or {}
        persist()
        if (result or {}).get("status") != "passed":
            break
        if phase == "A":
            snap = observe_with_retry(observe_fn, plan, a.port, ("positions", "open_orders"), sleep_fn)
            checkpoints["after_A"] = after_a_verdict(plan, snap, prefix, carry)
            if checkpoints["after_A"]["passed"]:
                carry["R2"]["venue_order_ids"] = checkpoints["after_A"]["r2_venue_order_ids"]
        elif phase == "B":
            snap = observe_with_retry(observe_fn, plan, a.port, ("positions", "open_orders", "completed"), sleep_fn)
            checkpoints["after_B"] = after_b_verdict(plan, snap, prefix, ids)
            # Only a passed checkpoint shows nothing of the run is left working.
            needs_cleanup = not checkpoints["after_B"]["passed"]
        else:
            needs_cleanup = False
        persist()
        if phase in ("A", "B") and not checkpoints[f"after_{phase}"]["passed"]:
            break
    if needs_cleanup or signals.interrupted:
        # The phase process has exited, so the node's client id is free for the cancel client.
        receipt["cleanup"] = cancel_fn(plan, a.port, prefix)
        persist()
    snap = observe_with_retry(observe_fn, plan, a.port, ("positions", "open_orders", "completed", "executions"), sleep_fn)
    receipt["final"] = final_verdict(plan, snap, prefix, ids)
    receipt["kill_switch"] = kill.status()
    status = run_status(phases, checkpoints, receipt["final"])
    if status == "passed" and signals.interrupted:
        status = "incomplete"
    receipt["status"] = status
    receipt["elapsed_seconds"] = round(time.monotonic() - t0, 3)
    receipt.pop("provisional", None)
    entries = None
    if status == "passed":
        ok, entries = gate_prerequisites(plan)
        # The steps receipt is final before the gate receipt binds its sha256, so it names the
        # gate receipt path only; the gate receipt carries the hash. A steps receipt outside the
        # repository could not be checked by anyone qualifying the flip, so it makes none.
        if rel(receipt_path, repo) == "<private>":
            receipt["gate_receipt"] = {"eligible": False, "reason": "steps_receipt_outside_repository"}
        elif not ok:
            receipt["gate_receipt"] = {"eligible": False, "reason": "prerequisites_changed_during_run",
                                       "prerequisites": entries}
        else:
            receipt["gate_receipt"] = {"eligible": True, "path": rel(gate_path, repo)}
    try:
        code = write_json(receipt_path, receipt, [account], quiet=True)
    except OSError as exc:
        print(json.dumps({"status": status, "final_receipt_written": False, "exit_code": 3,
                          "error": redact(f"{type(exc).__name__}: {exc}")[:200]}))
        return 3
    written = False
    if receipt["gate_receipt"].get("eligible"):
        try:
            write_json(gate_path, gate_receipt(plan, receipt, receipt_path, entries, repo), [account], quiet=True)
            written = True
        except OSError as exc:
            # Nothing binds the steps receipt yet, so it can record that the gate receipt is missing.
            receipt["gate_receipt"].update(written=False, error=redact(f"{type(exc).__name__}: {exc}")[:200])
            receipt["gate_receipt_error"] = receipt["gate_receipt"]["error"]
            try:
                write_json(receipt_path, receipt, [account], quiet=True)
            except OSError:
                pass
    print(json.dumps({"status": status, "exit_code": code, "run_prefix": prefix, "gate_receipt_written": written,
                      "gate_receipt_error": receipt.get("gate_receipt_error"),
                      "kill_switch_engaged": receipt["kill_switch"].get("engaged")}))
    return code


# --------------------------------------------------------------------------- CLI: phase (internal)


def cmd_phase(a, *, node_fn=None, versions_fn=None) -> int:
    """One TradingNode phase. Refused unless started by 'run' (token and manifest)."""
    def refuse(status, **fields):
        print(json.dumps({"status": status, "exit_code": 3, **fields}))
        return 3

    token = os.environ.get(TOKEN_ENV, "")
    try:
        manifest = json.loads(Path(a.manifest).read_text())
    except (OSError, ValueError):
        return refuse("refused_not_invoked_by_runner")
    if not token or sha256_text(token) != manifest.get("token_sha256") or manifest.get("phase") != a.phase_name:
        return refuse("refused_not_invoked_by_runner")
    plan_path = HERE / manifest["plan"]
    if manifest["plan"] not in PLAN_NAMES or PO.sha256_file(plan_path) != manifest.get("plan_sha256"):
        return refuse("refused_plan_changed")
    plan = load_plan(plan_path)
    if validate_plan(plan):
        return refuse("refused_plan_invalid")
    if port_refusal(plan, manifest["port"]):
        return refuse(port_refusal(plan, manifest["port"]))
    observed = (versions_fn or PO.versions)()
    if not PO.pinned_runtime(plan, observed):
        return refuse("refused_unpinned_runtime", runtime=observed)
    account = os.environ.get(ACCOUNT_ENV, "")
    if not account.startswith(plan["account_prefix"]):
        return refuse("refused_not_paper_account")
    kill = KillSwitch(manifest["state_dir"])
    if (a.phase_name == "C") is not kill.engaged():
        return refuse("refused_kill_switch_state", expected_engaged=a.phase_name == "C")
    PO.install_signal_handlers()
    t0 = time.monotonic()
    ctx = PhaseContext(plan, manifest["run_prefix"], a.phase_name, carry=manifest.get("carry") or {},
                       orders_created=manifest.get("orders_created") or 0,
                       server_minus_local_s=manifest.get("server_minus_local_s") or 0.0)
    result_path = Path(manifest["result_path"])
    result = {"schema_version": 1, "kind": PHASE_KIND, "phase": a.phase_name, "run_prefix": ctx.prefix,
              "versions": observed, "runner_sha256": PO.sha256_file(RUNNER_PATH)}

    def write(status, provisional):
        write_private(result_path, PO.scrub_serialized(json.dumps(
            {**result, "status": status, "provisional": provisional, "summary": ctx.summary()}, indent=2, default=str),
            [account]), durable=not provisional)

    write("cleanup_required", True)
    ctx.on_change = lambda: write("cleanup_required", True)
    deadline = float(manifest["deadline_seconds"])
    stop_s, cleanup_s = plan["timeouts"]["node_stop_allowance_seconds"], plan["timeouts"]["cleanup_seconds"]
    hard_stop_at = t0 + deadline - stop_s
    window_end = datetime.fromisoformat(manifest["window_end"]) if manifest.get("window_end") else None
    error = interrupted = False
    try:
        (node_fn or run_phase_node)(plan, account, manifest["port"], ctx, kill, abort_at=hard_stop_at - cleanup_s,
                                    hard_stop_at=hard_stop_at, window_end=window_end, log_level=manifest.get("log_level") or "WARNING")
    except BaseException as exc:  # noqa: BLE001 - the phase result must still be written
        ctx.errors.append(redact(f"node: {type(exc).__name__}: {exc}")[:200])
        error, interrupted = isinstance(exc, Exception), not isinstance(exc, Exception)
    ctx.on_change = None
    status = phase_status(ctx, error=error, interrupted=interrupted)
    result["elapsed_seconds"] = round(time.monotonic() - t0, 3)
    write(status, False)
    code = PO.exit_code_for(status)
    print(json.dumps({"phase": a.phase_name, "status": status, "exit_code": code}))
    return code


def cmd_kill_switch(a) -> int:
    ks = KillSwitch(a.state_dir)
    if a.action == "status":
        print(json.dumps(ks.status(), default=str))
        return 0
    res = ks.clear(a.confirm, a.reason)
    print(json.dumps(res, default=str))
    return 0 if res["status"] in ("cleared", "not_engaged") else 3


def main(argv=None, **hooks) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preflight", "run"):
        p = sub.add_parser(name)
        p.add_argument("--port", type=int, default=4002)
        p.add_argument("--plan", choices=PLAN_NAMES, default=PLAN_NAMES[0],
                       help="predeclared plan next to this file: regular session (default) or 16:00-20:00 with outsideRth")
        p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR),
                       help="private directory for the lock, the kill-switch latch and phase files (created 0700)")
        if name == "run":
            p.add_argument("--receipt", required=True)
            p.add_argument("--enable-paper-orders", action="store_true",
                           help="required: without it 'run' refuses before connecting")
            p.add_argument("--log-level", default="WARNING", help="Nautilus console log level (console output is not redacted)")
    k = sub.add_parser("kill-switch")
    k.add_argument("action", choices=("status", "clear"))
    k.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    k.add_argument("--confirm", action="store_true")
    k.add_argument("--reason")
    ph = sub.add_parser("phase", help="internal: started by 'run'")
    ph.add_argument("phase_name", choices=PHASES)
    ph.add_argument("--manifest", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "preflight":
        return cmd_preflight(a, **{k: v for k, v in hooks.items() if k in ("check_fn", "contender_fn", "now_fn", "versions_fn")})
    if a.cmd == "kill-switch":
        return cmd_kill_switch(a)
    if a.cmd == "phase":
        return cmd_phase(a, **{k: v for k, v in hooks.items() if k in ("node_fn", "versions_fn")})
    return cmd_run(a, **hooks)


if __name__ == "__main__":
    raise SystemExit(main())
