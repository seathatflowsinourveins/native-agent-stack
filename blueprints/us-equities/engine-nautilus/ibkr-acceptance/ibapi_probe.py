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
import threading
import time
from datetime import datetime, timezone

PAPER_PORTS = {4002, 7497}
PAPER_ACCOUNT_PREFIX = "DU"
SUMMARY_TAGS = "AccountType,NetLiquidation,TotalCashValue,BuyingPower"
MARKET_DATA_TYPES = {1: "REALTIME", 2: "FROZEN", 3: "DELAYED", 4: "DELAYED_FROZEN"}
# Informational codes the server sends on connection or with delayed data
# (farm status, "displaying delayed market data"); they are not failures.
INFO_CODES = {2104, 2106, 2107, 2108, 2158, 2119, 2100, 10167, 10089}
TICK_NAMES = {1: "bid", 2: "ask", 4: "last", 66: "delayed_bid", 67: "delayed_ask", 68: "delayed_last"}
REQUESTS = ("accounts", "time", "positions", "orders", "summary", "contract", "mktdata", "history")


def account_scope(accounts_list: str) -> tuple[int, bool]:
    """Count the managed accounts and check that every one is a paper account."""
    ids = [a.strip() for a in accounts_list.split(",") if a.strip()]
    return len(ids), bool(ids) and all(a.startswith(PAPER_ACCOUNT_PREFIX) for a in ids)


def is_info(code: int) -> bool:
    return code in INFO_CODES


class ProbeState:
    """Callback handlers and collected results, kept free of ibapi so they can be
    tested offline; ``build_probe`` mixes them into the ibapi client."""

    def __init__(self):
        self.done = {k: threading.Event() for k in REQUESTS}
        self.r = {"account_count": 0, "paper_accounts": None, "server_time_epoch": None, "positions": 0,
                  "open_orders": 0, "summary_tags": [], "account_type": None, "spy_contract": None,
                  "market_data_type": None, "spy_quote": {}, "history": {"bars": 0}, "errors": [], "info": []}

    def managedAccounts(self, accountsList):
        self.r["account_count"], self.r["paper_accounts"] = account_scope(accountsList)
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
        entry = {"reqId": reqId, "code": errorCode, "text": (errorString or "")[:160]}
        (self.r["info"] if is_info(errorCode) else self.r["errors"]).append(entry)

    def completed(self) -> dict:
        return {k: v.is_set() for k, v in self.done.items()}


def build_probe():
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class Probe(ProbeState, EWrapper, EClient):
        def __init__(self):
            ProbeState.__init__(self)
            EClient.__init__(self, self)

    return Probe()


def spy():
    from ibapi.contract import Contract

    c = Contract()
    c.symbol, c.secType, c.exchange, c.currency, c.primaryExchange = "SPY", "STK", "SMART", "USD", "ARCA"
    return c


def verdict(r: dict) -> str:
    return "passed" if (r["spy_contract"] and r["history"]["bars"] > 0 and r["server_time_epoch"]) else "incomplete"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4002)
    ap.add_argument("--client-id", type=int, default=73)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--deadline-seconds", type=float, default=60.0)
    a = ap.parse_args(argv)
    receipt = {"schema_version": 1, "gate_id": "ibkr-local-acceptance", "step": "acceptance-plan 5.1 read-only",
               "client": "ibapi (official IB API client)", "host": a.host, "port": a.port, "client_id": a.client_id,
               "generated_at": datetime.now(timezone.utc).isoformat()}
    if a.port not in PAPER_PORTS:
        receipt.update(status="refused_not_paper_port", evidence_class="none")
        return _write(a.receipt, receipt, 3)
    import ibapi

    receipt["ibapi_version"] = getattr(ibapi, "__version__", None) or ibapi.get_version_string()
    p = build_probe()
    deadline = time.monotonic() + a.deadline_seconds
    p.connect(a.host, a.port, a.client_id)
    threading.Thread(target=p.run, daemon=True).start()

    def wait(key, seconds):
        return p.done[key].wait(max(0.0, min(seconds, deadline - time.monotonic())))

    try:
        if not p.isConnected() or not wait("accounts", 10):
            receipt.update(status="not_connected", evidence_class="not_connected")
            return _write(a.receipt, receipt, 2, p)
        if not p.r["paper_accounts"]:
            receipt.update(status="refused_not_paper_account", evidence_class="none")
            return _write(a.receipt, receipt, 3, p)
        local_before = time.time()
        p.reqCurrentTime()
        wait("time", 5)
        if p.r["server_time_epoch"]:
            # reqCurrentTime has one-second resolution; the midpoint bounds the local side.
            p.r["server_minus_local_s"] = round(p.r["server_time_epoch"] - (local_before + time.time()) / 2, 3)
        p.reqPositions(); wait("positions", 10); p.cancelPositions()
        p.reqAllOpenOrders(); wait("orders", 10)
        p.reqAccountSummary(9001, "All", SUMMARY_TAGS); wait("summary", 10); p.cancelAccountSummary(9001)
        p.reqContractDetails(9002, spy()); wait("contract", 10)
        p.reqMarketDataType(3)  # delayed allowed; the callback records what is actually granted
        p.reqMktData(9003, spy(), "", True, False, []); wait("mktdata", 15)
        p.reqHistoricalData(9004, spy(), "", "2 D", "5 mins", "TRADES", 1, 2, False, []); wait("history", 20)
        status = verdict(p.r)
        receipt.update(status=status, evidence_class="native_paper_readonly",
                       existing_state={"positions": p.r["positions"], "open_orders": p.r["open_orders"]})
        return _write(a.receipt, receipt, 0 if status == "passed" else 1, p)
    finally:
        p.disconnect()


def _write(path, receipt, code, probe=None):
    if probe is not None:
        receipt["observed"] = probe.r
        receipt["requests_completed"] = probe.completed()
    receipt["exit_code"] = code
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2, default=str)
        f.write("\n")
    print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
