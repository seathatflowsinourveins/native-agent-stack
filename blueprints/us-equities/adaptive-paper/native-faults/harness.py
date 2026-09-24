"""Minimal native Alpaca paper broker-fault harness (gate native-fault-behaviour).

Four frozen cases (plan.json) run in order on ONE started engine
AlpacaPaperTransport with the engine's own Controller and Ledger in a
dedicated state root. Outcomes are judged from the engine's recorded ledger
state; HTTP statuses are retained only as evidence. No retry, no second
transport, SPY qty-1 non-marketable DAY limits only, at most plan.max_posts
POSTs. Cleanup always runs on the same started transport and must prove the
account flat with zero open orders, otherwise CLEANUP_REQUIRED is written.
A write-ahead IN_FLIGHT marker (run id and client-id prefix) is written in the
run directory before the first POST and removed only after cleanup proves
flat; SIGKILL or a crash leaves it for manual recovery.
The ledger is FaultLedger: the engine Ledger except that the single C04 client id
may carry a sub-penny price to Alpaca, whose documented 422 refusal the engine
records as broker_refused (see README.md, "C04 choice"). The default transport is
FaultTransport, the engine transport with the same single-id exemption at its
order-contract boundary.

Usage: harness.py run --env-file PATH --state-root PATH --out PATH
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from runner import Controller, credentials, reconcile, save  # noqa: E402
from safety import (DEFAULT_STOP, DEFINITIVE_REFUSAL_STATUSES, SUB_PENNY_REFUSAL,  # noqa: E402
                    TERMINAL as LEDGER_TERMINAL, Ledger, SafetyError, account_lock_fingerprint,
                    price_increment_valid)
from transport import (TERMINAL, AlpacaPaperTransport, TransportError, limit_order_request,  # noqa: E402
                       order_envelope, timestamp_ns)

PLAN_PATH = HERE / "plan.json"
STATE_BASE = Path.home() / ".local/state/native-agent-stack"
DEFAULT_ROOT = DEFAULT_STOP.parent
LOCK_ROOT = None  # None keeps the engine's shared account-writer lock namespace.
CASE_IDS = ["C01", "C02", "C05", "C04"]
OPEN = {"pending_new", "accepted", "new", "accepted_for_bidding"}
CENT = Decimal("0.01")
REFUSAL_STATUSES = DEFINITIVE_REFUSAL_STATUSES  # plus the documented sub-penny 422, judged from the ledger.
CANCEL_ANSWERS = (204, 404, 422)  # DELETE answers the engine treats as data.
EXIT = {"native_faults_passed": 0, "not_started": 2, "refused": 2, "cleanup_required": 3}


class Refused(RuntimeError):
    """Pre-write refusal; no order has been submitted."""


class FaultLedger(Ledger):
    """The engine Ledger with one harness-only change: the single C04 client id
    may carry a price outside the minimum price variance to the broker, so that
    Alpaca itself answers the fault. Every other client id, including every
    engine path, keeps the pre-send ``invalid_price_increment`` refusal."""

    def __init__(self, db_path, *, sub_penny_client_id):
        super().__init__(db_path)
        self.sub_penny_client_id = sub_penny_client_id

    def _check_price_increment(self, client_id, price):
        if client_id == self.sub_penny_client_id and not price_increment_valid(price):
            return
        super()._check_price_increment(client_id, price)


class FaultTransport(AlpacaPaperTransport):
    """The engine transport with one harness-only change, mirroring FaultLedger:
    the single C04 client id may carry its sub-penny limit price through the
    order-contract boundary. Its other fields are validated by the contract as
    usual (with the price truncated to the cent), and the serialized POST body
    must still equal its envelope. Every other client id is validated exactly as
    in the engine."""

    sub_penny_client_id = None

    def _validated_request(self, intent):
        price = Decimal(intent["limit_price"])
        if (self.sub_penny_client_id is None or intent["client_order_id"] != self.sub_penny_client_id
                or price_increment_valid(price)):
            return super()._validated_request(intent)
        on_cent = dict(intent, limit_price=str(price.quantize(CENT, ROUND_DOWN)))
        envelope = order_envelope(on_cent, extended_hours_allowed=self.extended_hours_allowed)
        envelope["intent"]["limit_price"] = intent["limit_price"]
        return envelope, limit_order_request(envelope)


def fault_transport(sub_penny_client_id):
    """Factory for FaultTransport exempting exactly one client id."""
    def build(*args, **kwargs):
        port = FaultTransport(*args, **kwargs)
        port.sub_penny_client_id = sub_penny_client_id
        return port
    return build


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    plan = json.loads(raw)
    if ([c.get("id") for c in plan.get("cases", [])] != CASE_IDS or plan.get("symbol") != "SPY"
            or plan.get("qty") != "1" or plan.get("side") != "buy" or plan.get("time_in_force") != "day"
            or plan.get("extended_hours") is not False or type(plan.get("max_posts")) is not int
            or not 1 <= plan["max_posts"] <= 4
            or not Decimal("0") < Decimal(plan["c04_price_ratio"]) <= Decimal(plan["max_price_ratio"]) <= Decimal("0.5")
            or not Decimal("0") < Decimal(plan["c04_sub_penny_increment"]) < CENT
            or not 0 < plan.get("cancel_settle_seconds", 0) <= 30):
        raise ValueError("plan_outside_frozen_bounds")
    return plan, hashlib.sha256(raw).hexdigest()


def dedicated_root(path):
    root, base, default = Path(path).expanduser().resolve(), STATE_BASE.resolve(), DEFAULT_ROOT.resolve()
    if base not in root.parents or root == default or default in root.parents:
        raise ValueError("state_root_must_be_dedicated_under_native_agent_stack_not_default")
    return root


def describe(exc):
    """Bounded error record: reason codes only from engine-sanitized error types."""
    name = type(exc).__name__
    safe = isinstance(exc, (SafetyError, TransportError, Refused)) or name == "NativeOrderRejected"
    return {"type": name, "reason": str(exc)[:160] if safe else None}


def intent_state(ledger, cid):
    intent = next((i for i in ledger.intents() if i.client_id == cid), None)
    if intent is None:
        return None
    return {"status": intent.status, "filled_qty": str(intent.filled_qty),
            "submit_attempted": intent.submit_attempted, "broker_id_recorded": intent.broker_id is not None}


def ledger_effect(ledger):
    return {"positions": {s: str(p.qty) for s, p in sorted(ledger.positions().items()) if p.qty},
            "cash_delta_usd": str(ledger.accounting().cash_delta_usd)}


def refusal_record(ledger, cid):
    """The ledger's own durable broker_refused event for ``cid`` (status and refusal)."""
    row = ledger.db.execute("SELECT payload FROM events WHERE kind='broker_refused' AND client_id=? "
                            "ORDER BY rowid DESC LIMIT 1", (cid,)).fetchone()
    if row is None:
        return None
    payload = json.loads(row[0])
    return {"http_status": payload.get("http_status"), "refusal": payload.get("refusal")}


