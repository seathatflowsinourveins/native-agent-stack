"""Durable, offline-testable IBKR paper journal; no broker/network dependencies.

Reference primitives: native-agent-stack@2673696c, adaptive-paper/safety.py
387–411, 427–499, 817–894, 1354–1408. IBKR identity/fee semantics:
nautilus_trader@1b0a49d2 execution/parse.rs 55–147 and core_updates.rs 240–280.
This controller does not resolve the selected rc5 native recovery holds.
The caller must verify native bindings and supply observed identities/events.
"""

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading


class Refused(ValueError):
    """Admission or journal binding refused before transport."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def decimal(value):
    if isinstance(value, bool) or value is None:
        raise Refused("invalid_decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise Refused("invalid_decimal") from None
    if not result.is_finite():
        raise Refused("nonfinite_decimal")
    return result


def cents(value):
    return int((decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def price(value):
    result = decimal(value)
    if result <= 0 or result % Decimal("0.01") != 0:
        raise Refused("invalid_tick_price")
    return result


def whole(value):
    if type(value) is not int or value <= 0:
        raise Refused("whole_positive_shares_required")
    return value


@dataclass(frozen=True)
class Binding:
    broker: str
    endpoint: str
    account_fingerprint: str
    client_id: int
    plan_sha256: str
    source_sha256: str
    source_revision: str
    source_version: str
    schema: int = 1


@dataclass(frozen=True)
class Limits:
    start_cash_cents: int = 1_000_000
    order_shares: int = 10
    order_notional_cents: int = 200_000
    exposure_cents: int = 200_000
    gross_loss_cents: int = 10_000
    drawdown_cents: int = 10_000
    quote_age_ns: int = 3_000_000_000
    session_open_ns: int = 1_000_000_000_000
    session_close_ns: int = 2_000_000_000_000
    request_window_ns: int = 60_000_000_000
    request_calls: int = 8
    control_reserve: int = 3
    backoff_initial_ns: int = 1_000_000_000
    backoff_max_ns: int = 8_000_000_000


class PaperState:
    """One account writer with durable attempt, reservation and event economics.

    ``lock_root`` is mandatory: every IBKR writer for the account must use the
    same private root, independently of journal path, client ID and endpoint.
    ``clock`` returns integer UTC ns. Transport.submit(ref,payload), lookup(ref),
    cancel(identity) are injected; each consumes one frozen request budget unit.
    A submit transport returns {kind:accepted, identity:{observed fields}} or
    {kind:rejected, reason:...}. All other outcomes remain unknown. No retry loop.
    """

    def __init__(self, db_path, binding, *, lock_root, clock, stop_path, limits=None):
        self.path = Path(db_path)
        self.binding = binding
        self.limits = limits or Limits()
        self.clock = clock
        self.stop_path = Path(stop_path)
        self._mutex = threading.RLock()
        self._lock_fd = None
        self._transport = None
        self.db = None
        if not isinstance(binding, Binding) or not isinstance(self.limits, Limits):
            raise Refused("typed_binding_and_limits_required")
        if not re.fullmatch(r"[0-9a-f]{64}", binding.account_fingerprint):
            raise Refused("invalid_account_fingerprint")
        frozen = canonical({"binding": asdict(binding), "limits": asdict(self.limits),
                            "money_rule": "USD:cents:ROUND_HALF_EVEN:execution-total:final-fee",
                            "kill_policy": "cancel-owned:unresolved-blocked"})
        root = Path(lock_root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock_fd = os.open(root / (binding.account_fingerprint+".lock"),
                                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused("account_writer_already_running") from None
            existed = self.path.exists()
            if existed:
                # No writable connect, journal-mode pragma, schema or metadata
                # changes may precede this check, even for a different account.
                if self.path.is_symlink():
                    raise Refused("journal_symlink_refused")
                with closing(sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro", uri=True)) as check:
                    row = check.execute("SELECT value FROM meta WHERE key='binding'").fetchone()
                    if not row or row[0] != frozen:
                        raise Refused("immutable_binding_mismatch")
            self._validate_binding()
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None,
                                      check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            with self._tx():
                for ddl in [
                    "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS orders(intent TEXT PRIMARY KEY,order_ref TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,attempted INTEGER NOT NULL CHECK(attempted=1),reserved_cents INTEGER NOT NULL,filled INTEGER NOT NULL DEFAULT 0,cancelled INTEGER NOT NULL DEFAULT 0,identity TEXT,reason TEXT)",
                    "CREATE TABLE IF NOT EXISTS executions(exec_id TEXT PRIMARY KEY,intent TEXT NOT NULL REFERENCES orders(intent),payload TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS commissions(exec_id TEXT PRIMARY KEY REFERENCES executions(exec_id),payload TEXT NOT NULL,posting TEXT NOT NULL,cents INTEGER NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS positions(symbol TEXT PRIMARY KEY,quantity INTEGER NOT NULL,cost TEXT NOT NULL,mark TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL)",
                ]:
                    self.db.execute(ddl)
                if not existed:
                    for key, value in {"binding": frozen, "cash_cents": self.limits.start_cash_cents,
                                       "fees_cents": 0, "gross_loss_cents": 0, "gross_loss_exact_cents": "0",
                                       "peak_equity_cents": self.limits.start_cash_cents,
                                       "halt": None, "stream_block": False, "contradiction": False,
                                       "alerts": [], "budget": {"window_start_ns": self._now(), "used": 0,
                                                                 "backoff_ns": 0, "blocked_until_ns": 0}}.items():
                        self._set(key, value)
                elif self.db.execute("SELECT 1 FROM orders LIMIT 1").fetchone():
                    self._set("stream_block", True)
                    self._event("restart_reconciliation_required", {})
            if not existed:
                fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except BaseException:
            self.close()
            raise

    def _validate_binding(self):
        b = self.binding
        if b.broker != "IBKR" or b.endpoint != "127.0.0.1:4002" or b.schema != 1:
            raise Refused("unsupported_broker_endpoint_schema")
        if type(b.client_id) is not int or b.client_id <= 0 or b.client_id % 1000 == 0:
            raise Refused("invalid_client_owner")
        for value in [b.plan_sha256, b.source_sha256]:
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise Refused("full_digest_required")
        if b.source_version != "2.0.0rc5" or b.source_revision != "1b0a49d2792a9432a3aca3fcb617ce7a630d905e":
            raise Refused("selected_rc5_source_required")
        l = self.limits
        if any(type(v) is not int or v <= 0 for v in asdict(l).values()):
            raise Refused("positive_integer_limits_required")
        if l.control_reserve >= l.request_calls or l.session_open_ns >= l.session_close_ns or l.backoff_initial_ns > l.backoff_max_ns:
            raise Refused("contradictory_limits")

    def close(self):
        """Close journal and release account ownership; halt remains in SQLite."""
        if self.db is not None:
            self.db.close()
            self.db = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    @contextmanager
    def _tx(self):
        with self._mutex:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise Refused("integer_clock_required")
        return now

    def _get(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _set(self, key, value):
        # The binding was initially supplied as serialized canonical JSON.
        stored = value if key == "binding" else canonical(value)
        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, stored))

    def _event(self, kind, payload):
        self.db.execute("INSERT INTO events(kind,payload) VALUES(?,?)", (kind, canonical(payload)))

    def _block(self, reason, *, contradiction=False):
        self._set("stream_block", True)
        if contradiction:
            self._set("contradiction", True)
        alerts = self._get("alerts")
        if reason not in alerts:
            alerts.append(reason)
            self._set("alerts", alerts)
        self._event("alert", {"reason": reason})
        return False

    def _halt(self, reason):
        if self._get("halt") is None:
            self._set("halt", reason)
            self._event("halt", {"reason": reason})

    def _pending_fees(self):
        return self.db.execute("SELECT 1 FROM executions e LEFT JOIN commissions c USING(exec_id) WHERE c.exec_id IS NULL OR c.posting!='final' LIMIT 1").fetchone() is not None

    def _ready(self):
        return not (self._get("halt") or self._get("stream_block") or self._get("contradiction")
                    or self._pending_fees() or self.db.execute("SELECT 1 FROM orders WHERE status IN ('unknown','cancel_pending','cancel_unknown') LIMIT 1").fetchone())

    def _order(self, intent):
        return self.db.execute("SELECT * FROM orders WHERE intent=?", (intent,)).fetchone()

    def _request(self, control=False):
        """Durably consume a call or retain bounded pause, with no transport retry."""
        now = self._now()
        b = self._get("budget")
        if now < b["window_start_ns"]:
            raise Refused("clock_regressed")
        if now >= b["window_start_ns"] + self.limits.request_window_ns:
            if not control and now < b["blocked_until_ns"]:
                self._event("request_paused", b)
                return False
            b = {"window_start_ns": now, "used": 0, "backoff_ns": 0, "blocked_until_ns": 0}
        limit = self.limits.request_calls if control else self.limits.request_calls-self.limits.control_reserve
        if b["used"] >= limit:
            b["backoff_ns"] = min(self.limits.backoff_max_ns,
                                    max(self.limits.backoff_initial_ns, b["backoff_ns"]*2))
            b["blocked_until_ns"] = max(now+b["backoff_ns"], b["window_start_ns"]+self.limits.request_window_ns)
            self._set("budget", b)
            self._event("request_paused", b)
            return False
        b["used"] += 1
        self._set("budget", b)
        return True

    def _payload(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"symbol", "side", "quantity", "limit_price", "currency"}:
            raise Refused("complete_order_payload_required")
        if not isinstance(payload["symbol"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", payload["symbol"]):
            raise Refused("invalid_instrument_identity")
        if payload["side"] not in ["BUY", "SELL"] or payload["currency"] != "USD":
            raise Refused("unsupported_side_currency")
        qty = whole(payload["quantity"])
        px = price(payload["limit_price"])
        if qty > self.limits.order_shares or cents(qty*px) > self.limits.order_notional_cents:
            raise Refused("single_order_cap_exceeded")
        return qty, px

    def _risk(self, payload, quote_price, quote_time_ns):
        qty, px = self._payload(payload)
        now = self._now()
        fresh_mark = price(quote_price)
        if type(quote_time_ns) is not int or not 0 <= now-quote_time_ns <= self.limits.quote_age_ns:
            raise Refused("quote_age_invalid")
        if not self.limits.session_open_ns <= now < self.limits.session_close_ns:
            raise Refused("session_closed")
        symbol = payload["symbol"]
        position = self.db.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
        quantity = position["quantity"] if position else 0
        rows = self.db.execute("SELECT * FROM orders WHERE status NOT IN ('filled','cancelled','rejected')").fetchall()
        reserved_buy = sum(o["reserved_cents"] for o in rows)
        reserved_sell = sum(json.loads(o["payload"])["quantity"]-o["filled"] for o in rows
                            if json.loads(o["payload"])["side"] == "SELL" and json.loads(o["payload"])["symbol"] == symbol)
        if payload["side"] == "SELL":
            if qty > quantity-reserved_sell:
                raise Refused("insufficient_unreserved_position")
            return 0
        reserve = cents(qty*px)
        if reserve > self._get("cash_cents")-reserved_buy:
            raise Refused("insufficient_cash")
        exposure = sum(cents(p["quantity"]*(fresh_mark if p["symbol"] == symbol else decimal(p["mark"])))
                       for p in self.db.execute("SELECT * FROM positions"))
        if exposure+reserved_buy+reserve > self.limits.exposure_cents:
            raise Refused("aggregate_exposure_cap_exceeded")
        return reserve

    def submit(self, intent, payload, transport, *, quote_price, quote_time_ns):
        """Reserve and commit one attempt before any submit; same ID never resends."""
        if not isinstance(intent, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", intent):
            raise Refused("invalid_intent_identity")
        self._payload(payload)
        encoded = canonical(payload)
        with self._mutex:
            previous = self._order(intent)
            if previous:
                if previous["payload"] != encoded:
                    raise Refused("intent_payload_changed")
                return previous["status"]
            if self.stop_path.exists():
                self.stop("independent_STOP", transport)
            reservation = self._risk(payload, quote_price, quote_time_ns)
            if self._get("halt"):
                raise Refused("halted:"+self._get("halt"))
            if not self._ready():
                raise Refused("reconciliation_required")
            ref = "I-"+hashlib.sha256((self.binding.account_fingerprint+self.binding.plan_sha256+intent).encode()).hexdigest()[:24]
            with self._tx():
                admitted = self._request()
                if admitted:
                    self.db.execute("INSERT INTO orders(intent,order_ref,payload,status,attempted,reserved_cents) VALUES(?,?,?,'unknown',1,?)",
                                    (intent, ref, encoded, reservation))
                    self._event("durable_submission_attempt", {"intent": intent, "order_ref": ref,
                                                                "payload_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                                                                "reserved_cents": reservation})
            if not admitted:
                raise Refused("request_budget_exhausted")
            self._transport = transport
            try:
                result = transport.submit(ref, json.loads(encoded))
            except Exception as exc:
                with self._tx():
                    self._block("submission_outcome_unknown")
                    self._event("submit_unknown", {"intent": intent, "exception": type(exc).__name__})
                return "unknown"
            with self._tx():
                if isinstance(result, dict) and result.get("kind") == "rejected" and isinstance(result.get("reason"), str) and result["reason"]:
                    self.db.execute("UPDATE orders SET status='rejected',reserved_cents=0,reason=? WHERE intent=?", (result["reason"], intent))
                    self._event("definitive_rejection", {"intent": intent, "reason": result["reason"]})
                    return "rejected"
                if isinstance(result, dict) and result.get("kind") == "accepted" and self._bind_identity(intent, result.get("identity")):
                    self.db.execute("UPDATE orders SET status='accepted' WHERE intent=?", (intent,))
                    self._event("accepted", {"intent": intent})
                    return "accepted"
                self._block("submission_outcome_unknown")
                return "unknown"

    def _bind_identity(self, intent, observed):
        order = self._order(intent)
        if not order or not isinstance(observed, dict) or not observed or set(observed)-{"order_ref", "client_order_id", "venue_order_id", "order_id", "perm_id"}:
            return self._block("unknown_order_identity", contradiction=True)
        value = dict(observed)
        ref = order["order_ref"]
        supplied_ref = value.get("order_ref", value.get("client_order_id"))
        if not isinstance(supplied_ref, str) or supplied_ref.rsplit(":", 1)[0] != ref:
            return self._block("unknown_order_reference", contradiction=True)
        if "client_order_id" in value and value["client_order_id"] != ref:
            return self._block("contradictory_client_order_id", contradiction=True)
        if "venue_order_id" in value:
            venue = value["venue_order_id"]
            if not isinstance(venue, str) or not re.fullmatch(r"(?:PERM-)?[1-9][0-9]*", venue):
                return self._block("unknown_venue_order_id", contradiction=True)
            key = "perm_id" if venue.startswith("PERM-") else "order_id"
            parsed = int(venue.removeprefix("PERM-"))
            if key in value and value[key] != parsed:
                return self._block("contradictory_venue_order_id", contradiction=True)
            value[key] = parsed
        if not any(key in value for key in ["order_id", "perm_id"]):
            return self._block("native_id_unobserved")
        if any(type(value[k]) is not int or value[k] <= 0 for k in ["order_id", "perm_id"] if k in value):
            return self._block("invalid_native_id", contradiction=True)
        old = json.loads(order["identity"]) if order["identity"] else {}
        for key in set(old)&set(value):
            if old[key] != value[key]:
                return self._block("native_identity_changed", contradiction=True)
        combined = {**old, **value}
        for other in self.db.execute("SELECT intent,identity FROM orders WHERE identity IS NOT NULL AND intent!=?", (intent,)):
            ident = json.loads(other["identity"])
            if any(k in combined and ident.get(k) == combined[k] for k in ["order_id", "perm_id"]):
                return self._block("native_identity_alias", contradiction=True)
        self.db.execute("UPDATE orders SET identity=? WHERE intent=?", (canonical(combined), intent))
        return True

    def lookup(self, intent, transport):
        """Explicit query by durable reference; absence is never permission to send."""
        with self._mutex:
            self._transport = transport
            order = self._order(intent)
            if not order:
                raise Refused("intent_not_found")
            with self._tx():
                admitted = self._request(control=True)
            if not admitted:
                raise Refused("request_budget_exhausted")
            try:
                identity = transport.lookup(order["order_ref"])
            except Exception:
                identity = None
            with self._tx():
                if identity is None:
                    self._block("lookup_unresolved")
                    return "unknown"
                if not self._bind_identity(intent, identity):
                    return "blocked"
                if order["status"] == "unknown":
                    self.db.execute("UPDATE orders SET status='accepted' WHERE intent=?", (intent,))
                self._event("lookup_adopted_identity", {"intent": intent})
                return self._order(intent)["status"]

    def execution(self, intent, exec_id, quantity, fill_price, currency, *, identity=None, transport=None):
        """Economic fill keyed by observed execution ID; status does not post cash."""
        with self._tx():
            order = self._order(intent)
            if not order or not order["identity"]:
                return self._block("unknown_execution_order", contradiction=True)
            if not isinstance(exec_id, str) or not exec_id or len(exec_id) > 160:
                return self._block("unknown_execution_identity", contradiction=True)
            try:
                qty = whole(quantity)
                px = price(fill_price)
            except Refused:
                return self._block("invalid_execution_economics", contradiction=True)
            if currency != "USD":
                return self._block("unknown_execution_currency", contradiction=True)
            if identity is not None and not self._bind_identity(intent, identity):
                return False
            payload = {"intent": intent, "quantity": qty, "price": str(px), "currency": currency}
            encoded = canonical(payload)
            previous = self.db.execute("SELECT payload FROM executions WHERE exec_id=?", (exec_id,)).fetchone()
            if previous:
                if previous[0] != encoded:
                    return self._block("execution_payload_changed", contradiction=True)
                return True
            original = json.loads(order["payload"])
            if order["status"] == "rejected" or order["filled"]+qty > original["quantity"]:
                return self._block("execution_quantity_contradiction", contradiction=True)
            symbol = original["symbol"]
            position = self.db.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
            old_qty = position["quantity"] if position else 0
            old_cost = decimal(position["cost"]) if position else Decimal(0)
            amount = cents(qty*px)
            if original["side"] == "BUY":
                new_qty, new_cost = old_qty+qty, old_cost+Decimal(amount)
                cash_delta = -amount
            else:
                if qty > old_qty:
                    return self._block("execution_short_position", contradiction=True)
                disposed_cost = old_cost*Decimal(qty)/Decimal(old_qty)
                new_qty, new_cost = old_qty-qty, old_cost-disposed_cost
                cash_delta = amount
                realized = Decimal(amount)-disposed_cost
                if realized < 0:
                    exact_loss = decimal(self._get("gross_loss_exact_cents"))-realized
                    self._set("gross_loss_exact_cents", str(exact_loss))
                    self._set("gross_loss_cents", int(exact_loss.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)))
            self.db.execute("INSERT INTO executions VALUES(?,?,?)", (exec_id, intent, encoded))
            self._set("cash_cents", self._get("cash_cents")+cash_delta)
            if new_qty:
                self.db.execute("INSERT OR REPLACE INTO positions VALUES(?,?,?,?)", (symbol, new_qty, str(new_cost), str(px)))
            else:
                self.db.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
            filled = order["filled"]+qty
            cancelled = max(0, original["quantity"]-filled) if order["status"] == "cancelled" else 0
            status = "filled" if filled == original["quantity"] else order["status"]
            reserve = 0 if status in ["cancelled", "filled"] or original["side"] == "SELL" else cents((original["quantity"]-filled)*decimal(original["limit_price"]))
            self.db.execute("UPDATE orders SET filled=?,cancelled=?,status=?,reserved_cents=? WHERE intent=?", (filled, cancelled, status, reserve, intent))
            self._event("execution", {"exec_id": exec_id, **payload, "cash_delta_cents": cash_delta})
            self._risk_latch()
        self._cancel_halted(transport)
        return True

    def commission(self, exec_id, amount, currency, posting, *, transport=None):
        """Late commission keyed by execution ID, with explicit posting/currency.

        Caller must keep raw pending sentinel distinguishable: a rc5 Money(0)
        alone is insufficient to prove the broker has posted a final zero fee.
        """
        with self._tx():
            if not self.db.execute("SELECT 1 FROM executions WHERE exec_id=?", (exec_id,)).fetchone():
                return self._block("unknown_commission_execution", contradiction=True)
            try:
                value = decimal(amount)
            except Refused:
                return self._block("invalid_commission", contradiction=True)
            if currency != "USD" or posting not in ["pending", "final"]:
                return self._block("unknown_commission_currency_posting")
            if value == -1 and posting == "final":
                return self._block("commission_pending_sentinel")
            payload = {"amount": str(value), "currency": currency, "posting": posting}
            encoded = canonical(payload)
            old = self.db.execute("SELECT * FROM commissions WHERE exec_id=?", (exec_id,)).fetchone()
            if old and old["posting"] == "final":
                if old["payload"] != encoded:
                    return self._block("commission_payload_changed", contradiction=True)
                return True
            if old and old["payload"] == encoded:
                return True
            posted = cents(value) if posting == "final" else 0
            self.db.execute("INSERT OR REPLACE INTO commissions VALUES(?,?,?,?)", (exec_id, encoded, posting, posted))
            if posting == "final":
                self._set("fees_cents", self._get("fees_cents")+posted)
                self._set("cash_cents", self._get("cash_cents")-posted)
                self._risk_latch()
            self._event("commission", {"exec_id": exec_id, **payload, "posted_cents": posted})
        self._cancel_halted(transport)
        return True

    def status(self, intent, status, cumulative_filled):
        """Observe lifecycle only; cumulative progress may never reduce real fills."""
        with self._tx():
            order = self._order(intent)
            if not order or not order["identity"]:
                return self._block("unknown_status_order", contradiction=True)
            qty = json.loads(order["payload"])["quantity"]
            if type(cumulative_filled) is not int or not 0 <= cumulative_filled <= qty or status not in ["accepted", "cancel_pending", "cancelled", "filled", "rejected"]:
                return self._block("unknown_order_status", contradiction=True)
            if cumulative_filled > order["filled"]:
                return self._block("status_missing_executions")
            if status == "filled" and order["filled"] != qty:
                return self._block("status_missing_executions")
            if status == "rejected" and order["filled"]:
                return self._block("rejection_after_fill", contradiction=True)
            if status in ["cancelled", "rejected"]:
                self.db.execute("UPDATE orders SET status=?,cancelled=?,reserved_cents=0 WHERE intent=?",
                                (status, qty-order["filled"] if status == "cancelled" else 0, intent))
            elif order["status"] not in ["filled", "cancelled", "rejected", "cancel_pending", "cancel_unknown"]:
                self.db.execute("UPDATE orders SET status=? WHERE intent=?", (status, intent))
            self._event("order_status", {"intent": intent, "status": status, "cumulative_filled": cumulative_filled})
            return True

    def cancel(self, intent, transport):
        with self._mutex:
            self._transport = transport
            order = self._order(intent)
            if not order:
                raise Refused("intent_not_found")
            if order["status"] in ["filled", "cancelled", "rejected"]:
                return order["status"]
            with self._tx():
                if not order["identity"]:
                    self._block("cancel_identity_unresolved")
                    return "cancel_unknown"
                admitted = self._request(control=True)
                if admitted:
                    self.db.execute("UPDATE orders SET status='cancel_pending' WHERE intent=?", (intent,))
                    self._event("cancel_attempt", {"intent": intent})
            if not admitted:
                raise Refused("request_budget_exhausted")
            try:
                result = transport.cancel(json.loads(order["identity"]))
            except Exception:
                result = None
            if not isinstance(result, dict) or result.get("kind") != "pending":
                with self._tx():
                    self.db.execute("UPDATE orders SET status='cancel_unknown' WHERE intent=?", (intent,))
                    self._block("cancel_outcome_unknown")
                return "cancel_unknown"
            return "cancel_pending"

    def disconnect(self, reason):
        with self._tx():
            return self._block("disconnect:"+str(reason))

    def _risk_latch(self):
        exposure = sum(cents(p["quantity"]*decimal(p["mark"])) for p in self.db.execute("SELECT * FROM positions"))
        pending = self.db.execute("SELECT COALESCE(sum(reserved_cents),0) FROM orders WHERE status NOT IN ('filled','cancelled','rejected')").fetchone()[0]
        if exposure+pending > self.limits.exposure_cents:
            self._halt("aggregate_exposure_cap_exceeded")
        if decimal(self._get("gross_loss_exact_cents")) > self.limits.gross_loss_cents:
            self._halt("gross_loss_cap_exceeded")
        equity = self._get("cash_cents")+sum(cents(p["quantity"]*decimal(p["mark"])) for p in self.db.execute("SELECT * FROM positions"))
        peak = max(self._get("peak_equity_cents"), equity)
        self._set("peak_equity_cents", peak)
        if peak-equity > self.limits.drawdown_cents:
            self._halt("drawdown_cap_exceeded")

    def _cancel_halted(self, transport=None):
        if self._get("halt") is not None:
            selected = transport if transport is not None else self._transport
            if selected is None:
                with self._tx():
                    self._block("halt_cancel_transport_unavailable")
            else:
                self.stop(self._get("halt"), selected)

    def observe_risk(self, marks, *, transport=None):
        """Deterministic mark observation; numeric halt persists even after restart."""
        with self._tx():
            held = {p[0] for p in self.db.execute("SELECT symbol FROM positions")}
            if not isinstance(marks, dict) or set(marks) != held:
                return self._block("incomplete_position_marks")
            try:
                values = {s: str(price(v)) for s, v in marks.items()}
            except Refused:
                return self._block("invalid_position_mark")
            for symbol, value in values.items():
                self.db.execute("UPDATE positions SET mark=? WHERE symbol=?", (value, symbol))
            self._risk_latch()
            self._event("risk_marks", values)
        self._cancel_halted(transport)
        return self._get("halt") is None

    def stop(self, reason, transport):
        """Latch first, then apply cancel-owned; failures retain blocked ownership."""
        with self._tx():
            self._halt(str(reason))
        orders = self.db.execute("SELECT intent FROM orders WHERE status NOT IN ('filled','cancelled','rejected','cancel_pending','cancel_unknown')").fetchall()
        for order in orders:
            try:
                self.cancel(order[0], transport)
            except Refused as exc:
                with self._tx():
                    self._block("stop_cancel_refused:"+str(exc))
        return False

    def poll_stop(self, transport):
        if self.stop_path.exists():
            return self.stop("independent_STOP", transport)
        return self._get("halt") is None

    def reconcile(self, snapshot):
        """Compare complete observations exactly; no adopted cash/flatness resets.

        Snapshot parts: complete flags orders/executions/commissions/positions/
        cash; all owned order identities, status and filled quantity; execution
        ID and final commission ID sets; symbol:whole quantity map; USD cash/fees
        decimals and fee_posting=final. Unknown or missing IDs block. Snapshot
        collection's native transport requests must use ``request_control``.
        """
        with self._tx():
            required = ["orders", "executions", "commissions", "positions", "cash"]
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("complete"), dict) or any(snapshot["complete"].get(k) is not True for k in required):
                return self._block("incomplete_snapshots")
            if self._get("contradiction"):
                return self._block("contradiction_requires_adjudication")
            if self._pending_fees():
                return self._block("commission_pending")
            if self.db.execute("SELECT 1 FROM orders WHERE identity IS NULL OR status IN ('unknown','cancel_pending','cancel_unknown') LIMIT 1").fetchone():
                return self._block("unresolved_order_or_cancel")
            try:
                if snapshot.get("currency") != "USD" or snapshot.get("fee_posting") != "final":
                    return self._block("snapshot_currency_posting_unknown")
                # Exact money agreement after predeclared cents conversion.
                if cents(snapshot["cash"]) != self._get("cash_cents") or cents(snapshot["fees"]) != self._get("fees_cents"):
                    return self._block("snapshot_cash_fee_mismatch")
                positions = {p["symbol"]: p["quantity"] for p in self.db.execute("SELECT * FROM positions")}
                if not isinstance(snapshot["positions"], dict) or any(type(v) is not int or v <= 0 for v in snapshot["positions"].values()) or snapshot["positions"] != positions:
                    return self._block("snapshot_position_mismatch")
                for table, key in [("executions", "executions"), ("commissions", "commissions")]:
                    expected = {r[0] for r in self.db.execute("SELECT exec_id FROM "+table)}
                    observed = snapshot[key]
                    if not isinstance(observed, list) or len(observed) != len(set(observed)) or set(observed) != expected:
                        return self._block("snapshot_"+key+"_mismatch")
                observed_orders = snapshot["orders"]
                if not isinstance(observed_orders, list):
                    return self._block("snapshot_orders_invalid")
                known = {o["intent"]: o for o in self.db.execute("SELECT * FROM orders WHERE identity IS NOT NULL")}
                seen = set()
                for observed in observed_orders:
                    intent = observed["intent"]
                    if intent not in known or intent in seen:
                        return self._block("snapshot_unknown_or_duplicate_order")
                    order = known[intent]
                    if type(observed["filled"]) is not int or observed["filled"] != order["filled"] or observed["status"] != order["status"]:
                        return self._block("snapshot_order_progress_mismatch")
                    if not self._bind_identity(intent, observed["identity"]):
                        return False
                    seen.add(intent)
                if seen != set(known):
                    return self._block("snapshot_missing_orders")
            except (KeyError, TypeError, Refused, ValueError):
                return self._block("snapshot_malformed")
            self._set("stream_block", False)
            self._event("reconciled", {"position_quantities": positions, "cash_cents": self._get("cash_cents"), "fees_cents": self._get("fees_cents")})
            return self._get("halt") is None

    def request_control(self):
        """Reserve one native snapshot/query/cancel request before its transport."""
        with self._tx():
            admitted = self._request(control=True)
        if not admitted:
            raise Refused("request_budget_exhausted")

    def snapshot(self):
        """Sanitized committed journal view for observation/evidence, without paths."""
        with self._mutex:
            orders = []
            for row in self.db.execute("SELECT * FROM orders ORDER BY intent"):
                order = dict(row)
                order["payload"] = json.loads(order["payload"])
                order["identity"] = json.loads(order["identity"]) if order["identity"] else None
                order["remaining"] = order["payload"]["quantity"]-order["filled"]-order["cancelled"]
                orders.append(order)
            executions = [{"exec_id": r["exec_id"], **json.loads(r["payload"])} for r in self.db.execute("SELECT * FROM executions ORDER BY exec_id")]
            commissions = [{"exec_id": r["exec_id"], **json.loads(r["payload"]), "posted_cents": r["cents"]} for r in self.db.execute("SELECT * FROM commissions ORDER BY exec_id")]
            return {"orders": orders, "executions": executions, "commissions": commissions,
                    "positions": {p["symbol"]: p["quantity"] for p in self.db.execute("SELECT * FROM positions ORDER BY symbol")},
                    "cash_cents": self._get("cash_cents"), "fees_cents": self._get("fees_cents"),
                    "gross_loss_cents": self._get("gross_loss_cents"), "halt": self._get("halt"),
                    "gross_loss_exact_cents": self._get("gross_loss_exact_cents"),
                    "ready": bool(self._ready()), "alerts": self._get("alerts"), "budget": self._get("budget"),
                    "event_count": self.db.execute("SELECT count(*) FROM events").fetchone()[0]}
