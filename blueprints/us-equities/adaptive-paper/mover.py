"""Mover trial mode: pure, deterministic logic (protocol mover-early-entry-v1-20260924, paper_e2e).

No broker transport, credential, network or NautilusTrader import lives here. This
module validates the mover config and the scanner's JSON file, sizes entries,
prices marketable limits, evaluates the X1-X4 exit rules and runs the per-symbol
order state machine (``MoverBook``) that ``mover_strategy.MoverStrategy``
executes inside the native LiveNode. Every order it proposes still passes the
engine's controller and ledger checks (``safety.Ledger.reserve_intent``) before
any broker request; nothing here relaxes a ledger cap.

Two per-order caps apply. The mover entry cap (``mover.max_entry_notional_usd``)
sizes and bounds every buy; ``mover_runner.MoverController`` also refuses a larger
buy before the ledger reserves it. The ledger's per-order cap
(``max_order_notional_usd``) bounds every order, exit sells included, so config
load requires it to be at least ``EXIT_HEADROOM_FACTOR`` times the entry cap.

Protocol constants (the sizing formula, the drawdown ladder, the X1-X4
parameters and the exit headroom factor) are fixed below rather than
configurable, so a config cannot drift from the protocol. The config selects the
rule, the exit, the rung schedule, the entry/exit limit caps and timeouts, the
entry cap and the engine's own risk caps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, localcontext
import hashlib
import json
import math
from pathlib import Path
import re
import sys

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from feeds import is_qualified_feed  # noqa: E402
from leverage import validate_leverage_policy  # noqa: E402
from safety import RiskLimits, SafetyError, symbol_name  # noqa: E402
from sessions import NY, _rth_close_time, validate_session_policy  # noqa: E402

D = Decimal
ZERO = D(0)

PROTOCOL_ID = "mover-early-entry-v1-20260924"
PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
EXIT_RULES = ("X1", "X2", "X3", "X4")
SESSION_SCOPES = ("pre_market_only", "any_session")
EVIDENCE_CLASSES = ("PAPER", "SYN")

# Sizing: notional_i = equity x L_i / SLOTS, L = min(MAX_LEVERAGE, rung x regime x drawdown).
MAX_SYMBOLS = 5
SLOTS = D(5)
MAX_LEVERAGE = D(4)
LOW_PRICE_USD = D(5)
LOW_PRICE_MAX_LEVERAGE = D(1)
DOLLAR_VOLUME_CAP_FRACTION = D("0.01")
ENTRY_BAR_CAP_FRACTION = D("0.10")
REGIME_ON_FACTOR = D(1)
REGIME_OFF_FACTOR = D("0.5")
# Drawdown from the mover ledger's equity peak: <=10% -> 1, <=20% -> 0.5, beyond 20% -> no entries for 10 sessions.
DRAWDOWN_HALF_ABOVE = D("0.10")
DRAWDOWN_PAUSE_ABOVE = D("0.20")
DRAWDOWN_PAUSE_SESSIONS = 10

MAX_SCAN_AGE_SECONDS = 300
CLOCK_TOLERANCE_SECONDS = 0.25
# The scanner's own firing rule (mover-early-entry rules.fires: protocol min_price and clarification
# C25): price_at_t >= 1.00 USD and gain >= G - 1e-9 as a ratio. mover_scan.engine_scan writes the gain
# in percentage points to nine decimals, so the same tolerance here is 1e-7 percentage points.
SCAN_MIN_PRICE_USD = D("1.00")
SCAN_GAIN_TOLERANCE_PCT = D("0.0000001")

X1_FLATTEN_AT_ET = dtime(15, 58)
X2_HOLD_SECONDS = 3600
X3_TRAIL_FRACTION = D("0.85")
X4_STOP_FRACTION = D("0.85")
X4_TARGET_FRACTION = D("1.50")

# Exit budget: at most max_exit_orders_per_symbol exit orders per leg, counted from the
# latest grant (trial start, then once more when a force reason latches). A sell the
# ledger or engine refused before any broker request is not charged; it is retried after
# PRE_WIRE_RETRY_SECONDS and has its own bound of the same size. Once a force reason has
# latched, the native loop hands every residual to recovery.recover when no exit has
# filled for HANDOFF_EXIT_TIMEOUTS exit timeouts or every held leg's exits are blocked.
PRE_WIRE_RETRY_SECONDS = 1.0
HANDOFF_EXIT_TIMEOUTS = 3
EXIT_BUDGET_EXHAUSTED = ("exit_orders_exhausted", "exit_refusals_exhausted")

# Exit headroom: the ledger's per-order cap bounds exit sells as well as buys, so config load
# requires max_order_notional_usd >= EXIT_HEADROOM_FACTOR x mover.max_entry_notional_usd. An
# entry is at most the entry cap, so a leg then sells in one order through a tenfold rise, and
# in whole-share chunks until one share is worth more than the ledger cap. Past that no engine
# order can sell it: the book blocks the leg (exit_share_exceeds_ledger_order_cap), recovery
# ends needs_attention, and the receipt lists the position (share_exceeds_ledger_order_cap).
# Ten is the largest factor the example's 2000 USD gross cap allows over its 200 USD entry cap
# (RiskLimits keeps the per-order cap at or below the gross cap). Keep-but-compare: the
# historical distribution of scanned movers' largest rise within the hold is the comparison
# that would change it.
EXIT_HEADROOM_FACTOR = D(10)
EXIT_SHARE_BLOCKED = "exit_share_exceeds_ledger_order_cap"

PRE_MARKET_OPEN_ET = dtime(4, 0)
RTH_OPEN_ET = dtime(9, 30)
RTH_CLOSE_ET = dtime(16, 0)
POST_CLOSE_ET = dtime(20, 0)

TERMINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "denied", "not_sent", "broker_refused"})


class MoverRefusal(SafetyError):
    """Bounded reason code for a scan, plan or session refusal. Never carries broker text."""


# ---------------------------------------------------------------------------
# Small parsing helpers
# ---------------------------------------------------------------------------

_DECIMAL_TEXT = re.compile(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]{1,3})?")


def parse_decimal(value):
    """A finite Decimal from str/int/float (floats via their shortest repr), else None.
    bool is refused even though it is an int subclass."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None
        text = repr(value)
    elif isinstance(value, str):
        text = value
    else:
        return None
    if not _DECIMAL_TEXT.fullmatch(text):
        return None
    try:
        result = D(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def text(value):
    """Plain fixed-point text for a Decimal (never exponent notation); other values unchanged."""
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def parse_hhmm(value, reason):
    if type(value) is not str or not re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", value):
        raise ValueError(reason)
    hours, minutes = int(value[:2]), int(value[3:])
    if hours > 23:
        raise ValueError(reason)
    return dtime(hours, minutes)


def et_epoch(session_date, at):
    """POSIX seconds for wall-clock ``at`` (America/New_York) on ``session_date``."""
    return datetime.combine(session_date, at, NY).timestamp()


def _seconds_of_day(at):
    return at.hour * 3600 + at.minute * 60 + at.second


def et_datetime(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(NY)


def broker_ref(venue_order_id):
    """A short, stable digest of a broker order id for receipts. Alpaca ids are UUIDs,
    which publication checks treat as private identifiers, so the raw id is never kept."""
    if venue_order_id is None:
        return None
    return hashlib.sha256(str(venue_order_id).encode()).hexdigest()[:16]


_DETAIL = re.compile(r"[^A-Za-z0-9_ .:()=/-]")


def bounded_detail(value):
    """Engine-generated refusal text, restricted to a safe alphabet and 120 characters."""
    if value is None:
        return None
    return _DETAIL.sub("_", str(value))[:120]


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------

_RULE = re.compile(r"(?P<hh>[0-2][0-9]):(?P<mm>[0-5][0-9])\|G(?P<gain>[0-9]+(?:\.[0-9]+)?)"
                   r"\|V(?P<volume>[0-9]+(?:\.[0-9]+)?)(?P<suffix>[KMB]?)\|(?P<news>any|news_before_t)")
_VOLUME_SUFFIX = {"": D(1), "K": D(10) ** 3, "M": D(10) ** 6, "B": D(10) ** 9}


@dataclass(frozen=True)
class Rule:
    """``HH:MM|G<gain>|V<dollar volume>|<any|news_before_t>``: at HH:MM ET, a gain of at
    least G percent points versus the previous close, a dollar volume of at least V
    (an optional K/M/B suffix scales V), and optionally news before t."""
    text: str
    at_et: dtime
    min_gain_pct: Decimal
    min_dollar_volume: Decimal
    news: str


def parse_rule(value):
    if type(value) is not str:
        raise ValueError("invalid_mover_rule")
    match = _RULE.fullmatch(value)
    if match is None or int(match["hh"]) > 23:
        raise ValueError("invalid_mover_rule")
    at = dtime(int(match["hh"]), int(match["mm"]))
    if not PRE_MARKET_OPEN_ET <= at < POST_CLOSE_ET:
        raise ValueError("invalid_mover_rule")
    volume = D(match["volume"]) * _VOLUME_SUFFIX[match["suffix"]]
    return Rule(value, at, D(match["gain"]), volume, match["news"])


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MoverSettings:
    rule: Rule
    session_scope: str
    trial_end_et: dtime
    exit_rule: str
    entry_cap_bps: Decimal
    entry_timeout_seconds: int
    entry_window_seconds: int
    exit_cap_bps: Decimal
    exit_timeout_seconds: int
    max_exit_orders_per_symbol: int
    flatten_reserve_seconds: int
    max_scan_age_seconds: int
    max_symbols: int
    max_entry_notional_usd: Decimal
    appreciation_allowance: Decimal
    gross_guard_fraction: Decimal
    stream_quote_timeout_seconds: int
    rung_schedule: tuple
    benchmarks: tuple


def _require_key(config, key):
    if key not in config:
        raise ValueError("mover_config_missing:" + key)
    return config[key]


def _int_setting(block, key, low, high, default=None):
    value = block.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid_mover_setting:" + key)
    return value


def _decimal_setting(block, key, low, high, default=None, *, low_inclusive=True):
    raw = block.get(key, default)
    if type(raw) is not str:
        raise ValueError("invalid_mover_setting:" + key)
    value = parse_decimal(raw)
    if value is None or value > high or value < low or (not low_inclusive and value == low):
        raise ValueError("invalid_mover_setting:" + key)
    return value


def _rung_schedule(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError("invalid_mover_rung_schedule")
    rows, expected_from = [], 1
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"from_session", "to_session", "rung"}:
            raise ValueError("invalid_mover_rung_schedule")
        start, end, rung_text = item["from_session"], item["to_session"], item["rung"]
        if (type(start) is not int or type(end) is not int or start != expected_from or end < start
                or end > 10000 or type(rung_text) is not str):
            raise ValueError("invalid_mover_rung_schedule")
        rung = parse_decimal(rung_text)
        if rung is None or not ZERO < rung <= MAX_LEVERAGE or rung.as_tuple().exponent < -2:
            raise ValueError("invalid_mover_rung_schedule")
        rows.append((start, end, rung))
        expected_from = end + 1
    return tuple(rows)


def load_mover_config(path):
    """Validate a mover config and build its RiskLimits.

    Returns ``(config, limits, settings)``. ``config`` keeps the engine's key names so
    ``runner.validate_preflight`` and ``recovery.recover`` consume it unchanged; a
    trial adds ``symbols`` from the scan (see ``engine_config``). The same lane gates
    as ``runner.load_config`` apply: paper endpoint only, catalysts off, leverage above
    1x only under a validated ``leverage_policy`` block, and the consolidated session
    policy. ``max_leverage`` must also be positive and at least the highest scheduled
    rung, because entries are sized at the full rung. The universe must not be fixed in
    config. ``mover.max_entry_notional_usd`` is required, and the ledger's
    ``max_order_notional_usd`` (which also bounds every exit sell) must be at least
    ``EXIT_HEADROOM_FACTOR`` times it. An X1 exit must be able to fire: a trial end at
    or before 15:58, or a session-close latch (the controller close less
    ``cleanup_seconds``, see ``mover_runner.run_mover``) at or before it, is refused.
    """
    try:
        config = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ValueError("invalid_mover_config_json") from error
    if (not isinstance(config, dict) or config.get("schema_version") != 1
            or isinstance(config.get("schema_version"), bool)
            or config.get("mode") != "mover_paper" or config.get("protocol") != PROTOCOL_ID):
        raise ValueError("unqualified_mover_configuration")
    if "symbols" in config:
        raise ValueError("mover_universe_comes_from_scan")
    if not is_qualified_feed(config.get("feed")):
        raise ValueError("unqualified_data_feed")
    leverage_block = "leverage_policy" in config
    max_leverage = parse_decimal(str(_require_key(config, "max_leverage")))
    if (config.get("endpoint") != PAPER_ENDPOINT or config.get("catalyst_orders_enabled") is not False
            or max_leverage is None or max_leverage <= 0 or (max_leverage > 1 and not leverage_block)):
        raise ValueError("unqualified_lane_configuration")
    session_policy = validate_session_policy(config)
    if session_policy["overnight_holds"]:
        raise ValueError("mover_requires_flat_end")
    leverage = validate_leverage_policy(config, session_policy) if leverage_block else None
    if leverage is not None:
        config["_leverage_policy"] = leverage
    for key in ("capital_usd", "max_gross_exposure_usd", "max_order_notional_usd", "max_order_quantity",
                "max_gross_loss_usd", "max_drawdown_usd", "max_spread_bps", "max_held_symbols",
                "max_outstanding_orders", "max_api_requests_per_minute", "max_submit_requests_per_minute",
                "quote_max_age_seconds", "duration_seconds", "cleanup_seconds", "min_entry_close_seconds",
                "order_timeout_seconds", "benchmarks", "mover"):
        _require_key(config, key)
    if type(config["order_timeout_seconds"]) is not int or not 1 <= config["order_timeout_seconds"] <= 60:
        raise ValueError("invalid_mover_setting:order_timeout_seconds")
    limits = RiskLimits(capital_usd=config["capital_usd"], max_gross_exposure_usd=config["max_gross_exposure_usd"],
                        max_order_notional_usd=config["max_order_notional_usd"],
                        max_order_qty=str(config["max_order_quantity"]),
                        max_order_qty_mode=config.get("max_order_qty_mode", "fixed"),
                        max_gross_loss_usd=config["max_gross_loss_usd"], max_drawdown_usd=config["max_drawdown_usd"],
                        max_spread_bps=config["max_spread_bps"], max_held_symbols=config["max_held_symbols"],
                        max_outstanding_orders=config["max_outstanding_orders"],
                        max_rest_per_minute=config["max_api_requests_per_minute"],
                        max_submits_per_minute=config["max_submit_requests_per_minute"],
                        quote_max_age_seconds=config["quote_max_age_seconds"],
                        trial_seconds=config["duration_seconds"], cleanup_seconds=config["cleanup_seconds"],
                        min_entry_close_seconds=config["min_entry_close_seconds"],
                        overnight_gross_multiple=session_policy["overnight_gross_multiple"],
                        **({"leverage": leverage} if leverage is not None else {}))
    if limits.max_order_qty_mode != "notional":
        # recovery.recover sizes each exit within the ledger's effective_max_order_qty. Only
        # "notional" mode makes that floor(max_order_notional_usd / bid) whole shares; in
        # "fixed" mode a recovery chunk can be the fractional notional capacity, which a
        # non-fractionable mover cannot sell.
        raise ValueError("mover_requires_notional_order_qty_mode")
    benchmarks = config["benchmarks"]
    if not isinstance(benchmarks, list) or not 1 <= len(benchmarks) <= 3 or len(set(benchmarks)) != len(benchmarks):
        raise ValueError("invalid_mover_benchmarks")
    try:
        benchmarks = tuple(symbol_name(s) for s in benchmarks)
    except SafetyError:
        raise ValueError("invalid_mover_benchmarks") from None
    block = config["mover"]
    if not isinstance(block, dict):
        raise ValueError("invalid_mover_block")
    allowed = {"rule", "session_scope", "trial_end_et", "exit", "entry", "exit_orders", "flatten_reserve_seconds",
               "max_scan_age_seconds", "max_symbols", "max_entry_notional_usd", "appreciation_allowance",
               "gross_guard_fraction", "stream_quote_timeout_seconds", "rung_schedule"}
    if set(block) - allowed:
        raise ValueError("invalid_mover_block")
    rule = parse_rule(block.get("rule"))
    scope = block.get("session_scope")
    if scope not in SESSION_SCOPES:
        raise ValueError("invalid_mover_setting:session_scope")
    trial_end = parse_hhmm(block.get("trial_end_et"), "invalid_mover_setting:trial_end_et")
    exit_rule = block.get("exit")
    if exit_rule not in EXIT_RULES:
        raise ValueError("invalid_mover_setting:exit")
    if scope == "pre_market_only":
        if not session_policy["extended_hours"]:
            raise ValueError("mover_pre_market_requires_extended_hours")
        if not PRE_MARKET_OPEN_ET < trial_end <= RTH_OPEN_ET or not rule.at_et < RTH_OPEN_ET:
            raise ValueError("mover_pre_market_window_invalid")
        if exit_rule == "X1":
            raise ValueError("mover_x1_requires_regular_session")
    else:
        latest = POST_CLOSE_ET if session_policy["extended_hours"] else RTH_CLOSE_ET
        if not PRE_MARKET_OPEN_ET < trial_end <= latest:
            raise ValueError("mover_trial_end_outside_session")
        if exit_rule == "X1":
            # Otherwise the hard flatten at trial_end_et, or run_mover's session_close latch at the
            # controller close (16:00, or 20:00 with extended hours) less cleanup_seconds, flattens
            # every leg at or before 15:58 and X1 can never fire.
            if trial_end <= X1_FLATTEN_AT_ET:
                raise ValueError("mover_x1_preempted_by_trial_end")
            if _seconds_of_day(latest) - _seconds_of_day(X1_FLATTEN_AT_ET) <= limits.cleanup_seconds:
                raise ValueError("mover_x1_preempted_by_session_close")
    entry = block.get("entry", {})
    exits = block.get("exit_orders", {})
    if not isinstance(entry, dict) or not isinstance(exits, dict) or set(entry) - {
            "limit_cap_bps", "timeout_seconds", "window_seconds"} or set(exits) - {
            "limit_cap_bps", "timeout_seconds", "max_orders_per_symbol"}:
        raise ValueError("invalid_mover_block")
    quote_age = config["quote_max_age_seconds"]
    settings = MoverSettings(
        rule=rule, session_scope=scope, trial_end_et=trial_end, exit_rule=exit_rule,
        entry_cap_bps=_decimal_setting(entry, "limit_cap_bps", ZERO, D(200), "50", low_inclusive=False),
        entry_timeout_seconds=_int_setting(entry, "timeout_seconds", 1, 600, 60),
        entry_window_seconds=_int_setting(entry, "window_seconds", 1, 300, 30),
        exit_cap_bps=_decimal_setting(exits, "limit_cap_bps", ZERO, D(500), "50", low_inclusive=False),
        exit_timeout_seconds=_int_setting(exits, "timeout_seconds", 1, 120, 10),
        max_exit_orders_per_symbol=_int_setting(exits, "max_orders_per_symbol", 1, 100, 20),
        flatten_reserve_seconds=_int_setting(block, "flatten_reserve_seconds", 10, 600, 120),
        max_scan_age_seconds=_int_setting(block, "max_scan_age_seconds", 1, MAX_SCAN_AGE_SECONDS, MAX_SCAN_AGE_SECONDS),
        max_symbols=_int_setting(block, "max_symbols", 1, MAX_SYMBOLS, MAX_SYMBOLS),
        max_entry_notional_usd=_decimal_setting(block, "max_entry_notional_usd", ZERO, D(10000), low_inclusive=False),
        appreciation_allowance=_decimal_setting(block, "appreciation_allowance", D(1), D(10), "2"),
        gross_guard_fraction=_decimal_setting(block, "gross_guard_fraction", D("0.5"), D("0.99"), "0.9"),
        stream_quote_timeout_seconds=(quote_age if "stream_quote_timeout_seconds" not in block else
                                      _int_setting(block, "stream_quote_timeout_seconds", quote_age, 30)),
        rung_schedule=_rung_schedule(block.get("rung_schedule")),
        benchmarks=benchmarks)
    if limits.max_held_symbols < settings.max_symbols or limits.max_outstanding_orders < 2 * settings.max_symbols:
        raise ValueError("mover_symbol_or_order_caps_below_scan_size")
    if limits.max_order_notional_usd < settings.max_entry_notional_usd * EXIT_HEADROOM_FACTOR:
        # The ledger's per-order cap also bounds every exit sell (see EXIT_HEADROOM_FACTOR).
        raise ValueError("mover_ledger_order_cap_below_exit_headroom")
    top_rung = max(rung for _, _, rung in settings.rung_schedule)
    if top_rung > 1 and (leverage is None or leverage.max_leverage < top_rung):
        raise ValueError("mover_rung_requires_leverage_policy")
    if top_rung > max_leverage:
        # build_plan sizes entries at the full rung; without a leverage_policy block nothing else
        # holds them to a max_leverage below 1.
        raise ValueError("mover_rung_exceeds_max_leverage")
    if settings.flatten_reserve_seconds >= config["duration_seconds"] + config["cleanup_seconds"]:
        raise ValueError("invalid_mover_setting:flatten_reserve_seconds")
    return config, limits, settings


def engine_config(config, symbols):
    """The engine-shaped config for one trial: the scan's symbols plus the benchmarks,
    which is what runner.validate_preflight checks for tradability and quote readiness."""
    result = dict(config)
    result["symbols"] = sorted(set(symbols) | set(config["benchmarks"]))
    return result


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanSymbol:
    symbol: str
    rank: int
    price_at_t: Decimal
    dollar_volume_at_t: Decimal
    entry_bar_dollar_volume: Decimal | None
    gain_pct_at_t: Decimal | None = None
    news_before_t: bool | None = None


@dataclass(frozen=True)
class Scan:
    sha256: str
    rule: str
    scan_time: float
    session_date: date
    age_seconds: float
    symbols: tuple
    regime_factor: Decimal
    regime_source: str
    regime_inputs: dict | None


_SCAN_KEYS = {"schema_version", "kind", "protocol", "rule", "scan_time", "session_date", "regime", "symbols", "notes",
              "source"}
_SCAN_SYMBOL_KEYS = {"symbol", "rank", "price_at_t", "dollar_volume_at_t", "entry_bar_dollar_volume",
                     "gain_pct_at_t", "news_before_t"}
_REGIME_INPUTS = ("spy_prev_close", "spy_sma20", "spy_rv20", "spy_rv20_median252")


def _scan_decimal(value, reason, *, maximum=D("1e13"), allow_negative=False):
    number = parse_decimal(value)
    if number is None or number > maximum or (number <= 0 and not allow_negative) or number < -maximum:
        raise MoverRefusal(reason)
    if number.as_tuple().exponent < -9:
        raise MoverRefusal(reason)
    return number


def _parse_scan_time(value):
    if type(value) is not str or "T" not in value:
        raise MoverRefusal("scan_time_invalid")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise MoverRefusal("scan_time_invalid") from None
    if moment.tzinfo is None:
        raise MoverRefusal("scan_time_invalid")
    try:
        moment.timestamp()
        moment.astimezone(NY)  # an offset at the edge of the datetime range overflows here
    except (OverflowError, ValueError):
        raise MoverRefusal("scan_time_invalid") from None
    return moment


def regime_factor(regime):
    """(factor, source, inputs) from the scan's optional ``regime`` block.

    Factor 1 when SPY's previous close is above its 20-session mean and its 20-session
    realised volatility is below its 252-session median, else 0.5. The engine does not
    fetch history: the scanner supplies either the four inputs (recomputed here and
    compared with any declared factor) or a precomputed factor. An absent block gives
    the conservative 0.5."""
    if regime is None:
        return REGIME_OFF_FACTOR, "absent_conservative_default", None
    if not isinstance(regime, dict) or set(regime) - {"factor", "inputs", "as_of_session"}:
        raise MoverRefusal("scan_regime_invalid")
    declared = None
    if "factor" in regime:
        declared = parse_decimal(regime["factor"])
        if declared not in (REGIME_ON_FACTOR, REGIME_OFF_FACTOR):
            raise MoverRefusal("scan_regime_invalid")
    inputs = regime.get("inputs")
    if inputs is None:
        if declared is None:
            raise MoverRefusal("scan_regime_invalid")
        return declared, "scan_precomputed", None
    if not isinstance(inputs, dict) or set(inputs) != set(_REGIME_INPUTS):
        raise MoverRefusal("scan_regime_invalid")
    values = {key: _scan_decimal(inputs[key], "scan_regime_invalid") for key in _REGIME_INPUTS}
    computed = (REGIME_ON_FACTOR if values["spy_prev_close"] > values["spy_sma20"]
                and values["spy_rv20"] < values["spy_rv20_median252"] else REGIME_OFF_FACTOR)
    if declared is not None and declared != computed:
        raise MoverRefusal("scan_regime_factor_inconsistent")
    return computed, "scan_inputs_recomputed", {key: text(value) for key, value in values.items()}


def load_scan(raw, settings, *, now):
    """Validate the scanner's JSON bytes against the configured rule and freshness bound.

    Refuses (``MoverRefusal``) a scan older than ``settings.max_scan_age_seconds``
    (at most five minutes) or stamped in the future, a scan taken before the rule's
    HH:MM, a rule other than the configured one, more than ``max_symbols`` symbols,
    and any row the scanner's frozen rule would not fire: a price below the protocol's
    1.00 USD minimum, a dollar volume below V, a supplied gain below G (less the
    scanner's own tolerance, ``SCAN_GAIN_TOLERANCE_PCT``), or missing news when the rule
    requires it. ``now=None`` evaluates the scan as of its own ``scan_time``: every
    check but the two age bounds, for ``check --assume-fresh`` and ``synthetic
    --allow-stale-scan``."""
    if not isinstance(raw, (bytes, bytearray)):
        raise MoverRefusal("scan_unreadable")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw)
    except ValueError:
        raise MoverRefusal("scan_invalid_json") from None
    if (not isinstance(data, dict) or set(data) - _SCAN_KEYS or data.get("schema_version") != 1
            or isinstance(data.get("schema_version"), bool) or data.get("kind") != "mover_scan"
            or data.get("protocol") != PROTOCOL_ID):
        raise MoverRefusal("scan_schema_invalid")
    if data.get("rule") != settings.rule.text:
        raise MoverRefusal("scan_rule_differs_from_config")
    moment = _parse_scan_time(data.get("scan_time"))
    scan_time = moment.timestamp()
    age = 0.0 if now is None else now - scan_time
    if age < -CLOCK_TOLERANCE_SECONDS:
        raise MoverRefusal("scan_from_future")
    if age > settings.max_scan_age_seconds:
        raise MoverRefusal("scan_stale")
    local = moment.astimezone(NY)
    session_date = local.date()
    if "session_date" in data and data["session_date"] != session_date.isoformat():
        raise MoverRefusal("scan_session_date_mismatch")
    if local.time() < settings.rule.at_et:
        raise MoverRefusal("scan_precedes_rule_time")
    factor, source, inputs = regime_factor(data.get("regime"))
    rows = data.get("symbols")
    if not isinstance(rows, list) or len(rows) > settings.max_symbols:
        raise MoverRefusal("scan_symbols_invalid")
    symbols, seen, ranks = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - _SCAN_SYMBOL_KEYS or not {
                "symbol", "rank", "price_at_t", "dollar_volume_at_t", "entry_bar_dollar_volume"} <= set(row):
            raise MoverRefusal("scan_symbol_fields_invalid")
        try:
            symbol = symbol_name(row["symbol"])
        except SafetyError:
            raise MoverRefusal("scan_symbol_invalid") from None
        rank = row["rank"]
        if type(rank) is not int or not 1 <= rank <= settings.max_symbols or rank in ranks or symbol in seen:
            raise MoverRefusal("scan_rank_or_symbol_duplicate")
        seen.add(symbol)
        ranks.add(rank)
        price = _scan_decimal(row["price_at_t"], "scan_price_invalid", maximum=D("1000000"))
        volume = _scan_decimal(row["dollar_volume_at_t"], "scan_dollar_volume_invalid")
        bar = row["entry_bar_dollar_volume"]
        bar = None if bar is None else _scan_decimal(bar, "scan_entry_bar_dollar_volume_invalid")
        gain = row.get("gain_pct_at_t")
        gain = None if gain is None else _scan_decimal(gain, "scan_gain_invalid", maximum=D("1000000"),
                                                       allow_negative=True)
        news = row.get("news_before_t")
        if news is not None and type(news) is not bool:
            raise MoverRefusal("scan_news_flag_invalid")
        if price < SCAN_MIN_PRICE_USD:
            raise MoverRefusal("scan_symbol_below_min_price")
        if volume < settings.rule.min_dollar_volume:
            raise MoverRefusal("scan_symbol_below_rule_dollar_volume")
        if gain is not None and gain < settings.rule.min_gain_pct - SCAN_GAIN_TOLERANCE_PCT:
            raise MoverRefusal("scan_symbol_below_rule_gain")
        if settings.rule.news == "news_before_t" and news is not True:
            raise MoverRefusal("scan_symbol_without_required_news")
        symbols.append(ScanSymbol(symbol, rank, price, volume, bar, gain, news))
    if ranks and ranks != set(range(1, len(ranks) + 1)):
        raise MoverRefusal("scan_ranks_not_contiguous")
    symbols.sort(key=lambda item: item.rank)
    return Scan(digest, settings.rule.text, scan_time, session_date, age, tuple(symbols), factor, source, inputs)


# ---------------------------------------------------------------------------
# Paper sessions, drawdown ladder and leverage multiple
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionPlan:
    number: int
    rung: Decimal
    equity_usd: Decimal
    equity_peak_usd: Decimal
    drawdown_fraction: Decimal
    drawdown_factor: Decimal
    paused: bool
    pause_sessions_remaining_after: int
    reason: str | None


def _state_value(state, key, default):
    if state is None:
        return default
    return state.get(key, default)


def plan_session(state, *, equity, rung_schedule):
    """The next paper session's rung and drawdown factor from the lane state.

    ``state`` is the previous ``session_state_after`` result (None for the first
    session). The equity peak is the highest session-boundary mover-ledger equity.
    A drawdown beyond 20% pauses entries for this and the next nine sessions; a
    session beyond the configured rung schedule is refused."""
    equity = D(equity)
    started = _state_value(state, "sessions_started", 0)
    remaining = _state_value(state, "pause_sessions_remaining", 0)
    if type(started) is not int or started < 0 or type(remaining) is not int or remaining < 0:
        raise MoverRefusal("mover_state_invalid")
    peak_text = _state_value(state, "equity_peak_usd", None)
    prior_peak = parse_decimal(peak_text) if peak_text is not None else equity
    if prior_peak is None or prior_peak <= 0:
        raise MoverRefusal("mover_state_invalid")
    number = started + 1
    rung = next((r for start, end, r in rung_schedule if start <= number <= end), None)
    if rung is None:
        raise MoverRefusal("mover_session_beyond_rung_schedule")
    peak = max(prior_peak, equity)
    drawdown = max(ZERO, (peak - equity) / peak) if peak > 0 else D(1)
    if remaining > 0:
        return SessionPlan(number, rung, equity, peak, drawdown, ZERO, True, remaining - 1, "drawdown_pause_active")
    if drawdown > DRAWDOWN_PAUSE_ABOVE:
        return SessionPlan(number, rung, equity, peak, drawdown, ZERO, True, DRAWDOWN_PAUSE_SESSIONS - 1,
                           "drawdown_beyond_20pct")
    factor = D("0.5") if drawdown > DRAWDOWN_HALF_ABOVE else D(1)
    return SessionPlan(number, rung, equity, peak, drawdown, factor, False, 0, None)


def session_state_after(plan, *, equity_end):
    """Lane state to persist once a session has started: count it, carry the pause and
    raise the equity peak to the session-end equity when that is higher."""
    return {"sessions_started": plan.number, "pause_sessions_remaining": plan.pause_sessions_remaining_after,
            "equity_peak_usd": text(max(plan.equity_peak_usd, D(equity_end)))}


def leverage_multiple(rung, regime, drawdown_factor):
    return min(MAX_LEVERAGE, D(rung) * D(regime) * D(drawdown_factor))


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

CENT = D("0.01")


@dataclass(frozen=True)
class SymbolSizing:
    scan: ScanSymbol
    leverage_i: Decimal
    raw_notional_usd: Decimal
    caps_usd: dict
    notional_usd: Decimal
    binding: str
    skip_reason: str | None
    price_decimals: int = 4


def symbol_price_decimals(price_at_t):
    """Native instrument precision for a scanned symbol: 4 for every mover symbol.

    Below 1 USD quotes, limits and fills move in 0.0001 steps, and a mover scanned
    above 1 USD can fall below it within the trial (X4's stop alone reaches it for any
    entry up to about 1.17 USD). A 2-decimal instrument cannot carry such a fill: the
    native adapter refuses a fill price finer than its instrument
    (execution_price_precision_requires_reconciliation). The pricing functions still
    use the 0.01 tick at or above 1 USD, as Alpaca and the ledger's price-increment
    check require; NautilusTrader accepts those coarser prices on a 4-decimal
    instrument. ``price_at_t`` is unused; the signature is kept for the plan's callers."""
    return 4


def size_symbols(symbols, *, equity, leverage, gross_budget, entry_cap, allowance):
    """Deterministic per-symbol entry notionals, in scan rank order.

    notional_i = equity x L_i / 5 with L_i = min(L, 1) below 5 USD, capped at 1% of
    dollar_volume_at_t, 10% of entry_bar_dollar_volume (when supplied), the mover entry
    cap and the remaining gross budget. A symbol whose scan price times the appreciation
    allowance exceeds the entry cap is skipped. Exits are bounded by the ledger's
    per-order cap instead, at least EXIT_HEADROOM_FACTOR times the entry cap (checked at
    config load), so one share of an entered leg stays sellable through a rise of about
    EXIT_HEADROOM_FACTOR x allowance (a share costs at most its buy limit, up to the entry
    limit cap above entry cap / allowance)."""
    result, allocated = [], ZERO
    with localcontext() as context:
        context.prec = 40
        for item in symbols:
            leverage_i = min(leverage, LOW_PRICE_MAX_LEVERAGE) if item.price_at_t < LOW_PRICE_USD else leverage
            raw = (D(equity) * leverage_i / SLOTS).quantize(CENT, rounding=ROUND_FLOOR)
            caps = {"dollar_volume_1pct": (item.dollar_volume_at_t * DOLLAR_VOLUME_CAP_FRACTION).quantize(
                        CENT, rounding=ROUND_FLOOR),
                    "entry_bar_10pct": (None if item.entry_bar_dollar_volume is None else
                                        (item.entry_bar_dollar_volume * ENTRY_BAR_CAP_FRACTION).quantize(
                                            CENT, rounding=ROUND_FLOOR)),
                    "max_entry_notional": D(entry_cap),
                    "gross_remaining": max(ZERO, D(gross_budget) - allocated)}
            binding, notional = "formula", raw
            for name, cap in caps.items():
                if cap is not None and cap < notional:
                    binding, notional = name, cap
            notional = max(ZERO, notional.quantize(CENT, rounding=ROUND_FLOOR))
            skip = None
            if leverage_i <= 0:
                skip = "leverage_zero"
            elif item.price_at_t * D(allowance) > D(entry_cap):
                skip = "price_exceeds_entry_headroom"
            elif notional < item.price_at_t:
                skip = "notional_below_one_share"
            if skip is None:
                allocated += notional
            else:
                notional = ZERO
            result.append(SymbolSizing(item, leverage_i, raw, caps, notional, binding, skip,
                                       symbol_price_decimals(item.price_at_t)))
    return tuple(result)


# ---------------------------------------------------------------------------
# Timing and plan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Timing:
    trial_start: float
    entry_deadline: float
    entry_timeout_seconds: float
    exit_timeout_seconds: float
    hard_flatten_at: float
    sell_window_end: float
    x1_at: float | None
    x2_hold_seconds: float


def plan_timing(settings, limits, *, t0, session_date):
    """Entries run from t0 for ``entry_window_seconds``; the ledger admits sells until
    t0 + trial_seconds + cleanup_seconds. The hard flatten is the earlier of the
    configured trial end (ET, on the scan's session date) and that sell-window end
    less ``flatten_reserve_seconds``, so the flatten always has time to complete."""
    sell_window_end = t0 + limits.trial_seconds + limits.cleanup_seconds
    trial_end = et_epoch(session_date, settings.trial_end_et)
    hard_flatten = min(trial_end, sell_window_end - settings.flatten_reserve_seconds)
    entry_deadline = t0 + settings.entry_window_seconds
    if hard_flatten <= entry_deadline + settings.entry_timeout_seconds:
        raise MoverRefusal("mover_window_too_short")
    x1_at = None
    if settings.exit_rule == "X1":
        # C26: the study's close is the session's regular close (13:00 on early closes); X1 fires two
        # minutes before it, and a plan whose hard flatten comes first can never reach X1.
        close = _rth_close_time(date.fromisoformat(session_date) if isinstance(session_date, str) else session_date)
        x1_at = et_epoch(session_date, dtime(close.hour, close.minute)) - (_seconds_of_day(RTH_CLOSE_ET) - _seconds_of_day(X1_FLATTEN_AT_ET))
        if hard_flatten <= x1_at:
            raise MoverRefusal("mover_x1_unreachable")
    return Timing(t0, entry_deadline, float(settings.entry_timeout_seconds), float(settings.exit_timeout_seconds),
                  hard_flatten, sell_window_end, x1_at, float(X2_HOLD_SECONDS))


@dataclass(frozen=True)
class MoverPlan:
    trial_id: str
    evidence_class: str
    rule: Rule
    exit_rule: str
    entry_cap_bps: Decimal
    exit_cap_bps: Decimal
    max_exit_orders_per_symbol: int
    max_entry_notional_usd: Decimal
    ledger_max_order_notional_usd: Decimal
    appreciation_allowance: Decimal
    gross_guard_usd: Decimal
    timing: Timing
    session: SessionPlan
    regime_factor: Decimal
    regime_source: str
    leverage: Decimal
    engine_leverage_multiple: Decimal
    sizing_equity_usd: Decimal
    gross_budget_usd: Decimal
    scan_sha256: str
    scan_time: float
    symbols: tuple

    def symbol_names(self):
        return tuple(s.scan.symbol for s in self.symbols)


def build_plan(settings, limits, scan, session, *, trial_id, evidence_class, t0, equity,
               engine_leverage_multiple=D(1), timing=None):
    """Combine a validated scan, the session plan and the ledger caps into a MoverPlan.

    ``engine_leverage_multiple`` is the ledger's own ceiling on gross/equity at t0
    (1 without a leverage policy; ``LeveragePolicy.envelope`` otherwise), so planned
    entries never exceed what ``safety.Ledger.reserve_intent`` admits. Entries use at
    most ``max_gross_exposure_usd / appreciation_allowance``: the ledger halts the
    whole lane when marked gross exposure exceeds its cap, so rising positions need
    headroom. Each entry is capped at ``settings.max_entry_notional_usd``; the ledger's
    per-order cap is kept on the plan for the receipt. ``timing`` overrides the real
    schedule only for synthetic runs."""
    if evidence_class not in EVIDENCE_CLASSES:
        raise MoverRefusal("invalid_evidence_class")
    if type(trial_id) is not str or not re.fullmatch(r"[a-z0-9-]{1,24}", trial_id):
        raise MoverRefusal("invalid_trial_id")
    leverage = ZERO if session.paused else leverage_multiple(session.rung, scan.regime_factor, session.drawdown_factor)
    equity = D(equity)
    budget = max(ZERO, min(limits.max_gross_exposure_usd / settings.appreciation_allowance,
                           equity * D(engine_leverage_multiple))).quantize(CENT, rounding=ROUND_FLOOR)
    sizing = size_symbols(scan.symbols, equity=equity, leverage=leverage, gross_budget=budget,
                          entry_cap=settings.max_entry_notional_usd, allowance=settings.appreciation_allowance)
    timing = timing or plan_timing(settings, limits, t0=t0, session_date=scan.session_date)
    guard = (limits.max_gross_exposure_usd * settings.gross_guard_fraction).quantize(CENT, rounding=ROUND_FLOOR)
    return MoverPlan(trial_id, evidence_class, settings.rule, settings.exit_rule, settings.entry_cap_bps,
                     settings.exit_cap_bps, settings.max_exit_orders_per_symbol, settings.max_entry_notional_usd,
                     limits.max_order_notional_usd, settings.appreciation_allowance,
                     guard, timing, session, scan.regime_factor, scan.regime_source, leverage,
                     D(engine_leverage_multiple), equity, budget, scan.sha256, scan.scan_time, sizing)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def tick_size(price, decimals=4):
    """Alpaca/ledger price increment: 0.01 at or above 1 USD, 0.0001 below; always 0.01
    for a 2-decimal instrument."""
    return D("0.01") if decimals == 2 or price >= 1 else D("0.0001")


def price_text(price):
    """Order price text; limits are already quantized to their tick by the functions below."""
    return format(D(price), "f")


def buy_limit_price(ask, cap_bps, decimals=4):
    """Marketable buy limit: ask x (1 + cap), rounded DOWN to the tick so the cap is
    never exceeded. None when that rounding would fall below the ask."""
    ask, cap = D(ask), D(cap_bps)
    if ask <= 0:
        return None
    raw = ask * (1 + cap / 10000)
    tick = tick_size(raw, decimals)
    limit = (raw / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    limit = limit.quantize(tick_size(limit, decimals))
    return limit if limit >= ask and limit > 0 else None


def sell_limit_price(bid, cap_bps, decimals=4):
    """Marketable sell limit for a simulated stop or exit: bid x (1 - cap), rounded UP to
    the tick so the sale is never priced below the cap, and never above the bid rounded
    DOWN to the tick, so it stays marketable. The second bound only binds for a 2-decimal
    instrument quoted below 1 USD in sub-penny increments, where no whole cent lies
    between the cap and the bid: bid 0.9349 with a 50 bps cap gives 0.9302, which rounds
    up to 0.94, above the bid; the limit is 0.93 (52 bps below that bid). None when not
    positive (a 2-decimal bid below one cent)."""
    bid, cap = D(bid), D(cap_bps)
    raw = bid * (1 - cap / 10000)
    if raw <= 0:
        return None
    tick = tick_size(raw, decimals)
    limit = (raw / tick).to_integral_value(rounding=ROUND_CEILING) * tick
    bid_tick = tick_size(bid, decimals)
    limit = min(limit, (bid / bid_tick).to_integral_value(rounding=ROUND_FLOOR) * bid_tick)
    if limit <= 0:
        return None
    return limit.quantize(tick_size(limit, decimals))


def whole_shares(value):
    return int(D(value).to_integral_value(rounding=ROUND_FLOOR)) if value > 0 else 0


def spread_bps(bid, ask):
    """The ledger's own spread formula (safety.Ledger._check_quote)."""
    return (D(ask) - D(bid)) * 10000 / ((D(ask) + D(bid)) / 2)


# ---------------------------------------------------------------------------
# Exit rules
# ---------------------------------------------------------------------------

def rule_exit_reason(exit_rule, *, now, bid, entry_price, running_high, first_fill_at, timing):
    """The protocol exit that fires now, or None. X1: the official-close flatten time.
    X2: 60 minutes after the first entry fill. X3: the bid at or below 0.85 x the
    running high since entry. X4: the bid at or below 0.85 x or at or above 1.50 x the
    entry price."""
    if exit_rule == "X1":
        return "x1_close" if timing.x1_at is not None and now >= timing.x1_at else None
    if exit_rule == "X2":
        return "x2_time" if first_fill_at is not None and now >= first_fill_at + timing.x2_hold_seconds else None
    if bid is None:
        return None
    if exit_rule == "X3":
        return "x3_trail" if running_high is not None and D(bid) <= X3_TRAIL_FRACTION * D(running_high) else None
    if exit_rule == "X4" and entry_price is not None:
        if D(bid) <= X4_STOP_FRACTION * D(entry_price):
            return "x4_stop"
        if D(bid) >= X4_TARGET_FRACTION * D(entry_price):
            return "x4_target"
    return None


# ---------------------------------------------------------------------------
# Order state machine
# ---------------------------------------------------------------------------

@dataclass
class OrderRecord:
    client_id: str
    symbol: str
    side: str
    qty: Decimal
    limit_price: Decimal
    reason: str
    created: float
    reference_price: Decimal
    accepted_at: float | None = None
    broker_ref: str | None = None
    fills: list = field(default_factory=list)
    status: str = "submitted"
    terminal: bool = False
    cancel_requested: bool = False
    cancel_reason: str | None = None
    detail: str | None = None
    # Refused before any broker request (no ledger intent was reserved, or it was proven
    # not sent); such an exit is not charged to the leg's exit budget.
    pre_wire: bool = False

    @property
    def filled_qty(self):
        return sum((qty for _, qty, _ in self.fills), ZERO)

    @property
    def average_fill_price(self):
        filled = self.filled_qty
        if not filled:
            return None
        return sum((qty * price for _, qty, price in self.fills), ZERO) / filled

    def receipt(self):
        average = self.average_fill_price
        return {"client_order_id": self.client_id, "broker_order_ref": self.broker_ref, "side": self.side,
                "qty": text(self.qty), "limit_price": price_text(self.limit_price), "reason": self.reason,
                "reference_price": text(self.reference_price), "submitted_at": _iso(self.created),
                "accepted_at": _iso(self.accepted_at), "status": self.status, "detail": self.detail,
                "cancel_requested": self.cancel_requested, "cancel_reason": self.cancel_reason,
                "pre_wire_refusal": self.pre_wire,
                "fills": [{"at": _iso(at), "qty": text(qty), "price": text(price)} for at, qty, price in self.fills],
                "filled_qty": text(self.filled_qty),
                "average_fill_price": None if average is None else text(average.quantize(D("0.000001")))}


def _iso(epoch):
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).isoformat()


@dataclass
class Leg:
    sizing: SymbolSizing
    state: str = "waiting_entry"
    skip_reason: str | None = None
    wait_reason: str | None = None
    entry: OrderRecord | None = None
    exits: list = field(default_factory=list)
    first_fill_at: float | None = None
    running_high: Decimal | None = None
    exit_reason: str | None = None
    exit_triggered_at: float | None = None
    exit_blocked: str | None = None
    exit_wait_reason: str | None = None
    exit_budget_from: int = 0
    exit_retry_at: float | None = None
    entry_ask: Decimal | None = None
    entry_notional_usd: Decimal | None = None
    entry_leverage_i: Decimal | None = None
    entry_qty_binding: str | None = None
    closed_at: float | None = None


@dataclass(frozen=True)
class Action:
    kind: str  # "submit" or "cancel"
    client_id: str
    record: OrderRecord | None = None


class MoverBook:
    """Per-symbol entry/exit state machine. Pure: it reads positions and quotes through
    the injected callables and returns actions; the native strategy executes them.

    Invariants: at most one buy per symbol for the whole trial (never re-priced, never
    re-sent after a refusal); at most one open order per symbol, so a sell is never
    sent while that symbol's buy is open (a wash-trade refusal would stop the run);
    exits are marketable limit sells at bid x (1 - cap) in every session because the
    transport only carries limit/DAY orders, re-priced after ``exit_timeout_seconds``
    and chunked to the ledger's per-order caps (buys to the mover entry cap); a latched
    force reason (kill switch, risk halt, transport gap, hard flatten, ...) cancels open
    buys and flattens, in the evaluation that latched it.

    Exit budget: no sell is sent while ``halted(symbol)`` (default: the quote's own halted
    flag; the runner passes Controller.is_halted, the status stream and startup seed only,
    so the quote's best-effort condition flag blocks entries but never exits), a pre-wire
    refusal is retried after PRE_WIRE_RETRY_SECONDS without being charged, a latched force
    reason grants each leg one fresh budget, and a leg that exhausts its budget before any
    force latches the book-wide force ``exit_orders_exhausted`` (or
    ``exit_refusals_exhausted``), so every leg flattens through the book first.
    ``handoff_reason`` then tells the runner when to stop the native loop and leave the
    residual to recovery.recover.
    """

    def __init__(self, plan, *, positions, quote, limits, trial_id, existing_client_ids=(), event_sink=None,
                 halted=None):
        self.plan = plan
        self._positions = positions
        self._quote = quote
        self._halted = halted or (lambda symbol: bool(getattr(self._quote(symbol), "halted", False)))
        self.limits = limits
        self.prefix = f"mvr-{trial_id}-"
        self.sequence = max((int(cid[len(self.prefix):]) for cid in existing_client_ids
                             if cid.startswith(self.prefix) and cid[len(self.prefix):].isdigit()), default=0)
        self.orders = {}
        self.legs = {item.scan.symbol: Leg(sizing=item) for item in plan.symbols}
        for leg in self.legs.values():
            if item_skip := leg.sizing.skip_reason:
                leg.state, leg.skip_reason = "skipped", item_skip
        self.force_reason = None
        self.force_at = None
        self.events = event_sink or (lambda event: None)
        self._held_total = None      # held quantity at the previous evaluation
        self._progress_at = None     # last evaluation that saw the held quantity fall

    # -- inputs ------------------------------------------------------------
    def set_force(self, reason, now):
        if self.force_reason is None and reason:
            self.force_reason, self.force_at = str(reason), now
            for leg in self.legs.values():
                # One fresh exit budget per leg for the flatten.
                leg.exit_budget_from = len(leg.exits)
                if leg.exit_blocked in EXIT_BUDGET_EXHAUSTED:
                    leg.exit_blocked = None
            self.events({"type": "mover_force", "reason": self.force_reason, "at": now})

    def order(self, client_id):
        return self.orders.get(client_id)

    def open_orders(self, symbol=None):
        return [o for o in self.orders.values() if not o.terminal and (symbol is None or o.symbol == symbol)]

    def on_accepted(self, client_id, at, reference=None):
        record = self.orders.get(client_id)
        if record is not None and record.accepted_at is None:
            record.accepted_at = at
            record.broker_ref = record.broker_ref or reference
            if record.status == "submitted":
                record.status = "accepted"

    def on_fill(self, client_id, at, qty, price, reference=None):
        record = self.orders.get(client_id)
        if record is None:
            return
        qty, price = D(qty), D(price)
        record.fills.append((at, qty, price))
        record.broker_ref = record.broker_ref or reference
        if record.accepted_at is None:
            record.accepted_at = at
        record.status = "filled" if record.filled_qty >= record.qty else "partially_filled"
        leg = self.legs.get(record.symbol)
        if leg is not None and record.side == "buy":
            if leg.first_fill_at is None:
                leg.first_fill_at = at
            leg.running_high = price if leg.running_high is None else max(leg.running_high, price)
        if record.filled_qty >= record.qty:
            self.on_terminal(client_id, "filled")

    def on_terminal(self, client_id, status, detail=None, *, pre_wire=False, at=None):
        """``pre_wire``: the caller proved the order was refused before any broker request
        (the ledger holds no intent for it, or holds it as not_sent). Such a sell is not
        charged to the exit budget and is retried after PRE_WIRE_RETRY_SECONDS from ``at``."""
        record = self.orders.get(client_id)
        if record is None or record.terminal:
            return
        record.terminal = True
        record.status = status
        record.detail = bounded_detail(detail) if detail is not None else record.detail
        record.pre_wire = bool(pre_wire) and not record.fills and record.accepted_at is None
        leg = self.legs.get(record.symbol)
        if leg is None:
            return
        if record.side == "buy" and leg.state == "entry_open":
            leg.state = "holding" if record.filled_qty > 0 else "no_fill"
        if record.side == "sell" and record.pre_wire:
            leg.exit_retry_at = (record.created if at is None else at) + PRE_WIRE_RETRY_SECONDS

    def on_cancel_rejected(self, client_id):
        record = self.orders.get(client_id)
        if record is not None and not record.terminal:
            record.cancel_requested = False

    # -- evaluation --------------------------------------------------------
    def _fresh(self, quote, now):
        return (quote is not None
                and -CLOCK_TOLERANCE_SECONDS <= now - quote.timestamp <= self.limits.quote_max_age_seconds)

    def _next_client_id(self):
        self.sequence += 1
        return f"{self.prefix}{self.sequence:07d}"

    def _guard_symbol(self, positions):
        """The largest held position once marked gross exposure (the ledger's own
        max(average cost, ask) x qty, plus open buy notional) reaches the guard, else None."""
        total, largest, largest_value = ZERO, None, ZERO
        for symbol, position in positions.items():
            if position.qty <= 0 or symbol not in self.legs:
                continue
            quote = self._quote(symbol)
            ask = quote.ask if quote is not None else position.average_cost
            value = position.qty * max(position.average_cost, D(ask))
            total += value
            if value > largest_value:
                largest, largest_value = symbol, value
        for record in self.open_orders():
            if record.side == "buy":
                total += (record.qty - record.filled_qty) * record.limit_price
        return largest if largest is not None and total >= self.plan.gross_guard_usd else None

    def evaluate(self, now, *, entries_enabled, symbols=None):
        """The actions for ``symbols`` (every leg by default) at ``now``.

        Cancels and exits come first, for every leg in scope, reading the force reason per
        leg. A force that latches during that pass (an exhausted exit budget, in ``_exit``)
        sends every leg through it once more, so the latch cancels open buys and flattens
        every leg in this same evaluation: legs evaluated before it, and legs outside
        ``symbols``, included. Entries come last, under the force as it then stands, so no
        buy is sent in an evaluation that latched a force (none is sent and canceled in
        one batch either)."""
        force_before = self.force_reason  # read before the hard-flatten latch, so that latch also sweeps every leg
        if self.force_reason is None and now >= self.plan.timing.hard_flatten_at:
            self.set_force("hard_flatten", now)
        positions = self._positions()
        self._note_progress(positions, now)
        guard = self._guard_symbol(positions)
        scope = tuple(symbols) if symbols is not None else tuple(self.legs)
        actions = []
        for symbol in scope:
            actions += self._manage(symbol, now, positions, guard)
        if force_before is None and self.force_reason is not None:
            scope = tuple(self.legs)
            for symbol in scope:
                actions += self._manage(symbol, now, positions, guard)
        for symbol in scope:
            leg = self.legs.get(symbol)
            if leg is not None and leg.state == "waiting_entry":
                quote = self._quote(symbol)
                action = self._entry(leg, symbol, quote, self._fresh(quote, now), positions, now,
                                     self.force_reason, entries_enabled)
                if action is not None:
                    actions.append(action)
        return actions

    def _manage(self, symbol, now, positions, guard):
        """One leg's cancels, exit trigger and exit order (no entry), under the force
        reason as it stands now: an earlier leg's ``_exit`` may have latched one."""
        leg = self.legs.get(symbol)
        if leg is None:
            return []
        actions = []
        force = self.force_reason
        quote = self._quote(symbol)
        fresh = self._fresh(quote, now)
        position = positions.get(symbol)
        held = position.qty if position is not None and position.qty > 0 else ZERO
        if held > 0 and leg.first_fill_at is not None and fresh:
            bid = D(quote.bid)
            leg.running_high = bid if leg.running_high is None else max(leg.running_high, bid)
        actions += self._cancels(leg, symbol, now, force)
        if held > 0:
            if leg.exit_reason is None:
                reason = force or ("gross_cap_guard" if guard == symbol else None)
                if reason is None and fresh and position is not None:
                    reason = rule_exit_reason(self.plan.exit_rule, now=now, bid=D(quote.bid),
                                              entry_price=position.average_cost, running_high=leg.running_high,
                                              first_fill_at=leg.first_fill_at, timing=self.plan.timing)
                if reason is not None:
                    leg.exit_reason, leg.exit_triggered_at = reason, now
                    self.events({"type": "mover_exit_triggered", "symbol": symbol, "reason": reason, "at": now})
                    actions += self._cancels(leg, symbol, now, force)
            if leg.exit_reason is not None and not self.open_orders(symbol):
                leg.exit_wait_reason = self._exit_wait(leg, self._halted(symbol), fresh, now)
                if leg.exit_wait_reason is None:
                    action = self._exit(leg, symbol, quote, held, now)
                    if action is not None:
                        actions.append(action)
        elif leg.state in ("holding", "exiting") and not self.open_orders(symbol):
            leg.state, leg.closed_at = "closed", leg.closed_at or now
        return actions

    def _note_progress(self, positions, now):
        held = sum((p.qty for s, p in positions.items() if s in self.legs and p.qty > 0), ZERO)
        if self._held_total is not None and held < self._held_total:
            self._progress_at = now
        self._held_total = held

    @staticmethod
    def _exit_wait(leg, halted, fresh, now):
        """Why a triggered exit is not sent now (never charged to the budget), or None."""
        if not fresh:
            return "no_fresh_quote"
        if halted:
            return "quote_halted"   # a limit sell cannot fill during a halt; wait for it to lift
        if leg.exit_retry_at is not None and now < leg.exit_retry_at:
            return "pre_wire_refusal_backoff"
        return None

    def handoff_reason(self, now):
        """Why the runner should stop the native loop and leave every residual to
        recovery.recover, or None.

        Only once a force reason has latched (every leg is then flattening through the
        book) and while a position or an open order remains:

        - ``exits_blocked``: every held leg's exits are blocked with nothing open for it
          (budget exhausted after the force's fresh budget, a limit that is not positive, or
          one share above the ledger's per-order cap);
        - ``no_exit_progress``: the held quantity has not fallen for HANDOFF_EXIT_TIMEOUTS
          exit timeouts since the latch or the last fill, which covers exits resting
          unfilled, refused, waiting on a halt, or impossible without a fresh quote.

        Before a force, a blocked leg keeps retrying on every evaluation and the other legs
        keep their rules: recovery stops at its first failed symbol, so an early hand-off
        could leave sellable legs unsold."""
        if self.force_reason is None:
            return None
        held = [s for s, p in self._positions().items() if s in self.legs and p.qty > 0]
        if not held and not self.open_orders():
            return None
        if held and all(self.legs[s].exit_blocked is not None and not self.open_orders(s) for s in held):
            return "exits_blocked"
        since = self.force_at if self._progress_at is None else max(self.force_at, self._progress_at)
        if now - since >= HANDOFF_EXIT_TIMEOUTS * self.plan.timing.exit_timeout_seconds:
            return "no_exit_progress"
        return None

    def _cancels(self, leg, symbol, now, force):
        """Cancels for one leg. A resting exit is re-priced after the exit timeout,
        except while the symbol is halted (a trading halt, LULD pause or quotation-only
        period; ``halted(symbol)``): a limit sell cannot fill then, and a cancel and
        re-send every exit timeout would spend the exit budget (20 orders in about 200 s
        against 5-10 min pauses). It rests; re-pricing resumes once the symbol trades."""
        actions = []
        halted = self._halted(symbol)
        for record in self.open_orders(symbol):
            if record.cancel_requested:
                continue
            why = None
            if record.side == "buy":
                if force:
                    why = "force:" + force
                elif leg.exit_reason is not None:
                    why = "exit_triggered"
                elif now - record.created >= self.plan.timing.entry_timeout_seconds:
                    why = "entry_timeout"
            elif now - record.created >= self.plan.timing.exit_timeout_seconds and not halted:
                why = "exit_reprice"
            if why is not None:
                record.cancel_requested, record.cancel_reason = True, why
                actions.append(Action("cancel", record.client_id))
                self.events({"type": "mover_cancel", "client_id": record.client_id, "why": why, "at": now})
        return actions

    def _skip(self, leg, symbol, reason, now):
        leg.state, leg.skip_reason = "skipped", reason
        self.events({"type": "mover_entry_skipped", "symbol": symbol, "reason": reason, "at": now})

    def _entry(self, leg, symbol, quote, fresh, positions, now, force, entries_enabled):
        if force:
            self._skip(leg, symbol, "force:" + force, now)
            return None
        if now >= self.plan.timing.entry_deadline:
            self._skip(leg, symbol, leg.wait_reason or "entry_window_elapsed", now)
            return None
        if not entries_enabled:
            leg.wait_reason = "entries_not_enabled"
            return None
        if not fresh:
            leg.wait_reason = "no_fresh_quote"
            return None
        if getattr(quote, "halted", False):
            leg.wait_reason = "quote_halted"
            return None
        bid, ask = D(quote.bid), D(quote.ask)
        if bid <= 0 or ask < bid or spread_bps(bid, ask) > self.limits.max_spread_bps:
            leg.wait_reason = "spread_exceeds_cap"
            return None
        for held_symbol, position in positions.items():
            if position.qty > 0 and not self._fresh(self._quote(held_symbol), now):
                leg.wait_reason = "held_mark_stale"
                return None
        limit = buy_limit_price(ask, self.plan.entry_cap_bps, leg.sizing.price_decimals)
        if limit is None:
            self._skip(leg, symbol, "entry_cap_below_tick", now)
            return None
        entry_cap = self.plan.max_entry_notional_usd
        if ask * self.plan.appreciation_allowance > entry_cap:
            self._skip(leg, symbol, "price_exceeds_entry_headroom", now)
            return None
        notional, leverage_i = leg.sizing.notional_usd, leg.sizing.leverage_i
        if ask < LOW_PRICE_USD and leverage_i > LOW_PRICE_MAX_LEVERAGE:
            leverage_i = LOW_PRICE_MAX_LEVERAGE
            notional = min(notional, (self.plan.sizing_equity_usd * leverage_i / SLOTS).quantize(
                CENT, rounding=ROUND_FLOOR))
        bounds = {"notional": whole_shares(notional / limit), "max_entry_notional": whole_shares(entry_cap / limit),
                  "max_order_qty": int(self.limits.effective_max_order_qty(limit, quote_price=ask))}
        binding = min(bounds, key=lambda name: bounds[name])
        quantity = bounds[binding]
        if quantity < 1:
            self._skip(leg, symbol, "notional_below_one_share", now)
            return None
        record = OrderRecord(self._next_client_id(), symbol, "buy", D(quantity), limit, "entry", now, ask)
        self.orders[record.client_id] = record
        leg.entry, leg.state, leg.wait_reason = record, "entry_open", None
        leg.entry_ask, leg.entry_notional_usd, leg.entry_leverage_i = ask, notional, leverage_i
        leg.entry_qty_binding = binding
        self.events({"type": "mover_entry_submitted", "symbol": symbol, "client_id": record.client_id,
                     "qty": quantity, "limit_price": price_text(limit), "ask": text(ask), "at": now})
        return Action("submit", record.client_id, record)

    def _block_exit(self, leg, symbol, reason, now):
        if leg.exit_blocked != reason:
            leg.exit_blocked = reason
            self.events({"type": "mover_exit_blocked", "symbol": symbol, "reason": reason, "at": now})

    def _exit(self, leg, symbol, quote, held, now):
        budget = leg.exits[leg.exit_budget_from:]
        refused = sum(1 for record in budget if record.pre_wire)
        exhausted = None
        if len(budget) - refused >= self.plan.max_exit_orders_per_symbol:
            exhausted = "exit_orders_exhausted"
        elif refused >= self.plan.max_exit_orders_per_symbol:
            exhausted = "exit_refusals_exhausted"
        if exhausted is not None:
            self._block_exit(leg, symbol, exhausted, now)
            if self.force_reason is None:
                # Flatten every leg through the book (one fresh budget each) before any
                # hand-off: recovery stops at its first failed symbol.
                self.set_force(exhausted, now)
            return None
        bid = D(quote.bid)
        limit = sell_limit_price(bid, self.plan.exit_cap_bps, leg.sizing.price_decimals)
        if limit is None:
            self._block_exit(leg, symbol, "exit_price_not_positive", now)
            return None
        # The ledger's per-order caps bound sells too (not the mover entry cap), so an exit is
        # chunked to them; one share above them is unsellable by any engine order.
        per_order = self.limits.max_order_notional_usd
        chunk = min(whole_shares(held), whole_shares(per_order / limit),
                    int(self.limits.effective_max_order_qty(limit, quote_price=bid)))
        if chunk < 1:
            self._block_exit(leg, symbol, EXIT_SHARE_BLOCKED, now)
            return None
        record = OrderRecord(self._next_client_id(), symbol, "sell", D(chunk), limit, leg.exit_reason, now, bid)
        self.orders[record.client_id] = record
        leg.exits.append(record)
        leg.state, leg.exit_blocked = "exiting", None
        self.events({"type": "mover_exit_submitted", "symbol": symbol, "client_id": record.client_id,
                     "qty": chunk, "limit_price": price_text(limit), "bid": text(bid), "reason": leg.exit_reason,
                     "at": now})
        return Action("submit", record.client_id, record)

    # -- outputs -----------------------------------------------------------
    def complete(self):
        """Every leg is skipped, unfilled or closed and no order is open."""
        return (not self.open_orders()
                and all(leg.state in ("skipped", "no_fill", "closed") for leg in self.legs.values()))

    def leg_receipts(self):
        rows = []
        for symbol, leg in self.legs.items():
            scan, sizing = leg.sizing.scan, leg.sizing
            rows.append({
                "symbol": symbol, "rank": scan.rank,
                "scan": {"price_at_t": text(scan.price_at_t), "dollar_volume_at_t": text(scan.dollar_volume_at_t),
                         "entry_bar_dollar_volume": text(scan.entry_bar_dollar_volume),
                         "gain_pct_at_t": text(scan.gain_pct_at_t), "news_before_t": scan.news_before_t},
                "sizing": {"leverage_i": text(sizing.leverage_i), "raw_notional_usd": text(sizing.raw_notional_usd),
                           "caps_usd": {k: text(v) for k, v in sizing.caps_usd.items()},
                           "intended_notional_usd": text(sizing.notional_usd), "binding": sizing.binding,
                           "price_decimals": sizing.price_decimals,
                           "entry_notional_usd": text(leg.entry_notional_usd),
                           "entry_leverage_i": text(leg.entry_leverage_i),
                           "entry_qty_binding": leg.entry_qty_binding,
                           "entry_order_notional_usd": (None if leg.entry is None else
                                                        text(leg.entry.qty * leg.entry.limit_price))},
                "state": leg.state, "skip_reason": leg.skip_reason, "last_wait_reason": leg.wait_reason,
                "entry": None if leg.entry is None else leg.entry.receipt(),
                "first_fill_at": _iso(leg.first_fill_at),
                "running_high": text(leg.running_high),
                "exit_reason": leg.exit_reason, "exit_triggered_at": _iso(leg.exit_triggered_at),
                "exit_blocked": leg.exit_blocked, "exit_wait_reason": leg.exit_wait_reason,
                "exit_budget_from": leg.exit_budget_from, "closed_at": _iso(leg.closed_at),
                "exits": [record.receipt() for record in leg.exits]})
        return rows
