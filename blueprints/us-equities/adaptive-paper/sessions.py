"""Session-aware NYSE market clock for America/New_York equities trading.

This module is deliberately pure: it never reads wall-clock time itself. Every
function takes a timezone-aware ``datetime`` as an explicit input and derives
the NYSE session (PRE / RTH / POST / CLOSED) that timestamp falls into, using
only the Python standard library ``zoneinfo`` for DST-correct America/New_York
conversion.

Session boundaries (Eastern local time, applied on every trading day):
    PRE     04:00 - 09:30
    RTH     09:30 - 16:00 (13:00 on a scheduled early-close day)
    POST    16:00 - 20:00 (13:00 - 20:00 on a scheduled early-close day)
    CLOSED  outside the above, and all day on a weekend or full-closure holiday

The 2026 NYSE full-closure holidays and scheduled 13:00 ET early closes below
are taken from the NYSE published holiday calendar
(https://www.nyse.com/markets/hours-calendars) and cross-checked against the
standard NYSE observance rules: New Year's Day; Martin Luther King, Jr. Day
(3rd Monday of January); Washington's Birthday (3rd Monday of February); Good
Friday (Gregorian Easter Sunday minus two days); Memorial Day (last Monday of
May); Juneteenth National Independence Day (June 19, fixed); Independence Day
(July 4, observed the preceding Friday when it falls on a Saturday); Labor Day
(1st Monday of September); Thanksgiving Day (4th Thursday of November);
Christmas Day (December 25, observed the preceding Friday when it falls on a
Saturday). Early closes are the Friday after Thanksgiving and Christmas Eve.

An optional ``exchange_calendars`` cross-check is provided for environments
that already have that package installed; it is never a hard dependency of
this module or of the engine, and this shared engine environment deliberately
does not install it (see the task's environment constraints). When present,
its NYSE ("XNYS") calendar is compared against the frozen table above for
every session date in 2026; a test skips this comparison when the package is
absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# NYSE 2026 full-closure holidays. Source: NYSE published holiday calendar,
# https://www.nyse.com/markets/hours-calendars.
HOLIDAYS_2026 = frozenset({
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King, Jr. Day
    date(2026, 2, 16),   # Washington's Birthday
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth National Independence Day
    date(2026, 7, 3),    # Independence Day (observed; Jul 4 falls on Saturday)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
})

# NYSE 2026 scheduled early closes (regular session ends 13:00 ET). Source:
# NYSE published holiday calendar, https://www.nyse.com/markets/hours-calendars.
EARLY_CLOSES_2026 = frozenset({
    date(2026, 11, 27),  # Friday after Thanksgiving
    date(2026, 12, 24),  # Christmas Eve
})

PRE_OPEN = dtime(4, 0)
RTH_OPEN = dtime(9, 30)
RTH_CLOSE = dtime(16, 0)
RTH_EARLY_CLOSE = dtime(13, 0)
POST_CLOSE = dtime(20, 0)

_MAX_HOLIDAY_RUN_DAYS = 10  # bounds the trading-day search; NYSE never closes this long

# Years the frozen HOLIDAYS_2026/EARLY_CLOSES_2026 tables actually cover.
# session_at()/is_trading_session() refuse any other year unless the optional
# exchange_calendars backend is importable and can answer for that specific
# date (D7): silently reusing the 2026 table for a different year's calendar
# would misclassify real holidays/early closes.
CALENDAR_YEARS = frozenset({2026})


class SessionKind(str, Enum):
    PRE = "PRE"
    RTH = "RTH"
    POST = "POST"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class SessionInfo:
    kind: SessionKind
    session_date: date
    open: datetime | None
    close: datetime | None
    is_early_close: bool
    next_open: datetime
    seconds_to_close: float | None


def _exchange_calendars_day(d: date):
    """Best-effort out-of-range-year fallback (D7): (is_trading_day, rth_close)
    for ``d`` via the optional exchange_calendars XNYS calendar, or None if
    the package is not importable or cannot answer. Not exercised by any test
    in this environment (exchange_calendars is deliberately not installed
    here); treat as unverified pending a real installation elsewhere."""
    try:
        import exchange_calendars as xcals
    except ImportError:
        return None
    try:
        cal = xcals.get_calendar("XNYS")
        if not bool(cal.is_session(d.isoformat())):
            return False, None
        _, close = cal.session_open_close(d.isoformat())
        close_ny = close.tz_convert(NY)
        return True, dtime(close_ny.hour, close_ny.minute)
    except Exception:
        return None


def _require_supported_calendar_year(d: date) -> None:
    if d.year in CALENDAR_YEARS:
        return
    if _exchange_calendars_day(d) is not None:
        return
    raise ValueError("session_calendar_out_of_range")


def _is_trading_day(d: date) -> bool:
    if d.year in CALENDAR_YEARS:
        return d.weekday() < 5 and d not in HOLIDAYS_2026
    fallback = _exchange_calendars_day(d)
    if fallback is None:
        raise ValueError("session_calendar_out_of_range")
    return fallback[0]


def _rth_close_time(d: date) -> dtime:
    if d.year in CALENDAR_YEARS:
        return RTH_EARLY_CLOSE if d in EARLY_CLOSES_2026 else RTH_CLOSE
    fallback = _exchange_calendars_day(d)
    if fallback is None or fallback[1] is None:
        raise ValueError("session_calendar_out_of_range")
    return fallback[1]


def _next_trading_day(d: date) -> date:
    for _ in range(_MAX_HOLIDAY_RUN_DAYS):
        d = d + timedelta(days=1)
        if _is_trading_day(d):
            return d
    raise ValueError("no_trading_day_found")


def _prev_trading_day(d: date) -> date:
    for _ in range(_MAX_HOLIDAY_RUN_DAYS):
        d = d - timedelta(days=1)
        if _is_trading_day(d):
            return d
    raise ValueError("no_trading_day_found")


def _boundaries(d: date):
    close_t = _rth_close_time(d)
    pre_open = datetime.combine(d, PRE_OPEN, NY)
    rth_open = datetime.combine(d, RTH_OPEN, NY)
    rth_close = datetime.combine(d, close_t, NY)
    post_close = datetime.combine(d, POST_CLOSE, NY)
    return pre_open, rth_open, rth_close, post_close


def session_at(ts: datetime) -> SessionInfo:
    """Classify ``ts`` (timezone-aware) into a NYSE session.

    ``ts`` is always an explicit input; this function never reads wall-clock
    time. Naive datetimes are rejected so callers cannot accidentally pass an
    ambiguous local time.
    """
    if ts.tzinfo is None:
        raise ValueError("ts must be timezone-aware")
    ts_ny = ts.astimezone(NY)
    d = ts_ny.date()
    _require_supported_calendar_year(d)
    is_early = d in EARLY_CLOSES_2026

    if _is_trading_day(d):
        pre_open, rth_open, rth_close, post_close = _boundaries(d)
        if ts_ny < pre_open:
            return SessionInfo(SessionKind.CLOSED, d, None, None, is_early, pre_open, None)
        if pre_open <= ts_ny < rth_open:
            return SessionInfo(SessionKind.PRE, d, pre_open, rth_open, is_early,
                                pre_open, (rth_open - ts_ny).total_seconds())
        if rth_open <= ts_ny < rth_close:
            return SessionInfo(SessionKind.RTH, d, rth_open, rth_close, is_early,
                                rth_open, (rth_close - ts_ny).total_seconds())
        if rth_close <= ts_ny < post_close:
            return SessionInfo(SessionKind.POST, d, rth_close, post_close, is_early,
                                rth_close, (post_close - ts_ny).total_seconds())
        nxt = _next_trading_day(d)
        nxt_pre_open, *_ = _boundaries(nxt)
        return SessionInfo(SessionKind.CLOSED, d, None, None, is_early, nxt_pre_open, None)

    nxt = _next_trading_day(d)
    nxt_pre_open, *_ = _boundaries(nxt)
    return SessionInfo(SessionKind.CLOSED, d, None, None, is_early, nxt_pre_open, None)


def is_trading_session(ts: datetime) -> bool:
    """True for PRE, RTH or POST; False (CLOSED) on weekends, holidays and
    outside the 04:00-20:00 ET window."""
    return session_at(ts).kind != SessionKind.CLOSED


def previous_trading_day(d: date) -> date:
    """D3 (round 4): the trading day immediately before ``d`` (skipping
    weekends/holidays), public so native_strategy.py's gap-risk stop can
    validate a persisted prior-RTH-close's session_date against "the
    trading day immediately before the session being armed" without
    reaching into this module's private ``_prev_trading_day``."""
    return _prev_trading_day(d)