def unfilled(state):
    return state is not None and Decimal(state["filled_qty"]) == 0


# Pure judges over engine-recorded state; HTTP status is supporting evidence only.
def judge_c01(broker_status, state):
    ok = (broker_status in OPEN and unfilled(state) and state["submit_attempted"]
          and state["broker_id_recorded"] and state["status"] in OPEN)
    return "passed" if ok else "failed"


def judge_c02(state, broker_status):
    ok = unfilled(state) and state["status"] == "canceled" and broker_status == "canceled"
    return "passed" if ok else "failed"


def judge_c05(before, after, error, new_reasons, effect_before, effect_after, requests):
    cancels = [r for r in requests if r["kind"] == "cancel"]
    detail = {"delete_sent": bool(cancels), "cancel_http_statuses": [r["status"] for r in cancels],
              "broker_refusal_observed": any(r["status"] in (404, 422) for r in cancels),
              "new_transport_freeze_reasons": sorted(new_reasons), "error": error}
    if not cancels:
        detail["engine_path"] = "no DELETE reached the broker"
    ok = (error is None and not new_reasons and before == after and effect_before == effect_after
          and after is not None and after["status"] == "canceled" and unfilled(after)
          and all(r["status"] in CANCEL_ANSWERS for r in cancels))
    return ("passed" if ok else "failed"), detail


