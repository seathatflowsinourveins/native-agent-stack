"""Durable deterministic risk/accounting for a bounded paper-only trial.

No broker transport, credentials, strategy, or model calls live in this module.
Callers must reconcile broker state before resuming entries after interruption.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading

D = Decimal
ZERO = D(0)
TERMINAL = frozenset({"filled", "canceled", "expired", "rejected", "not_sent"})
RANK = {"reserved": 0, "pending_new": 1, "accepted": 2, "new": 2,
        "accepted_for_bidding": 2, "held": 2, "partially_filled": 3,
        "pending_cancel": 4, "done_for_day": 4,
        "filled": 5, "canceled": 5, "expired": 5, "rejected": 5, "not_sent": 5}
DEFAULT_STOP = Path.home() / ".local/state/native-agent-stack/alpaca-paper/STOP"


class SafetyError(RuntimeError):
    """Bounded reason code, safe to retain without broker/account secrets."""


def decimal(value, *, zero=False, maximum=D("1000000000")):
    if type(value) not in (str, int, Decimal):
        raise SafetyError("decimal_text_or_integer_required")
    if type(value) is Decimal:
        if not value.is_finite() or value.is_signed() or value > maximum:
            raise SafetyError("decimal_out_of_bounds")
        sign, digits, exponent = value.as_tuple()
        digits = list(digits)
        while len(digits) > 1 and digits[-1] == 0 and exponent < 0:
            digits.pop()
            exponent += 1
        if not -9 <= exponent <= 9:
            raise SafetyError("decimal_precision_exceeded")
        # Fixed-point formatting must be bounded before expanding exponents.
        text = format(D((sign, tuple(digits), exponent)), "f")
    else:
        text = str(value)
    if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,9})?", text):
        raise SafetyError("invalid_decimal")
    result = D(text)
    if not result.is_finite() or result < 0 or (not zero and result == 0) or result > maximum:
        raise SafetyError("decimal_out_of_bounds")
    return result


def instant(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise SafetyError("invalid_timestamp")
    return float(value)


def symbol_name(value):
    if type(value) is not str or not re.fullmatch(r"[A-Z]{1,5}(?:[.-][A-Z])?", value):
        raise SafetyError("invalid_symbol")
    return value


@dataclass(frozen=True)
class RiskLimits:
    capital_usd: Decimal = D("10000")
    max_gross_exposure_usd: Decimal = D("5000")
    max_order_notional_usd: Decimal = D("1000")
    max_order_qty: Decimal = D("1")
    max_gross_loss_usd: Decimal = D("25")
    max_drawdown_usd: Decimal = D("25")
    max_spread_bps: Decimal = D("15")
    max_held_symbols: int = 10
    max_outstanding_orders: int = 20
    max_rest_per_minute: int = 200
    max_submits_per_minute: int = 180
    quote_max_age_seconds: int = 3
    trial_seconds: int = 300
    cleanup_seconds: int = 120
    min_entry_close_seconds: int = 300

    def __post_init__(self):
        for field in ("capital_usd", "max_gross_exposure_usd", "max_order_notional_usd",
                      "max_order_qty", "max_gross_loss_usd", "max_drawdown_usd", "max_spread_bps"):
            object.__setattr__(self, field, decimal(getattr(self, field)))
        if (self.capital_usd > D("1000000") or self.max_gross_exposure_usd > self.capital_usd
                or self.max_order_notional_usd > min(self.max_gross_exposure_usd, D("10000"))
                or self.max_order_qty > 100 or self.max_order_qty != self.max_order_qty.to_integral_value()
                or self.max_gross_loss_usd > self.capital_usd / 10
                or self.max_drawdown_usd > self.capital_usd / 10 or self.max_spread_bps > 100):
            raise SafetyError("risk_limit_out_of_bounds")
        caps = {"max_held_symbols": 50, "max_outstanding_orders": 100,
                "max_rest_per_minute": 200, "max_submits_per_minute": 180,
                "quote_max_age_seconds": 3, "trial_seconds": 3600,
                "cleanup_seconds": 600, "min_entry_close_seconds": 3600}
        for field, cap in caps.items():
            value = getattr(self, field)
            if type(value) is not int or not 1 <= value <= cap:
                raise SafetyError("integer_limit_out_of_bounds")
        if (self.max_submits_per_minute > self.max_rest_per_minute - 20
                or self.min_entry_close_seconds < self.cleanup_seconds):
            raise SafetyError("cleanup_reserve_required")


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: float

    def __post_init__(self):
        symbol_name(self.symbol)
        object.__setattr__(self, "bid", decimal(self.bid))
        object.__setattr__(self, "ask", decimal(self.ask))
        object.__setattr__(self, "timestamp", instant(self.timestamp))
        if self.ask < self.bid:
            raise SafetyError("crossed_quote")


@dataclass(frozen=True)
class Intent:
    client_id: str
    symbol: str
    side: str
    qty: Decimal
    limit_price: Decimal
    status: str
    filled_qty: Decimal
    average_price: Decimal | None
    broker_id: str | None
    newly_reserved: bool = False
    submit_attempted: bool = False

    @property
    def remaining_qty(self):
        return self.qty - self.filled_qty

    @property
    def terminal(self):
        return self.status in TERMINAL


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: Decimal
    cost_basis_usd: Decimal

    @property
    def average_cost(self):
        return self.cost_basis_usd / self.qty if self.qty else ZERO


@dataclass(frozen=True)
class AccountState:
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    cumulative_realized_loss_usd: Decimal
    gross_loss_usd: Decimal
    cash_delta_usd: Decimal
    gross_exposure_usd: Decimal
    pending_buy_notional_usd: Decimal
    peak_pnl_usd: Decimal
    drawdown_usd: Decimal
    outstanding_orders: int
    held_symbols: int
    halted_reason: str | None


@contextmanager
def account_lock(account_id, lock_root=None):
    """Use the exact accepted smoke-runner lock namespace, across all lanes."""
    if type(account_id) is not str or not account_id or len(account_id) > 128:
        raise SafetyError("invalid_account_identity")
    fingerprint = hashlib.sha256(account_id.encode()).hexdigest()
    with account_lock_fingerprint(fingerprint, lock_root) as value:
        yield value


@contextmanager
def account_lock_fingerprint(fingerprint, lock_root=None):
    """Lock an already hashed native identity without accidentally hashing twice."""
    if type(fingerprint) is not str or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise SafetyError("invalid_account_fingerprint")
    root = Path(lock_root) if lock_root is not None else DEFAULT_STOP.parent / "locks"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(root / (fingerprint + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("account_writer_already_running") from None
        yield fingerprint
    finally:
        os.close(fd)


def _intent(row, new=False):
    return Intent(row["client_id"], row["symbol"], row["side"], D(row["qty"]),
                  D(row["limit_price"]), row["status"], D(row["filled_qty"]),
                  D(row["average_price"]) if row["average_price"] else None,
                  row["broker_id"], new, bool(row["submit_attempted"]))


class Ledger:
    """One account-scoped database, retained across processes and trials.

    SQLite transactions protect risk reservations even across connections. The
    caller also holds account_lock for the entire account-writer lifetime.
    """
    def __init__(self, db_path, limits=None):
        self.path = Path(db_path)
        self.limits = limits or RiskLimits()
        if not isinstance(self.limits, RiskLimits):
            raise SafetyError("risk_limits_required")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intents(
                    client_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL,
                    qty TEXT NOT NULL, limit_price TEXT NOT NULL, status TEXT NOT NULL,
                    filled_qty TEXT NOT NULL DEFAULT '0', average_price TEXT, broker_id TEXT UNIQUE,
                    submit_attempted INTEGER NOT NULL DEFAULT 0, updated_at REAL);
                CREATE TABLE IF NOT EXISTS positions(symbol TEXT PRIMARY KEY, qty TEXT NOT NULL,
                    cost_basis TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS marks(symbol TEXT PRIMARY KEY, bid TEXT NOT NULL,
                    ask TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, at REAL NOT NULL,
                    kind TEXT NOT NULL, client_id TEXT REFERENCES intents(client_id));
                CREATE INDEX IF NOT EXISTS requests_time ON requests(at);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                    client_id TEXT, payload TEXT NOT NULL);
            """)
            frozen = json.dumps(asdict(self.limits), default=str, sort_keys=True)
            with self._transaction():
                previous = self._get("limits")
                if previous is not None and previous != frozen:
                    raise SafetyError("persisted_risk_limits_differ")
                self._set("limits", frozen)
                version = self._get("schema_version")
                if version not in (None, "1"):
                    raise SafetyError("unsupported_ledger_schema")
                self._set("schema_version", "1")
                for key in ("realized", "cash_delta", "realized_loss", "peak_pnl"):
                    if self._get(key) is None:
                        self._set(key, "0")
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException:
            self.db.close()
            raise

    @contextmanager
    def _transaction(self, *, keep_observations_on_refusal=False):
        with self._lock, localcontext() as context:
            context.prec = 40
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except SafetyError:
                # Risk refusal may follow an actual market observation. Retain
                # its loss/peak/STOP consequences rather than forgetting them.
                self.db.execute("COMMIT" if keep_observations_on_refusal else "ROLLBACK")
                raise
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _get(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _set(self, key, value):
        self.db.execute("INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, str(value)))

    def _event(self, kind, client_id=None, **data):
        self.db.execute("INSERT INTO events(kind,client_id,payload) VALUES (?,?,?)",
                        (kind, client_id, json.dumps(data, default=str, sort_keys=True, allow_nan=False)))

    def start_trial(self, now):
        now = instant(now)
        with self._transaction():
            if self._get("trial_start") is None:
                self._set("trial_start", now)
                self._event("trial_start", at=now)
            return float(self._get("trial_start"))

    def begin_recovery(self, now):
        """Explicit cleanup invocation; preserve state and permanently stop entries.

        Call only for an explicit bounded recovery run, never to extend an active
        execution loop automatically. No request, fill or loss history is reset.
        """
        now = instant(now)
        with self._transaction():
            start = self._get("trial_start")
            previous = self._get("recovery_start")
            if start is None:
                raise SafetyError("trial_not_started")
            if now < float(start) or (previous is not None and now < float(previous)):
                raise SafetyError("recovery_clock_moved_backward")
            self._set("recovery_start", now)
            self._set("recovery_only", "1")
            if self._get("halted_reason") is None:
                self._set("halted_reason", "recovery_only")
            self._event("recovery_started", at=now, cleanup_seconds=self.limits.cleanup_seconds)
            return now

    def _check_window(self, side, now):
        start = self._get("trial_start")
        if start is None:
            raise SafetyError("trial_not_started")
        recovery = self._get("recovery_start")
        if side == "buy" and self._get("recovery_only"):
            raise SafetyError("recovery_only_blocks_entry")
        if side == "sell" and recovery is not None:
            age, allowed = now - float(recovery), self.limits.cleanup_seconds
        else:
            age = now - float(start)
            allowed = self.limits.trial_seconds + (self.limits.cleanup_seconds if side == "sell" else 0)
        if age < 0 or age >= allowed:
            raise SafetyError("trial_window_ended")

    def _check_quote(self, quote, now):
        if not isinstance(quote, Quote):
            raise SafetyError("quote_required")
        if not -0.25 <= now - quote.timestamp <= self.limits.quote_max_age_seconds:
            raise SafetyError("quote_not_fresh")
        if (quote.ask - quote.bid) * 10000 / ((quote.ask + quote.bid) / 2) > self.limits.max_spread_bps:
            raise SafetyError("quote_spread_exceeds_cap")

    def _mark(self, quote):
        previous = self.db.execute("SELECT at FROM marks WHERE symbol=?", (quote.symbol,)).fetchone()
        if previous is not None and quote.timestamp < previous[0]:
            return
        self.db.execute("INSERT INTO marks VALUES (?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
                        "bid=excluded.bid,ask=excluded.ask,at=excluded.at",
                        (quote.symbol, str(quote.bid), str(quote.ask), quote.timestamp))

    def _positions(self):
        return {r["symbol"]: Position(r["symbol"], D(r["qty"]), D(r["cost_basis"]))
                for r in self.db.execute("SELECT * FROM positions") if D(r["qty"]) > 0}

    def _state(self):
        positions = self._positions()
        active = [_intent(r) for r in self.db.execute("SELECT * FROM intents") if r["status"] not in TERMINAL]
        pending = sum((i.remaining_qty * i.limit_price for i in active if i.side == "buy"), ZERO)
        unrealized, unrealized_loss, gross = ZERO, ZERO, ZERO
        symbols = set(positions) | {i.symbol for i in active if i.side == "buy" and i.remaining_qty}
        for position in positions.values():
            mark = self.db.execute("SELECT bid,ask FROM marks WHERE symbol=?", (position.symbol,)).fetchone()
            bid = D(mark["bid"]) if mark else position.average_cost
            ask = D(mark["ask"]) if mark else position.average_cost
            pnl = position.qty * bid - position.cost_basis_usd
            unrealized += pnl
            unrealized_loss += max(ZERO, -pnl)
            gross += position.qty * max(position.average_cost, ask)
        realized, loss, peak = (D(self._get(k)) for k in ("realized", "realized_loss", "peak_pnl"))
        return AccountState(realized, unrealized, loss, loss + unrealized_loss,
                            D(self._get("cash_delta")), gross + pending, pending,
                            peak, max(ZERO, peak - realized - unrealized), len(active), len(symbols),
                            self._get("halted_reason"))

    def _refresh_risk(self):
        state = self._state()
        self._set("peak_pnl", max(state.peak_pnl_usd, state.realized_pnl_usd + state.unrealized_pnl_usd))
        state = self._state()
        reason = None
        if state.gross_loss_usd >= self.limits.max_gross_loss_usd:
            reason = "gross_loss_cap_reached"
        elif state.drawdown_usd >= self.limits.max_drawdown_usd:
            reason = "drawdown_cap_reached"
        elif state.gross_exposure_usd > self.limits.max_gross_exposure_usd:
            reason = "gross_exposure_cap_exceeded"
        if reason and not state.halted_reason:
            self._set("halted_reason", reason)
            self._event("risk_halt", reason=reason)
        return self._state()

    def reserve_intent(self, client_id, symbol, side, qty, limit_price, *, quote,
                       now, market_open, session_close, stop_file=None):
        if type(client_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", client_id):
            raise SafetyError("invalid_client_order_id")
        symbol = symbol_name(symbol)
        if side not in ("buy", "sell"):
            raise SafetyError("invalid_order_side")
        qty, price, now, close = decimal(qty), decimal(limit_price), instant(now), instant(session_close)
        if price != price.quantize(D("0.01") if price >= 1 else D("0.0001")):
            raise SafetyError("invalid_price_increment")
        with self._transaction(keep_observations_on_refusal=True):
            previous = self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone()
            if previous:
                existing = _intent(previous)
                if (existing.symbol, existing.side, existing.qty, existing.limit_price) != (symbol, side, qty, price):
                    raise SafetyError("client_id_conflicts_with_durable_intent")
                return existing
            self._check_quote(quote, now)
            if quote.symbol != symbol:
                raise SafetyError("quote_symbol_mismatch")
            if market_open is not True or close - now < (self.limits.min_entry_close_seconds if side == "buy" else 1):
                raise SafetyError("outside_allowed_session")
            self._check_window(side, now)
            if qty > self.limits.max_order_qty or qty * price > self.limits.max_order_notional_usd:
                raise SafetyError("order_size_cap_exceeded")
            if side == "buy" and qty != qty.to_integral_value():
                raise SafetyError("entry_requires_whole_shares")
            self._mark(quote)
            state = self._refresh_risk()
            if state.outstanding_orders >= self.limits.max_outstanding_orders:
                raise SafetyError("outstanding_order_cap_reached")
            if side == "buy":
                if Path(stop_file or DEFAULT_STOP).exists():
                    raise SafetyError("stop_blocks_entry")
                if state.halted_reason:
                    raise SafetyError(state.halted_reason)
                # Existing positions must also have fresh marks before increasing risk.
                for held in self._positions():
                    mark = self.db.execute("SELECT at FROM marks WHERE symbol=?", (held,)).fetchone()
                    if mark is None or not -0.25 <= now - mark[0] <= self.limits.quote_max_age_seconds:
                        raise SafetyError("held_position_mark_stale")
                equity = self.limits.capital_usd + state.realized_pnl_usd + state.unrealized_pnl_usd
                if state.gross_exposure_usd + qty * price > min(self.limits.max_gross_exposure_usd, equity):
                    raise SafetyError("aggregate_exposure_cap_exceeded")
                exposed = set(self._positions()) | {r[0] for r in self.db.execute(
                    "SELECT symbol FROM intents WHERE side='buy' AND status NOT IN ('filled','canceled','expired','rejected','not_sent')")}
                if len(exposed | {symbol}) > self.limits.max_held_symbols:
                    raise SafetyError("held_symbol_cap_reached")
            else:
                held = self._positions().get(symbol)
                pending_sell = sum((D(r["qty"]) - D(r["filled_qty"]) for r in self.db.execute(
                    "SELECT qty,filled_qty FROM intents WHERE symbol=? AND side='sell' AND "
                    "status NOT IN ('filled','canceled','expired','rejected','not_sent')", (symbol,))), ZERO)
                if held is None or qty > held.qty - pending_sell:
                    raise SafetyError("sell_exceeds_owned_unreserved_position")
            self.db.execute("INSERT INTO intents(client_id,symbol,side,qty,limit_price,status,updated_at) "
                            "VALUES (?,?,?,?,?,'reserved',?)", (client_id, symbol, side, str(qty), str(price), now))
            self._event("intent_reserved", client_id, symbol=symbol, side=side, qty=qty, limit_price=price, at=now)
            return _intent(self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone(), True)

    def validate_pending(self, client_id, *, quote, now, market_open, session_close, stop_file=None):
        """Revalidate an existing reservation immediately before the first POST.

        Does not reserve a second position/order or authorize a duplicate send.
        The caller rechecks after every budget wait and binds the POST to the
        single durable request_budget submission identity.
        """
        now, close = instant(now), instant(session_close)
        with self._transaction(keep_observations_on_refusal=True):
            row = self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone()
            if row is None:
                raise SafetyError("unknown_client_order_id")
            intent = _intent(row)
            if intent.status != "reserved" or intent.broker_id is not None or intent.filled_qty:
                raise SafetyError("pending_intent_already_observed_or_terminal")
            self._check_quote(quote, now)
            if quote.symbol != intent.symbol:
                raise SafetyError("quote_symbol_mismatch")
            if market_open is not True or close - now < (self.limits.min_entry_close_seconds if intent.side == "buy" else 1):
                raise SafetyError("outside_allowed_session")
            self._check_window(intent.side, now)
            self._mark(quote)
            state = self._refresh_risk()
            if state.outstanding_orders > self.limits.max_outstanding_orders:
                raise SafetyError("outstanding_order_cap_reached")
            if intent.side == "buy":
                if Path(stop_file or DEFAULT_STOP).exists():
                    raise SafetyError("stop_blocks_entry")
                if state.halted_reason:
                    raise SafetyError(state.halted_reason)
                for symbol in self._positions():
                    mark = self.db.execute("SELECT at FROM marks WHERE symbol=?", (symbol,)).fetchone()
                    if mark is None or not -0.25 <= now - mark[0] <= self.limits.quote_max_age_seconds:
                        raise SafetyError("held_position_mark_stale")
                equity = self.limits.capital_usd + state.realized_pnl_usd + state.unrealized_pnl_usd
                if state.gross_exposure_usd > min(self.limits.max_gross_exposure_usd, equity):
                    raise SafetyError("aggregate_exposure_cap_exceeded")
                if state.held_symbols > self.limits.max_held_symbols:
                    raise SafetyError("held_symbol_cap_reached")
            else:
                position = self._positions().get(intent.symbol)
                pending = sum((i.remaining_qty for i in self.unresolved()
                               if i.symbol == intent.symbol and i.side == "sell"), ZERO)
                if position is None or pending > position.qty:
                    raise SafetyError("sell_exceeds_owned_unreserved_position")
            return intent

    def mark_not_sent(self, client_id, reason):
        """Release ONLY a definitively refused pre-send intent, never ambiguity.

        Transport must know no HTTP request was sent. A reserved request attempt
        still counts against its budget; this never refunds capacity or fabricates
        a broker order identity. An ambiguous timeout is not a pre-send refusal.
        """
        if type(reason) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", reason):
            raise SafetyError("invalid_not_sent_reason")
        with self._transaction():
            row = self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone()
            if row is None:
                raise SafetyError("unknown_client_order_id")
            intent = _intent(row)
            if intent.status == "not_sent":
                return False
            if intent.status != "reserved" or intent.broker_id is not None or intent.filled_qty:
                raise SafetyError("cannot_mark_observed_order_not_sent")
            self.db.execute("UPDATE intents SET status='not_sent' WHERE client_id=?", (client_id,))
            self._event("intent_not_sent", client_id, reason=reason)
            return True

    def record_order(self, client_id, broker_id, status, cumulative_qty, average_price, *, timestamp=None):
        if (type(broker_id) is not str or not broker_id or len(broker_id) > 128
                or type(status) is not str or status not in RANK or status in ("reserved", "not_sent")):
            raise SafetyError("invalid_broker_order_identity_or_status")
        filled = decimal(cumulative_qty, zero=True)
        average = decimal(average_price) if filled else None
        at = instant(timestamp) if timestamp is not None else None
        with self._transaction():
            row = self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone()
            if row is None:
                raise SafetyError("unknown_client_order_id")
            old = _intent(row)
            if old.status == "not_sent":
                raise SafetyError("broker_observation_after_definitive_not_sent")
            if old.broker_id not in (None, broker_id):
                raise SafetyError("broker_order_identity_changed")
            if filled > old.qty or (status == "filled" and filled != old.qty):
                raise SafetyError("broker_filled_quantity_invalid")
            if filled < old.filled_qty:
                return False  # Delayed cumulative snapshot, never subtract fills.
            if filled == old.filled_qty and old.average_price != average:
                raise SafetyError("same_quantity_conflicting_average_price")
            if old.terminal and (filled != old.filled_qty or status != old.status):
                if filled == old.filled_qty and status not in TERMINAL:
                    return False
                raise SafetyError("terminal_order_contradiction")
            if filled == old.filled_qty and RANK[status] < RANK[old.status]:
                return False
            if filled == old.filled_qty and status == old.status and old.broker_id == broker_id:
                return False
            delta = filled - old.filled_qty
            old_notional = old.filled_qty * (old.average_price or ZERO)
            delta_notional = filled * (average or ZERO) - old_notional
            if delta:
                incremental_price = delta_notional / delta
                if (incremental_price <= 0 or
                        (old.side == "buy" and incremental_price > old.limit_price) or
                        (old.side == "sell" and incremental_price < old.limit_price)):
                    raise SafetyError("incremental_fill_violates_limit")
                position = self._positions().get(old.symbol, Position(old.symbol, ZERO, ZERO))
                realized = ZERO
                if old.side == "buy":
                    new_qty, cost = position.qty + delta, position.cost_basis_usd + delta_notional
                    cash_delta = -delta_notional
                else:
                    if delta > position.qty:
                        raise SafetyError("fill_would_make_short_position")
                    basis = position.average_cost * delta
                    new_qty, cost = position.qty - delta, position.cost_basis_usd - basis
                    realized, cash_delta = delta_notional - basis, delta_notional
                if new_qty == 0:
                    cost = ZERO
                self.db.execute("INSERT INTO positions VALUES (?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
                                "qty=excluded.qty,cost_basis=excluded.cost_basis", (old.symbol, str(new_qty), str(cost)))
                self._set("cash_delta", D(self._get("cash_delta")) + cash_delta)
                self._set("realized", D(self._get("realized")) + realized)
                self._set("realized_loss", D(self._get("realized_loss")) + max(ZERO, -realized))
            # A delayed partial-fill snapshot can add a valid fill after a newer
            # pending-cancel status. Apply its quantity without reversing status.
            effective_status = old.status if RANK[old.status] > RANK[status] else status
            self.db.execute("UPDATE intents SET broker_id=?,status=?,filled_qty=?,average_price=?,updated_at=? WHERE client_id=?",
                            (broker_id, effective_status, str(filled), str(average) if average else None, at, client_id))
            self._event("order_observed", client_id, broker_id=broker_id, status=status, filled_qty=filled,
                        average_price=average, at=at, delta_qty=delta, delta_notional=delta_notional)
            self._refresh_risk()
            return True

    def request_budget(self, now, kind, client_id=None):
        """Return 0 after durable reservation, or delay <=60s WITHOUT reservation.

        The caller bounds its wait against entry/cleanup deadlines and calls again
        after waiting. Counts attempts, including failures; never refunds a send.
        Bind each submit to client_id to prevent duplicate submission on restart.
        """
        now = instant(now)
        if type(kind) is not str or kind not in ("submit", "read", "cancel", "data_read"):
            raise SafetyError("invalid_request_kind")
        with self._transaction():
            latest = self.db.execute("SELECT MAX(at) FROM requests").fetchone()[0]
            if latest is not None and now < latest:
                raise SafetyError("request_clock_moved_backward")
            if kind == "submit" and client_id is not None:
                row = self.db.execute("SELECT submit_attempted,status FROM intents WHERE client_id=?", (client_id,)).fetchone()
                if row is None or row["submit_attempted"] or row["status"] != "reserved":
                    raise SafetyError("submit_identity_already_attempted_or_invalid")
            total = self.db.execute("SELECT at,kind FROM requests WHERE at>? ORDER BY at,id", (now - 60,)).fetchall()
            delays = [ZERO]
            if len(total) >= self.limits.max_rest_per_minute:
                delays.append(D(str(total[-self.limits.max_rest_per_minute]["at"] + 60 - now)))
            submits = [r["at"] for r in total if r["kind"] == "submit"]
            if kind == "submit" and len(submits) >= self.limits.max_submits_per_minute:
                delays.append(D(str(submits[-self.limits.max_submits_per_minute] + 60 - now)))
            delay = float(max(delays))
            if delay > 0:
                return min(60.0, delay)
            self.db.execute("INSERT INTO requests(at,kind,client_id) VALUES (?,?,?)", (now, kind, client_id))
            if kind == "submit" and client_id is not None:
                self.db.execute("UPDATE intents SET submit_attempted=1 WHERE client_id=?", (client_id,))
            return 0.0

    def mark_to_market(self, quotes, now):
        now = instant(now)
        values = list(quotes.values()) if isinstance(quotes, dict) else list(quotes)
        for quote in values:
            self._check_quote(quote, now)
        with self._transaction(keep_observations_on_refusal=True):
            for quote in values:
                self._mark(quote)
            state = self._refresh_risk()
            for symbol in self._positions():
                mark = self.db.execute("SELECT at FROM marks WHERE symbol=?", (symbol,)).fetchone()
                if mark is None or not -0.25 <= now - mark[0] <= self.limits.quote_max_age_seconds:
                    raise SafetyError("held_position_mark_stale")
            return state

    def freeze(self, reason):
        if type(reason) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", reason):
            raise SafetyError("invalid_halt_reason")
        with self._transaction():
            if self._get("halted_reason") is None:
                self._set("halted_reason", reason)
                self._event("risk_halt", reason=reason)

    def intents(self):
        with self._lock:
            return [_intent(r) for r in self.db.execute("SELECT * FROM intents ORDER BY rowid")]

    def unresolved(self):
        return [i for i in self.intents() if not i.terminal]

    def positions(self):
        with self._lock:
            return self._positions()

    def accounting(self):
        with self._lock, localcontext() as context:
            context.prec = 40
            return self._state()

    def close(self):
        with self._lock:
            self.db.close()