# ---------------------------------------------------------------------------
# Session policy: a single consolidated gate for the extended-hours and
# overnight-holds decisions that previously existed as four separate ad-hoc
# refusal points (config.json's regular_session_only/extended_hours_enabled
# flags in runner.load_config, transport.normalize_intent, transport.submit,
# and native_adapter.AlpacaExecutionClient._submit_order /_connect).
# ---------------------------------------------------------------------------

DEFAULT_SESSION_POLICY = {"extended_hours": False, "overnight_holds": False,
                          "overnight_gross_multiple": "1.0"}


def validate_session_policy(config: dict) -> dict:
    """Validate and return the session policy declared in ``config``.

    With the default config (no ``sessions`` block, or one matching
    ``DEFAULT_SESSION_POLICY``), this enforces exactly the legacy invariant:
    ``regular_session_only`` must be ``True`` and ``extended_hours_enabled``
    must be ``False``. When ``sessions.extended_hours`` is deliberately set to
    ``True`` those two legacy top-level flags must flip in lockstep, so a
    config can never declare extended hours through one field while leaving
    the other in its old value.

    Raises ``ValueError("unqualified_lane_configuration")`` for any
    inconsistent or out-of-bounds policy, matching the error raised by the
    refusal point this consolidates.
    """
    sessions_cfg = config.get("sessions", DEFAULT_SESSION_POLICY)
    if not isinstance(sessions_cfg, dict):
        raise ValueError("unqualified_lane_configuration")
    extended = sessions_cfg.get("extended_hours", False)
    overnight = sessions_cfg.get("overnight_holds", False)
    if type(extended) is not bool or type(overnight) is not bool:
        raise ValueError("unqualified_lane_configuration")
    try:
        multiple = Decimal(str(sessions_cfg.get("overnight_gross_multiple", "1.0")))
        if not multiple.is_finite():
            raise ValueError("unqualified_lane_configuration")
        if not (Decimal("0") < multiple <= Decimal("2.0")):
            raise ValueError("unqualified_lane_configuration")
    except ValueError:
        raise
    except Exception:
        raise ValueError("unqualified_lane_configuration") from None
    if (config.get("regular_session_only") is not (not extended)
            or config.get("extended_hours_enabled") is not extended):
        raise ValueError("unqualified_lane_configuration")
    # D8: overnight_holds without extended_hours has no safe defined
    # semantics in this engine (PRE/POST order handling, the entry cut-off
    # and the exit-only-at-next-RTH-open path all assume extended_hours is
    # also enabled), so the combination is refused rather than given
    # undocumented behaviour.
    if overnight and not extended:
        raise ValueError("unqualified_lane_configuration")
    # S4: a regular-session-only lane (overnight_holds False) never carries
    # a position past the RTH close, so a non-default overnight_gross_multiple
    # would be silent, unused configuration at best and a misleading
    # authorized-exposure figure at worst; require overnight_holds True
    # whenever the multiple deviates from the neutral default of 1.0.
    if multiple != Decimal("1.0") and not overnight:
        raise ValueError("unqualified_lane_configuration")
    # D9: cross-check the overnight cap against leverage/capital so a wide
    # overnight_gross_multiple can never authorize more gross exposure than
    # the account's actual leveraged capital allows. Defaults mirror
    # RiskLimits' own defaults so callers that validate a minimal policy
    # fixture without the full engine config are not forced to supply these.
    try:
        capital_usd = Decimal(str(config.get("capital_usd", "10000")))
        max_gross_exposure_usd = Decimal(str(config.get("max_gross_exposure_usd", "5000")))
        max_leverage = Decimal(str(config.get("max_leverage", "1")))
        if not (capital_usd.is_finite() and max_gross_exposure_usd.is_finite() and max_leverage.is_finite()):
            raise ValueError("unqualified_lane_configuration")
    except ValueError:
        raise
    except Exception:
        raise ValueError("unqualified_lane_configuration") from None
    if max_gross_exposure_usd * multiple > capital_usd * max_leverage:
        raise ValueError("unqualified_lane_configuration")
    return {"extended_hours": extended, "overnight_holds": overnight,
            "overnight_gross_multiple": multiple}