def judge_c04(requests, state, error, effect_before, effect_after, refusal=None):
    """Passed only when the ledger records broker_refused with no effect and the broker's
    answer is a definitive refusal: 401/403/404, or the single documented sub-penny 422
    that the ledger recorded with refusal SUB_PENNY_REFUSAL (any other 400/422/429/5xx
    stays ambiguous and fails)."""
    submits = [r for r in requests if r["kind"] == "submit"]
    statuses = [r["status"] for r in submits]
    detail = {"submit_http_statuses": statuses, "error": error, "ledger_refusal": refusal}
    if not submits:
        reason = (error or {}).get("reason") or (error or {}).get("type") or "no_submit_request"
        detail["unobserved_reason"] = "engine_refused_before_send: " + reason
        return "unobserved", detail
    definitive = (all(s in REFUSAL_STATUSES for s in statuses)
                  or (statuses == [422] and refusal == {"http_status": 422, "refusal": SUB_PENNY_REFUSAL}))
    ok = (state is not None and state["status"] == "broker_refused" and unfilled(state)
          and effect_before == effect_after and definitive)
    return ("passed" if ok else "failed"), detail


class Harness:
    def __init__(self, plan, plan_sha, run_dir, prefix):
        if not prefix or not prefix.startswith("nf-"):
            raise ValueError("client_id_prefix_required")
        self.plan, self.plan_sha, self.run_dir, self.prefix = plan, plan_sha, run_dir, prefix
        self.symbol = plan["symbol"]
        self.ledger = FaultLedger(run_dir / "ledger.sqlite3", sub_penny_client_id=prefix + "c04")
        # Fail-closed until the broker clock is read on the started transport.
        self.controller = Controller(self.ledger, 0.0, market_open=False)
        self.responses, self.cases = [], []
        self.posts = self.builds = 0
        self.interrupted = None
        self.cleaning = False
        self.baseline_cash = None
        self.started_at = datetime.now(timezone.utc).isoformat()

    def on_signal(self, signum, _frame):
        # A signal during cleanup never aborts it: the handler only records the
        # name and stops new buy admissions; cleanup's cancels and proof continue.
        name = signal.Signals(signum).name
        if self.cleaning:
            print("%s received: cleanup in progress; not aborting, waiting for flat proof" % name,
                  file=sys.stderr)
        self.interrupted = name
        self.controller.stop = True

    @property
    def in_flight(self):
        return self.run_dir / "IN_FLIGHT"

    def mark_in_flight(self):
        """Write-ahead marker before the first POST; SIGKILL leaves it for manual recovery.
        The file and its directory are fsynced so a host crash after the POST keeps it."""
        data = json.dumps({"run_id": self.run_dir.name, "client_id_prefix": self.prefix, "at": time.time()}) + "\n"
        fd = os.open(self.in_flight, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        dir_fd = os.open(self.run_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def observe_response(self, observation):
        self.responses.append({"kind": observation["kind"], "status": observation["status"]})

    async def before_request(self, kind, client_id=None):
        if kind == "submit" and self.posts >= self.plan["max_posts"]:
            raise SafetyError("post_ceiling_reached")
        result = await self.controller.before_request(kind, client_id=client_id)
        if kind == "submit":
            self.posts += 1
        return result

    def order(self, cid, price):
        return {"client_order_id": cid, "symbol": self.symbol, "side": "buy", "qty": self.plan["qty"],
                "limit_price": str(price), "type": "limit", "time_in_force": "day", "extended_hours": False}

    def bid(self):
        quote = self.controller.quotes.get(self.symbol)
        if quote is None:
            raise Refused("no_engine_quote")
        return quote.bid

    async def settle(self, cid):
        deadline = time.monotonic() + self.plan["cancel_settle_seconds"]
        while time.monotonic() < deadline:
            state = intent_state(self.ledger, cid)
            if state is None or state["status"] in LEDGER_TERMINAL:
                return state
            await asyncio.sleep(0.1)
        return intent_state(self.ledger, cid)

    async def prepare(self, port, stack):
        # The account-writer lock is taken here, after port.start(). A pre-start
        # account read through the engine budget is impossible: the transport's
        # REST client routes every request through _on_owner, which requires the
        # owner loop that only start() sets, and a second client is out of bounds.
        # No order is written before this lock is held.
        clock = await asyncio.to_thread(port._client.get_clock)
        account = await asyncio.to_thread(port._client.get_account)
        fingerprint = hashlib.sha256(str(account["id"]).encode()).hexdigest()  # lock key only; never recorded
        del account
        try:
            stack.enter_context(account_lock_fingerprint(fingerprint, LOCK_ROOT))
        except SafetyError as exc:
            raise Refused("account_lock:" + str(exc)) from None
        try:
            snap = await port.snapshot()
        except Exception as exc:
            raise Refused("flat_start_unproven:" + describe(exc)["type"]) from None
        if (any(Decimal(p["qty"]) for p in snap["positions"])
                or any(o["status"] not in TERMINAL for o in snap["orders"])):
            raise Refused("account_not_flat_or_open_orders")
        if clock.get("is_open") is not True:
            raise Refused("market_closed")
        self.baseline_cash = snap["account"]["cash"]
        self.controller.close = timestamp_ns(clock["next_close"]) / 1e9
        self.controller.market_open = True
        self.bid()
        __import__("native_adapter")  # Controller.before_submit imports it; load before quotes age.
        self.ledger.start_trial(time.time())

    async def c01(self, port):
        cid, bid = self.prefix + "c01", self.bid()
        price = (bid * Decimal(self.plan["max_price_ratio"])).quantize(CENT, ROUND_DOWN)
        result = await port.submit(self.order(cid, price))
        state = intent_state(self.ledger, cid)
        return judge_c01(result.get("status"), state), {
            "client_order_id": cid, "limit_price": str(price), "reference_bid": str(bid),
            "broker_status": result.get("status"), "ledger": state}

    async def c02(self, port):
        cid = self.prefix + "c01"
        final = await port.cancel(cid)
        state = await self.settle(cid)
        snap = await port.snapshot()
        broker = next((o["status"] for o in snap["orders"] if o["client_order_id"] == cid), None)
        return judge_c02(state, broker), {"client_order_id": cid, "ledger": state,
                                          "cancel_result_status": final and final.get("status"),
                                          "broker_snapshot_status": broker}

    async def c05(self, port):
        cid, start = self.prefix + "c01", len(self.responses)
        before, effect_before = intent_state(self.ledger, cid), ledger_effect(self.ledger)
        reasons_before = set(port.health["reasons"])
        result, error = None, None
        try:
            result = await port.cancel(cid)
        except Exception as exc:
            error = describe(exc)
        after = intent_state(self.ledger, cid)
        outcome, detail = judge_c05(before, after, error, set(port.health["reasons"]) - reasons_before,
                                    effect_before, ledger_effect(self.ledger), self.responses[start:])
        detail.update(client_order_id=cid, ledger_before=before, ledger_after=after,
                      cancel_result_status=result and result.get("status"))
        return outcome, detail

    async def c04(self, port):
        cid, start, bid = self.prefix + "c04", len(self.responses), self.bid()
        price = ((bid * Decimal(self.plan["c04_price_ratio"])).quantize(CENT, ROUND_DOWN)
                 + Decimal(self.plan["c04_sub_penny_increment"]))
        if price < 1 or price > bid * Decimal(self.plan["max_price_ratio"]):
            return "unobserved", {"unobserved_reason": "reference_price_outside_sub_penny_bounds",
                                  "reference_bid": str(bid)}
        effect_before, error = ledger_effect(self.ledger), None
        try:
            await port.submit(self.order(cid, price))
        except Exception as exc:
            error = describe(exc)
        state = intent_state(self.ledger, cid)
        outcome, detail = judge_c04(self.responses[start:], state, error, effect_before, ledger_effect(self.ledger),
                                    refusal_record(self.ledger, cid))
        detail.update(client_order_id=cid, limit_price=str(price), reference_bid=str(bid), ledger=state,
                      effect_before=effect_before, effect_after=ledger_effect(self.ledger))
        return outcome, detail

    async def run_cases(self, port):
        steps = {"C01": self.c01, "C02": self.c02, "C05": self.c05, "C04": self.c04}
        for spec in self.plan["cases"]:
            if self.interrupted:
                return
            start = len(self.responses)
            try:
                outcome, detail = await steps[spec["id"]](port)
            except Exception as exc:
                outcome, detail = "error", {"error": describe(exc)}
            requests = self.responses[start:]
            reached = bool(requests) and outcome != "unobserved"
            evidence = "native_paper" if reached else "none"
            if spec["id"] == "C05" and reached and not any(r["kind"] == "cancel" for r in requests):
                # Only the fault request (DELETE) qualifies; a client-id GET alone does not.
                evidence = "engine_short_circuit"
                detail["delete_sent"] = False
            self.cases.append({"id": spec["id"], "name": spec["name"], "outcome": outcome,
                               "evidence_class": evidence,
                               "requests": requests, "detail": detail})
            if outcome in ("failed", "error"):
                return  # Stop after the first unexpected result; never retry.

    async def cleanup(self, port):
        out = {"client_id_prefix": self.prefix, "cancels": [], "flat": None}
        try:
            if await self._cancel_and_prove(port, out):
                return out
        except Exception as exc:  # any cleanup failure leaves the run marked, never silently clean
            out.update(proof="failed", flat=False, error=describe(exc))
        if out["flat"] is not True:
            marker = self.run_dir / "CLEANUP_REQUIRED"
            try:
                marker.write_text(json.dumps({"client_id_prefix": self.prefix, "at": time.time()}) + "\n")
                out["marker"] = "CLEANUP_REQUIRED written in the run state directory"
            except OSError as exc:
                out["marker_error"] = describe(exc)
            print("CLEANUP_REQUIRED: " + str(marker), file=sys.stderr)
        else:
            self.in_flight.unlink(missing_ok=True)  # Removed only after flat is proven.
        return out

    async def _cancel_and_prove(self, port, out):
        """Cancel this run's open intents and prove flat into ``out``; True when
        no broker write ever happened, so no proof is required."""
        for intent in self.ledger.intents():
            if intent.client_id.startswith(self.prefix) and intent.submit_attempted and not intent.terminal:
                entry = {"client_order_id": intent.client_id}
                try:
                    final = await port.cancel(intent.client_id)
                    entry["result_status"] = final and final.get("status")
                except Exception as exc:
                    entry["error"] = describe(exc)
                entry["ledger"] = await self.settle(intent.client_id)
                out["cancels"].append(entry)
        if self.posts == 0 and not any(i.submit_attempted for i in self.ledger.intents()):
            out["proof"] = "not_required_no_broker_writes"
            self.in_flight.unlink(missing_ok=True)
            return True
        try:
            snap = await port.snapshot()
            rec = reconcile(self.ledger, snap, self.baseline_cash)
            open_orders = sum(o["status"] not in TERMINAL for o in snap["orders"])
            out.update(proof="runner.reconcile over transport.snapshot", reconcile=rec, broker_open_orders=open_orders,
                       flat=(open_orders == 0 and rec["open_orders"] == 0 and rec["positions"] == 0
                             and not any(Decimal(p["qty"]) for p in snap["positions"])))
        except Exception as exc:
            out.update(proof="failed", flat=False, error=describe(exc))
        return False

    async def execute(self, factory, key, secret):
        try:
            port = self.controller.bind(factory(
                key, secret, [self.symbol], before_request=self.before_request,
                before_submit=self.controller.before_submit, sink_observation=self.controller.observe,
                request_observer=self.observe_response, history_start=datetime.now(timezone.utc)))
            self.builds += 1
        except Exception as exc:
            return self.receipt("not_started", error=describe(exc))
        self.controller.port = port
        try:
            await port.start(self.controller.quote, lambda order: None)
        except Exception as exc:
            try:
                await port.stop()  # start() stops itself on readiness failure; repeat is harmless.
            except Exception:
                pass
            return self.receipt("not_started", error=describe(exc))
        status = error = cleanup = stop_error = None
        try:
            with ExitStack() as stack:
                try:
                    await self.prepare(port, stack)
                    self.mark_in_flight()
                    await self.run_cases(port)
                except Refused as exc:
                    status, error = "refused", describe(exc)
                except Exception as exc:
                    error = describe(exc)
                finally:
                    self.cleaning = True
                    cleanup = await self.cleanup(port)
        finally:
            try:
                await port.stop()
            except Exception as exc:
                stop_error = describe(exc)
        return self.receipt(status, error=error, cleanup=cleanup, stop_error=stop_error)

    def receipt(self, status, *, error=None, cleanup=None, stop_error=None):
        done = {c["id"]: c for c in self.cases}
        cases = [done.get(s["id"]) or {"id": s["id"], "name": s["name"], "outcome": "not_run",
                                        "evidence_class": "none", "requests": [], "detail": {}}
                 for s in self.plan["cases"]]
        if (cleanup and cleanup.get("flat") is False) or self.in_flight.exists():
            status = "cleanup_required"
        elif status is None:
            if self.interrupted:
                status = "interrupted"
            elif error or stop_error:  # a transport that failed to stop never yields a pass
                status = "error"
            elif (all(c["outcome"] == "passed" and c["evidence_class"] == "native_paper" for c in cases)
                  and cleanup and cleanup.get("flat") is True):
                status = "native_faults_passed"
            elif any(c["outcome"] in ("failed", "error") for c in cases):
                status = "native_faults_failed"
            else:
                status = "native_faults_incomplete"
        return {"schema_version": 1, "kind": "native_fault_behaviour_receipt", "status": status,
                "broker": "alpaca", "endpoint": "paper", "gate": "native-fault-behaviour",
                "plan_sha256": self.plan_sha, "harness_sha256": sha256(__file__),
                "engine_sources_sha256": {n: sha256(ENGINE / n) for n in ("transport.py", "safety.py", "runner.py",
                                                                         "../order-contract/order_contract.py")},
                "started_at": self.started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
                "client_id_prefix": self.prefix, "symbol": self.symbol, "transport_builds": self.builds,
                "posts_reserved": self.posts, "max_posts": self.plan["max_posts"],
                "submit_responses": sum(r["kind"] == "submit" for r in self.responses),
                "interrupted": self.interrupted, "error": error, "stop_error": stop_error,
                "cases": cases, "cleanup": cleanup,
                "c04_pre_send_exemption": ("FaultLedger exempts only client id %sc04 from invalid_price_increment; "
                                           "FaultTransport exempts only its limit price increment from the "
                                           "order-contract boundary" % self.prefix),
                "in_flight_marker_present": self.in_flight.exists(),
                "evidence_note": ("native_paper marks a case only when the engine transport's request observer "
                                  "recorded a broker HTTP response inside that case and, for C05, only when "
                                  "the DELETE itself was sent; C05 without a DELETE is engine_short_circuit. "
                                  "unobserved and not_run cases made no qualifying broker request. Price reference is the engine's "
                                  "streamed quote bid, not a last-trade read. No credential, account id or "
                                  "account fingerprint is recorded.")}


def run(env_file, state_root, out, *, factory=None, plan_path=PLAN_PATH):
    plan, plan_sha = load_plan(plan_path)
    root = dedicated_root(state_root)
    unresolved = sorted(str(p.relative_to(root)) for name in ("IN_FLIGHT", "CLEANUP_REQUIRED")
                        for p in root.glob("*/" + name))
    if unresolved:
        # An earlier run may still own an order the broker has not shown yet: refuse
        # before any credential read, transport or write until it is resolved by hand.
        receipt = {"schema_version": 1, "kind": "native_fault_behaviour_receipt", "status": "not_started",
                   "broker": "alpaca", "endpoint": "paper", "gate": "native-fault-behaviour",
                   "error": {"type": "Refused", "reason": "prior_run_marker_present"}, "unresolved_markers": unresolved}
        save(out, receipt)
        print(json.dumps({"status": "not_started", "unresolved_markers": unresolved}))
        return EXIT["not_started"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    prefix = "nf-%s-%s-" % (stamp, secrets.token_hex(3))
    run_dir = root / prefix.rstrip("-")
    run_dir.mkdir(parents=True, mode=0o700)
    key, secret = credentials(env_file)
    harness = Harness(plan, plan_sha, run_dir, prefix)
    handled = (signal.SIGINT, signal.SIGTERM)
    previous = {sig: signal.signal(sig, harness.on_signal) for sig in handled}  # before any transport exists
    try:
        receipt = asyncio.run(harness.execute(factory or fault_transport(prefix + "c04"), key, secret))
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        harness.ledger.close()
    del key, secret
    save(out, receipt)
    print(json.dumps({"status": receipt["status"], "posts_reserved": receipt["posts_reserved"],
                      "cases": {c["id"]: c["outcome"] for c in receipt["cases"]}}))
    return EXIT.get(receipt["status"], 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("run")
    for name in ("--env-file", "--state-root", "--out"):
        cmd.add_argument(name, type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.env_file, args.state_root, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
