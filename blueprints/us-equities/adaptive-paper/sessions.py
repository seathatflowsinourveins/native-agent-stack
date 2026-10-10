"""Session-aware NYSE market clock for America/New_York equities trading.

This module is deliberately pure: it never reads wall-clock time itself. Every
query takes an explicit date or timezone-aware ``datetime`` and derives the
market session (OVERNIGHT / PRE / RTH / POST / CLOSED), with ``zoneinfo`` for DST-correct
America/New_York conversion.

Normal session boundaries (Eastern local time; RTH follows XNYS's schedule):
    PRE     04:00 - 09:30
    RTH     09:30 - 16:00 (13:00 on a scheduled early-close day)
    POST    16:00 - 20:00 (13:00 - 20:00 on a scheduled early-close day)
    OVERNIGHT 20:00 on the prior civil day - 04:00 on the XNYS trade date
    CLOSED  outside the above (no Friday/Saturday evening overnight session)

Alpaca's 24/5 FAQ (updated 2026-07-07, fetched 2026-10-10) and Blue Ocean
Technologies' venue hours define 20:00-04:00 Eastern, Sunday evening through
Friday morning. Holiday eligibility follows the upcoming XNYS trade date;
an early-close trade date still has the full eight-hour overnight window.
https://docs.alpaca.markets/us/docs/245-trading.md
https://blueocean-tech.io/

The source for trading dates, holidays and RTH opening/closing times is XNYS
from required exchange-calendars 4.13.2, gerrymanoim/exchange_calendars commit
dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a:
https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar_xnys.py
Native get_calendar/is_session/session_open/session_close/date_to_session APIs
provide the schedule and session navigation; PRE/POST endpoints remain engine policy.

Every calendar is constructed with explicit bounds: December 1 of the year
before the queried date through January 31 of the following year. Results
therefore never use upstream's wall-clock-derived default bounds (upstream
does initialize those unused defaults at import). Package, construction and
out-of-bounds errors propagate to callers; there is no fallback calendar.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

NY = ZoneInfo("America/New_York")

PRE_OPEN = dtime(4, 0)
RTH_CLOSE = dtime(16, 0)
POST_CLOSE = dtime(20, 0)

class SessionKind(str, Enum):
    OVERNIGHT = "OVERNIGHT"
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


@lru_cache(maxsize=4)
def _xnys_calendar_for_year(year: int):
    """Retain padded calendars for four query years, without consulting today.

    Upstream's factory retains only one bounds tuple per name:
    calendar_utils.py:212-235 at dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a.
    """
    return xcals.get_calendar("XNYS", start=f"{year - 1:04d}-12-01",
                              end=f"{year + 1:04d}-01-31")


def _xnys_calendar(d: date):
    return _xnys_calendar_for_year(d.year)


def is_trading_day(d: date) -> bool:
    """XNYS session membership for an explicit date; provider errors propagate."""
    return _xnys_calendar(d).is_session(d.isoformat())


def _exchange_calendars_day(d: date) -> tuple[bool, dtime | None]:
    """Return XNYS's trading-day status and local RTH close; errors propagate."""
    cal = _xnys_calendar(d)
    if not cal.is_session(d.isoformat()):
        return False, None
    return True, cal.session_close(d.isoformat()).tz_convert(NY).time()


def _rth_close_time(d: date) -> dtime:
    _, close = _exchange_calendars_day(d)
    if close is None:
        raise ValueError("not_a_trading_day")
    return close


def _next_trading_day(d: date) -> date:
    return _xnys_calendar(d).date_to_session(d + timedelta(days=1), direction="next").date()


def _prev_trading_day(d: date) -> date:
    return _xnys_calendar(d).date_to_session(d - timedelta(days=1), direction="previous").date()


def _boundaries(d: date, close_t: dtime | None = None):
    if close_t is None:
        close_t = _rth_close_time(d)
    pre_open = datetime.combine(d, PRE_OPEN, NY)
    # Native session_open: exchange_calendars/exchange_calendar.py:1006-1010
    # at dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a (4.13.2).
    rth_open = _xnys_calendar(d).session_open(d.isoformat()).tz_convert(NY).to_pydatetime()
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
    is_trading_day, close_t = _exchange_calendars_day(d)
    is_early = is_trading_day and close_t < RTH_CLOSE

    # Alpaca assigns 20:00+ activity to the next civil trade date, not the
    # next available session. Skipping a closed trade date would create a
    # phantom Friday/weekend/holiday overnight market.
    overnight_date = d + timedelta(days=1) if ts_ny.time() >= POST_CLOSE else d
    if ts_ny.time() >= POST_CLOSE or ts_ny.time() < PRE_OPEN:
        overnight_day, overnight_close_t = _exchange_calendars_day(overnight_date)
        if overnight_day:
            overnight_open = datetime.combine(overnight_date - timedelta(days=1), POST_CLOSE, NY)
            overnight_close = datetime.combine(overnight_date, PRE_OPEN, NY)
            return SessionInfo(SessionKind.OVERNIGHT, overnight_date, overnight_open,
                               overnight_close, overnight_close_t < RTH_CLOSE,
                               overnight_open, (overnight_close - ts_ny).total_seconds())

    if is_trading_day:
        pre_open, rth_open, rth_close, post_close = _boundaries(d, close_t)
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
        nxt_open = datetime.combine(nxt - timedelta(days=1), POST_CLOSE, NY)
        return SessionInfo(SessionKind.CLOSED, d, None, None, is_early, nxt_open, None)

    nxt = _next_trading_day(d)
    nxt_open = datetime.combine(nxt - timedelta(days=1), POST_CLOSE, NY)
    return SessionInfo(SessionKind.CLOSED, d, None, None, is_early, nxt_open, None)


def is_trading_session(ts: datetime) -> bool:
    """Market availability including OVERNIGHT, independent of lane admission.

    A known market session alone grants no order or paper-acceptance authority.
    """
    return session_at(ts).kind != SessionKind.CLOSED


def previous_trading_day(d: date) -> date:
    """D3 (round 4): the trading day immediately before ``d`` (skipping
    weekends/holidays), public so native_strategy.py's gap-risk stop can
    validate a persisted prior-RTH-close's session_date against "the
    trading day immediately before the session being armed" without
    reaching into this module's private ``_prev_trading_day``."""
    return _prev_trading_day(d)


def next_trading_day(d: date) -> date:
    """The trading day immediately after ``d`` (skipping weekends/holidays),
    public for the same reason ``previous_trading_day`` is: the corporate-
    action guard's overnight hold horizon (corporate_actions.py, consulted
    from native_strategy.py) is "today's session, extended through the
    next trading session", and needs this without reaching into this
    module's private ``_next_trading_day``. Raises ``ValueError`` on a date
    outside the upstream calendar's bounds, exactly like
    ``previous_trading_day``; callers must fail closed on that, never guess
    a horizon."""
    return _next_trading_day(d)


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
    extended hours enabled and the order is being placed in OVERNIGHT, PRE or POST; RTH
    orders never need the flag, and CLOSED is never a valid submission time
    (that is refused separately by the existing preflight/session-window
    checks, not by this helper).
    """
    if not policy.get("extended_hours", False):
        return False
    return session_at(ts).kind in (SessionKind.OVERNIGHT, SessionKind.PRE, SessionKind.POST)


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