def order_extended_hours_flag(ts: datetime, policy: dict) -> bool:
    """Whether a new order at ``ts`` should carry Alpaca's ``extended_hours``
    flag. Only meaningful (and only ever ``True``) when the session policy has
    extended hours enabled and the order is being placed in PRE or POST; RTH
    orders never need the flag, and CLOSED is never a valid submission time
    (that is refused separately by the existing preflight/session-window
    checks, not by this helper).
    """
    if not policy.get("extended_hours", False):
        return False
    return session_at(ts).kind in (SessionKind.PRE, SessionKind.POST)


def extended_session_close(ts: datetime) -> datetime:
    """The close of the continuous PRE->RTH->POST extended-hours trading
    window containing ``ts`` (deliverable D4). When extended_hours is
    enabled, PRE, RTH and POST form one uninterrupted window rather than
    three separately-closing sessions: PRE's own SessionInfo.close is only
    the RTH-open boundary (09:30), not a real closure -- trading continues
    straight into RTH -- so entries must be bounded by the window's actual
    end, the day's 20:00 ET POST close, regardless of which of PRE/RTH/POST
    ``ts`` currently falls in. Raises ValueError if ``ts`` is CLOSED: there
    is no active window to bound (that state is refused separately by the
    session-aware preflight window check, not by this helper).
    """
    info = session_at(ts)
    if info.kind == SessionKind.CLOSED:
        raise ValueError("no_active_extended_session")
    _, _, _, post_close = _boundaries(info.session_date)
    return post_close


