"""Durable deterministic risk/accounting for a bounded paper-only trial.

No broker transport, credentials, strategy, or model calls live in this module.
Callers must reconcile broker state before resuming entries after interruption.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading

# This module is sometimes loaded directly via importlib file-spec without its
# own directory on sys.path; self-heal so the local sessions.py sibling import
# below resolves regardless of how the caller imported this module.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from sessions import SessionKind, session_at as _session_at  # noqa: E402

D = Decimal
ZERO = D(0)
TERMINAL = frozenset({"filled", "canceled", "expired", "rejected", "not_sent", "broker_refused"})
RANK = {"reserved": 0, "pending_new": 1, "accepted": 2, "new": 2,
        "accepted_for_bidding": 2, "held": 2, "partially_filled": 3,
        "pending_cancel": 4, "done_for_day": 4,
        "filled": 5, "canceled": 5, "expired": 5, "rejected": 5, "not_sent": 5, "broker_refused": 5}
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
    # G-f deliverable 3: "fixed" (default) keeps max_order_qty a literal
    # per-order share cap, exactly the pre-G-f behavior. "notional" instead
    # derives the effective per-order share cap from max_order_notional_usd
    # at the live quote price (floor), via effective_max_order_qty below --
    # max_order_qty itself is then unused for the cap (still validated
    # above, but only ever consulted through effective_max_order_qty).
    # Every notional/gross/count cap is unchanged either way.
    max_order_qty_mode: str = "fixed"
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
    overnight_gross_multiple: Decimal = D("1.0")

    def __post_init__(self):
        for field in ("capital_usd", "max_gross_exposure_usd", "max_order_notional_usd",
                      "max_order_qty", "max_gross_loss_usd", "max_drawdown_usd", "max_spread_bps",
                      "overnight_gross_multiple"):
            object.__setattr__(self, field, decimal(getattr(self, field)))
        if (self.capital_usd > D("1000000") or self.max_gross_exposure_usd > self.capital_usd
                or self.max_order_notional_usd > min(self.max_gross_exposure_usd, D("10000"))
                or self.max_order_qty > 100 or self.max_order_qty != self.max_order_qty.to_integral_value()
                or self.max_gross_loss_usd > self.capital_usd / 10
                or self.max_drawdown_usd > self.capital_usd / 10 or self.max_spread_bps > 100
                # D6 (round 5): "self.overnight_gross_multiple <= 0" was
                # dead here -- the decimal(getattr(...)) conversion loop
                # above (zero=False, the default) already refuses a
                # non-positive overnight_gross_multiple before this
                # __post_init__ body ever reaches this check.
                or self.overnight_gross_multiple > D("2.0")):
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
        if self.max_order_qty_mode not in ("fixed", "notional"):
            raise SafetyError("invalid_max_order_qty_mode")

    def effective_max_order_qty(self, price, *, quote_price=None):
        """The per-order share cap `reserve_intent` enforces.

        "fixed" mode (the shipped default): `max_order_qty` unchanged,
        independent of price -- neither `price` nor `quote_price` is
        consulted at all.

        "notional" mode (D6, round 2; D4, round 3): min(max_order_qty,
        floor(max_order_notional_usd / reference_price), 100) -- the
        *smallest* of the operator's own configured `max_order_qty`, the
        notional cap expressed as a share count at `reference_price`, and
        the hard 100-share ceiling. The pre-round-2 version discarded the
        operator's configured max_order_qty entirely in notional mode, so
        an explicit operator cap (set for a reason -- e.g. a deliberately
        conservative per-order size even though the notional budget would
        allow more) silently stopped binding the moment notional mode was
        selected. An operator who wants notional mode to actually allow
        *more* than the "fixed" literal-1 default must now also raise
        max_order_qty explicitly (e.g. to the same ceiling "fixed" mode
        would have used); notional mode then narrows that cap further
        whenever the notional budget is the tighter constraint at
        `reference_price`, but it can never widen a cap the operator
        explicitly set.

        D4 (round 3): `reference_price` is `quote_price` -- the live
        quote's own price -- when the caller supplies one; `price` (the
        order's own limit price, which may already include a marketable
        offset from the quote -- see strategies_v1.limit_price) is only
        used as a fallback when no `quote_price` is given. Before this fix
        the docstring promised "the live quote price" but `reserve_intent`
        actually always passed the order's limit price; the two are now
        made consistent by making `reserve_intent` pass the quote's own
        price explicitly (see its call site) rather than by silently
        redefining what `price` alone means here."""
        price = decimal(price)
        reference_price = decimal(quote_price) if quote_price is not None else price
        if self.max_order_qty_mode == "fixed":
            return self.max_order_qty
        notional_implied = (self.max_order_notional_usd / reference_price).to_integral_value(rounding="ROUND_FLOOR")
        return min(self.max_order_qty, notional_implied, D("100"))

    def overnight_gross_exposure_cap_usd(self):
        """The gross-exposure ceiling that applies to a position carried
        through an overnight hold (deliverable 4). Never exceeds the
        RiskLimits-enforced <=2.0x bound on overnight_gross_multiple, and with
        the default multiple of 1.0 this equals the ordinary intraday cap."""
        return self.max_gross_exposure_usd * self.overnight_gross_multiple


def evaluate_gap_risk(prior_close, session_open, stop_bps):
    """Gap-risk rule (deliverable 4): evaluated at the first RTH bar after an
    overnight hold. Compares the new session's open against the prior
    session's close and returns the stop level implied by the configured
    ``stop_bps``, applied from the actual open rather than from the stale
    prior-session reference price. Pure and side-effect free: callers apply
    the returned stop through the existing exit chain, this function does not
    submit or cancel anything.

    Returns a dict: {"gap_bps": signed gap in bps, "stop_price": Decimal, the
    price at which the existing stop-loss exit should now trigger}.
    """
    # decimal(..., zero=False) (the default) already rejects non-positive,
    # non-finite and out-of-precision inputs by raising SafetyError, so no
    # separate "<= 0" guard is reachable here; do not add a dead check back.
    prior_close = decimal(prior_close)
    session_open = decimal(session_open)
    stop_bps = decimal(stop_bps)
    gap_bps = (session_open - prior_close) * 10000 / prior_close
    stop_price = session_open * (1 - stop_bps / 10000)
    return {"gap_bps": gap_bps, "stop_price": stop_price}


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: float
    halted: bool = False

    def __post_init__(self):
        symbol_name(self.symbol)
        object.__setattr__(self, "bid", decimal(self.bid))
        object.__setattr__(self, "ask", decimal(self.ask))
        object.__setattr__(self, "timestamp", instant(self.timestamp))
        if self.ask < self.bid:
            raise SafetyError("crossed_quote")
        if type(self.halted) is not bool:
            raise SafetyError("invalid_halt_flag")


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
                CREATE TABLE IF NOT EXISTS trials(trial_id TEXT PRIMARY KEY, started_at REAL NOT NULL);
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

    _PRIOR_RTH_CLOSE_PREFIX = "prior_rth_close:"

    def record_prior_rth_close(self, symbol, price, session_date, ts_ns):
        """S5 (+ D3, round 4): persist the RTH-close price captured for
        ``symbol`` at the RTH->non-RTH session crossing, keyed in the
        durable meta table so native_strategy.py's D5 gap-risk stop
        survives a process restart (it previously lived only in
        AdaptiveStrategy._prior_rth_close, per-process memory, so the stop
        could never fire across invocations under overnight_holds).

        D3 (round 4): the pre-fix version persisted only the bare price,
        with no date or staleness bound -- a value captured days or weeks
        earlier (e.g. a symbol that stopped trading, or a long-idle
        ledger) could still be loaded and armed against today's open with
        no way to tell it was never actually "yesterday's close". Persist
        ``session_date`` (the RTH session date, as an ISO "YYYY-MM-DD"
        string, that this close was captured for) and ``ts_ns`` (the
        capturing quote's own market-clock timestamp, nanoseconds) so a
        loader (native_strategy.py's ``_gap_risk_stop_symbols``) can refuse to arm
        against a close whose session_date is not exactly the trading day
        immediately before the session being armed."""
        symbol = symbol_name(symbol)
        price = decimal(price)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(session_date)):
            raise SafetyError("invalid_session_date")
        session_date = date.fromisoformat(str(session_date)).isoformat()
        if type(ts_ns) is not int or isinstance(ts_ns, bool) or ts_ns <= 0:
            raise SafetyError("invalid_ts_ns")
        payload = json.dumps({"price": str(price), "session_date": session_date, "ts_ns": ts_ns}, sort_keys=True)
        with self._transaction():
            self._set(f"{self._PRIOR_RTH_CLOSE_PREFIX}{symbol}", payload)

    def prior_rth_closes(self):
        """Every persisted prior-RTH-close record, keyed by symbol, for
        native_strategy.py to load back at startup under overnight_holds.
        Each value is ``{"price": Decimal, "session_date": date, "ts_ns":
        int}`` (D3, round 4: previously a bare price with no date/staleness
        information at all)."""
        rows = self.db.execute("SELECT key, value FROM meta WHERE key LIKE ?",
                               (f"{self._PRIOR_RTH_CLOSE_PREFIX}%",)).fetchall()
        result = {}
        for key, value in rows:
            symbol = key[len(self._PRIOR_RTH_CLOSE_PREFIX):]
            try:
                record = json.loads(value)
                result[symbol] = {"price": decimal(record["price"]),
                                  "session_date": date.fromisoformat(record["session_date"]),
                                  "ts_ns": int(record["ts_ns"])}
            except (ValueError, KeyError, TypeError):
                # A record written before D3 (round 4) (a bare price
                # string, no session_date/ts_ns) or otherwise malformed:
                # there is no date to validate it against, so the loader
                # must treat it as unusable rather than guess a date.
                continue
        return result

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

    def begin_next_trial(self, now, trial_id):
        """Start an explicitly requested new bounded trial in the SAME account DB.

        Caller must have stopped admissions, held the writer lock, and observed
        fresh broker flat/idle cash/position reconciliation before invoking this.
        Durable risk, fill accounting and request history are never reset.
        """
        return self._begin_trial(now, trial_id, require_flat=True, event_kind="next_trial_started")

    def resume_held_trial(self, now, trial_id):
        """S2: start an explicitly requested new bounded trial that
        continues (adopts) an existing "held_overnight" position/open-order
        state instead of requiring flat -- the resumable-hold counterpart
        to begin_next_trial.

        The runner.py resumable-hold path (a prior run's phase ==
        "held_overnight" under overnight_holds) deliberately bypasses its
        own earlier flat/cash-reconciliation guards for this case (D1's
        broker-snapshot adoption, not a fresh-flat requirement, is what
        reconciles the resumed state), but used to then fall straight
        through to begin_next_trial -- which always raises
        "next_trial_requires_flat_and_terminal" against exactly the
        non-flat state a hold is expected to have. Every other guard
        (trial_id uniqueness, clock monotonicity, risk halt, risk budget)
        stays enforced unchanged.
        """
        return self._begin_trial(now, trial_id, require_flat=False, event_kind="held_trial_resumed")

    def _begin_trial(self, now, trial_id, *, require_flat, event_kind):
        now = instant(now)
        if type(trial_id) is not str or not re.fullmatch(r"[a-z0-9-]{1,24}", trial_id):
            raise SafetyError("invalid_trial_id")
        with self._transaction():
            if self.db.execute("SELECT 1 FROM trials WHERE trial_id=?", (trial_id,)).fetchone():
                raise SafetyError("trial_id_already_used")
            start = self._get("trial_start")
            latest_request = self.db.execute("SELECT MAX(at) FROM requests").fetchone()[0]
            if ((start is not None and now < float(start)) or
                    (latest_request is not None and now < latest_request)):
                raise SafetyError("trial_clock_moved_backward")
            if require_flat and (self._positions() or any(not i.terminal for i in self.intents())):
                raise SafetyError("next_trial_requires_flat_and_terminal")
            state = self._state()
            if state.halted_reason not in (None, "recovery_only"):
                raise SafetyError("next_trial_cannot_clear_risk_halt")
            if (state.gross_loss_usd >= self.limits.max_gross_loss_usd or
                    state.drawdown_usd >= self.limits.max_drawdown_usd):
                raise SafetyError("next_trial_risk_budget_exhausted")
            self.db.execute("INSERT INTO trials VALUES (?,?)", (trial_id, now))
            self._set("trial_start", now)
            self._set("trial_id", trial_id)
            self.db.execute("DELETE FROM meta WHERE key IN ('recovery_start','recovery_only')")
            if state.halted_reason == "recovery_only":
                self.db.execute("DELETE FROM meta WHERE key='halted_reason'")
            self._event(event_kind, trial_id=trial_id, at=now,
                        required_external_proof="fresh_broker_flat_idle_and_cash_reconciled" if require_flat
                        else "held_position_adopted_from_broker_snapshot")
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

    def _check_quote(self, quote, now, *, check_spread=True):
        if not isinstance(quote, Quote):
            raise SafetyError("quote_required")
        if not -0.25 <= now - quote.timestamp <= self.limits.quote_max_age_seconds:
            raise SafetyError("quote_not_fresh")
        # check_spread doubles as "this is a new-risk (entry) check"; a halted
        # or LULD-flagged quote blocks new risk exactly like a stale or
        # over-wide quote does, while the existing exit (sell) chain, which
        # already skips the spread gate here, is left untouched.
        if check_spread and quote.halted:
            raise SafetyError("quote_halted")
        if check_spread and (quote.ask - quote.bid) * 10000 / ((quote.ask + quote.bid) / 2) > self.limits.max_spread_bps:
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

    def _effective_gross_cap(self, now):
        """The gross-exposure cap that applies at ``now`` (D2, widened by D3).
        With the default overnight_gross_multiple of 1.0 this is always equal
        to max_gross_exposure_usd, so default behaviour is byte-identical; it
        only differs once a caller has configured overnight_gross_multiple !=
        1.0 (only reachable when the session policy allows overnight holds,
        which D8 requires extended_hours for).

        D3: an overnight hold spans PRE (04:00-09:30) as well as POST/CLOSED
        -- the cap must not snap back to the ordinary intraday cap at the
        CLOSED->PRE crossing and trip the halt trigger before RTH reopens.
        The gross-exposure model here is account-level (it has no per-
        position entry timestamp), so this widens for any session kind other
        than RTH rather than only for positions individually proven to
        predate the last RTH close; that is a documented simplification, not
        a per-position age check.

        A date outside the frozen session calendar's supported years (D7)
        cannot be classified; this falls back to the ordinary cap rather than
        raising, so the risk engine's default hot path never breaks for a
        timestamp outside the calendar table (e.g. synthetic test fixtures)."""
        try:
            info = _session_at(datetime.fromtimestamp(now, tz=timezone.utc))
        except ValueError:
            return self.limits.max_gross_exposure_usd
        if info.kind != SessionKind.RTH:
            return self.limits.overnight_gross_exposure_cap_usd()
        return self.limits.max_gross_exposure_usd

    def _refresh_risk(self, now=None):
        # now=None (e.g. record_order's optional timestamp) falls back to the
        # ordinary intraday cap, the same behaviour as before D2; when now is
        # available this circuit breaker uses the same session-aware cap as
        # reserve_intent/validate_pending, so a position that is within the
        # configured overnight_gross_multiple never trips an unconditional
        # ordinary-cap halt during POST/CLOSED (D2's gross checks are the
        # entry gate AND this halt trigger, kept consistent with each other).
        cap = self._effective_gross_cap(now) if now is not None else self.limits.max_gross_exposure_usd
        state = self._state()
        self._set("peak_pnl", max(state.peak_pnl_usd, state.realized_pnl_usd + state.unrealized_pnl_usd))
        state = self._state()
        reason = None
        if state.gross_loss_usd >= self.limits.max_gross_loss_usd:
            reason = "gross_loss_cap_reached"
        elif state.drawdown_usd >= self.limits.max_drawdown_usd:
            reason = "drawdown_cap_reached"
        elif state.gross_exposure_usd > cap:
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
            self._check_quote(quote, now, check_spread=side == "buy")
            if quote.symbol != symbol:
                raise SafetyError("quote_symbol_mismatch")
            if market_open is not True or close - now < (self.limits.min_entry_close_seconds if side == "buy" else 1):
                raise SafetyError("outside_allowed_session")
            self._check_window(side, now)
            # D4 (round 3): the notional-implied per-order cap is derived
            # from the live quote's own price (the executable side: ask
            # for a buy, bid for a sell), not the order's own limit price
            # -- `price` here already carries strategies_v1.limit_price's
            # marketable offset baked in, which would otherwise silently
            # bias the notional-implied share count. `quote` was already
            # checked (`_check_quote` above) and is always present at this
            # point, so effective_max_order_qty's "price" fallback path
            # (no quote_price given) is only exercised by a direct,
            # standalone caller of effective_max_order_qty itself.
            quote_price = quote.ask if side == "buy" else quote.bid
            if (qty > self.limits.effective_max_order_qty(price, quote_price=quote_price)
                    or qty * price > self.limits.max_order_notional_usd):
                raise SafetyError("order_size_cap_exceeded")
            if side == "buy" and qty != qty.to_integral_value():
                raise SafetyError("entry_requires_whole_shares")
            self._mark(quote)
            state = self._refresh_risk(now)
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
                if state.gross_exposure_usd + qty * price > min(self._effective_gross_cap(now), equity):
                    raise SafetyError("aggregate_exposure_cap_exceeded")
                exposed = set(self._positions()) | {r[0] for r in self.db.execute(
                    "SELECT symbol FROM intents WHERE side='buy' AND status NOT IN ('filled','canceled','expired','rejected','not_sent','broker_refused')")}
                if len(exposed | {symbol}) > self.limits.max_held_symbols:
                    raise SafetyError("held_symbol_cap_reached")
            else:
                held = self._positions().get(symbol)
                pending_sell = sum((D(r["qty"]) - D(r["filled_qty"]) for r in self.db.execute(
                    "SELECT qty,filled_qty FROM intents WHERE symbol=? AND side='sell' AND "
                    "status NOT IN ('filled','canceled','expired','rejected','not_sent','broker_refused')", (symbol,))), ZERO)
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
            self._check_quote(quote, now, check_spread=intent.side == "buy")
            if quote.symbol != intent.symbol:
                raise SafetyError("quote_symbol_mismatch")
            if market_open is not True or close - now < (self.limits.min_entry_close_seconds if intent.side == "buy" else 1):
                raise SafetyError("outside_allowed_session")
            self._check_window(intent.side, now)
            self._mark(quote)
            state = self._refresh_risk(now)
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
                if state.gross_exposure_usd > min(self._effective_gross_cap(now), equity):
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

    def mark_broker_refused(self, client_id, http_status):
        """Retire a proven HTTP refusal after transport's client-ID absence check.

        Only 401/403/404 plus a subsequent broker client-ID lookup returning 404
        qualify at the transport seam. Caller owns that evidence; this API never
        infers refusal from absence alone. Timeout/400/422/429/5xx stay ambiguous.
        """
        if type(http_status) is not int or http_status not in (401, 403, 404):
            raise SafetyError("unsupported_broker_refusal_status")
        with self._transaction():
            row = self.db.execute("SELECT * FROM intents WHERE client_id=?", (client_id,)).fetchone()
            if row is None:
                raise SafetyError("unknown_client_order_id")
            intent = _intent(row)
            if intent.status == "broker_refused":
                return False
            if (intent.status != "reserved" or not intent.submit_attempted
                    or intent.broker_id is not None or intent.filled_qty):
                raise SafetyError("cannot_mark_order_broker_refused")
            self.db.execute("UPDATE intents SET status='broker_refused' WHERE client_id=?", (client_id,))
            self._event("broker_refused", client_id, http_status=http_status,
                        evidence_required="submission_http_refusal_then_client_id_404")
            return True

    def record_order(self, client_id, broker_id, status, cumulative_qty, average_price, *, timestamp=None):
        if (type(broker_id) is not str or not broker_id or len(broker_id) > 128
                or type(status) is not str or status not in RANK or status in ("reserved", "not_sent", "broker_refused")):
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
            if old.status == "broker_refused":
                raise SafetyError("broker_observation_after_definitive_refusal")
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
            self._refresh_risk(at)
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
            self._check_quote(quote, now, check_spread=False)
        with self._transaction(keep_observations_on_refusal=True):
            for quote in values:
                self._mark(quote)
            state = self._refresh_risk(now)
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

    def adopt_broker_snapshot(self, snapshot, now):
        """Seed local positions/open-order intents from a broker snapshot at
        startup reconciliation (D1), for an overnight_holds start where
        native_adapter accepted a non-flat broker account instead of
        requiring flat.

        The first call against a fresh (empty) ledger is the common case,
        for which the returned ``ledger_delta`` -- broker minus ledger, per
        D1 -- equals the imported broker totals (computed from before/after
        snapshots of this ledger, never assumed). This method is also
        called on every subsequent resumed invocation (S2's
        ``resume_held_trial`` path) against a ledger that already carries
        the locally, fill-derived cost basis for a held position: D2 --
        that local basis is authoritative and is never overwritten by the
        broker's own average price here. A position the ledger already has
        a row for is left untouched (only positions the ledger *lacks* are
        inserted); the broker's average price and the resulting cost-basis
        delta for any already-held symbol are recorded in the returned
        dict's ``resumed_position_basis`` list for the reconciliation
        receipt, never silently applied to the local row.

        Each open order is inserted as an already-``submit_attempted`` intent
        under its own broker-issued client_order_id (not a freshly-generated
        one), so a subsequent native/broker status update for that order is
        recognized by Controller.observe() instead of freezing the trial as
        an "external_order_detected" order.
        """
        now = instant(now)
        with self._transaction(keep_observations_on_refusal=True):
            before_positions = {p.symbol: p.qty for p in self._positions().values()}
            before_open_orders = len(self.unresolved())
            before_cash_basis = sum((p.cost_basis_usd for p in self._positions().values()), ZERO)
            resumed_position_basis = []
            for row in snapshot.get("positions", []):
                qty = decimal(row["qty"], zero=True)
                if qty <= 0:
                    continue
                symbol = symbol_name(row["symbol"])
                avg_price = decimal(row.get("avg_entry_price", row.get("cost_basis", "0")) or "0")
                cost_basis = qty * avg_price
                existing = self.db.execute(
                    "SELECT qty, cost_basis FROM positions WHERE symbol=?", (symbol,)).fetchone()
                if existing is None:
                    self.db.execute("INSERT INTO positions VALUES (?,?,?)", (symbol, str(qty), str(cost_basis)))
                    self._event("position_adopted", symbol=symbol, qty=str(qty), avg_price=str(avg_price), at=now)
                    continue
                # D2: resume path -- an existing local row's cost basis is
                # fill-derived and authoritative; never overwrite it with
                # the broker's average price. Only record the broker figure
                # and the delta for the reconciliation receipt.
                local_qty, local_cost_basis = D(existing[0]), D(existing[1])
                resumed_position_basis.append({
                    "symbol": symbol, "local_qty": str(local_qty),
                    "local_cost_basis_usd": str(local_cost_basis), "broker_qty": str(qty),
                    "broker_avg_price": str(avg_price), "broker_cost_basis_usd": str(cost_basis),
                    "basis_delta_usd": str(cost_basis - local_cost_basis)})
                self._event("position_resume_basis_retained", symbol=symbol,
                            local_cost_basis=str(local_cost_basis), broker_avg_price=str(avg_price), at=now)
            for row in snapshot.get("orders", []):
                if row.get("status") in TERMINAL:
                    continue
                cid = row.get("client_order_id")
                if not cid or self.db.execute("SELECT 1 FROM intents WHERE client_id=?", (cid,)).fetchone():
                    continue
                symbol = symbol_name(row["symbol"])
                qty = decimal(row["qty"])
                price = decimal(row.get("limit_price", "0") or "0")
                filled_qty = decimal(row.get("filled_qty", "0") or "0", zero=True)
                status = row.get("status")
                if status not in RANK:
                    raise SafetyError("unadoptable_broker_order_status")
                # S8: side is interpolated straight into the intents row and
                # later compared/relied on (e.g. sign of position deltas,
                # order-side-specific reconciliation); a malformed or
                # unexpected broker value must be refused explicitly here,
                # not silently stored.
                if row.get("side") not in ("buy", "sell"):
                    raise SafetyError("unadoptable_broker_order_side")
                self.db.execute(
                    "INSERT INTO intents(client_id,symbol,side,qty,limit_price,status,filled_qty,"
                    "average_price,broker_id,submit_attempted,updated_at) VALUES (?,?,?,?,?,?,?,?,?,1,?)",
                    (cid, symbol, row["side"], str(qty), str(price), status, str(filled_qty),
                     str(decimal(row["filled_avg_price"])) if row.get("filled_avg_price") and filled_qty else None,
                     row.get("id"), now))
                self._event("intent_adopted", cid, symbol=symbol, side=row["side"], qty=qty, at=now)
            after_positions = {p.symbol: p.qty for p in self._positions().values()}
            after_open_orders = len(self.unresolved())
            after_cash_basis = sum((p.cost_basis_usd for p in self._positions().values()), ZERO)
        return {"positions_before": len(before_positions), "positions_after": len(after_positions),
                "open_orders_before": before_open_orders, "open_orders_after": after_open_orders,
                "cost_basis_delta_usd": str(after_cash_basis - before_cash_basis),
                "resumed_position_basis": resumed_position_basis}

    def halted_reason(self):
        """Read-only: current halt reason, or None/"recovery_only" (see
        begin_recovery/begin_next_trial). Callers that need to distinguish a
        genuine risk halt from the reconciliation-pending marker should
        compare against "recovery_only" explicitly, as selector.py's
        OperationalStatus wiring in native_strategy.py does."""
        with self._lock:
            return self._get("halted_reason")

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
