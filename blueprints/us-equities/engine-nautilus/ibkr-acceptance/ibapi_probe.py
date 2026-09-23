"""Read-only IBKR paper acceptance probe on the official IB API client (ibapi).

Step 1 of engine-nautilus/acceptance-plan.md section 5: read-only socket
access with execution disabled. It never calls placeOrder, cancelOrder,
reqGlobalCancel or exerciseOptions. It refuses a port that is not a paper
default (4002 Gateway, 7497 TWS) before connecting, and disconnects unless
every managed account id starts with "DU" (an IBKR paper account). Account ids
are not recorded, not even hashed (a paper id is a short "DU" plus digits, so
its hash is trivially reversible); only the count and the paper check are.
Balances are not recorded, only which account-summary tags were returned.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
# The gate's flip receipt; a step-1 probe must never write there.
GATE_RECEIPT = HERE / "receipt.json"
PAPER_PORTS = {4002, 7497}
PAPER_ACCOUNT_PREFIX = "DU"
SUMMARY_TAGS = "AccountType,NetLiquidation,TotalCashValue,BuyingPower"
MARKET_DATA_TYPES = {1: "REALTIME", 2: "FROZEN", 3: "DELAYED", 4: "DELAYED_FROZEN"}
# Informational codes the server sends on connection or with delayed data
# (farm status, "displaying delayed market data"); they are not failures.
INFO_CODES = {2104, 2106, 2107, 2108, 2158, 2119, 2100, 10167, 10089}
TICK_NAMES = {1: "bid", 2: "ask", 4: "last", 66: "delayed_bid", 67: "delayed_ask", 68: "delayed_last"}
# LAST_TIMESTAMP and DELAYED_LAST_TIMESTAMP arrive as epoch-second strings.
TIMESTAMP_TICKS = {45: "last_trade_epoch", 88: "delayed_last_trade_epoch"}
QUOTE_AGE_RESOLUTION_S = 2.0
REQUESTS = ("accounts", "time", "positions", "orders", "summary", "contract", "mktdata", "history")
# IBKR account ids: paper DU/DF, live U/F, and I for some institutional forms.
ACCOUNT_ID = re.compile(r"\b(?:D?[UF]|I)\d{5,}\b")
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
ABS_PATH = re.compile(r"(?:[A-Za-z]:\\|/)(?:[\w.-]+[/\\])+[\w.-]*")


def redact(text: str) -> str:
    """Strip account ids, IPv4 endpoints and absolute paths from IB message text."""
    return ABS_PATH.sub("<path>", IPV4.sub("<ip>", ACCOUNT_ID.sub("<account-id>", text)))


def account_scope(accounts_list: str) -> tuple[int, bool]:
    """Count the managed accounts and check that every one is a paper account."""
    ids = [a.strip() for a in accounts_list.split(",") if a.strip()]
    return len(ids), bool(ids) and all(a.startswith(PAPER_ACCOUNT_PREFIX) for a in ids)


def is_info(code: int) -> bool:
    return code in INFO_CODES


def is_gate_receipt(path) -> bool:
    return Path(path).resolve() == GATE_RECEIPT


def max_quote_age(plan_path=PLAN) -> float:
    return float(json.loads(Path(plan_path).read_text())["max_acceptable_quote_age_seconds"])


class ProbeState:
    """Callback handlers and collected results, kept free of ibapi so they can be
    tested offline; ``build_probe`` mixes them into the ibapi client."""

    def __init__(self):
        self.done = {k: threading.Event() for k in REQUESTS}
        self.r = {"account_count": 0, "paper_accounts": None, "server_time_epoch": None, "positions": 0,
                  "open_orders": 0, "summary_tags": [], "account_type": None, "spy_contract": None,
                  "market_data_type": None, "spy_quote": {}, "history": {"bars": 0}, "errors": [], "info": []}

    def managedAccounts(self, accountsList):
        count, paper = account_scope(accountsList)
        self.r["account_count"] = max(self.r["account_count"], count)
        # Latched: once any callback reports a non-paper account the probe stays refused.
        self.r["paper_accounts"] = paper and self.r["paper_accounts"] is not False
        self.done["accounts"].set()

    def currentTime(self, t):
        self.r["server_time_epoch"] = t
        self.done["time"].set()

    def position(self, account, contract, pos, avgCost):
        if pos:
            self.r["positions"] += 1

    def positionEnd(self):
        self.done["positions"].set()

    def openOrder(self, orderId, contract, order, orderState):
        self.r["open_orders"] += 1

    def openOrderEnd(self):
        self.done["orders"].set()

    def accountSummary(self, reqId, account, tag, value, currency):
        if tag not in self.r["summary_tags"]:
            self.r["summary_tags"].append(tag)
        if tag == "AccountType":
            self.r["account_type"] = value

    def accountSummaryEnd(self, reqId):
        self.done["summary"].set()

    def contractDetails(self, reqId, d):
        c = d.contract
        self.r["spy_contract"] = {"conId": c.conId, "secType": c.secType, "currency": c.currency,
                                  "exchange": c.exchange, "primaryExchange": c.primaryExchange,
                                  "longName": d.longName, "tradingHoursSample": (d.tradingHours or "")[:40]}

    def contractDetailsEnd(self, reqId):
        self.done["contract"].set()

    def marketDataType(self, reqId, marketDataType):
        self.r["market_data_type"] = MARKET_DATA_TYPES.get(marketDataType, str(marketDataType))

    def tickPrice(self, reqId, tickType, price, attrib):
        name = TICK_NAMES.get(tickType)
        if name and price > 0:
            self.r["spy_quote"][name] = price
            self.r["spy_quote"].setdefault("first_tick_local_epoch", time.time())

    def tickString(self, reqId, tickType, value):
        name = TIMESTAMP_TICKS.get(tickType)
        if name and str(value).isdigit():
            self.r["spy_quote"][name] = int(value)

    def tickSnapshotEnd(self, reqId):
        self.done["mktdata"].set()

    def historicalData(self, reqId, bar):
        h = self.r["history"]
        h["bars"] += 1
        h.setdefault("first", bar.date)
        h["last"] = bar.date

    def historicalDataEnd(self, reqId, start, end):
        self.done["history"].set()

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        # ibapi 10.45 signature: (reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)
        text = redact(errorString or "")[:160]
        entry = {"reqId": reqId, "code": errorCode, "text": text}
        (self.r["info"] if is_info(errorCode) else self.r["errors"]).append(entry)

    def completed(self) -> dict:
        return {k: v.is_set() for k, v in self.done.items()}


def quote_age(r: dict, local_now: float) -> float | None:
    """Seconds from the last trade time IB reported to the server clock now."""
    quote = r["spy_quote"]
    epoch = quote.get("last_trade_epoch") or quote.get("delayed_last_trade_epoch")
    if epoch is None:
        return None
    return round(local_now + (r.get("server_minus_local_s") or 0.0) - epoch, 3)


def verdict(r: dict, completed: dict, max_age: float) -> str:
    """Passed needs every request complete, no existing positions or orders, the
    contract, bars, server time and a quote no older than the plan's limit. IB
    trade and server times have one-second resolution, so an age down to
    ``-QUOTE_AGE_RESOLUTION_S`` counts as current; anything earlier is refused."""
    if r["paper_accounts"] is not True:
        return "refused_not_paper_account"
    if not all(completed.get(k) for k in REQUESTS):
        return "incomplete"
    if r["positions"] or r["open_orders"]:
        return "blocked_existing_state"
    age = r.get("quote_age_s")
    if (r["spy_contract"] and r["history"]["bars"] > 0 and r["server_time_epoch"] and r["spy_quote"]
            and age is not None and -QUOTE_AGE_RESOLUTION_S <= age <= max_age):
        return "passed"
    return "incomplete"


EXIT_CODES = {"passed": 0, "incomplete": 1, "not_connected": 2, "refused_not_paper_port": 3,
              "refused_not_paper_account": 3, "blocked_existing_state": 4}


def build_probe():
    import ibapi
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class Probe(ProbeState, EWrapper, EClient):
        def __init__(self):
            ProbeState.__init__(self)
            EClient.__init__(self, self)

    probe = Probe()
    probe.client_version = ibapi.get_version_string()
    return probe


def spy():
    from ibapi.contract import Contract

    c = Contract()
    c.symbol, c.secType, c.exchange, c.currency, c.primaryExchange = "SPY", "STK", "SMART", "USD", "ARCA"
    return c


def main(argv=None, probe_factory=None, contract_factory=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4002)
    ap.add_argument("--client-id", type=int, default=73)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--deadline-seconds", type=float, default=90.0, help="plan.json overall_timeout_seconds")
    a = ap.parse_args(argv)
    if is_gate_receipt(a.receipt):
        print(json.dumps({"status": "refused_gate_receipt_path", "exit_code": 3}))
        return 3
    receipt = {"schema_version": 1, "gate_id": "ibkr-local-acceptance", "step": "acceptance-plan 5.1 read-only",
               "client": "ibapi (official IB API client)", "host": a.host, "port": a.port, "client_id": a.client_id,
               "deadline_seconds": a.deadline_seconds, "generated_at": datetime.now(timezone.utc).isoformat()}
    if a.port not in PAPER_PORTS:
        receipt.update(status="refused_not_paper_port", evidence_class="none")
        return _write(a.receipt, receipt)
    limit = max_quote_age()
    contract = contract_factory or spy
    p = (probe_factory or build_probe)()
    receipt["ibapi_version"] = getattr(p, "client_version", None)
    deadline = time.monotonic() + a.deadline_seconds
    try:
        p.connect(a.host, a.port, a.client_id)
    except OSError as exc:  # ibapi reports socket errors itself; this covers any that escape
        p.r["errors"].append({"reqId": -1, "code": None, "text": redact(f"{type(exc).__name__}: {exc}")[:160]})
    if p.isConnected():
        threading.Thread(target=p.run, daemon=True).start()

    def wait(key, seconds):
        return p.done[key].wait(max(0.0, min(seconds, deadline - time.monotonic())))

    try:
        if not p.isConnected() or not wait("accounts", 10):
            receipt.update(status="not_connected", evidence_class="not_connected")
            return _write(a.receipt, receipt, p)
        steps = (
            ("time", 5, p.reqCurrentTime, None),
            ("positions", 10, p.reqPositions, p.cancelPositions),
            ("orders", 10, p.reqAllOpenOrders, None),
            ("summary", 10, lambda: p.reqAccountSummary(9001, "All", SUMMARY_TAGS), lambda: p.cancelAccountSummary(9001)),
            ("contract", 10, lambda: p.reqContractDetails(9002, contract()), None),
            # Delayed data is allowed; the callback records the type actually granted.
            ("mktdata", 15, lambda: (p.reqMarketDataType(3), p.reqMktData(9003, contract(), "", True, False, [])), None),
            ("history", 20, lambda: p.reqHistoricalData(9004, contract(), "", "2 D", "5 mins", "TRADES", 1, 2, False, []),
             None),
        )
        for key, seconds, request, after in steps:
            if p.r["paper_accounts"] is not True:  # checked before every request
                break
            started = time.time()
            request()
            wait(key, seconds)
            if after:
                after()
            if key == "time" and p.r["server_time_epoch"]:
                # reqCurrentTime has one-second resolution; the midpoint bounds the local side.
                p.r["server_minus_local_s"] = round(p.r["server_time_epoch"] - (started + time.time()) / 2, 3)
            if key == "mktdata":
                p.r["quote_age_s"], p.r["max_quote_age_s"] = quote_age(p.r, time.time()), limit
        if p.r["paper_accounts"] is not True:
            receipt.update(status="refused_not_paper_account", evidence_class="none")
            return _write(a.receipt, receipt, p)
        completed = p.completed()
        receipt.update(status=verdict(p.r, completed, limit), evidence_class="native_paper_readonly",
                       existing_state={"positions": p.r["positions"] if completed["positions"] else None,
                                       "open_orders": p.r["open_orders"] if completed["orders"] else None})
        return _write(a.receipt, receipt, p)
    finally:
        p.disconnect()


def _write(path, receipt, probe=None):
    if probe is not None:
        receipt["observed"] = probe.r
        receipt["requests_completed"] = probe.completed()
    code = EXIT_CODES[receipt["status"]]
    receipt["exit_code"] = code
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2, default=str)
        f.write("\n")
    print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