# ---------------------------------------------------------------------------
# Reconciliation / boundary receipts (deliverables 3 and 5).
# ---------------------------------------------------------------------------

def reconciliation_receipt(snapshot: dict, ledger_delta=None, *, boundary: bool = True) -> dict:
    """Build a reconciliation receipt from a broker snapshot.

    Pure and side-effect free: the caller supplies the broker snapshot (as
    already validated/normalized by the transport/native layers) and an
    optional ledger delta description. ``reconciled_at_boundary`` records
    whether this receipt was produced while crossing a session boundary
    (``True``) or at engine startup before any session boundary has been
    crossed yet (``False``).
    """
    positions = list(snapshot.get("positions", []))
    open_orders = [o for o in snapshot.get("orders", [])
                   if o.get("status") not in ("filled", "canceled", "expired", "rejected")]
    return {"positions": positions, "open_orders": open_orders,
            "ledger_delta": ledger_delta, "reconciled_at_boundary": bool(boundary)}


def boundary_receipt(now: datetime, *, positions, cash, cash_delta, open_orders,
                     reconciled_at_boundary: bool) -> dict:
    """A per-session-boundary receipt for a multi-day trial window (deliverable 5).

    ``now`` must be timezone-aware; the receipt records the session the
    boundary falls into so a caller can tell which side of a boundary (e.g.
    end of RTH vs start of next day's PRE) it was written on. ``cash`` is the
    actual account cash balance; ``cash_delta`` is the change since the trial
    baseline. These are kept as separate keys (never conflate a delta with an
    absolute balance).
    """
    info = session_at(now)
    return {"at": now.astimezone(NY).isoformat(), "session_kind": info.kind.value,
            "session_date": info.session_date.isoformat(), "positions": list(positions),
            "cash": str(cash), "cash_delta": str(cash_delta), "open_orders": open_orders,
            "reconciled_at_boundary": bool(reconciled_at_boundary)}


def must_end_flat(policy: dict, *, is_final_boundary: bool) -> bool:
    """The must-end-flat rule: with ``overnight_holds`` disabled (the
    default) every boundary must end flat, exactly like today's single-session
    trial. With ``overnight_holds`` enabled, only the final boundary of a
    multi-day trial window must end flat.
    """
    if not policy.get("overnight_holds", False):
        return True
    return bool(is_final_boundary)


# ---------------------------------------------------------------------------
# Optional exchange_calendars cross-check (not a hard dependency; the shared
# engine environment for this task deliberately does not install it).
# ---------------------------------------------------------------------------

def exchange_calendars_agrees_2026():
    """Return True/False if ``exchange_calendars`` is importable and its XNYS
    calendar was compared against the frozen 2026 table above, or None if the
    package is not installed. Never raises for an absent package."""
    try:
        import exchange_calendars as xcals
    except ImportError:
        return None
    cal = xcals.get_calendar("XNYS")
    d = date(2026, 1, 1)
    end = date(2026, 12, 31)
    while d <= end:
        expected_open = _is_trading_day(d)
        actual_open = bool(cal.is_session(d.isoformat()))
        if expected_open != actual_open:
            return False
        if expected_open:
            open_close = cal.session_open_close(d.isoformat())
            actual_close = open_close[1].tz_convert(NY)
            expected_close_t = _rth_close_time(d)
            if (actual_close.hour, actual_close.minute) != (expected_close_t.hour, expected_close_t.minute):
                return False
        d += timedelta(days=1)
    return True
